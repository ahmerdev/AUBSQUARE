"""Editable home-page sections. `fields` drive the dashboard form; `defaults` mirror the original React copy."""

T, TA, URL, IMG, LINES, REP = "text", "textarea", "url", "image", "lines", "repeater"


def f(name, label, type=T, help="", columns=None):
    return {"name": name, "label": label, "type": type, "help": help, "columns": columns or []}


SECTIONS = [
    {
        "key": "hero", "label": "Hero", "fixed_first": True,
        "fields": [
            f("eyebrow", "Eyebrow badge"), f("headline_start", "Headline (plain part)"), f("headline_highlight", "Headline (gradient part)"),
            f("description", "Description", TA), f("cta_primary_label", "Primary button label"), f("cta_secondary_label", "Secondary button label"),
            f("cta_secondary_url", "Secondary button link", URL), f("trust_badges", "Trust badges (one per line)", LINES),
        ],
        "defaults": {
            "eyebrow": "CREATIVE AGENCY · BRAND STRATEGY · DIGITAL EXPERIENCES",
            "headline_start": "We Help Startups & Small Businesses Look Like", "headline_highlight": "Big, Trusted Brands.",
            "description": "Your customers judge your business in seconds. We design your logo, brand identity, website and social media so you look professional, build trust fast, and win more customers — wherever you are in the world.",
            "cta_primary_label": "Get a Free Quote", "cta_secondary_label": "Explore Our Work", "cta_secondary_url": "/portfolio",
            "trust_badges": ["100% Direct Founder Access", "Global Time-Zone Support", "Complete IP Copyright Handover"],
        },
    },
    {
        "key": "stats", "label": "Statistics & counters",
        "fields": [f("items", "Statistics", REP, "Only publish figures that are true.", [("value", "Value"), ("label", "Label"), ("icon", "Icon (Award, Clock, Zap, Globe2, Users)")])],
        "defaults": {"items": [
            {"value": "500+", "label": "Projects Completed", "icon": "Award"}, {"value": "6+ Years", "label": "Industry Experience", "icon": "Clock"},
            {"value": "100+", "label": "Unique Orders", "icon": "Zap"}, {"value": "USA & UK", "label": "Worldwide Clients", "icon": "Globe2"}]},
    },
    {
        "key": "services", "label": "Services section",
        "fields": [f("eyebrow", "Eyebrow"), f("title", "Title"), f("gradient_word", "Highlighted word"), f("subtitle", "Subtitle", TA)],
        "defaults": {"eyebrow": "Creative Disciplines", "title": "End-to-End Creative Solutions Built for Growth", "gradient_word": "Growth",
                     "subtitle": "From zero to market leader: we build complete visual languages and digital products that turn browsers into lifelong buyers."},
    },
    {
        "key": "about_preview", "label": "About preview",
        "fields": [f("eyebrow", "Eyebrow badge"), f("title_start", "Title (plain part)"), f("title_highlight", "Title (gradient part)"),
                   f("paragraph_1", "Paragraph 1", TA), f("paragraph_2", "Paragraph 2", TA), f("cta_label", "Button label"), f("cta_url", "Button link", URL)],
        "defaults": {"eyebrow": "The Story of AUB SQUARE", "title_start": "Crafting World-Class Identities for Tomorrow’s", "title_highlight": "Market Leaders",
                     "paragraph_1": "Founded by creative director Muhammad Bilal and full-stack technologist Mohammad Shahwaiz, AUB SQUARE was created with a clear singular mission: eliminate the gap between brilliant businesses and the world-class visual identity they deserve.",
                     "paragraph_2": "We bring enterprise-grade brand strategy, 3D WebGL immersion, and conversion psychology to every project.",
                     "cta_label": "Meet Our Entire Team", "cta_url": "/about"},
    },
    {
        "key": "why_us", "label": "Why choose us",
        "fields": [f("eyebrow", "Eyebrow"), f("title", "Title"), f("gradient_word", "Highlighted word"), f("subtitle", "Subtitle", TA),
                   f("items", "Reasons", REP, "", [("title", "Title"), ("description", "Description"), ("icon", "Icon (Users, Zap, TrendingUp, Globe2, ShieldCheck)")])],
        "defaults": {"eyebrow": "The AUB Advantage", "title": "Why Startups Choose to Partner With Us", "gradient_word": "Partner",
                     "subtitle": "We eliminate agency bureaucracy and slow feedback cycles so you get award-winning work at startup speed.",
                     "items": [
                         {"title": "Direct Founder Access", "description": "No junior account managers or games of telephone. You collaborate directly with agency founders Bilal and Shahwaiz.", "icon": "Users"},
                         {"title": "Fast & Transparent", "description": "Clear timelines, iterative milestones, and instant communication via dedicated WhatsApp & Slack channels.", "icon": "Zap"},
                         {"title": "Revenue-Driven Design", "description": "We design for commercial outcomes: higher conversion rates, investor confidence, and commanding pricing power.", "icon": "TrendingUp"},
                         {"title": "Global Collaboration", "description": "Seamless cross-border workflows across USA, UK, Europe, and Asia with flexible overlapping time zones.", "icon": "Globe2"}]},
    },
    {
        "key": "process", "label": "Process steps",
        "fields": [f("eyebrow", "Eyebrow"), f("title", "Title"), f("gradient_word", "Highlighted word"), f("subtitle", "Subtitle", TA),
                   f("steps", "Steps", REP, "", [("number", "Number"), ("title", "Title"), ("description", "Description")])],
        "defaults": {"eyebrow": "Our 3D Methodology", "title": "From Concept to Launch in Four Structured Phases", "gradient_word": "Structured",
                     "subtitle": "A predictable, high-precision creative framework with real-time 3D milestone coordination.",
                     "steps": [
                         {"number": "01", "title": "Discover", "description": "Audience research, competitive whitespace analysis, and brand strategic positioning brief."},
                         {"number": "02", "title": "Design", "description": "Crafting distinct visual directions, vector logo geometries, design systems, and 3D scenes."},
                         {"number": "03", "title": "Refine", "description": "Collaborative revision cycles, typography balancing, responsive polish, and performance auditing."},
                         {"number": "04", "title": "Deliver", "description": "Comprehensive asset exports, complete copyright IP transfer, guidelines, and production code."}]},
    },
    {
        "key": "portfolio", "label": "Featured portfolio slider",
        "fields": [f("eyebrow", "Eyebrow"), f("title", "Title"), f("gradient_word", "Highlighted word"), f("subtitle", "Subtitle", TA)],
        "defaults": {"eyebrow": "Selected Works", "title": "Signature Projects That Redefined Brands", "gradient_word": "Signature",
                     "subtitle": "Explore recent visual identities, corporate brand guidelines, and web architectures crafted for our clients."},
    },
    {
        "key": "case_studies", "label": "Case study slider",
        "fields": [f("eyebrow", "Eyebrow"), f("title", "Title"), f("gradient_word", "Highlighted word"), f("subtitle", "Subtitle", TA)],
        "defaults": {"eyebrow": "Case Studies", "title": "Selected Work. Measurable Impact.", "gradient_word": "Measurable",
                     "subtitle": "In-depth breakdowns of strategic challenges, creative execution, and real client results."},
    },
    {
        "key": "blog", "label": "Blog slider",
        "fields": [f("eyebrow", "Eyebrow"), f("title", "Title"), f("gradient_word", "Highlighted words"), f("subtitle", "Subtitle", TA)],
        "defaults": {"eyebrow": "Latest Agency Publications", "title": "Insights, Ideas & Creative Inspiration", "gradient_word": "Creative Inspiration",
                     "subtitle": "Practical insights, branding advice and creative ideas to help your business grow."},
    },
    {
        "key": "testimonials", "label": "Testimonials carousel",
        "fields": [f("eyebrow", "Eyebrow"), f("title", "Title"), f("gradient_word", "Highlighted word"), f("subtitle", "Subtitle", TA)],
        "defaults": {"eyebrow": "Client Praise", "title": "What Our Clients Say About Us", "gradient_word": "Clients",
                     "subtitle": "Hear directly from founders, CTOs, and station directors who trusted AUB SQUARE with their visual identity."},
    },
    {
        "key": "faq", "label": "FAQ section",
        "fields": [f("eyebrow", "Eyebrow"), f("title", "Title"), f("gradient_word", "Highlighted word"), f("subtitle", "Subtitle", TA)],
        "defaults": {"eyebrow": "Frequently Asked Questions", "title": "Everything You Need to Know Before We Begin", "gradient_word": "Everything",
                     "subtitle": "Clear, upfront answers about our timeline, copyright handover, and collaboration workflow."},
    },
    {
        "key": "final_cta", "label": "Final CTA banner",
        "fields": [f("badge", "Badge text"), f("title", "Title"), f("description", "Description", TA), f("primary_label", "Primary button label"),
                   f("secondary_label", "Secondary button label"), f("secondary_url", "Secondary button link", URL, "Empty = WhatsApp link from website settings."), f("footnote", "Footnote")],
        "defaults": {"badge": "Let’s Build Something Iconic", "title": "Ready to Grow Your Business?",
                     "description": "Your next 100 high-ticket customers will judge your legitimacy in seconds. Let's make sure your brand commands the respect and revenue it deserves.",
                     "primary_label": "Get a Free Quote", "secondary_label": "WhatsApp Us Directly", "secondary_url": "",
                     "footnote": "Fast turnaround · Direct founder consultation · Clear project milestones"},
    },
]
BY_KEY = {s["key"]: s for s in SECTIONS}


def merged(section) -> dict:
    """Section data = schema defaults overlaid with whatever the admin saved."""
    spec = BY_KEY.get(section.key)
    base = dict(spec["defaults"]) if spec else {}
    base.update({k: v for k, v in (section.data or {}).items() if v not in (None, "")})
    return base
