"""Website audit: fetches a public page safely, reads real facts from the HTML and turns them into findings + a score.
Nothing is estimated or invented – a check that could not be made is recorded as such."""
import json
import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

from . import netguard
from .models import BOOKING_CATEGORIES, ORDERING_CATEGORIES, SCORE_RULES, OutboundSettings, SiteAudit

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}")
BAD_EMAIL = ("sentry", "wixpress", "example.", "yourdomain", "domain.com", "email.com", "u003e", "noreply", "no-reply", "donotreply")
BAD_TLD = {"png", "jpg", "jpeg", "gif", "webp", "svg", "css", "js", "woff", "woff2", "ico"}
BOOKING = ("book online", "book now", "book an appointment", "book appointment", "make an appointment", "reservation", "reserve a table", "schedule appointment", "calendly.com", "appointment booking", "book a consultation")
ORDERING = ("order online", "order now", "start order", "place order", "add to cart", "online delivery", "checkout", "shop now", "view cart")
WHATSAPP = ("wa.me", "api.whatsapp.com", "whatsapp.com/send", "whatsapp://", "web.whatsapp.com")


class _Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.meta = {}
        self.h1 = ""
        self._in = None
        self.links = []
        self.imgs = 0
        self.imgs_no_alt = 0
        self.forms = 0
        self.has_canonical = False
        self.has_schema = False
        self.text = []
        self._skip = 0
        self.mailtos = []

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "title" and not self.title:
            self._in = "title"
        elif tag == "h1" and not self.h1:
            self._in = "h1"
        elif tag == "meta":
            key = (a.get("name") or a.get("property") or "").lower()
            if key:
                self.meta.setdefault(key, a.get("content", ""))
        elif tag == "link" and "canonical" in a.get("rel", "").lower():
            self.has_canonical = True
        elif tag == "a" and a.get("href"):
            href = a["href"].strip()
            self.links.append(href)
            if href.lower().startswith("mailto:"):
                self.mailtos.append(href[7:].split("?")[0])
        elif tag == "img":
            self.imgs += 1
            if not a.get("alt", "").strip():
                self.imgs_no_alt += 1
        elif tag == "form":
            self.forms += 1
        elif tag == "script":
            if "ld+json" in a.get("type", "").lower():
                self.has_schema = True
            self._skip += 1
        elif tag == "style":
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in ("title", "h1"):
            self._in = None
        elif tag in ("script", "style") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if self._in == "title":
            self.title += data
        elif self._in == "h1":
            self.h1 += data
        if not self._skip and len(self.text) < 4000:
            self.text.append(data)


def parse_html(html: str) -> _Page:
    p = _Page()
    try:
        p.feed(html[:1_200_000])
        p.close()
    except Exception:  # malformed HTML must never break an audit
        pass
    p.title, p.h1 = " ".join(p.title.split())[:300], " ".join(p.h1.split())[:300]
    return p


def clean_emails(found, domain=""):
    out = []
    for e in found:
        e = e.strip().strip(".,;:").lower()
        if not e or any(b in e for b in BAD_EMAIL) or e.rsplit(".", 1)[-1] in BAD_TLD or len(e) > 120:
            continue
        if e not in out:
            out.append(e)
    # prefer addresses on the business's own domain
    out.sort(key=lambda e: (0 if domain and e.endswith("@" + domain) else 1))
    return out[:5]


def _internal_links(page, base_url):
    host = urlsplit(base_url).hostname or ""
    host = host[4:] if host.startswith("www.") else host
    seen, out = set(), []
    for href in page.links:
        low = href.lower()
        if not href or low.startswith(("#", "mailto:", "tel:", "javascript:", "sms:", "data:")):
            continue
        full = urljoin(base_url, href).split("#")[0]
        u = urlsplit(full)
        h = (u.hostname or "")
        h = h[4:] if h.startswith("www.") else h
        if u.scheme in ("http", "https") and h == host and full not in seen and not re.search(r"\.(pdf|jpg|jpeg|png|gif|zip|webp|svg|mp4)$", u.path.lower()):
            seen.add(full)
            out.append(full)
    return out


