"""Invoice emails: plain-text templates (best deliverability) + PDF attachments. Every send is logged against the invoice."""
import logging

from django.utils import timezone

from apps.core.services import log_activity
from . import money
from .models import CompanyBilling, DocumentShare, InvoiceEmail
from .services import BillingError, current_profile, event, mark_sent, site_url

log = logging.getLogger(__name__)

KINDS = {
    "issued": "Invoice issued", "due_soon": "Invoice due soon", "reminder": "Payment reminder", "overdue": "Overdue invoice",
    "payment_received": "Payment received", "payment_failed": "Payment failed", "refund": "Refund processed", "cancelled": "Invoice cancelled / voided",
}
REMINDER_KINDS = ("due_soon", "reminder", "overdue")


def _first(name):
    return (name or "there").split(" ")[0]


def _payment_block(inv):
    lines = []
    link = site_url(inv.public_path)
    for m in inv.methods_snapshot or []:
        if m.get("kind") == "stripe":
            lines.append(f"• {m['label']}: open the invoice page below and press “Pay online”.")
            continue
        parts = [m.get("label", "")]
        for k, lab in (("account_title", "Account title"), ("bank_name", "Bank"), ("account_number", "Account no."), ("iban", "IBAN"), ("raast_id", "Raast ID"), ("swift_bic", "SWIFT/BIC")):
            if m.get(k):
                parts.append(f"   {lab}: {m[k]}")
        if m.get("reference"):
            parts.append(f"   Reference to use: {m['reference']}")
        if m.get("link_url"):
            parts.append(f"   Payment link: {m['link_url']}")
        if m.get("fee_note"):
            parts.append(f"   Note: {m['fee_note']}")
        lines.append("• " + "\n".join(parts))
    block = "\n\n".join(lines)
    return (block + "\n\n" if block else "") + f"Invoice page (details and PDF download): {link}"


def build(kind, inv, payment=None, refund_amount=None):
    cb = CompanyBilling.load()
    co = inv.company()
    sign = f"{co.get('trading_name') or co.get('name') or cb.display_name}" + (f"\n{co['email']}" if co.get("email") else "") + (f"\n{co['phone']}" if co.get("phone") else "") + (f"\n{co['website']}" if co.get("website") else "")
    hi = f"Hi {_first(inv.client_name)},"
    num, bal, tot = inv.number or "", money.fmt(inv.balance, inv.currency), money.fmt(inv.total, inv.currency)
    due = f"{inv.due_date:%d %B %Y}" if inv.due_date else "the due date"
    proj = f" for {inv.project_name}" if inv.project_name else ""
    if kind == "issued":
        subj = f"Invoice {num}{proj} – {tot}"
        body = f"{hi}\n\nPlease find invoice {num}{proj} attached (PDF).\n\nAmount due: {tot}\nDue date: {due}\n\nHow to pay:\n\n{_payment_block(inv)}\n\nIf you have any questions about this invoice, just reply to this email.\n\nKind regards,\n{sign}"
    elif kind == "due_soon":
        subj = f"Invoice {num} is due on {due}"
        body = f"{hi}\n\nA friendly reminder that invoice {num}{proj} ({bal} outstanding) is due on {due}. The invoice is attached again for convenience.\n\n{_payment_block(inv)}\n\nIf you have already paid, please ignore this message and accept our thanks.\n\nKind regards,\n{sign}"
    elif kind == "reminder":
        subj = f"Payment reminder – invoice {num}"
        body = f"{hi}\n\nThis is a reminder about invoice {num}{proj}. The outstanding balance is {bal}, due {due}.\n\n{_payment_block(inv)}\n\nIf you have already paid, please reply with the transfer reference so we can match it.\n\nKind regards,\n{sign}"
    elif kind == "overdue":
        subj = f"Overdue: invoice {num} ({inv.days_overdue} days past due)"
        body = f"{hi}\n\nOur records show invoice {num}{proj} is {inv.days_overdue} day(s) past its due date of {due}. The outstanding balance is {bal}.\n\n{_payment_block(inv)}\n\nIf there is a problem with the invoice or a payment is already on its way, please reply and let us know.\n\nKind regards,\n{sign}"
    elif kind == "payment_received":
        subj = f"Payment received – thank you ({num})"
        amt = money.fmt(payment.amount, payment.currency) if payment else ""
        rest = f"Remaining balance on the invoice: {bal}." if inv.balance > 0 else "This invoice is now paid in full."
        body = f"{hi}\n\nWe have received and verified your payment of {amt} for invoice {num}. {rest}\n\nYour receipt{' ' + payment.receipt_number if payment and payment.receipt_number else ''} is attached.\n\nThank you!\n\n{sign}"
    elif kind == "payment_failed":
        subj = f"Your payment for invoice {num} did not go through"
        body = f"{hi}\n\nThe online payment for invoice {num} was not completed{(': ' + payment.failure_reason) if payment and payment.failure_reason else ''}. No money has been taken for it.\n\nYou can try again, or pay by another method, here:\n\n{_payment_block(inv)}\n\nKind regards,\n{sign}"
    elif kind == "refund":
        amt = money.fmt(refund_amount, inv.currency) if refund_amount is not None else ""
        subj = f"Refund processed – invoice {num}"
        body = f"{hi}\n\nWe have processed a refund of {amt} relating to invoice {num}. Depending on your bank or card issuer it can take several business days to appear.\n\nKind regards,\n{sign}"
    elif kind == "cancelled":
        subj = f"Invoice {num} has been {'voided' if inv.status == 'void' else 'cancelled'}"
        body = f"{hi}\n\nInvoice {num}{proj} has been {'voided' if inv.status == 'void' else 'cancelled'}{(' (' + inv.close_reason + ')') if inv.close_reason else ''}. You do not need to pay it. If a corrected invoice is needed, you will receive it separately.\n\nKind regards,\n{sign}"
    else:
        raise BillingError("Unknown email type.")
    return subj, body


