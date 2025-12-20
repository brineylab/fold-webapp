from __future__ import annotations

from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords


class UserQuota(models.Model):
    """
    Per-user quota and account settings.
    
    Admin users (is_staff=True) are exempt from quota limits by default.
    Records are auto-created on first job submission if they don't exist.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="quota",
    )
    
    # Rate limits
    max_concurrent_jobs = models.PositiveIntegerField(
        default=1,
        help_text="Maximum number of jobs that can be running simultaneously",
    )
    max_queued_jobs = models.PositiveIntegerField(
        default=5,
        help_text="Maximum number of jobs that can be pending in the queue",
    )
    jobs_per_day = models.PositiveIntegerField(
        default=10,
        help_text="Maximum number of jobs that can be submitted per day",
    )
    
    # Data retention (days, 0 = never delete)
    retention_days = models.PositiveIntegerField(
        default=30,
        help_text="Days to retain job workdirs (0 = never delete)",
    )
    
    # Account status
    is_disabled = models.BooleanField(
        default=False,
        help_text="If true, user cannot submit new jobs",
    )
    disabled_reason = models.TextField(
        blank=True,
        help_text="Reason for disabling the account",
    )
    disabled_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the account was disabled",
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Audit history tracking
    history = HistoricalRecords()
    
    class Meta:
        verbose_name = "User Quota"
        verbose_name_plural = "User Quotas"
    
    def __str__(self) -> str:
        return f"Quota for {self.user.username}"


class SiteSettings(models.Model):
    """
    Singleton for site-wide settings.
    
    Use get_settings() to retrieve the singleton instance.
    """
    maintenance_mode = models.BooleanField(
        default=False,
        help_text="If true, new job submissions are blocked",
    )
    maintenance_message = models.TextField(
        blank=True,
        default="System is under maintenance. Please try again later.",
        help_text="Message shown to users when maintenance mode is active",
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="site_settings_updates",
    )
    
    # Audit history tracking
    history = HistoricalRecords()
    
    class Meta:
        verbose_name = "Site Settings"
        verbose_name_plural = "Site Settings"
    
    def __str__(self) -> str:
        status = "Maintenance ON" if self.maintenance_mode else "Maintenance OFF"
        return f"Site Settings ({status})"
    
    def save(self, *args, **kwargs):
        # Ensure only one instance exists
        self.pk = 1
        super().save(*args, **kwargs)
    
    @classmethod
    def get_settings(cls) -> "SiteSettings":
        """Get or create the singleton settings instance."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class RunnerConfig(models.Model):
    """
    Per-runner configuration.
    
    Records are auto-created for each registered runner on first access.
    Use get_config(runner_key) to retrieve configuration.
    """
    runner_key = models.CharField(
        max_length=50,
        unique=True,
        help_text="Unique key identifying the runner (e.g., 'alphafold3')",
    )
    enabled = models.BooleanField(
        default=True,
        help_text="If false, this runner cannot be selected for new jobs",
    )
    disabled_reason = models.TextField(
        blank=True,
        help_text="Reason for disabling this runner (shown to users)",
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="runner_config_updates",
    )
    
    # Audit history tracking
    history = HistoricalRecords()
    
    class Meta:
        verbose_name = "Runner Configuration"
        verbose_name_plural = "Runner Configurations"
        ordering = ["runner_key"]
    
    def __str__(self) -> str:
        status = "enabled" if self.enabled else "disabled"
        return f"{self.runner_key} ({status})"
    
    @classmethod
    def get_config(cls, runner_key: str) -> "RunnerConfig":
        """Get or create configuration for a runner."""
        obj, _ = cls.objects.get_or_create(runner_key=runner_key)
        return obj
    
    @classmethod
    def get_enabled_runners(cls) -> set[str]:
        """Return set of enabled runner keys."""
        # Get all explicitly disabled runners
        disabled = set(
            cls.objects.filter(enabled=False).values_list("runner_key", flat=True)
        )
        # Import here to avoid circular imports
        from runners import all_runners
        
        all_keys = {r.key for r in all_runners()}
        return all_keys - disabled
    
    @classmethod
    def is_runner_enabled(cls, runner_key: str) -> bool:
        """Check if a specific runner is enabled."""
        try:
            config = cls.objects.get(runner_key=runner_key)
            return config.enabled
        except cls.DoesNotExist:
            # If no config exists, runner is enabled by default
            return True
