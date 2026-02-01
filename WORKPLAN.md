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
- Optional batch/config file parsing
- Output metadata (what files/links to present, how to group/label them)

**Interface (Python ABC)**
```python
from abc import ABC, abstractmethod
from typing import TypedDict

class InputPayload(TypedDict):
    """Typed contract between normalize_inputs() and the service layer."""
    sequences: str            # may be empty for non-FASTA models
    params: dict              # model-specific parameters
    files: dict[str, bytes]   # filename -> content for uploaded files

class BaseModelType(ABC):
    key: str = ""
    name: str = ""
    template_name: str = ""
    form_class: type[forms.Form] = forms.Form
    help_text: str = ""

    def get_form(self, *args, **kwargs) -> forms.Form:
        return self.form_class(*args, **kwargs)

    @abstractmethod
    def validate(self, cleaned_data: dict) -> None:
        """Model-specific validation beyond what the form enforces.
        Raise ValidationError on failure. Do NOT duplicate form-level
        checks (e.g., required fields) -- only enforce cross-field
        constraints and domain rules."""
        ...

    @abstractmethod
    def normalize_inputs(self, cleaned_data: dict) -> InputPayload:
        """Convert form cleaned_data into a typed InputPayload dict.
        Must return an InputPayload with sequences, params, and files keys."""
        ...

    @abstractmethod
    def resolve_runner_key(self, cleaned_data: dict) -> str:
        """Return the runner key to use for this submission."""
        ...

    def prepare_workdir(self, job, input_payload: InputPayload) -> None:
        """Write input files to job.workdir. Default writes sequences.fasta
        if sequences is non-empty and any files from input_payload['files'].
        Override for models that need custom workdir layouts."""
        workdir = job.workdir
        (workdir / "input").mkdir(parents=True, exist_ok=True)
        (workdir / "output").mkdir(parents=True, exist_ok=True)
        sequences = input_payload.get("sequences", "")
        if sequences:
            (workdir / "input" / "sequences.fasta").write_text(sequences, encoding="utf-8")
        for filename, content in input_payload.get("files", {}).items():
            (workdir / "input" / filename).write_bytes(content)

    def get_output_context(self, job) -> dict:
        """Return template context for rendering job outputs.
        Default returns a flat file list. Override for model-specific
        grouping, labels, primary result highlighting, etc."""
        outdir = job.workdir / "output"
        files = []
        if outdir.exists() and outdir.is_dir():
            for p in sorted(outdir.iterdir()):
                if p.is_file():
                    files.append({"name": p.name, "size": p.stat().st_size})
        return {"files": files, "primary_files": [], "aux_files": []}
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
    partition = CharField(max_length=50, blank=True)        # e.g., "gpu"
    gpus = PositiveIntegerField(default=0)                  # --gres=gpu:N
    cpus = PositiveIntegerField(default=1)                  # --cpus-per-task
    mem_gb = PositiveIntegerField(default=8)                # --mem (in GB)
    time_limit = CharField(max_length=20, blank=True)       # --time, e.g., "02:00:00"

    # Container configuration
    image_uri = CharField(max_length=200, blank=True)       # override per-runner default
    extra_env = JSONField(default=dict, blank=True)         # additional env vars
    extra_mounts = JSONField(default=list, blank=True)      # additional bind mounts
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

### Data model changes
- `Job.model_key`: links job back to the ModelType that created it
- `Job.sequences`: `TextField(blank=True)` -- optional, not all models use FASTA
- `Job.params`: `JSONField` for model-specific parameters
- `Job.input_payload`: `JSONField` for the full normalized input (archival)
- `Job.output_payload`: `JSONField` for output metadata

## UX Flow

### Submission
1. User navigates to `/jobs/new/?model=<model_key>`.
2. View resolves ModelType, renders `template_name` with `form_class`.
3. On submit:
   - Form validates base fields (required, type constraints).
   - `ModelType.validate()` enforces model-specific cross-field and domain constraints.
   - `ModelType.normalize_inputs()` produces a typed `InputPayload`.
   - `ModelType.resolve_runner_key()` determines which runner to use.
4. Service layer checks maintenance mode, runner enabled, and user quota.
5. Job record is created. `ModelType.prepare_workdir()` writes input files.
6. Runner builds SLURM script (using resource config from `RunnerConfig`).
7. SLURM job is submitted.

### Output display
- `ModelType.get_output_context()` returns structured output metadata.
- Detail template uses this to render grouped files, primary results, and auxiliary outputs.

## Example ModelTypes

### 1) Structure Prediction: Boltz-2

**User UX goals**
- Simple: FASTA textarea for single sequence
- Advanced: optional config JSON upload
- Batch: optional multi-sequence FASTA file

**Form fields**
- `name` (text, optional)
- `sequences` (textarea, required)
- `use_msa_server` (bool, optional)
- `use_potentials` (bool, optional)
- `output_format` (choice: mmCIF/PDB)
- `recycling_steps` (int, optional)
- `sampling_steps` (int, optional)
- `diffusion_samples` (int, optional)

**ModelType outline**
```python
class Boltz2ModelType(BaseModelType):
    key = "boltz2"
    name = "Boltz-2"
    template_name = "jobs/submit_boltz2.html"
    form_class = Boltz2SubmitForm
    help_text = "Predict biomolecular structure and binding affinity with Boltz-2."

    def validate(self, cleaned_data):
        # Form already enforces sequences is required.
        # Add domain-specific checks here, e.g.:
        # - multi-chain complexes require at least 2 sequences
        # - ligand SMILES validation if applicable
        pass

    def normalize_inputs(self, cleaned_data) -> InputPayload:
        sequences = (cleaned_data.get("sequences") or "").strip()
        params = {
            "use_msa_server": bool(cleaned_data.get("use_msa_server")),
            "use_potentials": bool(cleaned_data.get("use_potentials")),
            "output_format": cleaned_data.get("output_format"),
            "recycling_steps": cleaned_data.get("recycling_steps"),
            "sampling_steps": cleaned_data.get("sampling_steps"),
            "diffusion_samples": cleaned_data.get("diffusion_samples"),
        }
        params = {k: v for k, v in params.items() if v not in (None, "", False)}
        return {"sequences": sequences, "params": params, "files": {}}

    def resolve_runner_key(self, cleaned_data):
        return "boltz-2"

    def get_output_context(self, job):
        """Boltz-2 produces structure files and confidence scores."""
        outdir = job.workdir / "output"
        primary = []
        aux = []
        if outdir.exists():
            for p in sorted(outdir.iterdir()):
                if not p.is_file():
                    continue
                entry = {"name": p.name, "size": p.stat().st_size}
                if p.suffix in (".pdb", ".cif", ".mmcif"):
                    primary.append(entry)
                elif p.name.startswith("slurm-"):
                    aux.append(entry)
                else:
                    aux.append(entry)
        return {"files": primary + aux, "primary_files": primary, "aux_files": aux}
