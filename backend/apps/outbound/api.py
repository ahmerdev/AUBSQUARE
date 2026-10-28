"""Public JSON API for the free website-audit lead magnet."""
import json
import logging

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.sanitize import clean_plain
from apps.core.services import client_ip, notify, visitor_hash
from . import audit as audit_engine
from .models import SiteAudit

log = logging.getLogger(__name__)
TOKEN_MAX_AGE_DAYS = 7


def error(message, details=None, status=400, code="validation_error"):
    return Response({"error": {"code": code, "message": message, "details": details}}, status=status)


def public_payload(a: SiteAudit) -> dict:
    checks = []
    if a.reachable:
        checks = [
            {"key": "https", "label": "Secure HTTPS", "ok": bool(a.is_https and a.ssl_ok)},
            {"key": "mobile", "label": "Mobile friendly", "ok": a.has_viewport},
            {"key": "title", "label": "Page title", "ok": bool(a.title)},
            {"key": "description", "label": "Meta description", "ok": bool(a.meta_description)},
            {"key": "h1", "label": "Main heading (H1)", "ok": bool(a.h1)},
            {"key": "whatsapp", "label": "WhatsApp / instant chat button", "ok": a.has_whatsapp},
            {"key": "contact", "label": "Contact form or email", "ok": bool(a.has_form or a.emails_found)},
            {"key": "links", "label": "Links work (no broken links)", "ok": not a.broken_links},
            {"key": "social", "label": "Social sharing tags", "ok": a.has_open_graph},
        ]
    return {"token": a.public_token, "url": a.final_url or a.url, "reachable": a.reachable, "error": a.error, "score": a.score if a.reachable else None, "health": (100 - a.score) if a.reachable else None,
            "level": a.level if a.reachable else None, "loadSeconds": a.load_seconds, "checks": checks,
            "findings": [{"title": f["title"], "detail": f["detail"], "fix": f["service"]} for f in a.findings], "leadSent": bool(a.lead_id), "checkedAt": a.created_at.isoformat()}


def _get(token):
    a = SiteAudit.objects.filter(public_token=token, kind="free").first()
    if not a or a.created_at < timezone.now() - timezone.timedelta(days=TOKEN_MAX_AGE_DAYS):
        return None
    return a


class AuditRunView(APIView):
    throttle_scope = "audit"

    def post(self, request):
        data = request.data if isinstance(request.data, dict) else {}
        if data.get("website"):  # honeypot
            return error("Something went wrong. Please try again.")
        url = clean_plain(str(data.get("url", "")), 300)
        if not url:
            return error("Please enter your website address.", details={"url": ["Enter your website address, e.g. yourbusiness.com"]})
        day = timezone.localdate().isoformat()
        cap_key = f"free-audit-day:{day}"
        if cache.get(cap_key, 0) >= settings.FREE_AUDIT_DAILY_CAP:
            return error("Our free audit tool is very busy today. Please try again tomorrow or contact us directly.", status=503)
        ip = client_ip(request) or "?"
        lock = f"free-audit-lock:{ip}"
        if not cache.add(lock, 1, 60):
            return error("Your audit is already running. Please wait a moment.", status=429)
        try:
            cache.set(cap_key, cache.get(cap_key, 0) + 1, 90000)
            a = audit_engine.run_audit(url, "free", check_internal=True, ip_hash=visitor_hash(request))
        finally:
            cache.delete(lock)
        return Response(public_payload(a), status=200)


class AuditDetailView(APIView):
    throttle_scope = "public"

    def get(self, request, token):
        a = _get(token)
        if not a:
            return error("This audit is no longer available. Please run a new one.", status=404)
        return Response(public_payload(a))


class AuditLeadView(APIView):
    throttle_scope = "audit_lead"

    def post(self, request, token):
        a = _get(token)
        if not a or not a.reachable:
            return error("This audit is no longer available. Please run a new one.", status=404)
        data = request.data if isinstance(request.data, dict) else {}
        if data.get("website"):
            return error("Something went wrong. Please try again.")
        if a.lead_id:
            return Response({"reference": a.lead.reference, "message": "We already have your request – we'll be in touch shortly.", "duplicate": True})
        name, email = clean_plain(str(data.get("name", "")), 120), clean_plain(str(data.get("email", "")), 254).lower()
        phone, note = clean_plain(str(data.get("phone", "")), 40), clean_plain(str(data.get("message", "")), 1000)
        errs = {}
        if len(name) < 2:
            errs["name"] = ["Please enter your name."]
        try:
            validate_email(email)
        except ValidationError:
            errs["email"] = ["Please enter a valid email address."]
        if not data.get("consent"):
            errs["consent"] = ["Please tick the box so we can contact you."]
        if errs:
            return error("Please correct the highlighted fields.", details=errs)
        from apps.leads.models import Lead
        from .services import lead_category, speed_to_lead

        top = "; ".join(f["title"] for f in a.findings[:4]) or "No major issues found"
        msg = f"Requested help after the free website audit of {a.final_url or a.url}. Website health score {100 - a.score}/100. Top findings: {top}." + (f"\n\nTheir note: {note}" if note else "")
        lead = Lead.objects.create(name=name, email=email, phone=phone, message=msg[:4000], source="audit_tool", service_label=(a.findings[0]["service"] if a.findings else "Website audit follow-up")[:160],
                                   category=lead_category(" ".join(f["category"] + " " + f["service"] for f in a.findings)), consent_given=True, visitor_hash=visitor_hash(request),
                                   source_page="/free-audit", content_hash=f"audit-{a.pk}")
        a.lead = lead
        a.save(update_fields=["lead", "updated_at"])
        try:
            notify("lead", f"New lead from free audit: {name}", f"{a.final_url or a.url} · health {100 - a.score}/100", f"/dashboard/leads/{lead.pk}/", module="leads", level="success")
        except Exception:
            log.exception("audit lead notify failed")
        from .services import staff_email

        staff_email(f"[AUB SQUARE] New lead {lead.reference} from the free audit – {name}", f"Name: {name}\nEmail: {email}\nPhone: {phone}\nWebsite: {a.final_url or a.url} (health {100 - a.score}/100)\n\n{msg}\n\nOpen: /dashboard/leads/{lead.pk}/")
        speed_to_lead(lead)
        return Response({"reference": lead.reference, "message": "Thank you! A specialist will review your audit and contact you very soon.", "duplicate": False}, status=201)
