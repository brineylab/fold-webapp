# ADR 0001: Host-Run Control Plane

## Status

Accepted

## Date

2026-03-06

## Context

`fold-webapp` currently treats job orchestration like a small cluster product:

- Django runs in Docker
- job state is delegated to `SLURM`
- a separate poller loop reconciles external scheduler state back into the app
- host/container path translation and UID/GID alignment are required to bridge Django, Docker, and `SLURM`

That architecture is materially more complex than the intended operating model:

- single host only
- one GPU per job
- web app and jobs run on the same machine
- intranet-only deployment
- simple tiered priority and quota policy

The Phase 0 goal is to lock in the target control-plane boundary before the queue rewrite begins.

## Decision

The target control plane will run directly on the host:

- Django runs on the host in a project-local virtual environment.
- The job worker runs on the host in the same virtual environment.
- `systemd` manages the long-running web and worker processes.
- Docker is retained only for model execution.
- The host control plane owns one canonical filesystem layout for app state, logs, and job workdirs.

This decision is now the baseline for all later simplification work in [`SIMPLIFY.md`](../../SIMPLIFY.md).

## Consequences

### Positive

- Removes the need for host/container path translation in the steady state.
- Removes the need for app-container UID/GID alignment and most permissive chmod workarounds.
- Makes the eventual `SLURM` removal simpler because the web app and worker already live on the same side of the boundary as the Docker executor.
- Gives operations a smaller and more standard runtime surface: `venv` + `systemd` + Docker.

### Negative

- The current Docker Compose deployment path becomes transitional rather than strategic.
- Production deployment docs and helper scripts will need follow-up changes in later phases.
- During the transition, the repository will temporarily describe both the current runtime and the target runtime.

### Explicit non-goals for Phase 0

- Do not remove `SLURM` yet.
- Do not replace the poller logic yet.
- Do not change the job state model yet.
- Do not remove Docker-based deployment artifacts yet.

## Implementation notes

Phase 0 is satisfied by:

- this accepted decision record
- a concrete host runtime layout document
- `systemd` unit templates for the host-run web and worker services
- a stable worker entrypoint command (`python manage.py run_job_worker`)
- a cutover inventory describing env vars and runtime surfaces that will be removed later
