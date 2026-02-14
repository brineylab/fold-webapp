# syntax=docker/dockerfile:1
FROM python:3.11-slim

# Prevent Python from writing pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install munge client library (required by SLURM's auth_munge plugin)
RUN apt-get update && \
    apt-get install -y --no-install-recommends libmunge2 && \
    rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Collect static files
RUN python manage.py collectstatic --noinput

# Create slurm user so sbatch can validate SlurmUser in slurm.conf.
# UID/GID must match the host slurm user; override at build time if needed.
ARG SLURM_UID=64030
ARG SLURM_GID=64030
RUN groupadd -g "$SLURM_GID" slurm && \
    useradd -u "$SLURM_UID" -g slurm -s /usr/sbin/nologin -M slurm

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser

# Default command (can be overridden in docker-compose)
CMD ["gunicorn", "bioportal.wsgi:application", "--bind", "0.0.0.0:8000"]

