from django.core.management.base import BaseCommand

from studio.reminders import send_due


class Command(BaseCommand):
    help = "Send today's opt-in practice reminders. Schedule once a day."

    def handle(self, *args, **options):
        self.stdout.write(f"Sent {send_due()} reminder(s).")
