"""Tests for jobs app (service-layer validation, workdir delegation, output presentation, input file upload)."""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from jobs.models import Job
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
# Defense-in-depth input checks
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
# Payload sanitization
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
# prepare_workdir
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
# Service calls prepare_workdir
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


# ---------------------------------------------------------------------------
# View-level tests (templates, model selection, page_title)
# ---------------------------------------------------------------------------


class TestJobSubmitViewModelSelection(TestCase):
    """job_submit view shows model selection page when no ?model= param."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="viewuser", password="testpass"
        )
        self.client.login(username="viewuser", password="testpass")

    def test_get_without_model_shows_selection_page(self):
        response = self.client.get("/jobs/new/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "jobs/select_model.html")
        self.assertIn("model_types", response.context)

    def test_get_with_model_shows_submit_form(self):
        response = self.client.get("/jobs/new/?model=boltz2")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "jobs/submit_boltz2.html")

    def test_get_with_invalid_model_returns_404(self):
        response = self.client.get("/jobs/new/?model=nonexistent")
        self.assertEqual(response.status_code, 404)

    def test_page_title_in_context(self):
        response = self.client.get("/jobs/new/?model=boltz2")
        self.assertEqual(response.context["page_title"], "New Boltz-2 Job")

    def test_selection_page_lists_boltz2(self):
        response = self.client.get("/jobs/new/")
        model_keys = [mt.key for mt in response.context["model_types"]]
        self.assertIn("boltz2", model_keys)


class TestSubmitBaseTemplate(TestCase):
    """Submit templates extend submit_base.html and include shared elements."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="tpluser", password="testpass"
        )
        self.client.login(username="tpluser", password="testpass")

    def test_boltz2_extends_submit_base(self):
        response = self.client.get("/jobs/new/?model=boltz2")
        self.assertTemplateUsed(response, "jobs/submit_base.html")
        self.assertTemplateUsed(response, "jobs/submit_boltz2.html")

    def test_submit_form_has_multipart_enctype(self):
        response = self.client.get("/jobs/new/?model=boltz2")
        self.assertContains(response, 'enctype="multipart/form-data"')

    def test_submit_form_has_hidden_model_field(self):
        response = self.client.get("/jobs/new/?model=boltz2")
        self.assertContains(response, 'name="model" value="boltz2"')


# ---------------------------------------------------------------------------
# Output presentation (view + template integration)
# ---------------------------------------------------------------------------


