# Model Harness Fixtures

This directory holds the canonical post-install validation manifest and the
small fixture files that drive it.

## Layout

- `cases.yaml`: source of truth for smoke and extended harness scenarios
- `fixtures/common/`: tiny reusable FASTA and structure inputs
- `fixtures/<model>/`: model-specific uploaded files such as YAML, CSV, and JSON

## Rules

- Keep fixtures intentionally small and deterministic.
- Prefer small but realistic inputs over toy placeholders; chain IDs, residue
  references, ligands, and contigs in the manifest must be consistent with the
  fixtures they reference.
- Prefer PDB files for shared structural inputs unless a model path requires a
  different format.
- Each registered submittable model must have exactly one `tier: smoke` case.
- Smoke cases should represent the canonical executable install-validation run
  for each model and define explicit `artifact_checks` for result validation.
- Extended cases should exercise validation, normalization, and workdir
  branches without turning every run into a full compute workload.

## Adding Coverage

1. Add any new fixture files under `fixtures/`.
2. Add a case entry to `cases.yaml`.
3. For smoke cases, define model-aware `artifact_checks` instead of relying on
   filename globs alone.
4. Keep smoke coverage one-to-one with submittable model types.
5. Update the harness tests if the manifest contract changes.
