# Deployment Guide

Step-by-step instructions for deploying Fold on a fresh Ubuntu 22.04 or 24.04 server with NVIDIA GPUs.

By the end of this guide you will have:

- Docker and the NVIDIA Container Toolkit installed
- The Fold web application running behind Gunicorn on port 8000
- Slurm configured for single-node GPU job scheduling
- Model runner containers (Boltz-2, Chai-1, LigandMPNN) built and pre-warmed
- Automated backups via cron

## Prerequisites

- Ubuntu 22.04 LTS or 24.04 LTS (fresh or existing server)
- One or more NVIDIA GPUs with drivers already installed, or willingness to install them in Step 1
- Root or sudo access
- At least 50 GB of free disk space (images + model weights)
- Network access to download packages and model weights

## Step 1: Install NVIDIA Drivers

Skip this step if `nvidia-smi` already works.

```bash
# Add the NVIDIA driver PPA and install
sudo apt-get update
sudo apt-get install -y ubuntu-drivers-common
sudo ubuntu-drivers install

# Reboot to load the driver
sudo reboot
```

After reboot, verify:

```bash
nvidia-smi
```

You should see your GPU(s) listed with driver and CUDA versions.

## Step 2: Install Docker

Install Docker Engine and the Compose v2 plugin from the official Docker repository.

```bash
# Install prerequisites
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg

# Add Docker GPG key
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
    sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Add Docker repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Allow your user to run Docker without sudo
sudo usermod -aG docker $USER
```

Log out and back in (or run `newgrp docker`) for the group change to take effect, then verify:

```bash
docker --version
docker compose version
```

## Step 3: Install NVIDIA Container Toolkit

This allows Docker containers to access the host GPUs.

```bash
# Add NVIDIA Container Toolkit repository
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
    sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
    sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

# Install
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit

# Configure Docker runtime
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

Verify GPU access from a container:

```bash
docker run --rm --gpus all nvidia/cuda:12.8.0-base-ubuntu22.04 nvidia-smi
```

## Step 4: Clone the Repository

```bash
sudo apt-get install -y git
git clone https://github.com/brineylab/fold-webapp.git
cd fold-webapp
```

All subsequent commands assume you are in the `fold-webapp` directory.

## Step 5: Run the Installer

The `deploy.sh install` command handles environment configuration, Docker image builds, database migrations, and admin account creation in one step.

```bash
./deploy.sh install
```

The installer will:

1. Create `.env` from `env.example` with a randomly generated `SECRET_KEY` and `DEBUG=false`
2. Prompt you for `ALLOWED_HOSTS` — enter the hostname or IP your users will access (e.g., `fold.example.com,localhost`)
3. Prompt you for `DATA_DIR` — the root directory for all persistent data (database, jobs, weight caches). Defaults to `./data`. For production, use an absolute path outside the repo (e.g., `/opt/fold-webapp/data`)
4. Build the Docker image for the web application
5. Start all services (runs database migrations automatically)
6. Prompt you to create an admin (superuser) account

After it finishes, verify the app is running:

```bash
./deploy.sh status
```

You should see three services: `migrate` (exited), `web` (running), and `poller` (running). The application is accessible at `http://<your-server>:8000`.

## Step 6: Configure Environment Variables

Edit `.env` to set model-specific configuration:

```bash
nano .env
```

Key variables to review:

| Variable | What to set | Example |
|----------|-------------|---------|
| `DATA_DIR` | Root directory for all persistent data | `/opt/fold-webapp/data` |
| `ALLOWED_HOSTS` | Hostnames/IPs users will use | `fold.lab.org,10.0.1.50` |
| `FAKE_SLURM` | Keep as `0` for production | `0` |
| `BOLTZ_IMAGE` | Boltz-2 container image name | `brineylab/boltz2:latest` |
| `BOLTZ_CACHE_DIR` | Where Boltz-2 caches model weights | `$DATA_DIR/jobs/boltz_cache` |
| `CHAI_IMAGE` | Chai-1 container image name | `brineylab/chai1:latest` |
| `CHAI_CACHE_DIR` | Where Chai-1 caches model weights | `$DATA_DIR/jobs/chai_cache` |
| `LIGANDMPNN_IMAGE` | LigandMPNN container image name | `brineylab/ligandmpnn:latest` |

Set `DATA_DIR` to a path with enough disk space. All other data paths (`DATABASE_PATH`, `JOB_BASE_DIR`, cache directories) default to subdirectories of `DATA_DIR`. The default `./data` works well for single-node setups.

After editing, restart to pick up changes:

```bash
./deploy.sh restart
```

## Step 7: Configure Slurm

The automated setup script installs Slurm, auto-detects your hardware, generates all config files, and creates a `docker-compose.override.yml` that wires the web and poller containers to the host Slurm installation.

```bash
sudo ./deploy.sh setup-slurm
```

The script will:

1. Install munge (authentication) and Slurm packages
2. Detect CPUs, RAM, and GPUs
3. Generate `/etc/slurm/slurm.conf`, `gres.conf`, and `cgroup.conf`
4. Start the `munge`, `slurmctld`, and `slurmd` services
5. Generate `docker-compose.override.yml` in the project root
6. Submit and verify a test job

After completion, verify Slurm is working:

```bash
sinfo
```

You should see your node in the `idle` state. Then restart the application so it picks up the new override file:

```bash
./deploy.sh restart
```

For more details, troubleshooting, and advanced options (`--dry-run`, `--force-reconfig`, `--skip-test`), see [`scripts/SLURM_README.md`](scripts/SLURM_README.md).

## Step 8: Build Model Containers

Build the Docker images for each model runner. These are the containers that Slurm jobs will launch to run predictions.

```bash
# Build all three model containers (or use ./scripts/build_image.sh)
./scripts/build_image.sh boltz2 latest
./scripts/build_image.sh chai1 latest
./scripts/build_image.sh ligandmpnn latest
```

Verify the images exist:

```bash
docker images | grep -E 'boltz2|chai1|ligandmpnn'
```

If you use a private registry, tag and push the images:

```bash
docker tag boltz2:latest registry.example.com/boltz2:latest
docker push registry.example.com/boltz2:latest
# Repeat for chai1 and ligandmpnn
```

Then update the image names in `.env` to match (e.g., `BOLTZ_IMAGE=registry.example.com/boltz2:latest`).

## Step 9: Pre-warm Model Weights

The first prediction for each model requires downloading several GB of weights. The pre-warm script does this ahead of time so first user jobs are fast.

```bash
./deploy.sh prewarm --skip-images
```

The `--skip-images` flag is used because you already built the images in Step 8. This step will:

1. Create cache directories for Boltz-2 and Chai-1
2. Run a minimal test prediction for each model to trigger weight downloads
3. LigandMPNN weights are already included in the container image

This requires GPU access and downloads several GB of data. See [`scripts/PREWARM_README.md`](scripts/PREWARM_README.md) for more details.

## Step 10: Configure Runner Settings in Django Admin

Open the Django admin panel to configure which models are available and how they run.

1. Open `http://<your-server>:8000/admin/` in a browser
2. Log in with the superuser account created in Step 5
3. Navigate to **Runner Configs**
4. Add a configuration for each model you want to enable:
   - Set the runner key (`boltz-2`, `chai-1`, `ligandmpnn`, `alphafold3`)
   - Set the container image URI (or leave blank to use the `.env` default)
   - Configure Slurm directives (partition, GPU count, time limit, etc.)

## Step 11: Set Up Automated Backups

Configure a cron job to back up the database, job data, and configuration daily:

```bash
# Edit crontab
sudo crontab -e

# Add this line (runs daily at 2 AM)
0 2 * * * /path/to/fold-webapp/scripts/backup.sh --quiet >> /var/log/fold-webapp-backup.log 2>&1
```

Backups are saved to `./backups/` as timestamped `.tar.gz` archives. Old backups are automatically pruned after 30 days (configurable via `BACKUP_RETENTION` in `.env`).

To restore from a backup:

```bash
./scripts/restore.sh backups/fold-webapp-backup-20250101_020000.tar.gz
```

## Step 12: Optional — Reverse Proxy with Nginx

The application serves on port 8000 by default. For production, put it behind Nginx with TLS.

```bash
sudo apt-get install -y nginx
```

Create `/etc/nginx/sites-available/fold`:

```nginx
server {
    listen 80;
    server_name fold.example.com;

    # Redirect HTTP to HTTPS
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name fold.example.com;

    ssl_certificate     /etc/ssl/certs/fold.example.com.pem;
    ssl_certificate_key /etc/ssl/private/fold.example.com.key;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable the site and restart Nginx:

```bash
sudo ln -s /etc/nginx/sites-available/fold /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
```

If you use a reverse proxy, add the external hostname to `ALLOWED_HOSTS` in `.env` and restart the app.

## Verification Checklist

After completing all steps, verify your deployment:

```bash
# Application is running
./deploy.sh status

# Slurm is healthy
sinfo                     # Node should be "idle"
squeue                    # Should be empty

