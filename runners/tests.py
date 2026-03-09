from __future__ import annotations

from django.test import TestCase

from console.models import RunnerConfig
from runners import get_runner


class _FakeJob:
    def __init__(self, job_id="00000000-0000-0000-0000-000000000001", params=None):
        self.id = job_id
        self.params = params or {}
        from pathlib import Path

        self.workdir = Path("/tmp/test-job")


class TestBoltzRunnerBuildScript(TestCase):
    def setUp(self):
        self.runner = get_runner("boltz-2")

    def test_without_config(self):
        script = self.runner.build_script(_FakeJob())

        self.assertIn("#!/bin/bash", script)
        self.assertIn("docker run --rm --gpus all", script)
        self.assertNotIn("#SBATCH", script)

    def test_config_image_override(self):
        config = RunnerConfig(runner_key="boltz-2", image_uri="custom-boltz:v2")

        script = self.runner.build_script(_FakeJob(), config=config)

        self.assertIn("custom-boltz:v2", script)

    def test_params_flags_still_work(self):
        job = _FakeJob(
            params={
                "use_msa_server": True,
                "output_format": "pdb",
                "recycling_steps": 5,
            }
        )

        script = self.runner.build_script(job)

        self.assertIn("--use_msa_server", script)
        self.assertIn("--output_format pdb", script)
        self.assertIn("--recycling_steps 5", script)


class TestLigandMPNNRunnerBuildScript(TestCase):
    def setUp(self):
        self.runner = get_runner("ligandmpnn")

    def test_without_config(self):
        script = self.runner.build_script(
            _FakeJob(params={"model_variant": "protein_mpnn", "noise_level": "v_48_020"})
        )

        self.assertIn("#!/bin/bash", script)
        self.assertIn("docker run --rm --gpus all", script)
        self.assertNotIn("#SBATCH", script)

    def test_config_image_override(self):
        config = RunnerConfig(
            runner_key="ligandmpnn",
            image_uri="custom-ligandmpnn:v1",
        )

        script = self.runner.build_script(
            _FakeJob(params={"model_variant": "protein_mpnn", "noise_level": "v_48_020"}),
            config=config,
        )

        self.assertIn("custom-ligandmpnn:v1", script)

    def test_variant_flags(self):
        protein_script = self.runner.build_script(
            _FakeJob(params={"model_variant": "protein_mpnn", "noise_level": "v_48_020"})
        )
        ligand_script = self.runner.build_script(
            _FakeJob(params={"model_variant": "ligand_mpnn", "noise_level": "v_32_010_25"})
        )

        self.assertIn("--model_type protein_mpnn", protein_script)
        self.assertIn(
            "--checkpoint_path /app/checkpoints/proteinmpnn_v_48_020.pt",
            protein_script,
        )
        self.assertIn("--model_type ligand_mpnn", ligand_script)
        self.assertIn(
            "--checkpoint_path /app/checkpoints/ligandmpnn_v_32_010_25.pt",
            ligand_script,
        )


class TestRunnerShellScripts(TestCase):
    def test_stub_runners_accept_config(self):
        for key in ("alphafold3", "chai-1"):
            script = get_runner(key).build_script(
                _FakeJob(),
                config=RunnerConfig(runner_key=key, image_uri="custom-image:latest"),
            )
            self.assertIn("#!/bin/bash", script)
            self.assertNotIn("#SBATCH", script)

    def test_all_runner_scripts_set_open_umask(self):
        cases = {
            "alphafold3": _FakeJob(),
            "bindcraft": _FakeJob(),
            "boltz-2": _FakeJob(),
            "boltzgen": _FakeJob(),
            "chai-1": _FakeJob(),
            "ligandmpnn": _FakeJob(
                params={"model_variant": "protein_mpnn", "noise_level": "v_48_020"}
            ),
            "rfdiffusion3": _FakeJob(),
        }
        for runner_key, job in cases.items():
            script = get_runner(runner_key).build_script(job)
            self.assertIn("umask 000", script, runner_key)


class TestBindCraftRunnerBuildScript(TestCase):
    def setUp(self):
        self.runner = get_runner("bindcraft")

    def test_without_config(self):
        script = self.runner.build_script(_FakeJob())

        self.assertIn("#!/bin/bash", script)
        self.assertIn("--settings /work/input/target_settings.json", script)
        self.assertNotIn("#SBATCH", script)

    def test_config_image_override(self):
        config = RunnerConfig(runner_key="bindcraft", image_uri="custom-bindcraft:v1")

        script = self.runner.build_script(_FakeJob(), config=config)

        self.assertIn("custom-bindcraft:v1", script)
