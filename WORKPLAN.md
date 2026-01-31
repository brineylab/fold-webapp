# ModelType + RunnerConfig API Spec and Implementation Plan

## Goal
Define a flexible, extensible API for model-specific UX, validation, and job execution that supports heterogeneous bio/ML tools (e.g., structure prediction, inverse folding), with a clean split between product-facing model types and ops/runtime configuration.

## Core Concepts

### ModelType (product/UX contract)
ModelType defines how a model appears to users, how inputs are collected/validated, and how outputs are presented.

**Key responsibilities**
- UX: submission forms, templates, help text, advanced options
- Input schema and validation
- Optional batch/config file parsing
- Output metadata (what files/links to present)

**Suggested interface (Python ABC / Protocol)**
```python
class ModelType(Protocol):
    key: str
    name: str
    description: str
    category: str  # e.g., "structure_prediction", "inverse_folding"

    # UX configuration
    template_name: str  # e.g., "jobs/submit/structure_prediction.html"
    form_class: Type[forms.Form]
    help_text: str

    # Input handling
    def validate(self, cleaned_data: dict) -> None: ...
    def normalize_inputs(self, cleaned_data: dict) -> dict: ...

    # Optional batch/config handling
    def parse_batch(self, upload: UploadedFile) -> list[dict]: ...
    def parse_config(self, upload: UploadedFile) -> dict: ...

    # Output handling
    def output_spec(self) -> dict: ...
```

### RunnerConfig (runtime/ops contract)
RunnerConfig defines how jobs run on the cluster. It should be data-driven and editable without code changes.

**Key responsibilities**
- Container image reference
- Resource requests (partition, GPUs, memory, time)
- Env vars, mounts, and entrypoint/args

**Suggested schema (DB or YAML)**
```yaml
key: boltz2
image_uri: docker://ghcr.io/org/boltz2:latest
partition: gpu
gpus: 1
cpus: 8
mem_gb: 32
time_limit: "02:00:00"
env:
  BOLTZ_CACHE: "/data/cache"
mounts:
  - source: /shared/models
    target: /models
  - source: /shared/jobs
    target: /jobs
entrypoint: ["/app/run_boltz.sh"]
args: ["--input", "/jobs/input.json", "--output", "/jobs/output"]
```

## API Structure

### Registry and discovery
- `model_types/` module with a registry and decorators
- Each ModelType registered by `key`
- Job submission view resolves model by `key` and uses its form/template

**Registry (example)**
```python
MODEL_TYPES: dict[str, ModelType] = {}

def register_model_type(model_type: ModelType) -> ModelType:
    MODEL_TYPES[model_type.key] = model_type
    return model_type

def get_model_type(key: str) -> ModelType:
    return MODEL_TYPES[key]
```

### Data model changes
- Add `model_key` to `Job` (or reuse runner key if aligned)
- Store `job_inputs` as JSON for normalized inputs
- Store `job_outputs` metadata for display

**Example fields**
- `Job.model_key: str`
- `Job.input_payload: JSONField`
- `Job.output_payload: JSONField`

## UX Flow

### Submission
1. User navigates to `/jobs/new/<model_key>/`.
2. View resolves ModelType, renders `template_name` with `form_class`.
3. On submit:
   - Form validates base fields.
   - `ModelType.validate()` enforces model-specific constraints.
   - If batch file is present, `parse_batch()` yields multiple payloads.
   - If config file is present, `parse_config()` merges into payload.
4. Job payload is normalized and stored as JSON.
5. Job submit calls runner with `RunnerConfig` matching `model_key`.

### Output display
- ModelType provides `output_spec()` to describe expected files, labels, and optional visualizations.
- UI uses this spec to render download links and summaries.

## Example ModelTypes

### 1) Structure Prediction: Boltz-2

**User UX goals**
- Simple: FASTA textarea for single sequence
- Advanced: optional config JSON upload
- Batch: optional multi-sequence FASTA file

**Form fields**
- `sequence_text` (textarea)
- `sequence_file` (file, optional)
- `config_file` (file, optional)
- `model_variant` (choice, optional)
- `use_templates` (bool, optional)

**Validation rules**
- Either `sequence_text` or `sequence_file` required
- `config_file` optional but must be valid JSON
- If batch file provided, it overrides single sequence

