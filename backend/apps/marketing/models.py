from django.conf import settings
from django.db import models

from apps.core.crypto import decrypt, encrypt
from apps.core.models import TimeStamped


class Campaign(TimeStamped):
    CHANNELS = [("google_ads", "Google Ads"), ("meta_ads", "Meta Ads"), ("email", "Email campaign"), ("organic", "Organic / SEO / social"), ("other", "Other")]
    STATUS = [("draft", "Draft"), ("pending_approval", "Pending approval"), ("approved", "Approved"), ("active", "Active"), ("paused", "Paused"), ("completed", "Completed"), ("cancelled", "Cancelled")]
    name = models.CharField(max_length=160)
    objective = models.CharField(max_length=200, blank=True)
    channel = models.CharField(max_length=12, choices=CHANNELS, default="organic", db_index=True)
    status = models.CharField(max_length=16, choices=STATUS, default="draft", db_index=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    budget = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default="USD")
    landing_page_url = models.CharField(max_length=400, blank=True)
    utm_source = models.CharField(max_length=80, blank=True)
    utm_medium = models.CharField(max_length=80, blank=True)
    utm_campaign = models.CharField(max_length=120, blank=True)
    utm_term = models.CharField(max_length=120, blank=True)
    utm_content = models.CharField(max_length=120, blank=True)
    audience_notes = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="campaigns")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    approved_at = models.DateTimeField(null=True, blank=True)
    external_id = models.CharField(max_length=120, blank=True, help_text="ID in the ad platform – only set by a real integration.")
    platform_linked = models.BooleanField(default=False, editable=False, help_text="True only when an official ad-platform integration manages this campaign.")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    @property
    def tracking_url(self):
        from urllib.parse import urlencode

        if not self.landing_page_url:
            return ""
        params = {k: v for k, v in {"utm_source": self.utm_source, "utm_medium": self.utm_medium, "utm_campaign": self.utm_campaign,
                                    "utm_term": self.utm_term, "utm_content": self.utm_content}.items() if v}
        if not params:
            return self.landing_page_url
        sep = "&" if "?" in self.landing_page_url else "?"
        return f"{self.landing_page_url}{sep}{urlencode(params)}"


class CampaignMetric(models.Model):
    """Manually entered or imported results. Every row states where it came from."""
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="metrics")
    date = models.DateField()
    impressions = models.PositiveIntegerField(default=0)
    clicks = models.PositiveIntegerField(default=0)
    spend = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    conversions = models.PositiveIntegerField(default=0)
    data_source = models.CharField(max_length=12, default="manual", choices=[("manual", "Entered manually"), ("import", "Imported from platform")])
    note = models.CharField(max_length=200, blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-id"]


class CampaignNote(models.Model):
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="activity_notes")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    body = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class AdGroup(TimeStamped):
    STATUS = [("draft", "Draft"), ("active", "Active"), ("paused", "Paused")]
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="ad_groups")
    name = models.CharField(max_length=160)
    audience = models.CharField(max_length=300, blank=True)
    daily_budget = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=8, choices=STATUS, default="draft")

    class Meta:
        ordering = ["campaign", "name"]

    def __str__(self):
        return f"{self.campaign.name} / {self.name}"


class AdCreative(TimeStamped):
    APPROVAL = [("draft", "Draft"), ("pending", "Pending approval"), ("approved", "Approved"), ("rejected", "Rejected")]
    ad_group = models.ForeignKey(AdGroup, on_delete=models.CASCADE, related_name="creatives")
    headline = models.CharField(max_length=160)
    body_text = models.TextField(blank=True)
    cta_text = models.CharField(max_length=60, blank=True)
    landing_url = models.CharField(max_length=400, blank=True)
    image_url = models.CharField(max_length=500, blank=True)
    approval_status = models.CharField(max_length=10, choices=APPROVAL, default="draft")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.headline


class AdIntegration(TimeStamped):
    """Placeholder for an official ad-platform connection (Google Ads API / Meta Marketing API)."""
    PROVIDERS = [("google_ads", "Google Ads API"), ("meta_ads", "Meta Marketing API")]
    provider = models.CharField(max_length=12, choices=PROVIDERS, unique=True)
    account_id = models.CharField(max_length=80, blank=True)
    credentials_enc = models.TextField(blank=True, editable=False)
    is_connected = models.BooleanField(default=False, editable=False)
    last_checked_at = models.DateTimeField(null=True, blank=True)
    last_message = models.CharField(max_length=300, blank=True)

    def set_credentials(self, raw):
        self.credentials_enc = encrypt(raw)

    def get_credentials(self):
        return decrypt(self.credentials_enc)

    def __str__(self):
        return self.get_provider_display()


class Subscriber(TimeStamped):
    STATUS = [("subscribed", "Subscribed"), ("unsubscribed", "Unsubscribed"), ("bounced", "Bounced"), ("suppressed", "Suppressed")]
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=12, choices=STATUS, default="subscribed", db_index=True)
    consent_at = models.DateTimeField(null=True, blank=True)
    consent_source = models.CharField(max_length=120, blank=True, help_text="Where/how consent was given")
    unsubscribed_at = models.DateTimeField(null=True, blank=True)
    token = models.CharField(max_length=40, unique=True, editable=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        if not self.token:
            import secrets

            self.token = secrets.token_urlsafe(24)
        super().save(*args, **kwargs)


class EmailCampaign(TimeStamped):
    STATUS = [("draft", "Draft"), ("scheduled", "Scheduled"), ("sending", "Sending"), ("sent", "Sent"), ("cancelled", "Cancelled")]
    name = models.CharField(max_length=160)
    subject = models.CharField(max_length=200)
    preview_text = models.CharField(max_length=200, blank=True)
    body_html = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS, default="draft")
    scheduled_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    recipient_count = models.PositiveIntegerField(default=0, editable=False)
    campaign = models.ForeignKey(Campaign, null=True, blank=True, on_delete=models.SET_NULL, related_name="email_campaigns")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name
