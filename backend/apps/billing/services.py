"""Billing business rules. Views and gateways call these; nothing else changes invoice state."""
import logging
from datetime import timedelta
from decimal import Decimal

from django.conf import settings as dj
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone

from apps.core.services import log_activity, notify
from . import money
from .models import (ZERO, CompanyBilling, CompanyDocument, DocumentShare, Invoice, InvoiceEmail, InvoiceEvent, InvoiceItem, NumberSequence, Payment, PaymentMethod,
                     Refund, WebhookEvent)

log = logging.getLogger(__name__)


class BillingError(Exception):
    """A rule was broken. The message is written for the person using the dashboard."""


def event(invoice, kind, detail="", user=None):
    return InvoiceEvent.objects.create(invoice=invoice, kind=kind, detail=detail[:400], actor=user if getattr(user, "pk", None) else None)


def site_url(path=""):
    return f"{dj.SITE_URL}{path}"


# ------------------------------------------------------------------ numbering
def _number(prefix_key, prefix, pad, yearly, start, with_year=True):
    year = timezone.localdate().year
    key = f"{prefix_key}-{year}" if yearly else prefix_key
    first_ever = not NumberSequence.objects.filter(key__startswith=prefix_key).exists()
    at_least = start if (first_ever or NumberSequence.objects.filter(key=key).exists()) else 1
    n = NumberSequence.take(key, at_least)
    return f"{prefix}-{year}-{n:0{pad}d}" if with_year else f"{prefix}-{n:0{pad}d}"


def next_invoice_number(cb=None):
    cb = cb or CompanyBilling.load()
    return _number("invoice", (cb.invoice_prefix or "INV").upper(), cb.number_padding, cb.reset_numbering_yearly, cb.invoice_start_number)


def next_receipt_number(cb=None):
    cb = cb or CompanyBilling.load()
    return _number("receipt", (cb.receipt_prefix or "RCT").upper(), cb.number_padding, cb.reset_numbering_yearly, 1)


# ------------------------------------------------------------------ drafts
def new_draft(user=None, **fields) -> Invoice:
    cb = CompanyBilling.load()
    inv = Invoice(currency=fields.pop("currency", None) or cb.default_currency, tax_percent=fields.pop("tax_percent", cb.default_tax_percent), tax_name=fields.pop("tax_name", None) or (cb.tax_name if cb.default_tax_percent else ""),
                  notes=fields.pop("notes", None) or cb.default_notes, created_by=user, **fields)
    inv.save()
    event(inv, "created", "Draft created", user)
    return inv


def replace_items(invoice, rows):
    invoice.items.all().delete()
    InvoiceItem.objects.bulk_create([InvoiceItem(invoice=invoice, **r) for r in rows])
    invoice.recalc()


def default_methods(currency):
    return [m for m in PaymentMethod.objects.filter(is_enabled=True) if m.accepts(currency) and (not m.is_gateway or m.gateway_ready)]


def problems_for_issue(inv) -> list:
    cb = CompanyBilling.load()
    out = []
    if not (cb.legal_name or cb.trading_name):
        out.append("Add your company name in Billing settings first.")
    if not inv.client_name.strip():
        out.append("Add the client's name.")
    if not inv.items.exists():
        out.append("Add at least one line item.")
    if inv.currency not in cb.currency_list:
        out.append(f"{inv.currency} is not an enabled currency.")
    inv.recalc(save=False)
    if inv.total <= 0:
        out.append("The total must be greater than zero.")
    if not (inv.methods.exists() or default_methods(inv.currency) or cb.payment_instructions.strip()):
        out.append("Enable at least one payment method (or write payment instructions) in Billing settings.")
    if inv.due_date and inv.issue_date and inv.due_date < inv.issue_date:
        out.append("The due date is before the issue date.")
    return out


