"""Outbound dashboard screens, permissions, outreach safety, sequences, proposals, public pages and the free audit API."""
import json
from datetime import timedelta
from unittest import mock

from django.core import mail
from django.urls import reverse
from django.utils import timezone

from apps.leads.models import Lead
from apps.mailer.models import EmailMessage
from apps.outbound import outreach, services
from apps.outbound.models import (OutboundSettings, OutreachMessage, Proposal, ProposalItem, Prospect, Sequence, SiteAudit, SuppressionEntry)

from .base import Base
from .test_outbound_core import LocalSite


def ready(cfg=None):
    cfg = cfg or OutboundSettings.load()
    cfg.postal_address = "1 Main Street, Lahore, Pakistan"
    cfg.sender_name = "Sam"
    cfg.save()
    return cfg


def make_prospect(**kw):
    d = dict(business_name="Bella Dental", website="https://bella.test", email="hello@bella.test", category="dental", country="Pakistan", city="Lahore")
    d.update(kw)
    p, why = services.create_prospect(d, "manual")
    assert p and not why, why
    return p


class ScreensAndPermissions(Base):
    def setUp(self):
        super().setUp()
        self.login(self.root)

    def test_every_outbound_screen_renders_for_admin(self):
        p = make_prospect()
        pr = Proposal.objects.create(title="Website", client_name="Ayesha", client_email="a@client.test")
        ProposalItem.objects.create(proposal=pr, description="Build", quantity=1, unit_price=500)
        names = [("dashboard:outbound", []), ("dashboard:prospects", []), ("dashboard:prospect_new", []), ("dashboard:prospect_detail", [p.pk]), ("dashboard:pipeline", []),
                 ("dashboard:outreach", []), ("dashboard:sequences", []), ("dashboard:sequence_new", []), ("dashboard:outbound_settings", []), ("dashboard:sales_reports", []),
                 ("dashboard:proposals", []), ("dashboard:proposal_new", []), ("dashboard:proposal_detail", [pr.pk]), ("dashboard:proposal_edit", [pr.pk]), ("dashboard:site_audit", [])]
        for name, args in names:
            r = self.client.get(reverse(name, args=args))
            self.assertEqual(r.status_code, 200, name)
        for slug in ("outreach-templates", "do-not-contact"):
            self.assertEqual(self.client.get(reverse("dashboard:list", args=[slug])).status_code, 200, slug)
            self.assertEqual(self.client.get(reverse("dashboard:create", args=[slug])).status_code, 200, slug)
        for tab in ("waiting", "approved", "sent", "whatsapp", "issues"):
            self.assertEqual(self.client.get(reverse("dashboard:outreach") + f"?tab={tab}").status_code, 200)
        self.assertEqual(self.client.get(reverse("dashboard:pipeline") + "?board=prospects").status_code, 200)
        self.assertEqual(self.client.get(reverse("dashboard:sales_reports") + "?range=all").status_code, 200)

    def test_sidebar_shows_outbound_group(self):
        r = self.client.get("/dashboard/outbound/")
        self.assertContains(r, "Outbound Sales")
        self.assertContains(r, "Prospects")

    def test_role_without_permission_is_blocked_everywhere(self):
        self.client.logout()
        self.login(self.make_user("support@example.com", "support_agent"))
        for url in ("/dashboard/outbound/", "/dashboard/prospects/", "/dashboard/outreach/", "/dashboard/proposals/", "/dashboard/outbound-settings/", "/dashboard/sales-reports/"):
            self.assertEqual(self.client.get(url).status_code, 403, url)
        self.assertEqual(self.client.post("/dashboard/prospects/bulk/", {"action": "delete", "ids": "1"}).status_code, 403)
        self.assertEqual(self.client.post("/dashboard/outbound/run-checks/").status_code, 403)

    def test_sales_manager_can_work_but_analyst_is_read_only(self):
        p = make_prospect()
        self.client.logout()
        self.login(self.make_user("an@example.com", "analyst"))
        self.assertEqual(self.client.get("/dashboard/prospects/").status_code, 200)
        self.assertEqual(self.client.post(f"/dashboard/prospects/{p.pk}/action/", {"action": "reject"}).status_code, 403)
        self.assertEqual(self.client.get("/dashboard/prospects/new/").status_code, 403)
        self.client.logout()
        self.login(self.make_user("sales@example.com", "sales_manager"))
        self.assertEqual(self.client.get("/dashboard/outreach/").status_code, 200)
        self.assertEqual(self.client.get("/dashboard/outbound-settings/").status_code, 200)

    def test_existing_roles_received_the_new_modules(self):
        from apps.accounts.models import Role

        self.assertIn("outbound", Role.objects.get(slug="sales_manager").permissions)
        self.assertIn("proposals", Role.objects.get(slug="sales_manager").permissions)

    def test_csrf_and_post_only_actions(self):
        p = make_prospect()
        self.assertEqual(self.client.get(f"/dashboard/prospects/{p.pk}/action/").status_code, 405)
        self.assertEqual(self.client.get("/dashboard/prospects/discover/").status_code, 405)


