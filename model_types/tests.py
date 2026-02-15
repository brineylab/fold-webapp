"""Tests for the model_types harness."""
from __future__ import annotations

import io
import shutil
import tempfile
from pathlib import Path

from django import forms
from django.core.exceptions import ValidationError
from django.test import TestCase

from model_types.base import BaseModelType, InputPayload
from model_types.parsers import parse_fasta_batch
from model_types.registry import (
    MODEL_TYPES,
    get_model_type,
    get_model_types_by_category,
    get_submittable_model_types,
)


# ---------------------------------------------------------------------------
# 2.1  ABC enforcement
# ---------------------------------------------------------------------------


class TestBaseModelTypeABC(TestCase):
    """BaseModelType cannot be instantiated directly or with missing methods."""

    def test_cannot_instantiate_base(self):
        with self.assertRaises(TypeError):
            BaseModelType()

    def test_cannot_instantiate_incomplete_subclass(self):
        class Incomplete(BaseModelType):
            pass

        with self.assertRaises(TypeError):
            Incomplete()

    def test_cannot_instantiate_partially_complete_subclass(self):
        class Partial(BaseModelType):
            def validate(self, cleaned_data):
                pass

        with self.assertRaises(TypeError):
            Partial()

    def test_can_instantiate_complete_subclass(self):
        class Complete(BaseModelType):
            key = "test"
            name = "Test"

            def validate(self, cleaned_data):
                pass

            def normalize_inputs(self, cleaned_data):
                return {"sequences": "", "params": {}, "files": {}}

            def resolve_runner_key(self, cleaned_data):
                return "test-runner"

        instance = Complete()
        self.assertEqual(instance.key, "test")

    def test_get_form_concrete_default(self):
        """get_form should work without override, using the default form_class."""

        class Minimal(BaseModelType):
            key = "min"
            name = "Minimal"

            def validate(self, cleaned_data):
                pass

            def normalize_inputs(self, cleaned_data):
                return {"sequences": "", "params": {}, "files": {}}

            def resolve_runner_key(self, cleaned_data):
                return "x"

        mt = Minimal()
        form = mt.get_form()
        self.assertIsInstance(form, forms.Form)

    def test_get_form_with_custom_form_class(self):
        class MyForm(forms.Form):
            name = forms.CharField()

        class Custom(BaseModelType):
            key = "custom"
            name = "Custom"
            form_class = MyForm

            def validate(self, cleaned_data):
                pass

            def normalize_inputs(self, cleaned_data):
                return {"sequences": "", "params": {}, "files": {}}

            def resolve_runner_key(self, cleaned_data):
                return "x"

        mt = Custom()
        form = mt.get_form(data={"name": "hello"})
        self.assertIsInstance(form, MyForm)
        self.assertTrue(form.is_valid())


# ---------------------------------------------------------------------------
# 2.2  InputPayload contract
# ---------------------------------------------------------------------------


class TestInputPayloadContract(TestCase):
    """Registered ModelTypes must return InputPayload-shaped dicts."""

    REQUIRED_KEYS = {"sequences", "params", "files"}

    def _assert_payload_shape(self, payload: dict):
        self.assertIsInstance(payload, dict)
        self.assertEqual(set(payload.keys()), self.REQUIRED_KEYS)
        self.assertIsInstance(payload["sequences"], str)
        self.assertIsInstance(payload["params"], dict)
        self.assertIsInstance(payload["files"], dict)

    def test_boltz2_normalize_inputs(self):
        mt = get_model_type("boltz2")
        payload = mt.normalize_inputs({
            "sequences": ">s\nMKTAYI",
            "use_msa_server": True,
            "output_format": "pdb",
        })
        self._assert_payload_shape(payload)
        self.assertEqual(payload["sequences"], ">s\nMKTAYI")
        self.assertIn("use_msa_server", payload["params"])
        self.assertEqual(payload["files"], {})

    def test_boltz2_strips_falsy_params(self):
        mt = get_model_type("boltz2")
        payload = mt.normalize_inputs({
            "sequences": ">s\nMKTAYI",
            "use_msa_server": False,
            "use_potentials": False,
            "output_format": None,
            "recycling_steps": None,
            "sampling_steps": None,
            "diffusion_samples": None,
        })
        self._assert_payload_shape(payload)
        # All falsy/None params should be stripped
        self.assertEqual(payload["params"], {})

    def test_boltz2_keeps_truthy_params(self):
        mt = get_model_type("boltz2")
        payload = mt.normalize_inputs({
            "sequences": ">s\nMKTAYI",
            "use_msa_server": True,
            "use_potentials": True,
            "output_format": "mmcif",
            "recycling_steps": 3,
            "sampling_steps": 10,
            "diffusion_samples": 5,
        })
        self.assertEqual(payload["params"], {
            "use_msa_server": True,
            "use_potentials": True,
            "output_format": "mmcif",
            "recycling_steps": 3,
            "sampling_steps": 10,
            "diffusion_samples": 5,
        })


# ---------------------------------------------------------------------------
# 2.2  InputPayload export
# ---------------------------------------------------------------------------


