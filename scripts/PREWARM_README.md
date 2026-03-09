# Prewarming

`./deploy.sh prewarm` and `./scripts/prewarm.sh` prepare a deployment so the
first real jobs do not spend their time pulling images or downloading model
weights.

Prewarm is a readiness step. It is not a validation step. After prewarming,
run the smoke harness with `./deploy.sh validate-models --tier smoke`.

## What The Script Actually Does

Unless you skip a phase with flags, `scripts/prewarm.sh` does two things:

1. It prepares images.
2. It prepares weight caches.

### Image Preparation

For each model image, the script first tries `docker pull`. If that fails, it
falls back to a local `docker build` from the corresponding directory under
`containers/`.

It does this for:

- `BOLTZ_IMAGE`
- `CHAI_IMAGE`
- `LIGANDMPNN_IMAGE`
- `BINDCRAFT_IMAGE`
- `RFDIFFUSION3_IMAGE`
- `BOLTZGEN_IMAGE`

After the model images, it runs `docker compose build` for the main web app
image.

### Weight Preparation

The script then calls `scripts/download_weights.sh`, which downloads caches for:

- Boltz-2 into `BOLTZ_CACHE_DIR`
- Chai-1 into `CHAI_CACHE_DIR`
- BoltzGen into `BOLTZGEN_CACHE_DIR`

ProteinMPNN, LigandMPNN, BindCraft, and RFdiffusion3 do not have a separate
weight-download step in this script. Their runtime assets are expected to be
available in the image that was pulled or built.

## Requirements

- Docker Engine
- Docker Compose v2
- Network access for image pulls and weight downloads
- Writable cache directories

The script also probes Docker GPU access and prints a warning if GPUs are not
available. That warning is informational for prewarming itself: the explicit
weight-download steps do not require a GPU. Real jobs and the smoke harness do.

## Usage

### Recommended

```bash
./deploy.sh prewarm
```

### Direct

```bash
./scripts/prewarm.sh
```

If `.env` exists, the script reads configuration from it. If `.env` does not
exist, it falls back to `env.example`. In that fallback case, `DATA_DIR`
defaults to `./data` inside the repo.

## Options

```bash
./scripts/prewarm.sh --skip-images
./scripts/prewarm.sh --skip-weights
./scripts/prewarm.sh --registry registry.example.com
```

### `--skip-images`

Skip image pulls and builds. Use this when the needed images are already
present locally and you only want to refresh weight caches.

### `--skip-weights`

Skip `scripts/download_weights.sh`. Use this when images are the only thing you
want to refresh.

### `--registry`

Prefix every configured image name with a registry URL.

Example:

- If `BOLTZ_IMAGE=brineylab/boltz2:latest`
- And you run `./scripts/prewarm.sh --registry registry.example.com`
- The script will use `registry.example.com/brineylab/boltz2:latest`

This flag prefixes the image name that is already present in `.env`; it does
not replace it.

## Model And Cache Mapping

| Model surface | Image variable | Cache variable | Separate download step |
| --- | --- | --- | --- |
| Boltz-2 | `BOLTZ_IMAGE` | `BOLTZ_CACHE_DIR` | Yes |
| Chai-1 | `CHAI_IMAGE` | `CHAI_CACHE_DIR` | Yes |
| ProteinMPNN and LigandMPNN | `LIGANDMPNN_IMAGE` | None | No |
| BindCraft | `BINDCRAFT_IMAGE` | None | No |
| RFdiffusion3 | `RFDIFFUSION3_IMAGE` | None | No |
| BoltzGen | `BOLTZGEN_IMAGE` | `BOLTZGEN_CACHE_DIR` | Yes |

## Typical Workflow

```bash
./deploy.sh install
./deploy.sh prewarm
./deploy.sh validate-models --tier smoke
```

If prewarm succeeds and the smoke harness passes, the deployment is both warmed
and tested.

## Troubleshooting

### Image pull fails

This is not automatically fatal. The script already falls back to a local build
from `containers/<model>/` when a pull fails.

If you intended to pull from a private registry, confirm that:

- The registry prefix passed to `--registry` is correct
- You are logged in to that registry
- The image names in `.env` point at the expected repository and tag

### Weight download fails

Common causes:

- No outbound network access
- Cache directory permissions
- The referenced image does not contain the expected runtime package

Useful retries:

```bash
./scripts/prewarm.sh --skip-images
./scripts/download_weights.sh
./scripts/download_weights.sh boltz2 --overwrite
```

### GPU probe warns

If you see a warning that Docker cannot access a GPU, prewarm may still finish.
That does not mean the deployment is ready for real inference jobs. Fix GPU
access before running the smoke harness or accepting user traffic.

### Cache directory permissions

The weight-download helpers require writable cache directories. By default those
live under `DATA_DIR/jobs/`. Ensure the account running the script can create
and write those directories.

## Related Docs

- [`../README.md`](../README.md) for the end-to-end install path
- [`../DEPLOY.md`](../DEPLOY.md) for runtime configuration and operations
- [`MODEL_HARNESS.md`](MODEL_HARNESS.md) for the post-install validation harness
