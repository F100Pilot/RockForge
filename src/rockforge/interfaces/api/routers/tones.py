"""Tones: detection, suggestions per part of each track, the swaps, the tone
library and the tones of the player's own songs."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from fastapi import APIRouter, HTTPException
from pydantic import ValidationError

from rockforge import i18n
from rockforge.infrastructure.db.models import JobStatus
from rockforge.interfaces.api import app as api
from rockforge.interfaces.api.schemas import (
    DetectTonesOut,
    JobOut,
    ToneChangeIn,
    ToneCollectionScanIn,
    ToneReasonOut,
    ToneSegmentOut,
    ToneSuggestionsOut,
    ToneSwapIn,
    ToneSwapsIn,
    TrackTonePlanOut,
)

router = APIRouter()


@router.post("/jobs/{job_id}/detect-tones", response_model=JobOut, status_code=202)
def detect_tones_endpoint(job_id: str) -> JobOut:
    """Kick off asynchronous tone detection (Demucs guitar separation + spectral
    analysis) on the job's source recording.  Slow — poll
    GET /jobs/{job_id}/detected-tones for the result.  Progress is tracked via
    params["tone_detection_status"]; never overwrites a completed build's status."""
    with api._session_factory() as session:
        job = api._job_or_404(session, job_id)
        if job.source_type not in {"gp", "upload"}:
            raise HTTPException(422, "tone detection is not supported for this job's source")
        if not Path(job.source).exists():
            raise HTTPException(409, "source recording no longer exists on the work volume")
        params = dict(job.params or {})
        params["tone_detection_status"] = "detecting"
        job.params = params
        session.commit()
        api._enqueue_detect_tones(job)
        return api._to_out(job)


@router.get("/jobs/{job_id}/detected-tones", response_model=DetectTonesOut)
def get_detected_tones(job_id: str) -> DetectTonesOut:
    """Current tone-detection status and suggested presets."""
    with api._session_factory() as session:
        job = api._job_or_404(session, job_id)
        params = job.params or {}
        status = str(params.get("tone_detection_status", "none"))
        log = cast("list[str]", params.get("tone_detection_log") or [])
        detected = cast("dict[str, Any]", params.get("detected_tones") or {})
        return DetectTonesOut(
            status=status,
            category=str(detected.get("category", "")),
            lead=dict(detected.get("lead", {})),
            rhythm=dict(detected.get("rhythm", {})),
            lead_candidates=list(detected.get("lead_candidates", [])),
            rhythm_candidates=list(detected.get("rhythm_candidates", [])),
            profile=dict(detected.get("profile", {})),
            log=[str(line) for line in log],
            has_timeline=bool(detected.get("timeline")),
        )


