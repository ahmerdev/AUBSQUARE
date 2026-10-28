"""Acceptance: public API serves only live content; drafts hidden; scheduled posts; sanitisation; preview tokens; cache invalidation."""
from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from apps.blog.models import Category, Comment, Post
from apps.cms.models import CaseStudy, Project, Service

from .base import Base, old_token


class PublicContent(Base):
    def setUp(self):
        super().setUp()
        self.live = Service.objects.create(title="Live Service", status="published", short_description="x")
        self.draft = Service.objects.create(title="Draft Service", status="draft")
        self.sched_future = Service.objects.create(title="Future Service", status="scheduled", publish_at=timezone.now() + timedelta(days=2))
        self.sched_past = Service.objects.create(title="Past Scheduled", status="scheduled", publish_at=timezone.now() - timedelta(minutes=5))

    def test_list_contains_only_live_items(self):
        titles = [s["title"] for s in self.client.get("/api/v1/services/").json()["results"]] if "results" in self.client.get("/api/v1/services/").json() else [s["title"] for s in self.client.get("/api/v1/services/").json()]
        self.assertIn("Live Service", titles)
        self.assertIn("Past Scheduled", titles)  # scheduled time reached -> live automatically
        self.assertNotIn("Draft Service", titles)
        self.assertNotIn("Future Service", titles)

    def test_draft_and_future_detail_are_404(self):
        self.assertEqual(self.client.get(f"/api/v1/services/{self.live.slug}/").status_code, 200)
        self.assertEqual(self.client.get(f"/api/v1/services/{self.draft.slug}/").status_code, 404)
        self.assertEqual(self.client.get(f"/api/v1/services/{self.sched_future.slug}/").status_code, 404)

    def test_signed_preview_token_shows_draft_but_a_guessed_one_does_not(self):
        from apps.seo import resolver

        tok = resolver.preview_token("services", self.draft.slug)
        r = self.client.get(f"/api/v1/services/{self.draft.slug}/?preview={tok}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.client.get(f"/api/v1/services/{self.draft.slug}/?preview=forged").status_code, 404)
        other = Service.objects.create(title="Other draft", status="draft")
        self.assertEqual(self.client.get(f"/api/v1/services/{other.slug}/?preview={tok}").status_code, 404)  # token bound to one slug

    def test_bootstrap_hides_drafts_and_updates_after_publish(self):
        d = self.client.get("/api/v1/bootstrap/").json()
        self.assertNotIn("Draft Service", [s["title"] for s in d["services"]])
        self.draft.status = "published"
        self.draft.save()  # content version bumped by signal -> cache invalidated
        d = self.client.get("/api/v1/bootstrap/").json()
        self.assertIn("Draft Service", [s["title"] for s in d["services"]])

    def test_dashboard_reorder_and_visibility_reach_the_api(self):
        self.login(self.root)
        r = self.client.get("/dashboard/home-builder/")
        self.assertEqual(r.status_code, 200)
        keys = [i["sec"].key for i in r.context["items"]]
        self.assertGreater(len(keys), 3)
        order = [keys[0]] + list(reversed(keys[1:]))
        data = {"order": order}
        for it in r.context["items"]:
            for bf in it["form"]:
                v = bf.value()
                if isinstance(v, bool):
                    if v:
                        data[bf.html_name] = "on"
                elif v is not None:
                    data[bf.html_name] = v if isinstance(v, str) else (v if isinstance(v, list) else str(v))
        for k in order:
            if k != keys[1]:
                data[f"visible-{k}"] = "on"
        resp = self.client.post("/dashboard/home-builder/", data)
        self.assertEqual(resp.status_code, 302, getattr(resp, "context", None) and [(i["sec"].key, i["form"].errors.as_json()) for i in resp.context["items"] if i["form"].errors])
        home = self.client.get("/api/v1/bootstrap/").json()["home"]
        self.assertEqual(home[0]["key"], keys[0])
        self.assertEqual([s["key"] for s in home], order)
        self.assertFalse(next(s for s in home if s["key"] == keys[1])["visible"])
        self.assertTrue(all(s["visible"] for s in home if s["key"] != keys[1]))


class BlogContent(Base):
    def post(self, **kw):
        d = dict(title="A post", status="published", content_html="<h2>Intro</h2><p>Hello world</p>")
        d.update(kw)
        return Post.objects.create(**d)

    def test_html_is_sanitised_and_toc_built(self):
        p = self.post(content_html='<h2>Intro</h2><p>ok</p><script>alert(1)</script><img src=x onerror=alert(1)><a href="javascript:alert(1)">bad</a><iframe src="http://evil"></iframe>')
        for bad in ("<script", "onerror", "javascript:", "<iframe"):
            self.assertNotIn(bad, p.content_html)
        self.assertEqual(p.toc[0]["title"], "Intro")
        self.assertIn('id="intro"', p.content_html)
        d = self.client.get(f"/api/v1/posts/{p.slug}/").json()
        self.assertNotIn("<script", d["contentHtml"])

    def test_external_links_get_safe_rel(self):
        p = self.post(content_html='<p><a href="https://example.org" target="_blank">x</a></p>')
        self.assertIn("noopener", p.content_html)

    def test_related_posts_and_pagination(self):
        for i in range(15):
            self.post(title=f"Post {i}")
        r = self.client.get("/api/v1/posts/?page=2").json()
        self.assertIn("results", r)
        self.assertTrue(r["results"])
        self.assertEqual(self.client.get("/api/v1/posts/?page=999").status_code, 404)

    def test_category_filter(self):
        c = Category.objects.create(name="SEO")
        p = self.post(title="Categorised", category=c)
        self.post(title="Other")
        r = self.client.get(f"/api/v1/posts/?category={c.slug}").json()
        self.assertEqual([x["title"] for x in r["results"]], ["Categorised"])

    def test_scheduled_post_goes_live_by_itself(self):
        p = self.post(title="Soon", status="scheduled", publish_at=timezone.now() + timedelta(hours=1))
        self.assertEqual(self.client.get(f"/api/v1/posts/{p.slug}/").status_code, 404)
        Post.objects.filter(pk=p.pk).update(publish_at=timezone.now() - timedelta(seconds=1))
        from apps.core.services import bump_content_version

        bump_content_version()
        self.assertEqual(self.client.get(f"/api/v1/posts/{p.slug}/").status_code, 200)


class CommentFlow(Base):
    def setUp(self):
        super().setUp()
        self.post = Post.objects.create(title="Commentable", status="published", content_html="<p>Body text here</p>")
        self.url = f"/api/v1/posts/{self.post.slug}/comments/"

    def send(self, **kw):
        d = {"name": "Visitor", "email": "v@example.com", "message": "Great article, thanks!", "formToken": old_token()}
        d.update(kw)
        return self.client.post(self.url, d, content_type="application/json")

    def test_comment_waits_for_moderation_then_appears(self):
        r = self.send()
        self.assertEqual(r.status_code, 201)
        self.assertEqual(self.client.get(self.url).json()["count"], 0)  # not public yet
        self.login(self.root)
        c = Comment.objects.get()
        self.assertEqual(c.status, "pending")
        self.client.post(reverse("dashboard:comment_action", args=[c.pk]), {"action": "approve"})
        self.client.logout()
        data = self.client.get(self.url).json()
        self.assertEqual(data["count"], 1)
        self.assertNotIn("email", str(data["comments"]))  # commenter email is never exposed

    def test_spam_heuristics(self):
        self.send(website="http://spam.example", message="Nice nice nice post!")
        self.send(message="buy http://a.com and http://b.com now", email="b@example.com")
        self.send(formToken="", email="c@example.com", message="no token here at all")
        self.assertEqual(Comment.objects.filter(status="spam").count(), 3)
        self.assertEqual(self.client.get(self.url).json()["count"], 0)

    def test_duplicate_comment_rejected(self):
        self.send()
        self.assertEqual(self.send().status_code, 400)

    def test_replies_threaded_under_approved_parent_only(self):
        parent = Comment.objects.create(post=self.post, name="P", email="p@example.com", body="Parent", status="approved")
        self.send(parentId=parent.pk, message="A reply to parent", email="r@example.com")
        reply = Comment.objects.get(body="A reply to parent")
        self.assertEqual(reply.parent_id, parent.pk)
        pending = Comment.objects.create(post=self.post, name="Q", email="q@example.com", body="Hidden", status="pending")
        self.send(parentId=pending.pk, message="Reply to hidden one", email="s@example.com")
        self.assertIsNone(Comment.objects.get(body="Reply to hidden one").parent_id)

    def test_html_in_comment_is_stripped(self):
        self.send(message='<script>alert(1)</script>hello there', email="x@example.com")
        self.assertNotIn("<script", Comment.objects.get(email="x@example.com").body)

    def test_closed_comments_and_rate_limit(self):
        self.post.allow_comments = False
        self.post.save()
        self.assertEqual(self.send().status_code, 403)
        self.post.allow_comments = True
        self.post.save()
        codes = [self.send(email=f"u{i}@example.com", message=f"unique message {i}").status_code for i in range(10)]
        self.assertIn(429, codes)

    def test_moderation_requires_permission(self):
        c = Comment.objects.create(post=self.post, name="P", email="p@example.com", body="x", status="pending")
        self.login(self.make_user("noperm@example.com", "analyst"))
        r = self.client.post(reverse("dashboard:comment_action", args=[c.pk]), {"action": "approve"})
        self.assertEqual(r.status_code, 403)
        c.refresh_from_db()
        self.assertEqual(c.status, "pending")
