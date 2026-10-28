"""Pages a client opens without logging in: the invoice page, receipts, the shared company-profile link and the provider webhook."""
import logging
import re

from django.core.cache import cache
from django.http import FileResponse, Http404, HttpResponse, HttpResponseBadRequest, HttpResponseRedirect
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.views.decorators.http import require_POST

from apps.core.sanitize import clean_plain
from apps.core.services import client_ip, notify
from apps.outbound.public_views import _brand, _private
from . import money
from .gateways import GatewayError, get_gateway_by_provider
from .models import CompanyDocument, Invoice, Payment, PaymentMethod
from .pdf import invoice_pdf, receipt_pdf
from .services import BillingError, event, process_webhook, record_payment, site_url, start_checkout

log = logging.getLogger(__name__)
BOT_RE = re.compile(r"bot|crawl|spider|preview|scanner|slurp|facebookexternalhit|whatsapp|curl|wget|python-requests|headless|monitor|proofpoint|mimecast|barracuda|safelinks", re.I)


def _invoice(token):
    inv = Invoice.objects.filter(token=token).prefetch_related("items", "payments").first()
    if not inv or inv.status == Invoice.DRAFT:
        raise Http404
    return inv


def _throttle(request, key, limit=10, secs=3600):
    k = f"{key}:{client_ip(request) or '?'}"
    n = cache.get(k, 0)
    if n >= limit:
        return True
    cache.set(k, n + 1, secs)
    return False


@never_cache
@csrf_protect
def invoice_page(request, token):
    inv = _invoice(token)
    staff = request.user.is_authenticated and getattr(request.user, "can_access_dashboard", False)
    notice = request.GET.get("paid") or ""
    err = ""
    if request.method == "POST":
        if _throttle(request, f"inv-act:{token}"):
            return _private(HttpResponse("Too many attempts. Please try again later.", status=429))
        act = request.POST.get("action")
        try:
            if act == "pay_online":
                m = PaymentMethod.objects.filter(pk=request.POST.get("method") or 0, kind=PaymentMethod.STRIPE, is_enabled=True).first()
                if not m or not any(x.get("id") == m.pk for x in inv.methods_snapshot or []):
                    raise BillingError("That payment method is not offered on this invoice.")
                url = start_checkout(inv, m, site_url(f"{inv.public_path}?paid=return"), site_url(f"{inv.public_path}?paid=cancelled"))
                return HttpResponseRedirect(url)
            if act == "report_payment":
                amount = money.to_dec(request.POST.get("amount"))
                ref = clean_plain(request.POST.get("reference", ""), 120)
                if not ref:
                    raise BillingError("Please enter the transfer reference or transaction ID so we can find your payment.")
                m = PaymentMethod.objects.filter(pk=request.POST.get("method") or 0).first()
                p = record_payment(inv, None, method=m, amount=amount or inv.balance, reference=ref, note=("Reported by client: " + clean_plain(request.POST.get("note", ""), 300))[:400], source="client")
                event(inv, "client_reported", f"Client says they paid {money.fmt(p.amount, p.currency)} (ref {ref}) – awaiting verification", None)
                notice = "reported"
        except BillingError as exc:
            err = str(exc)
    elif request.method == "GET" and not staff and not BOT_RE.search(request.META.get("HTTP_USER_AGENT", "")):
        first = inv.first_viewed_at is None
        Invoice.objects.filter(pk=inv.pk).update(view_count=inv.view_count + 1, first_viewed_at=inv.first_viewed_at or timezone.now())
        if first:
            event(inv, "viewed", "Client opened the invoice page", None)
            notify("invoice", f"{inv.client_name} opened invoice {inv.number}", "", f"/dashboard/invoices/{inv.pk}/", module="invoices", level="info")
    inv.refresh_from_db()
    methods = inv.methods_snapshot or []
    open_ = inv.status in Invoice.OPEN and inv.balance > 0
    gateway_ids = [m["id"] for m in methods if m.get("kind") == "stripe"]
    online = [m for m in PaymentMethod.objects.filter(pk__in=gateway_ids, is_enabled=True) if m.gateway_ready] if open_ else []
    resp = render(request, "public/invoice.html", {
        "inv": inv, "items": list(inv.items.all()), "co": inv.company(), "methods": methods, "online": online, "open": open_, "brand": _brand(), "notice": notice, "error": err,
        "receipts": [p for p in inv.payments.all() if p.status == Payment.CONFIRMED], "pending": [p for p in inv.payments.all() if p.status == Payment.PENDING],
    })
    return _private(resp)


@never_cache
def invoice_pdf_download(request, token):
    inv = _invoice(token)
    resp = HttpResponse(invoice_pdf(inv), content_type="application/pdf")
    resp["Content-Disposition"] = f'inline; filename="Invoice-{inv.number}.pdf"'
    return _private(resp)


@never_cache
def receipt_download(request, token, pk):
    inv = _invoice(token)
    p = inv.payments.filter(pk=pk, status=Payment.CONFIRMED).first()
    if not p:
        raise Http404
    resp = HttpResponse(receipt_pdf(p), content_type="application/pdf")
    resp["Content-Disposition"] = f'inline; filename="Receipt-{p.receipt_number}.pdf"'
    return _private(resp)


@never_cache
def shared_document(request, token):
    """Secure link to the company profile: works only for the version a staff member chose to share, and can be switched off."""
    doc = CompanyDocument.objects.filter(share_token=token, link_sharing=True).select_related("asset").first()
    if not doc or not doc.asset_id:
        raise Http404
    try:
        fh = doc.asset.file.open("rb")
    except OSError:
        raise Http404
    resp = FileResponse(fh, content_type="application/pdf")
    resp["Content-Disposition"] = f'inline; filename="{doc.asset.download_name}"'
    return _private(resp)


@csrf_exempt  # providers cannot send a CSRF token; the signed payload is the authorisation
@require_POST
def webhook(request, provider):
    if provider not in ("stripe",):
        raise Http404
    gw = get_gateway_by_provider(provider)
    if not gw or not gw.method.is_enabled:
        return HttpResponse(status=404)
    try:
        outcome = process_webhook(gw, request.body, request.headers)
    except GatewayError as exc:
        log.warning("webhook rejected: %s", exc)
        return HttpResponseBadRequest("invalid")
    except Exception:  # noqa: BLE001 – 500 makes the provider retry; the failure is stored on the WebhookEvent
        return HttpResponse(status=500)
    return HttpResponse(outcome)
