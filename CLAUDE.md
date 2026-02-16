# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

fold-webapp is a Django intranet web UI for submitting protein structure prediction and design jobs to SLURM. Supported models: Boltz-2, Chai-1, ProteinMPNN, LigandMPNN, BindCraft, RFdiffusion3, BoltzGen. It provides both web and REST API interfaces.

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

# Other management commands
python manage.py cleanup_jobs --dry-run       # delete workdirs past retention
python manage.py detect_orphans --verbose     # find orphaned workdirs/jobs
python manage.py backup_db --output backup.db # SQLite hot backup
python manage.py create_api_key <username>    # create API key for user

# Production (Docker)
./deploy.sh install          # first-time setup
./deploy.sh start|stop|restart|status|logs
./deploy.sh update           # pull, rebuild, restart
./deploy.sh shell            # Django shell in container
docker compose up -d --build  # manual alternative

# Build model containers
make build-image MODEL=boltz2 TAG=dev
./scripts/build_image.sh <model> <tag> [--push]
```

## Architecture

### Two-Layer Abstraction: ModelType + Runner

The core design separates **product concerns** (ModelType) from **operations concerns** (Runner + RunnerConfig):

**ModelType** (`model_types/base.py` → `BaseModelType` ABC): Defines how a model appears to users — forms, validation, input normalization, workdir preparation, output rendering. Each model type has a `category` (Structure Prediction, Sequence Design, Protein Design) used to group models on the selection page. Registered in `model_types/__init__.py` via `register_model_type()`. The flow is: `get_form()` → `validate()` → `normalize_inputs()` → `resolve_runner_key()` → `prepare_workdir()`.

**Runner** (`runners/__init__.py` → `Runner` ABC): Generates the `sbatch` shell script for a specific computational tool. Registered via the `@register` decorator. Note: model type keys and runner keys are not always 1:1 — ProteinMPNN and LigandMPNN both resolve to the `ligandmpnn` runner (same container/script).

**RunnerConfig** (`console/models.py`): DB-stored SLURM resource settings (partition, GPUs, memory, time limit, container image) editable via Django admin. Auto-created on first access via `get_or_create`. Runners receive config in `build_script(job, config=None)`.

### Current Models and Runners

| Model Type Key | Runner Key | Category |
|---|---|---|
| `boltz2` | `boltz` | Structure Prediction |
| `chai1` | `chai` | Structure Prediction |
| `protein_mpnn` | `ligandmpnn` | Sequence Design |
| `ligand_mpnn` | `ligandmpnn` | Sequence Design |
| `bindcraft` | `bindcraft` | Protein Design |
| `rfdiffusion3` | `rfdiffusion3` | Protein Design |
| `boltzgen` | `boltzgen` | Protein Design |

### Job Submission Pipeline

`jobs/services.py:create_and_submit_job()` orchestrates the full flow:
1. Check maintenance mode → check runner enabled → check user quota
2. Create `Job` record (UUID primary key)
3. `ModelType.prepare_workdir()` writes input files to `JOB_BASE_DIR/<job_uuid>/input/`
4. `Runner.build_script()` generates sbatch script
5. `slurm.submit()` calls sbatch and stores SLURM job ID

### Container vs Host Paths

The app runs in Docker but SLURM runs on the host. Path settings handle this:
- `DATA_DIR` — root directory for all persistent data (DB, jobs, weight caches). Defaults to `./data`. All other data paths derive from this unless explicitly overridden.
- `JOB_BASE_DIR` — container path (e.g., `/app/data/jobs`)
- `JOB_BASE_DIR_HOST` — host path passed to sbatch `--chdir`

### Key Apps

- **`bioportal/`** — Django project settings, root URLs, WSGI
- **`jobs/`** — User-facing job submission, list, detail, cancel views (`@login_required`)
- **`console/`** — Staff-only operations console (quotas, settings, monitoring). Views split into `console/views/`, services in `console/services/`
- **`api/`** — REST API v1 with bearer token auth (`@api_auth_required` decorator). API access is opt-in per user (`UserQuota.api_enabled`). See `api/README.md` for endpoint docs
- **`model_types/`** — ModelType registry and implementations
- **`runners/`** — Runner registry and SLURM script generators
- **`slurm.py`** — Root-level module for SLURM submit/check_status/cancel with FAKE_SLURM dev mode
- **`containers/`** — Per-model Dockerfiles

### Console Models

- **`UserQuota`** — Per-user limits (concurrent jobs, queued jobs, daily limit, retention days) + `api_enabled` flag + account disable capability
- **`SiteSettings`** — Singleton (`pk=1`) for maintenance mode toggle
- **`RunnerConfig`** — Per-runner SLURM resources and container overrides, with `enabled`/`disabled_reason` to gate individual runners

### FAKE_SLURM Mode

Set `FAKE_SLURM=1` in `.env` for local dev. Jobs auto-transition: PENDING (5s) → RUNNING (15s) → COMPLETED. No real SLURM needed.

### Job Status Polling

The `poll_jobs` management command runs in a loop (via honcho or Docker poller service), checking SLURM state every 10 seconds for all active jobs. Uses squeue for active jobs, falls back to sacct then scontrol for completed jobs.

## Adding a New Model

1. Create `model_types/<model_key>.py` — subclass `BaseModelType`, implement `validate()`, `normalize_inputs()`, `resolve_runner_key()`, set `category`. Optionally override `prepare_workdir()` and `get_output_context()`
2. Register in `model_types/__init__.py` via `register_model_type()`
3. Create `runners/<runner_key>.py` — subclass `Runner`, implement `build_script()`, decorate with `@register` (skip if reusing an existing runner)
4. Create form class in `jobs/forms.py`
5. Create template `jobs/templates/jobs/submit_<model_key>.html` (extends `submit_base.html`)
6. Add container image setting to `bioportal/settings.py` (e.g., `BOLTZ_IMAGE`)

## Code Style

- Python: PEP 8, 4-space indentation, snake_case
- Server-rendered Django templates (no JS framework)
- No formatter or linter configured — match existing style
- Models use `django-simple-history` for audit logging (`HistoricalRecords()`)
- Commit messages: short imperative phrases
