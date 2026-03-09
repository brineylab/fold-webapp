#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

info()  { echo -e "${GREEN}==>${NC} $*"; }
warn()  { echo -e "${YELLOW}WARNING:${NC} $*"; }
error() { echo -e "${RED}ERROR:${NC} $*" >&2; }
step()  { echo -e "${BLUE}  →${NC} $*"; }

usage() {
    cat <<EOF
Fold Webapp — Model Validation Harness

Usage: ./scripts/run_model_harness.sh [options]

Options:
  --tier smoke|extended         Coverage tier (default: smoke)
  --phase all|http|executor|prepare
                               Which phases to run (default: all)
  --case CASE_ID               Run a single manifest case
  --base-url URL               Base URL for HTTP checks (default: http://localhost:8000)
  --run-id ID                  Override generated run id
  --keep-workdirs              Preserve successful executor/prepared workdirs
  -h, --help                   Show this help message
EOF
}

TIER="smoke"
PHASE="all"
CASE_ID=""
BASE_URL="http://localhost:8000"
KEEP_WORKDIRS=false
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --tier)
            TIER="$2"
            shift 2
            ;;
        --phase)
            PHASE="$2"
            shift 2
            ;;
        --case)
            CASE_ID="$2"
            shift 2
            ;;
        --base-url)
            BASE_URL="$2"
            shift 2
            ;;
        --run-id)
            RUN_ID="$2"
            shift 2
            ;;
        --keep-workdirs)
            KEEP_WORKDIRS=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            error "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

case "$PHASE" in
    direct)
        PHASE="executor"
        ;;
    materialize)
        PHASE="prepare"
        ;;
esac

check_prereqs() {
    command -v docker >/dev/null || {
        error "Docker is required."
        exit 1
    }
    command -v python3 >/dev/null || {
        error "python3 is required."
        exit 1
    }
}

