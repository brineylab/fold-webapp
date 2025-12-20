from __future__ import annotations

from datetime import datetime

from django.core.management.base import BaseCommand

from console.services.cleanup import (
    detect_orphan_workdirs,
    detect_orphan_jobs,
    delete_orphan_workdir,
)


class Command(BaseCommand):
    help = "Detect orphaned workdirs (no DB record) and orphaned jobs (no workdir)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--fix",
            action="store_true",
            help="Automatically fix orphans (delete orphan workdirs, mark orphan jobs)",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Show detailed information about each orphan",
        )

    def handle(self, *args, **options):
        fix_mode = options["fix"]
        verbose = options["verbose"]

        if fix_mode:
            self.stdout.write(
                self.style.WARNING("FIX MODE - orphan workdirs will be deleted")
            )
            self.stdout.write("")

        # Detect orphan workdirs (files without DB records)
        self.stdout.write("Scanning for orphan workdirs...")
        orphan_workdirs = detect_orphan_workdirs()

        if orphan_workdirs:
            self.stdout.write(
                self.style.WARNING(f"Found {len(orphan_workdirs)} orphan workdir(s)")
            )
            
            total_size = sum(o["size"] for o in orphan_workdirs)
            self.stdout.write(f"Total size: {total_size / (1024 * 1024):.2f} MB")

            if verbose:
                self.stdout.write("")
                self.stdout.write("Orphan workdirs:")
                self.stdout.write("-" * 80)
                for orphan in orphan_workdirs:
                    mtime = datetime.fromtimestamp(orphan["mtime"])
                    self.stdout.write(
                        f"  {orphan['name']} | "
                        f"{orphan['size'] / 1024:.1f} KB | "
                        f"modified {mtime.strftime('%Y-%m-%d %H:%M')}"
                    )
                self.stdout.write("-" * 80)

            if fix_mode:
                self.stdout.write("")
                deleted = 0
                for orphan in orphan_workdirs:
                    if delete_orphan_workdir(orphan["path"]):
                        deleted += 1
                        self.stdout.write(f"  Deleted: {orphan['name']}")
                    else:
                        self.stdout.write(
                            self.style.ERROR(f"  Failed to delete: {orphan['name']}")
                        )
                self.stdout.write(f"Deleted {deleted} orphan workdir(s)")
        else:
            self.stdout.write(self.style.SUCCESS("No orphan workdirs found"))

        self.stdout.write("")

        # Detect orphan jobs (DB records without files)
        self.stdout.write("Scanning for orphan jobs (missing workdirs)...")
        orphan_jobs = detect_orphan_jobs()
        orphan_count = orphan_jobs.count()

        if orphan_count > 0:
            self.stdout.write(
                self.style.WARNING(f"Found {orphan_count} job(s) with missing workdirs")
            )

            if verbose:
                self.stdout.write("")
                self.stdout.write("Jobs with missing workdirs:")
                self.stdout.write("-" * 80)
                for job in orphan_jobs[:50]:  # Limit output
                    self.stdout.write(
                        f"  {job.id} | {job.owner.username} | "
                        f"{job.status} | created {job.created_at.strftime('%Y-%m-%d')}"
                    )
                if orphan_count > 50:
                    self.stdout.write(f"  ... and {orphan_count - 50} more")
                self.stdout.write("-" * 80)

            if fix_mode:
                self.stdout.write("")
                self.stdout.write(
                    "Note: Orphan jobs are not automatically modified. "
                    "Review them manually and decide whether to hide or delete."
                )
        else:
            self.stdout.write(self.style.SUCCESS("No orphan jobs found"))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Orphan detection complete"))

