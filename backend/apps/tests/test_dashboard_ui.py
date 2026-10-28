"""Dashboard redesign acceptance: logo changes reach the dashboard, sign-in page and website; every module has a safe read-only details page."""
import tempfile
from pathlib import Path

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.forms.models import model_to_dict
from django.test import override_settings
from django.urls import reverse

from apps.blog.models import Post
from apps.cms.models import Service
from apps.core.models import SiteSettings
from apps.dashboard import registry
from apps.dashboard.forms import make_form

from .base import Base
from .test_chat_seo_media import png_bytes


class LogoPropagationTests(Base):
    def setUp(self):
        super().setUp()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.media = override_settings(MEDIA_ROOT=self._tmp.name)
        self.media.enable()
        self.addCleanup(self.media.disable)
        self.login(self.root)

    def upload_logo(self):
        r = self.client.post(reverse("dashboard:media_upload"), {"files": SimpleUploadedFile("logo.png", png_bytes((120, 120)), content_type="image/png")})
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()["items"][0]["url"]

    def save_brand(self, **changes):
        """Save the Branding page exactly like the dashboard form does (all current values + the change)."""
        from apps.dashboard.views_brand import BrandingForm

        s = SiteSettings.load()
        data = {k: ("" if v is None else v) for k, v in model_to_dict(s, fields=BrandingForm.Meta.fields).items()}
        if not data.get("header_show_name"):
            data.pop("header_show_name", None)  # unchecked checkboxes are simply absent from a real POST
        data.update(changes)
        r = self.client.post(reverse("dashboard:branding"), data)
        self.assertEqual(r.status_code, 302, getattr(r, "context", None) and r.context["form"].errors)

    def test_default_dashboard_shows_initials_mark(self):
        html = self.client.get(reverse("dashboard:home")).content.decode()
        self.assertIn("AUB SQUARE", html)
        self.assertIn('data-brand-mark', html)
        self.assertNotIn("<img src=\"/media/", html.split('class="brand__mark')[1][:200])

    def test_new_logo_appears_in_dashboard_login_page_api_and_website_shell(self):
        url = self.upload_logo()
        self.assertTrue(url.startswith(("/media/", "http")), url)
        self.save_brand(logo_url=url, site_name="Studio Nine")
        path = "/media/" + url.split("/media/")[1]

        dash = self.client.get(reverse("dashboard:home")).content.decode()
        self.assertIn(path, dash)
        self.assertIn("Studio Nine", dash)
        self.assertIn('rel="icon"', dash)

        self.client.logout()
        login = self.client.get(reverse("accounts:login")).content.decode()
        self.assertIn(path, login)  # the sign-in page uses the same logo
        self.assertIn("Studio Nine", login)

        api = self.client.get("/api/v1/bootstrap/").json()
        self.assertIn(path, api["site"]["logo"])
        self.assertEqual(api["site"]["siteName"], "Studio Nine")

        with tempfile.TemporaryDirectory() as dist:
            Path(dist, "index.html").write_text('<!doctype html><html><head><title>x</title><link rel="icon" href="/old.ico"></head><body><div id="root"></div></body></html>', encoding="utf-8")
            from apps.seo import views as seo_views

            seo_views._shell_cache.update(mtime=None, html="")
            with override_settings(FRONTEND_DIST=dist):
                resp = self.client.get("/")
            self.assertEqual(resp.status_code, 200)
            body = resp.content.decode()
            self.assertIn(f'<link rel="icon" href="{url}"', body)
            self.assertNotIn("/old.ico", body)
            self.assertIn(path, body)  # bootstrap payload carries the new logo
            self.assertIn("no-cache", resp["Cache-Control"])  # so a dashboard change is visible on the next load

    def test_logo_change_busts_caches_immediately(self):
        self.client.get("/api/v1/bootstrap/")  # warm the public cache
        url = self.upload_logo()
        self.save_brand(logo_url=url)
        self.assertIn("/media/", self.client.get("/api/v1/bootstrap/").json()["site"]["logo"])
        self.save_brand(logo_url="")
        self.assertEqual(self.client.get("/api/v1/bootstrap/").json()["site"]["logo"], "")

    def test_dashboard_logo_url_has_cache_buster_and_uses_local_path(self):
        self.save_brand(logo_url="http://other-host.example/media/uploads/x.png")
        dash = self.client.get(reverse("dashboard:home")).content.decode()
        self.assertIn('src="/media/uploads/x.png?v=', dash)  # host-independent + refreshes after every settings save