# GPU containers work
docker run --rm --gpus all brineylab/boltz2:latest predict --help
docker run --rm --gpus all brineylab/chai1:latest fold --help
docker run --rm --gpus all brineylab/ligandmpnn:latest --help

# Web UI is accessible
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/
# Should return 200
```

Then submit a test job through the web UI at `http://<your-server>:8000` and confirm it progresses through PENDING, RUNNING, and COMPLETED states.

## Updating

To update to a newer version of the application:

```bash
./deploy.sh update
```

This pulls the latest code, rebuilds the Docker image, and restarts all services. Database migrations run automatically on startup.

To rebuild model containers after an update:

```bash
./scripts/build_image.sh boltz2 latest
./scripts/build_image.sh chai1 latest
./scripts/build_image.sh ligandmpnn latest
```

## Troubleshooting

### Application won't start

```bash
# Check container logs
./deploy.sh logs

# Check a specific service
./deploy.sh logs web
./deploy.sh logs poller
```

### Jobs stay in PENDING state

```bash
# Check Slurm node state
sinfo -N -l

# If node is DOWN, reset it
sudo scontrol update NodeName=$(hostname -s) State=IDLE

# Check Slurm controller logs
sudo journalctl -u slurmctld -n 50

# Check that the override file is loaded
docker compose config | grep sbatch
```

### GPU not found in containers

```bash
# Verify NVIDIA runtime is configured
docker info | grep -i nvidia

# Test GPU access
docker run --rm --gpus all nvidia/cuda:12.8.0-base-ubuntu22.04 nvidia-smi

# If this fails, reconfigure the toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

### Permission errors on data directories

```bash
# The web container runs as UID 1000 (appuser)
# Replace ./data with your DATA_DIR if you changed it
sudo chown -R 1000:1000 data/
```

### Port 8000 already in use

```bash
# Find what's using the port
sudo ss -tlnp | grep 8000

# Change the port in docker-compose.yml if needed (ports: "9000:8000")
```

## File Layout Reference

```
fold-webapp/
├── deploy.sh                      # Main deployment CLI
├── docker-compose.yml             # Service definitions
├── docker-compose.override.yml    # Generated by setup-slurm (git-ignored)
├── Dockerfile                     # Web application image
├── .env                           # Environment config (git-ignored)
├── env.example                    # Environment template
├── containers/
│   ├── boltz2/Dockerfile          # Boltz-2 runner image
│   ├── chai1/Dockerfile           # Chai-1 runner image
│   └── ligandmpnn/Dockerfile      # LigandMPNN runner image
├── runners/                       # Job submission logic per model
├── scripts/
│   ├── setup-slurm.sh             # Slurm installer/configurator
│   ├── prewarm.sh                 # Image + weight pre-warming
│   ├── backup.sh                  # Backup script
│   ├── restore.sh                 # Restore script
│   └── build_image.sh             # Container build helper
└── backups/                       # Backup archives (git-ignored)

$DATA_DIR/                         # Persistent data (default: ./data)
├── db/
│   └── db.sqlite3                 # SQLite database
└── jobs/                          # Job working directories
    ├── boltz_cache/               # Boltz-2 model weight cache
    ├── chai_cache/                # Chai-1 model weight cache
    ├── boltzgen_cache/            # BoltzGen model weight cache
    └── rfdiffusion_models/        # RFdiffusion model weights
```

## Migrating Existing Data

If you have an existing deployment with data in `./data/` and want to move it to a new location:

```bash
# 1. Stop services
./deploy.sh stop

# 2. Move the data directory
sudo mv ./data /opt/fold-webapp/data

# 3. Set DATA_DIR in .env
echo "DATA_DIR=/opt/fold-webapp/data" >> .env

# 4. Fix ownership (web container runs as UID 1000)
sudo chown -R 1000:1000 /opt/fold-webapp/data

# 5. Start services
./deploy.sh start
```

## Quick Reference

| Task | Command |
|------|---------|
| Start services | `./deploy.sh start` |
| Stop services | `./deploy.sh stop` |
| Restart services | `./deploy.sh restart` |
| View logs | `./deploy.sh logs` |
| Check status | `./deploy.sh status` |
| Update application | `./deploy.sh update` |
| Set up Slurm | `sudo ./deploy.sh setup-slurm` |
| Pre-warm models | `./deploy.sh prewarm` |
| Create admin user | `./deploy.sh createsuperuser` |
| Django shell | `./deploy.sh shell` |
| Create backup | `./deploy.sh backup` |
| Restore backup | `./scripts/restore.sh <archive>` |
