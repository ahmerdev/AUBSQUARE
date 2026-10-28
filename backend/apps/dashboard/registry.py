"""Declarative registry that drives the generic list / create / edit / delete / export screens."""
from dataclasses import dataclass, field
from typing import Callable

from django.apps import apps as django_apps

SEO = ["seo_title", "meta_description", "canonical_url", "og_title", "og_description", "og_image", "noindex", "nofollow", "schema_json"]
PUBLISH = ["status", "publish_at"]
SEO_SET = ("SEO & social sharing", SEO)
PUBLISH_SET = ("Publishing", PUBLISH)

STEP_SPEC = [("step", "Step", "text"), ("title", "Title", "text"), ("description", "Description", "textarea")]
QA_SPEC = [("question", "Question", "text"), ("answer", "Answer", "textarea")]
TD_SPEC = [("title", "Title", "text"), ("description", "Description", "textarea")]
LV_SPEC = [("label", "Label", "text"), ("value", "Value", "text")]
RESULT_SPEC = [("label", "Label", "text"), ("value", "Value", "text"), ("change", "Change (optional)", "text")]
STAT_SPEC = [("value", "Value", "text"), ("label", "Label", "text")]


@dataclass
class Module:
    slug: str
    perm: str                      # permission module key
    model: str                     # "app_label.Model"
    title: str                     # plural title
    singular: str
    columns: list                  # (attr, label, kind)
    group: str = ""
    icon: str = "doc"
    search: list = field(default_factory=list)
    filters: list = field(default_factory=list)      # model field names
    fieldsets: list = field(default_factory=list)    # [(title, [fields])]
    types: dict = field(default_factory=dict)        # field -> media|rich|lines|json|("repeater", spec)|textarea
    ordering: list = field(default_factory=list)
    singleton: bool = False
    can_create: bool = True
    can_delete: bool = True
    status_field: str = ""
    help: str = ""
    export: list = field(default_factory=list)
    bulk: list = field(default_factory=list)         # [(key, label, perm)]
    preview: Callable = None                         # obj -> public path
    readonly: list = field(default_factory=list)
    defaults: dict = field(default_factory=dict)
    list_template: str = ""
    form_template: str = ""
    parent: str = ""                                 # breadcrumb parent label

    @property
    def Model(self):
        return django_apps.get_model(self.model)

    @property
    def form_fields(self):
        out = []
        for _, fields in self.fieldsets:
            out.extend(fields)
        return out


PUB_BULK = [("publish", "Publish", "publish"), ("draft", "Move to draft", "edit"), ("delete", "Delete", "delete")]
BASIC_BULK = [("delete", "Delete", "delete")]
PUB_FILTERS = ["status"]

REGISTRY: dict[str, Module] = {}


def register(m: Module):
    REGISTRY[m.slug] = m
    return m


# ---------------------------------------------------------------- Website pages (static page SEO)
register(Module(
    slug="pages", perm="pages", model="seo.PageSEO", title="Website pages", singular="page", icon="layers",
    columns=[("label", "Page", "title"), ("path", "URL", "text"), ("seo_title", "SEO title", "text"), ("noindex", "Hidden from search", "bool"), ("include_in_sitemap", "In sitemap", "bool")],
    search=["label", "path", "seo_title"], filters=["noindex", "include_in_sitemap"], ordering=["path"], export=["label", "path", "seo_title", "meta_description"],
    fieldsets=[("Page", ["label", "path"]), SEO_SET, ("Sitemap", ["include_in_sitemap", "priority", "changefreq"])],
    help="Search-engine titles, descriptions and sharing images for the fixed pages of the website. Page content itself is edited in Home page, About us and Services.",
    bulk=BASIC_BULK, preview=lambda o: o.path,
))

