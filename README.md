# fold-webapp

Minimal intranet web UI for submitting protein structure prediction and design jobs to a local Docker-backed worker queue.

## Development

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp env.example .env
# Edit .env and set GPU_SLOTS to the host GPU indices the worker may use.

python manage.py migrate
python manage.py createsuperuser
honcho start
```

`honcho start` runs both long-lived processes:

- `web`: `python manage.py runserver 0.0.0.0:8000`
- `worker`: `python manage.py run_job_worker --interval 10`

You can also run them separately with `python manage.py runserver` and `python manage.py run_job_worker --interval 10`.

## Deployment

The supported runtime is the local Docker executor:

- Django manages the queue in the database.
- `run_job_worker` dispatches queued jobs directly to `docker run`.
- Each job uses one configured GPU slot.
- `SLURM`, `FAKE_SLURM`, `poll_jobs`, and host/container path translation are no longer part of the runtime.

For host-run deployments, use the systemd artifacts under [`deploy/systemd/`](deploy/systemd).

For containerized deployments, `docker compose up -d --build` starts:

- `migrate`
- `web`
- `worker`

## Common Commands

```bash
./deploy.sh install
./deploy.sh start
./deploy.sh stop
./deploy.sh restart
./deploy.sh status
./deploy.sh logs
./deploy.sh shell
./deploy.sh createsuperuser
./deploy.sh validate-models --tier smoke
```

Model images are built separately:

```bash
make build-image MODEL=boltz2 TAG=dev
./scripts/build_image.sh <model> <tag> [--push]
```

## Validation Harness

Run the acceptance harness against a live deployment with:

```bash
./deploy.sh validate-models --tier smoke
```

Harness artifacts are written under `HARNESS_BASE_DIR/runs/<run_id>/reports/`.

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `DEBUG` | Enable debug mode | `false` |
| `SECRET_KEY` | Django secret key | `dev-key-change-in-production` |
| `ALLOWED_HOSTS` | Comma-separated hostnames | `localhost,127.0.0.1` |
| `DATA_DIR` | Root directory for persistent runtime data | `$HOME/.fold-webapp/data` |
| `APP_UID` | App container runtime UID | installing user UID |
| `APP_GID` | App container runtime GID | installing user GID |
| `DATABASE_PATH` | Path to SQLite database file | `$DATA_DIR/db/db.sqlite3` |
| `JOB_BASE_DIR` | Directory for job working files | `$DATA_DIR/jobs` |
| `HARNESS_BASE_DIR` | Directory for harness runs | `$DATA_DIR/harness` |
| `GPU_SLOTS` | Comma-separated GPU indices available to the worker | `0` |
| `BOLTZ_IMAGE` | Boltz-2 container image | `brineylab/boltz2:latest` |
| `CHAI_IMAGE` | Chai-1 container image | `brineylab/chai1:latest` |
| `LIGANDMPNN_IMAGE` | LigandMPNN container image | `brineylab/ligandmpnn:latest` |
| `BINDCRAFT_IMAGE` | BindCraft container image | `brineylab/bindcraft:latest` |
| `RFDIFFUSION3_IMAGE` | RFdiffusion3 container image | `brineylab/rfdiffusion3:latest` |
| `BOLTZGEN_IMAGE` | BoltzGen container image | `brineylab/boltzgen:latest` |

## Notes

- Job workdirs live under `JOB_BASE_DIR/<job_uuid>/`.
- The current runtime is always the local Docker executor.
- `RunnerConfig` now exposes only runner enable/disable state plus an optional image override.
- Use Django admin for generic user/account edits; the console is focused on queue, policy, cleanup, and reporting.
- The worker command `python manage.py run_job_worker --interval 10` is the canonical long-lived queue process.
