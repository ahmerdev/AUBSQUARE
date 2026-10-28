from django.conf import settings
from django.db import models

from apps.core.models import Publishable, SEOFields, TimeStamped, unique_slug

ICON_CHOICES = [(n, n) for n in ["Sparkles", "Palette", "Layout", "Code", "Share2", "Camera", "Megaphone", "Globe2", "Box", "PenTool",
                                 "BarChart3", "Smartphone", "Zap", "Layers", "Film", "ShoppingBag", "Search", "Mail"]]


class SlugMixin(models.Model):
    slug = models.SlugField(max_length=160, unique=True, blank=True, help_text="Part of the page URL. Leave empty to generate from the title.")

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, getattr(self, "title", None) or getattr(self, "name", "item"))
        super().save(*args, **kwargs)


# ------------------------------------------------------------------ taxonomy
class ServiceCategory(SlugMixin, TimeStamped):
    name = models.CharField(max_length=80)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]
        verbose_name_plural = "service categories"

    def __str__(self):
        return self.name


class PortfolioCategory(SlugMixin, TimeStamped):
    name = models.CharField(max_length=80)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]
        verbose_name_plural = "portfolio categories"

    def __str__(self):
        return self.name


# ------------------------------------------------------------------ testimonials / faqs / team
class Testimonial(TimeStamped):
    client_name = models.CharField(max_length=100)
    role = models.CharField(max_length=100, blank=True)
    company = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=80, blank=True)
    avatar_url = models.CharField(max_length=500, blank=True)
    rating = models.PositiveSmallIntegerField(default=5)
    content = models.TextField()
    project_type = models.CharField(max_length=120, blank=True)
    featured = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "-created_at"]

    def __str__(self):
        return f"{self.client_name} – {self.company}"


class FAQ(TimeStamped):
    question = models.CharField(max_length=300)
    answer = models.TextField()
    group = models.CharField(max_length=30, default="general", help_text="Free label, e.g. general, pricing, process.")
    show_on_home = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "FAQ"

    def __str__(self):
        return self.question[:80]


class TeamMember(TimeStamped):
    name = models.CharField(max_length=100)
    role = models.CharField(max_length=120)
    bio = models.TextField(blank=True)
    photo_url = models.CharField(max_length=500, blank=True)
    photo_alt = models.CharField(max_length=200, blank=True)
    specialty = models.CharField(max_length=200, blank=True)
    linkedin_url = models.URLField(blank=True)
    twitter_url = models.URLField(blank=True)
    is_founder = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.name


# ------------------------------------------------------------------ services
class Service(SlugMixin, Publishable, SEOFields, TimeStamped):
    PRICE_CHOICES = [("none", "Don't show a price"), ("from", "Show “Starting from …”"), ("range", "Show a range"), ("custom", "Show custom text")]
    title = models.CharField(max_length=140)
    short_description = models.TextField()
    full_description = models.TextField(blank=True)
    icon_name = models.CharField(max_length=30, choices=ICON_CHOICES, default="Sparkles")
    cover_image = models.CharField(max_length=500, blank=True)
    cover_alt = models.CharField(max_length=200, blank=True)
    gallery = models.JSONField(default=list, blank=True, help_text="Image URLs")
    category = models.ForeignKey(ServiceCategory, null=True, blank=True, on_delete=models.SET_NULL, related_name="services")
    is_primary = models.BooleanField("Highlight as primary service", default=False)
    featured = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    deliverables = models.JSONField(default=list, blank=True)
    process = models.JSONField(default=list, blank=True, help_text="[{step,title,description}]")
    benefits = models.JSONField(default=list, blank=True)
    faqs = models.JSONField(default=list, blank=True, help_text="[{question,answer}]")
    price_display = models.CharField(max_length=8, choices=PRICE_CHOICES, default="none")
    price_label = models.CharField(max_length=80, blank=True, help_text="e.g. “$500” or “$500 – $2,000”")
    cta_label = models.CharField(max_length=60, blank=True, default="Request a quote")
    cta_url = models.CharField(max_length=300, blank=True, help_text="Empty = open the quote popup for this service.")
    related_projects = models.ManyToManyField("Project", blank=True, related_name="related_services")
    related_case_studies = models.ManyToManyField("CaseStudy", blank=True, related_name="related_services")

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.title


