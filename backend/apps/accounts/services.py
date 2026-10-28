"""Account lifecycle: invite, register, approve, reject, suspend, session invalidation, security checks."""
import logging
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse
from django.utils import timezone

from apps.core.services import absolute_url, log_activity, notify, notify_user
from .models import Invitation, LoginAttempt, Role

User = get_user_model()
log = logging.getLogger(__name__)
VERIFY_SALT = "aub.email.verify"


# ------------------------------------------------------------- throttling
def is_locked_out(email: str, ip: str | None) -> bool:
    window = timezone.now() - timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES)
    qs = LoginAttempt.objects.filter(created_at__gte=window, success=False)
    if qs.filter(email=email.lower()).count() >= settings.LOGIN_MAX_FAILURES:
        return True
    return bool(ip and qs.filter(ip_address=ip).count() >= settings.LOGIN_MAX_FAILURES * 4)


def record_attempt(email: str, ip: str | None, success: bool):
    LoginAttempt.objects.create(email=email.lower()[:254], ip_address=ip, success=success)
    if success:  # a good login clears the failure counter for that email
        LoginAttempt.objects.filter(email=email.lower(), success=False).delete()


# ------------------------------------------------------------- sessions
def invalidate_sessions(user):
    """Log a user out everywhere (used on suspension/rejection and sensitive changes)."""
    count = 0
    for s in Session.objects.filter(expire_date__gt=timezone.now()).iterator():
        if str(s.get_decoded().get("_auth_user_id")) == str(user.pk):
            s.delete()
            count += 1
    return count


# ------------------------------------------------------------- email verification
def verification_link(user) -> str:
    token = signing.dumps({"uid": user.pk, "email": user.email}, salt=VERIFY_SALT)
    return absolute_url(reverse("accounts:verify_email", args=[token]))


def read_verification_token(token: str):
    return signing.loads(token, salt=VERIFY_SALT, max_age=60 * 60 * 24 * 3)


# ------------------------------------------------------------- lifecycle
def _send(kind, to, subject, body, **kw):
    from apps.mailer.service import queue_email

    return queue_email(to=[to], subject=subject, body_text=body, kind=kind, **kw)


def register_staff(email: str, full_name: str, password: str, request=None) -> "User":
    user = User.objects.create_user(email=email, password=password, full_name=full_name, status=User.PENDING)
    log_activity(user, "user.registered", user, "Staff account requested", request, security=True)
    notify("account", "New staff account request", f"{user.full_name} <{user.email}> is waiting for approval.", "/dashboard/users/?status=pending", module="users", level="warning")
    _send("account", user.email, "Verify your AUB SQUARE staff email",
          f"Hi {user.full_name},\n\nPlease confirm your email address:\n{verification_link(user)}\n\n"
          "After verification your account stays 'Pending approval' until a Super Admin approves it.")
    return user


def accept_invitation(invitation: Invitation, full_name: str, password: str, request=None):
    if not invitation.is_valid:
        raise ValidationError("This invitation is invalid or has expired.")
    if User.objects.filter(email__iexact=invitation.email).exists():
        raise ValidationError("An account with this email already exists.")
    user = User.objects.create_user(
        email=invitation.email, password=password, full_name=full_name, role=invitation.role,
        status=User.APPROVED if invitation.pre_approved else User.PENDING, email_verified=True,
        approved_by=invitation.invited_by if invitation.pre_approved else None,
        approved_at=timezone.now() if invitation.pre_approved else None,
    )
    invitation.accepted_at = timezone.now()
    invitation.save(update_fields=["accepted_at"])
    log_activity(user, "user.invite_accepted", user, f"Role: {invitation.role}", request, security=True)
    if not invitation.pre_approved:
        notify("account", "Invited user is waiting for approval", f"{user.full_name} accepted an invitation.", "/dashboard/users/?status=pending", module="users", level="warning")
    return user


def _require_super(actor):
    if not getattr(actor, "is_superuser", False) or not actor.can_access_dashboard:
        raise PermissionDenied("Only a Super Admin can do this.")


def approve_user(actor, user, role: Role | None, request=None):
    _require_super(actor)
    if user.pk == actor.pk:
        raise PermissionDenied("You cannot approve your own account.")
    if role is None and not user.role_id:
        raise ValidationError("Choose a role before approving.")
    if role is not None:
        user.role = role
    user.status = User.APPROVED
    user.approved_by, user.approved_at, user.status_note = actor, timezone.now(), ""
    user.save()
    log_activity(actor, "user.approved", user, f"Role: {user.role}", request, security=True)
    notify_user(user, "account", "Your account was approved", "You can now access the dashboard.", "/dashboard/", "success")
    _send("account", user.email, "Your AUB SQUARE dashboard account is approved",
          f"Hi {user.full_name},\n\nYour account has been approved with the role “{user.role}”.\nSign in: {absolute_url('/dashboard/login/')}")


def reject_user(actor, user, reason="", request=None):
    _require_super(actor)
    if user.is_superuser:
        raise PermissionDenied("Super Admins cannot be rejected.")
    user.status, user.status_note = User.REJECTED, reason[:300]
    user.save(update_fields=["status", "status_note"])
    invalidate_sessions(user)
    log_activity(actor, "user.rejected", user, reason, request, security=True)
    _send("account", user.email, "Your AUB SQUARE account request", f"Hi {user.full_name},\n\nWe're unable to approve your account request.\n{reason}")


def suspend_user(actor, user, reason="", request=None):
    _require_super(actor)
    if user.pk == actor.pk or user.is_superuser:
        raise PermissionDenied("This account cannot be suspended.")
    user.status, user.status_note = User.SUSPENDED, reason[:300]
    user.save(update_fields=["status", "status_note"])
    invalidate_sessions(user)
    log_activity(actor, "user.suspended", user, reason, request, security=True)


def reactivate_user(actor, user, request=None):
    _require_super(actor)
    user.status, user.status_note = User.APPROVED, ""
    user.save(update_fields=["status", "status_note"])
    log_activity(actor, "user.reactivated", user, "", request, security=True)


def change_role(actor, user, role: Role, request=None):
    _require_super(actor)
    if user.pk == actor.pk:
        raise PermissionDenied("You cannot change your own role.")
    old = user.role
    user.role = role
    user.save(update_fields=["role"])
    log_activity(actor, "user.role_changed", user, f"{old} → {role}", request, security=True)


def can_delete_user(actor, user) -> bool:
    if not actor.is_superuser or user.pk == actor.pk:
        return False
    if user.is_superuser and User.objects.filter(is_superuser=True, is_active=True).count() <= 1:
        return False
    return True
