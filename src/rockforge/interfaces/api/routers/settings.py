"""The app's own settings and the machine: the UI language, the in-app
settings, re-enabling the GPU, the version, the system check and the gear
catalogue with its pictures."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from rockforge import i18n
from rockforge.interfaces.api import app as api
from rockforge.interfaces.api.schemas import (
    ComponentsOut,
    RequirementOut,
    SettingsIn,
    SettingsOut,
    SystemCheckOut,
    UiLanguageIn,
    UpdateCheckOut,
)

router = APIRouter()


def _settings_out() -> SettingsOut:
    from rockforge import runtime_settings
    from rockforge.infrastructure.diagnostics import detected_rocksmith_folder
    from rockforge.interfaces.worker.celery_app import _cuda_known_broken

    repo, ckpt, queries = runtime_settings.banquet_paths()
    return SettingsOut(
        stem_separator=runtime_settings.stem_separator(),
        banquet_repo=str(repo) if repo else "",
        banquet_ckpt=str(ckpt) if ckpt else "",
        banquet_queries=str(queries) if queries else "",
        banquet=runtime_settings.banquet_validation(),
        loudness_target=runtime_settings.loudness_target(),
        gpu_broken=_cuda_known_broken(),
        whisperx_compute_type=runtime_settings.whisperx_compute_type(),
        ml_python=str(runtime_settings.ml_python() or ""),
        ml_python_info=runtime_settings.ml_python_validation(),
        rocksmith_dir=str(runtime_settings.load().get("rocksmith_dir") or ""),
        rocksmith_dir_detected=str(detected_rocksmith_folder() or ""),
        check_updates=runtime_settings.check_updates(),
        wwise_root=str(runtime_settings.load().get("wwise_root") or ""),
        wwise_root_detected=str(runtime_settings.wwise_root() or ""),
    )


@router.put("/ui-language")
def set_ui_language(body: UiLanguageIn) -> dict[str, str]:
    """Remember the app's language (Português / English) for what runs outside a
    request — the worker's logs, the desktop window's close dialog. The browser
    keeps its own copy and sends it with every request."""
    from rockforge import runtime_settings

    if not i18n.valid(body.lang):
        raise HTTPException(422, "lang must be a language code such as 'pt' or 'en'")
    runtime_settings.save({**runtime_settings.load(), "ui_language": body.lang})
    return {"lang": body.lang}


@router.get("/settings", response_model=SettingsOut)
def get_settings() -> SettingsOut:
    """App settings editable from the UI (stem-separator backend + Banquet paths).
    Includes per-path readiness so the UI can show which parts are configured."""
    return _settings_out()


@router.post("/settings", response_model=SettingsOut)
def update_settings(body: SettingsIn) -> SettingsOut:
    """Persist the settings (work_dir/settings.json), shared by the worker. An
    empty string clears an override (falls back to the env default). Enabling
    Banquet without valid paths is allowed but flagged not-ready in the response
    (the separation itself then fails gracefully with a clear message)."""
    from rockforge import runtime_settings

    if body.stem_separator not in (None, "", "demucs", "banquet"):
        raise HTTPException(422, "stem_separator must be 'demucs' or 'banquet'")
    updates = dict(runtime_settings.load())
    for key in (
        "stem_separator", "banquet_repo", "banquet_ckpt", "banquet_queries",
        "whisperx_compute_type", "ml_python", "rocksmith_dir", "wwise_root",
    ):
        val = getattr(body, key)
        if val is not None:
            updates[key] = val.strip() if isinstance(val, str) else val
    if body.loudness_target is not None:
        updates["loudness_target"] = float(body.loudness_target)
    if body.check_updates is not None:
        updates["check_updates"] = bool(body.check_updates)
    runtime_settings.save(updates)
    return _settings_out()


@router.post("/gpu-reset", response_model=SettingsOut)
def reset_gpu() -> SettingsOut:
    """Delete the GPU-broken marker so the ML stack (Demucs + WhisperX) retries
    the GPU on the next detection — for after the user fixed their CUDA/cuDNN
    install. Saves them hunting for the hidden marker file in the work dir."""
    from rockforge.interfaces.worker.celery_app import _clear_cuda_broken

    _clear_cuda_broken()
    return _settings_out()


@router.get("/version", include_in_schema=False)
def version() -> dict[str, str]:
    return {"version": api.app.version}


@router.get("/update-check", response_model=UpdateCheckOut)
def update_check(force: bool = False) -> UpdateCheckOut:
    """Whether a newer RockForge is on GitHub's Releases page — asked at most
    once a day, never when the user turned it off, and every failure is just
    "nothing new" (infrastructure/update_check.py)."""
    from rockforge import __version__, runtime_settings
    from rockforge.infrastructure import update_check as uc

    if not runtime_settings.check_updates():
        return UpdateCheckOut(enabled=False, current=__version__, kind=uc.install_kind())
    info = uc.check(force=force)
    return UpdateCheckOut(**{k: v for k, v in uc.as_dict(info).items() if k != "checked_at"})


def _components_out() -> ComponentsOut:
    from rockforge.infrastructure import components

    return ComponentsOut(**{
        k: v for k, v in components.status().items() if k in ComponentsOut.model_fields
    })


@router.get("/components", response_model=ComponentsOut)
def components_status() -> ComponentsOut:
    """What the `.exe`'s extra components have, and how an install is going."""
    return _components_out()


