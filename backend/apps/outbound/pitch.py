"""Writes outreach messages from REAL audit findings. Gemini is optional; without a key a clearly-labelled template is used."""
import json
import logging
import re
import urllib.request

from django.conf import settings as dj

from .models import CATEGORIES, OutboundSettings, OutreachTemplate, Prospect

log = logging.getLogger(__name__)
CAT = dict(CATEGORIES)

DEFAULTS = {
    "first": ("Quick idea for {business}",
              "Hi {business} team,\n\nI had a quick look at your website and noticed {issue}.\n\nWe're {agency}, a web & marketing studio. If it helps, I can send you a short free audit of your site showing what I'd fix first – no obligation.\n\nWould that be useful?\n\n{sender}"),
    "follow_up_1": ("Re: Quick idea for {business}",
                    "Hi {business} team,\n\nJust following up on my note about your website ({issue}). Happy to send the short audit if you'd like it – just reply \"yes\".\n\n{sender}"),
    "follow_up_2": ("Last note about your website",
                    "Hi {business} team,\n\nI don't want to clutter your inbox, so this is my last message. If improving your website's enquiries is on your list, reply any time and I'll share the audit.\n\n{sender}"),
    "whatsapp": ("", "Hi {business} team, this is {sender} from {agency}. I looked at your website and noticed {issue}. Can I send you a short free audit?"),
}


def issues_text(prospect: Prospect, limit=2) -> tuple[str, list]:
    audit = prospect.audits.filter(reachable=True).first()
    if not audit or not audit.findings:
        return "a few things that could bring you more enquiries", []
    top = sorted(audit.findings, key=lambda f: -f["points"])[:limit]
    parts = [f["title"][0].lower() + f["title"][1:] for f in top]
    return " and ".join(parts), top


def context(prospect: Prospect, cfg: OutboundSettings):
    issue, top = issues_text(prospect)
    return {"business": prospect.business_name, "name": prospect.business_name, "city": prospect.city or "your area", "issue": issue,
            "service": top[0]["service"] if top else "website improvements", "score": prospect.opportunity_score,
            "sender": cfg.sender_name or cfg.sender_business, "agency": cfg.sender_business, "category": CAT.get(prospect.category, "local").lower()}


def fill(text, ctx):
    return re.sub(r"\{(\w+)\}", lambda m: str(ctx.get(m.group(1), m.group(0))), text)


def pick_template(kind, prospect):
    qs = OutreachTemplate.objects.filter(is_active=True, kind=kind)
    return qs.filter(category=prospect.category).first() or qs.filter(category="").first()


def template_pitch(prospect, step=1, channel="email", cfg=None):
    cfg = cfg or OutboundSettings.load()
    kind = "whatsapp" if channel == "whatsapp" else ("first" if step <= 1 else f"follow_up_{min(step - 1, 2)}")
    tpl = pick_template("whatsapp" if channel == "whatsapp" else ("first" if step <= 1 else "follow_up"), prospect)
    subj, body = (tpl.subject, tpl.body) if tpl else DEFAULTS[kind]
    ctx = context(prospect, cfg)
    return fill(subj, ctx), fill(body, ctx)


def gemini_pitch(prospect, step, channel, cfg):
    key = cfg.get_gemini_key()
    issue, top = issues_text(prospect)
    facts = [f"- {f['title']}: {f['detail']}" for f in top] or ["- (no audit findings available – do not claim any specific problem)"]
    prompt = (f"Write a short, polite, human-sounding {'WhatsApp message' if channel == 'whatsapp' else 'cold email'} (max 110 words) from {cfg.sender_name or cfg.sender_business} at {cfg.sender_business}, "
              f"a web design & marketing studio, to {prospect.business_name} ({CAT.get(prospect.category)}, {prospect.city} {prospect.country}). "
              f"This is message number {step} in a sequence{' (a gentle follow-up)' if step > 1 else ''}. Use ONLY these verified facts from an audit of their website, never invent facts, prices, results or claims:\n"
              + "\n".join(facts) + "\nOffer a free short audit. No links, no attachments, no emojis, no spammy words. Do not add a signature footer or unsubscribe text. "
              'Reply ONLY as JSON: {"subject": "...", "body": "..."}' + (' (subject may be empty for WhatsApp)' if channel == "whatsapp" else ""))
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{cfg.gemini_model}:generateContent"
    req = urllib.request.Request(url, data=json.dumps({"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.6, "responseMimeType": "application/json"}}).encode(),
                                 headers={"Content-Type": "application/json", "x-goog-api-key": key})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read(500_000).decode())
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    out = json.loads(text)
    subject, body = str(out.get("subject", ""))[:150].strip(), str(out.get("body", "")).strip()[:1500]
    if len(body) < 40:
        raise ValueError("AI reply too short")
    return subject, body


def build(prospect: Prospect, step=1, channel="email", use_ai=None):
    """Returns (subject, body, generated_by, note). generated_by is 'ai' or 'template' – never pretends."""
    cfg = OutboundSettings.load()
    want_ai = cfg.ai_enabled if use_ai is None else use_ai
    note = ""
    if want_ai and cfg.has_gemini_key:
        try:
            s, b = gemini_pitch(prospect, step, channel, cfg)
            return (s or template_pitch(prospect, step, channel, cfg)[0]), b, "ai", ""
        except Exception as exc:
            log.warning("gemini pitch failed: %s", exc.__class__.__name__)
            note = "AI was unavailable, so a template was used instead."
    elif want_ai:
        note = "No Gemini key is saved, so a template was used."
    s, b = template_pitch(prospect, step, channel, cfg)
    return s, b, "template", note


def report_url(prospect) -> str:
    return f"{dj.SITE_URL}/r/{prospect.token}/"


def has_report(prospect) -> bool:
    return prospect.audits.filter(reachable=True).exists()


def links_block(prospect, cfg) -> str:
    """Links added by the system (never by the AI): their own audit report, our portfolio, our website."""
    base = dj.SITE_URL
    lines = []
    if getattr(cfg, "include_prospect_site", False) and prospect.website:
        lines.append(f"Website reviewed: {prospect.website}")
    if cfg.include_report_link and has_report(prospect):
        lines.append(f"Your free website audit report: {report_url(prospect)}")
    if cfg.include_portfolio_link:
        lines.append(f"Some of our work: {base}/portfolio")
    if cfg.include_site_link:
        lines.append(f"Our website: {base}")
    return ("\n\n" + "\n".join(lines)) if lines else ""


def final_text(prospect, body, cfg=None) -> str:
    """Exactly what the recipient receives: the approved text + links + postal address + unsubscribe line."""
    cfg = cfg or OutboundSettings.load()
    return body + links_block(prospect, cfg) + footer(prospect, cfg)[0]


def footer(prospect, cfg):
    unsub = f"{dj.SITE_URL}/o/{prospect.token}/"
    return (f"\n\n--\n{cfg.sender_name + ' · ' if cfg.sender_name else ''}{cfg.sender_business}\n{cfg.postal_address}\n"
            f"You received this because your business contact details are publicly listed. Don't want to hear from us? Unsubscribe: {unsub}"), unsub
