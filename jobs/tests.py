"""Tests for jobs app (Phases 2-3: service-layer validation and workdir delegation)."""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from jobs.services import create_and_submit_job, _sanitize_payload_for_storage
from model_types import get_model_type
from model_types.base import BaseModelType, InputPayload


# ---------------------------------------------------------------------------
# Helper: a minimal concrete ModelType for testing
# ---------------------------------------------------------------------------


class _StubModelType(BaseModelType):
    key = "stub"
    name = "Stub"

    def validate(self, cleaned_data):
        pass

    def normalize_inputs(self, cleaned_data):
        return {"sequences": "", "params": {}, "files": {}}

    def resolve_runner_key(self, cleaned_data):
        return "boltz-2"


# ---------------------------------------------------------------------------
# Phase 2: Defense-in-depth input checks
# ---------------------------------------------------------------------------


class TestCreateAndSubmitJobValidation(TestCase):
    """Defense-in-depth input checks in create_and_submit_job."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="testpass"
        )
        self.model_type = get_model_type("boltz2")

    @patch("jobs.services.slurm")
    def test_rejects_no_sequences_and_no_files(self, mock_slurm):
        """Should reject when both sequences and files are empty."""
        with self.assertRaises(ValidationError) as ctx:
            create_and_submit_job(
                owner=self.user,
                model_type=self.model_type,
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
                model_type=self.model_type,
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
            model_type=self.model_type,
            runner_key="boltz-2",
            sequences=">s\nMKTAYI",
            params={},
            model_key="boltz2",
            input_payload={"sequences": ">s\nMKTAYI", "params": {}, "files": {}},
        )
        self.assertEqual(job.sequences, ">s\nMKTAYI")

    @patch("jobs.services.slurm")
    def test_accepts_files_without_sequences(self, mock_slurm):
        """Should accept when files are provided without sequences."""
        mock_slurm.submit.return_value = "FAKE-123"
        job = create_and_submit_job(
            owner=self.user,
            model_type=_StubModelType(),
            runner_key="boltz-2",
            sequences="",
            params={},
            model_key="stub",
            input_payload={
                "sequences": "",
                "params": {},
                "files": {"backbone.pdb": b"ATOM ..."},
            },
        )
        self.assertEqual(job.sequences, "")

    @patch("jobs.services.slurm")
    def test_rejects_oversized_sequences(self, mock_slurm):
        """Should reject sequences exceeding MAX_SEQUENCE_CHARS."""
        with self.assertRaises(ValidationError) as ctx:
            create_and_submit_job(
                owner=self.user,
                model_type=self.model_type,
                runner_key="boltz-2",
                sequences="A" * 200_001,
                params={},
                model_key="boltz2",
            )
        self.assertIn("too large", str(ctx.exception))

    @patch("jobs.services.slurm")
    def test_sequences_defaults_to_empty(self, mock_slurm):
        """sequences parameter should default to empty string."""
        mock_slurm.submit.return_value = "FAKE-123"
        job = create_and_submit_job(
            owner=self.user,
            model_type=_StubModelType(),
            runner_key="boltz-2",
            params={},
            model_key="stub",
            input_payload={
                "sequences": "",
                "params": {},
                "files": {"backbone.pdb": b"ATOM ..."},
            },
        )
        self.assertEqual(job.sequences, "")


# ---------------------------------------------------------------------------
# Phase 3: payload sanitization
# ---------------------------------------------------------------------------


class TestSanitizePayloadForStorage(TestCase):
    """_sanitize_payload_for_storage strips binary content for DB storage."""

    def test_strips_binary_file_content(self):
        payload = {
            "sequences": ">s\nMKTAYI",
            "params": {"temperature": 0.1},
            "files": {"backbone.pdb": b"ATOM ...", "constraints.json": b"{}"},
        }
        result = _sanitize_payload_for_storage(payload)
        self.assertEqual(result["sequences"], ">s\nMKTAYI")
        self.assertEqual(result["params"], {"temperature": 0.1})
        # files should be a list of filenames, not a dict of bytes
        self.assertIsInstance(result["files"], list)
        self.assertEqual(sorted(result["files"]), ["backbone.pdb", "constraints.json"])

    def test_handles_empty_files(self):
        payload = {"sequences": ">s\nMKTAYI", "params": {}, "files": {}}
        result = _sanitize_payload_for_storage(payload)
        self.assertEqual(result["files"], [])

    def test_handles_none_payload(self):
        result = _sanitize_payload_for_storage(None)
        self.assertEqual(result, {})

    def test_handles_empty_payload(self):
        # Empty dict is falsy, treated same as None
        result = _sanitize_payload_for_storage({})
        self.assertEqual(result, {})


# ---------------------------------------------------------------------------
# Phase 3: prepare_workdir
# ---------------------------------------------------------------------------


class TestPrepareWorkdirDefault(TestCase):
    """BaseModelType.prepare_workdir default implementation."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _make_fake_job(self):
        """Create a lightweight object with a workdir property."""
        class FakeJob:
            workdir = self.tmpdir / "test-job"
        return FakeJob()

    def test_creates_input_and_output_dirs(self):
        mt = _StubModelType()
        job = self._make_fake_job()
        mt.prepare_workdir(job, {"sequences": "", "params": {}, "files": {}})
        self.assertTrue((job.workdir / "input").is_dir())
        self.assertTrue((job.workdir / "output").is_dir())

    def test_writes_sequences_fasta_when_non_empty(self):
        mt = _StubModelType()
        job = self._make_fake_job()
        mt.prepare_workdir(
            job,
            {"sequences": ">s\nMKTAYI", "params": {}, "files": {}},
        )
        fasta = job.workdir / "input" / "sequences.fasta"
        self.assertTrue(fasta.exists())
        self.assertEqual(fasta.read_text(), ">s\nMKTAYI")

    def test_skips_sequences_fasta_when_empty(self):
        mt = _StubModelType()
        job = self._make_fake_job()
        mt.prepare_workdir(job, {"sequences": "", "params": {}, "files": {}})
        fasta = job.workdir / "input" / "sequences.fasta"
        self.assertFalse(fasta.exists())

    def test_writes_uploaded_files(self):
        mt = _StubModelType()
        job = self._make_fake_job()
        mt.prepare_workdir(
            job,
            {
                "sequences": "",
                "params": {},
                "files": {
                    "backbone.pdb": b"ATOM 1 N ALA",
                    "constraints.json": b'{"fixed": []}',
                },
            },
        )
        pdb = job.workdir / "input" / "backbone.pdb"
        self.assertTrue(pdb.exists())
        self.assertEqual(pdb.read_bytes(), b"ATOM 1 N ALA")
        cst = job.workdir / "input" / "constraints.json"
        self.assertTrue(cst.exists())
        self.assertEqual(cst.read_bytes(), b'{"fixed": []}')

    def test_writes_both_sequences_and_files(self):
        mt = _StubModelType()
        job = self._make_fake_job()
        mt.prepare_workdir(
            job,
            {
                "sequences": ">chain\nACDEFG",
                "params": {},
                "files": {"extra.txt": b"hello"},
            },
        )
        self.assertTrue((job.workdir / "input" / "sequences.fasta").exists())
        self.assertTrue((job.workdir / "input" / "extra.txt").exists())


