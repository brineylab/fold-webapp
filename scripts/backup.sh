#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Defaults
BACKUP_DIR="${BACKUP_DIR:-$PROJECT_DIR/backups}"
RETENTION_DAYS="${BACKUP_RETENTION:-30}"
QUIET=false

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Create a backup of the Fold web application (database, job data, config).

Options:
  --dir <path>        Backup destination directory (default: ./backups)
  --retention <days>  Delete backups older than N days (default: 30, 0 to disable)
  --quiet             Minimal output (suitable for cron)
  -h, --help          Show this help message
EOF
}

log() {
    if [ "$QUIET" = false ]; then
        echo "$@"
    fi
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dir)       BACKUP_DIR="$2"; shift 2 ;;
        --retention) RETENTION_DAYS="$2"; shift 2 ;;
        --quiet)     QUIET=true; shift ;;
        -h|--help)   usage; exit 0 ;;
        *)           echo "Unknown option: $1" >&2; usage; exit 1 ;;
    esac
done

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
WORK_DIR="$BACKUP_DIR/.work-$TIMESTAMP"
ARCHIVE_NAME="fold-webapp-backup-${TIMESTAMP}.tar.gz"
ARCHIVE_PATH="$BACKUP_DIR/$ARCHIVE_NAME"

mkdir -p "$WORK_DIR"

cleanup() {
    rm -rf "$WORK_DIR"
}
trap cleanup EXIT

log "Starting backup..."

# --- Database backup ---
log "  Backing up database..."
if docker compose -f "$PROJECT_DIR/docker-compose.yml" ps --status running 2>/dev/null | grep -q "web"; then
    docker compose -f "$PROJECT_DIR/docker-compose.yml" exec -T web \
        python manage.py backup_db --output /tmp/backup_db.sqlite3
    docker compose -f "$PROJECT_DIR/docker-compose.yml" cp web:/tmp/backup_db.sqlite3 "$WORK_DIR/db.sqlite3"
    docker compose -f "$PROJECT_DIR/docker-compose.yml" exec -T web rm -f /tmp/backup_db.sqlite3
else
    # Containers not running — back up the file directly from bind mount
    DB_FILE="$PROJECT_DIR/data/db/db.sqlite3"
    if [ -f "$DB_FILE" ]; then
        cp "$DB_FILE" "$WORK_DIR/db.sqlite3"
    else
        echo "Warning: Database file not found at $DB_FILE" >&2
    fi
fi

# --- Job data backup ---
JOB_DATA_DIR="$PROJECT_DIR/data/jobs"
if [ -d "$JOB_DATA_DIR" ] && [ "$(ls -A "$JOB_DATA_DIR" 2>/dev/null)" ]; then
    log "  Backing up job data..."
    tar -czf "$WORK_DIR/jobs.tar.gz" -C "$JOB_DATA_DIR" .
else
    log "  No job data to back up."
fi

# --- Config backup ---
if [ -f "$PROJECT_DIR/.env" ]; then
    log "  Backing up .env config..."
    cp "$PROJECT_DIR/.env" "$WORK_DIR/env"
fi

# --- Manifest ---
GIT_COMMIT=""
if command -v git &>/dev/null && git -C "$PROJECT_DIR" rev-parse HEAD &>/dev/null; then
    GIT_COMMIT="$(git -C "$PROJECT_DIR" rev-parse --short HEAD)"
fi

cat > "$WORK_DIR/manifest.txt" <<EOF
Fold Webapp Backup
==================
Timestamp:  $(date -u +"%Y-%m-%d %H:%M:%S UTC")
Git commit: ${GIT_COMMIT:-unknown}

Contents:
  db.sqlite3    - SQLite database snapshot
  jobs.tar.gz   - Compressed job data (if present)
  env           - Environment config (if present)
  manifest.txt  - This file
EOF

# --- Create archive ---
log "  Creating archive..."
tar -czf "$ARCHIVE_PATH" -C "$WORK_DIR" .

ARCHIVE_SIZE="$(du -h "$ARCHIVE_PATH" | cut -f1)"
log "Backup complete: $ARCHIVE_PATH ($ARCHIVE_SIZE)"

# --- Prune old backups ---
if [ "$RETENTION_DAYS" -gt 0 ] 2>/dev/null; then
    DELETED=0
    while IFS= read -r old_backup; do
        rm -f "$old_backup"
        DELETED=$((DELETED + 1))
    done < <(find "$BACKUP_DIR" -maxdepth 1 -name "fold-webapp-backup-*.tar.gz" -mtime +"$RETENTION_DAYS" 2>/dev/null)
    if [ "$DELETED" -gt 0 ]; then
        log "Pruned $DELETED backup(s) older than $RETENTION_DAYS days."
    fi
fi
