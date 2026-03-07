from __future__ import annotations

import shutil
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from jobs.models import Job, JobAttempt
from jobs.services import cancel_job, create_and_submit_job, sync_job_status
from model_types.base import BaseModelType


class _StubModelType(BaseModelType):
    key = "stub"
    name = "Stub"

    def validate(self, cleaned_data):
        return None

    def normalize_inputs(self, cleaned_data):
        return {"sequences": "", "params": {}, "files": {}}

    def resolve_runner_key(self, cleaned_data):
        return "boltz-2"


class Phase1SubmissionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="phase1", password="testpass")
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch("jobs.services.get_runner")
    @patch("jobs.services.slurm.submit", return_value="FAKE-123")
    def test_submission_creates_first_attempt_and_priority_snapshot(
        self,
        mock_submit,
        mock_get_runner,
    ):
        from console.services.quota import get_user_quota

        class StubRunner:
            def validate(self, sequences, params):
                return []

            def build_script(self, job, config):
                return "echo test"

        mock_get_runner.return_value = StubRunner()

        quota = get_user_quota(self.user)
        quota.priority_tier = "priority"
        quota.save(update_fields=["priority_tier"])

        with override_settings(JOB_BASE_DIR=self.tmpdir):
            job = create_and_submit_job(
                owner=self.user,
                model_type=_StubModelType(),
                runner_key="boltz-2",
                sequences="",
                params={},
                model_key="stub",
                input_payload={
                    "sequences": "",
                    "params": {},
                    "files": {"input.pdb": b"ATOM"},
                },
            )

        self.assertEqual(job.priority_tier_snapshot, "priority")
        self.assertEqual(job.attempt_count, 1)
        attempt = job.attempts.get()
        self.assertEqual(attempt.attempt_number, 1)
        self.assertEqual(attempt.status, JobAttempt.Status.PENDING)
        self.assertEqual(attempt.scheduler_job_id, "FAKE-123")
        self.assertEqual(job.slurm_job_id, "FAKE-123")
        self.assertIsNotNone(job.submitted_at)
        mock_submit.assert_called_once()


class Phase1LifecycleTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="lifecycle", password="testpass")
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
            scheduler_job_id="123",
        )
        self.job.attempt_count = 1
        self.job.slurm_job_id = "123"
        self.job.save(update_fields=["attempt_count", "slurm_job_id"])

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

    @patch("jobs.services.slurm.cancel")
    def test_cancel_job_marks_cancelled(self, mock_cancel):
        cancelled = cancel_job(self.job, actor=self.user, source="admin")

        self.job.refresh_from_db()
        self.attempt.refresh_from_db()

        self.assertTrue(cancelled)
        self.assertEqual(self.job.status, Job.Status.CANCELLED)
        self.assertEqual(self.attempt.status, JobAttempt.Status.CANCELLED)
        self.assertIn("admin", self.job.error_message.lower())
        self.assertIsNotNone(self.job.completed_at)
        mock_cancel.assert_called_once_with("123")


class Phase1PollerTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="poll-phase1", password="testpass")
        self.job = Job.objects.create(
            owner=self.user,
            runner="boltz-2",
            model_key="stub",
            status=Job.Status.RUNNING,
            slurm_job_id="77",
            queued_at=timezone.now() - timedelta(minutes=15),
            submitted_at=timezone.now() - timedelta(minutes=14),
        )
        JobAttempt.objects.create(
            job=self.job,
            attempt_number=1,
            status=JobAttempt.Status.RUNNING,
            scheduler_job_id="77",
            started_at=timezone.now() - timedelta(minutes=14),
        )

    @patch("jobs.management.commands.poll_jobs.slurm.check_status", return_value="CANCELLED")
    def test_poll_jobs_marks_cancelled_terminal_state(self, mock_check_status):
        call_command("poll_jobs")

        self.job.refresh_from_db()
        attempt = self.job.attempts.get()

        self.assertEqual(self.job.status, Job.Status.CANCELLED)
        self.assertEqual(attempt.status, JobAttempt.Status.CANCELLED)
        self.assertIsNotNone(self.job.completed_at)
        mock_check_status.assert_called_once_with("77")
