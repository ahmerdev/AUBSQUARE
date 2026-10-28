"""Business rules for outbound sales: prospects, de-duplication, do-not-contact, conversion to leads, speed-to-lead."""
import csv
import io
import logging
import re
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone

from apps.core.sanitize import clean_plain
from apps.core.services import log_activity, notify
from . import netguard
from .models import CATEGORIES, OutboundSettings, Prospect, ProspectNote, SuppressionEntry, domain_of

log = logging.getLogger(__name__)
CATEGORY_KEYS = {k for k, _ in CATEGORIES}


# ------------------------------------------------------------------ categories
from apps.leads.categories import lead_category  # noqa: E402,F401  (re-exported)


# ------------------------------------------------------------------ do-not-contact
def is_suppressed(email: str = "", website: str = "") -> str:
    """Returns the reason text if this address/domain must not be contacted, else ''."""
    email = (email or "").strip().lower()
    dom = (email.split("@")[-1] if "@" in email else "") or domain_of(website)
    q = SuppressionEntry.objects.none()
    from django.db.models import Q

    cond = Q()
    if email:
        cond |= Q(email=email)
    if dom:
        cond |= Q(domain=dom)
    if not cond:
        return ""
    hit = SuppressionEntry.objects.filter(cond).first()
    if hit:
        return f"On the do-not-contact list ({hit.get_reason_display().lower()})"
    from apps.marketing.models import Subscriber

    if email and Subscriber.objects.filter(email=email, status__in=["unsubscribed", "suppressed", "bounced"]).exists():
        return "This address unsubscribed from our emails"
    return ""


def suppress(email="", domain="", reason="manual", note=""):
    email = (email or "").strip().lower()
    domain = (domain or "").strip().lower()
    if not (email or domain):
        return None
    obj, _ = SuppressionEntry.objects.get_or_create(email=email, domain=domain, defaults={"reason": reason, "note": note[:200]})
    if email:
        Prospect.objects.filter(email=email).exclude(status=Prospect.CONVERTED).update(status=Prospect.SUPPRESSED, next_follow_up_at=None)
        from .models import SequenceEnrollment

        SequenceEnrollment.objects.filter(prospect__email=email, status="active").update(status="stopped", stop_reason="do not contact", next_at=None)
        from .models import OutreachMessage

        OutreachMessage.objects.filter(prospect__email=email, status__in=["draft", "approved"]).update(status="skipped", block_reason="do not contact")
    return obj


def region_block(prospect: Prospect, cfg: OutboundSettings | None = None) -> str:
    cfg = cfg or OutboundSettings.load()
    if cfg.region_mode == "manual_only":
        return "Cold email is turned off in Outbound settings."
    if not prospect.country:
        return "Country is unknown – add it before emailing."
    if prospect.country.strip().lower() not in cfg.allowed_country_set():
        return f"Cold email to {prospect.country} is not enabled in Outbound settings."
    return ""


def email_block(prospect: Prospect, cfg: OutboundSettings | None = None) -> str:
    """Why this prospect cannot be emailed right now ('' = OK)."""
    cfg = cfg or OutboundSettings.load()
    if prospect.status in (Prospect.SUPPRESSED, Prospect.REJECTED, Prospect.CONVERTED):
        return {"suppressed": "Marked do-not-contact.", "rejected": "Marked as not a fit.", "converted": "Already became a lead."}[prospect.status]
    if not prospect.email:
        return "No email address on file."
    try:
        validate_email(prospect.email)
    except ValidationError:
        return "The email address is not valid."
    sup = is_suppressed(prospect.email, prospect.website)
    if sup:
        return sup
    if not cfg.postal_address.strip():
        return "Add your business postal address in Outbound settings first (needed in every email footer)."
    return region_block(prospect, cfg)


def daily_remaining(cfg: OutboundSettings | None = None) -> int:
    from .models import OutreachMessage

    cfg = cfg or OutboundSettings.load()
    start = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    used = OutreachMessage.objects.filter(channel="email", status__in=["queued", "sent"], queued_at__gte=start).count()
    return max(cfg.daily_email_limit - used, 0)


# ------------------------------------------------------------------ prospects
def find_duplicate(website="", email="", external_id="", business_name="", city="") -> Prospect | None:
    dom = domain_of(website)
    if external_id:
        p = Prospect.objects.filter(external_id=external_id).first()
        if p:
            return p
    if dom:
        p = Prospect.objects.filter(domain=dom).first()
        if p:
            return p
    if email:
        p = Prospect.objects.filter(email=email.strip().lower()).first()
        if p:
            return p
    if business_name and city:
        return Prospect.objects.filter(business_name__iexact=business_name, city__iexact=city).first()
    return None


