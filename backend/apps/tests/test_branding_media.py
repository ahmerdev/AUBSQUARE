"""Branding (Google Fonts, live preview, header option) and the advanced Media library."""
import io
import tempfile
import zipfile
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.forms.models import model_to_dict
from django.test import override_settings
from django.urls import reverse

from apps.core import fonts
from apps.core.media import media_used_ids
from apps.core.models import MediaAsset, SiteSettings
from apps.dashboard.views_brand import BrandingForm

from .base import Base
from .test_chat_seo_media import png_bytes


class FontCatalogueTests(Base):
    def test_every_catalogue_entry_is_a_safe_family_name(self):
        for name, cat, weights in fonts.CATALOGUE:
            self.assertRegex(name, r"^[A-Za-z0-9 ]+$", name)  # nothing that could break out of a CSS string or URL
            self.assertIn(cat, fonts.CATEGORY_LABELS)
            self.assertRegex(weights, r"^\d{3}(;\d{3})*$")

    def test_unknown_or_malicious_names_are_rejected(self):
        fonts.validate_font("Inter")
        for bad in ("", "Comic Sans", 'Inter"; } body { display:none', "Inter&family=Evil", "<script>"):
            with self.assertRaises(ValidationError, msg=bad):
                fonts.validate_font(bad)
        self.assertEqual(fonts.safe("nope", "Outfit"), "Outfit")

    def test_stylesheet_url_is_built_only_from_whitelisted_names(self):
        url = fonts.css_url("Playfair Display", "Lora")
        self.assertTrue(url.startswith("https://fonts.googleapis.com/css2?family="))
        self.assertIn("family=Playfair+Display:wght@", url)
        self.assertIn("family=Lora:wght@", url)
        self.assertTrue(url.endswith("display=swap"))
        self.assertEqual(fonts.css_url("Inter", "Inter").count("family=Inter"), 1)  # same font twice is requested once

    def test_for_site_falls_back_to_defaults(self):
        s = SiteSettings.load()
        s.heading_font, s.body_font = "garbage", ""
        info = fonts.for_site(s)
        self.assertEqual((info["heading"], info["body"]), (fonts.DEFAULT_HEADING, fonts.DEFAULT_BODY))
        self.assertIn("sans-serif", info["headingStack"])

    def test_picker_data_lists_every_font_with_a_stack(self):
        data = fonts.picker_data()
        self.assertEqual(len(data), len(fonts.CATALOGUE))
        self.assertTrue(all(d["stack"].startswith('"') for d in data))