```

### 2) Inverse Folding: ProteinMPNN

**User UX goals**
- Requires a backbone structure input (PDB file upload)
- Optional constraints/positions file
- No FASTA sequences -- primary input is a file

**Form fields**
- `name` (text, optional)
- `backbone_pdb` (file, required)
- `constraint_file` (file, optional)
- `num_sequences` (int, default 1)
- `temperature` (float, default 0.1)

**ModelType outline**
```python
class ProteinMPNNModelType(BaseModelType):
    key = "protein_mpnn"
    name = "ProteinMPNN"
    template_name = "jobs/submit_protein_mpnn.html"
    form_class = ProteinMPNNForm
    help_text = "Design sequences for a given backbone structure."

    def validate(self, cleaned_data):
        pdb = cleaned_data.get("backbone_pdb")
        if pdb and pdb.size > 10 * 1024 * 1024:  # 10MB
            raise ValidationError("PDB file too large (max 10MB).")

    def normalize_inputs(self, cleaned_data) -> InputPayload:
        files = {}
        pdb = cleaned_data.get("backbone_pdb")
        if pdb:
            files["backbone.pdb"] = pdb.read()
        constraint = cleaned_data.get("constraint_file")
        if constraint:
            files["constraints.json"] = constraint.read()
        return {
            "sequences": "",  # no FASTA for inverse folding
            "params": {
                "num_sequences": cleaned_data.get("num_sequences", 1),
                "temperature": cleaned_data.get("temperature", 0.1),
            },
            "files": files,
        }

    def resolve_runner_key(self, cleaned_data):
        return "protein-mpnn"

    def prepare_workdir(self, job, input_payload):
        """ProteinMPNN needs PDB in a specific location."""
        workdir = job.workdir
        (workdir / "input").mkdir(parents=True, exist_ok=True)
        (workdir / "output").mkdir(parents=True, exist_ok=True)
        for filename, content in input_payload.get("files", {}).items():
            (workdir / "input" / filename).write_bytes(content)
