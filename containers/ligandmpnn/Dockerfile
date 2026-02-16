FROM nvidia/cuda:13.0.1-cudnn-runtime-ubuntu24.04

ARG TORCH_CUDA_INDEX_URL=https://download.pytorch.org/whl/cu130

ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# System dependencies (gcc + python3-dev needed to compile biotite C extensions)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       python3 python3-pip python3-venv python3-dev gcc g++ ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create venv and install foundry
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"
RUN pip install --no-cache-dir --index-url ${TORCH_CUDA_INDEX_URL} torch \
    && pip install --no-cache-dir rc-foundry

# Download ProteinMPNN and LigandMPNN checkpoints
RUN foundry install proteinmpnn --checkpoint-dir /app/checkpoints \
    && foundry install ligandmpnn --checkpoint-dir /app/checkpoints

ENTRYPOINT ["mpnn"]
