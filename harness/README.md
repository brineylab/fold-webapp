# Model Harness Fixtures

This directory holds the canonical post-install validation manifest and the
small fixture files that drive it.

## Layout

- `cases.yaml`: source of truth for smoke and extended harness scenarios
- `fixtures/common/`: tiny reusable FASTA and structure inputs
- `fixtures/<model>/`: model-specific uploaded files such as YAML, CSV, and JSON

## Rules

- Keep fixtures intentionally small and deterministic.
- Prefer PDB files for shared structural inputs unless a model path requires a
  different format.
- Each registered submittable model must have exactly one `tier: smoke` case.
- Extended cases should exercise validation, normalization, and workdir
  branches without turning every run into a full compute workload.

## Adding Coverage

1. Add any new fixture files under `fixtures/`.
2. Add a case entry to `cases.yaml`.
3. Keep smoke coverage one-to-one with submittable model types.
4. Update the harness tests if the manifest contract changes.
