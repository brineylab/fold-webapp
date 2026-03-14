from __future__ import annotations

from django.test import TestCase, override_settings

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
        self.assertIn("--shm-size 16g", script)
        self.assertNotIn("#SBATCH", script)

    def test_config_image_override(self):
        config = RunnerConfig(runner_key="boltz-2", image_uri="custom-boltz:v2")

        script = self.runner.build_script(_FakeJob(), config=config)

        self.assertIn("custom-boltz:v2", script)

    def test_params_flags_still_work(self):
        job = _FakeJob(
            params={
                "use_msa_server": True,
                "no_kernels": True,
                "output_format": "pdb",
                "recycling_steps": 5,
            }
        )

        script = self.runner.build_script(job)

        self.assertIn("--use_msa_server", script)
        self.assertIn("--no_kernels", script)
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
        self.assertIn("--shm-size 8g", script)
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

    def test_packages_results_with_python_zipfile(self):
        script = self.runner.build_script(
            _FakeJob(params={"model_variant": "protein_mpnn", "noise_level": "v_48_020"})
        )

        self.assertIn("python3 - <<'PY'", script)
        self.assertNotIn("zip -r results.zip", script)


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
            "openfold3": _FakeJob(),
            "rfdiffusion3": _FakeJob(),
        }
        for runner_key, job in cases.items():
            script = get_runner(runner_key).build_script(job)
            self.assertIn("umask 000", script, runner_key)

    def test_gpu_runners_do_not_export_blank_cuda_visible_devices(self):
        cases = {
            "bindcraft": _FakeJob(),
            "boltz-2": _FakeJob(),
            "boltzgen": _FakeJob(),
            "chai-1": _FakeJob(),
            "ligandmpnn": _FakeJob(
                params={"model_variant": "protein_mpnn", "noise_level": "v_48_020"}
            ),
            "openfold3": _FakeJob(),
            "rfdiffusion3": _FakeJob(),
        }
        for runner_key, job in cases.items():
            script = get_runner(runner_key).build_script(job)
            self.assertIn("cuda_visible_devices_flag", script, runner_key)
            self.assertNotIn(
                "-e CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-}",
                script,
                runner_key,
            )

    def test_gpu_runners_include_shared_memory_budget(self):
        cases = {
            "bindcraft": ("--shm-size 8g", _FakeJob()),
            "boltz-2": ("--shm-size 16g", _FakeJob()),
            "boltzgen": ("--shm-size 8g", _FakeJob()),
            "chai-1": ("--shm-size 8g", _FakeJob()),
            "ligandmpnn": (
                "--shm-size 8g",
                _FakeJob(params={"model_variant": "protein_mpnn", "noise_level": "v_48_020"}),
            ),
            "openfold3": ("--shm-size 16g", _FakeJob()),
            "rfdiffusion3": ("--shm-size 8g", _FakeJob()),
        }
        for runner_key, (expected_flag, job) in cases.items():
            script = get_runner(runner_key).build_script(job)
            self.assertIn(expected_flag, script, runner_key)

    @override_settings(
        DOCKER_DEFAULT_SHM_SIZE="12g",
        DOCKER_DEFAULT_IPC_MODE="host",
        CHAI_DOCKER_SHM_SIZE="12g",
        CHAI_DOCKER_IPC_MODE="host",
    )
    def test_gpu_runner_supports_ipc_override(self):
        script = get_runner("chai-1").build_script(_FakeJob())
        self.assertIn("--shm-size 12g", script)
        self.assertIn("--ipc host", script)

    def test_boltzgen_uses_entrypoint_subcommand(self):
        script = get_runner("boltzgen").build_script(_FakeJob())
        self.assertIn("run /work/input/design.yaml", script)
        self.assertNotIn("boltzgen run /work/input/design.yaml", script)


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


class TestOpenFold3RunnerBuildScript(TestCase):
    def setUp(self):
        self.runner = get_runner("openfold3")

    def test_without_config(self):
        script = self.runner.build_script(_FakeJob())

        self.assertIn("#!/bin/bash", script)
        self.assertIn("docker run --rm --gpus all", script)
        self.assertIn("--shm-size 16g", script)
        self.assertIn("run_openfold predict", script)
        self.assertIn("--query-json /work/input/query.json", script)
        self.assertIn("--output-dir /work/output", script)

    def test_config_image_override(self):
        config = RunnerConfig(runner_key="openfold3", image_uri="custom-openfold3:v1")

        script = self.runner.build_script(_FakeJob(), config=config)

        self.assertIn("custom-openfold3:v1", script)

    def test_msa_server_enabled(self):
        job = _FakeJob(params={"use_msa_server": True})
        script = self.runner.build_script(job)
        self.assertIn("--use-msa-server", script)
        self.assertNotIn("--no-use-msa-server", script)

    def test_msa_server_disabled(self):
        job = _FakeJob(params={"use_msa_server": False})
        script = self.runner.build_script(job)
        self.assertIn("--no-use-msa-server", script)

    def test_templates_enabled(self):
        job = _FakeJob(params={"use_templates": True})
        script = self.runner.build_script(job)
        self.assertIn("--use-templates", script)
        self.assertNotIn("--no-use-templates", script)

    def test_templates_disabled(self):
        job = _FakeJob(params={"use_templates": False})
        script = self.runner.build_script(job)
        self.assertIn("--no-use-templates", script)

    def test_diffusion_samples_flag(self):
        job = _FakeJob(params={"num_diffusion_samples": 10})
        script = self.runner.build_script(job)
        self.assertIn("--num-diffusion-samples 10", script)

    def test_model_seeds_flag(self):
        job = _FakeJob(params={"num_model_seeds": 3})
        script = self.runner.build_script(job)
        self.assertIn("--num-model-seeds 3", script)

    def test_seed_flag(self):
        job = _FakeJob(params={"seed": 42})
        script = self.runner.build_script(job)
        self.assertIn("--seed 42", script)

    def test_pdb_output_format_generates_runner_yaml(self):
        job = _FakeJob(params={"output_format": "pdb"})
        script = self.runner.build_script(job)
        self.assertIn("structure_format: pdb", script)
        self.assertIn("--runner-yaml /work/input/output_settings.yaml", script)

    def test_cif_output_format_no_runner_yaml(self):
        job = _FakeJob(params={"output_format": "cif"})
        script = self.runner.build_script(job)
        self.assertNotIn("--runner-yaml", script)

    def test_openfold_cache_env(self):
        script = self.runner.build_script(_FakeJob())
        self.assertIn("-e OPENFOLD_CACHE=/cache", script)