class BrandingPageTests(Base):
    def setUp(self):
        super().setUp()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        ov = override_settings(MEDIA_ROOT=self._tmp.name)
        ov.enable()
        self.addCleanup(ov.disable)

    def payload(self, **changes):
        s = SiteSettings.load()
        data = {k: ("" if v is None else v) for k, v in model_to_dict(s, fields=BrandingForm.Meta.fields).items()}
        if not data.get("header_show_name"):
            data.pop("header_show_name", None)
        data.update(changes)
        return data

    def test_page_renders_with_fonts_preview_and_devices(self):
        self.login(self.root)
        r = self.client.get(reverse("dashboard:branding"))
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        for needle in ("Heading font", "Body", 'name="heading_font"', 'name="body_font"', 'data-fontpick', "branding.js", "<iframe", "Desktop", "Tablet", "Mobile"):
            self.assertIn(needle, html, needle)
        self.assertIn("Playfair Display", html)  # font list is available to the picker

    def test_preview_can_point_at_a_website_running_on_another_address(self):
        """Dev setup: dashboard on 127.0.0.1:8000, React dev server on localhost:3000."""
        self.login(self.root)
        with override_settings(PREVIEW_SITE_URL="http://localhost:3000"):
            html = self.client.get(reverse("dashboard:branding")).content.decode()
        self.assertIn('data-base="http://localhost:3000"', html)
        self.assertIn('id="pv-addr"', html)  # the address can also be changed on the page
        self.assertIn("pv-fail", html)  # help shown when the website does not answer
        self.assertNotIn('src="/"', html.split('id="pv-frame"')[1][:80])  # the frame is pointed by the script, not hard-wired to this server
        with override_settings(PREVIEW_SITE_URL="", DEBUG=False):
            html = self.client.get(reverse("dashboard:branding")).content.decode()
        self.assertIn('data-base=""', html)  # production: Django serves the site itself

    def test_saving_fonts_applies_to_dashboard_website_shell_and_api(self):
        self.login(self.root)
        r = self.client.post(reverse("dashboard:branding"), self.payload(heading_font="Playfair Display", body_font="Lora"))
        self.assertEqual(r.status_code, 302)
        s = SiteSettings.load()
        self.assertEqual((s.heading_font, s.body_font), ("Playfair Display", "Lora"))

        dash = self.client.get(reverse("dashboard:home")).content.decode()
        self.assertIn("--font-heading:\"Playfair Display\"", dash)
        self.assertIn("family=Playfair+Display", dash)

        api = self.client.get("/api/v1/bootstrap/").json()["site"]
        self.assertEqual(api["fonts"]["heading"], "Playfair Display")
        self.assertEqual(api["fonts"]["body"], "Lora")
        self.assertIn("fonts.googleapis.com", api["fonts"]["cssUrl"])

        with tempfile.TemporaryDirectory() as dist:
            Path(dist, "index.html").write_text("<!doctype html><html><head><title>x</title></head><body><div id=\"root\"></div></body></html>", encoding="utf-8")
            from apps.seo import views as seo_views

            seo_views._shell_cache.update(mtime=None, html="")
            with override_settings(FRONTEND_DIST=dist):
                resp = self.client.get("/")
            body = resp.content.decode()
        self.assertIn('id="aub-font-link"', body)
        self.assertIn("family=Playfair+Display", body)
        self.assertIn("--font-heading:\"Playfair Display\"", body)
        self.assertIn("--font-body:\"Lora\"", body)

    def test_font_outside_the_catalogue_is_rejected_and_nothing_changes(self):
        self.login(self.root)
        before = SiteSettings.load().heading_font
        r = self.client.post(reverse("dashboard:branding"), self.payload(heading_font='x"}</style><script>alert(1)</script>'))
        self.assertEqual(r.status_code, 200)
        self.assertIn("form", r.context)
        self.assertIn("heading_font", r.context["form"].errors)
        self.assertEqual(SiteSettings.load().heading_font, before)
        self.assertNotIn("<script>alert(1)</script>", r.content.decode())

    def test_invalid_colour_is_rejected(self):
        self.login(self.root)
        r = self.client.post(reverse("dashboard:branding"), self.payload(primary_color="red"))
        self.assertEqual(r.status_code, 200)
        self.assertIn("primary_color", r.context["form"].errors)

    def test_header_shows_logo_only_by_default_and_name_is_opt_in(self):
        self.assertFalse(SiteSettings.load().header_show_name)
        self.assertFalse(self.client.get("/api/v1/bootstrap/").json()["site"]["headerShowName"])
        self.login(self.root)
        self.client.post(reverse("dashboard:branding"), self.payload(header_show_name="on"))
        self.assertTrue(self.client.get("/api/v1/bootstrap/").json()["site"]["headerShowName"])

    def test_branding_changes_are_visible_immediately_despite_the_public_cache(self):
        self.client.get("/api/v1/bootstrap/")  # warm cache
        self.login(self.root)
        self.client.post(reverse("dashboard:branding"), self.payload(body_font="Inter"))
        self.assertEqual(self.client.get("/api/v1/bootstrap/").json()["site"]["fonts"]["body"], "Inter")

    def test_permissions(self):
        seo = self.make_user("seo@example.com", role_slug="seo_manager")  # has no access to settings
        self.login(seo)
        self.assertEqual(self.client.get(reverse("dashboard:branding")).status_code, 403)
        self.assertEqual(self.client.post(reverse("dashboard:branding"), self.payload(body_font="Inter")).status_code, 403)
        self.assertNotEqual(SiteSettings.load().body_font, "Inter")
        self.client.logout()
        self.assertEqual(self.client.get(reverse("dashboard:branding")).status_code, 302)  # anonymous → sign-in

    def test_save_is_written_to_the_activity_log(self):
        from apps.core.models import ActivityLog

        self.login(self.root)
        self.client.post(reverse("dashboard:branding"), self.payload(site_name="Studio Nine"))
        self.assertTrue(ActivityLog.objects.filter(action="branding.updated").exists())

    def test_old_brand_fields_are_no_longer_on_website_settings(self):
        self.login(self.root)
        page = self.client.get("/dashboard/site-settings/1/").content.decode()
        self.assertNotIn('name="logo_url"', page)
        self.assertIn("Branding &amp; logo", page)