class DetailPageTests(Base):
    def setUp(self):
        super().setUp()
        self.login(self.root)

    def test_every_registry_module_has_working_list_form_and_detail(self):
        for slug, m in registry.REGISTRY.items():
            with self.subTest(module=slug):
                self.assertEqual(self.client.get(reverse("dashboard:list", args=[slug]), follow=True).status_code, 200)
                if m.singleton:
                    continue
                if m.can_create:
                    self.assertEqual(self.client.get(reverse("dashboard:create", args=[slug])).status_code, 200)
                for obj in m.Model.objects.all()[:3]:
                    self.assertEqual(self.client.get(reverse("dashboard:detail", args=[slug, obj.pk])).status_code, 200)
                    self.assertEqual(self.client.get(reverse("dashboard:edit", args=[slug, obj.pk])).status_code, 200)

    def test_detail_shows_values_and_links(self):
        svc = Service.objects.create(title="Brand Identity", slug="brand-identity", short_description="Logos that last", status="published")
        r = self.client.get(reverse("dashboard:detail", args=["services", svc.pk]))
        self.assertContains(r, "Brand Identity")
        self.assertContains(r, "Logos that last")
        self.assertContains(r, reverse("dashboard:edit", args=["services", svc.pk]))
        lst = self.client.get(reverse("dashboard:list", args=["services"]))
        self.assertContains(lst, reverse("dashboard:detail", args=["services", svc.pk]))
        form = self.client.get(reverse("dashboard:edit", args=["services", svc.pk]))
        self.assertContains(form, reverse("dashboard:detail", args=["services", svc.pk]))

    def test_rich_text_is_sanitised_on_the_details_page(self):
        post = Post.objects.create(title="Hello", slug="hello", status="draft", content_html='<p>ok</p><script>alert(1)</script><img src=x onerror=alert(2)>')
        r = self.client.get(reverse("dashboard:detail", args=["posts", post.pk]))
        self.assertNotContains(r, "<script>alert(1)")
        self.assertNotContains(r, "onerror=")

    def test_detail_requires_view_permission_and_login(self):
        svc = Service.objects.create(title="X", slug="x", status="draft")
        url = reverse("dashboard:detail", args=["services", svc.pk])
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)  # to sign-in
        nobody = self.make_user("nobody@example.com")  # approved, no role
        self.login(nobody)
        self.assertIn(self.client.get(url).status_code, (302, 403))

    def test_unknown_record_is_404(self):
        self.assertEqual(self.client.get(reverse("dashboard:detail", args=["services", 99999])).status_code, 404)

    def test_secret_fields_never_rendered(self):
        from apps.dashboard.crud import _detail_item

        class Dummy:
            _meta = Service._meta

        self.assertIsNone(_detail_item(registry.get("services"), Service(), "api_key"))
        self.assertIsNone(_detail_item(registry.get("services"), Service(), "password"))


class ThemeShellTests(Base):
    def test_pages_ship_theme_switch_and_prepaint_script(self):
        self.login(self.root)
        html = self.client.get(reverse("dashboard:home")).content.decode()
        self.assertIn('data-theme-set="light"', html)
        self.assertIn('data-theme-set="dark"', html)
        self.assertIn("aub.theme", html)  # no flash of the wrong theme
        self.assertIn("theme.js", html)
        self.client.logout()
        login = self.client.get(reverse("accounts:login")).content.decode()
        self.assertIn('data-theme-set="dark"', login)
        self.assertIn("aub.theme", login)


