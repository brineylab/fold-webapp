from __future__ import annotations

import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Job",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("runner", models.CharField(max_length=50)),
                (
                    "status",
                    models.CharField(
                        choices=[("PENDING", "PENDING"), ("RUNNING", "RUNNING"), ("COMPLETED", "COMPLETED"), ("FAILED", "FAILED")],
                        default="PENDING",
                        max_length=20,
                    ),
                ),
                ("sequences", models.TextField()),
                ("params", models.JSONField(blank=True, default=dict)),
                ("slurm_job_id", models.CharField(blank=True, max_length=50)),
                ("error_message", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "owner",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
                ),
            ],
        ),
    ]