@router.post("/components/install", response_model=ComponentsOut, status_code=202)
def components_install() -> ComponentsOut:
    """Download and install the extra components in the background (the
    Windows `.exe` only: a Python install has start.bat for that)."""
    from rockforge.infrastructure import components

    if not components.supported():
        raise HTTPException(409, i18n.tr(
            "Só o RockForge instalado (.exe) instala os componentes sozinho; a partir do "
            "código, o start.bat instala-os.",
            "Only the installed RockForge (.exe) installs the components itself; from the "
            "source code, start.bat installs them.",
        ))
    if not components.start_install():
        raise HTTPException(409, i18n.tr(
            "A instalação já está a decorrer.", "The install is already running."
        ))
    return _components_out()


@router.post("/components/decline", response_model=ComponentsOut)
def components_decline() -> ComponentsOut:
    """«Agora não»: stop offering them on the home page (Definições still can)."""
    from rockforge import runtime_settings

    runtime_settings.save({**runtime_settings.load(), "components_declined": True})
    return _components_out()


@router.get("/system-check", response_model=SystemCheckOut)
def system_check() -> SystemCheckOut:
    """What external software this machine has, and what each gap costs.

    RockForge ships almost none of its dependencies — Wwise cannot legally be
    redistributed, the ML stack is gigabytes, ffmpeg is better taken from the
    system. Each already degrades cleanly on its own, but the symptom always
    surfaces downstream and reads as a bug ("o PSARC não é jogável"), so this
    is the one place that names the cause instead.
    """
    from rockforge.infrastructure import diagnostics
    from rockforge.interfaces.worker.celery_app import _cuda_known_broken

    reqs = diagnostics.check_requirements(api.settings, gpu_broken=_cuda_known_broken())
    return SystemCheckOut(
        requirements=[RequirementOut(**vars(r)) for r in reqs],
        missing_required=[r.key for r in diagnostics.missing_required(reqs)],
    )


@router.get("/gear-catalogue")
def gear_catalogue() -> dict[str, Any]:
    """The Rocksmith gear catalogue (amps/cabinets/pedals/racks + descriptors)
    that backs the tone-builder UI. Static data — safe to cache client-side."""
    from rockforge.infrastructure.packaging.gear.gear_catalogue import catalogue_for_ui

    return catalogue_for_ui()


@router.get("/gear-image/{key}")
def gear_image(key: str) -> FileResponse:
    """Serve a gear image for the tone editor, if one exists.

    Looks first in ``work_dir/gear_images/<key>.<ext>`` (the user's own
    override) then the bundled ``web/gear_images/<key>.<ext>`` shipped in the
    repo. 404 when absent in both; the UI then falls back to the generic panel.
    The key is sanitised to a bare slug so it can't escape the folder."""
    slug = "".join(c for c in key if c.isalnum() or c in "-_")
    if not slug:
        raise HTTPException(404, "no such gear image")
    for folder in api._gear_image_dirs():
        for ext in (".png", ".jpg", ".jpeg", ".webp"):
            candidate = folder / f"{slug}{ext}"
            if candidate.is_file():
                media = (
                    "image/jpeg" if ext in (".jpg", ".jpeg") else f"image/{ext[1:]}"
                )
                return FileResponse(candidate, media_type=media)
    raise HTTPException(404, "no gear image for this key")