```

## Implementation Plan (Phased)

### Phase 1: Core API + Registry ✅
1. [x] Create `model_types/` module with registry and base class.
2. [x] Add `model_key` to `Job` model and migrate.
3. [x] Add JSON fields for `input_payload` and `output_payload`.
4. [x] Add model lookup and dispatch in submission view.
5. [x] Implement `Boltz2ModelType` with form, template, and runner.

---

### Phase 2: Harden Base Abstractions ✅

**Goal**: Make the base contracts strict, typed, and safe so that future model types get compile-time (or at least registration-time) enforcement rather than runtime surprises.

#### 2.1 Make `BaseModelType` a proper ABC ✅

**File**: `model_types/base.py`

Current state: `BaseModelType` is a plain class. `validate()` silently returns `None`, `normalize_inputs()` returns a raw dict copy, and `resolve_runner_key()` raises `NotImplementedError` at runtime. There's no enforcement that subclasses implement required methods. This is inconsistent with `Runner` in `runners/__init__.py`, which correctly uses `ABC` + `@abstractmethod`.

Changes:
- Import `ABC` and `abstractmethod` from `abc`
- Make `BaseModelType` inherit from `ABC`
- Mark `validate`, `normalize_inputs`, and `resolve_runner_key` as `@abstractmethod`
- Remove the default implementations of `validate` (silent `return None`) and `normalize_inputs` (`return dict(cleaned_data)`) -- these are footguns, not useful defaults
- Keep `get_form` as a concrete method (the default is genuinely useful)

```python
from abc import ABC, abstractmethod
from django import forms

class BaseModelType(ABC):
    key: str = ""
    name: str = ""
    template_name: str = ""
    form_class: type[forms.Form] = forms.Form
    help_text: str = ""

    def get_form(self, *args, **kwargs) -> forms.Form:
        return self.form_class(*args, **kwargs)

    @abstractmethod
    def validate(self, cleaned_data: dict) -> None: ...

    @abstractmethod
    def normalize_inputs(self, cleaned_data: dict) -> dict: ...

    @abstractmethod
    def resolve_runner_key(self, cleaned_data: dict) -> str: ...
```

#### 2.2 Define the `InputPayload` contract ✅

**File**: `model_types/base.py` (add to the same file)

Current state: `normalize_inputs` returns `dict` with no documented shape. The view (`jobs/views.py:61-70`) assumes `"sequences"` and `"params"` keys. `create_and_submit_job` (`jobs/services.py:47-56`) requires `sequences: str` and `params: dict` as positional kwargs. If a future model type returns a differently-shaped dict, the view silently passes empty strings/dicts to the service.

Changes:
- Define an `InputPayload` TypedDict in `model_types/base.py`:

```python
from typing import TypedDict

class InputPayload(TypedDict):
    sequences: str            # FASTA text; empty string for non-FASTA models
    params: dict              # model-specific parameters (stored in Job.params)
    files: dict[str, bytes]   # filename -> content for uploaded files to write to workdir
```

- Update `BaseModelType.normalize_inputs` return type annotation to `-> InputPayload`
- Update both `Boltz2ModelType.normalize_inputs` and `RunnerModelType.normalize_inputs` to return dicts conforming to this shape (add `"files": {}` to both)
- Export `InputPayload` from `model_types/__init__.py`

This makes the contract between ModelType and the service layer explicit. A model type that only takes file uploads returns `{"sequences": "", "params": {...}, "files": {"backbone.pdb": b"..."}}`.

#### 2.3 Clarify validation ownership ✅

**Context**: Sequence-empty checks currently happen in three places:
1. `Boltz2SubmitForm.sequences` is a required `CharField` (Django enforces non-empty)
2. `Boltz2ModelType.validate()` checks sequences are non-empty
3. `create_and_submit_job()` checks sequences are non-empty

The form layer should own required-field checks. The service layer should own defense-in-depth checks at the API boundary. `ModelType.validate()` should only do things the form can't -- cross-field constraints, domain rules (e.g., "multi-chain complex requires 2+ sequences"), and input-format validation (e.g., "must be valid FASTA").

Changes:
- **`Boltz2ModelType.validate()`** (`model_types/boltz2.py`): Remove the `if not sequences: raise ValidationError` check. The form already enforces this. Instead, add a `pass` body (or add actual domain validation like FASTA format checking if desired now, otherwise leave it as a placeholder with a comment explaining what belongs here).
- **`RunnerModelType.validate()`** (`model_types/runner.py`): Same -- remove the redundant sequences check.
- **`create_and_submit_job()`** (`jobs/services.py`): Keep the `if not sequences` check but also check `if not sequences and not input_payload.get("files")` -- because non-FASTA models will have empty sequences but should have files. This becomes the defense-in-depth boundary check.
- Add a docstring to `BaseModelType.validate()` explicitly stating: "Do not duplicate form-level required-field checks here. Use this for cross-field constraints and domain-specific validation only."

---

### Phase 3: Generalize the Job Model and Service Layer ✅

**Goal**: Make the data model and service layer work for models with non-FASTA inputs (file uploads, JSON configs, structure files) without breaking existing FASTA-based models.

#### 3.1 Make `Job.sequences` optional ✅

**File**: `jobs/models.py`

Current state: `Job.sequences = models.TextField()` -- implicitly required (no `blank=True`). This works for Boltz-2 but breaks for models like ProteinMPNN where the primary input is a PDB file, not FASTA text.

Changes:
- [x] Change to `sequences = models.TextField(blank=True, default="")`.
- [x] Create and run a migration. Existing rows all have sequences, so this is backwards-compatible.

#### 3.2 Add `prepare_workdir` hook to `BaseModelType` ✅

**File**: `model_types/base.py`

Current state: `create_and_submit_job()` in `jobs/services.py:97-101` hardcodes the workdir layout:
```python
(job.workdir / "input").mkdir(parents=True, exist_ok=True)
(job.workdir / "output").mkdir(parents=True, exist_ok=True)
(job.workdir / "input" / "sequences.fasta").write_text(sequences, encoding="utf-8")
```
A model that needs to write a PDB file, multiple files, or a JSON config has no hook to control this.

Changes:
- [x] Add a `prepare_workdir(self, job, input_payload: InputPayload) -> None` method to `BaseModelType` with a concrete default implementation:

```python
def prepare_workdir(self, job, input_payload: InputPayload) -> None:
    """Write input files to job.workdir.

    Default implementation:
    - Creates input/ and output/ subdirectories
    - Writes sequences.fasta if sequences is non-empty
    - Writes all files from input_payload["files"] into input/

    Override for models that need custom workdir layouts
    (e.g., nested directories, config files, specific filenames).
    """
    workdir = job.workdir
    (workdir / "input").mkdir(parents=True, exist_ok=True)
    (workdir / "output").mkdir(parents=True, exist_ok=True)
    sequences = input_payload.get("sequences", "")
    if sequences:
        (workdir / "input" / "sequences.fasta").write_text(sequences, encoding="utf-8")
    for filename, content in input_payload.get("files", {}).items():
        (workdir / "input" / filename).write_bytes(content)
