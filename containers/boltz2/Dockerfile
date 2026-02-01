FROM nvidia/cuda:12.2.2-cudnn8-runtime-ubuntu22.04

ARG DEBIAN_FRONTEND=noninteractive
ARG BOLTZ_VERSION=2.2.1
ARG TORCH_CUDA_INDEX_URL=https://download.pytorch.org/whl/cu121

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3 \
        python3-venv \
        python3-pip \
        git \
        curl \
        ca-certificates \
        libglib2.0-0 \
        libsm6 \
        libxrender1 \
        libxext6 \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONUNBUFFERED=1 \
    PIP_EXTRA_INDEX_URL=${TORCH_CUDA_INDEX_URL}

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir "boltz[cuda]==${BOLTZ_VERSION}"

WORKDIR /app

# Usage: boltz predict <INPUT_PATH> [OPTIONS]
ENTRYPOINT ["boltz"]
CMD ["predict", "--help"]
