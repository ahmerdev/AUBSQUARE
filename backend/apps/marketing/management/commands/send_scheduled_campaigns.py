"""Send email campaigns whose scheduled time has arrived (only to subscribers with recorded consent)."""
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.marketing import services as mk
from apps.marketing.models import EmailCampaign


class Command(BaseCommand):
    help = "Queue scheduled email campaigns that are due."

    def handle(self, *a, **o):
        due = EmailCampaign.objects.filter(status="scheduled", scheduled_at__lte=timezone.now())
        for ec in due:
            n = mk.send_campaign(ec, ec.created_by)
            self.stdout.write(f"{ec.name}: queued for {n} subscribers")
        if not due:
            self.stdout.write("Nothing due.")
