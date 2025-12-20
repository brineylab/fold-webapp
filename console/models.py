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
