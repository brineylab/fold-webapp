FROM nvidia/cuda:12.8.0-cudnn-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV CONDA_DIR=/opt/conda
ENV PATH=${CONDA_DIR}/bin:${PATH}

WORKDIR /app

# System dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       wget git build-essential ca-certificates \
       dssp \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Miniforge (mamba)
RUN wget -q https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-$(uname -m).sh -O /tmp/miniforge.sh \
    && bash /tmp/miniforge.sh -b -p ${CONDA_DIR} \
    && rm /tmp/miniforge.sh \
    && mamba clean -afy \
    && conda config --remove channels defaults 2>/dev/null || true

SHELL ["/bin/bash", "-lc"]

# Clone BindCraft
RUN git clone https://github.com/martinpacesa/BindCraft.git /app/bindcraft

# Install BindCraft using the repository's own install script.
# Note: PyRosetta requires access to the GrayLab channel described by BindCraft.
RUN cd /app/bindcraft \
    && bash ./install_bindcraft.sh --cuda '12.8' --pkg_manager 'mamba' \
    && mamba clean -afy

# Make conda env the default
ENV CONDA_DEFAULT_ENV=BindCraft
RUN echo "conda activate BindCraft" >> ~/.bashrc

ENTRYPOINT ["conda", "run", "--no-capture-output", "-n", "BindCraft"]
