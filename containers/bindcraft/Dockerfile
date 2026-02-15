FROM nvidia/cuda:12.4.0-cudnn-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV CONDA_DIR=/opt/conda
ENV PATH=${CONDA_DIR}/bin:${PATH}

WORKDIR /app

# System dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       wget git build-essential ca-certificates \
       dssp \
    && rm -rf /var/lib/apt/lists/*

# Install Miniconda
RUN wget -q https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O /tmp/miniconda.sh \
    && bash /tmp/miniconda.sh -b -p ${CONDA_DIR} \
    && rm /tmp/miniconda.sh \
    && conda clean -afy

# Clone BindCraft
RUN git clone https://github.com/martinpacesa/BindCraft.git /app/bindcraft

# Create conda environment from BindCraft's environment file
# Note: PyRosetta requires academic license access via conda channel.
# Adjust the channel URL below if needed for your license.
RUN cd /app/bindcraft \
    && conda env create -f environment.yml -n bindcraft \
    && conda clean -afy

# Install ColabDesign (af2 binder hallucination backbone)
RUN conda run -n bindcraft pip install --no-cache-dir \
    git+https://github.com/sokrypton/ColabDesign.git

# Download AlphaFold2 weights
RUN conda run -n bindcraft python /app/bindcraft/functions/download_af2_weights.py \
    --weights_dir /app/params

# Make conda env the default
ENV CONDA_DEFAULT_ENV=bindcraft
RUN echo "conda activate bindcraft" >> ~/.bashrc
SHELL ["conda", "run", "-n", "bindcraft", "/bin/bash", "-c"]

ENTRYPOINT ["conda", "run", "--no-capture-output", "-n", "bindcraft"]
