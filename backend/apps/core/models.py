import os
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from . import fonts


# ------------------------------------------------------------------ abstract helpers
class TimeStamped(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SingletonModel(models.Model):
    """Exactly one row (pk=1). Use Model.load()."""

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):  # never delete the singleton
        pass

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class SEOFields(models.Model):
    seo_title = models.CharField("SEO title", max_length=120, blank=True, help_text="Ideal: 50–60 characters.")
    meta_description = models.CharField(max_length=320, blank=True, help_text="Ideal: 120–160 characters.")
    canonical_url = models.URLField(blank=True, help_text="Leave empty to use the page's own URL.")
    og_title = models.CharField("Open Graph title", max_length=120, blank=True)
    og_description = models.CharField("Open Graph description", max_length=320, blank=True)
    og_image = models.CharField("Open Graph image URL", max_length=500, blank=True)
    noindex = models.BooleanField("Hide from search engines (noindex)", default=False)
    nofollow = models.BooleanField("Do not follow links (nofollow)", default=False)
    schema_json = models.JSONField("Structured data override (JSON-LD)", blank=True, null=True,
                                   help_text="Optional. Leave empty to generate it automatically.")

    class Meta:
        abstract = True


class PublishQuerySet(models.QuerySet):
    def live(self):
        now = timezone.now()
        return self.filter(
            models.Q(status="published") | models.Q(status="scheduled", publish_at__lte=now)
        )


class Publishable(models.Model):
    DRAFT, REVIEW, SCHEDULED, PUBLISHED = "draft", "review", "scheduled", "published"
    STATUS_CHOICES = [(DRAFT, "Draft"), (REVIEW, "In review"), (SCHEDULED, "Scheduled"), (PUBLISHED, "Published")]
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=DRAFT, db_index=True)
    publish_at = models.DateTimeField("Scheduled for", null=True, blank=True,
                                      help_text="Used with the Scheduled status: goes live automatically at this time.")
    published_at = models.DateTimeField(null=True, blank=True, editable=False)

    objects = PublishQuerySet.as_manager()

    class Meta:
        abstract = True

    @property
    def is_live(self) -> bool:
        if self.status == self.PUBLISHED:
            return True
        return self.status == self.SCHEDULED and bool(self.publish_at) and self.publish_at <= timezone.now()

    def save(self, *args, **kwargs):
        if self.status == self.PUBLISHED and not self.published_at:
            self.published_at = timezone.now()
        if self.status == self.SCHEDULED and self.publish_at and not self.published_at and self.publish_at <= timezone.now():
            self.published_at = self.publish_at
        super().save(*args, **kwargs)


def unique_slug(instance, source: str, field: str = "slug", max_len: int = 150) -> str:
    base = slugify(source)[:max_len] or "item"
    slug, i = base, 2
    Model = instance.__class__
    while Model.objects.filter(**{field: slug}).exclude(pk=instance.pk).exists():
        slug = f"{base[: max_len - 5]}-{i}"
        i += 1
    return slug


# ------------------------------------------------------------------ site-wide settings
class SiteSettings(SingletonModel, TimeStamped):
    site_name = models.CharField(max_length=80, default="AUB SQUARE")
    tagline = models.CharField(max_length=200, default="Creative agency for startups & small businesses")
    logo_url = models.CharField(max_length=500, blank=True)
    favicon_url = models.CharField(max_length=500, blank=True)
    primary_color = models.CharField(max_length=9, default="#EC008C")
    secondary_color = models.CharField(max_length=9, default="#7B2FFF")
    accent_color = models.CharField(max_length=9, default="#9333EA")
    background_color = models.CharField(max_length=9, default="#0B0B12")
    heading_font = models.CharField("Heading font", max_length=60, default=fonts.DEFAULT_HEADING, validators=[fonts.validate_font], help_text="Google Font used for headings on the website and in this dashboard.")
    body_font = models.CharField("Body / sub-text font", max_length=60, default=fonts.DEFAULT_BODY, validators=[fonts.validate_font], help_text="Google Font used for paragraphs, buttons and small text.")
    header_show_name = models.BooleanField("Show company name next to the logo in the header", default=False, help_text="Off = the header shows only the logo (the name is used as its accessible label).")

    contact_email = models.EmailField(blank=True)
    whatsapp_number = models.CharField(max_length=30, blank=True, help_text="Digits with country code, e.g. 923272755118")
    phone = models.CharField(max_length=40, blank=True)
    address = models.CharField(max_length=300, blank=True)
    business_hours = models.CharField(max_length=200, blank=True)

    facebook_url = models.URLField(blank=True)
    instagram_url = models.URLField(blank=True)
    linkedin_url = models.URLField(blank=True)
    twitter_url = models.URLField("X / Twitter URL", blank=True)
    youtube_url = models.URLField(blank=True)
    behance_url = models.URLField(blank=True)
    dribbble_url = models.URLField(blank=True)

    footer_text = models.TextField(blank=True)
    copyright_text = models.CharField(max_length=200, blank=True)
    cta_label = models.CharField("Primary CTA label", max_length=60, default="Get a Free Quote")
    cta_url = models.CharField("Primary CTA destination", max_length=300, default="#quote",
                               help_text="Use #quote to open the quote popup, or a URL/path.")

    default_seo_title = models.CharField(max_length=120, blank=True)
    default_meta_description = models.CharField(max_length=320, blank=True)
    default_og_image = models.CharField(max_length=500, blank=True)
    title_suffix = models.CharField(max_length=60, blank=True, default=" | AUB SQUARE")
    google_analytics_id = models.CharField("Google Analytics ID (G-XXXX)", max_length=40, blank=True)
    google_tag_manager_id = models.CharField(max_length=40, blank=True)
    facebook_pixel_id = models.CharField(max_length=40, blank=True)
    google_site_verification = models.CharField(max_length=120, blank=True)
    bing_site_verification = models.CharField(max_length=120, blank=True)
    robots_extra = models.TextField("Extra robots.txt lines", blank=True)

    cookie_notice_enabled = models.BooleanField(default=False)
    cookie_notice_text = models.CharField(max_length=400, blank=True, default="We use essential cookies to make this site work.")
    privacy_policy_url = models.CharField(max_length=300, blank=True)
    terms_url = models.CharField(max_length=300, blank=True)

    allow_staff_registration = models.BooleanField(
        default=True, help_text="Allow people to request a staff account. Requests stay 'Pending approval' until a Super Admin approves."
    )
    comment_blocklist = models.TextField(blank=True, help_text="One word/phrase per line. Comments containing these are held as spam.")

    class Meta:
        verbose_name = "Website settings"
        verbose_name_plural = "Website settings"

    def __str__(self):
        return "Website settings"


