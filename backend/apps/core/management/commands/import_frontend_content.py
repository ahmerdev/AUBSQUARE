"""Imports the ORIGINAL website content (exported from src/data/*.ts) plus sensible defaults.

Idempotent: re-running never duplicates rows and never overwrites content you've edited in the dashboard
(use --force to overwrite the imported records).  Nothing here is demo analytics – it is the content
that was already on your public website.
"""
import json
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.utils.html import escape

from apps.blog.models import Category, Post
from apps.chatbot.models import ChatbotSettings, KnowledgeEntry
from apps.cms import home_schema
from apps.cms.models import (FAQ, AboutPage, CaseStudy, HomeSection, PortfolioCategory, Project, Service, ServiceCategory, TeamMember, Testimonial)
from apps.core.models import NavItem, SiteSettings
from apps.leads.models import BudgetOption, LeadFormConfig
from apps.seo.models import PageSEO

SEED = Path(settings.BASE_DIR) / "seed" / "frontend_content.json"
BUDGETS = ["$500 - $1,500", "$1,500 - $3,000", "$3,000 - $5,000", "$5,000+ (Enterprise Scope)"]
STATIC_PAGES = [("/", "Home", 1.0, "weekly"), ("/services", "Services", 0.9, "monthly"), ("/portfolio", "Portfolio", 0.8, "weekly"),
                ("/case-studies", "Case studies", 0.8, "weekly"), ("/about", "About", 0.7, "monthly"), ("/blog", "Blog", 0.8, "daily"), ("/contact", "Contact", 0.7, "yearly")]


def html_from_sections(sections):
    out = []
    for s in sections:
        out.append(f'<h2>{escape(s["heading"])}</h2>')
        out += [f"<p>{escape(p)}</p>" for p in s.get("paragraphs", [])]
        if s.get("pullQuote"):
            out.append(f'<blockquote>{escape(s["pullQuote"])}</blockquote>')
        if s.get("keyPoints"):
            out.append("<ul>" + "".join(f"<li>{escape(k)}</li>" for k in s["keyPoints"]) + "</ul>")
    return "\n".join(out)


