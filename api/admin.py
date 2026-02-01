from django.contrib import admin

from api.models import APIKey


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ("user", "label", "is_active", "created_at", "last_used_at")
    list_filter = ("is_active",)
    search_fields = ("user__username", "label")
    readonly_fields = ("key", "created_at", "last_used_at")
