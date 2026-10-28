import json

from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe

register = template.Library()

ICONS = {
    "home": '<path d="M3 11l9-8 9 8"/><path d="M5 10v10h14V10"/>',
    "bell": '<path d="M6 8a6 6 0 0112 0c0 7 3 8 3 8H3s3-1 3-8"/><path d="M10 21a2 2 0 004 0"/>',
    "layers": '<path d="M12 3l9 5-9 5-9-5 9-5z"/><path d="M3 13l9 5 9-5"/>',
    "layout": '<rect x="3" y="3" width="18" height="18" rx="3"/><path d="M3 9h18M9 21V9"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 8h.01M11 12h1v5h1"/>',
    "spark": '<path d="M12 3l2.2 5.8L20 11l-5.8 2.2L12 19l-2.2-5.8L4 11l5.8-2.2L12 3z"/>',
    "grid": '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
    "chart": '<path d="M4 20V10M10 20V4M16 20v-8M22 20H2"/>',
    "pen": '<path d="M4 20l4-1 11-11a2.1 2.1 0 00-3-3L5 16l-1 4z"/>',
    "tag": '<path d="M3 12V4h8l10 10-8 8L3 12z"/><circle cx="7.5" cy="8.5" r="1"/>',
    "quote": '<path d="M7 17c-2 0-3-1.5-3-4 0-3 2-5 5-6M17 17c-2 0-3-1.5-3-4 0-3 2-5 5-6"/>',
    "help": '<circle cx="12" cy="12" r="9"/><path d="M9.5 9.5a2.5 2.5 0 114 2c-1 .7-1.5 1.2-1.5 2.5M12 17h.01"/>',
    "image": '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="1.6"/><path d="M21 16l-5-5-8 8"/>',
    "cog": '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 00.3 1.9l.1.1a2 2 0 11-2.8 2.8l-.1-.1a1.7 1.7 0 00-1.9-.3 1.7 1.7 0 00-1 1.5V21a2 2 0 11-4 0v-.1a1.7 1.7 0 00-1.1-1.5 1.7 1.7 0 00-1.9.3l-.1.1a2 2 0 11-2.8-2.8l.1-.1a1.7 1.7 0 00.3-1.9 1.7 1.7 0 00-1.5-1H3a2 2 0 110-4h.1a1.7 1.7 0 001.5-1.1 1.7 1.7 0 00-.3-1.9l-.1-.1a2 2 0 112.8-2.8l.1.1a1.7 1.7 0 001.9.3h0a1.7 1.7 0 001-1.5V3a2 2 0 114 0v.1a1.7 1.7 0 001 1.5 1.7 1.7 0 001.9-.3l.1-.1a2 2 0 112.8 2.8l-.1.1a1.7 1.7 0 00-.3 1.9v0a1.7 1.7 0 001.5 1H21a2 2 0 110 4h-.1a1.7 1.7 0 00-1.5 1z"/>',
    "inbox": '<path d="M22 12h-6l-2 3h-4l-2-3H2"/><path d="M5.5 5h13L22 12v6a2 2 0 01-2 2H4a2 2 0 01-2-2v-6l3.5-7z"/>',
    "chat": '<path d="M21 12a8 8 0 01-11.5 7.2L3 21l1.8-6A8 8 0 1121 12z"/>',
    "mail": '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 7l9 6 9-6"/>',
    "send": '<path d="M22 2L11 13"/><path d="M22 2l-7 20-4-9-9-4 20-7z"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/>',
    "rocket": '<path d="M5 15c-1 1-2 4-2 6 2 0 5-1 6-2M14 4c3-1 6-1 7-1 0 1 0 4-1 7l-7 7-6-6 7-7z"/><circle cx="15" cy="9" r="1.5"/>',
    "target": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>',
    "pulse": '<path d="M3 12h4l3-8 4 16 3-8h4"/>',
    "shield": '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6l8-3z"/><path d="M9 12l2 2 4-4"/>',
    "lock": '<rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 118 0v4"/>',
    "users": '<circle cx="9" cy="8" r="3.5"/><path d="M2 21c0-4 3-6 7-6s7 2 7 6"/><path d="M16 4.5a3.5 3.5 0 010 7M22 21c0-3-1.5-5-4-5.7"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "edit": '<path d="M4 20h4L19 9a2.1 2.1 0 00-3-3L5 17v3z"/>',
    "trash": '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>',
    "download": '<path d="M12 3v12M7 10l5 5 5-5M4 21h16"/>',
    "upload": '<path d="M12 21V9M7 14l5-5 5 5M4 3h16"/>',
    "eye": '<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
    "check": '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    "x": '<path d="M6 6l12 12M18 6L6 18"/>',
    "menu": '<path d="M4 7h16M4 12h16M4 17h16"/>',
    "chevron": '<path d="M9 6l6 6-6 6"/>',
    "external": '<path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 01-1 1H5a1 1 0 01-1-1V7a1 1 0 011-1h5"/>',
    "link": '<path d="M10 14a4 4 0 005.7 0l3-3a4 4 0 00-5.7-5.7l-1 1M14 10a4 4 0 00-5.7 0l-3 3a4 4 0 005.7 5.7l1-1"/>',
    "redirect": '<path d="M4 7h10a5 5 0 015 5v5M15 13l4 4 4-4M4 17h5"/>',
    "form": '<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 8h8M8 12h8M8 16h5"/>',
    "coin": '<circle cx="12" cy="12" r="9"/><path d="M14.5 9.5c-.5-1-1.5-1.5-2.5-1.5-1.5 0-2.5.8-2.5 2s1 1.7 2.5 2 2.5.8 2.5 2-1 2-2.5 2c-1 0-2-.5-2.5-1.5M12 6.5v1.5M12 16v1.5"/>',
    "book": '<path d="M4 4h6a3 3 0 013 3v13a2 2 0 00-2-2H4V4zM20 4h-6a3 3 0 00-3 3v13a2 2 0 012-2h7V4z"/>',
    "doc": '<path d="M7 3h7l5 5v13H7V3z"/><path d="M14 3v5h5"/>',
    "logout": '<path d="M15 4h4a1 1 0 011 1v14a1 1 0 01-1 1h-4M10 8l-4 4 4 4M6 12h11"/>',
    "refresh": '<path d="M20 11a8 8 0 10-2.3 5.7M20 4v7h-7"/>',
    "alert": '<path d="M12 3l10 18H2L12 3z"/><path d="M12 10v5M12 18h.01"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "star": '<path d="M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9L12 3z"/>',
    "drag": '<circle cx="9" cy="6" r="1.2"/><circle cx="15" cy="6" r="1.2"/><circle cx="9" cy="12" r="1.2"/><circle cx="15" cy="12" r="1.2"/><circle cx="9" cy="18" r="1.2"/><circle cx="15" cy="18" r="1.2"/>',
    "up": '<path d="M6 15l6-6 6 6"/>',
    "down": '<path d="M6 9l6 6 6-6"/>',
    "phone": '<path d="M5 4h4l2 5-2.5 1.5a11 11 0 005 5L15 13l5 2v4a2 2 0 01-2 2A16 16 0 013 6a2 2 0 012-2z"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
    "moon": '<path d="M21 13.2A8.5 8.5 0 1110.8 3a6.6 6.6 0 0010.2 10.2z"/>',
    "palette": '<path d="M12 3a9 9 0 100 18c1.4 0 2-1 2-2 0-1.5-1.2-1.7-1.2-3 0-1 .8-1.6 1.8-1.6H17a4 4 0 004-4c0-4-4-7.4-9-7.4z"/><circle cx="7.5" cy="11" r="1"/><circle cx="10" cy="7" r="1"/><circle cx="15" cy="7.5" r="1"/>',
    "monitor": '<rect x="2.5" y="4" width="19" height="13" rx="2.5"/><path d="M8 21h8M12 17v4"/>',
    "tablet": '<rect x="5" y="2.5" width="14" height="19" rx="2.5"/><path d="M11 18.5h2"/>',
    "phone": '<rect x="7" y="2.5" width="10" height="19" rx="2.5"/><path d="M11 18.5h2"/>',
    "refresh": '<path d="M20 11a8 8 0 10-2.3 5.7"/><path d="M20 4v7h-7"/>',
    "expand": '<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/>',
    "panel": '<rect x="3" y="4" width="18" height="16" rx="3"/><path d="M9 4v16"/>',
    "back": '<path d="M15 6l-6 6 6 6"/>',
    "utensils": '<path d="M7 3v8a2 2 0 002 2v8M4 3v6a3 3 0 003 3M10 3v6a3 3 0 01-3 3"/><path d="M17 21V3c-2.5 1.5-4 4.5-4 8h4"/>',
    "tooth": '<path d="M7.5 3C5 3 3.5 5 3.5 7.5c0 2.5 1 3.5 1.5 6S5.5 21 7.5 21c1.7 0 1.8-4 4.5-4s2.8 4 4.5 4c2 0 1.5-5 2-7.5s1.5-3.5 1.5-6C20.5 5 19 3 16.5 3c-2 0-3 1-4.5 1S9.5 3 7.5 3z"/>',
    "dumbbell": '<path d="M6.5 6.5v11M17.5 6.5v11M3.5 9v6M20.5 9v6M6.5 12h11"/>',
    "building": '<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M9 7.5h1M14 7.5h1M9 11.5h1M14 11.5h1M10 21v-4h4v4"/>',
    "bag": '<path d="M5 8h14l-1 12H6L5 8z"/><path d="M9 8V6a3 3 0 016 0v2"/>',
    "stethoscope": '<path d="M6 3v6a4 4 0 008 0V3M10 13v2a4 4 0 008 0v-1"/><circle cx="18" cy="12" r="2"/>',
    "scale": '<path d="M12 3v18M7 21h10M5 7h14"/><path d="M5 7l-3 7a3.5 3.5 0 006 0L5 7zM19 7l-3 7a3.5 3.5 0 006 0l-3-7z"/>',
    "bed": '<path d="M3 18V6M3 14h18v4M21 14v-2a3 3 0 00-3-3h-7v5"/><circle cx="7" cy="11" r="1.6"/>',
    "car": '<path d="M3 17v-4l2-5a2 2 0 012-1.3h10a2 2 0 012 1.3l2 5v4h-3M3 17h3M18 17h3M9 17h6"/><path d="M3 13h18"/><circle cx="7.5" cy="17" r="1.5"/><circle cx="16.5" cy="17" r="1.5"/>',
    "wrench": '<path d="M14.5 6.5a4 4 0 005 5L12 19a2.1 2.1 0 01-3-3l7.5-7.5"/><path d="M14.5 6.5a4 4 0 014-4l-2.5 2.5 1 2 2 1 2.5-2.5a4 4 0 01-4 4"/>',
    "factory": '<path d="M3 21V10l6 3V10l6 3V6h4v15H3z"/><path d="M8 21v-3M13 21v-3"/>',
    "briefcase": '<rect x="3" y="7" width="18" height="13" rx="2"/><path d="M9 7V5a2 2 0 012-2h2a2 2 0 012 2v2M3 13h18"/>',
    "globe": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"/>',
    "bolt": '<path d="M13 2L4 14h7l-1 8 9-12h-7l1-8z"/>',
}