class ProspectFlows(Base):
    def setUp(self):
        super().setUp()
        self.login(self.root)

    def test_add_prospect_manually_and_duplicate_is_redirected(self):
        r = self.client.post("/dashboard/prospects/new/", {"business_name": "Chai Spot", "category": "restaurant", "website": "chaispot.test", "email": "hi@chaispot.test", "country": "Pakistan"})
        self.assertEqual(r.status_code, 302)
        r2 = self.client.post("/dashboard/prospects/new/", {"business_name": "Chai Spot 2", "category": "restaurant", "website": "https://www.chaispot.test/", "country": "Pakistan"})
        self.assertEqual(Prospect.objects.count(), 1)
        self.assertEqual(r2.status_code, 302)

    def test_form_validation(self):
        r = self.client.post("/dashboard/prospects/new/", {"business_name": "X Co", "category": "other"})
        self.assertContains(r, "at least a website, email or phone")
        r = self.client.post("/dashboard/prospects/new/", {"business_name": "X Co", "category": "other", "website": "javascript:alert(1)"})
        self.assertEqual(Prospect.objects.count(), 0)

    def test_audit_from_detail_page_scores_and_finds_email(self):
        p = make_prospect(website="", email="", phone="+92 300 1")
        with LocalSite() as base:
            p.website = base
            p.save()
            r = self.client.post(f"/dashboard/prospects/{p.pk}/action/", {"action": "audit"}, follow=True)
        p.refresh_from_db()
        self.assertEqual(r.status_code, 200)
        self.assertEqual((p.status, p.email), ("audited", "hello@bella.test"))
        self.assertGreater(p.opportunity_score, 0)
        self.assertContains(r, "What we would fix")

    def test_audit_of_unreachable_site_shows_honest_error(self):
        p = make_prospect(website="https://127.0.0.1/")
        r = self.client.post(f"/dashboard/prospects/{p.pk}/action/", {"action": "audit"}, follow=True)
        self.assertContains(r, "could not be audited")
        p.refresh_from_db()
        self.assertEqual((p.opportunity_score, p.opportunity_level), (0, "unknown"))

    def test_convert_creates_lead_and_redirects(self):
        p = make_prospect()
        r = self.client.post(f"/dashboard/prospects/{p.pk}/action/", {"action": "convert"})
        lead = Lead.objects.get()
        self.assertRedirects(r, f"/dashboard/leads/{lead.pk}/", fetch_redirect_response=False)
        self.client.post(f"/dashboard/prospects/{p.pk}/action/", {"action": "convert"})
        self.assertEqual(Lead.objects.count(), 1)

    def test_do_not_contact_button_blocks_and_stops_everything(self):
        ready()
        p = make_prospect()
        outreach.draft_message(p, 1, "email", self.root)
        self.client.post(f"/dashboard/prospects/{p.pk}/action/", {"action": "dnc"})
        p.refresh_from_db()
        self.assertEqual(p.status, "suppressed")
        self.assertTrue(SuppressionEntry.objects.filter(email="hello@bella.test").exists())
        self.assertEqual(OutreachMessage.objects.get().status, "skipped")

    def test_csv_import_and_export_is_formula_safe(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        f = SimpleUploadedFile("p.csv", b"business_name,website,email,category,city,country\n=HYPERLINK(1),evil.test,x@evil.test,dental,Lahore,Pakistan\n")
        self.client.post("/dashboard/prospects/import/", {"file": f})
        self.assertEqual(Prospect.objects.count(), 1)
        r = self.client.get("/dashboard/prospects/export/")
        self.assertIn("'=HYPERLINK", r.content.decode())

    def test_csv_without_name_column_is_rejected(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        self.client.post("/dashboard/prospects/import/", {"file": SimpleUploadedFile("p.csv", b"foo,bar\n1,2\n")})
        self.assertEqual(Prospect.objects.count(), 0)

    def test_discovery_adds_only_real_returned_records_and_reports_failure(self):
        cand = [{"external_id": "osm/node/1", "business_name": "Real Dental", "website": "https://realdental.test", "phone": "", "email": "", "city": "Lahore", "country": "Pakistan", "category": "dental", "address": ""}]
        with mock.patch("apps.outbound.discovery.discover", return_value=(cand, [])):
            self.client.post("/dashboard/prospects/discover/", {"category": "dental", "city": "Lahore", "country": "Pakistan", "limit": "10"})
        p = Prospect.objects.get()
        self.assertEqual((p.source, p.external_id), ("osm", "osm/node/1"))
        with mock.patch("apps.outbound.discovery.discover", return_value=(cand, [])):
            self.client.post("/dashboard/prospects/discover/", {"category": "dental", "city": "Lahore", "country": "Pakistan"})
        self.assertEqual(Prospect.objects.count(), 1)  # same OSM id is not added twice
        from apps.outbound.discovery import DiscoveryError

        with mock.patch("apps.outbound.discovery.discover", side_effect=DiscoveryError("busy")):
            r = self.client.post("/dashboard/prospects/discover/", {"category": "dental", "city": "X"}, follow=True)
        self.assertContains(r, "busy")
        self.assertEqual(Prospect.objects.count(), 1)

    def test_bulk_actions(self):
        a, b = make_prospect(), make_prospect(business_name="Other", website="https://o.test", email="o@o.test")
        self.client.post("/dashboard/prospects/bulk/", {"action": "reject", "ids": [a.pk, b.pk]})
        self.assertEqual(Prospect.objects.filter(status="rejected").count(), 2)
        self.client.post("/dashboard/prospects/bulk/", {"action": "delete", "ids": [a.pk]})
        self.assertEqual(Prospect.objects.count(), 1)


class OutreachSafety(Base):
    def setUp(self):
        super().setUp()
        self.login(self.root)
        self.cfg = ready()

    def _approve_and_send(self, p, **post):
        m = outreach.draft_message(p, 1, "email", self.root)
        self.client.post(f"/dashboard/outreach/{m.pk}/action/", {"action": "approve", "tab": "waiting"})
        m.refresh_from_db()
        return m

    def test_draft_uses_real_audit_findings_and_is_labelled_template(self):
        p = make_prospect()
        with LocalSite() as base:
            p.website = base
            p.save()
            services.audit_prospect(p, self.root)
        m = outreach.draft_message(p, 1, "email", self.root)
        self.assertEqual(m.generated_by, "template")
        self.assertIn("Bella Dental", m.body)
        self.assertIn("WhatsApp", m.body + m.subject)  # the real top finding is mentioned
        self.assertEqual(m.status, "draft")

    def test_nothing_is_sent_until_approved_then_send_adds_footer_and_unsubscribe(self):
        p = make_prospect()
        m = outreach.draft_message(p, 1, "email", self.root)
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            res = outreach.send_approved()
        self.assertEqual((res["queued"], len(mail.outbox)), (0, 0))
        self.client.post(f"/dashboard/outreach/{m.pk}/action/", {"action": "approve"})
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post("/dashboard/outreach/bulk/", {"action": "send"})
        self.assertEqual(len(mail.outbox), 1)
        out = mail.outbox[0]
        self.assertEqual(out.to, ["hello@bella.test"])
        self.assertIn("1 Main Street, Lahore", out.body)
        self.assertIn(f"/o/{p.token}/", out.body)
        self.assertIn(f"/o/{p.token}/", out.extra_headers["List-Unsubscribe"])
        self.assertEqual(out.extra_headers["List-Unsubscribe-Post"], "List-Unsubscribe=One-Click")
        m.refresh_from_db()
        outreach.sync_status()
        m.refresh_from_db()
        self.assertEqual(m.status, "sent")
        p.refresh_from_db()
        self.assertEqual(p.status, "contacted")
        self.assertEqual(EmailMessage.objects.get(kind="outbound").status, "sent")

    def test_postal_address_required(self):
        self.cfg.postal_address = ""
        self.cfg.save()
        p = make_prospect()
        m = outreach.draft_message(p, 1, "email", self.root)
        self.assertIn("postal address", m.block_reason)
        ok, why = outreach.approve(m, self.root)
        self.assertFalse(ok)

    def test_region_rule_blocks_other_countries(self):
        p = make_prospect(country="Germany")
        m = outreach.draft_message(p, 1, "email", self.root)
        self.assertIn("not enabled", m.block_reason)
        self.assertFalse(outreach.approve(m, self.root)[0])

    def test_daily_limit_is_enforced(self):
        self.cfg.daily_email_limit = 2
        self.cfg.save()
        ps = [make_prospect(business_name=f"B{i}", website=f"https://b{i}.test", email=f"e{i}@b{i}.test") for i in range(4)]
        for p in ps:
            m = outreach.draft_message(p, 1, "email", self.root)
            outreach.approve(m, self.root)
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            res = outreach.send_approved()
        self.assertEqual((res["queued"], res["limit_reached"], len(mail.outbox)), (2, True, 2))
        self.assertEqual(services.daily_remaining(), 0)
        self.assertEqual(OutreachMessage.objects.filter(status="approved").count(), 2)

    def test_suppressed_after_approval_is_still_not_sent(self):
        p = make_prospect()
        m = self._approve_and_send(p)
        self.assertEqual(m.status, "approved")
        services.suppress(email=p.email, reason="unsubscribed")
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            outreach.send_approved()
        self.assertEqual(len(mail.outbox), 0)
        m.refresh_from_db()
        self.assertEqual(m.status, "skipped")

    def test_unsubscribe_page_get_does_not_unsubscribe_post_does(self):
        p = make_prospect()
        self.client.logout()
        r = self.client.get(f"/o/{p.token}/")
        self.assertContains(r, "Yes, unsubscribe me")
        self.assertEqual(r["X-Robots-Tag"], "noindex, nofollow, noarchive")
        p.refresh_from_db()
        self.assertNotEqual(p.status, "suppressed")
        r = self.client.post(f"/o/{p.token}/", {"List-Unsubscribe": "One-Click"})
        self.assertContains(r, "won't hear from us again")
        p.refresh_from_db()
        self.assertEqual(p.status, "suppressed")
        self.assertTrue(SuppressionEntry.objects.filter(email="hello@bella.test", reason="unsubscribed").exists())
        self.assertEqual(self.client.get("/o/nonexistent/").status_code, 404)

    def test_reply_stops_sequence_and_flags_prospect(self):
        p = make_prospect()
        seq = Sequence.objects.first()
        ok, why = outreach.enroll(p, seq, self.root)
        self.assertTrue(ok, why)
        self.assertEqual(OutreachMessage.objects.filter(prospect=p).count(), 1)
        inbound = mock.Mock(from_email="hello@bella.test", in_reply_to="", subject="Re: Quick idea", body_text="Yes please send the audit")
        outreach.handle_inbound_reply(inbound)
        p.refresh_from_db()
        self.assertEqual(p.status, "replied")
        self.assertEqual(p.enrollments.get().status, "stopped")
        self.assertEqual(OutreachMessage.objects.get().status, "skipped")  # waiting draft cancelled

    def test_reply_asking_to_stop_adds_to_do_not_contact(self):
        p = make_prospect()
        outreach.handle_inbound_reply(mock.Mock(from_email="hello@bella.test", in_reply_to="", subject="Re: hi", body_text="Please remove me from your list"))
        p.refresh_from_db()
        self.assertEqual(p.status, "suppressed")
        self.assertTrue(services.is_suppressed("hello@bella.test"))

    def test_inbound_hook_runs_for_real_imap_store(self):
        from apps.mailer.inbound import store_inbound

        p = make_prospect()
        store_inbound({"message_id": "<abc@x>", "from_email": "hello@bella.test", "from_name": "Bella", "subject": "Re: Quick idea", "text": "interested, send details", "html": "",
                       "in_reply_to": "", "references": "", "to": ["us@x.test"], "cc": [], "attachments": [], "date": timezone.now()})
        p.refresh_from_db()
        self.assertEqual(p.status, "replied")

    def test_follow_up_waits_for_previous_email_to_be_sent_and_respects_delay(self):
        p = make_prospect()
        outreach.enroll(p, Sequence.objects.first(), self.root)
        en = p.enrollments.get()
        en.next_at = timezone.now() - timedelta(minutes=1)
        en.save()
        self.assertEqual(outreach.advance_due(), 0)  # step 1 was never sent → no follow-up
        m = OutreachMessage.objects.get(step=1)
        m.status = "sent"
        m.save()
        en.refresh_from_db()
        en.next_at = timezone.now() - timedelta(minutes=1)
        en.save()
        self.assertEqual(outreach.advance_due(), 1)
        self.assertEqual(OutreachMessage.objects.filter(step=2).count(), 1)

    def test_cannot_enroll_blocked_or_twice(self):
        p = make_prospect(country="Germany")
        self.assertFalse(outreach.enroll(p, Sequence.objects.first())[0])
        q = make_prospect(business_name="Qq Cafe", website="https://q.test", email="q@q.test")
        self.assertTrue(outreach.enroll(q, Sequence.objects.first())[0])
        self.assertFalse(outreach.enroll(q, Sequence.objects.first())[0])

    def test_ai_falls_back_to_labelled_template_when_gemini_fails(self):
        self.cfg.ai_enabled = True
        self.cfg.set_gemini_key("fake-key")
        self.cfg.save()
        p = make_prospect()
        with mock.patch("apps.outbound.pitch.urllib.request.urlopen", side_effect=OSError("down")):
            m = outreach.draft_message(p, 1, "email", self.root, use_ai=True)
        self.assertEqual(m.generated_by, "template")
        self.assertIn("AI was unavailable", m.block_reason)

    def test_ai_pitch_is_marked_ai_and_key_goes_in_header_not_url(self):
        self.cfg.ai_enabled = True
        self.cfg.set_gemini_key("secret-key-123")
        self.cfg.save()
        p = make_prospect()
        body = json.dumps({"candidates": [{"content": {"parts": [{"text": json.dumps({"subject": "Idea for Bella", "body": "Hi Bella team, I noticed your site has no booking button. " * 2})}]}}]}).encode()
        resp = mock.MagicMock()
        resp.read.return_value = body
        resp.__enter__.return_value = resp
        with mock.patch("apps.outbound.pitch.urllib.request.urlopen", return_value=resp) as uo:
            m = outreach.draft_message(p, 1, "email", self.root, use_ai=True)
        req = uo.call_args[0][0]
        self.assertEqual(m.generated_by, "ai")
        self.assertNotIn("secret-key-123", req.full_url)
        self.assertEqual(req.get_header("X-goog-api-key"), "secret-key-123")

    def test_whatsapp_is_a_click_to_chat_link_only(self):
        p = make_prospect(phone="+92 300 1234567")
        m = outreach.draft_message(p, 1, "whatsapp", self.root)
        r = self.client.get("/dashboard/outreach/?tab=whatsapp")
        self.assertContains(r, "https://wa.me/923001234567?text=")
        self.assertEqual(EmailMessage.objects.count(), 0)
        self.client.post(f"/dashboard/outreach/{m.pk}/action/", {"action": "mark_sent", "tab": "whatsapp"})
        m.refresh_from_db()
        self.assertEqual(m.status, "sent")


class SettingsTests(Base):
    def setUp(self):
        super().setUp()
        self.login(self.root)

    def _post(self, **kw):
        cfg = OutboundSettings.load()
        d = {"daily_email_limit": 25, "require_approval": "on", "region_mode": "allow_list", "allowed_countries": "Pakistan", "sender_business": "AUB SQUARE", "sender_name": "Sam", "postal_address": "Lahore",
             "whatsapp_number": "", "gemini_model": "gemini-1.5-flash", "speed_alert_minutes": 10, "auto_reply_subject": "Hi {name}", "auto_reply_body": "Thanks {name}", "follow_up_days": "3,7",
             "proposal_reminder_days": 3, "proposal_valid_days": 14, "currency": "usd"}
        from apps.outbound.models import SCORE_RULES

        d.update({"w_" + k: v[1] for k, v in SCORE_RULES.items()})
        d.update(kw)
        return self.client.post("/dashboard/outbound-settings/", d, follow=True)

    def test_save_encrypts_key_and_never_echoes_it(self):
        r = self._post(gemini_key="AIza-super-secret")
        cfg = OutboundSettings.load()
        self.assertEqual(cfg.get_gemini_key(), "AIza-super-secret")
        self.assertNotIn("AIza-super-secret", cfg.gemini_key_enc)
        self.assertNotContains(r, "AIza-super-secret")
        self._post()  # blank keeps it
        self.assertEqual(OutboundSettings.load().get_gemini_key(), "AIza-super-secret")
        self._post(clear_key="on")
        self.assertFalse(OutboundSettings.load().has_gemini_key)
        self.assertEqual(OutboundSettings.load().currency, "USD")

    def test_limit_validation_and_weights(self):
        r = self._post(daily_email_limit=5000)
        self.assertContains(r, "Choose a number from 1 to 200")
        self._post(w_no_ssl=40)
        self.assertEqual(OutboundSettings.load().weight("no_ssl"), 40)


class PipelineTests(Base):
    def setUp(self):
        super().setUp()
        self.login(self.root)

    def test_board_groups_leads_and_moves_with_response_tracking(self):
        l1 = Lead.objects.create(name="A", email="a@a.test", category="design", service_label="Logo")
        Lead.objects.create(name="B", email="b@a.test", category="website")
        r = self.client.get("/dashboard/pipeline/?category=design")
        self.assertContains(r, "A")
        self.assertNotContains(r, ">B<")
        r = self.client.post("/dashboard/pipeline/move/", {"kind": "lead", "id": l1.pk, "to": "contacted"})
        self.assertEqual(r.json(), {"ok": True})
        l1.refresh_from_db()
        self.assertEqual(l1.status, "contacted")
        self.assertIsNotNone(l1.first_response_at)
        self.assertEqual(self.client.post("/dashboard/pipeline/move/", {"kind": "lead", "id": l1.pk, "to": "hacked"}).json(), {"ok": True, "unchanged": True})
        self.assertEqual(self.client.post("/dashboard/pipeline/move/", {"kind": "x", "id": 1, "to": "new"}).status_code, 400)

    def test_prospect_board_move_rules(self):
        p = make_prospect()
        self.assertEqual(self.client.post("/dashboard/pipeline/move/", {"kind": "prospect", "id": p.pk, "to": "replied"}).status_code, 200)
        self.assertEqual(self.client.post("/dashboard/pipeline/move/", {"kind": "prospect", "id": p.pk, "to": "converted"}).status_code, 400)

    def test_lead_category_can_be_changed_on_lead_page(self):
        l = Lead.objects.create(name="A", email="a@a.test")
        self.client.post(f"/dashboard/leads/{l.pk}/update/", {"action": "category", "category": "seo"})
        l.refresh_from_db()
        self.assertEqual(l.category, "seo")

    def test_lead_status_change_from_lead_page_records_first_response(self):
        l = Lead.objects.create(name="A", email="a@a.test")
        self.client.post(f"/dashboard/leads/{l.pk}/update/", {"action": "status", "status": "contacted"})
        l.refresh_from_db()
        self.assertIsNotNone(l.first_response_at)

    def test_staff_reply_records_first_response(self):
        from apps.mailer.service import reply_to_lead

        l = Lead.objects.create(name="A", email="a@a.test")
        reply_to_lead(l, self.root, "Hello", "Thanks for your enquiry")
        l.refresh_from_db()
        self.assertIsNotNone(l.first_response_at)

    def test_reports_calculate_funnel_and_response_time(self):
        l = Lead.objects.create(name="A", email="a@a.test", category="design", status="won")
        Lead.objects.filter(pk=l.pk).update(created_at=timezone.now() - timedelta(minutes=30), first_response_at=timezone.now() - timedelta(minutes=20))
        r = self.client.get("/dashboard/sales-reports/")
        self.assertEqual(r.context["resp"]["avg"], 10)
        self.assertEqual(r.context["resp"]["within"], 100)
        self.assertEqual(r.context["by_cat"][0]["won"], 1)

    def test_cost_per_lead_uses_only_recorded_spend(self):
        from apps.marketing.models import Campaign, CampaignMetric

        c = Campaign.objects.create(name="Search", channel="google_ads", utm_campaign="search-jan")
        Lead.objects.create(name="A", email="a@a.test", utm_campaign="search-jan")
        Lead.objects.create(name="B", email="b@a.test", utm_campaign="search-jan")
        CampaignMetric.objects.create(campaign=c, date=timezone.localdate(), spend=100)
        r = self.client.get("/dashboard/sales-reports/")
        row = r.context["camp"][0]
        self.assertEqual((row["leads"], float(row["cpl"])), (2, 50.0))
        Campaign.objects.create(name="NoSpend", channel="meta_ads", utm_campaign="meta-x")
        r = self.client.get("/dashboard/sales-reports/")
        self.assertEqual(len(r.context["camp"]), 1)  # a campaign with no leads and no spend is not shown with invented numbers


class SequenceEditorTests(Base):
    def setUp(self):
        super().setUp()
        self.login(self.root)

    def test_create_edit_delete_sequence(self):
        r = self.client.post("/dashboard/sequences/new/", {"name": "Short", "is_active": "on", "delay_days": ["0", "5"], "template": ["", ""]})
        self.assertEqual(r.status_code, 302)
        seq = Sequence.objects.get(name="Short")
        self.assertEqual([s.delay_days for s in seq.steps.all()], [0, 5])
        self.client.post(f"/dashboard/sequences/{seq.pk}/", {"name": "Short2", "delay_days": ["0"], "template": [""]})
        seq.refresh_from_db()
        self.assertEqual((seq.name, seq.steps.count(), seq.is_active), ("Short2", 1, False))
        self.client.post(f"/dashboard/sequences/{seq.pk}/delete/")
        self.assertFalse(Sequence.objects.filter(pk=seq.pk).exists())

    def test_validation(self):
        self.assertEqual(self.client.post("/dashboard/sequences/new/", {"name": "", "delay_days": ["0"], "template": [""]}).status_code, 200)
        self.assertEqual(self.client.post("/dashboard/sequences/new/", {"name": "Six", "delay_days": ["0"] * 6, "template": [""] * 6}).status_code, 200)
        self.assertEqual(Sequence.objects.filter(name__in=["", "Six"]).count(), 0)

    def test_templates_registry_crud(self):
        r = self.client.post("/dashboard/outreach-templates/new/", {"name": "T1", "kind": "first", "category": "", "is_active": "on", "subject": "Hi {business}", "body": "Hello {business}, {issue}"})
        self.assertEqual(r.status_code, 302)
        p = make_prospect()
        ready()
        m = outreach.draft_message(p, 1, "email", self.root)
        self.assertEqual(m.subject, "Hi Bella Dental")


class SalesTouchpoints(Base):
    """Lead screens, home card and public SEO entries added with the outbound work."""

    def setUp(self):
        super().setUp()
        self.login(self.root)
        self.lead = Lead.objects.create(name="Dana", email="dana@example.com", message="Need a logo and brand identity", category="design")

    def test_lead_detail_shows_group_waiting_and_proposal_button(self):
        body = self.client.get(reverse("dashboard:lead_detail", args=[self.lead.pk])).content.decode()
        self.assertIn("Design &amp; branding", body)
        self.assertIn("Waiting for a reply", body)
        self.assertIn(f"/dashboard/proposals/new/?lead={self.lead.pk}", body)

    def test_proposal_button_hidden_without_permission(self):
        self.client.logout()
        self.login(self.make_user("an4@example.com", "analyst"))
        body = self.client.get(reverse("dashboard:lead_detail", args=[self.lead.pk])).content.decode()
        self.assertNotIn("/dashboard/proposals/new/", body)

    def test_leads_list_category_filter(self):
        Lead.objects.create(name="Eli", email="eli@example.com", message="Need a website", category="website")
        body = self.client.get(reverse("dashboard:leads") + "?category=design").content.decode()
        self.assertIn("Dana", body)
        self.assertNotIn("Eli", body)
        self.assertEqual(self.client.get(reverse("dashboard:leads") + "?category=bogus").status_code, 200)

    def test_home_card_counts_only_real_waiting_items(self):
        Lead.objects.filter(pk=self.lead.pk).update(created_at=timezone.now() - timedelta(hours=2))
        body = self.client.get(reverse("dashboard:home")).content.decode()
        self.assertIn("Leads waiting for a first reply", body)
        self.lead.refresh_from_db()
        Lead.objects.filter(pk=self.lead.pk).update(first_response_at=timezone.now())
        from apps.dashboard.views_core import _sales_attention

        counts = {label: n for label, n, _u, _h in _sales_attention(self.root)}
        self.assertEqual(counts["Leads waiting for a first reply"], 0)

    def test_free_audit_page_in_sitemap_and_has_meta(self):
        self.assertIn("/free-audit", self.client.get("/sitemap.xml").content.decode())
        meta = self.client.get("/api/v1/seo/?path=/free-audit")
        self.assertEqual(meta.status_code, 200)
        self.assertIn("Free Website Audit", json.dumps(meta.json()))

    def test_prospect_and_outreach_pages_render_block_reason_as_text(self):
        """Regression: a context variable called `block` collided with Django's {% block %} machinery and printed template internals."""
        ready()
        ok = make_prospect()
        body = self.client.get(reverse("dashboard:prospect_detail", args=[ok.pk])).content.decode()
        self.assertNotIn("Block Node", body)
        self.assertNotIn("is blocked for this prospect", body)
        self.assertNotRegex(body, r'value="draft_email"\s+disabled')
        bad = make_prospect(business_name="No Mail Co", email="", website="https://nomail.test")
        body = self.client.get(reverse("dashboard:prospect_detail", args=[bad.pk])).content.decode()
        self.assertIn("is blocked for this prospect", body)
        self.assertNotIn("Block Node", body)
        self.assertRegex(body, r'value="draft_email"\s+disabled')
        outreach.draft_message(ok, 1, "email", self.root)
        self.assertNotIn("Block Node", self.client.get(reverse("dashboard:outreach")).content.decode())
