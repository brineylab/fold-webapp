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
Fold Webapp — Model Weight Download Script

Usage: ./scripts/download_weights.sh [model] [--overwrite]

Downloads and caches model weights for supported models.

Models:
  boltz2        Boltz-2 weights (~2-3 GB)
  chai1         Chai-1 weights (~2-3 GB)
  boltzgen      BoltzGen weights (~6 GB)
  rfdiffusion   RFdiffusion weights (~1.5 GB)

If no model is specified, downloads weights for all supported models.

Options:
  --overwrite   Remove existing cached weights before re-downloading
  -h, --help    Show this help message

Skipped models (weights baked into Docker image at build time):
  - LigandMPNN / ProteinMPNN (via foundry install in Dockerfile)
  - BindCraft (via download_af2_weights.py in Dockerfile)
  - RFdiffusion3 (via foundry install rfd3 in Dockerfile)
EOF
}

# ---------- argument parsing ----------

MODEL=""
OVERWRITE=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --overwrite)
            OVERWRITE=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        -*)
            echo "ERROR: Unknown option: $1"
            usage
            exit 1
            ;;
        *)
            if [ -n "$MODEL" ]; then
                echo "ERROR: Only one model can be specified at a time"
                usage
                exit 1
            fi
            MODEL="$1"
            shift
            ;;
    esac
done

# ---------- environment setup ----------

if [ ! -f .env ]; then
    warn ".env file not found. Using env.example defaults."
    ENV_FILE=env.example
else
    ENV_FILE=.env
fi

set -a
source "$ENV_FILE"
set +a

BOLTZ_IMAGE="${BOLTZ_IMAGE:-brineylab/boltz2:latest}"
BOLTZ_CACHE_DIR="${BOLTZ_CACHE_DIR:-./data/jobs/boltz_cache}"

CHAI_IMAGE="${CHAI_IMAGE:-brineylab/chai1:latest}"
CHAI_CACHE_DIR="${CHAI_CACHE_DIR:-./data/jobs/chai_cache}"

BOLTZGEN_IMAGE="${BOLTZGEN_IMAGE:-brineylab/boltzgen:latest}"
BOLTZGEN_CACHE_DIR="${BOLTZGEN_CACHE_DIR:-./data/jobs/boltzgen_cache}"

RFDIFFUSION_MODELS_DIR="${RFDIFFUSION_MODELS_DIR:-./data/jobs/rfdiffusion_models}"

# ---------- prerequisite checks ----------

check_docker() {
    if ! command -v docker &>/dev/null; then
        echo "ERROR: Docker is not installed. See https://docs.docker.com/get-docker/"
        exit 1
    fi
}

# ---------- per-model download functions ----------

download_boltz2_weights() {
    info "Boltz-2 weights"

    if [ "$OVERWRITE" = true ] && [ -d "$BOLTZ_CACHE_DIR" ]; then
        step "Removing existing Boltz-2 cache (--overwrite)..."
        rm -rf "$BOLTZ_CACHE_DIR"
    fi

    if [ -f "$BOLTZ_CACHE_DIR/boltz2_conf.ckpt" ]; then
        step "Weights already cached at $BOLTZ_CACHE_DIR (skipping)"
        return 0
    fi

    check_docker
    mkdir -p "$BOLTZ_CACHE_DIR"

    step "Downloading Boltz-2 weights via direct API (no GPU required)..."
    docker run --rm \
        -v "$BOLTZ_CACHE_DIR:/cache" \
        "$BOLTZ_IMAGE" \
        python3 -c "from pathlib import Path; from boltz.main import download_boltz2; download_boltz2(Path('/cache'))" || {
            warn "Boltz-2 weight download failed."
            return 1
        }

    step "Boltz-2 weights cached to $BOLTZ_CACHE_DIR"
}

download_chai1_weights() {
    info "Chai-1 weights"

    if [ "$OVERWRITE" = true ] && [ -d "$CHAI_CACHE_DIR" ]; then
        step "Removing existing Chai-1 cache (--overwrite)..."
        rm -rf "$CHAI_CACHE_DIR"
    fi

    if [ -f "$CHAI_CACHE_DIR/models_v2/trunk.pt" ]; then
        step "Weights already cached at $CHAI_CACHE_DIR (skipping)"
        return 0
    fi

    check_docker
    mkdir -p "$CHAI_CACHE_DIR"

    step "Downloading Chai-1 weights via direct API (no GPU required)..."
    docker run --rm \
        -e CHAI_DOWNLOADS_DIR=/cache \
        -v "$CHAI_CACHE_DIR:/cache" \
        "$CHAI_IMAGE" \
        python3 -c "
from chai_lab.utils.paths import chai1_component, cached_conformers
components = ['default', 'trunk', 'diffusion', 'confidence', 'token_embedder']
for c in components:
    chai1_component(c)
cached_conformers.get_path()
" || {
            warn "Chai-1 weight download failed."
            return 1
        }

    step "Chai-1 weights cached to $CHAI_CACHE_DIR"
}

