import logging
import re
import threading
import uuid
from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.db import transaction
from django.utils import timezone

from apps.core.sanitize import clean_html, strip_html
from .models import EmailMessage, EmailSettings, EmailThread

log = logging.getLogger(__name__)
MAX_ATTEMPTS = 5
BACKOFF_MINUTES = [5, 15, 60, 360]


def _domain(es: EmailSettings) -> str:
    fe = es.effective_from_email
    return (fe.split("@")[-1] if fe else "aubsquare.local") or "aubsquare.local"


def _from_header(es: EmailSettings) -> str:
    fe = es.effective_from_email
    if fe:
        return f'"{es.from_name}" <{fe}>' if es.from_name else fe
    return settings.DEFAULT_FROM_EMAIL


def get_smtp_connection(es: EmailSettings | None = None):
    es = es or EmailSettings.load()
    if es.smtp_configured:
        return get_connection(
            backend="django.core.mail.backends.smtp.EmailBackend" if not settings.TESTING else settings.EMAIL_BACKEND,
            host=es.smtp_host, port=es.smtp_port, username=es.effective_username or None,
            password=es.get_smtp_password() or None, use_tls=es.smtp_security == "tls",
            use_ssl=es.smtp_security == "ssl", timeout=settings.EMAIL_TIMEOUT, fail_silently=False,
        )
    return get_connection(fail_silently=False)


def scrub(text: str, es: EmailSettings | None = None) -> str:
    es = es or EmailSettings.load()
    for secret in (es.get_smtp_password(),):
        if secret:
            text = text.replace(secret, "••••")
    return text[:1500]


def queue_email(to, subject, body_text="", body_html="", kind="system", lead=None, thread=None, created_by=None,
                cc=None, in_reply_to="", references="", send_now=True, headers=None, attachments=None) -> EmailMessage:
    es = EmailSettings.load()
    info = []
    if attachments:
        from .attachments import describe
        info = describe(attachments)  # validates every file now, so a missing file is reported before anything is queued
    msg = EmailMessage.objects.create(
        direction=EmailMessage.OUT, kind=kind, status=EmailMessage.QUEUED, lead=lead, thread=thread,
        message_id=f"<{uuid.uuid4().hex}@{_domain(es)}>", in_reply_to=in_reply_to, references=references,
        from_email=es.effective_from_email or settings.DEFAULT_FROM_EMAIL, from_name=es.from_name,
        to_emails=[t for t in to if t], cc_emails=cc or [], subject=subject[:300], body_text=body_text,
        body_html=clean_html(body_html), created_by=created_by, next_attempt_at=timezone.now(), extra_headers=headers or {},
        attachment_refs=attachments or [], attachments_info=info,
    )
    if send_now and getattr(settings, "EMAIL_SEND_MODE", "thread") != "queue":
        if settings.TESTING:
            transaction.on_commit(lambda: deliver(msg.pk))
        else:
            transaction.on_commit(lambda: threading.Thread(target=deliver, args=(msg.pk,), daemon=True).start())
    return msg


