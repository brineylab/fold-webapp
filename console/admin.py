from django.contrib import admin

from console.models import RunnerConfig, SiteSettings, UserQuota


@admin.register(RunnerConfig)
class RunnerConfigAdmin(admin.ModelAdmin):
    list_display = ("runner_key", "enabled", "partition", "gpus", "mem_gb", "time_limit", "image_uri")
    list_filter = ("enabled",)
    search_fields = ("runner_key",)
    readonly_fields = ("updated_at", "updated_by")
    fieldsets = (
        (None, {
            "fields": ("runner_key", "enabled", "disabled_reason"),
        }),
        ("SLURM Resources", {
            "fields": ("partition", "gpus", "cpus", "mem_gb", "time_limit"),
        }),
        ("Container", {
            "fields": ("image_uri", "extra_env", "extra_mounts"),
        }),
        ("Audit", {
            "fields": ("updated_at", "updated_by"),
        }),
    )

    def save_model(self, request, obj, form, change):
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(UserQuota)
class UserQuotaAdmin(admin.ModelAdmin):
    list_display = ("user", "max_concurrent_jobs", "max_queued_jobs", "jobs_per_day", "is_disabled")
    list_filter = ("is_disabled",)
    search_fields = ("user__username",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ("__str__", "maintenance_mode", "updated_at")
    readonly_fields = ("updated_at", "updated_by")

    def save_model(self, request, obj, form, change):
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)

    def has_add_permission(self, request):
        # Singleton — only allow adding if none exists
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
