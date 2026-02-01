# ModelType + RunnerConfig API Spec and Implementation Plan

## Goal
Define a flexible, extensible API for model-specific UX, validation, and job execution that supports heterogeneous bio/ML tools (e.g., structure prediction, inverse folding), with a clean split between product-facing model types and ops/runtime configuration.

## Core Concepts

### ModelType (product/UX contract)
ModelType defines how a model appears to users, how inputs are collected/validated, how inputs are written to the workdir, and how outputs are presented.

**Key responsibilities**
- UX: submission forms, templates, help text, advanced options
- Input schema and validation
- Workdir preparation (writing input files to disk)
- Model-specific file upload (native input format: YAML, JSON, FASTA, etc.)
- Output metadata (what files/links to present, how to group/label them)
- Category assignment for landing page grouping

**Interface (Python ABC)**
```python
from abc import ABC, abstractmethod
from typing import TypedDict

class InputPayload(TypedDict):
    sequences: str            # may be empty for non-FASTA models or file uploads
    params: dict              # model-specific parameters
    files: dict[str, bytes]   # filename -> content for uploaded files

class BaseModelType(ABC):
    key: str = ""
    name: str = ""
    category: str = ""        # e.g., "Structure Prediction", "Inverse Folding"
    template_name: str = ""
    form_class: type[forms.Form] = forms.Form
    help_text: str = ""

    def get_form(self, *args, **kwargs) -> forms.Form:
        return self.form_class(*args, **kwargs)

    @abstractmethod
    def validate(self, cleaned_data: dict) -> None: ...

    @abstractmethod
    def normalize_inputs(self, cleaned_data: dict) -> InputPayload: ...

    @abstractmethod
    def resolve_runner_key(self, cleaned_data: dict) -> str: ...

    def prepare_workdir(self, job, input_payload: InputPayload) -> None: ...

    def get_output_context(self, job) -> dict: ...
```

### RunnerConfig (runtime/ops contract)
RunnerConfig defines how jobs run on the cluster. SLURM resource requirements are stored per-runner and editable via Django admin without code changes.

**Key responsibilities**
- Container image reference
- SLURM resource requests (partition, GPUs, memory, time limit)
- Env vars, mounts, and entrypoint/args

**Schema (DB fields on RunnerConfig model)**
```python
class RunnerConfig(models.Model):
    runner_key = CharField(max_length=50, unique=True)
    enabled = BooleanField(default=True)
    disabled_reason = TextField(blank=True)

    # SLURM resource configuration
    partition = CharField(max_length=50, blank=True)
    gpus = PositiveIntegerField(default=0)
    cpus = PositiveIntegerField(default=1)
    mem_gb = PositiveIntegerField(default=8)
    time_limit = CharField(max_length=20, blank=True)

    # Container configuration
    image_uri = CharField(max_length=200, blank=True)
    extra_env = JSONField(default=dict, blank=True)
    extra_mounts = JSONField(default=list, blank=True)
```

## API Structure

### Registry and discovery
- `model_types/` module with a registry dict
- Each ModelType registered by `key`
- Job submission view resolves model by `key` and uses its form/template

**Registry**
```python
MODEL_TYPES: dict[str, BaseModelType] = {}

def register_model_type(model_type: BaseModelType) -> BaseModelType:
    MODEL_TYPES[model_type.key] = model_type
    return model_type

def get_model_type(key: str) -> BaseModelType:
    return MODEL_TYPES[key]
```

### Data model
- `Job.model_key`: links job back to the ModelType that created it
- `Job.sequences`: `TextField(blank=True)` -- optional, not all models use FASTA
- `Job.params`: `JSONField` for model-specific parameters
- `Job.input_payload`: `JSONField` for the full normalized input (archival, files as filename list)
- `Job.output_payload`: `JSONField` for output metadata

### Model-specific file uploads
Each model type can accept a native input file that replaces the textarea-based sequence input. The file is the raw input format accepted by the model CLI:
- **Boltz-2**: YAML file
- **AlphaFold3**: JSON file
- **Chai-1**: FASTA file + optional restraints file

The file upload **replaces** the sequence textarea, but model configuration options (MSA server, diffusion samples, etc.) still apply alongside the uploaded file. The file is stored verbatim in the job workdir and passed to the model command.

## UX Flow

### Submission
1. User navigates to `/jobs/new/` and sees the model selection landing page with models grouped by category.
2. User selects a model, which navigates to `/jobs/new/?model=<model_key>`.
3. View resolves ModelType, renders `template_name` with `form_class`.
4. On submit:
   - Form validates base fields (required, type constraints).
   - `ModelType.validate()` enforces model-specific cross-field and domain constraints.
   - `ModelType.normalize_inputs()` produces a typed `InputPayload`.
   - `ModelType.resolve_runner_key()` determines which runner to use.
5. Service layer checks maintenance mode, runner enabled, and user quota.
6. Job record is created. `ModelType.prepare_workdir()` writes input files.
7. Runner builds SLURM script (using resource config from `RunnerConfig`).
8. SLURM job is submitted.

### Output display
- `ModelType.get_output_context()` returns structured output metadata.
- Detail template uses this to render grouped files, primary results, and auxiliary outputs.

## Completed Phases (1-11)

Phases 1-11 have been implemented. Summary of what was built:

