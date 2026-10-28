"""Single source of truth for page metadata: used by the SEO-aware HTML shell, the sitemap and the JSON API."""
import json
import re
from html import escape

from django.conf import settings
from django.core import signing

from apps.core.models import SiteSettings
from apps.core.sanitize import strip_html
from apps.core.services import absolute_url, public_media_url

PREVIEW_SALT = "aub.preview"
STATIC_TITLES = {
    "/": ("Home", ""), "/services": ("Services", ""), "/portfolio": ("Portfolio", ""), "/case-studies": ("Case Studies", ""),
    "/about": ("About Us", ""), "/blog": ("Insights & Blog", ""), "/contact": ("Contact", ""),
    "/free-audit": ("Free Website Audit", ""),
}


def preview_token(kind: str, slug: str) -> str:
    return signing.dumps({"k": kind, "s": slug}, salt=PREVIEW_SALT)


def read_preview_token(token: str, kind: str, slug: str) -> bool:
    try:
        d = signing.loads(token, salt=PREVIEW_SALT, max_age=3600)
    except signing.BadSignature:
        return False
    return d.get("k") == kind and d.get("s") == slug


def _trim(text, n=160):
    text = re.sub(r"\s+", " ", strip_html(text or "")).strip()
    return text if len(text) <= n else text[: n - 1].rsplit(" ", 1)[0] + "…"


def _meta(site, path, title, desc, *, image="", canonical="", noindex=False, nofollow=False, og_title="", og_desc="", og_type="website",
          jsonld=None, h1="", body="", status=200, seo_title=""):
    full_title = seo_title or (f"{title}{site.title_suffix}" if title and site.title_suffix else title or site.default_seo_title or site.site_name)
    desc = desc or site.default_meta_description
    image = public_media_url(image or site.default_og_image)
    url = absolute_url(path)
    robots = ", ".join(["noindex" if noindex else "index", "nofollow" if nofollow else "follow"])
    return {
        "status": status, "title": full_title, "description": _trim(desc, 320), "canonical": canonical or url, "robots": robots,
        "og": {"title": og_title or full_title, "description": _trim(og_desc or desc, 300), "image": image, "url": url, "type": og_type, "site_name": site.site_name},
        "jsonld": jsonld or [], "h1": h1, "body": body, "path": path,
    }


