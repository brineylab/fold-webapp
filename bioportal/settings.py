from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


SECRET_KEY = os.environ.get("SECRET_KEY", "dev-key-change-in-production")
DEBUG = os.environ.get("DEBUG", "false").lower() == "true"

ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get(
        # "ALLOWED_HOSTS", "localhost,127.0.0.1,kraken.scripps.edu"
        "ALLOWED_HOSTS", "*"
    ).split(",")
    if h.strip()
]


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "simple_history",
    "jobs.apps.JobsConfig",
    "console.apps.ConsoleConfig",
    "api.apps.ApiConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "simple_history.middleware.HistoryRequestMiddleware",
]

ROOT_URLCONF = "bioportal.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

WSGI_APPLICATION = "bioportal.wsgi.application"


DATABASE_PATH = Path(
    os.environ.get("DATABASE_PATH", str(BASE_DIR / "db.sqlite3"))
)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DATABASE_PATH,
    }
}


AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True


STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "job_list"
LOGOUT_REDIRECT_URL = "login"


#
# Where job working directories live. In production you should set JOB_BASE_DIR
# to a dedicated filesystem path (e.g. /mnt/bioportal/jobs). The default is a
# repo-local directory for convenience.
#
JOB_BASE_DIR = Path(os.environ.get("JOB_BASE_DIR", str(BASE_DIR / "job_data")))

# Host-side path to the jobs directory. SLURM runs on the host, so sbatch
# scripts must reference host paths, not container paths. When unset (local
# dev or non-Docker), falls back to JOB_BASE_DIR.
JOB_BASE_DIR_HOST = Path(os.environ.get("JOB_BASE_DIR_HOST", str(JOB_BASE_DIR)))

# Set to "1" for development without SLURM (fake job IDs), "0" for production with real SLURM.
FAKE_SLURM = os.environ.get("FAKE_SLURM", "0") == "1"

# Boltz-2 configuration
BOLTZ_IMAGE = os.environ.get("BOLTZ_IMAGE", "boltz2:latest")
BOLTZ_CACHE_DIR = Path(os.environ.get("BOLTZ_CACHE_DIR", str(JOB_BASE_DIR_HOST / "boltz_cache")))

# Chai-1 configuration
CHAI_IMAGE = os.environ.get("CHAI_IMAGE", "chai1:latest")
CHAI_CACHE_DIR = Path(os.environ.get("CHAI_CACHE_DIR", str(JOB_BASE_DIR_HOST / "chai_cache")))

# LigandMPNN configuration (shared by ProteinMPNN and LigandMPNN model types)
LIGANDMPNN_IMAGE = os.environ.get("LIGANDMPNN_IMAGE", "ligandmpnn:latest")

# BindCraft configuration
BINDCRAFT_IMAGE = os.environ.get("BINDCRAFT_IMAGE", "bindcraft:latest")

# RFdiffusion configuration
RFDIFFUSION_IMAGE = os.environ.get("RFDIFFUSION_IMAGE", "rfdiffusion:latest")


#
# Default quota settings for new users.
# Staff users (is_staff=True) are exempt from quotas.
#
DEFAULT_MAX_CONCURRENT_JOBS = int(os.environ.get("DEFAULT_MAX_CONCURRENT_JOBS", "1"))
DEFAULT_MAX_QUEUED_JOBS = int(os.environ.get("DEFAULT_MAX_QUEUED_JOBS", "5"))
DEFAULT_JOBS_PER_DAY = int(os.environ.get("DEFAULT_JOBS_PER_DAY", "10"))
DEFAULT_RETENTION_DAYS = int(os.environ.get("DEFAULT_RETENTION_DAYS", "30"))