class TestPrepareWorkdirOverride(TestCase):
    """Subclasses can override prepare_workdir for custom layouts."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_override_custom_layout(self):
        class CustomModelType(BaseModelType):
            key = "custom"
            name = "Custom"

            def validate(self, cleaned_data):
                pass

            def normalize_inputs(self, cleaned_data):
                return {"sequences": "", "params": {}, "files": {}}

            def resolve_runner_key(self, cleaned_data):
                return "test"

            def prepare_workdir(self, job, input_payload):
                workdir = job.workdir
                (workdir / "structures").mkdir(parents=True, exist_ok=True)
                for fname, content in input_payload.get("files", {}).items():
                    (workdir / "structures" / fname).write_bytes(content)

        class FakeJob:
            workdir = self.tmpdir / "custom-job"

        mt = CustomModelType()
        job = FakeJob()
        mt.prepare_workdir(
            job,
            {"sequences": "", "params": {}, "files": {"input.pdb": b"PDB DATA"}},
        )
        self.assertTrue((job.workdir / "structures" / "input.pdb").exists())
        # Default dirs should NOT exist since we fully overrode
        self.assertFalse((job.workdir / "input").exists())
        self.assertFalse((job.workdir / "output").exists())


# ---------------------------------------------------------------------------
# Phase 3: service calls prepare_workdir
# ---------------------------------------------------------------------------


class TestServiceCallsPrepareWorkdir(TestCase):
    """create_and_submit_job delegates workdir setup to model_type.prepare_workdir."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser2", password="testpass"
        )

    @patch("jobs.services.slurm")
    def test_calls_prepare_workdir(self, mock_slurm):
        """The service should call model_type.prepare_workdir, not do its own layout."""
        mock_slurm.submit.return_value = "FAKE-456"

        class SpyModelType(_StubModelType):
            prepare_called = False
            prepare_payload = None

            def prepare_workdir(self, job, input_payload):
                SpyModelType.prepare_called = True
                SpyModelType.prepare_payload = input_payload
                super().prepare_workdir(job, input_payload)

        mt = SpyModelType()
        payload = {"sequences": ">s\nMKTAYI", "params": {}, "files": {}}
        create_and_submit_job(
            owner=self.user,
            model_type=mt,
            runner_key="boltz-2",
            sequences=">s\nMKTAYI",
            params={},
            model_key="stub",
            input_payload=payload,
        )
        self.assertTrue(SpyModelType.prepare_called)
        self.assertEqual(SpyModelType.prepare_payload, payload)

    @patch("jobs.services.slurm")
    def test_stored_payload_has_filenames_not_bytes(self, mock_slurm):
        """input_payload stored in DB should have filename list, not binary content."""
        mock_slurm.submit.return_value = "FAKE-789"
        job = create_and_submit_job(
            owner=self.user,
            model_type=_StubModelType(),
            runner_key="boltz-2",
            sequences="",
            params={},
            model_key="stub",
            input_payload={
                "sequences": "",
                "params": {},
                "files": {"backbone.pdb": b"ATOM ..."},
            },
        )
        stored = job.input_payload
        self.assertIsInstance(stored["files"], list)
        self.assertEqual(stored["files"], ["backbone.pdb"])
