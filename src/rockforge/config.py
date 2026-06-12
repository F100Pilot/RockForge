"""Application settings (12-factor, env-driven)."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ROCKFORGE_", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./rockforge.db"  # PostgreSQL in production (docker-compose)
    broker_url: str = "redis://localhost:6379/0"
    result_backend: str = "redis://localhost:6379/1"
    work_dir: Path = Path.home() / "Downloads" / "RockForge"
    enable_youtube: bool = False  # ToS violation if enabled — operator's explicit decision
    demucs_device: str = "cpu"
    psarc_packer_cmd: str | None = None  # e.g. external DLC Builder CLI invocation

    # Local Wwise installation (NEVER bundled — Audiokinetic EULA). Falls back to
    # the standard WWISEROOT env var set by the Audiokinetic Launcher.
    wwise_root: Path | None = None

    def resolved_wwise_root(self) -> Path | None:
        if self.wwise_root is not None:
            return self.wwise_root
        env = os.environ.get("WWISEROOT")
        return Path(env) if env else None


settings = Settings()