class Command(BaseCommand):
    help = "Import the existing website content and defaults into the database (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Overwrite imported records that already exist.")
        parser.add_argument("--defaults-only", action="store_true", help="Only create settings/navigation/home defaults, no sample content.")

    @transaction.atomic
    def handle(self, *args, **opts):
        force = opts["force"]
        self.seed_settings()
        self.seed_home_and_about()
        if not opts["defaults_only"]:
            data = json.loads(SEED.read_text(encoding="utf-8"))
            self.seed_content(data, force)
        self.seed_chatbot()
        self.stdout.write(self.style.SUCCESS("Import complete."))

    # ---------------------------------------------------------------
    def seed_settings(self):
        s = SiteSettings.load()
        if not s.contact_email:
            s.contact_email = "contact@aubsquare.com"
            s.whatsapp_number = "923272755118"
            s.phone = "+92-327-2755118"
            s.instagram_url = "https://www.instagram.com/aubsquare"
            s.linkedin_url = "https://www.linkedin.com/company/aubsquare"
            s.footer_text = "We help startups and small businesses worldwide look like big, trusted brands."
            s.copyright_text = "© 2026 AUB SQUARE. All rights reserved. Designed & Engineered with precision."
            s.default_seo_title = "AUB SQUARE – Brand Identity, UI/UX & 3D Web Development Agency"
            s.default_meta_description = "AUB SQUARE helps startups and small businesses look like big, trusted brands with logo & brand identity, graphic design, UI/UX, web development and social media."
            s.save()
        if not NavItem.objects.exists():
            header = [("Home", "/"), ("Services", "/services"), ("Portfolio", "/portfolio"), ("Case Studies", "/case-studies"), ("About", "/about"), ("Blog", "/blog"), ("Contact", "/contact")]
            explore = [("Home", "/"), ("About Us", "/about"), ("Our Services", "/services"), ("Portfolio", "/portfolio"), ("Case Studies", "/case-studies"), ("Insights & Blog", "/blog"), ("Contact", "/contact")]
            for i, (l, u) in enumerate(header):
                NavItem.objects.create(location=NavItem.HEADER, label=l, url=u, order=i)
            for i, (l, u) in enumerate(explore):
                NavItem.objects.create(location=NavItem.FOOTER_EXPLORE, label=l, url=u, order=i)
        if not BudgetOption.objects.exists():
            for i, b in enumerate(BUDGETS):
                BudgetOption.objects.create(label=b, value=b, order=i)
        LeadFormConfig.load()
        for path, label, prio, freq in STATIC_PAGES:
            PageSEO.objects.get_or_create(path=path, defaults={"label": label, "priority": prio, "changefreq": freq})

    def seed_home_and_about(self):
        for i, spec in enumerate(home_schema.SECTIONS):
            HomeSection.objects.get_or_create(key=spec["key"], defaults={"label": spec["label"], "order": i, "data": {}})
        a = AboutPage.load()
        if not a.hero_title:
            a.hero_eyebrow = "About AUB SQUARE Creative Studio"
            a.hero_title = "We Believe Great Design Is An Unfair Advantage."
            a.hero_description = "Founded on the principle that startups and growing businesses should never look small or unproven. We combine strategic brand positioning with cutting-edge 3D web engineering."
            a.story_title = "From Passionate Freelancers to an International Agency"
            a.story_html = ("<p>AUB SQUARE started with a simple observation: hundreds of innovative startups with brilliant products were failing to raise capital or close deals simply because their branding looked amateurish.</p>"
                            "<p>Muhammad Bilal, an obsessive brand identity designer, joined forces with Mohammad Shahwaiz, a full-stack engineer passionate about interactive 3D WebGL experiences. Together, they established AUB SQUARE to offer a cohesive, full-spectrum creative service: from the vector curve of a primary logo mark to complex animated 3D web platforms.</p>")
            a.values = [
                {"title": "Precision & Craft", "description": "No shortcuts. Every kerning pair, color contrast ratio, and pixel is art-directed for perfection."},
                {"title": "Commercial Efficacy", "description": "Design must generate revenue, shorten sales cycles, and elevate perceived value."},
                {"title": "Founder-to-Founder Transparency", "description": "Direct, honest counsel. We treat your marketing budget with the same stewardship as our own."}]
            a.stats = [{"value": "500+", "label": "Projects"}, {"value": "6+ Years", "label": "Experience"}, {"value": "Worldwide", "label": "Reach"}]
            a.cta_title = "Ready to Build Your Brand With Us?"
            a.cta_text = "Let’s discuss your upcoming venture or rebrand. We will prepare an exact scope, roadmap, and milestone schedule within 24 hours."
            a.cta_label = "Get a Free Quote"
            a.save()
        if not TeamMember.objects.exists():
            TeamMember.objects.create(name="Muhammad Bilal", role="Founder & Lead Designer", is_founder=True, order=0,
                                      photo_url="https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=300&q=80", photo_alt="Muhammad Bilal",
                                      bio="With 6+ years of mastery in brand architecture, logo marks, typographic hierarchy, and visual storytelling, Bilal leads the creative vision for all AUB SQUARE brand programs.",
                                      specialty="Brand Identity, Design Systems")
            TeamMember.objects.create(name="Mohammad Shahwaiz", role="Co-Founder & Full-Stack Developer", is_founder=True, order=1,
                                      photo_url="https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?auto=format&fit=crop&w=300&q=80", photo_alt="Mohammad Shahwaiz",
                                      bio="Architecting high-performance web systems with React, TypeScript, Next.js, and interactive Three.js 3D WebGL scenes. Shahwaiz brings designs to life with silky 60fps animations.",
                                      specialty="React & 3D WebGL, Full-Stack Architecture")

    def seed_content(self, d, force):
        now = timezone.now()
        # services
        cat, _ = ServiceCategory.objects.get_or_create(name="Creative services")
        svc_by_title = {}
        for i, s in enumerate(d["services"]):
            obj, created = Service.objects.get_or_create(slug=s["id"], defaults={"title": s["title"], "short_description": s["shortDescription"]})
            if created or force:
                obj.title, obj.short_description, obj.full_description = s["title"], s["shortDescription"], s["fullDescription"]
                obj.icon_name, obj.is_primary, obj.order, obj.category = s["iconName"], bool(s.get("isPrimary")), i, cat
                obj.deliverables, obj.process, obj.benefits, obj.faqs = s["deliverables"], s["process"], s["benefits"], s.get("faqs", [])
                obj.status, obj.featured = "published", True
                obj.save()
            svc_by_title[s["title"]] = obj
        # testimonials
        for i, t in enumerate(d["testimonials"]):
            Testimonial.objects.get_or_create(client_name=t["clientName"], company=t["company"], defaults={
                "role": t["role"], "country": t["country"], "avatar_url": t["avatar"], "rating": t["rating"], "content": t["content"],
                "project_type": t["projectType"], "order": i, "featured": True})
        # faqs
        for i, q in enumerate(d["faqs"]):
            FAQ.objects.get_or_create(question=q["question"], defaults={"answer": q["answer"], "order": i})
        # portfolio
        projects = {}
        for i, p in enumerate(d["projects"]):
            pc, _ = PortfolioCategory.objects.get_or_create(name=p["category"])
            obj, created = Project.objects.get_or_create(slug=p["slug"], defaults={"title": p["title"], "summary": p["summary"]})
            if created or force:
                obj.title, obj.client_name, obj.category, obj.year = p["title"], p["client"], pc, p["year"]
                obj.thumbnail, obj.thumbnail_alt, obj.images = p["thumbnail"], p["title"], p["images"]
                obj.summary, obj.challenge, obj.solution = p["summary"], p["challenge"], p["solution"]
                obj.deliverables, obj.services_provided, obj.metrics = p["deliverables"], p["servicesProvided"], p.get("metrics", [])
                obj.featured, obj.order, obj.status = bool(p.get("featured")), i, "published"
                try:
                    obj.completion_date = datetime(int(p["year"]), 1, 1).date()
                except Exception:
                    pass
                first = p["servicesProvided"][0] if p["servicesProvided"] else None
                obj.service = svc_by_title.get(first)
                if p.get("testimonial") and not obj.testimonial:
                    t = p["testimonial"]
                    obj.testimonial = Testimonial.objects.create(client_name=t["author"], role=t["role"], company=p["client"], content=t["quote"], is_published=False,
                                                                 project_type=f"Project quote – {p['title']}")
                obj.save()
            projects[p["slug"]] = obj
        # case studies
        for i, c in enumerate(d["caseStudies"]):
            obj, created = CaseStudy.objects.get_or_create(slug=c["slug"], defaults={"title": c["title"], "client": c["client"], "summary": c["summary"]})
            if created or force:
                obj.title, obj.client, obj.industry, obj.category = c["title"], c["client"], c["industry"], c["category"]
                obj.hero_image, obj.hero_alt, obj.gallery = c["heroImage"], c["title"], c["galleryImages"]
                obj.summary, obj.overview, obj.challenge, obj.strategy, obj.solution = c["summary"], c["summary"], c["challenge"], c["strategy"], c["solution"]
                obj.deliverables, obj.results, obj.featured, obj.order, obj.status = c["deliverables"], c["results"], bool(c.get("featured")), i, "published"
                if c.get("testimonial") and not obj.testimonial:
                    t = c["testimonial"]
                    obj.testimonial = Testimonial.objects.create(client_name=t["author"], role=t["role"], company=c["client"], country=t.get("country", ""), content=t["quote"],
                                                                 is_published=False, project_type=f"Case study quote – {c['title'][:40]}")
                obj.save()
        # blog
        for a in d["articles"]:
            cat, _ = Category.objects.get_or_create(name=a["category"])
            obj, created = Post.objects.get_or_create(slug=a["slug"], defaults={"title": a["title"]})
            if created or force:
                try:
                    dt = timezone.make_aware(datetime.strptime(a["publishDate"], "%B %d, %Y"))
                except Exception:
                    dt = now
                obj.title, obj.excerpt, obj.category = a["title"], a["excerpt"], cat
                obj.featured_image, obj.featured_alt = a["featuredImage"], a["title"]
                obj.author_name, obj.author_role, obj.author_avatar = a["author"]["name"], a["author"]["role"], a["author"]["avatar"]
                obj.content_html = html_from_sections(a["content"])
                obj.featured, obj.status = bool(a.get("featured")), "published"
                obj.display_date = dt
                obj.published_at = min(dt, now)
                obj.save()

    def seed_chatbot(self):
        ChatbotSettings.load()
        if KnowledgeEntry.objects.exists():
            return
        entries = [
            ("What services do you offer?", "service,services,offer,what do you do", "We specialize in: 1) Brand Identity & Logo Design, 2) Graphic Design & Pitch Decks, 3) Web & App UI/UX Design, 4) Modern 3D Web Development, and 5) Social Media Content Systems. Which discipline does your project need?", "View our services", "/services", True),
            ("How much do your projects cost?", "price,prices,cost,package,packages,pricing,budget,how much", "Our projects typically range from $500 for focused design deliverables up to $5,000+ for enterprise full-stack 3D platforms. We provide customized proposals tailored to your specific milestones.", "Request a proposal", "", True),
            ("How long does a logo or branding project take?", "how long,timeline,logo,duration,turnaround,days,weeks", "A standalone strategic logo system takes about 7 to 10 business days. Comprehensive brand guidelines and full-stack websites generally require 2 to 3 weeks.", "", "", False),
            ("How do we start?", "start,hire,begin,get started,work with you", "To begin, you can request a free proposal using our Quote Form or speak directly with our founders on WhatsApp.", "Contact us", "/contact", True),
        ]
        for i, (q, k, a, ll, lu, sq) in enumerate(entries):
            KnowledgeEntry.objects.create(question=q, keywords=k, answer=a, link_label=ll, link_url=lu, suggest_quote=sq, order=i)
