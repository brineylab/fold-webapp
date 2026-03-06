from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase, override_settings

from api.models import APIKey
from jobs.harness import (
    get_case,
    load_cases,
    materialize_case,
    prepare_run_directories,
    read_json,
    resolve_case_fields,
    run_root_local,
    verify_materialized_case,
)
from model_types import get_submittable_model_types

class TestHarnessManifest(TestCase):
    def test_each_submittable_model_has_one_smoke_case(self):
        cases = load_cases()
        smoke_ids = {
            model.key: [
                case.id
                for case in cases
                if case.model_key == model.key and case.tier == "smoke"
            ]
            for model in get_submittable_model_types()
        }
        for model_key, case_ids in smoke_ids.items():
            self.assertEqual(
                len(case_ids),
                1,
                f"Expected one smoke case for {model_key}, found {case_ids}",
            )

    def test_fixture_text_resolution(self):
        case = get_case("smoke-boltz2")
        fields = resolve_case_fields(case)
        self.assertIn(">protein_A", fields["sequences"])


class TestHarnessMaterialization(TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.job_dir = self.tmpdir / "jobs"
        self.job_dir.mkdir(parents=True, exist_ok=True)
        self.harness_dir = self.tmpdir / "harness"
        self.harness_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_materialize_case_writes_inputs_and_script(self):
        with override_settings(
            JOB_BASE_DIR=self.job_dir,
            JOB_BASE_DIR_HOST=self.job_dir,
            HARNESS_BASE_DIR=self.harness_dir,
            HARNESS_BASE_DIR_HOST=self.harness_dir,
        ):
            prepare_run_directories("run-1")
            metadata = materialize_case("run-1", "smoke-protein-mpnn")

            workdir = Path(metadata.local_workdir)
            self.assertTrue((workdir / "input" / "input.pdb").exists())
            self.assertTrue((workdir / "job.sbatch").exists())
            self.assertTrue((workdir / "metadata.json").exists())

    def test_verify_materialized_case_passes_when_expected_outputs_exist(self):
        with override_settings(
            JOB_BASE_DIR=self.job_dir,
            JOB_BASE_DIR_HOST=self.job_dir,
            HARNESS_BASE_DIR=self.harness_dir,
            HARNESS_BASE_DIR_HOST=self.harness_dir,
        ):
            prepare_run_directories("run-2")
            metadata = materialize_case("run-2", "smoke-protein-mpnn")
            workdir = Path(metadata.local_workdir)
            output_dir = workdir / "output"
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "results.zip").write_bytes(b"zip-data")
            (workdir / "stdout.log").write_text("", encoding="utf-8")
            (workdir / "stderr.log").write_text("", encoding="utf-8")

            report = verify_materialized_case("run-2", "smoke-protein-mpnn", exit_code=0)

            self.assertTrue(report["ok"])
            self.assertEqual(report["output_files"], ["results.zip"])

    def test_verify_materialized_case_fails_when_outputs_missing(self):
        with override_settings(
            JOB_BASE_DIR=self.job_dir,
            JOB_BASE_DIR_HOST=self.job_dir,
            HARNESS_BASE_DIR=self.harness_dir,
            HARNESS_BASE_DIR_HOST=self.harness_dir,
        ):
            prepare_run_directories("run-3")
            metadata = materialize_case("run-3", "smoke-protein-mpnn")
            workdir = Path(metadata.local_workdir)
            (workdir / "stdout.log").write_text("", encoding="utf-8")
            (workdir / "stderr.log").write_text("", encoding="utf-8")

            report = verify_materialized_case("run-3", "smoke-protein-mpnn", exit_code=0)

            self.assertFalse(report["ok"])
            self.assertTrue(report["errors"])


class TestHarnessPrepareCommand(TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.job_dir = self.tmpdir / "jobs"
        self.job_dir.mkdir(parents=True, exist_ok=True)
        self.harness_dir = self.tmpdir / "harness"
        self.harness_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_prepare_command_writes_prepare_json_and_credentials(self):
        with override_settings(
            JOB_BASE_DIR=self.job_dir,
            JOB_BASE_DIR_HOST=self.job_dir,
            HARNESS_BASE_DIR=self.harness_dir,
            HARNESS_BASE_DIR_HOST=self.harness_dir,
        ):
            call_command(
                "harness_prepare",
                "--run-id",
                "run-prepare",
                "--tier",
                "extended",
                "--phase",
                "all",
            )

            payload = read_json(run_root_local("run-prepare") / "prepare.json")

            self.assertEqual(payload["run_id"], "run-prepare")
            self.assertTrue(payload["direct_case_ids"])
            self.assertTrue(payload["materialize_case_ids"])
            self.assertEqual(payload["users"]["admin"]["username"], "harness_admin")
            self.assertTrue(
                APIKey.objects.filter(user__username="harness_admin").exists()
            )
