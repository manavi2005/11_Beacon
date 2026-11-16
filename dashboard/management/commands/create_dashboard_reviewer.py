import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create the assignment reviewer superuser using DASHBOARD_REVIEWER_PASSWORD."

    def add_arguments(self, parser):
        parser.add_argument("--update-existing", action="store_true", help="Explicitly reset the existing reviewer's password and superuser access.")

    def handle(self, *args, **options):
        password = os.environ.get("DASHBOARD_REVIEWER_PASSWORD")
        if not password:
            raise CommandError("Set DASHBOARD_REVIEWER_PASSWORD first.")
        user, created = get_user_model().objects.get_or_create(username="mohitg2")
        if not created and not options["update_existing"]:
            raise CommandError("mohitg2 already exists; no password or permissions were changed.")
        user.is_active = user.is_staff = user.is_superuser = True
        user.set_password(password)
        user.save()
        self.stdout.write(self.style.SUCCESS("Configured dashboard reviewer mohitg2."))
