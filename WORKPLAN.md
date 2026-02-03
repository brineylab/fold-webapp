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

## Completed Phases (1-17)

Phases 1-17 have been implemented. Summary of what was built:

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
14. **Phase 14**: Chai-1 Dockerfile -- created `containers/chai1/Dockerfile` (CUDA 12.2 + cuDNN base, `chai_lab` from PyPI, `chai-lab` entrypoint, `CHAI_VERSION` build arg).
15. **Phase 15**: Chai-1 Runner -- replaced stub in `runners/chai.py` with real `ChaiRunner` (Docker + SLURM script generation, `CHAI_DOWNLOADS_DIR` cache mount, conditional `--constraint-path` for restraints, `--use-msa-server`/`--num-diffn-samples`/`--seed` flags). Added `CHAI_IMAGE` and `CHAI_CACHE_DIR` settings.
16. **Phase 16**: Chai-1 ModelType, Form, and Template -- added `Chai1ModelType` (category "Structure Prediction"), `Chai1SubmitForm` with sequences textarea + FASTA file upload + restraints CSV upload + MSA server + diffusion samples + seed, submit template, registered in `model_types/__init__.py`.
17. **Phase 17**: Settings, env.example, and File Reference Updates -- added `CHAI_IMAGE`/`CHAI_CACHE_DIR` to `env.example`, updated workplan completed phases and file reference.

---

## File Reference

**Model types harness**:
- `model_types/__init__.py` -- registration and exports
- `model_types/base.py` -- `BaseModelType` ABC and `InputPayload` TypedDict
- `model_types/registry.py` -- registry dict and lookup functions
- `model_types/boltz2.py` -- Boltz-2 ModelType implementation
- `model_types/chai1.py` -- Chai-1 ModelType implementation
- `model_types/protein_mpnn.py` -- ProteinMPNN ModelType implementation
- `model_types/ligand_mpnn.py` -- LigandMPNN ModelType implementation
- `model_types/parsers.py` -- FASTA parsing/validation utilities

**Runners**:
- `runners/__init__.py` -- `Runner` ABC, registry, `@register` decorator
- `runners/boltz.py` -- `BoltzRunner` (Docker + SLURM script)
- `runners/chai.py` -- `ChaiRunner` (Docker + SLURM script)
- `runners/ligandmpnn.py` -- `LigandMPNNRunner` (shared by ProteinMPNN and LigandMPNN)
- `runners/alphafold.py` -- stub

**Jobs app**:
- `jobs/models.py` -- `Job` model
- `jobs/forms.py` -- `Boltz2SubmitForm`, `Chai1SubmitForm`, runner helpers
- `jobs/views.py` -- submission, detail, download, cancel, delete views
- `jobs/services.py` -- `create_and_submit_job` orchestration
- `jobs/urls.py` -- URL routing

**Console (ops)**:
- `console/models.py` -- `RunnerConfig`, `UserQuota`, `SiteSettings`
- `console/services/quota.py` -- quota checking

**Infrastructure**:
- `slurm.py` -- SLURM submission, status polling, cancellation
- `bioportal/settings.py` -- Django settings, Boltz config, Chai-1 config, LigandMPNN config, quota defaults
- `containers/boltz2/Dockerfile` -- Boltz-2 container image
- `containers/chai1/Dockerfile` -- Chai-1 container image
- `containers/ligandmpnn/Dockerfile` -- LigandMPNN container image (shared by ProteinMPNN and LigandMPNN)

**Templates**:
- `jobs/templates/jobs/base.html` -- base layout
- `jobs/templates/jobs/submit_base.html` -- shared submission form
- `jobs/templates/jobs/select_model.html` -- model selection landing page (grouped by category)
- `jobs/templates/jobs/submit_boltz2.html` -- Boltz-2 form
- `jobs/templates/jobs/submit_chai1.html` -- Chai-1 form
- `jobs/templates/jobs/submit_protein_mpnn.html` -- ProteinMPNN form
- `jobs/templates/jobs/submit_ligand_mpnn.html` -- LigandMPNN form
- `jobs/templates/jobs/detail.html` -- job detail / output files
- `jobs/templates/jobs/list.html` -- job list

---

## Phase 18: Accessibility (High Priority)