# ------------------------------------------------------------------ portfolio
class Project(SlugMixin, Publishable, SEOFields, TimeStamped):
    title = models.CharField(max_length=160)
    client_name = models.CharField(max_length=140, blank=True)
    show_client_name = models.BooleanField("Client has authorised showing their name", default=True)
    category = models.ForeignKey(PortfolioCategory, null=True, blank=True, on_delete=models.SET_NULL, related_name="projects")
    service = models.ForeignKey(Service, null=True, blank=True, on_delete=models.SET_NULL, related_name="projects")
    year = models.CharField(max_length=4, blank=True)
    completion_date = models.DateField(null=True, blank=True)
    thumbnail = models.CharField(max_length=500, blank=True)
    thumbnail_alt = models.CharField(max_length=200, blank=True)
    images = models.JSONField(default=list, blank=True, help_text="Gallery image URLs")
    summary = models.TextField()
    description = models.TextField("Project description", blank=True)
    challenge = models.TextField(blank=True)
    solution = models.TextField(blank=True)
    project_url = models.URLField("External project URL", blank=True)
    deliverables = models.JSONField(default=list, blank=True)
    services_provided = models.JSONField(default=list, blank=True)
    technologies = models.JSONField(default=list, blank=True)
    metrics = models.JSONField(default=list, blank=True, help_text="[{label,value}] – only real, verified results")
    testimonial = models.ForeignKey(Testimonial, null=True, blank=True, on_delete=models.SET_NULL, related_name="projects")
    featured = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "-completion_date", "id"]

    def __str__(self):
        return self.title


# ------------------------------------------------------------------ case studies
class CaseStudy(SlugMixin, Publishable, SEOFields, TimeStamped):
    title = models.CharField(max_length=200)
    client = models.CharField(max_length=140)
    industry = models.CharField(max_length=100, blank=True)
    category = models.CharField(max_length=140, blank=True, help_text="e.g. Brand Strategy & Visual Identity")
    hero_image = models.CharField(max_length=500, blank=True)
    hero_alt = models.CharField(max_length=200, blank=True)
    gallery = models.JSONField(default=list, blank=True)
    before_image = models.CharField(max_length=500, blank=True)
    after_image = models.CharField(max_length=500, blank=True)
    video_urls = models.JSONField(default=list, blank=True, help_text="YouTube / Vimeo URLs")
    summary = models.TextField()
    overview = models.TextField("Project overview", blank=True)
    challenge = models.TextField(blank=True)
    strategy = models.TextField(blank=True)
    solution = models.TextField(blank=True)
    implementation = models.TextField("Implementation details", blank=True)
    deliverables = models.JSONField(default=list, blank=True)
    results = models.JSONField(default=list, blank=True, help_text="[{label,value,change}] – genuine, client-approved results only")
    services = models.ManyToManyField(Service, blank=True, related_name="case_studies")
    related_projects = models.ManyToManyField(Project, blank=True, related_name="case_studies")
    testimonial = models.ForeignKey(Testimonial, null=True, blank=True, on_delete=models.SET_NULL, related_name="case_studies")
    cta_label = models.CharField(max_length=60, blank=True, default="Start a similar project")
    cta_url = models.CharField(max_length=300, blank=True)
    featured = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["order", "-created_at"]

    def __str__(self):
        return self.title


# ------------------------------------------------------------------ home page + about
class HomeSection(TimeStamped):
    key = models.SlugField(max_length=40, unique=True)
    label = models.CharField(max_length=80)
    order = models.PositiveIntegerField(default=0)
    is_visible = models.BooleanField(default=True)
    data = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.label


class AboutPage(TimeStamped, SEOFields):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    hero_eyebrow = models.CharField(max_length=100, blank=True)
    hero_title = models.CharField(max_length=200, blank=True)
    hero_description = models.TextField(blank=True)
    hero_image = models.CharField(max_length=500, blank=True)
    hero_image_alt = models.CharField(max_length=200, blank=True)
    story_title = models.CharField(max_length=200, blank=True)
    story_html = models.TextField("Company story", blank=True)
    mission = models.TextField(blank=True)
    vision = models.TextField(blank=True)
    values = models.JSONField(default=list, blank=True, help_text="[{title,description}]")
    differentiators = models.JSONField(default=list, blank=True, help_text="[{title,description}]")
    stats = models.JSONField(default=list, blank=True, help_text="[{value,label}] – real figures only")
    cta_title = models.CharField(max_length=200, blank=True)
    cta_text = models.TextField(blank=True)
    cta_label = models.CharField(max_length=60, blank=True)
    cta_url = models.CharField(max_length=300, blank=True)

    class Meta:
        verbose_name = "About page"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        return cls.objects.get_or_create(pk=1)[0]

    def __str__(self):
        return "About page"
