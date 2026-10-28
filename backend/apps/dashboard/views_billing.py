"""Billing screens: invoices, payments & verification, receipts, reports, company billing settings, payment methods, company profile."""
import csv
import logging
import re
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from django import forms
from django.conf import settings as dj
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.billing import emails, money
from apps.billing.gateways import get_gateway
from apps.billing.models import CompanyBilling, CompanyDocument, DocumentShare, Invoice, InvoiceItem, Payment, PaymentMethod, Refund, WebhookEvent
from apps.billing.pdf import invoice_pdf, receipt_pdf
from apps.billing.services import (BillingError, close_invoice, confirm_payment, current_profile, event, invoice_from_proposal, issue_invoice, new_draft, proposal_billing,
                                   problems_for_issue, record_payment, refund_payment, reject_payment, replace_items, revise_invoice, set_company_profile)
from apps.core.models import MediaAsset
from apps.core.sanitize import clean_plain
from apps.core.services import log_activity
from apps.leads.models import Lead
from apps.outbound.models import Proposal, Prospect
from .mixins import needs
from .widgets import MediaPickerWidget

log = logging.getLogger(__name__)
CRUMB = ("Invoices", "/dashboard/invoices/")
HOME = ("Dashboard", "/dashboard/")


def _d(s):
    try:
        return date.fromisoformat(s)
    except (TypeError, ValueError):
        return None


def _err(request, exc):
    messages.error(request, str(exc))


# ================================================================== invoices
def _filtered(request):
    g = request.GET
    qs = Invoice.objects.all()
    if g.get("q"):
        qs = qs.filter(Q(number__icontains=g["q"]) | Q(project_name__icontains=g["q"]) | Q(client_name__icontains=g["q"]) | Q(client_company__icontains=g["q"]))
    if g.get("client"):
        qs = qs.filter(Q(client_name__icontains=g["client"]) | Q(client_company__icontains=g["client"]) | Q(client_email__icontains=g["client"]))
    st = g.get("status")
    if st == "overdue":
        qs = qs.filter(status__in=Invoice.OPEN, due_date__lt=timezone.localdate(), amount_paid__lt=models_total())
    elif st in dict(Invoice.STATUS):
        qs = qs.filter(status=st)
    if g.get("currency"):
        qs = qs.filter(currency=g["currency"].upper())
    if _d(g.get("from")):
        qs = qs.filter(Q(issue_date__gte=_d(g["from"])) | Q(issue_date__isnull=True, created_at__date__gte=_d(g["from"])))
    if _d(g.get("to")):
        qs = qs.filter(Q(issue_date__lte=_d(g["to"])) | Q(issue_date__isnull=True, created_at__date__lte=_d(g["to"])))
    if g.get("method") in dict(PaymentMethod.KINDS):
        qs = qs.filter(Q(payments__method_kind=g["method"]) | Q(methods__kind=g["method"])).distinct()
    return qs


def models_total():
    from django.db.models import F
    return F("total")


@needs("invoices", "view")
def invoices_list(request):
    qs = _filtered(request)
    qd = request.GET.copy()
    qd.pop("page", None)
    page = Paginator(qs.order_by("-created_at", "-id"), 20).get_page(request.GET.get("page"))
    today = timezone.localdate()
    open_qs = Invoice.objects.filter(status__in=Invoice.OPEN)
    out = defaultdict(lambda: {"outstanding": Decimal(0), "overdue": Decimal(0)})
    for r in open_qs.values("currency").annotate(t=Sum("total"), p=Sum("amount_paid")):
        out[r["currency"]]["outstanding"] = r["t"] - r["p"]
    for r in open_qs.filter(due_date__lt=today).values("currency").annotate(t=Sum("total"), p=Sum("amount_paid")):
        out[r["currency"]]["overdue"] = r["t"] - r["p"]
    cb = CompanyBilling.load()
    counts = dict(Invoice.objects.values_list("status").annotate(n=Count("id")))
    return render(request, "dashboard/billing/invoices.html", {
        "page": page, "g": request.GET, "qs": qd.urlencode(), "statuses": Invoice.STATUS, "counts": counts, "total": sum(counts.values()),
        "outstanding": [(c, v["outstanding"], v["overdue"]) for c, v in sorted(out.items()) if v["outstanding"] > 0], "currencies": cb.currency_list, "kinds": PaymentMethod.KINDS,
        "can_create": request.user.can("invoices", "create"), "can_export": request.user.can("invoices", "export"), "pending": Payment.objects.filter(status=Payment.PENDING).count(),
        "page_title": "Invoices", "crumbs": [HOME, ("Billing", ""), ("Invoices", "")],
    })


@needs("invoices", "export")
def invoices_export(request):
    resp = HttpResponse(content_type="text/csv")
    resp["Content-Disposition"] = 'attachment; filename="invoices.csv"'
    w = csv.writer(resp)
    w.writerow(["Number", "Status", "Client", "Company", "Email", "Project", "Currency", "Issue date", "Due date", "Subtotal", "Discount", "Tax", "Total", "Paid", "Balance", "Overdue days"])
    for i in _filtered(request).order_by("-created_at")[:5000]:
        w.writerow([_safe(x) for x in [i.number or "", i.display_status_label, i.client_name, i.client_company, i.client_email, i.project_name, i.currency, i.issue_date or "", i.due_date or "", i.subtotal, i.discount, i.tax_amount, i.total, i.amount_paid, i.balance, i.days_overdue]])
    log_activity(request.user, "invoice.exported", None, "CSV", request)
    return resp


