#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# ---------- helpers ----------

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

info()  { echo -e "${GREEN}==>${NC} $*"; }
warn()  { echo -e "${YELLOW}WARNING:${NC} $*"; }
step()  { echo -e "${BLUE}  →${NC} $*"; }
error() { echo -e "${RED}ERROR:${NC} $*" >&2; }

usage() {
    cat <<EOF
Fold Webapp — Single-Node Slurm Setup

Usage: sudo scripts/setup-slurm.sh [options]

Installs and configures Slurm on a single Ubuntu node for use with Fold.
Auto-detects hardware (CPUs, RAM, GPUs), generates config files, and
produces a docker-compose.override.yml so the web/poller containers
can communicate with Slurm.

Options:
  --dry-run           Show what would be done without making changes
  --skip-test         Skip the verification test job
  --force-reconfig    Regenerate config files even if they exist
  -h, --help          Show this help message
EOF
}

# ---------- argument parsing ----------

DRY_RUN=false
SKIP_TEST=false
FORCE_RECONFIG=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --skip-test)
            SKIP_TEST=true
            shift
            ;;
        --force-reconfig)
            FORCE_RECONFIG=true
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

# =====================================================================
# Phase 1: Prerequisites check
# =====================================================================

info "Phase 1: Checking prerequisites..."

# Must be root
if [[ "$EUID" -ne 0 ]]; then
    error "This script must be run as root (use sudo)."
    exit 1
fi

# Must be Ubuntu 22.04 or 24.04
if [[ -f /etc/os-release ]]; then
    . /etc/os-release
    if [[ "$ID" != "ubuntu" ]]; then
        error "This script requires Ubuntu. Detected: $ID"
        exit 1
    fi
    case "$VERSION_ID" in
        22.04|24.04)
            step "Detected Ubuntu $VERSION_ID"
            ;;
        *)
            error "Unsupported Ubuntu version: $VERSION_ID (requires 22.04 or 24.04)"
            exit 1
            ;;
    esac
else
    error "/etc/os-release not found. Cannot determine OS."
    exit 1
fi

# Check for nvidia-smi
HAS_GPU=false
GPU_COUNT=0
GPU_TYPE=""
if command -v nvidia-smi &>/dev/null; then
    HAS_GPU=true
    GPU_COUNT=$(nvidia-smi --query-gpu=name --format=csv,noheader | wc -l)
    GPU_TYPE=$(nvidia-smi --query-gpu=name --format=csv,noheader | head -1 | xargs)
    step "Detected $GPU_COUNT GPU(s): $GPU_TYPE"
else
    warn "nvidia-smi not found. GPU support will be disabled."
    warn "Install NVIDIA drivers if you need GPU job scheduling."
fi

# Check for Docker + NVIDIA Container Toolkit
if ! command -v docker &>/dev/null; then
    warn "Docker is not installed. docker-compose.override.yml will still be generated,"
    warn "but you will need Docker to run the application."
fi

if [[ "$HAS_GPU" == true ]] && ! docker run --rm --gpus all nvidia/cuda:12.8.0-base-ubuntu22.04 nvidia-smi &>/dev/null 2>&1; then
    warn "NVIDIA Container Toolkit may not be configured."
    warn "GPU containers may not work until it is installed."
fi

# Detect hardware
HOSTNAME_SHORT=$(hostname -s)
CPU_COUNT=$(nproc)
TOTAL_RAM_MB=$(free -m | awk '/^Mem:/ {print $2}')
REAL_MEMORY=$((TOTAL_RAM_MB - 2048))
if [[ "$REAL_MEMORY" -lt 1024 ]]; then
    REAL_MEMORY=1024
fi

step "Hostname: $HOSTNAME_SHORT"
step "CPUs: $CPU_COUNT"
step "RAM: ${TOTAL_RAM_MB}MB total, ${REAL_MEMORY}MB allocated to Slurm"

if [[ "$DRY_RUN" == true ]]; then
    info "Dry run — showing planned actions without making changes."
    echo
fi

# =====================================================================
# Phase 2: Install munge
# =====================================================================

info "Phase 2: Installing munge..."

if [[ "$DRY_RUN" == true ]]; then
    step "[dry-run] Would install: munge libmunge-dev"
    step "[dry-run] Would generate munge key if missing"
    step "[dry-run] Would enable and start munge.service"
else
    apt-get update -qq
    apt-get install -y munge libmunge-dev

    if [[ ! -f /etc/munge/munge.key ]]; then
        step "Generating munge key..."
        create-munge-key -f
    else
        step "Munge key already exists."
    fi

    chown munge:munge /etc/munge/munge.key
    chmod 400 /etc/munge/munge.key

    systemctl enable munge
    systemctl restart munge
    step "Munge service started."
