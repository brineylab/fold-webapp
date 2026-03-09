# Phase 0 Host Runtime

This document captures the concrete host-run control-plane layout selected in Phase 0 of [`SIMPLIFY.md`](../../SIMPLIFY.md).

It is intentionally a target-state artifact. It does not mean the repository has already completed the later queue and `SLURM` removal phases.

## Target runtime layout

Recommended host paths:

| Purpose | Path |
|---|---|
| Checkout | `/opt/fold-webapp` |
| Virtual environment | `/opt/fold-webapp/.venv` |
| Environment file | `/etc/fold-webapp/fold-webapp.env` |
| Persistent data root | `/var/lib/fold-webapp` |
| SQLite database | `/var/lib/fold-webapp/db/db.sqlite3` |
| Job workdirs | `/var/lib/fold-webapp/jobs` |
| Harness data | `/var/lib/fold-webapp/harness` |
| App logs | `/var/log/fold-webapp` |

Recommended ownership:

- application user: `fold`
- application group: `fold`
- Docker access granted to `fold`

## Process model

Two long-running host services are planned:

| Service | Responsibility | Current command |
|---|---|---|
| `fold-webapp-web.service` | Serve Django via Gunicorn | `/opt/fold-webapp/.venv/bin/gunicorn bioportal.wsgi:application ...` |
| `fold-webapp-worker.service` | Run the job worker loop | `/opt/fold-webapp/.venv/bin/python manage.py run_job_worker --interval 10` |

The worker command name is intentionally generic. Today it wraps the status poll loop. In later phases it becomes the single-host queue dispatcher and reconciler behind the same operational entrypoint.

## Bootstrap sequence

Recommended host bootstrap:

```bash
sudo useradd --system --create-home --home-dir /var/lib/fold-webapp --shell /usr/sbin/nologin fold
sudo usermod -aG docker fold

sudo mkdir -p /opt/fold-webapp /etc/fold-webapp /var/lib/fold-webapp/db /var/lib/fold-webapp/jobs /var/lib/fold-webapp/harness /var/log/fold-webapp
sudo chown -R fold:fold /var/lib/fold-webapp /var/log/fold-webapp

git clone https://github.com/brineylab/fold-webapp.git /opt/fold-webapp
cd /opt/fold-webapp
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
```

Then:

1. install the environment file at `/etc/fold-webapp/fold-webapp.env`
2. install the `systemd` units from [`deploy/systemd/`](../../deploy/systemd)
3. run `systemctl daemon-reload`
4. enable and start the `fold-webapp-web` and `fold-webapp-worker` services

## Environment variables to keep at cutover

Keep these in the host-run control plane:

| Variable | Why it stays |
|---|---|
| `DEBUG` | standard Django runtime toggle |
| `SECRET_KEY` | Django secret |
| `ALLOWED_HOSTS` | host validation |
| `DATA_DIR` | canonical app state root |
| `DATABASE_PATH` | explicit SQLite path |
| `JOB_BASE_DIR` | canonical job workdir root |
| `HARNESS_BASE_DIR` | harness storage root |
| `BOLTZ_IMAGE` | model container selection |
| `BOLTZ_CACHE_DIR` | model cache location |
| `CHAI_IMAGE` | model container selection |
| `CHAI_CACHE_DIR` | model cache location |
| `LIGANDMPNN_IMAGE` | model container selection |
| `BINDCRAFT_IMAGE` | model container selection |
| `RFDIFFUSION3_IMAGE` | model container selection |
| `BOLTZGEN_IMAGE` | model container selection |
| `BOLTZGEN_CACHE_DIR` | model cache location |
| `DEFAULT_MAX_CONCURRENT_JOBS` | policy default until tier model lands |
| `DEFAULT_MAX_QUEUED_JOBS` | policy default until tier model lands |
| `DEFAULT_JOBS_PER_DAY` | policy default until monthly quotas land |
| `DEFAULT_RETENTION_DAYS` | cleanup policy default |

## Environment variables to remove after cutover

Remove these when the host-run control plane fully replaces the Docker + `SLURM` bridge:

| Variable | Why it goes away |
|---|---|
| `APP_UID` | only needed for app container uid alignment |
| `APP_GID` | only needed for app container gid alignment |
| `JOB_BASE_DIR_HOST` | only needed for host/container path translation |
| `HARNESS_BASE_DIR_HOST` | only needed for host/container path translation |
| `FAKE_SLURM` | disappears with the `SLURM` control plane |

## Runtime surfaces to delete after cutover

These are the major runtime surfaces that remain during transition but should be removed after the later phases land:

| Surface | Planned disposition |
|---|---|
| `slurm.py` | delete |
| `jobs/management/commands/poll_jobs.py` | replace with local executor logic behind `run_job_worker` |
| Docker Compose `poller` service | delete |
| `Dockerfile` `slurm` user setup | delete |
| `deploy.sh` host/container permission bridge logic | delete or sharply reduce |
| `scripts/setup-slurm.sh` | delete |
| `scripts/SLURM_README.md` | delete |
| `JOB_BASE_DIR_HOST` / `HARNESS_BASE_DIR_HOST` settings | delete |
| `RunnerConfig` `partition` / `gpus` / `cpus` / `mem_gb` / `time_limit` / `extra_env` / `extra_mounts` | delete or narrow sharply |
| `console` `SLURM` monitoring UI | delete |

## systemd artifacts

Phase 0 stores the target unit templates here:

- [`deploy/systemd/fold-webapp-web.service`](../../deploy/systemd/fold-webapp-web.service)
- [`deploy/systemd/fold-webapp-worker.service`](../../deploy/systemd/fold-webapp-worker.service)
- [`deploy/systemd/fold-webapp.tmpfiles.conf`](../../deploy/systemd/fold-webapp.tmpfiles.conf)

These units assume the host layout above and a `fold` service account.

An example host environment file is provided at [`deploy/systemd/fold-webapp.env.example`](../../deploy/systemd/fold-webapp.env.example).