class NavigationAndHomeTests(Base):
    """The side menu must list every page the user may open, with its name – nothing hidden behind icons."""

    def test_side_menu_lists_every_page_with_labels_including_testimonials_and_branding(self):
        self.login(self.root)
        html = self.client.get(reverse("dashboard:home")).content.decode()
        rail = html.split('id="railnav"')[1].split("</nav>")[0]
        for label in ("Testimonials", "FAQs", "Branding &amp; logo", "Website settings", "Media library", "Blog", "Services", "Portfolio",
                      "Leads &amp; messages", "Chatbot &amp; live chat", "Email inbox", "SEO", "Campaigns", "Ads manager", "Users &amp; roles", "Security &amp; activity"):
            self.assertIn(f'<span class="lbl">{label}</span>', rail, label)

    def test_branding_link_points_at_the_brand_section_that_exists(self):
        self.login(self.root)
        home = self.client.get(reverse("dashboard:home")).content.decode()
        self.assertIn('href="/dashboard/branding/"', home)
        page = self.client.get("/dashboard/branding/")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Branding", page.content.decode())

    def test_testimonials_module_opens_from_the_menu(self):
        self.login(self.root)
        self.assertEqual(self.client.get("/dashboard/testimonials/").status_code, 200)

    def test_menu_only_shows_pages_the_user_may_see(self):
        self.login(self.make_user("cm@example.com", role_slug="content_manager"))
        html = self.client.get(reverse("dashboard:home")).content.decode()
        rail = html.split('id="railnav"')[1].split("</nav>")[0]
        self.assertIn('<span class="lbl">Testimonials</span>', rail)
        self.assertNotIn('<span class="lbl">Users &amp; roles</span>', rail)
        self.assertNotIn('<span class="lbl">Security &amp; activity</span>', rail)

    def test_home_counts_come_from_real_records(self):
        from apps.leads.models import Lead

        self.login(self.root)
        before = self.client.get(reverse("dashboard:home")).context["kpis"]["leads_30"]
        Lead.objects.create(name="Real Person", email="real@example.com", message="hi", status="qualified")
        r = self.client.get(reverse("dashboard:home"))
        self.assertEqual(r.context["kpis"]["leads_30"], before + 1)
        self.assertEqual(r.context["kpis"]["leads_qualified"], 1)
        html = r.content.decode()
        self.assertIn("Good ", html)
        self.assertIn("Pipeline", html)
        self.assertIn("Real Person", html)


class FixedSidebarAndModernFormTests(Base):
    """The side menu is one fixed card whose list scrolls inside it; form pages use the sectioned layout."""

    def test_sidebar_is_a_single_scrolling_list_with_tooltips_and_a_collapse_handle(self):
        self.login(self.root)
        html = self.client.get(reverse("dashboard:home")).content.decode()
        self.assertIn('id="railnav"', html)  # the only part that scrolls
        self.assertIn("data-rail-toggle", html)
        self.assertIn('class="rail__handle"', html)
        self.assertIn('id="railtip"', html)
        self.assertIn('data-tip="Testimonials"', html)  # shown as a tooltip when the menu is icon-only
        self.assertIn('data-tip="Sign out"', html)

    def test_sidebar_css_is_sticky_with_inner_scroll(self):
        from pathlib import Path

        css = (Path(__file__).resolve().parents[2] / "static/dashboard/dashboard.css").read_text()
        block = css[css.index("/* ------------------------------------------------------------ side menu\n"):]
        self.assertRegex(block, r"\.rail \{ position: sticky;")
        self.assertRegex(block, r"\.railnav \{[^}]*overflow-y: auto")

    def test_form_page_has_numbered_sections_toc_and_save_panel(self):
        self.login(self.root)
        page = self.client.get("/dashboard/site-settings/1/").content.decode()
        for needle in ('class="fl"', 'class="card fieldset fsec', 'fsec__num', 'class="card fl__toc"', 'data-spy="fs-contact-details"', "fl__panel", "fl__mobile", "state-dirty"):
            self.assertIn(needle, page, needle)
        self.assertIn('id="fs-contact-details"', page)
        self.assertIn('href="#fs-contact-details"', page)

    def test_checkbox_fields_render_as_toggle_rows(self):
        self.login(self.root)
        page = self.client.get("/dashboard/site-settings/1/").content.decode()
        self.assertIn("field--check", page)
        self.assertIn("field__text", page)

    def test_media_picker_fields_use_the_full_width(self):
        self.login(self.root)
        page = self.client.get("/dashboard/site-settings/1/").content.decode()
        i = page.index("media-picker")
        self.assertIn("field--wide", page[max(0, i - 700):i])

    def test_form_still_saves_and_secret_fields_are_not_echoed(self):
        self.login(self.root)
        page = self.client.get("/dashboard/chatbot-settings/1/")
        self.assertEqual(page.status_code, 200)
        self.assertNotIn("sk-", page.content.decode())
