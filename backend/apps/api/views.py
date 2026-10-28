import logging
from datetime import timedelta

from django.core import signing
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.http import Http404
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.analytics.models import PageView
from apps.blog.models import Category, Comment, Post, Tag
from apps.blog.services import submit_comment
from apps.chatbot import engine
from apps.chatbot.models import ChatbotSettings, ChatMessage, Conversation
from apps.cms import home_schema
from apps.cms.models import FAQ, AboutPage, CaseStudy, HomeSection, Project, Service, TeamMember, Testimonial
from apps.core.models import AnnouncementBanner, NavItem, SiteSettings
from apps.core.sanitize import clean_plain
from apps.core.services import cached_public, client_ip, notify, public_media_url, visitor_hash
from apps.leads.models import BudgetOption, LeadFormConfig
from apps.leads import services as lead_services
from apps.seo import resolver
from . import serializers as S

log = logging.getLogger(__name__)


def error(message, code="validation_error", details=None, http=400):
    return Response({"error": {"code": code, "message": message, "details": details}}, status=http)


def preview_ok(request, kind, slug):
    tok = request.query_params.get("preview", "")
    return bool(tok) and resolver.read_preview_token(tok, kind, slug)


# ---------------------------------------------------------------- bootstrap
def build_bootstrap():
    site = SiteSettings.load()
    nav = {}
    for n in NavItem.objects.filter(is_active=True):
        nav.setdefault(n.location, []).append(S.nav_item(n))
    banner = AnnouncementBanner.current()
    sections = []
    for sec in HomeSection.objects.all():
        spec = home_schema.BY_KEY.get(sec.key)
        if spec:
            sections.append({"key": sec.key, "label": sec.label, "visible": sec.is_visible, "order": sec.order, "fixedFirst": bool(spec.get("fixed_first")), "data": home_schema.merged(sec)})
    sections.sort(key=lambda s: (0 if s["fixedFirst"] else 1, s["order"]))
    cfg = LeadFormConfig.load()
    bot = ChatbotSettings.load()
    services = Service.objects.live().select_related("category").prefetch_related("related_projects", "related_case_studies")
    projects = Project.objects.live().select_related("category", "service", "testimonial")
    cases = CaseStudy.objects.live().select_related("testimonial").prefetch_related("services", "related_projects")
    posts = Post.objects.live().select_related("category", "author").prefetch_related("tags")[:12]
    return {
        "site": S.site(site),
        "nav": nav,
        "banner": {"id": banner.pk, "message": banner.message, "linkLabel": banner.link_label, "linkUrl": banner.link_url, "style": banner.style, "dismissible": banner.dismissible} if banner else None,
        "home": sections,
        "services": [S.service(s) for s in services],
        "projects": [S.project(p) for p in projects],
        "caseStudies": [S.case_study(c) for c in cases],
        "testimonials": [S.testimonial(t) for t in Testimonial.objects.filter(is_published=True)],
        "faqs": [{"id": str(f.pk), "question": f.question, "answer": f.answer, "showOnHome": f.show_on_home, "group": f.group} for f in FAQ.objects.filter(is_published=True)],
        "team": [S.team_member(m) for m in TeamMember.objects.filter(is_published=True)],
        "about": S.about(AboutPage.load()),
        "latestPosts": [S.post_summary(p) for p in posts],
        "categories": [{"name": c.name, "slug": c.slug} for c in Category.objects.filter(posts__status="published").distinct()],
        "form": {
            "budgetOptions": [{"label": b.label, "value": b.value} for b in BudgetOption.objects.filter(is_active=True)],
            "serviceOptions": lead_services.service_options(cfg),
            "requirePhone": cfg.require_phone, "requireService": cfg.require_service, "requireBudget": cfg.require_budget,
            "placeholders": {"name": cfg.placeholder_name, "email": cfg.placeholder_email, "phone": cfg.placeholder_phone, "message": cfg.placeholder_message},
            "consentRequired": cfg.consent_required, "consentText": cfg.consent_text,
            "marketingOptinEnabled": cfg.marketing_optin_enabled, "marketingOptinText": cfg.marketing_optin_text,
            "successTitle": cfg.success_title, "successMessage": cfg.success_message, "errorMessage": cfg.error_message,
        },
        "chatbot": {
            "enabled": bot.enabled, "botName": bot.bot_name, "welcomeMessage": bot.welcome_message, "quickReplies": bot.quick_reply_list(),
            "privacyNotice": bot.privacy_notice, "aiEnabled": bot.ai_active, "humanHandoff": bot.human_handoff_enabled, "askContact": bot.ask_contact_details,
        },
    }


