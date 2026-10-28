"""Finds real local businesses from OpenStreetMap (Nominatim + Overpass). Only genuine OSM records are returned:
no sample data, no 'curated' fallback. If OSM does not answer, the caller is told so honestly."""
import json
import logging
import time
import urllib.parse
import urllib.request

from . import netguard
from .models import CATEGORIES

log = logging.getLogger(__name__)
NOMINATIM = "https://nominatim.openstreetmap.org/search"
OVERPASS = ["https://overpass-api.de/api/interpreter", "https://overpass.private.coffee/api/interpreter", "https://overpass.kumi.systems/api/interpreter"]
SOCIAL = ("facebook.com", "instagram.com", "twitter.com", "x.com", "linkedin.com", "tiktok.com", "youtube.com", "wa.me", "whatsapp.com", "linktr.ee", "tripadvisor.", "google.com", "goo.gl", "maps.app")

OSM_FILTERS = {
    "restaurant": ['["amenity"~"^(restaurant|cafe|fast_food|food_court)$"]'],
    "dental": ['["amenity"="dentist"]', '["healthcare"="dentist"]'],
    "fitness": ['["leisure"~"^(fitness_centre|sports_centre)$"]'],
    "real_estate": ['["office"="estate_agent"]'],
    "ecommerce": ['["shop"]'],
    "healthcare": ['["amenity"~"^(clinic|hospital|doctors)$"]', '["healthcare"~"^(clinic|hospital|doctor|centre)$"]'],
    "legal": ['["office"~"^(lawyer|notary)$"]'],
    "hospitality": ['["tourism"~"^(hotel|guest_house|hostel|motel|resort)$"]'],
    "automotive": ['["shop"~"^(car|car_repair|car_parts|tyres)$"]'],
    "home_services": ['["craft"~"^(plumber|electrician|carpenter|painter|hvac|roofer|builder)$"]'],
    "manufacturing": ['["man_made"="works"]', '["industrial"]'],
    "other": ['["office"="company"]'],
}
CATEGORY_LABELS = dict(CATEGORIES)


class DiscoveryError(Exception):
    """Message is safe to show to staff."""


def _ua(contact=""):
    return f"AUBSquareOutbound/1.0 (business lead research; {contact or 'contact: site owner'})"


def _get_json(url, params=None, data=None, timeout=12, contact=""):
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode() if data else None, headers={"User-Agent": _ua(contact), "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # fixed https hosts above – never user-supplied
        return json.loads(resp.read(3_000_000).decode("utf-8", errors="replace"))


def clean_website(raw: str) -> str:
    raw = (raw or "").split(";")[0].strip()
    url = netguard.normalize_url(raw)
    if not url:
        return ""
    host = urllib.parse.urlsplit(url).hostname or ""
    return "" if any(s in host for s in SOCIAL) else url


def geocode(city, country, contact=""):
    q = ", ".join(x for x in (city, country) if x)
    rows = _get_json(NOMINATIM, {"q": q, "format": "json", "limit": 1}, contact=contact)
    if rows and rows[0].get("boundingbox"):
        s, n, w, e = (float(x) for x in rows[0]["boundingbox"])
        return s, w, n, e
    return None


def _element(el, category, city, country):
    t = el.get("tags") or {}
    name = (t.get("name") or t.get("name:en") or "").strip()
    website = clean_website(t.get("website") or t.get("contact:website") or t.get("url") or "")
    phone = (t.get("phone") or t.get("contact:phone") or "").split(";")[0].strip()[:60]
    email = (t.get("email") or t.get("contact:email") or "").split(";")[0].strip().lower()
    if not name or not (website or phone or email):
        return None
    addr = ", ".join(x for x in (t.get("addr:housenumber", ""), t.get("addr:street", ""), t.get("addr:city", "")) if x)
    return {"external_id": f"osm/{el.get('type', 'node')}/{el.get('id')}", "business_name": name[:200], "website": website, "phone": phone,
            "email": email, "city": (t.get("addr:city") or city)[:100], "country": country[:80], "category": category, "address": addr[:300]}


def discover(category: str, city: str, country: str, limit: int = 40, contact: str = ""):
    """Returns (candidates, messages). `messages` explains anything that went wrong so staff are never shown a silent empty list."""
    city, country = (city or "").strip(), (country or "").strip()
    if not city:
        raise DiscoveryError("Please enter a city.")
    if category not in OSM_FILTERS:
        category = "other"
    limit = max(1, min(int(limit or 40), 80))
    messages = []
    try:
        bbox = geocode(city, country, contact)
    except Exception as exc:
        log.warning("geocode failed: %s", exc)
        raise DiscoveryError("The OpenStreetMap search service did not answer. Please try again in a minute.")
    if not bbox:
        raise DiscoveryError(f"OpenStreetMap could not find “{city}”. Check the spelling or add the country.")
    s, w, n, e = bbox
    parts = []
    for flt in OSM_FILTERS[category]:  # one regex clause for all contact keys keeps the query light for big cities
        parts.append(f'nwr{flt}["name"][~"^(website|contact:website|url|phone|contact:phone|email|contact:email)$"~"."]({s},{w},{n},{e});')
    query = f"[out:json][timeout:30];({''.join(parts)});out tags center {limit * 3};"
    elements, last_err = None, ""
    time.sleep(1)  # be polite to the free public service
    for url in OVERPASS:
        try:
            elements = _get_json(url, data={"data": query}, timeout=40, contact=contact).get("elements", [])
            break
        except Exception as exc:
            last_err = exc.__class__.__name__
            log.warning("overpass %s failed: %s", url, exc)
    if elements is None:
        raise DiscoveryError("OpenStreetMap's data service is busy or unreachable right now (" + last_err + "). Nothing was imported – please try again later.")
    out, seen = [], set()
    for el in elements:
        c = _element(el, category, city, country)
        if c and c["external_id"] not in seen:
            seen.add(c["external_id"])
            out.append(c)
        if len(out) >= limit:
            break
    if not out:
        messages.append("OpenStreetMap has no matching businesses with contact details here. Try another city or business type – no sample data is ever added.")
    return out, messages