```

This is a concrete method (not abstract) because the default is genuinely useful for most models. Models with custom needs override it.

#### 3.3 Refactor `create_and_submit_job` to use `prepare_workdir` ✅

**File**: `jobs/services.py`

Changes:
- [x] Add `model_type: BaseModelType` as a parameter to `create_and_submit_job` (or resolve it internally from `model_key`).
- [x] Replace the hardcoded workdir setup (lines 97-101) with a call to `model_type.prepare_workdir(job, input_payload)`.
- [x] Update the `sequences` parameter: accept it as optional (`sequences: str = ""`). When empty, skip the old empty-check or gate it on whether the model provides files.
- [x] Update the defense-in-depth input check: instead of `if not sequences: raise`, use `if not sequences and not (input_payload or {}).get("files"): raise ValidationError("No input provided.")`.
- [x] Add `_sanitize_payload_for_storage()` to strip binary file content before DB storage.
- The new function signature:

```python
def create_and_submit_job(
    *,
    owner,
    model_type: BaseModelType,
    name: str = "",
    runner_key: str,
    sequences: str = "",
    params: dict,
    model_key: str,
    input_payload: dict | None = None,
) -> Job:
```

- [x] In the view (`jobs/views.py`), pass `model_type=model_type` to `create_and_submit_job`.

#### 3.4 Update the view to pass `input_payload` through properly ✅

**File**: `jobs/views.py`

Current state (lines 59-71):
```python
model_type.validate(form.cleaned_data)
input_payload = model_type.normalize_inputs(form.cleaned_data)
runner_key = model_type.resolve_runner_key(form.cleaned_data)
job = create_and_submit_job(
    owner=request.user,
    name=form.cleaned_data.get("name", ""),
    runner_key=runner_key,
    sequences=input_payload.get("sequences", ""),
    params=input_payload.get("params", {}),
    model_key=model_type.key,
    input_payload=input_payload,
)
```

Changes:
- [x] Add `model_type=model_type` to the `create_and_submit_job` call.
- [x] The `input_payload` is already passed through. The service layer will now use it for `prepare_workdir` instead of reconstructing the workdir layout itself.
- [x] When storing `input_payload` in the Job record, strip the `"files"` key (binary content shouldn't be stored in JSON). Store a version with filenames only (handled in `_sanitize_payload_for_storage` in the service layer):

```python
# In the view, before passing to service:
storage_payload = {
    "sequences": input_payload.get("sequences", ""),
    "params": input_payload.get("params", {}),
    "files": list(input_payload.get("files", {}).keys()),  # filenames only
}
```

Or handle this inside `create_and_submit_job` before writing to the DB.

---

### Phase 4: Templates and UX ✅

**Goal**: Eliminate template duplication and resolve the awkward two-track submission system (generic `RunnerModelType` vs. specialized model types).

#### 4.1 Create a shared base submission template ✅

**File**: `jobs/templates/jobs/submit_base.html` (new)

Current state: `submit.html` and `submit_boltz2.html` share ~80% of their markup (maintenance banner, disabled runners banner, card layout, CSRF token, hidden model field, submit/cancel buttons). Every new model type would copy-paste this boilerplate.

Changes:
- [x] Create `jobs/templates/jobs/submit_base.html` with the shared structure:

```html
{% extends "jobs/base.html" %}

