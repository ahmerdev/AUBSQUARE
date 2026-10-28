"""HTML sanitising for rich text and plain-text hardening for visitor input."""
import html as _html
import re

import nh3

ALLOWED_TAGS = {
    "p", "br", "hr", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "li", "strong", "b", "em", "i", "u", "s", "sub", "sup",
    "blockquote", "pre", "code", "a", "img", "figure", "figcaption", "table", "thead", "tbody", "tfoot", "tr", "th", "td",
    "span", "div",
}
ALLOWED_ATTRS = {
    "a": {"href", "title", "target"},
    "img": {"src", "alt", "title", "width", "height", "loading"},
    "td": {"colspan", "rowspan"},
    "th": {"colspan", "rowspan", "scope"},
    "h2": {"id"}, "h3": {"id"}, "h4": {"id"},
    "*": {"class"},
}
SAFE_CLASS = re.compile(r"""\sclass="([^"]*)""")


def clean_html(html: str) -> str:
    """Sanitise rich-text submitted by staff (scripts, handlers, javascript: URLs are removed)."""
    if not html:
        return ""
    return nh3.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRS,
        url_schemes={"http", "https", "mailto", "tel"},
        link_rel="noopener noreferrer",
        strip_comments=True,
    )


def strip_html(html: str) -> str:
    return nh3.clean(html or "", tags=set())


def clean_plain(text: str, max_len: int = 5000) -> str:
    """Visitor supplied text: strip every tag/control char. Templates and React escape on output as well."""
    text = _html.unescape(strip_html(text or ""))
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    return text.strip()[:max_len]
