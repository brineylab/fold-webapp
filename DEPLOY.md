# Deployment Guide

Fold has one runtime model: the local Docker executor. Regardless of whether
you package the control plane with Docker Compose or run Django directly on the
host, queued jobs are launched as `docker run` commands against the host Docker
daemon. The old scheduler bridge, poller, and SLURM deployment path are gone.

## Deployment Modes

- Recommended: `./deploy.sh` plus Docker Compose on a single host
- Advanced: host-run Django web and worker services managed by systemd, using
  the same Docker executor underneath

If you are setting up a new host, start with the Compose path.

## Prerequisites

- Docker Engine
- Docker Compose v2 (`docker compose version`)
- Python 3 on the host
- NVIDIA drivers plus Docker GPU support
- A writable persistent data path for `DATA_DIR`

Recommended smoke checks before the first install:

```bash
docker info
docker compose version
docker run --rm --gpus all nvidia/cuda:12.8.0-base-ubuntu22.04 nvidia-smi
```

## Recommended: Single-Host Compose Deployment

### Install

From the repo root:

```bash
./deploy.sh install
```

`install` is interactive. On a fresh checkout it:

- Creates `.env` from `env.example`
- Generates `SECRET_KEY`
- Prompts for `ALLOWED_HOSTS`
- Prompts for `DATA_DIR`
- Sets `APP_UID` and `APP_GID` to the installing user's uid/gid
- Sets `HARNESS_BASE_DIR` to `$DATA_DIR/harness`
- Creates the data and cache directories
- Runs `docker compose build`
- Runs `docker compose up -d`
- Offers to create a superuser

If `.env` already exists, it is preserved unless you rerun with `--force`:

```bash
./deploy.sh install --force
```

### Service Layout

The Compose deployment starts these services:

| Service | What it runs | Purpose |
| --- | --- | --- |
| `migrate` | `python manage.py migrate --noinput` | One-shot schema migration step |
| `web` | `gunicorn bioportal.wsgi:application --bind 0.0.0.0:8000 --workers 2` | User UI, API, admin, and Ops Console |
| `worker` | `python manage.py run_job_worker --interval 10` | Queue dispatch and reconciliation loop |

Both `web` and `worker` mount `DATA_DIR` at the same absolute host path inside
the container and bind `/var/run/docker.sock`. That is what allows the worker
to launch model containers with host-visible bind mounts.

### Post-Install Workflow

For a new deployment, the normal sequence is:

```bash
./deploy.sh install
./deploy.sh prewarm
./deploy.sh validate-models --tier smoke
```

Use `./deploy.sh createsuperuser` if you skipped admin creation during install.

### Data Layout

With the default `deploy.sh` path, the data root is `$HOME/.fold-webapp/data`.

Important subpaths:

- `DATA_DIR/db/db.sqlite3`: SQLite database
- `DATA_DIR/jobs/`: job workdirs, attempt logs, and model caches
- `DATA_DIR/jobs/boltz_cache`: Boltz-2 weights
- `DATA_DIR/jobs/chai_cache`: Chai-1 weights
- `DATA_DIR/jobs/boltzgen_cache`: BoltzGen weights
- `DATA_DIR/harness/`: validation harness runs and reports

`JOB_BASE_DIR`, `HARNESS_BASE_DIR`, and `DATABASE_PATH` are derived from
`DATA_DIR` unless you override them explicitly.

## Configuration Reference

### Core Settings

