"""Inbound mail via IMAP. SMTP can only SEND – reading mail needs a mailbox protocol (IMAP) or a provider webhook."""
import email
import imaplib
import logging
from email import policy
from email.utils import getaddresses, parseaddr, parsedate_to_datetime

from django.utils import timezone

from apps.core.sanitize import clean_html, strip_html
from .models import EmailMessage, EmailSettings, EmailThread
from .service import REF_RE

log = logging.getLogger(__name__)
MAX_PER_SYNC = 100


class InboundNotConfigured(Exception):
    pass


def parse_raw_message(raw: bytes) -> dict:
    msg = email.message_from_bytes(raw, policy=policy.default)
    name, addr = parseaddr(str(msg.get("From", "")))
    text = html = ""
    attachments = []
    for part in msg.walk():
        if part.is_multipart():
            continue
        disp = part.get_content_disposition()
        ctype = part.get_content_type()
        if disp == "attachment" or part.get_filename():
            attachments.append({"name": part.get_filename() or "attachment", "type": ctype, "size": len(part.get_payload(decode=True) or b"")})
            continue
        try:
            content = part.get_content()
        except Exception:
            continue
        if ctype == "text/plain" and not text:
            text = content
        elif ctype == "text/html" and not html:
            html = content
    try:
        date = parsedate_to_datetime(str(msg.get("Date"))) if msg.get("Date") else timezone.now()
        if timezone.is_naive(date):
            date = timezone.make_aware(date)
    except Exception:
        date = timezone.now()
    return {
        "message_id": str(msg.get("Message-ID", "")).strip(), "in_reply_to": str(msg.get("In-Reply-To", "")).strip(),
        "references": str(msg.get("References", "")).strip(), "from_email": addr.lower(), "from_name": name,
        "to": [a for _, a in getaddresses(msg.get_all("To", []))], "cc": [a for _, a in getaddresses(msg.get_all("Cc", []))],
        "subject": str(msg.get("Subject", "(no subject)"))[:300], "text": text or strip_html(html), "html": clean_html(html),
        "date": date, "attachments": attachments,
    }


def store_inbound(parsed: dict, uid: int | None = None):
    """Persist one parsed message (deduplicated by Message-ID), thread it, link it to a lead."""
    from apps.leads.models import Lead
    from apps.core.services import notify

    mid = parsed["message_id"]
    if mid and EmailMessage.objects.filter(direction=EmailMessage.IN, message_id=mid).exists():
        return None
    es = EmailSettings.load()
    if parsed["from_email"] and es.from_email and parsed["from_email"] == es.from_email.lower():
        return None  # our own copy in the folder

    thread = lead = None
    if parsed["in_reply_to"] or parsed["references"]:
        ids = [parsed["in_reply_to"]] + parsed["references"].split()
        known = EmailMessage.objects.filter(message_id__in=[i for i in ids if i], thread__isnull=False).first()
        if known:
            thread, lead = known.thread, known.lead
    if not thread:
        m = REF_RE.search(parsed["subject"])
        if m:
            lead = Lead.objects.filter(reference=m.group(1)).first()
        if not lead and parsed["from_email"]:
            lead = Lead.objects.filter(email__iexact=parsed["from_email"]).order_by("-created_at").first()
        if lead:
            thread = EmailThread.objects.filter(lead=lead).first()
    if not thread:
        thread = EmailThread.objects.create(subject=parsed["subject"], lead=lead, participant=parsed["from_email"])
    msg = EmailMessage.objects.create(
        thread=thread, lead=lead or thread.lead, direction=EmailMessage.IN, kind="inbound", status=EmailMessage.RECEIVED,
        message_id=mid, in_reply_to=parsed["in_reply_to"][:300], references=parsed["references"], from_email=parsed["from_email"],
        from_name=parsed["from_name"][:200], to_emails=parsed["to"], cc_emails=parsed["cc"], subject=parsed["subject"],
        body_text=parsed["text"], body_html=parsed["html"], attachments_info=parsed["attachments"], received_at=parsed["date"],
        imap_uid=uid, is_read=False,
    )
    thread.has_unread, thread.last_message_at = True, parsed["date"]
    thread.save(update_fields=["has_unread", "last_message_at"])
    try:
        from apps.outbound.outreach import handle_inbound_reply

        handle_inbound_reply(msg)
    except Exception:  # prospect linking must never block inbox sync
        log.exception("outbound reply linking failed")
    notify("email", "New email received", f"{parsed['from_name'] or parsed['from_email']}: {parsed['subject'][:100]}", f"/dashboard/inbox/thread/{thread.pk}/", module="email")
    return msg


