from urllib.parse import urlparse

from django.conf import settings
from django.contrib import messages
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.models import SiteSettings
from apps.core.services import log_activity
from apps.seo import audit, resolver, verify
from apps.seo.models import Backlink, Redirect
from .mixins import needs


@needs("seo", "view")
def seo_overview(request):
    results, summary = audit.audit_all() if request.GET.get("audit") != "0" else ([], {"pages": 0, "errors": 0, "warnings": 0, "clean": 0})
    site = SiteSettings.load()
    broken_redirects = Redirect.objects.filter(is_active=True).count()
    chains = []
    live = {r.from_path: r.to_path for r in Redirect.objects.filter(is_active=True)}
    for fp, tp in live.items():
        if tp in live:
            chains.append((fp, tp, live[tp]))
    sev = request.GET.get("sev", "")
    shown = [r for r in results if (not sev) or any(i["severity"] == sev for i in r["issues"])]
    return render(request, "dashboard/seo.html", {
        "results": shown, "summary": summary, "site": site, "chains": chains, "redirect_count": broken_redirects,
        "backlinks": {"total": Backlink.objects.count(), "active": Backlink.objects.filter(status="active").count(), "verified": Backlink.objects.filter(verified=True).count()},
        "sev": sev, "site_url": settings.SITE_URL, "sitemap_url": f"{settings.SITE_URL}/sitemap.xml", "robots_url": f"{settings.SITE_URL}/robots.txt",
        "can_edit": request.user.can("seo", "edit"),
        "page_title": "SEO", "crumbs": [("Dashboard", "/dashboard/"), ("SEO", "")],
    })


@needs("seo", "edit")
@require_POST
def backlink_verify(request, pk):
    bl = get_object_or_404(Backlink, pk=pk)
    hosts = {urlparse(settings.SITE_URL).hostname or ""}
    hosts |= set(settings.ALLOWED_HOSTS) - {"*"}
    hosts = {h.replace("www.", "") for h in hosts if h and not h.startswith(".") and h not in ("localhost", "127.0.0.1")} or {urlparse(settings.SITE_URL).hostname or ""}
    res = verify.verify_backlink(bl.source_url, hosts)
    bl.last_checked_at, bl.last_check_message = timezone.now(), res["message"][:200]
    bl.verified = res["found"]
    bl.data_source = "verified" if res["found"] else bl.data_source
    if res["found"]:
        bl.status, bl.link_type = "active", res.get("link_type", bl.link_type)
        if res.get("anchor") and not bl.anchor_text:
            bl.anchor_text = res["anchor"]
    elif bl.status == "active":
        bl.status = "lost"
    bl.save()
    log_activity(request.user, "backlink.verified", bl, res["message"], request)
    (messages.success if res["found"] else messages.warning)(request, res["message"])
    return redirect("dashboard:edit", mslug="backlinks", pk=pk)


@needs("seo", "export")
def sitemap_preview(request):
    from apps.seo.views import sitemap_xml

    return sitemap_xml(request)