fi

# =====================================================================
# Phase 3: Install Slurm packages
# =====================================================================

info "Phase 3: Installing Slurm packages..."

# Ubuntu default repos include Slurm (21.08 on 22.04, 23.02 on 24.04).
# For newer versions, consider adding the SchedMD PPA:
# https://packages.schedmd.com/

if [[ "$DRY_RUN" == true ]]; then
    step "[dry-run] Would install: slurm-wlm slurm-client"
    step "[dry-run] Would create spool and log directories"
else
    apt-get install -y slurm-wlm slurm-client

    mkdir -p /var/spool/slurm/ctld /var/spool/slurm/d /var/log/slurm
    chown -R slurm:slurm /var/spool/slurm /var/log/slurm
    step "Slurm packages installed."
fi

# =====================================================================
# Phase 4: Hardware auto-detection (already done in Phase 1)
# =====================================================================

info "Phase 4: Hardware detection complete."
step "CPUs=$CPU_COUNT  RealMemory=${REAL_MEMORY}MB  GPUs=$GPU_COUNT"

# =====================================================================
# Phase 5: Generate /etc/slurm/slurm.conf
# =====================================================================

info "Phase 5: Generating /etc/slurm/slurm.conf..."

SLURM_CONF="/etc/slurm/slurm.conf"
JOBCOMP_LOG="/var/log/slurm/jobcomp.log"

if [[ "$HAS_GPU" == true ]]; then
    PARTITION_NAME="gpu"
    GRES_CONFIG="Gres=gpu:$GPU_COUNT"
else
    PARTITION_NAME="cpu"
    GRES_CONFIG=""
fi

if [[ -f "$SLURM_CONF" && "$FORCE_RECONFIG" != true ]]; then
    warn "$SLURM_CONF already exists. Use --force-reconfig to overwrite."
    if grep -Eq '^\s*AccountingStorageType\s*=\s*accounting_storage/filetxt\b' "$SLURM_CONF"; then
        error "Detected deprecated AccountingStorageType=accounting_storage/filetxt in $SLURM_CONF."
        error "Re-run with --force-reconfig to regenerate a Slurm 21.08+ compatible config."
        exit 1
    fi
elif [[ "$DRY_RUN" == true ]]; then
    step "[dry-run] Would write $SLURM_CONF"
    step "[dry-run] ClusterName=fold, SlurmctldHost=$HOSTNAME_SHORT"
    step "[dry-run] NodeName=$HOSTNAME_SHORT CPUs=$CPU_COUNT RealMemory=$REAL_MEMORY $GRES_CONFIG"
    step "[dry-run] PartitionName=$PARTITION_NAME"
else
    mkdir -p /etc/slurm

    # Build NodeName line
    NODE_LINE="NodeName=$HOSTNAME_SHORT CPUs=$CPU_COUNT RealMemory=$REAL_MEMORY"
    if [[ -n "$GRES_CONFIG" ]]; then
        NODE_LINE="$NODE_LINE $GRES_CONFIG"
    fi
    NODE_LINE="$NODE_LINE State=UNKNOWN"

    cat > "$SLURM_CONF" <<SLURM_EOF
# slurm.conf — generated by setup-slurm.sh
# See: https://slurm.schedmd.com/slurm.conf.html

ClusterName=fold
SlurmctldHost=$HOSTNAME_SHORT

# Scheduling
SelectType=select/cons_tres
SelectTypeParameters=CR_Core_Memory

# Process tracking and task management
ProctrackType=proctrack/cgroup
TaskPlugin=task/cgroup,task/affinity

# Job accounting / completion
# NOTE: accounting_storage/filetxt was removed in Slurm 20.11+.
JobAcctGatherType=jobacct_gather/cgroup
JobCompType=jobcomp/filetxt
JobCompLoc=$JOBCOMP_LOG

# GRES (Generic Resources — GPUs)
GresTypes=gpu

# Logging
SlurmctldLogFile=/var/log/slurm/slurmctld.log
SlurmdLogFile=/var/log/slurm/slurmd.log
SlurmctldPidFile=/run/slurmctld.pid
SlurmdPidFile=/run/slurmd.pid

# Spool directories
StateSaveLocation=/var/spool/slurm/ctld
SlurmdSpoolDir=/var/spool/slurm/d

# Node management
ReturnToService=2

# Nodes
$NODE_LINE

