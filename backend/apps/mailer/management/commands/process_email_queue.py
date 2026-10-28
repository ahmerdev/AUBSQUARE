"""Send queued emails (with retry/backoff). Run every minute from cron/systemd, or use --loop."""
import time

from django.core.management.base import BaseCommand

from apps.mailer.service import process_queue


class Command(BaseCommand):
    help = "Deliver queued outgoing email (retries failed messages with back-off)."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=50)
        parser.add_argument("--loop", action="store_true", help="Keep running, checking every --interval seconds.")
        parser.add_argument("--interval", type=int, default=30)

    def handle(self, *a, **o):
        while True:
            res = process_queue(limit=o["limit"])
            self.stdout.write(f"processed: {res}")
            if not o["loop"]:
                return
            time.sleep(max(5, o["interval"]))
