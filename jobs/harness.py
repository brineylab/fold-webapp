from __future__ import annotations

import fnmatch
import json
import shutil
import uuid
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.forms import Form

from console.models import RunnerConfig
from jobs.fs import ensure_dir, write_text
from model_types import get_model_type, get_submittable_model_types
from runners import get_runner


MANIFEST_PATH = Path(settings.BASE_DIR) / "harness" / "cases.yaml"
FIXTURE_ROOT = Path(settings.BASE_DIR) / "harness" / "fixtures"


@dataclass(frozen=True)
class HarnessCase:
    id: str
    tier: str
    model_key: str
    transport: str
    fields: dict[str, Any]
    files: dict[str, str]
    expected_outputs: list[str | list[str]]
    timeout_sec: int
    requires: list[str]


@dataclass(frozen=True)
class MaterializedCase:
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
    expected_outputs: list[str | list[str]]
    timeout_sec: int
    requires: list[str]


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


@lru_cache(maxsize=1)
def load_cases() -> list[HarnessCase]:
    manifest = _read_yaml(MANIFEST_PATH)
    raw_cases = manifest.get("cases", [])
    cases = [
        HarnessCase(
            id=item["id"],
            tier=item["tier"],
            model_key=item["model_key"],
            transport=item["transport"],
            fields=item.get("fields", {}),
            files=item.get("files", {}),
            expected_outputs=item.get("expected_outputs", []),
            timeout_sec=int(item.get("timeout_sec", 900)),
            requires=list(item.get("requires", [])),
        )
        for item in raw_cases
    ]
    _validate_cases(cases)
    return cases


def _validate_cases(cases: list[HarnessCase]) -> None:
    seen_ids: set[str] = set()
    for case in cases:
        if case.id in seen_ids:
            raise ValueError(f"Duplicate harness case id: {case.id}")
        seen_ids.add(case.id)
        if case.transport not in {"web", "api", "direct", "materialize_only"}:
            raise ValueError(f"Invalid transport {case.transport!r} for {case.id}")
        if case.tier not in {"smoke", "extended"}:
            raise ValueError(f"Invalid tier {case.tier!r} for {case.id}")

    model_keys = {mt.key for mt in get_submittable_model_types()}
    for case in cases:
        if case.model_key not in model_keys:
            raise ValueError(f"Unknown model key {case.model_key!r} in harness manifest")

    for model_key in model_keys:
        smoke_count = sum(
            1
            for case in cases
            if case.model_key == model_key and case.tier == "smoke"
        )
        if smoke_count != 1:
            raise ValueError(
                f"Expected exactly one smoke case for {model_key}, found {smoke_count}"
            )


def get_case(case_id: str) -> HarnessCase:
    for case in load_cases():
        if case.id == case_id:
            return case
    raise KeyError(case_id)


def select_cases(*, tier: str, case_id: str | None = None) -> list[HarnessCase]:
    if case_id:
        case = get_case(case_id)
        if tier == "smoke" and case.tier != "smoke":
            raise ValueError(f"Case {case_id} is not a smoke case")
        return [case]

    cases = [case for case in load_cases() if case.tier == "smoke"]
    if tier == "extended":
        cases.extend(case for case in load_cases() if case.tier == "extended")
    return cases


def harness_root_local() -> Path:
    return Path(settings.HARNESS_BASE_DIR)


def run_root_local(run_id: str) -> Path:
    return harness_root_local() / "runs" / run_id


def reports_dir_local(run_id: str) -> Path:
    return run_root_local(run_id) / "reports"


def direct_case_root_local(run_id: str, case_id: str) -> Path:
    return run_root_local(run_id) / "direct" / case_id


def prepare_run_directories(run_id: str) -> dict[str, str]:
    local_root = run_root_local(run_id)
    ensure_dir(reports_dir_local(run_id) / "direct")
    ensure_dir(local_root / "http")
    return {
        "run_root": str(local_root),
        "reports_dir": str(reports_dir_local(run_id)),
    }


def fixture_path(relative_path: str) -> Path:
    path = FIXTURE_ROOT / relative_path
    if not path.exists():
        raise FileNotFoundError(f"Missing harness fixture: {relative_path}")
    return path


def resolve_case_fields(case: HarnessCase) -> dict[str, Any]:
    resolved: dict[str, Any] = {}
    for key, value in case.fields.items():
        if isinstance(value, dict) and "fixture_text" in value:
            resolved[key] = fixture_path(value["fixture_text"]).read_text(encoding="utf-8")
        else:
            resolved[key] = value
    return resolved


def submission_data_from_fields(fields: dict[str, Any]) -> dict[str, str]:
    data: dict[str, str] = {}
    for key, value in fields.items():
        if value is None:
            continue
        if isinstance(value, bool):
            if value:
                data[key] = "on"
            continue
        if isinstance(value, (dict, list)):
            data[key] = json.dumps(value)
        else:
            data[key] = str(value)
    return data


def upload_files_for_case(case: HarnessCase) -> dict[str, SimpleUploadedFile]:
    uploads: dict[str, SimpleUploadedFile] = {}
    for field_name, relative_path in case.files.items():
        path = fixture_path(relative_path)
        uploads[field_name] = SimpleUploadedFile(
            path.name,
            path.read_bytes(),
        )
    return uploads


