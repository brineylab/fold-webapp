FROM nvidia/cuda:13.0.1-cudnn-runtime-ubuntu24.04

ARG TORCH_CUDA_INDEX_URL=https://download.pytorch.org/whl/cu130

ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv git ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Create venv and install BoltzGen (requires Python >= 3.11; Ubuntu 24.04 ships 3.12)
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"
RUN pip install --no-cache-dir --index-url ${TORCH_CUDA_INDEX_URL} torch \
    && pip install --no-cache-dir boltzgen

# Optional: pre-download weights (~6GB)
ARG DOWNLOAD_WEIGHTS=false
RUN if [ "$DOWNLOAD_WEIGHTS" = "true" ]; then \
    python3 -c "import boltzgen; boltzgen.download_weights()"; fi

ENTRYPOINT ["boltzgen"]
