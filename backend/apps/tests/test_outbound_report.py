"""Prospect audit report page, links attached to outreach emails, health score, and the country/city picker data."""
import json
from pathlib import Path

from django.conf import settings as dj
from django.urls import reverse

from apps.core.models import Notification
from apps.outbound import outreach, pitch, services
from apps.outbound.models import OutboundSettings, Prospect, ProspectNote

from .base import Base
from .test_outbound_core import LocalSite
from .test_outbound_ui import make_prospect, ready

BROWSER = {"HTTP_USER_AGENT": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0 Safari/537.36"}


def audited(**kw):
    with LocalSite() as base:
        p = make_prospect(website=base, **kw)
        services.audit_prospect(p)
    p.refresh_from_db()
    return p


class ReportPage(Base):
    def setUp(self):
        super().setUp()
        ready()

    def test_404_until_the_website_was_really_audited(self):
        p = make_prospect()
        self.assertEqual(self.client.get(f"/r/{p.token}/", **BROWSER).status_code, 404)
        self.assertEqual(self.client.get("/r/not-a-token/", **BROWSER).status_code, 404)

    def test_unreachable_site_gets_no_report_button_instead_of_a_broken_link(self):
        """Regression: 'Open report' was offered after a failed audit and led to a 404."""
        p = make_prospect(website="http://10.0.0.5/")
        services.audit_prospect(p)
        self.assertTrue(p.audits.exists())
        self.assertFalse(pitch.has_report(p))
        self.login(self.root)
        r = self.client.get(reverse("dashboard:prospect_detail", args=[p.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "No report page for this prospect")
        self.assertNotContains(r, reverse("dashboard:prospect_report", args=[p.pk]))

    def test_page_is_private_noindex_and_shows_only_real_findings(self):
        p = audited()
        r = self.client.get(f"/r/{p.token}/", **BROWSER)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["X-Robots-Tag"], "noindex, nofollow, noarchive")
        self.assertEqual(r["Referrer-Policy"], "same-origin")
        self.assertContains(r, "Website report for Bella Dental")
        self.assertContains(r, "What to fix first")
        self.assertContains(r, "No WhatsApp")
        self.assertNotContains(r, "opportunity", status_code=200)  # sales-side wording never reaches the prospect
        self.assertNotContains(r, "points")
        health = 100 - p.audits.first().score
        self.assertContains(r, f'aria-label="Website health score {health} out of 100"')

    def test_first_human_open_alerts_staff_bots_and_staff_do_not_count(self):
        p = audited()
        self.client.get(f"/r/{p.token}/", HTTP_USER_AGENT="Mozilla/5.0 (compatible; Googlebot/2.1)")
        self.client.get(f"/r/{p.token}/", HTTP_USER_AGENT="Mozilla/5.0 safelinks.protection.outlook.com")
        p.refresh_from_db()
        self.assertEqual(p.report_views, 0)
        self.client.get(f"/r/{p.token}/", **BROWSER)
        self.client.get(f"/r/{p.token}/", **BROWSER)
        p.refresh_from_db()
        self.assertEqual(p.report_views, 2)
        self.assertIsNotNone(p.report_first_opened_at)
        self.assertEqual(Notification.objects.filter(title__contains="opened their audit report").count(), 1)  # only the first open alerts
        self.assertEqual(ProspectNote.objects.filter(prospect=p, body="Opened their audit report.").count(), 1)

    def test_staff_preview_is_not_counted(self):
        p = audited()
        self.login(self.root)
        r = self.client.get(reverse("dashboard:prospect_report", args=[p.pk]), **BROWSER)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r["Location"], f"/r/{p.token}/?preview=1")
        self.assertContains(self.client.get(r["Location"], **BROWSER), "Views from here are not counted")
        p.refresh_from_db()
        self.assertEqual(p.report_views, 0)

    def test_report_shortcut_needs_permission(self):
        p = audited()
        self.login(self.make_user("sup2@example.com", "support_agent"))
        self.assertEqual(self.client.get(reverse("dashboard:prospect_report", args=[p.pk])).status_code, 403)

    def test_free_audit_api_returns_health_as_the_inverse_of_problem_points(self):
        with LocalSite() as base:
            d = self.client.post("/api/v1/audit/", json.dumps({"url": base}), content_type="application/json").json()
        self.assertEqual(d["health"], 100 - d["score"])


class LinksInEmails(Base):
    def setUp(self):
        super().setUp()
        self.cfg = ready()

    def test_email_includes_report_portfolio_site_postal_address_and_unsubscribe(self):
        p = audited()
        text = pitch.final_text(p, "Hello there", self.cfg)
        self.assertIn(f"{dj.SITE_URL}/r/{p.token}/", text)
        self.assertIn(f"{dj.SITE_URL}/portfolio", text)
        self.assertIn(f"Our website: {dj.SITE_URL}", text)
        self.assertIn("1 Main Street", text)
        self.assertIn(f"/o/{p.token}/", text)

    def test_each_link_can_be_switched_off(self):
        p = audited()
        self.cfg.include_report_link = self.cfg.include_portfolio_link = self.cfg.include_site_link = False
        self.cfg.save()
        text = pitch.final_text(p, "Hello", self.cfg)
        self.assertNotIn("/r/", text)
        self.assertNotIn("/portfolio", text)
        self.assertNotIn("Our website", text)
        self.assertIn(f"/o/{p.token}/", text)  # the unsubscribe line is never optional

    def test_no_report_link_when_there_is_nothing_to_show(self):
        p = make_prospect()
        self.assertNotIn("/r/", pitch.final_text(p, "Hello", self.cfg))

    def test_queued_email_carries_the_links_and_whatsapp_gets_the_report_link(self):
        from apps.mailer.models import EmailMessage

        p = audited()
        m = outreach.draft_message(p, 1, "email")
        outreach.approve(m, self.root)
        outreach.send_approved()
        body = EmailMessage.objects.get(kind="outbound").body_text
        self.assertIn(f"/r/{p.token}/", body)
        wa = outreach.draft_message(p, 1, "whatsapp")
        self.assertIn(f"/r/{p.token}/", wa.body)

    def test_outreach_screen_shows_exactly_what_will_be_sent(self):
        p = audited()
        outreach.draft_message(p, 1, "email", self.root)
        self.login(self.root)
        body = self.client.get(reverse("dashboard:outreach")).content.decode()
        self.assertIn("See exactly what the prospect will receive", body)
        self.assertIn(f"/r/{p.token}/", body)

    def test_settings_page_offers_the_attachment_switches(self):
        self.login(self.root)
        body = self.client.get(reverse("dashboard:outbound_settings")).content.decode()
        self.assertIn("What is attached to every email", body)
        self.assertIn("include_report_link", body)
        self.assertIn("data-geo-multi", body)


class GeoPicker(Base):
    def test_geo_file_is_valid_and_covers_the_main_markets(self):
        data = json.loads((Path(dj.BASE_DIR) / "static" / "dashboard" / "geo.json").read_text(encoding="utf-8"))["countries"]
        self.assertGreater(len(data), 200)
        by = {c["n"]: c for c in data}
        self.assertIn("Karachi", by["Pakistan"]["ci"])
        self.assertIn("Lahore", by["Pakistan"]["ci"])
        self.assertIn("Dubai", by["United Arab Emirates"]["ci"])
        self.assertIn("Riyadh", by["Saudi Arabia"]["ci"])
        for c in data:
            self.assertEqual(len(c["c"]), 2)
            self.assertTrue(c["n"])

    def test_prospect_screens_use_the_searchable_pickers(self):
        self.login(self.root)
        body = self.client.get(reverse("dashboard:prospects")).content.decode()
        self.assertIn("data-geo-country", body)
        self.assertIn("data-geo-city", body)
        self.assertIn('name="geo-src"', body)
        self.assertIn("Find businesses", body)
        form = self.client.get(reverse("dashboard:prospect_new")).content.decode()
        self.assertIn("data-geo-country", form)
        self.assertLess(form.index('name="country"'), form.index('name="city"'))  # country first, then its cities

    def test_manual_prospect_with_picked_country_and_city_saves(self):
        self.login(self.root)
        r = self.client.post(reverse("dashboard:prospect_new"), {"business_name": "Qq Cafe", "category": "restaurant", "country": "Pakistan", "city": "Karachi", "email": "q@qq.test"})
        self.assertEqual(r.status_code, 302)
        p = Prospect.objects.get(business_name="Qq Cafe")
        self.assertEqual((p.country, p.city), ("Pakistan", "Karachi"))
