"""Rule-based on-page SEO checklist computed from the CMS records. It is a checklist, not a ranking prediction."""
import re
from collections import Counter

from apps.core.sanitize import strip_html
from . import resolver


def _issue(sev, msg, fix):
    return {"severity": sev, "message": msg, "fix": fix}


def audit_all():
    from apps.blog.models import Post
    from apps.cms.models import CaseStudy, Project, Service
    from .models import PageSEO

    pages = []
    for p in PageSEO.objects.all():
        pages.append(("Page", p.label or p.path, p.path, f"/dashboard/pages/{p.pk}/", p))
    for kind, qs, base, edit, in [("Service", Service.objects.live(), "/services/", "services"), ("Project", Project.objects.live(), "/portfolio/", "portfolio"),
                                  ("Case study", CaseStudy.objects.live(), "/case-studies/", "case-studies"), ("Post", Post.objects.live(), "/blog/", "posts")]:
        for o in qs:
            pages.append((kind, o.title, f"{base}{o.slug}", f"/dashboard/{edit}/{o.pk}/", o))
    results, titles = [], Counter()
    metas = {}
    for kind, label, path, edit_url, obj in pages:
        m = resolver.resolve(path)
        metas[path] = m
        titles[m["title"]] += 1
    for kind, label, path, edit_url, obj in pages:
        m = metas[path]
        issues = []
        t, d = m["title"], m["description"]
        if len(t) < 25:
            issues.append(_issue("warn", f"Title is short ({len(t)} characters).", "Aim for 50–60 characters that include the main topic."))
        if len(t) > 65:
            issues.append(_issue("warn", f"Title may be truncated in search results ({len(t)} characters).", "Shorten it to about 60 characters."))
        if not d:
            issues.append(_issue("error", "Meta description is missing.", "Write a 120–160 character summary that invites the click."))
        elif len(d) < 70:
            issues.append(_issue("warn", f"Meta description is short ({len(d)} characters).", "Expand it to 120–160 characters."))
        elif len(d) > 165:
            issues.append(_issue("warn", f"Meta description may be cut off ({len(d)} characters).", "Trim it to about 155 characters."))
        if titles[t] > 1:
            issues.append(_issue("error", "Another page uses the same title.", "Give every page a unique title."))
        if not m["og"].get("image"):
            issues.append(_issue("warn", "No social-sharing (Open Graph) image.", "Add an image so links look good when shared."))
        if "noindex" in m["robots"]:
            issues.append(_issue("info", "Page is hidden from search engines (noindex).", "Remove noindex if you want it to appear in search results."))
        if kind == "Post":
            words = len(strip_html(obj.content_html).split())
            if words < 300:
                issues.append(_issue("warn", f"Article is short ({words} words).", "Longer, useful articles usually perform better; aim for 600+ words where it fits."))
            if obj.featured_image and not obj.featured_alt:
                issues.append(_issue("warn", "Featured image has no alt text.", "Describe the image for accessibility and image search."))
            if not obj.category_id:
                issues.append(_issue("info", "Post has no category.", "Assign a category to improve navigation."))
            imgs_without_alt = len(re.findall(r"<img(?![^>]*\balt=\"[^\"]+\")[^>]*>", obj.content_html))
            if imgs_without_alt:
                issues.append(_issue("warn", f"{imgs_without_alt} image(s) in the article have no alt text.", "Add alt text in the editor."))
        if kind == "Project" and obj.thumbnail and not obj.thumbnail_alt:
            issues.append(_issue("warn", "Thumbnail has no alt text.", "Add alt text to the project thumbnail."))
        if kind in ("Service", "Case study") and (obj.cover_image if kind == "Service" else obj.hero_image) and not (obj.cover_alt if kind == "Service" else obj.hero_alt):
            issues.append(_issue("warn", "Main image has no alt text.", "Add alt text."))
        if len(path) > 80:
            issues.append(_issue("info", "URL is long.", "Shorter slugs are easier to share."))
        checks = 8
        score = max(0, round(100 * (1 - (sum(2 if i["severity"] == "error" else 1 if i["severity"] == "warn" else 0 for i in issues)) / (checks * 1.5))))
        results.append({"kind": kind, "label": label, "path": path, "edit_url": edit_url, "title": t, "description": d, "issues": issues, "score": score})
    results.sort(key=lambda r: r["score"])
    summary = {
        "pages": len(results),
        "errors": sum(1 for r in results for i in r["issues"] if i["severity"] == "error"),
        "warnings": sum(1 for r in results for i in r["issues"] if i["severity"] == "warn"),
        "clean": sum(1 for r in results if not [i for i in r["issues"] if i["severity"] != "info"]),
    }
    return results, summary