{% block title %}{{ page_title }}{% endblock %}

{% block content %}
  <h1 class="mb-4">{{ page_title }}</h1>

  {% if maintenance_mode %}
  <div class="alert alert-warning d-flex align-items-center mb-4" role="alert">
    <!-- maintenance SVG icon -->
    <div>
      <strong>Maintenance Mode Active</strong>
      <p class="mb-0">{{ maintenance_message }}</p>
    </div>
  </div>
  {% endif %}

  {% if disabled_runners %}
  <div class="alert alert-info mb-4" role="alert">
    <strong>Some runners are temporarily unavailable:</strong>
    <ul class="mb-0 mt-2">
      {% for runner in disabled_runners %}
      <li><strong>{{ runner.name }}</strong>: {{ runner.reason }}</li>
      {% endfor %}
    </ul>
  </div>
  {% endif %}

  <div class="card">
    <div class="card-body">
      <form method="post" enctype="multipart/form-data">
        {% csrf_token %}
        <input type="hidden" name="model" value="{{ model_key }}">
        {{ form.non_field_errors }}

        {% block form_fields %}{% endblock %}

        {% if maintenance_mode %}
        <button class="btn btn-secondary" type="submit" disabled>
          <!-- lock icon -->
          Submissions Disabled
        </button>
        {% else %}
        <button class="btn btn-primary" type="submit">Submit</button>
        {% endif %}
        <a class="btn btn-outline-secondary" href="{% url 'job_list' %}">Cancel</a>
      </form>
    </div>
  </div>
{% endblock %}
```

Key additions vs. current templates:
- `enctype="multipart/form-data"` on the form tag (required for file uploads)
- `{{ page_title }}` variable instead of hardcoded title
- `{% block form_fields %}` for model-specific content

- [x] Update `submit_boltz2.html` to extend `submit_base.html` and only define `{% block form_fields %}` with the Boltz-specific fields.
- [x] Update `submit.html` to extend `submit_base.html` similarly.
- [x] Add `page_title` to the template context in the view (e.g., `f"New {model_type.name} Job"`).

#### 4.2 Resolve the generic vs. specialized model type tension ✅

Current state: `RunnerModelType` (key="runner") is a generic catch-all that shows all registered runners in a dropdown. `Boltz2ModelType` (key="boltz2") provides a dedicated Boltz-2 form. Both paths can submit Boltz-2 jobs, but the generic path omits all Boltz-specific parameters. This creates a confusing dual-path UX that will get worse as more specialized model types are added.

**Decision**: The generic `RunnerModelType` should serve as a minimal fallback for runners that don't yet have dedicated model types. Runners that DO have a dedicated model type should be excluded from the generic dropdown.

Changes:
- [x] **`jobs/forms.py`**: Update `get_enabled_runner_choices()` to accept an `exclude_keys` parameter:

```python
def get_enabled_runner_choices(exclude_keys: set[str] | None = None) -> list[tuple[str, str]]:
    enabled_keys = RunnerConfig.get_enabled_runners()
    exclude = exclude_keys or set()
    return [(r.key, r.name) for r in all_runners()
            if r.key in enabled_keys and r.key not in exclude]
```

- [x] **`model_types/runner.py`**: In `RunnerModelType.get_form()`, compute the set of runner keys that have dedicated model types and exclude them:

```python
def get_form(self, *args, **kwargs) -> forms.Form:
    form = super().get_form(*args, **kwargs)
    # Exclude runners that have their own dedicated ModelType
    from model_types.registry import MODEL_TYPES
    dedicated_runner_keys = set()
    for mt in MODEL_TYPES.values():
        if mt.key != "runner":  # don't exclude ourselves
            # Each dedicated ModelType maps to exactly one runner key
            # Use a class attribute or inspect resolve_runner_key
            if hasattr(mt, '_runner_key'):
                dedicated_runner_keys.add(mt._runner_key)
    form.fields["runner"].choices = get_enabled_runner_choices(
        exclude_keys=dedicated_runner_keys
    )
    return form
