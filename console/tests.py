"""Tests for console app (Phase 5: RunnerConfig SLURM resources)."""
from __future__ import annotations

from django.test import TestCase

from console.models import RunnerConfig


class TestRunnerConfigResourceFields(TestCase):
    """RunnerConfig stores SLURM resource settings."""

    def test_default_field_values(self):
        config = RunnerConfig.get_config("test-runner")
        self.assertEqual(config.partition, "")
        self.assertEqual(config.gpus, 0)
        self.assertEqual(config.cpus, 1)
        self.assertEqual(config.mem_gb, 8)
        self.assertEqual(config.time_limit, "")
        self.assertEqual(config.image_uri, "")
        self.assertEqual(config.extra_env, {})
        self.assertEqual(config.extra_mounts, [])

    def test_resource_fields_persist(self):
        config = RunnerConfig.get_config("gpu-runner")
        config.partition = "gpu"
        config.gpus = 2
        config.cpus = 8
        config.mem_gb = 64
        config.time_limit = "04:00:00"
        config.image_uri = "myimage:latest"
        config.extra_env = {"CUDA_VISIBLE_DEVICES": "0,1"}
        config.extra_mounts = [{"source": "/data", "target": "/mnt/data"}]
        config.save()

        reloaded = RunnerConfig.objects.get(runner_key="gpu-runner")
        self.assertEqual(reloaded.partition, "gpu")
        self.assertEqual(reloaded.gpus, 2)
        self.assertEqual(reloaded.cpus, 8)
        self.assertEqual(reloaded.mem_gb, 64)
        self.assertEqual(reloaded.time_limit, "04:00:00")
        self.assertEqual(reloaded.image_uri, "myimage:latest")
        self.assertEqual(reloaded.extra_env, {"CUDA_VISIBLE_DEVICES": "0,1"})
        self.assertEqual(reloaded.extra_mounts, [{"source": "/data", "target": "/mnt/data"}])


class TestGetSlurmDirectives(TestCase):
    """RunnerConfig.get_slurm_directives generates correct SBATCH lines."""

    def test_empty_config_returns_empty_string(self):
        config = RunnerConfig.get_config("empty-runner")
        # defaults: partition="", gpus=0, cpus=1, mem_gb=8, time_limit=""
        # cpus=1 is skipped (only >1 emitted), gpus=0 is skipped
        # but mem_gb=8 should be included
        directives = config.get_slurm_directives()
        self.assertIn("#SBATCH --mem=8G", directives)
        self.assertNotIn("--partition", directives)
        self.assertNotIn("--gres", directives)
        self.assertNotIn("--cpus-per-task", directives)
        self.assertNotIn("--time", directives)

    def test_full_config(self):
        config = RunnerConfig(
            runner_key="full",
            partition="gpu",
            gpus=4,
            cpus=16,
            mem_gb=128,
            time_limit="08:00:00",
        )
        directives = config.get_slurm_directives()
        self.assertIn("#SBATCH --partition=gpu", directives)
        self.assertIn("#SBATCH --gres=gpu:4", directives)
        self.assertIn("#SBATCH --cpus-per-task=16", directives)
        self.assertIn("#SBATCH --mem=128G", directives)
        self.assertIn("#SBATCH --time=08:00:00", directives)

    def test_gpu_only(self):
        config = RunnerConfig(runner_key="gpu-only", gpus=1, cpus=1, mem_gb=0)
        directives = config.get_slurm_directives()
        self.assertIn("#SBATCH --gres=gpu:1", directives)
        self.assertNotIn("--cpus-per-task", directives)
        self.assertNotIn("--mem=", directives)

    def test_cpus_equal_one_skipped(self):
        config = RunnerConfig(runner_key="cpu1", cpus=1, gpus=0, mem_gb=0)
        directives = config.get_slurm_directives()
        self.assertNotIn("--cpus-per-task", directives)

    def test_cpus_greater_than_one_included(self):
        config = RunnerConfig(runner_key="cpu4", cpus=4, gpus=0, mem_gb=0)
        directives = config.get_slurm_directives()
        self.assertIn("#SBATCH --cpus-per-task=4", directives)

    def test_directives_are_newline_separated(self):
        config = RunnerConfig(
            runner_key="multi", partition="gpu", gpus=1, mem_gb=32
        )
        directives = config.get_slurm_directives()
        lines = directives.strip().split("\n")
        self.assertTrue(all(line.startswith("#SBATCH") for line in lines))
        self.assertTrue(len(lines) >= 3)
