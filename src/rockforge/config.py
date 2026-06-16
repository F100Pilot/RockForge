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
    enable_youtube: bool = True  # operator-enabled; downloading audio violates the YouTube ToS
    # ML device: "auto" (default) picks a CUDA GPU when one is usable and falls
    # back to CPU; force with "cpu" or "cuda". Resolution happens in the worker
    # (deferred torch import) — see celery_app._resolve_device.
    demucs_device: str = "auto"
    # Lyric detection (Demucs vocals + WhisperX). On CPU this is the slow path;
    # set both devices to "cuda" (or leave "auto" with a GPU present) for the
    # ~3-minute experience online tools get. whisperx_device defaults to
    # demucs_device when unset.
    whisperx_device: str | None = None
    # WhisperX model: "tiny"/"base"/"small"/"medium"/"large-v3". Bigger = more
    # accurate but slower; "small" is a good CPU default. Drop to "base"/"tiny"
    # to trade accuracy for speed.
    whisper_model: str = "small"

    def lyrics_device(self) -> str:
        return self.whisperx_device or self.demucs_device
    psarc_packer_cmd: str | None = None  # e.g. external DLC Builder CLI invocation
    psarc_mode: str = "dlcbuilder"  # "dlcbuilder" (default) | "native" (packer/packer.py)

    # Local single-user setups (start.bat): if > 0, the API process exits when
    # the web UI stops sending /heartbeat pings for this many seconds (i.e. the
    # browser tab was closed), so start.bat's cleanup also stops the worker and
    # any Redis it launched. 0 (default) disables this — required for shared
    # deployments (docker-compose) where closing one user's tab must not affect
    # others.
    idle_shutdown_s: float = 0.0

    # Local Wwise installation (NEVER bundled — Audiokinetic EULA). Falls back to
    # the standard WWISEROOT env var set by the Audiokinetic Launcher.
    wwise_root: Path | None = None

    def resolved_wwise_root(self) -> Path | None:
        if self.wwise_root is not None:
            return self.wwise_root
        env = os.environ.get("WWISEROOT")
        return Path(env) if env else None


settings = Settings()
