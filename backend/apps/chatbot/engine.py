"""Chat logic: rule-based FAQ assistant (always available) + optional AI provider (server-side key)."""
import json
import logging
import re
import urllib.error
import urllib.request

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.core.sanitize import clean_plain
from apps.core.services import notify, visitor_hash
from .models import ChatbotSettings, ChatMessage, Conversation, KnowledgeEntry

log = logging.getLogger(__name__)
STOP = set("the a an and or to of in on for is are can you your we i me my do does how what which with about our us it be at as by".split())
MAX_MESSAGES = 250


def tokens(text):
    return {w for w in re.findall(r"[a-z0-9$+]+", text.lower()) if w not in STOP and len(w) > 1}


def add_message(conv, sender, body, agent=None, meta=None):
    msg = ChatMessage.objects.create(conversation=conv, sender=sender, body=body[:4000], agent=agent, meta=meta or {})
    updates = {"last_message_at": msg.created_at, "last_message_preview": body[:140]}
    if sender == ChatMessage.VISITOR:
        updates["unread_for_agent"] = F("unread_for_agent") + 1
    Conversation.objects.filter(pk=conv.pk).update(**updates)
    return msg


def start_conversation(request, page_url=""):
    cfg = ChatbotSettings.load()
    conv = Conversation.objects.create(page_url=clean_plain(page_url, 300), visitor_hash=visitor_hash(request), privacy_acknowledged=True)
    add_message(conv, ChatMessage.BOT, cfg.welcome_message, meta={"welcome": True})
    return conv


# ------------------------------------------------------------------ rule based
def best_knowledge(query):
    qt = tokens(query)
    ql = query.lower()
    best, best_score = None, 0
    for e in KnowledgeEntry.objects.filter(is_active=True):
        score = 0
        for kw in [k.strip().lower() for k in e.keywords.split(",") if k.strip()]:
            if kw in ql:
                score += 3 if " " in kw else 2
        score += len(qt & tokens(e.question)) * 1.0
        if score > best_score:
            best, best_score = e, score
    return (best, best_score) if best_score >= 2 else (None, 0)


def content_matches(query):
    """Look through live services / FAQs / case studies / posts for something relevant."""
    from apps.blog.models import Post
    from apps.cms.models import FAQ, CaseStudy, Service

    qt = tokens(query)
    if not qt:
        return None
    found = []
    for s in Service.objects.live():
        sc = len(qt & (tokens(s.title) | tokens(s.short_description)))
        if sc >= 1:
            found.append((sc * 2, "service", s))
    for f in FAQ.objects.filter(is_published=True):
        sc = len(qt & tokens(f.question))
        if sc >= 2:
            found.append((sc * 2 + 1, "faq", f))
    for c in CaseStudy.objects.live():
        sc = len(qt & (tokens(c.title) | tokens(c.industry)))
        if sc >= 2:
            found.append((sc, "case", c))
    for p in Post.objects.live():
        sc = len(qt & tokens(p.title))
        if sc >= 2:
            found.append((sc, "post", p))
    found.sort(key=lambda x: -x[0])
    return found[:3] or None


def rule_based_reply(text, cfg):
    entry, _ = best_knowledge(text)
    links = []
    if entry:
        if entry.link_url:
            links.append({"label": entry.link_label or "Learn more", "url": entry.link_url})
        return entry.answer, {"action": "quote" if entry.suggest_quote else "", "links": links}
    matches = content_matches(text)
    if matches:
        parts, action = [], ""
        for _, kind, obj in matches:
            if kind == "service":
                parts.append(f"{obj.title}: {obj.short_description}")
                links.append({"label": obj.title, "url": f"/services/{obj.slug}"})
                action = "quote"
            elif kind == "faq":
                parts.append(obj.answer)
            elif kind == "case":
                parts.append(f"You might like our case study “{obj.title}”.")
                links.append({"label": "Read the case study", "url": f"/case-studies/{obj.slug}"})
            elif kind == "post":
                parts.append(f"We wrote about this: “{obj.title}”.")
                links.append({"label": "Read the article", "url": f"/blog/{obj.slug}"})
        return "\n\n".join(parts[:2]), {"action": action, "links": links[:3]}
    return cfg.fallback_message, {"action": "quote", "links": [], "fallback": True}


# ------------------------------------------------------------------ AI provider (optional)
def _http_json(url, headers, payload, timeout=25):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json", **headers}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 (fixed https endpoints configured by admin)
        return json.loads(r.read().decode())


def site_context():
    from apps.cms.models import FAQ, Service
    from apps.core.models import SiteSettings

    s = SiteSettings.load()
    lines = [f"Business: {s.site_name} – {s.tagline}.", f"Contact: {s.contact_email}, WhatsApp {s.whatsapp_number}."]
    lines.append("Services: " + "; ".join(f"{x.title} ({x.short_description})" for x in Service.objects.live()))
    lines.append("FAQs: " + " | ".join(f"Q: {f.question} A: {f.answer}" for f in FAQ.objects.filter(is_published=True)[:12]))
    for k in KnowledgeEntry.objects.filter(is_active=True)[:20]:
        lines.append(f"Q: {k.question} A: {k.answer}")
    return "\n".join(lines)


