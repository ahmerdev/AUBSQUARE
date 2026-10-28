from django.db import models

from apps.core.models import SEOFields, TimeStamped


class PageSEO(SEOFields, TimeStamped):
    CHANGEFREQ = [(c, c) for c in ["always", "hourly", "daily", "weekly", "monthly", "yearly", "never"]]
    path = models.CharField(max_length=300, unique=True, help_text="Public path, e.g. /about")
    label = models.CharField(max_length=120, blank=True)
    include_in_sitemap = models.BooleanField(default=True)
    priority = models.DecimalField(max_digits=2, decimal_places=1, default=0.7)
    changefreq = models.CharField(max_length=10, choices=CHANGEFREQ, default="monthly")

    class Meta:
        ordering = ["path"]
        verbose_name = "page SEO"
        verbose_name_plural = "page SEO"

    def __str__(self):
        return self.path


class Redirect(TimeStamped):
    from_path = models.CharField(max_length=300, unique=True, help_text="Old path, e.g. /blog/old-slug")
    to_path = models.CharField(max_length=500, help_text="New path or full URL")
    permanent = models.BooleanField("Permanent (301)", default=True)
    is_active = models.BooleanField(default=True)
    auto_created = models.BooleanField(default=False, editable=False)
    hit_count = models.PositiveIntegerField(default=0, editable=False)
    last_hit_at = models.DateTimeField(null=True, blank=True, editable=False)
    note = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.from_path} → {self.to_path}"


class InternalLink(TimeStamped):
    source_path = models.CharField(max_length=300, help_text="Page that contains the link")
    target_path = models.CharField(max_length=300)
    anchor_text = models.CharField(max_length=200)
    notes = models.CharField(max_length=300, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["source_path", "target_path"]

    def __str__(self):
        return f"{self.source_path} → {self.target_path}"


class Backlink(TimeStamped):
    TYPES = [("dofollow", "Dofollow"), ("nofollow", "Nofollow"), ("sponsored", "Sponsored"), ("ugc", "UGC")]
    STATUS = [("pending", "Pending"), ("active", "Active"), ("lost", "Lost"), ("broken", "Broken")]
    SOURCES = [("manual", "Entered manually"), ("verified", "Checked by this system"), ("import", "Imported from provider")]
    referring_domain = models.CharField(max_length=200)
    source_url = models.URLField(max_length=500, help_text="The page that links to us")
    target_url = models.CharField(max_length=500, help_text="Our page being linked to")
    anchor_text = models.CharField(max_length=200, blank=True)
    link_type = models.CharField(max_length=10, choices=TYPES, default="dofollow")
    status = models.CharField(max_length=8, choices=STATUS, default="pending")
    data_source = models.CharField(max_length=10, choices=SOURCES, default="manual")
    verified = models.BooleanField(default=False)
    last_checked_at = models.DateTimeField(null=True, blank=True)
    last_check_message = models.CharField(max_length=200, blank=True)
    notes = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        from urllib.parse import urlparse

        if self.source_url:
            self.referring_domain = (urlparse(self.source_url).hostname or self.referring_domain or "").replace("www.", "")[:200]
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.referring_domain} → {self.target_url}"
