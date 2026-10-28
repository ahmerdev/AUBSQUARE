from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from apps.core.services import client_ip, log_activity
from . import services
from .forms import InviteAcceptForm, LoginForm, ProfileForm, QueuedPasswordResetForm, RegisterForm, StyledPasswordChange, StyledSetPassword
from .models import Invitation, User

GENERIC_FAIL = "Invalid email or password, or the account is not active."


def _safe_next(request):
    nxt = request.POST.get("next") or request.GET.get("next") or ""
    return nxt if nxt and url_has_allowed_host_and_scheme(nxt, {request.get_host()}, request.is_secure()) else settings.LOGIN_REDIRECT_URL


@never_cache
def login_view(request):
    if request.user.is_authenticated and request.user.can_access_dashboard:
        return redirect(settings.LOGIN_REDIRECT_URL)
    form = LoginForm(request.POST or None)
    notice = ""
    if request.method == "POST" and form.is_valid():
        email, pw, ip = form.cleaned_data["email"].lower(), form.cleaned_data["password"], client_ip(request)
        if services.is_locked_out(email, ip):
            services.record_attempt(email, ip, False)
            form.add_error(None, "Too many failed attempts. Please wait a few minutes and try again.")
            log_activity(None, "auth.locked", None, email, request, security=True)
        else:
            user = authenticate(request, email=email, password=pw)
            if user is not None and user.can_access_dashboard:
                services.record_attempt(email, ip, True)
                request.session.cycle_key()
                login(request, user, backend="apps.accounts.backends.ApprovedEmailBackend")
                log_activity(user, "auth.login", user, "", request, security=True)
                return redirect(_safe_next(request))
            services.record_attempt(email, ip, False)
            log_activity(None, "auth.failed", None, email, request, security=True)
            # Only reveal a pending/rejected state after the PASSWORD is proven correct.
            u = User.objects.filter(email__iexact=email).first()
            if u and u.check_password(pw) and u.status != User.APPROVED:
                notice = {
                    User.PENDING: "Your account is waiting for Super Admin approval. You will be able to sign in once it is approved.",
                    User.REJECTED: "Your account request was not approved. Please contact a Super Admin.",
                    User.SUSPENDED: "Your account is suspended. Please contact a Super Admin.",
                }.get(u.status, "")
            if not notice:
                form.add_error(None, GENERIC_FAIL)
    return render(request, "accounts/login.html", {"form": form, "notice": notice, "next": request.GET.get("next", "")})


@require_POST
def logout_view(request):
    if request.user.is_authenticated:
        log_activity(request.user, "auth.logout", request.user, "", request, security=True)
    logout(request)
    return redirect("accounts:login")


@never_cache
def register_view(request):
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"].lower()
        # Same response whether or not the email is taken (no account enumeration).
        if not User.objects.filter(email__iexact=email).exists():
            services.register_staff(email, form.cleaned_data["full_name"], form.cleaned_data["password1"], request)
        return render(request, "accounts/register_done.html")
    return render(request, "accounts/register.html", {"form": form})


def verify_email(request, token):
    try:
        data = services.read_verification_token(token)
        user = User.objects.get(pk=data["uid"], email=data["email"])
    except (signing.BadSignature, signing.SignatureExpired, User.DoesNotExist):
        return render(request, "accounts/message.html", {"title": "Link expired", "text": "This verification link is invalid or has expired.", "ok": False}, status=400)
    if not user.email_verified:
        user.email_verified = True
        user.save(update_fields=["email_verified"])
        log_activity(user, "user.email_verified", user, "", request, security=True)
    return render(request, "accounts/message.html", {"title": "Email verified", "text": "Thank you. Your account now waits for Super Admin approval; you will be notified by email.", "ok": True})


@never_cache
def accept_invite(request, token):
    inv = Invitation.objects.filter(token_hash=Invitation.hash_token(token)).first()
    if not inv or not inv.is_valid:
        return render(request, "accounts/message.html", {"title": "Invitation unavailable", "text": "This invitation is invalid, already used, or expired. Ask a Super Admin for a new one.", "ok": False}, status=400)
    form = InviteAcceptForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            user = services.accept_invitation(inv, form.cleaned_data["full_name"], form.cleaned_data["password1"], request)
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            text = "Your account is active. You can sign in now." if user.status == User.APPROVED else "Your account was created and is waiting for Super Admin approval."
            return render(request, "accounts/message.html", {"title": "Welcome aboard", "text": text, "ok": True, "login": user.status == User.APPROVED})
    return render(request, "accounts/accept_invite.html", {"form": form, "invitation": inv})


# ---- password reset (Django's token machinery; responses never confirm whether an email exists) ----
class ResetRequest(auth_views.PasswordResetView):
    form_class = QueuedPasswordResetForm
    template_name = "accounts/reset_request.html"
    success_url = reverse_lazy("accounts:reset_sent")
    email_template_name = "accounts/emails/reset_email.txt"
    subject_template_name = "accounts/emails/reset_subject.txt"

    def get_extra_email_context(self):
        from urllib.parse import urlparse

        u = urlparse(settings.SITE_URL)
        return {"domain": u.netloc or self.request.get_host(), "protocol": u.scheme or "https"}

    def form_valid(self, form):
        from apps.core.services import absolute_url

        log_activity(None, "auth.reset_requested", None, form.cleaned_data["email"], self.request, security=True)
        return super().form_valid(form)


class ResetConfirm(auth_views.PasswordResetConfirmView):
    form_class = StyledSetPassword
    template_name = "accounts/reset_confirm.html"
    success_url = reverse_lazy("accounts:reset_done")

    def form_valid(self, form):
        resp = super().form_valid(form)
        services.invalidate_sessions(form.user)
        log_activity(form.user, "auth.password_reset", form.user, "", self.request, security=True)
        return resp


@login_required
def profile(request):
    user = request.user
    pform = ProfileForm(request.POST if request.POST.get("form") == "profile" else None, instance=user)
    cform = StyledPasswordChange(user, request.POST if request.POST.get("form") == "password" else None)
    if request.method == "POST":
        if request.POST.get("form") == "profile" and pform.is_valid():
            pform.save()
            messages.success(request, "Profile updated.")
            return redirect("accounts:profile")
        if request.POST.get("form") == "password" and cform.is_valid():
            cform.save()
            update_session_auth_hash(request, user)
            log_activity(user, "auth.password_changed", user, "", request, security=True)
            messages.success(request, "Password changed.")
            return redirect("accounts:profile")
    return render(request, "dashboard/profile.html", {"pform": pform, "cform": cform, "page_title": "My profile", "crumbs": [("Dashboard", "/dashboard/"), ("Profile", "")]})
