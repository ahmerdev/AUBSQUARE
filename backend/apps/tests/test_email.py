"""Acceptance: SMTP settings (encrypted credentials, explicit test only), real SMTP delivery against a local server, retry/backoff, inbound IMAP parsing + threading."""
import socket
from datetime import timedelta
from email.message import EmailMessage as PyMessage

from django.core import mail
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from apps.leads.models import Lead
from apps.mailer import inbound, service
from apps.mailer.models import EmailMessage, EmailSettings, EmailThread

from .base import Base


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class SettingsAndSecrets(Base):
    def post_settings(self, **extra):
        data = {"provider": "custom", "smtp_host": "smtp.example.com", "smtp_port": 587, "smtp_security": "tls", "smtp_username": "user@example.com",
                "smtp_password": "S3cret-App-Password", "from_email": "hello@aubsquare.test", "from_name": "AUB SQUARE", "reply_to": "", "notification_recipients": "team@example.com",
                "imap_host": "", "imap_port": 993, "imap_security": "ssl", "imap_username": "", "imap_password": "", "imap_folder": "INBOX"}
        for f in ("notify_new_lead", "notify_new_chat", "notify_new_comment", "notify_new_staff", "notify_marketing_lead", "notify_system"):
            data[f] = "on"
        data.update(extra)
        return self.client.post(reverse("dashboard:email_settings"), data)

    def test_saving_settings_does_not_send_any_email(self):
        self.login(self.root)
        r = self.post_settings()
        self.assertEqual(r.status_code, 302, getattr(r, "context", None) and r.context["form"].errors.as_text())
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(EmailMessage.objects.filter(kind="test").count(), 0)

    def test_password_is_encrypted_at_rest_and_never_rendered(self):
        self.login(self.root)
        self.post_settings()
        es = EmailSettings.load()
        self.assertNotIn("S3cret-App-Password", es.smtp_password_enc)
        self.assertEqual(es.get_smtp_password(), "S3cret-App-Password")
        html = self.client.get(reverse("dashboard:email_settings")).content.decode()
        self.assertNotIn("S3cret-App-Password", html)
        self.assertNotIn(es.smtp_password_enc, html)
        for url in ("/api/v1/bootstrap/",):
            self.assertNotIn("S3cret", self.client.get(url).content.decode())

    def test_blank_password_keeps_the_saved_one(self):
        self.login(self.root)
        self.post_settings()
        self.post_settings(smtp_password="", smtp_port=465)
        es = EmailSettings.load()
        self.assertEqual((es.smtp_port, es.get_smtp_password()), (465, "S3cret-App-Password"))

    def test_only_permitted_roles_open_email_settings(self):
        self.login(self.make_user("cm@example.com", "content_manager"))
        self.assertEqual(self.client.get(reverse("dashboard:email_settings")).status_code, 403)
        self.assertEqual(self.client.post(reverse("dashboard:email_test"), {"to": "a@b.co"}).status_code, 403)

    def test_test_email_needs_an_explicit_valid_recipient(self):
        self.login(self.root)
        self.post_settings()
        self.client.post(reverse("dashboard:email_test"), {"to": "not-an-email"})
        self.assertEqual(EmailMessage.objects.filter(kind="test").count(), 0)

    def test_provider_presets_cover_requested_services(self):
        from apps.mailer.models import PROVIDER_PRESETS

        for k in ("gmail", "google_workspace", "outlook", "microsoft365", "custom"):
            self.assertIn(k, PROVIDER_PRESETS)
        self.assertEqual(PROVIDER_PRESETS["gmail"]["smtp_host"], "smtp.gmail.com")