def create_prospect(data: dict, source="manual", user=None) -> tuple[Prospect | None, str]:
    """Validates and stores one prospect. Returns (prospect, '') or (None, reason). Duplicates return (existing, 'duplicate')."""
    name = clean_plain(data.get("business_name", ""), 200)
    website = netguard.normalize_url(data.get("website", "")) if data.get("website") else ""
    email = clean_plain(data.get("email", ""), 254).lower()
    if len(name) < 2:
        return None, "Business name is missing."
    if email:
        try:
            validate_email(email)
        except ValidationError:
            email = ""
    if not (website or email or data.get("phone")):
        return None, "Needs at least a website, email or phone."
    dup = find_duplicate(website, email, data.get("external_id", ""), name, data.get("city", ""))
    if dup:
        return dup, "duplicate"
    cat = data.get("category") if data.get("category") in CATEGORY_KEYS else "other"
    p = Prospect.objects.create(
        business_name=name, category=cat, website=website, email=email, email_source=clean_plain(data.get("email_source", "") or ("OpenStreetMap" if email and source == "osm" else ""), 40),
        phone=clean_plain(data.get("phone", ""), 60), city=clean_plain(data.get("city", ""), 100), country=clean_plain(data.get("country", ""), 80),
        address=clean_plain(data.get("address", ""), 300), source=source, external_id=clean_plain(data.get("external_id", ""), 100),
        notes=clean_plain(data.get("notes", ""), 2000), created_by=user,
    )
    reason = is_suppressed(p.email, p.website)
    if reason:
        p.status = Prospect.SUPPRESSED
        p.save(update_fields=["status", "updated_at"])
    return p, ""


def import_candidates(candidates, source, user=None) -> dict:
    res = {"added": 0, "duplicates": 0, "skipped": 0, "errors": []}
    for c in candidates:
        p, why = create_prospect(c, source, user)
        if why == "duplicate":
            res["duplicates"] += 1
        elif p:
            res["added"] += 1
        else:
            res["skipped"] += 1
            if len(res["errors"]) < 10:
                res["errors"].append(f"{c.get('business_name') or '(no name)'}: {why}")
    return res


CSV_ALIASES = {"business_name": ("business_name", "business", "name", "company", "company_name"), "website": ("website", "url", "site", "web"), "email": ("email", "e-mail", "email_address"),
               "phone": ("phone", "telephone", "mobile", "whatsapp"), "city": ("city", "town"), "country": ("country",), "category": ("category", "industry", "type"), "address": ("address",)}
MAX_CSV_ROWS = 500


def parse_csv(raw: bytes):
    text = raw.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValidationError("The file is empty.")
    cols = {f.strip().lower().replace(" ", "_"): f for f in reader.fieldnames if f}
    mapping = {}
    for key, names in CSV_ALIASES.items():
        for n in names:
            if n in cols:
                mapping[key] = cols[n]
                break
    if "business_name" not in mapping:
        raise ValidationError("The CSV needs a column called business_name (or name / company).")
    rows = []
    for i, row in enumerate(reader):
        if i >= MAX_CSV_ROWS:
            raise ValidationError(f"Please import at most {MAX_CSV_ROWS} rows at a time.")
        d = {k: (row.get(col) or "").strip() for k, col in mapping.items()}
        cat = d.get("category", "").lower().replace(" ", "_").replace("/", "_")
        d["category"] = cat if cat in CATEGORY_KEYS else next((k for k, label in CATEGORIES if cat and cat in label.lower()), "other")
        rows.append(d)
    return rows


# ------------------------------------------------------------------ audit → prospect
def apply_audit(prospect: Prospect, audit, user=None):
    prospect.opportunity_score = audit.score
    prospect.opportunity_level = audit.level if audit.reachable else "unknown"
    fields = ["opportunity_score", "opportunity_level", "updated_at"]
    if audit.reachable and prospect.status == Prospect.NEW:
        prospect.status = Prospect.AUDITED
        fields.append("status")
    if audit.reachable and not prospect.email and audit.emails_found:
        prospect.email, prospect.email_source = audit.emails_found[0], (audit.final_url or audit.url)[:40]
        fields += ["email", "email_source"]
        if is_suppressed(prospect.email, prospect.website):
            prospect.status = Prospect.SUPPRESSED
            fields.append("status")
    if audit.reachable and not prospect.whatsapp and audit.whatsapp_link:
        digits = "".join(ch for ch in audit.whatsapp_link.split("?")[0] if ch.isdigit())
        if len(digits) >= 8:
            prospect.whatsapp = digits[:30]
            fields.append("whatsapp")
    prospect.save(update_fields=list(set(fields)))