@transaction.atomic
def issue_invoice(invoice, user, issue_date=None, due_date=None) -> Invoice:
    inv = Invoice.objects.select_for_update().get(pk=invoice.pk)
    if inv.status != Invoice.DRAFT:
        raise BillingError("This invoice has already been issued.")
    if issue_date:
        inv.issue_date = issue_date
    if due_date:
        inv.due_date = due_date
    pr = problems_for_issue(inv)
    if pr:
        raise BillingError(" ".join(pr))
    cb = CompanyBilling.load()
    inv.number = next_invoice_number(cb)
    inv.issue_date = inv.issue_date or timezone.localdate()
    inv.due_date = inv.due_date or inv.issue_date + timedelta(days=cb.payment_terms_days)
    chosen = list(inv.methods.all()) or default_methods(inv.currency)
    inv.methods.set(chosen)
    inv.methods_snapshot = [m.snapshot_for(inv) for m in chosen]
    inv.company_snapshot = cb.snapshot()
    inv.footer = inv.footer or cb.invoice_footer
    inv.terms = inv.terms or cb.payment_instructions
    inv.status, inv.issued_at, inv.issued_by = Invoice.ISSUED, timezone.now(), user
    inv.save()
    event(inv, "issued", f"Issued as {inv.number} · {money.fmt(inv.total, inv.currency)}", user)
    log_activity(user, "invoice.issued", inv, inv.number)
    return inv


def mark_sent(inv, user=None):
    if inv.status == Invoice.ISSUED:
        inv.status, inv.sent_at = Invoice.SENT, timezone.now()
        inv.save(update_fields=["status", "sent_at", "updated_at"])
    elif not inv.sent_at:
        inv.sent_at = timezone.now()
        inv.save(update_fields=["sent_at", "updated_at"])


@transaction.atomic
def close_invoice(invoice, user, status, reason):
    """Cancel (issued by mistake, never needed) or void (replaced / withdrawn). Never possible once money has been received."""
    inv = Invoice.objects.select_for_update().get(pk=invoice.pk)
    if status not in (Invoice.CANCELLED, Invoice.VOID):
        raise BillingError("Invalid action.")
    if inv.status in (Invoice.DRAFT, Invoice.PAID, Invoice.CANCELLED, Invoice.VOID):
        raise BillingError("This invoice cannot be cancelled or voided in its current state.")
    if inv.amount_paid > 0:
        raise BillingError("Payments have been received on this invoice. Refund them first (or leave the invoice open).")
    reason = (reason or "").strip()
    if len(reason) < 3:
        raise BillingError("Please write the reason – it is kept in the audit trail.")
    inv.payments.filter(status__in=[Payment.PENDING, Payment.INITIATED]).update(status=Payment.CANCELLED, failure_reason="Invoice closed")
    inv.status, inv.closed_at, inv.close_reason = status, timezone.now(), reason[:300]
    inv.save(update_fields=["status", "closed_at", "close_reason", "updated_at"])
    event(inv, status, reason, user)
    log_activity(user, f"invoice.{status}", inv, inv.number or "")
    return inv


@transaction.atomic
def revise_invoice(invoice, user):
    """Correct an issued invoice the safe way: the old one is voided (kept for the record) and a new draft copy is created."""
    old = close_invoice(invoice, user, Invoice.VOID, "Revised – replaced by a corrected invoice")
    new = Invoice.objects.create(
        client_name=old.client_name, client_company=old.client_company, client_email=old.client_email, client_phone=old.client_phone, client_address=old.client_address,
        client_country=old.client_country, client_tax_label=old.client_tax_label, client_tax_no=old.client_tax_no, lead=old.lead, prospect=old.prospect, proposal=old.proposal,
        replaces=old, project_name=old.project_name, description=old.description, currency=old.currency, discount=old.discount, tax_percent=old.tax_percent, tax_name=old.tax_name,
        notes=old.notes, terms=old.terms, footer=old.footer, billing_type=old.billing_type, milestone_label=old.milestone_label, created_by=user)
    InvoiceItem.objects.bulk_create([InvoiceItem(invoice=new, description=i.description, detail=i.detail, quantity=i.quantity, unit_price=i.unit_price, unit=i.unit, order=i.order) for i in old.items.all()])
    new.methods.set(old.methods.all())
    new.recalc()
    event(new, "created", f"Draft revision of {old.number}", user)
    return new


# ------------------------------------------------------------------ proposal -> invoice
def proposal_billing(pr):
    """What has already been invoiced against a proposal (cancelled / void invoices don't count)."""
    live = pr.invoices.exclude(status__in=[Invoice.CANCELLED, Invoice.VOID])
    invoiced = live.aggregate(s=Sum("total"))["s"] or ZERO
    return {"invoices": list(live), "invoiced": money.q(invoiced, pr.currency), "remaining": max(money.q(pr.total - invoiced, pr.currency), ZERO)}