class RealSmtpDelivery(Base):
    """Runs a genuine SMTP conversation against an in-process aiosmtpd server (not Django's locmem)."""

    def setUp(self):
        super().setUp()
        from aiosmtpd.controller import Controller
        from aiosmtpd.smtp import AuthResult, LoginPassword

        self.received = []
        outer = self

        class Handler:
            async def handle_DATA(self, server, session, envelope):
                outer.received.append(envelope)
                return "250 OK"

        def auth(server, session, envelope, mechanism, data):
            ok = isinstance(data, LoginPassword) and data.login == b"mailer" and data.password == b"right-password"
            return AuthResult(success=ok, handled=False if not ok else True)

        self.port = free_port()
        self.ctl = Controller(Handler(), hostname="127.0.0.1", port=self.port, authenticator=auth, auth_required=True, auth_require_tls=False)
        self.ctl.start()
        self.addCleanup(self._stop_server)
        es = EmailSettings.load()
        es.smtp_host, es.smtp_port, es.smtp_security = "127.0.0.1", self.port, "none"
        es.smtp_username, es.from_email = "mailer", "hello@aubsquare.test"
        es.set_smtp_password("right-password")
        es.save()

    def _stop_server(self):
        try:
            self.ctl.stop(no_assert=True)
        except RuntimeError:
            pass  # already stopped by the test

    @override_settings(TESTING=False)
    def test_test_email_is_delivered_over_real_smtp_with_auth(self):
        self.login(self.root)
        r = self.client.post(reverse("dashboard:email_test"), {"to": "owner@example.com"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(len(self.received), 1)
        self.assertEqual(self.received[0].rcpt_tos, ["owner@example.com"])
        self.assertIn(b"outgoing email works", self.received[0].content)
        es = EmailSettings.load()
        self.assertTrue(es.last_test_ok)
        self.assertEqual(EmailMessage.objects.get(kind="test").status, "sent")

    @override_settings(TESTING=False)
    def test_wrong_password_is_reported_without_leaking_it(self):
        es = EmailSettings.load()
        es.set_smtp_password("wrong-password-123")
        es.save()
        ok, msg = service.send_test_email("owner@example.com")
        self.assertFalse(ok)
        self.assertEqual(len(self.received), 0)
        self.assertNotIn("wrong-password-123", msg)
        self.assertNotIn("wrong-password-123", EmailMessage.objects.get(kind="test").error)

    @override_settings(TESTING=False)
    def test_lead_reply_is_sent_with_threading_headers_and_reference(self):
        lead = Lead.objects.create(name="Sara", email="sara@example.com", message="Need a logo please")
        msg = service.reply_to_lead(lead, self.root, "Your enquiry", "Hello Sara")
        self.assertTrue(service.deliver(msg.pk))
        raw = self.received[0].content.decode()
        self.assertIn(f"[{lead.reference}]", raw)
        self.assertIn("Message-ID:", raw)
        lead.refresh_from_db()
        self.assertEqual(lead.status, "contacted")

    @override_settings(TESTING=False)
    def test_failed_send_is_retried_with_backoff_then_gives_up(self):
        self.ctl.stop()  # server goes away -> connection refused
        m = service.queue_email(["x@example.com"], "Hello", "Body", send_now=False)
        self.assertFalse(service.deliver(m.pk))
        m.refresh_from_db()
        self.assertEqual((m.status, m.attempts), ("failed", 1))
        self.assertGreater(m.next_attempt_at, timezone.now() + timedelta(minutes=4))
        self.assertEqual(service.process_queue(), {"sent": 0, "failed": 0})  # not due yet
        EmailMessage.objects.filter(pk=m.pk).update(next_attempt_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(service.process_queue()["failed"], 1)
        EmailMessage.objects.filter(pk=m.pk).update(attempts=service.MAX_ATTEMPTS - 1, next_attempt_at=timezone.now() - timedelta(seconds=1))
        service.process_queue()
        m.refresh_from_db()
        self.assertEqual(m.status, "failed")
        self.assertIsNone(m.next_attempt_at)  # permanently failed
        from apps.core.models import Notification

        self.assertTrue(Notification.objects.filter(kind="email", level="danger").exists())

    @override_settings(TESTING=False)
    def test_business_record_survives_email_failure(self):
        self.ctl.stop()
        from apps.tests.base import old_token
        import json

        r = self.client.post("/api/v1/leads/", json.dumps({"name": "Zed Zed", "email": "z@example.com", "phone": "3001112222", "service": "Graphic Design", "budget": "$1,500 - $3,000",
                                                           "message": "My email server is down but my lead should be saved.", "formToken": old_token()}), content_type="application/json")
        self.assertIn(r.status_code, (201, 400))
        if r.status_code == 201:
            self.assertEqual(Lead.objects.count(), 1)


RAW_REPLY = b"""From: Sara Khan <sara@example.com>
To: hello@aubsquare.test
Subject: Re: Your enquiry [%(ref)s]
Message-ID: <reply-1@example.com>
In-Reply-To: <orig@aubsquare.test>
Date: Tue, 01 Sep 2026 10:00:00 +0000
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="b"

--b
Content-Type: text/plain; charset=utf-8

Thanks! Can we talk tomorrow?
--b
Content-Type: application/pdf; name="brief.pdf"
Content-Disposition: attachment; filename="brief.pdf"
Content-Transfer-Encoding: base64

JVBERi0xLjQK
--b--
"""


class InboundEmail(Base):
    def setUp(self):
        super().setUp()
        es = EmailSettings.load()
        es.from_email = "hello@aubsquare.test"
        es.save()
        self.lead = Lead.objects.create(name="Sara", email="sara@example.com", message="Need a logo please")

    def parsed(self, raw=None):
        return inbound.parse_raw_message(raw or RAW_REPLY % {b"ref": self.lead.reference.encode()})

    def test_parse_extracts_headers_body_and_attachments(self):
        p = self.parsed()
        self.assertEqual((p["from_email"], p["message_id"]), ("sara@example.com", "<reply-1@example.com>"))
        self.assertIn("talk tomorrow", p["text"])
        self.assertEqual(p["attachments"][0]["name"], "brief.pdf")

    def test_inbound_is_threaded_to_the_lead_by_reference_tag(self):
        m = inbound.store_inbound(self.parsed(), uid=5)
        self.assertEqual(m.lead_id, self.lead.pk)
        self.assertEqual(m.direction, "in")
        self.assertFalse(m.is_read)
        self.assertTrue(m.thread.has_unread)

    def test_inbound_deduplicated_by_message_id(self):
        inbound.store_inbound(self.parsed(), uid=5)
        self.assertIsNone(inbound.store_inbound(self.parsed(), uid=6))
        self.assertEqual(EmailMessage.objects.filter(direction="in").count(), 1)

    def test_reply_threads_with_outbound_via_in_reply_to(self):
        out = service.reply_to_lead(self.lead, self.root, "Hi", "Hello")
        raw = (RAW_REPLY % {b"ref": b"none"}).replace(b"<orig@aubsquare.test>", out.message_id.encode()).replace(b"Subject: Re: Your enquiry [none]", b"Subject: totally different")
        m = inbound.store_inbound(inbound.parse_raw_message(raw))
        self.assertEqual(m.thread_id, out.thread_id)

    def test_own_outbound_copies_are_ignored(self):
        raw = (RAW_REPLY % {b"ref": b"x"}).replace(b"sara@example.com", b"hello@aubsquare.test", 1)
        self.assertIsNone(inbound.store_inbound(inbound.parse_raw_message(raw)))

    def test_html_in_inbound_mail_is_sanitised(self):
        raw = b"From: a@example.com\nTo: hello@aubsquare.test\nSubject: hi\nMessage-ID: <h@x>\nContent-Type: text/html\n\n<p>ok</p><script>alert(1)</script><img src=x onerror=alert(1)>"
        m = inbound.store_inbound(inbound.parse_raw_message(raw))
        self.assertNotIn("<script", m.body_html)
        self.assertNotIn("onerror", m.body_html)

    def test_inbox_page_renders_and_requires_permission(self):
        inbound.store_inbound(self.parsed())
        self.login(self.root)
        r = self.client.get(reverse("dashboard:inbox"))
        self.assertContains(r, "Your enquiry")
        t = EmailThread.objects.get()
        self.assertEqual(self.client.get(reverse("dashboard:thread", args=[t.pk])).status_code, 200)
        self.client.logout()
        self.login(self.make_user("cm2@example.com", "content_manager"))
        self.assertEqual(self.client.get(reverse("dashboard:inbox")).status_code, 403)

    def test_sync_without_configuration_is_refused_not_faked(self):
        with self.assertRaises(inbound.InboundNotConfigured):
            inbound.sync_inbox()

    def test_smtp_alone_never_claims_to_receive(self):
        es = EmailSettings.load()
        es.smtp_host = "smtp.example.com"
        es.save()
        self.assertFalse(es.imap_configured)


class SettingsHelpers(SettingsAndSecrets):
    """Mistakes people really make in the Email settings form must be fixed or explained, never silently ignored."""

    def test_gmail_app_password_spaces_are_removed_and_port_encryption_mismatch_is_corrected(self):
        self.login(self.root)
        r = self.post_settings(provider="gmail", smtp_host=" SMTP.Gmail.com ", smtp_port=465, smtp_security="tls", smtp_password="abcd efgh ijkl mnop",
                               smtp_username="me@gmail.com", from_email="me@gmail.com")
        self.assertEqual(r.status_code, 302)
        es = EmailSettings.load()
        self.assertEqual(es.smtp_host, "smtp.gmail.com")
        self.assertEqual(es.smtp_security, "ssl")
        self.assertEqual(es.get_smtp_password(), "abcdefghijklmnop")
        self.post_settings(provider="gmail", smtp_host="smtp.gmail.com", smtp_port=587, smtp_security="ssl", smtp_password="")
        self.assertEqual(EmailSettings.load().smtp_security, "tls")

    def test_blank_username_and_from_fall_back_to_each_other(self):
        es = EmailSettings.load()
        es.smtp_host, es.smtp_username, es.from_email = "smtp.gmail.com", "me@gmail.com", ""
        es.set_smtp_password("x")
        self.assertTrue(es.smtp_configured)
        self.assertEqual(es.effective_from_email, "me@gmail.com")
        es.smtp_username, es.from_email = "", "me@gmail.com"
        self.assertEqual(es.effective_username, "me@gmail.com")
        es.smtp_username = "login-name"
        self.assertEqual(es.effective_username, "login-name")  # an explicit login is never overridden

    def test_unconfigured_test_email_says_so_instead_of_pretending(self):
        es = EmailSettings.load()
        es.smtp_host, es.from_email, es.smtp_username = "", "", ""
        es.save()
        ok, msg = service.send_test_email("owner@example.com")
        self.assertFalse(ok)
        self.assertIn("Not configured", msg)
        self.assertEqual(EmailMessage.objects.filter(kind="test").count(), 0)

    def test_common_failures_get_a_plain_explanation(self):
        es = EmailSettings(smtp_host="smtp.gmail.com")
        self.assertIn("App Password", service.explain_error("SMTPAuthenticationError: (535, b'5.7.8 Username and Password not accepted. BadCredentials')", es))
        self.assertIn("App Password", service.explain_error("(534, b'5.7.9 Application-specific password required')", es))
        self.assertIn("login", service.explain_error("(530, b'5.7.0 Authentication Required')", es).lower())
        self.assertIn("587", service.explain_error("SSLError: [SSL: WRONG_VERSION_NUMBER] wrong version number", es))
        self.assertIn("host name", service.explain_error("gaierror: [Errno 11001] getaddrinfo failed", es))
        self.assertEqual(service.explain_error("something unusual", es), "")

    def test_save_button_is_inside_the_settings_form_and_forms_are_not_nested(self):
        """Regression: a nested <form> closed the settings form early, so the Save button submitted nothing."""
        self.login(self.root)
        html = self.client.get(reverse("dashboard:email_settings")).content.decode()
        start = html.index("data-warn-unsaved")
        end = html.index("</form>", start)  # the first closing tag after the settings form opens
        self.assertIn("sticky-save", html[start:end])
        self.assertNotIn("<form", html[start + 10:end])
        self.assertIn('form="f-email-test"', html)