class BootstrapView(APIView):
    throttle_scope = "public"

    def get(self, request):
        data = cached_public("bootstrap", build_bootstrap, 300)
        resp = Response(data)
        resp["Cache-Control"] = "public, max-age=30"
        return resp


class FormTokenView(APIView):
    throttle_scope = "public"

    def get(self, request):
        return Response({"token": lead_services.issue_form_token()})


# ---------------------------------------------------------------- generic list/detail for CMS content
def paginate(request, qs, serializer):
    from apps.core.api import StandardPagination

    pg = StandardPagination()
    page = pg.paginate_queryset(qs, request)
    return pg.get_paginated_response([serializer(o) for o in page])


class ServiceList(APIView):
    throttle_scope = "public"

    def get(self, request):
        qs = Service.objects.live().select_related("category").prefetch_related("related_projects", "related_case_studies")
        return paginate(request, qs, S.service)


class ServiceDetail(APIView):
    throttle_scope = "public"

    def get(self, request, slug):
        qs = Service.objects.select_related("category").prefetch_related("related_projects", "related_case_studies")
        obj = qs.filter(slug=slug).first()
        if not obj or not (obj.is_live or preview_ok(request, "services", slug)):
            raise Http404
        return Response(S.service(obj))


class ProjectList(APIView):
    throttle_scope = "public"

    def get(self, request):
        qs = Project.objects.live().select_related("category", "service", "testimonial")
        if request.query_params.get("category"):
            qs = qs.filter(category__slug=request.query_params["category"])
        if request.query_params.get("featured"):
            qs = qs.filter(featured=True)
        return paginate(request, qs, S.project)


class ProjectDetail(APIView):
    throttle_scope = "public"

    def get(self, request, slug):
        obj = Project.objects.select_related("category", "service", "testimonial").filter(slug=slug).first()
        if not obj or not (obj.is_live or preview_ok(request, "portfolio", slug)):
            raise Http404
        return Response(S.project(obj))


class CaseStudyList(APIView):
    throttle_scope = "public"

    def get(self, request):
        qs = CaseStudy.objects.live().select_related("testimonial").prefetch_related("services", "related_projects")
        if request.query_params.get("industry"):
            qs = qs.filter(industry__iexact=request.query_params["industry"])
        return paginate(request, qs, S.case_study)


class CaseStudyDetail(APIView):
    throttle_scope = "public"

    def get(self, request, slug):
        obj = CaseStudy.objects.select_related("testimonial").prefetch_related("services", "related_projects").filter(slug=slug).first()
        if not obj or not (obj.is_live or preview_ok(request, "case-studies", slug)):
            raise Http404
        return Response(S.case_study(obj))


# ---------------------------------------------------------------- blog
class PostList(APIView):
    throttle_scope = "public"

    def get(self, request):
        qs = Post.objects.live().select_related("category", "author").prefetch_related("tags")
        q = request.query_params
        if q.get("category"):
            qs = qs.filter(category__slug=q["category"])
        if q.get("tag"):
            qs = qs.filter(tags__slug=q["tag"])
        if q.get("featured"):
            qs = qs.filter(featured=True)
        if q.get("q"):
            term = clean_plain(q["q"], 80)
            qs = qs.filter(Q(title__icontains=term) | Q(excerpt__icontains=term))
        return paginate(request, qs.distinct(), S.post_summary)


class PostDetail(APIView):
    throttle_scope = "public"

    def get(self, request, slug):
        obj = Post.objects.select_related("category", "author").prefetch_related("tags", "related_posts").filter(slug=slug).first()
        if not obj or not (obj.is_live or preview_ok(request, "blog", slug)):
            raise Http404
        related = [r for r in obj.related_posts.live()[:3]]
        if len(related) < 3:
            extra = Post.objects.live().exclude(pk=obj.pk).exclude(pk__in=[r.pk for r in related])
            if obj.category_id:
                extra = extra.filter(category=obj.category)
            related += list(extra.select_related("category", "author").prefetch_related("tags")[: 3 - len(related)])
        data = S.post_detail(obj, related)
        data["commentsCount"] = obj.comments.filter(status=Comment.APPROVED).count()
        return Response(data)