def sync_inbox(limit: int = MAX_PER_SYNC) -> dict:
    es = EmailSettings.load()
    if not es.imap_configured:
        raise InboundNotConfigured("Inbound email is not configured. Add IMAP settings and enable inbound sync first.")
    try:
        if es.imap_security == "ssl":
            conn = imaplib.IMAP4_SSL(es.imap_host, es.imap_port, timeout=30)
        else:
            conn = imaplib.IMAP4(es.imap_host, es.imap_port, timeout=30)
            if es.imap_security == "starttls":
                conn.starttls()
        conn.login(es.imap_username, es.get_imap_password())
        typ, _ = conn.select(es.imap_folder, readonly=True)  # read-only: we never modify the mailbox
        if typ != "OK":
            raise RuntimeError(f"Cannot open folder {es.imap_folder}")
        uidvalidity = ""
        try:
            typ, data = conn.response("UIDVALIDITY")
            uidvalidity = (data[0] or b"").decode() if data and data[0] else ""
        except Exception:
            pass
        if uidvalidity and es.imap_uidvalidity and uidvalidity != es.imap_uidvalidity:
            es.imap_last_uid = 0  # mailbox was rebuilt – dedupe by Message-ID protects us from duplicates
        typ, data = conn.uid("search", None, "UID", f"{es.imap_last_uid + 1}:*")
        uids = [int(x) for x in (data[0] or b"").split() if int(x) > es.imap_last_uid][:limit]
        new = 0
        for uid in uids:
            typ, parts = conn.uid("fetch", str(uid), "(BODY.PEEK[])")
            if typ != "OK" or not parts or not isinstance(parts[0], tuple):
                continue
            if store_inbound(parse_raw_message(parts[0][1]), uid):
                new += 1
            es.imap_last_uid = max(es.imap_last_uid, uid)
        conn.logout()
        es.imap_uidvalidity = uidvalidity or es.imap_uidvalidity
        es.last_sync_at, es.last_sync_ok = timezone.now(), True
        es.last_sync_message = f"Fetched {len(uids)} message(s), {new} new."
        es.save()
        return {"checked": len(uids), "new": new}
    except InboundNotConfigured:
        raise
    except Exception as exc:
        es.last_sync_at, es.last_sync_ok = timezone.now(), False
        es.last_sync_message = f"{exc.__class__.__name__}: {exc}"[:300].replace(es.get_imap_password() or "\0", "••••")
        es.save(update_fields=["last_sync_at", "last_sync_ok", "last_sync_message"])
        raise


def test_connection() -> str:
    """Log in and open the folder read-only; never fetches or changes anything."""
    es = EmailSettings.load()
    if not es.imap_configured:
        raise InboundNotConfigured("Inbound email is not configured. Add IMAP settings and enable inbound sync first.")
    try:
        if es.imap_security == "ssl":
            conn = imaplib.IMAP4_SSL(es.imap_host, es.imap_port, timeout=20)
        else:
            conn = imaplib.IMAP4(es.imap_host, es.imap_port, timeout=20)
            if es.imap_security == "starttls":
                conn.starttls()
        conn.login(es.imap_username, es.get_imap_password())
        typ, data = conn.select(es.imap_folder, readonly=True)
        conn.logout()
        if typ != "OK":
            raise RuntimeError(f"Cannot open folder {es.imap_folder}")
        return f"Connected. Folder “{es.imap_folder}” holds {int(data[0] or 0)} message(s)."
    except InboundNotConfigured:
        raise
    except Exception as exc:
        raise RuntimeError(str(exc).replace(es.get_imap_password() or "\0", "••••"))