# ---------------------------------------------------------------- About us: team
register(Module(
    slug="team", perm="about", model="cms.TeamMember", title="Team & founders", singular="team member", icon="users", group="about",
    columns=[("photo_url", "", "image"), ("name", "Name", "title"), ("role", "Role", "text"), ("is_founder", "Founder", "bool"), ("is_published", "Visible", "bool"), ("order", "Order", "num")],
    search=["name", "role"], filters=["is_founder", "is_published"], ordering=["order", "name"],
    fieldsets=[("Profile", ["name", "role", "specialty", "bio", "photo_url", "photo_alt"]), ("Links", ["linkedin_url", "twitter_url"]), ("Display", ["is_founder", "is_published", "order"])],
    types={"photo_url": "media"}, bulk=BASIC_BULK, parent="About us",
))

# ---------------------------------------------------------------- Services
register(Module(
    slug="services", perm="services", model="cms.Service", title="Services", singular="service", icon="spark",
    columns=[("cover_image", "", "image"), ("title", "Title", "title"), ("category", "Category", "text"), ("status", "Status", "status"), ("featured", "Featured", "bool"), ("order", "Order", "num"), ("updated_at", "Updated", "date")],
    search=["title", "short_description"], filters=["status", "category", "featured"], ordering=["order", "title"], status_field="status",
    fieldsets=[
        ("Basics", ["title", "slug", "short_description", "full_description", "icon_name", "category"]),
        ("Media", ["cover_image", "cover_alt", "gallery"]),
        ("Details", ["deliverables", "process", "benefits", "faqs"]),
        ("Call to action & pricing", ["price_label", "price_display", "cta_label", "cta_url"]),
        ("Related content", ["related_projects", "related_case_studies"]),
        ("Display", ["is_primary", "featured", "order"]),
        PUBLISH_SET, SEO_SET,
    ],
    types={"cover_image": "media", "gallery": "lines", "deliverables": "lines", "benefits": "lines", "process": ("repeater", STEP_SPEC), "faqs": ("repeater", QA_SPEC), "short_description": "textarea:3", "full_description": "textarea:8"},
    bulk=PUB_BULK, export=["title", "slug", "status", "category", "updated_at"], preview=lambda o: f"/services/{o.slug}",
))

# ---------------------------------------------------------------- Portfolio
register(Module(
    slug="portfolio", perm="portfolio", model="cms.Project", title="Portfolio projects", singular="project", icon="grid",
    columns=[("thumbnail", "", "image"), ("title", "Title", "title"), ("category", "Category", "text"), ("year", "Year", "text"), ("status", "Status", "status"), ("featured", "Featured", "bool"), ("updated_at", "Updated", "date")],
    search=["title", "client_name", "summary"], filters=["status", "category", "service", "featured"], ordering=["order", "-created_at"], status_field="status",
    fieldsets=[
        ("Project", ["title", "slug", "client_name", "show_client_name", "category", "service", "year", "completion_date", "project_url"]),
        ("Media", ["thumbnail", "thumbnail_alt", "images"]),
        ("Story", ["summary", "description", "challenge", "solution"]),
        ("Delivery", ["deliverables", "services_provided", "technologies", "metrics"]),
        ("Testimonial", ["testimonial"]),
        ("Display", ["featured", "order"]),
        PUBLISH_SET, SEO_SET,
    ],
    types={"thumbnail": "media", "images": "lines", "deliverables": "lines", "services_provided": "lines", "technologies": "lines", "metrics": ("repeater", LV_SPEC),
           "summary": "textarea:3", "description": "textarea:6", "challenge": "textarea:5", "solution": "textarea:5"},
    bulk=PUB_BULK, export=["title", "slug", "client_name", "status", "year", "updated_at"], preview=lambda o: f"/portfolio/{o.slug}",
))