def default_attachments(kind, inv, payment=None):
    if kind in ("issued", "due_soon", "reminder", "overdue"):
        return [{"kind": "invoice_pdf", "id": inv.pk}]
    if kind == "payment_received" and payment and payment.status == "confirmed":
        return [{"kind": "receipt_pdf", "id": payment.pk}]
    return []


def send_invoice_email(inv, user, kind, subject=None, body=None, attach_pdf=True, profile_mode="none", payment=None, to=None, refund_amount=None):
    """Queue the email through the normal mailer (SMTP settings, retries, inbox log). Returns the EmailMessage.
    The message is 'queued' until the SMTP server accepts it – we never call it 'delivered'."""
    from apps.mailer.service import queue_email
    from apps.outbound.services import is_suppressed

    recipient = (to or inv.client_email or "").strip()
    if not recipient:
        raise BillingError("Add the client's email address first.")
    if inv.is_draft:
        raise BillingError("Issue the invoice before emailing it.")
    if kind in REMINDER_KINDS:
        if inv.status not in inv.OPEN or inv.balance <= 0:
            raise BillingError("This invoice is already paid or closed – no reminder is sent.")
        if inv.in_dispute:
            raise BillingError("This invoice is marked as disputed – reminders are paused.")
    if inv.in_dispute and kind == "payment_failed":
        pass
    if is_suppressed(recipient) and kind in REMINDER_KINDS:
        raise BillingError("This address is on the do-not-contact list.")
    s0, b0 = build(kind, inv, payment, refund_amount)
    subject, body = (subject or s0).strip(), (body or b0).strip()
    refs = default_attachments(kind, inv, payment) if attach_pdf else []
    doc = current_profile() if profile_mode in ("attach", "link") else None
    if profile_mode in ("attach", "link") and not doc:
        raise BillingError("No company profile PDF has been selected yet (Billing settings → Company profile).")
    if doc and profile_mode == "attach":
        if not doc.asset_id:
            raise BillingError("The company profile file was removed from the Media library.")
        refs.append({"kind": "media", "id": doc.asset_id})
    elif doc and profile_mode == "link":
        body += f"\n\nCompany profile (secure link, opens in your browser): {site_url(doc.link_path)}"
    try:
        msg = queue_email([recipient], subject, body_text=body, kind="system", lead=inv.lead, created_by=user if getattr(user, "pk", None) else None, attachments=refs)
    except Exception as exc:  # noqa: BLE001 – e.g. attachment missing
        raise BillingError(f"The email could not be prepared: {exc}")
    InvoiceEmail.objects.create(invoice=inv, message=msg, kind=kind, to=recipient[:300], subject=subject[:300], created_by=user if getattr(user, "pk", None) else None)
    event(inv, "email", f"{KINDS[kind]} queued to {recipient}" + (" with PDF" if any(r['kind'].endswith('_pdf') for r in refs) else ""), user)
    if doc:
        DocumentShare.objects.create(document=doc, mode=profile_mode, invoice=inv, email=msg, lead=inv.lead, created_by=user if getattr(user, "pk", None) else None)
    if kind == "issued":
        mark_sent(inv, user)
    log_activity(user, f"invoice.email.{kind}", inv, recipient)
    return msg


def delivery_label(msg):
    """Honest wording: 'Sent' means the SMTP server accepted it – not that the recipient received or read it."""
    if not msg:
        return "Not queued"
    return {"queued": "Queued", "sending": "Sending", "sent": "Accepted by mail server", "failed": "Failed – will retry" if msg.next_attempt_at else "Failed"}.get(msg.status, msg.status)
