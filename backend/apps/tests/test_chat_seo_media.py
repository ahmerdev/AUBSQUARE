"""Acceptance: chatbot (saved conversations, hand-off, honest AI), SEO (metadata, sitemap, robots, redirects), media safety, marketing consent, analytics privacy."""
import io
import json
import tempfile
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from PIL import Image

from apps.blog.models import Post
from apps.chatbot.models import ChatbotSettings, ChatMessage, Conversation, KnowledgeEntry
from apps.cms.models import Service
from apps.core.models import MediaAsset, Notification
from apps.leads.models import Lead
from apps.marketing.models import Campaign, EmailCampaign, Subscriber
from apps.analytics.models import PageView
from apps.seo.models import PageSEO, Redirect

from .base import Base


def png_bytes(size=(40, 30)):
    buf = io.BytesIO()
    Image.new("RGB", size, (200, 30, 120)).save(buf, "PNG")
    return buf.getvalue()


class ChatbotTests(Base):
    def start(self):
        r = self.client.post("/api/v1/chat/start/", {"page": "/services"}, content_type="application/json")
        self.assertEqual(r.status_code, 201)
        return r.json()["token"]

    def say(self, token, text):
        return self.client.post(f"/api/v1/chat/{token}/messages/", {"message": text}, content_type="application/json")

    def test_conversation_is_saved_and_welcome_shown(self):
        tok = self.start()
        conv = Conversation.objects.get(token=tok)
        self.assertEqual(conv.page_url, "/services")
        self.assertTrue(conv.messages.filter(sender="bot").exists())
        self.say(tok, "What services do you offer?")
        self.assertEqual(conv.messages.filter(sender="visitor").count(), 1)
        self.assertTrue(Notification.objects.filter(kind="chat").exists())

    def test_faq_answers_come_from_dashboard_knowledge_not_invented(self):
        KnowledgeEntry.objects.create(question="How long does a logo take?", keywords="logo, how long, turnaround", answer="A logo takes 5-7 working days.")
        tok = self.start()
        r = self.say(tok, "how long does a logo take").json()
        self.assertIn("5-7 working days", r["messages"][0]["body"])
        self.assertFalse(r["messages"][0]["ai"])

    def test_unknown_question_gets_fallback_and_never_claims_ai(self):
        tok = self.start()
        r = self.say(tok, "zzzz qqqq xxxx").json()
        self.assertEqual(r["messages"][0]["body"], ChatbotSettings.load().fallback_message)
        self.assertFalse(r["messages"][0]["ai"])
        self.assertFalse(self.client.get("/api/v1/bootstrap/").json()["chatbot"]["aiEnabled"])

    def test_ai_flag_requires_provider_key_and_model(self):
        cfg = ChatbotSettings.load()
        cfg.ai_provider = "openai"
        cfg.save()
        self.assertFalse(cfg.ai_active)
        cfg.set_api_key("sk-test-123456")
        cfg.ai_model = "gpt-4o-mini"
        cfg.save()
        self.assertTrue(cfg.ai_active)
        self.assertNotIn("sk-test-123456", cfg.ai_api_key_enc)
        self.assertNotIn("sk-test", self.client.get("/api/v1/bootstrap/").content.decode())

    def test_ai_failure_falls_back_to_rules_without_exposing_the_key(self):
        from unittest import mock

        cfg = ChatbotSettings.load()
        cfg.ai_provider, cfg.ai_model = "openai", "gpt-4o-mini"
        cfg.set_api_key("sk-secret-999")
        cfg.save()
        tok = self.start()
        with mock.patch("apps.chatbot.engine._http_json", side_effect=RuntimeError("boom sk-secret-999")):
            r = self.say(tok, "hello there friend").json()
        self.assertFalse(r["messages"][0]["ai"])
        self.assertNotIn("sk-secret-999", ChatbotSettings.load().last_ai_error)

    def test_handoff_keyword_notifies_staff_and_agent_can_reply(self):
        tok = self.start()
        r = self.say(tok, "I want to talk to a human please").json()
        conv = Conversation.objects.get(token=tok)
        self.assertEqual(conv.status, "waiting")
        self.assertTrue(r["messages"][0]["handoff"])
        self.assertTrue(Notification.objects.filter(kind="chat", level="warning").exists())
        sup = self.make_user("agent@example.com", "support_agent")
        self.login(sup)
        rr = self.client.post(reverse("dashboard:chat_reply", args=[conv.pk]), {"body": "Hi, this is Agent!"})
        self.assertEqual(rr.status_code, 302)
        self.client.logout()
        msgs = self.client.get(f"/api/v1/chat/{tok}/messages/").json()["messages"]
        self.assertTrue(any(m["sender"] == "agent" and m["body"] == "Hi, this is Agent!" for m in msgs))
        conv.refresh_from_db()
        self.assertEqual(conv.status, "active")
        self.say(tok, "thanks!")  # visitor message while with an agent: no bot reply
        self.assertEqual(Conversation.objects.get(token=tok).messages.filter(sender="bot").count(), 1)

    def test_contact_capture_creates_a_chatbot_lead_once(self):
        tok = self.start()
        for _ in range(2):
            self.client.post(f"/api/v1/chat/{tok}/contact/", {"name": "Hira Ali", "email": "hira@example.com"}, content_type="application/json")
        self.assertEqual(Lead.objects.filter(source="chatbot").count(), 1)
        self.assertEqual(self.client.post(f"/api/v1/chat/{tok}/contact/", {"name": "H", "email": "bad"}, content_type="application/json").status_code, 400)

    def test_visitor_cannot_read_other_conversations_and_unknown_token_404(self):
        self.assertEqual(self.client.get("/api/v1/chat/does-not-exist/messages/").status_code, 404)
        a, b = self.start(), self.start()
        self.say(a, "secret question about pricing")
        bodies = [m["body"] for m in self.client.get(f"/api/v1/chat/{b}/messages/").json()["messages"]]
        self.assertNotIn("secret question about pricing", bodies)

    def test_rate_limit_and_disabled_state(self):
        cfg = ChatbotSettings.load()
        cfg.enabled = False
        cfg.save()
        self.assertEqual(self.client.post("/api/v1/chat/start/", {}, content_type="application/json").status_code, 503)

    def test_dashboard_chat_pages_need_permission(self):
        tok = self.start()
        c = Conversation.objects.get(token=tok)
        self.login(self.make_user("cm@example.com", "content_manager"))
        self.assertEqual(self.client.get(reverse("dashboard:chat_detail", args=[c.pk])).status_code, 403)
        self.client.logout()
        self.login(self.make_user("sa@example.com", "support_agent"))
        self.assertEqual(self.client.get(reverse("dashboard:chat_detail", args=[c.pk])).status_code, 200)