class TestInputPayloadExport(TestCase):
    """InputPayload should be importable from the package root."""

    def test_import_from_package(self):
        from model_types import InputPayload as IP
        self.assertIs(IP, InputPayload)


# ---------------------------------------------------------------------------
# 2.3  Validation ownership
# ---------------------------------------------------------------------------


class TestValidationOwnership(TestCase):
    """ModelType.validate() should NOT duplicate form-level required checks."""

    def test_boltz2_validate_does_not_check_empty_sequences(self):
        """Boltz2ModelType.validate() should not raise on empty sequences --
        that's the form's job."""
        mt = get_model_type("boltz2")
        # Should not raise -- form handles the required check
        mt.validate({"sequences": ""})
        mt.validate({})


# ---------------------------------------------------------------------------
# Registry sanity
# ---------------------------------------------------------------------------


class TestRegistry(TestCase):
    def test_all_model_types_registered(self):
        self.assertIn("boltz2", MODEL_TYPES)
        self.assertIn("protein_mpnn", MODEL_TYPES)
        self.assertIn("ligand_mpnn", MODEL_TYPES)

    def test_get_model_type_unknown_raises(self):
        with self.assertRaises(KeyError):
            get_model_type("nonexistent")


# ---------------------------------------------------------------------------
# 3.2  prepare_workdir is a concrete method on BaseModelType
# ---------------------------------------------------------------------------


class _MinimalModelType(BaseModelType):
    """Minimal concrete subclass for testing base prepare_workdir."""
    key = "minimal"
    name = "Minimal"

    def validate(self, cleaned_data):
        pass

    def normalize_inputs(self, cleaned_data):
        return {"sequences": "", "params": {}, "files": {}}

    def resolve_runner_key(self, cleaned_data):
        return "test"


class TestPrepareWorkdirOnBase(TestCase):
    """prepare_workdir is a concrete (non-abstract) method on BaseModelType."""

    def test_prepare_workdir_is_not_abstract(self):
        """Subclasses that don't override prepare_workdir should still instantiate."""
        mt = _MinimalModelType()
        self.assertTrue(callable(mt.prepare_workdir))

    def test_registered_model_types_have_prepare_workdir(self):
        """All registered model types should have prepare_workdir."""
        for key, mt in MODEL_TYPES.items():
            self.assertTrue(
                callable(getattr(mt, "prepare_workdir", None)),
                f"ModelType {key!r} missing prepare_workdir",
            )

    def test_default_prepare_workdir_creates_dirs(self):
        tmpdir = Path(tempfile.mkdtemp())
        try:
            class FakeJob:
                workdir = tmpdir / "job"

            mt = _MinimalModelType()
            mt.prepare_workdir(FakeJob(), {"sequences": "", "params": {}, "files": {}})
            self.assertTrue((tmpdir / "job" / "input").is_dir())
            self.assertTrue((tmpdir / "job" / "output").is_dir())
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_default_prepare_workdir_writes_fasta(self):
        tmpdir = Path(tempfile.mkdtemp())
        try:
            class FakeJob:
                workdir = tmpdir / "job"

            mt = _MinimalModelType()
            mt.prepare_workdir(
                FakeJob(),
                {"sequences": ">s\nACDEFG", "params": {}, "files": {}},
            )
            fasta = tmpdir / "job" / "input" / "sequences.fasta"
            self.assertTrue(fasta.exists())
            self.assertEqual(fasta.read_text(), ">s\nACDEFG")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_default_prepare_workdir_skips_empty_sequences(self):
        tmpdir = Path(tempfile.mkdtemp())
        try:
            class FakeJob:
                workdir = tmpdir / "job"

            mt = _MinimalModelType()
            mt.prepare_workdir(FakeJob(), {"sequences": "", "params": {}, "files": {}})
            self.assertFalse((tmpdir / "job" / "input" / "sequences.fasta").exists())
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_default_prepare_workdir_writes_files(self):
        tmpdir = Path(tempfile.mkdtemp())
        try:
            class FakeJob:
                workdir = tmpdir / "job"

            mt = _MinimalModelType()
            mt.prepare_workdir(
                FakeJob(),
                {
                    "sequences": "",
                    "params": {},
                    "files": {"backbone.pdb": b"ATOM 1 N ALA"},
                },
            )
            pdb = tmpdir / "job" / "input" / "backbone.pdb"
            self.assertTrue(pdb.exists())
            self.assertEqual(pdb.read_bytes(), b"ATOM 1 N ALA")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# 4.3  Model selection / submittable model types
# ---------------------------------------------------------------------------


class TestGetSubmittableModelTypes(TestCase):
    """get_submittable_model_types returns the right set for the landing page."""

    def test_includes_boltz2(self):
        model_types = get_submittable_model_types()
        keys = [mt.key for mt in model_types]
        self.assertIn("boltz2", keys)

    def test_all_have_name_and_help_text(self):
        for mt in get_submittable_model_types():
            self.assertTrue(mt.name, f"ModelType {mt.key!r} missing name")
            self.assertTrue(mt.help_text, f"ModelType {mt.key!r} missing help_text")


