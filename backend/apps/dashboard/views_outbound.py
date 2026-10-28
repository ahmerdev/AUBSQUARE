"""Outbound Sales: prospects, discovery, audits, pipeline, outreach queue, sequences, settings and reports."""
import re
import csv
import logging
from datetime import timedelta
from urllib.parse import quote

from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q, Sum
from django.http import HttpResponse
from django.conf import settings
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.sanitize import clean_plain
from apps.core.services import log_activity
from apps.leads.models import Lead
from apps.mailer.models import EmailSettings
from apps.outbound import discovery, outreach, pitch, services
from apps.outbound.audit import run_audit
from apps.outbound.models import (CATEGORIES, LEVELS, SCORE_RULES, OutboundSettings, OutreachMessage, OutreachTemplate, Prospect, ProspectNote, Sequence,
                                  SequenceEnrollment, SequenceStep, SiteAudit, SuppressionEntry)
from .mixins import needs

log = logging.getLogger(__name__)
CRUMB = ("Outbound Sales", "/dashboard/outbound/")


def _staff():
    from apps.accounts.models import User

    return User.objects.filter(is_active=True, status="approved")


def _page(request, qs, n=25):
    qd = request.GET.copy()
    qd.pop("page", None)
    return Paginator(qs, n).get_page(request.GET.get("page")), qd.urlencode()


# ------------------------------------------------------------------ overview
def readiness():
    es, cfg = EmailSettings.load(), OutboundSettings.load()
    return [
        ("Outgoing email (SMTP) is set up", es.smtp_configured, "/dashboard/email-settings/", "Needed to send any email."),
        ("Replies are read automatically (IMAP)", es.imap_configured, "/dashboard/email-settings/", "Without it, prospect replies are not detected and follow-ups cannot stop themselves."),
        ("Business postal address is filled in", bool(cfg.postal_address.strip()), "/dashboard/outbound-settings/", "Required in every cold-email footer."),
        ("Allowed countries are chosen", cfg.region_mode == "allow_list" and bool(cfg.allowed_country_set()), "/dashboard/outbound-settings/", "Cold email is only sent to these countries."),
        ("Your public website address is set (not localhost)", not re.search(r"localhost|127\.0\.0\.1|\.local\b", settings.SITE_URL), "/dashboard/outbound-settings/",
         "Emails link to your portfolio and to each prospect's audit report. Set SITE_URL in your .env to your real address, or prospects cannot open them."),
        ("Gemini key (optional, for AI pitches)", cfg.has_gemini_key, "/dashboard/outbound-settings/", "Without it, clearly labelled templates are used."),
    ]


@needs("outbound", "view")
def overview(request):
    outreach.sync_status()
    cfg = OutboundSettings.load()
    pc = {r["status"]: r["n"] for r in Prospect.objects.values("status").annotate(n=Count("id"))}
    now = timezone.now()
    waiting = Lead.objects.filter(is_spam=False, status="new", first_response_at__isnull=True, created_at__lte=now - timedelta(minutes=cfg.speed_alert_minutes)).order_by("created_at")
    from apps.outbound.models import Proposal

    ctx = {
        "pc": pc, "prospect_total": sum(pc.values()), "to_audit": Prospect.objects.filter(status="new").exclude(website="").count(),
        "high": Prospect.objects.filter(opportunity_level="high").exclude(status__in=["converted", "rejected", "suppressed"]).count(),
        "drafts": OutreachMessage.objects.filter(status="draft", block_reason="").count(), "blocked": OutreachMessage.objects.filter(status="draft").exclude(block_reason="").count(),
        "approved": OutreachMessage.objects.filter(status="approved").count(), "sent_today": cfg.daily_email_limit - services.daily_remaining(cfg), "limit": cfg.daily_email_limit,
        "replied": pc.get("replied", 0), "converted_leads": Lead.objects.filter(source="outbound").count(),
        "waiting_leads": waiting[:6], "waiting_count": waiting.count(), "minutes": cfg.speed_alert_minutes,
        "open_proposals": Proposal.objects.filter(status__in=["sent", "viewed", "accept_requested"]).count(),
        "accept_requests": Proposal.objects.filter(status="accept_requested").select_related("lead")[:5],
        "ready": readiness(), "can_edit": request.user.can("outbound", "edit"), "can_settings": request.user.can("outbound", "manage_settings"),
        "page_title": "Outbound overview", "crumbs": [("Dashboard", "/dashboard/"), ("Outbound Sales", "")],
    }
    ctx["ready_ok"] = all(ok for _, ok, _, _ in ctx["ready"][:4])
    return render(request, "dashboard/outbound/overview.html", ctx)


@needs("outbound", "edit")
@require_POST
def run_checks(request):
    res = services.check_overdue()
    n = outreach.advance_due(user=request.user)
    sent = outreach.send_approved()
    messages.success(request, f"Checks done: {res['slow_leads']} slow lead alert(s), {res['follow_ups']} follow-up reminder(s), {res['proposals']} proposal reminder(s), {n} new follow-up draft(s), {sent['queued']} email(s) queued.")
    return redirect(request.POST.get("next") or "dashboard:outbound")