# ---------------------------------------------------------------- Case studies
register(Module(
    slug="case-studies", perm="case_studies", model="cms.CaseStudy", title="Case studies", singular="case study", icon="chart",
    columns=[("hero_image", "", "image"), ("title", "Title", "title"), ("client", "Client", "text"), ("industry", "Industry", "text"), ("status", "Status", "status"), ("featured", "Featured", "bool"), ("updated_at", "Updated", "date")],
    search=["title", "client", "industry", "summary"], filters=["status", "industry", "featured"], ordering=["order", "-created_at"], status_field="status",
    fieldsets=[
        ("Case study", ["title", "slug", "client", "industry", "category", "author"]),
        ("Media", ["hero_image", "hero_alt", "gallery", "before_image", "after_image", "video_urls"]),
        ("Narrative", ["summary", "overview", "challenge", "strategy", "solution", "implementation"]),
        ("Outcome", ["deliverables", "results", "testimonial"]),
        ("Call to action", ["cta_label", "cta_url"]),
        ("Display", ["featured", "order"]),
        PUBLISH_SET, SEO_SET,
    ],
    types={"hero_image": "media", "before_image": "media", "after_image": "media", "gallery": "lines", "video_urls": "lines", "deliverables": "lines", "results": ("repeater", RESULT_SPEC),
           "summary": "textarea:3", "overview": "textarea:5", "challenge": "textarea:5", "strategy": "textarea:5", "solution": "textarea:5", "implementation": "textarea:5"},
    help="Only publish results that are genuine and client-approved. The Results block is shown to visitors exactly as entered.",
    bulk=PUB_BULK, export=["title", "slug", "client", "industry", "status", "updated_at"], preview=lambda o: f"/case-studies/{o.slug}",
))

# ---------------------------------------------------------------- Blog posts
register(Module(
    slug="posts", perm="blog", model="blog.Post", title="Blog posts", singular="post", icon="pen", group="blog",
    columns=[("featured_image", "", "image"), ("title", "Title", "title"), ("category", "Category", "text"), ("status", "Status", "status"), ("comment_count", "Comments", "num"), ("published_at", "Published", "date")],
    search=["title", "excerpt", "author_name"], filters=["status", "category", "featured"], ordering=["-published_at", "-created_at"], status_field="status",
    fieldsets=[
        ("Article", ["title", "slug", "excerpt", "content_html"]),
        ("Media", ["featured_image", "featured_alt", "gallery"]),
        ("Author", ["author", "author_name", "author_role", "author_avatar"]),
        ("Organisation", ["category", "tags", "related_posts"]),
        ("Options", ["featured", "allow_comments", "schema_type", "display_date"]),
        PUBLISH_SET, SEO_SET,
    ],
    types={"featured_image": "media", "author_avatar": "media", "gallery": "lines", "content_html": "rich", "excerpt": "textarea:3"},
    bulk=PUB_BULK, export=["title", "slug", "status", "category", "published_at"], preview=lambda o: f"/blog/{o.slug}",
))

# ---------------------------------------------------------------- Taxonomy
for _slug, _model, _title, _sing in [
    ("blog-categories", "blog.Category", "Blog categories", "blog category"),
    ("tags", "blog.Tag", "Blog tags", "tag"),
    ("service-categories", "cms.ServiceCategory", "Service categories", "service category"),
    ("portfolio-categories", "cms.PortfolioCategory", "Portfolio categories", "portfolio category"),
]:
    cols = [("name", "Name", "title"), ("slug", "Slug", "text")]
    flds = ["name", "slug"]
    if _slug == "blog-categories":
        flds += ["description", "order", "seo_title", "meta_description"]
        cols.append(("order", "Order", "num"))
    elif _slug != "tags":
        flds += ["order"]
        cols.append(("order", "Order", "num"))
    register(Module(slug=_slug, perm="taxonomy", model=_model, title=_title, singular=_sing, icon="tag", group="taxonomy", columns=cols, search=["name"],
                    fieldsets=[("Details", flds)], ordering=["name"], bulk=BASIC_BULK, parent="Categories & tags"))