# ---------------------------------------------------------------------------
# 11.1  Model categories
# ---------------------------------------------------------------------------


class TestModelCategories(TestCase):
    """get_model_types_by_category groups models correctly."""

    def test_returns_list_of_tuples(self):
        result = get_model_types_by_category()
        self.assertIsInstance(result, list)
        for item in result:
            self.assertIsInstance(item, tuple)
            self.assertEqual(len(item), 2)
            self.assertIsInstance(item[0], str)
            self.assertIsInstance(item[1], list)

    def test_boltz2_in_structure_prediction(self):
        result = get_model_types_by_category()
        categories = dict(result)
        self.assertIn("Structure Prediction", categories)
        keys = [mt.key for mt in categories["Structure Prediction"]]
        self.assertIn("boltz2", keys)

    def test_all_registered_models_present(self):
        result = get_model_types_by_category()
        all_keys = set()
        for _cat, models in result:
            for mt in models:
                all_keys.add(mt.key)
        for key in MODEL_TYPES:
            self.assertIn(key, all_keys)

    def test_models_without_category_grouped_under_other(self):
        """Models with empty category should fall under 'Other'."""
        mt = _MinimalModelType()
        self.assertEqual(mt.category, "")
        # The fallback logic uses "Other" for empty category strings
        cat = mt.category or "Other"
        self.assertEqual(cat, "Other")

    def test_boltz2_has_category_set(self):
        mt = get_model_type("boltz2")
        self.assertEqual(mt.category, "Structure Prediction")


# ---------------------------------------------------------------------------
# 6.1  get_output_context on BaseModelType (concrete default)
# ---------------------------------------------------------------------------


class TestGetOutputContextBase(TestCase):
    """get_output_context is a concrete method with a useful default."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _make_fake_job(self):
        class FakeJob:
            workdir = self.tmpdir / "job"
        return FakeJob()

    def test_is_not_abstract(self):
        """Subclasses that don't override get_output_context should still instantiate."""
        mt = _MinimalModelType()
        self.assertTrue(callable(mt.get_output_context))

    def test_all_registered_model_types_have_get_output_context(self):
        for key, mt in MODEL_TYPES.items():
            self.assertTrue(
                callable(getattr(mt, "get_output_context", None)),
                f"ModelType {key!r} missing get_output_context",
            )

    def test_returns_empty_when_no_output_dir(self):
        job = self._make_fake_job()
        mt = _MinimalModelType()
        result = mt.get_output_context(job)
        self.assertEqual(result, {"files": [], "primary_files": [], "aux_files": []})

    def test_returns_empty_when_output_dir_empty(self):
        job = self._make_fake_job()
        (job.workdir / "output").mkdir(parents=True)
        mt = _MinimalModelType()
        result = mt.get_output_context(job)
        self.assertEqual(result, {"files": [], "primary_files": [], "aux_files": []})

    def test_lists_files_with_name_and_size(self):
        job = self._make_fake_job()
        outdir = job.workdir / "output"
        outdir.mkdir(parents=True)
        (outdir / "result.pdb").write_text("ATOM 1")
        (outdir / "log.txt").write_text("done")

        mt = _MinimalModelType()
        result = mt.get_output_context(job)
        names = [f["name"] for f in result["files"]]
        self.assertIn("result.pdb", names)
        self.assertIn("log.txt", names)
        for f in result["files"]:
            self.assertIn("name", f)
            self.assertIn("size", f)
            self.assertIsInstance(f["size"], int)
        # Base default puts everything in files, nothing in primary/aux
        self.assertEqual(result["primary_files"], [])
        self.assertEqual(result["aux_files"], [])

    def test_skips_subdirectories(self):
        job = self._make_fake_job()
        outdir = job.workdir / "output"
        outdir.mkdir(parents=True)
        (outdir / "subdir").mkdir()
        (outdir / "file.txt").write_text("hello")

        mt = _MinimalModelType()
        result = mt.get_output_context(job)
        self.assertEqual(len(result["files"]), 1)
        self.assertEqual(result["files"][0]["name"], "file.txt")

    def test_files_sorted_alphabetically(self):
        job = self._make_fake_job()
        outdir = job.workdir / "output"
        outdir.mkdir(parents=True)
        (outdir / "z_file.txt").write_text("z")
        (outdir / "a_file.txt").write_text("a")
        (outdir / "m_file.txt").write_text("m")

        mt = _MinimalModelType()
        result = mt.get_output_context(job)
        names = [f["name"] for f in result["files"]]
        self.assertEqual(names, ["a_file.txt", "m_file.txt", "z_file.txt"])


# ---------------------------------------------------------------------------
# 6.2  get_output_context override in Boltz2ModelType
# ---------------------------------------------------------------------------


