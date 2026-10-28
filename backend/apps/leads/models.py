from django.conf import settings
from django.db import IntegrityError, models, transaction
from django.utils import timezone

from apps.core.models import SingletonModel, TimeStamped


class BudgetOption(TimeStamped):
    label = models.CharField(max_length=80, help_text="Shown to visitors, e.g. “$1,500 – $3,000”.")
    value = models.CharField(max_length=80, help_text="Stored with the lead. Usually the same as the label.")
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.label


class LeadFormConfig(SingletonModel, TimeStamped):
    require_phone = models.BooleanField(default=True)
    require_service = models.BooleanField(default=True)
    require_budget = models.BooleanField(default=True)
    use_services_as_options = models.BooleanField("Use published Services as the service list", default=True)
    extra_service_options = models.TextField("Extra service options", blank=True, help_text="One per line, added after the services (e.g. “Other / Not sure yet”).")
    placeholder_name = models.CharField(max_length=80, default="Your full name")
    placeholder_email = models.CharField(max_length=80, default="you@company.com")
    placeholder_phone = models.CharField(max_length=80, default="3XX XXXXXXX")
    placeholder_message = models.CharField(max_length=160, default="Tell us about your project, goals and timeline…")
    consent_required = models.BooleanField("Require privacy consent checkbox", default=False)
    consent_text = models.CharField(max_length=300, blank=True, default="I agree to be contacted about my enquiry and to the privacy policy.")
    marketing_optin_enabled = models.BooleanField("Show optional marketing opt-in", default=False)
    marketing_optin_text = models.CharField(max_length=300, blank=True, default="Send me occasional news and offers from AUB SQUARE (you can unsubscribe at any time).")
    success_title = models.CharField(max_length=120, default="Request received!")
    success_message = models.CharField(max_length=400, default="Thank you — our team will reply within 24 hours.")
    error_message = models.CharField(max_length=300, default="We couldn't send your request. Please try again or message us on WhatsApp.")
    notification_recipients = models.TextField("Extra notification recipients", blank=True, help_text="One email per line, in addition to the default recipients in Email settings.")
    min_seconds_to_submit = models.PositiveSmallIntegerField(default=3, help_text="Submissions faster than this are treated as bots.")

    class Meta:
        verbose_name = "Contact form settings"

    def __str__(self):
        return "Contact form settings"

    def extra_recipients(self):
        return [e.strip() for e in self.notification_recipients.replace(",", "\n").splitlines() if e.strip()]


class Lead(TimeStamped):
    NEW, CONTACTED, QUALIFIED, PROPOSAL, WON, LOST, ARCHIVED = "new", "contacted", "qualified", "proposal", "won", "lost", "archived"
    STATUS_CHOICES = [(NEW, "New"), (CONTACTED, "Contacted"), (QUALIFIED, "Qualified"), (PROPOSAL, "Proposal Sent"), (WON, "Won"), (LOST, "Lost"), (ARCHIVED, "Archived")]
    CATEGORIES = [("website", "Website / development"), ("design", "Design & branding"), ("marketing", "Marketing & ads"), ("seo", "SEO"), ("other", "Other")]
    SOURCES = [("contact_form", "Contact form"), ("quote_modal", "Quote popup"), ("chatbot", "Chatbot"), ("manual", "Added manually"), ("email", "Inbound email"),
               ("outbound", "Outbound prospecting"), ("audit_tool", "Free website audit")]

    reference = models.CharField(max_length=20, unique=True, editable=False)
    name = models.CharField(max_length=120)
    email = models.EmailField(db_index=True)
    country_code = models.CharField(max_length=8, blank=True)
    phone = models.CharField(max_length=40, blank=True)
    service = models.ForeignKey("cms.Service", null=True, blank=True, on_delete=models.SET_NULL, related_name="leads")
    service_label = models.CharField(max_length=160, blank=True)
    budget = models.ForeignKey(BudgetOption, null=True, blank=True, on_delete=models.SET_NULL, related_name="leads")
    budget_label = models.CharField(max_length=120, blank=True, help_text="Snapshot of the option the visitor chose.")
    message = models.TextField(blank=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=NEW, db_index=True)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_leads")
    source = models.CharField(max_length=14, choices=SOURCES, default="contact_form")
    source_page = models.CharField(max_length=300, blank=True)
    utm_source = models.CharField(max_length=120, blank=True)
    utm_medium = models.CharField(max_length=120, blank=True)
    utm_campaign = models.CharField(max_length=160, blank=True)
    consent_given = models.BooleanField(default=False)
    marketing_consent = models.BooleanField(default=False)
    visitor_hash = models.CharField(max_length=32, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    content_hash = models.CharField(max_length=64, blank=True, db_index=True)
    is_spam = models.BooleanField(default=False, db_index=True)
    spam_reason = models.CharField(max_length=200, blank=True)
    last_contacted_at = models.DateTimeField(null=True, blank=True)
    follow_up_at = models.DateTimeField(null=True, blank=True, db_index=True)
    follow_up_note = models.CharField(max_length=300, blank=True)
    category = models.CharField(max_length=10, choices=CATEGORIES, default="other", db_index=True, help_text="Which kind of work this enquiry is about (website, design, marketing, SEO).")
    first_response_at = models.DateTimeField(null=True, blank=True, help_text="When our team first replied – used for response-time reporting.")
    speed_alerted_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["status", "-created_at"])]

    def __str__(self):
        return f"{self.reference} · {self.name}"

    @property
    def full_phone(self):
        return f"{self.country_code} {self.phone}".strip()

    @property
    def whatsapp_link(self):
        digits = "".join(ch for ch in f"{self.country_code}{self.phone}" if ch.isdigit())
        return f"https://wa.me/{digits}" if digits else ""

    @property
    def response_minutes(self):
        if self.first_response_at:
            return max(0, int((self.first_response_at - self.created_at).total_seconds() // 60))
        return None

    @property
    def follow_up_overdue(self):
        return bool(self.follow_up_at and self.follow_up_at < timezone.now() and self.status not in (self.WON, self.LOST, self.ARCHIVED))

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = self._next_reference()
        for attempt in range(5):
            try:
                with transaction.atomic():
                    return super().save(*args, **kwargs)
            except IntegrityError:
                if self.pk or attempt == 4:
                    raise
                self.reference = self._next_reference(offset=attempt + 1)

    @classmethod
    def _next_reference(cls, offset=0):
        prefix = f"AUB-{timezone.now():%y%m}-"
        last = cls.objects.filter(reference__startswith=prefix).order_by("-reference").values_list("reference", flat=True).first()
        n = int(last.split("-")[-1]) + 1 if last else 1
        return f"{prefix}{n + offset:04d}"


class LeadNote(models.Model):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="notes")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
