# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

fold-webapp is a Django intranet web UI for submitting protein structure prediction jobs (AlphaFold, Boltz-2, Chai-1, ProteinMPNN, LigandMPNN) to SLURM. It provides both web and REST API interfaces.

## Development Commands

```bash
# Setup
python -m venv venv && source venv/bin/activate && pip install -r requirements.txt
cp env.example .env   # set FAKE_SLURM=1 for local dev

# Database
python manage.py migrate
python manage.py createsuperuser

# Run (recommended: web server + job poller together)
honcho start

# Run separately
python manage.py runserver        # web server
python manage.py poll_jobs        # single poll cycle (run in a loop with sleep 10)

# Tests
python manage.py test                          # all tests
python manage.py test jobs                     # single app
python manage.py test jobs.tests.TestClassName  # single test class

# Production (Docker)
./deploy.sh install          # first-time setup
./deploy.sh start|stop|restart|status|logs
docker compose up -d --build  # manual alternative

# Build model containers
make build-image MODEL=boltz2 TAG=dev
./scripts/build_image.sh <model> <tag> [--push]
```

## Architecture

### Two-Layer Abstraction: ModelType + Runner

The core design separates **product concerns** (ModelType) from **operations concerns** (Runner + RunnerConfig):

**ModelType** (`model_types/base.py` → `BaseModelType` ABC): Defines how a model appears to users — forms, validation, input normalization, workdir preparation, output rendering. Each model type is registered in `model_types/__init__.py`. The flow is: `get_form()` → `validate()` → `normalize_inputs()` → `resolve_runner_key()` → `prepare_workdir()`.

**Runner** (`runners/__init__.py` → `Runner` ABC): Generates the `sbatch` shell script for a specific computational tool. Registered via the `@register` decorator.

**RunnerConfig** (`console/models.py`): DB-stored SLURM resource settings (partition, GPUs, memory, time limit, container image) editable via Django admin. Runners receive config in `build_script(job, config=None)`.

### Job Submission Pipeline

`jobs/services.py:create_and_submit_job()` orchestrates the full flow:
1. Check maintenance mode → check runner enabled → check user quota
2. Create `Job` record (UUID primary key)
3. `ModelType.prepare_workdir()` writes input files to `JOB_BASE_DIR/<job_uuid>/input/`
4. `Runner.build_script()` generates sbatch script
5. `slurm.submit()` calls sbatch and stores SLURM job ID

### Container vs Host Paths

The app runs in Docker but SLURM runs on the host. Two path settings handle this:
- `JOB_BASE_DIR` — container path (e.g., `/app/data/jobs`)
- `JOB_BASE_DIR_HOST` — host path passed to sbatch `--chdir`

### Key Apps

- **`bioportal/`** — Django project settings, root URLs, WSGI
- **`jobs/`** — User-facing job submission, list, detail, cancel views
- **`console/`** — Staff-only operations console (quotas, settings, monitoring). Views split into `console/views/`, services in `console/services/`
- **`api/`** — REST API v1 with bearer token auth (`@api_auth_required` decorator). See `api/README.md` for endpoint docs
- **`model_types/`** — ModelType registry and implementations (boltz2, chai1, protein_mpnn, ligand_mpnn)
- **`runners/`** — Runner registry and SLURM script generators (boltz, chai, ligandmpnn, alphafold stub)
- **`slurm.py`** — Root-level module for SLURM submit/check_status/cancel with FAKE_SLURM dev mode
- **`containers/`** — Per-model Dockerfiles

### FAKE_SLURM Mode

Set `FAKE_SLURM=1` in `.env` for local dev. Jobs auto-transition: PENDING (5s) → RUNNING (15s) → COMPLETED. No real SLURM needed.

### Job Status Polling

The `poll_jobs` management command runs in a loop (via honcho or Docker poller service), checking SLURM state every 10 seconds for all active jobs. Uses squeue for active jobs, falls back to sacct then scontrol for completed jobs.

## Adding a New Model

1. Create `model_types/<model_key>.py` — subclass `BaseModelType`, implement `validate()`, `normalize_inputs()`, `resolve_runner_key()`, optionally override `prepare_workdir()` and `get_output_context()`
2. Register in `model_types/__init__.py` via `register_model_type()`
3. Create `runners/<runner_key>.py` — subclass `Runner`, implement `build_script()`, decorate with `@register`
4. Create form class in `jobs/forms.py`
5. Create template `jobs/templates/jobs/submit_<model_key>.html` (extends `submit_base.html`)

## Code Style

- Python: PEP 8, 4-space indentation, snake_case
- Server-rendered Django templates (no JS framework)
- No formatter or linter configured — match existing style
- Models use `django-simple-history` for audit logging (`HistoricalRecords()`)
- Commit messages: short imperative phrases