# ------------------------------------------------------------------ prospects
def _prospect_filter(request):
    g = request.GET
    qs = Prospect.objects.select_related("assigned_to")
    if g.get("q"):
        q = g["q"].strip()
        qs = qs.filter(Q(business_name__icontains=q) | Q(domain__icontains=q) | Q(email__icontains=q) | Q(city__icontains=q) | Q(phone__icontains=q))
    for f in ("status", "category", "country"):
        if g.get(f):
            qs = qs.filter(**{f: g[f]})
    if g.get("level"):
        qs = qs.filter(opportunity_level=g["level"])
    if g.get("email") == "yes":
        qs = qs.exclude(email="")
    elif g.get("email") == "no":
        qs = qs.filter(email="")
    return qs


@needs("outbound", "view")
def prospects_list(request):
    qs = _prospect_filter(request)
    page, qs_str = _page(request, qs)
    counts = {r["status"]: r["n"] for r in Prospect.objects.values("status").annotate(n=Count("id"))}
    return render(request, "dashboard/outbound/prospects.html", {
        "page": page, "qs": qs_str, "g": request.GET, "statuses": Prospect.STATUS, "counts": counts, "total": sum(counts.values()), "categories": CATEGORIES, "levels": LEVELS,
        "high_count": Prospect.objects.filter(opportunity_level="high").exclude(status__in=["converted", "rejected", "suppressed"]).count(),
        "ready_count": Prospect.objects.filter(status="audited").exclude(email="").count(),
        "countries": Prospect.objects.exclude(country="").values_list("country", flat=True).distinct().order_by("country"), "sequences": Sequence.objects.filter(is_active=True),
        "can_create": request.user.can("outbound", "create"), "can_edit": request.user.can("outbound", "edit"), "can_delete": request.user.can("outbound", "delete"), "can_export": request.user.can("outbound", "export"),
        "page_title": "Prospects", "crumbs": [("Dashboard", "/dashboard/"), CRUMB, ("Prospects", "")],
    })


@needs("outbound", "view")
def prospect_report(request, pk):
    """Staff shortcut: opens the exact report page the prospect will see (views from here are not counted)."""
    p = get_object_or_404(Prospect, pk=pk)
    return redirect(f"/r/{p.token}/?preview=1")


@needs("outbound", "create")
@require_POST
def prospects_discover(request):
    cfg = OutboundSettings.load()
    contact = EmailSettings.load().from_email
    cat, city, country = request.POST.get("category", "other"), request.POST.get("city", ""), clean_plain(request.POST.get("country", ""), 80)
    try:
        cands, msgs = discovery.discover(cat, clean_plain(city, 100), country, int(request.POST.get("limit") or 40), contact)
    except discovery.DiscoveryError as exc:
        messages.error(request, str(exc))
        return redirect("dashboard:prospects")
    except ValueError:
        messages.error(request, "Choose a number between 1 and 80 for the limit.")
        return redirect("dashboard:prospects")
    res = services.import_candidates(cands, "osm", request.user)
    for m in msgs:
        messages.info(request, m)
    log_activity(request.user, "prospects.discovered", None, f"{cat} / {city} / {country}: +{res['added']}", request)
    if res["added"] or res["duplicates"]:
        messages.success(request, f"OpenStreetMap search finished: {res['added']} new prospect(s) added, {res['duplicates']} already in your list, {res['skipped']} skipped. Next: select them and press “Audit websites”.")
    return redirect("dashboard:prospects")


@needs("outbound", "create")
@require_POST
def prospects_import(request):
    f = request.FILES.get("file")
    if not f:
        messages.error(request, "Choose a CSV file first.")
    elif f.size > 1_000_000:
        messages.error(request, "That file is larger than 1 MB.")
    else:
        try:
            rows = services.parse_csv(f.read())
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
            return redirect("dashboard:prospects")
        res = services.import_candidates(rows, "csv", request.user)
        log_activity(request.user, "prospects.csv_import", None, f"+{res['added']}", request)
        messages.success(request, f"CSV imported: {res['added']} added, {res['duplicates']} duplicates ignored, {res['skipped']} skipped (missing name or contact details).")
        for e in res["errors"][:3]:
            messages.info(request, e)
    return redirect("dashboard:prospects")


