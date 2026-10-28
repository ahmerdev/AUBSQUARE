"""Aggregations for the dashboard. Everything is computed from stored records; nothing is estimated or invented."""
from datetime import timedelta

from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.utils import timezone


def daily_series(qs, field, days=30, extra_filter=None, distinct_field=None):
    """Return (labels, values) for the last N days, zero-filled."""
    end = timezone.localdate()
    start = end - timedelta(days=days - 1)
    agg = Count(distinct_field, distinct=True) if distinct_field else Count("pk")
    rows = qs.filter(**{f"{field}__date__gte": start}).annotate(d=TruncDate(field)).values("d").annotate(n=agg).order_by("d")
    by = {r["d"]: r["n"] for r in rows}
    labels, values = [], []
    for i in range(days):
        d = start + timedelta(days=i)
        labels.append(d.strftime("%d %b"))
        values.append(by.get(d, 0))
    return labels, values


def dashboard_data(user):
    from apps.analytics.models import PageView
    from apps.blog.models import Comment, Post
    from apps.chatbot.models import Conversation
    from apps.cms.models import CaseStudy, Project, Service
    from apps.leads.models import Lead
    from apps.mailer.models import EmailMessage, EmailSettings
    from apps.accounts.models import User
    from apps.core.models import ActivityLog

    now = timezone.now()
    d30, d7 = now - timedelta(days=30), now - timedelta(days=7)
    prev30 = now - timedelta(days=60)
    leads = Lead.objects.filter(is_spam=False)
    out = {}
    out["kpis"] = {
        "leads_30": leads.filter(created_at__gte=d30).count(),
        "leads_prev30": leads.filter(created_at__gte=prev30, created_at__lt=d30).count(),
        "leads_new": leads.filter(status="new").count(),
        "leads_won": leads.filter(status="won").count(),
        "leads_qualified": leads.filter(status="qualified").count(),
        "inbox_unread": EmailMessage.objects.filter(direction="in", is_read=False).count(),
        "convs_30": Conversation.objects.filter(created_at__gte=d30).count(),
        "leads_total": leads.count(),
        "views_30": PageView.objects.filter(created_at__gte=d30).count(),
        "visitors_30": PageView.objects.filter(created_at__gte=d30).values("visitor").distinct().count(),
        "chats_open": Conversation.objects.filter(status__in=["waiting", "active"]).count(),
        "comments_pending": Comment.objects.filter(status="pending").count(),
        "users_pending": User.objects.filter(status="pending").count(),
        "email_failed": EmailMessage.objects.filter(direction="out", status="failed").count(),
        "email_queued": EmailMessage.objects.filter(direction="out", status="queued").count(),
        "follow_ups_due": leads.filter(follow_up_at__lte=now).exclude(status__in=["won", "lost", "archived"]).count(),
    }
    k = out["kpis"]
    k["lead_trend"] = None
    if k["leads_prev30"]:
        k["lead_trend"] = round((k["leads_30"] - k["leads_prev30"]) / k["leads_prev30"] * 100)
    k["win_rate"] = round(k["leads_won"] / k["leads_total"] * 100) if k["leads_total"] else None

    out["leads_series"] = daily_series(leads, "created_at", 30)
    out["views_series"] = daily_series(PageView.objects.all(), "created_at", 30)
    out["status_counts"] = [(label, leads.filter(status=key).count()) for key, label in Lead.STATUS_CHOICES]
    top = max([n for _, n in out["status_counts"]] or [0]) or 1
    out["pipeline"] = [(label, n, round(n / top * 100)) for label, n in out["status_counts"] if label != "Archived"]
    out["latest_comment"] = Comment.objects.filter(status="pending").select_related("post").order_by("-created_at").first()
    out["source_counts"] = [(label, leads.filter(source=key).count()) for key, label in Lead.SOURCES if leads.filter(source=key).exists()]
    out["top_pages"] = list(PageView.objects.filter(created_at__gte=d30).values("path").annotate(n=Count("pk")).order_by("-n")[:6])
    out["top_referrers"] = list(PageView.objects.filter(created_at__gte=d30).exclude(referrer_domain="").values("referrer_domain").annotate(n=Count("pk")).order_by("-n")[:6])
    out["devices"] = list(PageView.objects.filter(created_at__gte=d30).values("device").annotate(n=Count("pk")).order_by("-n"))
    out["recent_leads"] = list(leads.select_related("assigned_to").order_by("-created_at")[:6])
    out["recent_activity"] = list(ActivityLog.objects.select_related("actor").filter(is_security=False).order_by("-created_at")[:8])
    out["content"] = {
        "services": Service.objects.live().count(), "projects": Project.objects.live().count(), "case_studies": CaseStudy.objects.live().count(),
        "posts": Post.objects.live().count(),
        "drafts": Post.objects.filter(status__in=["draft", "review"]).count() + Service.objects.filter(status__in=["draft", "review"]).count() + Project.objects.filter(status__in=["draft", "review"]).count() + CaseStudy.objects.filter(status__in=["draft", "review"]).count(),
        "scheduled": Post.objects.filter(status="scheduled").count() + Project.objects.filter(status="scheduled").count() + CaseStudy.objects.filter(status="scheduled").count() + Service.objects.filter(status="scheduled").count(),
    }
    es = EmailSettings.load()
    checklist = []
    if not es.smtp_host or not es.smtp_password_enc:
        checklist.append(("Connect an email provider so lead notifications and replies can be sent.", "/dashboard/email-settings/"))
    if not es.imap_enabled:
        checklist.append(("Turn on inbox sync (IMAP) to receive customer replies in the dashboard.", "/dashboard/email-settings/"))
    from apps.core.models import SiteSettings

    ss = SiteSettings.load()
    if not ss.contact_email:
        checklist.append(("Add a public contact email in Website settings.", "/dashboard/site-settings/"))
    if not (ss.google_analytics_id or ss.google_tag_manager_id):
        checklist.append(("Optional: add a Google Analytics ID to measure with your own analytics account.", "/dashboard/site-settings/"))
    out["checklist"] = checklist
    out["smtp_ok"] = bool(es.smtp_host and es.smtp_password_enc)
    out["smtp_last_test"] = es.last_test_at
    out["smtp_last_ok"] = es.last_test_ok
    return out
