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
    logo_file: str = "logo.png"

    # Database
    database_url: str = "sqlite:///fold_webapp.db"

    # OAuth (GitHub)
    oauth_client_id: str = ""
    oauth_client_secret: str = ""
    oauth_redirect_uri: str = "http://localhost:8501"

    # Security
    secret_key: str = ""  # Required in production

    # AlphaFold3 paths (external dependency: run_alphafold.py is not packaged with this app)
    af3_run_script: str = "/alphafold/alphafold3/run_alphafold.py"
    af3_model_dir: str = "/alphafold/alphafold3/models"
    af3_db_dir: str = "/alphafold/af3_db"

    # Environment settings
    af3_mamba_prefix: str = "/opt/micromamba"
    af3_mamba_exe: str = "/usr/local/bin/micromamba"
    af3_conda_env: str = "af3"

    # JAX settings
    jax_cache_dir: str = "/af3_raid0/jax_cache"

    # Slurm settings
    slurm_partition: str = "main"
    slurm_cpus: int = 24
    slurm_mem: str = "128G"
    slurm_time: str = "7-00:00:00"
    slurm_gpu: str = "gpu:1"

    # SLURM priority mapping (nice values; lower is higher priority)
    slurm_priority_normal: int = 0
    slurm_priority_high: int = -100
    slurm_priority_urgent: int = -500


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