@transaction.atomic
def invoice_from_proposal(pr, user, mode="full", percent=None, amount=None, label=""):
    """Create a DRAFT invoice from a won proposal. Nothing is issued or emailed automatically."""
    from apps.outbound.models import Proposal

    pr = Proposal.objects.select_for_update().get(pk=pr.pk)
    if pr.status != Proposal.WON:
        raise BillingError("Only a proposal marked Won can be invoiced.")
    cb = CompanyBilling.load()
    bill = proposal_billing(pr)
    cur = pr.currency
    if bill["remaining"] <= 0:
        raise BillingError("This proposal has already been invoiced in full.")
    if any(i.billing_type == mode and i.billing_type in (Invoice.FULL, Invoice.DEPOSIT, Invoice.FINAL) for i in bill["invoices"]):
        raise BillingError(f"A {mode} invoice already exists for this proposal ({', '.join(i.number or 'draft' for i in bill['invoices'] if i.billing_type == mode)}). Open it instead of creating a duplicate.")
    tax = pr.tax_percent or 0
    base = dict(client_name=pr.client_name, client_company=pr.client_company, client_email=pr.client_email, lead=pr.lead, prospect=pr.prospect, proposal=pr, currency=cur,
                project_name=pr.title, tax_percent=tax, tax_name=cb.tax_name if tax else "", terms=pr.terms, created_by=user, billing_type=mode, milestone_label=label[:120])
    if pr.lead:
        base["client_phone"] = pr.lead.phone or ""
    if mode == Invoice.FULL:
        if bill["invoiced"] > 0:
            raise BillingError("Part of this proposal is already invoiced. Use 'Final payment' for the remainder.")
        inv = Invoice.objects.create(discount=pr.discount, **base)
        InvoiceItem.objects.bulk_create([InvoiceItem(invoice=inv, description=i.description, detail=i.detail, quantity=i.quantity, unit_price=i.unit_price, order=i.order) for i in pr.items.all()])
    else:
        if mode == Invoice.FINAL:
            target_total = bill["remaining"]
            desc = f"Final payment – {pr.title} ({pr.reference})"
        else:
            if percent:
                pct = money.to_dec(percent)
                if not 0 < pct <= 100:
                    raise BillingError("Enter a percentage between 1 and 100.")
                target_total = money.q(pr.total * pct / 100, cur)
                desc = f"{label or ('Deposit' if mode == Invoice.DEPOSIT else 'Milestone')} ({pct.normalize():f}%) – {pr.title} ({pr.reference})"
            else:
                target_total = money.q(money.to_dec(amount), cur)
                desc = f"{label or 'Milestone'} – {pr.title} ({pr.reference})"
        if target_total <= 0:
            raise BillingError("Enter a percentage or an amount.")
        if target_total > bill["remaining"]:
            raise BillingError(f"That is more than what is left to invoice ({money.fmt(bill['remaining'], cur)}).")
        net = money.q(target_total / (1 + Decimal(tax) / 100), cur) if tax else target_total
        inv = Invoice.objects.create(**base)
        InvoiceItem.objects.create(invoice=inv, description=desc[:300], quantity=1, unit_price=net, order=0)
    inv.recalc()
    event(inv, "created", f"Created from proposal {pr.reference} ({inv.get_billing_type_display()})", user)
    log_activity(user, "invoice.from_proposal", inv, pr.reference)
    return inv


# ------------------------------------------------------------------ payments
def refresh_invoice(inv):
    """Recalculate what has been paid from CONFIRMED payments (minus refunds) and move the status accordingly."""
    inv = Invoice.objects.select_for_update().get(pk=inv.pk)
    agg = inv.payments.filter(status=Payment.CONFIRMED).aggregate(a=Sum("amount"), r=Sum("refunded_amount"))
    paid = max(money.q((agg["a"] or ZERO) - (agg["r"] or ZERO), inv.currency), ZERO)
    inv.amount_paid = paid
    if inv.status in (Invoice.ISSUED, Invoice.SENT, Invoice.PARTIAL, Invoice.PAID):
        if inv.total > 0 and paid >= inv.total:
            inv.status = Invoice.PAID
            inv.paid_at = inv.paid_at or timezone.now()
        elif paid > 0:
            inv.status, inv.paid_at = Invoice.PARTIAL, None
        else:
            inv.status, inv.paid_at = (Invoice.SENT if inv.sent_at else Invoice.ISSUED), None
    inv.save(update_fields=["amount_paid", "status", "paid_at", "updated_at"])
    return inv


