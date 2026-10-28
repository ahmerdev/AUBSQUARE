"""Outreach workflow: drafts → human approval → send through the normal mail queue, sequences, stop-on-reply, unsubscribe."""
import logging
import re
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.core.services import notify
from . import pitch
from .models import OutboundSettings, OutreachMessage, Prospect, ProspectNote, Sequence, SequenceEnrollment
from .services import daily_remaining, email_block, suppress

log = logging.getLogger(__name__)
STOP_RE = re.compile(r"\b(unsubscribe|remove me|stop (emailing|sending|contacting)|do not (contact|email)|don'?t (contact|email)|not interested)\b", re.I)


def draft_message(prospect: Prospect, step=1, channel="email", user=None, use_ai=None, send_after=None) -> OutreachMessage:
    subject, body, by, note = pitch.build(prospect, step, channel, use_ai)
    if channel == "whatsapp":
        cfg = OutboundSettings.load()
        if cfg.include_report_link and pitch.has_report(prospect):
            body += f"\n\nYour free website audit report: {pitch.report_url(prospect)}"
    blocked = email_block(prospect) if channel == "email" else ""
    return OutreachMessage.objects.create(prospect=prospect, channel=channel, step=step, subject=subject[:300], body=body, generated_by=by, block_reason=(blocked or note)[:200],
                                          created_by=user, send_after=send_after)


def approve(msg: OutreachMessage, user) -> tuple[bool, str]:
    if msg.status not in (OutreachMessage.DRAFT, OutreachMessage.FAILED):
        return False, "This message was already handled."
    if msg.channel == "email":
        why = email_block(msg.prospect)
        if why:
            return False, why
    msg.status, msg.approved_by, msg.approved_at = OutreachMessage.APPROVED, user, timezone.now()
    msg.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
    return True, ""


def send_approved(limit=50) -> dict:
    """Queue approved emails (respecting the daily limit, do-not-contact list and region rules) and refresh sent/failed status."""
    from apps.mailer.service import queue_email

    cfg = OutboundSettings.load()
    res = {"queued": 0, "blocked": 0, "limit_reached": False}
    now = timezone.now()
    for m in OutreachMessage.objects.filter(channel="email", status=OutreachMessage.APPROVED).select_related("prospect")[:limit]:
        if m.send_after and m.send_after > now:
            continue
        why = email_block(m.prospect, cfg)
        if why:
            m.status, m.block_reason = OutreachMessage.SKIPPED, why[:200]
            m.save(update_fields=["status", "block_reason", "updated_at"])
            res["blocked"] += 1
            continue
        if daily_remaining(cfg) <= 0:
            res["limit_reached"] = True
            break
        foot, unsub = pitch.footer(m.prospect, cfg)
        foot = pitch.links_block(m.prospect, cfg) + foot
        with transaction.atomic():
            em = queue_email([m.prospect.email], m.subject, m.body + foot, kind="outbound", headers={"List-Unsubscribe": f"<{unsub}>", "List-Unsubscribe-Post": "List-Unsubscribe=One-Click", "Precedence": "bulk"})
            m.email_message, m.status, m.queued_at = em, OutreachMessage.QUEUED, now
            m.save(update_fields=["email_message", "status", "queued_at", "updated_at"])
            p = m.prospect
            p.status = Prospect.CONTACTED if p.status in (Prospect.NEW, Prospect.AUDITED) else p.status
            p.last_contacted_at = now
            p.save(update_fields=["status", "last_contacted_at", "updated_at"])
            ProspectNote.objects.create(prospect=p, author=m.approved_by, kind="email", body=f"Email #{m.step} queued: {m.subject[:100]}")
        res["queued"] += 1
    sync_status()
    return res


def sync_status():
    for m in OutreachMessage.objects.filter(status=OutreachMessage.QUEUED, email_message__isnull=False).select_related("email_message"):
        em = m.email_message
        if em.status == "sent":
            m.status, m.sent_at = OutreachMessage.SENT, em.sent_at or timezone.now()
            m.save(update_fields=["status", "sent_at", "updated_at"])
        elif em.status == "failed" and em.attempts >= 5:
            m.status, m.error = OutreachMessage.FAILED, (em.error or "")[:300]
            m.save(update_fields=["status", "error", "updated_at"])


# ------------------------------------------------------------------ sequences
def enroll(prospect: Prospect, sequence: Sequence, user=None) -> tuple[bool, str]:
    why = email_block(prospect)
    if why:
        return False, why
    if SequenceEnrollment.objects.filter(prospect=prospect, sequence=sequence).exists():
        return False, "Already in this sequence."
    if SequenceEnrollment.objects.filter(prospect=prospect, status="active").exists():
        return False, "Already in another active sequence."
    steps = list(sequence.steps.all())
    if not steps:
        return False, "This sequence has no steps."
    SequenceEnrollment.objects.create(prospect=prospect, sequence=sequence, next_step=1, next_at=timezone.now())
    advance_due(only=prospect.pk, user=user)
    return True, ""


