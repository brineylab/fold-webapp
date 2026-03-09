from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _parse_gpu_slots(raw_value: str | list[int] | tuple[int, ...] | None) -> list[int]:
    if raw_value is None:
        return []
    if isinstance(raw_value, (list, tuple)):
        return [int(slot) for slot in raw_value]

    slots: list[int] = []
    for chunk in str(raw_value).split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        slots.append(int(chunk))
    return slots


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


DATA_DIR = Path(os.environ.get("DATA_DIR", str(BASE_DIR / "data")))

DATABASE_PATH = Path(
    os.environ.get("DATABASE_PATH", str(DATA_DIR / "db" / "db.sqlite3"))
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
STATICFILES_DIRS = [BASE_DIR / "static"]
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
JOB_BASE_DIR = Path(os.environ.get("JOB_BASE_DIR", str(DATA_DIR / "jobs")))

# Dedicated harness working directory. This can be separate from JOB_BASE_DIR so
# the post-install validation harness can use a host-writable path even when the
# main jobs directory is managed with stricter permissions.
HARNESS_BASE_DIR = Path(
    os.environ.get("HARNESS_BASE_DIR", str(DATA_DIR / "harness"))
)
GPU_SLOTS = _parse_gpu_slots(os.environ.get("GPU_SLOTS", ""))


def _parse_optional_runtime_value(name: str, default: str = "") -> str:
    return str(os.environ.get(name, default)).strip()


DOCKER_DEFAULT_SHM_SIZE = _parse_optional_runtime_value("DOCKER_DEFAULT_SHM_SIZE", "8g")
DOCKER_DEFAULT_IPC_MODE = _parse_optional_runtime_value("DOCKER_DEFAULT_IPC_MODE", "")

# Boltz-2 configuration
BOLTZ_IMAGE = os.environ.get("BOLTZ_IMAGE", "brineylab/boltz2:latest")
BOLTZ_CACHE_DIR = Path(os.environ.get("BOLTZ_CACHE_DIR", str(JOB_BASE_DIR / "boltz_cache")))
BOLTZ_DOCKER_SHM_SIZE = _parse_optional_runtime_value(
    "BOLTZ_DOCKER_SHM_SIZE",
    "16g",
)
BOLTZ_DOCKER_IPC_MODE = _parse_optional_runtime_value(
    "BOLTZ_DOCKER_IPC_MODE",
    DOCKER_DEFAULT_IPC_MODE,
)

# Chai-1 configuration
CHAI_IMAGE = os.environ.get("CHAI_IMAGE", "brineylab/chai1:latest")
CHAI_CACHE_DIR = Path(os.environ.get("CHAI_CACHE_DIR", str(JOB_BASE_DIR / "chai_cache")))
CHAI_DOCKER_SHM_SIZE = _parse_optional_runtime_value(
    "CHAI_DOCKER_SHM_SIZE",
    DOCKER_DEFAULT_SHM_SIZE,
)
CHAI_DOCKER_IPC_MODE = _parse_optional_runtime_value(
    "CHAI_DOCKER_IPC_MODE",
    DOCKER_DEFAULT_IPC_MODE,
)

# LigandMPNN configuration (shared by ProteinMPNN and LigandMPNN model types)
LIGANDMPNN_IMAGE = os.environ.get("LIGANDMPNN_IMAGE", "brineylab/ligandmpnn:latest")
LIGANDMPNN_DOCKER_SHM_SIZE = _parse_optional_runtime_value(
    "LIGANDMPNN_DOCKER_SHM_SIZE",
    DOCKER_DEFAULT_SHM_SIZE,
)
LIGANDMPNN_DOCKER_IPC_MODE = _parse_optional_runtime_value(
    "LIGANDMPNN_DOCKER_IPC_MODE",
    DOCKER_DEFAULT_IPC_MODE,
)

# BindCraft configuration
BINDCRAFT_IMAGE = os.environ.get("BINDCRAFT_IMAGE", "brineylab/bindcraft:latest")
BINDCRAFT_DOCKER_SHM_SIZE = _parse_optional_runtime_value(
    "BINDCRAFT_DOCKER_SHM_SIZE",
    DOCKER_DEFAULT_SHM_SIZE,
)
BINDCRAFT_DOCKER_IPC_MODE = _parse_optional_runtime_value(
    "BINDCRAFT_DOCKER_IPC_MODE",
    DOCKER_DEFAULT_IPC_MODE,
)

# RFdiffusion3 configuration
RFDIFFUSION3_IMAGE = os.environ.get("RFDIFFUSION3_IMAGE", "brineylab/rfdiffusion3:latest")
RFDIFFUSION3_DOCKER_SHM_SIZE = _parse_optional_runtime_value(
    "RFDIFFUSION3_DOCKER_SHM_SIZE",
    DOCKER_DEFAULT_SHM_SIZE,
)
RFDIFFUSION3_DOCKER_IPC_MODE = _parse_optional_runtime_value(
    "RFDIFFUSION3_DOCKER_IPC_MODE",
    DOCKER_DEFAULT_IPC_MODE,
)

# BoltzGen configuration
BOLTZGEN_IMAGE = os.environ.get("BOLTZGEN_IMAGE", "brineylab/boltzgen:latest")
BOLTZGEN_CACHE_DIR = Path(os.environ.get("BOLTZGEN_CACHE_DIR", str(JOB_BASE_DIR / "boltzgen_cache")))
BOLTZGEN_DOCKER_SHM_SIZE = _parse_optional_runtime_value(
    "BOLTZGEN_DOCKER_SHM_SIZE",
    DOCKER_DEFAULT_SHM_SIZE,
)
BOLTZGEN_DOCKER_IPC_MODE = _parse_optional_runtime_value(
    "BOLTZGEN_DOCKER_IPC_MODE",
    DOCKER_DEFAULT_IPC_MODE,
)


#
# Default quota settings for new users.
# Staff users (is_staff=True) are exempt from quotas.
#
DEFAULT_MAX_CONCURRENT_JOBS = int(os.environ.get("DEFAULT_MAX_CONCURRENT_JOBS", "1"))
DEFAULT_MAX_QUEUED_JOBS = int(os.environ.get("DEFAULT_MAX_QUEUED_JOBS", "5"))
DEFAULT_JOBS_PER_DAY = int(os.environ.get("DEFAULT_JOBS_PER_DAY", "10"))
DEFAULT_RETENTION_DAYS = int(os.environ.get("DEFAULT_RETENTION_DAYS", "30"))