def _method_fields(method):
    return {"method": method, "method_kind": method.kind if method else "", "method_label": method.label if method else ""}


@transaction.atomic
def record_payment(invoice, user, *, method=None, amount, reference="", paid_on=None, note="", received_currency="", received_amount=None, exchange_rate=None, bank_fee=None,
                   source="staff", verify=False, verification_note=""):
    inv = Invoice.objects.select_for_update().get(pk=invoice.pk)
    if inv.status not in Invoice.OPEN:
        raise BillingError("Payments can only be recorded on an issued, unpaid or partly paid invoice.")
    amt = money.q(amount, inv.currency)
    if amt <= 0:
        raise BillingError("Enter the amount credited to the invoice.")
    if amt > inv.balance:
        raise BillingError(f"That is more than the remaining balance ({money.fmt(inv.balance, inv.currency)}).")
    rc = (received_currency or "").upper()
    if rc and rc != inv.currency:
        if not exchange_rate or money.to_dec(exchange_rate) <= 0:
            raise BillingError(f"The money arrived in {rc} but the invoice is in {inv.currency}. Enter the exchange rate your bank actually used – it is never estimated for you.")
    ref = (reference or "").strip()[:120]
    if ref and inv.payments.filter(reference__iexact=ref, amount=amt).exclude(status__in=[Payment.REJECTED, Payment.CANCELLED, Payment.FAILED]).exists():
        raise BillingError("A payment with the same reference and amount is already recorded on this invoice.")
    p = Payment.objects.create(
        invoice=inv, status=Payment.PENDING, source=source, amount=amt, currency=inv.currency, received_currency=rc if rc and rc != inv.currency else "",
        received_amount=money.q(received_amount, rc or inv.currency) if received_amount not in (None, "") and rc else None,
        exchange_rate=money.to_dec(exchange_rate) if exchange_rate not in (None, "", 0) and rc and rc != inv.currency else None,
        bank_fee=money.q(bank_fee, rc or inv.currency) if bank_fee not in (None, "") else None,
        reference=ref, paid_on=paid_on, note=(note or "")[:400], recorded_by=user if getattr(user, "pk", None) else None, **_method_fields(method))
    event(inv, "payment_recorded", f"{money.fmt(amt, inv.currency)} via {p.method_label or 'unspecified method'}{' · ref ' + ref if ref else ''} – awaiting verification", user)
    log_activity(user, "payment.recorded", p, inv.number or "")
    if verify:
        confirm_payment(p, user, verification_note)
        p.refresh_from_db()
    else:
        notify("invoice", f"Payment to verify: {inv.number}", f"{money.fmt(amt, inv.currency)} reported for {inv.client_name}", "/dashboard/payments/?status=pending", module="payments", level="warning")
    return p