def _safe(v):
    """Neutralise spreadsheet formula injection in exported text."""
    s = str(v)
    return "'" + s if s[:1] in ("=", "+", "-", "@") else s


class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ["client_name", "client_company", "client_email", "client_phone", "client_address", "client_country", "client_tax_label", "client_tax_no", "project_name", "description",
                  "currency", "billing_type", "milestone_label", "issue_date", "due_date", "discount", "tax_percent", "tax_name", "notes", "terms", "footer", "methods"]
        widgets = {"client_address": forms.Textarea(attrs={"rows": 3}), "description": forms.Textarea(attrs={"rows": 3}), "notes": forms.Textarea(attrs={"rows": 3}), "terms": forms.Textarea(attrs={"rows": 3}),
                   "footer": forms.Textarea(attrs={"rows": 2}), "issue_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"), "due_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
                   "methods": forms.CheckboxSelectMultiple}
        labels = {"methods": "Accepted payment methods"}
        help_texts = {"methods": "Leave all unticked to offer every enabled method for this currency.", "tax_name": "Shown next to the tax line, e.g. VAT or Sales tax."}

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        cb = CompanyBilling.load()
        self.fields["currency"] = forms.ChoiceField(choices=[(c, f"{c} – {money.CURRENCIES[c][0]}") for c in cb.currency_list], initial=cb.default_currency)
        self.fields["methods"].queryset = PaymentMethod.objects.filter(is_enabled=True)
        self.fields["methods"].required = False
        for n, f in self.fields.items():
            if n != "methods":
                f.widget.attrs["class"] = "input"
        self.fields["client_name"].widget.attrs["required"] = True

    def clean_discount(self):
        v = self.cleaned_data.get("discount") or 0
        if v < 0:
            raise forms.ValidationError("Discount cannot be negative.")
        return v

    def clean_tax_percent(self):
        v = self.cleaned_data.get("tax_percent") or 0
        if not 0 <= v <= 100:
            raise forms.ValidationError("Tax must be between 0 and 100.")
        return v

    def clean(self):
        d = super().clean()
        if d.get("issue_date") and d.get("due_date") and d["due_date"] < d["issue_date"]:
            self.add_error("due_date", "The due date cannot be before the issue date.")
        return d


def _read_items(post):
    rows = []
    cols = [post.getlist(k) for k in ("item_desc", "item_detail", "item_qty", "item_price", "item_unit")]
    n = len(cols[0])
    cols = [c + [""] * (n - len(c)) for c in cols]  # a missing column must not silently drop every line
    for i, (desc, detail, qty, price, unit) in enumerate(zip(*cols)):
        desc = clean_plain(desc, 300)
        if not desc:
            continue
        q_, p_ = money.to_dec(qty, "1"), money.to_dec(price)
        rows.append({"description": desc, "detail": clean_plain(detail, 500), "quantity": min(max(q_, Decimal("0.01")), Decimal("99999999")), "unit_price": min(max(p_, Decimal(0)), Decimal("999999999")), "unit": clean_plain(unit, 20), "order": i})
    return rows


@needs("invoices", "create")
def invoice_new(request):
    return _editor(request, None)


@needs("invoices", "edit")
def invoice_edit(request, pk):
    inv = get_object_or_404(Invoice, pk=pk)
    if not inv.is_draft:
        messages.error(request, "An issued invoice cannot be edited – that would silently rewrite history. Use 'Revise' to void it and create a corrected draft.")
        return redirect("dashboard:invoice_detail", pk=pk)
    return _editor(request, inv)


def _editor(request, inv):
    cb = CompanyBilling.load()
    initial = {}
    if inv is None:
        g = request.GET
        lead = Lead.objects.filter(pk=g.get("lead")).first() if (g.get("lead") or "").isdigit() else None
        prospect = Prospect.objects.filter(pk=g.get("prospect")).first() if (g.get("prospect") or "").isdigit() else None
        initial = {"currency": cb.default_currency, "tax_percent": cb.default_tax_percent, "tax_name": cb.tax_name if cb.default_tax_percent else "", "notes": cb.default_notes, "issue_date": timezone.localdate(),
                   "due_date": timezone.localdate() + timedelta(days=cb.payment_terms_days)}
        if lead:
            initial.update(client_name=lead.name, client_email=lead.email, client_phone=lead.phone or "")
        elif prospect:
            initial.update(client_name=prospect.business_name, client_company=prospect.business_name, client_email=prospect.email, client_country=getattr(prospect, "country", "") or "")
    else:
        lead, prospect = inv.lead, inv.prospect
    form = InvoiceForm(request.POST or None, instance=inv, initial=initial)
    items = _read_items(request.POST) if request.method == "POST" else ([{"description": i.description, "detail": i.detail, "quantity": i.quantity, "unit_price": i.unit_price, "unit": i.unit} for i in inv.items.all()] if inv else [])
    if request.method == "POST":
        if not items:
            form.add_error(None, "Add at least one line item.")
        if form.is_valid() and items:
            obj = form.save(commit=False)
            if inv is None:
                obj.created_by, obj.lead, obj.prospect = request.user, lead, prospect
            obj.save()
            form.save_m2m()
            replace_items(obj, items)
            event(obj, "created" if inv is None else "edited", "Draft saved", request.user)
            log_activity(request.user, "invoice.saved", obj, obj.number or f"draft {obj.pk}", request)
            messages.success(request, "Draft saved. Review it, then issue it when you're ready – nothing has been sent.")
            return redirect("dashboard:invoice_detail", pk=obj.pk)
    return render(request, "dashboard/billing/invoice_form.html", {
        "form": form, "items": items, "inv": inv, "lead": lead, "prospect": prospect, "co": cb.snapshot(), "currencies": {c: money.decimals(c) for c in cb.currency_list},
        "page_title": "Invoice editor", "crumbs": [HOME, CRUMB, (inv.number or "Draft" if inv else "New", "")],
    })