def check_links(page, base_url, limit=6):
    """Really requests up to `limit` same-site links (HEAD-style GET with tiny body cap) and reports the ones that answer 404/410/5xx."""
    broken, checked = [], 0
    for link in _internal_links(page, base_url)[:limit]:
        checked += 1
        try:
            r = netguard.fetch(link, timeout=5, max_bytes=2000)
        except (netguard.UnsafeURL, netguard.FetchError):
            continue  # could not be checked – not counted as broken
        if r.status in (404, 410) or r.status >= 500:
            broken.append({"url": link[:200], "status": r.status})
    return checked, broken


def evaluate(a: SiteAudit, category="other", settings=None):
    """Fills a.score / a.level / a.findings from the facts already stored on the audit."""
    s = settings or OutboundSettings.load()
    findings = []

    def add(key, title, detail, service, group):
        pts = s.weight(key)
        findings.append({"key": key, "title": title, "detail": detail, "points": pts, "service": service, "category": group})

    if not a.reachable:
        a.score, a.level, a.findings = 0, "unknown", []
        return
    if not a.has_whatsapp:
        add("no_whatsapp", "No WhatsApp / instant-chat button", "Visitors on mobile cannot message the business in one tap, so quick enquiries are lost.", "WhatsApp chat & lead capture setup", "website")
    if category in ORDERING_CATEGORIES and not a.has_ordering:
        add("no_ordering", "No way to order online", "Customers cannot order or buy directly on the website, which pushes them to third-party apps or competitors.", "Online ordering / e-commerce website", "website")
    if category in BOOKING_CATEGORIES and not a.has_booking:
        add("no_booking", "No online booking", "There is no booking or appointment option – customers must phone or message first.", "Online booking system", "website")
    missing = [n for n, ok in (("page title", a.title), ("meta description", a.meta_description), ("H1 heading", a.h1)) if not ok]
    if missing:
        add("weak_seo", f"Missing basic SEO: {', '.join(missing)}", "Search engines rely on these tags to understand and rank the page.", "On-page & local SEO", "seo")
    if not (a.is_https and a.ssl_ok):
        add("no_ssl", "Website is not securely served over HTTPS", a.ssl_error or "Browsers warn visitors that the site is 'Not secure', which hurts trust and rankings.", "SSL / HTTPS security fix", "website")
    if a.broken_links:
        add("broken_links", f"{len(a.broken_links)} broken internal link(s)", "Links on the page lead to missing pages: " + ", ".join(b["url"] for b in a.broken_links[:3]), "Website maintenance & technical cleanup", "website")
    if not a.has_viewport:
        add("not_mobile", "Not set up for mobile screens", "The page has no mobile viewport tag, so it usually looks zoomed-out on phones.", "Mobile-first website redesign", "design")
    if a.load_seconds > 3:
        add("slow", f"Slow to respond ({a.load_seconds:.1f}s)", "The server took over 3 seconds to deliver the page.", "Performance optimisation", "website")
    if not a.has_form and not a.emails_found:
        add("no_contact_form", "No contact form or email address on the page", "Visitors have no easy written way to get in touch.", "Contact & lead-capture forms", "website")
    total = min(sum(f["points"] for f in findings), 100)
    a.score = total
    a.level = "high" if total >= 70 else "medium" if total >= 40 else "low"
    a.findings = findings
    return a


