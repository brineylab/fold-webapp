from __future__ import annotations

from django.core.management.base import BaseCommand

from console.services.cleanup import cleanup_jobs, get_jobs_for_cleanup


class Command(BaseCommand):
    help = "Clean up job workdirs that are past their retention period"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be cleaned up without actually deleting anything",
        )
        parser.add_argument(
            "--days",
            type=int,
            default=None,
            help="Override per-user retention settings with this number of days",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Show detailed information about each job",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        override_days = options["days"]
        verbose = options["verbose"]

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - no files will be deleted"))
            self.stdout.write("")

        if override_days is not None:
            self.stdout.write(f"Using override retention period: {override_days} days")
            self.stdout.write("")

        result = cleanup_jobs(override_days=override_days, dry_run=dry_run)

        if verbose and result["jobs"]:
            self.stdout.write("Jobs eligible for cleanup:")
            self.stdout.write("-" * 80)
            for item in result["jobs"]:
                job = item["job"]
                self.stdout.write(
                    f"  {job.id} | {job.owner.username} | "
                    f"completed {item['age_days']}d ago | "
                    f"retention {item['retention_days']}d | "
                    f"{'workdir exists' if item['workdir_exists'] else 'workdir missing'} | "
                    f"{item['workdir_size'] / 1024:.1f} KB"
                )
            self.stdout.write("-" * 80)
            self.stdout.write("")

        self.stdout.write(f"Total candidates: {result['total_candidates']}")
        self.stdout.write(f"Cleaned: {result['cleaned']}")
        self.stdout.write(f"Skipped (no workdir): {result['skipped']}")
        self.stdout.write(f"Space freed: {result['bytes_freed_mb']} MB")

        if result["errors"]:
            self.stdout.write("")
            self.stdout.write(self.style.ERROR("Errors:"))
            for error in result["errors"]:
                self.stdout.write(f"  - {error}")

        if dry_run:
            self.stdout.write("")
            self.stdout.write(
                self.style.WARNING("Run without --dry-run to actually delete files")
            )
        else:
            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS("Cleanup complete"))