@needs("invoices", "view")
def invoice_detail(request, pk):
    inv = get_object_or_404(Invoice.objects.select_related("lead", "prospect", "proposal", "replaces", "created_by", "issued_by"), pk=pk)
    u = request.user
    pays = list(inv.payments.select_related("method", "recorded_by", "verified_by").prefetch_related("refunds"))
    return render(request, "dashboard/billing/invoice_detail.html", {
        "inv": inv, "items": list(inv.items.all()), "events": inv.events.select_related("actor")[:40], "payments": pays, "emails": inv.emails.select_related("message")[:15], "co": inv.company(),
        "problems": problems_for_issue(inv) if inv.is_draft else [], "public_url": f"{dj.SITE_URL}{inv.public_path}", "revisions": inv.revisions.all(), "email_label": emails.delivery_label,
        "methods": PaymentMethod.objects.filter(is_enabled=True) if inv.status in Invoice.OPEN else [], "kinds": PaymentMethod.KINDS, "currencies": CompanyBilling.load().currency_list,
        "can_edit": u.can("invoices", "edit"), "can_issue": u.can("invoices", "approve"), "can_void": u.can("invoices", "delete"), "can_record": u.can("payments", "create"),
        "can_verify": u.can("payments", "approve"), "can_refund": u.can("payments", "edit"), "email_kinds": emails.KINDS,
        "page_title": inv.number or "Draft invoice", "crumbs": [HOME, CRUMB, (inv.number or "Draft", "")],
    })


@needs("invoices", "view")
def invoice_pdf_view(request, pk):
    inv = get_object_or_404(Invoice, pk=pk)
    resp = HttpResponse(invoice_pdf(inv), content_type="application/pdf")
    resp["Content-Disposition"] = f'{"attachment" if request.GET.get("dl") else "inline"}; filename="Invoice-{inv.number or "draft"}.pdf"'
    resp["X-Content-Type-Options"] = "nosniff"
    return resp


@needs("invoices", "view")
@require_POST
def invoice_action(request, pk):
    inv = get_object_or_404(Invoice, pk=pk)
    act, u = request.POST.get("action"), request.user
    back = redirect("dashboard:invoice_detail", pk=inv.pk)

    def need(module, action):
        if not u.can(module, action):
            messages.error(request, "You don't have permission to do that.")
            return False
        return True
    try:
        if act == "issue":
            if not need("invoices", "approve"):
                return back
            if request.POST.get("confirm") != "yes":
                messages.error(request, "Tick the confirmation box to issue the invoice. Once issued it gets its number and can no longer be edited.")
                return back
            inv = issue_invoice(inv, u, issue_date=_d(request.POST.get("issue_date")), due_date=_d(request.POST.get("due_date")))
            messages.success(request, f"Issued as {inv.number}. It has not been emailed yet – use 'Send to client'.")
        elif act in ("cancel", "void"):
            if not need("invoices", "delete"):
                return back
            close_invoice(inv, u, Invoice.CANCELLED if act == "cancel" else Invoice.VOID, request.POST.get("reason", ""))
            messages.success(request, "Invoice cancelled." if act == "cancel" else "Invoice voided. It stays in the records.")
        elif act == "revise":
            if not (need("invoices", "edit") and need("invoices", "delete")):
                return back
            new = revise_invoice(inv, u)
            messages.success(request, f"{inv.number} was voided and a corrected draft was created.")
            return redirect("dashboard:invoice_edit", pk=new.pk)
        elif act == "delete_draft":
            if not need("invoices", "delete"):
                return back
            if not inv.is_draft:
                raise BillingError("Only drafts can be deleted. Issued invoices are cancelled or voided instead.")
            log_activity(u, "invoice.draft_deleted", inv, f"draft {inv.pk}", request)
            inv.delete()
            messages.success(request, "Draft deleted.")
            return redirect("dashboard:invoices")
        elif act == "dispute":
            if not need("invoices", "edit"):
                return back
            inv.in_dispute = request.POST.get("on") == "1"
            inv.dispute_note = clean_plain(request.POST.get("note", ""), 300)
            inv.save(update_fields=["in_dispute", "dispute_note", "updated_at"])
            event(inv, "dispute", ("Marked as disputed – reminders paused: " + inv.dispute_note) if inv.in_dispute else "Dispute cleared – reminders can resume", u)
            messages.success(request, "Dispute flag updated.")
        elif act == "note":
            if not need("invoices", "edit"):
                return back
            body = clean_plain(request.POST.get("body", ""), 300)
            if body:
                event(inv, "note", body, u)
        else:
            raise BillingError("Unknown action.")
    except BillingError as exc:
        _err(request, exc)
    return back