| Variable | Meaning | Notes |
| --- | --- | --- |
| `DEBUG` | Django debug mode | `deploy.sh install` sets this to `false` |
| `SECRET_KEY` | Django secret key | Generated during `install` |
| `ALLOWED_HOSTS` | Comma-separated hostnames and IPs | Must include the host users connect to |
| `DATA_DIR` | Root for database, jobs, harness runs, and caches | New `deploy.sh` installs default to `$HOME/.fold-webapp/data` |
| `APP_UID` | Container runtime uid | Set by `deploy.sh install` |
| `APP_GID` | Container runtime gid | Set by `deploy.sh install` |
| `DATABASE_PATH` | SQLite database file path | Usually left derived from `DATA_DIR` |
| `JOB_BASE_DIR` | Root for job workdirs and caches | Usually left derived from `DATA_DIR` |
| `HARNESS_BASE_DIR` | Root for harness run artifacts | Usually left derived from `DATA_DIR` |
| `GPU_SLOTS` | Comma-separated GPU indices available to the worker | New installs default to `0` |

### Model Image Selection

| Variable | Used by |
| --- | --- |
| `BOLTZ_IMAGE` | Boltz-2 |
| `CHAI_IMAGE` | Chai-1 |
| `LIGANDMPNN_IMAGE` | ProteinMPNN and LigandMPNN |
| `BINDCRAFT_IMAGE` | BindCraft |
| `RFDIFFUSION3_IMAGE` | RFdiffusion3 |
| `BOLTZGEN_IMAGE` | BoltzGen |

### Weight Cache Locations

| Variable | Meaning |
| --- | --- |
| `BOLTZ_CACHE_DIR` | Boltz-2 weight cache |
| `CHAI_CACHE_DIR` | Chai-1 weight cache |
| `BOLTZGEN_CACHE_DIR` | BoltzGen weight cache |

### Container Runtime Tuning

| Variable | Meaning |
| --- | --- |
| `DOCKER_DEFAULT_SHM_SIZE` | Default `--shm-size` for GPU model containers |
| `DOCKER_DEFAULT_IPC_MODE` | Default `--ipc` mode for GPU model containers |
| `BOLTZ_DOCKER_SHM_SIZE` | Boltz-2 specific shared memory setting |
| `BOLTZ_DOCKER_IPC_MODE` | Boltz-2 specific IPC setting |
| `CHAI_DOCKER_SHM_SIZE` | Chai-1 specific shared memory setting |
| `CHAI_DOCKER_IPC_MODE` | Chai-1 specific IPC setting |
| `LIGANDMPNN_DOCKER_SHM_SIZE` | ProteinMPNN and LigandMPNN shared memory setting |
| `LIGANDMPNN_DOCKER_IPC_MODE` | ProteinMPNN and LigandMPNN IPC setting |
| `BINDCRAFT_DOCKER_SHM_SIZE` | BindCraft shared memory setting |
| `BINDCRAFT_DOCKER_IPC_MODE` | BindCraft IPC setting |
| `RFDIFFUSION3_DOCKER_SHM_SIZE` | RFdiffusion3 shared memory setting |
| `RFDIFFUSION3_DOCKER_IPC_MODE` | RFdiffusion3 IPC setting |
| `BOLTZGEN_DOCKER_SHM_SIZE` | BoltzGen shared memory setting |
| `BOLTZGEN_DOCKER_IPC_MODE` | BoltzGen IPC setting |

### Default User Policy Settings

| Variable | Meaning |
| --- | --- |
| `DEFAULT_MAX_CONCURRENT_JOBS` | Default running-job quota for new non-staff users |
| `DEFAULT_MAX_QUEUED_JOBS` | Default queued-job quota for new non-staff users |
| `DEFAULT_JOBS_PER_DAY` | Default daily submission quota for new non-staff users |
| `DEFAULT_RETENTION_DAYS` | Default workdir retention period for new non-staff users |

## Operations