@transaction.atomic
def confirm_payment(payment, user, verification_note="", from_gateway=False):
    p = Payment.objects.select_for_update().get(pk=payment.pk)
    inv = Invoice.objects.select_for_update().get(pk=p.invoice_id)
    if p.status == Payment.CONFIRMED:
        return p  # idempotent
    if p.status in (Payment.REJECTED, Payment.CANCELLED) and not from_gateway:
        raise BillingError("This payment was rejected or cancelled. Record a new one if the money really arrived.")
    if inv.status in (Invoice.CANCELLED, Invoice.VOID, Invoice.DRAFT):
        raise BillingError("This invoice is closed.")
    if not from_gateway:
        if not (verification_note or "").strip():
            raise BillingError("Write how you verified it (e.g. 'Seen on HBL statement, 12 Oct').")
        if p.amount > inv.balance:
            raise BillingError(f"This would overpay the invoice (balance {money.fmt(inv.balance, inv.currency)}).")
    p.status, p.verified_by, p.verified_at = Payment.CONFIRMED, user if getattr(user, "pk", None) else None, timezone.now()
    p.verification_note = (verification_note or ("Confirmed by payment provider (verified webhook)" if from_gateway else ""))[:400]
    p.paid_on = p.paid_on or timezone.localdate()
    p.receipt_number, p.receipt_issued_at = next_receipt_number(), timezone.now()
    p.save()
    event(inv, "payment_confirmed", f"{money.fmt(p.amount, p.currency)} confirmed · receipt {p.receipt_number}", user)
    inv = refresh_invoice(inv)
    log_activity(user, "payment.confirmed", p, inv.number or "")
    overpaid = inv.amount_paid > inv.total
    notify("invoice", f"Payment received: {inv.number}", f"{money.fmt(p.amount, p.currency)} from {inv.client_name}" + (" – OVERPAID, review a refund" if overpaid else ""), f"/dashboard/invoices/{inv.pk}/", module="invoices",
           level="warning" if overpaid else "success")
    return p


@transaction.atomic
def reject_payment(payment, user, reason):
    p = Payment.objects.select_for_update().get(pk=payment.pk)
    if p.status not in (Payment.PENDING, Payment.INITIATED):
        raise BillingError("Only a pending payment can be rejected.")
    if len((reason or "").strip()) < 3:
        raise BillingError("Write why it was rejected (e.g. 'Not found on bank statement').")
    p.status, p.verified_by, p.verified_at, p.verification_note = Payment.REJECTED, user, timezone.now(), reason.strip()[:400]
    p.save()
    event(p.invoice, "payment_rejected", f"{money.fmt(p.amount, p.currency)} rejected: {reason.strip()[:200]}", user)
    log_activity(user, "payment.rejected", p, p.invoice.number or "")
    return p


@transaction.atomic
def refund_payment(payment, user, amount, reason=""):
    p = Payment.objects.select_for_update().get(pk=payment.pk)
    if p.status != Payment.CONFIRMED:
        raise BillingError("Only a confirmed payment can be refunded.")
    amt = money.q(amount, p.currency)
    if amt <= 0 or amt > p.refundable:
        raise BillingError(f"Enter an amount up to {money.fmt(p.refundable, p.currency)}.")
    if len((reason or "").strip()) < 3:
        raise BillingError("Write the reason for the refund.")
    rf = Refund(payment=p, amount=amt, reason=reason.strip()[:300], created_by=user, status=Refund.RECORDED)
    if p.provider:
        from .gateways import get_gateway_by_provider, GatewayError
        gw = get_gateway_by_provider(p.provider)
        if not gw or not gw.configured():
            raise BillingError("The payment provider is not configured, so the refund cannot be sent to it.")
        try:
            res = gw.refund(p, amt, reason)
        except GatewayError as exc:
            raise BillingError(str(exc))
        rf.provider_refund_id, rf.status = res.get("id", ""), Refund.SUCCEEDED if res.get("status") == "succeeded" else Refund.PENDING
    rf.save()
    p.refunded_amount = money.q(p.refunded_amount + amt, p.currency)
    p.save(update_fields=["refunded_amount", "updated_at"])
    event(p.invoice, "refund", f"{money.fmt(amt, p.currency)} refunded on {p.receipt_number}: {reason.strip()[:150]}", user)
    log_activity(user, "payment.refunded", p, f"{amt} {p.currency}")
    refresh_invoice(p.invoice)
    return rf


# ------------------------------------------------------------------ online payment (gateway) + webhooks
def start_checkout(invoice, method, success_url, cancel_url):
    from .gateways import GatewayError, get_gateway

    gw = get_gateway(method)
    if not gw or not gw.configured() or not method.is_enabled:
        raise BillingError("Online payment is not available for this invoice.")
    with transaction.atomic():
        inv = Invoice.objects.select_for_update().get(pk=invoice.pk)
        if inv.status not in Invoice.OPEN or inv.balance <= 0:
            raise BillingError("This invoice has nothing left to pay.")
        if not method.accepts(inv.currency):
            raise BillingError(f"This payment method does not accept {inv.currency}. Please use another method.")
        inv.payments.filter(status=Payment.INITIATED, provider=gw.provider).update(status=Payment.CANCELLED, failure_reason="Replaced by a newer checkout")
        p = Payment.objects.create(invoice=inv, status=Payment.INITIATED, source="gateway", provider=gw.provider, amount=inv.balance, currency=inv.currency, **_method_fields(method))
    try:
        return gw.create_checkout(inv, p, success_url, cancel_url)
    except GatewayError as exc:
        p.status, p.failure_reason = Payment.FAILED, str(exc)[:300]
        p.save(update_fields=["status", "failure_reason", "updated_at"])
        raise BillingError(str(exc))


