import re

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from apps.cms.models import SlugMixin
from apps.core.models import Publishable, SEOFields, TimeStamped
from apps.core.sanitize import clean_html, strip_html


class Category(SlugMixin, TimeStamped):
    name = models.CharField(max_length=80)
    description = models.CharField(max_length=300, blank=True)
    order = models.PositiveIntegerField(default=0)
    seo_title = models.CharField(max_length=120, blank=True)
    meta_description = models.CharField(max_length=320, blank=True)

    class Meta:
        ordering = ["order", "name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class Tag(SlugMixin, TimeStamped):
    name = models.CharField(max_length=60)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


HEADING_RE = re.compile(r"<h([23])(\s[^>]*)?>(.*?)</h\1>", re.S | re.I)


class Post(SlugMixin, Publishable, SEOFields, TimeStamped):
    title = models.CharField(max_length=200)
    excerpt = models.TextField(max_length=500, blank=True)
    featured_image = models.CharField(max_length=500, blank=True)
    featured_alt = models.CharField(max_length=200, blank=True)
    gallery = models.JSONField(default=list, blank=True)
    content_html = models.TextField("Article content", blank=True)
    toc = models.JSONField(default=list, blank=True, editable=False)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="posts")
    author_name = models.CharField(max_length=100, blank=True, help_text="Overrides the account name if set.")
    author_role = models.CharField(max_length=140, blank=True)
    author_avatar = models.CharField(max_length=500, blank=True)
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.SET_NULL, related_name="posts")
    tags = models.ManyToManyField(Tag, blank=True, related_name="posts")
    reading_minutes = models.PositiveSmallIntegerField(default=1, editable=False)
    featured = models.BooleanField("Featured article", default=False)
    allow_comments = models.BooleanField(default=True)
    related_posts = models.ManyToManyField("self", blank=True, symmetrical=False)
    schema_type = models.CharField(max_length=20, default="BlogPosting", choices=[("BlogPosting", "BlogPosting"), ("Article", "Article"), ("NewsArticle", "NewsArticle")])
    display_date = models.DateTimeField(null=True, blank=True, help_text="Public date. Defaults to the publish date.")

    class Meta:
        ordering = ["-published_at", "-created_at"]
        indexes = [models.Index(fields=["status", "-published_at"])]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        html = clean_html(self.content_html)
        html, toc = self._add_heading_ids(html)
        self.content_html, self.toc = html, toc
        words = len(strip_html(html).split())
        self.reading_minutes = max(1, round(words / 220))
        if not self.excerpt and html:
            self.excerpt = strip_html(html)[:240].rsplit(" ", 1)[0]
        super().save(*args, **kwargs)

    @staticmethod
    def _add_heading_ids(html):
        toc, used = [], set()

        def repl(m):
            level, attrs, inner = m.group(1), m.group(2) or "", m.group(3)
            text = strip_html(inner).strip()
            base = slugify(text)[:60] or "section"
            hid, n = base, 2
            while hid in used:
                hid, n = f"{base}-{n}", n + 1
            used.add(hid)
            attrs = re.sub(r'\sid="[^"]*"', "", attrs)
            if level == "2":
                toc.append({"id": hid, "title": text})
            return f'<h{level}{attrs} id="{hid}">{inner}</h{level}>'

        return HEADING_RE.sub(repl, html), toc

    @property
    def public_date(self):
        return self.display_date or self.published_at or self.created_at

    @property
    def byline(self):
        return self.author_name or (self.author.display_name if self.author else "AUB SQUARE")


class Comment(TimeStamped):
    PENDING, APPROVED, REJECTED, SPAM = "pending", "approved", "rejected", "spam"
    STATUS = [(PENDING, "Pending"), (APPROVED, "Approved"), (REJECTED, "Rejected"), (SPAM, "Spam")]
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE, related_name="replies")
    name = models.CharField(max_length=80)
    email = models.EmailField()
    body = models.TextField(max_length=2000)
    status = models.CharField(max_length=10, choices=STATUS, default=PENDING, db_index=True)
    spam_reason = models.CharField(max_length=160, blank=True)
    visitor_hash = models.CharField(max_length=32, blank=True)
    moderated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    moderated_at = models.DateTimeField(null=True, blank=True)
    is_staff_reply = models.BooleanField(default=False)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["post", "status"])]

    def __str__(self):
        return f"{self.name}: {self.body[:50]}"