```

- [x] **Simpler alternative**: Add a `_runner_key` class attribute to each dedicated ModelType (e.g., `Boltz2ModelType._runner_key = "boltz-2"`) and use that for exclusion. Added `get_dedicated_runner_keys()` to registry.

- [x] **If the generic dropdown ends up empty** (all runners have dedicated model types), `get_submittable_model_types()` excludes the generic runner from the selection page.

#### 4.3 Add a model selection landing page ✅

**File**: `jobs/templates/jobs/select_model.html` (new)

When the user navigates to `/jobs/new/` without a `?model=` parameter, instead of defaulting to the generic runner form, show a card grid of available model types:

```html
{% extends "jobs/base.html" %}
{% block content %}
  <h1 class="mb-4">New Job</h1>
  <div class="row g-4">
    {% for model in model_types %}
    <div class="col-md-4">
      <div class="card h-100">
        <div class="card-body">
          <h5 class="card-title">{{ model.name }}</h5>
          <p class="card-text">{{ model.help_text }}</p>
          <a href="{% url 'job_submit' %}?model={{ model.key }}" class="btn btn-primary">
            Select
          </a>
        </div>
      </div>
    </div>
    {% endfor %}
  </div>
{% endblock %}
```

Changes to the view (`jobs/views.py`):
- [x] If no `model` param is provided and `request.method == "GET"`, render the selection page with all registered model types.
- [x] Added `get_submittable_model_types()` to registry for smart filtering of the selection page.

---

### Phase 5: RunnerConfig with SLURM Resources ✅

**Goal**: Make SLURM resource requirements (partition, GPUs, memory, time limit) configurable per-runner via Django admin, and have runners use these settings when building sbatch scripts.

#### 5.1 Add resource fields to `RunnerConfig` ✅

**File**: `console/models.py`

Current state: `RunnerConfig` has `runner_key`, `enabled`, `disabled_reason`, and timestamps. No resource fields.

Changes (all done):
- [x] Add these fields to `RunnerConfig`:
```python
# SLURM resource configuration
partition = models.CharField(
    max_length=50, blank=True,
    help_text="SLURM partition (e.g., 'gpu', 'cpu'). Empty = cluster default.",
)
gpus = models.PositiveIntegerField(
    default=0,
    help_text="Number of GPUs (--gres=gpu:N). 0 = no GPU request.",
)
cpus = models.PositiveIntegerField(
    default=1,
    help_text="CPUs per task (--cpus-per-task).",
)
mem_gb = models.PositiveIntegerField(
    default=8,
    help_text="Memory in GB (--mem).",
)
time_limit = models.CharField(
    max_length=20, blank=True,
    help_text="Time limit (--time, e.g., '02:00:00'). Empty = cluster default.",
)

# Container configuration
image_uri = models.CharField(
    max_length=200, blank=True,
    help_text="Container image override. Empty = use runner's default.",
)
extra_env = models.JSONField(
    default=dict, blank=True,
    help_text="Additional environment variables as JSON object.",
)
extra_mounts = models.JSONField(
    default=list, blank=True,
    help_text='Additional bind mounts as JSON array of {"source": "...", "target": "..."} objects.',
)
```

- [x] Create and run migration (`0003_add_runnerconfig_resource_fields`).

#### 5.2 Add a `get_slurm_directives` method to `RunnerConfig` ✅

**File**: `console/models.py`

```python
def get_slurm_directives(self) -> str:
    """Generate #SBATCH directive lines from resource config."""
    lines = []
    if self.partition:
        lines.append(f"#SBATCH --partition={self.partition}")
    if self.gpus:
        lines.append(f"#SBATCH --gres=gpu:{self.gpus}")
    if self.cpus > 1:
        lines.append(f"#SBATCH --cpus-per-task={self.cpus}")
    if self.mem_gb:
        lines.append(f"#SBATCH --mem={self.mem_gb}G")
    if self.time_limit:
        lines.append(f"#SBATCH --time={self.time_limit}")
    return "\n".join(lines)
```

#### 5.3 Update `Runner.build_script` to accept resource config ✅

**File**: `runners/__init__.py`

Changes:
- [x] Update the `Runner` ABC to pass resource config into `build_script`:

```python
class Runner(ABC):
    key: str
    name: str

    @abstractmethod
    def build_script(self, job, config: RunnerConfig | None = None) -> str:
        """Generate sbatch script content for a Job.
        config provides SLURM resource settings and container overrides."""
        ...
