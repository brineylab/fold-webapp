# Repository Guidelines

## Project Structure & Module Organization

- `bioportal/` holds the Django project settings, root URLs, and WSGI entry point.
- `jobs/` contains the user-facing job submission app, including models, views, forms, and templates under `jobs/templates/jobs/`.
- `console/` is the staff-only operations console, with service modules in `console/services/` and templates in `console/templates/console/`.
- `model_types/` defines model-type contracts and the registry used to drive model-specific UX and input normalization.
- `runners/` provides pluggable SLURM runner stubs (AlphaFold, Boltz, Chai) and registration helpers.
- `templates/` includes shared site templates (e.g., `templates/base.html`, login).
- `containers/` stores per-model Dockerfiles and shared assets; see `containers/README.md` for best practices.
- `manage.py`, `Dockerfile`, `docker-compose.yml`, and `Procfile` define local/dev/prod entry points.

## Build, Test, and Development Commands

- `python -m venv venv && source venv/bin/activate && pip install -r requirements.txt` sets up the local environment.
- `cp env.example .env` then edit `.env` (set `FAKE_SLURM=1` for local dev).
- `python manage.py migrate` initializes the database.
- `python manage.py createsuperuser` creates an admin account.
- `honcho start` runs the web server and job poller together (recommended).
- `python manage.py runserver` and `python manage.py poll_jobs` run them separately.
- `docker compose up -d --build` launches production-style services.
- `./scripts/build_image.sh <model> <tag> [--push]` builds and optionally pushes a model container.
- `make build-image MODEL=<model> TAG=<tag>` wraps the same build workflow.

## Coding Style & Naming Conventions

- Python follows standard Django conventions and PEP 8 (4-space indentation, snake_case).
- Templates are server-rendered Django HTML; keep blocks and template names aligned to their app (e.g., `jobs/templates/jobs/`).
- No formatter or linter is configured; keep edits consistent with existing files.
- When adding models, register a ModelType in `model_types/` and keep runner keys aligned with container image tags where possible.

## Testing Guidelines

- There is no test framework configured in this repository at the moment.
- If you add tests, prefer Django’s built-in `unittest` runner and document new commands in this file.

## Commit & Pull Request Guidelines

- Recent commit messages are short, imperative phrases (e.g., “Update README.md”); follow that style.
- PRs should include a concise description of changes, steps to verify (commands run), and screenshots for UI changes.

## Configuration & Operations Notes

- SLURM integration is controlled by environment variables; set `FAKE_SLURM=1` to simulate SLURM locally.
- Job work directories live under `JOB_BASE_DIR` (default `./job_data`); keep paths stable for shared storage setups.
- Container best practices (tagging, pinning dependencies, build conventions) are documented in `containers/README.md`.
