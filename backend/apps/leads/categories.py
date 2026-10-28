"""Plain-Python helper (no model imports) so migrations, the API and the dashboard share one definition."""
import re


CATEGORY_WORDS = {
    "seo": ("seo", "search engine", "ranking", "google business", "backlink"),
    "marketing": ("marketing", "ads", "advert", "campaign", "social media", "ppc", "lead gen", "facebook", "instagram"),
    "design": ("design", "brand", "logo", "identity", "ui", "ux", "graphic", "packaging", "creative"),
    "website": ("website", "web", "development", "shopify", "wordpress", "ecommerce", "e-commerce", "app", "react", "portal", "landing page", "online store"),
}


def lead_category(text: str, primary: str = "") -> str:
    """Group an enquiry by the kind of work it is about. The chosen service counts double; a tie goes to website → design → marketing → seo."""
    def hits(t):
        t = (t or "").lower()
        return {c: sum(1 for w in words if re.search(r"(?<![a-z])" + re.escape(w) + r"(?![a-z])", t)) for c, words in CATEGORY_WORDS.items()}

    a, b = hits(primary), hits(text)
    scores = {c: a[c] * 2 + b[c] for c in CATEGORY_WORDS}
    best = max(("website", "design", "marketing", "seo"), key=lambda c: scores[c])
    return best if scores[best] else "other"
