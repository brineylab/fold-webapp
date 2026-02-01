from __future__ import annotations

import sqlite3
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create a safe SQLite database backup using the sqlite3 backup API."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            type=str,
            required=True,
            help="Output path for the backup file.",
        )

    def handle(self, *args, **options):
        db_path = str(settings.DATABASES["default"]["NAME"])
        output_path = Path(options["output"])
        output_path.parent.mkdir(parents=True, exist_ok=True)

        source = sqlite3.connect(db_path)
        try:
            dest = sqlite3.connect(str(output_path))
            try:
                source.backup(dest)
            finally:
                dest.close()
        finally:
            source.close()

        size = output_path.stat().st_size
        if size >= 1024 * 1024:
            human = f"{size / (1024 * 1024):.1f} MB"
        elif size >= 1024:
            human = f"{size / 1024:.1f} KB"
        else:
            human = f"{size} bytes"

        self.stdout.write(
            self.style.SUCCESS(f"Database backed up to {output_path} ({human})")
        )
