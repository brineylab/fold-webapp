# Model Harness

`./deploy.sh validate-models` runs the post-install acceptance harness for the deployed app.

## What It Covers

- Live login, model selection, submit, detail, and API checks against the running deployment
- One direct runner execution for each submittable web model
- Extended materialization-only coverage for alternate form and workdir branches in `harness/cases.yaml`

## Reports

Harness artifacts are written under `HARNESS_BASE_DIR/runs/<run_id>/`.

By default `./deploy.sh install` provisions `HARNESS_BASE_DIR=$DATA_DIR/harness`, with `DATA_DIR` defaulting to `~/.fold-webapp/data`.

- `reports/summary.md`
- `reports/summary.json`
- `reports/direct/*.json`
- `reports/http.json`

Successful direct-run workdirs are deleted by default. Pass `--keep-workdirs` to retain them.
