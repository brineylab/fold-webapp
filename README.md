# fold-webapp

Fold is a Django web app plus a local Docker-backed worker for protein
structure prediction and design on a single host. The current runtime is
always the local Docker executor: Django stores jobs in SQLite, the worker pulls
queued jobs from the database, and each running job launches a model container
directly with `docker run`.

## Start Here

For a new install, use `./deploy.sh` and Docker Compose. That is the shortest
path from a fresh checkout to a running, prewarmed, smoke-tested deployment.

### Requirements

- Linux host with Docker Engine and the Docker Compose v2 plugin
- Python 3 on the host
- NVIDIA drivers plus Docker GPU support
- Outbound network access for image pulls and weight downloads
- Enough disk space for app data, model images, and weight caches under
  `DATA_DIR`

Confirm Docker can see a GPU before you start:

```bash
docker run --rm --gpus all nvidia/cuda:12.8.0-base-ubuntu22.04 nvidia-smi
```

## Zero To Running, Prewarmed, Validated

### 1. Clone the repo

```bash
git clone https://github.com/brineylab/fold-webapp
cd fold-webapp
```

### 2. Install and start the app

```bash
./deploy.sh install
```

`install` does the following:

- Copies `env.example` to `.env` if `.env` does not already exist
- Generates a fresh `SECRET_KEY`
- Sets `DEBUG=false`
- Prompts for `ALLOWED_HOSTS` and `DATA_DIR`
- Sets `APP_UID`, `APP_GID`, and `HARNESS_BASE_DIR`
- Creates the data directories and cache directories
- Builds the web image and starts the `migrate`, `web`, and `worker` services
- Optionally prompts you to create a Django superuser

If you skip superuser creation during install, create one later with:

```bash
./deploy.sh createsuperuser
```

### 3. Review `.env`

For most new installs, these are the only settings you need to touch:

| Variable | What to check |
| --- | --- |
| `ALLOWED_HOSTS` | Add the hostname or IP address users will connect to |
| `DATA_DIR` | Persistent root for the database, jobs, harness runs, and caches |
| `GPU_SLOTS` | Comma-separated GPU indices the worker may use; new installs default to `0` |
| `BOLTZ_IMAGE`, `CHAI_IMAGE`, `LIGANDMPNN_IMAGE`, `BINDCRAFT_IMAGE`, `RFDIFFUSION3_IMAGE`, `BOLTZGEN_IMAGE` | Override these if you pin custom tags or use a private registry |

`./deploy.sh install` defaults `DATA_DIR` to `$HOME/.fold-webapp/data` and
keeps it writable by the installing user.

### 4. Prewarm model images and caches

```bash
./deploy.sh prewarm
```

Prewarming prepares the deployment for real traffic by:

- Pulling each model image, or building it locally if no registry image is
  available
- Rebuilding the main web image
- Downloading weight caches for Boltz-2, Chai-1, and BoltzGen

For script details and troubleshooting, see
[`scripts/PREWARM_README.md`](scripts/PREWARM_README.md).

### 5. Run the smoke harness

```bash
./deploy.sh validate-models --tier smoke
```

This is the canonical post-install test. It exercises the live app and the
model runners, then writes reports under:

```text
HARNESS_BASE_DIR/runs/<run_id>/reports/
```

The main human-readable report is:

```text
HARNESS_BASE_DIR/runs/<run_id>/reports/summary.md
```

For harness phases, reports, and single-case runs, see
[`scripts/MODEL_HARNESS.md`](scripts/MODEL_HARNESS.md).

### 6. Log in

Open `http://localhost:8000`.

- The main user UI is at `/`
- Staff users can access the Ops Console at `/console/`
- API clients can discover models at `/api/v1/models/`

## What Success Looks Like

After the steps above:

- `./deploy.sh status` shows the `web` and `worker` containers running
- You can log in with the superuser you created
- `./deploy.sh validate-models --tier smoke` exits successfully
- The harness summary report shows all smoke cases passing
- First real jobs do not need to pull large images or download fresh weights

## Runtime Model

- The Compose deployment runs three services: `migrate`, `web`, and `worker`
- `web` serves Django through Gunicorn on port `8000`
- `worker` runs `python manage.py run_job_worker --interval 10`
- The worker launches model containers directly against the host Docker daemon
- Each running job consumes one GPU slot from `GPU_SLOTS`
- Persistent state lives under `DATA_DIR`
- Job workdirs live under `JOB_BASE_DIR/<job_uuid>/`
- Harness artifacts live under `HARNESS_BASE_DIR/runs/<run_id>/`
- There is no scheduler bridge, poller, SLURM sidecar, or host/container path
  translation layer

## Supported Models

| Model key | UI name | Runner key | Image variable |
| --- | --- | --- | --- |
| `boltz2` | Boltz-2 | `boltz-2` | `BOLTZ_IMAGE` |
| `chai1` | Chai-1 | `chai-1` | `CHAI_IMAGE` |
| `protein_mpnn` | ProteinMPNN | `ligandmpnn` | `LIGANDMPNN_IMAGE` |
| `ligand_mpnn` | LigandMPNN | `ligandmpnn` | `LIGANDMPNN_IMAGE` |
| `bindcraft` | BindCraft | `bindcraft` | `BINDCRAFT_IMAGE` |
| `rfdiffusion3` | RFdiffusion3 | `rfdiffusion3` | `RFDIFFUSION3_IMAGE` |
| `boltzgen` | BoltzGen | `boltzgen` | `BOLTZGEN_IMAGE` |

ProteinMPNN and LigandMPNN are separate model types in the UI and API, but they
share the same runner and container image.

## Common Operations

```bash
./deploy.sh start
./deploy.sh stop
./deploy.sh restart
./deploy.sh status
./deploy.sh logs
./deploy.sh logs web
./deploy.sh shell
./deploy.sh createsuperuser
./deploy.sh prewarm
./deploy.sh validate-models --tier smoke
./deploy.sh backup
./deploy.sh restore <backup-archive>
./deploy.sh update
```

Model images can also be built explicitly:

```bash
./scripts/build_image.sh <model> <tag> [--push]
make build-image MODEL=<model> TAG=<tag>
```

## Development Workflow

Development uses the same local Docker executor, but runs Django directly on
the host:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp env.example .env
python manage.py migrate
python manage.py createsuperuser
honcho start
```

`honcho start` runs:

- `web`: `python manage.py runserver 0.0.0.0:8000`
- `worker`: `python manage.py run_job_worker --interval 10`

You can also run them separately with `python manage.py runserver` and
`python manage.py run_job_worker --interval 10`.

## Further Reading

- [`DEPLOY.md`](DEPLOY.md) for the full deployment and operations reference
- [`scripts/PREWARM_README.md`](scripts/PREWARM_README.md) for prewarm behavior
  and troubleshooting
- [`scripts/MODEL_HARNESS.md`](scripts/MODEL_HARNESS.md) for validation harness
  phases and reports
- [`harness/README.md`](harness/README.md) for the fixture manifest used by the
  harness
- [`deploy/systemd/`](deploy/systemd/) for the advanced host-run systemd layout
