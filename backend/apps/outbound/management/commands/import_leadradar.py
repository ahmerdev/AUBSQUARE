"""One-time import of real businesses from the old LeadRadar AI database (read-only)."""
import sqlite3
from pathlib import Path
from urllib.parse import urlsplit

from django.core.management.base import BaseCommand, CommandError

from apps.outbound import services

INDUSTRY = {"Restaurant": "restaurant", "Dental": "dental", "Fitness": "fitness", "Real Estate": "real_estate", "E-Commerce": "ecommerce", "Healthcare": "healthcare", "Legal": "legal",
            "Hospitality": "hospitality", "Automotive": "automotive", "Home Services": "home_services", "Manufacturing": "manufacturing"}
PARKED = ("sedo.com", "hugedomains.com", "godaddy.com/domains", "dan.com", "afternic.com")


class Command(BaseCommand):
    help = "Import prospects from the LeadRadar AI SQLite file. Only rows that came from OpenStreetMap are imported – the old sample/curated rows are skipped."

    def add_arguments(self, parser):
        parser.add_argument("--db", required=True, help="Path to LeadRadar's db.sqlite3")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *a, **o):
        path = Path(o["db"])
        if not path.is_file():
            raise CommandError(f"File not found: {path}")
        try:
            con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            con.row_factory = sqlite3.Row
            rows = con.execute("select business_name, website, email, phone, city, country, industry, source, external_id, notes from leads_lead").fetchall()
        except sqlite3.Error as exc:
            raise CommandError(f"Could not read the database: {exc}")
        added = dup = skipped = 0
        for r in rows:
            ext = (r["external_id"] or "").strip()
            if r["source"] != "OSM" or not ext.startswith(("node/", "way/", "relation/")):
                skipped += 1  # curated / sample / manual rows are not real discovery data
                continue
            site = r["website"] or ""
            host = (urlsplit(site).hostname or "").lower()
            if any(p in site.lower() for p in PARKED):
                site = ""  # a parked-domain page is not the business's website
            data = {"business_name": r["business_name"], "website": site, "email": r["email"] or "", "phone": r["phone"] or "", "city": r["city"] or "", "country": r["country"] or "",
                    "category": INDUSTRY.get(r["industry"], "other"), "external_id": f"osm/{ext}", "notes": "Imported from LeadRadar AI.", "email_source": "OpenStreetMap"}
            if o["dry_run"]:
                added += 0 if services.find_duplicate(site, data["email"], data["external_id"], data["business_name"], data["city"]) else 1
                continue
            p, why = services.create_prospect(data, "legacy")
            if why == "duplicate":
                dup += 1
            elif p:
                added += 1
            else:
                skipped += 1
        self.stdout.write(self.style.SUCCESS(f"{'Would add' if o['dry_run'] else 'Added'} {added}, duplicates {dup}, skipped {skipped} (non-OSM rows or missing contact details)."))