def stop_enrollments(prospect: Prospect, reason: str):
    SequenceEnrollment.objects.filter(prospect=prospect, status="active").update(status="stopped", stop_reason=reason[:80], next_at=None)
    OutreachMessage.objects.filter(prospect=prospect, status__in=["draft", "approved"]).update(status="skipped", block_reason=reason[:200])


def advance_due(only=None, user=None) -> int:
    """Creates the next draft for every enrollment that is due. Follow-ups wait for the previous email to be actually sent."""
    cfg = OutboundSettings.load()
    n = 0
    qs = SequenceEnrollment.objects.filter(status="active", next_at__lte=timezone.now()).select_related("prospect", "sequence")
    if only:
        qs = qs.filter(prospect_id=only)
    for en in qs:
        p = en.prospect
        if p.status in (Prospect.REPLIED, Prospect.CONVERTED, Prospect.SUPPRESSED, Prospect.REJECTED):
            en.status, en.stop_reason, en.next_at = "stopped", p.get_status_display(), None
            en.save(update_fields=["status", "stop_reason", "next_at", "updated_at"])
            continue
        steps = list(en.sequence.steps.all())
        step = next((s for s in steps if s.order == en.next_step), None)
        if not step:
            en.status, en.next_at = "done", None
            en.save(update_fields=["status", "next_at", "updated_at"])
            continue
        prev = OutreachMessage.objects.filter(prospect=p, step=en.next_step - 1).exclude(status="skipped").first() if en.next_step > 1 else None
        if prev and prev.status != OutreachMessage.SENT:
            en.next_at = timezone.now() + timedelta(hours=12)  # wait until the previous message has really gone out
            en.save(update_fields=["next_at", "updated_at"])
            continue
        msg = draft_message(p, en.next_step, "email", user)
        if step.template_id:
            from .pitch import context, fill

            ctx = context(p, cfg)
            msg.subject, msg.body, msg.generated_by = fill(step.template.subject, ctx)[:300], fill(step.template.body, ctx), "template"
            msg.save(update_fields=["subject", "body", "generated_by"])
        if not cfg.require_approval and not msg.block_reason:
            approve(msg, user)
        later = next((s for s in steps if s.order == en.next_step + 1), None)
        en.next_step += 1
        en.next_at = timezone.now() + timedelta(days=later.delay_days) if later else None
        if not later:
            en.status = "done"
        en.save(update_fields=["next_step", "next_at", "status", "updated_at"])
        n += 1
    return n


# ------------------------------------------------------------------ replies & unsubscribe
def handle_inbound_reply(msg):
    """Called for every inbound email. Links it to a prospect, stops their sequence and honours 'stop' requests."""
    sender = (msg.from_email or "").strip().lower()
    if not sender:
        return None
    prospect = None
    if msg.in_reply_to:
        om = OutreachMessage.objects.filter(email_message__message_id=msg.in_reply_to).select_related("prospect").first()
        prospect = om.prospect if om else None
    if not prospect:
        prospect = Prospect.objects.filter(email=sender).first()
    if sender.startswith(("mailer-daemon", "postmaster")):
        for addr in set(re.findall(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", msg.body_text or "")):
            if Prospect.objects.filter(email=addr.lower()).exists():
                suppress(addr, reason="bounced", note="Delivery failure notice")
        return None
    if not prospect:
        return None
    if prospect.status in (Prospect.CONVERTED,):
        return prospect
    text = (msg.body_text or "")[:600]
    if STOP_RE.search((msg.subject or "") + " " + text):
        suppress(prospect.email, reason="replied_stop", note="Asked to stop in a reply")
        ProspectNote.objects.create(prospect=prospect, kind="reply", body="Replied asking us to stop – added to the do-not-contact list.")
        return prospect
    prospect.status, prospect.replied_at, prospect.next_follow_up_at = Prospect.REPLIED, timezone.now(), None
    prospect.save(update_fields=["status", "replied_at", "next_follow_up_at", "updated_at"])
    stop_enrollments(prospect, "prospect replied")
    ProspectNote.objects.create(prospect=prospect, kind="reply", body=f"Replied: {(msg.subject or '')[:120]}")
    notify("prospect", f"{prospect.business_name} replied", (msg.subject or "")[:120], f"/dashboard/prospects/{prospect.pk}/", module="outbound", level="success")
    return prospect


def unsubscribe_prospect(prospect: Prospect):
    if prospect.email:
        suppress(prospect.email, reason="unsubscribed", note="Used the unsubscribe link")
    else:
        prospect.status = Prospect.SUPPRESSED
        prospect.save(update_fields=["status", "updated_at"])
    ProspectNote.objects.create(prospect=prospect, kind="unsubscribe", body="Unsubscribed using the link in our email.")
