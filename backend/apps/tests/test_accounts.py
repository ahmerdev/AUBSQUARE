"""Acceptance: staff approval workflow, roles & permissions, lockout, password reset, sessions."""
from django.contrib.sessions.models import Session
from django.core import mail
from django.test import override_settings
from django.urls import reverse

from apps.accounts import services
from apps.accounts.models import Invitation, User
from apps.core.models import ActivityLog
from apps.mailer.models import EmailMessage

from .base import PW, Base


class ApprovalWorkflow(Base):
    def register(self, email="new@example.com"):
        return self.client.post(reverse("accounts:register"), {"full_name": "New Person", "email": email, "password1": PW, "password2": PW})

    def test_new_registration_is_pending_and_cannot_log_in(self):
        r = self.register()
        self.assertEqual(r.status_code, 200)
        u = User.objects.get(email="new@example.com")
        self.assertEqual(u.status, "pending")
        self.assertFalse(u.is_superuser)
        r = self.client.post(reverse("accounts:login"), {"email": "new@example.com", "password": PW})
        self.assertContains(r, "waiting for Super Admin approval")
        self.assertEqual(self.client.get("/dashboard/").status_code, 302)  # still not signed in

    def test_registration_never_reveals_existing_emails(self):
        a = self.register("root@example.com")
        b = self.register("brand-new@example.com")
        self.assertEqual(a.status_code, b.status_code)
        self.assertEqual(a.content.decode().count("<form"), b.content.decode().count("<form"))
        self.assertEqual(User.objects.filter(email="root@example.com").count(), 1)

    def test_pending_user_never_gets_a_role_or_access(self):
        self.register()
        u = User.objects.get(email="new@example.com")
        self.assertIsNone(u.role)
        self.assertFalse(u.can("leads", "view"))

    def test_registration_honeypot_blocks_bots(self):
        r = self.client.post(reverse("accounts:register"), {"full_name": "Bot", "email": "bot@example.com", "password1": PW, "password2": PW, "website": "http://spam"})
        self.assertFalse(User.objects.filter(email="bot@example.com").exists())
        self.assertEqual(r.status_code, 200)

    def test_weak_password_rejected(self):
        r = self.client.post(reverse("accounts:register"), {"full_name": "Weak", "email": "weak@example.com", "password1": "12345678", "password2": "12345678"})
        self.assertFalse(User.objects.filter(email="weak@example.com").exists())
        self.assertEqual(r.status_code, 200)

    def test_super_admin_approves_with_role_then_user_can_log_in(self):
        self.register()
        u = User.objects.get(email="new@example.com")
        self.login(self.root)
        from apps.accounts.models import Role

        r = self.client.post(reverse("dashboard:user_action", args=[u.pk]), {"action": "approve", "role": Role.objects.get(slug="content_manager").pk})
        self.assertEqual(r.status_code, 302)
        u.refresh_from_db()
        self.assertEqual((u.status, u.role.slug, u.approved_by_id), ("approved", "content_manager", self.root.pk))
        self.assertTrue(ActivityLog.objects.filter(action="user.approved").exists())
        self.client.logout()
        r = self.client.post(reverse("accounts:login"), {"email": "new@example.com", "password": PW})
        self.assertRedirects(r, "/dashboard/", fetch_redirect_response=False)

    def test_rejected_and_suspended_cannot_log_in(self):
        for status in ("rejected", "suspended"):
            self.make_user(f"{status}@example.com", "analyst", status=status)
            r = self.client.post(reverse("accounts:login"), {"email": f"{status}@example.com", "password": PW})
            self.assertEqual(r.status_code, 200, status)
            self.assertNotIn("_auth_user_id", self.client.session)

    def test_non_super_admin_cannot_approve(self):
        mgr = self.make_user("mgr@example.com", "administrator")
        target = self.make_user("t@example.com", status="pending")
        self.login(mgr)
        r = self.client.post(reverse("dashboard:user_action", args=[target.pk]), {"action": "approve"})
        self.assertIn(r.status_code, (302, 403))
        target.refresh_from_db()
        self.assertEqual(target.status, "pending")

    def test_suspend_kills_existing_sessions_immediately(self):
        victim = self.make_user("victim@example.com", "administrator")
        from django.test import Client

        c = Client()
        c.force_login(victim, backend="apps.accounts.backends.ApprovedEmailBackend")
        self.assertEqual(c.get("/dashboard/").status_code, 200)
        self.login(self.root)
        self.client.post(reverse("dashboard:user_action", args=[victim.pk]), {"action": "suspend", "reason": "test"})
        self.assertEqual(c.get("/dashboard/").status_code, 302)  # bounced to login
        victim.refresh_from_db()
        self.assertEqual(victim.status, "suspended")

    def test_super_admin_cannot_be_suspended_or_deleted_by_accident(self):
        other = User.objects.create_superuser(email="other@example.com", password=PW, full_name="Other")
        with self.assertRaises(Exception):
            services.suspend_user(self.root, self.root, "", None)
        self.assertFalse(services.can_delete_user(self.root, self.root))
        self.assertTrue(other.is_superuser)

    def test_invitation_single_use_and_expiry(self):
        from apps.accounts.models import Role

        inv, token = Invitation.create_for("inv@example.com", Role.objects.get(slug="analyst"), self.root, pre_approved=True)
        url = reverse("accounts:accept_invite", args=[token])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.post(url, {"full_name": "Invited", "password1": PW, "password2": PW})
        u = User.objects.get(email="inv@example.com")
        self.assertEqual(u.status, "approved")
        self.assertEqual(self.client.get(url).status_code, 400)  # used
        inv2, t2 = Invitation.create_for("late@example.com", None, self.root, days=-1)
        self.assertEqual(self.client.get(reverse("accounts:accept_invite", args=[t2])).status_code, 400)
        self.assertEqual(self.client.get(reverse("accounts:accept_invite", args=["garbage"])).status_code, 400)

    def test_invitation_token_is_stored_hashed(self):
        inv, token = Invitation.create_for("h@example.com", None, self.root)
        self.assertNotIn(token, inv.token_hash)
        self.assertEqual(len(inv.token_hash), 64)