class ProspectForm(forms.ModelForm):
    class Meta:
        model = Prospect
        fields = ["business_name", "category", "website", "email", "phone", "whatsapp", "country", "city", "address", "assigned_to", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 3}), "country": forms.TextInput(attrs={"data-geo-country": "", "placeholder": "Search a country…"}),
                   "city": forms.TextInput(attrs={"data-geo-city": "", "placeholder": "Choose a country first (or type any city)"})}

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.fields["assigned_to"].queryset = _staff()
        for f in self.fields.values():
            f.widget.attrs["class"] = "input"

    def clean_website(self):
        from apps.outbound import netguard

        raw = self.cleaned_data.get("website", "").strip()
        if not raw:
            return ""
        url = netguard.normalize_url(raw)
        if not url:
            raise forms.ValidationError("Enter a valid website address, like example.com.")
        return url

    def clean(self):
        d = super().clean()
        if not (d.get("website") or d.get("email") or d.get("phone")):
            raise forms.ValidationError("Add at least a website, email or phone number.")
        return d


@needs("outbound", "create")
def prospect_new(request):
    form = ProspectForm(request.POST or None, initial={"category": "other"})
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        dup = services.find_duplicate(d["website"], d["email"], "", d["business_name"], d["city"])
        if dup:
            messages.info(request, "This business is already in your list.")
            return redirect("dashboard:prospect_detail", pk=dup.pk)
        p = form.save(commit=False)
        p.source, p.created_by = "manual", request.user
        p.save()
        if services.is_suppressed(p.email, p.website):
            p.status = Prospect.SUPPRESSED
            p.save(update_fields=["status"])
            messages.warning(request, "Saved, but this address/domain is on the do-not-contact list, so it will never be emailed.")
        else:
            messages.success(request, "Prospect added.")
        return redirect("dashboard:prospect_detail", pk=p.pk)
    return render(request, "dashboard/outbound/prospect_form.html", {"form": form, "page_title": "Add prospect", "crumbs": [("Dashboard", "/dashboard/"), CRUMB, ("Prospects", "/dashboard/prospects/"), ("Add", "")]})


@needs("outbound", "view")
def prospect_detail(request, pk):
    p = get_object_or_404(Prospect.objects.select_related("lead", "assigned_to"), pk=pk)
    outreach.sync_status()
    audit = p.audits.first()
    cfg = OutboundSettings.load()
    form = ProspectForm(instance=p)
    wa_text = ""
    if p.whatsapp_link:
        wa_text = p.whatsapp_link + "?text=" + quote(OutreachMessage.objects.filter(prospect=p, channel="whatsapp").values_list("body", flat=True).first() or "")
    return render(request, "dashboard/outbound/prospect_detail.html", {
        "p": p, "audit": audit, "audits": p.audits.all()[:5], "msgs": p.messages.all()[:10], "activity": p.activity.select_related("author")[:20], "form": form, "report_url": pitch.report_url(p), "report_ready": pitch.has_report(p), "email_why": services.email_block(p, cfg),
        "sequences": Sequence.objects.filter(is_active=True), "enrollments": p.enrollments.select_related("sequence"), "wa_link": wa_text,
        "can_edit": request.user.can("outbound", "edit"), "can_delete": request.user.can("outbound", "delete"), "ai_ready": cfg.ai_enabled and cfg.has_gemini_key,
        "page_title": p.business_name, "crumbs": [("Dashboard", "/dashboard/"), CRUMB, ("Prospects", "/dashboard/prospects/"), (p.business_name, "")],
    })


@needs("outbound", "edit")
@require_POST
def prospect_action(request, pk):
    p = get_object_or_404(Prospect, pk=pk)
    act, u = request.POST.get("action"), request.user
    back = redirect("dashboard:prospect_detail", pk=p.pk)
    if act == "save":
        form = ProspectForm(request.POST, instance=p)
        if form.is_valid():
            form.save()
            messages.success(request, "Saved.")
        else:
            messages.error(request, "Could not save: " + "; ".join(f"{k}: {v[0]}" for k, v in form.errors.items()))
    elif act == "audit":
        if not p.website:
            messages.error(request, "This prospect has no website to audit.")
        else:
            a = services.audit_prospect(p, u)
            messages.success(request, f"Audit finished: score {a.score} ({a.get_level_display()})." if a.reachable else f"The website could not be audited: {a.error}")
    elif act == "note":
        body = clean_plain(request.POST.get("body", ""), 1500)
        if body:
            ProspectNote.objects.create(prospect=p, author=u, body=body)
    elif act in ("draft_email", "draft_ai", "draft_whatsapp"):
        channel = "whatsapp" if act == "draft_whatsapp" else "email"
        if channel == "email":
            why = services.email_block(p)
            if why:
                messages.error(request, "Cannot draft an email: " + why)
                return back
        step = p.messages.filter(channel=channel).exclude(status="skipped").count() + 1
        m = outreach.draft_message(p, step, channel, u, use_ai=True if act == "draft_ai" else False)
        messages.success(request, ("Draft written by AI" if m.generated_by == "ai" else "Draft created from a template") + (f" ({m.block_reason})" if m.block_reason else "") + ". Review it in Outreach, then approve.")
        return redirect("dashboard:outreach")
    elif act == "enroll":
        seq = get_object_or_404(Sequence, pk=request.POST.get("sequence"))
        ok, why = outreach.enroll(p, seq, u)
        messages.success(request, "Added to the sequence. The first email is waiting for your approval in Outreach.") if ok else messages.error(request, why)
    elif act == "stop_sequences":
        outreach.stop_enrollments(p, "stopped by staff")
        messages.success(request, "Sequences stopped and waiting drafts skipped.")
    elif act == "convert":
        try:
            lead, created = services.convert_to_lead(p, u, clean_plain(request.POST.get("message", ""), 2000))
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
            return back
        log_activity(u, "prospect.converted", p, lead.reference, request)
        messages.success(request, f"Lead {lead.reference} created. It is now in your Leads pipeline.")
        return redirect("dashboard:lead_detail", pk=lead.pk)
    elif act == "reject":
        p.status = Prospect.REJECTED
        p.save(update_fields=["status", "updated_at"])
        outreach.stop_enrollments(p, "marked not a fit")
        messages.success(request, "Marked as not a fit.")
    elif act == "reopen":
        p.status = Prospect.AUDITED if p.audits.exists() else Prospect.NEW
        p.save(update_fields=["status", "updated_at"])
    elif act == "dnc":
        services.suppress(email=p.email, domain="" if p.email else p.domain, reason="manual", note=f"Added from prospect {p.business_name}")
        p.status = Prospect.SUPPRESSED
        p.save(update_fields=["status", "updated_at"])
        outreach.stop_enrollments(p, "do not contact")
        log_activity(u, "prospect.dnc", p, "", request)
        messages.success(request, "Added to the do-not-contact list.")
    elif act == "assign":
        p.assigned_to = _staff().filter(pk=request.POST.get("assigned_to")).first()
        p.save(update_fields=["assigned_to", "updated_at"])
    return back


