import secrets
from urllib.parse import urlsplit

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.crypto import decrypt, encrypt
from apps.core.models import SingletonModel, TimeStamped

LEVELS = [("high", "High"), ("medium", "Medium"), ("low", "Low"), ("unknown", "Not scored")]

CATEGORIES = [
    ("restaurant", "Restaurant / café"), ("dental", "Dental"), ("fitness", "Fitness / gym"), ("real_estate", "Real estate"),
    ("ecommerce", "Shop / e-commerce"), ("healthcare", "Healthcare"), ("legal", "Legal"), ("hospitality", "Hotels / hospitality"),
    ("automotive", "Automotive"), ("home_services", "Home services"), ("manufacturing", "Manufacturing"), ("other", "Other"),
]
ORDERING_CATEGORIES = {"restaurant", "ecommerce"}
BOOKING_CATEGORIES = {"dental", "healthcare", "fitness", "real_estate", "legal", "hospitality", "home_services", "automotive"}

# rule key -> (label, default points). Editable in Outbound settings.
SCORE_RULES = {
    "no_whatsapp": ("No WhatsApp / instant-chat button", 15),
    "no_ordering": ("No online ordering (food & shops only)", 20),
    "no_booking": ("No online booking (service businesses only)", 15),
    "weak_seo": ("Missing page title, meta description or H1", 15),
    "no_ssl": ("Website not secure (no valid HTTPS)", 15),
    "broken_links": ("Broken internal links found", 10),
    "not_mobile": ("Not mobile friendly (no viewport tag)", 10),
    "slow": ("Slow first response (over 3 seconds)", 5),
    "no_contact_form": ("No contact form or email on the page", 5),
}


def new_token(n=24):
    return secrets.token_urlsafe(n)


def domain_of(url: str) -> str:
    if not url:
        return ""
    try:
        host = (urlsplit(url if "://" in url else "https://" + url).hostname or "").lower()
    except ValueError:
        return ""
    return host[4:] if host.startswith("www.") else host