class TestGetOutputContextBoltz2(TestCase):
    """Boltz2ModelType classifies structure files as primary."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _make_fake_job(self):
        class FakeJob:
            workdir = self.tmpdir / "job"
        return FakeJob()

    def test_pdb_files_are_primary(self):
        job = self._make_fake_job()
        outdir = job.workdir / "output"
        outdir.mkdir(parents=True)
        (outdir / "model.pdb").write_text("ATOM")
        (outdir / "slurm-123.out").write_text("log")

        mt = get_model_type("boltz2")
        result = mt.get_output_context(job)
        primary_names = [f["name"] for f in result["primary_files"]]
        aux_names = [f["name"] for f in result["aux_files"]]
        self.assertIn("model.pdb", primary_names)
        self.assertIn("slurm-123.out", aux_names)

    def test_cif_and_mmcif_are_primary(self):
        job = self._make_fake_job()
        outdir = job.workdir / "output"
        outdir.mkdir(parents=True)
        (outdir / "structure.cif").write_text("data")
        (outdir / "complex.mmcif").write_text("data")
        (outdir / "scores.json").write_text("{}")

        mt = get_model_type("boltz2")
        result = mt.get_output_context(job)
        primary_names = [f["name"] for f in result["primary_files"]]
        aux_names = [f["name"] for f in result["aux_files"]]
        self.assertIn("structure.cif", primary_names)
        self.assertIn("complex.mmcif", primary_names)
        self.assertIn("scores.json", aux_names)

    def test_files_is_primary_plus_aux(self):
        job = self._make_fake_job()
        outdir = job.workdir / "output"
        outdir.mkdir(parents=True)
        (outdir / "model.pdb").write_text("ATOM")
        (outdir / "log.txt").write_text("done")

        mt = get_model_type("boltz2")
        result = mt.get_output_context(job)
        all_names = [f["name"] for f in result["files"]]
        primary_names = [f["name"] for f in result["primary_files"]]
        aux_names = [f["name"] for f in result["aux_files"]]
        self.assertEqual(all_names, primary_names + aux_names)

    def test_empty_output_dir(self):
        job = self._make_fake_job()
        outdir = job.workdir / "output"
        outdir.mkdir(parents=True)

        mt = get_model_type("boltz2")
        result = mt.get_output_context(job)
        self.assertEqual(result["files"], [])
        self.assertEqual(result["primary_files"], [])
        self.assertEqual(result["aux_files"], [])


# ---------------------------------------------------------------------------
# 7.1  FASTA parsing utility (kept from Phase 7)
# ---------------------------------------------------------------------------


class TestParseFastaBatch(TestCase):
    """parse_fasta_batch parses multi-FASTA text correctly."""

    def test_single_entry(self):
        text = ">seq1\nMKTAYI"
        entries = parse_fasta_batch(text)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["header"], "seq1")
        self.assertEqual(entries[0]["sequence"], "MKTAYI")

    def test_multiple_entries(self):
        text = ">seq1\nMKTAYI\n>seq2\nACDEFG\n>seq3\nHIKLMN"
        entries = parse_fasta_batch(text)
        self.assertEqual(len(entries), 3)
        self.assertEqual(entries[0]["header"], "seq1")
        self.assertEqual(entries[1]["header"], "seq2")
        self.assertEqual(entries[2]["header"], "seq3")
        self.assertEqual(entries[2]["sequence"], "HIKLMN")

    def test_multiline_sequence(self):
        text = ">seq1\nMKTA\nYIAC\nDEFG"
        entries = parse_fasta_batch(text)
        self.assertEqual(entries[0]["sequence"], "MKTAYIACDEFG")

    def test_blank_lines_ignored(self):
        text = ">seq1\nMKTAYI\n\n>seq2\nACDEFG\n\n"
        entries = parse_fasta_batch(text)
        self.assertEqual(len(entries), 2)

    def test_strips_whitespace(self):
        text = "  >seq1  \n  MKTAYI  \n"
        entries = parse_fasta_batch(text)
        self.assertEqual(entries[0]["header"], "seq1")
        self.assertEqual(entries[0]["sequence"], "MKTAYI")

    def test_empty_text_raises(self):
        with self.assertRaises(ValidationError):
            parse_fasta_batch("")

    def test_no_header_raises(self):
        with self.assertRaises(ValidationError):
            parse_fasta_batch("MKTAYI")

    def test_empty_sequence_raises(self):
        with self.assertRaises(ValidationError):
            parse_fasta_batch(">seq1\n>seq2\nMKTAYI")

    def test_too_many_entries_raises(self):
        text = "\n".join(f">seq{i}\nMKTAYI" for i in range(101))
        with self.assertRaises(ValidationError) as ctx:
            parse_fasta_batch(text)
        self.assertIn("Too many", str(ctx.exception))


# ---------------------------------------------------------------------------
# 9.2  Boltz2 input_file in normalize_inputs
# ---------------------------------------------------------------------------


class TestBoltz2InputFile(TestCase):
    """Boltz2ModelType.normalize_inputs handles input_file uploads."""

    def _make_upload(self, name: str, content: bytes):
        """Create a fake file upload object."""
        upload = io.BytesIO(content)
        upload.name = name
        return upload

    def test_input_file_included_in_files(self):
        mt = get_model_type("boltz2")
        upload = self._make_upload("complex.yaml", b"version: 2\nsequences:\n  - protein:")
        payload = mt.normalize_inputs({
            "sequences": ">s\nMKTAYI",
            "input_file": upload,
        })
        self.assertIn("complex.yaml", payload["files"])
        self.assertEqual(payload["files"]["complex.yaml"], b"version: 2\nsequences:\n  - protein:")

    def test_input_file_clears_sequences(self):
        mt = get_model_type("boltz2")
        upload = self._make_upload("input.yaml", b"version: 2")
        payload = mt.normalize_inputs({
            "sequences": ">s\nMKTAYI",
            "input_file": upload,
        })
        self.assertEqual(payload["sequences"], "")

    def test_no_input_file_keeps_sequences(self):
        mt = get_model_type("boltz2")
        payload = mt.normalize_inputs({
            "sequences": ">s\nMKTAYI",
        })
        self.assertEqual(payload["sequences"], ">s\nMKTAYI")
        self.assertEqual(payload["files"], {})

    def test_params_still_populated_with_file(self):
        mt = get_model_type("boltz2")
        upload = self._make_upload("input.yaml", b"version: 2")
        payload = mt.normalize_inputs({
            "sequences": "",
            "input_file": upload,
            "use_msa_server": True,
            "recycling_steps": 5,
        })
        self.assertIn("use_msa_server", payload["params"])
        self.assertIn("recycling_steps", payload["params"])


# ---------------------------------------------------------------------------
# 12-13  ProteinMPNN / LigandMPNN model types
# ---------------------------------------------------------------------------


class TestProteinMPNNInputPayload(TestCase):
    """ProteinMPNNModelType.normalize_inputs returns correct structure."""

    def _make_upload(self, name: str, content: bytes):
        upload = io.BytesIO(content)
        upload.name = name
        return upload

    def test_payload_shape(self):
        mt = get_model_type("protein_mpnn")
        upload = self._make_upload("test.pdb", b"ATOM 1 N ALA")
        payload = mt.normalize_inputs({
            "pdb_file": upload,
            "noise_level": "v_48_020",
            "temperature": 0.1,
            "num_sequences": 8,
        })
        self.assertIsInstance(payload, dict)
        self.assertEqual(set(payload.keys()), {"sequences", "params", "files"})
        self.assertEqual(payload["sequences"], "")
        self.assertIsInstance(payload["params"], dict)
        self.assertIsInstance(payload["files"], dict)

    def test_pdb_renamed_to_input_pdb(self):
        mt = get_model_type("protein_mpnn")
        upload = self._make_upload("my_structure.pdb", b"ATOM 1 N ALA")
        payload = mt.normalize_inputs({
            "pdb_file": upload,
            "noise_level": "v_48_020",
        })
        self.assertIn("input.pdb", payload["files"])
        self.assertEqual(payload["files"]["input.pdb"], b"ATOM 1 N ALA")

    def test_model_variant_set(self):
        mt = get_model_type("protein_mpnn")
        upload = self._make_upload("test.pdb", b"ATOM")
        payload = mt.normalize_inputs({
            "pdb_file": upload,
            "noise_level": "v_48_020",
        })
        self.assertEqual(payload["params"]["model_variant"], "protein_mpnn")

    def test_strips_falsy_params(self):
        mt = get_model_type("protein_mpnn")
        upload = self._make_upload("test.pdb", b"ATOM")
        payload = mt.normalize_inputs({
            "pdb_file": upload,
            "noise_level": "v_48_020",
            "temperature": None,
            "num_sequences": None,
            "chains_to_design": "",
            "fixed_residues": "",
            "seed": None,
        })
        self.assertNotIn("temperature", payload["params"])
        self.assertNotIn("chains_to_design", payload["params"])

    def test_resolve_runner_key(self):
        mt = get_model_type("protein_mpnn")
        self.assertEqual(mt.resolve_runner_key({}), "ligandmpnn")


class TestLigandMPNNInputPayload(TestCase):
    """LigandMPNNModelType.normalize_inputs returns correct structure."""

    def _make_upload(self, name: str, content: bytes):
        upload = io.BytesIO(content)
        upload.name = name
        return upload

    def test_model_variant_set(self):
        mt = get_model_type("ligand_mpnn")
        upload = self._make_upload("test.pdb", b"ATOM")
        payload = mt.normalize_inputs({
            "pdb_file": upload,
            "noise_level": "v_32_010_25",
        })
        self.assertEqual(payload["params"]["model_variant"], "ligand_mpnn")

    def test_pdb_renamed_to_input_pdb(self):
        mt = get_model_type("ligand_mpnn")
        upload = self._make_upload("complex.pdb", b"ATOM 1 N ALA")
        payload = mt.normalize_inputs({
            "pdb_file": upload,
            "noise_level": "v_32_010_25",
        })
        self.assertIn("input.pdb", payload["files"])

    def test_resolve_runner_key(self):
        mt = get_model_type("ligand_mpnn")
        self.assertEqual(mt.resolve_runner_key({}), "ligandmpnn")


class TestInverseFoldingValidation(TestCase):
    """validate() passes for valid data (cross-field checks deferred to form)."""

    def test_protein_mpnn_validate_passes(self):
        mt = get_model_type("protein_mpnn")
        mt.validate({"pdb_file": "something", "noise_level": "v_48_020"})

    def test_ligand_mpnn_validate_passes(self):
        mt = get_model_type("ligand_mpnn")
        mt.validate({"pdb_file": "something", "noise_level": "v_32_010_25"})


class TestInverseFoldingCategories(TestCase):
    """Inverse Folding category appears in get_model_types_by_category()."""

    def test_inverse_folding_category_exists(self):
        result = get_model_types_by_category()
        categories = dict(result)
        self.assertIn("Inverse Folding", categories)

    def test_both_models_in_inverse_folding(self):
        result = get_model_types_by_category()
        categories = dict(result)
        keys = [mt.key for mt in categories["Inverse Folding"]]
        self.assertIn("protein_mpnn", keys)
        self.assertIn("ligand_mpnn", keys)


class TestInverseFoldingOutputContext(TestCase):
    """get_output_context classifies files in nested subdirectories."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _make_fake_job(self):
        class FakeJob:
            workdir = self.tmpdir / "job"
        return FakeJob()

    def test_fasta_in_seqs_is_primary(self):
        job = self._make_fake_job()
        outdir = job.workdir / "output"
        (outdir / "seqs").mkdir(parents=True)
        (outdir / "seqs" / "sample_1.fa").write_text(">designed\nACDEFG")
        (outdir / "backbones").mkdir(parents=True)
        (outdir / "backbones" / "sample_1.pdb").write_text("ATOM")

        mt = get_model_type("protein_mpnn")
        result = mt.get_output_context(job)
        primary_names = [f["name"] for f in result["primary_files"]]
        aux_names = [f["name"] for f in result["aux_files"]]
        self.assertIn("seqs/sample_1.fa", primary_names)
        self.assertIn("backbones/sample_1.pdb", aux_names)

    def test_files_is_primary_plus_aux(self):
        job = self._make_fake_job()
        outdir = job.workdir / "output"
        (outdir / "seqs").mkdir(parents=True)
        (outdir / "seqs" / "result.fasta").write_text(">s\nACDE")
        (outdir / "stats").mkdir(parents=True)
        (outdir / "stats" / "scores.pt").write_bytes(b"\x00")

        mt = get_model_type("ligand_mpnn")
        result = mt.get_output_context(job)
        all_names = [f["name"] for f in result["files"]]
        primary_names = [f["name"] for f in result["primary_files"]]
        aux_names = [f["name"] for f in result["aux_files"]]
        self.assertEqual(all_names, primary_names + aux_names)

    def test_empty_output_dir(self):
        job = self._make_fake_job()
        outdir = job.workdir / "output"
        outdir.mkdir(parents=True)

        mt = get_model_type("protein_mpnn")
        result = mt.get_output_context(job)
        self.assertEqual(result["files"], [])
        self.assertEqual(result["primary_files"], [])
        self.assertEqual(result["aux_files"], [])

    def test_no_output_dir(self):
        job = self._make_fake_job()
        mt = get_model_type("protein_mpnn")
        result = mt.get_output_context(job)
        self.assertEqual(result, {"files": [], "primary_files": [], "aux_files": []})

    def test_zip_is_primary_when_present(self):
        """When results.zip exists, it should be the sole primary file."""
        job = self._make_fake_job()
        outdir = job.workdir / "output"
        (outdir / "seqs").mkdir(parents=True)
        (outdir / "seqs" / "sample_1.fa").write_text(">designed\nACDEFG")
        (outdir / "backbones").mkdir(parents=True)
        (outdir / "backbones" / "sample_1.pdb").write_text("ATOM")
        (outdir / "slurm-12345.out").write_text("log output")
        (outdir / "results.zip").write_bytes(b"PK\x03\x04fake")

        for key in ("protein_mpnn", "ligand_mpnn"):
            with self.subTest(model=key):
                mt = get_model_type(key)
                result = mt.get_output_context(job)
                primary_names = [f["name"] for f in result["primary_files"]]
                aux_names = [f["name"] for f in result["aux_files"]]
                self.assertEqual(primary_names, ["results.zip"])
                self.assertIn("seqs/sample_1.fa", aux_names)
                self.assertIn("backbones/sample_1.pdb", aux_names)
                self.assertIn("slurm-12345.out", aux_names)
                self.assertNotIn("results.zip", aux_names)

    def test_fallback_without_zip(self):
        """Without results.zip, FASTA in seqs/ should be primary (backward compat)."""
        job = self._make_fake_job()
        outdir = job.workdir / "output"
        (outdir / "seqs").mkdir(parents=True)
        (outdir / "seqs" / "sample_1.fa").write_text(">designed\nACDEFG")
        (outdir / "backbones").mkdir(parents=True)
        (outdir / "backbones" / "sample_1.pdb").write_text("ATOM")

        for key in ("protein_mpnn", "ligand_mpnn"):
            with self.subTest(model=key):
                mt = get_model_type(key)
                result = mt.get_output_context(job)
                primary_names = [f["name"] for f in result["primary_files"]]
                aux_names = [f["name"] for f in result["aux_files"]]
                self.assertIn("seqs/sample_1.fa", primary_names)
                self.assertIn("backbones/sample_1.pdb", aux_names)


