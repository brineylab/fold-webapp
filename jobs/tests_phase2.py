from __future__ import annotations

import shutil
import tempfile
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from jobs.execution import local_attempt_paths, run_local_worker_iteration
from jobs.management.commands.run_job_worker import run_worker_iteration
from jobs.models import Job, JobAttempt
from jobs.services import cancel_job, create_and_submit_job
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


class _StubExecutorRunner:
    def validate(self, sequences, params):
        return []

    def build_script(self, job, config=None) -> str:
        return """#!/bin/bash
#SBATCH --job-name=test
set -euo pipefail
docker run --rm --gpus all alpine echo hello
"""


class LocalBackendSubmissionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="local-submit", password="testpass")
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch("jobs.services.slurm.submit")
    @patch("jobs.services.get_runner")
    def test_local_backend_queues_job_without_slurm_submission(
        self,
        mock_get_runner,
        mock_submit,
    ):
        mock_get_runner.return_value = _StubExecutorRunner()

        with override_settings(
            JOB_EXECUTION_BACKEND="local",
            JOB_BASE_DIR=self.tmpdir,
            GPU_SLOTS=[0],
        ):
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
            input_path = job.workdir / "input" / "input.pdb"

        attempt = job.attempts.get()

        self.assertEqual(job.status, Job.Status.PENDING)
        self.assertEqual(job.submitted_at, None)
        self.assertEqual(job.slurm_job_id, "")
        self.assertEqual(attempt.status, JobAttempt.Status.PENDING)
        self.assertEqual(attempt.scheduler_job_id, "")
        self.assertTrue(input_path.exists())
        mock_submit.assert_not_called()


class LocalWorkerDispatchTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="local-dispatch", password="testpass")
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch("jobs.execution.subprocess.Popen")
    @patch("jobs.execution.get_runner")
    def test_worker_dispatches_priority_job_first(self, mock_get_runner, mock_popen):
        mock_get_runner.return_value = _StubExecutorRunner()
        mock_popen.return_value = SimpleNamespace(pid=4242)

        earlier = timezone.now() - timedelta(minutes=5)
        later = timezone.now() - timedelta(minutes=1)
        standard_job = Job.objects.create(
            owner=self.user,
            runner="boltz-2",
            model_key="stub",
            status=Job.Status.PENDING,
            queued_at=earlier,
            priority_tier_snapshot="standard",
        )
        priority_job = Job.objects.create(
            owner=self.user,
            runner="boltz-2",
            model_key="stub",
            status=Job.Status.PENDING,
            queued_at=later,
            priority_tier_snapshot="priority",
        )
        JobAttempt.objects.create(
            job=standard_job,
            attempt_number=1,
            status=JobAttempt.Status.PENDING,
        )
        priority_attempt = JobAttempt.objects.create(
            job=priority_job,
            attempt_number=1,
            status=JobAttempt.Status.PENDING,
        )

        with override_settings(
            JOB_EXECUTION_BACKEND="local",
            JOB_BASE_DIR=self.tmpdir,
            GPU_SLOTS=[0],
        ):
            run_local_worker_iteration()
            paths = local_attempt_paths(priority_job, priority_attempt)
            runner_script = paths.runner_script.read_text(encoding="utf-8")

        standard_job.refresh_from_db()
        priority_job.refresh_from_db()
        priority_attempt.refresh_from_db()

        self.assertEqual(standard_job.status, Job.Status.PENDING)
        self.assertEqual(priority_job.status, Job.Status.RUNNING)
        self.assertEqual(priority_attempt.status, JobAttempt.Status.RUNNING)
        self.assertEqual(priority_attempt.gpu_index, 0)
        self.assertEqual(priority_attempt.scheduler_job_id, "local:4242")

        self.assertTrue(paths.runner_script.exists())
        self.assertTrue(paths.launcher_script.exists())
        self.assertIn("--cidfile", runner_script)
        self.assertIn("device=0", runner_script)
        self.assertEqual(priority_attempt.stdout_path, str(paths.stdout_path))
        self.assertEqual(priority_attempt.stderr_path, str(paths.stderr_path))

    def test_worker_reconciles_completed_local_attempt(self):
        queued_at = timezone.now() - timedelta(minutes=10)
        started_at = timezone.now() - timedelta(minutes=4)
        finished_at = timezone.now()

        job = Job.objects.create(
            owner=self.user,
            runner="boltz-2",
            model_key="stub",
            status=Job.Status.RUNNING,
            queued_at=queued_at,
            started_at=started_at,
            submitted_at=started_at,
        )
        attempt = JobAttempt.objects.create(
            job=job,
            attempt_number=1,
            status=JobAttempt.Status.RUNNING,
            gpu_index=0,
            started_at=started_at,
        )

        with override_settings(
            JOB_EXECUTION_BACKEND="local",
            JOB_BASE_DIR=self.tmpdir,
            GPU_SLOTS=[0],
        ):
            paths = local_attempt_paths(job, attempt)
            paths.root.mkdir(parents=True, exist_ok=True)
            paths.exit_code_file.write_text("0", encoding="utf-8")
            paths.finished_at_file.write_text(
                finished_at.isoformat(),
                encoding="utf-8",
            )

            run_local_worker_iteration()

        job.refresh_from_db()
        attempt.refresh_from_db()

        self.assertEqual(job.status, Job.Status.COMPLETED)
        self.assertEqual(attempt.status, JobAttempt.Status.COMPLETED)
        self.assertEqual(attempt.exit_code, 0)
        self.assertIsNotNone(job.finished_at)
        self.assertGreaterEqual(job.run_seconds or 0, 0)


class LocalCancellationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="local-cancel", password="testpass")
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch("jobs.execution.subprocess.run")
    def test_cancel_job_stops_running_local_container(self, mock_run):
        job = Job.objects.create(
            owner=self.user,
            runner="boltz-2",
            model_key="stub",
            status=Job.Status.RUNNING,
            queued_at=timezone.now() - timedelta(minutes=2),
        )
        attempt = JobAttempt.objects.create(
            job=job,
            attempt_number=1,
            status=JobAttempt.Status.RUNNING,
            gpu_index=0,
        )

        with override_settings(
            JOB_EXECUTION_BACKEND="local",
            JOB_BASE_DIR=self.tmpdir,
        ):
            paths = local_attempt_paths(job, attempt)
            paths.root.mkdir(parents=True, exist_ok=True)
            paths.container_file.write_text("container-123", encoding="utf-8")

            cancelled = cancel_job(job, actor=self.user, source="admin")

        job.refresh_from_db()
        attempt.refresh_from_db()

        self.assertTrue(cancelled)
        self.assertEqual(job.status, Job.Status.CANCELLED)
        self.assertEqual(attempt.status, JobAttempt.Status.CANCELLED)
        mock_run.assert_called_once_with(
            ["docker", "stop", "--time", "10", "container-123"],
            capture_output=True,
            text=True,
        )


class WorkerBackendRoutingTests(SimpleTestCase):
    @override_settings(JOB_EXECUTION_BACKEND="local")
    @patch("jobs.management.commands.run_job_worker.call_command")
    @patch("jobs.management.commands.run_job_worker.run_local_worker_iteration")
    def test_run_worker_iteration_uses_local_backend(
        self,
        mock_local_iteration,
        mock_call_command,
    ):
        run_worker_iteration()

        mock_local_iteration.assert_called_once()
        mock_call_command.assert_not_called()

    @override_settings(JOB_EXECUTION_BACKEND="slurm")
    @patch("jobs.management.commands.run_job_worker.call_command")
    @patch("jobs.management.commands.run_job_worker.run_local_worker_iteration")
    def test_run_worker_iteration_keeps_slurm_path_available(
        self,
        mock_local_iteration,
        mock_call_command,
    ):
        run_worker_iteration()

        mock_local_iteration.assert_not_called()
        mock_call_command.assert_called_once_with("poll_jobs")
