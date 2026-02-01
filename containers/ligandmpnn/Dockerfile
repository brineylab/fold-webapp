FROM nvidia/cuda:12.8.0-runtime-ubuntu22.04

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       python3 python3-pip git \
    && rm -rf /var/lib/apt/lists/*

RUN git clone https://github.com/dauparas/LigandMPNN.git /app \
    && pip3 install --no-cache-dir -r /app/requirements.txt

# Download all checkpoint files
RUN bash /app/get_model_params.sh /app

ENTRYPOINT ["python3", "/app/run.py"]
