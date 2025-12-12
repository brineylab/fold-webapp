from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration.

    Values can be overridden via environment variables prefixed with `FOLD_`.
    Example: `FOLD_BASE_DIR=/path/to/jobs`.
    """

    model_config = SettingsConfigDict(env_prefix="FOLD_", env_file=".env", extra="ignore")

    base_dir: str = "/af3_raid0/web_jobs"
    af3_run_cmd: str = "/usr/local/bin/af3run"
    logo_file: str = "logo.png"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


