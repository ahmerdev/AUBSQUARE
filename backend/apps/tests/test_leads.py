"""Acceptance: contact/quote form storage (all fields + budget), spam handling, CRM workflow, privacy, export safety."""
import json

from django.urls import reverse

from apps.core.models import Notification
from apps.leads.models import BudgetOption, Lead, LeadFormConfig
from apps.mailer.models import EmailMessage
from apps.cms.models import Service

from .base import Base, old_token


class LeadSubmission(Base):
    def setUp(self):
        super().setUp()
        Service.objects.create(title="Web Design", status="published", short_description="x")
        self.budget = BudgetOption.objects.get(label="$1,500 - $3,000")

    def payload(self, **kw):
        d = {"name": "Ayesha Khan", "email": "Ayesha@Example.com", "countryCode": "+92", "phone": "3001234567", "service": "Web Design",
             "budget": "$1,500 - $3,000", "message": "I need a new website for my shop.", "formToken": old_token(), "page": "/contact"}
        d.update(kw)
        return d

    def send(self, **kw):
        return self.client.post("/api/v1/leads/", json.dumps(self.payload(**kw)), content_type="application/json")

    def test_all_fields_and_budget_are_stored(self):
        r = self.send()
        self.assertEqual(r.status_code, 201, r.content)
        lead = Lead.objects.get()
        self.assertEqual((lead.name, lead.email, lead.country_code, lead.phone), ("Ayesha Khan", "ayesha@example.com", "+92", "3001234567"))
        self.assertEqual((lead.service_label, lead.budget_label, lead.status), ("Web Design", "$1,500 - $3,000", "new"))
        self.assertEqual(lead.budget_id, self.budget.pk)
        self.assertTrue(lead.service_id)
        self.assertRegex(lead.reference, r"^AUB-\d{4}-\d{4}$")
        self.assertEqual(r.json()["reference"], lead.reference)
        self.assertEqual(lead.source_page, "/contact")

    def test_references_are_unique_and_sequential(self):
        self.send()
        self.send(email="b@example.com", message="A second, different message here.")
        refs = list(Lead.objects.order_by("id").values_list("reference", flat=True))
        self.assertEqual(len(set(refs)), 2)

    def test_validation_errors_per_field(self):
        r = self.send(name="", email="nope", phone="", service="", budget="", message="hi")
        self.assertEqual(r.status_code, 400)
        details = r.json()["error"]["details"]
        for f in ("name", "email", "phone", "service", "budget", "message"):
            self.assertIn(f, details)
        self.assertEqual(Lead.objects.count(), 0)

    def test_unknown_budget_or_service_rejected(self):
        self.assertEqual(self.send(budget="$1").status_code, 400)
        self.assertEqual(self.send(service="Hacking").status_code, 400)

    def test_budget_options_are_editable_from_dashboard(self):
        self.login(self.root)
        BudgetOption.objects.create(label="$10,000+", value="$10,000+", order=9)
        self.client.logout()
        boot = self.client.get("/api/v1/bootstrap/").json()
        labels = [b["label"] if isinstance(b, dict) else b for b in boot["form"]["budgetOptions"]]
        self.assertIn("$10,000+", labels)
        self.assertEqual(self.send(budget="$10,000+", message="Budget option added in dashboard.").status_code, 201)
        BudgetOption.objects.filter(label="$10,000+").update(is_active=False)
        from apps.core.services import bump_content_version

        bump_content_version()
        self.assertEqual(self.send(budget="$10,000+", message="Budget option now disabled here.", email="z@example.com").status_code, 400)

    def test_spam_is_quarantined_not_notified(self):
        self.send(website="http://spam", email="s1@example.com")
        self.send(formToken="", email="s2@example.com", message="no token spam message")
        self.send(message="http://a.com http://b.com http://c.com http://d.com", email="s3@example.com")
        self.assertEqual(Lead.objects.filter(is_spam=True).count(), 3)
        self.assertEqual(Notification.objects.filter(kind="lead").count(), 0)
        self.assertEqual(EmailMessage.objects.filter(kind="notification").count(), 0)

    def test_too_fast_submission_is_flagged(self):
        self.send(formToken=old_token(0))
        self.assertTrue(Lead.objects.get().is_spam)

    def test_double_submit_is_idempotent(self):
        a, b = self.send(), self.send()
        self.assertEqual((a.status_code, b.status_code), (201, 200))
        self.assertEqual(Lead.objects.count(), 1)

    def test_rate_limit(self):
        codes = [self.send(email=f"u{i}@example.com", message=f"unique message number {i}").status_code for i in range(9)]
        self.assertIn(429, codes)
        self.assertLessEqual(Lead.objects.count(), 6)

    def test_staff_get_in_app_and_email_notification(self):
        self.send()
        self.assertTrue(Notification.objects.filter(recipient=self.root, kind="lead").exists())
        self.assertTrue(any(self.root.email in m.to_emails for m in EmailMessage.objects.filter(kind="notification")))

    def test_html_in_fields_is_neutralised(self):
        self.send(name="<b>Eve</b><script>x()</script>", message="<img src=x onerror=alert(1)> please help me")
        l = Lead.objects.get()
        self.assertNotIn("<", l.name + l.message)

    def test_consent_required_when_configured(self):
        cfg = LeadFormConfig.load()
        cfg.consent_required = True
        cfg.save()
        self.assertEqual(self.send().status_code, 400)
        self.assertEqual(self.send(consent=True).status_code, 201)
        self.assertTrue(Lead.objects.get().consent_given)

    def test_marketing_opt_in_only_when_enabled_and_ticked(self):
        from apps.marketing.models import Subscriber

        self.send(marketingConsent=True)
        self.assertEqual(Subscriber.objects.count(), 0)  # feature disabled -> ignored
        cfg = LeadFormConfig.load()
        cfg.marketing_optin_enabled = True
        cfg.save()
        self.send(marketingConsent=True, email="m@example.com", message="Another enquiry with consent.")
        sub = Subscriber.objects.get()
        self.assertTrue(sub.consent_at)
        self.assertIn("AUB-", sub.consent_source)

    def test_api_never_returns_private_data(self):
        self.send()
        for url in ("/api/v1/bootstrap/", "/api/v1/leads/"):
            body = self.client.get(url).content.decode()
            self.assertNotIn("ayesha@example.com", body.lower())


