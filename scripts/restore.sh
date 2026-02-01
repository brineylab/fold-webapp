#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

SKIP_CONFIRM=false
RESTORE_ENV=false

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS] <backup-archive>

Restore the Fold web application from a backup archive.

Arguments:
  <backup-archive>    Path to a fold-webapp-backup-*.tar.gz file

Options:
  --restore-env       Also restore the .env configuration file
  --yes               Skip confirmation prompt
  -h, --help          Show this help message
EOF
}

ARCHIVE=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --restore-env) RESTORE_ENV=true; shift ;;
        --yes)         SKIP_CONFIRM=true; shift ;;
        -h|--help)     usage; exit 0 ;;
        -*)            echo "Unknown option: $1" >&2; usage; exit 1 ;;
        *)             ARCHIVE="$1"; shift ;;
    esac
done

if [ -z "$ARCHIVE" ]; then
    echo "Error: No backup archive specified." >&2
    usage
    exit 1
fi

if [ ! -f "$ARCHIVE" ]; then
    echo "Error: File not found: $ARCHIVE" >&2
    exit 1
fi

# Extract to temp dir for inspection
WORK_DIR="$(mktemp -d)"
cleanup() {
    rm -rf "$WORK_DIR"
}
trap cleanup EXIT

tar -xzf "$ARCHIVE" -C "$WORK_DIR"

# Show manifest
echo "=== Backup Manifest ==="
if [ -f "$WORK_DIR/manifest.txt" ]; then
    cat "$WORK_DIR/manifest.txt"
else
    echo "(no manifest found)"
fi
echo "======================="
echo

# Show what will be restored
echo "This will restore:"
[ -f "$WORK_DIR/db.sqlite3" ]  && echo "  - Database (db.sqlite3)"
[ -f "$WORK_DIR/jobs.tar.gz" ] && echo "  - Job data"
if [ "$RESTORE_ENV" = true ] && [ -f "$WORK_DIR/env" ]; then
    echo "  - .env configuration"
fi
echo
echo "Target: $PROJECT_DIR"
echo

# Confirm
if [ "$SKIP_CONFIRM" = false ]; then
    echo "WARNING: This will overwrite existing data. This operation is destructive."
    read -rp "Continue? [y/N] " confirm
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        echo "Restore cancelled."
        exit 0
    fi
fi

# Stop services if running
if docker compose -f "$PROJECT_DIR/docker-compose.yml" ps --status running 2>/dev/null | grep -q "web\|poller"; then
    echo "Stopping Docker services..."
    docker compose -f "$PROJECT_DIR/docker-compose.yml" down
fi

# Ensure data directories exist
mkdir -p "$PROJECT_DIR/data/db" "$PROJECT_DIR/data/jobs"

# Restore database
if [ -f "$WORK_DIR/db.sqlite3" ]; then
    echo "Restoring database..."
    cp "$WORK_DIR/db.sqlite3" "$PROJECT_DIR/data/db/db.sqlite3"
fi

# Restore job data
if [ -f "$WORK_DIR/jobs.tar.gz" ]; then
    echo "Restoring job data..."
    tar -xzf "$WORK_DIR/jobs.tar.gz" -C "$PROJECT_DIR/data/jobs"
fi

# Restore .env if requested
if [ "$RESTORE_ENV" = true ] && [ -f "$WORK_DIR/env" ]; then
    echo "Restoring .env configuration..."
    cp "$WORK_DIR/env" "$PROJECT_DIR/.env"
fi

echo
echo "Restore complete."
echo
echo "Next steps:"
echo "  1. Review the restored data"
echo "  2. Start services:  ./deploy.sh start"
echo "  3. Verify the application is working correctly"
