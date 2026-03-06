# Simplification Analysis for fold-webapp

## Scope and assumptions

This review was done against the intended operating model you described:

- Single host only
- One GPU per job, always
- Single-GPU dev box, multi-GPU production box
- Web app and jobs run on the same server
- Intranet-only access
- Simple visibility boundaries are enough for user data
- Policy needs are simple tiered priority, queue/running limits, and daily/monthly quotas
- Usage reporting and failure logging matter a lot

Validation note: this is a static analysis pass. I could not run the Django test suite in this environment because project dependencies are not installed (`python3 manage.py test` fails with `ModuleNotFoundError: django`).

## Executive summary

The main over-engineering is exactly where you suspected: the job control plane. The current design is paying cluster-grade complexity for a deployment that is not a cluster. `SLURM`, `FAKE_SLURM`, host/container path translation, a separate status poller, dynamic `RunnerConfig` resource controls, open filesystem permissions, and deployment-time UID/GID alignment all exist to support a scheduler model that is materially more complex than your actual use case.

The good news is that the codebase is not over-engineered everywhere. The `ModelType` abstraction is justified, the per-job workdir model is useful, the API surface is reasonably thin, and container-per-model execution is aligned with the problem. The largest simplification win is therefore not "rewrite everything"; it is "replace the scheduler/control plane, collapse the operational surface around that change, and keep the parts that are actually earning their keep."

My strongest recommendation is:

1. Replace `SLURM` with a single-host durable queue plus local Docker executor.
2. Shrink runtime configuration from a live cluster-like control plane to a small set of fixed per-model settings.
3. Redesign quotas and reporting around tiered policy plus explicit job/attempt telemetry.
4. Centralize job lifecycle actions so web, API, console, and admin all use the same behavior.

## What Is Already Aligned

These parts are worth keeping, with only modest cleanup:

- `ModelType` separation is justified. Different models genuinely have different forms, normalization logic, workdir layouts, and output presentation. `model_types/base.py` and the registry are pulling their weight.
- The split between `model_key` and `runner_key` is also justified. Multiple user-facing workflows can target the same container/runtime.
- Per-job workdirs under `JOB_BASE_DIR/<job_uuid>/...` are a good fit for reproducibility, downloads, and debugging.
- The API is thin and conceptually aligned. It mostly needs deduplication, not removal.
- SQLite can remain acceptable if you move to a single dispatcher/worker process instead of trying to emulate a distributed scheduler inside the app.

## Priority-Ranked Simplification Opportunities

### 1. Replace SLURM with a single-host queue and local Docker executor

Priority: Highest  
De-complexifying gain: Very high

#### Why this is misaligned

Your deployment model is not a cluster:

- no multi-node scheduling
- no multi-GPU jobs
- no need for partitions, reservations, fair-share, or host-level batch RPC
- the web app and all jobs run on the same machine

The codebase is still carrying the complexity of a cluster control plane:

- `jobs/services.py` creates a job, writes a workdir, builds an `sbatch` script, and submits to `SLURM`.
- `slurm.py` wraps `sbatch`, `squeue`, `sacct`, `scontrol`, and `scancel`, plus a second fake execution mode.
- `jobs/management/commands/poll_jobs.py` exists only because job state is external and must be polled back into Django.
- `docker-compose.yml` runs a dedicated `poller` service.
- `Dockerfile`, `deploy.sh`, `env.example`, `README.md`, and `DEPLOY.md` all carry host/container glue for the scheduler boundary.

Relevant code:

- `jobs/services.py:48-119`
- `slurm.py:33-305`
- `jobs/management/commands/poll_jobs.py:26-100`
- `docker-compose.yml:55-83`
- `Dockerfile:10-39`
- `bioportal/settings.py:117-156`

#### Current complexity that disappears if SLURM goes away

- `FAKE_SLURM` dev mode
- `slurm_job_id` as a first-class concept
- `sbatch` script generation as the main execution primitive
- `squeue`/`sacct`/`scontrol` status reconciliation
- the separate polling process
- host-path translation (`host_workdir`)
- container access to host scheduler binaries and config
- munge/slurm user concerns
- many "job disappeared from SLURM" failure cases that are artifacts of the architecture, not the workload

#### Proposed fix

Replace the scheduler layer with a single-host executor that launches model containers directly and records durable state in Django.

Recommended design:

- Keep a dedicated worker process, but change its job from "poll SLURM" to "dispatch queued jobs and reconcile running containers."
- Queue state lives in the database, not in `SLURM`.
- Every queued job requires exactly one GPU slot.
- Configure available GPU slots explicitly, e.g. `GPU_SLOTS=0` in dev and `GPU_SLOTS=0,1,2,3` in production.
- Worker loop:
  - reconcile running jobs on startup and periodically
  - pick the next eligible queued jobs by priority tier, then FIFO
  - launch `docker run` pinned to a specific GPU index
  - record container id, GPU slot, exit code, stdout path, stderr path
  - mark job terminal when container exits
- Cancellation:
  - queued job -> mark `CANCELLED`
  - running job -> `docker stop` then mark `CANCELLED`
- Retry:
  - implement "retry as a new job" first
  - do not start with in-place reruns

Keep only a very thin execution interface if you want future optional backends. Example shape:

- `enqueue(job)`
- `cancel(job)`
- `reconcile()`
- `launch_next()`

Do not preserve the current generic cluster abstraction just in case you might someday need it.

#### Data model changes to support this

Add a `JobAttempt` (or `JobRun`) table and stop overloading the main `Job` row with scheduler-specific state.

Recommended minimum fields on `JobAttempt`:

- `job`
- `attempt_number`
- `status`
- `container_id`
- `gpu_index`
- `started_at`
- `finished_at`
- `exit_code`
- `stdout_path`
- `stderr_path`
- `failure_summary`

Recommended status model:

- `QUEUED`
- `RUNNING`
- `COMPLETED`
- `FAILED`
- `CANCELLED`

This is slightly richer than the current four-state model, but it makes the system simpler to reason about because "cancelled" stops pretending to be "failed", and attempts become explicit instead of leaking across unrelated fields.

### 2. Collapse the runtime configuration surface

Priority: High  
De-complexifying gain: Very high

#### Why this is misaligned

`RunnerConfig` currently exposes a live admin-editable runtime control plane:

- `partition`
- `gpus`
- `cpus`
- `mem_gb`
- `time_limit`
- `image_uri`
- `extra_env`
- `extra_mounts`

This makes sense for a general scheduler-backed batch system. It does not match your stated model:

- all jobs need exactly one GPU
- there is no partitioning problem
- there is no multi-node resource placement problem
- most container mounts and env are deployment concerns, not staff UI concerns

Relevant code:

- `console/models.py:124-244`
- `console/views/settings.py:14-204`
- `runners/boltz.py:15-87`
- `runners/chai.py:15-85`
- `runners/ligandmpnn.py:15-101`

#### Why this causes maintenance pain

- Each runner script knows how to consume a mutable config object instead of fixed runtime defaults.
- The settings UI has to parse and validate JSON for env vars and mounts.
- Operators can create configuration drift in the database that does not exist in code review.
- The app carries support for values you already know will never vary meaningfully, such as per-job GPU count.

#### Proposed fix

Shrink runtime configuration to the smallest set that is actually operationally useful.

Recommended end state:

- Keep only:
  - `enabled`
  - optional `disabled_reason`
  - maybe `image_uri` override if you really need live image flips
  - maybe one timeout field if you want it operator-editable
- Remove:
  - `partition`
  - `gpus`
  - `cpus`
  - `mem_gb`
  - `time_limit` from the general-purpose admin surface unless truly needed
  - `extra_mounts`
  - arbitrary `extra_env`

Move model runtime details into code or deployment config:

- per-model image defaults in settings or env
- per-model cache mounts in code
- one-GPU invariant in the executor
- any CPU/memory settings as fixed constants per model, not mutable staff-entered JSON

If a model genuinely needs custom runtime behavior, encode that in the model's executor adapter, not a general-purpose database control panel.

### 3. Replace per-user manual quota tuning with tiered policy plus explicit usage telemetry

Priority: High  
De-complexifying gain: High

#### Why this is misaligned

The current policy model is both too detailed in the wrong places and too weak in the places you care about:

- It stores per-user numeric settings directly.
- It does not model priority tiers.
- It does not support monthly quotas.
- It does not capture robust usage metrics for reporting.
- It computes quota checks from live `Job` counts at submit time, without durable usage telemetry or strong reservation semantics.

Relevant code:

- `console/models.py:8-74`
- `console/services/quota.py:17-148`
- `console/views/users.py:63-282`

#### Current problems