def process_webhook(gateway, body: bytes, headers) -> str:
    """Returns 'processed' | 'duplicate' | 'ignored'. Raises GatewayError for an invalid signature/payload (→ HTTP 400)."""
    res = gateway.verify_and_parse(body, headers)
    if not res.event_id:
        from .gateways import GatewayError
        raise GatewayError("Event has no id.")
    try:
        ev, created = WebhookEvent.objects.get_or_create(provider=gateway.provider, event_id=res.event_id, defaults={"event_type": res.event_type, "payload": res.raw})
    except IntegrityError:
        return "duplicate"
    if not created and ev.status in ("processed", "ignored"):
        return "duplicate"
    try:
        with transaction.atomic():
            outcome = _apply_webhook(gateway, res)
        ev.status, ev.processed_at, ev.error = ("processed" if outcome else "ignored"), timezone.now(), ""
    except Exception as exc:  # noqa: BLE001 – recorded, provider retries
        log.exception("webhook %s failed", res.event_id)
        ev.status, ev.error = "failed", f"{exc.__class__.__name__}: {exc}"[:300]
        ev.save(update_fields=["status", "error"])
        raise
    ev.save(update_fields=["status", "processed_at", "error"])
    return "processed" if outcome else "ignored"


def _find_payment(gateway, res):
    qs = Payment.objects.select_for_update().filter(provider=gateway.provider)
    if res.payment_id:
        p = qs.filter(pk=res.payment_id).first()
        if p and (not res.session_id or not p.provider_session_id or p.provider_session_id == res.session_id):
            return p
    if res.session_id:
        return qs.filter(provider_session_id=res.session_id).first()
    if res.txn_id:
        return qs.filter(provider_txn_id=res.txn_id).first()
    return None


def _apply_webhook(gateway, res) -> bool:
    if res.action == "ignore":
        return False
    p = _find_payment(gateway, res)
    if res.action == "refunded":
        p = Payment.objects.select_for_update().filter(provider=gateway.provider, provider_txn_id=res.txn_id).first() if res.txn_id else None
        if not p or not res.refund_id or Refund.objects.filter(payment=p, provider_refund_id=res.refund_id).exists():
            return False
        amt = money.from_minor(res.refund_minor or 0, p.currency)
        if amt <= 0 or amt > p.refundable:
            return False
        Refund.objects.create(payment=p, amount=amt, reason="Refund recorded from provider", status=Refund.SUCCEEDED, provider_refund_id=res.refund_id)
        p.refunded_amount = money.q(p.refunded_amount + amt, p.currency)
        p.save(update_fields=["refunded_amount", "updated_at"])
        event(p.invoice, "refund", f"{money.fmt(amt, p.currency)} refunded by the provider", None)
        refresh_invoice(p.invoice)
        return True
    if not p:
        log.warning("webhook %s: no matching payment", res.event_id)
        return False
    if res.action == "paid":
        if p.status == Payment.CONFIRMED:
            return False
        dup = Payment.objects.filter(provider=gateway.provider, provider_txn_id=res.txn_id).exclude(pk=p.pk).exists() if res.txn_id else False
        if dup:
            return False
        p.provider_txn_id = res.txn_id or p.provider_txn_id
        if res.session_id:
            p.provider_session_id = res.session_id
        mismatch = (res.amount_minor is not None and res.amount_minor != money.minor_units(p.amount, p.currency)) or (res.currency and res.currency != p.currency.upper())
        if mismatch:  # real money arrived but not what we asked for: never auto-confirm, send to a human
            p.status, p.failure_reason = Payment.PENDING, "Amount or currency differs from the invoice – verify before confirming."
            p.save()
            notify("invoice", f"Check payment {p.invoice.number}", "The provider reports a different amount/currency than requested.", "/dashboard/payments/?status=pending", module="payments", level="danger")
            return True
        p.save()
        confirm_payment(p, None, from_gateway=True)
        return True
    if res.action in ("failed", "cancelled") and p.status in (Payment.INITIATED, Payment.PENDING):
        p.status = Payment.FAILED if res.action == "failed" else Payment.CANCELLED
        p.failure_reason = res.reason[:300] or ("Checkout expired" if res.action == "cancelled" else "Payment failed")
        p.save(update_fields=["status", "failure_reason", "updated_at"])
        event(p.invoice, "payment_" + res.action, p.failure_reason, None)
        if res.action == "failed" and p.invoice.client_email:
            try:
                from .emails import send_invoice_email
                send_invoice_email(p.invoice, None, "payment_failed", payment=p)
            except Exception:  # noqa: BLE001
                log.exception("failed-payment email not queued")
        return True
    return False


