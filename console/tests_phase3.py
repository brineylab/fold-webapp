from __future__ import annotations

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone

from console.services.monitoring import get_execution_backend_status
from jobs.models import Job, JobAttempt


class Phase3ConsoleJobListTests(TestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            username="ops-phase3",
            password="testpass",
            is_staff=True,
        )
        self.job_owner = User.objects.create_user(
            username="owner-phase3",
            password="testpass",
        )
        self.client.force_login(self.staff_user)

    def test_console_job_search_matches_local_runtime_identifier(self):
        job = Job.objects.create(
            owner=self.job_owner,
            runner="boltz-2",
            model_key="stub",
            status=Job.Status.RUNNING,
            queued_at=timezone.now(),
        )
        JobAttempt.objects.create(
            job=job,
            attempt_number=1,
            status=JobAttempt.Status.RUNNING,
            scheduler_job_id="local:4242",
            container_id="container-4242",
        )

        response = self.client.get("/console/jobs/", {"search": "local:4242"})

        self.assertEqual(response.status_code, 200)
        self.assertIn(job, list(response.context["jobs"]))
        self.assertContains(response, "Runtime ID")


class Phase3MonitoringTests(TestCase):
    @override_settings(JOB_EXECUTION_BACKEND="local", GPU_SLOTS=[0, 2])
    def test_backend_status_reports_local_executor(self):
        status = get_execution_backend_status()

        self.assertEqual(status["mode"], "local")
        self.assertEqual(status["label"], "Local Docker Executor")
        self.assertEqual(status["gpu_slots"], [0, 2])
        self.assertFalse(status["uses_legacy_slurm"])

    @override_settings(JOB_EXECUTION_BACKEND="slurm", FAKE_SLURM=True)
    def test_backend_status_reports_legacy_slurm_mode(self):
        status = get_execution_backend_status()

        self.assertEqual(status["mode"], "slurm")
        self.assertTrue(status["uses_legacy_slurm"])
        self.assertIn("FAKE_SLURM", status["message"])
