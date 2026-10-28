"""Email marketing: consent-only audience, mandatory unsubscribe link, queued delivery."""
from django.utils import timezone

from apps.core.sanitize import strip_html
from apps.core.services import absolute_url
from apps.mailer.service import queue_email
from .models import EmailCampaign, Subscriber


def audience():
    """Only people who explicitly consented and have not unsubscribed."""
    return Subscriber.objects.filter(status="subscribed", consent_at__isnull=False)


def unsubscribe_url(sub):
    return absolute_url(f"/u/{sub.token}/")


def render_for(campaign: EmailCampaign, sub: Subscriber):
    link = unsubscribe_url(sub)
    html = (campaign.body_html or "") + f'<hr><p style="font-size:12px;color:#888">You are receiving this because you subscribed to AUB SQUARE updates. <a href="{link}">Unsubscribe</a>.</p>'
    text = strip_html(campaign.body_html or "") + f"\n\n--\nYou are receiving this because you subscribed to AUB SQUARE updates.\nUnsubscribe: {link}\n"
    return html, text


def send_campaign(campaign: EmailCampaign, user) -> int:
    if campaign.status in ("sent", "sending"):
        raise ValueError("This campaign was already sent.")
    subs = list(audience())
    campaign.status, campaign.recipient_count = "sending", len(subs)
    campaign.save(update_fields=["status", "recipient_count", "updated_at"])
    for s in subs:
        html, text = render_for(campaign, s)
        queue_email([s.email], campaign.subject, text, html, kind="marketing", created_by=user, send_now=False)
    campaign.status, campaign.sent_at = "sent", timezone.now()
    campaign.save(update_fields=["status", "sent_at", "updated_at"])
    return len(subs)
