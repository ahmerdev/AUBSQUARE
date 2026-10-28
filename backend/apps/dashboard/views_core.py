import csv
from datetime import timedelta

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.analytics.models import PageView
from apps.core.models import ActivityLog, Notification
from apps.core.services import log_activity
from . import stats
from .mixins import needs, staff_only
from .registry import REGISTRY


@needs("dashboard", "view")
def home(request):
    data = stats.dashboard_data(request.user)
    ll, lv = data["leads_series"]
    vl, vv = data["views_series"]
    charts = {
        "leads": {"type": "bar", "labels": ll, "datasets": [{"label": "Leads", "data": lv, "color": "#EC008C"}]},
        "views": {"type": "line", "labels": vl, "datasets": [{"label": "Page views", "data": vv, "color": "#7B2FFF"}]},
        "status": {"type": "doughnut", "labels": [a for a, b in data["status_counts"]], "datasets": [{"data": [b for a, b in data["status_counts"]], "backgroundColor": ["#EC008C", "#60A5FA", "#9333EA", "#C99BFF", "#34D399", "#F87171", "#6b6785"]}]},
    }
    u = request.user
    perms = {k: u.can(k, "view") for k in ("leads", "analytics", "chatbot", "blog", "users", "email", "services", "security")}
    needed = {"/dashboard/email-settings/": "email_settings", "/dashboard/site-settings/": "settings"}
    data["checklist"] = [(t, url) for t, url in data["checklist"] if u.can(needed.get(url, "settings"), "view")]
    hour = timezone.localtime().hour
    greeting = "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"
    first = (u.display_name or "").split(" ")[0] or "there"
    data["sales_attention"] = _sales_attention(u)
    return render(request, "dashboard/home.html", {**data, "greeting": greeting, "first_name": first, "charts": charts, "perms": perms, "has_data": bool(data["kpis"]["leads_total"] or data["kpis"]["views_30"]), "page_title": "Dashboard", "crumbs": [("Dashboard", "")]})


def _sales_attention(u):
    """Small, real counts of things waiting on a person (nothing estimated)."""
    from datetime import timedelta

    out = []
    if u.can("leads", "view"):
        from apps.leads.models import Lead
        from apps.outbound.models import OutboundSettings

        mins = OutboundSettings.load().speed_alert_minutes or 15
        late = Lead.objects.filter(is_spam=False, first_response_at__isnull=True, status="new", created_at__lte=timezone.now() - timedelta(minutes=mins)).count()
        out.append(("Leads waiting for a first reply", late, "/dashboard/leads/?status=new", late > 0))
    if u.can("outbound", "view"):
        from apps.outbound.models import OutreachMessage

        n = OutreachMessage.objects.filter(status="draft").count()
        out.append(("Outreach drafts to approve", n, "/dashboard/outreach/", n > 0))
    if u.can("proposals", "view"):
        from apps.outbound.models import Proposal

        n = Proposal.objects.filter(status="accept_requested").count()
        out.append(("Proposals the client wants to accept", n, "/dashboard/proposals/", n > 0))
    if u.can("payments", "approve"):
        from apps.billing.models import Payment

        n = Payment.objects.filter(status="pending").count()
        out.append(("Payments waiting to be verified", n, "/dashboard/payments/", n > 0))
    if u.can("invoices", "view"):
        from apps.billing.models import Invoice

        n = Invoice.objects.filter(status__in=Invoice.OPEN, due_date__lt=timezone.localdate()).count()
        out.append(("Overdue invoices", n, "/dashboard/invoices/?status=overdue", n > 0))
    return out