@needs("invoices", "edit")
def invoice_send(request, pk):
    """Preview the email (editable), choose attachments, then send. Nothing leaves until the final button."""
    inv = get_object_or_404(Invoice, pk=pk)
    if inv.is_draft:
        messages.error(request, "Issue the invoice before sending it.")
        return redirect("dashboard:invoice_detail", pk=pk)
    kind = request.POST.get("kind") or request.GET.get("kind") or ("issued" if not inv.sent_at else "reminder")
    if kind not in emails.KINDS:
        kind = "issued"
    payment = inv.payments.filter(pk=request.POST.get("payment") or request.GET.get("payment") or 0, status=Payment.CONFIRMED).first() or inv.payments.filter(status=Payment.CONFIRMED).order_by("-id").first()
    try:
        subj, body = emails.build(kind, inv, payment)
    except BillingError as exc:
        messages.error(request, str(exc))
        return redirect("dashboard:invoice_detail", pk=pk)
    doc = current_profile()
    if request.method == "POST" and request.POST.get("do") == "send":
        try:
            emails.send_invoice_email(inv, request.user, kind, subject=request.POST.get("subject"), body=request.POST.get("body"), attach_pdf=request.POST.get("attach_pdf") == "1",
                                      profile_mode=request.POST.get("profile_mode", "none"), payment=payment, to=request.POST.get("to"))
            messages.success(request, "Email queued. Its delivery status is shown on the invoice (it says 'Accepted by mail server' only once your SMTP server takes it).")
            return redirect("dashboard:invoice_detail", pk=pk)
        except BillingError as exc:
            messages.error(request, str(exc))
        subj, body = request.POST.get("subject", subj), request.POST.get("body", body)
    return render(request, "dashboard/billing/invoice_send.html", {
        "inv": inv, "kind": kind, "kinds": emails.KINDS, "subject": subj, "body": body, "to": request.POST.get("to") or inv.client_email, "doc": doc, "payment": payment,
        "has_pdf": bool(emails.default_attachments(kind, inv, payment)), "default_pdf": request.method == "GET" or request.POST.get("attach_pdf") == "1",
        "page_title": "Send invoice", "crumbs": [HOME, CRUMB, (inv.number, f"/dashboard/invoices/{inv.pk}/"), ("Send", "")],
    })


@needs("payments", "create")
@require_POST
def invoice_payment(request, pk):
    inv = get_object_or_404(Invoice, pk=pk)
    p = request.POST
    method = PaymentMethod.objects.filter(pk=p.get("method") or 0).first()
    verify = p.get("verify") == "1"
    try:
        if verify and not request.user.can("payments", "approve"):
            raise BillingError("You can record a payment but only someone with verification permission can confirm it.")
        pay = record_payment(inv, request.user, method=method, amount=money.to_dec(p.get("amount")), reference=clean_plain(p.get("reference", ""), 120), paid_on=_d(p.get("paid_on")),
                             note=clean_plain(p.get("note", ""), 400), received_currency=(p.get("received_currency") or "").upper() if p.get("received_currency") != inv.currency else "",
                             received_amount=p.get("received_amount") or None, exchange_rate=p.get("exchange_rate") or None, bank_fee=p.get("bank_fee") or None,
                             verify=verify, verification_note=clean_plain(p.get("verification_note", ""), 400))
        messages.success(request, "Payment confirmed and applied." if pay.status == Payment.CONFIRMED else "Payment recorded as PENDING. It does not count until it is verified against the bank record.")
    except BillingError as exc:
        _err(request, exc)
    return redirect("dashboard:invoice_detail", pk=pk)


# ================================================================== payments / verification / receipts
@needs("payments", "view")
def payments_list(request):
    g = request.GET
    qs = Payment.objects.select_related("invoice", "method")
    st = g.get("status", "pending")
    if st in dict(Payment.STATUS):
        qs = qs.filter(status=st)
    if g.get("q"):
        qs = qs.filter(Q(invoice__number__icontains=g["q"]) | Q(invoice__client_name__icontains=g["q"]) | Q(reference__icontains=g["q"]) | Q(receipt_number__icontains=g["q"]))
    if g.get("currency"):
        qs = qs.filter(currency=g["currency"].upper())
    if g.get("method") in dict(PaymentMethod.KINDS):
        qs = qs.filter(method_kind=g["method"])
    page = Paginator(qs, 25).get_page(g.get("page"))
    qd = g.copy()
    qd.pop("page", None)
    counts = dict(Payment.objects.values_list("status").annotate(n=Count("id")))
    return render(request, "dashboard/billing/payments.html", {
        "page": page, "g": g, "status": st, "statuses": Payment.STATUS, "counts": counts, "qs": qd.urlencode(), "kinds": PaymentMethod.KINDS, "currencies": CompanyBilling.load().currency_list,
        "can_verify": request.user.can("payments", "approve"), "can_export": request.user.can("payments", "export"),
        "page_title": "Payments", "crumbs": [HOME, ("Billing", ""), ("Payments", "")],
    })


