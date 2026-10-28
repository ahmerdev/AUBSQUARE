"""Outbound sales core: safe fetching (SSRF), website audit, prospects, do-not-contact, conversion, speed-to-lead."""
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest import mock

from django.core import mail
from django.core.exceptions import ValidationError
from django.test import override_settings
from django.utils import timezone

from apps.leads.models import Lead
from apps.outbound import audit, discovery, netguard, services
from apps.outbound.models import OutboundSettings, Prospect, SiteAudit, SuppressionEntry

from .base import Base

HOME = b"""<!doctype html><html><head><title>Bella Dental</title><meta name="viewport" content="width=device-width">
<meta name="description" content="Family dentist"></head><body><h1>Bella Dental Clinic</h1>
<a href="/about">About</a><a href="/missing-page">Old offer</a><a href="mailto:hello@bella.test">Mail</a>
<img src="a.png"><img src="b.png" alt="team"><p>Call us today</p></body></html>"""


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            code, body = 200, HOME
        elif self.path == "/about":
            code, body = 200, b"<html><body>about</body></html>"
        elif self.path == "/redir":
            self.send_response(302)
            self.send_header("Location", "http://169.254.169.254/latest/meta-data/")
            self.end_headers()
            return
        else:
            code, body = 404, b"nope"
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


class LocalSite:
    """A real HTTP server on localhost; the SSRF guard is relaxed only inside this context for these tests."""

    def __enter__(self):
        self.srv = HTTPServer(("127.0.0.1", 0), _Handler)
        self.port = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.patches = [mock.patch.object(netguard, "_is_public", lambda ip: True), mock.patch.object(netguard, "ALLOWED_PORTS", {self.port})]
        for p in self.patches:
            p.start()
        return f"http://127.0.0.1:{self.port}/"

    def __exit__(self, *a):
        for p in self.patches:
            p.stop()
        self.srv.shutdown()


class NetGuardTests(Base):
    def test_blocks_private_loopback_and_metadata_addresses(self):
        for url in ("http://127.0.0.1/", "http://localhost/", "http://10.0.0.5/", "http://192.168.1.1/", "http://169.254.169.254/latest/meta-data/",
                    "http://[::1]/", "http://[::ffff:127.0.0.1]/", "http://0.0.0.0/", "http://100.64.0.1/", "http://printer.local/", "http://intranet/"):
            with self.assertRaises(netguard.UnsafeURL, msg=url):
                netguard.validate_url(url)

    def test_blocks_odd_schemes_ports_and_credentials(self):
        for url in ("file:///etc/passwd", "ftp://example.com/", "gopher://example.com/", "http://example.com:22/", "http://example.com:8080/", "https://user:pw@example.com/"):
            with self.assertRaises(netguard.UnsafeURL, msg=url):
                netguard.validate_url(url)

    def test_hostname_resolving_to_a_private_ip_is_blocked(self):
        with mock.patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("10.1.2.3", 80))]):
            with self.assertRaises(netguard.UnsafeURL):
                netguard.validate_url("http://innocent-looking.example.com/")
        with mock.patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("93.184.216.34", 80)), (2, 1, 6, "", ("127.0.0.1", 80))]):
            with self.assertRaises(netguard.UnsafeURL):  # a single private answer among public ones is enough to refuse
                netguard.validate_url("http://mixed.example.com/")

    def test_public_address_is_allowed(self):
        with mock.patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("93.184.216.34", 443))]):
            scheme, host, port, target, ips = netguard.validate_url("https://example.com/a?b=1")
        self.assertEqual((scheme, host, port, target, ips), ("https", "example.com", 443, "/a?b=1", ["93.184.216.34"]))

    def test_normalize_url(self):
        self.assertEqual(netguard.normalize_url("Example.com/Menu"), "https://example.com/Menu")
        self.assertEqual(netguard.normalize_url("  http://a.com  "), "http://a.com/")
        for bad in ("", "nodots", "javascript:alert(1)", "ftp://a.com"):
            self.assertEqual(netguard.normalize_url(bad), "", bad)

    def test_real_fetch_and_redirect_to_metadata_is_refused(self):
        with LocalSite() as base:
            r = netguard.fetch(base)
            self.assertEqual(r.status, 200)
            self.assertIn(b"Bella Dental", r.body)
        with LocalSite() as base:
            with mock.patch.object(netguard, "_is_public", lambda ip: ip == "127.0.0.1"):
                with self.assertRaises(netguard.UnsafeURL):
                    netguard.fetch(base + "redir")  # 302 → 169.254.169.254 must be re-validated and refused


