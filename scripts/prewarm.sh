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
  Reads .env file for configuration (BOLTZ_CACHE_DIR, CHAI_CACHE_DIR,
  RFDIFFUSION_MODELS_DIR, etc.)
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
RFDIFFUSION_IMAGE="${RFDIFFUSION_IMAGE:-brineylab/rfdiffusion:latest}"
BOLTZ_CACHE_DIR="${BOLTZ_CACHE_DIR:-./data/jobs/boltz_cache}"
CHAI_CACHE_DIR="${CHAI_CACHE_DIR:-./data/jobs/chai_cache}"
RFDIFFUSION_MODELS_DIR="${RFDIFFUSION_MODELS_DIR:-./data/jobs/rfdiffusion_models}"

# Add registry prefix if specified
if [ -n "$REGISTRY" ]; then
    BOLTZ_IMAGE="${REGISTRY}/${BOLTZ_IMAGE}"
    CHAI_IMAGE="${REGISTRY}/${CHAI_IMAGE}"
    LIGANDMPNN_IMAGE="${REGISTRY}/${LIGANDMPNN_IMAGE}"
    RFDIFFUSION_IMAGE="${REGISTRY}/${RFDIFFUSION_IMAGE}"
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

    step "Pulling RFdiffusion image: $RFDIFFUSION_IMAGE"
    if ! docker pull "$RFDIFFUSION_IMAGE" 2>/dev/null; then
        warn "Failed to pull $RFDIFFUSION_IMAGE from registry."
        step "Building RFdiffusion image locally..."
        docker build -t "$RFDIFFUSION_IMAGE" containers/rfdiffusion/
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
echo "  - RFdiffusion models: $RFDIFFUSION_MODELS_DIR"
echo "  - LigandMPNN: ready (weights in image)"
echo
echo "Your deployment is now ready for production use."
echo "First-time job submissions will be significantly faster."
echo
