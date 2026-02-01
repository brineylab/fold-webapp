"""Tests for the model_types harness (Phase 2: Harden Base Abstractions)."""
from __future__ import annotations

from django import forms
from django.test import TestCase

from model_types.base import BaseModelType, InputPayload
from model_types.registry import MODEL_TYPES, get_model_type


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
    """Both registered ModelTypes must return InputPayload-shaped dicts."""

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

    def test_runner_normalize_inputs(self):
        mt = get_model_type("runner")
        payload = mt.normalize_inputs({
            "sequences": ">s\nMKTAYI",
            "runner": "boltz-2",
        })
        self._assert_payload_shape(payload)
        self.assertEqual(payload["sequences"], ">s\nMKTAYI")
        self.assertEqual(payload["params"], {})
        self.assertEqual(payload["files"], {})

    def test_runner_strips_whitespace(self):
        mt = get_model_type("runner")
        payload = mt.normalize_inputs({
            "sequences": "  >s\nMKTAYI  \n",
            "runner": "boltz-2",
        })
        self.assertEqual(payload["sequences"], ">s\nMKTAYI")


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

    def test_runner_validate_does_not_check_empty_sequences(self):
        mt = get_model_type("runner")
        mt.validate({"sequences": ""})
        mt.validate({})


# ---------------------------------------------------------------------------
# Registry sanity
# ---------------------------------------------------------------------------


class TestRegistry(TestCase):
    def test_both_model_types_registered(self):
        self.assertIn("boltz2", MODEL_TYPES)
        self.assertIn("runner", MODEL_TYPES)

    def test_get_model_type_unknown_raises(self):
        with self.assertRaises(KeyError):
            get_model_type("nonexistent")
