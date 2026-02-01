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

## Completed Phases (1-8)

Phases 1-8 have been implemented. Summary of what was built:

1. **Phase 1**: Core API + Registry -- `model_types/` module, `BaseModelType`, `Boltz2ModelType`, `Job.model_key`, registry, view dispatch.
2. **Phase 2**: Harden Base Abstractions -- ABC enforcement, `InputPayload` TypedDict, validation ownership clarification.
3. **Phase 3**: Generalize Job Model -- `Job.sequences` optional, `prepare_workdir` hook, service layer refactor with `_sanitize_payload_for_storage`.
4. **Phase 4**: Templates and UX -- shared `submit_base.html`, model selection landing page, generic runner exclusion from dedicated model dropdowns.
5. **Phase 5**: RunnerConfig with SLURM Resources -- resource fields, `get_slurm_directives()`, runners accept config, Boltz runner uses config.
6. **Phase 6**: Output Presentation -- `get_output_context()` on base and Boltz-2, detail template with primary/auxiliary file sections.
7. **Phase 7**: Batch + Config Parsing -- `model_types/parsers.py`, `parse_batch`/`parse_config` hooks, batch_id on Job model. **To be reworked in Phase 9.**
8. **Phase 8**: Minor Fixes -- unused variable removal, boolean filter fix, `Path.open()` in download view.

---

## Phase 9: Remove Batch/Config, Add Model-Specific File Upload

**Goal**: Replace the batch/config file infrastructure (Phase 7) with model-specific native input file uploads. The file upload accepts the raw input format for each model's CLI (YAML for Boltz-2, JSON for AF3, FASTA+restraints for Chai-1). Uploaded files replace the textarea sequence input; model configuration options still apply.

### 9.1 Remove batch/config infrastructure from BaseModelType

**File**: `model_types/base.py`

Remove the `parse_batch` and `parse_config` methods entirely. These are being replaced by the file upload approach in `normalize_inputs`.

### 9.2 Remove batch/config from Boltz2ModelType

**File**: `model_types/boltz2.py`

- Remove `parse_batch()` and `parse_config()` methods.
- Update `normalize_inputs()` to handle the new `input_file` field: when an uploaded file is present, read its content and include it in `InputPayload["files"]` under its original filename, and set `sequences` to empty string (the file replaces the textarea).

### 9.3 Replace batch/config form fields with input_file

**File**: `jobs/forms.py`

- Remove `batch_file` and `config_file` fields from `Boltz2SubmitForm`.
- Add `input_file = forms.FileField(required=False, ...)` with help text explaining it accepts a Boltz-2 YAML input file.
- Update the `clean()` method: require either `sequences` or `input_file` (not both -- file takes precedence, or error if neither provided).

### 9.4 Update submission view

**File**: `jobs/views.py`

- Remove all batch handling logic (batch_file detection, `parse_batch()` loop, `batch_id` generation).
- Remove config handling logic (config_file detection, `parse_config()` call, `merged_data` merging).
- Simplify the POST path: validate → `normalize_inputs(cleaned_data)` → `resolve_runner_key` → `create_and_submit_job`. The `normalize_inputs` method on each ModelType is now responsible for handling the file upload from `cleaned_data`.

### 9.5 Remove batch_id from Job model

**File**: `jobs/models.py`

- Remove `batch_id = models.UUIDField(null=True, blank=True, db_index=True)`.
- Create a migration to drop the field.

**File**: `jobs/services.py`

- Remove `batch_id` parameter from `create_and_submit_job`.
- Remove `batch_id` from `job_kwargs`.

### 9.6 Update Boltz-2 submit template

**File**: `jobs/templates/jobs/submit_boltz2.html`

- Remove the "Advanced" section with `batch_file` and `config_file` fields.
- Add an `input_file` field in the main form area, near the sequences textarea, with help text like: "Upload a Boltz-2 YAML input file. When provided, the sequences field is ignored."

### 9.7 Rework parsers.py

**File**: `model_types/parsers.py`

- Remove `parse_json_config()` (no longer needed for config merging).
- Keep `parse_fasta_batch()` -- it's still useful for FASTA validation in model types that accept FASTA input (Boltz-2 textarea, Chai-1 file upload).
- Remove `parse_zip_entries()` unless there's a concrete use case. Can be re-added later if needed.
- Rename or simplify the module to reflect its new purpose (FASTA validation utilities).

### 9.8 Update tests

**Files**: `model_types/tests.py`, `jobs/tests.py`

- Remove all batch/config tests: `TestBaseModelTypeBatchConfig`, `TestBoltz2ParseBatch`, `TestBoltz2ParseConfig`, `TestJobBatchIdField`, `TestServiceBatchId`, `TestBatchSubmissionView`, `TestConfigSubmissionView`, `TestBoltz2TemplateAdvancedFields`.
- Remove `TestParseJsonConfig` and `TestParseZipEntries` from parser tests.
- Keep `TestParseFastaBatch` (still useful).
- Add tests for the new `input_file` flow:
  - `Boltz2SubmitForm` accepts either sequences or input_file.
  - `Boltz2ModelType.normalize_inputs` includes file content in `InputPayload["files"]` when input_file is present.
  - View submission with input_file creates a job with the file written to workdir.
  - Form validation rejects submission with neither sequences nor input_file.

---

## Phase 10: Remove Generic RunnerModelType

**Goal**: Every model must have a dedicated ModelType. Remove the generic "runner" fallback entirely.

### 10.1 Delete RunnerModelType

**File**: `model_types/runner.py` -- **delete this file**.

### 10.2 Remove runner registration and imports

**File**: `model_types/__init__.py`

- Remove `from model_types.runner import RunnerModelType`.
- Remove `register_model_type(RunnerModelType())`.

