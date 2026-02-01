"""Tests for jobs app (Phase 2: service-layer validation ownership)."""
from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase

from jobs.services import create_and_submit_job


class TestCreateAndSubmitJobValidation(TestCase):
    """Defense-in-depth input checks in create_and_submit_job."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="testpass"
        )

    @patch("jobs.services.slurm")
    def test_rejects_no_sequences_and_no_files(self, mock_slurm):
        """Should reject when both sequences and files are empty."""
        with self.assertRaises(ValidationError) as ctx:
            create_and_submit_job(
                owner=self.user,
                runner_key="boltz-2",
                sequences="",
                params={},
                model_key="boltz2",
                input_payload={"sequences": "", "params": {}, "files": {}},
            )
        self.assertIn("No input provided", str(ctx.exception))

    @patch("jobs.services.slurm")
    def test_rejects_no_sequences_and_no_input_payload(self, mock_slurm):
        """Should reject when sequences is empty and input_payload is None."""
        with self.assertRaises(ValidationError):
            create_and_submit_job(
                owner=self.user,
                runner_key="boltz-2",
                sequences="",
                params={},
                model_key="boltz2",
                input_payload=None,
            )

    @patch("jobs.services.slurm")
    def test_accepts_sequences_without_files(self, mock_slurm):
        """Should accept when sequences is provided even without files."""
        mock_slurm.submit.return_value = "FAKE-123"
        job = create_and_submit_job(
            owner=self.user,
            runner_key="boltz-2",
            sequences=">s\nMKTAYI",
            params={},
            model_key="boltz2",
            input_payload={"sequences": ">s\nMKTAYI", "params": {}, "files": {}},
        )
        self.assertEqual(job.sequences, ">s\nMKTAYI")

    @patch("jobs.services.slurm")
    def test_accepts_files_without_sequences(self, mock_slurm):
        """Should accept when files are indicated even without sequences.
        (Prepares for Phase 3 file-based models. Uses filenames-only
        in input_payload since the service layer stores it as JSON.)"""
        mock_slurm.submit.return_value = "FAKE-123"
        job = create_and_submit_job(
            owner=self.user,
            runner_key="boltz-2",
            sequences="",
            params={},
            model_key="boltz2",
            input_payload={
                "sequences": "",
                "params": {},
                "files": {"backbone.pdb": "uploaded"},
            },
        )
        self.assertEqual(job.sequences, "")

    @patch("jobs.services.slurm")
    def test_rejects_oversized_sequences(self, mock_slurm):
        """Should reject sequences exceeding MAX_SEQUENCE_CHARS."""
        with self.assertRaises(ValidationError) as ctx:
            create_and_submit_job(
                owner=self.user,
                runner_key="boltz-2",
                sequences="A" * 200_001,
                params={},
                model_key="boltz2",
            )
        self.assertIn("too large", str(ctx.exception))