resolve_host_harness_dir() {
    local host_harness_dir="${HARNESS_BASE_DIR:-}"
    local env_harness_dir="${HARNESS_BASE_DIR:-}"
    local env_data_dir="${DATA_DIR:-}"

    if [[ -f .env ]]; then
        set -a
        # shellcheck disable=SC1091
        source .env
        set +a
    fi

    if [[ -z "$env_harness_dir" ]]; then
        host_harness_dir="${HARNESS_BASE_DIR:-$host_harness_dir}"
    fi
    if [[ -z "$env_data_dir" ]]; then
        env_data_dir="${DATA_DIR:-$env_data_dir}"
    fi

    if [[ -z "$host_harness_dir" ]]; then
        if [[ -n "$env_data_dir" ]]; then
            host_harness_dir="$env_data_dir/harness"
        else
            host_harness_dir="$PROJECT_ROOT/data/harness"
        fi
    fi

    if [[ "$host_harness_dir" != /* ]]; then
        host_harness_dir="$(cd "$PROJECT_ROOT" && mkdir -p "$host_harness_dir" && cd "$host_harness_dir" && pwd)"
    fi
    printf '%s\n' "$host_harness_dir"
}

ensure_service_running() {
    local service="$1"
    if [[ "$MANAGE_WITH_COMPOSE" != true ]]; then
        return 0
    fi
    local running
    running="$(docker compose ps --services --status running 2>/dev/null || true)"
    if ! grep -qx "$service" <<<"$running"; then
        error "Required service '$service' is not running."
        error "Start the deployment first with ./deploy.sh start"
        exit 1
    fi
}

json_field() {
    local json_path="$1"
    local field_path="$2"
    python3 - "$json_path" "$field_path" <<'PY'
import json
import sys

path = sys.argv[1]
field_path = sys.argv[2]
with open(path, "r", encoding="utf-8") as handle:
    value = json.load(handle)
for part in field_path.split("."):
    if part:
        value = value[part]
if isinstance(value, list):
    for item in value:
        print(item)
else:
    print(value)
PY
}

json_field_from_text() {
    local field_path="$1"
    local json_text="$2"
    python3 - "$field_path" "$json_text" <<'PY'
import json
import sys

field_path = sys.argv[1]
value = json.loads(sys.argv[2])
for part in field_path.split("."):
    if part:
        value = value[part]
if isinstance(value, list):
    for item in value:
        print(item)
else:
    print(value)
PY
}

run_manage() {
    if [[ "$MANAGE_WITH_COMPOSE" == true ]]; then
        docker compose exec -T web python manage.py "$@"
        return
    fi
    python3 manage.py "$@"
}

cleanup_workdir() {
    local workdir_host="$1"
    local workdir_local="$2"
    local label="$3"

    if [[ "$KEEP_WORKDIRS" == true ]]; then
        return 0
    fi

    if [[ "$HOST_CAN_WRITE" == true ]]; then
        if rm -rf "$workdir_host" >/dev/null 2>&1; then
            return 0
        fi
    fi

    if [[ "$MANAGE_WITH_COMPOSE" == true ]] && docker compose exec -T web rm -rf "$workdir_local" >/dev/null 2>&1; then
        return 0
    fi

    warn "Could not remove $label workdir: $workdir_host"
    return 0
}

host_harness_dir_writable() {
    local host_harness_dir="$1"
    local probe="$host_harness_dir/.harness-write-test.$$"
    if ! mkdir -p "$host_harness_dir" >/dev/null 2>&1; then
        return 1
    fi
    if ! touch "$probe" >/dev/null 2>&1; then
        return 1
    fi
    rm -f "$probe"
}

run_executor_case() {
    local case_id="$1"
    step "Preparing executor case: $case_id"
    local metadata_json
    if ! metadata_json="$(run_manage harness_executor --run-id "$RUN_ID" --case "$case_id")"; then
        warn "Failed to prepare executor case: $case_id"
        return 1
    fi
    local workdir workdir_local timeout_sec
    workdir="$(json_field_from_text "workdir" "$metadata_json")"
    workdir_local="$workdir"
    timeout_sec="$(json_field_from_text "timeout_sec" "$metadata_json")"

    local stdout_path="$workdir/stdout.log"
    local stderr_path="$workdir/stderr.log"
    local rc=0

    step "Executing prepared runner script: $case_id"
    if command -v timeout >/dev/null 2>&1; then
        set +e
        timeout "${timeout_sec}s" bash "$workdir/job.sh" >"$stdout_path" 2>"$stderr_path"
        rc=$?
        set -e
    else
        warn "'timeout' not found; running without an execution timeout."
        set +e
        bash "$workdir/job.sh" >"$stdout_path" 2>"$stderr_path"
        rc=$?
        set -e
    fi

    local verify_json
    verify_json="$(run_manage harness_executor --run-id "$RUN_ID" --case "$case_id" --verify --exit-code "$rc")"
    local ok
    ok="$(json_field_from_text "ok" "$verify_json")"
    if [[ "$ok" != "True" ]]; then
        warn "Executor case failed: $case_id"
        return 1
    fi

    cleanup_workdir "$workdir" "$workdir_local" "executor-run"
    return 0
}

run_prepare_case() {
    local case_id="$1"
    step "Preparing extended case: $case_id"
    local metadata_json
    if ! metadata_json="$(run_manage harness_executor --run-id "$RUN_ID" --case "$case_id")"; then
        warn "Failed to prepare extended case: $case_id"
        return 1
    fi
    local workdir workdir_local
    workdir="$(json_field_from_text "workdir" "$metadata_json")"
    workdir_local="$workdir"
    local verify_json
    verify_json="$(run_manage harness_executor --run-id "$RUN_ID" --case "$case_id" --verify --prepare-only)"
    local ok
    ok="$(json_field_from_text "ok" "$verify_json")"
    if [[ "$ok" != "True" ]]; then
        warn "Prepare-only case failed: $case_id"
        return 1
    fi
    cleanup_workdir "$workdir" "$workdir_local" "prepared"
    return 0
}

check_prereqs
MANAGE_WITH_COMPOSE=false
if docker compose ps --services --status running 2>/dev/null | grep -qx "web"; then
    MANAGE_WITH_COMPOSE=true
fi

ensure_service_running web
if [[ "$PHASE" == "all" || "$PHASE" == "http" ]]; then
    ensure_service_running worker
fi

HOST_HARNESS_DIR="$(resolve_host_harness_dir)"
RUN_ROOT_HOST="$HOST_HARNESS_DIR/runs/$RUN_ID"
PREPARE_JSON="$RUN_ROOT_HOST/prepare.json"
HOST_CAN_WRITE=false
if host_harness_dir_writable "$HOST_HARNESS_DIR"; then
    HOST_CAN_WRITE=true
fi

if [[ "$PHASE" == "all" || "$PHASE" == "executor" ]]; then
    if [[ "$HOST_CAN_WRITE" != true ]]; then
        error "The host account cannot write to HARNESS_BASE_DIR: $HOST_HARNESS_DIR"
        error "Executor validation requires host write access to the shared harness directory."
        exit 1
    fi
fi

if [[ "$HOST_CAN_WRITE" != true && "$KEEP_WORKDIRS" != true ]]; then
    warn "Host write access is unavailable for $HOST_HARNESS_DIR; successful case cleanup will be skipped."
fi

info "Preparing harness run $RUN_ID"
prepare_args=(harness_prepare --run-id "$RUN_ID" --tier "$TIER" --phase "$PHASE" --base-url "$BASE_URL")
if [[ -n "$CASE_ID" ]]; then
    prepare_args+=(--case "$CASE_ID")
fi
run_manage "${prepare_args[@]}" >/dev/null

run_failed=0

if [[ "$PHASE" == "all" || "$PHASE" == "executor" ]]; then
    while IFS= read -r case_id; do
        [[ -n "$case_id" ]] || continue
        run_executor_case "$case_id" || run_failed=1
    done < <(json_field "$PREPARE_JSON" "executor_case_ids")
fi

if [[ "$PHASE" == "all" || "$PHASE" == "executor" || "$PHASE" == "prepare" ]]; then
    while IFS= read -r case_id; do
        [[ -n "$case_id" ]] || continue
        run_prepare_case "$case_id" || run_failed=1
    done < <(json_field "$PREPARE_JSON" "prepare_only_case_ids")
fi

if [[ "$PHASE" == "all" || "$PHASE" == "http" ]]; then
    info "Running HTTP/API validation"
    http_args=(harness_http --run-id "$RUN_ID" --tier "$TIER" --base-url "$BASE_URL")
    if [[ -n "$CASE_ID" ]]; then
        http_args+=(--case "$CASE_ID")
    fi
    run_manage "${http_args[@]}" >/dev/null || run_failed=1
fi

run_manage harness_summary --run-id "$RUN_ID" >/dev/null
SUMMARY_MD="$RUN_ROOT_HOST/reports/summary.md"

if [[ "$run_failed" -ne 0 ]]; then
    warn "Harness completed with failures."
    warn "Summary: $SUMMARY_MD"
    exit 1
fi

info "Harness completed successfully."
echo "Summary: $SUMMARY_MD"