@needs("outbound", "delete")
@require_POST
def prospect_delete(request, pk):
    p = get_object_or_404(Prospect, pk=pk)
    log_activity(request.user, "prospect.deleted", p, p.business_name, request)
    p.delete()
    messages.success(request, "Prospect deleted.")
    return redirect("dashboard:prospects")


@needs("outbound", "edit")
@require_POST
def prospects_bulk(request):
    ids = [i for i in request.POST.getlist("ids") if i.isdigit()] or [i for i in request.POST.get("ids_csv", "").split(",") if i.isdigit()]
    qs = Prospect.objects.filter(pk__in=ids)
    act, n = request.POST.get("action"), qs.count()
    if not n:
        messages.error(request, "Select at least one prospect.")
    elif act == "audit":
        done = failed = 0
        for p in qs.exclude(website="")[:8]:
            a = services.audit_prospect(p, request.user)
            done += 1 if a and a.reachable else 0
            failed += 0 if a and a.reachable else 1
        messages.success(request, f"Audited {done} website(s); {failed} could not be reached." + (" (Up to 8 are audited per click – repeat for the rest.)" if n > 8 else ""))
    elif act == "reject":
        qs.update(status=Prospect.REJECTED)
        messages.success(request, f"{n} marked as not a fit.")
    elif act == "enroll":
        seq = get_object_or_404(Sequence, pk=request.POST.get("sequence"))
        ok = 0
        for p in qs:
            ok += 1 if outreach.enroll(p, seq, request.user)[0] else 0
        messages.success(request, f"{ok} of {n} added to “{seq.name}” (the rest are blocked: no email, wrong country, do-not-contact or already enrolled). Drafts wait for approval in Outreach.")
    elif act == "delete":
        if not request.user.can("outbound", "delete"):
            messages.error(request, "You don't have permission to delete.")
        else:
            qs.delete()
            messages.success(request, f"{n} deleted.")
    return redirect(request.POST.get("next") or "dashboard:prospects")