def deliver(message_pk: int) -> bool:
    """Send one queued message. Failures are recorded on the message – the business record is never lost."""
    try:
        msg = EmailMessage.objects.get(pk=message_pk)
    except EmailMessage.DoesNotExist:
        return False
    if msg.status == EmailMessage.SENT or msg.direction != EmailMessage.OUT:
        return True
    es = EmailSettings.load()
    msg.status, msg.attempts = EmailMessage.SENDING, msg.attempts + 1
    msg.save(update_fields=["status", "attempts"])
    try:
        headers = {"Message-ID": msg.message_id}
        if msg.in_reply_to:
            headers["In-Reply-To"] = msg.in_reply_to
        if msg.references:
            headers["References"] = msg.references
        for k, v in (msg.extra_headers or {}).items():
            if k.lower() in ("list-unsubscribe", "list-unsubscribe-post", "precedence", "auto-submitted"):
                headers[k] = v
        mail = EmailMultiAlternatives(
            subject=msg.subject, body=msg.body_text or strip_html(msg.body_html), from_email=_from_header(es),
            to=msg.to_emails, cc=msg.cc_emails or None, reply_to=[es.reply_to] if es.reply_to else None,
            headers=headers, connection=get_smtp_connection(es),
        )
        if msg.body_html:
            mail.attach_alternative(msg.body_html, "text/html")
        if msg.attachment_refs:
            from .attachments import resolve
            for ref in msg.attachment_refs:
                fname, data, mime = resolve(ref)
                mail.attach(fname, data, mime)
        mail.send()
    except Exception as exc:
        err = scrub(f"{exc.__class__.__name__}: {exc}", es)
        msg.status, msg.error = EmailMessage.FAILED, err
        permanent = msg.attempts >= MAX_ATTEMPTS
        msg.next_attempt_at = None if permanent else timezone.now() + timedelta(minutes=BACKOFF_MINUTES[min(msg.attempts - 1, len(BACKOFF_MINUTES) - 1)])
        msg.save(update_fields=["status", "error", "next_attempt_at"])
        log.warning("email %s failed (attempt %s): %s", msg.pk, msg.attempts, err)
        if msg.attempts == 1 or permanent:
            from apps.core.services import notify

            notify("email", "Email delivery failed" if not permanent else "Email permanently failed",
                   f"“{msg.subject[:80]}” to {', '.join(msg.to_emails)[:100]} — {err[:160]}",
                   f"/dashboard/inbox/message/{msg.pk}/", module="email", level="danger")
        return False
    msg.status, msg.error, msg.sent_at, msg.next_attempt_at = EmailMessage.SENT, "", timezone.now(), None
    msg.save(update_fields=["status", "error", "sent_at", "next_attempt_at"])
    if msg.thread_id:
        EmailThread.objects.filter(pk=msg.thread_id).update(last_message_at=timezone.now())
    return True


def process_queue(limit=50) -> dict:
    """Send queued messages and retry failed ones whose back-off has elapsed (cron / worker friendly)."""
    now = timezone.now()
    due = EmailMessage.objects.filter(direction=EmailMessage.OUT, status__in=[EmailMessage.QUEUED, EmailMessage.FAILED],
                                      next_attempt_at__lte=now, attempts__lt=MAX_ATTEMPTS)[:limit]
    ok = bad = 0
    for m in due:
        if deliver(m.pk):
            ok += 1
        else:
            bad += 1
    return {"sent": ok, "failed": bad}


def retry_message(msg: EmailMessage) -> bool:
    msg.attempts = 0
    msg.status = EmailMessage.QUEUED
    msg.save(update_fields=["attempts", "status"])
    return deliver(msg.pk)


def explain_error(text: str, es: EmailSettings | None = None) -> str:
    """Plain-language reason for the usual SMTP failures (the raw error is kept after it)."""
    t = (text or "").lower()
    gmail = "gmail" in ((es.smtp_host if es else "") or "").lower()
    if "534" in t or "application-specific password" in t or "5.7.9" in t:
        return "Google wants an App Password (not your normal password). Turn on 2-Step Verification, then create one at myaccount.google.com/apppasswords."
    if "535" in t or "badcredentials" in t or "username and password not accepted" in t or "authentication failed" in t or "auth" in t and "invalid" in t:
        return ("Login refused. " + ("For Gmail use a 16-letter App Password (2-Step Verification on) and the full Gmail address as username." if gmail
                else "Check the username (usually the full e-mail address) and the password / app password."))
    if "530" in t or "authentication required" in t or "smtp auth extension" in t:
        return "The server needs a login. Fill in the SMTP username (your full e-mail address) and password."
    if "wrong_version_number" in t or "unknown protocol" in t:
        return "Port and encryption do not match. Use port 587 with STARTTLS, or port 465 with SSL/TLS."
    if "timed out" in t or "timeout" in t:
        return "No answer from the server. Check the host and port, that your internet/firewall allows outgoing SMTP (587/465), and that the encryption matches the port."
    if "getaddrinfo" in t or "name or service not known" in t or "nodename nor servname" in t or "11001" in t:
        return "The SMTP host name was not found. Check the spelling (Gmail: smtp.gmail.com)."
    if "connection refused" in t or "10061" in t:
        return "The server refused the connection. Check the port number (587 STARTTLS or 465 SSL/TLS)."
    if "certificate" in t or "ssl:" in t:
        return "The secure connection failed. Try the other option: port 587 + STARTTLS, or port 465 + SSL/TLS."
    if "sender address rejected" in t or "553" in t or "550" in t and "sender" in t:
        return "The From address is not allowed for this login. Use the same address as the SMTP username."
    if "recipient" in t and "rejected" in t:
        return "The server rejected the recipient address."
    return ""


