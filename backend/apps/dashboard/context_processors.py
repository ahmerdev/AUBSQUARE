from django.urls import reverse

from apps.accounts.permissions import MODULE_LABELS

# (label, url name or path, permission module, icon, section)
NAV = [
    ("Overview", [
        ("Dashboard", "/dashboard/", "dashboard", "home"),
        ("Notifications", "/dashboard/notifications/", "notifications", "bell"),
    ]),
    ("Website", [
        ("Website pages", "/dashboard/pages/", "pages", "layers"),
        ("Home page builder", "/dashboard/home-builder/", "home", "layout"),
        ("About us", "/dashboard/about/", "about", "info"),
        ("Services", "/dashboard/services/", "services", "spark"),
        ("Portfolio", "/dashboard/portfolio/", "portfolio", "grid"),
        ("Case studies", "/dashboard/case-studies/", "case_studies", "chart"),
        ("Blog", "/dashboard/posts/", "blog", "pen"),
        ("Categories & tags", "/dashboard/blog-categories/", "taxonomy", "tag"),
        ("Testimonials", "/dashboard/testimonials/", "testimonials", "quote"),
        ("FAQs", "/dashboard/faqs/", "faqs", "help"),
        ("Media library", "/dashboard/media/", "media", "image"),
        ("Branding & logo", "/dashboard/branding/", "settings", "palette"),
        ("Website settings", "/dashboard/site-settings/", "settings", "cog"),
    ]),
    ("Customers", [
        ("Leads & messages", "/dashboard/leads/", "leads", "inbox"),
        ("Chatbot & live chat", "/dashboard/chat/", "chatbot", "chat"),
        ("Email inbox", "/dashboard/inbox/", "email", "mail"),
        ("Email settings", "/dashboard/email-settings/", "email_settings", "send"),
    ]),
    ("Growth", [
        ("SEO", "/dashboard/seo/", "seo", "search"),
        ("Campaigns", "/dashboard/campaigns/", "campaigns", "rocket"),
        ("Ads manager", "/dashboard/ads/", "ads", "target"),
        ("Analytics & reports", "/dashboard/analytics/", "analytics", "pulse"),
    ]),
    ("Outbound Sales", [
        ("Outbound overview", "/dashboard/outbound/", "outbound", "target"),
        ("Prospects", "/dashboard/prospects/", "outbound", "search"),
        ("Pipeline board", "/dashboard/pipeline/", "leads", "grid"),
        ("Outreach", "/dashboard/outreach/", "outbound", "send"),
        ("Proposals", "/dashboard/proposals/", "proposals", "doc"),
        ("Sales reports", "/dashboard/sales-reports/", "outbound", "pulse"),
    ]),
    ("Billing", [
        ("Invoices", "/dashboard/invoices/", "invoices", "doc"),
        ("Payments", "/dashboard/payments/", "payments", "check"),
        ("Billing reports", "/dashboard/billing/reports/", "billing_reports", "pulse"),
        ("Company billing", "/dashboard/billing/settings/", "billing_settings", "shield"),
        ("Payment methods", "/dashboard/billing/methods/", "billing_settings", "lock"),
        ("Company profile PDF", "/dashboard/billing/profile/", "billing_settings", "doc"),
    ]),
    ("Administration", [
        ("Users & roles", "/dashboard/users/", "users", "shield"),
        ("Security & activity", "/dashboard/activity/", "security", "lock"),
    ]),
]


def _local_media(url: str) -> str:
    """Uploaded files are served from /media/ on the same host as the dashboard, so keep only the path
    (an absolute URL built from SITE_URL could point at a different host than the one the admin is using)."""
    if not url:
        return ""
    if url.startswith("/"):
        return url
    try:
        from urllib.parse import urlparse

        u = urlparse(url)
        if u.path.startswith("/media/"):
            return u.path
    except ValueError:
        pass
    return url