download_boltzgen_weights() {
    info "BoltzGen weights"

    if [ "$OVERWRITE" = true ] && [ -d "$BOLTZGEN_CACHE_DIR" ]; then
        step "Removing existing BoltzGen cache (--overwrite)..."
        rm -rf "$BOLTZGEN_CACHE_DIR"
    fi

    # Check if cache dir exists and is non-empty
    if [ -d "$BOLTZGEN_CACHE_DIR" ] && [ -n "$(ls -A "$BOLTZGEN_CACHE_DIR" 2>/dev/null)" ]; then
        step "Weights already cached at $BOLTZGEN_CACHE_DIR (skipping)"
        return 0
    fi

    check_docker
    mkdir -p "$BOLTZGEN_CACHE_DIR"

    step "Downloading BoltzGen weights via direct API (no GPU required)..."
    docker run --rm \
        -v "$BOLTZGEN_CACHE_DIR:/cache" \
        -e HF_HOME=/cache \
        "$BOLTZGEN_IMAGE" \
        python3 -c "import boltzgen; boltzgen.download_weights()" || {
            warn "BoltzGen weight download failed."
            return 1
        }

    step "BoltzGen weights cached to $BOLTZGEN_CACHE_DIR"
}

download_rfdiffusion_weights() {
    info "RFdiffusion weights"

    if [ "$OVERWRITE" = true ] && [ -d "$RFDIFFUSION_MODELS_DIR" ]; then
        step "Removing existing RFdiffusion models (--overwrite)..."
        rm -rf "$RFDIFFUSION_MODELS_DIR"
    fi

    if [ -f "$RFDIFFUSION_MODELS_DIR/Base_ckpt.pt" ]; then
        step "Weights already cached at $RFDIFFUSION_MODELS_DIR (skipping)"
        return 0
    fi

    if ! command -v wget &>/dev/null; then
        echo "ERROR: wget is required for RFdiffusion weight downloads."
        return 1
    fi

    mkdir -p "$RFDIFFUSION_MODELS_DIR"

    RFDIFFUSION_BASE_URL="http://files.ipd.uw.edu/pub/RFdiffusion"
    RFDIFFUSION_WEIGHTS=(
        "6f5902ac237024bdd0c176cb93063dc4/Base_ckpt.pt"
        "e75e09f351e8c1f6e5c75dba5feab75e/Complex_base_ckpt.pt"
    )

    for weight_path in "${RFDIFFUSION_WEIGHTS[@]}"; do
        filename="${weight_path##*/}"
        if [ -f "$RFDIFFUSION_MODELS_DIR/$filename" ]; then
            step "$filename already exists, skipping"
        else
            step "Downloading $filename..."
            wget -q --show-progress -O "$RFDIFFUSION_MODELS_DIR/$filename" \
                "$RFDIFFUSION_BASE_URL/$weight_path" || {
                    warn "Failed to download $filename"
                }
        fi
    done

    step "RFdiffusion weights cached to $RFDIFFUSION_MODELS_DIR"
}

# ---------- main ----------

run_all() {
    download_boltz2_weights
    echo
    download_chai1_weights
    echo
    download_boltzgen_weights
    echo
    download_rfdiffusion_weights
    echo
}

if [ -n "$MODEL" ]; then
    case "$MODEL" in
        boltz2)       download_boltz2_weights ;;
        chai1)        download_chai1_weights ;;
        boltzgen)     download_boltzgen_weights ;;
        rfdiffusion)  download_rfdiffusion_weights ;;
        *)
            echo "ERROR: Unknown model: $MODEL"
            echo "Supported models: boltz2, chai1, boltzgen, rfdiffusion"
            exit 1
            ;;
    esac
else
    info "Downloading weights for all supported models..."
    echo
    run_all
    info "All model weights downloaded."
fi
