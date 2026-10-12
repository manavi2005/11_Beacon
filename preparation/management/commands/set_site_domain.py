"""Point django.contrib.sites at the domain this deployment actually serves.

Assignment 5, Part 2.

A fresh database gets a Site row of "example.com". allauth reads that row,
so leaving it wrong makes the Google flow build callback URLs for a domain
nobody owns. Doing it with a command rather than by hand in the admin means
the deploy step is repeatable and can be written down:

    python manage.py set_site_domain beacon.pythonanywhere.com
"""

from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Set the django.contrib.sites domain for this deployment."

    def add_arguments(self, parser):
        parser.add_argument("domain", help="e.g. yourname.pythonanywhere.com")
        parser.add_argument(
            "--name",
            default="",
            help="Human-readable label. Defaults to the domain.",
        )

    def handle(self, *args, **options):
        domain = options["domain"].strip()
        # A scheme or a path here is the common mistake, and it fails later
        # as a broken callback rather than here, so reject it now.
        if "://" in domain or "/" in domain:
            raise CommandError(
                f"Pass the bare host, not a URL: got {domain!r}. "
                "Example: yourname.pythonanywhere.com"
            )

        from django.conf import settings

        site, created = Site.objects.update_or_create(
            pk=settings.SITE_ID,
            defaults={"domain": domain, "name": options["name"] or domain},
        )
        verb = "Created" if created else "Updated"
        self.stdout.write(
            self.style.SUCCESS(f"{verb} site {site.pk}: {site.domain}")
        )
        self.stdout.write(
            "Register this callback with Google if you have not already:\n"
            f"  https://{domain}/accounts/google/login/callback/"
        )