class OutboundSettings(SingletonModel, TimeStamped):
    REGION_MODES = [("allow_list", "Cold email only to the countries listed below"), ("manual_only", "Never send cold email – I contact prospects myself")]
    daily_email_limit = models.PositiveSmallIntegerField(default=30, help_text="Maximum cold emails sent per day (all prospects together).")
    require_approval = models.BooleanField(default=True, help_text="Every outreach message must be approved by a person before it is sent. Strongly recommended.")
    region_mode = models.CharField(max_length=12, choices=REGION_MODES, default="allow_list")
    allowed_countries = models.TextField(default="Pakistan\nUnited Arab Emirates\nSaudi Arabia\nUnited States",
                                         help_text="One country per line. Cold email is blocked for prospects in any other country (WhatsApp links still work). This is a safety setting, not legal advice – check the rules for the countries you target.")
    include_report_link = models.BooleanField("Add the prospect's own audit report link to emails", default=True, help_text="A private page showing their score and what to fix. Only added when their website was audited.")
    include_portfolio_link = models.BooleanField("Add a link to your portfolio", default=True, help_text="Points to /portfolio on your website.")
    include_site_link = models.BooleanField("Add a link to your website", default=True)
    include_prospect_site = models.BooleanField("Mention the prospect's own website address", default=True, help_text="Adds a line like \"Website reviewed: https://their-site.com\" so it is clear which website the message is about.")
    sender_business = models.CharField("Business name in emails", max_length=120, default="AUB SQUARE")
    sender_name = models.CharField("Your name in emails", max_length=80, blank=True)
    postal_address = models.CharField("Business postal address", max_length=240, blank=True, help_text="Shown in every outreach email footer (required by anti-spam laws in many countries). Outreach is blocked until this is filled in.")
    whatsapp_number = models.CharField("Your WhatsApp number", max_length=30, blank=True, help_text="With country code. Used for click-to-chat links only; nothing is sent automatically.")
    ai_enabled = models.BooleanField("Use Gemini to write pitches", default=False)
    gemini_key_enc = models.TextField(blank=True, editable=False)
    gemini_model = models.CharField(max_length=60, default="gemini-1.5-flash")
    # speed to lead
    speed_alert_minutes = models.PositiveSmallIntegerField(default=15, help_text="Warn the team when a new lead has had no reply for this many minutes.")
    auto_reply_enabled = models.BooleanField("Send an instant acknowledgement to new website leads", default=True, help_text="The visitor gets a short \"we received your request\" email with their reference number (only if they gave consent).")
    auto_reply_subject = models.CharField(max_length=160, default="We got your message – {name}")
    auto_reply_body = models.TextField(default="Hi {name},\n\nThanks for contacting {business}. We have received your request ({reference}) and a member of our team will reply personally very soon.\n\n{business}")
    # follow-ups
    follow_up_days = models.CharField(max_length=40, default="3,7", help_text="Days after the first email to draft follow-ups, e.g. 3,7")
    proposal_reminder_days = models.PositiveSmallIntegerField(default=3, help_text="Remind the team when a sent proposal has had no response after this many days.")
    proposal_valid_days = models.PositiveSmallIntegerField(default=14)
    currency = models.CharField(max_length=3, default="USD")
    score_weights = models.JSONField(default=dict, blank=True)
    last_run_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Outbound settings"

    def __str__(self):
        return "Outbound settings"

    def set_gemini_key(self, raw):
        self.gemini_key_enc = encrypt(raw)

    def get_gemini_key(self):
        return decrypt(self.gemini_key_enc)

    @property
    def has_gemini_key(self):
        return bool(self.gemini_key_enc)

    def weight(self, key):
        w = (self.score_weights or {}).get(key)
        try:
            return max(0, min(50, int(w)))
        except (TypeError, ValueError):
            return SCORE_RULES[key][1]

    def allowed_country_set(self):
        return {c.strip().lower() for c in self.allowed_countries.splitlines() if c.strip()}

    def follow_up_offsets(self):
        out = []
        for part in self.follow_up_days.split(","):
            part = part.strip()
            if part.isdigit() and 0 < int(part) <= 60:
                out.append(int(part))
        return sorted(set(out))[:4]


class Prospect(TimeStamped):
    NEW, AUDITED, CONTACTED, REPLIED, CONVERTED, REJECTED, SUPPRESSED = "new", "audited", "contacted", "replied", "converted", "rejected", "suppressed"
    STATUS = [(NEW, "New"), (AUDITED, "Audited"), (CONTACTED, "Contacted"), (REPLIED, "Replied"), (CONVERTED, "Became a lead"), (REJECTED, "Not a fit"), (SUPPRESSED, "Do not contact")]
    SOURCES = [("osm", "OpenStreetMap search"), ("csv", "CSV import"), ("manual", "Added manually"), ("legacy", "Imported from LeadRadar")]
    business_name = models.CharField(max_length=200)
    category = models.CharField(max_length=16, choices=CATEGORIES, default="other", db_index=True)
    website = models.CharField(max_length=500, blank=True)
    domain = models.CharField(max_length=200, blank=True, db_index=True, editable=False)
    email = models.EmailField(blank=True, db_index=True)
    email_source = models.CharField(max_length=40, blank=True, help_text="Where the email address was found (e.g. the contact page URL).")
    phone = models.CharField(max_length=60, blank=True)
    whatsapp = models.CharField(max_length=40, blank=True)
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=80, blank=True, db_index=True)
    address = models.CharField(max_length=300, blank=True)
    source = models.CharField(max_length=8, choices=SOURCES, default="manual")
    external_id = models.CharField(max_length=100, blank=True, db_index=True, editable=False)
    status = models.CharField(max_length=10, choices=STATUS, default=NEW, db_index=True)
    opportunity_score = models.PositiveSmallIntegerField(default=0)
    opportunity_level = models.CharField(max_length=8, choices=LEVELS, default="unknown", db_index=True)
    notes = models.TextField(blank=True)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    lead = models.OneToOneField("leads.Lead", null=True, blank=True, on_delete=models.SET_NULL, related_name="prospect")
    token = models.CharField(max_length=40, unique=True, editable=False)
    report_views = models.PositiveIntegerField(default=0, editable=False)
    report_first_opened_at = models.DateTimeField(null=True, blank=True, editable=False)
    last_contacted_at = models.DateTimeField(null=True, blank=True)
    replied_at = models.DateTimeField(null=True, blank=True)
    next_follow_up_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["-opportunity_score", "-created_at"]

    def __str__(self):
        return self.business_name

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = new_token()
        self.domain = domain_of(self.website)
        self.email = (self.email or "").strip().lower()
        super().save(*args, **kwargs)

    @property
    def whatsapp_link(self):
        digits = "".join(ch for ch in (self.whatsapp or self.phone) if ch.isdigit())
        return f"https://wa.me/{digits}" if len(digits) >= 8 else ""

    @property
    def latest_audit(self):
        return self.audits.first()


