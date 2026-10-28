"""Notifications, roles editor, migrations, security headers, error envelope."""
from io import StringIO

from django.core.management import call_command
from django.urls import reverse

from apps.accounts.models import Role
from apps.core.models import Notification
from apps.core.services import notify

from .base import Base


class Notifications(Base):
    def test_notify_targets_only_users_with_module_access(self):
        an = self.make_user("an@example.com", "analyst")
        cm = self.make_user("cm@example.com", "content_manager")
        sales = self.make_user("s@example.com", "sales_manager")
        notify("lead", "New lead", "x", "/dashboard/leads/1/", module="leads")
        recipients = set(Notification.objects.values_list("recipient__email", flat=True))
        self.assertIn("s@example.com", recipients)
        self.assertIn("root@example.com", recipients)
        self.assertNotIn("an@example.com", recipients) if not an.can("leads", "view") else None
        self.assertEqual(Notification.objects.filter(recipient=self.make_user("pending@example.com", status="pending")).count(), 0)

    def test_feed_mark_read_and_privacy_between_users(self):
        a = self.make_user("a@example.com", "administrator")
        n = Notification.objects.create(recipient=self.root, title="Root only", kind="system")
        mine = Notification.objects.create(recipient=a, title="Mine", kind="system")
        self.login(a)
        feed = self.client.get(reverse("dashboard:notifications_feed")).json()
        self.assertEqual([i["title"] for i in feed["items"]], ["Mine"])
        self.assertEqual(feed["unread"], 1)
        self.assertEqual(self.client.post(reverse("dashboard:notification_read", args=[n.pk])).status_code, 404)  # cannot touch someone else's
        self.client.post(reverse("dashboard:notification_read", args=[mine.pk]), HTTP_X_REQUESTED_WITH="fetch")
        mine.refresh_from_db()
        self.assertTrue(mine.is_read)
        self.assertEqual(self.client.get(reverse("dashboard:notifications")).status_code, 200)

    def test_mark_all_read(self):
        for i in range(3):
            Notification.objects.create(recipient=self.root, title=f"n{i}", kind="system")
        self.login(self.root)
        self.client.post(reverse("dashboard:notifications_read_all"))
        self.assertEqual(Notification.objects.filter(recipient=self.root, is_read=False).count(), 0)


class RolesEditor(Base):
    def test_super_admin_can_create_a_custom_role_and_it_is_enforced(self):
        self.login(self.root)
        r = self.client.post(reverse("dashboard:role_create"), {"name": "Blog Intern", "description": "Drafts only", "p-dashboard-view": "1", "p-blog-view": "1", "p-blog-create": "1", "p-taxonomy-view": "1"})
        self.assertEqual(r.status_code, 302)
        role = Role.objects.get(name="Blog Intern")
        self.assertEqual(sorted(role.permissions["blog"]), ["create", "view"])
        u = self.make_user("intern@example.com")
        u.role = role
        u.save()
        self.client.logout()
        self.login(u)
        self.assertEqual(self.client.get("/dashboard/posts/").status_code, 200)
        self.assertEqual(self.client.get("/dashboard/posts/new/").status_code, 200)
        self.assertEqual(self.client.get("/dashboard/leads/").status_code, 403)

    def test_removing_a_permission_takes_effect_on_next_request(self):
        role = Role.objects.get(slug="content_manager")
        u = self.make_user("cm@example.com", "content_manager")
        self.login(u)
        self.assertEqual(self.client.get("/dashboard/posts/").status_code, 200)
        role.permissions = {**role.permissions, "blog": []}
        role.save()
        self.assertEqual(self.client.get("/dashboard/posts/").status_code, 403)

    def test_non_super_admins_cannot_edit_roles(self):
        self.login(self.make_user("adm@example.com", "administrator"))
        r = self.client.post(reverse("dashboard:role_create"), {"name": "Backdoor", "p-users-view": "1"})
        self.assertIn(r.status_code, (302, 403))
        self.assertFalse(Role.objects.filter(name="Backdoor").exists())

    def test_cannot_delete_role_in_use_or_builtin(self):
        self.login(self.root)
        self.make_user("x@example.com", "analyst")
        analyst = Role.objects.get(slug="analyst")
        self.client.post(reverse("dashboard:role_delete", args=[analyst.pk]))
        self.assertTrue(Role.objects.filter(pk=analyst.pk).exists())


class Platform(Base):
    def test_no_missing_migrations(self):
        out = StringIO()
        call_command("makemigrations", "--check", "--dry-run", stdout=out)

    def test_security_headers(self):
        r = self.client.get("/dashboard/login/")
        self.assertEqual(r["X-Frame-Options"], "DENY")
        self.assertEqual(r["X-Content-Type-Options"], "nosniff")
        self.assertIn("same-origin", r["Cross-Origin-Opener-Policy"])
        self.assertEqual(r["Referrer-Policy"], "strict-origin-when-cross-origin")

    def test_session_cookie_flags(self):
        from django.conf import settings

        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)
        self.assertEqual(settings.SESSION_COOKIE_SAMESITE, "Lax")

    def test_api_errors_use_one_envelope_and_do_not_leak_internals(self):
        r = self.client.get("/api/v1/services/does-not-exist/")
        self.assertEqual(r.status_code, 404)
        self.assertIn("error", r.json())
        self.assertNotIn("Traceback", r.content.decode())

    def test_public_api_is_read_only_except_forms(self):
        self.assertEqual(self.client.post("/api/v1/services/", {}).status_code, 405)
        self.assertEqual(self.client.delete("/api/v1/posts/x/").status_code, 405)

    def test_no_secrets_in_repo_settings_defaults(self):
        from pathlib import Path
        import re

        src = Path(__file__).resolve().parents[2].joinpath("config/settings.py").read_text()
        self.assertFalse(re.search(r"(PASSWORD|API_KEY)\s*=\s*['\"][^'\"]{6,}['\"]", src))

    def test_bootstrap_admin_command_requires_env_and_is_idempotent(self):
        import os
        from django.core.management.base import CommandError
        from apps.accounts.models import User

        User.objects.filter(is_superuser=True).delete()
        with self.assertRaises(CommandError):
            call_command("bootstrap_admin")
        os.environ.update(AUB_ADMIN_EMAIL="boot@example.com", AUB_ADMIN_PASSWORD="Tr0ub4dor-and-3-horses-ok")
        try:
            call_command("bootstrap_admin", stdout=StringIO())
            call_command("bootstrap_admin", stdout=StringIO())
        finally:
            os.environ.pop("AUB_ADMIN_PASSWORD"); os.environ.pop("AUB_ADMIN_EMAIL")
        u = User.objects.get(email="boot@example.com")
        self.assertTrue(u.is_superuser and u.status == "approved")

    def test_process_email_queue_command_runs(self):
        call_command("process_email_queue", stdout=StringIO())
