from __future__ import annotations

import shutil
import tempfile
import uuid
from pathlib import Path

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone

from console.models import ActionLog
from console.services.jobs import cancel_job as console_cancel_job
from console.services.quota import get_user_quota
from jobs.models import Job, JobAttempt


class Phase5OperationsLogTests(TestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            username="ops-phase5",
            password="testpass",
            is_staff=True,
            is_superuser=True,
        )
        self.job_owner = User.objects.create_user(
            username="owner-phase5",
            password="testpass",
        )
        self.client.force_login(self.staff_user)

    def test_operations_log_shows_action_records_and_attempts_for_job(self):
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
            gpu_index=0,
        )

        console_cancel_job(job, self.staff_user)

        response = self.client.get("/console/audit/", {"job": str(job.id)})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Operations Log")
        self.assertContains(response, "Job Timeline")
        self.assertContains(response, "local:4242")
        self.assertContains(response, "cancelled")

    def test_quota_update_writes_action_log(self):
        quota = get_user_quota(self.job_owner)

        response = self.client.post(
            f"/console/users/{self.job_owner.id}/quota/",
            {
                "priority_tier": "priority",
                "max_concurrent_jobs": 2,
                "max_queued_jobs": 6,
                "jobs_per_day": 12,
                "jobs_per_month": 120,
                "retention_days": 45,
            },
        )

        self.assertEqual(response.status_code, 302)

        log = ActionLog.objects.get(
            scope=ActionLog.Scope.POLICY,
            action="quota_updated",
            target_user=self.job_owner,
        )
        self.assertEqual(log.actor, self.staff_user)
        self.assertEqual(log.metadata["before"]["priority_tier"], quota.priority_tier)
        self.assertEqual(log.metadata["after"]["priority_tier"], "priority")


class Phase5ConsoleSurfaceTests(TestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            username="superops-phase5",
            password="testpass",
            is_staff=True,
            is_superuser=True,
        )
        self.target_user = User.objects.create_user(
            username="target-phase5",
            password="testpass",
            email="target@example.com",
        )
        self.client.force_login(self.staff_user)

    def test_user_detail_moves_generic_account_edits_to_django_admin(self):
        response = self.client.get(f"/console/users/{self.target_user.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Open in Django Admin")
        self.assertContains(response, "Disable New Job Submissions")
        self.assertNotContains(response, "Reset Password")
        self.assertNotContains(response, "Deactivate (Django)")


class Phase5CleanupDashboardTests(TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.job_dir = self.tmpdir / "jobs"
        self.job_dir.mkdir(parents=True, exist_ok=True)
        self.staff_user = User.objects.create_user(
            username="cleanup-phase5",
            password="testpass",
            is_staff=True,
        )
        self.job_owner = User.objects.create_user(
            username="cleanup-owner",
            password="testpass",
        )
        self.client.force_login(self.staff_user)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_cleanup_dashboard_reports_orphans_without_delete_actions(self):
        (self.job_dir / str(uuid.uuid4())).mkdir()
        Job.objects.create(
            owner=self.job_owner,
            runner="boltz-2",
            model_key="stub",
            status=Job.Status.COMPLETED,
            queued_at=timezone.now(),
            completed_at=timezone.now(),
        )

        with override_settings(JOB_BASE_DIR=self.job_dir):
            response = self.client.get("/console/cleanup/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "review-only")
        self.assertContains(response, "Filesystem Orphans")
        self.assertNotContains(response, "Delete All Orphans")
        self.assertNotContains(response, "/console/cleanup/delete-orphan/")
