#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ---------- helpers ----------

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

info()  { echo -e "${GREEN}==>${NC} $*"; }
warn()  { echo -e "${YELLOW}WARNING:${NC} $*"; }
error() { echo -e "${RED}ERROR:${NC} $*" >&2; }

ensure_data_dirs() {
    local data_dir="./data"
    if [ -f .env ]; then
        local env_val
        env_val="$(grep '^DATA_DIR=' .env 2>/dev/null | cut -d= -f2-)"
        [ -n "$env_val" ] && data_dir="$env_val"
    fi
    mkdir -p "$data_dir/db" "$data_dir/jobs"
}

usage() {
    cat <<EOF
Fold Webapp — deployment helper

Usage: ./deploy.sh <command> [options]

Commands:
  install           First-time setup (env, build, migrate, superuser)
  start             Start services (docker compose up -d)
  stop              Stop services (docker compose down)
  restart           Restart services
  status            Show service status
  logs [service]    Tail container logs
  update            Pull latest code, rebuild, and restart
  shell             Open Django shell in web container
  createsuperuser   Create a new admin user
  backup            Run a backup (delegates to scripts/backup.sh)
  restore <file>    Restore from backup (delegates to scripts/restore.sh)
  prewarm [opts]    Pre-warm by pulling images and downloading model weights
  download-weights  Download/cache model weights only (no image building)
  setup-slurm       Configure Slurm on this host (requires sudo)

Options:
  -h, --help        Show this help message
EOF
}

# ---------- prerequisite checks ----------

check_docker() {
    if ! command -v docker &>/dev/null; then
        error "Docker is not installed. See https://docs.docker.com/get-docker/"
        exit 1
    fi
    if ! docker compose version &>/dev/null; then
        error "Docker Compose v2 plugin is required."
        error "See https://docs.docker.com/compose/install/"
        exit 1
    fi
}

# ---------- commands ----------

cmd_install() {
    local force=false
    for arg in "$@"; do
        case "$arg" in
            --force) force=true ;;
        esac
    done

    info "Checking prerequisites..."
    check_docker

    # --- .env setup ---
    if [ ! -f .env ] || [ "$force" = true ]; then
        info "Creating .env from env.example..."
        cp env.example .env

        # Generate random SECRET_KEY
        SECRET_KEY="$(python3 -c "import secrets; print(secrets.token_urlsafe(50))" 2>/dev/null \
            || openssl rand -base64 50 | tr -d '\n/+=' | head -c 50)"
        sed -i "s|^SECRET_KEY=.*|SECRET_KEY=$SECRET_KEY|" .env

        # Set production defaults
        sed -i "s|^DEBUG=.*|DEBUG=false|" .env

        # Prompt for ALLOWED_HOSTS
        echo
        read -rp "Enter allowed hosts (comma-separated, e.g. example.com,localhost) [localhost]: " hosts
        hosts="${hosts:-localhost}"
        sed -i "s|^ALLOWED_HOSTS=.*|ALLOWED_HOSTS=$hosts|" .env

        # Prompt for DATA_DIR
        echo
        read -rp "Enter data directory path [./data]: " data_dir
        data_dir="${data_dir:-./data}"
        # Resolve relative paths to absolute
        if [[ "$data_dir" != /* ]]; then
            mkdir -p "$data_dir"
            data_dir="$(cd "$SCRIPT_DIR" && cd "$data_dir" && pwd)"
        fi
        sed -i "s|^# DATA_DIR=.*|DATA_DIR=$data_dir|" .env

        info ".env created. You can edit it later at: $SCRIPT_DIR/.env"
    else
        info ".env already exists (use --force to overwrite)."
    fi

    # --- Create data directories ---
    info "Creating data directories..."
    ensure_data_dirs

    # --- Build ---
    info "Building Docker image..."
    docker compose build

    # --- Start services (migrations run automatically) ---
    info "Starting services..."
    docker compose up -d

    # --- Wait for web to be healthy ---
    info "Waiting for services to start..."
    sleep 3

    # --- Superuser ---
    echo
    read -rp "Create an admin (superuser) account now? [Y/n] " create_su
    if [[ ! "$create_su" =~ ^[Nn]$ ]]; then
        docker compose exec web python manage.py createsuperuser
    fi

    echo
    info "Installation complete!"
    echo
    echo "  Access the application at: http://localhost:8000"
    echo "  Manage with: ./deploy.sh <command>"
    echo "  Run ./deploy.sh --help for available commands."
    echo
}

cmd_start() {
    check_docker
    info "Starting services..."
    ensure_data_dirs
    docker compose up -d
    info "Services started. Access at http://localhost:8000"
}

cmd_stop() {
    check_docker
    info "Stopping services..."
    docker compose down
    info "Services stopped."
}

cmd_restart() {
    check_docker
    info "Restarting services..."
    docker compose down
    ensure_data_dirs
    docker compose up -d
    info "Services restarted."
}

cmd_status() {
    check_docker
    docker compose ps
}

cmd_logs() {
    check_docker
    if [ $# -gt 0 ]; then
        docker compose logs -f "$@"
    else
        docker compose logs -f
    fi
}

cmd_update() {
    check_docker
    info "Pulling latest code..."
    git pull

    info "Rebuilding Docker image..."
    docker compose build

    info "Restarting services..."
    docker compose down
    ensure_data_dirs
    docker compose up -d

    info "Update complete."
}

cmd_shell() {
    check_docker
    docker compose exec web python manage.py shell
}

cmd_createsuperuser() {
    check_docker
    docker compose exec web python manage.py createsuperuser
}

cmd_backup() {
    exec "$SCRIPT_DIR/scripts/backup.sh" "$@"
}

cmd_restore() {
    exec "$SCRIPT_DIR/scripts/restore.sh" "$@"
}

cmd_prewarm() {
    exec "$SCRIPT_DIR/scripts/prewarm.sh" "$@"
}

cmd_download_weights() {
    exec "$SCRIPT_DIR/scripts/download_weights.sh" "$@"
}

cmd_setup_slurm() {
    exec "$SCRIPT_DIR/scripts/setup-slurm.sh" "$@"
}

# ---------- main ----------

if [ $# -eq 0 ]; then
    usage
    exit 1
fi

COMMAND="$1"
shift

case "$COMMAND" in
    install)          cmd_install "$@" ;;
    start|up)         cmd_start "$@" ;;
    stop|down)        cmd_stop "$@" ;;
    restart)          cmd_restart "$@" ;;
    status|ps)        cmd_status "$@" ;;
    logs)             cmd_logs "$@" ;;
    update)           cmd_update "$@" ;;
    shell)            cmd_shell "$@" ;;
    createsuperuser)  cmd_createsuperuser "$@" ;;
    backup)           cmd_backup "$@" ;;
    restore)          cmd_restore "$@" ;;
    prewarm)          cmd_prewarm "$@" ;;
    download-weights) cmd_download_weights "$@" ;;
    setup-slurm)      cmd_setup_slurm "$@" ;;
    -h|--help|help)   usage ;;
    *)
        error "Unknown command: $COMMAND"
        usage
        exit 1
        ;;
esac