class AuditTests(Base):
    def test_audit_reads_real_facts_and_scores_them(self):
        with LocalSite() as base:
            a = audit.run_audit(base, "prospect", category="dental")
        self.assertTrue(a.reachable)
        self.assertEqual((a.title, a.h1, a.has_viewport), ("Bella Dental", "Bella Dental Clinic", True))
        self.assertEqual(a.images_total, 2)
        self.assertEqual(a.images_missing_alt, 1)
        self.assertEqual(a.emails_found, ["hello@bella.test"])
        self.assertEqual([b["url"].endswith("/missing-page") for b in a.broken_links], [True])  # genuinely requested, genuinely 404
        keys = {f["key"] for f in a.findings}
        self.assertIn("no_whatsapp", keys)
        self.assertIn("no_booking", keys)       # dental → booking matters
        self.assertNotIn("no_ordering", keys)   # …but online ordering is irrelevant for a dentist
        self.assertIn("no_ssl", keys)           # served over plain http
        self.assertEqual(a.score, sum(f["points"] for f in a.findings))

    def test_weak_seo_not_flagged_when_title_description_h1_exist(self):
        with LocalSite() as base:
            a = audit.run_audit(base, "prospect", category="dental")
        self.assertNotIn("weak_seo", {f["key"] for f in a.findings})

    def test_unreachable_site_is_recorded_honestly_with_no_score(self):
        a = audit.run_audit("http://127.0.0.1/", "prospect")
        self.assertFalse(a.reachable)
        self.assertEqual((a.score, a.level, a.findings), (0, "unknown", []))
        self.assertTrue(a.error)

    def test_invalid_address(self):
        a = audit.run_audit("not a url", "free")
        self.assertFalse(a.reachable)
        self.assertEqual(SiteAudit.objects.count(), 1)

    def test_score_weights_are_editable_and_capped(self):
        cfg = OutboundSettings.load()
        cfg.score_weights = {"no_whatsapp": 0, "no_ssl": 99, "weak_seo": "x"}
        cfg.save()
        self.assertEqual((cfg.weight("no_whatsapp"), cfg.weight("no_ssl"), cfg.weight("weak_seo")), (0, 50, 15))

    def test_email_cleaning_drops_junk(self):
        self.assertEqual(audit.clean_emails(["a@sentry.io", "logo@2x.png", "Info@Bella.test", "noreply@bella.test", "info@bella.test"], "bella.test"), ["info@bella.test"])


class ServicesTests(Base):
    def test_create_prospect_validates_and_dedupes(self):
        p, why = services.create_prospect({"business_name": "Bella Dental", "website": "bella.test", "email": "Hello@Bella.test", "category": "dental", "country": "Pakistan"}, "manual", self.root)
        self.assertEqual((why, p.domain, p.email), ("", "bella.test", "hello@bella.test"))
        dup, why = services.create_prospect({"business_name": "Other name", "website": "https://www.bella.test/contact"}, "csv")
        self.assertEqual((dup.pk, why), (p.pk, "duplicate"))
        self.assertEqual(Prospect.objects.count(), 1)
        self.assertIsNone(services.create_prospect({"business_name": "x"}, "csv")[0])
        self.assertIsNone(services.create_prospect({"business_name": "No contact"}, "csv")[0])

    def test_do_not_contact_blocks_email_and_domain(self):
        services.suppress(email="no@bella.test", reason="unsubscribed")
        services.suppress(domain="blocked.test", reason="manual")
        self.assertTrue(services.is_suppressed("no@bella.test"))
        self.assertTrue(services.is_suppressed("anyone@blocked.test"))
        self.assertTrue(services.is_suppressed("", "https://www.blocked.test/x"))
        self.assertFalse(services.is_suppressed("ok@bella.test"))
        p, _ = services.create_prospect({"business_name": "Blocked Co", "website": "blocked.test"}, "manual")
        self.assertEqual(p.status, Prospect.SUPPRESSED)

    def test_marketing_unsubscribers_are_respected(self):
        from apps.marketing.models import Subscriber

        Subscriber.objects.create(email="gone@x.test", status="unsubscribed")
        self.assertTrue(services.is_suppressed("gone@x.test"))

    def test_email_block_needs_address_region_and_postal_address(self):
        cfg = OutboundSettings.load()
        p, _ = services.create_prospect({"business_name": "A Co", "email": "a@a.test", "country": "Pakistan"}, "manual")
        self.assertIn("postal address", services.email_block(p, cfg))
        cfg.postal_address = "1 Main Street, Lahore"
        cfg.save()
        self.assertEqual(services.email_block(p, cfg), "")
        p.country = "Germany"
        self.assertIn("not enabled", services.email_block(p, cfg))
        p.country = ""
        self.assertIn("Country is unknown", services.email_block(p, cfg))
        p.country = "Pakistan"
        cfg.region_mode = "manual_only"
        self.assertIn("turned off", services.email_block(p, cfg))

    def test_csv_import_maps_columns_and_enforces_limits(self):
        rows = services.parse_csv(b"Business Name,Website,Industry,City\nBella Dental,bella.test,Dental,Lahore\n,,,\n")
        self.assertEqual(rows[0]["category"], "dental")
        with self.assertRaises(ValidationError):
            services.parse_csv(b"foo,bar\n1,2\n")
        res = services.import_candidates(rows, "csv", self.root)
        self.assertEqual((res["added"], res["skipped"]), (1, 1))

    def test_conversion_creates_one_lead_and_is_idempotent(self):
        p, _ = services.create_prospect({"business_name": "Bella Dental", "email": "hello@bella.test", "category": "dental"}, "manual")
        lead, created = services.convert_to_lead(p, self.root)
        self.assertTrue(created)
        self.assertEqual((lead.source, lead.email), ("outbound", "hello@bella.test"))
        p.refresh_from_db()
        self.assertEqual((p.status, p.lead_id), (Prospect.CONVERTED, lead.pk))
        lead2, created2 = services.convert_to_lead(p, self.root)
        self.assertEqual((lead2.pk, created2), (lead.pk, False))
        self.assertEqual(Lead.objects.count(), 1)
        nomail, _ = services.create_prospect({"business_name": "No Mail", "phone": "+92 300 1234567"}, "manual")
        with self.assertRaises(ValidationError):
            services.convert_to_lead(nomail)

    def test_lead_category_groups_enquiries(self):
        self.assertEqual(services.lead_category("Logo & brand identity"), "design")
        self.assertEqual(services.lead_category("E-commerce website on Shopify"), "website")
        self.assertEqual(services.lead_category("Google Ads campaign"), "marketing")
        self.assertEqual(services.lead_category("SEO audit"), "seo")
        self.assertEqual(services.lead_category("hello"), "other")


