"""Audit www/non-www retry, prospect website in emails, proposal client website, visitor confirmation + staff alert emails."""
import json
from datetime import timedelta
from unittest import mock

from django.core import mail
from django.utils import timezone

from apps.leads.models import Lead
from apps.outbound import netguard, pitch, services
from apps.outbound.audit import run_audit
from apps.outbound.models import OutboundSettings, Proposal, ProposalItem, Prospect

from .base import Base, old_token


def fetched(url="https://sirialab.it/", html="<html><head><title>Siria</title></head><body><h1>Hi</h1></body></html>"):
    return netguard.Fetched(status=200, url=url, headers={"content-type": "text/html"}, body=html.encode(), elapsed=0.2)


class AuditRetries(Base):
    def test_host_variants_toggle_www_and_scheme(self):
        self.assertEqual(netguard.host_variants("https://www.sirialab.it/"), ["https://sirialab.it/", "http://www.sirialab.it/"])
        self.assertEqual(netguard.host_variants("http://example.com/x"), ["http://www.example.com/x"])
        self.assertEqual(netguard.host_variants("https://93.184.216.34/"), [])

    def test_dns_failure_raises_a_specific_clear_error(self):
        import socket
        with mock.patch("apps.outbound.netguard.socket.getaddrinfo", side_effect=socket.gaierror):
            with self.assertRaises(netguard.HostNotFound) as cm:
                netguard.validate_url("https://nonexistent-site-xyz.com/")
        self.assertIn("nonexistent-site-xyz.com", str(cm.exception))
        self.assertIsInstance(netguard.HostNotFound("x"), netguard.UnsafeURL)

    def test_www_that_does_not_resolve_falls_back_to_the_bare_domain(self):
        calls = []

        def fake_fetch(url, *a, **k):
            calls.append(url)
            if "://www." in url:
                raise netguard.HostNotFound("no dns")
            return fetched(url)
        with mock.patch("apps.outbound.audit.netguard.fetch", side_effect=fake_fetch):
            a = run_audit("http://www.sirialab.it/", "free", check_internal=False)
        self.assertTrue(a.reachable, a.error)
        self.assertEqual(a.url, "http://sirialab.it/")
        self.assertEqual(calls[0], "http://www.sirialab.it/")

    def test_when_every_variant_fails_the_message_names_what_was_tried(self):
        with mock.patch("apps.outbound.audit.netguard.fetch", side_effect=netguard.HostNotFound("no dns")):
            a = run_audit("https://www.sirialab.it/", "free", check_internal=False)
        self.assertFalse(a.reachable)
        self.assertIn("sirialab.it", a.error)
        self.assertIn("www.sirialab.it", a.error)
        self.assertIn("none of these addresses resolve", a.error)

    def test_private_addresses_are_still_blocked_and_never_retried(self):
        with mock.patch("apps.outbound.audit.netguard.fetch", side_effect=netguard.UnsafeURL("Only public websites can be checked.")) as f:
            a = run_audit("http://127.0.0.1/", "free", check_internal=False)
        self.assertEqual(f.call_count, 1)
        self.assertIn("public websites", a.error)


class WebsiteInEmailsAndProposals(Base):
    def setUp(self):
        super().setUp()
        self.cfg = OutboundSettings.load()
        self.p = Prospect.objects.create(business_name="Siria Lab", website="https://sirialab.it/", email="info@sirialab.it", country="Italy")

    def test_outreach_email_names_the_prospects_website_when_enabled(self):
        self.assertIn("Website reviewed: https://sirialab.it/", pitch.links_block(self.p, self.cfg))
        self.cfg.include_prospect_site = False
        self.assertNotIn("Website reviewed", pitch.links_block(self.p, self.cfg))

    def test_final_text_still_ends_with_unsubscribe_footer(self):
        txt = pitch.final_text(self.p, "Hello", self.cfg)
        self.assertIn("Website reviewed", txt)
        self.assertIn("Unsubscribe", txt)

    def test_no_website_line_when_prospect_has_none(self):
        self.p.website = ""
        self.assertNotIn("Website reviewed", pitch.links_block(self.p, self.cfg))

    def test_proposal_form_prefills_and_saves_client_website_and_shows_it_publicly_and_in_email(self):
        self.login(self.root)
        r = self.client.get(f"/dashboard/proposals/new/?prospect={self.p.pk}")
        self.assertContains(r, "https://sirialab.it/")
        r = self.client.post("/dashboard/proposals/new/", {"title": "Site", "client_name": "Siria", "client_company": "Siria Lab", "client_email": "info@sirialab.it", "client_website": "https://sirialab.it/",
                                                          "currency": "USD", "discount": "0", "tax_percent": "0", "item_desc": ["Build"], "item_detail": [""], "item_qty": ["1"], "item_price": ["500"], "item_service": [""]})
        pr = Proposal.objects.get(client_name="Siria")
        self.assertEqual(pr.client_website, "https://sirialab.it/")
        pr.status = Proposal.SENT
        pr.save()
        self.assertContains(self.client.get(pr.public_path), "Website: https://sirialab.it/")
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(f"/dashboard/proposals/{pr.pk}/action/", {"action": "send"})
        self.assertIn("Website this proposal is about: https://sirialab.it/", mail.outbox[-1].body)

    def test_duplicating_a_proposal_keeps_the_website(self):
        pr = Proposal.objects.create(title="A", client_name="X", client_website="https://x.test", client_email="x@x.test")
        ProposalItem.objects.create(proposal=pr, description="d", quantity=1, unit_price=10)
        self.login(self.root)
        self.client.post(f"/dashboard/proposals/{pr.pk}/action/", {"action": "duplicate"})
        self.assertEqual(Proposal.objects.exclude(pk=pr.pk).get().client_website, "https://x.test")


