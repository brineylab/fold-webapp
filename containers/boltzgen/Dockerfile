FROM nvidia/cuda:12.4.0-cudnn-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip git ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Install BoltzGen (requires Python >= 3.11)
RUN pip install --no-cache-dir boltzgen

# Optional: pre-download weights (~6GB)
ARG DOWNLOAD_WEIGHTS=false
RUN if [ "$DOWNLOAD_WEIGHTS" = "true" ]; then \
    python3 -c "import boltzgen; boltzgen.download_weights()"; fi

ENTRYPOINT ["boltzgen"]
