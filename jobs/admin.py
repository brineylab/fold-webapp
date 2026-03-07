from django.contrib import admin

from jobs.models import Job
from jobs.services import cancel_job


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
            cancel_job(job, actor=request.user, source="admin")

