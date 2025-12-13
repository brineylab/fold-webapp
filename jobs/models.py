from __future__ import annotations

import uuid
from pathlib import Path

from django.conf import settings
from django.db import models


class Job(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING"
        RUNNING = "RUNNING"
        COMPLETED = "COMPLETED"
        FAILED = "FAILED"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=100, blank=True, default="")
    runner = models.CharField(max_length=50)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    sequences = models.TextField()
    params = models.JSONField(default=dict, blank=True)

    slurm_job_id = models.CharField(max_length=50, blank=True)
    error_message = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    hidden_from_owner = models.BooleanField(default=False)

    @property
    def workdir(self) -> Path:
        base = getattr(settings, "JOB_BASE_DIR", None)
        if base is None:
            base = Path(".")
        return Path(base) / str(self.id)

    def __str__(self) -> str:
        return f"{self.id} ({self.runner})"


