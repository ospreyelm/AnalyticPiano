"""Ensure a factory system account exists for automated operations."""
from django.core.management.base import BaseCommand
from django.conf import settings

from apps.accounts.models import User, ROLE_TEACHER


class Command(BaseCommand):
    help = "Ensure a factory system account exists for automated operations."

    def add_arguments(self, parser):
        parser.add_argument(
            "--email",
            type=str,
            default=None,
            help="Override the factory account email (default: settings.FACTORY_USER_EMAIL)",
        )

    def handle(self, *args, **options):
        email = options.get("email") or settings.FACTORY_USER_EMAIL

        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "role": ROLE_TEACHER,
                "first_name": "Factory",
                "last_name": "Account",
            }
        )

        # Ensure password is unusable
        if user.has_usable_password():
            user.set_unusable_password()
            user.save()

        if created:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Created factory account: {user.id} ({email})"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Factory account exists: {user.id} ({email})"
                )
            )