def send_test_email(to_address: str, user=None):
    """Sends ONE real message, only ever called from an explicit user action."""
    es = EmailSettings.load()
    if not es.smtp_configured:
        es.last_test_at, es.last_test_ok = timezone.now(), False
        es.last_test_message = "Not configured: fill in the SMTP host and the From email (or a username that is an email address), then save."
        es.save(update_fields=["last_test_at", "last_test_ok", "last_test_message"])
        return False, es.last_test_message
    msg = queue_email([to_address], "AUB SQUARE – SMTP test", "This is a test message from your AUB SQUARE dashboard.\nIf you can read this, outgoing email works.",
                      kind="test", created_by=user, send_now=False)
    ok = deliver(msg.pk)
    msg.refresh_from_db()
    es.last_test_at, es.last_test_ok = timezone.now(), ok
    if ok:
        es.last_test_message = "Test email delivered to the SMTP server. If it does not arrive in a minute, check Spam."
    else:
        raw = msg.error or "Failed"
        hint = explain_error(raw, es)
        es.last_test_message = ((hint + " — " if hint else "") + raw[: max(0, 290 - len(hint))])[:300]
    es.save(update_fields=["last_test_at", "last_test_ok", "last_test_message"])
    return ok, es.last_test_message


# ------------------------------------------------------------- staff notifications by email
EVENT_FLAGS = {"lead": "notify_new_lead", "chat": "notify_new_chat", "comment": "notify_new_comment",
               "staff": "notify_new_staff", "marketing": "notify_marketing_lead", "system": "notify_system"}


def staff_recipients(es: EmailSettings | None = None) -> list[str]:
    es = es or EmailSettings.load()
    rec = es.recipients()
    if rec:
        return rec
    from apps.accounts.models import User

    return list(User.objects.filter(is_superuser=True, is_active=True, status="approved", notify_email=True).values_list("email", flat=True))


def notify_staff_by_email(event: str, subject: str, body: str):
    es = EmailSettings.load()
    if not getattr(es, EVENT_FLAGS.get(event, "notify_system"), True):
        return None
    to = staff_recipients(es)
    if not to:
        return None
    return queue_email(to, subject, body, kind="notification")


# ------------------------------------------------------------- threads / lead replies
REF_RE = re.compile(r"\[(AUB-\d{4}-\d{4,})\]")


def thread_for_lead(lead) -> EmailThread:
    t = EmailThread.objects.filter(lead=lead).first()
    if t:
        return t
    return EmailThread.objects.create(subject=f"Lead {lead.reference} – {lead.name}", lead=lead, participant=lead.email)


def reply_to_lead(lead, user, subject: str, body: str, attachments=None) -> EmailMessage:
    thread = thread_for_lead(lead)
    last = thread.messages.exclude(message_id="").order_by("-created_at").first()
    tag = f"[{lead.reference}]"
    subj = subject if tag in subject else f"{subject} {tag}"
    refs = " ".join(filter(None, [last.references if last else "", last.message_id if last else ""])).strip()
    msg = queue_email([lead.email], subj, body, kind="reply", lead=lead, thread=thread, created_by=user,
                      in_reply_to=last.message_id if last else "", references=refs, attachments=attachments)
    thread.last_message_at = timezone.now()
    thread.save(update_fields=["last_message_at"])
    lead.last_contacted_at = timezone.now()
    if lead.status == lead.NEW:
        lead.status = lead.CONTACTED
    if lead.first_response_at is None:
        lead.first_response_at = timezone.now()
    lead.save(update_fields=["last_contacted_at", "status", "first_response_at", "updated_at"])
    return msg