def brand(request=None) -> dict:
    """Site name + logo taken from Website settings → Brand, so the dashboard and login pages always match the website."""
    try:
        from apps.core.models import SiteSettings

        s = SiteSettings.load()
    except Exception:  # database not ready (first migrate) – fall back to the defaults
        return {"name": "AUB SQUARE", "logo": "", "favicon": "", "initials": "AS", "version": "", "fonts_html": ""}
    name = (s.site_name or "AUB SQUARE").strip()
    words = name.split()
    initials = ("".join(w[0] for w in words[:2]) if len(words) > 1 else name[:2]).upper() or "AS"
    version = str(int(s.updated_at.timestamp())) if getattr(s, "updated_at", None) else ""
    logo = _local_media(s.logo_url)
    favicon = _local_media(s.favicon_url) or logo
    bust = lambda u: (u + ("&" if "?" in u else "?") + "v=" + version) if (u and version) else u  # noqa: E731
    from django.utils.safestring import mark_safe

    from apps.core import fonts

    return {"name": name, "logo": bust(logo), "favicon": bust(favicon), "initials": initials, "version": version, "fonts_html": mark_safe(fonts.head_html(s))}  # noqa: S308 – names are whitelisted


def dashboard(request):
    if not request.path.startswith("/dashboard"):
        return {}
    from django.contrib.messages import get_messages

    ctx = {"flash_messages": [{"text": str(m.message), "level": m.level_tag or "info"} for m in get_messages(request)], "brand": brand(request)}
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return ctx
    u = request.user
    if not u.can_access_dashboard:
        return ctx
    path = request.path
    from apps.core.models import Notification

    unread = Notification.objects.filter(recipient=u, is_read=False).count()
    groups = []
    for title, items in NAV:
        shown = []
        for label, url, perm, icon in items:
            if u.can(perm, "view"):
                entry = {"label": label, "url": url, "icon": icon, "active": _active(path, url, label)}
                if label == "Notifications" and unread:
                    entry["count"] = unread
                shown.append(entry)
        if shown:
            groups.append({"title": title, "items": shown, "url": shown[0]["url"], "active": any(i["active"] for i in shown),
                           "count": unread if title == "Overview" else 0})
    current = next((g for g in groups if g["active"]), groups[0] if groups else None)
    ctx.update({"nav_groups": groups, "rail_items": current["items"] if current else [], "rail_title": current["title"] if current else "",
                "unread_count": unread, "has_picker": True})
    return ctx


# Which sidebar entry owns which URL prefixes (so e.g. /dashboard/comments/ highlights "Blog").
OWNERS = {
    "Blog": ("/dashboard/posts", "/dashboard/comments"),
    "Categories & tags": ("/dashboard/blog-categories", "/dashboard/tags", "/dashboard/service-categories", "/dashboard/portfolio-categories"),
    "About us": ("/dashboard/about", "/dashboard/team"),
    "Leads & messages": ("/dashboard/leads", "/dashboard/lead-form", "/dashboard/budget-options"),
    "Chatbot & live chat": ("/dashboard/chat", "/dashboard/knowledge", "/dashboard/chatbot-settings"),
    "SEO": ("/dashboard/seo", "/dashboard/redirects", "/dashboard/internal-links", "/dashboard/backlinks"),
    "Campaigns": ("/dashboard/campaigns", "/dashboard/email-campaigns", "/dashboard/subscribers"),
    "Ads manager": ("/dashboard/ads", "/dashboard/ad-groups", "/dashboard/ad-creatives"),
    "Users & roles": ("/dashboard/users", "/dashboard/roles"),
    "Website settings": ("/dashboard/site-settings", "/dashboard/navigation", "/dashboard/banners"),
    "Branding & logo": ("/dashboard/branding",),
    "Email inbox": ("/dashboard/inbox",),
    "Website pages": ("/dashboard/pages",),
    "Outbound overview": ("/dashboard/outbound",),
    "Prospects": ("/dashboard/prospects",),
    "Pipeline board": ("/dashboard/pipeline",),
    "Outreach": ("/dashboard/outreach", "/dashboard/outreach-templates", "/dashboard/sequences", "/dashboard/do-not-contact", "/dashboard/outbound-settings"),
    "Proposals": ("/dashboard/proposals",),
    "Invoices": ("/dashboard/invoices",),
    "Payments": ("/dashboard/payments",),
    "Billing reports": ("/dashboard/billing/reports",),
    "Company billing": ("/dashboard/billing/settings",),
    "Payment methods": ("/dashboard/billing/methods",),
    "Company profile PDF": ("/dashboard/billing/profile",),
    "Sales reports": ("/dashboard/sales-reports",),
}


def _active(path, url, label):
    if url == "/dashboard/":
        return path == "/dashboard/"
    prefixes = OWNERS.get(label, (url.rstrip("/"),))
    return any(path == p or path.startswith(p + "/") for p in prefixes)