```

- [x] Update `jobs/services.py` to fetch the `RunnerConfig` and pass it:

```python
config = RunnerConfig.get_config(runner_key)
script = runner.build_script(job, config=config)
```

#### 5.4 Update `BoltzRunner.build_script` to use config ✅

**File**: `runners/boltz.py`

Current state: The sbatch script has no resource directives -- only `--job-name`, `--output`, and `--error`. The container image is read from `settings.BOLTZ_IMAGE`.

Changes:
```python
def build_script(self, job, config=None) -> str:
    workdir = Path(job.workdir)
    outdir = workdir / "output"
    cache_dir = Path(settings.BOLTZ_CACHE_DIR)

    # Use config image override, fall back to settings
    image = (config.image_uri if config and config.image_uri
             else settings.BOLTZ_IMAGE)

    # Build SLURM directives from config
    slurm_directives = config.get_slurm_directives() if config else ""

    # ... build flags from params as before ...

    return f"""#!/bin/bash
#SBATCH --job-name=boltz-{job.id}
#SBATCH --output={outdir}/slurm-%j.out
#SBATCH --error={outdir}/slurm-%j.err
{slurm_directives}

set -euo pipefail
mkdir -p {outdir} {cache_dir}

docker run --rm --gpus all \\
  -e BOLTZ_CACHE=/cache \\
  -e BOLTZ_MSA_USERNAME \\
  -e BOLTZ_MSA_PASSWORD \\
  -v {workdir}:/work \\
  -v {cache_dir}:/cache \\
  {image} predict /work/input/sequences.fasta --out_dir /work/output --cache /cache {flag_str}
"""
```

Also:
- [x] Remove the unused `input_path` variable (was on line 18 of `runners/boltz.py`).
- [x] Update stub runners (`alphafold.py`, `chai.py`) to accept `config` parameter and emit SLURM directives.

---

### Phase 6: Output Presentation ✅

**Goal**: Give model types control over how job outputs are displayed, enabling primary result highlighting, file grouping, and model-specific rendering.

#### 6.1 Add `get_output_context` to `BaseModelType` ✅

**File**: `model_types/base.py`

Added a concrete (not abstract) method with a useful default:

```python
def get_output_context(self, job) -> dict:
    """Return template context for rendering job outputs on the detail page.

    Returns a dict with:
      - files: list of all output file dicts (name, size)
      - primary_files: list of "main result" file dicts
      - aux_files: list of auxiliary/log file dicts

    Override to customize grouping, add labels, or flag specific
    files for inline preview.
    """
    outdir = job.workdir / "output"
    files = []
    if outdir.exists() and outdir.is_dir():
        for p in sorted(outdir.iterdir()):
            if p.is_file():
                files.append({"name": p.name, "size": p.stat().st_size})
    return {"files": files, "primary_files": [], "aux_files": []}
```

#### 6.2 Override in `Boltz2ModelType` ✅

**File**: `model_types/boltz2.py`

```python
def get_output_context(self, job) -> dict:
    outdir = job.workdir / "output"
    primary, aux = [], []
    if outdir.exists():
        for p in sorted(outdir.iterdir()):
            if not p.is_file():
                continue
            entry = {"name": p.name, "size": p.stat().st_size}
            if p.suffix in (".pdb", ".cif", ".mmcif"):
                primary.append(entry)
            else:
                aux.append(entry)
    return {
        "files": primary + aux,
        "primary_files": primary,
        "aux_files": aux,
    }
```

#### 6.3 Update `job_detail` view to use `get_output_context` ✅

**File**: `jobs/views.py`

Previous state:
```python
def job_detail(request, job_id):
    job = get_object_or_404(...)
    outdir = job.workdir / "output"
    files = []
    if outdir.exists() and outdir.is_dir():
        for p in sorted(outdir.iterdir()):
            if p.is_file():
                files.append(p.name)
    return render(request, "jobs/detail.html", {"job": job, "files": files})
```

Changes (all done):
- [x] Resolve model type from `job.model_key` with fallback to `get_default_model_type()`
- [x] Call `model_type.get_output_context(job)` and spread into template context
- [x] Import `get_default_model_type` from registry

#### 6.4 Update `detail.html` template ✅

**File**: `jobs/templates/jobs/detail.html`

Updated the output files section to use the structured context:

```html
<h2 class="mb-3">Output Files</h2>
<div class="card">
  <div class="card-body">
    {% if primary_files %}
      <h6 class="text-muted mb-2">Results</h6>
      <div class="table-responsive mb-3">
        <table class="table table-hover mb-0">
          <thead><tr><th>File</th><th>Size</th><th></th></tr></thead>
          <tbody>
            {% for f in primary_files %}
            <tr>
              <td class="font-monospace">{{ f.name }}</td>
              <td class="text-muted">{{ f.size|filesizeformat }}</td>
              <td><a class="btn btn-outline-primary btn-sm" href="{% url 'download_file' job_id=job.id filename=f.name %}">Download</a></td>
            </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
    {% endif %}

    {% if aux_files %}
      <h6 class="text-muted mb-2">Logs &amp; Auxiliary</h6>
      <!-- same table structure for aux_files -->
    {% endif %}

    {% if not files %}
      <p class="text-muted mb-0">No output files found yet.</p>
    {% endif %}
  </div>