class ProspectNote(models.Model):
    prospect = models.ForeignKey(Prospect, on_delete=models.CASCADE, related_name="activity")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    kind = models.CharField(max_length=20, default="note")
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class SiteAudit(TimeStamped):
    KINDS = [("prospect", "Prospect"), ("own", "Our own website"), ("free", "Free audit tool")]
    kind = models.CharField(max_length=8, choices=KINDS, default="prospect", db_index=True)
    prospect = models.ForeignKey(Prospect, null=True, blank=True, on_delete=models.CASCADE, related_name="audits")
    url = models.CharField(max_length=500)
    final_url = models.CharField(max_length=500, blank=True)
    reachable = models.BooleanField(default=False)
    status_code = models.PositiveSmallIntegerField(default=0)
    error = models.CharField(max_length=300, blank=True)
    load_seconds = models.FloatField(default=0)
    is_https = models.BooleanField(default=False)
    ssl_ok = models.BooleanField(default=False)
    ssl_error = models.CharField(max_length=300, blank=True)
    has_viewport = models.BooleanField(default=False)
    title = models.CharField(max_length=300, blank=True)
    meta_description = models.CharField(max_length=400, blank=True)
    h1 = models.CharField(max_length=300, blank=True)
    has_canonical = models.BooleanField(default=False)
    has_open_graph = models.BooleanField(default=False)
    has_schema = models.BooleanField(default=False)
    images_total = models.PositiveIntegerField(default=0)
    images_missing_alt = models.PositiveIntegerField(default=0)
    has_whatsapp = models.BooleanField(default=False)
    whatsapp_link = models.CharField(max_length=300, blank=True)
    has_booking = models.BooleanField(default=False)
    has_ordering = models.BooleanField(default=False)
    has_form = models.BooleanField(default=False)
    emails_found = models.JSONField(default=list, blank=True)
    links_checked = models.PositiveSmallIntegerField(default=0)
    broken_links = models.JSONField(default=list, blank=True)
    score = models.PositiveSmallIntegerField(default=0)
    level = models.CharField(max_length=8, choices=LEVELS, default="unknown")
    findings = models.JSONField(default=list, blank=True, help_text="[{key,title,detail,points,service,category}]")
    public_token = models.CharField(max_length=40, unique=True, editable=False)
    requester_ip_hash = models.CharField(max_length=32, blank=True)
    lead = models.ForeignKey("leads.Lead", null=True, blank=True, on_delete=models.SET_NULL, related_name="audits")

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"Audit of {self.url}"

    def save(self, *args, **kwargs):
        if not self.public_token:
            self.public_token = new_token(18)
        super().save(*args, **kwargs)