# ---------------------------------------------------------------- Testimonials / FAQs
register(Module(
    slug="testimonials", perm="testimonials", model="cms.Testimonial", title="Testimonials", singular="testimonial", icon="quote",
    columns=[("avatar_url", "", "image"), ("client_name", "Client", "title"), ("role", "Role", "text"), ("company", "Company", "text"), ("rating", "Rating", "num"), ("featured", "Featured", "bool"), ("is_published", "Visible", "bool")],
    search=["client_name", "company", "content"], filters=["is_published", "featured"], ordering=["order", "-created_at"],
    fieldsets=[("Client", ["client_name", "role", "company", "country", "avatar_url"]), ("Testimonial", ["content", "rating", "project_type"]), ("Display", ["featured", "is_published", "order"])],
    types={"avatar_url": "media", "content": "textarea:5"},
    help="Add only testimonials you have permission to publish. Nothing here is generated.",
    bulk=[("show", "Show on site", "publish"), ("hide", "Hide", "edit"), ("delete", "Delete", "delete")],
))
register(Module(
    slug="faqs", perm="faqs", model="cms.FAQ", title="FAQs", singular="FAQ", icon="help",
    columns=[("question", "Question", "title"), ("group", "Group", "text"), ("show_on_home", "On home", "bool"), ("is_published", "Visible", "bool"), ("order", "Order", "num")],
    search=["question", "answer"], filters=["is_published", "show_on_home", "group"], ordering=["order"],
    fieldsets=[("FAQ", ["question", "answer", "group"]), ("Display", ["show_on_home", "is_published", "order"])], types={"answer": "textarea:5"},
    bulk=[("show", "Show on site", "publish"), ("hide", "Hide", "edit"), ("delete", "Delete", "delete")],
))

# ---------------------------------------------------------------- Singletons
register(Module(
    slug="about", perm="about", model="cms.AboutPage", title="About us page", singular="About page", icon="info", singleton=True, can_create=False, can_delete=False,
    columns=[],
    fieldsets=[("Hero", ["hero_eyebrow", "hero_title", "hero_description", "hero_image", "hero_image_alt"]), ("Story", ["story_title", "story_html"]),
               ("Mission & vision", ["mission", "vision"]), ("Values & differentiators", ["values", "differentiators"]), ("Stats (real figures only)", ["stats"]),
               ("Call to action", ["cta_title", "cta_text", "cta_label", "cta_url"]), SEO_SET],
    types={"hero_image": "media", "story_html": "rich", "mission": "textarea:3", "vision": "textarea:3", "hero_description": "textarea:3", "values": ("repeater", TD_SPEC), "differentiators": ("repeater", TD_SPEC), "stats": ("repeater", STAT_SPEC)},
    preview=lambda o: "/about",
))
register(Module(
    slug="site-settings", perm="settings", model="core.SiteSettings", title="Website settings", singular="Website settings", icon="cog", singleton=True, can_create=False, can_delete=False,
    columns=[],
    fieldsets=[
        ("Contact details", ["contact_email", "phone", "whatsapp_number", "address", "business_hours"]),
        ("Social links", ["facebook_url", "instagram_url", "linkedin_url", "twitter_url", "youtube_url", "behance_url", "dribbble_url"]),
        ("Header & footer", ["cta_label", "cta_url", "footer_text", "copyright_text"]),
        ("Default SEO", ["default_seo_title", "default_meta_description", "default_og_image", "title_suffix"]),
        ("Tracking & verification", ["google_analytics_id", "google_tag_manager_id", "facebook_pixel_id", "google_site_verification", "bing_site_verification"]),
        ("Cookie notice", ["cookie_notice_enabled", "cookie_notice_text", "privacy_policy_url"]),
        ("Comments", ["comment_blocklist"]),
        ("robots.txt", ["robots_extra"]),
    ],
    types={"default_og_image": "media", "footer_text": "textarea:3", "cookie_notice_text": "textarea:3", "comment_blocklist": "textarea:4", "robots_extra": "textarea:4"},
    help="Tracking IDs are only loaded on the public site when filled in. Nothing is sent to third parties otherwise. Logo, fonts and colours are in “Branding & logo”.",
))
register(Module(
    slug="lead-form", perm="leads", model="leads.LeadFormConfig", title="Quote form settings", singular="Quote form settings", icon="form", singleton=True, can_create=False, can_delete=False, columns=[], group="leads",
    fieldsets=[("Required fields", ["require_phone", "require_service", "require_budget"]), ("Service options", ["use_services_as_options", "extra_service_options"]),
               ("Placeholders", ["placeholder_name", "placeholder_email", "placeholder_phone", "placeholder_message"]),
               ("Consent", ["consent_required", "consent_text", "marketing_optin_enabled", "marketing_optin_text"]),
               ("Messages", ["success_title", "success_message", "error_message"]), ("Notifications & spam", ["notification_recipients", "min_seconds_to_submit"])],
    types={"success_message": "textarea:3", "error_message": "textarea:3", "consent_text": "textarea:3", "marketing_optin_text": "textarea:3", "extra_service_options": "textarea:4", "notification_recipients": "textarea:3"},
    parent="Leads",
))