**Example ModelType outline**
```python
class Boltz2ModelType(ModelType):
    key = "boltz2"
    name = "Boltz-2"
    category = "structure_prediction"
    template_name = "jobs/submit/structure_prediction.html"
    form_class = Boltz2SubmitForm
    help_text = "Predict protein structure from FASTA sequences."

    def validate(self, cleaned_data):
        if not cleaned_data.get("sequence_text") and not cleaned_data.get("sequence_file"):
            raise ValidationError("Provide a sequence or upload a FASTA file.")

    def parse_batch(self, upload):
        # Parse multi-FASTA into list of payloads
        return parse_fasta_batch(upload)

    def parse_config(self, upload):
        return json.load(upload)

    def normalize_inputs(self, cleaned_data):
        # Produce a uniform input JSON
        return {
            "sequences": cleaned_data.get("sequences"),
            "params": {
                "model_variant": cleaned_data.get("model_variant"),
                "use_templates": cleaned_data.get("use_templates"),
            },
        }

    def output_spec(self):
        return {
            "primary": ["predicted_structure.pdb"],
            "aux": ["scores.json", "logs.txt"],
        }
```

### 2) Inverse Folding: ProteinMPNN

**User UX goals**
- Requires a backbone structure input (PDB)
- Optional constraints/positions file
- Optional batch of PDBs

**Form fields**
- `backbone_pdb` (file, required)
- `constraint_file` (file, optional)
- `batch_zip` (file, optional)
- `num_sequences` (int, default 1)
- `temperature` (float, default 0.1)

**Validation rules**
- Either single PDB or batch zip required
- Constraint file must match expected format if provided

**Example ModelType outline**
```python
class ProteinMPNNModelType(ModelType):
    key = "protein_mpnn"
    name = "ProteinMPNN"
    category = "inverse_folding"
    template_name = "jobs/submit/inverse_folding.html"
    form_class = ProteinMPNNForm
    help_text = "Design sequences for a given backbone structure."

    def validate(self, cleaned_data):
        if not cleaned_data.get("backbone_pdb") and not cleaned_data.get("batch_zip"):
            raise ValidationError("Provide a PDB or upload a batch ZIP.")

    def parse_batch(self, upload):
        return parse_zip_batch(upload)

    def normalize_inputs(self, cleaned_data):
        return {
            "backbone": cleaned_data.get("backbone_pdb"),
            "params": {
                "num_sequences": cleaned_data.get("num_sequences"),
                "temperature": cleaned_data.get("temperature"),
            },
        }

    def output_spec(self):
        return {
            "primary": ["designed_sequences.fasta"],
            "aux": ["scores.json", "logs.txt"],
        }
```

## Implementation Plan (Phased)

### Phase 1: Core API + Registry
1. Create `model_types/` module with registry and base protocol/ABC.
2. Add `model_key` to `Job` model and migrate.
3. Add JSON fields for `input_payload` and `output_payload` (if not already present).
4. Add model lookup and dispatch in submission view.

### Phase 2: Forms + Templates
1. Create base submission template `jobs/templates/jobs/submit/base.html`.
2. Add model-specific templates:
   - `jobs/templates/jobs/submit/structure_prediction.html`
   - `jobs/templates/jobs/submit/inverse_folding.html`
3. Add Django forms for Boltz-2 and ProteinMPNN.
4. Wire templates to the new ModelType implementations.

### Phase 3: RunnerConfig integration
1. Add `RunnerConfig` model or YAML loader.
2. Update job submission to resolve config by `model_key`.
3. Update `runners/` to accept config (image, args, env, mounts).
4. Update SLURM submit script builder to use config settings.

### Phase 4: Batch + Config parsing
1. Add shared parsing utilities (multi-FASTA, ZIP extraction).
2. Store normalized payloads per sub-job (batch).
3. Add UI hints for batch uploads and advanced config.

### Phase 5: Output presentation
1. Add `output_spec` renderer in job detail view.
2. Allow model types to attach custom post-processing.

## Open Questions
- Do you want RunnerConfig in DB (admin editable) or YAML (code-reviewed)?
- Should batch uploads create many jobs or one job with many tasks?
- Should advanced config files be stored verbatim and passed through, or normalized into JSON?

## Example URL and UX Mapping
- `/jobs/new/boltz2/` -> Structure prediction form (sequence + optional config)
- `/jobs/new/protein_mpnn/` -> Inverse folding form (PDB + constraints)
- `/jobs/<uuid>/` -> output rendered based on `output_spec`
