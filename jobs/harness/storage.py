from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from django.conf import settings

from jobs.fs import ensure_dir, write_text


def harness_root_local() -> Path:
    return Path(settings.HARNESS_BASE_DIR)


def run_root_local(run_id: str) -> Path:
    return harness_root_local() / "runs" / run_id


def reports_dir_local(run_id: str) -> Path:
    return run_root_local(run_id) / "reports"


def executor_case_root_local(run_id: str, case_id: str) -> Path:
    return run_root_local(run_id) / "executor" / case_id


def prepare_run_directories(run_id: str) -> dict[str, str]:
    local_root = run_root_local(run_id)
    ensure_dir(reports_dir_local(run_id) / "executor")
    ensure_dir(local_root / "http")
    return {
        "run_root": str(local_root),
        "reports_dir": str(reports_dir_local(run_id)),
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    write_text(path, json.dumps(payload, indent=2, sort_keys=True))


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)
