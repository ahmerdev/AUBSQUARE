"""Proposals (builder → send → public page → alerts → accept request → confirm), reminders, free audit API, commands."""
import io
import json
import sqlite3
import tempfile
from datetime import timedelta
from pathlib import Path

from django.core import mail
from django.core.cache import cache
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone

from apps.cms.models import CaseStudy, Project, Service, Testimonial
from apps.leads.models import Lead
from apps.outbound import services
from apps.outbound.models import OutboundSettings, Proposal, ProposalEvent, ProposalItem, Prospect, SiteAudit

from .base import Base
from .test_outbound_core import LocalSite
from .test_outbound_ui import make_prospect, ready

BROWSER = {"HTTP_USER_AGENT": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0 Safari/537.36"}


class ProposalFlow(Base):
    def setUp(self):
        super().setUp()
        self.admin = self.root
        self.mgr = self.make_user("sales@example.com", "sales_manager")
        self.login(self.admin)
        self.svc = Service.objects.create(title="Brand Identity", status="published", short_description="Logo and guidelines")
        self.lead = Lead.objects.create(name="Ayesha Khan", email="ayesha@client.test", service_label="Logo", status="qualified")

    def build(self, **extra):
        data = {"title": "Brand identity for Ayesha", "client_name": "Ayesha Khan", "client_company": "Khan Co", "client_email": "ayesha@client.test", "currency": "usd", "discount": "100", "tax_percent": "10",
                "valid_until": (timezone.localdate() + timedelta(days=10)).isoformat(), "intro": "Hello", "scope": "Logo, guidelines", "terms": "50% upfront",
                "item_service": [str(self.svc.pk), ""], "item_desc": ["Brand identity", "Stationery"], "item_detail": ["Logo + guide", ""], "item_qty": ["1", "2"], "item_price": ["1500", "200"]}
        data.update(extra)
        r = self.client.post(f"/dashboard/proposals/new/?lead={self.lead.pk}", data)
        self.assertEqual(r.status_code, 302, r.content[:400])
        return Proposal.objects.get()

    def test_builder_computes_totals_and_links_lead(self):
        pr = self.build()
        self.assertEqual(pr.lead_id, self.lead.pk)
        self.assertEqual(pr.reference[:4], "PRP-")
        self.assertEqual(float(pr.subtotal), 1900.0)
        self.assertEqual(float(pr.tax_amount), 180.0)   # (1900-100) * 10%
        self.assertEqual(float(pr.total), 1980.0)
        self.assertEqual(pr.status, "draft")

    def test_builder_requires_items_and_clamps_negative_numbers(self):
        r = self.client.post("/dashboard/proposals/new/", {"title": "T", "client_name": "C", "currency": "USD", "discount": "0", "tax_percent": "0", "item_desc": [""], "item_qty": ["1"], "item_price": ["5"], "item_detail": [""], "item_service": [""]})
        self.assertContains(r, "Add at least one line item")
        pr = self.build(item_price=["-50", "-1"], tax_percent="0", discount="0")
        self.assertEqual(float(pr.subtotal), 0.0)

    def test_draft_proposal_is_not_public(self):
        pr = self.build()
        self.client.logout()
        self.assertEqual(self.client.get(pr.public_path).status_code, 404)

    def test_send_emails_link_through_lead_thread_and_sets_stage(self):
        pr = self.build()
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(f"/dashboard/proposals/{pr.pk}/action/", {"action": "send"})
        pr.refresh_from_db()
        self.lead.refresh_from_db()
        self.assertEqual((pr.status, self.lead.status), ("sent", "proposal"))
        sent = [m for m in mail.outbox if m.to == ["ayesha@client.test"]]
        self.assertEqual(len(sent), 1)
        self.assertIn(pr.public_path, sent[0].body)
        self.assertIn(self.lead.reference, sent[0].subject)
        self.assertIsNotNone(Lead.objects.get(pk=self.lead.pk).first_response_at)

    def _sent(self):
        pr = self.build()
        pr.show_portfolio.add(Project.objects.create(title="Showcase", summary="s", status="published", slug="showcase"))
        pr.show_testimonials.add(Testimonial.objects.create(client_name="Zed", content="Great work", company="ZCo"))
        self.client.post(f"/dashboard/proposals/{pr.pk}/action/", {"action": "mark_sent"})
        pr.refresh_from_db()
        self.client.logout()
        return pr

    def test_public_page_is_private_noindex_and_shows_totals_and_proof(self):
        pr = self._sent()
        r = self.client.get(pr.public_path, **BROWSER)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["X-Robots-Tag"], "noindex, nofollow, noarchive")
        self.assertIn("no-store", r["Cache-Control"])
        # "no-referrer" makes browsers send `Origin: null` on the page's own POSTs, which Django's CSRF check rejects (found in a real browser run).
        self.assertEqual(r["Referrer-Policy"], "same-origin")
        self.assertNotContains(r, 'content="no-referrer"')
        self.assertContains(r, "1,980.00")
        self.assertContains(r, "Showcase")
        self.assertContains(r, "Great work")
        self.assertContains(r, 'name="robots" content="noindex')
        self.assertEqual(self.client.get("/p/not-a-real-token/").status_code, 404)

    def test_view_alert_first_open_counts_bots_and_staff_do_not(self):
        pr = self._sent()
        mail.outbox.clear()
        self.client.get(pr.public_path, HTTP_USER_AGENT="Googlebot/2.1")
        pr.refresh_from_db()
        self.assertEqual(pr.view_count, 0)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.get(pr.public_path, **BROWSER)
        pr.refresh_from_db()
        self.assertEqual((pr.view_count, pr.status), (1, "viewed"))
        self.assertTrue(self.mgr.notifications.filter(title__contains="opened").exists())
        self.assertTrue(ProposalEvent.objects.filter(proposal=pr, kind="viewed").exists())
        n_before = self.mgr.notifications.filter(title__contains="opened").count()
        self.client.get(pr.public_path, **BROWSER)  # reload a minute later: counted, but no second alert
        pr.refresh_from_db()
        self.assertEqual(pr.view_count, 2)
        self.assertEqual(self.mgr.notifications.filter(title__contains="opened").count(), n_before)
        self.login(self.root)
        self.client.get(pr.public_path, **BROWSER)  # staff viewing is not a client view
        pr.refresh_from_db()
        self.assertEqual(pr.view_count, 2)

    def test_preview_requires_staff_and_does_not_count(self):
        pr = self.build()
        self.assertEqual(self.client.get(pr.public_path + "?preview=1").status_code, 200)  # staff, draft ok
        self.client.logout()
        self.assertEqual(self.client.get(pr.public_path + "?preview=1").status_code, 404)

    def test_accept_is_a_request_that_staff_must_confirm(self):
        pr = self._sent()
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            r = self.client.post(pr.public_path, {"action": "accept", "name": "Ayesha K", "note": "Start Monday?"}, **BROWSER)
        self.assertContains(r, "Thank you")
        pr.refresh_from_db()
        self.lead = Lead.objects.get(pk=self.lead.pk)
        self.assertEqual(pr.status, "accept_requested")
        self.assertNotEqual(self.lead.status, "won")      # the client's click alone never marks a deal as won
        self.assertTrue(self.mgr.notifications.filter(title__contains="wants to go ahead").exists())
        self.assertTrue([m for m in mail.outbox if "wants to go ahead" in m.subject])
        r = self.client.post(pr.public_path, {"action": "decline"}, **BROWSER)   # a second response can't flip it silently
        pr.refresh_from_db()
        self.assertEqual(pr.status, "accept_requested")
        self.login(self.root)
        self.client.post(f"/dashboard/proposals/{pr.pk}/action/", {"action": "won"})
        pr.refresh_from_db()
        self.lead.refresh_from_db()
        self.assertEqual((pr.status, self.lead.status), ("won", "won"))

    def test_decline_and_question(self):
        pr = self._sent()
        self.client.post(pr.public_path, {"action": "question", "note": "Can we do 3 logos?"}, **BROWSER)
        pr.refresh_from_db()
        self.assertEqual(pr.status, "sent")
        self.assertTrue(pr.events.filter(kind="question").exists())
        self.client.post(pr.public_path, {"action": "decline", "note": "Too expensive"}, **BROWSER)
        pr.refresh_from_db()
        self.assertEqual(pr.status, "declined")

    def test_expired_proposal_cannot_be_accepted(self):
        pr = self._sent()
        Proposal.objects.filter(pk=pr.pk).update(valid_until=timezone.localdate() - timedelta(days=1))
        r = self.client.get(pr.public_path, **BROWSER)
        self.assertContains(r, "expired")
        self.client.post(pr.public_path, {"action": "accept"}, **BROWSER)
        pr.refresh_from_db()
        self.assertEqual(pr.status, "expired")

    def test_response_rate_limit(self):
        pr = self._sent()
        for _ in range(14):
            r = self.client.post(pr.public_path, {"action": "question", "note": "hi"}, **BROWSER)
        self.assertEqual(r.status_code, 429)

    def test_follow_up_reminder_after_silence_fires_once_and_expiry_is_applied(self):
        pr = self._sent()
        Proposal.objects.filter(pk=pr.pk).update(sent_at=timezone.now() - timedelta(days=4))
        self.assertEqual(services.check_overdue()["proposals"], 1)
        self.assertEqual(services.check_overdue()["proposals"], 0)
        self.assertTrue(self.mgr.notifications.filter(title__startswith="No answer on proposal").exists())
        Proposal.objects.filter(pk=pr.pk).update(valid_until=timezone.localdate() - timedelta(days=1))
        services.check_overdue()
        pr.refresh_from_db()
        self.assertEqual(pr.status, "expired")

    def test_lead_follow_up_reminder_fires_once(self):
        Lead.objects.filter(pk=self.lead.pk).update(follow_up_at=timezone.now() - timedelta(hours=1), follow_up_note="Call back")
        self.assertEqual(services.check_overdue()["follow_ups"], 1)
        self.assertEqual(services.check_overdue()["follow_ups"], 0)

    def test_permissions(self):
        pr = self.build()
        self.client.logout()
        self.login(self.make_user("an@example.com", "analyst"))
        self.assertEqual(self.client.get(f"/dashboard/proposals/{pr.pk}/").status_code, 200)
        self.assertEqual(self.client.post(f"/dashboard/proposals/{pr.pk}/action/", {"action": "won"}).status_code, 403)
        self.assertEqual(self.client.post(f"/dashboard/proposals/{pr.pk}/delete/").status_code, 403)
        self.assertEqual(self.client.get("/dashboard/proposals/new/").status_code, 403)

    def test_duplicate_and_delete(self):
        pr = self.build()
        self.client.post(f"/dashboard/proposals/{pr.pk}/action/", {"action": "duplicate"})
        self.assertEqual(Proposal.objects.count(), 2)
        self.assertEqual(ProposalItem.objects.count(), 4)
        self.client.post(f"/dashboard/proposals/{pr.pk}/delete/")
        self.assertEqual(Proposal.objects.count(), 1)


