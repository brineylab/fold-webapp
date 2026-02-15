FROM nvcr.io/nvidia/cuda:11.6.2-cudnn8-runtime-ubuntu20.04

RUN apt-get -q update \
  && DEBIAN_FRONTEND=noninteractive apt-get install --no-install-recommends -y \
  git \
  python3.9 \
  python3-pip \
  && python3.9 -m pip install -q -U --no-cache-dir pip \
  && rm -rf /var/lib/apt/lists/* \
  && apt-get autoremove -y \
  && apt-get clean

RUN git clone https://github.com/RosettaCommons/RFdiffusion.git /app/RFdiffusion

# PyTorch 1.12.1 with CUDA 11.6 — use PyTorch index as primary so pip
# fetches the cu116 wheel; fall back to PyPI for transitive deps.
RUN pip install -q --no-cache-dir \
  torch==1.12.1 \
  --index-url https://download.pytorch.org/whl/cu116 \
  --extra-index-url https://pypi.org/simple

# DGL with CUDA 11.6
RUN pip install -q --no-cache-dir \
  dgl==1.0.2+cu116 \
  -f https://data.dgl.ai/wheels/cu116/repo.html

# Remaining Python deps + SE3Transformer + RFdiffusion
RUN pip install -q --no-cache-dir \
  e3nn==0.3.3 \
  wandb==0.12.0 \
  pynvml==11.0.0 \
  git+https://github.com/NVIDIA/dllogger#egg=dllogger \
  decorator==5.1.0 \
  hydra-core==1.3.2 \
  pyrsistent==0.19.3 \
  /app/RFdiffusion/env/SE3Transformer \
  && pip install --no-cache-dir /app/RFdiffusion --no-deps

RUN mkdir -p /app/RFdiffusion/models

WORKDIR /app/RFdiffusion

ENV DGLBACKEND="pytorch"

ENTRYPOINT ["python3.9", "scripts/run_inference.py"]
