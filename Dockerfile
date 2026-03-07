# syntax=docker/dockerfile:1
FROM python:3.11-slim

# Prevent Python from writing pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

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