class SuppressionEntry(TimeStamped):
    REASONS = [("unsubscribed", "Unsubscribed"), ("replied_stop", "Asked us to stop"), ("bounced", "Bounced"), ("complaint", "Complaint"), ("manual", "Added manually"), ("client", "Existing client")]
    email = models.EmailField(blank=True, db_index=True)
    domain = models.CharField(max_length=200, blank=True, db_index=True, help_text="Blocks every address at this domain.")
    reason = models.CharField(max_length=14, choices=REASONS, default="manual")
    note = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Do-not-contact list"

    def __str__(self):
        return self.email or self.domain

    def save(self, *args, **kwargs):
        self.email = (self.email or "").strip().lower()
        self.domain = (self.domain or "").strip().lower().removeprefix("www.")
        super().save(*args, **kwargs)


class OutreachTemplate(TimeStamped):
    KINDS = [("first", "First email"), ("follow_up", "Follow-up"), ("whatsapp", "WhatsApp message")]
    name = models.CharField(max_length=120)
    kind = models.CharField(max_length=10, choices=KINDS, default="first")
    category = models.CharField(max_length=16, choices=[("", "Any business type")] + CATEGORIES, blank=True)
    subject = models.CharField(max_length=200, blank=True, help_text="Placeholders: {business} {name} {city} {issue} {service} {score} {sender} {agency}")
    body = models.TextField(help_text="Same placeholders. Write it the way you would write to one person. {issue} is filled from the real audit findings.")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["kind", "name"]

    def __str__(self):
        return self.name


