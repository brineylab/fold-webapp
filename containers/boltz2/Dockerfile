FROM nvidia/cuda:12.8.0-cudnn-runtime-ubuntu22.04

ARG DEBIAN_FRONTEND=noninteractive
ARG TORCH_CUDA_INDEX_URL=https://download.pytorch.org/whl/cu128

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
    PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir "boltz[cuda]==2.2.1" \
    && pip install --no-cache-dir \
       --index-url ${TORCH_CUDA_INDEX_URL} \
       --extra-index-url https://pypi.org/simple/ \
       --force-reinstall torch

WORKDIR /app

# Usage: boltz predict <INPUT_PATH> [OPTIONS]
ENTRYPOINT ["boltz"]
CMD ["predict", "--help"]