# Partitions
PartitionName=$PARTITION_NAME Nodes=$HOSTNAME_SHORT Default=YES MaxTime=INFINITE State=UP
SLURM_EOF

    chown slurm:slurm "$SLURM_CONF"
    step "Generated $SLURM_CONF"
fi

# =====================================================================
# Phase 6: Generate /etc/slurm/gres.conf
# =====================================================================

info "Phase 6: Generating /etc/slurm/gres.conf..."

GRES_CONF="/etc/slurm/gres.conf"

if [[ -f "$GRES_CONF" && "$FORCE_RECONFIG" != true ]]; then
    warn "$GRES_CONF already exists. Use --force-reconfig to overwrite."
elif [[ "$DRY_RUN" == true ]]; then
    if [[ "$HAS_GPU" == true ]]; then
        step "[dry-run] Would write $GRES_CONF with AutoDetect=nvml"
    else
        step "[dry-run] Would write $GRES_CONF (comment-only, no GPUs)"
    fi
else
    if [[ "$HAS_GPU" == true ]]; then
        cat > "$GRES_CONF" <<GRES_EOF
# gres.conf — generated by setup-slurm.sh
# AutoDetect=nvml is supported on Slurm 21.08+ and auto-detects NVIDIA GPUs
AutoDetect=nvml
GRES_EOF
    else
        cat > "$GRES_CONF" <<GRES_EOF
# gres.conf — generated by setup-slurm.sh
# No GPUs detected. Add GPU configuration here if GPUs are added later.
# Example: AutoDetect=nvml
GRES_EOF
    fi

    chown slurm:slurm "$GRES_CONF"
    step "Generated $GRES_CONF"
fi

# =====================================================================
# Phase 7: Generate /etc/slurm/cgroup.conf
# =====================================================================

info "Phase 7: Generating /etc/slurm/cgroup.conf..."

CGROUP_CONF="/etc/slurm/cgroup.conf"

if [[ -f "$CGROUP_CONF" && "$FORCE_RECONFIG" != true ]]; then
    warn "$CGROUP_CONF already exists. Use --force-reconfig to overwrite."
    if grep -Eq '^\s*CgroupAutomount\s*=' "$CGROUP_CONF"; then
        warn "Detected legacy CgroupAutomount setting in $CGROUP_CONF."
        warn "Consider re-running with --force-reconfig for current Slurm cgroup settings."
    fi
elif [[ "$DRY_RUN" == true ]]; then
    step "[dry-run] Would write $CGROUP_CONF"
else
    cat > "$CGROUP_CONF" <<CGROUP_EOF
# cgroup.conf — generated by setup-slurm.sh
ConstrainCores=yes
ConstrainRAMSpace=yes
ConstrainDevices=yes
CGROUP_EOF

    chown slurm:slurm "$CGROUP_CONF"
    step "Generated $CGROUP_CONF"
fi

# =====================================================================
# Phase 8: Configure job completion logging
# =====================================================================

info "Phase 8: Configuring job completion logging..."

if [[ "$DRY_RUN" == true ]]; then
    step "[dry-run] Would create $JOBCOMP_LOG if missing"
else
    if [[ ! -f "$JOBCOMP_LOG" ]]; then
        touch "$JOBCOMP_LOG"
        step "Created $JOBCOMP_LOG"
    else
        step "$JOBCOMP_LOG already exists."
    fi
    chown slurm:slurm "$JOBCOMP_LOG"
fi

# =====================================================================
# Phase 9: Enable and start services
# =====================================================================

info "Phase 9: Enabling and starting Slurm services..."

if [[ "$DRY_RUN" == true ]]; then
    step "[dry-run] Would validate: slurmctld -t -f $SLURM_CONF"
    step "[dry-run] Would enable and restart: munge, slurmctld, slurmd"
    step "[dry-run] Would set node $HOSTNAME_SHORT to IDLE state"
else
    step "Validating Slurm config syntax..."
    if slurmctld -t -f "$SLURM_CONF" >/tmp/slurmctld-validate.log 2>&1; then
        step "slurm.conf validation passed."
    else
        error "slurm.conf validation failed. See: /tmp/slurmctld-validate.log"
        tail -n 20 /tmp/slurmctld-validate.log || true
        exit 1
    fi

    for svc in munge slurmctld slurmd; do
        systemctl enable "$svc"
        systemctl restart "$svc"

        if systemctl is-active --quiet "$svc"; then
            step "$svc is running."
        else
            error "$svc failed to start. Check: journalctl -u $svc -n 50"
            exit 1
        fi
    done

    # Transition node from UNKNOWN to IDLE
    sleep 2
    scontrol update NodeName="$HOSTNAME_SHORT" State=IDLE || {
        warn "Could not set node to IDLE. It may need manual intervention."
        warn "Run: scontrol update NodeName=$HOSTNAME_SHORT State=IDLE"
    }
    step "Node $HOSTNAME_SHORT set to IDLE."
