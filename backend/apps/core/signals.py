"""Bump the public-content cache version whenever CMS content changes."""
from django.db.models.signals import post_delete, post_save

from .services import bump_content_version

WATCHED = {
    "core": {"SiteSettings", "NavItem", "AnnouncementBanner"},
    "cms": None, "blog": None, "leads": {"BudgetOption", "LeadFormConfig"}, "seo": {"PageSEO", "Redirect"},
    "chatbot": {"ChatbotSettings", "KnowledgeEntry"},
}


def _maybe_bump(sender, **kwargs):
    app = sender._meta.app_label
    if app not in WATCHED:
        return
    names = WATCHED[app]
    if names is None or sender.__name__ in names:
        if sender.__name__ == "Comment":
            pass
        bump_content_version()


post_save.connect(_maybe_bump, dispatch_uid="aub_bump_save")
post_delete.connect(_maybe_bump, dispatch_uid="aub_bump_delete")
