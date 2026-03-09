from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from jobs.models import Job, JobAttempt
from jobs.services import cancel_job, get_or_create_current_attempt, sync_job_status


class Phase1LifecycleTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="phase1", password="testpass")
        self.job = Job.objects.create(
            owner=self.user,
            runner="boltz-2",
            model_key="stub",
            status=Job.Status.PENDING,
            queued_at=timezone.now() - timedelta(minutes=10),
        )
        self.attempt = JobAttempt.objects.create(
            job=self.job,
            attempt_number=1,
            status=JobAttempt.Status.PENDING,
        )
        self.job.attempt_count = 1
        self.job.save(update_fields=["attempt_count"])

    def test_sync_job_status_records_usage_metrics(self):
        started_at = timezone.now() - timedelta(minutes=5)
        finished_at = timezone.now()

        sync_job_status(self.job, Job.Status.RUNNING, when=started_at)
        sync_job_status(self.job, Job.Status.COMPLETED, when=finished_at)

        self.job.refresh_from_db()
        self.attempt.refresh_from_db()

        self.assertEqual(self.job.status, Job.Status.COMPLETED)
        self.assertEqual(self.job.started_at, started_at)
        self.assertEqual(self.job.finished_at, finished_at)
        self.assertEqual(self.job.completed_at, finished_at)
        self.assertEqual(self.job.wait_seconds, 300)
        self.assertEqual(self.job.run_seconds, 300)
        self.assertEqual(self.job.gpu_seconds, 300)
        self.assertEqual(self.attempt.status, JobAttempt.Status.COMPLETED)
        self.assertEqual(self.attempt.started_at, started_at)
        self.assertEqual(self.attempt.finished_at, finished_at)

    @patch("jobs.execution.subprocess.run")
    def test_cancel_job_marks_cancelled(self, mock_run):
        mock_run.return_value = SimpleNamespace(returncode=0)
        self.attempt.status = JobAttempt.Status.RUNNING
        self.attempt.container_id = "container-123"
        self.attempt.save(update_fields=["status", "container_id"])
        self.job.status = Job.Status.RUNNING
        self.job.save(update_fields=["status"])

        cancelled = cancel_job(self.job, actor=self.user, source="admin")

        self.job.refresh_from_db()
        self.attempt.refresh_from_db()

        self.assertTrue(cancelled)
        self.assertEqual(self.job.status, Job.Status.CANCELLED)
        self.assertEqual(self.attempt.status, JobAttempt.Status.CANCELLED)
        self.assertIn("admin", self.job.error_message.lower())
        self.assertIsNotNone(self.job.completed_at)
        mock_run.assert_called_once_with(
            ["docker", "stop", "--time", "10", "container-123"],
            capture_output=True,
            text=True,
        )

    def test_get_or_create_current_attempt_backfills_missing_attempt(self):
        self.attempt.delete()
        self.job.attempt_count = 3
        self.job.started_at = timezone.now() - timedelta(minutes=1)
        self.job.finished_at = timezone.now()
        self.job.error_message = "failed"
        self.job.save(
            update_fields=["attempt_count", "started_at", "finished_at", "error_message"]
        )

        attempt = get_or_create_current_attempt(self.job)

        self.job.refresh_from_db()
        self.assertEqual(attempt.attempt_number, 1)
        self.assertEqual(attempt.failure_summary, "failed")
        self.assertEqual(self.job.attempt_count, 1)