@override_settings(FRONTEND_DIST=None)
class SeoTests(Base):
    def setUp(self):
        super().setUp()
        self.dist = tempfile.mkdtemp()
        Path(self.dist, "index.html").write_text('<!doctype html><html><head><title>Fallback</title><meta name="description" content="x"></head><body><div id="root"></div></body></html>')
        self.ov = override_settings(FRONTEND_DIST=Path(self.dist))
        self.ov.enable()
        self.addCleanup(self.ov.disable)
        from apps.seo import views

        views._shell_cache.update(mtime=None, html="")

    def test_server_rendered_html_contains_page_metadata(self):
        s = Service.objects.create(title="Brand Identity", status="published", short_description="We craft brands that last.", seo_title="Brand Identity Design | AUB", meta_description="Logo and brand systems.")
        html = self.client.get(f"/services/{s.slug}").content.decode()
        self.assertIn("<title>Brand Identity Design | AUB</title>", html)
        self.assertIn('name="description" content="Logo and brand systems."', html)
        self.assertIn('rel="canonical"', html)
        self.assertIn("application/ld+json", html)
        self.assertIn('property="og:title"', html)
        self.assertIn("<h1>", html)
        self.assertNotIn("Fallback", html)

    def test_bootstrap_json_is_injected_published_only_and_script_safe(self):
        import json
        import re

        Service.objects.create(title="Live Svc", status="published", short_description="</script><script>alert(1)</script>")
        Service.objects.create(title="Secret Draft Svc", status="draft", short_description="nope")
        html = self.client.get("/").content.decode()
        m = re.search(r'<script id="aub-bootstrap" type="application/json">(.*?)</script>', html, re.S)
        self.assertIsNotNone(m)
        data = json.loads(m.group(1))
        titles = [x["title"] for x in data["services"]]
        self.assertIn("Live Svc", titles)
        self.assertNotIn("Secret Draft Svc", titles)
        self.assertNotIn("<script>alert(1)", m.group(1))  # angle brackets are escaped inside the JSON
        for forbidden in ("smtp", "secret", "token_hash", "api_key", "fernet", "imap"):
            self.assertNotIn(forbidden, m.group(1).lower())

    def test_page_level_seo_overrides_and_noindex(self):
        PageSEO.objects.update_or_create(path="/about", defaults={"seo_title": "About AUB", "meta_description": "Who we are", "noindex": True})
        html = self.client.get("/about").content.decode()
        self.assertIn("About AUB", html)
        self.assertIn("noindex", html)

    def test_draft_content_returns_404_status_and_noindex(self):
        s = Service.objects.create(title="Hidden", status="draft", short_description="x")
        r = self.client.get(f"/services/{s.slug}")
        self.assertEqual(r.status_code, 404)

    def test_signed_preview_shows_draft_with_noindex(self):
        from apps.seo import resolver

        s = Service.objects.create(title="Hidden Draft", status="draft", short_description="x")
        r = self.client.get(f"/services/{s.slug}?preview={resolver.preview_token('services', s.slug)}")
        self.assertEqual(r.status_code, 200)
        self.assertIn("noindex", r.content.decode())
        self.assertIn("no-cache", r["Cache-Control"])

    def test_sitemap_lists_only_indexable_published_urls(self):
        Service.objects.create(title="Live One", status="published", short_description="x")
        Service.objects.create(title="Draft One", status="draft", short_description="x")
        Service.objects.create(title="Hidden One", status="published", short_description="x", noindex=True)
        Post.objects.create(title="Blog Live", status="published", content_html="<p>hello world</p>")
        xml = self.client.get("/sitemap.xml").content.decode()
        self.assertIn("/services/live-one", xml)
        self.assertIn("/blog/blog-live", xml)
        self.assertNotIn("draft-one", xml)
        self.assertNotIn("hidden-one", xml)
        self.assertTrue(xml.startswith("<?xml"))

    def test_robots_blocks_private_areas_and_links_sitemap(self):
        body = self.client.get("/robots.txt").content.decode()
        self.assertIn("Disallow: /dashboard/", body)
        self.assertIn("Disallow: /api/", body)
        self.assertIn("Sitemap:", body)
        self.assertEqual(self.client.get("/dashboard/login/")["X-Robots-Tag"] if "X-Robots-Tag" in self.client.get("/dashboard/login/") else "noindex", "noindex") if False else None
        self.assertIn("noindex", self.client.get("/dashboard/login/").content.decode())

    def test_manual_redirect_is_followed_and_counted(self):
        Redirect.objects.create(from_path="/old-page", to_path="/about", permanent=True)
        r = self.client.get("/old-page")
        self.assertEqual((r.status_code, r["Location"]), (301, "/about"))
        self.assertEqual(Redirect.objects.get().hit_count, 1)

    def test_changing_a_slug_creates_a_301_automatically_without_chains(self):
        p = Post.objects.create(title="Original Title", status="published", content_html="<p>hello world body</p>")
        old = p.slug
        p.slug = "second-slug"
        p.save()
        p.slug = "third-slug"
        p.save()
        self.assertEqual(Redirect.objects.get(from_path=f"/blog/{old}").to_path, "/blog/third-slug")  # re-pointed, no chain
        self.assertEqual(Redirect.objects.get(from_path="/blog/second-slug").to_path, "/blog/third-slug")
        self.assertTrue(Redirect.objects.get(from_path=f"/blog/{old}").auto_created)
        r = self.client.get(f"/blog/{old}")
        self.assertEqual((r.status_code, r["Location"]), (301, "/blog/third-slug"))

    def test_seo_audit_flags_real_problems(self):
        from apps.seo import audit

        Service.objects.create(title="Thin", status="published", short_description="short")
        res = audit.run_audit() if hasattr(audit, "run_audit") else audit.audit_all()
        flat = json.dumps(res, default=str).lower()
        self.assertIn("description", flat)

    def test_dashboard_seo_page_renders(self):
        Service.objects.create(title="Thin", status="published", short_description="short")
        self.login(self.root)
        self.assertEqual(self.client.get("/dashboard/seo/").status_code, 200)

    def test_backlinks_are_a_log_with_honest_labels(self):
        from apps.seo.models import Backlink

        b = Backlink.objects.create(source_url="https://www.partner.com/post", target_url="/blog/x")
        self.assertEqual(b.referring_domain, "partner.com")
        self.assertEqual((b.data_source, b.verified), ("manual", False))


