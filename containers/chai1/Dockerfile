FROM nvidia/cuda:12.8.0-cudnn-runtime-ubuntu22.04

ARG DEBIAN_FRONTEND=noninteractive
ARG TORCH_CUDA_INDEX_URL=https://download.pytorch.org/whl/cu128

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3 \
        python3-dev \
        python3-venv \
        python3-pip \
        build-essential \
        git \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH \
    CC=/usr/bin/gcc \
    CXX=/usr/bin/g++ \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir "chai_lab==0.6.1" \
    && pip install --no-cache-dir \
       --index-url ${TORCH_CUDA_INDEX_URL} \
       --extra-index-url https://pypi.org/simple/ \
       --force-reinstall torch

WORKDIR /app

# Usage: chai-lab fold <FASTA_FILE> <OUTPUT_DIR> [OPTIONS]
ENTRYPOINT ["chai-lab"]
CMD ["fold", "--help"]