# ------------------------------------------------------------------ global search (JSON)
@staff_only
def search(request):
    q = request.GET.get("q", "").strip()[:80]
    u = request.user
    results = []
    if len(q) >= 2:
        from apps.blog.models import Post
        from apps.cms.models import CaseStudy, Project, Service
        from apps.leads.models import Lead
        from apps.accounts.models import User

        def add(group, qs, perm, label_fn, url_fn, n=5):
            if u.can(perm, "view"):
                for o in qs[:n]:
                    results.append({"group": group, "label": label_fn(o), "url": url_fn(o)})

        add("Leads", Lead.objects.filter(Q(name__icontains=q) | Q(email__icontains=q) | Q(reference__icontains=q) | Q(message__icontains=q)), "leads", lambda o: f"{o.reference} · {o.name}", lambda o: f"/dashboard/leads/{o.pk}/")
        add("Blog posts", Post.objects.filter(title__icontains=q), "blog", lambda o: o.title, lambda o: f"/dashboard/posts/{o.pk}/")
        add("Services", Service.objects.filter(title__icontains=q), "services", lambda o: o.title, lambda o: f"/dashboard/services/{o.pk}/")
        add("Portfolio", Project.objects.filter(Q(title__icontains=q) | Q(client_name__icontains=q)), "portfolio", lambda o: o.title, lambda o: f"/dashboard/portfolio/{o.pk}/")
        add("Case studies", CaseStudy.objects.filter(Q(title__icontains=q) | Q(client__icontains=q)), "case_studies", lambda o: o.title, lambda o: f"/dashboard/case-studies/{o.pk}/")
        add("Users", User.objects.filter(Q(full_name__icontains=q) | Q(email__icontains=q)), "users", lambda o: f"{o.display_name} · {o.email}", lambda o: f"/dashboard/users/{o.pk}/")
    return JsonResponse({"results": results})


# ------------------------------------------------------------------ notifications
@needs("notifications", "view")
def notifications(request):
    qs = Notification.objects.filter(recipient=request.user)
    only = request.GET.get("filter", "")
    if only == "unread":
        qs = qs.filter(is_read=False)
    page = Paginator(qs, 25).get_page(request.GET.get("page"))
    return render(request, "dashboard/notifications.html", {"page": page, "filter": only, "page_title": "Notifications", "crumbs": [("Dashboard", "/dashboard/"), ("Notifications", "")]})


@staff_only
def notifications_feed(request):
    qs = Notification.objects.filter(recipient=request.user)
    items = [{"id": n.pk, "title": n.title, "body": n.body[:140], "url": n.url, "level": n.level, "read": n.is_read, "kind": n.kind, "at": n.created_at.isoformat()} for n in qs[:10]]
    return JsonResponse({"unread": qs.filter(is_read=False).count(), "items": items})


@staff_only
@require_POST
def notification_read(request, pk=None):
    qs = Notification.objects.filter(recipient=request.user, is_read=False)
    if pk:
        n = get_object_or_404(Notification, pk=pk, recipient=request.user)
        n.is_read = True
        n.save(update_fields=["is_read"])
        return JsonResponse({"ok": True}) if request.headers.get("x-requested-with") == "fetch" else redirect(n.url or "dashboard:notifications")
    qs.update(is_read=True)
    if request.headers.get("x-requested-with") == "fetch":
        return JsonResponse({"ok": True})
    messages.success(request, "All notifications marked as read.")
    return redirect("dashboard:notifications")


# ------------------------------------------------------------------ activity & security
@needs("security", "view")
def activity(request):
    qs = ActivityLog.objects.select_related("actor")
    tab = request.GET.get("tab", "all")
    if tab == "security":
        qs = qs.filter(is_security=True)
    elif tab == "content":
        qs = qs.filter(is_security=False)
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(action__icontains=q) | Q(actor_label__icontains=q) | Q(target_repr__icontains=q) | Q(detail__icontains=q))
    if request.GET.get("actor"):
        qs = qs.filter(actor_id=request.GET["actor"]) if request.GET["actor"].isdigit() else qs
    page = Paginator(qs, 40).get_page(request.GET.get("page"))
    from apps.accounts.models import LoginAttempt

    failed = LoginAttempt.objects.filter(success=False, created_at__gte=timezone.now() - timedelta(hours=24)).count()
    qd = request.GET.copy()
    qd.pop("page", None)
    return render(request, "dashboard/activity.html", {"page": page, "tab": tab, "q": q, "failed_24h": failed, "qs": qd.urlencode(), "can_export": request.user.can("security", "export"),
                                                      "page_title": "Security & activity", "crumbs": [("Dashboard", "/dashboard/"), ("Security & activity", "")]})