def _breadcrumb(path_items):
    return {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": n, "item": absolute_url(u)} for i, (n, u) in enumerate(path_items)]}


def _override(site, meta, ov):
    """Apply a PageSEO row on top of auto-generated metadata."""
    if not ov:
        return meta
    if ov.seo_title:
        meta["title"] = ov.seo_title
    if ov.meta_description:
        meta["description"] = ov.meta_description
    if ov.canonical_url:
        meta["canonical"] = ov.canonical_url
    if ov.og_title:
        meta["og"]["title"] = ov.og_title
    if ov.og_description:
        meta["og"]["description"] = ov.og_description
    if ov.og_image:
        meta["og"]["image"] = public_media_url(ov.og_image)
    if ov.noindex or ov.nofollow:
        meta["robots"] = ", ".join(["noindex" if ov.noindex else "index", "nofollow" if ov.nofollow else "follow"])
    if ov.schema_json:
        meta["jsonld"] = [ov.schema_json] if isinstance(ov.schema_json, dict) else list(ov.schema_json)
    return meta


def _obj_robots(o):
    return dict(noindex=getattr(o, "noindex", False), nofollow=getattr(o, "nofollow", False), canonical=getattr(o, "canonical_url", ""),
                og_title=getattr(o, "og_title", ""), og_desc=getattr(o, "og_description", ""))


def resolve(path: str, preview=False) -> dict:
    from apps.blog.models import Category, Post, Tag
    from apps.cms.models import FAQ, AboutPage, CaseStudy, Project, Service
    from .models import PageSEO

    site = SiteSettings.load()
    path = "/" + path.strip("/") if path.strip("/") else "/"
    ov = PageSEO.objects.filter(path=path).first()
    org = {"@context": "https://schema.org", "@type": "Organization", "name": site.site_name, "url": settings.SITE_URL,
           "logo": public_media_url(site.logo_url) or None, "email": site.contact_email or None, "telephone": site.phone or None,
           "sameAs": [u for u in [site.facebook_url, site.instagram_url, site.linkedin_url, site.twitter_url, site.youtube_url] if u]}
    org = {k: v for k, v in org.items() if v}

    def live(qs):
        return qs if preview else qs.live()

    if path == "/":
        faqs = FAQ.objects.filter(is_published=True, show_on_home=True)
        ld = [org, {"@context": "https://schema.org", "@type": "WebSite", "name": site.site_name, "url": settings.SITE_URL}]
        if faqs:
            ld.append({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
                {"@type": "Question", "name": f.question, "acceptedAnswer": {"@type": "Answer", "text": strip_html(f.answer)}} for f in faqs]})
        from apps.cms.models import HomeSection
        from apps.cms import home_schema

        hero = next((home_schema.merged(s) for s in HomeSection.objects.filter(key="hero")), home_schema.BY_KEY["hero"]["defaults"])
        m = _meta(site, "/", "", site.default_meta_description or hero.get("description", ""), seo_title=site.default_seo_title, jsonld=ld,
                  h1=f"{hero.get('headline_start', '')} {hero.get('headline_highlight', '')}".strip(), body=f"<p>{escape(hero.get('description', ''))}</p>" + "".join(
                      f"<h2>{escape(s.title)}</h2><p>{escape(s.short_description)}</p>" for s in Service.objects.live()))
        return _override(site, m, ov)

    if path in STATIC_TITLES and path != "/":
        label = STATIC_TITLES[path][0]
        desc, body, h1, jl = "", "", label, [_breadcrumb([("Home", "/"), (label, path)])]
        if path == "/services":
            svcs = Service.objects.live()
            body = "".join(f"<h2><a href='/services/{s.slug}'>{escape(s.title)}</a></h2><p>{escape(s.short_description)}</p>" for s in svcs)
            desc = "Brand identity, graphic design, UI/UX, web development and social media services from AUB SQUARE."
        elif path == "/portfolio":
            body = "".join(f"<h2><a href='/portfolio/{p.slug}'>{escape(p.title)}</a></h2><p>{escape(p.summary)}</p>" for p in Project.objects.live())
            desc = "Selected brand identity, UI/UX and web projects by AUB SQUARE."
        elif path == "/case-studies":
            body = "".join(f"<h2><a href='/case-studies/{c.slug}'>{escape(c.title)}</a></h2><p>{escape(c.summary)}</p>" for c in CaseStudy.objects.live())
            desc = "In-depth case studies with the challenge, strategy and results."
        elif path == "/blog":
            body = "".join(f"<h2><a href='/blog/{p.slug}'>{escape(p.title)}</a></h2><p>{escape(p.excerpt)}</p>" for p in Post.objects.live()[:20])
            desc = "Branding, design and web development insights from AUB SQUARE."
        elif path == "/about":
            a = AboutPage.load()
            h1, desc = a.hero_title or label, a.hero_description
            body = f"<p>{escape(a.hero_description)}</p>{a.story_html}"
            m = _meta(site, path, a.hero_title or label, desc, image=a.og_image or a.hero_image, h1=h1, body=body, jsonld=jl + [org],
                      noindex=a.noindex, nofollow=a.nofollow, canonical=a.canonical_url, seo_title=a.seo_title)
            if a.meta_description:
                m["description"] = a.meta_description
            return _override(site, m, ov)
        elif path == "/contact":
            desc = "Request a free quote from AUB SQUARE – our founders reply within 24 hours."
            body = f"<p>{escape(desc)}</p>"
        elif path == "/free-audit":
            desc = "Check your website in seconds: HTTPS, mobile friendliness, SEO basics, WhatsApp button and broken links – with a clear list of fixes."
            body = f"<p>{escape(desc)}</p>"
        return _override(site, _meta(site, path, label, desc, h1=h1, body=body, jsonld=jl), ov)

    m = re.match(r"^/services/([\w-]+)$", path)
    if m:
        s = live(Service.objects.filter(slug=m.group(1))).first()
        if s:
            ld = {"@context": "https://schema.org", "@type": "Service", "name": s.title, "description": _trim(s.short_description), "provider": {"@type": "Organization", "name": site.site_name, "url": settings.SITE_URL}, "url": absolute_url(path)}
            body = f"<p>{escape(s.full_description or s.short_description)}</p><ul>" + "".join(f"<li>{escape(d)}</li>" for d in s.deliverables) + "</ul>"
            return _override(site, _meta(site, path, s.title, s.meta_description or s.short_description, image=s.og_image or s.cover_image, h1=s.title, body=body,
                                         jsonld=[ld, _breadcrumb([("Home", "/"), ("Services", "/services"), (s.title, path)])], seo_title=s.seo_title, **_obj_robots(s)), ov)
    m = re.match(r"^/portfolio/([\w-]+)$", path)
    if m:
        p = live(Project.objects.filter(slug=m.group(1))).first()
        if p:
            ld = {"@context": "https://schema.org", "@type": "CreativeWork", "name": p.title, "description": _trim(p.summary), "image": public_media_url(p.thumbnail), "url": absolute_url(path),
                  "creator": {"@type": "Organization", "name": site.site_name}}
            body = f"<p>{escape(p.summary)}</p><p>{escape(p.challenge)}</p><p>{escape(p.solution)}</p>"
            return _override(site, _meta(site, path, p.title, p.meta_description or p.summary, image=p.og_image or p.thumbnail, h1=p.title, body=body, og_type="article",
                                         jsonld=[ld, _breadcrumb([("Home", "/"), ("Portfolio", "/portfolio"), (p.title, path)])], seo_title=p.seo_title, **_obj_robots(p)), ov)
    m = re.match(r"^/case-studies/([\w-]+)$", path)
    if m:
        c = live(CaseStudy.objects.filter(slug=m.group(1))).first()
        if c:
            ld = {"@context": "https://schema.org", "@type": "Article", "headline": c.title, "description": _trim(c.summary), "image": public_media_url(c.hero_image),
                  "datePublished": (c.published_at or c.created_at).isoformat(), "dateModified": c.updated_at.isoformat(),
                  "author": {"@type": "Organization", "name": site.site_name}, "publisher": {"@type": "Organization", "name": site.site_name}, "mainEntityOfPage": absolute_url(path)}
            body = f"<p>{escape(c.summary)}</p><h2>Challenge</h2><p>{escape(c.challenge)}</p><h2>Strategy</h2><p>{escape(c.strategy)}</p><h2>Solution</h2><p>{escape(c.solution)}</p>"
            return _override(site, _meta(site, path, c.title, c.meta_description or c.summary, image=c.og_image or c.hero_image, h1=c.title, body=body, og_type="article",
                                         jsonld=[ld, _breadcrumb([("Home", "/"), ("Case Studies", "/case-studies"), (c.title, path)])], seo_title=c.seo_title, **_obj_robots(c)), ov)
    m = re.match(r"^/blog/([\w-]+)$", path)
    if m and m.group(1) not in ("category", "tag"):
        p = live(Post.objects.filter(slug=m.group(1)).select_related("category", "author")).first()
        if p:
            ld = {"@context": "https://schema.org", "@type": p.schema_type, "headline": p.title, "description": _trim(p.excerpt), "image": public_media_url(p.featured_image),
                  "datePublished": p.public_date.isoformat(), "dateModified": p.updated_at.isoformat(), "author": {"@type": "Person", "name": p.byline},
                  "publisher": {"@type": "Organization", "name": site.site_name}, "mainEntityOfPage": absolute_url(path)}
            return _override(site, _meta(site, path, p.title, p.meta_description or p.excerpt, image=p.og_image or p.featured_image, h1=p.title, body=p.content_html, og_type="article",
                                         jsonld=[ld, _breadcrumb([("Home", "/"), ("Blog", "/blog"), (p.title, path)])], seo_title=p.seo_title, **_obj_robots(p)), ov)
    m = re.match(r"^/blog/category/([\w-]+)$", path)
    if m:
        c = Category.objects.filter(slug=m.group(1)).first()
        if c:
            return _override(site, _meta(site, path, c.seo_title or f"{c.name} articles", c.meta_description or c.description or f"{c.name} articles from {site.site_name}", h1=c.name,
                                         body="".join(f"<h2><a href='/blog/{p.slug}'>{escape(p.title)}</a></h2>" for p in c.posts.live()[:20]),
                                         jsonld=[_breadcrumb([("Home", "/"), ("Blog", "/blog"), (c.name, path)])]), ov)
    m = re.match(r"^/blog/tag/([\w-]+)$", path)
    if m:
        t = Tag.objects.filter(slug=m.group(1)).first()
        if t:
            return _override(site, _meta(site, path, f"Articles tagged {t.name}", f"Articles tagged {t.name} on {site.site_name}", h1=t.name, noindex=True,
                                         body="".join(f"<h2><a href='/blog/{p.slug}'>{escape(p.title)}</a></h2>" for p in t.posts.live()[:20])), ov)
    return _meta(site, path, "Page not found", "The page you are looking for does not exist.", noindex=True, status=404, h1="Page not found")