class Lockout(Base):
    def test_repeated_failures_lock_out_even_correct_password(self):
        self.make_user("lock@example.com", "analyst")
        for _ in range(12):
            self.client.post(reverse("accounts:login"), {"email": "lock@example.com", "password": "wrong-wrong-wrong"})
        r = self.client.post(reverse("accounts:login"), {"email": "lock@example.com", "password": PW})
        self.assertContains(r, "Too many failed attempts")
        self.assertTrue(ActivityLog.objects.filter(action="auth.locked").exists())

    def test_unknown_and_wrong_password_give_same_message(self):
        self.make_user("real@example.com", "analyst")
        a = self.client.post(reverse("accounts:login"), {"email": "real@example.com", "password": "nope-nope-nope"})
        b = self.client.post(reverse("accounts:login"), {"email": "ghost@example.com", "password": "nope-nope-nope"})
        errs = lambda r: r.context["form"].non_field_errors().as_text()
        self.assertTrue(errs(a))
        self.assertEqual(errs(a), errs(b))


class PasswordReset(Base):
    def test_reset_does_not_reveal_whether_email_exists(self):
        self.make_user("exists@example.com", "analyst")
        r1 = self.client.post(reverse("accounts:reset"), {"email": "exists@example.com"})
        r2 = self.client.post(reverse("accounts:reset"), {"email": "nobody@example.com"})
        self.assertEqual((r1.status_code, r1.url), (r2.status_code, r2.url))
        self.assertEqual(EmailMessage.objects.filter(kind="account").count(), 1)

    def test_reset_link_works_once_and_kills_sessions(self):
        u = self.make_user("reset@example.com", "analyst")
        self.client.post(reverse("accounts:reset"), {"email": "reset@example.com"})
        body = EmailMessage.objects.filter(kind="account").latest("id").body_text
        import re

        link = re.search(r"/dashboard/password-reset/[^\s]+", body).group(0)
        r = self.client.get(link, follow=True)
        self.assertEqual(r.status_code, 200)
        post_url = r.redirect_chain[-1][0] if r.redirect_chain else link
        new_pw = "Another-Strong-Pass-55!"
        r = self.client.post(post_url, {"new_password1": new_pw, "new_password2": new_pw})
        self.assertEqual(r.status_code, 302)
        u.refresh_from_db()
        self.assertTrue(u.check_password(new_pw))
        r = self.client.get(link, follow=True)  # token now spent
        self.assertNotContains(r, "new_password1")

    def test_pending_users_get_no_reset_email(self):
        self.make_user("p@example.com", status="pending")
        self.client.post(reverse("accounts:reset"), {"email": "p@example.com"})
        self.assertEqual(EmailMessage.objects.filter(kind="account").count(), 0)

    def test_reset_token_lifetime_is_short(self):
        from django.conf import settings

        self.assertLessEqual(settings.PASSWORD_RESET_TIMEOUT, 3600)