fi

# =====================================================================
# Phase 10: Generate docker-compose.override.yml
# =====================================================================

info "Phase 10: Generating docker-compose.override.yml..."

OVERRIDE_FILE="$PROJECT_ROOT/docker-compose.override.yml"

if [[ -f "$OVERRIDE_FILE" && "$FORCE_RECONFIG" != true ]]; then
    warn "$OVERRIDE_FILE already exists. Use --force-reconfig to overwrite."
elif [[ "$DRY_RUN" == true ]]; then
    step "[dry-run] Would write $OVERRIDE_FILE"
    step "[dry-run] Mounts: Slurm binaries, config, munge socket, shared libraries"
else
    # Auto-discover Slurm shared libraries
    SLURM_LIB_PATHS=()
    while IFS= read -r lib_line; do
        lib_path=$(echo "$lib_line" | grep -oP '=>\s*\K/[^\s]+')
        if [[ -n "$lib_path" ]]; then
            lib_dir=$(dirname "$lib_path")
            # Deduplicate
            local_found=false
            for existing in "${SLURM_LIB_PATHS[@]+"${SLURM_LIB_PATHS[@]}"}"; do
                if [[ "$existing" == "$lib_dir" ]]; then
                    local_found=true
                    break
                fi
            done
            if [[ "$local_found" == false ]]; then
                SLURM_LIB_PATHS+=("$lib_dir")
            fi
        fi
    done < <(ldconfig -p 2>/dev/null | grep -i slurm || true)

    # Build LD_LIBRARY_PATH from discovered paths
    LD_LIB_PATH=""
    LIB_VOLUME_MOUNTS=""
    for lib_dir in "${SLURM_LIB_PATHS[@]+"${SLURM_LIB_PATHS[@]}"}"; do
        if [[ -n "$LD_LIB_PATH" ]]; then
            LD_LIB_PATH="$LD_LIB_PATH:$lib_dir"
        else
            LD_LIB_PATH="$lib_dir"
        fi
        LIB_VOLUME_MOUNTS="$LIB_VOLUME_MOUNTS
      - $lib_dir:$lib_dir:ro"
    done

    # Build environment section
    ENV_SECTION=""
    if [[ -n "$LD_LIB_PATH" ]]; then
        ENV_SECTION="
    environment:
      - LD_LIBRARY_PATH=$LD_LIB_PATH"
    fi

    cat > "$OVERRIDE_FILE" <<OVERRIDE_EOF
# docker-compose.override.yml — generated by setup-slurm.sh
# Mounts host Slurm binaries, config, and munge socket into containers.
# This file is environment-specific and should not be committed to git.

services:
  web:
    volumes:
      - /usr/bin/sbatch:/usr/bin/sbatch:ro
      - /usr/bin/squeue:/usr/bin/squeue:ro
      - /usr/bin/sacct:/usr/bin/sacct:ro
      - /usr/bin/scancel:/usr/bin/scancel:ro
      - /etc/slurm:/etc/slurm:ro
      - /var/run/munge:/var/run/munge:ro${LIB_VOLUME_MOUNTS}${ENV_SECTION}

  poller:
    volumes:
      - /usr/bin/squeue:/usr/bin/squeue:ro
      - /usr/bin/sacct:/usr/bin/sacct:ro
      - /usr/bin/scancel:/usr/bin/scancel:ro
      - /etc/slurm:/etc/slurm:ro
      - /var/run/munge:/var/run/munge:ro${LIB_VOLUME_MOUNTS}${ENV_SECTION}
OVERRIDE_EOF

    step "Generated $OVERRIDE_FILE"
fi

# =====================================================================
# Phase 11: Verification
# =====================================================================

if [[ "$SKIP_TEST" == true ]]; then
    info "Phase 11: Skipping verification (--skip-test specified)."
elif [[ "$DRY_RUN" == true ]]; then
    info "Phase 11: [dry-run] Would submit test job and verify via scheduler state."