# ---------------------------------------------------------------- Lead helpers
register(Module(
    slug="budget-options", perm="leads", model="leads.BudgetOption", title="Budget options", singular="budget option", icon="coin", group="leads",
    columns=[("label", "Label", "title"), ("value", "Stored value", "text"), ("order", "Order", "num"), ("is_active", "Active", "bool")], ordering=["order"],
    fieldsets=[("Option", ["label", "value", "order", "is_active"])], bulk=BASIC_BULK, parent="Leads",
    help="These options appear in the quote form's budget dropdown. Existing leads keep the label they were submitted with.",
))
register(Module(
    slug="knowledge", perm="chatbot", model="chatbot.KnowledgeEntry", title="Chatbot knowledge base", singular="FAQ answer", icon="book", group="chatbot",
    columns=[("question", "Question", "title"), ("keywords", "Keywords", "text"), ("suggest_quote", "Offers quote", "bool"), ("is_active", "Active", "bool"), ("order", "Order", "num")],
    search=["question", "keywords", "answer"], filters=["is_active"], ordering=["order"],
    fieldsets=[("Entry", ["question", "keywords", "answer"]), ("Action", ["link_label", "link_url", "suggest_quote"]), ("Display", ["is_active", "order"])],
    types={"answer": "textarea:5", "keywords": "textarea:2"}, bulk=BASIC_BULK, parent="Chatbot",
    help="The rule-based assistant matches visitor questions against these keywords. Separate keywords with commas.",
))
register(Module(
    slug="chatbot-settings", perm="chatbot", model="chatbot.ChatbotSettings", title="Chatbot settings", singular="Chatbot settings", icon="cog", singleton=True, can_create=False, can_delete=False, columns=[], group="chatbot",
    fieldsets=[("Widget", ["enabled", "bot_name", "welcome_message", "quick_replies", "privacy_notice", "offline_message", "fallback_message"]),
               ("Human hand-off", ["human_handoff_enabled", "handoff_message", "handoff_keywords", "ask_contact_details"]),
               ("Optional AI provider", ["ai_provider", "ai_api_key", "ai_model", "ai_base_url", "ai_extra_instructions"])],
    types={"welcome_message": "textarea:3", "quick_replies": "textarea:4", "privacy_notice": "textarea:3", "offline_message": "textarea:3", "fallback_message": "textarea:3", "handoff_message": "textarea:3", "handoff_keywords": "textarea:2", "ai_extra_instructions": "textarea:4"},
    parent="Chatbot",
    help="Without an AI provider the assistant is a rule-based FAQ bot and never claims to be AI. The API key is stored encrypted and is never shown again.",
))

# ---------------------------------------------------------------- Site navigation / banner
register(Module(
    slug="navigation", perm="settings", model="core.NavItem", title="Navigation & footer links", singular="link", icon="menu", group="settings",
    columns=[("label", "Label", "title"), ("url", "URL", "text"), ("location", "Location", "text"), ("order", "Order", "num"), ("is_active", "Active", "bool")],
    filters=["location", "is_active"], ordering=["location", "order"],
    fieldsets=[("Link", ["location", "label", "url", "open_in_new_tab"]), ("Display", ["order", "is_active"])], bulk=BASIC_BULK, parent="Website settings",
))
register(Module(
    slug="banners", perm="settings", model="core.AnnouncementBanner", title="Announcement banners", singular="banner", icon="bell", group="settings",
    columns=[("message", "Message", "title"), ("style", "Style", "text"), ("is_active", "Active", "bool"), ("starts_at", "Starts", "date"), ("ends_at", "Ends", "date")], ordering=["-created_at"],
    fieldsets=[("Banner", ["message", "link_label", "link_url", "style", "dismissible"]), ("Schedule", ["is_active", "starts_at", "ends_at"])], bulk=BASIC_BULK, parent="Website settings",
))