@router.get("/jobs/{job_id}/tone-suggestions", response_model=ToneSuggestionsOut)
def get_tone_suggestions(job_id: str) -> ToneSuggestionsOut:
    """A tone for each part of each track: the recording's tone over time (from
    "Detetar tom") read against what each track plays there. Computed from the
    CURRENT build, so its parts and times follow every applied correction. 409
    until the project is built and the detection has measured the tone over
    time. See ``tone_analysis/sections.py``."""
    import xml.etree.ElementTree as ET

    from rockforge.application.gp_pipeline import MIN_LEAD_S
    from rockforge.infrastructure.rsxml.reader import read_arrangement_xml
    from rockforge.infrastructure.tone_analysis.analyzer import WindowProfile
    from rockforge.infrastructure.tone_analysis.sections import TrackChart, plan_tones, segments_for

    with api._session_factory() as session:
        job = api._job_or_404(session, job_id)
        if job.status is not JobStatus.COMPLETED or not job.bundle_dir:
            raise HTTPException(409, "the project has to be built first")
        params = dict(job.params or {})
        bundle = Path(job.bundle_dir)
    detected = params.get("detected_tones") or {}
    raw = detected.get("timeline") if isinstance(detected, dict) else None
    if not raw:
        raise HTTPException(409, i18n.tr(
            "ainda não há análise do tom ao longo da música — corre «Detetar tom» "
            "(de novo, se correu antes desta versão)",
            "no tone-over-time analysis yet — run «Detect tone» (again, if it ran "
            "before this version)",
        ))
    windows = [
        WindowProfile(t=float(r[0]), gain_level=float(r[1]), brightness=float(r[2]),
                      low_end=float(r[3]), active=bool(r[4]))
        for r in raw if isinstance(r, list) and len(r) >= 5
    ]
    profile_raw = detected.get("profile") if isinstance(detected, dict) else None
    profile = profile_raw if isinstance(profile_raw, dict) else {}
    song = (
        float(profile.get("gain_level", 0.4)),
        float(profile.get("brightness", 0.5)),
        float(profile.get("low_end", 0.5)),
    )

    def _num(key: str) -> float:
        v = params.get(key, 0.0)
        return float(v) if isinstance(v, (int, float, str)) else 0.0

    # The recording sits this much later in the bundle (the build's own pad).
    pad_s = max(0.0, MIN_LEAD_S - _num("offset_s")) + max(0.0, _num("lead_in_s"))
    charts: list[TrackChart] = []
    for xml_path in sorted(bundle.glob("arrangement_*.xml")):
        try:
            root = ET.parse(xml_path).getroot()
            arr = read_arrangement_xml(xml_path)
        except (ET.ParseError, ValueError, OSError):
            continue
        kind = api._built_arrangement_kind(xml_path, root)
        if kind == "Bass":
            # The timeline was measured on the GUITAR stem, and the presets are
            # guitar amps: nothing here speaks for the bass.
            continue
        end = max(
            [n.time + n.sustain for n in arr.notes] + [b.time for b in arr.tempo_map.beats] + [0.0]
        )
        charts.append(TrackChart(
            kind=kind,
            notes=arr.notes,
            segments=segments_for(
                [(sec.name, sec.start_time) for sec in arr.sections],
                [b.time for b in arr.tempo_map.beats if b.measure > 0],
                end,
            ),
        ))
    charts.sort(key=lambda c: api._build_order(c.kind))
    plans = plan_tones(windows, pad_s, song, charts)
    return ToneSuggestionsOut(
        tracks=[
            TrackTonePlanOut(
                kind=p.kind,
                segments=[
                    ToneSegmentOut(
                        name=g.name, start=g.start, end=g.end, role=g.role,
                        tone_key=g.tone_key, tone_name=g.tone_name, match=g.match,
                        confidence=g.confidence,
                        reasons=[ToneReasonOut(code=r.code, value=r.value) for r in g.reasons],
                        gain=g.gain, brightness=g.brightness, low_end=g.low_end,
                    )
                    for g in p.segments
                ],
                base=p.base, names=p.names,
                changes=[ToneChangeIn(time=t, name=k) for t, k in p.changes],
                tones=p.tones,
            )
            for p in plans
        ],
        timeline=[[round(w.t + pad_s, 3), w.gain_level, 1.0 if w.active else 0.0] for w in windows],
        swaps=_stored_tone_swaps(params),
    )


_MAX_TONE_SWAPS = 32


def _stored_tone_swaps(params: dict[str, Any]) -> dict[str, ToneSwapIn]:
    """The project's stored stand-ins, skipping any entry that no longer reads."""
    out: dict[str, ToneSwapIn] = {}
    raw = params.get("tone_swaps")
    for key, value in (raw.items() if isinstance(raw, dict) else []):
        try:
            out[str(key)] = ToneSwapIn.model_validate(value)
        except ValidationError:
            continue
    return out


