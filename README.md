# fold-webapp

Minimal intranet web UI for submitting protein structure prediction jobs to a local Docker-backed queue.

The default runtime now uses the host-run Django app plus a database-backed worker that launches model containers directly. The legacy `SLURM` path remains available only as an explicit fallback pending phase 4 cleanup. Phase 0 artifacts for the target architecture live in [`docs/architecture/0001-host-run-control-plane.md`](docs/architecture/0001-host-run-control-plane.md) and [`docs/operations/PHASE0_HOST_RUNTIME.md`](docs/operations/PHASE0_HOST_RUNTIME.md).

## Quick Start (Development)

### Option 1: Using Honcho (Recommended)

Honcho manages all processes from a single command using the `Procfile`:

```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure environment
cp env.example .env
# Edit .env and confirm JOB_EXECUTION_BACKEND=local and GPU_SLOTS=0

# Run migrations and create admin user
python manage.py migrate
python manage.py createsuperuser

# Start all services (web server + job worker)
honcho start
```

This starts both the web server and the background job worker in a single terminal.

### Option 2: Manual (Separate Terminals)

If you prefer running processes separately:

```bash
# Terminal 1: Web server
python manage.py runserver

# Terminal 2: Job worker
python manage.py run_job_worker --interval 10
```

## Production Deployment (Docker Compose)

For a complete walkthrough starting from a vanilla Ubuntu installation — including NVIDIA drivers, Docker, Slurm, model containers, and pre-warming — see **[DEPLOY.md](DEPLOY.md)**.

The recommended way to deploy is with the `deploy.sh` script, which handles environment setup, Docker builds, migrations, and service management.

### First-Time Install

```bash
./deploy.sh install
```

This will:
1. Check that Docker and Docker Compose v2 are installed
2. Create `.env` from `env.example` with a generated `SECRET_KEY` and production defaults
3. Create the `DATA_DIR` directories for persistent storage (default: `~/.fold-webapp/data`)
4. Align the app container uid/gid to the installing user via `APP_UID` and `APP_GID`
5. Build the Docker image and start all services
6. Prompt you to create an admin (superuser) account

Re-running `install` is safe — it skips steps that are already done. Pass `--force` to regenerate `.env`.

### Managing Services

```bash
./deploy.sh start             # Start services
./deploy.sh stop              # Stop services
./deploy.sh restart           # Restart services
./deploy.sh status            # Show service status
./deploy.sh logs              # Tail all logs
./deploy.sh logs web          # Tail logs for a specific service
./deploy.sh update            # Pull latest code, rebuild, and restart
./deploy.sh shell             # Open a Django shell
./deploy.sh createsuperuser   # Create a new admin user
./deploy.sh validate-models   # Run the post-install model validation harness
./deploy.sh setup-slurm       # Configure Slurm on this host (requires sudo)
./deploy.sh adopt-single-user-layout  # Move an older install to the new home layout
```

Make targets are also available as shortcuts (e.g., `make start`, `make stop`, `make logs`).

### Backup and Restore

Create a backup (database, job data, and config):

```bash
./deploy.sh backup
```

Backups are saved to `./backups/` as timestamped `.tar.gz` archives. Old backups are automatically pruned after 30 days (configurable via `BACKUP_RETENTION` in `.env`).

The backup script can also be called directly for cron use:

```bash
# Cron example: daily backup at 2am
0 2 * * * /path/to/fold-webapp/scripts/backup.sh --quiet >> /var/log/fold-webapp-backup.log 2>&1
```

Restore from a backup:

```bash
./scripts/restore.sh backups/fold-webapp-backup-20250101_020000.tar.gz
```

The restore script will show a manifest, prompt for confirmation, stop services, and restore all data. Pass `--restore-env` to also restore the `.env` file, or `--yes` to skip the confirmation prompt.

### SLURM Integration

The `setup-slurm` command installs and configures Slurm on a single Ubuntu node, auto-detects hardware (CPUs, RAM, GPUs), and generates a `docker-compose.override.yml` that mounts Slurm binaries and config into the web/poller containers:

```bash
sudo ./deploy.sh setup-slurm
```

After setup, set `FAKE_SLURM=0` in `.env` and restart:

```bash
./deploy.sh restart
```

