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

get_env_value() {
    local key="$1"
    if [ ! -f .env ]; then
        return 0
    fi
    grep "^${key}=" .env 2>/dev/null | tail -n 1 | cut -d= -f2- || true
}

set_env_value() {
    local key="$1"
    local value="$2"
    if [ ! -f .env ]; then
        return 0
    fi
    if grep -q "^${key}=" .env 2>/dev/null; then
        sed -i "s|^${key}=.*|${key}=${value}|" .env
    elif grep -q "^# ${key}=" .env 2>/dev/null; then
        sed -i "s|^# ${key}=.*|${key}=${value}|" .env
    else
        echo "${key}=${value}" >> .env
    fi
}

resolve_install_user() {
    local install_user="${SUDO_USER:-}"
    if [ -n "$install_user" ] && [ "$install_user" != "root" ]; then
        printf '%s\n' "$install_user"
        return 0
    fi
    id -un
}

resolve_install_home() {
    local install_user="${1:-$(resolve_install_user)}"
    getent passwd "$install_user" | cut -d: -f6
}

resolve_install_uid() {
    local install_user="${1:-$(resolve_install_user)}"
    id -u "$install_user"
}

resolve_install_gid() {
    local install_user="${1:-$(resolve_install_user)}"
    id -g "$install_user"
}

default_data_dir() {
    local install_user="${1:-$(resolve_install_user)}"
    local install_home
    install_home="$(resolve_install_home "$install_user")"
    printf '%s\n' "$install_home/.fold-webapp/data"
}

