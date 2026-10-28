"""Scheduled housekeeping for outbound sales. Run every 10–15 minutes from cron / systemd (or use --loop)."""
import time

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.mailer.service import process_queue
from apps.outbound import outreach, services
from apps.outbound.models import OutboundSettings, Prospect


class Command(BaseCommand):
    help = "Drafts due follow-ups, sends approved emails (within limits), raises slow-reply / proposal reminders and optionally audits waiting prospects."

    def add_arguments(self, parser):
        parser.add_argument("--audit", type=int, default=0, help="Also audit up to N prospects that have a website but no audit yet.")
        parser.add_argument("--loop", action="store_true")
        parser.add_argument("--interval", type=int, default=600)

    def run_once(self, audit):
        cfg = OutboundSettings.load()
        out = {}
        if audit:
            n = 0
            for p in Prospect.objects.filter(status="new").exclude(website="").order_by("-created_at")[:audit]:
                services.audit_prospect(p)
                n += 1
            out["audited"] = n
        out["drafted"] = outreach.advance_due()
        out["email"] = outreach.send_approved()
        out["mail_queue"] = process_queue(limit=50)
        outreach.sync_status()
        out["checks"] = services.check_overdue(cfg)
        cfg.last_run_at = timezone.now()
        cfg.save(update_fields=["last_run_at"])
        return out

    def handle(self, *a, **o):
        while True:
            self.stdout.write(str(self.run_once(o["audit"])))
            if not o["loop"]:
                return
            time.sleep(max(60, o["interval"]))
