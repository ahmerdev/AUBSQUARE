"""Curated Google Fonts catalogue used by Branding settings.

Only families listed here can be chosen, so the font name that ends up in the website's <link>/CSS can never be arbitrary text
(no CSS or HTML injection through the dashboard). Weights are the ones Google Fonts publishes for each family.
"""
from django.core.exceptions import ValidationError
from urllib.parse import quote

from django.utils.html import escape

DEFAULT_HEADING = "Outfit"
DEFAULT_BODY = "Plus Jakarta Sans"
FONTS_ORIGIN = "https://fonts.googleapis.com/css2?"

_W = "300;400;500;600;700;800"
# (family, category, weights)  –  category: sans | serif | display | script | mono
CATALOGUE = [
    ("Outfit", "sans", _W), ("Plus Jakarta Sans", "sans", _W), ("Inter", "sans", _W), ("Poppins", "sans", _W), ("Montserrat", "sans", _W),
    ("DM Sans", "sans", _W), ("Manrope", "sans", _W), ("Space Grotesk", "sans", "300;400;500;600;700"), ("Sora", "sans", _W), ("Urbanist", "sans", _W),
    ("Lexend", "sans", _W), ("Work Sans", "sans", _W), ("Nunito", "sans", _W), ("Nunito Sans", "sans", _W), ("Rubik", "sans", _W),
    ("Raleway", "sans", _W), ("Open Sans", "sans", _W), ("Lato", "sans", "300;400;700"), ("Roboto", "sans", "300;400;500;700"),
    ("Source Sans 3", "sans", _W), ("Figtree", "sans", _W), ("Albert Sans", "sans", _W), ("Be Vietnam Pro", "sans", "300;400;500;600;700;800"),
    ("Barlow", "sans", "300;400;500;600;700;800"), ("Mulish", "sans", _W), ("Josefin Sans", "sans", "300;400;500;600;700"),
    ("Quicksand", "sans", "300;400;500;600;700"), ("Kanit", "sans", "300;400;500;600;700;800"), ("Archivo", "sans", _W),
    ("Syne", "sans", "400;500;600;700;800"), ("Bricolage Grotesque", "sans", "300;400;500;600;700;800"), ("Onest", "sans", _W),
    ("Cairo", "sans", "300;400;500;600;700;800"), ("Noto Nastaliq Urdu", "sans", "400;500;600;700"),
    ("Playfair Display", "serif", "400;500;600;700;800"), ("Merriweather", "serif", "300;400;700"), ("Lora", "serif", "400;500;600;700"),
    ("Cormorant Garamond", "serif", "300;400;500;600;700"), ("DM Serif Display", "serif", "400"), ("Libre Baskerville", "serif", "400;700"),
    ("Fraunces", "serif", "300;400;500;600;700;800"), ("Source Serif 4", "serif", "300;400;500;600;700;800"), ("PT Serif", "serif", "400;700"),
    ("Cinzel", "serif", "400;500;600;700;800"),
    ("Bebas Neue", "display", "400"), ("Anton", "display", "400"), ("Abril Fatface", "display", "400"), ("Righteous", "display", "400"),
    ("Unbounded", "display", "300;400;500;600;700;800"), ("Pacifico", "script", "400"), ("Lobster", "script", "400"),
    ("JetBrains Mono", "mono", "300;400;500;600;700;800"), ("Space Mono", "mono", "400;700"), ("Fira Code", "mono", "300;400;500;600;700"),
]
BY_NAME = {n: (c, w) for n, c, w in CATALOGUE}
CATEGORY_LABELS = {"sans": "Sans-serif", "serif": "Serif", "display": "Display", "script": "Script", "mono": "Monospace"}
_FALLBACK = {
    "sans": 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif', "serif": 'Georgia, "Times New Roman", serif',
    "display": "system-ui, sans-serif", "script": "cursive, system-ui, sans-serif", "mono": 'ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace',
}


def validate_font(value):
    if value not in BY_NAME:
        raise ValidationError("Choose a font from the list.")


def safe(name, default):
    return name if name in BY_NAME else default


def stack(name):
    """CSS font-family value for a whitelisted family (the name is quoted and cannot contain anything else)."""
    cat = BY_NAME[name][0]
    return f'"{name}", {_FALLBACK[cat]}'


def _family_param(name):
    weights = BY_NAME[name][1]
    fam = name.replace(" ", "+")
    return f"family={fam}:wght@{weights}" if ";" in weights or weights != "400" else f"family={fam}"


def css_url(*names):
    """One Google Fonts stylesheet URL for the given (whitelisted) families, in order, without duplicates."""
    seen, params = set(), []
    for n in names:
        if n in BY_NAME and n not in seen:
            seen.add(n)
            params.append(_family_param(n))
    return FONTS_ORIGIN + "&".join(params) + "&display=swap" if params else ""


def for_site(site):
    """What the dashboard and the website need to apply the chosen fonts."""
    h = safe(getattr(site, "heading_font", ""), DEFAULT_HEADING)
    b = safe(getattr(site, "body_font", ""), DEFAULT_BODY)
    return {"heading": h, "body": b, "headingStack": stack(h), "bodyStack": stack(b), "cssUrl": css_url(h, b)}


def head_html(site):
    """<link> + <style> for the <head> of the website and of every dashboard page. Safe: names come from the whitelist."""
    f = for_site(site)
    out = []
    if f["cssUrl"]:
        out.append('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>')
        out.append(f'<link rel="stylesheet" id="aub-font-link" href="{escape(f["cssUrl"])}">')
    out.append(f'<style id="aub-fonts">:root{{--font-heading:{f["headingStack"]};--font-body:{f["bodyStack"]}}}</style>')
    return "\n    ".join(out)


def picker_data():
    """Everything the dashboard's font picker needs (name, group, ready-made CSS URL)."""
    def tiny(n):  # regular weight, only the letters of the name – a few hundred bytes per family
        return f"{FONTS_ORIGIN}family={n.replace(' ', '+')}&text={quote(n)}&display=swap"

    return [{"name": n, "group": CATEGORY_LABELS[c], "cat": c, "stack": stack(n), "url": css_url(n), "tiny": tiny(n)} for n, c, _ in CATALOGUE]
