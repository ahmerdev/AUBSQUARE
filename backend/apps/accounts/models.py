import secrets
import hashlib

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils import timezone

from .permissions import ACTION_KEYS, MODULE_KEYS


class Role(models.Model):
    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=60, unique=True)
    description = models.CharField(max_length=200, blank=True)
    permissions = models.JSONField(default=dict, blank=True, help_text="{module: [actions]}")
    is_system = models.BooleanField(default=False, help_text="Built-in roles can be edited but not deleted.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.name

    def clean_permissions(self):
        clean = {}
        for module, actions in (self.permissions or {}).items():
            if module in MODULE_KEYS:
                acts = [a for a in actions if a in ACTION_KEYS]
                if acts:
                    clean[module] = acts
        self.permissions = clean

    def save(self, *args, **kwargs):
        self.clean_permissions()
        super().save(*args, **kwargs)


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create(self, email, password, **extra):
        if not email:
            raise ValueError("Email is required")
        user = self.model(email=self.normalize_email(email).lower(), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("status", User.PENDING)
        return self._create(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.update(is_superuser=True, is_staff=True, status=User.APPROVED, email_verified=True, approved_at=timezone.now())
        return self._create(email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    PENDING, APPROVED, REJECTED, SUSPENDED = "pending", "approved", "rejected", "suspended"
    STATUS_CHOICES = [(PENDING, "Pending approval"), (APPROVED, "Approved"), (REJECTED, "Rejected"), (SUSPENDED, "Suspended")]

    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=120)
    job_title = models.CharField(max_length=120, blank=True)
    avatar_url = models.CharField(max_length=500, blank=True)
    phone = models.CharField(max_length=40, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING, db_index=True)
    role = models.ForeignKey(Role, null=True, blank=True, on_delete=models.SET_NULL, related_name="users")
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    email_verified = models.BooleanField(default=False)
    approved_by = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    approved_at = models.DateTimeField(null=True, blank=True)
    status_note = models.CharField(max_length=300, blank=True)
    date_joined = models.DateTimeField(default=timezone.now)
    notify_email = models.BooleanField("Email me important notifications", default=True)

    objects = UserManager()
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        ordering = ["full_name", "email"]

    def __str__(self):
        return self.full_name or self.email

    @property
    def display_name(self):
        return self.full_name or self.email.split("@")[0]

    @property
    def initials(self):
        parts = (self.full_name or self.email).split()
        return "".join(p[0] for p in parts[:2]).upper() or "?"

    @property
    def can_access_dashboard(self) -> bool:
        return bool(self.is_active and self.status == self.APPROVED and (self.is_superuser or self.role_id))

    def can(self, module: str, action: str = "view") -> bool:
        if not self.can_access_dashboard:
            return False
        if self.is_superuser:
            return True
        return action in (self.role.permissions or {}).get(module, [])

    def modules_with_access(self):
        return [m for m in MODULE_KEYS if self.can(m, "view")]


class Invitation(models.Model):
    email = models.EmailField()
    role = models.ForeignKey(Role, null=True, blank=True, on_delete=models.SET_NULL)
    token_hash = models.CharField(max_length=64, unique=True)
    invited_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name="invitations_sent")
    pre_approved = models.BooleanField(default=False, help_text="Super Admin explicitly approves the account at invite time.")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    @staticmethod
    def hash_token(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    @classmethod
    def create_for(cls, email, role, invited_by, pre_approved=False, days=7):
        token = secrets.token_urlsafe(32)
        inv = cls.objects.create(
            email=email.lower(), role=role, invited_by=invited_by, pre_approved=pre_approved,
            token_hash=cls.hash_token(token), expires_at=timezone.now() + timezone.timedelta(days=days),
        )
        return inv, token

    @property
    def is_valid(self):
        return not self.accepted_at and self.expires_at > timezone.now()


class LoginAttempt(models.Model):
    email = models.CharField(max_length=254, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True, db_index=True)
    success = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [models.Index(fields=["email", "created_at"])]
