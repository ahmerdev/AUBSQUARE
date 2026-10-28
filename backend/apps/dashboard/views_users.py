from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.core.validators import validate_email
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts import services
from apps.accounts.models import Invitation, Role, User
from apps.accounts.permissions import ACTIONS, MODULES
from apps.core.models import ActivityLog
from apps.core.services import absolute_url, log_activity
from apps.mailer.service import queue_email
from .mixins import needs, superuser_only


@needs("users", "view")
def users_list(request):
    status = request.GET.get("status", "")
    qs = User.objects.select_related("role")
    if status in dict(User.STATUS_CHOICES):
        qs = qs.filter(status=status)
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(full_name__icontains=q) | Q(email__icontains=q))
    page = Paginator(qs.order_by("status", "full_name"), 25).get_page(request.GET.get("page"))
    counts = {k: User.objects.filter(status=k).count() for k, _ in User.STATUS_CHOICES}
    invites = Invitation.objects.select_related("role", "invited_by").filter(accepted_at__isnull=True).order_by("-created_at")[:10]
    return render(request, "dashboard/users.html", {
        "page": page, "status": status, "counts": counts, "q": q, "statuses": User.STATUS_CHOICES, "roles": Role.objects.all(), "invites": invites, "now": timezone.now(),
        "is_super": request.user.is_superuser, "total": User.objects.count(),
        "page_title": "Users & roles", "crumbs": [("Dashboard", "/dashboard/"), ("Users & roles", "")],
    })


@needs("users", "view")
def user_detail(request, pk):
    u = get_object_or_404(User.objects.select_related("role", "approved_by"), pk=pk)
    logs = ActivityLog.objects.filter(Q(actor=u) | Q(target_type="User", target_id=str(u.pk))).select_related("actor")[:20]
    return render(request, "dashboard/user_detail.html", {
        "u": u, "roles": Role.objects.all(), "logs": logs, "is_super": request.user.is_superuser, "is_self": u.pk == request.user.pk,
        "can_delete": services.can_delete_user(request.user, u), "modules": MODULES,
        "page_title": u.display_name, "crumbs": [("Dashboard", "/dashboard/"), ("Users & roles", "/dashboard/users/"), (u.display_name, "")],
    })


@superuser_only
@require_POST
def user_action(request, pk):
    u = get_object_or_404(User, pk=pk)
    act = request.POST.get("action")
    reason = request.POST.get("reason", "")[:300]
    try:
        if act == "approve":
            role = Role.objects.filter(pk=request.POST.get("role") or 0).first()
            services.approve_user(request.user, u, role, request)
            messages.success(request, f"{u.display_name} approved.")
        elif act == "reject":
            services.reject_user(request.user, u, reason, request)
            messages.success(request, f"{u.display_name} rejected.")
        elif act == "suspend":
            services.suspend_user(request.user, u, reason, request)
            messages.success(request, f"{u.display_name} suspended and signed out everywhere.")
        elif act == "reactivate":
            services.reactivate_user(request.user, u, request)
            messages.success(request, f"{u.display_name} reactivated.")
        elif act == "role":
            role = get_object_or_404(Role, pk=request.POST.get("role"))
            services.change_role(request.user, u, role, request)
            messages.success(request, "Role updated.")
        elif act == "logout":
            n = services.invalidate_sessions(u)
            log_activity(request.user, "user.force_logout", u, f"{n} sessions", request, security=True)
            messages.success(request, f"Signed out {n} session(s).")
        elif act == "delete":
            if not services.can_delete_user(request.user, u):
                raise PermissionDenied("This account can't be deleted.")
            log_activity(request.user, "user.deleted", u, u.email, request, security=True)
            services.invalidate_sessions(u)
            u.delete()
            messages.success(request, "User deleted. Their past activity remains in the log.")
            return redirect("dashboard:users")
    except (PermissionDenied, ValidationError) as exc:
        messages.error(request, "; ".join(exc.messages) if isinstance(exc, ValidationError) else str(exc))
    nxt = request.POST.get("next", "")
    if nxt.startswith("/dashboard/") and not nxt.startswith("//"):
        return redirect(nxt)
    return redirect("dashboard:user_detail", pk=pk)


class InviteForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={"class": "input", "placeholder": "colleague@company.com"}))
    role = forms.ModelChoiceField(queryset=Role.objects.all(), widget=forms.Select(attrs={"class": "input"}))
    pre_approved = forms.BooleanField(required=False, label="Approve automatically when they accept (I vouch for this person)", widget=forms.CheckboxInput(attrs={"class": "check"}))


