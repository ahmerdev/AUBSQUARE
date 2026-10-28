"""Fetch new customer replies from the configured IMAP mailbox (read-only; messages are never deleted)."""
from django.core.management.base import BaseCommand, CommandError

from apps.mailer.inbound import InboundNotConfigured, sync_inbox


class Command(BaseCommand):
    help = "Pull new messages from the IMAP inbox into the dashboard."

    def handle(self, *a, **o):
        try:
            self.stdout.write(f"synced: {sync_inbox()}")
        except InboundNotConfigured as e:
            raise CommandError(str(e))