@router.patch("/jobs/{job_id}/tone-swaps")
def set_tone_swaps(job_id: str, payload: ToneSwapsIn) -> dict[str, Any]:
    """Keep the tones the user picked to stand in for the suggested ones (the
    whole map, replaced), so leaving the project does not lose them. Nothing is
    rebuilt; it lives in `params`, so a fork inherits it. Each stand-in must be
    a real tone (an amp and cabinet the catalogue knows)."""
    from rockforge.infrastructure.packaging.gear.gear_catalogue import tone_from_dict

    if len(payload.swaps) > _MAX_TONE_SWAPS:
        raise HTTPException(422, f"at most {_MAX_TONE_SWAPS} tone swaps")
    for key, swap in payload.swaps.items():
        if not key or len(key) > 200:
            raise HTTPException(422, "a suggested tone key must be 1-200 characters")
        try:
            valid = tone_from_dict(swap.tone) is not None
        except (KeyError, TypeError, ValueError):
            valid = False
        if not valid:
            raise HTTPException(422, i18n.tr(
                f"o tom escolhido para «{key}» não tem amplificador e coluna válidos",
                f"the tone chosen for “{key}” has no valid amp and cabinet",
            ))
    with api._session_factory() as session:
        job = api._job_or_404(session, job_id)
        params = dict(job.params or {})
        if payload.swaps:
            params["tone_swaps"] = {k: v.model_dump() for k, v in payload.swaps.items()}
        else:
            params.pop("tone_swaps", None)
        job.params = params
        session.commit()
    return {"swaps": {k: v.model_dump() for k, v in payload.swaps.items()}}


@router.get("/tone-library")
def get_tone_library() -> dict[str, Any]:
    """All tones saved to the cross-project library (work_dir/tone_library.json).
    The UI loads one of these into a project's tone editor to reuse a dialled-in
    gear chain without rebuilding it."""
    from rockforge import tone_library

    return {"tones": tone_library.load()}


@router.post("/tone-library")
def save_tone_to_library(tone: dict[str, Any]) -> dict[str, Any]:
    """Save (or overwrite, by key) one tone in the library. The body is the same
    tone dict the tone editor stores in a job — it must carry an amp and cabinet
    (a tone is meaningless without them) and a key/name to file it under."""
    from rockforge import tone_library
    from rockforge.infrastructure.packaging.gear.gear_catalogue import tone_from_dict

    if tone_from_dict(tone) is None:
        raise HTTPException(422, "a saved tone needs a valid amp and cabinet")
    try:
        tones = tone_library.save_tone(tone)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"tones": tones}


@router.delete("/tone-library/{key}")
def delete_tone_from_library(key: str) -> dict[str, Any]:
    """Remove a tone from the library by its key (a no-op if it isn't there)."""
    from rockforge import tone_library

    return {"tones": tone_library.delete_tone(key)}


def _tone_collection_folder() -> Path | None:
    from rockforge import runtime_settings

    return runtime_settings.rocksmith_dlc_dir()


def _gear_name(gear: object) -> str:
    from rockforge.infrastructure.packaging.gear.gear_catalogue import gear_name

    return gear_name(str(gear.get("key", ""))) if isinstance(gear, dict) else ""


def _tone_collection_status() -> dict[str, Any]:
    from rockforge.i18n import tr
    from rockforge.infrastructure import tone_collection

    status = tone_collection.status()
    if status.get("error") == "psarc":
        status["error"] = tr(
            "Ler os ficheiros .psarc precisa do extra [psarc] "
            "(pip install -e \".[psarc]\").",
            "Reading .psarc files needs the [psarc] extra (pip install -e \".[psarc]\").",
        )
    return status