- Quotas are enforced by counting current `Job` rows (`RUNNING`, `PENDING`, and today's submissions).
- There is no snapshot of policy at submission time.
- There is no explicit metric like runtime seconds, wait time, GPU time, or attempt count.
- The model assumes staff are quota-exempt by default, which is convenient but not a reporting model.
- Concurrent submissions can still race because checks and inserts are not a single reserved scheduling operation.

#### Proposed fix

Redesign policy around a small number of tiers plus optional per-user overrides.

Recommended policy model:

- `priority_tier`: `standard`, `priority` (start with two tiers)
- `max_queued_jobs`
- `max_running_jobs`
- `jobs_per_day`
- `jobs_per_month`
- `retention_days`
- `api_enabled`
- `disabled`

Recommended structure:

- one shared tier definition table or enum for defaults
- one user policy row with optional overrides only when needed

This is simpler than manually tuning every user while still supporting exceptions.

For reporting, record usage directly on job completion:

- `queued_at`
- `started_at`
- `finished_at`
- `wait_seconds`
- `run_seconds`
- `gpu_seconds`
- `runner`
- `owner`
- `priority_tier_snapshot`
- `final_status`
- `attempt_count`

Because every job uses exactly one GPU, `gpu_seconds == run_seconds` unless you later change the contract. That makes reporting much easier than a generic scheduler accounting model.

### 4. Centralize job lifecycle logic across web, API, console, and admin

Priority: High  
De-complexifying gain: Medium-high

#### Why this is misaligned

Job submission, cancellation, deletion, and serialization are spread across several entry points:

- web views
- API views
- console services
- Django admin actions

Relevant code:

- `jobs/views.py:43-222`
- `api/views.py:20-282`
- `console/services/jobs.py:1-84`
- `jobs/admin.py:1-28`

#### Current problems

- cancellation behavior is duplicated
- hidden/delete behavior is duplicated
- job serialization is separate in API
- failure/cancel messages diverge by surface
- every future queue change has to be wired through multiple layers

#### Proposed fix

Create one service module for job lifecycle commands and make every interface call it.

Recommended command set:

- `submit_job(...)`
- `cancel_job(job, actor, source)`
- `hide_job(job, actor)`
- `retry_job(job, actor)` or `clone_job(job, actor)`
- `serialize_job(job)`
- `list_output_files(job)`

Then make:

- web views thin HTML adapters
- API views thin JSON adapters
- console actions thin admin adapters
- Django admin actions call the same command layer

This is not the largest simplification by itself, but it is an important enabler. It will make the queue rewrite and later policy changes much easier.

### 5. Simplify deployment by removing host/container path translation and open permission hacks

Priority: Medium-high  
De-complexifying gain: High

#### Why this is misaligned

The deployment surface is doing a lot of work to make "containerized web app submits jobs to host scheduler" function:

- build-time `APP_UID` / `APP_GID`
- `JOB_BASE_DIR_HOST`
- `HARNESS_BASE_DIR_HOST`
- a dedicated `slurm` user in the web image
- aggressive `0777` / `0666` chmod behavior
- path traversal checks for host-visible workdirs
- commented compose mounts for scheduler binaries and config

Relevant code:

- `Dockerfile:10-39`
- `docker-compose.yml:1-86`
- `deploy.sh:81-245`
- `jobs/models.py:42-55`
- `jobs/fs.py:6-42`
- `bioportal/settings.py:117-156`

#### Current problems

- The app image must align with host uid/gid choices.
- Workdir paths have dual identities.
- Permissions are intentionally opened far wider than the functional use case really needs.
- Deployment docs are much longer because they explain boundary problems instead of application behavior.

#### Proposed fix

After `SLURM` removal, choose one of these two deployment models:

Option A - Recommended for maximum simplification:

- Run Django and the worker directly on the host via `venv` + `systemd`.
- Continue running model executions as Docker containers.
- Remove `JOB_BASE_DIR_HOST`, `HARNESS_BASE_DIR_HOST`, the `slurm` image user, and most UID/GID gymnastics.

Option B - Still simpler than today:

- Keep Django containerized.
- Add one worker container with Docker socket access and a single bind-mounted data directory.
- Use one canonical path inside the app and worker containers.

Either way, after removing `SLURM`, you should also remove:

- world-writable defaults in `jobs/fs.py`
- host scheduler binary mounts
- most of the path/permission logic in `deploy.sh`

### 6. Reduce the admin/ops surface to what staff will actually use

Priority: Medium  
De-complexifying gain: Medium

#### Why this is misaligned

The repository currently has:

- a custom ops console
- Django admin registrations
- user account actions in the custom console
- cleanup pages
- monitoring pages
- stats pages
- audit pages
- future role-based decorators

Relevant code:

- `console/views/users.py:22-282`
- `console/views/settings.py:14-204`
- `console/views/jobs.py:12-106`
- `console/views/audit.py:9-60`
- `console/services/monitoring.py:140-170`
- `console/decorators.py:9-68`
- `console/admin.py:1-44`

#### Current problems

- There are two administrative surfaces to maintain.
- Some pages expose features that are only meaningful in a cluster model.
- Some code explicitly exists as a placeholder for future roles/groups you may never need.
- `get_slurm_cluster_status()` is a stub, but the app already carries the page and UI.

#### Proposed fix

Pick one primary admin path and reduce the rest.

Recommended approach:

- Keep a small custom console for:
  - queue dashboard
  - recent failures
  - tier/policy management
  - basic job retry/cancel
- Push generic user/account editing back to Django admin.
- Remove `ops_required` unless you are actually introducing groups now.
- Remove the `SLURM` monitoring page instead of expanding it.

If staff really prefer the custom console, then still stop duplicating features already served adequately by Django admin.

### 7. Replace generic history tracking with domain-specific execution and policy events

Priority: Medium  
De-complexifying gain: Medium

#### Why this is misaligned

`django-simple-history` is attached to:

- `Job`
- `UserQuota`
- `SiteSettings`
- `RunnerConfig`

Relevant code:

- `jobs/models.py:39-40`
- `console/models.py:66-67`
- `console/models.py:101-102`
- `console/models.py:190-191`
- `bioportal/settings.py:25-48`
- `console/views/audit.py:9-60`

#### Current problems

- You get generic object history, not first-class job execution events.
- Troubleshooting wants stderr/stdout, exit code, GPU slot, attempt count, and who cancelled or retried.
- Funding reports want durable usage metrics, not historical diffs of quota rows.
- The app is carrying audit tables, middleware, and an audit UI for limited domain value.

#### Proposed fix

Replace broad generic history with focused domain events:

- `JobAttempt`
- optional `JobEvent` for submit/cancel/retry/reconcile actions
- optional `AdminActionLog` for tier or settings changes if you still need change audit

I would keep explicit job execution records and strongly consider removing `simple_history` from the operational models once the queue rewrite lands.

### 8. Cleanup and orphan tooling should shrink after the runtime model is simplified

Priority: Low-medium  
De-complexifying gain: Medium

#### Why this is misaligned

There is a substantial cleanup/orphan subsystem:

- retention scanning
- orphan workdir scanning
- orphan job detection
- cleanup console pages
- cleanup management commands

Relevant code:

- `console/services/cleanup.py:20-298`
- `console/views/cleanup.py:1-86`
- `jobs/management/commands/cleanup_jobs.py:1-78`
- `jobs/management/commands/detect_orphans.py:1-105`

#### Current problems

Much of this exists because the current execution model allows state drift:

- scheduler state is external
- files can outlive jobs
- jobs can outlive files
- host/container path mismatch makes cleanup logic more defensive

#### Proposed fix

Keep only the pieces that still matter after the executor rewrite:

- one scheduled retention task
- one simple orphan scan management command

The custom cleanup dashboard is probably not worth keeping unless operators use it heavily.

### 9. Keep the validation harness, but isolate it from runtime-specific concerns

Priority: Low  
De-complexifying gain: Low-medium

#### Why this is not the main problem

The harness is large, but it is mostly engineering support for a legitimately complex model/container matrix. It is not the main source of runtime over-engineering.

Relevant code:

- `jobs/harness.py:23-380`
- `scripts/run_model_harness.sh`
- `harness/cases.yaml`

#### Current issue

The harness currently knows too much about the runtime layer:

- host/local path duality
- `RunnerConfig`
- materialized `sbatch` scripts

#### Proposed fix

Keep the harness, but rewrite it against the simplified executor contract after the queue rewrite. Treat it as an engineering validation tool, not part of the core control plane.

### 10. Split the monolithic form file eventually, but do not confuse that with the main simplification win

Priority: Low  
De-complexifying gain: Low

`jobs/forms.py` is large and will get harder to maintain as more models are added. That said, this is not the main over-engineering problem. It is an organizational refactor, not a control-plane simplification.

Recommended fix:

- split forms into per-model modules once the queue/control-plane rewrite settles
- keep the `ModelType` pattern
- do not collapse model-specific logic into a generic mega-form

## Recommended Target Architecture

The architecture that best matches your stated use case is:

1. Web/API create a `Job` row in `QUEUED`.
2. A single worker process reads queued jobs from the database.
3. Worker selects the next eligible job by:
   - tier priority
   - FIFO within a tier
   - per-user running/queued quota
   - available GPU slot
4. Worker launches the model container directly with `docker run`, pinned to one GPU.
5. Worker writes structured attempt metadata plus stdout/stderr logs into the job workdir and database.
6. On exit, worker marks the job `COMPLETED`, `FAILED`, or `CANCELLED`.
7. Reporting queries use `Job` and `JobAttempt` metrics, not scheduler accounting.

This keeps the system durable and extensible without pretending it is a cluster scheduler.

## Recommended Simplified Data Model

### Keep

- `Job`
- per-job workdir layout
- model-specific input/output handling
- API key auth if you still want programmatic submission

### Add

- `JobAttempt`
- `priority_tier` on the user policy model
- monthly quota fields
- explicit usage metrics (`wait_seconds`, `run_seconds`, `gpu_seconds`)
- `CANCELLED` as a first-class status

### Remove or shrink

- `slurm_job_id`
- `host_workdir`
- `RunnerConfig` resource knobs
- `FAKE_SLURM`
- cluster monitoring
- most generic object history

## Phased Implementation Plan

### Phase 0 - Freeze the target and choose the deployment boundary

Decide one thing up front: whether the Django app should remain containerized in production.

Recommended choice:

- run Django and the worker on the host for maximum simplification

If you do not want that change now:

- keep Django containerized, but still remove `SLURM` and use a local Docker worker

Deliverables:

- one short architecture decision note
- list of env vars to keep vs remove
- list of runtime surfaces to delete after cutover

### Phase 1 - Introduce the domain model for the simpler runtime

Make data-model changes before changing execution behavior:

- add `CANCELLED` status
- add `JobAttempt`
- add usage fields
- add tier priority and monthly quota support
- add shared lifecycle service functions

Do not remove `SLURM` yet in this phase. The goal is to give the codebase the right concepts first.

### Phase 2 - Build the local executor and worker

Implement:

- `LocalDockerExecutor`
- worker loop for dispatch + reconciliation
- direct container launch with GPU slot assignment
- log capture and attempt metadata
- cancellation through the executor

At this point, use the new worker in development first. This should replace `FAKE_SLURM` as the primary dev path.

### Phase 3 - Switch production scheduling to the new executor

Cut over the live submission path:

- web/API submit to the database queue
- worker launches containers directly
- console/job actions call the new lifecycle service

Verify:

- single-GPU dev behavior
- multi-GPU production parallelism
- queue ordering by tier
- daily/monthly quota checks
- usage reporting
- failure log capture

### Phase 4 - Delete SLURM-era code and config

Remove:

- `slurm.py`
- `jobs/management/commands/poll_jobs.py`
- `FAKE_SLURM`
- `slurm_job_id`
- `host_workdir`
- `scripts/setup-slurm.sh`
- `scripts/SLURM_README.md`
- compose mounts and docs related to host scheduler binaries
- `RunnerConfig` fields for partition/gpu/cpu/memory/time/mounts/env JSON
- cluster monitoring UI

This is where the codebase should get materially smaller and easier to reason about.

### Phase 5 - Simplify admin, audit, and cleanup around the new runtime

After the runtime cutover:

- reduce the custom console to queue/policy/reporting essentials
- move generic user editing back to Django admin
- replace `simple_history` with job attempts and targeted action logs
- shrink cleanup/orphan tooling
- simplify deployment docs and environment variables

### Phase 6 - Optional organizational cleanup

Once the runtime is stable:

- split `jobs/forms.py`
- split any overly large view modules
- adapt the harness to the new executor

This is worthwhile, but it is not the highest-value first move.

## Implementation Guardrails

To avoid reintroducing the same complexity in a new shape:

- Do not build a generalized scheduler abstraction with cluster concepts you are not using.
- Do not keep both `SLURM` and the new executor long-term.
- Do not model per-job GPU count if every job is always one GPU.
- Do not implement in-place retry before you have a clear attempt model.
- Do not keep arbitrary JSON runtime controls in the admin unless there is a demonstrated need.
- Do not treat cancellation as failure in the new reporting model.

## Bottom line

The codebase is not broadly over-engineered. It is specifically carrying a scheduler and operations model that is too large for the deployment you actually have. The highest-leverage move is to replace `SLURM` with a durable single-host Docker executor, then remove the configuration, deployment, polling, audit, and cleanup machinery that only exists to support that old model.

If you make that one architectural move cleanly, most of the remaining simplification work becomes obvious and mechanical.
