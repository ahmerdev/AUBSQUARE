import json
import re
from pathlib import Path

from django.conf import settings
from django.http import Http404, HttpResponse
from django.utils.html import escape
from django.views import View

from apps.core import fonts
from apps.core.models import SiteSettings
from apps.core.services import absolute_url, cached_public
from . import resolver
from .models import PageSEO


def robots_txt(request):
    s = SiteSettings.load()
    lines = ["User-agent: *", "Disallow: /dashboard/", "Disallow: /api/", "Disallow: /p/", "Disallow: /r/", "Disallow: /o/", "Disallow: /u/", "Allow: /", "", f"Sitemap: {absolute_url('/sitemap.xml')}"]
    if s.robots_extra.strip():
        lines += ["", s.robots_extra.strip()]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain; charset=utf-8")


def _sitemap_entries():
    from apps.blog.models import Category, Post
    from apps.cms.models import CaseStudy, Project, Service

    entries = []
    seen = set()

    def add(path, lastmod=None, prio="0.6", freq="monthly"):
        if path in seen:
            return
        seen.add(path)
        entries.append((absolute_url(path), lastmod, prio, freq))

    for p in PageSEO.objects.filter(include_in_sitemap=True, noindex=False):
        add(p.path, p.updated_at, str(p.priority), p.changefreq)
    add("/free-audit", None, "0.6", "monthly")
    for model, prefix, prio in ((Service, "/services/", "0.8"), (Project, "/portfolio/", "0.7"), (CaseStudy, "/case-studies/", "0.7"), (Post, "/blog/", "0.6")):
        for o in model.objects.live().filter(noindex=False):
            add(prefix + o.slug, o.updated_at, prio)
    for c in Category.objects.filter(posts__isnull=False).distinct():
        add(f"/blog/category/{c.slug}", c.updated_at, "0.4", "weekly")
    return entries


def sitemap_xml(request):
    def build():
        out = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
        for loc, lastmod, prio, freq in _sitemap_entries():
            out.append(f"<url><loc>{escape(loc)}</loc>" + (f"<lastmod>{lastmod:%Y-%m-%d}</lastmod>" if lastmod else "") + f"<changefreq>{freq}</changefreq><priority>{prio}</priority></url>")
        out.append("</urlset>")
        return "\n".join(out)

    return HttpResponse(cached_public("sitemap", build, 600), content_type="application/xml; charset=utf-8")


_shell_cache = {"mtime": None, "html": ""}


def _read_shell():
    index = Path(settings.FRONTEND_DIST) / "index.html"
    if not index.exists():
        return None
    mtime = index.stat().st_mtime
    if _shell_cache["mtime"] != mtime:
        _shell_cache.update(mtime=mtime, html=index.read_text(encoding="utf-8"))
    return _shell_cache["html"]


class FrontendShell(View):
    """Serves the built React app with real <title>/meta/canonical/JSON-LD and crawlable body text injected
    for the requested route – so search engines and social crawlers see correct metadata without running JS."""

    def get(self, request, path=""):
        html = _read_shell()
        if html is None:
            return HttpResponse(
                "<h1>Frontend not built</h1><p>Run <code>npm run build</code> in the project root (or set FRONTEND_DIST).</p>"
                "<p>The Django dashboard is at <a href='/dashboard/'>/dashboard/</a>.</p>", status=503)
        preview = False
        if request.GET.get("preview"):
            m = re.match(r"^/?(?:blog|services|portfolio|case-studies)/([\w-]+)$", request.path)
            kind = request.path.strip("/").split("/")[0]
            preview = bool(m) and resolver.read_preview_token(request.GET["preview"], kind, m.group(1))
        meta = resolver.resolve(request.path, preview=preview)
        if preview:
            meta["robots"] = "noindex, nofollow"
        head = resolver.render_head(meta)
        html = re.sub(r"<title>.*?</title>", "", html, flags=re.S)
        html = re.sub(r'<meta\s+name="description"[^>]*>', "", html)
        html = html.replace("</head>", f"    {head}\n  </head>", 1)
        site = SiteSettings.load()
        scripts = []
        if site.google_site_verification:
            scripts.append(f'<meta name="google-site-verification" content="{escape(site.google_site_verification)}" />')
        if site.bing_site_verification:
            scripts.append(f'<meta name="msvalidate.01" content="{escape(site.bing_site_verification)}" />')
        if scripts:
            html = html.replace("</head>", "    " + "\n    ".join(scripts) + "\n  </head>", 1)
        icon = site.favicon_url or site.logo_url  # '/media/…' paths stay relative so they work on whatever host serves the page
        if icon:
            html = re.sub(r'<link\s+rel="icon"[^>]*>', "", html)
            html = html.replace("</head>", f'    <link rel="icon" href="{escape(icon)}" />\n    <link rel="apple-touch-icon" href="{escape(icon)}" />\n  </head>', 1)
        html = html.replace("</head>", "    " + fonts.head_html(site) + "\n  </head>", 1)
        prerender = f'<div id="root"><div data-prerender="true" style="position:absolute;left:-9999px;top:0;width:1px;height:1px;overflow:hidden"><h1>{escape(meta["h1"])}</h1>{meta["body"]}</div></div>'
        html = re.sub(r'<div id="root">\s*</div>', lambda _: prerender, html, count=1)
        # Hand the React app its data in the page itself: no loading flash, and it still works if the first API call is slow.
        try:
            from apps.api.views import build_bootstrap

            payload = json.dumps(cached_public("bootstrap", build_bootstrap, 300), ensure_ascii=False, default=str)
            payload = payload.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
            html = html.replace("</head>", f'    <script id="aub-bootstrap" type="application/json">{payload}</script>\n  </head>', 1)
        except Exception:  # never take the whole site down because the data snapshot failed; the app falls back to the API
            import logging

            logging.getLogger(__name__).exception("bootstrap injection failed")
        resp = HttpResponse(html, content_type="text/html; charset=utf-8", status=meta["status"])
        # The page embeds the CMS snapshot (logo, menus, content). Always revalidate so a dashboard change appears on the next load.
        resp["Cache-Control"] = "no-cache"
        resp["X-Frame-Options"] = "SAMEORIGIN"  # lets the dashboard's Branding preview embed the site; other origins still cannot frame it
        return resp
