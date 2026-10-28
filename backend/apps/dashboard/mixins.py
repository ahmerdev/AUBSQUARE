from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache


def forbidden(request, msg="You don't have permission to do that."):
    if request.headers.get("x-requested-with") == "fetch" or request.path.endswith(".json") or "application/json" in request.headers.get("accept", ""):
        return JsonResponse({"error": {"code": "forbidden", "message": msg}}, status=403)
    return render(request, "dashboard/403.html", {"message": msg, "page_title": "Access denied"}, status=403)


def needs(module, action="view"):
    """Server-side permission gate. Every dashboard view must be wrapped by this (or `staff_only`)."""

    def deco(fn):
        @wraps(fn)
        @never_cache
        def wrapper(request, *args, **kwargs):
            u = request.user
            if not u.is_authenticated or not u.can_access_dashboard:
                return redirect_to_login(request.get_full_path(), "/dashboard/login/")
            mod = module(request, *args, **kwargs) if callable(module) else module
            act = action(request, *args, **kwargs) if callable(action) else action
            if mod and not u.can(mod, act):
                return forbidden(request)
            return fn(request, *args, **kwargs)

        return wrapper

    return deco


def staff_only(fn):
    return needs(None)(fn)


def superuser_only(fn):
    @wraps(fn)
    @never_cache
    def wrapper(request, *args, **kwargs):
        u = request.user
        if not u.is_authenticated or not u.can_access_dashboard:
            return redirect_to_login(request.get_full_path(), "/dashboard/login/")
        if not u.is_superuser:
            return forbidden(request, "Only a Super Admin can open this page.")
        return fn(request, *args, **kwargs)

    return wrapper