@needs("outbound", "export")
def prospects_export(request):
    qs = _prospect_filter(request)
    resp = HttpResponse(content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="prospects-{timezone.now():%Y%m%d}.csv"'
    resp.write("﻿")
    w = csv.writer(resp)
    safe = lambda v: ("'" + str(v)) if str(v)[:1] in ("=", "+", "-", "@") else ("" if v is None else str(v))
    w.writerow(["business", "category", "website", "email", "phone", "city", "country", "status", "score", "level"])
    for p in qs.iterator():
        w.writerow([safe(p.business_name), p.category, safe(p.website), safe(p.email), safe(p.phone), safe(p.city), safe(p.country), p.status, p.opportunity_score, p.opportunity_level])
    log_activity(request.user, "prospects.exported", None, f"{qs.count()} rows", request, security=True)
    return resp


# ------------------------------------------------------------------ own website audit (SEO)
@needs("seo", "view")
def site_audit(request):
    from django.conf import settings as dj

    default = dj.PREVIEW_SITE_URL or dj.SITE_URL
    audit = None
    if request.method == "POST":
        if not request.user.can("seo", "edit"):
            return redirect("dashboard:site_audit")
        audit = run_audit(request.POST.get("url", ""), "own")
        log_activity(request.user, "seo.site_audit", None, audit.url[:100], request)
        if not audit.reachable:
            messages.error(request, audit.error or "The website could not be audited.")
    return render(request, "dashboard/outbound/site_audit.html", {
        "audit": audit or SiteAudit.objects.filter(kind="own").first(), "history": SiteAudit.objects.filter(kind="own")[:8], "default_url": request.POST.get("url") or default,
        "can_run": request.user.can("seo", "edit"), "page_title": "Site audit", "crumbs": [("Dashboard", "/dashboard/"), ("SEO", "/dashboard/seo/"), ("Site audit", "")],
    })


# ------------------------------------------------------------------ pipeline board
LEAD_COLUMNS = [Lead.NEW, Lead.CONTACTED, Lead.QUALIFIED, Lead.PROPOSAL, Lead.WON, Lead.LOST]
PROSPECT_COLUMNS = [Prospect.NEW, Prospect.AUDITED, Prospect.CONTACTED, Prospect.REPLIED]


@needs("leads", "view")
def pipeline(request):
    g = request.GET
    mode = "prospects" if g.get("board") == "prospects" and request.user.can("outbound", "view") else "leads"
    cats = []
    if mode == "leads":
        base = Lead.objects.filter(is_spam=False).exclude(status="archived")
        if g.get("source"):
            base = base.filter(source=g["source"])
        if g.get("assigned") == "me":
            base = base.filter(assigned_to=request.user)
        counts = {r["category"]: r["n"] for r in base.values("category").annotate(n=Count("id"))}
        cats = [("", "All", sum(counts.values()))] + [(k, l, counts.get(k, 0)) for k, l in Lead.CATEGORIES]
        qs = base.filter(category=g["category"]) if g.get("category") else base
        qs = qs.select_related("assigned_to")
        week = timezone.now() - timedelta(days=45)
        cols = []
        for st in LEAD_COLUMNS:
            items = qs.filter(status=st)
            if st in (Lead.WON, Lead.LOST):
                items = items.filter(updated_at__gte=week)
            cols.append({"key": st, "label": dict(Lead.STATUS_CHOICES)[st], "items": list(items.order_by("-created_at")[:40]), "count": items.count()})
        sources = Lead.SOURCES
    else:
        qs = Prospect.objects.filter(status__in=PROSPECT_COLUMNS).select_related("assigned_to")
        if g.get("category"):
            qs = qs.filter(category=g["category"])
        cols = [{"key": st, "label": dict(Prospect.STATUS)[st], "items": list(qs.filter(status=st).order_by("-opportunity_score")[:40]), "count": qs.filter(status=st).count()} for st in PROSPECT_COLUMNS]
        sources = []
        cats = [("", "All", Prospect.objects.filter(status__in=PROSPECT_COLUMNS).count())] + [(k, l, Prospect.objects.filter(status__in=PROSPECT_COLUMNS, category=k).count()) for k, l in CATEGORIES]
    return render(request, "dashboard/outbound/pipeline.html", {
        "mode": mode, "cols": cols, "cats": cats, "g": g, "sources": sources, "can_move": request.user.can("leads" if mode == "leads" else "outbound", "edit"), "can_outbound": request.user.can("outbound", "view"),
        "page_title": "Pipeline board", "crumbs": [("Dashboard", "/dashboard/"), CRUMB, ("Pipeline board", "")],
    })


@needs("leads", "edit")
@require_POST
def pipeline_move(request):
    from django.http import JsonResponse

    kind, pk, to = request.POST.get("kind"), request.POST.get("id", ""), request.POST.get("to", "")
    if not pk.isdigit():
        return JsonResponse({"error": "bad id"}, status=400)
    if kind == "lead":
        lead = get_object_or_404(Lead, pk=pk)
        if to not in LEAD_COLUMNS or to == lead.status:
            return JsonResponse({"ok": True, "unchanged": True})
        old, lead.status = lead.status, to
        lead.save(update_fields=["status", "updated_at"])
        if old == Lead.NEW:
            services.mark_first_response(lead)
        log_activity(request.user, "lead.status", lead, f"{old} → {to} (pipeline)", request)
        return JsonResponse({"ok": True})
    if kind == "prospect":
        if not request.user.can("outbound", "edit"):
            return JsonResponse({"error": "forbidden"}, status=403)
        p = get_object_or_404(Prospect, pk=pk)
        if to not in PROSPECT_COLUMNS or p.status in (Prospect.CONVERTED, Prospect.SUPPRESSED):
            return JsonResponse({"error": "That move is not allowed."}, status=400)
        p.status = to
        p.save(update_fields=["status", "updated_at"])
        return JsonResponse({"ok": True})
    return JsonResponse({"error": "bad kind"}, status=400)


# ------------------------------------------------------------------ outreach queue
@needs("outbound", "view")
def outreach_queue(request):
    outreach.sync_status()
    tab = request.GET.get("tab", "waiting")
    cfg = OutboundSettings.load()
    base = OutreachMessage.objects.select_related("prospect", "approved_by")
    tabs = [("waiting", "Waiting for approval", base.filter(status="draft", channel="email")), ("approved", "Approved / sending", base.filter(status__in=["approved", "queued"], channel="email")),
            ("sent", "Sent", base.filter(status="sent", channel="email")), ("whatsapp", "WhatsApp", base.filter(channel="whatsapp").exclude(status="skipped")),
            ("issues", "Skipped / failed", base.filter(status__in=["skipped", "failed"]))]
    counts = {k: qs.count() for k, _, qs in tabs}
    qs = next((q for k, _, q in tabs if k == tab), tabs[0][2])
    page, qs_str = _page(request, qs, 20)
    items = [(m, services.email_block(m.prospect, cfg) if m.channel == "email" and m.status == "draft" else "",
              pitch.final_text(m.prospect, m.body, cfg) if m.channel == "email" and m.status in ("draft", "approved") else "") for m in page.object_list]
    return render(request, "dashboard/outbound/outreach.html", {
        "site_url": settings.SITE_URL, "tab": tab, "tabs": [(k, l) for k, l, _ in tabs], "counts": counts, "page": page, "qs": qs_str, "items": items, "remaining": services.daily_remaining(cfg), "limit": cfg.daily_email_limit,
        "can_edit": request.user.can("outbound", "edit"), "can_approve": request.user.can("outbound", "approve"), "ready": readiness()[:4], "cfg": cfg,
        "page_title": "Outreach", "crumbs": [("Dashboard", "/dashboard/"), CRUMB, ("Outreach", "")],
    })


@needs("outbound", "edit")
@require_POST
def outreach_action(request, pk):
    m = get_object_or_404(OutreachMessage.objects.select_related("prospect"), pk=pk)
    act, u = request.POST.get("action"), request.user
    tab = request.POST.get("tab", "waiting")
    if act == "save" and m.status in ("draft", "approved", "failed"):
        m.subject, m.body = clean_plain(request.POST.get("subject", ""), 300), (request.POST.get("body", "") or "").strip()[:4000]
        if m.status == "approved":
            m.status = "draft"  # editing an approved message sends it back for approval
        m.generated_by = "template" if m.generated_by == "template" else "ai+edited"
        m.save()
        messages.success(request, "Saved.")
    elif act == "approve":
        if not u.can("outbound", "approve"):
            messages.error(request, "You don't have permission to approve outreach.")
        elif not m.body.strip() or (m.channel == "email" and not m.subject.strip()):
            messages.error(request, "Add a subject and message first.")
        else:
            ok, why = outreach.approve(m, u)
            if ok:
                log_activity(u, "outreach.approved", m.prospect, f"#{m.step}", request)
                messages.success(request, "Approved. Press “Send approved emails” to send it now, or it goes out on the next scheduled run.")
            else:
                messages.error(request, why)
    elif act == "skip":
        m.status = OutreachMessage.SKIPPED
        m.save(update_fields=["status", "updated_at"])
    elif act == "mark_sent" and m.channel == "whatsapp":
        m.status, m.sent_at, m.approved_by, m.approved_at = OutreachMessage.SENT, timezone.now(), u, timezone.now()
        m.save()
        p = m.prospect
        if p.status in (Prospect.NEW, Prospect.AUDITED):
            p.status = Prospect.CONTACTED
        p.last_contacted_at = timezone.now()
        p.save(update_fields=["status", "last_contacted_at", "updated_at"])
        ProspectNote.objects.create(prospect=p, author=u, kind="whatsapp", body="WhatsApp message sent manually by staff.")
        messages.success(request, "Marked as sent.")
    elif act == "delete":
        m.delete()
    return redirect(f"/dashboard/outreach/?tab={tab}")


@needs("outbound", "approve")
@require_POST
def outreach_bulk(request):
    act = request.POST.get("action")
    if act == "approve_all":
        ok = blocked = 0
        for m in OutreachMessage.objects.filter(status="draft", channel="email").select_related("prospect"):
            if m.body.strip() and m.subject.strip() and outreach.approve(m, request.user)[0]:
                ok += 1
            else:
                blocked += 1
        messages.success(request, f"{ok} approved, {blocked} could not be approved (blocked by rules – open them to see why).")
    elif act == "send":
        res = outreach.send_approved()
        messages.success(request, f"{res['queued']} email(s) queued for sending, {res['blocked']} skipped by safety rules." + (" Daily limit reached – the rest wait until tomorrow." if res["limit_reached"] else ""))
        log_activity(request.user, "outreach.send", None, f"{res['queued']} queued", request)
    return redirect("/dashboard/outreach/?tab=" + ("approved" if act == "approve_all" else "sent"))


# ------------------------------------------------------------------ sequences
@needs("outbound", "view")
def sequences(request):
    return render(request, "dashboard/outbound/sequences.html", {
        "seqs": Sequence.objects.annotate(n_steps=Count("steps", distinct=True), n_active=Count("enrollments", filter=Q(enrollments__status="active"), distinct=True)),
        "can_edit": request.user.can("outbound", "edit"), "page_title": "Sequences", "crumbs": [("Dashboard", "/dashboard/"), CRUMB, ("Outreach", "/dashboard/outreach/"), ("Sequences", "")],
    })


@needs("outbound", "edit")
def sequence_edit(request, pk=None):
    seq = get_object_or_404(Sequence, pk=pk) if pk else None
    templates = OutreachTemplate.objects.filter(is_active=True).exclude(kind="whatsapp")
    if request.method == "POST":
        name = clean_plain(request.POST.get("name", ""), 120)
        days, tpls = request.POST.getlist("delay_days"), request.POST.getlist("template")
        steps = []
        for d, t in zip(days, tpls):
            if d.strip().isdigit() and 0 <= int(d) <= 60:
                steps.append((int(d), templates.filter(pk=t).first() if t.isdigit() else None))
        if len(name) < 2:
            messages.error(request, "Give the sequence a name.")
        elif not steps:
            messages.error(request, "Add at least one step.")
        elif len(steps) > 5:
            messages.error(request, "A sequence can have at most 5 steps.")
        else:
            seq = seq or Sequence()
            seq.name, seq.description, seq.is_active = name, clean_plain(request.POST.get("description", ""), 240), bool(request.POST.get("is_active"))
            seq.save()
            seq.steps.all().delete()
            for i, (d, t) in enumerate(steps, 1):
                SequenceStep.objects.create(sequence=seq, order=i, delay_days=0 if i == 1 else d, template=t)
            messages.success(request, "Sequence saved. Each step creates a draft that still needs your approval.")
            return redirect("dashboard:sequences")
    return render(request, "dashboard/outbound/sequence_form.html", {
        "seq": seq, "steps": list(seq.steps.select_related("template")) if seq else [], "templates": templates, "form_post": request.POST if request.method == "POST" else None,
        "page_title": "Sequence", "crumbs": [("Dashboard", "/dashboard/"), CRUMB, ("Sequences", "/dashboard/sequences/"), (seq.name if seq else "New", "")],
    })


@needs("outbound", "delete")
@require_POST
def sequence_delete(request, pk):
    get_object_or_404(Sequence, pk=pk).delete()
    messages.success(request, "Sequence deleted.")
    return redirect("dashboard:sequences")


# ------------------------------------------------------------------ settings
class OutboundSettingsForm(forms.ModelForm):
    gemini_key = forms.CharField(required=False, label="Gemini API key", widget=forms.PasswordInput(attrs={"autocomplete": "new-password", "placeholder": "Leave blank to keep the saved key"}, render_value=False))
    clear_key = forms.BooleanField(required=False, label="Remove the saved Gemini key")

    class Meta:
        model = OutboundSettings
        fields = ["daily_email_limit", "require_approval", "region_mode", "allowed_countries", "sender_business", "sender_name", "postal_address", "whatsapp_number", "include_report_link", "include_portfolio_link", "include_site_link", "include_prospect_site", "ai_enabled", "gemini_model",
                  "speed_alert_minutes", "auto_reply_enabled", "auto_reply_subject", "auto_reply_body", "follow_up_days", "proposal_reminder_days", "proposal_valid_days", "currency"]
        widgets = {"allowed_countries": forms.Textarea(attrs={"rows": 4, "data-geo-multi": ""}), "auto_reply_body": forms.Textarea(attrs={"rows": 6})}

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        for k in SCORE_RULES:
            self.fields["w_" + k] = forms.IntegerField(min_value=0, max_value=50, label=SCORE_RULES[k][0], initial=self.instance.weight(k))
        for f in self.fields.values():
            if not isinstance(f.widget, forms.CheckboxInput):
                f.widget.attrs["class"] = "input"
            else:
                f.widget.attrs["class"] = "check"

    def clean_daily_email_limit(self):
        v = self.cleaned_data["daily_email_limit"]
        if not 1 <= v <= 200:
            raise forms.ValidationError("Choose a number from 1 to 200. Low numbers protect your sender reputation.")
        return v

    def clean_currency(self):
        return (self.cleaned_data.get("currency") or "USD").upper()[:3]

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.score_weights = {k: self.cleaned_data["w_" + k] for k in SCORE_RULES}
        if self.cleaned_data.get("clear_key"):
            obj.set_gemini_key("")
        elif self.cleaned_data.get("gemini_key"):
            obj.set_gemini_key(self.cleaned_data["gemini_key"].strip())
        if commit:
            obj.save()
        return obj


@needs("outbound", "manage_settings")
def outbound_settings(request):
    cfg = OutboundSettings.load()
    form = OutboundSettingsForm(request.POST or None, instance=cfg)
    if request.method == "POST" and form.is_valid():
        form.save()
        log_activity(request.user, "outbound.settings", cfg, "", request)
        messages.success(request, "Outbound settings saved.")
        return redirect("dashboard:outbound_settings")
    groups = [("Sending limits & safety", ["daily_email_limit", "require_approval", "region_mode", "allowed_countries", "sender_business", "sender_name", "postal_address", "whatsapp_number"]),
              ("What is attached to every email", ["include_report_link", "include_portfolio_link", "include_site_link", "include_prospect_site"]),
              ("AI pitches (optional)", ["ai_enabled", "gemini_key", "clear_key", "gemini_model"]),
              ("Speed to lead", ["speed_alert_minutes", "auto_reply_enabled", "auto_reply_subject", "auto_reply_body"]),
              ("Follow-ups & proposals", ["follow_up_days", "proposal_reminder_days", "proposal_valid_days", "currency"]),
              ("Opportunity score points", ["w_" + k for k in SCORE_RULES])]
    return render(request, "dashboard/outbound/settings.html", {
        "form": form, "groups": [(t, [form[n] for n in names]) for t, names in groups], "has_key": cfg.has_gemini_key,
        "page_title": "Outbound settings", "crumbs": [("Dashboard", "/dashboard/"), CRUMB, ("Settings", "")],
    })


# ------------------------------------------------------------------ reports
@needs("outbound", "view")
def sales_reports(request):
    from apps.marketing.models import Campaign, CampaignMetric
    from apps.outbound.models import Proposal

    days = request.GET.get("range", "90")
    since = timezone.now() - timedelta(days=int(days)) if days.isdigit() else None
    flt = (lambda qs: qs.filter(created_at__gte=since)) if since else (lambda qs: qs)
    leads = flt(Lead.objects.filter(is_spam=False))
    prospects = flt(Prospect.objects.all())
    props = flt(Proposal.objects.all())
    funnel = [("Prospects found", prospects.count()), ("Audited", prospects.filter(audits__reachable=True).distinct().count()),
              ("Contacted", prospects.filter(Q(last_contacted_at__isnull=False)).count()), ("Replied", prospects.filter(replied_at__isnull=False).count()),
              ("Became leads", prospects.filter(lead__isnull=False).count()), ("Proposals sent", props.exclude(status="draft").count()), ("Won", props.filter(status="won").count())]
    top = max([n for _, n in funnel] + [1])
    funnel = [(label, n, round(n / top * 100)) for label, n in funnel]
    by_source = []
    for key, label in Lead.SOURCES:
        qs = leads.filter(source=key)
        n = qs.count()
        if n:
            won = qs.filter(status="won").count()
            by_source.append({"label": label, "n": n, "won": won, "rate": round(won / n * 100) if n else 0})
    by_cat = []
    for key, label in Lead.CATEGORIES:
        qs = leads.filter(category=key)
        n = qs.count()
        if n:
            won = qs.filter(status="won").count()
            by_cat.append({"label": label, "n": n, "won": won, "rate": round(won / n * 100) if n else 0})
    responded = leads.filter(first_response_at__isnull=False)
    mins = [l.response_minutes for l in responded[:500]]
    cfg = OutboundSettings.load()
    resp = {"n": len(mins), "avg": round(sum(mins) / len(mins)) if mins else None, "within": round(sum(1 for m in mins if m <= cfg.speed_alert_minutes) / len(mins) * 100) if mins else None,
            "pending": leads.filter(first_response_at__isnull=True, status="new").count(), "target": cfg.speed_alert_minutes}
    camp = []
    for c in Campaign.objects.exclude(utm_campaign="")[:50]:
        spend = CampaignMetric.objects.filter(campaign=c).aggregate(s=Sum("spend"))["s"] or 0
        ls = leads.filter(utm_campaign=c.utm_campaign)
        n = ls.count()
        if n or spend:
            camp.append({"c": c, "spend": spend, "leads": n, "won": ls.filter(status="won").count(), "cpl": round(spend / n, 2) if n and spend else None})
    pv = props.exclude(status="draft")
    prop_stats = {"sent": pv.count(), "viewed": pv.filter(view_count__gt=0).count(), "requested": props.filter(status="accept_requested").count(), "won": props.filter(status="won").count(),
                  "declined": props.filter(status="declined").count(), "won_value": sum((p.total for p in props.filter(status="won").prefetch_related("items")), 0)}
    return render(request, "dashboard/outbound/reports.html", {
        "funnel": funnel, "by_source": by_source, "by_cat": by_cat, "resp": resp, "camp": camp, "prop": prop_stats, "range": days, "currency": cfg.currency, "ranges": [("30", "30 days"), ("90", "90 days"), ("365", "12 months"), ("all", "All time")],
        "page_title": "Sales reports", "crumbs": [("Dashboard", "/dashboard/"), CRUMB, ("Sales reports", "")],
    })
