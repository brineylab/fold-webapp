# Containers

This directory holds per-model container recipes and shared build assets.

## Layout

- `containers/<model>/Dockerfile` - model-specific image definition
- `containers/shared/` - shared scripts or base assets
- `scripts/build_image.sh` - helper to build and optionally push images

## Conventions

- Tag images with immutable version tags (e.g., `boltz2:v1.2.0`).
- Update the corresponding RunnerConfig to reference the new tag or digest.
- Pin system packages and Python dependencies for reproducibility.

## Example build

```bash
./scripts/build_image.sh boltz2 v1.2.0
./scripts/build_image.sh protein_mpnn v0.1.0 --push
```

## Notes

- Keep model inputs/outputs consistent with the runtime contract defined in `WORKPLAN.md`.
- For GPU usage, prefer CUDA-compatible base images and document the required driver/CUDA versions.