def ai_reply(conv, text, cfg):
    history = [{"role": "assistant" if m.sender in ("bot", "agent") else "user", "content": m.body}
               for m in conv.messages.exclude(sender="system").order_by("-id")[:10]][::-1]
    system = ("You are the website assistant for a creative agency. Answer ONLY from the business information below. "
              "Never invent prices, timelines, clients or results; if unsure, say so and offer to connect the visitor with the team. "
              "Be concise (max 3 short paragraphs).\n\n" + site_context() + ("\n\n" + cfg.ai_extra_instructions if cfg.ai_extra_instructions else ""))
    key = cfg.get_api_key()
    try:
        if cfg.ai_provider == "anthropic":
            out = _http_json("https://api.anthropic.com/v1/messages", {"x-api-key": key, "anthropic-version": "2023-06-01"},
                             {"model": cfg.ai_model, "max_tokens": 500, "system": system, "messages": history})
            return out["content"][0]["text"].strip()
        base = cfg.ai_base_url.rstrip("/") if cfg.ai_provider == "openai_compatible" and cfg.ai_base_url else "https://api.openai.com/v1"
        out = _http_json(f"{base}/chat/completions", {"Authorization": f"Bearer {key}"},
                         {"model": cfg.ai_model, "max_tokens": 500, "messages": [{"role": "system", "content": system}] + history})
        return out["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        err = f"{exc.__class__.__name__}: {exc}"[:280].replace(key or "\0", "••••")
        ChatbotSettings.objects.filter(pk=1).update(last_ai_error=err)
        log.warning("AI provider failed: %s", err)
        return None


# ------------------------------------------------------------------ orchestration
def request_handoff(conv, cfg, reason="visitor request"):
    if conv.status in (Conversation.WAITING, Conversation.ACTIVE):
        return None
    conv.status = Conversation.WAITING
    conv.save(update_fields=["status", "updated_at"])
    notify("chat", f"Chat needs a human: {conv.visitor_name or 'Visitor'}", conv.last_message_preview, f"/dashboard/chat/{conv.pk}/", module="chatbot", level="warning")
    try:
        from apps.mailer.service import notify_staff_by_email

        notify_staff_by_email("chat", "[AUB SQUARE] A website visitor is waiting for a human reply",
                              f"Conversation #{conv.pk} ({conv.visitor_name or 'unknown visitor'}) asked for a human.\nLast message: {conv.last_message_preview}\n/dashboard/chat/{conv.pk}/")
    except Exception:
        log.exception("handoff email failed")
    return add_message(conv, ChatMessage.SYSTEM, cfg.handoff_message, meta={"handoff": True})


@transaction.atomic
def handle_visitor_message(conv, text):
    cfg = ChatbotSettings.load()
    text = clean_plain(text, 1000)
    if not text:
        return []
    if conv.messages.count() >= MAX_MESSAGES:
        raise ValueError("This conversation is full. Please contact us by email or WhatsApp.")
    first = not conv.messages.filter(sender=ChatMessage.VISITOR).exists()
    add_message(conv, ChatMessage.VISITOR, text)
    conv.refresh_from_db()
    created = []
    if conv.status in (Conversation.WAITING, Conversation.ACTIVE):
        notify("chat", f"New chat message: {conv.visitor_name or 'Visitor'}", text[:140], f"/dashboard/chat/{conv.pk}/", module="chatbot")
        return created
    if first:
        notify("chat", "New website chat started", text[:140], f"/dashboard/chat/{conv.pk}/", module="chatbot")
        try:
            from apps.mailer.service import notify_staff_by_email

            notify_staff_by_email("chat", "[AUB SQUARE] New website chat", f"A visitor started a chat:\n\n{text}\n\n/dashboard/chat/{conv.pk}/")
        except Exception:
            log.exception("chat email failed")
    low = text.lower()
    if cfg.human_handoff_enabled and any(w in low for w in cfg.handoff_words()):
        msg = request_handoff(conv, cfg)
        return [msg] if msg else []
    meta = {}
    reply = None
    if cfg.ai_active:
        reply = ai_reply(conv, text, cfg)
        meta["ai"] = bool(reply)
    if not reply:
        reply, extra = rule_based_reply(text, cfg)
        meta.update(extra)
    created.append(add_message(conv, ChatMessage.BOT, reply, meta=meta))
    return created


def lead_from_conversation(conv, request=None):
    """When a visitor leaves name + email, make it visible as a lead too (source=chatbot)."""
    from apps.leads.models import Lead

    if conv.lead_id or not conv.visitor_email:
        return conv.lead
    transcript = "\n".join(f"{m.get_sender_display()}: {m.body}" for m in conv.messages.exclude(sender="system")[:30])
    lead = Lead.objects.create(name=conv.visitor_name or "Chat visitor", email=conv.visitor_email, phone=conv.visitor_phone, source="chatbot",
                               source_page=conv.page_url, message=transcript[:4000], visitor_hash=conv.visitor_hash,
                               service_label="", budget_label="")
    conv.lead = lead
    conv.save(update_fields=["lead", "updated_at"])
    notify("lead", f"New chat lead: {lead.name}", conv.last_message_preview, f"/dashboard/leads/{lead.pk}/", module="leads", level="success")
    return lead
