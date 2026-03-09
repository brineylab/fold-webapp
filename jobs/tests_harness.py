from __future__ import annotations

import shutil
import tempfile
import zipfile
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase, override_settings

from api.models import APIKey
from jobs.harness import (
    get_case,
    load_cases,
    prepare_executor_case,
    prepare_run_directories,
    read_json,
    resolve_case_fields,
    run_root_local,
    verify_prepared_case,
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

    def test_smoke_cases_define_artifact_checks(self):
        for case in load_cases():
            if case.tier != "smoke":
                continue
            self.assertTrue(case.artifact_checks, case.id)

    def test_fixture_text_resolution(self):
        case = get_case("smoke-boltz2")
        fields = resolve_case_fields(case)
        self.assertTrue(fields["sequences"].startswith(">A|protein\n"))
        self.assertTrue(fields["use_msa_server"])

    def test_realistic_smoke_cases_are_pinned(self):
        chai_case = get_case("smoke-chai1")
        protein_case = get_case("smoke-protein-mpnn")
        ligand_case = get_case("smoke-ligand-mpnn")

        self.assertEqual(
            chai_case.fields["sequences"]["fixture_text"],
            "chai1/de-novo-monomer_1LQ7.fasta",
        )
        self.assertEqual(protein_case.files["pdb_file"], "common/structures/1LQ7.pdb")
        self.assertEqual(
            ligand_case.files["pdb_file"],
            "common/structures/CXCR4_with-ligand_8ZPN.pdb",
        )


class TestHarnessMaterialization(TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.job_dir = self.tmpdir / "jobs"
        self.job_dir.mkdir(parents=True, exist_ok=True)
        self.harness_dir = self.tmpdir / "harness"
        self.harness_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_mpnn_archive(self, path: Path, *, include_fasta: bool) -> None:
        with zipfile.ZipFile(path, "w") as archive:
            if include_fasta:
                archive.writestr("seqs/sample_1.fa", ">designed\nACDEFGHIK")
            archive.writestr("backbones/sample_1.pdb", "ATOM      1  CA  ALA A   1\n")

    def test_prepare_executor_case_writes_inputs_and_script(self):
        with override_settings(
            JOB_BASE_DIR=self.job_dir,
            HARNESS_BASE_DIR=self.harness_dir,
        ):
            prepare_run_directories("run-1")
            metadata = prepare_executor_case("run-1", "smoke-protein-mpnn")

            workdir = Path(metadata.workdir)
            self.assertTrue((workdir / "input" / "input.pdb").exists())
            self.assertTrue((workdir / "job.sh").exists())
            self.assertTrue((workdir / "metadata.json").exists())
            self.assertTrue(metadata.artifact_checks)

    def test_verify_prepared_case_passes_when_archive_members_are_valid(self):
        with override_settings(
            JOB_BASE_DIR=self.job_dir,
            HARNESS_BASE_DIR=self.harness_dir,
        ):
            prepare_run_directories("run-2")
            metadata = prepare_executor_case("run-2", "smoke-protein-mpnn")
            workdir = Path(metadata.workdir)
            output_dir = workdir / "output"
            output_dir.mkdir(parents=True, exist_ok=True)
            self._write_mpnn_archive(output_dir / "results.zip", include_fasta=True)
            (workdir / "stdout.log").write_text("", encoding="utf-8")
            (workdir / "stderr.log").write_text("", encoding="utf-8")

            report = verify_prepared_case("run-2", "smoke-protein-mpnn", exit_code=0)

            self.assertTrue(report["ok"])
            self.assertEqual(report["output_files"], ["results.zip"])
            self.assertEqual(report["artifact_reports"][0]["validated_file"], "results.zip")

    def test_verify_prepared_case_passes_for_multi_artifact_bindcraft_case(self):
        with override_settings(
            JOB_BASE_DIR=self.job_dir,
            HARNESS_BASE_DIR=self.harness_dir,
        ):
            prepare_run_directories("run-3")
            metadata = prepare_executor_case("run-3", "smoke-bindcraft")
            workdir = Path(metadata.workdir)
            output_dir = workdir / "output"
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "binder_001.pdb").write_text(
                (
                    "ATOM      1  CA  ALA A   1      11.104  13.207  10.331  1.00 20.00           C\n"
                    "ATOM      2  CA  GLY A   2      12.320  12.485  10.011  1.00 20.00           C\n"
                ),
                encoding="utf-8",
            )
            (output_dir / "scores.csv").write_text(
                "score,value\nplddt,0.75\n",
                encoding="utf-8",
            )
            (workdir / "stdout.log").write_text("", encoding="utf-8")
            (workdir / "stderr.log").write_text("", encoding="utf-8")

            report = verify_prepared_case("run-3", "smoke-bindcraft", exit_code=0)

            self.assertTrue(report["ok"])
            self.assertEqual(len(report["artifact_reports"]), 2)
            self.assertEqual(
                [item["validated_file"] for item in report["artifact_reports"]],
                ["binder_001.pdb", "scores.csv"],
            )

    def test_verify_prepared_case_fails_when_outputs_missing(self):
        with override_settings(
            JOB_BASE_DIR=self.job_dir,
            HARNESS_BASE_DIR=self.harness_dir,
        ):
            prepare_run_directories("run-4")
            metadata = prepare_executor_case("run-4", "smoke-protein-mpnn")
            workdir = Path(metadata.workdir)
            (workdir / "stdout.log").write_text("", encoding="utf-8")
            (workdir / "stderr.log").write_text("", encoding="utf-8")

            report = verify_prepared_case("run-4", "smoke-protein-mpnn", exit_code=0)

            self.assertFalse(report["ok"])
            self.assertTrue(report["errors"])

    def test_verify_prepared_case_fails_when_archive_members_are_invalid(self):
        with override_settings(
            JOB_BASE_DIR=self.job_dir,
            HARNESS_BASE_DIR=self.harness_dir,
        ):
            prepare_run_directories("run-5")
            metadata = prepare_executor_case("run-5", "smoke-protein-mpnn")
            workdir = Path(metadata.workdir)
            output_dir = workdir / "output"
            output_dir.mkdir(parents=True, exist_ok=True)
            self._write_mpnn_archive(output_dir / "results.zip", include_fasta=False)
            (workdir / "stdout.log").write_text("", encoding="utf-8")
            (workdir / "stderr.log").write_text("", encoding="utf-8")

            report = verify_prepared_case("run-5", "smoke-protein-mpnn", exit_code=0)

            self.assertFalse(report["ok"])
            self.assertIn("Missing required archive member", "\n".join(report["errors"]))


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
            HARNESS_BASE_DIR=self.harness_dir,
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
            self.assertTrue(payload["executor_case_ids"])
            self.assertTrue(payload["prepare_only_case_ids"])
            self.assertEqual(payload["users"]["admin"]["username"], "harness_admin")
            self.assertTrue(
                APIKey.objects.filter(user__username="harness_admin").exists()
            )


class TestHarnessSummaryCommand(TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.job_dir = self.tmpdir / "jobs"
        self.job_dir.mkdir(parents=True, exist_ok=True)
        self.harness_dir = self.tmpdir / "harness"
        self.harness_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_summary_command_writes_json_and_markdown(self):
        with override_settings(
            JOB_BASE_DIR=self.job_dir,
            HARNESS_BASE_DIR=self.harness_dir,
        ):
            call_command(
                "harness_prepare",
                "--run-id",
                "run-summary",
                "--tier",
                "smoke",
                "--phase",
                "executor",
                "--case",
                "smoke-protein-mpnn",
            )
            prepare_executor_case("run-summary", "smoke-protein-mpnn")

            workdir = (
                run_root_local("run-summary")
                / "executor"
                / "smoke-protein-mpnn"
            )
            output_dir = workdir / "output"
            output_dir.mkdir(parents=True, exist_ok=True)
            self._write_summary_archive(output_dir / "results.zip")
            (workdir / "stdout.log").write_text("", encoding="utf-8")
            (workdir / "stderr.log").write_text("", encoding="utf-8")

            verify_prepared_case("run-summary", "smoke-protein-mpnn", exit_code=0)
            call_command("harness_summary", "--run-id", "run-summary")

            summary_json = read_json(run_root_local("run-summary") / "reports" / "summary.json")
            summary_md = (
                run_root_local("run-summary") / "reports" / "summary.md"
            ).read_text(encoding="utf-8")

            self.assertTrue(summary_json["ok"])
            self.assertIn("smoke-protein-mpnn", summary_md)

    def _write_summary_archive(self, path: Path) -> None:
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("seqs/sample_1.fa", ">designed\nACDEFGHIK")