# ---------------------------------------------------------------- SEO tools
register(Module(
    slug="redirects", perm="seo", model="seo.Redirect", title="Redirects", singular="redirect", icon="redirect", group="seo",
    columns=[("from_path", "From", "title"), ("to_path", "To", "text"), ("permanent", "301", "bool"), ("is_active", "Active", "bool"), ("hit_count", "Hits", "num"), ("auto_created", "Auto", "bool")],
    search=["from_path", "to_path"], filters=["is_active", "permanent"], ordering=["-created_at"],
    fieldsets=[("Redirect", ["from_path", "to_path", "permanent", "is_active", "note"])], bulk=BASIC_BULK, parent="SEO",
    help="Visitors (and search engines) requesting the 'from' path are sent to the 'to' path. Slug changes create redirects automatically.",
))
register(Module(
    slug="internal-links", perm="seo", model="seo.InternalLink", title="Internal links", singular="internal link", icon="link", group="seo",
    columns=[("source_path", "From page", "title"), ("target_path", "To page", "text"), ("anchor_text", "Anchor", "text"), ("is_active", "Active", "bool")],
    search=["source_path", "target_path", "anchor_text"], ordering=["source_path"],
    fieldsets=[("Link plan", ["source_path", "target_path", "anchor_text", "notes", "is_active"])], bulk=BASIC_BULK, parent="SEO",
    help="A planning record of internal links you intend to build or maintain. It does not modify page content automatically.",
))
register(Module(
    slug="backlinks", perm="seo", model="seo.Backlink", title="Backlinks", singular="backlink", icon="link", group="seo",
    columns=[("referring_domain", "Domain", "title"), ("source_url", "Source page", "text"), ("link_type", "Type", "text"), ("status", "Status", "badge"), ("verified", "Verified", "bool"), ("last_checked_at", "Last checked", "date")],
    search=["referring_domain", "source_url", "anchor_text"], filters=["status", "link_type", "verified"], ordering=["-created_at"], parent="SEO",
    fieldsets=[("Backlink", ["source_url", "target_url", "anchor_text", "link_type", "status", "notes"])],
    bulk=BASIC_BULK,
    help="Backlinks are tracked manually or by verifying a URL you enter. This tool does not claim to discover every link pointing to your site.",
))

# ---------------------------------------------------------------- Marketing
CAMPAIGN_SET = [("Campaign", ["name", "objective", "channel", "status", "owner"]), ("Schedule & budget", ["start_date", "end_date", "budget", "currency"]),
                ("Tracking", ["landing_page_url", "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content"]), ("Planning", ["audience_notes", "notes"])]
register(Module(
    slug="campaigns", perm="campaigns", model="marketing.Campaign", title="Campaigns", singular="campaign", icon="rocket", group="campaigns",
    columns=[("name", "Campaign", "title"), ("channel", "Channel", "text"), ("status", "Status", "badge"), ("start_date", "Start", "date"), ("budget", "Budget", "text"), ("platform_linked", "Live-linked", "bool")],
    search=["name", "objective"], filters=["status", "channel"], ordering=["-created_at"], fieldsets=CAMPAIGN_SET, types={"audience_notes": "textarea:3", "notes": "textarea:4", "objective": "textarea:2"},
    bulk=BASIC_BULK, export=["name", "channel", "status", "start_date", "end_date", "budget"],
    help="Campaigns here are internal planning records. Spend/metrics are only what your team enters or imports; nothing is pulled from ad platforms unless an integration is connected.",
))
register(Module(
    slug="email-campaigns", perm="campaigns", model="marketing.EmailCampaign", title="Email campaigns", singular="email campaign", icon="mail", group="campaigns",
    columns=[("name", "Name", "title"), ("subject", "Subject", "text"), ("status", "Status", "badge"), ("scheduled_at", "Scheduled", "date"), ("recipient_count", "Recipients", "num")],
    search=["name", "subject"], filters=["status"], ordering=["-created_at"],
    fieldsets=[("Email", ["name", "subject", "preview_text", "body_html", "campaign"])], types={"body_html": "rich"}, bulk=BASIC_BULK, parent="Campaigns",
))
register(Module(
    slug="subscribers", perm="campaigns", model="marketing.Subscriber", title="Subscribers", singular="subscriber", icon="users", group="campaigns",
    columns=[("email", "Email", "title"), ("name", "Name", "text"), ("status", "Status", "badge"), ("consent_at", "Consent given", "date"), ("consent_source", "Source", "text")],
    search=["email", "name"], filters=["status"], ordering=["-created_at"], export=["email", "name", "status", "consent_at", "consent_source"],
    fieldsets=[("Subscriber", ["email", "name", "status", "consent_source"])], bulk=BASIC_BULK, parent="Campaigns",
    help="Only add people who have given consent. Every marketing email includes an unsubscribe link and unsubscribed contacts are never emailed.",
))