class Sequence(TimeStamped):
    name = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)
    description = models.CharField(max_length=240, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class SequenceStep(models.Model):
    sequence = models.ForeignKey(Sequence, on_delete=models.CASCADE, related_name="steps")
    order = models.PositiveSmallIntegerField(default=1)
    delay_days = models.PositiveSmallIntegerField(default=0, help_text="Days after the previous step.")
    template = models.ForeignKey(OutreachTemplate, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["sequence", "order"]


class OutreachMessage(TimeStamped):
    DRAFT, APPROVED, QUEUED, SENT, FAILED, SKIPPED = "draft", "approved", "queued", "sent", "failed", "skipped"
    STATUS = [(DRAFT, "Waiting for approval"), (APPROVED, "Approved"), (QUEUED, "Sending"), (SENT, "Sent"), (FAILED, "Failed"), (SKIPPED, "Skipped")]
    prospect = models.ForeignKey(Prospect, on_delete=models.CASCADE, related_name="messages")
    channel = models.CharField(max_length=8, choices=[("email", "Email"), ("whatsapp", "WhatsApp")], default="email")
    step = models.PositiveSmallIntegerField(default=1)
    subject = models.CharField(max_length=300, blank=True)
    body = models.TextField()
    status = models.CharField(max_length=8, choices=STATUS, default=DRAFT, db_index=True)
    generated_by = models.CharField(max_length=10, default="template", help_text="template or ai")
    block_reason = models.CharField(max_length=200, blank=True)
    email_message = models.ForeignKey("mailer.EmailMessage", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    approved_at = models.DateTimeField(null=True, blank=True)
    send_after = models.DateTimeField(null=True, blank=True, db_index=True)
    queued_at = models.DateTimeField(null=True, blank=True, db_index=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    error = models.CharField(max_length=300, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["-created_at", "-id"]


class SequenceEnrollment(TimeStamped):
    ACTIVE, DONE, STOPPED = "active", "done", "stopped"
    prospect = models.ForeignKey(Prospect, on_delete=models.CASCADE, related_name="enrollments")
    sequence = models.ForeignKey(Sequence, on_delete=models.CASCADE, related_name="enrollments")
    next_step = models.PositiveSmallIntegerField(default=1)
    next_at = models.DateTimeField(null=True, blank=True, db_index=True)
    status = models.CharField(max_length=7, default=ACTIVE, db_index=True)
    stop_reason = models.CharField(max_length=80, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["prospect", "sequence"], name="uniq_prospect_sequence")]


class Proposal(TimeStamped):
    DRAFT, SENT, VIEWED, ACCEPT_REQ, WON, DECLINED, EXPIRED = "draft", "sent", "viewed", "accept_requested", "won", "declined", "expired"
    STATUS = [(DRAFT, "Draft"), (SENT, "Sent"), (VIEWED, "Viewed"), (ACCEPT_REQ, "Client wants to go ahead"), (WON, "Won"), (DECLINED, "Declined"), (EXPIRED, "Expired")]
    reference = models.CharField(max_length=20, unique=True, editable=False)
    token = models.CharField(max_length=40, unique=True, editable=False)
    title = models.CharField(max_length=200)
    client_name = models.CharField(max_length=160)
    client_company = models.CharField(max_length=160, blank=True)
    client_email = models.EmailField(blank=True)
    client_website = models.CharField("Client website", max_length=300, blank=True, help_text="The website this proposal is about (shown on the proposal and in the email).")
    lead = models.ForeignKey("leads.Lead", null=True, blank=True, on_delete=models.SET_NULL, related_name="proposals")
    prospect = models.ForeignKey(Prospect, null=True, blank=True, on_delete=models.SET_NULL, related_name="proposals")
    status = models.CharField(max_length=16, choices=STATUS, default=DRAFT, db_index=True)
    currency = models.CharField(max_length=3, default="USD")
    intro = models.TextField(blank=True)
    scope = models.TextField(blank=True, help_text="What is included, timeline and how we work.")
    terms = models.TextField(blank=True, default="Payment: 50% to start, 50% on delivery. Prices exclude third-party costs (domains, hosting, ad spend). Valid until the date shown.")
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    valid_until = models.DateField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    first_viewed_at = models.DateTimeField(null=True, blank=True)
    last_viewed_at = models.DateTimeField(null=True, blank=True)
    view_count = models.PositiveIntegerField(default=0)
    responded_at = models.DateTimeField(null=True, blank=True)
    response_note = models.CharField(max_length=600, blank=True)
    responded_name = models.CharField(max_length=160, blank=True)
    reminder_sent_at = models.DateTimeField(null=True, blank=True)
    show_portfolio = models.ManyToManyField("cms.Project", blank=True, related_name="+")
    show_case_studies = models.ManyToManyField("cms.CaseStudy", blank=True, related_name="+")
    show_testimonials = models.ManyToManyField("cms.Testimonial", blank=True, related_name="+")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.reference} · {self.title}"

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = new_token(28)
        if not self.reference:
            prefix = f"PRP-{timezone.now():%y%m}-"
            last = Proposal.objects.filter(reference__startswith=prefix).order_by("-reference").values_list("reference", flat=True).first()
            self.reference = f"{prefix}{(int(last.split('-')[-1]) + 1) if last else 1:04d}"
        super().save(*args, **kwargs)

    @property
    def subtotal(self):
        return sum((i.total for i in self.items.all()), 0)

    @property
    def tax_amount(self):
        return round((self.subtotal - self.discount) * self.tax_percent / 100, 2)

    @property
    def total(self):
        return max(self.subtotal - self.discount, 0) + self.tax_amount

    @property
    def is_expired(self):
        return bool(self.valid_until and self.valid_until < timezone.localdate() and self.status in (self.SENT, self.VIEWED))

    @property
    def public_path(self):
        return f"/p/{self.token}/"


class ProposalItem(models.Model):
    proposal = models.ForeignKey(Proposal, on_delete=models.CASCADE, related_name="items")
    service = models.ForeignKey("cms.Service", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    description = models.CharField(max_length=300)
    detail = models.CharField(max_length=500, blank=True)
    quantity = models.DecimalField(max_digits=8, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    @property
    def total(self):
        return self.quantity * self.unit_price


class ProposalEvent(models.Model):
    proposal = models.ForeignKey(Proposal, on_delete=models.CASCADE, related_name="events")
    kind = models.CharField(max_length=20)  # created sent viewed accept_requested declined won reminder note
    detail = models.CharField(max_length=300, blank=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