else
    info "Phase 11: Running verification..."

    step "Submitting test job..."
    TEST_JOB_ID=$(sbatch --parsable --wrap="hostname")
    TEST_OUTPUT_FILE="slurm-${TEST_JOB_ID}.out"

    if [[ -z "$TEST_JOB_ID" ]]; then
        error "Failed to submit test job."
        exit 1
    fi
    step "Test job submitted: $TEST_JOB_ID"

    step "Waiting for job to complete (up to 60s)..."
    ELAPSED=0
    JOB_STATE=""
    while [[ $ELAPSED -lt 60 ]]; do
        JOB_STATE=""

        # Check active queue first
        SQUEUE_STATE=$(squeue -j "$TEST_JOB_ID" -h -o "%T" 2>/dev/null | head -1 | xargs)
        if [[ -n "$SQUEUE_STATE" ]]; then
            JOB_STATE="$SQUEUE_STATE"
        else
            # Prefer sacct when available
            SACCT_STATE=$(sacct -j "$TEST_JOB_ID" --format=State --noheader --parsable2 2>/dev/null | head -1 | xargs || true)
            if [[ -n "$SACCT_STATE" ]]; then
                JOB_STATE="$SACCT_STATE"
            else
                # Fallback for systems without persistent accounting
                SCONTROL_STATE=$(scontrol show job "$TEST_JOB_ID" -o 2>/dev/null | sed -n 's/.*JobState=\([^ ]*\).*/\1/p' | head -1 | xargs || true)
                if [[ -n "$SCONTROL_STATE" ]]; then
                    JOB_STATE="$SCONTROL_STATE"
                elif [[ -s "$TEST_OUTPUT_FILE" ]]; then
                    # scontrol can lose old job records quickly without accounting DB.
                    JOB_STATE="COMPLETED"
                fi
            fi
        fi

        if [[ "$JOB_STATE" == "COMPLETED" ]]; then
            break
        fi
        if [[ "$JOB_STATE" == FAILED* || "$JOB_STATE" == CANCELLED* || "$JOB_STATE" == TIMEOUT* || "$JOB_STATE" == NODE_FAIL* || "$JOB_STATE" == OUT_OF_MEMORY* || "$JOB_STATE" == PREEMPTED* ]]; then
            break
        fi

        sleep 2
        ELAPSED=$((ELAPSED + 2))
    done

    if [[ "$JOB_STATE" == "COMPLETED" ]]; then
        step "Test job $TEST_JOB_ID completed successfully."
    elif [[ "$JOB_STATE" == FAILED* || "$JOB_STATE" == CANCELLED* || "$JOB_STATE" == TIMEOUT* || "$JOB_STATE" == NODE_FAIL* || "$JOB_STATE" == OUT_OF_MEMORY* || "$JOB_STATE" == PREEMPTED* ]]; then
        error "Test job failed. State: $JOB_STATE"
        exit 1
    else
        error "Test job did not complete within 60s. State: ${JOB_STATE:-UNKNOWN}"
        error "Check: squeue -j $TEST_JOB_ID"
        exit 1
    fi

    SACCT_OUTPUT=$(sacct -j "$TEST_JOB_ID" --format=JobID,State --noheader --parsable2 2>/dev/null || true)
    if [[ -n "$SACCT_OUTPUT" ]]; then
        step "sacct verification passed."
    else
        warn "sacct returned no results for job $TEST_JOB_ID (no accounting DB configured)."
        warn "Status polling will use squeue/scontrol fallback."
    fi

    # Clean up test output
    rm -f "slurm-${TEST_JOB_ID}.out"
fi

# =====================================================================
# Phase 12: Summary
# =====================================================================

echo
info "Phase 12: Setup complete!"
echo
echo "  Hardware:"
echo "    Hostname:   $HOSTNAME_SHORT"
echo "    CPUs:       $CPU_COUNT"
echo "    RAM:        ${REAL_MEMORY}MB (allocated to Slurm)"
if [[ "$HAS_GPU" == true ]]; then
    echo "    GPUs:       $GPU_COUNT × $GPU_TYPE"
else
    echo "    GPUs:       none"
fi
echo
echo "  Config files:"
echo "    Slurm:      $SLURM_CONF"
echo "    GRES:       $GRES_CONF"
echo "    Cgroup:     $CGROUP_CONF"
echo "    Override:   $OVERRIDE_FILE"
echo

if [[ "$DRY_RUN" != true ]]; then
    echo "  Service status:"
    for svc in munge slurmctld slurmd; do
        if systemctl is-active --quiet "$svc"; then
            echo "    $svc: active"
        else
            echo "    $svc: INACTIVE"
        fi
    done
    echo
fi

echo "  Next steps:"
echo "    1. Set FAKE_SLURM=0 in .env"
echo "    2. Restart the app: ./deploy.sh restart"
echo "    3. Configure RunnerConfig in Django admin (http://localhost:8000/admin/)"
echo
