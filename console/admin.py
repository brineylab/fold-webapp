from django.contrib import admin

from console.models import ActionLog, RunnerConfig, SiteSettings, UserQuota


@admin.register(RunnerConfig)
class RunnerConfigAdmin(admin.ModelAdmin):
    list_display = ("runner_key", "enabled", "image_uri")
    list_filter = ("enabled",)
    search_fields = ("runner_key",)
    readonly_fields = ("updated_at", "updated_by")
    fieldsets = (
        (None, {
            "fields": ("runner_key", "enabled", "disabled_reason", "image_uri"),
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


@admin.register(ActionLog)
class ActionLogAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "scope",
        "action",
        "source",
        "actor",
        "target_summary",
    )
    list_filter = ("scope", "action", "source", "created_at")
    search_fields = (
        "message",
        "job__id",
        "target_user__username",
        "target_label",
        "runner_key",
        "actor__username",
    )
    readonly_fields = (
        "created_at",
        "scope",
        "action",
        "source",
        "actor",
        "job",
        "target_user",
        "target_label",
        "runner_key",
        "message",
        "metadata",
    )

    @admin.display(description="Target")
    def target_summary(self, obj):
        return obj.target_display or "-"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return request.user.is_staff

    def has_delete_permission(self, request, obj=None):
        return False
