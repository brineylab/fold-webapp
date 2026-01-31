# Placeholder Dockerfile for Boltz-2
# TODO: replace base image and install steps with actual Boltz-2 requirements.
FROM nvidia/cuda:12.2.2-runtime-ubuntu22.04

WORKDIR /app

# Example dependencies (replace with real ones)
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-venv python3-pip \
    && rm -rf /var/lib/apt/lists/*

COPY ./containers/shared/ /app/shared/

CMD ["/bin/bash"]
