# Model Validation Harness

`./deploy.sh validate-models` is the canonical post-install validation command.
It delegates to `./scripts/run_model_harness.sh`, which prepares a harness run,
executes the requested checks, and writes a report bundle under
`HARNESS_BASE_DIR`.

## Recommended Usage

For the normal Compose deployment:

```bash
./deploy.sh validate-models --tier smoke
```

`deploy.sh` ensures the `web` and `worker` services are up before running the
harness.

For advanced use, you can invoke the script directly:

```bash
./scripts/run_model_harness.sh --tier smoke
./scripts/run_model_harness.sh --tier extended
```

If you run the script directly outside Compose, it falls back to local
`python3 manage.py ...` commands and therefore requires the repo's Python
environment to be installed on the host.

## What A Harness Run Does

Each run gets a timestamp-style run id and a directory at:

```text
HARNESS_BASE_DIR/runs/<run_id>/
```

The harness then:

1. Writes run metadata and selected case information to `prepare.json`
2. Creates or refreshes the temporary harness users and API keys
3. Executes the requested phases
4. Writes machine-readable reports and a human-readable summary

The harness-managed users are:

- `harness_admin`
- `harness_limited`

These are recreated as needed for each run.

## Tiers

### `smoke`

Runs the canonical installation-validation coverage:

- One smoke case per submittable model type
- Live login, model listing, submit-form, submission, detail, download, and API
  checks for smoke cases that use `web` or `api`
- Real executor runs for smoke cases

### `extended`

Includes everything in `smoke`, plus the extended manifest cases from
`harness/cases.yaml`. Extended cases are used to exercise alternate validation,
normalization, and workdir-preparation branches without turning every extended
run into a full compute workload.

## Phases

### `all`

Runs the full post-install harness:

- Executor runs for smoke cases
- Prepare-only coverage for extended cases when `--tier extended`
- HTTP and API coverage for smoke web/API cases

### `http`

Runs only the browserless HTTP and API checks against the live deployment.

This phase writes `reports/http.json`.

### `executor`

Runs only the smoke executor cases. For each selected smoke case, the harness:

- Materializes the workdir and runner script
- Executes the generated `job.sh`
- Verifies the resulting artifacts against the case's `artifact_checks`

This phase writes per-case reports under `reports/executor/`.

### `prepare`

Runs only the prepare-only case verification path. This is the modern name for
what older docs called "materialize" coverage.

### Compatibility aliases

These aliases still work:

- `direct` -> `executor`
- `materialize` -> `prepare`

For new docs and new automation, use the canonical names:

- `http`
- `executor`
- `prepare`
- `all`

## Useful Options

```bash
./scripts/run_model_harness.sh --tier smoke --phase http
./scripts/run_model_harness.sh --tier smoke --phase executor --case smoke-boltz2
./scripts/run_model_harness.sh --tier extended --phase prepare
./scripts/run_model_harness.sh --tier smoke --keep-workdirs
./scripts/run_model_harness.sh --tier smoke --base-url http://localhost:8000
./scripts/run_model_harness.sh --run-id manual-test-001
```

Option summary:

- `--tier smoke|extended`: coverage level
- `--phase all|http|executor|prepare`: which phases to run
- `--case CASE_ID`: limit the run to one manifest case
- `--base-url URL`: target deployment URL, default `http://localhost:8000`
- `--run-id ID`: override the generated run id
- `--keep-workdirs`: preserve successful executor and prepare workdirs

## Reports

Reports are written under:

```text
HARNESS_BASE_DIR/runs/<run_id>/reports/
```

Important outputs:

- `summary.md`: top-level human-readable result summary
- `summary.json`: machine-readable summary
- `http.json`: HTTP and API phase report
- `executor/<case_id>.json`: per-case executor and prepare verification reports

The main report to inspect first is:

```text
HARNESS_BASE_DIR/runs/<run_id>/reports/summary.md
```

## Prerequisites And Constraints

- Docker must be installed
- `python3` must be available on the host
- The target deployment must be reachable at `--base-url`
- If Compose is managing the app, the `web` service must be running for any
  harness phase
- If Compose is managing the app and you run `all` or `http`, the `worker`
  service must also be running
- Executor validation requires host write access to `HARNESS_BASE_DIR`

If the host account cannot write `HARNESS_BASE_DIR`, executor validation will
fail before it runs smoke cases.

## Workdir Cleanup

Successful executor and prepare-only workdirs are deleted by default. Use
`--keep-workdirs` when you want to inspect generated scripts, inputs, outputs,
or logs after a run.

## Manifest Source Of Truth

The case list lives in [`../harness/cases.yaml`](../harness/cases.yaml).

Important enforced invariants:

- Every submittable model type must have exactly one `tier: smoke` case
- Every smoke case must define explicit `artifact_checks`
- Extended cases are additive and do not replace smoke coverage

The maintainer-facing manifest details are documented in
[`../harness/README.md`](../harness/README.md).