@needs("security", "export")
def activity_export(request):
    resp = HttpResponse(content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = 'attachment; filename="activity-log.csv"'
    resp.write("﻿")
    w = csv.writer(resp)
    w.writerow(["time", "actor", "action", "target", "detail", "ip", "security"])
    safe = lambda s: ("'" + s) if s[:1] in "=+-@" and s else s
    for a in ActivityLog.objects.select_related("actor").order_by("-created_at")[:5000]:
        w.writerow([a.created_at.isoformat(), safe(a.actor_label), a.action, safe(a.target_repr), safe(a.detail), a.ip_address or "", a.is_security])
    log_activity(request.user, "activity.exported", None, "", request, security=True)
    return resp


# ------------------------------------------------------------------ analytics & reports
RANGES = {"7": 7, "30": 30, "90": 90}


@needs("analytics", "view")
def analytics(request):
    from apps.leads.models import Lead

    days = RANGES.get(request.GET.get("range", "30"), 30)
    since = timezone.now() - timedelta(days=days)
    pv = PageView.objects.filter(created_at__gte=since)
    leads = Lead.objects.filter(is_spam=False, created_at__gte=since)
    views_labels, views_vals = stats.daily_series(PageView.objects.all(), "created_at", days)
    _, visitors_vals = stats.daily_series(PageView.objects.all(), "created_at", days, distinct_field="visitor")
    _, lead_vals = stats.daily_series(Lead.objects.filter(is_spam=False), "created_at", days)
    total_views = pv.count()
    visitors = pv.values("visitor").distinct().count()
    lead_count = leads.count()
    ctx = {
        "charts": {
            "traffic": {"type": "line", "labels": views_labels, "datasets": [{"label": "Page views", "data": views_vals, "color": "#7B2FFF"}, {"label": "Unique visitors", "data": visitors_vals, "color": "#38BDF8"}]},
            "leads": {"type": "bar", "labels": views_labels, "datasets": [{"label": "Leads", "data": lead_vals, "color": "#EC008C"}]},
        },
        "days": days, "range": str(days), "total_views": total_views, "visitors": visitors, "lead_count": lead_count,
        "conversion": round(lead_count / visitors * 100, 1) if visitors else None,
        "labels": views_labels, "views": views_vals, "visitor_series": visitors_vals, "lead_series": lead_vals,
        "top_pages": list(pv.values("path").annotate(n=Count("pk"), v=Count("visitor", distinct=True)).order_by("-n")[:10]),
        "referrers": list(pv.exclude(referrer_domain="").values("referrer_domain").annotate(n=Count("pk")).order_by("-n")[:8]),
        "utm": list(pv.exclude(utm_source="").values("utm_source", "utm_medium", "utm_campaign").annotate(n=Count("pk")).order_by("-n")[:8]),
        "devices": list(pv.values("device").annotate(n=Count("pk")).order_by("-n")),
        "lead_sources": list(leads.values("source").annotate(n=Count("pk")).order_by("-n")),
        "lead_utm": list(leads.exclude(utm_source="").values("utm_source", "utm_campaign").annotate(n=Count("pk")).order_by("-n")[:8]),
        "lead_services": list(leads.exclude(service_label="").values("service_label").annotate(n=Count("pk")).order_by("-n")[:8]),
        "lead_budgets": list(leads.exclude(budget_label="").values("budget_label").annotate(n=Count("pk")).order_by("-n")),
        "status_counts": [(label, leads.filter(status=key).count()) for key, label in Lead.STATUS_CHOICES],
        "page_title": "Analytics & reports", "crumbs": [("Dashboard", "/dashboard/"), ("Analytics & reports", "")],
        "can_export": request.user.can("analytics", "export"),
    }
    return render(request, "dashboard/analytics.html", ctx)


@needs("analytics", "export")
def analytics_export(request):
    from apps.leads.models import Lead

    days = RANGES.get(request.GET.get("range", "30"), 30)
    since = timezone.now() - timedelta(days=days)
    kind = request.GET.get("kind", "pages")
    resp = HttpResponse(content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="analytics-{kind}-{days}d.csv"'
    resp.write("﻿")
    w = csv.writer(resp)
    if kind == "leads":
        w.writerow(["reference", "created", "status", "source", "service", "budget", "utm_source", "utm_campaign"])
        for l in Lead.objects.filter(is_spam=False, created_at__gte=since):
            w.writerow([l.reference, l.created_at.date(), l.status, l.source, l.service_label, l.budget_label, l.utm_source, l.utm_campaign])
    else:
        w.writerow(["path", "views", "unique_visitors"])
        for r in PageView.objects.filter(created_at__gte=since).values("path").annotate(n=Count("pk"), v=Count("visitor", distinct=True)).order_by("-n"):
            w.writerow([r["path"], r["n"], r["v"]])
    log_activity(request.user, "analytics.exported", None, kind, request)
    return resp
