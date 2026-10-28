"""Public API payloads. Shapes intentionally mirror the React TypeScript types (camelCase) so the existing
components keep working unchanged. Only PUBLISHED content and non-sensitive fields ever leave the server."""
from django.conf import settings

from apps.core import fonts
from apps.core.services import public_media_url as media

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]


def fmt_date(dt):
    return f"{MONTHS[dt.month - 1]} {dt.day}, {dt.year}" if dt else ""


def seo_block(obj, default_title="", default_desc="", default_image=""):
    return {
        "title": getattr(obj, "seo_title", "") or default_title,
        "description": getattr(obj, "meta_description", "") or default_desc,
        "canonical": getattr(obj, "canonical_url", ""),
        "ogTitle": getattr(obj, "og_title", ""), "ogDescription": getattr(obj, "og_description", ""),
        "ogImage": media(getattr(obj, "og_image", "") or default_image),
        "noindex": getattr(obj, "noindex", False), "nofollow": getattr(obj, "nofollow", False),
    }


def site(s):
    return {
        "siteName": s.site_name, "tagline": s.tagline, "logo": media(s.logo_url), "favicon": media(s.favicon_url),
        "colors": {"primary": s.primary_color, "secondary": s.secondary_color, "accent": s.accent_color, "background": s.background_color},
        "fonts": fonts.for_site(s), "headerShowName": s.header_show_name,
        "contactEmail": s.contact_email, "whatsappNumber": s.whatsapp_number, "phone": s.phone, "address": s.address, "businessHours": s.business_hours,
        "socials": {k: v for k, v in {"facebook": s.facebook_url, "instagram": s.instagram_url, "linkedin": s.linkedin_url, "twitter": s.twitter_url,
                                      "youtube": s.youtube_url, "behance": s.behance_url, "dribbble": s.dribbble_url}.items() if v},
        "footerText": s.footer_text, "copyright": s.copyright_text, "ctaLabel": s.cta_label, "ctaUrl": s.cta_url,
        "cookieNotice": {"enabled": s.cookie_notice_enabled, "text": s.cookie_notice_text}, "privacyUrl": s.privacy_policy_url, "termsUrl": s.terms_url,
        "analytics": {"gaId": s.google_analytics_id, "gtmId": s.google_tag_manager_id, "pixelId": s.facebook_pixel_id},
        "titleSuffix": s.title_suffix,
        "defaultSeo": {"title": s.default_seo_title, "description": s.default_meta_description, "ogImage": media(s.default_og_image)},
    }


def nav_item(n):
    return {"label": n.label, "url": n.url, "newTab": n.open_in_new_tab}


def testimonial(t):
    return {"id": str(t.pk), "clientName": t.client_name, "role": t.role, "company": t.company, "country": t.country, "avatar": media(t.avatar_url),
            "rating": t.rating, "content": t.content, "projectType": t.project_type, "featured": t.featured}


def quote_of(t, with_country=False):
    if not t:
        return None
    q = {"quote": t.content, "author": t.client_name, "role": (t.company or t.role) if with_country else t.role}
    if with_country:
        q["country"] = t.country
    return q


def service(s, full=True):
    d = {
        "id": s.slug, "slug": s.slug, "title": s.title, "shortDescription": s.short_description, "fullDescription": s.full_description or s.short_description,
        "iconName": s.icon_name, "isPrimary": s.is_primary, "featured": s.featured, "deliverables": s.deliverables or [], "process": s.process or [],
        "benefits": s.benefits or [], "faqs": s.faqs or [], "coverImage": media(s.cover_image), "coverAlt": s.cover_alt or s.title,
        "gallery": [media(u) for u in (s.gallery or [])], "category": s.category.name if s.category_id else "",
        "priceDisplay": s.price_display, "priceLabel": s.price_label if s.price_display != "none" else "",
        "ctaLabel": s.cta_label, "ctaUrl": s.cta_url, "seo": seo_block(s, s.title, s.short_description, s.cover_image),
    }
    if full:
        d["relatedProjects"] = [p.slug for p in s.related_projects.all() if p.is_live]
        d["relatedCaseStudies"] = [c.slug for c in s.related_case_studies.all() if c.is_live]
    return d


