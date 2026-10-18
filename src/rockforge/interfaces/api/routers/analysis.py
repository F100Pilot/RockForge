"""Measurements on the recording from one point: the tempo from a clicked instant
("Corrigir daqui") and the recording's cent offset."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException

from rockforge import i18n
from rockforge.interfaces.api import app as api
from rockforge.interfaces.api.schemas import (
    AttackSourcesOut,
    DetectAttacksOut,
    DetectBeatSyncIn,
    DetectBeatSyncOut,
    DetectTempoIn,
    DetectTempoOut,
    DetectTuningOut,
    OnsetLevelsOut,
)

router = APIRouter()


@router.post("/jobs/{job_id}/detect-tempo", response_model=DetectTempoOut)
def detect_tempo(job_id: str, payload: DetectTempoIn) -> DetectTempoOut:
    """Measure the recording's tempo from ``from_s`` onward (librosa) and return a
    factor to re-tempo the chart's following notes to it. This is a
    proposal the user previews in the tab viewer before rebuilding."""
    with api._session_factory() as session:
        job = api._job_or_404(session, job_id)
        if job.source_type != "gp":
            raise HTTPException(422, "tempo detection only applies to Guitar Pro jobs")
        gp_path = Path(str((job.params or {}).get("gp_path", "")))
        src = Path(job.source)
        params = dict(job.params or {})
    if not gp_path.exists():
        raise HTTPException(409, "the Guitar Pro file no longer exists on the work volume")
    if not src.exists():
        raise HTTPException(409, "source audio no longer exists on the work volume")

    from rockforge.application.gp_pipeline import suggest_tempo_scale
    from rockforge.infrastructure.gpimport.parser import inspect_gp
    from rockforge.infrastructure.rhythm.librosa_adapter import detect_tempo_from

    gp_bpm = float(inspect_gp(gp_path).tempo)
    # The factor is applied by the viewer as a RELATIVE stretch of the tail of the
    # already-displayed timeline, so it must be measured against the tempo that
    # timeline currently plays at — not against the GP header tempo. Using the
    # header was wrong twice over: it ignores the song's own tempo changes (a
    # section authored slower than bar 1 got "corrected" by that whole
    # difference), and it ignores the tempo_scale/anchors already applied, so
    # correcting the same passage twice applied the same absolute factor again
    # and compounded into a chart running far too fast.
    reference_bpm = (
        float(payload.chart_bpm) if payload.chart_bpm and payload.chart_bpm > 0 else gp_bpm
    )
    drums = api._drum_stem(params)
    try:
        detected_bpm = detect_tempo_from(drums or src, payload.from_s, reference_bpm)
    except ImportError as exc:
        raise api._ml_extra_missing("beat detection", exc) from exc
    except Exception as exc:
        raise HTTPException(422, f"could not analyse the recording: {exc}") from exc
    return DetectTempoOut(
        gp_bpm=gp_bpm,
        reference_bpm=reference_bpm,
        detected_bpm=detected_bpm,
        suggested_factor=suggest_tempo_scale(reference_bpm, detected_bpm),
        used_drum_stem=drums is not None,
    )


@router.post("/jobs/{job_id}/detect-beat-sync", response_model=DetectBeatSyncOut)
def detect_beat_sync(job_id: str, payload: DetectBeatSyncIn) -> DetectBeatSyncOut:
    """EXPERIMENTAL: where each of the chart's beats sits in the recording, the
    tempo allowed to change slowly (``align_to_recording``). A proposal — the
    viewer turns it into ordinary pending corrections the user hears before
    rebuilding. The full mix is analysed: a separated stem may have been
    trimmed to the song's start, and these times are in the recording's clock."""
    if any(b <= a for a, b in zip(payload.beats, payload.beats[1:], strict=False)):
        raise HTTPException(422, "beats must be in increasing order")
    with api._session_factory() as session:
        job = api._job_or_404(session, job_id)
        if job.source_type != "gp":
            raise HTTPException(422, "automatic sync only applies to Guitar Pro jobs")
        src = Path(job.source)
    if not src.exists():
        raise HTTPException(409, "source audio no longer exists on the work volume")

    from rockforge.infrastructure.rhythm.librosa_adapter import align_to_recording

    try:
        result = align_to_recording(src, list(payload.beats), list(payload.notes))
    except ImportError as exc:
        raise api._ml_extra_missing("automatic sync", exc) from exc
    except Exception as exc:
        raise HTTPException(422, f"could not analyse the recording: {exc}") from exc
    return DetectBeatSyncOut.model_validate(result)


@router.get("/jobs/{job_id}/attack-sources", response_model=AttackSourcesOut)
def attack_sources(job_id: str) -> AttackSourcesOut:
    """The separated instruments the attacks can be measured on."""
    with api._session_factory() as session:
        job = api._job_or_404(session, job_id)
        stems = api._separated_stems(job.id, dict(job.params or {}))
        with_drums = api._separated_stems(job.id, dict(job.params or {}), drums=True)
    return AttackSourcesOut(stems=sorted(stems), level_stems=sorted(with_drums))


@router.post("/jobs/{job_id}/detect-attacks", response_model=DetectAttacksOut)
def detect_attacks(job_id: str, source: str | None = None) -> DetectAttacksOut:
    """Where the recording has attacks (onsets), drawn under the score so a tab
    whose rhythm is wrong shows where it differs from what is heard. ``source``
    names a separated instrument (``/attack-sources``) or ``mix``; without it,
    the separated guitar when there is one — the drums and the voice add attacks
    of their own in the mix — else the mix. The answer says which. Only WHEN
    something is struck, never which notes."""
    with api._session_factory() as session:
        job = api._job_or_404(session, job_id)
        if job.source_type != "gp":
            raise HTTPException(422, "attack detection only applies to Guitar Pro jobs")
        src = Path(job.source)
        stems = api._separated_stems(job.id, dict(job.params or {}))
    name = source if source is not None else ("guitar" if "guitar" in stems else "mix")
    if name != "mix" and name not in stems:
        raise HTTPException(409, i18n.tr(
            "esse instrumento ainda não foi separado (Áudio ▾ → Separar instrumentos)",
            "that instrument has not been separated yet (Audio ▾ → Separate instruments)",
        ))
    stem = stems.get(name)
    if stem is None and not src.exists():
        raise HTTPException(409, "source audio no longer exists on the work volume")

    from rockforge.infrastructure.rhythm.librosa_adapter import detect_attacks as measure

    try:
        result = measure(stem or src, separated=stem is not None)
    except ImportError as exc:
        raise api._ml_extra_missing("attack detection", exc) from exc
    except Exception as exc:
        raise HTTPException(422, f"could not analyse the recording: {exc}") from exc
    return DetectAttacksOut.model_validate({**result, "source": name})


@router.get("/jobs/{job_id}/onset-levels", response_model=OnsetLevelsOut)
def onset_levels(job_id: str, source: str = "mix") -> OnsetLevelsOut:
    """The recording's attack strength over time — the envelope "Ataques da
    gravação" picks its attacks from, every frame kept — for the "Barras de
    áudio" lane over the score. ``source`` is ``mix`` or a separated
    instrument, the drums included: a drum track is the clearest beat there
    is to check bar lines against, though it is no playback source. Nothing is
    stored; the viewer keeps it per version."""
    with api._session_factory() as session:
        job = api._job_or_404(session, job_id)
        if job.source_type != "gp":
            raise HTTPException(422, "the audio bars only apply to Guitar Pro jobs")
        src = Path(job.source)
        stems = api._separated_stems(job.id, dict(job.params or {}), drums=True)
    if source != "mix" and source not in stems:
        raise HTTPException(409, i18n.tr(
            "esse instrumento ainda não foi separado (Áudio ▾ → Separar instrumentos)",
            "that instrument has not been separated yet (Audio ▾ → Separate instruments)",
        ))
    stem = stems.get(source)
    if stem is None and not src.exists():
        raise HTTPException(409, "source audio no longer exists on the work volume")

    from rockforge.infrastructure.rhythm.librosa_adapter import onset_levels as measure

    try:
        result = measure(stem or src, separated=stem is not None)
    except ImportError as exc:
        raise api._ml_extra_missing("the attack bars", exc) from exc
    except Exception as exc:
        raise HTTPException(422, f"could not analyse the recording: {exc}") from exc
    return OnsetLevelsOut.model_validate({**result, "source": source})


@router.post("/jobs/{job_id}/detect-tuning", response_model=DetectTuningOut)
def detect_tuning(job_id: str) -> DetectTuningOut:
    """Estimate the recording's fine-tuning deviation from A440 (librosa) for
    GP jobs. String/drop tuning is taken from the GP file and is NOT detected
    here (no production-grade solution from polyphonic audio — see
    librosa_adapter). This is a proposal: the suggested cent_offset fills the
    "Desvio da afinação" field and is applied by the normal rebuild."""
    with api._session_factory() as session:
        job = api._job_or_404(session, job_id)
        if job.source_type != "gp":
            raise HTTPException(422, "tuning detection only applies to Guitar Pro jobs")
        src = Path(job.source)
    if not src.exists():
        raise HTTPException(409, "source audio no longer exists on the work volume")

    from rockforge.infrastructure.rhythm.librosa_adapter import estimate_tuning_cents

    try:
        cents = estimate_tuning_cents(src)
    except ImportError as exc:
        raise api._ml_extra_missing("tuning detection", exc) from exc
    except Exception as exc:
        raise HTTPException(422, f"could not analyse the recording: {exc}") from exc
    return DetectTuningOut(suggested_cent_offset=cents)