Evaluated against [Vercel Web Interface Guidelines](https://github.com/vercel-labs/web-interface-guidelines).

### 18.1 Add "Skip to content" link
**File:** `jobs/templates/jobs/base.html`

Add a visually-hidden skip link as the first child of `<body>`, targeting a `#main-content` id on the content container.

```html
<a href="#main-content" class="visually-hidden-focusable position-absolute top-0 start-0 p-2 bg-primary text-white z-3">
  Skip to content
</a>
```

Add `id="main-content"` to the `<div class="container py-4">` wrapper.

### 18.2 Add `aria-live` to message container
**File:** `jobs/templates/jobs/base.html`

Wrap the Django messages block in a `<div aria-live="polite" aria-atomic="true">` so screen readers announce flash messages.

### 18.3 Replace `:focus` with `:focus-visible` in custom CSS
**File:** `jobs/templates/jobs/base.html`

Change the custom form focus styles from `form input:focus` to `form input:focus-visible` (and same for select/textarea). Remove `outline: 0` -- Bootstrap's `:focus-visible` handles this properly. The spec says "never apply `outline: none` without a visible replacement" and the current code suppresses outline.

### 18.4 Add `color-scheme` CSS property
**File:** `jobs/templates/jobs/base.html`

Add to the `<style>` block:
```css
html[data-bs-theme="dark"] { color-scheme: dark; }
html[data-bs-theme="light"] { color-scheme: light; }
```
Ensures native form controls, scrollbars, and system UI match the theme.

### 18.5 Honor `prefers-reduced-motion`
**File:** `jobs/templates/jobs/base.html`

Add to the `<style>` block:
```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

---

## Phase 19: Forms (High Priority)

### 19.1 Submit button loading state
**File:** `jobs/templates/jobs/submit_base.html`

Add JS to the submit form that, on submit: (a) disables the button, (b) shows a spinner, (c) preserves the original label text. Prevents double-submission and gives feedback.

```html
<button class="btn btn-primary" type="submit" id="submitBtn">Submit</button>
<script>
document.querySelector('form').addEventListener('submit', function() {
  const btn = document.getElementById('submitBtn');
  if (btn && !btn.disabled) {
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1" aria-hidden="true"></span>Submit';
  }
});
</script>
```

Apply the same pattern to: login form, console settings forms, and any other POST forms.

### 19.2 Login form `autocomplete` attributes
**File:** `templates/registration/login.html` and new form class

Django renders fields from `AuthenticationForm`. Create a `CustomLoginForm` that extends `AuthenticationForm` and sets widget attrs:
- Username: `autocomplete="username"`, `spellcheck="false"`
- Password: `autocomplete="current-password"`

Wire it in `bioportal/urls.py`.

### 19.3 Add `autocomplete` and `spellcheck` to job forms
**File:** `jobs/forms.py`

- Add `spellcheck="false"` to the `name` field widgets across all forms (identifiers, not prose)
- Add `autocomplete="off"` to scientific input fields (sequences, residues, etc.)

### 19.4 Placeholder ellipsis consistency
**Files:** `jobs/forms.py` and console templates

Replace `...` with `…` (proper ellipsis character) in all placeholders. Update placeholders to end with `…` where they demonstrate expected patterns.

- `"placeholder": "A,B"` → `"placeholder": "A, B…"`
- `"placeholder": "1 2 3 4"` → `"placeholder": "1 2 3 4…"`
- Console templates: `"Job ID, name, owner, SLURM ID..."` → `"Job ID, name, owner, SLURM ID…"`

### 19.5 Extend checkbox/radio hit targets
**Files:** `jobs/templates/jobs/submit_boltz2.html` and other submit templates

Ensure `<label>` elements wrap or reference checkbox inputs via `for` attribute so the entire label is clickable.

---

## Phase 20: UX & Navigation (Medium Priority)

### 20.1 Unsaved changes warning on forms
**File:** `jobs/templates/jobs/submit_base.html`

Add a `beforeunload` listener that fires when form inputs have been modified but not submitted:

```js
let formDirty = false;
document.querySelector('form').addEventListener('input', () => formDirty = true);
document.querySelector('form').addEventListener('submit', () => formDirty = false);
window.addEventListener('beforeunload', (e) => {
  if (formDirty) { e.preventDefault(); }
});
```

### 20.2 `scroll-margin-top` on headings
**File:** `jobs/templates/jobs/base.html` (global styles)

```css
h1, h2, h3, h4, h5, h6, [id] { scroll-margin-top: 4rem; }
```

Accounts for the fixed navbar when using anchor links.

### 20.3 `<meta name="theme-color">`
**File:** `jobs/templates/jobs/base.html`

Add a theme-color meta tag and update it dynamically when theme changes:

```html
<meta name="theme-color" content="#f8f9fa">
```

Update the `applyTheme()` JS function to also set `theme-color` based on the resolved theme (light: `#f8f9fa`, dark: `#212529`).

### 20.4 `font-variant-numeric: tabular-nums` for data displays
**File:** `jobs/templates/jobs/base.html` (global styles)

```css
.table td, .badge { font-variant-numeric: tabular-nums; }
```

Ensures numbers in tables and badges align properly for comparison.

---

## Phase 21: Performance & Polish (Lower Priority)

### 21.1 Add `<link rel="preconnect">` for CDN
**File:** `jobs/templates/jobs/base.html`

Add before the Bootstrap CSS link:
```html
<link rel="preconnect" href="https://cdn.jsdelivr.net" crossorigin>
```

### 21.2 `touch-action: manipulation` on interactive elements
**File:** `jobs/templates/jobs/base.html` (global styles)

```css
a, button, [role="button"], input, select, textarea { touch-action: manipulation; }
```

Prevents double-tap zoom delay on mobile.

### 21.3 `overscroll-behavior: contain` on modals
**File:** `jobs/templates/jobs/base.html` (global styles)

```css
.modal { overscroll-behavior: contain; }
```

### 21.4 `text-wrap: balance` on headings
**File:** `jobs/templates/jobs/base.html` (global styles)

```css
h1, h2, h3 { text-wrap: balance; }
```

### 21.5 Non-breaking spaces between values and units
**Files:** Console templates (dashboard, stats, cleanup)

Use `&nbsp;` between numbers and units: `{{ value }}&nbsp;GB`, `{{ count }}&nbsp;MB`, etc.

### 21.6 Use `…` character instead of `...`
**Files:** All templates

Replace all `...` in user-facing text with `…`.

---

## Verification (Phases 18-21)

1. **Accessibility:** Use browser devtools or axe-core to verify skip link, aria-live announcements, focus rings, and no bare `outline: none`
2. **Forms:** Test submit spinners, beforeunload warnings, login autocomplete
3. **Theme:** Verify `color-scheme` property and `theme-color` meta update on toggle
4. **Reduced motion:** Enable OS "Reduce motion" setting and verify animations suppressed
5. **Mobile:** Confirm no double-tap delay, modal scroll containment
6. **Visual:** Verify tabular number alignment in tables