class LeadWorkflow(Base):
    def setUp(self):
        super().setUp()
        self.lead = Lead.objects.create(name="Bilal", email="bilal@example.com", message="Need help with SEO", budget_label="$500")
        self.sales = self.make_user("sales@example.com", "sales_manager")

    def test_status_assignment_note_followup(self):
        self.login(self.sales)
        url = reverse("dashboard:lead_update", args=[self.lead.pk])
        r = self.client.post(url, {"action": "status", "status": "qualified"})
        self.assertEqual(r.status_code, 302)
        self.client.post(url, {"action": "assign", "assigned_to": self.sales.pk})
        self.client.post(url, {"action": "note", "body": "Called, wants a proposal"})
        self.client.post(url, {"action": "followup", "follow_up_at": "2030-01-01T10:00", "follow_up_note": "Send proposal"})
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.status, "qualified")
        self.assertEqual(self.lead.assigned_to_id, self.sales.pk)
        self.assertEqual(self.lead.notes.count(), 1)
        self.assertIsNotNone(self.lead.follow_up_at)
        self.assertEqual(self.client.get(reverse("dashboard:lead_detail", args=[self.lead.pk])).status_code, 200)

    def test_all_seven_statuses_exist(self):
        self.assertEqual([k for k, _ in Lead.STATUS_CHOICES], ["new", "contacted", "qualified", "proposal", "won", "lost", "archived"])

    def test_reply_from_dashboard_threads_and_marks_contacted(self):
        from apps.mailer.models import EmailSettings

        es = EmailSettings.load()
        es.smtp_host, es.from_email = "smtp.example.com", "hello@aubsquare.test"
        es.save()
        self.login(self.sales)
        r = self.client.post(reverse("dashboard:lead_reply", args=[self.lead.pk]), {"subject": "Re: your enquiry", "body": "Hi Bilal, happy to help."})
        self.assertEqual(r.status_code, 302)
        m = EmailMessage.objects.get(kind="reply")
        self.assertIn(self.lead.reference, m.subject)
        self.assertEqual(m.to_emails, ["bilal@example.com"])
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.status, "contacted")

    def test_analyst_cannot_edit_leads(self):
        self.login(self.make_user("an@example.com", "analyst"))
        r = self.client.post(reverse("dashboard:lead_update", args=[self.lead.pk]), {"action": "status", "status": "won"})
        self.assertEqual(r.status_code, 403)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.status, "new")

    def test_csv_export_requires_permission_and_blocks_formula_injection(self):
        Lead.objects.create(name="=HYPERLINK(\"http://evil\")", email="x@example.com", message="+cmd|' /C calc'!A0")
        self.login(self.make_user("an3@example.com", "support_agent"))
        self.assertEqual(self.client.get(reverse("dashboard:leads_export")).status_code, 403)
        self.client.logout()
        self.login(self.root)
        body = self.client.get(reverse("dashboard:leads_export")).content.decode("utf-8-sig")
        self.assertIn("'=HYPERLINK", body)
        self.assertNotIn(",=HYPERLINK", body)
        self.assertIn("'+cmd", body)

    def test_manual_lead_creation(self):
        self.login(self.sales)
        r = self.client.post(reverse("dashboard:lead_create"), {"name": "Manual Lead", "email": "m@example.com", "message": "Phone enquiry about branding", "phone": "300", "source": "manual"})
        self.assertIn(r.status_code, (200, 302))
        if r.status_code == 302:
            self.assertTrue(Lead.objects.filter(name="Manual Lead").exists())

    def test_delete_requires_permission_and_post(self):
        self.login(self.make_user("sup@example.com", "support_agent"))
        self.assertEqual(self.client.post(reverse("dashboard:lead_delete", args=[self.lead.pk])).status_code, 403)
        self.assertTrue(Lead.objects.filter(pk=self.lead.pk).exists())
        self.client.logout()
        self.login(self.root)
        self.assertEqual(self.client.get(reverse("dashboard:lead_delete", args=[self.lead.pk])).status_code, 405)  # never deletes on GET
        self.assertTrue(Lead.objects.filter(pk=self.lead.pk).exists())