class TestJobDetailOutputContext(TestCase):
    """job_detail view uses model_type.get_output_context for structured output."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="detailuser", password="testpass"
        )
        self.client.login(username="detailuser", password="testpass")
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _create_job(self, model_key="boltz2"):
        from jobs.models import Job
        job = Job.objects.create(
            owner=self.user,
            runner="boltz-2",
            model_key=model_key,
            sequences=">s\nMKTAYI",
            status=Job.Status.COMPLETED,
        )
        return job

    def test_detail_view_provides_output_context_keys(self):
        """Detail view should include files, primary_files, aux_files in context."""
        job = self._create_job()
        # Patch workdir to our temp dir
        outdir = self.tmpdir / str(job.id) / "output"
        outdir.mkdir(parents=True)
        with override_settings(JOB_BASE_DIR=self.tmpdir):
            response = self.client.get(f"/jobs/{job.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("files", response.context)
        self.assertIn("primary_files", response.context)
        self.assertIn("aux_files", response.context)

    def test_detail_view_boltz2_classifies_pdb_as_primary(self):
        """Boltz-2 jobs should classify .pdb files as primary."""
        job = self._create_job(model_key="boltz2")
        outdir = self.tmpdir / str(job.id) / "output"
        outdir.mkdir(parents=True)
        (outdir / "model.pdb").write_text("ATOM 1")
        (outdir / "slurm-999.out").write_text("log output")
        with override_settings(JOB_BASE_DIR=self.tmpdir):
            response = self.client.get(f"/jobs/{job.id}/")
        primary_names = [f["name"] for f in response.context["primary_files"]]
        aux_names = [f["name"] for f in response.context["aux_files"]]
        self.assertIn("model.pdb", primary_names)
        self.assertIn("slurm-999.out", aux_names)

    def test_detail_view_unknown_model_key_falls_back(self):
        """Jobs with unrecognized model_key should fall back to default model type."""
        job = self._create_job(model_key="nonexistent_model")
        outdir = self.tmpdir / str(job.id) / "output"
        outdir.mkdir(parents=True)
        (outdir / "result.txt").write_text("data")
        with override_settings(JOB_BASE_DIR=self.tmpdir):
            response = self.client.get(f"/jobs/{job.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("files", response.context)
        # Default model type puts everything in files, not primary
        self.assertEqual(response.context["primary_files"], [])

    def test_detail_view_no_output_dir(self):
        """When output dir doesn't exist, files should be empty."""
        job = self._create_job()
        with override_settings(JOB_BASE_DIR=self.tmpdir):
            response = self.client.get(f"/jobs/{job.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["files"], [])


class TestJobDetailTemplateRendering(TestCase):
    """detail.html renders structured output sections correctly."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="tpldetailuser", password="testpass"
        )
        self.client.login(username="tpldetailuser", password="testpass")
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _create_job(self, model_key="boltz2"):
        from jobs.models import Job
        return Job.objects.create(
            owner=self.user,
            runner="boltz-2",
            model_key=model_key,
            sequences=">s\nMKTAYI",
            status=Job.Status.COMPLETED,
        )

    def test_primary_files_section_rendered(self):
        """When primary_files exist, the Results section should be rendered."""
        job = self._create_job()
        outdir = self.tmpdir / str(job.id) / "output"
        outdir.mkdir(parents=True)
        (outdir / "predicted.pdb").write_text("ATOM 1")
        with override_settings(JOB_BASE_DIR=self.tmpdir):
            response = self.client.get(f"/jobs/{job.id}/")
        self.assertContains(response, "Results")
        self.assertContains(response, "predicted.pdb")

    def test_aux_files_section_rendered(self):
        """When aux_files exist, the Logs & Auxiliary section should be rendered."""
        job = self._create_job()
        outdir = self.tmpdir / str(job.id) / "output"
        outdir.mkdir(parents=True)
        (outdir / "slurm-123.out").write_text("log")
        with override_settings(JOB_BASE_DIR=self.tmpdir):
            response = self.client.get(f"/jobs/{job.id}/")
        self.assertContains(response, "Logs &amp; Auxiliary")
        self.assertContains(response, "slurm-123.out")

    def test_no_files_message(self):
        """When no output files exist, show the 'no files' message."""
        job = self._create_job()
        with override_settings(JOB_BASE_DIR=self.tmpdir):
            response = self.client.get(f"/jobs/{job.id}/")
        self.assertContains(response, "No output files found yet")

    def test_flat_file_list_for_base_model_type(self):
        """Jobs with unrecognized model_key (no primary/aux split) show flat file list."""
        job = self._create_job(model_key="unknown_model")
        outdir = self.tmpdir / str(job.id) / "output"
        outdir.mkdir(parents=True)
        (outdir / "output.txt").write_text("result data")
        with override_settings(JOB_BASE_DIR=self.tmpdir):
            response = self.client.get(f"/jobs/{job.id}/")
        self.assertContains(response, "output.txt")
        # Should NOT show "Results" or "Logs & Auxiliary" headers
        self.assertNotContains(response, "Results")
        self.assertNotContains(response, "Logs &amp; Auxiliary")

    def test_file_sizes_displayed(self):
        """Output files should have their size displayed."""
        job = self._create_job()
        outdir = self.tmpdir / str(job.id) / "output"
        outdir.mkdir(parents=True)
        (outdir / "model.pdb").write_text("A" * 1024)
        with override_settings(JOB_BASE_DIR=self.tmpdir):
            response = self.client.get(f"/jobs/{job.id}/")
        # Django's filesizeformat should render something like "1.0 KB"
        self.assertContains(response, "KB")

    def test_download_links_present(self):
        """Each file should have a download link."""
        job = self._create_job()
        outdir = self.tmpdir / str(job.id) / "output"
        outdir.mkdir(parents=True)
        (outdir / "model.pdb").write_text("ATOM")
        with override_settings(JOB_BASE_DIR=self.tmpdir):
            response = self.client.get(f"/jobs/{job.id}/")
        self.assertContains(response, "Download")
        self.assertContains(response, f"/jobs/{job.id}/download/model.pdb")


# ---------------------------------------------------------------------------
# Input file upload (view integration)
# ---------------------------------------------------------------------------


class TestInputFileSubmission(TestCase):
    """Submitting a job with an input file via the view."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="fileuser", password="testpass"
        )
        self.client.login(username="fileuser", password="testpass")

    @patch("jobs.services.slurm")
    def test_input_file_creates_job(self, mock_slurm):
        mock_slurm.submit.return_value = "FAKE-FILE"
        yaml_content = b"version: 2\nsequences:\n  - protein:\n      id: A\n"
        input_file = SimpleUploadedFile(
            "complex.yaml", yaml_content, content_type="application/x-yaml"
        )
        response = self.client.post(
            "/jobs/new/?model=boltz2",
            {"model": "boltz2", "input_file": input_file},
        )
        self.assertEqual(response.status_code, 302)  # redirect to detail
        job = Job.objects.get(owner=self.user)
        # sequences should be empty since file replaces textarea
        self.assertEqual(job.sequences, "")
        # input_payload should record the filename
        self.assertIn("complex.yaml", job.input_payload.get("files", []))

    @patch("jobs.services.slurm")
    def test_sequences_submission_still_works(self, mock_slurm):
        mock_slurm.submit.return_value = "FAKE-SEQ"
        response = self.client.post(
            "/jobs/new/?model=boltz2",
            {"model": "boltz2", "sequences": ">s\nMKTAYI"},
        )
        self.assertEqual(response.status_code, 302)
        job = Job.objects.get(owner=self.user)
        self.assertEqual(job.sequences, ">s\nMKTAYI")

    def test_no_sequences_or_file_shows_error(self):
        """Submitting without sequences and without input file should fail."""
        response = self.client.post(
            "/jobs/new/?model=boltz2",
            {"model": "boltz2"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)

    @patch("jobs.services.slurm")
    def test_input_file_written_to_workdir(self, mock_slurm):
        """The uploaded file should be written verbatim to the job workdir."""
        mock_slurm.submit.return_value = "FAKE-WD"
        yaml_content = b"version: 2\ndata: test\n"
        input_file = SimpleUploadedFile(
            "input.yaml", yaml_content, content_type="application/x-yaml"
        )
        response = self.client.post(
            "/jobs/new/?model=boltz2",
            {"model": "boltz2", "input_file": input_file},
        )
        self.assertEqual(response.status_code, 302)
        job = Job.objects.get(owner=self.user)
        written = job.workdir / "input" / "input.yaml"
        self.assertTrue(written.exists())
        self.assertEqual(written.read_bytes(), yaml_content)


class TestBoltz2TemplateInputFileField(TestCase):
    """Boltz-2 submit template includes the input file field."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="tplfileuser", password="testpass"
        )
        self.client.login(username="tplfileuser", password="testpass")

    def test_input_file_field_present(self):
        response = self.client.get("/jobs/new/?model=boltz2")
        self.assertContains(response, "input_file")
        self.assertContains(response, "Input file")

    def test_batch_file_field_absent(self):
        response = self.client.get("/jobs/new/?model=boltz2")
        self.assertNotContains(response, "batch_file")

    def test_config_file_field_absent(self):
        response = self.client.get("/jobs/new/?model=boltz2")
        self.assertNotContains(response, "config_file")
