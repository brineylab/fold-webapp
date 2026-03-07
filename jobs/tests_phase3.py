from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone

from jobs.models import Job, JobAttempt
from jobs.services import serialize_job


class Phase3RuntimeMetadataTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="phase3-user", password="testpass")
        self.tmpdir = Path(tempfile.mkdtemp())
        self.client.force_login(self.user)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_serialize_job_includes_local_runtime_metadata(self):
        job = Job.objects.create(
            owner=self.user,
            runner="boltz-2",
            model_key="stub",
            status=Job.Status.RUNNING,
            queued_at=timezone.now(),
        )
        JobAttempt.objects.create(
            job=job,
            attempt_number=2,
            status=JobAttempt.Status.RUNNING,
            scheduler_job_id="local:4242",
            container_id="container-123",
            gpu_index=3,
        )

        payload = serialize_job(job)

        self.assertEqual(payload["execution_backend"], "local")
        self.assertEqual(payload["runtime_id"], "local:4242")
        self.assertEqual(payload["runtime_container_id"], "container-123")
        self.assertEqual(payload["runtime_gpu_index"], 3)
        self.assertEqual(payload["current_attempt_number"], 2)

    def test_job_detail_view_shows_runtime_metadata(self):
        with override_settings(JOB_BASE_DIR=self.tmpdir):
            job = Job.objects.create(
                owner=self.user,
                runner="boltz-2",
                model_key="stub",
                status=Job.Status.RUNNING,
                queued_at=timezone.now(),
            )
            JobAttempt.objects.create(
                job=job,
                attempt_number=1,
                status=JobAttempt.Status.RUNNING,
                scheduler_job_id="local:5150",
                gpu_index=0,
            )

            response = self.client.get(f"/jobs/{job.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Runtime ID")
        self.assertContains(response, "local:5150")
        self.assertContains(response, "Backend")
        self.assertContains(response, "local")