1. **Phase 1**: Core API + Registry -- `model_types/` module, `BaseModelType`, `Boltz2ModelType`, `Job.model_key`, registry, view dispatch.
2. **Phase 2**: Harden Base Abstractions -- ABC enforcement, `InputPayload` TypedDict, validation ownership clarification.
3. **Phase 3**: Generalize Job Model -- `Job.sequences` optional, `prepare_workdir` hook, service layer refactor with `_sanitize_payload_for_storage`.
4. **Phase 4**: Templates and UX -- shared `submit_base.html`, model selection landing page, generic runner exclusion from dedicated model dropdowns.
5. **Phase 5**: RunnerConfig with SLURM Resources -- resource fields, `get_slurm_directives()`, runners accept config, Boltz runner uses config.
6. **Phase 6**: Output Presentation -- `get_output_context()` on base and Boltz-2, detail template with primary/auxiliary file sections.
7. **Phase 7**: Batch + Config Parsing -- `model_types/parsers.py`, `parse_batch`/`parse_config` hooks, batch_id on Job model. **Reworked in Phase 9.**
8. **Phase 8**: Minor Fixes -- unused variable removal, boolean filter fix, `Path.open()` in download view.
9. **Phase 9**: Remove Batch/Config, Add Model-Specific File Upload -- replaced batch/config infrastructure with model-specific native input file uploads (`input_file` field on Boltz2SubmitForm), removed `parse_batch`/`parse_config`/`batch_id`, simplified parsers.py to FASTA-only utilities.
10. **Phase 10**: Remove Generic RunnerModelType -- deleted `model_types/runner.py` and generic `submit.html`, removed `get_default_model_type`/`get_dedicated_runner_keys`/`JobForm`/`get_enabled_runner_choices`, simplified registry, added `_fallback_output_context` in views for legacy jobs.
11. **Phase 11**: Model Categories on Landing Page -- added `category` attribute to `BaseModelType`, set "Structure Prediction" on Boltz-2, added `get_model_types_by_category()` registry function, updated landing page template to render models grouped by category headings.
12. **Phase 12**: LigandMPNN Runner Infrastructure -- created `containers/ligandmpnn/Dockerfile`, deleted old `containers/protein_mpnn/` placeholder, added `LIGANDMPNN_IMAGE` setting, created shared `LigandMPNNRunner` (key=`"ligandmpnn"`) with checkpoint/model_type flag dispatch.
13. **Phase 13**: ProteinMPNN + LigandMPNN ModelTypes, Forms, Templates -- added `ProteinMPNNModelType` and `LigandMPNNModelType` (category "Inverse Folding"), `ProteinMPNNSubmitForm`/`LigandMPNNSubmitForm` with PDB upload + noise level + temperature + sequences + chains + fixed residues + seed, submit templates, updated `download_file` view for subdirectory output paths.

---

## File Reference

**Model types harness**:
- `model_types/__init__.py` -- registration and exports
- `model_types/base.py` -- `BaseModelType` ABC and `InputPayload` TypedDict
- `model_types/registry.py` -- registry dict and lookup functions
- `model_types/boltz2.py` -- Boltz-2 ModelType implementation
- `model_types/protein_mpnn.py` -- ProteinMPNN ModelType implementation
- `model_types/ligand_mpnn.py` -- LigandMPNN ModelType implementation
- `model_types/parsers.py` -- FASTA parsing/validation utilities

**Runners**:
- `runners/__init__.py` -- `Runner` ABC, registry, `@register` decorator
- `runners/boltz.py` -- `BoltzRunner` (Docker + SLURM script)
- `runners/ligandmpnn.py` -- `LigandMPNNRunner` (shared by ProteinMPNN and LigandMPNN)
- `runners/alphafold.py` -- stub
- `runners/chai.py` -- stub

**Jobs app**:
- `jobs/models.py` -- `Job` model
- `jobs/forms.py` -- `Boltz2SubmitForm`, runner helpers
- `jobs/views.py` -- submission, detail, download, cancel, delete views
- `jobs/services.py` -- `create_and_submit_job` orchestration
- `jobs/urls.py` -- URL routing

**Console (ops)**:
- `console/models.py` -- `RunnerConfig`, `UserQuota`, `SiteSettings`
- `console/services/quota.py` -- quota checking

**Infrastructure**:
- `slurm.py` -- SLURM submission, status polling, cancellation
- `bioportal/settings.py` -- Django settings, Boltz config, LigandMPNN config, quota defaults
- `containers/boltz2/Dockerfile` -- Boltz-2 container image
- `containers/ligandmpnn/Dockerfile` -- LigandMPNN container image (shared by ProteinMPNN and LigandMPNN)

**Templates**:
- `jobs/templates/jobs/base.html` -- base layout
- `jobs/templates/jobs/submit_base.html` -- shared submission form
- `jobs/templates/jobs/select_model.html` -- model selection landing page (grouped by category)
- `jobs/templates/jobs/submit_boltz2.html` -- Boltz-2 form
- `jobs/templates/jobs/submit_protein_mpnn.html` -- ProteinMPNN form
- `jobs/templates/jobs/submit_ligand_mpnn.html` -- LigandMPNN form
- `jobs/templates/jobs/detail.html` -- job detail / output files
- `jobs/templates/jobs/list.html` -- job list