ensure_absolute_dir() {
    local dir="$1"
    if [[ "$dir" != /* ]]; then
        mkdir -p "$dir"
        dir="$(cd "$dir" && pwd)"
    fi
    printf '%s\n' "$dir"
}

resolve_data_dir() {
    local data_dir="${DATA_DIR:-}"
    if [ -z "$data_dir" ]; then
        data_dir="$(get_env_value DATA_DIR)"
    fi
    if [ -z "$data_dir" ]; then
        data_dir="$(default_data_dir)"
    fi
    ensure_absolute_dir "$data_dir"
}

resolve_host_harness_dir() {
    local data_dir="$1"
    local legacy_harness_dir="/tmp/fold-webapp-harness"
    local harness_dir="${HARNESS_BASE_DIR_HOST:-}"
    if [ -z "$harness_dir" ]; then
        harness_dir="$(get_env_value HARNESS_BASE_DIR_HOST)"
    fi
    case "$harness_dir" in
        ""|"$legacy_harness_dir"|"$SCRIPT_DIR/.harness_runtime"|"$SCRIPT_DIR/.harness_runtime_uid"*)
            harness_dir="$data_dir/harness"
            ;;
    esac
    ensure_absolute_dir "$harness_dir"
}

resolve_app_uid() {
    local app_uid="${APP_UID:-}"
    if [ -z "$app_uid" ]; then
        app_uid="$(get_env_value APP_UID)"
    fi
    if [ -z "$app_uid" ]; then
        app_uid="$(resolve_install_uid)"
    fi
    printf '%s\n' "$app_uid"
}

resolve_app_gid() {
    local app_gid="${APP_GID:-}"
    if [ -z "$app_gid" ]; then
        app_gid="$(get_env_value APP_GID)"
    fi
    if [ -z "$app_gid" ]; then
        app_gid="$(resolve_install_gid)"
    fi
    printf '%s\n' "$app_gid"
}

dir_is_writable() {
    local dir="$1"
    local probe="$dir/.write-test.$$"
    mkdir -p "$dir" 2>/dev/null || return 1
    touch "$probe" 2>/dev/null || return 1
    rm -f "$probe"
}

ensure_data_dirs() {
    local data_dir
    local harness_dir
    local app_uid
    local app_gid
    data_dir="$(resolve_data_dir)"
    harness_dir="$(resolve_host_harness_dir "$data_dir")"
    app_uid="$(resolve_app_uid)"
    app_gid="$(resolve_app_gid)"

    mkdir -p "$data_dir/db" "$data_dir/jobs" "$data_dir/jobs/boltz_cache" \
        "$data_dir/jobs/chai_cache" "$data_dir/jobs/boltzgen_cache" "$harness_dir" 2>/dev/null || true

    if ! chmod 0777 "$data_dir" "$data_dir/db" "$data_dir/jobs" "$data_dir/jobs/boltz_cache" \
        "$data_dir/jobs/chai_cache" "$data_dir/jobs/boltzgen_cache" "$harness_dir" 2>/dev/null; then
        if ! chmod a+rwx "$data_dir" "$data_dir/db" "$data_dir/jobs" "$data_dir/jobs/boltz_cache" \
            "$data_dir/jobs/chai_cache" "$data_dir/jobs/boltzgen_cache" "$harness_dir" 2>/dev/null; then
            warn "Cannot set open permissions on $data_dir"
            warn "Fix with: sudo chmod -R a+rwX $data_dir"
        fi
    fi

    if [ -f "$data_dir/db/db.sqlite3" ]; then
        if ! chmod 0666 "$data_dir/db/db.sqlite3" 2>/dev/null; then
            if ! chmod a+rw "$data_dir/db/db.sqlite3" 2>/dev/null; then
                warn "Cannot set permissions on $data_dir/db/db.sqlite3"
                warn "Fix with: sudo chmod a+rw $data_dir/db/db.sqlite3"
            fi
        fi
    fi

    if ! dir_is_writable "$harness_dir"; then
        warn "Cannot write to harness directory: $harness_dir"
        warn "Fix with: sudo mkdir -p $harness_dir && sudo chmod 0777 $harness_dir"
    fi

    if [ -f .env ]; then
        if [ -z "$(get_env_value JOB_BASE_DIR_HOST)" ]; then
            set_env_value JOB_BASE_DIR_HOST "$data_dir/jobs"
        fi
        if [ -z "$(get_env_value HARNESS_BASE_DIR_HOST)" ] || [ "$(get_env_value HARNESS_BASE_DIR_HOST)" != "$harness_dir" ]; then
            set_env_value HARNESS_BASE_DIR_HOST "$harness_dir"
        fi
        if [ -z "$(get_env_value APP_UID)" ]; then
            set_env_value APP_UID "$app_uid"
        fi
        if [ -z "$(get_env_value APP_GID)" ]; then
            set_env_value APP_GID "$app_gid"
        fi
    fi

    warn_if_untraversable_host_jobs_dir
}

get_host_jobs_dir() {
    local host_jobs_dir="${JOB_BASE_DIR_HOST:-}"
    if [ -z "$host_jobs_dir" ]; then
        host_jobs_dir="$(get_env_value JOB_BASE_DIR_HOST)"
    fi
    if [ -z "$host_jobs_dir" ]; then
        host_jobs_dir="$(resolve_data_dir)/jobs"
    fi
    ensure_absolute_dir "$host_jobs_dir"
}

digit_has_exec() {
    case "$1" in
        1|3|5|7) return 0 ;;
        *) return 1 ;;
    esac
}

warn_if_untraversable_host_jobs_dir() {
    local host_jobs_dir
    host_jobs_dir="$(get_host_jobs_dir)"
    local app_uid
    local app_gid
    app_uid="$(resolve_app_uid)"
    app_gid="$(resolve_app_gid)"
    local current="/"
    local owner_uid group_gid perms owner_digit group_digit other_digit
    local -a parts=()

    IFS='/' read -r -a parts <<< "${host_jobs_dir#/}"
    for part in "${parts[@]}"; do
        [ -n "$part" ] || continue
        current="${current%/}/$part"
        [ -d "$current" ] || continue

        read -r owner_uid group_gid perms < <(stat -c '%u %g %a' "$current")
        perms="$(printf '%03d' "$((10#$perms))")"
        owner_digit="${perms:0:1}"
        group_digit="${perms:1:1}"
        other_digit="${perms:2:1}"

        if [ "$owner_uid" = "$app_uid" ] && digit_has_exec "$owner_digit"; then
            continue
        fi
        if [ "$group_gid" = "$app_gid" ] && digit_has_exec "$group_digit"; then
            continue
        fi
        if digit_has_exec "$other_digit"; then
            continue
        fi

        warn "JOB_BASE_DIR_HOST uses a parent directory that uid:$app_uid gid:$app_gid cannot traverse: $current"
        warn "Real SLURM jobs may fail before startup, often as ExitCode=1:0 with no slurm-<jobid>.out/err files."
        warn "Use a path the app uid/gid can traverse, such as ~/.fold-webapp/data, or relax execute permissions on the parent directories."
        return 0
    done
}

usage() {
    cat <<EOF
Fold Webapp — deployment helper

Usage: ./deploy.sh <command> [options]

Commands:
  install           First-time setup (env, build, migrate, superuser)
  adopt-single-user-layout
                    Move an existing install to the single-user home layout
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
  validate-models   Run the post-install model validation harness
  setup-slurm       Configure Slurm on this host (requires sudo)
  destroy           Tear down everything (containers, images, data, .env)

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
    if ! docker info &>/dev/null; then
        error "Cannot connect to the Docker daemon."
        error "Either start Docker or add your user to the docker group:"
        error "  sudo usermod -aG docker \$USER && newgrp docker"
        exit 1
    fi
}

# ---------- commands ----------

cmd_install() {
    local force=false
    local install_user
    local install_uid
    local install_gid
    local default_data_root
    for arg in "$@"; do
        case "$arg" in
            --force) force=true ;;
        esac
    done

    info "Checking prerequisites..."
    check_docker
    install_user="$(resolve_install_user)"
    install_uid="$(resolve_install_uid "$install_user")"
    install_gid="$(resolve_install_gid "$install_user")"
    default_data_root="$(default_data_dir "$install_user")"

    if [ "$install_uid" -eq 0 ] || [ "$install_gid" -eq 0 ]; then
        error "Single-user installs must be initialized by a non-root account."
        error "Re-run ./deploy.sh install as the user who will own the deployment."
        exit 1
    fi

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
        read -rp "Enter data directory path [$default_data_root]: " data_dir
        data_dir="${data_dir:-$default_data_root}"
        data_dir="$(ensure_absolute_dir "$data_dir")"
        set_env_value DATA_DIR "$data_dir"
        set_env_value APP_UID "$install_uid"
        set_env_value APP_GID "$install_gid"
        set_env_value JOB_BASE_DIR_HOST "$data_dir/jobs"
        set_env_value HARNESS_BASE_DIR_HOST "$data_dir/harness"

        info ".env created. You can edit it later at: $SCRIPT_DIR/.env"
        info "Using single-user defaults for $install_user ($install_uid:$install_gid)"
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
    echo "  For real SLURM execution on this host: sudo ./deploy.sh setup-slurm"
    echo "  Run ./deploy.sh --help for available commands."
    echo
}

cmd_adopt_single_user_layout() {
    local install_user
    local install_uid
    local install_gid
    local target_data_dir
    local current_data_dir
    local current_harness_dir
    local configured_harness_dir
    local source_data_retained=false

    check_docker

    if [ ! -f .env ]; then
        error "No .env file found. Run ./deploy.sh install first."
        exit 1
    fi

    install_user="$(resolve_install_user)"
    install_uid="$(resolve_install_uid "$install_user")"
    install_gid="$(resolve_install_gid "$install_user")"
    target_data_dir="$(default_data_dir "$install_user")"
    target_data_dir="$(ensure_absolute_dir "$target_data_dir")"
    current_data_dir="$(resolve_data_dir)"
    configured_harness_dir="$(get_env_value HARNESS_BASE_DIR_HOST)"
    current_harness_dir="${configured_harness_dir:-$current_data_dir/harness}"

    if [ "$install_uid" -eq 0 ] || [ "$install_gid" -eq 0 ]; then
        error "Single-user layout adoption must be run by a non-root account."
        exit 1
    fi

    echo
    warn "This will reconfigure the deployment for the single-user layout:"
    echo "  - Data directory: $current_data_dir -> $target_data_dir"
    echo "  - App runtime UID:GID -> $install_uid:$install_gid"
    echo "  - Harness directory -> $target_data_dir/harness"
    echo
    read -rp "Type \"adopt\" to continue: " confirm
    if [ "$confirm" != "adopt" ]; then
        info "Aborted."
        exit 1
    fi

    docker compose down

    if [ "$current_data_dir" != "$target_data_dir" ] && [ -d "$current_data_dir" ]; then
        mkdir -p "$(dirname "$target_data_dir")"
        if [ -d "$target_data_dir" ] && [ -n "$(find "$target_data_dir" -mindepth 1 -maxdepth 1 2>/dev/null | head -n 1 || true)" ]; then
            error "Target data directory already exists and is not empty: $target_data_dir"
            error "Move or remove it, then rerun adopt-single-user-layout."
            exit 1
        fi
        info "Moving data directory to the single-user default..."
        if ! mv "$current_data_dir" "$target_data_dir"; then
            warn "Move failed; attempting a copy instead."
            warn "The original data will remain at $current_data_dir until you remove it manually."
            mkdir -p "$target_data_dir"
            cp -a "$current_data_dir"/. "$target_data_dir"/
            source_data_retained=true
        fi
    fi

    set_env_value DATA_DIR "$target_data_dir"
    set_env_value APP_UID "$install_uid"
    set_env_value APP_GID "$install_gid"
    set_env_value JOB_BASE_DIR_HOST "$target_data_dir/jobs"
    set_env_value HARNESS_BASE_DIR_HOST "$target_data_dir/harness"

    if [ -d "$current_harness_dir" ] && [ "$current_harness_dir" != "$target_data_dir/harness" ]; then
        mkdir -p "$target_data_dir/harness"
        cp -a "$current_harness_dir"/. "$target_data_dir/harness"/ 2>/dev/null || true
    fi

    ensure_data_dirs
    docker compose up -d --build

    if [ "$source_data_retained" = true ]; then
        warn "Source data still exists at $current_data_dir"
        warn "Remove it manually after confirming the migrated deployment works."
    fi

    info "Single-user layout adopted."
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

cmd_destroy() {
    check_docker

    # Determine data directory
    local data_dir
    local harness_dir
    data_dir="$(resolve_data_dir)"
    harness_dir="$(resolve_host_harness_dir "$data_dir")"

    echo
    warn "This will permanently delete:"
    echo "  - All containers and volumes"
    echo "  - All built Docker images for this project"
    echo "  - Data directory: $data_dir (jobs, database, caches)"
    echo "  - Harness directory: $harness_dir"
    echo "  - .env file"
    echo
    read -rp "Type \"destroy\" to confirm: " confirm
    if [ "$confirm" != "destroy" ]; then
        info "Aborted."
        exit 1
    fi

    info "Stopping containers and removing volumes and images..."
    docker compose down -v --rmi all

    if [ -d "$data_dir" ]; then
        info "Removing data directory: $data_dir"
        rm -rf "$data_dir"
    fi

    if [ -d "$harness_dir" ] && [ "$harness_dir" != "$data_dir" ] && [[ "$harness_dir" != "$data_dir/"* ]]; then
        info "Removing harness directory: $harness_dir"
        rm -rf "$harness_dir"
    fi

    if [ -f .env ]; then
        info "Removing .env"
        rm -f .env
    fi

    echo
    info "Destroy complete. All deployment artifacts have been removed."
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

cmd_validate_models() {
    check_docker
    ensure_data_dirs
    info "Reconciling harness service mounts..."
    docker compose up -d web poller
    exec "$SCRIPT_DIR/scripts/run_model_harness.sh" "$@"
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
    adopt-single-user-layout) cmd_adopt_single_user_layout "$@" ;;
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
    validate-models)  cmd_validate_models "$@" ;;
    setup-slurm)      cmd_setup_slurm "$@" ;;
    destroy)          cmd_destroy "$@" ;;
    -h|--help|help)   usage ;;
    *)
        error "Unknown command: $COMMAND"
        usage
        exit 1
        ;;
esac