For manual configuration or multi-node clusters, you can instead uncomment the volume mounts in `docker-compose.yml` directly. See [`scripts/SLURM_README.md`](scripts/SLURM_README.md) for full details.

### Post-Install Validation Harness

After images, weights, and the deployed services are ready, run:

```bash
./deploy.sh validate-models --tier smoke
```

This validates the live HTTP/API surface, executes each registered web model once outside SLURM for easier debugging, and writes reports under `HARNESS_BASE_DIR_HOST/runs/<run_id>/reports/` on the host. Fresh installs place `HARNESS_BASE_DIR_HOST` under `DATA_DIR/harness`.

### Shared Storage

Fresh installs now optimize for a single-user deployment: `DATA_DIR` defaults to `~/.fold-webapp/data`, the web container runs with the installing user's uid/gid, and the harness lives under `DATA_DIR/harness`. For shared or multi-user setups, override `DATA_DIR`, `APP_UID`, `APP_GID`, and the host path variables explicitly.

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DEBUG` | Enable debug mode | `false` |
| `SECRET_KEY` | Django secret key | `dev-key-change-in-production` |
| `ALLOWED_HOSTS` | Comma-separated hostnames | `localhost,127.0.0.1` |
| `DATA_DIR` | Root directory for persistent runtime data | `$HOME/.fold-webapp/data` |
| `APP_UID` | App container runtime UID | installing user UID |
| `APP_GID` | App container runtime GID | installing user GID |
| `DATABASE_PATH` | Path to SQLite database file | `$DATA_DIR/db/db.sqlite3` |
| `JOB_BASE_DIR` | Directory for job working files | `$DATA_DIR/jobs` |
| `HARNESS_BASE_DIR_HOST` | Host directory for post-install harness runs | `$DATA_DIR/harness` |
| `FAKE_SLURM` | Legacy SLURM compatibility switch (`1` or `0`) | `0` |
| `JOB_EXECUTION_BACKEND` | Execution backend (`local` or `slurm`) | `local` |
| `GPU_SLOTS` | Comma-separated GPU indices available to the worker | `0` |
| `BACKUP_DIR` | Directory for backup archives | `./backups` |
| `BACKUP_RETENTION` | Days to keep old backups | `30` |

In Docker, `DATABASE_PATH`, `JOB_BASE_DIR`, and the harness path are set automatically by `docker-compose.yml` to use bind mounts under `DATA_DIR`. You typically do not need to set them yourself beyond choosing `DATA_DIR`.

If you change `APP_UID`, `APP_GID`, or `DATA_DIR` on an existing install, rebuild and recreate the services so the image and bind mounts pick up the new values:

```bash
docker compose up -d --build
```

## Architecture

```
┌─────────────────────────────────────────────────┐
│  Web Server (Django)                            │
│  ┌──────────────┐  ┌───────────────┐            │
│  │  web         │  │  worker       │            │
│  │  (gunicorn)  │  │  (job loop)   │            │
│  └──────┬───────┘  └──────┬────────┘            │
│         │                 │                     │
│         └────────┬────────┘                     │
│                  │ sbatch / squeue / sacct      │
└──────────────────┼──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│  SLURM Jobs                                     │
│  ┌─────────────────────────────────────────┐    │
│  │  Model Runners                          │    │
│  │  (AlphaFold, Boltz, Chai, etc)          │    │
│  └─────────────────────────────────────────┘    │
└─────────────────────────────────────────────────┘
```

## REST API

BioPortal includes a REST API for programmatic job submission and management. API access is opt-in per user, controlled by administrators via the Ops Console.

```bash
# Submit a job
curl -X POST http://localhost:8000/api/v1/jobs/ \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "boltz2", "sequences": ">A\nMKTAYIAKQRQISFVK..."}'
```

See **[api/README.md](api/README.md)** for full endpoint documentation, authentication setup, and usage examples.

## Notes

- **Job directories**: Controlled filesystem layout under `JOB_BASE_DIR/<job_uuid>/...`
- **Default runtime**: Set `JOB_EXECUTION_BACKEND=local` and `GPU_SLOTS` to the host GPU indices the worker may use
- **Worker entrypoint**: `python manage.py run_job_worker --interval 10` is the canonical long-lived worker command
- **Runners**: Stub implementations in `runners/` — replace with actual tool invocations for production