class NavItem(TimeStamped):
    HEADER, FOOTER_EXPLORE, FOOTER_SERVICES, FOOTER_LEGAL = "header", "footer_explore", "footer_services", "footer_legal"
    LOCATIONS = [(HEADER, "Header navigation"), (FOOTER_EXPLORE, "Footer – Explore"), (FOOTER_SERVICES, "Footer – Services"), (FOOTER_LEGAL, "Footer – Legal")]
    location = models.CharField(max_length=20, choices=LOCATIONS, default=HEADER, db_index=True)
    label = models.CharField(max_length=60)
    url = models.CharField(max_length=300, help_text="Path (/services) or full URL.")
    order = models.PositiveIntegerField(default=0)
    open_in_new_tab = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["location", "order", "id"]

    def __str__(self):
        return f"{self.get_location_display()}: {self.label}"


class AnnouncementBanner(TimeStamped):
    message = models.CharField(max_length=300)
    link_label = models.CharField(max_length=60, blank=True)
    link_url = models.CharField(max_length=300, blank=True)
    style = models.CharField(max_length=10, default="info", choices=[("info", "Info"), ("promo", "Promo"), ("warning", "Warning")])
    is_active = models.BooleanField(default=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    dismissible = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.message[:60]

    @classmethod
    def current(cls):
        now = timezone.now()
        return (
            cls.objects.filter(is_active=True)
            .filter(models.Q(starts_at__isnull=True) | models.Q(starts_at__lte=now))
            .filter(models.Q(ends_at__isnull=True) | models.Q(ends_at__gte=now))
            .first()
        )


# ------------------------------------------------------------------ audit + notifications
class ActivityLog(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="activity")
    actor_label = models.CharField(max_length=200, blank=True)
    action = models.CharField(max_length=60, db_index=True)  # e.g. user.approved, blog.published
    target_type = models.CharField(max_length=80, blank=True)
    target_id = models.CharField(max_length=40, blank=True)
    target_repr = models.CharField(max_length=200, blank=True)
    detail = models.CharField(max_length=500, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    is_security = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.action} by {self.actor_label or 'system'}"


class Notification(models.Model):
    KINDS = [
        ("lead", "Lead"), ("chat", "Chat"), ("comment", "Comment"), ("account", "Account"), ("email", "Email"),
        ("campaign", "Campaign"), ("security", "Security"), ("content", "Content"), ("system", "System"),
    ]
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    kind = models.CharField(max_length=12, choices=KINDS, default="system")
    level = models.CharField(max_length=8, default="info", choices=[("info", "Info"), ("success", "Success"), ("warning", "Warning"), ("danger", "Danger")])
    title = models.CharField(max_length=200)
    body = models.CharField(max_length=500, blank=True)
    url = models.CharField(max_length=300, blank=True)
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["recipient", "is_read"])]

    def __str__(self):
        return self.title


# ------------------------------------------------------------------ media library
def media_upload_path(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    now = timezone.now()
    return f"uploads/{now:%Y/%m}/{uuid.uuid4().hex}{ext}"


class MediaAsset(TimeStamped):
    IMAGE, DOCUMENT = "image", "document"
    file = models.FileField(upload_to=media_upload_path, max_length=300)
    title = models.CharField(max_length=200, blank=True)
    alt_text = models.CharField(max_length=250, blank=True, help_text="Describes the image for screen readers and SEO.")
    caption = models.CharField(max_length=300, blank=True)
    kind = models.CharField(max_length=10, default=IMAGE, choices=[(IMAGE, "Image"), (DOCUMENT, "Document")], db_index=True)
    mime_type = models.CharField(max_length=100, blank=True)
    size = models.PositiveIntegerField(default=0)
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    original_name = models.CharField(max_length=200, blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="uploads")

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return self.title or self.original_name or os.path.basename(self.file.name)

    @property
    def url(self):
        return self.file.url

    @property
    def ext(self):
        return os.path.splitext(self.file.name)[1].lstrip(".").upper()

    @property
    def download_name(self):
        """A friendly, filesystem-safe file name for downloads (original name, else the title) that keeps the real extension."""
        import re

        ext = os.path.splitext(self.file.name)[1].lower()
        base = os.path.splitext(self.original_name or self.title or "file")[0]
        base = re.sub(r"[^\w\-. ]+", "_", base).strip(" ._") or "file"
        return f"{base[:120]}{ext}"
