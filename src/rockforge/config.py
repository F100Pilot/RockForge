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
    # ctranslate2 compute type for WhisperX. None = pick by device (int8 on CPU,
    # float16 on CUDA). On some NVIDIA GPUs (notably Turing / RTX 20-series) the
    # float16 path crashes natively (Windows exit 0xC0000409) on a cuDNN mismatch;
    # set "int8_float16" (lower VRAM, more compatible) to try to make the GPU work
    # instead of falling back to CPU. See ROCKFORGE_WHISPERX_COMPUTE_TYPE.
    whisperx_compute_type: str | None = None

    def lyrics_device(self) -> str:
        return self.whisperx_device or self.demucs_device

    # Stem-separation backend for POST /jobs/{id}/separate-stems:
    #   "demucs"  (default) — htdemucs_6s; one aggregated "guitar" stem.
    #   "banquet" — EXPERIMENTAL / IN TESTING: query-based finer separation
    #     (electric vs acoustic, clean vs distorted) via the query-bandit model
    #     (MIT). Needs the three paths below configured. See TESTING.md §Banquet.
    # Two guitars of the SAME class (both distorted) are still inseparable —
    # that limit is fundamental, not a backend gap.
    stem_separator: str = "demucs"
    banquet_repo: Path | None = None      # a cloned kwatcharasupat/query-bandit
    banquet_ckpt: Path | None = None      # checkpoint, e.g. ev-pre-aug.ckpt (Zenodo)
    banquet_queries: Path | None = None   # dir of <class>.wav reference clips
    banquet_device: str | None = None     # falls back to demucs_device
    banquet_batch_size: int = 4           # lower than the repo default (VRAM-safe)

    def banquet_stem_device(self) -> str:
        return self.banquet_device or self.demucs_device

    psarc_packer_cmd: str | None = None  # e.g. external DLC Builder CLI invocation
    psarc_mode: str = "native"  # "native" (default, always produces .psarc) | "dlcbuilder"
    # "celery" (default): tasks dispatched to the Celery worker (needs Redis).
    # "inprocess": tasks run in a background thread inside the API process (no
    # Redis needed). The standalone .exe sets this automatically.
    worker_mode: str = "celery"

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

    # Optional shared-secret gate (HTTP Basic — the browser's native prompt
    # attaches it automatically to every subsequent request, no frontend code
    # needed) in front of EVERY route. None (default) = no auth, correct for the
    # single-user local setups (start.bat / the standalone .exe) that bind
    # 127.0.0.1. Any deployment that opens a network port (docker-compose) MUST
    # set this — see app._verify_api_auth and docker-compose.yml.
    api_token: str | None = None

    def resolved_wwise_root(self) -> Path | None:
        if self.wwise_root is not None:
            return self.wwise_root
        env = os.environ.get("WWISEROOT")
        return Path(env) if env else None


settings = Settings()