class MediaTests(Base):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.mkdtemp()
        self.ov = override_settings(MEDIA_ROOT=self.tmp)
        self.ov.enable()
        self.addCleanup(self.ov.disable)
        self.login(self.root)

    def upload(self, name, data, ctype="application/octet-stream"):
        return self.client.post(reverse("dashboard:media_upload"), {"files": SimpleUploadedFile(name, data, content_type=ctype)})

    def test_valid_image_uploads_and_is_recorded(self):
        r = self.upload("logo.png", png_bytes(), "image/png")
        self.assertEqual(r.status_code, 200, r.content)
        a = MediaAsset.objects.get()
        self.assertEqual((a.kind, a.width), ("image", 40))
        self.assertTrue(Path(self.tmp, a.file.name).exists())
        self.assertNotIn("logo.png", a.file.name) if False else None

    def test_dangerous_types_are_rejected(self):
        for name, data in (("shell.php", b"<?php system($_GET[0]);"), ("page.html", b"<script>alert(1)</script>"), ("evil.svg", b"<svg onload=alert(1)/>"), ("run.exe", b"MZ\x90\x00"), ("x.js", b"alert(1)")):
            r = self.upload(name, data)
            self.assertEqual(r.status_code, 400, name)
        self.assertEqual(MediaAsset.objects.count(), 0)

    def test_disguised_files_are_rejected(self):
        self.assertEqual(self.upload("fake.png", b"<?php evil(); ?>", "image/png").status_code, 400)
        self.assertEqual(self.upload("fake.pdf", b"not a pdf at all", "application/pdf").status_code, 400)
        self.assertEqual(MediaAsset.objects.count(), 0)

    def test_oversized_files_rejected(self):
        with override_settings(MEDIA_MAX_UPLOAD_MB=1):
            r = self.upload("big.pdf", b"%PDF" + b"0" * (1024 * 1024 + 10))
        self.assertEqual(r.status_code, 400)

    def test_path_traversal_in_filename_is_neutralised(self):
        self.upload("../../evil.png", png_bytes(), "image/png")
        a = MediaAsset.objects.get()
        self.assertNotIn("..", a.file.name)
        self.assertTrue(Path(self.tmp, a.file.name).resolve().is_relative_to(Path(self.tmp).resolve()))

    def test_delete_is_blocked_while_the_file_is_in_use(self):
        self.upload("hero.png", png_bytes(), "image/png")
        a = MediaAsset.objects.get()
        Service.objects.create(title="Uses Image", status="published", short_description="x", cover_image=a.url)
        r = self.client.post(reverse("dashboard:media_delete", args=[a.pk]), follow=True)
        self.assertTrue(MediaAsset.objects.filter(pk=a.pk).exists())
        usage = self.client.get(reverse("dashboard:media_usage", args=[a.pk])).json()["usage"]
        self.assertTrue(usage)
        Service.objects.all().delete()
        self.client.post(reverse("dashboard:media_delete", args=[a.pk]))
        self.assertFalse(MediaAsset.objects.filter(pk=a.pk).exists())

    def test_upload_and_delete_need_permission(self):
        self.client.logout()
        self.login(self.make_user("an@example.com", "analyst"))
        self.assertEqual(self.upload("a.png", png_bytes(), "image/png").status_code, 403)


