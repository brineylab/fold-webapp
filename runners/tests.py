"""Tests for runners (Phase 5: config-aware build_script)."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import PropertyMock

from django.test import TestCase

from console.models import RunnerConfig
from runners import get_runner


class _FakeJob:
    """Lightweight job stand-in for build_script tests."""

    def __init__(self, job_id="00000000-0000-0000-0000-000000000001", params=None):
        self.id = job_id
        self.params = params or {}
        from pathlib import Path
        self.workdir = Path("/tmp/test-job")
        self.host_workdir = Path("/tmp/test-job")


class TestBoltzRunnerBuildScript(TestCase):
    """BoltzRunner.build_script uses RunnerConfig for SLURM directives and image."""

    def setUp(self):
        self.runner = get_runner("boltz-2")

    def test_without_config(self):
        job = _FakeJob()
        script = self.runner.build_script(job)
        self.assertIn("#!/bin/bash", script)
        self.assertIn("#SBATCH --job-name=boltz-", script)
        self.assertNotIn("--partition", script)

    def test_with_config_directives(self):
        config = RunnerConfig(
            runner_key="boltz-2",
            partition="gpu",
            gpus=2,
            cpus=8,
            mem_gb=64,
            time_limit="02:00:00",
        )
        job = _FakeJob()
        script = self.runner.build_script(job, config=config)
        self.assertIn("#SBATCH --partition=gpu", script)
        self.assertIn("#SBATCH --gres=gpu:2", script)
        self.assertIn("#SBATCH --cpus-per-task=8", script)
        self.assertIn("#SBATCH --mem=64G", script)
        self.assertIn("#SBATCH --time=02:00:00", script)

    def test_config_image_override(self):
        config = RunnerConfig(
            runner_key="boltz-2",
            image_uri="custom-boltz:v2",
        )
        job = _FakeJob()
        script = self.runner.build_script(job, config=config)
        self.assertIn("custom-boltz:v2", script)
        # Should NOT contain the default image from settings
        from django.conf import settings
        if settings.BOLTZ_IMAGE != "custom-boltz:v2":
            self.assertNotIn(settings.BOLTZ_IMAGE, script)

    def test_config_empty_image_falls_back_to_settings(self):
        config = RunnerConfig(runner_key="boltz-2", image_uri="")
        job = _FakeJob()
        script = self.runner.build_script(job, config=config)
        from django.conf import settings
        self.assertIn(settings.BOLTZ_IMAGE, script)

    def test_params_flags_still_work(self):
        job = _FakeJob(params={
            "use_msa_server": True,
            "output_format": "pdb",
            "recycling_steps": 5,
        })
        script = self.runner.build_script(job)
        self.assertIn("--use_msa_server", script)
        self.assertIn("--output_format pdb", script)
        self.assertIn("--recycling_steps 5", script)

    def test_unused_input_path_removed(self):
        """The old unused input_path variable should no longer exist."""
        import inspect
        source = inspect.getsource(self.runner.build_script)
        self.assertNotIn("input_path", source)


class TestLigandMPNNRunnerBuildScript(TestCase):
    """LigandMPNNRunner.build_script generates correct scripts for both model variants."""

    def setUp(self):
        self.runner = get_runner("ligandmpnn")

    def test_without_config(self):
        job = _FakeJob(params={"model_variant": "protein_mpnn", "noise_level": "v_48_020"})
        script = self.runner.build_script(job)
        self.assertIn("#!/bin/bash", script)
        self.assertIn("#SBATCH --job-name=ligandmpnn-", script)
        self.assertNotIn("--partition", script)

    def test_with_config_directives(self):
        config = RunnerConfig(
            runner_key="ligandmpnn",
            partition="gpu",
            gpus=1,
            cpus=4,
            mem_gb=32,
            time_limit="01:00:00",
        )
        job = _FakeJob(params={"model_variant": "protein_mpnn", "noise_level": "v_48_020"})
        script = self.runner.build_script(job, config=config)
        self.assertIn("#SBATCH --partition=gpu", script)
        self.assertIn("#SBATCH --gres=gpu:1", script)
        self.assertIn("#SBATCH --cpus-per-task=4", script)
        self.assertIn("#SBATCH --mem=32G", script)
        self.assertIn("#SBATCH --time=01:00:00", script)

    def test_config_image_override(self):
        config = RunnerConfig(
            runner_key="ligandmpnn",
            image_uri="custom-ligandmpnn:v1",
        )
        job = _FakeJob(params={"model_variant": "protein_mpnn", "noise_level": "v_48_020"})
        script = self.runner.build_script(job, config=config)
        self.assertIn("custom-ligandmpnn:v1", script)

    def test_protein_mpnn_variant(self):
        job = _FakeJob(params={"model_variant": "protein_mpnn", "noise_level": "v_48_020"})
        script = self.runner.build_script(job)
        self.assertIn("--model_type protein_mpnn", script)
        self.assertIn("--checkpoint_protein_mpnn /app/model_params/proteinmpnn_v_48_020.pt", script)

    def test_ligand_mpnn_variant(self):
        job = _FakeJob(params={"model_variant": "ligand_mpnn", "noise_level": "v_32_010_25"})
        script = self.runner.build_script(job)
        self.assertIn("--model_type ligand_mpnn", script)
        self.assertIn("--checkpoint_ligand_mpnn /app/model_params/ligandmpnn_v_32_010_25.pt", script)

    def test_params_flags(self):
        job = _FakeJob(params={
            "model_variant": "protein_mpnn",
            "noise_level": "v_48_020",
            "temperature": 0.1,
            "num_sequences": 8,
            "seed": 42,
            "chains_to_design": "A,B",
            "fixed_residues": "1 2 3 4",
        })
        script = self.runner.build_script(job)
        self.assertIn('--sampling_temp "0.1"', script)
        self.assertIn("--number_of_batches 8", script)
        self.assertIn("--seed 42", script)
        self.assertIn('--chains_to_design "A,B"', script)
        self.assertIn('--fixed_positions "1 2 3 4"', script)


class TestStubRunnersBuildScript(TestCase):
    """Stub runners accept config parameter."""

    def test_alphafold_accepts_config(self):
        runner = get_runner("alphafold3")
        config = RunnerConfig(
            runner_key="alphafold3",
            partition="cpu",
            mem_gb=32,
        )
        job = _FakeJob()
        script = runner.build_script(job, config=config)
        self.assertIn("#SBATCH --partition=cpu", script)
        self.assertIn("#SBATCH --mem=32G", script)

    def test_chai_accepts_config(self):
        runner = get_runner("chai-1")
        config = RunnerConfig(
            runner_key="chai-1",
            gpus=1,
            time_limit="01:00:00",
        )
        job = _FakeJob()
        script = runner.build_script(job, config=config)
        self.assertIn("#SBATCH --gres=gpu:1", script)
        self.assertIn("#SBATCH --time=01:00:00", script)

    def test_stubs_work_without_config(self):
        for key in ("alphafold3", "chai-1"):
            runner = get_runner(key)
            job = _FakeJob()
            script = runner.build_script(job)
            self.assertIn("#!/bin/bash", script)


class TestBindCraftRunnerBuildScript(TestCase):
    """BindCraftRunner.build_script generates correct scripts."""

    def setUp(self):
        self.runner = get_runner("bindcraft")

    def test_without_config(self):
        job = _FakeJob()
        script = self.runner.build_script(job)
        self.assertIn("#!/bin/bash", script)
        self.assertIn("#SBATCH --job-name=bindcraft-", script)
        self.assertNotIn("--partition", script)

    def test_with_config_directives(self):
        config = RunnerConfig(
            runner_key="bindcraft",
            partition="gpu",
            gpus=2,
            cpus=8,
            mem_gb=64,
            time_limit="08:00:00",
        )
        job = _FakeJob()
        script = self.runner.build_script(job, config=config)
        self.assertIn("#SBATCH --partition=gpu", script)
        self.assertIn("#SBATCH --gres=gpu:2", script)
        self.assertIn("#SBATCH --cpus-per-task=8", script)
        self.assertIn("#SBATCH --mem=64G", script)
        self.assertIn("#SBATCH --time=08:00:00", script)

    def test_config_image_override(self):
        config = RunnerConfig(
            runner_key="bindcraft",
            image_uri="custom-bindcraft:v1",
        )
        job = _FakeJob()
        script = self.runner.build_script(job, config=config)
        self.assertIn("custom-bindcraft:v1", script)

    def test_config_empty_image_falls_back_to_settings(self):
        config = RunnerConfig(runner_key="bindcraft", image_uri="")
        job = _FakeJob()
        script = self.runner.build_script(job, config=config)
        from django.conf import settings
        self.assertIn(settings.BINDCRAFT_IMAGE, script)

    def test_always_has_settings_flag(self):
        job = _FakeJob()
        script = self.runner.build_script(job)
        self.assertIn("--settings /work/input/target_settings.json", script)

    def test_custom_filters_flag(self):
        job = _FakeJob(params={"has_custom_filters": True})
        script = self.runner.build_script(job)
        self.assertIn("--filters /work/input/filters.json", script)

    def test_no_filters_flag_without_custom(self):
        job = _FakeJob(params={})
        script = self.runner.build_script(job)
        self.assertNotIn("--filters", script)

    def test_custom_advanced_flag(self):
        job = _FakeJob(params={"has_custom_advanced": True})
        script = self.runner.build_script(job)
        self.assertIn("--advanced /work/input/advanced.json", script)

    def test_no_advanced_flag_without_custom(self):
        job = _FakeJob(params={})
        script = self.runner.build_script(job)
        self.assertNotIn("--advanced", script)

    def test_both_custom_configs(self):
        job = _FakeJob(params={
            "has_custom_filters": True,
            "has_custom_advanced": True,
        })
        script = self.runner.build_script(job)
        self.assertIn("--settings /work/input/target_settings.json", script)
        self.assertIn("--filters /work/input/filters.json", script)
        self.assertIn("--advanced /work/input/advanced.json", script)


class TestRFdiffusionRunnerBuildScript(TestCase):
    """RFdiffusionRunner.build_script generates correct scripts for all modes."""

    def setUp(self):
        self.runner = get_runner("rfdiffusion")

    def test_without_config(self):
        job = _FakeJob(params={"mode": "unconditional", "contigs": "[100-200]"})
        script = self.runner.build_script(job)
        self.assertIn("#!/bin/bash", script)
        self.assertIn("#SBATCH --job-name=rfdiffusion-", script)
        self.assertNotIn("--partition", script)

    def test_with_config_directives(self):
        config = RunnerConfig(
            runner_key="rfdiffusion",
            partition="gpu",
            gpus=1,
            cpus=4,
            mem_gb=32,
            time_limit="02:00:00",
        )
        job = _FakeJob(params={"mode": "unconditional", "contigs": "[100-200]"})
        script = self.runner.build_script(job, config=config)
        self.assertIn("#SBATCH --partition=gpu", script)
        self.assertIn("#SBATCH --gres=gpu:1", script)
        self.assertIn("#SBATCH --cpus-per-task=4", script)
        self.assertIn("#SBATCH --mem=32G", script)
        self.assertIn("#SBATCH --time=02:00:00", script)

    def test_config_image_override(self):
        config = RunnerConfig(
            runner_key="rfdiffusion",
            image_uri="custom-rfdiffusion:v1",
        )
        job = _FakeJob(params={"mode": "unconditional", "contigs": "[100-200]"})
        script = self.runner.build_script(job, config=config)
        self.assertIn("custom-rfdiffusion:v1", script)

    def test_config_empty_image_falls_back_to_settings(self):
        config = RunnerConfig(runner_key="rfdiffusion", image_uri="")
        job = _FakeJob(params={"mode": "unconditional", "contigs": "[100-200]"})
        script = self.runner.build_script(job, config=config)
        from django.conf import settings
        self.assertIn(settings.RFDIFFUSION_IMAGE, script)

    def test_unconditional_mode(self):
        job = _FakeJob(params={
            "mode": "unconditional",
            "num_designs": 10,
            "timesteps": 50,
            "contigs": "[100-200]",
        })
        script = self.runner.build_script(job)
        self.assertIn("inference.num_designs=10", script)
        self.assertIn("diffuser.T=50", script)
        self.assertIn("contigmap.contigs=[100-200]", script)
        self.assertIn("--config-name base", script)

    def test_binder_mode(self):
        job = _FakeJob(params={
            "mode": "binder",
            "num_designs": 5,
            "timesteps": 50,
            "contigs": "[A1-1000/0 70-100]",
            "hotspot_residues": "A30,A33,A34",
        })
        script = self.runner.build_script(job)
        self.assertIn("inference.input_pdb=/work/input/target.pdb", script)
        self.assertIn("contigmap.contigs=[A1-1000/0 70-100]", script)
        self.assertIn("ppi.hotspot_res=[A30,A33,A34]", script)
        self.assertIn("inference.num_designs=5", script)

    def test_binder_mode_no_hotspot(self):
        job = _FakeJob(params={
            "mode": "binder",
            "contigs": "[A1-1000/0 70-100]",
        })
        script = self.runner.build_script(job)
        self.assertNotIn("hotspot_res", script)

    def test_motif_mode(self):
        job = _FakeJob(params={
            "mode": "motif",
            "contigs": "[10-40/A163-181/10-40]",
        })
        script = self.runner.build_script(job)
        self.assertIn("inference.input_pdb=/work/input/input.pdb", script)
        self.assertIn("contigmap.contigs=[10-40/A163-181/10-40]", script)
        self.assertNotIn("partial_T", script)

    def test_partial_diffusion_mode(self):
        job = _FakeJob(params={
            "mode": "partial",
            "timesteps": 50,
            "contigs": "[A1-100]",
            "partial_T": 20,
        })
        script = self.runner.build_script(job)
        self.assertIn("inference.input_pdb=/work/input/input.pdb", script)
        self.assertIn("diffuser.partial_T=20", script)

    def test_symmetric_mode(self):
        job = _FakeJob(params={
            "mode": "symmetric",
            "symmetry_type": "cyclic",
            "symmetry_order": 3,
            "contigs": "[100-100]",
        })
        script = self.runner.build_script(job)
        self.assertIn("--config-name symmetry", script)
        self.assertIn("inference.symmetry=cyclic", script)
        self.assertIn("inference.symmetry_order=3", script)
        self.assertNotIn("inference.input_pdb", script)

    def test_symmetric_dihedral(self):
        job = _FakeJob(params={
            "mode": "symmetric",
            "symmetry_type": "dihedral",
            "symmetry_order": 4,
            "contigs": "[80-80]",
        })
        script = self.runner.build_script(job)
        self.assertIn("inference.symmetry=dihedral", script)
        self.assertIn("inference.symmetry_order=4", script)

    def test_default_params(self):
        """Runner uses defaults when params are empty."""
        job = _FakeJob(params={})
        script = self.runner.build_script(job)
        self.assertIn("inference.num_designs=10", script)
        self.assertIn("diffuser.T=50", script)
        self.assertIn("--config-name base", script)