def audit_prospect(prospect: Prospect, user=None):
    from .audit import find_contact_email, run_audit

    if not prospect.website:
        return None
    a = run_audit(prospect.website, "prospect", prospect, prospect.category)
    apply_audit(prospect, a, user)
    if a.reachable and not prospect.email:
        email, where = find_contact_email(prospect.website, a)
        if email and not is_suppressed(email):
            prospect.email, prospect.email_source = email, where[:40]
            prospect.save(update_fields=["email", "email_source", "updated_at"])
    ProspectNote.objects.create(prospect=prospect, author=user, kind="audit", body=(f"Audit done: score {a.score} ({a.level})." if a.reachable else f"Audit could not be completed: {a.error}"))
    return a


# ------------------------------------------------------------------ conversion
def convert_to_lead(prospect: Prospect, user=None, message: str = ""):
    """Creates (or reuses) a Lead from a prospect who showed interest. Idempotent."""
    from apps.leads.models import Lead

    if prospect.lead_id:
        return prospect.lead, False
    email = prospect.email
    if not email:
        raise ValidationError("Add an email address for this prospect first (leads need one).")
    existing = Lead.objects.filter(email__iexact=email, is_spam=False).order_by("-created_at").first()
    audit = prospect.audits.filter(reachable=True).first()
    top = "; ".join(f["title"] for f in (audit.findings[:3] if audit else []))
    with transaction.atomic():
        lead = existing or Lead.objects.create(
            name=prospect.business_name[:120], email=email, phone=prospect.phone[:40], source="outbound", status=Lead.QUALIFIED if prospect.status == Prospect.REPLIED else Lead.NEW,
            message=(message or f"Outbound prospect ({prospect.get_category_display()}, {prospect.city or prospect.country}). Website: {prospect.website or 'n/a'}. Opportunity score {prospect.opportunity_score}. " + (f"Findings: {top}" if top else ""))[:4000],
            service_label=(audit.findings[0]["service"] if audit and audit.findings else "")[:160], category=lead_category(" ".join(f["category"] + " " + f["service"] for f in (audit.findings if audit else [])) or ""),
            assigned_to=prospect.assigned_to or user, consent_given=False, content_hash=f"outbound-{prospect.pk}",
        )
        prospect.lead, prospect.status = lead, Prospect.CONVERTED
        prospect.next_follow_up_at = None
        prospect.save(update_fields=["lead", "status", "next_follow_up_at", "updated_at"])
        from .models import SequenceEnrollment

        SequenceEnrollment.objects.filter(prospect=prospect, status="active").update(status="stopped", stop_reason="became a lead", next_at=None)
        ProspectNote.objects.create(prospect=prospect, author=user, kind="converted", body=f"Converted to lead {lead.reference}.")
    return lead, existing is None