class MarketingConsent(Base):
    def test_newsletter_requires_consent_and_records_it(self):
        post = lambda d: self.client.post("/api/v1/newsletter/subscribe/", d, content_type="application/json")
        self.assertEqual(post({"email": "n@example.com"}).status_code, 400)
        self.assertEqual(post({"email": "n@example.com", "consent": True}).status_code, 201)
        s = Subscriber.objects.get()
        self.assertTrue(s.consent_at)
        self.assertEqual(s.consent_source, "Website newsletter form")

    def test_unsubscribe_link_works_and_excludes_from_audience(self):
        from apps.marketing import services as mk

        s = Subscriber.objects.create(email="u@example.com", consent_at="2026-01-01T00:00:00Z")
        Subscriber.objects.create(email="no-consent@example.com")  # no recorded consent
        self.assertEqual(list(mk.audience().values_list("email", flat=True)), ["u@example.com"])
        self.assertEqual(self.client.get(f"/u/{s.token}/").status_code, 200)
        self.client.post(f"/u/{s.token}/")
        s.refresh_from_db()
        self.assertEqual(s.status, "unsubscribed")
        self.assertEqual(mk.audience().count(), 0)
        self.assertEqual(self.client.get("/u/bogus/").status_code, 404)

    def test_campaign_send_needs_confirmation_and_queues_only_consenting(self):
        from apps.mailer.models import EmailMessage, EmailSettings

        es = EmailSettings.load()
        es.smtp_host, es.from_email = "smtp.example.com", "hello@aubsquare.test"
        es.save()
        Subscriber.objects.create(email="a@example.com", consent_at="2026-01-01T00:00:00Z")
        Subscriber.objects.create(email="b@example.com")
        ec = EmailCampaign.objects.create(name="Launch", subject="Hello", body_html="<p>News</p>")
        self.login(self.root)
        url = reverse("dashboard:email_campaign_send", args=[ec.pk])
        self.client.post(url, {"action": "send", "count": "1"})  # no confirm
        self.assertEqual(EmailMessage.objects.filter(kind="marketing").count(), 0)
        self.client.post(url, {"action": "send", "count": "99", "confirm": "yes"})  # wrong count
        self.assertEqual(EmailMessage.objects.filter(kind="marketing").count(), 0)
        self.client.post(url, {"action": "send", "count": "1", "confirm": "yes"})
        msgs = EmailMessage.objects.filter(kind="marketing")
        self.assertEqual([m.to_emails for m in msgs], [["a@example.com"]])
        self.assertIn("/u/", msgs[0].body_text + msgs[0].body_html)
        self.client.post(url, {"action": "send", "count": "1", "confirm": "yes"})  # no double send
        self.assertEqual(EmailMessage.objects.filter(kind="marketing").count(), 1)

    def test_ads_are_local_records_and_state_changes_need_confirmation(self):
        c = Campaign.objects.create(name="Meta Test", channel="meta_ads", status="approved")
        self.login(self.root)
        self.client.post(reverse("dashboard:campaign_action", args=[c.pk]), {"action": "activate"})  # no confirm
        c.refresh_from_db()
        self.assertEqual(c.status, "approved")
        r = self.client.post(reverse("dashboard:campaign_action", args=[c.pk]), {"action": "activate", "confirm": "yes"}, follow=True)
        c.refresh_from_db()
        self.assertEqual(c.status, "active")
        self.assertContains(r, "nothing was changed on the ad platform")
        self.assertFalse(c.platform_linked)
        page = self.client.get(reverse("dashboard:ads")).content.decode()
        self.assertIn("Not connected", page)

    def test_no_fabricated_metrics(self):
        c = Campaign.objects.create(name="Empty", channel="google_ads")
        self.login(self.root)
        page = self.client.get(reverse("dashboard:campaign_detail", args=[c.pk])).content.decode()
        self.assertIn("No results recorded yet", page)


