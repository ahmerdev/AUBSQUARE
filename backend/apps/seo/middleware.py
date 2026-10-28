from django.db.models import F
from django.http import HttpResponsePermanentRedirect, HttpResponseRedirect
from django.utils import timezone

from apps.core.services import cached_public

SKIP = ("/dashboard", "/api", "/static", "/media", "/admin")


def _redirect_map():
    from .models import Redirect

    return {r.from_path.rstrip("/") or "/": (r.to_path, r.permanent, r.pk) for r in Redirect.objects.filter(is_active=True)}


class RedirectMiddleware:
    """Serves managed 301/302 redirects (old slugs, moved pages) before any view runs."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method in ("GET", "HEAD") and not request.path.startswith(SKIP):
            hit = cached_public("redirect-map", _redirect_map, 300).get(request.path.rstrip("/") or "/")
            if hit:
                to, permanent, pk = hit
                if to.rstrip("/") != request.path.rstrip("/"):
                    from .models import Redirect

                    Redirect.objects.filter(pk=pk).update(hit_count=F("hit_count") + 1, last_hit_at=timezone.now())
                    return (HttpResponsePermanentRedirect if permanent else HttpResponseRedirect)(to)
        return self.get_response(request)
