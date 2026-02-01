from __future__ import annotations

from django.core.management.base import BaseCommand
from django.utils import timezone

import slurm
from jobs.models import Job


class Command(BaseCommand):
    help = "Poll SLURM for active job statuses"

    def handle(self, *args, **options):
        qs = (
            Job.objects.filter(status__in=[Job.Status.PENDING, Job.Status.RUNNING])
            .exclude(slurm_job_id="")
            .only("id", "status", "slurm_job_id", "completed_at")
        )

        for job in qs.iterator():
            new_status = slurm.check_status(job.slurm_job_id)
            if new_status == "UNKNOWN":
                continue

            if new_status == job.status:
                continue

            old = job.status
            job.status = new_status

            if new_status in {Job.Status.COMPLETED, Job.Status.FAILED}:
                job.completed_at = timezone.now()

            job.save(update_fields=["status", "completed_at"])
            self.stdout.write(f"Job {job.id}: {old} -> {new_status}")


