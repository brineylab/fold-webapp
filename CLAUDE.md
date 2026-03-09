# CLAUDE.md

This repository is a Django intranet app for submitting protein structure prediction and design jobs to a local Docker-backed worker queue.

## Development

```bash
python -m venv venv && source venv/bin/activate && pip install -r requirements.txt
cp env.example .env
python manage.py migrate
python manage.py createsuperuser
honcho start
```

Long-lived processes:

- `web`: `python manage.py runserver`
- `worker`: `python manage.py run_job_worker --interval 10`

## Architecture

- `ModelType` handles forms, validation, input normalization, workdir preparation, and output rendering.
- `Runner` emits the shell script the worker launches for a job.
- `RunnerConfig` stores only enable/disable state and an optional image override.
- `JobAttempt` stores runtime metadata for each launch attempt.
- The worker reconciles running attempts and dispatches queued jobs directly to `docker run`.

## Runtime Notes

- `SLURM`, `FAKE_SLURM`, `poll_jobs`, and host/container path translation were removed in Phase 4.
- Job workdirs live under `JOB_BASE_DIR/<job_uuid>/`.
- Harness artifacts live under `HARNESS_BASE_DIR/runs/<run_id>/`.
- Model image settings live in `bioportal/settings.py` and are overrideable via environment variables.

## Key Paths

- `jobs/`: user-facing submission, list, detail, and worker-facing lifecycle code
- `console/`: staff-only operations console
- `model_types/`: model-specific UX and normalization
- `runners/`: runtime script builders for model containers
- `deploy/systemd/`: recommended host-run deployment artifacts