@needs("payments", "export")
def payments_export(request):
    resp = HttpResponse(content_type="text/csv")
    resp["Content-Disposition"] = 'attachment; filename="payments.csv"'
    w = csv.writer(resp)
    w.writerow(["Receipt", "Status", "Invoice", "Client", "Method", "Currency", "Credited amount", "Refunded", "Received currency", "Received amount", "Exchange rate", "Bank fee", "Reference", "Paid on", "Verified by", "Verified at"])
    for p in Payment.objects.select_related("invoice", "verified_by").order_by("-created_at")[:5000]:
        w.writerow([_safe(x) for x in [p.receipt_number or "", p.get_status_display(), p.invoice.number, p.invoice.client_name, p.method_label, p.currency, p.amount, p.refunded_amount, p.received_currency,
                                      p.received_amount or "", p.exchange_rate or "", p.bank_fee or "", p.reference, p.paid_on or "", p.verified_by.email if p.verified_by else "", p.verified_at or ""]])
    log_activity(request.user, "payment.exported", None, "CSV", request)
    return resp


@needs("payments", "view")
def payment_detail(request, pk):
    p = get_object_or_404(Payment.objects.select_related("invoice", "method", "recorded_by", "verified_by"), pk=pk)
    return render(request, "dashboard/billing/payment_detail.html", {
        "p": p, "inv": p.invoice, "refunds": p.refunds.select_related("created_by"), "can_verify": request.user.can("payments", "approve"), "can_refund": request.user.can("payments", "edit"),
        "page_title": p.receipt_number or "Payment", "crumbs": [HOME, ("Payments", "/dashboard/payments/"), (p.receipt_number or f"#{p.pk}", "")],
    })


@needs("payments", "view")
def receipt_pdf_view(request, pk):
    p = get_object_or_404(Payment.objects.select_related("invoice"), pk=pk, status=Payment.CONFIRMED)
    resp = HttpResponse(receipt_pdf(p), content_type="application/pdf")
    resp["Content-Disposition"] = f'{"attachment" if request.GET.get("dl") else "inline"}; filename="Receipt-{p.receipt_number}.pdf"'
    return resp


@needs("payments", "view")
@require_POST
def payment_action(request, pk):
    p = get_object_or_404(Payment, pk=pk)
    act, u = request.POST.get("action"), request.user
    nxt = request.POST.get("next", "")
    back = redirect(nxt) if nxt.startswith("/dashboard/") and not nxt.startswith("//") else redirect("dashboard:payment_detail", pk=p.pk)
    try:
        if act in ("confirm", "reject"):
            if not u.can("payments", "approve"):
                raise BillingError("You don't have permission to verify payments.")
            if act == "confirm":
                if request.POST.get("checked") != "1":
                    raise BillingError("Tick the box to confirm you checked the real bank/provider record.")
                confirm_payment(p, u, clean_plain(request.POST.get("note", ""), 400))
                messages.success(request, f"Payment confirmed. Receipt {Payment.objects.get(pk=p.pk).receipt_number} created.")
            else:
                reject_payment(p, u, clean_plain(request.POST.get("note", ""), 400))
                messages.success(request, "Payment rejected. The invoice balance is unchanged.")
        elif act == "refund":
            if not u.can("payments", "edit"):
                raise BillingError("You don't have permission to refund payments.")
            rf = refund_payment(p, u, money.to_dec(request.POST.get("amount")), clean_plain(request.POST.get("note", ""), 300))
            messages.success(request, f"Refund of {money.fmt(rf.amount, p.currency)} recorded" + (" and sent to the provider." if p.provider else ". Remember to send the money back through your bank."))
        elif act == "email_receipt":
            if not u.can("invoices", "edit"):
                raise BillingError("You don't have permission to email clients.")
            emails.send_invoice_email(p.invoice, u, "payment_received", payment=p)
            messages.success(request, "Receipt email queued.")
        else:
            raise BillingError("Unknown action.")
    except BillingError as exc:
        _err(request, exc)
    return back


# ================================================================== proposal → invoice
@needs("invoices", "create")
@require_POST
def proposal_to_invoice(request, pk):
    pr = get_object_or_404(Proposal, pk=pk)
    p = request.POST
    try:
        inv = invoice_from_proposal(pr, request.user, mode=p.get("mode", "full"), percent=p.get("percent") or None, amount=p.get("amount") or None, label=clean_plain(p.get("label", ""), 120))
        messages.success(request, "Draft invoice created from the proposal. Nothing is issued or emailed until you do it. Review the lines first.")
        return redirect("dashboard:invoice_edit", pk=inv.pk)
    except BillingError as exc:
        _err(request, exc)
        return redirect("dashboard:proposal_detail", pk=pk)


