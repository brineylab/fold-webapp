# fold-webapp

Minimal intranet web UI for submitting protein structure prediction jobs to SLURM.

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
# Edit .env and set FAKE_SLURM=1 for local development

# Run migrations and create admin user
python manage.py migrate
python manage.py createsuperuser

# Start all services (web server + job poller)
honcho start
```

This starts both the web server and the job status poller in a single terminal.

### Option 2: Manual (Separate Terminals)

If you prefer running processes separately:

```bash
# Terminal 1: Web server
python manage.py runserver

# Terminal 2: Job poller (polls every 10 seconds)
while true; do python manage.py poll_jobs; sleep 10; done
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
3. Create `./data/` directories for persistent storage
4. Build the Docker image and start all services
5. Prompt you to create an admin (superuser) account

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
./deploy.sh setup-slurm       # Configure Slurm on this host (requires sudo)
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

### Shared Storage

Both the web container and SLURM compute nodes need access to job working directories. Configure `JOB_BASE_DIR` to point to shared storage (e.g., NFS mount) accessible from both.

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DEBUG` | Enable debug mode | `false` |
| `SECRET_KEY` | Django secret key | `dev-key-change-in-production` |
| `ALLOWED_HOSTS` | Comma-separated hostnames | `localhost,127.0.0.1` |
| `DATABASE_PATH` | Path to SQLite database file | `<BASE_DIR>/db.sqlite3` |
| `JOB_BASE_DIR` | Directory for job working files | `./job_data` |
| `FAKE_SLURM` | Simulate SLURM for local dev (`1` or `0`) | `0` |
| `BACKUP_DIR` | Directory for backup archives | `./backups` |
| `BACKUP_RETENTION` | Days to keep old backups | `30` |

In Docker, `DATABASE_PATH` and `JOB_BASE_DIR` are set automatically by `docker-compose.yml` to use bind mounts under `./data/`. You typically don't need to set these yourself.

## Architecture

```
┌─────────────────────────────────────────────────┐
│  Web Server (Django)                            │
│  ┌──────────────┐  ┌───────────────┐            │
│  │  web         │  │  poller       │            │
│  │  (gunicorn)  │  │  (poll_jobs)  │            │
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
- **Fake mode**: Set `FAKE_SLURM=1` to develop without SLURM; jobs transition PENDING→RUNNING→COMPLETED automatically after ~15 seconds
- **Runners**: Stub implementations in `runners/` — replace with actual tool invocations for production
