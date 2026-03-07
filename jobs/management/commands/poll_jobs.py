from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

import slurm
from jobs.models import Job
from jobs.services import sync_job_status

# If a job stays UNKNOWN for longer than this, mark it FAILED.
STALE_JOB_TIMEOUT = timedelta(hours=1)


def _has_materialized_outputs(job) -> bool:
    """Treat non-SLURM files in output/ as evidence the job completed."""
    outdir = job.workdir / "output"
    if not outdir.is_dir():
        return False
    return any(
        p.is_file() and not p.name.startswith("slurm-")
        for p in outdir.rglob("*")
    )


class Command(BaseCommand):
    help = "Poll SLURM for active job statuses"

    def handle(self, *args, **options):
        qs = (
            Job.objects.filter(status__in=[Job.Status.PENDING, Job.Status.RUNNING])
            .exclude(slurm_job_id="")
            .only(
                "id",
                "status",
                "slurm_job_id",
                "submitted_at",
                "completed_at",
                "error_message",
            )
        )

        now = timezone.now()

        for job in qs.iterator():
            new_status = slurm.check_status(job.slurm_job_id)

            if new_status == "UNKNOWN":
                if slurm.job_missing(job.slurm_job_id):
                    old = job.status
                    terminal_status = (
                        Job.Status.COMPLETED
                        if _has_materialized_outputs(job)
                        else Job.Status.FAILED
                    )
                    error_message = None
                    if terminal_status == Job.Status.FAILED and not job.error_message:
                        error_message = (
                            "Job disappeared from SLURM before the poller could "
                            "read a terminal state."
                        )
                    sync_job_status(
                        job,
                        terminal_status,
                        when=now,
                        error_message=error_message,
                    )
                    self.stdout.write(f"Job {job.id}: {old} -> {terminal_status} (missing)")
                    continue

                # If the job has been untrackable for too long, mark it failed.
                if job.submitted_at and (now - job.submitted_at) > STALE_JOB_TIMEOUT:
                    sync_job_status(
                        job,
                        Job.Status.FAILED,
                        when=now,
                        error_message=(
                            "Job not found in SLURM. It may have failed before "
                            "being scheduled, or SLURM lost track of it."
                        ),
                    )
                    self.stdout.write(
                        f"Job {job.id}: {Job.Status.PENDING} -> FAILED (stale)"
                    )
                continue

            if new_status == job.status:
                if new_status == Job.Status.RUNNING and job.started_at is None:
                    sync_job_status(job, new_status, when=now)
                continue

            old = job.status
            error_message = None
            if new_status == Job.Status.FAILED and not job.error_message:
                error_message = slurm.get_failure_message(job.slurm_job_id)
            sync_job_status(job, new_status, when=now, error_message=error_message)
            self.stdout.write(f"Job {job.id}: {old} -> {new_status}")