# ================================================================== reports
@needs("billing_reports", "view")
def billing_reports(request):
    g = request.GET
    today = timezone.localdate()
    d_from, d_to = _d(g.get("from")) or date(today.year, 1, 1), _d(g.get("to")) or today
    live = Invoice.objects.exclude(status__in=[Invoice.DRAFT, Invoice.CANCELLED, Invoice.VOID])
    inv_range = live.filter(issue_date__gte=d_from, issue_date__lte=d_to)
    pay_range = Payment.objects.filter(status=Payment.CONFIRMED, paid_on__gte=d_from, paid_on__lte=d_to)
    cur = defaultdict(lambda: defaultdict(Decimal))
    for r in inv_range.values("currency").annotate(t=Sum("total"), n=Count("id")):
        cur[r["currency"]]["invoiced"], cur[r["currency"]]["invoice_count"] = r["t"], r["n"]
    for r in pay_range.values("currency").annotate(t=Sum("amount"), rf=Sum("refunded_amount")):
        cur[r["currency"]]["collected_gross"], cur[r["currency"]]["refunded"] = r["t"], r["rf"] or Decimal(0)
        cur[r["currency"]]["collected_net"] = r["t"] - (r["rf"] or 0)
    for r in Invoice.objects.filter(status__in=Invoice.OPEN).values("currency").annotate(t=Sum("total"), p=Sum("amount_paid")):
        cur[r["currency"]]["outstanding"] = r["t"] - r["p"]
    for r in Invoice.objects.filter(status__in=Invoice.OPEN, due_date__lt=today).values("currency").annotate(t=Sum("total"), p=Sum("amount_paid"), n=Count("id")):
        cur[r["currency"]]["overdue"], cur[r["currency"]]["overdue_count"] = r["t"] - r["p"], r["n"]
    for r in Invoice.objects.filter(status=Invoice.PARTIAL).values("currency").annotate(n=Count("id"), p=Sum("amount_paid")):
        cur[r["currency"]]["partial_count"], cur[r["currency"]]["partial_paid"] = r["n"], r["p"]
    for r in Payment.objects.filter(status=Payment.PENDING).values("currency").annotate(t=Sum("amount"), n=Count("id")):
        cur[r["currency"]]["unverified"], cur[r["currency"]]["unverified_count"] = r["t"], r["n"]
    for r in Payment.objects.filter(status=Payment.FAILED, created_at__date__gte=d_from, created_at__date__lte=d_to).values("currency").annotate(n=Count("id")):
        cur[r["currency"]]["failed_count"] = r["n"]
    by_method = list(pay_range.values("currency", "method_label").annotate(t=Sum("amount"), n=Count("id")).order_by("currency", "-t"))
    months = defaultdict(lambda: defaultdict(Decimal))
    for r in inv_range.annotate(m=TruncMonth("issue_date")).values("currency", "m").annotate(t=Sum("total")):
        months[(r["m"], r["currency"])]["invoiced"] = r["t"]
    for r in pay_range.annotate(m=TruncMonth("paid_on")).values("currency", "m").annotate(t=Sum("amount"), rf=Sum("refunded_amount")):
        months[(r["m"], r["currency"])]["collected"] = r["t"] - (r["rf"] or 0)
    monthly = [{"month": k[0], "currency": k[1], **v} for k, v in sorted(months.items(), key=lambda kv: (kv[0][0], kv[0][1]), reverse=True)]
    return render(request, "dashboard/billing/reports.html", {
        "cur": [(c, dict(v)) for c, v in sorted(cur.items())], "by_method": by_method, "monthly": monthly, "d_from": d_from, "d_to": d_to,
        "page_title": "Billing reports", "crumbs": [HOME, ("Billing", ""), ("Reports", "")],
    })


# ================================================================== settings
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


class CompanyBillingForm(forms.ModelForm):
    class Meta:
        model = CompanyBilling
        exclude = ["created_at", "updated_at"]
        widgets = {"logo_url": MediaPickerWidget(kind="image"), "signature_url": MediaPickerWidget(kind="image"), "invoice_footer": forms.Textarea(attrs={"rows": 3}),
                   "payment_instructions": forms.Textarea(attrs={"rows": 3}), "default_notes": forms.Textarea(attrs={"rows": 3}), "brand_color": forms.TextInput(attrs={"type": "color"})}

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        for f in self.fields.values():
            f.widget.attrs.setdefault("class", "check" if isinstance(f.widget, forms.CheckboxInput) else "input")
        for n in ("default_currency", "quotation_currency"):
            self.fields[n].widget = forms.Select(choices=[(c, f"{c} – {v[0]}") for c, v in money.CURRENCIES.items()], attrs={"class": "input"})

    def clean_brand_color(self):
        v = self.cleaned_data["brand_color"]
        if not HEX.match(v):
            raise forms.ValidationError("Use a colour like #EC008C.")
        return v

    def clean_invoice_prefix(self):
        v = (self.cleaned_data["invoice_prefix"] or "").strip().upper()
        if not re.match(r"^[A-Z0-9]{1,12}$", v):
            raise forms.ValidationError("Letters and digits only, up to 12 characters.")
        return v

    def clean_receipt_prefix(self):
        v = (self.cleaned_data["receipt_prefix"] or "").strip().upper()
        if not re.match(r"^[A-Z0-9]{1,12}$", v):
            raise forms.ValidationError("Letters and digits only, up to 12 characters.")
        return v

    def clean_default_tax_percent(self):
        v = self.cleaned_data["default_tax_percent"]
        if not 0 <= v <= 100:
            raise forms.ValidationError("Tax must be between 0 and 100.")
        return v

    def clean_payment_terms_days(self):
        v = self.cleaned_data["payment_terms_days"]
        if v > 365:
            raise forms.ValidationError("Choose up to 365 days.")
        return v

    def clean_enabled_currencies(self):
        codes = [c.strip().upper() for c in (self.cleaned_data["enabled_currencies"] or "").split(",") if c.strip()]
        bad = [c for c in codes if c not in money.CURRENCIES]
        if bad:
            raise forms.ValidationError(f"Unsupported currency code(s): {', '.join(bad)}. Supported: {', '.join(money.CURRENCIES)}.")
        if not codes:
            raise forms.ValidationError("Enable at least one currency.")
        return ",".join(dict.fromkeys(codes))

    def clean(self):
        d = super().clean()
        en = [c for c in (d.get("enabled_currencies") or "").split(",") if c]
        for n in ("default_currency", "quotation_currency"):
            if en and d.get(n) and d[n] not in en:
                self.add_error(n, "This currency must be one of the enabled currencies.")
        return d