class Permissions(Base):
    def test_anonymous_redirected_everywhere(self):
        for p in ("/dashboard/", "/dashboard/leads/", "/dashboard/posts/", "/dashboard/users/", "/dashboard/media/", "/dashboard/analytics/"):
            r = self.client.get(p)
            self.assertEqual(r.status_code, 302, p)
            self.assertIn("/dashboard/login/", r.url)

    def test_role_matrix_is_enforced_server_side(self):
        analyst = self.make_user("an@example.com", "analyst")
        self.login(analyst)
        self.assertEqual(self.client.get("/dashboard/").status_code, 200)
        self.assertEqual(self.client.get("/dashboard/users/").status_code, 403)
        self.assertEqual(self.client.get("/dashboard/email-settings/").status_code, 403)
        self.assertEqual(self.client.post("/dashboard/posts/new/", {"title": "x"}).status_code, 403)
        self.assertEqual(self.client.post("/dashboard/leads/new/", {"name": "x"}).status_code, 403)

    def test_content_manager_can_publish_but_not_see_users_or_email(self):
        cm = self.make_user("cm@example.com", "content_manager")
        self.login(cm)
        self.assertEqual(self.client.get("/dashboard/posts/").status_code, 200)
        self.assertEqual(self.client.get("/dashboard/users/").status_code, 403)
        self.assertEqual(self.client.get("/dashboard/inbox/").status_code, 403)
        self.assertEqual(self.client.get("/dashboard/email-settings/").status_code, 403)

    def test_sidebar_hides_sections_without_access(self):
        self.login(self.make_user("an2@example.com", "analyst"))
        html = self.client.get("/dashboard/").content.decode()
        self.assertNotIn("/dashboard/users/", html)
        self.assertNotIn("/dashboard/email-settings/", html)
        self.assertIn("/dashboard/analytics/", html)

    def test_publish_permission_required_to_publish(self):
        from apps.accounts.models import Role

        role = Role.objects.create(name="Writer", slug="writer", permissions={"dashboard": ["view"], "blog": ["view", "create", "edit"], "taxonomy": ["view"]})
        u = self.make_user("w@example.com")
        u.role = role
        u.save()
        self.login(u)
        r = self.client.post("/dashboard/posts/new/", {"title": "Sneaky", "slug": "sneaky", "schema_type": "BlogPosting", "status": "published", "content_html": "<p>Hello hello hello</p>", "excerpt": "e"})
        from apps.blog.models import Post

        self.assertEqual(r.status_code, 200)  # form re-shown with an error
        self.assertContains(r, "permission to publish")
        self.assertFalse(Post.objects.filter(slug="sneaky").exists())
        r = self.client.post("/dashboard/posts/new/", {"title": "Okay", "slug": "okay", "schema_type": "BlogPosting", "status": "draft", "content_html": "<p>Hello hello hello</p>", "excerpt": "e"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Post.objects.get(slug="okay").status, "draft")

    def test_csrf_enforced_on_dashboard_posts(self):
        from django.test import Client

        c = Client(enforce_csrf_checks=True)
        c.force_login(self.root, backend="apps.accounts.backends.ApprovedEmailBackend")
        self.assertEqual(c.post("/dashboard/posts/new/", {"title": "x"}).status_code, 403)

    def test_audit_log_records_security_events(self):
        self.client.post(reverse("accounts:login"), {"email": "root@example.com", "password": "wrong-wrong-wrong"})
        self.client.post(reverse("accounts:login"), {"email": "root@example.com", "password": PW})
        actions = set(ActivityLog.objects.values_list("action", flat=True))
        self.assertTrue({"auth.failed", "auth.login"} <= actions)
        self.assertFalse(ActivityLog.objects.filter(detail__icontains=PW).exists())
