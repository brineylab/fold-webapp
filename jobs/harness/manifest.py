from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile

from model_types import get_submittable_model_types


MANIFEST_PATH = Path(settings.BASE_DIR) / "harness" / "cases.yaml"
FIXTURE_ROOT = Path(settings.BASE_DIR) / "harness" / "fixtures"

TRANSPORT_ALIASES = {
    "direct": "executor",
    "materialize_only": "prepare_only",
}
VALID_TRANSPORTS = {"web", "api", "executor", "prepare_only"}


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


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _normalize_transport(transport: str) -> str:
    return TRANSPORT_ALIASES.get(transport, transport)


@lru_cache(maxsize=1)
def load_cases() -> list[HarnessCase]:
    manifest = _read_yaml(MANIFEST_PATH)
    raw_cases = manifest.get("cases", [])
    cases = [
        HarnessCase(
            id=item["id"],
            tier=item["tier"],
            model_key=item["model_key"],
            transport=_normalize_transport(item["transport"]),
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
        if case.transport not in VALID_TRANSPORTS:
            raise ValueError(f"Invalid transport {case.transport!r} for {case.id}")
        if case.tier not in {"smoke", "extended"}:
            raise ValueError(f"Invalid tier {case.tier!r} for {case.id}")

    model_keys = {model_type.key for model_type in get_submittable_model_types()}
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


def fixture_path(relative_path: str) -> Path:
    path = FIXTURE_ROOT / relative_path
    if not path.exists():
        raise FileNotFoundError(f"Missing harness fixture: {relative_path}")
    return path


def resolve_case_fields(case: HarnessCase) -> dict[str, Any]:
    resolved: dict[str, Any] = {}
    for key, value in case.fields.items():
        if isinstance(value, dict) and "fixture_text" in value:
            resolved[key] = fixture_path(value["fixture_text"]).read_text(
                encoding="utf-8"
            )
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
        uploads[field_name] = SimpleUploadedFile(path.name, path.read_bytes())
    return uploads


def api_payload_for_case(case: HarnessCase) -> dict[str, Any]:
    payload = resolve_case_fields(case)
    payload["model"] = case.model_key
    if "name" not in payload:
        payload["name"] = f"Harness {case.id}"
    return payload
