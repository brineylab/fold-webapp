FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV CONDA_DIR=/opt/conda
ENV PATH=${CONDA_DIR}/bin:${PATH}

WORKDIR /app

# System dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       wget git build-essential ca-certificates \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Miniforge (mamba)
RUN wget -q https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-$(uname -m).sh -O /tmp/miniforge.sh \
    && bash /tmp/miniforge.sh -b -p ${CONDA_DIR} \
    && rm /tmp/miniforge.sh \
    && mamba clean -afy \
    && conda config --remove channels defaults 2>/dev/null || true

# Copy our custom environment file (unpinned deps, no defaults channel)
COPY containers/rfdiffusion/SE3nv.yml /tmp/SE3nv.yml

# Clone RFdiffusion
RUN git clone https://github.com/RosettaCommons/RFdiffusion.git /app/RFdiffusion

# Create conda environment from our custom environment file
RUN mamba env create -f /tmp/SE3nv.yml -n SE3nv \
    && mamba clean -afy

# Install SE3Transformer (bundled in repo) and RFdiffusion
RUN mamba run -n SE3nv pip install --no-cache-dir \
    /app/RFdiffusion/env/SE3Transformer \
    -e /app/RFdiffusion

# Model weights directory — mount from host via RunnerConfig extra_mounts
# e.g. {"source": "/data/rfdiffusion/models", "target": "/app/RFdiffusion/models"}
RUN mkdir -p /app/RFdiffusion/models

# Set workdir to RFdiffusion root for correct Hydra config resolution
WORKDIR /app/RFdiffusion

# Make conda env the default
ENV CONDA_DEFAULT_ENV=SE3nv
RUN echo "conda activate SE3nv" >> ~/.bashrc
SHELL ["conda", "run", "-n", "SE3nv", "/bin/bash", "-c"]

ENTRYPOINT ["conda", "run", "--no-capture-output", "-n", "SE3nv"]