</div>
```

Changes (all done):
- [x] Primary files shown in a "Results" section with `btn-outline-primary` download buttons
- [x] Auxiliary files shown in a "Logs & Auxiliary" section with `btn-outline-secondary` download buttons
- [x] Flat file list fallback when no primary/aux classification (base model type default)
- [x] File sizes displayed via `filesizeformat` filter
- [x] "No output files found yet" message when no files exist
- [x] Backwards-compatible: base model type returns empty primary/aux lists, template shows flat list

---

### Phase 7: Batch + Config Parsing ✅

**Goal**: Support batch submissions (multi-FASTA file, ZIP of PDBs) and advanced configuration files (JSON config overrides).

#### 7.1 Add shared parsing utilities ✅

**File**: `model_types/parsers.py` (new)

Changes (all done):
- [x] `parse_fasta_batch(text)` — parses multi-FASTA into `[{"header", "sequence"}, ...]` with validation (empty text, missing headers, empty sequences, max 100 entries)
- [x] `parse_zip_entries(upload, allowed_extensions, max_total_bytes)` — extracts ZIP entries with safety checks (path traversal rejection, extension filtering, size limits, max 100 entries, basename deduplication)
- [x] `parse_json_config(upload)` — parses JSON config files with type validation (must be a dict)

#### 7.2 Add batch/config methods to `BaseModelType` ✅

**File**: `model_types/base.py`

Changes (all done):
- [x] Added `parse_batch(self, upload) -> list[dict]` — concrete method that raises `NotImplementedError` by default
- [x] Added `parse_config(self, upload) -> dict` — concrete method that raises `NotImplementedError` by default
- [x] Model types opt in to batch/config support by overriding these methods

#### 7.3 Update submission view and service layer ✅

Changes (all done):
- [x] Added `batch_id = UUIDField(null=True, blank=True, db_index=True)` to Job model with migration `0007_add_batch_id`
- [x] Updated `create_and_submit_job()` to accept optional `batch_id` parameter
- [x] Updated `job_submit` view: detects `batch_file` in cleaned_data, calls `model_type.parse_batch()`, loops to create multiple jobs with shared `batch_id`, redirects to job list
- [x] Updated `job_submit` view: detects `config_file` in cleaned_data, calls `model_type.parse_config()`, merges overrides into cleaned_data before `normalize_inputs()`
- [x] Config merging happens before batch splitting, so batch + config works together

#### 7.4 Add UI hints ✅

Changes (all done):
- [x] Added `batch_file` and `config_file` FileField to `Boltz2SubmitForm` with descriptive help text
- [x] Made `sequences` field optional in `Boltz2SubmitForm` (required=False) with cross-field `clean()` that requires either sequences or batch_file
- [x] Added "Advanced" section to `submit_boltz2.html` with batch file and config file upload fields
- [x] `submit_base.html` already has `enctype="multipart/form-data"` for file uploads
- [x] Implemented `Boltz2ModelType.parse_batch()` — splits multi-FASTA into per-sequence items with name from header
- [x] Implemented `Boltz2ModelType.parse_config()` — parses JSON, filters to allowed Boltz-2 parameter keys only

---

### Phase 8: Minor Fixes and Cleanup ✅

These can be done at any point, ideally alongside the phase that touches the relevant file.

#### 8.1 Remove unused variable in `BoltzRunner` ✅

**File**: `runners/boltz.py:18`

`input_path = workdir / "input" / "sequences.fasta"` was defined but never used. Already removed in Phase 5.

#### 8.2 Fix `normalize_inputs` filter for boolean False ✅

**File**: `model_types/boltz2.py:31`

Filter already updated to `{k: v for k, v in params.items() if v not in (None, "", False)}` to exclude dead-weight `False` values from stored JSON.

#### 8.3 Fix file handle in `download_file` ✅

**File**: `jobs/views.py:153`

Changed `open(file_path, "rb")` to `file_path.open("rb")` for idiomatic `Path` usage.

---

## Open Questions
- Should batch uploads create many independent jobs or one parent job with sub-tasks?
- Should advanced config files be stored verbatim (as a file in the workdir) or parsed and merged into `input_payload`?
- For the model selection landing page: should it replace the default "runner" form, or coexist alongside it?

## File Reference

**Model types harness**:
- `model_types/__init__.py` -- registration and exports
- `model_types/base.py` -- `BaseModelType` ABC and `InputPayload` TypedDict
- `model_types/registry.py` -- registry dict and lookup functions
- `model_types/boltz2.py` -- Boltz-2 ModelType implementation
- `model_types/runner.py` -- generic runner ModelType
- `model_types/parsers.py` -- shared parsing utilities (FASTA, ZIP, JSON config) (Phase 7)

**Runners**:
- `runners/__init__.py` -- `Runner` ABC, registry, `@register` decorator
- `runners/boltz.py` -- `BoltzRunner` (Docker + SLURM script)
- `runners/alphafold.py` -- stub
- `runners/chai.py` -- stub

**Jobs app**:
- `jobs/models.py` -- `Job` model
- `jobs/forms.py` -- `JobForm`, `Boltz2SubmitForm`, runner helpers
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
- `jobs/templates/jobs/submit_base.html` -- shared submission form (Phase 4)
- `jobs/templates/jobs/select_model.html` -- model selection landing page (Phase 4)
- `jobs/templates/jobs/submit.html` -- generic runner form (extends submit_base)
- `jobs/templates/jobs/submit_boltz2.html` -- Boltz-2 form (extends submit_base)
- `jobs/templates/jobs/detail.html` -- job detail / output files
- `jobs/templates/jobs/list.html` -- job list