def render_head(meta: dict) -> str:
    e = escape
    og = meta["og"]
    tags = [
        f"<title>{e(meta['title'])}</title>",
        f'<meta name="description" content="{e(meta["description"])}" />',
        f'<meta name="robots" content="{e(meta["robots"])}" />',
        f'<link rel="canonical" href="{e(meta["canonical"])}" />',
        f'<meta property="og:type" content="{e(og["type"])}" />', f'<meta property="og:site_name" content="{e(og["site_name"])}" />',
        f'<meta property="og:title" content="{e(og["title"])}" />', f'<meta property="og:description" content="{e(og["description"])}" />',
        f'<meta property="og:url" content="{e(og["url"])}" />',
        f'<meta name="twitter:card" content="{"summary_large_image" if og["image"] else "summary"}" />',
        f'<meta name="twitter:title" content="{e(og["title"])}" />', f'<meta name="twitter:description" content="{e(og["description"])}" />',
    ]
    if og["image"]:
        tags += [f'<meta property="og:image" content="{e(og["image"])}" />', f'<meta name="twitter:image" content="{e(og["image"])}" />']
    for ld in meta["jsonld"]:
        # "</" is escaped so structured data can never close the script tag
        tags.append('<script type="application/ld+json">' + json.dumps(ld, ensure_ascii=False).replace("</", "<\\/") + "</script>")
    return "\n    ".join(tags)
