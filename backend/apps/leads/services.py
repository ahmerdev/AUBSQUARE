import hashlib
import logging
import re

from django.core import signing
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone

from apps.core.sanitize import clean_plain
from apps.core.services import client_ip, notify, visitor_hash
from .models import BudgetOption, Lead, LeadFormConfig

log = logging.getLogger(__name__)
FORM_SALT = "aub.form"
PHONE_RE = re.compile(r"^[0-9+\-\s()]{5,22}$")


def issue_form_token() -> str:
    return signing.dumps({"t": timezone.now().timestamp()}, salt=FORM_SALT)


def check_form_token(token: str, min_seconds: int):
    """Returns (ok, reason). Missing / too-fast / expired tokens are spam signals."""
    if not token:
        return False, "missing form token"
    try:
        data = signing.loads(token, salt=FORM_SALT, max_age=60 * 60 * 6)
    except signing.BadSignature:
        return False, "invalid or expired form token"
    if timezone.now().timestamp() - data["t"] < min_seconds:
        return False, "submitted too fast"
    return True, ""


def service_options(cfg: LeadFormConfig):
    from apps.cms.models import Service

    opts = []
    if cfg.use_services_as_options:
        opts += [s.title for s in Service.objects.live().order_by("order", "id")]
    opts += [l.strip() for l in cfg.extra_service_options.splitlines() if l.strip()]
    return opts


def validate_lead_payload(data: dict, cfg: LeadFormConfig) -> dict:
    errors = {}
    name = clean_plain(data.get("name", ""), 120)
    email = clean_plain(data.get("email", ""), 254).lower()
    phone = clean_plain(data.get("phone", ""), 22)
    code = clean_plain(data.get("countryCode", ""), 8)
    service = clean_plain(data.get("service", ""), 160)
    budget_raw = clean_plain(data.get("budget", ""), 120)
    message = clean_plain(data.get("message", ""), 4000)
    if len(name) < 2:
        errors["name"] = "Please enter your name."
    try:
        validate_email(email)
    except ValidationError:
        errors["email"] = "Please enter a valid email address."
    if phone and not PHONE_RE.match(phone):
        errors["phone"] = "Please enter a valid phone number."
    if cfg.require_phone and not phone:
        errors["phone"] = "Please enter your WhatsApp / phone number."
    if code and not re.match(r"^\+\d{1,4}$", code):
        errors["countryCode"] = "Invalid country code."
    options = service_options(cfg)
    if cfg.require_service and not service:
        errors["service"] = "Please choose a service."
    elif service and options and service not in options:
        errors["service"] = "Please choose one of the listed services."
    budget = None
    if budget_raw:
        budget = BudgetOption.objects.filter(is_active=True).filter(value=budget_raw).first() or BudgetOption.objects.filter(is_active=True, label=budget_raw).first()
        if not budget:
            errors["budget"] = "Please choose one of the listed budget ranges."
    elif cfg.require_budget:
        errors["budget"] = "Please choose a budget range."
    if len(message) < 10:
        errors["message"] = "Please tell us a little more about your project (at least 10 characters)."
    if cfg.consent_required and not data.get("consent"):
        errors["consent"] = "Please accept to continue."
    if errors:
        raise ValidationError(errors)
    return dict(name=name, email=email, phone=phone, country_code=code, service=service, budget=budget, message=message)


def submit_lead(data: dict, request, source="quote_modal") -> tuple[Lead, bool]:
    """Validate → de-duplicate → store → notify. Returns (lead, created)."""
    from apps.cms.models import Service
    from apps.mailer.service import notify_staff_by_email

    cfg = LeadFormConfig.load()
    clean = validate_lead_payload(data, cfg)
    spam = []
    if data.get("website"):  # honeypot field is invisible to humans
        spam.append("honeypot filled")
    ok, reason = check_form_token(data.get("formToken", ""), cfg.min_seconds_to_submit)
    if not ok:
        spam.append(reason)
    if len(re.findall(r"https?://", clean["message"])) > 3:
        spam.append("too many links")

    content_hash = hashlib.sha256(f"{clean['email']}|{clean['message']}".encode()).hexdigest()
    recent = Lead.objects.filter(content_hash=content_hash, created_at__gte=timezone.now() - timezone.timedelta(hours=24)).first()
    if recent:
        return recent, False  # same person, same message: idempotent (double-click / retry)

    svc = Service.objects.filter(title=clean["service"]).first() if clean["service"] else None
    with transaction.atomic():
        lead = Lead.objects.create(
            name=clean["name"], email=clean["email"], country_code=clean["country_code"], phone=clean["phone"], service=svc,
            service_label=clean["service"], budget=clean["budget"], budget_label=clean["budget"].label if clean["budget"] else "",
            message=clean["message"], source=source, source_page=clean_plain(data.get("page", ""), 300),
            utm_source=clean_plain(data.get("utm_source", ""), 120), utm_medium=clean_plain(data.get("utm_medium", ""), 120),
            utm_campaign=clean_plain(data.get("utm_campaign", ""), 160), consent_given=bool(data.get("consent")),
            marketing_consent=bool(data.get("marketingConsent")) and cfg.marketing_optin_enabled,
            visitor_hash=visitor_hash(request), user_agent=request.META.get("HTTP_USER_AGENT", "")[:300],
            content_hash=content_hash, is_spam=bool(spam), spam_reason="; ".join(spam)[:200],
            status=Lead.ARCHIVED if spam else Lead.NEW,
        )
        if lead.marketing_consent:
            from apps.marketing.models import Subscriber

            sub, _ = Subscriber.objects.get_or_create(email=lead.email, defaults={"name": lead.name})
            if sub.status != "suppressed":
                sub.consent_at, sub.consent_source = timezone.now(), f"Contact form {lead.reference}"
                if sub.status == "unsubscribed":
                    sub.status = "subscribed"
                sub.save()
    if not spam:
        try:
            notify("lead", f"New lead: {lead.name}", f"{lead.service_label or 'No service'} · {lead.budget_label or 'No budget'}", f"/dashboard/leads/{lead.pk}/", module="leads", level="success")
            body = (f"New lead {lead.reference}\n\nName: {lead.name}\nEmail: {lead.email}\nPhone: {lead.full_phone}\nService: {lead.service_label}\n"
                    f"Budget: {lead.budget_label}\n\nMessage:\n{lead.message}\n\nOpen in dashboard: /dashboard/leads/{lead.pk}/")
            msg = notify_staff_by_email("lead", f"[AUB SQUARE] New lead {lead.reference} – {lead.name}", body)
            extra = cfg.extra_recipients()
            if msg and extra:
                from apps.mailer.service import queue_email

                queue_email(extra, msg.subject, body, kind="notification")
        except Exception:  # the lead is already safely stored – never fail the visitor's request
            log.exception("lead notification failed for %s", lead.reference)
        from apps.outbound.services import speed_to_lead

        speed_to_lead(lead)
    return lead, True
