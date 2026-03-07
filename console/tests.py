from __future__ import annotations

from django.test import TestCase

from console.models import RunnerConfig


class RunnerConfigTests(TestCase):
    def test_default_field_values(self):
        config = RunnerConfig.get_config("test-runner")

        self.assertTrue(config.enabled)
        self.assertEqual(config.disabled_reason, "")
        self.assertEqual(config.image_uri, "")

    def test_image_override_persists(self):
        config = RunnerConfig.get_config("gpu-runner")
        config.image_uri = "myimage:latest"
        config.save()

        reloaded = RunnerConfig.objects.get(runner_key="gpu-runner")
        self.assertEqual(reloaded.image_uri, "myimage:latest")