class ConfirmationAndStaffAlerts(Base):
    def lead_payload(self, **kw):
        d = {"name": "Sara Ali", "email": "sara@client.test", "phone": "3001234567", "countryCode": "+92", "service": "Web Design", "budget": "$1,500 - $3,000", "message": "Please build a new website for my clinic", "formToken": old_token(), "source": "contact_form", "consent": True}
        d.update(kw)
        return json.dumps(d)

    def setUp(self):
        super().setUp()
        from apps.cms.models import Service
        Service.objects.create(title="Web Design", status="published", short_description="x")

    def post_lead(self, **kw):
        return self.client.post("/api/v1/leads/", self.lead_payload(**kw), content_type="application/json")

    def test_contact_form_notifies_admin_by_dashboard_and_email_and_confirms_to_the_visitor(self):
        from apps.mailer.models import EmailSettings
        es = EmailSettings.load()
        es.notification_recipients = "owner@aub.test"
        es.save()
        with self.captureOnCommitCallbacks(execute=True):
            r = self.post_lead()
        self.assertIn(r.status_code, (200, 201), r.content)
        lead = Lead.objects.get(email="sara@client.test")
        self.assertTrue(self.root.notifications.filter(title__startswith="New lead").exists())
        to_admin = [m for m in mail.outbox if "owner@aub.test" in m.to]
        self.assertTrue(to_admin and lead.reference in to_admin[0].subject)
        to_visitor = [m for m in mail.outbox if m.to == ["sara@client.test"]]
        self.assertEqual(len(to_visitor), 1)
        self.assertIn(lead.reference, to_visitor[0].subject)
        self.assertIn("Sara", to_visitor[0].body)

    def test_no_confirmation_without_consent_when_consent_is_required(self):
        from apps.leads.models import LeadFormConfig
        c = LeadFormConfig.load()
        c.consent_required = True
        c.save()
        with self.captureOnCommitCallbacks(execute=True):
            self.post_lead(consent=False)
        self.assertFalse([m for m in mail.outbox if m.to == ["sara@client.test"]])

    def test_double_submit_sends_only_one_confirmation(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.post_lead()
            self.post_lead()
        self.assertEqual(len([m for m in mail.outbox if m.to == ["sara@client.test"]]), 1)

    def test_slow_lead_and_overdue_follow_up_also_email_the_team(self):
        from apps.mailer.models import EmailSettings
        es = EmailSettings.load()
        es.notification_recipients = "owner@aub.test"
        es.save()
        lead = Lead.objects.create(name="Late", email="late@client.test", message="help", consent_given=True)
        Lead.objects.filter(pk=lead.pk).update(created_at=timezone.now() - timedelta(minutes=45))
        other = Lead.objects.create(name="Due", email="due@client.test", message="help", status="contacted", follow_up_at=timezone.now() - timedelta(hours=1), follow_up_note="Call back")
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            services.check_overdue()
            services.check_overdue()  # second run must not repeat
        subjects = [m.subject for m in mail.outbox if "owner@aub.test" in m.to]
        self.assertEqual(len([s for s in subjects if s.startswith("[ACTION] No reply yet")]), 1)
        self.assertEqual(len([s for s in subjects if s.startswith("Follow-up due")]), 1)

    def test_report_opened_emails_the_team_once(self):
        from apps.mailer.models import EmailSettings
        es = EmailSettings.load()
        es.notification_recipients = "owner@aub.test"
        es.save()
        p = Prospect.objects.create(business_name="Siria Lab", website="https://sirialab.it/", email="info@sirialab.it")
        from apps.outbound.models import SiteAudit
        SiteAudit.objects.create(kind="prospect", prospect=p, url="https://sirialab.it/", reachable=True, score=40, findings=[])
        with self.captureOnCommitCallbacks(execute=True):
            self.client.get(f"/r/{p.token}/", HTTP_USER_AGENT="Mozilla/5.0 Chrome")
            self.client.get(f"/r/{p.token}/", HTTP_USER_AGENT="Mozilla/5.0 Chrome")
        self.assertEqual(len([m for m in mail.outbox if "owner@aub.test" in m.to and "opened their audit report" in m.subject]), 1)

    def test_staff_email_failure_never_breaks_the_request(self):
        with mock.patch("apps.mailer.service.notify_staff_by_email", side_effect=RuntimeError("boom")):
            self.assertIsNone(services.staff_email("x", "y"))
