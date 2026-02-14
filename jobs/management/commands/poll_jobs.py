from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

import slurm
from jobs.models import Job

# If a job stays UNKNOWN for longer than this, mark it FAILED.
STALE_JOB_TIMEOUT = timedelta(hours=1)


class Command(BaseCommand):
    help = "Poll SLURM for active job statuses"

    def handle(self, *args, **options):
        qs = (
            Job.objects.filter(status__in=[Job.Status.PENDING, Job.Status.RUNNING])
            .exclude(slurm_job_id="")
            .only("id", "status", "slurm_job_id", "submitted_at", "completed_at")
        )

        now = timezone.now()

        for job in qs.iterator():
            new_status = slurm.check_status(job.slurm_job_id)

            if new_status == "UNKNOWN":
                # If the job has been untrackable for too long, mark it failed.
                if job.submitted_at and (now - job.submitted_at) > STALE_JOB_TIMEOUT:
                    job.status = Job.Status.FAILED
                    job.error_message = (
                        "Job not found in SLURM. It may have failed before "
                        "being scheduled, or SLURM lost track of it."
                    )
                    job.completed_at = now
                    job.save(update_fields=["status", "error_message", "completed_at"])
                    self.stdout.write(
                        f"Job {job.id}: {Job.Status.PENDING} -> FAILED (stale)"
                    )
                continue

            if new_status == job.status:
                continue

            old = job.status
            job.status = new_status

            if new_status in {Job.Status.COMPLETED, Job.Status.FAILED}:
                job.completed_at = now

            job.save(update_fields=["status", "completed_at"])
            self.stdout.write(f"Job {job.id}: {old} -> {new_status}")