class SpeedToLeadTests(Base):
    def setUp(self):
        super().setUp()
        self.mgr = self.make_user("sales@example.com", "sales_manager")

    def _lead(self, **kw):
        d = dict(name="Ayesha Khan", email="ayesha@client.test", service_label="Logo & brand identity", message="I need a new logo and brand", consent_given=True)
        d.update(kw)
        return Lead.objects.create(**d)

    def test_new_lead_is_categorised_and_team_alerted_and_visitor_confirmation_is_on_by_default(self):
        lead = self._lead()
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            services.speed_to_lead(lead)
        lead.refresh_from_db()
        self.assertEqual(lead.category, "design")
        self.assertTrue(self.mgr.notifications.filter(title__startswith="Reply fast").exists())
        self.assertTrue([m for m in mail.outbox if m.to == ["ayesha@client.test"]])

    def test_confirmation_can_be_switched_off(self):
        cfg = OutboundSettings.load()
        cfg.auto_reply_enabled = False
        cfg.save()
        lead = self._lead()
        mail.outbox.clear()
        services.speed_to_lead(lead)
        self.assertFalse([m for m in mail.outbox if m.to == ["ayesha@client.test"]])

    def test_autoreply_only_when_enabled_and_logs_an_outbound_record(self):
        cfg = OutboundSettings.load()
        cfg.auto_reply_enabled = True
        cfg.save()
        lead = self._lead()
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            services.speed_to_lead(lead)
        sent = [m for m in mail.outbox if m.to == ["ayesha@client.test"]]
        self.assertEqual(len(sent), 1)
        self.assertIn(lead.reference, sent[0].subject)
        self.assertIn("Ayesha", sent[0].body)

    def test_autoreply_skipped_for_suppressed_address(self):
        cfg = OutboundSettings.load()
        cfg.auto_reply_enabled = True
        cfg.save()
        services.suppress(email="ayesha@client.test", reason="unsubscribed")
        lead = self._lead()
        mail.outbox.clear()
        services.speed_to_lead(lead)
        self.assertFalse([m for m in mail.outbox if m.to == ["ayesha@client.test"]])

    def test_slow_lead_alert_fires_once_and_first_response_is_tracked(self):
        lead = self._lead()
        Lead.objects.filter(pk=lead.pk).update(created_at=timezone.now() - timezone.timedelta(minutes=40))
        r1 = services.check_overdue()
        r2 = services.check_overdue()
        self.assertEqual((r1["slow_leads"], r2["slow_leads"]), (1, 0))
        lead.refresh_from_db()
        self.assertIsNone(lead.response_minutes)
        services.mark_first_response(lead)
        lead.refresh_from_db()
        self.assertGreaterEqual(lead.response_minutes, 39)

    def test_public_form_submission_triggers_speed_to_lead(self):
        import json

        from apps.cms.models import Service

        from .base import old_token

        Service.objects.create(title="Web Design", status="published", short_description="x")
        r = self.client.post("/api/v1/leads/", json.dumps({"name": "Sara Ali", "email": "sara@client.test", "phone": "3001234567", "countryCode": "+92", "service": "Web Design", "budget": "$1,500 - $3,000",
                                                          "message": "Please build a new website for my clinic", "formToken": old_token(), "source": "contact_form"}), content_type="application/json")
        self.assertIn(r.status_code, (200, 201), r.content)
        lead = Lead.objects.get(email="sara@client.test")
        self.assertEqual(lead.category, "website")
        self.assertTrue(self.mgr.notifications.filter(title__startswith="Reply fast").exists())