GROUPS = [
    ("Company identity", ["legal_name", "trading_name", "logo_url", "brand_color", "email", "phone", "website"]),
    ("Address", ["address_line1", "address_line2", "city", "postal_code", "country"]),
    ("Registration & tax", ["registration_label", "registration_no", "tax_label", "tax_no", "tax_name", "default_tax_percent"]),
    ("Currency & terms", ["default_currency", "quotation_currency", "enabled_currencies", "payment_terms_days"]),
    ("Numbering", ["invoice_prefix", "invoice_start_number", "number_padding", "reset_numbering_yearly", "receipt_prefix"]),
    ("Document text", ["invoice_footer", "payment_instructions", "default_notes", "signatory_name", "signatory_title", "signature_url"]),
    ("Reminders", ["send_reminders", "remind_before_days", "remind_every_days", "max_reminders"]),
]


@needs("billing_settings", "view")
def billing_settings(request):
    cfg = CompanyBilling.load()
    form = CompanyBillingForm(request.POST or None, instance=cfg)
    can_edit = request.user.can("billing_settings", "edit")
    if request.method == "POST":
        if not can_edit:
            messages.error(request, "You don't have permission to change company billing settings.")
            return redirect("dashboard:billing_settings")
        if form.is_valid():
            form.save()
            log_activity(request.user, "billing.settings", cfg, "", request)
            messages.success(request, "Company billing settings saved. Invoices already issued keep the details they were issued with.")
            return redirect("dashboard:billing_settings")
    return render(request, "dashboard/billing/settings.html", {
        "form": form, "groups": [(t, [form[n] for n in names]) for t, names in GROUPS], "can_edit": can_edit, "next_no": _preview_number(cfg),
        "page_title": "Company billing", "crumbs": [HOME, ("Billing", ""), ("Company details", "")],
    })


def _preview_number(cfg):
    from apps.billing.models import NumberSequence
    year = timezone.localdate().year
    row = NumberSequence.objects.filter(key=f"invoice-{year}" if cfg.reset_numbering_yearly else "invoice").first()
    n = max((row.last if row else 0) + 1, cfg.invoice_start_number)
    return f"{cfg.invoice_prefix}-{year}-{n:0{cfg.number_padding}d}"


class PaymentMethodForm(forms.ModelForm):
    class Meta:
        model = PaymentMethod
        exclude = ["created_at", "updated_at"]
        widgets = {"instructions": forms.Textarea(attrs={"rows": 3}), "notes": forms.Textarea(attrs={"rows": 2}), "bank_address": forms.TextInput(), "correspondent_bank": forms.TextInput()}

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        for f in self.fields.values():
            f.widget.attrs.setdefault("class", "check" if isinstance(f.widget, forms.CheckboxInput) else "input")

    def clean_currencies(self):
        codes = [c.strip().upper() for c in (self.cleaned_data["currencies"] or "").split(",") if c.strip()]
        bad = [c for c in codes if c not in money.CURRENCIES]
        if bad:
            raise forms.ValidationError(f"Unsupported currency code(s): {', '.join(bad)}.")
        return ",".join(codes)

    def clean_iban(self):
        v = re.sub(r"\s+", "", self.cleaned_data["iban"] or "").upper()
        if v and not re.match(r"^[A-Z]{2}\d{2}[A-Z0-9]{8,30}$", v):
            raise forms.ValidationError("This does not look like an IBAN (e.g. PK36SCBL0000001123456702).")
        return v

    def clean(self):
        d = super().clean()
        kind = d.get("kind")
        if d.get("is_enabled"):
            if kind in PaymentMethod.BANK_LIKE and not ((d.get("account_number") or d.get("iban") or d.get("raast_id")) and d.get("account_title")):
                self.add_error("account_title", "Enter the account title and an account number / IBAN / Raast ID before enabling a bank method.")
            if kind == PaymentMethod.WIRE and not d.get("swift_bic"):
                self.add_error("swift_bic", "International wires need the SWIFT/BIC code.")
            if kind in (PaymentMethod.PAYPAL, PaymentMethod.PAYONEER, PaymentMethod.LINK) and not d.get("link_url"):
                self.add_error("link_url", "Paste the real payment link from your provider account first.")
            if kind == PaymentMethod.STRIPE and not d.get("verified_eligible"):
                self.add_error("verified_eligible", "Online gateways stay off until you confirm your provider account is approved for your business.")
        return d


