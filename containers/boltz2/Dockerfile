FROM nvidia/cuda:13.0.1-cudnn-runtime-ubuntu24.04

ARG DEBIAN_FRONTEND=noninteractive
ARG TORCH_CUDA_INDEX_URL=https://download.pytorch.org/whl/cu130

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
        cuda-cupti-13-0 \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir "boltz[cuda]" \
    && pip install --no-cache-dir --index-url ${TORCH_CUDA_INDEX_URL} \
       --force-reinstall --no-deps torch

WORKDIR /app

# Usage: boltz predict <INPUT_PATH> [OPTIONS]
ENTRYPOINT ["boltz"]
CMD ["predict", "--help"]