@superuser_only
def invite_user(request):
    form = InviteForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        if User.objects.filter(email__iexact=d["email"]).exists():
            form.add_error("email", "A user with this email already exists.")
        else:
            inv, token = Invitation.create_for(d["email"], d["role"], request.user, d["pre_approved"])
            link = absolute_url(f"/dashboard/invite/{token}/")
            queue_email([d["email"]], "You're invited to the AUB SQUARE dashboard",
                        f"Hi,\n\n{request.user.display_name} invited you to join the AUB SQUARE dashboard as “{d['role'].name}”.\n\nAccept the invitation (valid 7 days):\n{link}\n", kind="account", created_by=request.user)
            log_activity(request.user, "user.invited", inv, f"{d['email']} as {d['role']}", request, security=True)
            messages.success(request, f"Invitation emailed to {d['email']}. The link is valid for 7 days.")
            return redirect("dashboard:users")
    return render(request, "dashboard/invite.html", {"form": form, "page_title": "Invite a user", "crumbs": [("Dashboard", "/dashboard/"), ("Users & roles", "/dashboard/users/"), ("Invite", "")]})


@superuser_only
@require_POST
def invite_revoke(request, pk):
    inv = get_object_or_404(Invitation, pk=pk, accepted_at__isnull=True)
    log_activity(request.user, "user.invite_revoked", inv, inv.email, request, security=True)
    inv.delete()
    messages.success(request, "Invitation revoked.")
    return redirect("dashboard:users")


# ------------------------------------------------------------------ roles & the permission matrix
@needs("users", "view")
def roles_list(request):
    roles = Role.objects.all()
    for r in roles:
        r.user_count = r.users.count()
        r.module_count = len([m for m, a in (r.permissions or {}).items() if a])
    return render(request, "dashboard/roles.html", {"roles": roles, "is_super": request.user.is_superuser, "page_title": "Roles & permissions", "crumbs": [("Dashboard", "/dashboard/"), ("Users & roles", "/dashboard/users/"), ("Roles", "")]})


@superuser_only
def role_edit(request, pk=None):
    role = get_object_or_404(Role, pk=pk) if pk else Role()
    if request.method == "POST":
        name = request.POST.get("name", "").strip()[:60]
        desc = request.POST.get("description", "").strip()[:200]
        perms = {}
        for key, _ in MODULES:
            acts = [a for a, _ in ACTIONS if request.POST.get(f"p-{key}-{a}")]
            if acts:
                perms[key] = acts
        if not name:
            messages.error(request, "Give the role a name.")
        elif Role.objects.filter(name__iexact=name).exclude(pk=role.pk).exists():
            messages.error(request, "A role with this name already exists.")
        else:
            role.name, role.description, role.permissions = name, desc, perms
            if not role.slug:
                from django.utils.text import slugify

                base, n = slugify(name)[:50] or "role", 2
                role.slug = base
                while Role.objects.filter(slug=role.slug).exists():
                    role.slug, n = f"{base}-{n}", n + 1
            role.save()
            log_activity(request.user, "role.saved", role, f"{len(perms)} modules", request, security=True)
            messages.success(request, "Role saved. Permissions apply immediately.")
            return redirect("dashboard:roles")
    matrix = [{"key": k, "label": lbl, "actions": [(a, al, a in (role.permissions or {}).get(k, [])) for a, al in ACTIONS]} for k, lbl in MODULES]
    return render(request, "dashboard/role_form.html", {"role": role, "matrix": matrix, "actions": ACTIONS, "page_title": role.name or "New role",
                                                        "crumbs": [("Dashboard", "/dashboard/"), ("Users & roles", "/dashboard/users/"), ("Roles", "/dashboard/roles/"), (role.name or "New role", "")]})


@superuser_only
@require_POST
def role_delete(request, pk):
    role = get_object_or_404(Role, pk=pk)
    if role.is_system:
        messages.error(request, "Built-in roles can't be deleted.")
    elif role.users.exists():
        messages.error(request, "Move the users on this role to another role first.")
    else:
        log_activity(request.user, "role.deleted", role, "", request, security=True)
        role.delete()
        messages.success(request, "Role deleted.")
    return redirect("dashboard:roles")
