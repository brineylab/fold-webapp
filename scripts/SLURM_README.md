# Slurm Setup Script

The `setup-slurm.sh` script installs and configures Slurm on a single Ubuntu node for use with Fold. It auto-detects hardware (CPUs, RAM, GPUs), generates all required config files, and produces a `docker-compose.override.yml` so the web and poller containers can communicate with Slurm.

## Quick Start

```bash
# After deployment, run:
sudo ./deploy.sh setup-slurm

# Or run directly:
sudo ./scripts/setup-slurm.sh
```

## What It Does

The script runs 12 phases in order:

1. **Prerequisites check** — verifies root access, Ubuntu version (22.04/24.04), GPU drivers, Docker
2. **Install munge** — installs munge authentication and generates a key
3. **Install Slurm packages** — installs `slurm-wlm` and `slurm-client` from Ubuntu repos
4. **Hardware auto-detection** — discovers CPUs, RAM, GPU count and type
5. **Generate `slurm.conf`** — writes `/etc/slurm/slurm.conf` with detected hardware
6. **Generate `gres.conf`** — writes `/etc/slurm/gres.conf` for GPU scheduling (`AutoDetect=nvml` when available, static `/dev/nvidiaN` fallback otherwise)
7. **Generate `cgroup.conf`** — writes `/etc/slurm/cgroup.conf` for resource isolation
8. **Configure job completion logging** — creates a local completion log file
9. **Enable and start services** — starts munge, slurmctld, and slurmd; sets node to IDLE
10. **Generate `docker-compose.override.yml`** — mounts Slurm binaries, config, munge socket, and shared libraries into web/poller containers
11. **Verification** — submits a test job and confirms completion via scheduler state (`squeue`/`sacct`/`scontrol`)
12. **Print summary** — shows detected hardware, config paths, service status, and next steps

## When to Run

- **After initial deployment** — set up Slurm for the first time
- **After OS upgrades** — Slurm packages may need reinstallation
- **After hardware changes** — new GPUs, RAM, or CPU changes (use `--force-reconfig`)
- **After Slurm upgrades** — regenerate configs for the new version (use `--force-reconfig`)

## Usage

### Basic Usage

```bash
sudo ./deploy.sh setup-slurm
```

### Preview Without Making Changes

```bash
sudo ./scripts/setup-slurm.sh --dry-run
```

Shows all planned actions — package installs, config file contents, service changes — without modifying anything. Useful for reviewing what will happen before committing.

### Skip the Test Job

```bash
sudo ./scripts/setup-slurm.sh --skip-test
```

Skips the verification phase (Phase 11) that submits a test job. Useful in CI or when you know the cluster is already working.

### Force Regenerate All Configs

```bash
sudo ./scripts/setup-slurm.sh --force-reconfig
```

Overwrites existing config files (`slurm.conf`, `gres.conf`, `cgroup.conf`, `docker-compose.override.yml`) even if they already exist. Use this after hardware changes or when you want a clean config based on current hardware.

### Combine Options

```bash
sudo ./scripts/setup-slurm.sh --force-reconfig --skip-test
```

## Requirements

- **Ubuntu 22.04 or 24.04** (other distributions are not supported)
- **Root access** (the script must be run with `sudo`)
- **NVIDIA drivers** (optional — required for GPU scheduling)
- **Docker** (optional — required for `docker-compose.override.yml` to be useful)
- **NVIDIA Container Toolkit** (optional — required for GPU containers)

## Generated Config Files

### `/etc/slurm/slurm.conf`

Main Slurm configuration. Key settings:

| Setting | Value | Purpose |
|---------|-------|---------|
| `ClusterName` | `fold` | Cluster identifier |
| `SlurmctldHost` | auto-detected node identity (`slurmd -C`) | Controller node |
| `SelectType` | `select/cons_tres` | Enables GPU GRES scheduling |
| `ProctrackType` | `proctrack/cgroup` | Process tracking via cgroups |
| `TaskPlugin` | `task/cgroup,task/affinity` | Resource isolation |
| `JobCompType` | `jobcomp/filetxt` | File-based job completion logging |
| `GresTypes` | `gpu` | Generic resource types |
| `ReturnToService` | `2` | Auto-return node after reboot |

Node identity is sourced from `slurmd -C` when available to avoid hostname mismatch issues.
Node resources (CPUs, RAM, GPUs) are auto-detected from hardware.

### `/etc/slurm/gres.conf`

GPU resource configuration:

- With GPUs: prefers `AutoDetect=nvml` when the Slurm NVML plugin is available; otherwise writes static `Name=gpu File=/dev/nvidiaN` entries
- Without GPUs: comment-only placeholder file

### `/etc/slurm/cgroup.conf`

Cgroup resource isolation:

```
ConstrainCores=yes
ConstrainRAMSpace=yes
ConstrainDevices=yes
```

### `docker-compose.override.yml`

Generated in the project root. Mounts into the `web` and `poller` services:

- **Slurm binaries**: `/usr/bin/{sbatch,squeue,sacct,scancel}` (read-only)
- **Slurm config**: `/etc/slurm` (read-only)
- **Munge socket**: `/var/run/munge` (read-only)
- **Slurm shared libraries**: auto-discovered via `ldconfig -p` (read-only)
- **`LD_LIBRARY_PATH`**: set so mounted Slurm binaries can find their shared libraries inside the container

This file is git-ignored since it is environment-specific.

## Idempotency

The script is safe to re-run:

