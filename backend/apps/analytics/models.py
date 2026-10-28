from django.db import models


class PageView(models.Model):
    """First-party, cookie-less page view. No raw IP / user-agent is stored."""
    path = models.CharField(max_length=300, db_index=True)
    referrer_domain = models.CharField(max_length=200, blank=True)
    utm_source = models.CharField(max_length=120, blank=True)
    utm_medium = models.CharField(max_length=120, blank=True)
    utm_campaign = models.CharField(max_length=160, blank=True, db_index=True)
    device = models.CharField(max_length=8, default="desktop")
    visitor = models.CharField(max_length=32, db_index=True)  # daily-rotating hash
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [models.Index(fields=["created_at", "path"])]
