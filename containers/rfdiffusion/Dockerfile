FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV CONDA_DIR=/opt/conda
ENV PATH=${CONDA_DIR}/bin:${PATH}

WORKDIR /app

# System dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       wget git build-essential ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Miniconda
RUN wget -q https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O /tmp/miniconda.sh \
    && bash /tmp/miniconda.sh -b -p ${CONDA_DIR} \
    && rm /tmp/miniconda.sh \
    && conda clean -afy

# Clone RFdiffusion
RUN git clone https://github.com/RosettaCommons/RFdiffusion.git /app/RFdiffusion

# Create conda environment from RFdiffusion's SE3nv environment file
RUN cd /app/RFdiffusion \
    && conda env create -f env/SE3nv.yml -n SE3nv \
    && conda clean -afy

# Install RFdiffusion in editable mode
RUN conda run -n SE3nv pip install --no-cache-dir -e /app/RFdiffusion

# Download model weights
RUN mkdir -p /app/RFdiffusion/models \
    && cd /app/RFdiffusion/models \
    && wget -q http://files.ipd.uw.edu/pub/RFdiffusion/6f5902ac237024bdd0c176cb93063dc4/Base_ckpt.pt \
    && wget -q http://files.ipd.uw.edu/pub/RFdiffusion/e29311f6f1bf1af907f9ef9f44b8328b/Complex_base_ckpt.pt \
    && wget -q http://files.ipd.uw.edu/pub/RFdiffusion/60f09a193fb5e5ccdc4980f631cb966f/Complex_Fold_base_ckpt.pt \
    && wget -q http://files.ipd.uw.edu/pub/RFdiffusion/74f51cfb8b440f50d70878e05361d8f0/InpaintSeq_ckpt.pt \
    && wget -q http://files.ipd.uw.edu/pub/RFdiffusion/76d00716416567174cdb7ca96e208296/InpaintSeq_Fold_ckpt.pt \
    && wget -q http://files.ipd.uw.edu/pub/RFdiffusion/5532d2571571dcf28f36d75b602f9c0b/ActiveSite_ckpt.pt \
    && wget -q http://files.ipd.uw.edu/pub/RFdiffusion/12fc204edeae5b57713c5ad7dcb97d39/Base_epoch8_ckpt.pt \
    && wget -q http://files.ipd.uw.edu/pub/RFdiffusion/f572d396fae9206628714fb2ce00f72e/Complex_beta_ckpt.pt \
    && wget -q http://files.ipd.uw.edu/pub/RFdiffusion/1befcb9b28e2f778f53d47f18b7597fa/RF_structure_prediction_weights.pt

# Set workdir to RFdiffusion root for correct Hydra config resolution
WORKDIR /app/RFdiffusion

# Make conda env the default
ENV CONDA_DEFAULT_ENV=SE3nv
RUN echo "conda activate SE3nv" >> ~/.bashrc
SHELL ["conda", "run", "-n", "SE3nv", "/bin/bash", "-c"]

ENTRYPOINT ["conda", "run", "--no-capture-output", "-n", "SE3nv"]