class FreeAuditApi(Base):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.mgr = self.make_user("sales@example.com", "sales_manager")

    def run_audit(self, base):
        return self.client.post("/api/v1/audit/", json.dumps({"url": base}), content_type="application/json")

    def test_run_audit_returns_real_results_without_internal_data(self):
        with LocalSite() as base:
            r = self.run_audit(base)
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertTrue(d["reachable"])
        self.assertGreater(d["score"], 0)
        self.assertTrue(d["findings"])
        self.assertNotIn("points", d["findings"][0])
        self.assertEqual(SiteAudit.objects.get().kind, "free")
        self.assertTrue(any(c["key"] == "https" and not c["ok"] for c in d["checks"]))

    def test_private_targets_are_refused_with_friendly_message(self):
        for url in ("http://127.0.0.1/", "http://169.254.169.254/", "localhost", "file:///etc/passwd", "http://10.0.0.1:22/"):
            cache.clear()
            r = self.run_audit(url)
            self.assertEqual(r.status_code, 200, url)
            d = r.json()
            self.assertFalse(d["reachable"], url)
            self.assertTrue(d["error"])
            self.assertIsNone(d["score"])
        self.assertEqual(self.client.post("/api/v1/audit/", json.dumps({"url": ""}), content_type="application/json").status_code, 400)

    def test_rate_limit_and_daily_cap(self):
        cache.clear()
        with override_settings(FREE_AUDIT_DAILY_CAP=1):
            self.assertEqual(self.run_audit("http://127.0.0.1/").status_code, 200)
            cache.delete(f"free-audit-lock:127.0.0.1")
            r = self.run_audit("http://127.0.0.1/")
            self.assertEqual(r.status_code, 503)

    def test_throttle(self):
        codes = []
        for _ in range(8):
            cache.delete("free-audit-lock:127.0.0.1")
            codes.append(self.run_audit("http://127.0.0.1/").status_code)
        self.assertIn(429, codes)

    def test_honeypot(self):
        r = self.client.post("/api/v1/audit/", json.dumps({"url": "example.com", "website": "spam"}), content_type="application/json")
        self.assertEqual(r.status_code, 400)

    def test_get_by_token_and_expiry(self):
        with LocalSite() as base:
            tok = self.run_audit(base).json()["token"]
        self.assertEqual(self.client.get(f"/api/v1/audit/{tok}/").status_code, 200)
        SiteAudit.objects.filter(public_token=tok).update(created_at=timezone.now() - timedelta(days=8))
        self.assertEqual(self.client.get(f"/api/v1/audit/{tok}/").status_code, 404)
        self.assertEqual(self.client.get("/api/v1/audit/nope/").status_code, 404)

    def test_visitor_can_request_help_once_and_becomes_a_lead(self):
        with LocalSite() as base:
            tok = self.run_audit(base).json()["token"]
        bad = self.client.post(f"/api/v1/audit/{tok}/lead/", json.dumps({"name": "Sara", "email": "bad"}), content_type="application/json")
        self.assertEqual(bad.status_code, 400)
        self.assertIn("consent", bad.json()["error"]["details"])
        body = {"name": "Sara Ali", "email": "Sara@Client.test", "phone": "+92 300 1", "consent": True, "message": "Please help"}
        r = self.client.post(f"/api/v1/audit/{tok}/lead/", json.dumps(body), content_type="application/json")
        self.assertEqual(r.status_code, 201)
        lead = Lead.objects.get()
        self.assertEqual((lead.source, lead.email, lead.consent_given), ("audit_tool", "sara@client.test", True))
        self.assertIn("Top findings", lead.message)
        self.assertIn("Please help", lead.message)
        self.assertTrue(self.mgr.notifications.filter(title__startswith="Reply fast").exists())
        again = self.client.post(f"/api/v1/audit/{tok}/lead/", json.dumps(body), content_type="application/json")
        self.assertTrue(again.json()["duplicate"])
        self.assertEqual(Lead.objects.count(), 1)

    def test_unreachable_audit_cannot_create_lead(self):
        tok = self.run_audit("http://127.0.0.1/").json()["token"]
        r = self.client.post(f"/api/v1/audit/{tok}/lead/", json.dumps({"name": "Sara Ali", "email": "s@c.test", "consent": True}), content_type="application/json")
        self.assertEqual(r.status_code, 404)