def api_payload_for_case(case: HarnessCase) -> dict[str, Any]:
    payload = resolve_case_fields(case)
    payload["model"] = case.model_key
    if "name" not in payload:
        payload["name"] = f"Harness {case.id}"
    return payload


def _materialized_report_path(run_id: str, case_id: str) -> Path:
    return reports_dir_local(run_id) / "direct" / f"{case_id}.json"


def materialized_metadata_path(run_id: str, case_id: str) -> Path:
    return direct_case_root_local(run_id, case_id) / "metadata.json"


def _build_form(case: HarnessCase) -> tuple[Form, dict[str, Any], dict[str, SimpleUploadedFile]]:
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


def materialize_case(run_id: str, case_id: str) -> MaterializedCase:
    case = get_case(case_id)
    model_type = get_model_type(case.model_key)

    workdir = direct_case_root_local(run_id, case.id)
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

    metadata = MaterializedCase(
        case_id=case.id,
        model_key=case.model_key,
        runner_key=runner_key,
        job_id=job.id,
        transport=case.transport,
        workdir=str(workdir),
        output_dir=str(workdir / "output"),
        metadata_path=str(materialized_metadata_path(run_id, case.id)),
        stdout_path=str(workdir / "stdout.log"),
        stderr_path=str(workdir / "stderr.log"),
        expected_outputs=case.expected_outputs,
        timeout_sec=case.timeout_sec,
        requires=case.requires,
    )
    write_json(materialized_metadata_path(run_id, case.id), asdict(metadata))
    return metadata


def _iter_expected_matches(
    file_names: list[str],
    expected_outputs: list[str | list[str]],
) -> tuple[list[dict[str, Any]], list[str]]:
    matches: list[dict[str, Any]] = []
    errors: list[str] = []

    for index, requirement in enumerate(expected_outputs, start=1):
        patterns = requirement if isinstance(requirement, list) else [requirement]
        expanded_patterns = set(patterns)
        expanded_patterns.update(
            pattern[3:]
            for pattern in patterns
            if pattern.startswith("**/")
        )
        matched = [
            name
            for name in file_names
            if any(fnmatch.fnmatch(name, pattern) for pattern in expanded_patterns)
        ]
        if not matched:
            errors.append(
                f"Missing expected output requirement {index}: {', '.join(patterns)}"
            )
        matches.append({"patterns": patterns, "matched": matched})
    return matches, errors


def _scan_text_log(path: Path) -> list[str]:
    if not path.exists() or not path.is_file():
        return []
    text = path.read_text(encoding="utf-8", errors="ignore")
    errors = []
    if "traceback" in text.lower():
        errors.append(f"Traceback found in {path.name}")
    return errors


def verify_materialized_case(
    run_id: str,
    case_id: str,
    *,
    exit_code: int,
    materialized_only: bool = False,
) -> dict[str, Any]:
    metadata_path = materialized_metadata_path(run_id, case_id)
    metadata = read_json(metadata_path)
    output_dir = Path(metadata["output_dir"])
    report: dict[str, Any] = {
        "case_id": case_id,
        "model_key": metadata["model_key"],
        "runner_key": metadata["runner_key"],
        "phase": "materialize" if materialized_only else "direct",
        "ok": True,
        "exit_code": exit_code,
        "errors": [],
        "matched_outputs": [],
        "output_files": [],
        "workdir": metadata["workdir"],
    }

    if not materialized_only and exit_code != 0:
        report["errors"].append(f"Direct execution exited with code {exit_code}")

    if output_dir.exists():
        file_names = [
            str(path.relative_to(output_dir))
            for path in sorted(output_dir.rglob("*"))
            if path.is_file()
        ]
    else:
        file_names = []

    report["output_files"] = file_names

    if not materialized_only:
        matches, match_errors = _iter_expected_matches(
            file_names,
            metadata.get("expected_outputs", []),
        )
        report["matched_outputs"] = matches
        report["errors"].extend(match_errors)
        report["errors"].extend(_scan_text_log(Path(metadata["stdout_path"])))
        report["errors"].extend(_scan_text_log(Path(metadata["stderr_path"])))

    report["ok"] = not report["errors"]
    write_json(_materialized_report_path(run_id, case_id), report)
    return report


def direct_reports_for_run(run_id: str) -> list[dict[str, Any]]:
    reports_root = reports_dir_local(run_id) / "direct"
    if not reports_root.exists():
        return []
    return [read_json(path) for path in sorted(reports_root.glob("*.json"))]


def summarize_run(run_id: str) -> dict[str, Any]:
    prepare = read_json(run_root_local(run_id) / "prepare.json")
    direct_reports = direct_reports_for_run(run_id)
    http_report_path = reports_dir_local(run_id) / "http.json"
    http_report = read_json(http_report_path) if http_report_path.exists() else None
    failures = [
        report["case_id"]
        for report in direct_reports
        if not report.get("ok", False)
    ]
    if http_report and not http_report.get("ok", False):
        failures.append("http")

    return {
        "run_id": run_id,
        "tier": prepare["tier"],
        "phase": prepare["phase"],
        "case": prepare.get("case"),
        "base_url": prepare["base_url"],
        "direct_reports": direct_reports,
        "http_report": http_report,
        "failed_items": failures,
        "ok": not failures,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    write_text(path, json.dumps(payload, indent=2, sort_keys=True))


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)
