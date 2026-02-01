from django.contrib import admin
from django.utils import timezone

from jobs.models import Job
import slurm


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ("id", "runner", "status", "owner", "slurm_job_id", "hidden_from_owner", "created_at")
    list_filter = ("status", "runner", "hidden_from_owner", "created_at")
    search_fields = ("id", "slurm_job_id", "owner__username")
    readonly_fields = ("id", "created_at", "submitted_at", "completed_at")
    actions = ["cancel_jobs"]

    @admin.action(description="Cancel selected jobs (scancel)")
    def cancel_jobs(self, request, queryset):
        for job in queryset.iterator():
            if job.status not in {Job.Status.PENDING, Job.Status.RUNNING}:
                continue
            if not job.slurm_job_id:
                continue
            slurm.cancel(job.slurm_job_id)
            job.status = Job.Status.FAILED
            job.error_message = "Cancelled by admin"
            job.completed_at = timezone.now()
            job.save(update_fields=["status", "error_message", "completed_at"])