@needs("billing_settings", "manage_settings")
def methods_list(request):
    rows = []
    for m in PaymentMethod.objects.all():
        gw = get_gateway(m) if m.is_gateway else None
        rows.append((m, gw))
    return render(request, "dashboard/billing/methods.html", {
        "rows": rows, "kinds": PaymentMethod.KINDS, "site_url": dj.SITE_URL, "events": WebhookEvent.objects.all()[:8],
        "page_title": "Payment methods", "crumbs": [HOME, ("Billing", ""), ("Payment methods", "")],
    })


@needs("billing_settings", "manage_settings")
def method_edit(request, pk=None):
    m = get_object_or_404(PaymentMethod, pk=pk) if pk else PaymentMethod(kind=request.GET.get("kind") if request.GET.get("kind") in dict(PaymentMethod.KINDS) else PaymentMethod.BANK_PK)
    if not pk:
        m.label = dict(PaymentMethod.KINDS).get(m.kind, "")
    form = PaymentMethodForm(request.POST or None, instance=m)
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        log_activity(request.user, "billing.method", obj, obj.label, request)
        messages.success(request, "Payment method saved.")
        return redirect("dashboard:billing_methods")
    gw = get_gateway(m) if m.pk and m.is_gateway else None
    return render(request, "dashboard/billing/method_form.html", {
        "form": form, "m": m, "gw": gw, "webhook_url": f"{dj.SITE_URL}/billing/webhooks/{m.kind}/" if m.is_gateway else "",
        "page_title": "Payment method", "crumbs": [HOME, ("Payment methods", "/dashboard/billing/methods/"), (m.label or "New", "")],
    })


@needs("billing_settings", "manage_settings")
@require_POST
def method_delete(request, pk):
    m = get_object_or_404(PaymentMethod, pk=pk)
    if m.payments.exists() or m.invoices.exists():
        m.is_enabled = False
        m.save(update_fields=["is_enabled"])
        messages.info(request, "This method is used by existing invoices, so it was switched off instead of deleted.")
    else:
        m.delete()
        messages.success(request, "Payment method deleted.")
    return redirect("dashboard:billing_methods")


# ================================================================== company profile PDF (Media library)
def _asset_from_url(url):
    url = (url or "").strip()
    if not url:
        return None
    name = url.split("?")[0]
    if "/media/" in name:
        name = name.split("/media/", 1)[1]
    return MediaAsset.objects.filter(file=name).first()


@needs("billing_settings", "view")
def company_profile(request):
    docs = list(CompanyDocument.objects.filter(kind=CompanyDocument.PROFILE).select_related("asset", "created_by"))
    cur = next((d for d in docs if d.is_current), None)
    can_edit = request.user.can("billing_settings", "edit")
    if request.method == "POST":
        if not can_edit:
            messages.error(request, "You don't have permission to change the company profile.")
            return redirect("dashboard:company_profile")
        act = request.POST.get("action")
        try:
            if act == "select":
                asset = _asset_from_url(request.POST.get("file_url"))
                if not asset:
                    raise BillingError("Choose a PDF from the Media library (use 'Choose from library', or upload it there first).")
                set_company_profile(asset, request.user, clean_plain(request.POST.get("note", ""), 300))
                messages.success(request, "Company profile selected. It is NOT emailed anywhere – you choose to attach or link it when you send something.")
            elif act == "restore":
                d = get_object_or_404(CompanyDocument, pk=request.POST.get("doc"), kind=CompanyDocument.PROFILE)
                if not d.asset_id:
                    raise BillingError("That version's file was removed from the Media library.")
                set_company_profile(d.asset, request.user, f"Restored version {d.version}")
                messages.success(request, "Earlier version is current again.")
            elif act == "sharing":
                d = get_object_or_404(CompanyDocument, pk=request.POST.get("doc"))
                d.link_sharing = request.POST.get("on") == "1"
                d.save(update_fields=["link_sharing", "updated_at"])
                messages.success(request, "Secure link sharing " + ("enabled." if d.link_sharing else "switched off – the old link stops working."))
        except BillingError as exc:
            _err(request, exc)
        return redirect("dashboard:company_profile")
    form = forms.Form()
    form.fields["file_url"] = forms.CharField(required=False, label="Company profile PDF", widget=MediaPickerWidget(kind="document"))
    form.fields["note"] = forms.CharField(required=False, max_length=300, label="Version note", widget=forms.TextInput(attrs={"class": "input", "placeholder": "e.g. 2026 refresh with new case studies"}))
    shares = DocumentShare.objects.select_related("document", "lead", "invoice", "proposal", "created_by")[:15]
    return render(request, "dashboard/billing/profile.html", {
        "docs": docs, "cur": cur, "form": form, "shares": shares, "can_edit": can_edit, "site_url": dj.SITE_URL, "max_mb": dj.MEDIA_MAX_UPLOAD_MB,
        "page_title": "Company profile", "crumbs": [HOME, ("Billing", ""), ("Company profile", "")],
    })


@needs("billing_settings", "view")
def company_profile_download(request, pk):
    d = get_object_or_404(CompanyDocument, pk=pk)
    if not d.asset_id:
        raise Http404
    from django.http import FileResponse
    resp = FileResponse(d.asset.file.open("rb"), content_type="application/pdf", as_attachment=bool(request.GET.get("dl")), filename=d.asset.download_name)
    resp["X-Content-Type-Options"] = "nosniff"
    return resp