@router.get("/tone-collection")
def get_tone_collection(
    q: str = "", artist: str = "", offset: int = 0, limit: int = 200,
) -> dict[str, Any]:
    """The tones of every song in the player's Rocksmith dlc folder, as the last
    scan found them (``tone_collection``), filtered by ``q`` and/or one
    ``artist`` and paged — a large library has thousands. Each row is light
    (names only); the full tone is ``/tone-collection/tone``. ``artists`` lists
    every artist of the whole collection, whatever the filter, for the picker."""
    from rockforge.infrastructure import tone_collection

    # The status BEFORE the list: a scan finishing between the two reads would
    # otherwise answer "done" with the list from before it (the next poll
    # would fix it, but a "done" must mean the list is complete).
    status = _tone_collection_status()
    data = tone_collection.load()
    folder = _tone_collection_folder()
    if folder is not None and data.get("folder") not in (None, str(folder)):
        data = {}  # the cache belongs to another folder: nothing scanned here yet
    matched = tone_collection.search(q, data, artist)
    files = data.get("files") or {}
    page = []
    for row in matched[max(0, offset): max(0, offset) + max(1, min(limit, 500))]:
        tone = row["tone"]
        effects = [
            _gear_name(g)
            for slot in ("pre", "post", "racks")
            for g in tone.get(slot) or []
            if isinstance(g, dict)
        ]
        page.append({
            "id": row["id"],
            "name": tone.get("name") or tone.get("key"),
            "key": tone.get("key"),
            "song": row.get("song", ""),
            "artist": row.get("artist", ""),
            "album": row.get("album", ""),
            "arrangements": row.get("arrangements", []),
            "amp": _gear_name(tone.get("amp")),
            "cabinet": _gear_name(tone.get("cabinet")),
            "effects": effects,
            "file": row["file"],
        })
    suggested = tone_collection.suggested_folder()
    return {
        "folder": str(folder) if folder else None,
        "suggested_folder": str(suggested) if suggested else None,
        "status": status,
        "scanned_at": data.get("scanned_at"),
        "files": len(files),
        "unreadable": sum(1 for f in files.values() if isinstance(f, dict) and f.get("error")),
        "tones_total": sum(len((f or {}).get("tones") or []) for f in files.values()),
        "matched": len(matched),
        "artists": tone_collection.artists(data),
        "entries": page,
    }


@router.get("/tone-collection/tone")
def get_tone_collection_tone(id: str) -> dict[str, Any]:
    """One tone of the collection, whole, ready to add to a project or the library."""
    from rockforge.i18n import tr
    from rockforge.infrastructure import tone_collection

    for row in tone_collection.rows():
        if row["id"] == id:
            return {"tone": row["tone"], "song": row.get("song", ""),
                    "artist": row.get("artist", "")}
    raise HTTPException(404, tr(
        "tom não encontrado na coleção", "tone not found in the collection",
    ))


@router.post("/tone-collection/scan", status_code=202)
def scan_tone_collection(body: ToneCollectionScanIn) -> dict[str, Any]:
    """Read the tones of every ``.psarc`` under ``folder`` (or the folder stored
    last time) on a background thread; poll ``GET /tone-collection``. The folder
    is remembered. The archives are only read."""
    from rockforge import runtime_settings
    from rockforge.i18n import tr
    from rockforge.infrastructure import tone_collection

    raw = (body.folder or "").strip().strip('"')
    folder = Path(raw).expanduser() if raw else _tone_collection_folder()
    if folder is None:
        raise HTTPException(422, tr(
            "Indica a pasta dlc do Rocksmith.", "Give the Rocksmith dlc folder.",
        ))
    if not folder.is_dir():
        raise HTTPException(422, tr(
            f"A pasta não existe: {folder}", f"The folder does not exist: {folder}",
        ))
    runtime_settings.save({**runtime_settings.load(), "rocksmith_dlc_dir": str(folder)})
    if not tone_collection.start_scan(folder):
        raise HTTPException(409, tr(
            "Já está a decorrer uma leitura da pasta.", "A scan of the folder is already running.",
        ))
    return {"folder": str(folder), "status": _tone_collection_status()}


@router.get("/jobs/{job_id}/tones")
def get_tones(job_id: str) -> dict[str, Any]:
    """The job's current tone setup (full gear definitions, the base/extra tone
    keys, and the timed changes placed on the partitura). Backs the tone editor."""
    with api._session_factory() as session:
        job = api._job_or_404(session, job_id)
        params = job.params or {}
        names = params.get("tone_names")
        tones = params.get("tones")
        changes = params.get("tone_changes")
        per_track = params.get("arrangement_tones")
        return {
            "tone_base": params.get("tone_base"),
            "tone_names": list(names) if isinstance(names, list) else [],
            "tones": list(tones) if isinstance(tones, list) else [],
            "tone_changes": list(changes) if isinstance(changes, list) else [],
            # Tracks with their own setup; the rest use the song-level one above.
            "arrangement_tones": dict(per_track) if isinstance(per_track, dict) else {},
        }