### 10.3 Simplify registry

**File**: `model_types/registry.py`

- Remove `get_default_model_type()` (was returning the "runner" model type -- no longer exists). If a fallback is still needed for `job_detail` with old `model_key="runner"` jobs, use the first registered model type or handle the KeyError gracefully in the view.
- Remove `get_dedicated_runner_keys()` (only existed to exclude dedicated runners from the generic dropdown -- no generic dropdown anymore).
- Simplify `get_submittable_model_types()`: just return all registered model types (no special "runner" filtering logic).

### 10.4 Delete generic submit template and form

- **Delete**: `jobs/templates/jobs/submit.html`
- **File**: `jobs/forms.py` -- Remove `JobForm` class and `get_enabled_runner_choices()` function. Keep `get_disabled_runners()` (still used in the view for the disabled runners banner) and `Boltz2SubmitForm`.

### 10.5 Update job_detail fallback

**File**: `jobs/views.py`

- Remove `from model_types.registry import get_default_model_type`.
- In `job_detail`, handle `KeyError` from `get_model_type(job.model_key)` by using the base `get_output_context` default directly (instantiate a minimal fallback, or just return empty primary/aux lists).

### 10.6 Update tests

- Remove `test_runner_normalize_inputs`, `test_runner_strips_whitespace`, `test_runner_validate_does_not_check_empty_sequences`.
- Remove `TestRunnerModelTypeExclusion`, `TestDedicatedRunnerKeys`.
- Update `TestRegistry.test_both_model_types_registered` -- should only check for `boltz2`.
- Update `TestSubmitBaseTemplate.test_runner_extends_submit_base` -- remove this test.
- Update `TestJobDetailTemplateRendering.test_flat_file_list_for_base_model_type` -- use a different model_key for fallback testing (e.g., an unknown key).
- Update any other tests referencing `model_key="runner"` or `get_model_type("runner")`.

---

## Phase 11: Model Categories on Landing Page

**Goal**: Group models by category on the selection page. Categories include "Structure Prediction", "Inverse Folding", and will be extended as new model types are added.

### 11.1 Add `category` to BaseModelType

**File**: `model_types/base.py`

Add a class attribute:
```python
class BaseModelType(ABC):
    key: str = ""
    name: str = ""
    category: str = ""  # e.g., "Structure Prediction", "Inverse Folding"
    ...
```

### 11.2 Set categories on existing model types

**File**: `model_types/boltz2.py`

```python
class Boltz2ModelType(BaseModelType):
    category = "Structure Prediction"
    ...
```

Future model types will set their category similarly.

### 11.3 Add `get_model_types_by_category` to registry

**File**: `model_types/registry.py`

```python
def get_model_types_by_category() -> list[tuple[str, list[BaseModelType]]]:
    """Return model types grouped by category, ordered.

    Returns a list of (category_name, model_type_list) tuples.
    Models without a category are grouped under "Other".
    """
    from collections import OrderedDict
    groups: dict[str, list[BaseModelType]] = OrderedDict()
    for mt in MODEL_TYPES.values():
        cat = mt.category or "Other"
        groups.setdefault(cat, []).append(mt)
    return list(groups.items())
```

### 11.4 Update landing page template

**File**: `jobs/templates/jobs/select_model.html`

Replace the flat card grid with a grouped layout:
```html
{% for category, models in model_categories %}
  <h4 class="mb-3 mt-4">{{ category }}</h4>
  <div class="row g-4 mb-4">
    {% for model in models %}
    <div class="col-md-4">
      <div class="card h-100">
        <div class="card-body d-flex flex-column">
          <h5 class="card-title">{{ model.name }}</h5>
          <p class="card-text flex-grow-1">{{ model.help_text }}</p>
          {% if maintenance_mode %}
          <button class="btn btn-secondary" disabled>Submissions Disabled</button>
          {% else %}
          <a href="{% url 'job_submit' %}?model={{ model.key }}" class="btn btn-primary">Select</a>
          {% endif %}
        </div>
      </div>
    </div>
    {% endfor %}
  </div>
{% endfor %}
```

### 11.5 Update view to pass grouped model types

**File**: `jobs/views.py`

In the `job_submit` view, when rendering the model selection page:
```python
from model_types.registry import get_model_types_by_category

return render(request, "jobs/select_model.html", {
    "model_categories": get_model_types_by_category(),
    ...
})
```

### 11.6 Tests

- Test that `get_model_types_by_category()` returns grouped results.
- Test that models with `category` set appear under the right heading.
- Test that the landing page renders category headings.

---

## File Reference

**Model types harness**:
- `model_types/__init__.py` -- registration and exports
- `model_types/base.py` -- `BaseModelType` ABC and `InputPayload` TypedDict
- `model_types/registry.py` -- registry dict and lookup functions
- `model_types/boltz2.py` -- Boltz-2 ModelType implementation
- `model_types/parsers.py` -- FASTA parsing/validation utilities

**Runners**:
- `runners/__init__.py` -- `Runner` ABC, registry, `@register` decorator
- `runners/boltz.py` -- `BoltzRunner` (Docker + SLURM script)
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
- `bioportal/settings.py` -- Django settings, Boltz config, quota defaults
- `containers/boltz2/Dockerfile` -- Boltz-2 container image

**Templates**:
- `jobs/templates/jobs/base.html` -- base layout
- `jobs/templates/jobs/submit_base.html` -- shared submission form
- `jobs/templates/jobs/select_model.html` -- model selection landing page (grouped by category)
- `jobs/templates/jobs/submit_boltz2.html` -- Boltz-2 form
- `jobs/templates/jobs/detail.html` -- job detail / output files
- `jobs/templates/jobs/list.html` -- job list