class CommandTests(Base):
    def _legacy_db(self):
        path = Path(tempfile.mkdtemp()) / "old.sqlite3"
        con = sqlite3.connect(path)
        con.execute("create table leads_lead (business_name text, website text, email text, phone text, city text, country text, industry text, source text, external_id text, notes text)")
        rows = [("Real Dental", "https://realdental.ae/", "info@realdental.ae", "", "Dubai", "United Arab Emirates", "Dental", "OSM", "node/1", ""),
                ("Parked Realty", "https://sedo.com/search/details/?domain=x.ae", "info@x.ae", "", "Dubai", "United Arab Emirates", "Real Estate", "OSM", "node/2", ""),
                ("Curated Sample", "https://sample.test", "a@sample.test", "", "Lahore", "Pakistan", "Restaurant", "DISCOVERY", "curated/1", ""),
                ("Manual Entry", "https://manual.test", "a@manual.test", "", "Lahore", "Pakistan", "Restaurant", "MANUAL", "", "")]
        con.executemany("insert into leads_lead values (?,?,?,?,?,?,?,?,?,?)", rows)
        con.commit()
        con.close()
        return str(path)

    def test_import_only_real_osm_rows_and_is_idempotent(self):
        db = self._legacy_db()
        out = io.StringIO()
        call_command("import_leadradar", db=db, stdout=out)
        self.assertEqual(set(Prospect.objects.values_list("business_name", flat=True)), {"Real Dental", "Parked Realty"})
        self.assertEqual(Prospect.objects.get(business_name="Parked Realty").website, "")   # parking page is not their website
        self.assertEqual(Prospect.objects.get(business_name="Real Dental").source, "legacy")
        call_command("import_leadradar", db=db, stdout=io.StringIO())
        self.assertEqual(Prospect.objects.count(), 2)

    def test_import_dry_run_changes_nothing(self):
        call_command("import_leadradar", db=self._legacy_db(), dry_run=True, stdout=io.StringIO())
        self.assertEqual(Prospect.objects.count(), 0)

    def test_run_outreach_does_housekeeping_and_never_sends_unapproved(self):
        ready()
        p = make_prospect()
        from apps.outbound import outreach

        outreach.draft_message(p, 1, "email", self.root)
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            call_command("run_outreach", stdout=io.StringIO())
        self.assertEqual(len(mail.outbox), 0)
        self.assertIsNotNone(OutboundSettings.load().last_run_at)

    def test_run_outreach_audits_waiting_prospects(self):
        with LocalSite() as base:
            p = make_prospect(website=base, email="")
            call_command("run_outreach", audit=5, stdout=io.StringIO())
        p.refresh_from_db()
        self.assertEqual(p.status, "audited")
