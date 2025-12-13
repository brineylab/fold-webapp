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

For production deployments, use Docker Compose:

```bash
# Configure environment
cp env.example .env
# Edit .env with production settings:
#   - Set DEBUG=false
#   - Set a secure SECRET_KEY
#   - Set FAKE_SLURM=0 (use real SLURM)
#   - Configure JOB_BASE_DIR for shared storage

# Build and start all services
docker compose up -d --build

# Create admin user (first time only)
docker compose exec web python manage.py createsuperuser

# View logs
docker compose logs -f
```

### SLURM Integration

For the web container to communicate with SLURM, uncomment the volume mounts in `docker-compose.yml` to expose SLURM binaries and configuration:

```yaml
volumes:
  - /usr/bin/sbatch:/usr/bin/sbatch:ro
  - /usr/bin/squeue:/usr/bin/squeue:ro
  - /usr/bin/sacct:/usr/bin/sacct:ro
  - /usr/bin/scancel:/usr/bin/scancel:ro
  - /etc/slurm:/etc/slurm:ro
  - /var/run/munge:/var/run/munge:ro
```

### Shared Storage

Both the web container and SLURM compute nodes need access to job working directories. Configure `JOB_BASE_DIR` to point to shared storage (e.g., NFS mount) accessible from both.

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DEBUG` | Enable debug mode | `false` |
| `SECRET_KEY` | Django secret key | `dev-key-change-in-production` |
| `ALLOWED_HOSTS` | Comma-separated hostnames | `localhost,127.0.0.1` |
| `JOB_BASE_DIR` | Directory for job working files | `./job_data` |
| `FAKE_SLURM` | Simulate SLURM for local dev (`1` or `0`) | `0` |

## Architecture

```
┌─────────────────────────────────────────────────┐
│  Web Server (Django)                            │
│  ┌─────────────┐  ┌─────────────┐               │
│  │  web        │  │  poller     │               │
│  │  (gunicorn) │  │  (poll_jobs)│               │
│  └──────┬──────┘  └──────┬──────┘               │
│         │                │                      │
│         └────────┬───────┘                      │
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

## Notes

- **Job directories**: Controlled filesystem layout under `JOB_BASE_DIR/<job_uuid>/...`
- **Fake mode**: Set `FAKE_SLURM=1` to develop without SLURM; jobs transition PENDING→RUNNING→COMPLETED automatically after ~15 seconds
- **Runners**: Stub implementations in `runners/` — replace with actual tool invocations for production
