from jobs.harness.executor import (
    PreparedCase,
    executor_case_root_local,
    executor_reports_for_run,
    prepare_executor_case,
    prepared_case_metadata_path,
    verify_prepared_case,
)
from jobs.harness.manifest import (
    HarnessCase,
    api_payload_for_case,
    get_case,
    load_cases,
    resolve_case_fields,
    select_cases,
    submission_data_from_fields,
    upload_files_for_case,
)
from jobs.harness.reporting import summarize_run
from jobs.harness.storage import (
    harness_root_local,
    prepare_run_directories,
    read_json,
    reports_dir_local,
    run_root_local,
    write_json,
)

# Backward-compatible aliases for older harness scripts and imports.
MaterializedCase = PreparedCase
direct_case_root_local = executor_case_root_local
direct_reports_for_run = executor_reports_for_run
materialize_case = prepare_executor_case
materialized_metadata_path = prepared_case_metadata_path
verify_materialized_case = verify_prepared_case

__all__ = [
    "HarnessCase",
    "MaterializedCase",
    "PreparedCase",
    "api_payload_for_case",
    "direct_case_root_local",
    "direct_reports_for_run",
    "executor_case_root_local",
    "executor_reports_for_run",
    "get_case",
    "harness_root_local",
    "load_cases",
    "materialize_case",
    "materialized_metadata_path",
    "prepare_executor_case",
    "prepare_run_directories",
    "prepared_case_metadata_path",
    "read_json",
    "reports_dir_local",
    "resolve_case_fields",
    "run_root_local",
    "select_cases",
    "submission_data_from_fields",
    "summarize_run",
    "upload_files_for_case",
    "verify_materialized_case",
    "verify_prepared_case",
    "write_json",
]
