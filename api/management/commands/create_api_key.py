from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from api.models import APIKey

User = get_user_model()


class Command(BaseCommand):
    help = "Create an API key for a user."

    def add_arguments(self, parser):
        parser.add_argument("username", type=str, help="Username to create key for")
        parser.add_argument(
            "--label",
            type=str,
            default="",
            help="Optional label for the key (e.g. 'lab notebook script')",
        )

    def handle(self, *args, **options):
        username = options["username"]
        label = options["label"]

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise CommandError(f"User '{username}' does not exist.")

        api_key = APIKey(user=user, label=label)
        api_key.save()

        self.stdout.write(f"API key created for {username}:")
        self.stdout.write(api_key.key)
