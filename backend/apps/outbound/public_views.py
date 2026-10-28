"""Pages that clients and prospects open without logging in: unsubscribe link and the private proposal page."""
import logging
import re
from datetime import timedelta

from django.core.cache import cache
from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt, csrf_protect

from apps.core.sanitize import clean_plain
from apps.core.services import client_ip, notify
from .models import Proposal, ProposalEvent, Prospect

log = logging.getLogger(__name__)
BOT_RE = re.compile(r"bot|crawl|spider|preview|scanner|slurp|facebookexternalhit|whatsapp|curl|wget|python-requests|headless|monitor|proofpoint|mimecast|barracuda|safelinks", re.I)


def _brand():
    from django.utils.safestring import mark_safe

    from apps.core import fonts
    from apps.core.models import SiteSettings
    from apps.dashboard.context_processors import _local_media

    s = SiteSettings.load()
    return {"name": s.site_name or "AUB SQUARE", "logo": _local_media(s.logo_url), "fonts_html": mark_safe(fonts.head_html(s))}  # noqa: S308 – whitelisted names


def _private(resp):
    resp["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    resp["Referrer-Policy"] = "same-origin"
    resp["Cache-Control"] = "private, no-store"
    return resp


@never_cache
@csrf_exempt  # mail providers POST here for RFC 8058 one-click unsubscribe and cannot send a CSRF token; the secret token is the authorisation
def unsubscribe(request, token):
    from .outreach import unsubscribe_prospect

    p = Prospect.objects.filter(token=token).first()
    if not p:
        raise Http404
    done = p.status == Prospect.SUPPRESSED
    if request.method == "POST":
        if not done:
            unsubscribe_prospect(p)
        done = True
    resp = render(request, "public/outbound_unsub.html", {"p": p, "done": done, "brand": _brand()})
    return _private(resp)


@never_cache
@csrf_protect
def proposal_page(request, token):
    from apps.mailer.service import notify_staff_by_email

    pr = Proposal.objects.filter(token=token).select_related("lead").prefetch_related("items", "show_portfolio", "show_case_studies", "show_testimonials").first()
    staff = request.user.is_authenticated and getattr(request.user, "can_access_dashboard", False)
    preview = staff and request.GET.get("preview") == "1"
    if not pr or (pr.status == Proposal.DRAFT and not preview):
        raise Http404
    notice = ""
    if pr.status in (Proposal.SENT, Proposal.VIEWED) and pr.valid_until and pr.valid_until < timezone.localdate():
        pr.status = Proposal.EXPIRED
        pr.save(update_fields=["status", "updated_at"])
    if request.method == "POST" and not preview:
        ip = client_ip(request) or "?"
        key = f"prop-resp:{ip}"
        n = cache.get(key, 0)
        if n >= 12:
            return _private(HttpResponse("Too many attempts. Please try again later.", status=429))
        cache.set(key, n + 1, 3600)
        act = request.POST.get("action")
        name = clean_plain(request.POST.get("name", ""), 160) or pr.client_name
        note = clean_plain(request.POST.get("note", ""), 600)
        live = pr.status in (Proposal.SENT, Proposal.VIEWED)
        if act == "accept" and live:
            pr.status, pr.responded_at, pr.response_note, pr.responded_name = Proposal.ACCEPT_REQ, timezone.now(), note, name
            pr.save(update_fields=["status", "responded_at", "response_note", "responded_name", "updated_at"])
            ProposalEvent.objects.create(proposal=pr, kind="accept_requested", detail=f"{name} asked to go ahead" + (f": {note}" if note else ""))
            notify("proposal", f"{name} wants to go ahead: {pr.reference}", pr.title, f"/dashboard/proposals/{pr.pk}/", module="proposals", level="success")
            notify_staff_by_email("lead", f"[ACTION] {name} wants to go ahead with {pr.reference}", f"{pr.title}\n\n{note}\n\nConfirm it in the dashboard: /dashboard/proposals/{pr.pk}/")
            notice = "accepted"
        elif act == "decline" and live:
            pr.status, pr.responded_at, pr.response_note, pr.responded_name = Proposal.DECLINED, timezone.now(), note, name
            pr.save(update_fields=["status", "responded_at", "response_note", "responded_name", "updated_at"])
            ProposalEvent.objects.create(proposal=pr, kind="declined", detail=f"{name} declined" + (f": {note}" if note else ""))
            notify("proposal", f"Proposal declined: {pr.reference}", note[:150] or pr.title, f"/dashboard/proposals/{pr.pk}/", module="proposals", level="warning")
            notice = "declined"
        elif act == "question" and note:
            ProposalEvent.objects.create(proposal=pr, kind="question", detail=f"{name}: {note}"[:300])
            notify("proposal", f"Question about {pr.reference}", note[:150], f"/dashboard/proposals/{pr.pk}/", module="proposals", level="info")
            notify_staff_by_email("lead", f"Client question about {pr.reference}", f"{name} wrote:\n\n{note}\n\n/dashboard/proposals/{pr.pk}/")
            notice = "question"
    elif request.method == "GET" and not preview and not BOT_RE.search(request.META.get("HTTP_USER_AGENT", "")) and not staff and pr.status != Proposal.DRAFT:
        now = timezone.now()
        again = pr.last_viewed_at is None or now - pr.last_viewed_at > timedelta(hours=6)
        first = pr.first_viewed_at is None
        Proposal.objects.filter(pk=pr.pk).update(view_count=pr.view_count + 1, last_viewed_at=now, first_viewed_at=pr.first_viewed_at or now)
        if pr.status == Proposal.SENT:
            Proposal.objects.filter(pk=pr.pk).update(status=Proposal.VIEWED)
            pr.status = Proposal.VIEWED
        if first or again:
            ProposalEvent.objects.create(proposal=pr, kind="viewed", detail="Opened the proposal" if first else "Opened the proposal again")
            notify("proposal", f"{pr.client_name} opened {pr.reference}", "First time" if first else f"Viewed {pr.view_count + 1} times", f"/dashboard/proposals/{pr.pk}/", module="proposals", level="info")
            if first:
                notify_staff_by_email("lead", f"{pr.client_name} just opened proposal {pr.reference}", f"{pr.title}\n\nThis is a good moment to follow up.\n/dashboard/proposals/{pr.pk}/")
        pr.refresh_from_db()
    can_respond = pr.status in (Proposal.SENT, Proposal.VIEWED) and not preview
    resp = render(request, "public/proposal.html", {
        "pr": pr, "items": list(pr.items.all()), "brand": _brand(), "notice": notice, "can_respond": can_respond, "preview": preview,
        "projects": pr.show_portfolio.all()[:6], "cases": pr.show_case_studies.all()[:4], "testimonials": pr.show_testimonials.all()[:4],
    })
    return _private(resp)


@never_cache
def report_page(request, token):
    """The private audit report a prospect opens from the link in our email. Shows only what the audit really found."""
    from django.conf import settings as dj
    from apps.cms.models import Project
    from apps.core.models import SiteSettings
    from apps.core.services import public_media_url
    from .api import public_payload
    from .models import OutboundSettings, ProspectNote

    p = Prospect.objects.filter(token=token).first()
    audit = p.audits.filter(reachable=True).first() if p else None
    if not p or not audit:
        raise Http404
    staff = request.user.is_authenticated and getattr(request.user, "can_access_dashboard", False)
    preview = staff and request.GET.get("preview") == "1"
    ua = request.META.get("HTTP_USER_AGENT", "")
    counted = not preview and not staff and bool(ua) and not BOT_RE.search(ua) and request.method == "GET"
    if counted:
        first = p.report_first_opened_at is None
        Prospect.objects.filter(pk=p.pk).update(report_views=p.report_views + 1, report_first_opened_at=p.report_first_opened_at or timezone.now())
        if first:
            try:
                ProspectNote.objects.create(prospect=p, kind="system", body="Opened their audit report.")
                notify("lead", f"{p.business_name} opened their audit report", "A warm signal – a follow-up now has the best chance.", f"/dashboard/prospects/{p.pk}/", module="outbound", level="success")
                from .services import staff_email

                staff_email(f"{p.business_name} just opened their audit report", f"A warm signal – a follow-up now has the best chance.\n\nOpen: /dashboard/prospects/{p.pk}/")
            except Exception:
                log.exception("report-open notify failed")
    data = public_payload(audit)
    cfg = OutboundSettings.load()
    site = SiteSettings.load()
    wa = re.sub(r"\D", "", cfg.whatsapp_number or "")
    projects = [{"title": x.title, "summary": (x.summary or "")[:140], "image": public_media_url(x.thumbnail) if x.thumbnail else ""} for x in Project.objects.live()[:3]]
    health = max(0, min(100, 100 - (audit.score or 0)))
    ctx = {"health": health, "offset": round(326.7 * (1 - health / 100), 1), "p": p, "a": audit, "data": data, "checks": data["checks"], "findings": data["findings"], "failed": sum(1 for c in data["checks"] if not c["ok"]), "brand": _brand(), "preview": preview,
           "wa": f"https://wa.me/{wa}?text=" + "Hi%2C%20I%20saw%20the%20audit%20report%20for%20my%20website." if wa else "", "email": site.contact_email, "site_url": dj.SITE_URL,
           "projects": projects, "sender": cfg.sender_business, "level_label": {"high": "A lot of room to improve", "medium": "Some clear gaps", "low": "In good shape"}.get(audit.level, "")}
    return _private(render(request, "public/report.html", ctx))