- `apt-get install -y` skips already-installed packages
- Munge key generation is guarded by file existence check
- All config file writes are guarded by existence checks (use `--force-reconfig` to overwrite)
- `systemctl enable` is idempotent
- `docker-compose.override.yml` is guarded the same way as config files

Re-running the script on an already-configured node will print warnings about existing files and skip those phases.

## Post-Setup Steps

After the script completes:

1. **Set `FAKE_SLURM=0` in `.env`** — disables the simulated Slurm backend
2. **Restart the app** — `./deploy.sh restart`
3. **Configure RunnerConfig** — in Django admin (`http://localhost:8000/admin/`), set up runner configurations for your model containers

## Troubleshooting

### Service fails to start

```
ERROR: slurmctld failed to start. Check: journalctl -u slurmctld -n 50
```

**Common causes**:
- Config syntax error in `slurm.conf`
- Port conflict (another Slurm instance running)
- Permissions on spool directories
- NVML GPU plugin not available with `AutoDetect=nvml`

**Solution**:

```bash
# Check service logs
journalctl -u slurmctld -n 50
journalctl -u slurmd -n 50

# Verify config syntax
slurmctld -h | grep -qE '(^|[[:space:]])-t([[:space:]]|$)' && slurmctld -t -f /etc/slurm/slurm.conf || echo "slurmctld -t not supported on this host"

# Regenerate configs from scratch
sudo ./scripts/setup-slurm.sh --force-reconfig
```

### Node stuck in UNKNOWN or DOWN state

```bash
# Check node state
sinfo

# Manually set to IDLE
sudo scontrol update NodeName=$(hostname -s) State=IDLE
```

### slurmd fails with gpu/nvml errors

```
slurmd: error: cannot find gpu plugin for gpu/nvml
```

This means `AutoDetect=nvml` was requested but the Slurm NVML plugin is not present. The setup script automatically falls back to static `/dev/nvidiaN` entries on reconfigure.

```bash
sudo ./scripts/setup-slurm.sh --force-reconfig
```

### Test job fails or times out

```
ERROR: Test job did not complete within 60s.
```

**Common causes**:
- `slurmd` is not running on the node
- Node is in DOWN state
- Cgroup configuration mismatch

**Solution**:

```bash
# Check node state
sinfo -N -l

# Check slurmd logs
journalctl -u slurmd -n 50

# Check if the job is stuck
squeue
sacct -j <job_id>    # optional; may be empty without slurmdbd
scontrol show job <job_id> -o
```

### sacct returns no results

```
WARNING: sacct returned no results for job <id> (no accounting DB configured).
```

This is expected on single-node setups without `slurmdbd`.

```bash
grep -E "JobCompType|JobCompLoc|JobAcctGatherType" /etc/slurm/slurm.conf
```

Status polling still works because the app falls back to `scontrol` when `sacct` is unavailable.

### Munge authentication errors

```bash
# Check munge is running
systemctl status munge

# Test munge
munge -n | unmunge

# Fix permissions if needed
sudo chown munge:munge /etc/munge/munge.key
sudo chmod 400 /etc/munge/munge.key
sudo systemctl restart munge
```

### Docker containers can't find Slurm binaries

Verify the override file was generated:

```bash
cat docker-compose.override.yml
```

Check that Docker Compose picks it up:

```bash
docker compose config | grep sbatch
```

If the override is not being loaded, ensure it is in the project root alongside `docker-compose.yml`.

### Shared library errors in containers

```
sbatch: error while loading shared libraries: libslurm.so
```

The script auto-discovers Slurm shared libraries via `ldconfig -p` and mounts them into containers. If libraries are in a non-standard location:

```bash
# Find the library
ldconfig -p | grep slurm

# Regenerate the override
sudo ./scripts/setup-slurm.sh --force-reconfig
```

## Hardware Detection Details

| Resource | Detection Method | Notes |
|----------|-----------------|-------|
| Hostname | `hostname -s` | Short hostname, used as Slurm node name |
| CPUs | `nproc` | Total available CPU cores |
| RAM | `free -m` minus 2 GB | 2 GB reserved for OS overhead (minimum 1 GB allocated) |
| GPUs | `nvidia-smi --query-gpu=name` | Count and type auto-detected |

## Slurm Version Notes

The script installs Slurm from Ubuntu default repositories:

| Ubuntu Version | Slurm Version |
|----------------|---------------|
| 22.04 | 21.08 |
| 24.04 | 23.02 |

Both versions support the features used by this script (GRES scheduling with NVML-or-static fallback, cgroup integration). For newer Slurm versions, consider adding the [SchedMD PPA](https://packages.schedmd.com/).

## Integration with deploy.sh

The setup script is integrated into `deploy.sh`:

```bash
# Via deploy.sh (recommended)
sudo ./deploy.sh setup-slurm [options]

# Direct invocation
sudo ./scripts/setup-slurm.sh [options]
```

Both approaches are equivalent. The `deploy.sh` wrapper simply delegates to the script.

## Example Deployment Workflow

```bash
# 1. Initial setup
./deploy.sh install

# 2. Configure Slurm
sudo ./deploy.sh setup-slurm

# 3. Switch from fake to real Slurm
# Edit .env: set FAKE_SLURM=0
./deploy.sh restart

# 4. Pre-warm model containers (optional)
./deploy.sh prewarm

# 5. Verify
sinfo                  # Should show node in "idle" state
squeue                 # Should be empty (no pending jobs)
```

## See Also

- `deploy.sh` — Main deployment script
- `prewarm.sh` — Pre-warming script for Docker images and model weights
- `backup.sh` — Backup script
- `restore.sh` — Restore script
- `env.example` — Environment variable template
