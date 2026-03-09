from __future__ import annotations

import shutil
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from django.forms import Form

from console.models import RunnerConfig
from jobs.fs import ensure_dir, write_text
from jobs.harness.manifest import (
    HarnessCase,
    get_case,
    resolve_case_fields,
    submission_data_from_fields,
    upload_files_for_case,
)
from jobs.harness.storage import (
    executor_case_root_local,
    read_json,
    reports_dir_local,
    write_json,
)
from jobs.harness.validation import (
    ArtifactCheck,
    ensure_artifact_check,
    evaluate_artifact_checks,
    validate_artifact_path,
)
from model_types import get_model_type
from runners import get_runner


@dataclass(frozen=True)
class PreparedCase:
    case_id: str
    model_key: str
    runner_key: str
    job_id: str
    transport: str
    workdir: str
    output_dir: str
    metadata_path: str
    stdout_path: str
    stderr_path: str
    artifact_checks: list[dict[str, Any]]
    expected_outputs: list[str | list[str]]
    timeout_sec: int
    requires: list[str]


def _executor_report_path(run_id: str, case_id: str) -> Path:
    return reports_dir_local(run_id) / "executor" / f"{case_id}.json"


def prepared_case_metadata_path(run_id: str, case_id: str) -> Path:
    return executor_case_root_local(run_id, case_id) / "metadata.json"


def _build_form(
    case: HarnessCase,
) -> tuple[Form, dict[str, Any], dict[str, Any]]:
    model_type = get_model_type(case.model_key)
    fields = resolve_case_fields(case)
    if "name" not in fields:
        fields["name"] = f"Harness {case.id}"
    uploads = upload_files_for_case(case)
    form = model_type.get_form(
        submission_data_from_fields(fields),
        uploads,
    )
    return form, fields, uploads


def prepare_executor_case(run_id: str, case_id: str) -> PreparedCase:
    case = get_case(case_id)
    model_type = get_model_type(case.model_key)

    workdir = executor_case_root_local(run_id, case.id)
    if workdir.exists():
        shutil.rmtree(workdir)
    ensure_dir(workdir)

    form, _, _ = _build_form(case)
    if not form.is_valid():
        raise ValueError(f"Harness case {case.id} is invalid: {form.errors.as_json()}")

    model_type.validate(form.cleaned_data)
    input_payload = model_type.normalize_inputs(form.cleaned_data)
    runner_key = model_type.resolve_runner_key(form.cleaned_data)
    runner = get_runner(runner_key)
    config = RunnerConfig.get_config(runner_key)

    class HarnessJob:
        def __init__(self):
            self.id = str(uuid.uuid4())
            self.model_key = case.model_key
            self.runner = runner_key
            self.params = input_payload.get("params", {})
            self.workdir = workdir

    job = HarnessJob()
    model_type.prepare_workdir(job, input_payload)
    script = runner.build_script(job, config=config)
    script_path = workdir / "job.sh"
    write_text(script_path, script)

    metadata = PreparedCase(
        case_id=case.id,
        model_key=case.model_key,
        runner_key=runner_key,
        job_id=job.id,
        transport=case.transport,
        workdir=str(workdir),
        output_dir=str(workdir / "output"),
        metadata_path=str(prepared_case_metadata_path(run_id, case.id)),
        stdout_path=str(workdir / "stdout.log"),
        stderr_path=str(workdir / "stderr.log"),
        artifact_checks=[check.as_dict() for check in case.artifact_checks],
        expected_outputs=case.expected_outputs,
        timeout_sec=case.timeout_sec,
        requires=case.requires,
    )
    write_json(prepared_case_metadata_path(run_id, case.id), asdict(metadata))
    return metadata


def _scan_text_log(path: Path) -> list[str]:
    if not path.exists() or not path.is_file():
        return []
    text = path.read_text(encoding="utf-8", errors="ignore")
    errors = []
    if "traceback" in text.lower():
        errors.append(f"Traceback found in {path.name}")
    return errors


def verify_prepared_case(
    run_id: str,
    case_id: str,
    *,
    exit_code: int,
    prepare_only: bool = False,
) -> dict[str, Any]:
    metadata = read_json(prepared_case_metadata_path(run_id, case_id))
    output_dir = Path(metadata["output_dir"])
    report: dict[str, Any] = {
        "case_id": case_id,
        "model_key": metadata["model_key"],
        "runner_key": metadata["runner_key"],
        "phase": "prepare" if prepare_only else "executor",
        "ok": True,
        "exit_code": exit_code,
        "errors": [],
        "matched_outputs": [],
        "output_files": [],
        "workdir": metadata["workdir"],
    }

    if not prepare_only and exit_code != 0:
        report["errors"].append(f"Executor run exited with code {exit_code}")

    if output_dir.exists():
        output_files = [
            {
                "name": str(path.relative_to(output_dir)),
                "size": path.stat().st_size,
                "path": path,
            }
            for path in sorted(output_dir.rglob("*"))
            if path.is_file()
        ]
    else:
        output_files = []

    report["output_files"] = [item["name"] for item in output_files]
    report["output_file_details"] = [
        {"name": item["name"], "size_bytes": int(item["size"])}
        for item in output_files
    ]

    if not prepare_only:
        artifact_reports, artifact_errors = evaluate_artifact_checks(
            output_files,
            _artifact_checks_from_metadata(metadata),
            _validate_executor_candidate,
        )
        report["artifact_reports"] = artifact_reports
        report["matched_outputs"] = [
            {
                "patterns": item["patterns"],
                "matched": [match["name"] for match in item["matched"]],
            }
            for item in artifact_reports
        ]
        report["errors"].extend(artifact_errors)
        report["errors"].extend(_scan_text_log(Path(metadata["stdout_path"])))
        report["errors"].extend(_scan_text_log(Path(metadata["stderr_path"])))
    else:
        report["artifact_reports"] = []

    report["ok"] = not report["errors"]
    write_json(_executor_report_path(run_id, case_id), report)
    return report


def executor_reports_for_run(run_id: str) -> list[dict[str, Any]]:
    reports_root = reports_dir_local(run_id) / "executor"
    if not reports_root.exists():
        return []
    return [read_json(path) for path in sorted(reports_root.glob("*.json"))]


def _artifact_checks_from_metadata(metadata: dict[str, Any]) -> list[ArtifactCheck]:
    raw_checks = metadata.get("artifact_checks")
    if raw_checks:
        return [ensure_artifact_check(item) for item in raw_checks]

    return [
        ArtifactCheck(patterns=patterns if isinstance(patterns, list) else [patterns])
        for patterns in metadata.get("expected_outputs", [])
    ]


def _validate_executor_candidate(
    candidate: dict[str, Any],
    check: ArtifactCheck,
) -> list[str]:
    return validate_artifact_path(Path(candidate["path"]), check)