CAT_ICONS = {"restaurant": "utensils", "dental": "tooth", "fitness": "dumbbell", "real_estate": "home", "ecommerce": "bag", "healthcare": "stethoscope",
             "legal": "scale", "hospitality": "bed", "automotive": "car", "home_services": "wrench", "manufacturing": "factory"}


@register.filter
def catico(key):
    return CAT_ICONS.get(key, "briefcase")


@register.simple_tag
def vstatic(path):
    """Static URL with a ?v=<file modified time> suffix so browsers never keep an old dashboard.css/js after an update."""
    import os
    from django.conf import settings
    from django.contrib.staticfiles import finders
    from django.templatetags.static import static
    url = static(path)
    try:
        found = finders.find(path)
        if found:
            url += ("&" if "?" in url else "?") + "v=" + str(int(os.path.getmtime(found)))
    except Exception:
        pass
    return url


@register.simple_tag
def icon(name, size=18, cls=""):
    body = ICONS.get(name, ICONS["doc"])
    return format_html('<svg class="ic {}" width="{}" height="{}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{}</svg>', cls, size, size, mark_safe(body))


BADGES = {
    "published": "ok", "approved": "ok", "active": "ok", "won": "ok", "sent": "ok", "subscribed": "ok", "completed": "ok", "verified": "ok", "success": "ok",
    "draft": "muted", "archived": "muted", "closed": "muted", "bot": "muted", "cancelled": "muted", "unsubscribed": "muted", "pending": "warn", "pending_approval": "warn",
    "review": "info", "new": "brand", "scheduled": "info", "queued": "info", "sending": "info", "contacted": "info", "qualified": "violet", "proposal": "violet", "waiting": "warn",
    "audited": "info", "replied": "ok", "converted": "ok", "high": "ok", "medium": "warn", "low": "muted", "unknown": "muted", "viewed": "info", "accept_requested": "violet", "expired": "muted", "declined": "bad", "suppressed": "bad", "skipped": "muted", "done": "ok", "stopped": "muted", "rejected": "bad", "failed": "bad", "lost": "bad", "spam": "bad", "suspended": "bad", "broken": "bad", "bounced": "bad", "paused": "warn", "danger": "bad", "warning": "warn", "error": "bad",
    "issued": "info", "partially_paid": "warn", "paid": "ok", "overdue": "bad", "void": "muted", "initiated": "info", "confirmed": "ok", "recorded": "muted", "succeeded": "ok", "processed": "ok", "ignored": "muted",
}


