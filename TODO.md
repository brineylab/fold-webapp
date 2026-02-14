# TODO

## Move data directory out of the git repo

**Priority:** Medium
**Context:** The `data/` directory (containing `db/` and `jobs/`) currently lives
inside the cloned repo at `./data/`. This works but mixes runtime data with
application code — a `git clean`, re-clone, or accidental deletion could wipe
the database and all job files.

The `JOB_BASE_DIR_HOST=${PWD}/data/jobs` setting in `docker-compose.yml` is a
temporary solution that correctly maps container paths to host paths for SLURM.
It should be replaced with a proper absolute path once a production data
location is chosen.

**Suggested locations:**
- `/opt/fold-webapp/data/` — conventional for self-contained app data
- `/var/lib/fold-webapp/` — follows FHS for variable application data
- `/data/fold-webapp/` — simple, common on GPU servers with dedicated data disks

**What needs to change:**
1. Pick a host directory and create `db/` and `jobs/` subdirectories
2. Update `docker-compose.yml` volume mounts to use absolute paths
3. Update `JOB_BASE_DIR_HOST` to the new absolute path (and remove `${PWD}`)
4. Update `deploy.sh` `mkdir -p` commands for the new location
5. Migrate existing data from `./data/` to the new location
6. Update documentation (README, DEPLOY.md) to reflect the new paths
