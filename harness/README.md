# Harness Fixtures And Manifest

This directory is the source of truth for the post-install validation harness.
It contains the canonical case manifest and the small fixture files used to
exercise real submission and executor flows.

This document is for maintainers editing the harness, not for operators running
it. Operators should start with [`../scripts/MODEL_HARNESS.md`](../scripts/MODEL_HARNESS.md).

## Layout

- `cases.yaml`: case manifest
- `fixtures/common/`: shared FASTA and structure inputs
- `fixtures/<model>/`: model-specific uploaded files such as YAML, CSV, and
  JSON fixtures

## Manifest Schema

Each entry in `cases.yaml` defines one harness case.

Required top-level fields:

| Field | Meaning |
| --- | --- |
| `id` | Stable case identifier used by the harness CLI and reports |
| `tier` | `smoke` or `extended` |
| `model_key` | Registered model type key such as `boltz2` or `protein_mpnn` |
| `transport` | How the case is exercised |
| `timeout_sec` | Maximum executor runtime for the case |
| `requires` | Feature requirements such as `gpu` |
| `fields` | Form or API field values |
| `files` | Uploaded fixture files keyed by field name |
| `artifact_checks` | Output validation rules |

### Canonical `transport` Values

Use these values for new cases:

- `web`
- `api`
- `executor`
- `prepare_only`

The loader still accepts a couple of compatibility aliases:

- `direct` becomes `executor`
- `materialize_only` becomes `prepare_only`

Do not use the aliases for new manifest entries.

### `fields`

`fields` holds the logical values sent to the model form or API.

Special case:

- A value of the form `{fixture_text: path/to/file}` loads the text content from
  `fixtures/` at runtime and uses that text as the field value

Everything else is passed through as a scalar, boolean, JSON-like structure, or
stringified value as appropriate for the selected transport.

### `files`

`files` maps upload field names to fixture paths under `fixtures/`.

Example:

```yaml
files:
  pdb_file: common/structures/1LQ7.pdb
```

### `artifact_checks`

`artifact_checks` is the modern output-validation contract. Each item supports:

| Field | Meaning |
| --- | --- |
| `patterns` | One or more glob patterns matched against output file names |
| `validator` | One of `text_nonempty`, `json`, `csv`, `fasta`, `structure_file`, or `zip_members` |
| `min_size_bytes` | Minimum acceptable size for a candidate output |
| `required_members` | For `zip_members`, archive members that must exist |

The harness succeeds only when each artifact check finds at least one matching
candidate that passes validation.

## Fixture Rules

- Keep fixtures intentionally small and deterministic
- Prefer realistic fixtures over placeholders
- Keep chain ids, residue references, ligand names, contigs, and other
  cross-file semantics consistent
- Prefer shared fixtures under `fixtures/common/` when possible
- Prefer PDB for shared structural fixtures unless a model path specifically
  requires another format

## Enforced Invariants

The harness loader and tests enforce the following:

- Every registered submittable model type has exactly one smoke case
- Every smoke case defines explicit `artifact_checks`
- Every `model_key` in the manifest maps to a registered model type
- `transport` must normalize to one of the valid transport modes
- Fixture files must parse according to their file type
- Some model-specific cases must also be semantically consistent with their
  referenced structures

That semantic validation currently includes checks such as:

- Existing target chains for BindCraft
- Valid chain and residue references for ProteinMPNN and LigandMPNN
- Ligand presence for LigandMPNN
- Valid target chain references for BoltzGen and RFdiffusion3 cases that depend
  on structure fixtures

## Adding Or Updating Cases

1. Add or update any needed files under `fixtures/`.
2. Add or edit the case in `cases.yaml`.
3. For smoke cases, define explicit `artifact_checks` that match the real
   expected outputs for that model.
4. Keep smoke coverage one-to-one with registered submittable model types.
5. Use canonical transport values for new entries.
6. Update tests if the manifest contract or fixture semantics change.

## Test Expectations

The harness-related tests live primarily in:

- `jobs/tests_harness.py`
- `jobs/tests_harness_validation.py`
- `jobs/tests_harness_submission.py`
- `jobs/tests_harness_http.py`

At a minimum, manifest or fixture changes should continue to satisfy the smoke
coverage and artifact-check invariants enforced there.