class TaxonomyView(APIView):
    throttle_scope = "public"

    def get(self, request):
        return Response({
            "categories": [{"name": c.name, "slug": c.slug, "description": c.description} for c in Category.objects.all()],
            "tags": [{"name": t.name, "slug": t.slug} for t in Tag.objects.filter(posts__status="published").distinct()],
        })


class CommentsView(APIView):
    def get_throttles(self):
        self.throttle_scope = "comment" if self.request.method == "POST" else "public"
        return super().get_throttles()

    def get(self, request, slug):
        post = Post.objects.live().filter(slug=slug).first() or (Post.objects.filter(slug=slug).first() if preview_ok(request, "blog", slug) else None)
        if not post:
            raise Http404
        qs = post.comments.filter(status=Comment.APPROVED)
        return Response({"allowComments": post.allow_comments, "count": qs.count(), "comments": S.comment_tree(qs)})

    def post(self, request, slug):
        post = Post.objects.live().filter(slug=slug).first()
        if not post:
            raise Http404
        if not post.allow_comments:
            return error("Comments are closed for this article.", "comments_closed", http=403)
        cfg = LeadFormConfig.load()
        comment, errs = submit_comment(post, request.data, request, lambda t: lead_services.check_form_token(t, 3))
        if errs:
            return error("Please correct the highlighted fields.", details=errs)
        return Response({"status": "pending", "message": "Thanks! Your comment is awaiting moderation and will appear once approved."}, status=201)


# ---------------------------------------------------------------- leads
class LeadCreateView(APIView):
    throttle_scope = "contact"

    def post(self, request):
        try:
            lead, created = lead_services.submit_lead(request.data, request, source=request.data.get("source") if request.data.get("source") in ("contact_form", "quote_modal") else "quote_modal")
        except DjangoValidationError as exc:
            details = exc.message_dict if hasattr(exc, "error_dict") else {"non_field": exc.messages}
            return error("Please correct the highlighted fields.", details=details)
        cfg = LeadFormConfig.load()
        return Response({"reference": lead.reference, "title": cfg.success_title, "message": cfg.success_message, "duplicate": not created}, status=201 if created else 200)


# ---------------------------------------------------------------- chat
def _msg(m):
    return {"id": m.pk, "sender": m.sender, "body": m.body, "createdAt": m.created_at.isoformat(), "agent": m.agent.display_name if m.agent_id else "",
            "action": m.meta.get("action", ""), "links": m.meta.get("links", []), "ai": bool(m.meta.get("ai")), "handoff": bool(m.meta.get("handoff"))}


def _conv_or_404(token):
    conv = Conversation.objects.filter(token=token).first()
    if not conv:
        raise Http404
    return conv


class ChatStartView(APIView):
    throttle_scope = "chat_start"

    def post(self, request):
        bot = ChatbotSettings.load()
        if not bot.enabled:
            return error("Chat is currently unavailable.", "chat_disabled", http=503)
        conv = engine.start_conversation(request, request.data.get("page", ""))
        return Response({"token": conv.token, "status": conv.status, "messages": [_msg(m) for m in conv.messages.all()]}, status=201)


class ChatMessagesView(APIView):
    throttle_scope = "chat"

    def get(self, request, token):
        conv = _conv_or_404(token)
        after = int(request.query_params.get("after", 0) or 0)
        msgs = conv.messages.filter(id__gt=after).select_related("agent")
        return Response({"status": conv.status, "messages": [_msg(m) for m in msgs]})

    def post(self, request, token):
        conv = _conv_or_404(token)
        if conv.status == Conversation.CLOSED:
            return error("This conversation is closed. Start a new chat.", "closed", http=409)
        text = clean_plain(request.data.get("message", ""), 1000)
        if not text:
            return error("Please type a message.")
        try:
            created = engine.handle_visitor_message(conv, text)
        except ValueError as exc:
            return error(str(exc), "limit", http=429)
        conv.refresh_from_db()
        last_visitor = conv.messages.filter(sender=ChatMessage.VISITOR).last()
        return Response({"status": conv.status, "visitorMessage": _msg(last_visitor), "messages": [_msg(m) for m in created]}, status=201)