| Command | What it does |
| --- | --- |
| `./deploy.sh start` | Starts the Compose services |
| `./deploy.sh stop` | Stops the Compose services |
| `./deploy.sh restart` | Restarts the Compose services |
| `./deploy.sh status` | Shows `docker compose ps` output |
| `./deploy.sh logs [service]` | Follows logs for all services or one named service |
| `./deploy.sh shell` | Opens a Django shell in the `web` container |
| `./deploy.sh createsuperuser` | Creates a Django admin user in the running deployment |
| `./deploy.sh prewarm [opts]` | Pulls or builds images and downloads model weights |
| `./deploy.sh download-weights [model]` | Downloads weight caches without rebuilding images |
| `./deploy.sh validate-models [opts]` | Runs the post-install validation harness |
| `./deploy.sh backup [opts]` | Creates a backup archive of DB, jobs, and `.env` |
| `./deploy.sh restore <archive>` | Restores from a backup archive |
| `./deploy.sh update` | Runs `git pull`, rebuilds images, and restarts services |
| `./deploy.sh adopt-single-user-layout` | Migrates an existing install into the single-user data layout |
| `./deploy.sh destroy` | Stops containers and deletes the data dir, harness dir, images, and `.env` after confirmation |

Notes:

- `backup` uses the safe SQLite backup command when the `web` container is
  running, and falls back to a direct file copy when it is not.
- `restore` stops running services before restoring the database and job data.
- `destroy` is intentionally destructive and prompts for confirmation.

## Validation And Prewarm

- `./deploy.sh prewarm` prepares images and caches, but does not perform
  end-to-end submission testing
- `./deploy.sh validate-models --tier smoke` is the end-to-end post-install test
- Smoke reports are written under
  `HARNESS_BASE_DIR/runs/<run_id>/reports/summary.md`

See [`scripts/PREWARM_README.md`](scripts/PREWARM_README.md) and
[`scripts/MODEL_HARNESS.md`](scripts/MODEL_HARNESS.md) for script-level detail.

## Advanced: Host-Run Systemd Deployment

The systemd artifacts live under [`deploy/systemd/`](deploy/systemd/):

- `fold-webapp-web.service`
- `fold-webapp-worker.service`
- `fold-webapp.env.example`
- `fold-webapp.tmpfiles.conf`

Those files assume:

- Repo checkout at `/opt/fold-webapp`
- Virtualenv at `/opt/fold-webapp/.venv`
- Runtime user and group `fold`
- Environment file at `/etc/fold-webapp/fold-webapp.env`
- Persistent data under `/var/lib/fold-webapp`

If you use different paths or a different account, edit the unit files before
installing them.

### Minimal Host-Run Sequence

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
```

Then:

1. Copy `deploy/systemd/fold-webapp.env.example` to
   `/etc/fold-webapp/fold-webapp.env` and edit it.
2. Create the data and log directories from
   `deploy/systemd/fold-webapp.tmpfiles.conf`, or install that tmpfiles
   configuration.
3. Install the two service units.
4. Enable and start both units.

This path uses the same local Docker executor as Compose. Jobs still launch as
Docker containers on the same host.

## Troubleshooting

### Docker daemon unavailable

If `./deploy.sh install` fails early, run `docker info`. The installing user
must be able to talk to the Docker daemon.

### GPU not visible to Docker

If the `nvidia-smi` container probe fails, the app may still start, but real
GPU jobs and the smoke harness will fail. Fix Docker GPU support first.

### Smoke harness cannot write `HARNESS_BASE_DIR`

Executor validation needs host write access to `HARNESS_BASE_DIR`. If the
harness reports a write-permission problem, fix the directory ownership or
permissions and rerun the harness.

### Jobs fail with shared-memory or IPC errors

Raise `DOCKER_DEFAULT_SHM_SIZE` or the relevant per-model `*_DOCKER_SHM_SIZE`
setting. If a model specifically requires host IPC, set the matching
`*_DOCKER_IPC_MODE`.

### App reachable only on localhost

Check `ALLOWED_HOSTS`, firewall rules, and whether you are connecting to the
correct hostname or IP address.

## Removed Surfaces

These are no longer part of the deployment model:

- `SLURM`
- `FAKE_SLURM`
- `poll_jobs`
- `JOB_BASE_DIR_HOST`
- `HARNESS_BASE_DIR_HOST`
- Scheduler-specific mounts in `docker-compose.yml`