# ------------------------------------------------------------------ company profile document (Media library reuse)
@transaction.atomic
def set_company_profile(asset, user, note=""):
    """Make `asset` (an existing Media-library PDF) the current company profile. Older versions are kept."""
    if asset is None or asset.kind != "document" or not (asset.mime_type == "application/pdf" or asset.file.name.lower().endswith(".pdf")):
        raise BillingError("Choose a PDF from the Media library.")
    cur = CompanyDocument.objects.filter(kind=CompanyDocument.PROFILE, is_current=True).first()
    if cur and cur.asset_id == asset.pk:
        return cur
    last = CompanyDocument.objects.filter(kind=CompanyDocument.PROFILE).order_by("-version").first()
    CompanyDocument.objects.filter(kind=CompanyDocument.PROFILE, is_current=True).update(is_current=False)
    doc = CompanyDocument.objects.create(kind=CompanyDocument.PROFILE, version=(last.version + 1) if last else 1, asset=asset, filename=asset.download_name, size=asset.size, is_current=True, note=note[:300], created_by=user)
    log_activity(user, "profile.set", doc, asset.download_name)
    return doc


def current_profile():
    return CompanyDocument.objects.filter(kind=CompanyDocument.PROFILE, is_current=True).select_related("asset").first()


# ------------------------------------------------------------------ scheduled checks (called from outbound.check_overdue / manage.py)
def billing_checks() -> dict:
    """Overdue alerts to staff + optional client reminders. Never reminds paid / closed / disputed invoices."""
    from .emails import send_invoice_email

    cb = CompanyBilling.load()
    today, now = timezone.localdate(), timezone.now()
    out = {"overdue_alerts": 0, "reminders": 0}
    for inv in Invoice.objects.filter(status__in=Invoice.OPEN, due_date__lt=today):
        if inv.balance <= 0:
            continue
        if not inv.events.filter(kind="overdue_alert").exists():
            event(inv, "overdue_alert", f"Became overdue ({inv.days_overdue} day(s))", None)
            notify("invoice", f"Overdue: {inv.number}", f"{inv.client_name} · {money.fmt(inv.balance, inv.currency)} outstanding", f"/dashboard/invoices/{inv.pk}/", module="invoices", level="danger")
            out["overdue_alerts"] += 1
    if cb.send_reminders:
        for inv in Invoice.objects.filter(status__in=Invoice.OPEN, in_dispute=False).exclude(client_email=""):
            if inv.balance <= 0 or inv.reminder_count >= cb.max_reminders or not inv.due_date:
                continue
            gap = (inv.last_reminder_at is None) or (now - inv.last_reminder_at >= timedelta(days=max(cb.remind_every_days, 1)))
            kind = ""
            if inv.is_overdue and gap:
                kind = "overdue"
            elif not inv.is_overdue and inv.due_date - today <= timedelta(days=cb.remind_before_days) and inv.reminder_count == 0:
                kind = "due_soon"
            if kind:
                try:
                    send_invoice_email(inv, None, kind)
                    Invoice.objects.filter(pk=inv.pk).update(reminder_count=inv.reminder_count + 1, last_reminder_at=now)
                    out["reminders"] += 1
                except Exception:  # noqa: BLE001
                    log.exception("reminder failed for %s", inv.pk)
    return out
