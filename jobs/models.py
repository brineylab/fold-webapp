from __future__ import annotations

import uuid
from pathlib import Path

from django.conf import settings
from django.db import models
from django.utils import timezone


class Job(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING"
        RUNNING = "RUNNING"
        COMPLETED = "COMPLETED"
        FAILED = "FAILED"
        CANCELLED = "CANCELLED"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=100, blank=True, default="")
    runner = models.CharField(max_length=50)
    model_key = models.CharField(max_length=50, default="runner")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    sequences = models.TextField(blank=True, default="")
    params = models.JSONField(default=dict, blank=True)
    input_payload = models.JSONField(default=dict, blank=True)
    output_payload = models.JSONField(default=dict, blank=True)

    error_message = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    queued_at = models.DateTimeField(default=timezone.now)
    submitted_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    wait_seconds = models.PositiveIntegerField(null=True, blank=True)
    run_seconds = models.PositiveIntegerField(null=True, blank=True)
    gpu_seconds = models.PositiveIntegerField(null=True, blank=True)
    priority_tier_snapshot = models.CharField(max_length=20, blank=True, default="")
    attempt_count = models.PositiveIntegerField(default=0)

    hidden_from_owner = models.BooleanField(default=False)

    @property
    def workdir(self) -> Path:
        base = getattr(settings, "JOB_BASE_DIR", None)
        if base is None:
            base = Path(".")
        return Path(base) / str(self.id)

    @property
    def current_attempt(self):
        prefetched = getattr(self, "prefetched_attempts", None)
        if prefetched is not None:
            return prefetched[0] if prefetched else None
        return self.attempts.order_by("-attempt_number").first()

    @property
    def runtime_backend(self) -> str:
        return "local"

    @property
    def runtime_identifier(self) -> str:
        attempt = self.current_attempt
        if attempt is None:
            return ""
        if attempt.scheduler_job_id:
            return attempt.scheduler_job_id
        if attempt.container_id:
            return attempt.container_id
        return ""

    @property
    def runtime_container_id(self) -> str:
        attempt = self.current_attempt
        if attempt is None:
            return ""
        return attempt.container_id

    @property
    def runtime_gpu_index(self):
        attempt = self.current_attempt
        if attempt is None:
            return None
        return attempt.gpu_index

    def __str__(self) -> str:
        return f"{self.id} ({self.runner})"


class JobAttempt(models.Model):
    class Status(models.TextChoices):
        PENDING = Job.Status.PENDING, "Pending"
        RUNNING = Job.Status.RUNNING, "Running"
        COMPLETED = Job.Status.COMPLETED, "Completed"
        FAILED = Job.Status.FAILED, "Failed"
        CANCELLED = Job.Status.CANCELLED, "Cancelled"

    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="attempts")
    attempt_number = models.PositiveIntegerField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    scheduler_job_id = models.CharField(max_length=50, blank=True)
    container_id = models.CharField(max_length=200, blank=True)
    gpu_index = models.PositiveIntegerField(null=True, blank=True)

    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    exit_code = models.IntegerField(null=True, blank=True)
    stdout_path = models.CharField(max_length=500, blank=True)
    stderr_path = models.CharField(max_length=500, blank=True)
    failure_summary = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["attempt_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["job", "attempt_number"],
                name="jobs_jobattempt_unique_attempt_number",
            )
        ]

    def __str__(self) -> str:
        return f"{self.job_id} attempt {self.attempt_number}"
