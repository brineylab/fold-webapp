# Deployment Guide

Fold now runs jobs through the local Docker executor. The old SLURM deployment path has been removed.

## Recommended Runtime

Use the host-run control plane described by the systemd artifacts in [`deploy/systemd/`](deploy/systemd):

- [`deploy/systemd/fold-webapp-web.service`](deploy/systemd/fold-webapp-web.service)
- [`deploy/systemd/fold-webapp-worker.service`](deploy/systemd/fold-webapp-worker.service)
- [`deploy/systemd/fold-webapp.env.example`](deploy/systemd/fold-webapp.env.example)
- [`deploy/systemd/fold-webapp.tmpfiles.conf`](deploy/systemd/fold-webapp.tmpfiles.conf)

That layout runs:

- Django on the host
- the queue worker on the host
- model workloads in Docker containers launched by the worker

## Minimal Host Setup

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt

cp env.example .env
# Edit ALLOWED_HOSTS, SECRET_KEY, DATA_DIR, GPU_SLOTS, and any image overrides.

python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 0.0.0.0:8000
python manage.py run_job_worker --interval 10
```

## Docker Compose

`docker compose up -d --build` remains available as a packaging path for the web app itself. It runs:

- `migrate`
- `web`
- `worker`

The runtime model is still the same local Docker executor. There is no scheduler bridge, poller, or SLURM sidecar to configure. Compose mounts `DATA_DIR` at the same absolute host path inside the containers and exposes the host Docker socket so `run_job_worker` and job cancellation can launch and stop runner containers directly.

## Validation

Run the post-install harness with:

```bash
./deploy.sh validate-models --tier smoke
```

Reports are written under `HARNESS_BASE_DIR/runs/<run_id>/reports/`.

## Removed Surfaces

These are no longer part of deployment:

- `setup-slurm`
- `FAKE_SLURM`
- `JOB_EXECUTION_BACKEND`
- `JOB_BASE_DIR_HOST`
- `HARNESS_BASE_DIR_HOST`
- scheduler binary mounts in `docker-compose.yml`