def project(p):
    client = p.client_name if p.show_client_name else "Confidential client"
    return {
        "id": p.slug, "slug": p.slug, "title": p.title, "client": client, "category": p.category.name if p.category_id else "Other",
        "categorySlug": p.category.slug if p.category_id else "", "year": p.year or (str(p.completion_date.year) if p.completion_date else ""),
        "completionDate": p.completion_date.isoformat() if p.completion_date else "", "thumbnail": media(p.thumbnail), "thumbnailAlt": p.thumbnail_alt or p.title,
        "images": [media(u) for u in (p.images or [])], "summary": p.summary, "description": p.description, "challenge": p.challenge, "solution": p.solution,
        "projectUrl": p.project_url, "deliverables": p.deliverables or [], "servicesProvided": p.services_provided or ([p.service.title] if p.service_id else []),
        "technologies": p.technologies or [], "featured": p.featured, "metrics": p.metrics or [],
        "testimonial": quote_of(p.testimonial), "service": {"slug": p.service.slug, "title": p.service.title} if p.service_id else None,
        "seo": seo_block(p, p.title, p.summary, p.thumbnail),
    }


def case_study(c):
    return {
        "id": c.slug, "slug": c.slug, "title": c.title, "client": c.client, "industry": c.industry, "category": c.category,
        "heroImage": media(c.hero_image), "heroAlt": c.hero_alt or c.title, "galleryImages": [media(u) for u in (c.gallery or [])],
        "beforeImage": media(c.before_image), "afterImage": media(c.after_image), "videoUrls": c.video_urls or [],
        "summary": c.summary, "overview": c.overview, "challenge": c.challenge, "strategy": c.strategy, "solution": c.solution,
        "implementation": c.implementation, "deliverables": c.deliverables or [], "results": c.results or [], "featured": c.featured,
        "testimonial": quote_of(c.testimonial, with_country=True),
        "services": [{"slug": s.slug, "title": s.title} for s in c.services.all() if s.is_live],
        "relatedProjects": [{"slug": p.slug, "title": p.title, "thumbnail": media(p.thumbnail)} for p in c.related_projects.all() if p.is_live],
        "ctaLabel": c.cta_label, "ctaUrl": c.cta_url, "publishDate": fmt_date(c.published_at or c.created_at),
        "seo": seo_block(c, c.title, c.summary, c.hero_image),
    }


def post_summary(p):
    return {
        "id": p.slug, "slug": p.slug, "title": p.title, "category": p.category.name if p.category_id else "General",
        "categorySlug": p.category.slug if p.category_id else "", "excerpt": p.excerpt, "featuredImage": media(p.featured_image), "featuredAlt": p.featured_alt or p.title,
        "publishDate": fmt_date(p.public_date), "publishedAt": p.public_date.isoformat() if p.public_date else "",
        "readingTime": f"{p.reading_minutes} min read", "featured": p.featured, "allowComments": p.allow_comments,
        "author": {"name": p.byline, "role": p.author_role or (p.author.job_title if p.author else ""), "avatar": media(p.author_avatar or (p.author.avatar_url if p.author else ""))},
        "tags": [{"name": t.name, "slug": t.slug} for t in p.tags.all()],
    }


def post_detail(p, related):
    d = post_summary(p)
    d.update({
        "contentHtml": p.content_html, "tableOfContents": p.toc or [], "gallery": [media(u) for u in (p.gallery or [])],
        "related": [post_summary(r) for r in related], "updatedAt": p.updated_at.isoformat(),
        "seo": seo_block(p, p.title, p.excerpt, p.featured_image), "schemaType": p.schema_type,
    })
    return d


def comment_tree(comments):
    by_parent = {}
    for c in comments:
        by_parent.setdefault(c.parent_id, []).append(c)

    def node(c):
        return {"id": c.pk, "authorName": c.name, "createdAt": c.created_at.isoformat(), "message": c.body, "isStaff": c.is_staff_reply,
                "replies": [node(r) for r in by_parent.get(c.pk, [])]}

    return [node(c) for c in by_parent.get(None, [])]


def team_member(m):
    return {"id": m.pk, "name": m.name, "role": m.role, "bio": m.bio, "photo": media(m.photo_url), "photoAlt": m.photo_alt or m.name,
            "specialties": [x.strip() for x in m.specialty.split(",") if x.strip()], "isFounder": m.is_founder, "linkedin": m.linkedin_url, "twitter": m.twitter_url}


def about(a):
    return {
        "heroEyebrow": a.hero_eyebrow, "heroTitle": a.hero_title, "heroDescription": a.hero_description, "heroImage": media(a.hero_image), "heroImageAlt": a.hero_image_alt,
        "storyTitle": a.story_title, "storyHtml": a.story_html, "mission": a.mission, "vision": a.vision, "values": a.values or [],
        "differentiators": a.differentiators or [], "stats": a.stats or [], "ctaTitle": a.cta_title, "ctaText": a.cta_text, "ctaLabel": a.cta_label, "ctaUrl": a.cta_url,
        "seo": seo_block(a, a.hero_title, a.hero_description, a.hero_image),
    }
