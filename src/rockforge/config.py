"""Application settings (12-factor, env-driven)."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ROCKFORGE_", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./rockforge.db"  # PostgreSQL in production (docker-compose)
    broker_url: str = "redis://localhost:6379/0"
    result_backend: str = "redis://localhost:6379/1"
    work_dir: Path = Path("/tmp/rockforge")
    enable_youtube: bool = False  # ToS violation if enabled — operator's explicit decision
    demucs_device: str = "cpu"
    psarc_packer_cmd: str | None = None  # e.g. external DLC Builder CLI invocation


settings = Settings()
