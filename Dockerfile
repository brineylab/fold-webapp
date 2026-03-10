# syntax=docker/dockerfile:1

# --- Stage 1: build Tailwind CSS ---
FROM node:20-slim AS css-build
WORKDIR /build
COPY package.json package-lock.json* ./
RUN npm ci --ignore-scripts
COPY tailwind.config.js .
COPY static_src/ static_src/
COPY jobs/templates/ jobs/templates/
COPY console/templates/ console/templates/
COPY templates/ templates/
RUN npm run build:css

# --- Stage 2: application image ---
FROM docker:cli AS dockercli
FROM python:3.11-slim

# Prevent Python from writing pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# The compose-packaged web/worker processes shell out to the host Docker daemon.
COPY --from=dockercli /usr/local/bin/docker /usr/local/bin/docker

# Copy application code
COPY . .

# Copy built Tailwind CSS from stage 1
COPY --from=css-build /build/static/css/app.css static/css/app.css

# Collect static files
RUN python manage.py collectstatic --noinput

# Create non-root user for security. Match the host install user's uid/gid by
# default so bind-mounted data stays writable without manual chown cycles.
ARG APP_UID=1000
ARG APP_GID=1000
RUN groupadd -o -g "$APP_GID" appuser && \
    useradd -o -u "$APP_UID" -g appuser --create-home --shell /bin/bash appuser && \
    chown -R "$APP_UID:$APP_GID" /app
USER appuser

# Default command (can be overridden in docker-compose)
CMD ["gunicorn", "bioportal.wsgi:application", "--bind", "0.0.0.0:8000"]