# ------------------------------------------------------------------ speed to lead
def minutes_open(lead) -> int:
    return int((timezone.now() - lead.created_at).total_seconds() // 60)


def speed_to_lead(lead):
    """Called right after a website lead is stored: tag it, alert the team, optionally acknowledge instantly. Never raises."""
    try:
        cfg = OutboundSettings.load()
        cat = lead_category(lead.message[:400], lead.service_label)
        if lead.category != cat:
            lead.category = cat
            lead.save(update_fields=["category", "updated_at"])
        notify("lead", f"Reply fast: {lead.name} just enquired", f"{lead.get_category_display()} · aim to reply within {cfg.speed_alert_minutes} min", f"/dashboard/leads/{lead.pk}/", module="leads", level="danger")
        if cfg.auto_reply_enabled and lead.email and not is_suppressed(lead.email):
            from apps.leads.models import LeadFormConfig
            from apps.mailer.service import queue_email

            if lead.consent_given or not LeadFormConfig.load().consent_required:
                ctx = {"name": lead.name.split(" ")[0] or lead.name, "business": cfg.sender_business, "reference": lead.reference}
                subject = _fill(cfg.auto_reply_subject, ctx)
                body = _fill(cfg.auto_reply_body, ctx)
                queue_email([lead.email], f"{subject} [{lead.reference}]", body, kind="system", lead=lead, headers={"Auto-Submitted": "auto-replied"})
    except Exception:
        log.exception("speed-to-lead failed for lead %s", getattr(lead, "pk", "?"))


def staff_email(subject: str, body: str, event: str = "lead"):
    """Email the team (same recipients and on/off switches as the 'New lead' email). Never raises – the dashboard notification is the primary signal."""
    try:
        from apps.mailer.service import notify_staff_by_email

        return notify_staff_by_email(event, subject, body)
    except Exception:
        log.exception("staff email failed: %s", subject)
        return None


def _fill(text, ctx):
    return re.sub(r"\{(\w+)\}", lambda m: str(ctx.get(m.group(1), m.group(0))), text)


def mark_first_response(lead):
    if lead.first_response_at is None:
        lead.first_response_at = timezone.now()
        lead.save(update_fields=["first_response_at", "updated_at"])


def check_overdue(cfg: OutboundSettings | None = None) -> dict:
    """Run from cron / 'Run checks now': alerts once per lead that waited too long, and once for overdue follow-ups / silent proposals."""
    from apps.leads.models import Lead
    from .models import Proposal, ProposalEvent

    cfg = cfg or OutboundSettings.load()
    now = timezone.now()
    out = {"slow_leads": 0, "follow_ups": 0, "proposals": 0}
    cutoff = now - timedelta(minutes=cfg.speed_alert_minutes)
    for lead in Lead.objects.filter(is_spam=False, first_response_at__isnull=True, status=Lead.NEW, speed_alerted_at__isnull=True, created_at__lte=cutoff, created_at__gte=now - timedelta(days=7)):
        notify("lead", f"No reply yet: {lead.name}", f"Waiting {minutes_open(lead)} minutes – the first reply decides who wins the job.", f"/dashboard/leads/{lead.pk}/", module="leads", level="danger")
        lead.speed_alerted_at = now
        lead.save(update_fields=["speed_alerted_at"])
        staff_email(f"[ACTION] No reply yet to {lead.reference} – {lead.name} ({minutes_open(lead)} min)", f"{lead.name} <{lead.email}> enquired {minutes_open(lead)} minutes ago and nobody has replied yet.\n\nThe first reply usually decides who wins the job.\nOpen: /dashboard/leads/{lead.pk}/")
        out["slow_leads"] += 1
    for lead in Lead.objects.filter(is_spam=False, follow_up_at__lte=now, follow_up_at__gte=now - timedelta(days=2)).exclude(status__in=["won", "lost", "archived"]):
        if not lead.notes.filter(body__startswith="[reminder]", created_at__gte=lead.follow_up_at).exists():
            notify("lead", f"Follow-up due: {lead.name}", lead.follow_up_note or "A follow-up you scheduled is due.", f"/dashboard/leads/{lead.pk}/", module="leads", level="warning")
            from apps.leads.models import LeadNote

            LeadNote.objects.create(lead=lead, body="[reminder] Follow-up reminder sent to the team.")
            staff_email(f"Follow-up due: {lead.reference} – {lead.name}", f"{lead.follow_up_note or 'A follow-up you scheduled is due.'}\n\nOpen: /dashboard/leads/{lead.pk}/")
            out["follow_ups"] += 1
    limit = now - timedelta(days=cfg.proposal_reminder_days)
    for pr in Proposal.objects.filter(status__in=["sent", "viewed"], sent_at__lte=limit, reminder_sent_at__isnull=True):
        notify("proposal", f"No answer on proposal {pr.reference}", f"{pr.client_name} – sent {pr.sent_at:%d %b}, {'viewed' if pr.view_count else 'not opened yet'}. Time to follow up.", f"/dashboard/proposals/{pr.pk}/", module="proposals", level="warning")
        pr.reminder_sent_at = now
        pr.save(update_fields=["reminder_sent_at"])
        ProposalEvent.objects.create(proposal=pr, kind="reminder", detail="Team reminded to follow up")
        staff_email(f"No answer yet on proposal {pr.reference}", f"{pr.client_name} – sent {pr.sent_at:%d %b}, {'viewed' if pr.view_count else 'not opened yet'}. Time to follow up.\n\nOpen: /dashboard/proposals/{pr.pk}/")
        out["proposals"] += 1
    Proposal.objects.filter(status__in=["sent", "viewed"], valid_until__lt=timezone.localdate()).update(status="expired")
    try:
        from apps.billing.services import billing_checks

        out.update(billing_checks())
    except Exception:
        log.exception("billing checks failed")
    return out
