#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# ---------- helpers ----------

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

info()  { echo -e "${GREEN}==>${NC} $*"; }
warn()  { echo -e "${YELLOW}WARNING:${NC} $*"; }
step()  { echo -e "${BLUE}  →${NC} $*"; }

usage() {
    cat <<EOF
Fold Webapp — Pre-warming Script

Usage: ./scripts/prewarm.sh [options]

Pre-warms the deployment by:
  1. Pulling/building all Docker images
  2. Downloading model weights to cache directories

This script should be run after deployment to prepare the system
for production use. It can also be run after updates when new
models are added or model versions change.

Options:
  --skip-images       Skip Docker image pull/build
  --skip-weights      Skip model weight downloads
  --registry URL      Docker registry URL (default: none, uses env.example names)
  -h, --help          Show this help message

Environment:
  Reads .env file for configuration (BOLTZ_CACHE_DIR, CHAI_CACHE_DIR, BOLTZGEN_CACHE_DIR, etc.)
EOF
}

# ---------- argument parsing ----------

SKIP_IMAGES=false
SKIP_WEIGHTS=false
REGISTRY=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --skip-images)
            SKIP_IMAGES=true
            shift
            ;;
        --skip-weights)
            SKIP_WEIGHTS=true
            shift
            ;;
        --registry)
            REGISTRY="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "ERROR: Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# ---------- environment setup ----------

if [ ! -f .env ]; then
    warn ".env file not found. Using env.example defaults."
    warn "For production, run './deploy.sh install' first."
    ENV_FILE=env.example
else
    ENV_FILE=.env
fi

# Load environment variables
set -a
source "$ENV_FILE"
set +a

# Set defaults if not in env
BOLTZ_IMAGE="${BOLTZ_IMAGE:-brineylab/boltz2:latest}"
CHAI_IMAGE="${CHAI_IMAGE:-brineylab/chai1:latest}"
LIGANDMPNN_IMAGE="${LIGANDMPNN_IMAGE:-brineylab/ligandmpnn:latest}"
BINDCRAFT_IMAGE="${BINDCRAFT_IMAGE:-brineylab/bindcraft:latest}"
RFDIFFUSION3_IMAGE="${RFDIFFUSION3_IMAGE:-brineylab/rfdiffusion3:latest}"
BOLTZGEN_IMAGE="${BOLTZGEN_IMAGE:-brineylab/boltzgen:latest}"
OPENFOLD3_IMAGE="${OPENFOLD3_IMAGE:-brineylab/openfold3:latest}"
DATA_DIR="${DATA_DIR:-./data}"
BOLTZ_CACHE_DIR="${BOLTZ_CACHE_DIR:-$DATA_DIR/jobs/boltz_cache}"
CHAI_CACHE_DIR="${CHAI_CACHE_DIR:-$DATA_DIR/jobs/chai_cache}"
BOLTZGEN_CACHE_DIR="${BOLTZGEN_CACHE_DIR:-$DATA_DIR/jobs/boltzgen_cache}"
OPENFOLD3_CACHE_DIR="${OPENFOLD3_CACHE_DIR:-$DATA_DIR/jobs/openfold3_cache}"

# Add registry prefix if specified
if [ -n "$REGISTRY" ]; then
    BOLTZ_IMAGE="${REGISTRY}/${BOLTZ_IMAGE}"
    CHAI_IMAGE="${REGISTRY}/${CHAI_IMAGE}"
    LIGANDMPNN_IMAGE="${REGISTRY}/${LIGANDMPNN_IMAGE}"
    BINDCRAFT_IMAGE="${REGISTRY}/${BINDCRAFT_IMAGE}"
    RFDIFFUSION3_IMAGE="${REGISTRY}/${RFDIFFUSION3_IMAGE}"
    BOLTZGEN_IMAGE="${REGISTRY}/${BOLTZGEN_IMAGE}"
    OPENFOLD3_IMAGE="${REGISTRY}/${OPENFOLD3_IMAGE}"
fi

# ---------- prerequisite checks ----------

if ! command -v docker &>/dev/null; then
    echo "ERROR: Docker is not installed. See https://docs.docker.com/get-docker/"
    exit 1
fi

if ! docker compose version &>/dev/null; then
    echo "ERROR: Docker Compose v2 plugin is required."
    echo "See https://docs.docker.com/compose/install/"
    exit 1
fi

