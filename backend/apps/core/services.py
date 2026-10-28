import hashlib
import logging

from django.apps import apps
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

log = logging.getLogger(__name__)

# ---------------------------------------------------------------- request helpers
def client_ip(request) -> str | None:
    """Best-effort client IP. Only trust X-Forwarded-For when explicitly enabled (behind a proxy)."""
    if getattr(settings, "TRUST_X_FORWARDED_FOR", False):
        xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if xff:
            return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def visitor_hash(request) -> str:
    """Anonymous, daily-rotating hash (no raw IP is stored for analytics / spam checks)."""
    day = timezone.now().strftime("%Y-%m-%d")
    raw = f"{settings.VISITOR_HASH_SALT}|{day}|{client_ip(request)}|{request.META.get('HTTP_USER_AGENT', '')[:200]}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


# ---------------------------------------------------------------- public content cache
_VERSION_KEY = "content:version"


def content_version() -> int:
    v = cache.get(_VERSION_KEY)
    if v is None:
        v = 1
        cache.set(_VERSION_KEY, v, None)
    return v


def bump_content_version():
    try:
        cache.incr(_VERSION_KEY)
    except ValueError:
        cache.set(_VERSION_KEY, 2, None)


def cached_public(key: str, builder, timeout: int = 300):
    """Cache a public API payload; any content save bumps the version so updates appear immediately."""
    full = f"pub:{content_version()}:{key}"
    data = cache.get(full)
    if data is None:
        data = builder()
        cache.set(full, data, timeout)
    return data


# ---------------------------------------------------------------- activity log
def log_activity(user, action: str, obj=None, detail: str = "", request=None, security: bool = False):
    from .models import ActivityLog

    try:
        ActivityLog.objects.create(
            actor=user if getattr(user, "pk", None) else None,
            actor_label=(getattr(user, "email", "") or "")[:200] if getattr(user, "pk", None) else "system",
            action=action[:60],
            target_type=obj.__class__.__name__ if obj is not None else "",
            target_id=str(getattr(obj, "pk", ""))[:40] if obj is not None else "",
            target_repr=str(obj)[:200] if obj is not None else "",
            detail=detail[:500],
            ip_address=client_ip(request) if request is not None else None,
            is_security=security,
        )
    except Exception:  # logging must never break a request
        log.exception("activity log failed")


# ---------------------------------------------------------------- notifications
def notify(kind: str, title: str, body: str = "", url: str = "", module: str = "", level: str = "info", exclude=None):
    """Fan out an in-dashboard notification to every approved staff member allowed to view `module`."""
    from apps.accounts.models import User
    from .models import Notification

    recipients = []
    for u in User.objects.filter(is_active=True, status=User.APPROVED).select_related("role"):
        if exclude is not None and u.pk == getattr(exclude, "pk", None):
            continue
        if not module or u.can(module, "view"):
            recipients.append(u)
    Notification.objects.bulk_create(
        [Notification(recipient=u, kind=kind, title=title[:200], body=body[:500], url=url[:300], level=level) for u in recipients]
    )
    return len(recipients)


def notify_user(user, kind: str, title: str, body: str = "", url: str = "", level: str = "info"):
    from .models import Notification

    return Notification.objects.create(recipient=user, kind=kind, title=title[:200], body=body[:500], url=url[:300], level=level)


def absolute_url(path: str) -> str:
    if path.startswith("http"):
        return path
    return f"{settings.SITE_URL}{path if path.startswith('/') else '/' + path}"


def public_media_url(value: str, request=None) -> str:
    """Turn '/media/..' paths into absolute URLs for the public API."""
    if not value:
        return ""
    if value.startswith("http://") or value.startswith("https://") or value.startswith("data:"):
        return value
    if request is not None:
        return request.build_absolute_uri(value)
    return absolute_url(value)