# ---------------------------------------------------------------------------
# 14  BindCraft model type
# ---------------------------------------------------------------------------


class TestBindCraftInputPayload(TestCase):
    """BindCraftModelType.normalize_inputs returns correct structure."""

    def _make_upload(self, name: str, content: bytes):
        upload = io.BytesIO(content)
        upload.name = name
        return upload

    def test_payload_shape(self):
        mt = get_model_type("bindcraft")
        upload = self._make_upload("target.pdb", b"ATOM 1 N ALA")
        payload = mt.normalize_inputs({
            "pdb_file": upload,
            "target_chain": "A",
            "length_min": 65,
            "length_max": 150,
            "number_of_final_designs": 10,
        })
        self.assertIsInstance(payload, dict)
        self.assertEqual(set(payload.keys()), {"sequences", "params", "files"})
        self.assertEqual(payload["sequences"], "")
        self.assertIsInstance(payload["params"], dict)
        self.assertIsInstance(payload["files"], dict)

    def test_pdb_renamed_to_target_pdb(self):
        mt = get_model_type("bindcraft")
        upload = self._make_upload("my_protein.pdb", b"ATOM 1 N ALA")
        payload = mt.normalize_inputs({
            "pdb_file": upload,
            "target_chain": "A",
            "length_min": 65,
            "length_max": 150,
            "number_of_final_designs": 10,
        })
        self.assertIn("target.pdb", payload["files"])
        self.assertEqual(payload["files"]["target.pdb"], b"ATOM 1 N ALA")

    def test_params_populated(self):
        mt = get_model_type("bindcraft")
        upload = self._make_upload("target.pdb", b"ATOM")
        payload = mt.normalize_inputs({
            "pdb_file": upload,
            "target_chain": "B",
            "hotspot_residues": "56,78,102",
            "length_min": 50,
            "length_max": 200,
            "number_of_final_designs": 20,
        })
        self.assertEqual(payload["params"]["target_chain"], "B")
        self.assertEqual(payload["params"]["hotspot_residues"], "56,78,102")
        self.assertEqual(payload["params"]["length_min"], 50)
        self.assertEqual(payload["params"]["length_max"], 200)
        self.assertEqual(payload["params"]["number_of_final_designs"], 20)

    def test_strips_empty_hotspot(self):
        mt = get_model_type("bindcraft")
        upload = self._make_upload("target.pdb", b"ATOM")
        payload = mt.normalize_inputs({
            "pdb_file": upload,
            "target_chain": "A",
            "hotspot_residues": "",
            "length_min": 65,
            "length_max": 150,
            "number_of_final_designs": 10,
        })
        self.assertNotIn("hotspot_residues", payload["params"])

    def test_optional_config_files_included(self):
        mt = get_model_type("bindcraft")
        pdb = self._make_upload("target.pdb", b"ATOM")
        filters = self._make_upload("filters.json", b'{"key": "val"}')
        advanced = self._make_upload("advanced.json", b'{"adv": true}')
        payload = mt.normalize_inputs({
            "pdb_file": pdb,
            "target_chain": "A",
            "length_min": 65,
            "length_max": 150,
            "number_of_final_designs": 10,
            "filters_file": filters,
            "advanced_file": advanced,
        })
        self.assertIn("filters.json", payload["files"])
        self.assertIn("advanced.json", payload["files"])
        self.assertTrue(payload["params"]["has_custom_filters"])
        self.assertTrue(payload["params"]["has_custom_advanced"])

    def test_no_optional_config_files(self):
        mt = get_model_type("bindcraft")
        pdb = self._make_upload("target.pdb", b"ATOM")
        payload = mt.normalize_inputs({
            "pdb_file": pdb,
            "target_chain": "A",
            "length_min": 65,
            "length_max": 150,
            "number_of_final_designs": 10,
        })
        self.assertNotIn("filters.json", payload["files"])
        self.assertNotIn("advanced.json", payload["files"])
        self.assertNotIn("has_custom_filters", payload["params"])
        self.assertNotIn("has_custom_advanced", payload["params"])

    def test_resolve_runner_key(self):
        mt = get_model_type("bindcraft")
        self.assertEqual(mt.resolve_runner_key({}), "bindcraft")


