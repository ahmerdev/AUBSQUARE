from django.contrib.auth import get_user_model
from django.core import signing
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import Role
from apps.leads.models import BudgetOption, LeadFormConfig
from apps.leads.services import FORM_SALT

User = get_user_model()
PW = "Corr3ct-Horse-Battery-77!"


def old_token(seconds=30):
    """A valid signed form token that looks like it was issued `seconds` ago."""
    return signing.dumps({"t": timezone.now().timestamp() - seconds}, salt=FORM_SALT)


class Base(TestCase):
    def setUp(self):
        cache.clear()
        self.root = User.objects.create_superuser(email="root@example.com", password=PW, full_name="Root Admin")
        BudgetOption.objects.get_or_create(label="$1,500 - $3,000", defaults={"value": "$1,500 - $3,000"})
        LeadFormConfig.load()

    def make_user(self, email, role_slug=None, status="approved", **kw):
        role = Role.objects.get(slug=role_slug) if role_slug else None
        u = User.objects.create_user(email=email, password=PW, full_name=kw.pop("full_name", email.split("@")[0]), **kw)
        u.status, u.role, u.email_verified = status, role, True
        u.save()
        return u

    def login(self, user):
        self.client.force_login(user, backend="apps.accounts.backends.ApprovedEmailBackend")
        return self.client
