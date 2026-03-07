import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("jobs", "0011_phase5_remove_history"),
        ("console", "0006_phase4_simplify_runnerconfig"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ActionLog",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "scope",
                    models.CharField(
                        choices=[
                            ("job", "Job"),
                            ("policy", "Policy"),
                            ("settings", "Settings"),
                            ("cleanup", "Cleanup"),
                            ("api", "API"),
                        ],
                        max_length=20,
                    ),
                ),
                ("action", models.CharField(max_length=50)),
                ("source", models.CharField(blank=True, default="", max_length=20)),
                ("target_label", models.CharField(blank=True, default="", max_length=200)),
                ("runner_key", models.CharField(blank=True, default="", max_length=50)),
                ("message", models.TextField()),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="action_logs_as_actor",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "job",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="action_logs",
                        to="jobs.job",
                    ),
                ),
                (
                    "target_user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="action_logs_as_target",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.DeleteModel(
            name="HistoricalRunnerConfig",
        ),
        migrations.DeleteModel(
            name="HistoricalSiteSettings",
        ),
        migrations.DeleteModel(
            name="HistoricalUserQuota",
        ),
    ]