def run_audit(url: str, kind="prospect", prospect=None, category="other", check_internal=True, ip_hash="") -> SiteAudit:
    """Performs one real audit and returns the saved SiteAudit (reachable=False with an honest error when it could not be done)."""
    norm = netguard.normalize_url(url)
    a = SiteAudit(kind=kind, prospect=prospect, url=norm or url[:500], requester_ip_hash=ip_hash)
    if not norm:
        a.error = "That doesn't look like a valid web address."
        a.save()
        return a
    tried = [norm]
    try:
        try:
            r = netguard.fetch(norm)
        except (netguard.HostNotFound, netguard.FetchError) as first:
            # www / non-www and http / https are often configured differently – try the close variants before giving up
            r = None
            for alt in netguard.host_variants(norm):
                tried.append(alt)
                try:
                    r = netguard.fetch(alt)
                    a.url = alt[:500]
                    break
                except (netguard.UnsafeURL, netguard.FetchError):
                    continue
            if r is None:
                if len(tried) > 1 and isinstance(first, netguard.HostNotFound):
                    hosts = ", ".join(sorted({urlsplit(t).hostname or "" for t in tried}))
                    raise netguard.HostNotFound(f"We couldn't find this website – none of these addresses resolve: {hosts}. Check the spelling, or the domain may be expired or offline.")
                raise first
    except netguard.UnsafeURL as exc:
        a.error = str(exc)[:300]
        a.save()
        return a
    except netguard.FetchError as exc:
        a.error = str(exc)[:300]
        a.save()
        return a
    except Exception:  # never let an audit crash a request
        a.error = "The website could not be checked right now."
        a.save()
        return a
    a.final_url, a.status_code, a.load_seconds = r.url[:500], r.status, r.elapsed
    a.is_https = r.url.startswith("https://")
    a.ssl_error = r.ssl_error[:300]
    a.ssl_ok = a.is_https and not r.ssl_error
    a.reachable = 200 <= r.status < 400 and r.is_html
    if not a.reachable:
        a.error = f"The website answered with status {r.status}." if r.status >= 400 else "The address did not return a web page."
        a.save()
        return a
    html = r.text
    page = parse_html(html)
    low = html.lower()
    text = " ".join(page.text).lower()
    hrefs = " ".join(page.links).lower()
    a.has_viewport = "viewport" in page.meta
    a.title = page.title
    a.meta_description = " ".join((page.meta.get("description") or "").split())[:400]
    a.h1 = page.h1
    a.has_canonical, a.has_open_graph, a.has_schema = page.has_canonical, "og:title" in page.meta or "og:image" in page.meta, page.has_schema
    a.images_total, a.images_missing_alt = page.imgs, page.imgs_no_alt
    wa = next((l for l in page.links if any(w in l.lower() for w in WHATSAPP)), "")
    a.has_whatsapp, a.whatsapp_link = bool(wa or any(w in low for w in ("wa.me/", "api.whatsapp.com/send"))), wa[:300]
    a.has_booking = any(k in text or k in hrefs for k in BOOKING)
    a.has_ordering = any(k in text or k in hrefs for k in ORDERING)
    a.has_form = page.forms > 0
    dom = (urlsplit(r.url).hostname or "").removeprefix("www.")
    a.emails_found = clean_emails(page.mailtos + EMAIL_RE.findall(" ".join(page.text)), dom)
    if check_internal:
        a.links_checked, a.broken_links = check_links(page, r.url)
    evaluate(a, category)
    a.save()
    return a


def find_contact_email(website: str, audit: SiteAudit | None = None):
    """Looks for a public business email on the home page (already in the audit) and, if none, on /contact. Returns (email, where)."""
    if audit and audit.emails_found:
        return audit.emails_found[0], audit.final_url or audit.url
    base = netguard.normalize_url(website)
    if not base:
        return "", ""
    u = urlsplit(base)
    for path in ("/contact", "/contact-us", "/about"):
        try:
            r = netguard.fetch(f"{u.scheme}://{u.netloc}{path}", timeout=6, max_bytes=400_000)
        except Exception:
            continue
        if r.status != 200 or not r.is_html:
            continue
        pg = parse_html(r.text)
        emails = clean_emails(pg.mailtos + EMAIL_RE.findall(" ".join(pg.text)), (u.hostname or "").removeprefix("www."))
        if emails:
            return emails[0], r.url
    return "", ""
