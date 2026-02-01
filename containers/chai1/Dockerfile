FROM nvidia/cuda:12.8.0-cudnn9-runtime-ubuntu22.04

ARG DEBIAN_FRONTEND=noninteractive
ARG CHAI_VERSION=0.6.1
ARG TORCH_CUDA_INDEX_URL=https://download.pytorch.org/whl/cu128

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3 \
        python3-venv \
        python3-pip \
        git \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONUNBUFFERED=1 \
    PIP_EXTRA_INDEX_URL=${TORCH_CUDA_INDEX_URL}

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir "chai_lab==${CHAI_VERSION}"

WORKDIR /app

# Usage: chai-lab fold <FASTA_FILE> <OUTPUT_DIR> [OPTIONS]
ENTRYPOINT ["chai-lab"]
CMD ["fold", "--help"]