# Check for GPU availability (informational only — weight downloads don't need GPUs)
if ! docker run --rm --gpus all nvidia/cuda:12.8.0-base-ubuntu22.04 nvidia-smi &>/dev/null; then
    warn "GPU not accessible via Docker."
    warn "Weight downloads will still work, but test predictions will require a GPU."
fi

# ---------- main pre-warming steps ----------

info "Starting pre-warm process..."
echo

# Step 1: Pull/build Docker images
if [ "$SKIP_IMAGES" = false ]; then
    info "Step 1/2: Pulling Docker images..."

    step "Pulling Boltz-2 image: $BOLTZ_IMAGE"
    if ! docker pull "$BOLTZ_IMAGE" 2>/dev/null; then
        warn "Failed to pull $BOLTZ_IMAGE from registry."
        warn "This is expected if images haven't been pushed yet."
        step "Building Boltz-2 image locally..."
        docker build -t "$BOLTZ_IMAGE" containers/boltz2/
    fi

    step "Pulling Chai-1 image: $CHAI_IMAGE"
    if ! docker pull "$CHAI_IMAGE" 2>/dev/null; then
        warn "Failed to pull $CHAI_IMAGE from registry."
        step "Building Chai-1 image locally..."
        docker build -t "$CHAI_IMAGE" containers/chai1/
    fi

    step "Pulling LigandMPNN image: $LIGANDMPNN_IMAGE"
    if ! docker pull "$LIGANDMPNN_IMAGE" 2>/dev/null; then
        warn "Failed to pull $LIGANDMPNN_IMAGE from registry."
        step "Building LigandMPNN image locally..."
        docker build -t "$LIGANDMPNN_IMAGE" containers/ligandmpnn/
    fi

    step "Pulling BindCraft image: $BINDCRAFT_IMAGE"
    if ! docker pull "$BINDCRAFT_IMAGE" 2>/dev/null; then
        warn "Failed to pull $BINDCRAFT_IMAGE from registry."
        step "Building BindCraft image locally..."
        docker build -t "$BINDCRAFT_IMAGE" containers/bindcraft/
    fi

    step "Pulling RFdiffusion3 image: $RFDIFFUSION3_IMAGE"
    if ! docker pull "$RFDIFFUSION3_IMAGE" 2>/dev/null; then
        warn "Failed to pull $RFDIFFUSION3_IMAGE from registry."
        step "Building RFdiffusion3 image locally..."
        docker build -t "$RFDIFFUSION3_IMAGE" containers/rfdiffusion3/
    fi

    step "Pulling BoltzGen image: $BOLTZGEN_IMAGE"
    if ! docker pull "$BOLTZGEN_IMAGE" 2>/dev/null; then
        warn "Failed to pull $BOLTZGEN_IMAGE from registry."
        step "Building BoltzGen image locally..."
        docker build -t "$BOLTZGEN_IMAGE" containers/boltzgen/
    fi

    step "Pulling OpenFold3 image: $OPENFOLD3_IMAGE"
    if ! docker pull "$OPENFOLD3_IMAGE" 2>/dev/null; then
        warn "Failed to pull $OPENFOLD3_IMAGE from registry."
        step "Building OpenFold3 image locally..."
        docker build -t "$OPENFOLD3_IMAGE" containers/openfold3/
    fi

    step "Building main web application image..."
    docker compose build

    echo
    info "Docker images ready."
else
    info "Skipping Docker image pull/build (--skip-images specified)"
fi

echo

# Step 2: Download model weights
if [ "$SKIP_WEIGHTS" = false ]; then
    info "Step 2/2: Downloading model weights..."
    "$SCRIPT_DIR/download_weights.sh"
else
    info "Skipping model weight downloads (--skip-weights specified)"
fi

echo
info "Pre-warming complete!"
echo
echo "Summary:"
echo "  - Docker images: ready"
echo "  - Boltz-2 cache: $BOLTZ_CACHE_DIR"
echo "  - Chai-1 cache: $CHAI_CACHE_DIR"
echo "  - BoltzGen cache: $BOLTZGEN_CACHE_DIR"
echo "  - OpenFold3 cache: $OPENFOLD3_CACHE_DIR"
echo "  - LigandMPNN: ready (weights in image)"
echo "  - BindCraft: ready (weights in image)"
echo "  - RFdiffusion3: ready (weights in image)"
echo
echo "Your deployment is now ready for production use."
echo "First-time job submissions will be significantly faster."
echo