class FrameHeaderTests(Base):
    def test_public_site_may_be_framed_by_itself_only_and_dashboard_never(self):
        with tempfile.TemporaryDirectory() as dist:
            Path(dist, "index.html").write_text("<!doctype html><html><head><title>x</title></head><body></body></html>", encoding="utf-8")
            from apps.seo import views as seo_views

            seo_views._shell_cache.update(mtime=None, html="")
            with override_settings(FRONTEND_DIST=dist):
                self.assertEqual(self.client.get("/")["X-Frame-Options"], "SAMEORIGIN")  # needed for the Branding live preview
        self.assertEqual(self.client.get("/dashboard/login/")["X-Frame-Options"], "DENY")
        self.assertEqual(self.client.get("/api/v1/bootstrap/")["X-Frame-Options"], "DENY")


class MediaLibraryTests(Base):
    def setUp(self):
        super().setUp()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        ov = override_settings(MEDIA_ROOT=self._tmp.name)
        ov.enable()
        self.addCleanup(ov.disable)
        self.login(self.root)

    def upload(self, name="team photo.png", size=(64, 48), user=None):
        r = self.client.post(reverse("dashboard:media_upload"), {"files": SimpleUploadedFile(name, png_bytes(size), content_type="image/png")})
        self.assertEqual(r.status_code, 200, r.content)
        return MediaAsset.objects.get(pk=r.json()["items"][0]["id"])

    def test_library_lists_name_url_size_type_and_actions(self):
        a = self.upload()
        html = self.client.get(reverse("dashboard:media")).content.decode()
        for needle in (a.url, "team photo", "PNG", "64", "download", "Delete"):
            self.assertIn(needle, html, needle)

    def test_search_filter_and_sort(self):
        a = self.upload("alpha.png")
        b = self.upload("bravo.png")
        pdf = MediaAsset.objects.create(file="uploads/x/doc.pdf", kind=MediaAsset.DOCUMENT, original_name="doc.pdf", mime_type="application/pdf", size=10)
        r = self.client.get(reverse("dashboard:media") + "?q=alpha")
        self.assertContains(r, "alpha")
        self.assertNotContains(r, "bravo.png")
        r = self.client.get(reverse("dashboard:media") + "?kind=document")
        self.assertContains(r, "doc.pdf")
        self.assertNotContains(r, "alpha.png")
        for sort in ("newest", "oldest", "name", "size", "bogus"):
            self.assertEqual(self.client.get(reverse("dashboard:media") + f"?sort={sort}").status_code, 200, sort)
        self.assertTrue(a.pk and b.pk and pdf.pk)

    def test_single_download_is_an_attachment_with_a_friendly_name(self):
        a = self.upload("team photo.png")
        r = self.client.get(reverse("dashboard:media_download", args=[a.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertIn("attachment", r["Content-Disposition"])
        self.assertIn("team photo.png", r["Content-Disposition"])
        self.assertEqual(b"".join(r.streaming_content)[:8], b"\x89PNG\r\n\x1a\n")

    def test_download_of_a_missing_file_is_a_404_not_a_crash(self):
        a = MediaAsset.objects.create(file="uploads/gone/none.png", kind="image", original_name="none.png", size=1)
        self.assertEqual(self.client.get(reverse("dashboard:media_download", args=[a.pk])).status_code, 404)

    def test_download_requires_login(self):
        a = self.upload()
        self.client.logout()
        r = self.client.get(reverse("dashboard:media_download", args=[a.pk]))
        self.assertEqual(r.status_code, 302)

    def test_bulk_zip_contains_the_selected_files_with_unique_names(self):
        a = self.upload("same.png")
        b = self.upload("same.png")
        c = self.upload("other.png")
        r = self.client.post(reverse("dashboard:media_bulk"), {"action": "download", "ids": [a.pk, b.pk]})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "application/zip")
        names = zipfile.ZipFile(io.BytesIO(b"".join(r.streaming_content))).namelist()
        self.assertEqual(len(names), 2)
        self.assertEqual(len(set(names)), 2)
        self.assertNotIn("other.png", names)
        self.assertTrue(c.pk)

    def test_bulk_requires_a_selection_and_a_known_action(self):
        r = self.client.post(reverse("dashboard:media_bulk"), {"action": "download"})
        self.assertEqual(r.status_code, 302)
        a = self.upload()
        r = self.client.post(reverse("dashboard:media_bulk"), {"action": "explode", "ids": [a.pk]})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(MediaAsset.objects.filter(pk=a.pk).exists())

    def test_bulk_next_cannot_redirect_off_site(self):
        for evil in ("https://evil.example/", "//evil.example/", "/dashboard/media/..//evil.example", "/other/"):
            r = self.client.post(reverse("dashboard:media_bulk"), {"action": "download", "next": evil})
            loc = r["Location"]
            self.assertTrue(loc.startswith("/dashboard/media/"), loc)
            self.assertNotIn("//", loc.replace("://", ""))

    def test_bulk_delete_keeps_files_that_are_in_use(self):
        used = self.upload("used.png")
        free = self.upload("free.png")
        s = SiteSettings.load()
        s.logo_url = used.url  # the logo references the file → it is "in use"
        s.save()
        self.assertIn(used.pk, media_used_ids([used, free]))
        self.assertNotIn(free.pk, media_used_ids([used, free]))

        r = self.client.post(reverse("dashboard:media_bulk"), {"action": "delete", "ids": [used.pk, free.pk]})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(MediaAsset.objects.filter(pk=used.pk).exists())
        self.assertFalse(MediaAsset.objects.filter(pk=free.pk).exists())

    def test_bulk_delete_needs_the_delete_permission(self):
        seo = self.make_user("seo2@example.com", role_slug="seo_manager")  # media: view/create/edit only
        a = self.upload()
        self.login(seo)
        r = self.client.post(reverse("dashboard:media_bulk"), {"action": "delete", "ids": [a.pk]})
        self.assertEqual(r.status_code, 403)
        self.assertTrue(MediaAsset.objects.filter(pk=a.pk).exists())
        self.assertEqual(self.client.get(reverse("dashboard:media_download", args=[a.pk])).status_code, 200)  # but may still download

    def test_media_used_ids_is_empty_for_nothing_and_detects_json_references(self):
        self.assertEqual(media_used_ids([]), set())
        a = self.upload("json.png")
        s = SiteSettings.load()
        s.logo_url = a.url
        s.save()
        self.assertEqual(media_used_ids([a]), {a.pk})

    def test_edit_details_saves_title_alt_and_caption(self):
        a = self.upload()
        r = self.client.post(reverse("dashboard:media_edit", args=[a.pk]), {"title": "New title", "alt_text": "A team", "caption": "Us"}, HTTP_X_REQUESTED_WITH="fetch")
        self.assertIn(r.status_code, (200, 302))
        a.refresh_from_db()
        self.assertEqual((a.title, a.alt_text, a.caption), ("New title", "A team", "Us"))

    def test_single_delete_is_blocked_while_the_file_is_used(self):
        a = self.upload()
        s = SiteSettings.load()
        s.logo_url = a.url
        s.save()
        self.client.post(reverse("dashboard:media_delete", args=[a.pk]), HTTP_X_REQUESTED_WITH="fetch")
        self.assertTrue(MediaAsset.objects.filter(pk=a.pk).exists())
