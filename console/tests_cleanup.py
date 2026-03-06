from __future__ import annotations

import shutil
import tempfile
import uuid
from pathlib import Path

from django.test import TestCase, override_settings

from console.services.cleanup import detect_orphan_workdirs


class TestCleanupOrphanDetection(TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.job_dir = self.tmpdir / "jobs"
        self.job_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_detect_orphan_workdirs_ignores_non_job_system_dirs(self):
        orphan_uuid = str(uuid.uuid4())
        (self.job_dir / orphan_uuid).mkdir()
        (self.job_dir / "harness").mkdir()
        (self.job_dir / "boltz_cache").mkdir()
        (self.job_dir / "chai_cache").mkdir()
        (self.job_dir / "not-a-job-dir").mkdir()

        with override_settings(JOB_BASE_DIR=self.job_dir):
            orphans = detect_orphan_workdirs()

        self.assertEqual([item["name"] for item in orphans], [orphan_uuid])