class ChatHandoffView(APIView):
    throttle_scope = "chat"

    def post(self, request, token):
        conv = _conv_or_404(token)
        bot = ChatbotSettings.load()
        if not bot.human_handoff_enabled:
            return error("Human hand-off is not available right now.", "disabled", http=403)
        msg = engine.request_handoff(conv, bot)
        conv.refresh_from_db()
        return Response({"status": conv.status, "messages": [_msg(msg)] if msg else []})


class ChatContactView(APIView):
    throttle_scope = "chat"

    def post(self, request, token):
        from django.core.validators import validate_email

        conv = _conv_or_404(token)
        name = clean_plain(request.data.get("name", ""), 100)
        email = clean_plain(request.data.get("email", ""), 254).lower()
        phone = clean_plain(request.data.get("phone", ""), 40)
        try:
            validate_email(email)
        except DjangoValidationError:
            return error("Please enter a valid email address.", details={"email": "Invalid email"})
        if len(name) < 2:
            return error("Please enter your name.", details={"name": "Required"})
        conv.visitor_name, conv.visitor_email, conv.visitor_phone = name, email, phone
        conv.save(update_fields=["visitor_name", "visitor_email", "visitor_phone", "updated_at"])
        engine.lead_from_conversation(conv, request)
        engine.add_message(conv, ChatMessage.SYSTEM, f"Thanks {name.split()[0]}! We'll follow up at {email} if we miss you here.")
        return Response({"ok": True})


# ---------------------------------------------------------------- misc public
class PageViewView(APIView):
    throttle_scope = "pageview"

    def post(self, request):
        if request.META.get("HTTP_DNT") == "1" or request.META.get("HTTP_SEC_GPC") == "1":
            return Response(status=204)
        path = clean_plain(request.data.get("path", "/"), 300).split("?")[0] or "/"
        if path.startswith(("/dashboard", "/api")):
            return Response(status=204)
        ua = request.META.get("HTTP_USER_AGENT", "").lower()
        if any(b in ua for b in ("bot", "spider", "crawl", "headless")):
            return Response(status=204)
        ref = clean_plain(request.data.get("referrer", ""), 300)
        from urllib.parse import urlparse

        host = urlparse(ref).netloc.replace("www.", "")[:200] if ref else ""
        own = urlparse(request.build_absolute_uri()).netloc.replace("www.", "")
        PageView.objects.create(
            path=path, referrer_domain="" if host == own else host, utm_source=clean_plain(request.data.get("utm_source", ""), 120),
            utm_medium=clean_plain(request.data.get("utm_medium", ""), 120), utm_campaign=clean_plain(request.data.get("utm_campaign", ""), 160),
            device="mobile" if "mobile" in ua or "android" in ua else "desktop", visitor=visitor_hash(request))
        return Response(status=204)


class SeoMetaView(APIView):
    throttle_scope = "public"

    def get(self, request):
        meta = resolver.resolve(request.query_params.get("path", "/"))
        return Response({k: meta[k] for k in ("status", "title", "description", "canonical", "robots", "og", "jsonld")})


class SubscribeView(APIView):
    throttle_scope = "contact"

    def post(self, request):
        from django.core.validators import validate_email
        from apps.marketing.models import Subscriber

        email = clean_plain(request.data.get("email", ""), 254).lower()
        try:
            validate_email(email)
        except DjangoValidationError:
            return error("Please enter a valid email address.", details={"email": "Invalid"})
        if not request.data.get("consent"):
            return error("Please tick the consent box to subscribe.", details={"consent": "Required"})
        if request.data.get("website"):
            return Response({"ok": True})
        sub, created = Subscriber.objects.get_or_create(email=email, defaults={"consent_at": timezone.now(), "consent_source": "Website newsletter form"})
        if not created and sub.status == "unsubscribed":
            sub.status, sub.consent_at, sub.unsubscribed_at = "subscribed", timezone.now(), None
            sub.save()
        return Response({"ok": True, "message": "Thanks for subscribing!"}, status=201)
