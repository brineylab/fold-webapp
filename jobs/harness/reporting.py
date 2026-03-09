from __future__ import annotations

from typing import Any

from jobs.harness.executor import executor_reports_for_run
from jobs.harness.storage import read_json, reports_dir_local, run_root_local


def summarize_run(run_id: str) -> dict[str, Any]:
    prepare = read_json(run_root_local(run_id) / "prepare.json")
    executor_reports = executor_reports_for_run(run_id)
    http_report_path = reports_dir_local(run_id) / "http.json"
    http_report = read_json(http_report_path) if http_report_path.exists() else None
    failures = [
        report["case_id"]
        for report in executor_reports
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
        "executor_reports": executor_reports,
        "direct_reports": executor_reports,
        "http_report": http_report,
        "failed_items": failures,
        "ok": not failures,
    }
