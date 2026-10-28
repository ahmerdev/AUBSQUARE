"""Create the first Super Admin from environment variables (no credentials are stored in code).

    AUB_ADMIN_EMAIL=you@company.com AUB_ADMIN_PASSWORD='long-random-password' python manage.py bootstrap_admin

Does nothing if a Super Admin already exists. Alternatively use the standard `python manage.py createsuperuser`.
Remove the password variable from your environment afterwards.
"""
import os

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import User


class Command(BaseCommand):
    help = "Create the first Super Admin from AUB_ADMIN_EMAIL / AUB_ADMIN_PASSWORD."

    def handle(self, *a, **o):
        if User.objects.filter(is_superuser=True).exists():
            self.stdout.write("A Super Admin already exists - nothing to do.")
            return
        email, pw = os.environ.get("AUB_ADMIN_EMAIL", "").strip().lower(), os.environ.get("AUB_ADMIN_PASSWORD", "")
        if not email or not pw:
            raise CommandError("Set AUB_ADMIN_EMAIL and AUB_ADMIN_PASSWORD, or run `createsuperuser`.")
        try:
            validate_password(pw)
        except ValidationError as e:
            raise CommandError("Password rejected: " + " ".join(e.messages))
        User.objects.create_superuser(email=email, password=pw, full_name=os.environ.get("AUB_ADMIN_NAME", "Super Admin"))
        self.stdout.write(self.style.SUCCESS(f"Super Admin created: {email}. Remove AUB_ADMIN_PASSWORD from the environment now."))