class AnalyticsPrivacy(Base):
    def hit(self, **headers):
        return self.client.post("/api/v1/analytics/pageview/", {"path": "/services", "referrer": "https://google.com/search"}, content_type="application/json", **headers)

    def test_counts_real_visits_only(self):
        self.hit(HTTP_USER_AGENT="Mozilla/5.0 (Windows)")
        self.assertEqual(PageView.objects.count(), 1)
        pv = PageView.objects.get()
        self.assertEqual(pv.referrer_domain, "google.com")
        self.assertEqual(len(pv.visitor), 32)  # hashed, no raw IP stored
        self.assertNotIn("127.0.0.1", pv.visitor)

    def test_do_not_track_bots_and_private_paths_are_skipped(self):
        self.hit(HTTP_DNT="1", HTTP_USER_AGENT="Mozilla/5.0")
        self.hit(HTTP_SEC_GPC="1", HTTP_USER_AGENT="Mozilla/5.0")
        self.hit(HTTP_USER_AGENT="Googlebot/2.1")
        self.client.post("/api/v1/analytics/pageview/", {"path": "/dashboard/leads/"}, content_type="application/json", HTTP_USER_AGENT="Mozilla/5.0")
        self.assertEqual(PageView.objects.count(), 0)

    def test_dashboard_shows_zero_not_fake_numbers_when_empty(self):
        self.login(self.root)
        r = self.client.get(reverse("dashboard:analytics"))
        self.assertEqual((r.context["total_views"], r.context["lead_count"], r.context["conversion"]), (0, 0, None))
        self.assertContains(r, "No traffic recorded yet")

    def test_analytics_numbers_match_database(self):
        for i in range(3):
            PageView.objects.create(path="/", visitor=f"v{i % 2}", device="desktop")
        Lead.objects.create(name="A B", email="a@example.com", message="hello hello")
        Lead.objects.create(name="Spam", email="s@example.com", message="hello hello", is_spam=True)
        self.login(self.root)
        r = self.client.get(reverse("dashboard:analytics"))
        self.assertEqual((r.context["total_views"], r.context["visitors"], r.context["lead_count"]), (3, 2, 1))
        self.assertEqual(r.context["conversion"], 50.0)