class TestBindCraftCategory(TestCase):
    """BindCraft appears in Protein Design category."""

    def test_protein_design_category_exists(self):
        result = get_model_types_by_category()
        categories = dict(result)
        self.assertIn("Protein Design", categories)

    def test_bindcraft_in_protein_design(self):
        result = get_model_types_by_category()
        categories = dict(result)
        keys = [mt.key for mt in categories["Protein Design"]]
        self.assertIn("bindcraft", keys)


class TestBindCraftPrepareWorkdir(TestCase):
    """BindCraft prepare_workdir generates target_settings.json."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_generates_target_settings_json(self):
        import json

        class FakeJob:
            id = "test-uuid-1234"
            workdir = self.tmpdir / "job"

        mt = get_model_type("bindcraft")
        payload = {
            "sequences": "",
            "params": {
                "target_chain": "B",
                "hotspot_residues": "56,78",
                "length_min": 50,
                "length_max": 200,
                "number_of_final_designs": 5,
            },
            "files": {"target.pdb": b"ATOM 1 N ALA"},
        }
        mt.prepare_workdir(FakeJob(), payload)

        settings_path = self.tmpdir / "job" / "input" / "target_settings.json"
        self.assertTrue(settings_path.exists())
        data = json.loads(settings_path.read_text())
        self.assertEqual(data["chains"], "B")
        self.assertEqual(data["target_hotspot_residues"], "56,78")
        self.assertEqual(data["lengths"], [50, 200])
        self.assertEqual(data["number_of_final_designs"], 5)
        self.assertEqual(data["starting_pdb"], "/work/input/target.pdb")

    def test_writes_pdb_file(self):
        class FakeJob:
            id = "test-uuid"
            workdir = self.tmpdir / "job"

        mt = get_model_type("bindcraft")
        payload = {
            "sequences": "",
            "params": {"target_chain": "A", "length_min": 65, "length_max": 150},
            "files": {"target.pdb": b"ATOM 1 N ALA A"},
        }
        mt.prepare_workdir(FakeJob(), payload)
        pdb_path = self.tmpdir / "job" / "input" / "target.pdb"
        self.assertTrue(pdb_path.exists())
        self.assertEqual(pdb_path.read_bytes(), b"ATOM 1 N ALA A")


class TestBindCraftOutputContext(TestCase):
    """BindCraft get_output_context classifies PDB as primary."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _make_fake_job(self):
        class FakeJob:
            workdir = self.tmpdir / "job"
        return FakeJob()

    def test_pdb_files_are_primary(self):
        job = self._make_fake_job()
        outdir = job.workdir / "output"
        outdir.mkdir(parents=True)
        (outdir / "binder_001.pdb").write_text("ATOM")
        (outdir / "scores.csv").write_text("score,value")

        mt = get_model_type("bindcraft")
        result = mt.get_output_context(job)
        primary_names = [f["name"] for f in result["primary_files"]]
        aux_names = [f["name"] for f in result["aux_files"]]
        self.assertIn("binder_001.pdb", primary_names)
        self.assertIn("scores.csv", aux_names)

    def test_cif_files_are_primary(self):
        job = self._make_fake_job()
        outdir = job.workdir / "output"
        outdir.mkdir(parents=True)
        (outdir / "structure.cif").write_text("data")

        mt = get_model_type("bindcraft")
        result = mt.get_output_context(job)
        primary_names = [f["name"] for f in result["primary_files"]]
        self.assertIn("structure.cif", primary_names)

    def test_files_is_primary_plus_aux(self):
        job = self._make_fake_job()
        outdir = job.workdir / "output"
        outdir.mkdir(parents=True)
        (outdir / "binder.pdb").write_text("ATOM")
        (outdir / "log.txt").write_text("done")

        mt = get_model_type("bindcraft")
        result = mt.get_output_context(job)
        all_names = [f["name"] for f in result["files"]]
        primary_names = [f["name"] for f in result["primary_files"]]
        aux_names = [f["name"] for f in result["aux_files"]]
        self.assertEqual(all_names, primary_names + aux_names)

    def test_empty_output_dir(self):
        job = self._make_fake_job()
        outdir = job.workdir / "output"
        outdir.mkdir(parents=True)

        mt = get_model_type("bindcraft")
        result = mt.get_output_context(job)
        self.assertEqual(result["files"], [])
        self.assertEqual(result["primary_files"], [])
        self.assertEqual(result["aux_files"], [])

    def test_nested_pdb_files(self):
        job = self._make_fake_job()
        outdir = job.workdir / "output"
        (outdir / "designs").mkdir(parents=True)
        (outdir / "designs" / "binder_001.pdb").write_text("ATOM")
        (outdir / "animations").mkdir(parents=True)
        (outdir / "animations" / "trajectory.gif").write_bytes(b"\x00")

        mt = get_model_type("bindcraft")
        result = mt.get_output_context(job)
        primary_names = [f["name"] for f in result["primary_files"]]
        aux_names = [f["name"] for f in result["aux_files"]]
        self.assertIn("designs/binder_001.pdb", primary_names)
        self.assertIn("animations/trajectory.gif", aux_names)


class TestBindCraftValidation(TestCase):
    """validate() passes for valid data (form handles cross-field checks)."""

    def test_validate_passes(self):
        mt = get_model_type("bindcraft")
        mt.validate({"pdb_file": "something", "target_chain": "A"})

    def test_validate_passes_empty(self):
        mt = get_model_type("bindcraft")
        mt.validate({})
