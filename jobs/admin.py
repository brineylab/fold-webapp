from django.contrib import admin
from django.db.models import Prefetch

from jobs.models import Job, JobAttempt
from jobs.services import cancel_job


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "runner",
        "status",
        "owner",
        "runtime_id_display",
        "hidden_from_owner",
        "created_at",
    )
    list_filter = ("status", "runner", "hidden_from_owner", "created_at")
    search_fields = (
        "id",
        "slurm_job_id",
        "attempts__scheduler_job_id",
        "attempts__container_id",
        "owner__username",
    )
    readonly_fields = ("id", "created_at", "submitted_at", "completed_at")
    actions = ["cancel_jobs"]
    list_select_related = ("owner",)

    def get_queryset(self, request):
        latest_attempts = Prefetch(
            "attempts",
            queryset=JobAttempt.objects.order_by("-attempt_number"),
            to_attr="prefetched_attempts",
        )
        return super().get_queryset(request).prefetch_related(latest_attempts)

    @admin.display(description="Runtime ID")
    def runtime_id_display(self, obj):
        return obj.runtime_identifier or "-"

    @admin.action(description="Cancel selected jobs")
    def cancel_jobs(self, request, queryset):
        for job in queryset.iterator():
            cancel_job(job, actor=request.user, source="admin")