# ---------------------------------------------------------------- Ads
register(Module(
    slug="ad-groups", perm="ads", model="marketing.AdGroup", title="Ad groups", singular="ad group", icon="target", group="ads",
    columns=[("name", "Ad group", "title"), ("campaign", "Campaign", "text"), ("daily_budget", "Daily budget", "text"), ("status", "Status", "badge")],
    search=["name"], filters=["status", "campaign"], ordering=["-created_at"], parent="Ads manager",
    fieldsets=[("Ad group", ["campaign", "name", "audience", "daily_budget", "start_date", "end_date", "status"])], types={"audience": "textarea:3"}, bulk=BASIC_BULK,
))
register(Module(
    slug="ad-creatives", perm="ads", model="marketing.AdCreative", title="Ad creatives", singular="creative", icon="image", group="ads",
    columns=[("image_url", "", "image"), ("headline", "Headline", "title"), ("ad_group", "Ad group", "text"), ("approval_status", "Approval", "badge")],
    search=["headline", "body_text"], filters=["approval_status"], ordering=["-created_at"], parent="Ads manager",
    fieldsets=[("Creative", ["ad_group", "headline", "body_text", "cta_text", "landing_url", "image_url"])], types={"image_url": "media", "body_text": "textarea:4"}, bulk=BASIC_BULK,
))

# ---------------------------------------------------------------- Outbound sales
register(Module(
    slug="outreach-templates", perm="outbound", model="outbound.OutreachTemplate", title="Message templates", singular="message template", icon="doc", group="outbound",
    columns=[("name", "Name", "title"), ("kind", "Type", "text"), ("category", "Business type", "text"), ("is_active", "Active", "bool"), ("updated_at", "Updated", "date")],
    search=["name", "subject", "body"], filters=["kind", "is_active"], ordering=["kind", "name"], parent="Outreach",
    fieldsets=[("Template", ["name", "kind", "category", "is_active"]), ("Message", ["subject", "body"])], types={"body": "textarea:10"}, bulk=BASIC_BULK,
    help="Placeholders: {business} {city} {issue} {service} {score} {sender} {agency}. {issue} is filled from the real audit of that prospect. The unsubscribe link and postal address are added automatically.",
))
register(Module(
    slug="do-not-contact", perm="outbound", model="outbound.SuppressionEntry", title="Do-not-contact list", singular="entry", icon="shield", group="outbound",
    columns=[("email", "Email", "title"), ("domain", "Domain", "text"), ("reason", "Reason", "text"), ("created_at", "Added", "date")],
    search=["email", "domain", "note"], filters=["reason"], ordering=["-created_at"], parent="Outreach", export=["email", "domain", "reason", "created_at"],
    fieldsets=[("Block", ["email", "domain", "reason", "note"])], bulk=BASIC_BULK,
    help="Addresses and whole domains listed here are never emailed by outbound sales. People who click Unsubscribe or ask us to stop are added automatically.",
))

# ---------------------------------------------------------------- Users
register(Module(
    slug="roles", perm="users", model="accounts.Role", title="Roles & permissions", singular="role", icon="shield", group="users",
    columns=[("name", "Role", "title"), ("description", "Description", "text"), ("is_system", "Built-in", "bool")], ordering=["name"], parent="Users & roles",
    fieldsets=[("Role", ["name", "description"])], bulk=[],
))


def get(slug):
    return REGISTRY.get(slug)