@register.filter
def badge_class(value):
    return "b-" + BADGES.get(str(value).lower().replace(" ", "_"), "muted")


@register.filter
def get_item(d, key):
    try:
        return d.get(key)
    except Exception:
        return None


@register.filter
def filesize(n):
    try:
        n = float(n)
    except (TypeError, ValueError):
        return ""
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


@register.filter
def to_json(value):
    return mark_safe(json.dumps(value).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026"))


@register.filter
def initials(name):
    parts = str(name or "?").split()
    return "".join(p[0] for p in parts[:2]).upper() or "?"


@register.filter
def pretty_action(a):
    return str(a).replace(".", " · ").replace("_", " ")


@register.simple_tag
def qs_replace(querystring, **kwargs):
    from urllib.parse import parse_qsl, urlencode

    d = dict(parse_qsl(querystring or ""))
    for k, v in kwargs.items():
        if v in ("", None):
            d.pop(k, None)
        else:
            d[k] = v
    return urlencode(d)


@register.filter
def has_perm(user, spec):
    module, _, action = str(spec).partition(".")
    try:
        return user.can(module, action or "view")
    except Exception:
        return False


@register.filter
def is_wide(bf):
    from django import forms as dj

    w = bf.field.widget
    name = bf.name
    return isinstance(w, (dj.Textarea, dj.SelectMultiple)) or w.template_name in ("dashboard/widgets/repeater.html", "dashboard/widgets/richtext.html", "dashboard/widgets/media_picker.html") or name in ("schema_json", "title", "name", "slug") and False


@register.filter
def is_checkbox(bf):
    from django import forms as dj

    return isinstance(bf.field.widget, dj.CheckboxInput)


@register.filter(name="money")
def money_filter(value, cur="USD"):
    """{{ invoice.total|money:invoice.currency }} -> 'USD 1,250.00' (Decimal-safe, currency precision aware)."""
    from apps.billing import money as bm
    try:
        return bm.fmt(value, cur)
    except Exception:
        return ""


@register.filter
def split(value, sep=","):
    return [x.strip() for x in str(value).split(sep) if x.strip()]


@register.filter(name="field")
def form_field(form, name):
    try:
        return form[name]
    except KeyError:
        return None