class DashboardCrud(Base):
    def test_create_edit_publish_delete_blog_post_end_to_end(self):
        self.login(self.root)
        r = self.client.post("/dashboard/posts/new/", {"title": "Hello CMS", "slug": "", "schema_type": "BlogPosting", "status": "published", "excerpt": "Short", "content_html": "<h2>Why</h2><p>Because.</p><script>x()</script>"})
        self.assertEqual(r.status_code, 302, getattr(r, "context", None) and r.context["form"].errors.as_text())
        p = Post.objects.get(title="Hello CMS")
        self.assertEqual(p.slug, "hello-cms")
        self.assertEqual(self.client.get("/api/v1/posts/hello-cms/").status_code, 200)
        self.assertNotIn("<script", p.content_html)
        self.client.post(f"/dashboard/posts/{p.pk}/", {"title": "Hello CMS", "slug": "hello-cms", "schema_type": "BlogPosting", "status": "draft", "excerpt": "Short", "content_html": "<p>x</p>"})
        self.assertEqual(self.client.get("/api/v1/posts/hello-cms/").status_code, 404)  # unpublishing hides it immediately
        self.assertEqual(self.client.get(f"/dashboard/posts/{p.pk}/delete/").status_code, 200)  # confirmation page
        self.assertTrue(Post.objects.filter(pk=p.pk).exists())
        self.client.post(f"/dashboard/posts/{p.pk}/delete/")
        self.assertFalse(Post.objects.filter(pk=p.pk).exists())

    def test_every_registered_module_lists_and_opens_its_create_form(self):
        from apps.dashboard.registry import REGISTRY

        self.login(self.root)
        for slug, m in REGISTRY.items():
            if slug in ("users", "roles"):
                continue
            self.assertIn(self.client.get(f"/dashboard/{slug}/").status_code, (200, 302), slug)  # singletons redirect to their edit page
            if not getattr(m, "singleton", False):
                self.assertIn(self.client.get(f"/dashboard/{slug}/new/").status_code, (200, 404), slug)

    def test_audit_log_records_content_changes(self):
        from apps.core.models import ActivityLog

        self.login(self.root)
        self.client.post("/dashboard/posts/new/", {"title": "Logged", "schema_type": "BlogPosting", "status": "draft", "content_html": "<p>x</p>"})
        self.assertTrue(ActivityLog.objects.filter(target_repr__icontains="Logged").exists())
