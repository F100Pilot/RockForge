"""Lyrics: detection and alignment, the online lookup (LRCLIB), parsing an LRC,
the editor's rows and the vocal line the GP lyrics are sung on."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, cast

from fastapi import APIRouter, HTTPException

from rockforge.interfaces.api import app as api
from rockforge.interfaces.api.schemas import (
    DetectLyricsIn,
    JobOut,
    LyricEventOut,
    LyricsCandidateOut,
    LyricsLookupOut,
    LyricsOut,
    LyricsParseIn,
    LyricsParseOut,
    VocalLineOut,
    VocalNoteOut,
)

router = APIRouter()


@router.post("/jobs/{job_id}/detect-lyrics", response_model=JobOut, status_code=202)
def detect_lyrics_endpoint(job_id: str, payload: DetectLyricsIn | None = None) -> JobOut:
    """Kick off asynchronous lyric detection (Demucs vocal isolation + WhisperX
    forced alignment) on the job's source recording. Slow — poll
    GET /jobs/{job_id}/lyrics for the result. Never overwrites a completed
    build's status; progress is tracked via params["lyrics_status"].

    With ``align_lines`` (lyrics found on LRCLIB, or already in the editor) the
    same task ALIGNS those words to the vocals instead of transcribing — the
    text is right by construction, only the timing is measured."""
    with api._session_factory() as session:
        job = api._job_or_404(session, job_id)
        # Detection is source-type-agnostic (operates on job.source, the
        # recording). "gp" is the only type the app creates today; the
        # long-removed "youtube" URL-ingestion type is gone from the set.
        if job.source_type not in {"gp", "upload"}:
            raise HTTPException(422, "lyric detection is not supported for this job's source")
        if not Path(job.source).exists():
            raise HTTPException(409, "source recording no longer exists on the work volume")
        params = dict(job.params or {})
        params["lyrics_status"] = "detecting"
        params.pop("lyrics_align", None)
        lines = [ln for ln in (payload.align_lines if payload else []) if ln.text.strip()]
        if lines:
            from rockforge.infrastructure.lyrics_lookup import guess_language

            assert payload is not None
            params["lyrics_align"] = {
                "lines": [{"time": ln.time, "text": ln.text.strip()} for ln in lines],
                "language": payload.language
                or guess_language(" ".join(ln.text for ln in lines)),
            }
        job.params = params
        session.commit()
        api._enqueue_detect(job)
        return api._to_out(job)


@router.get("/lyrics-lookup", response_model=LyricsLookupOut)
def lyrics_lookup(title: str = "", artist: str = "", duration: float = 0.0) -> LyricsLookupOut:
    """Lyrics candidates from LRCLIB for the user to choose — nothing is written
    until they pick one. ``duration`` (the recording's length) ranks the entry
    of the same edit first. LRCLIB unreachable is a 502. See
    ``infrastructure/lyrics_lookup.py``."""
    from rockforge.infrastructure.album_lookup import primary_artist, search_title
    from rockforge.infrastructure.lyrics_lookup import LyricsLookupError, search_lyrics

    if not title.strip() or not artist.strip():
        raise HTTPException(422, "title and artist are required to look up lyrics")
    try:
        found = search_lyrics(
            title, artist, duration if math.isfinite(duration) and duration > 0 else None
        )
    except LyricsLookupError as exc:
        raise HTTPException(502, str(exc)) from exc
    return LyricsLookupOut(
        candidates=[LyricsCandidateOut(**vars(c)) for c in found],
        searched_title=search_title(title),
        searched_artist=primary_artist(artist),
    )


@router.post("/lyrics/parse", response_model=LyricsParseOut)
def parse_lyrics_text(payload: LyricsParseIn) -> LyricsParseOut:
    """LRC/UltraStar text → the editor's per-word events (with ``offset_s``
    added). The same parser the build uses for an uploaded LRC, so what the
    editor shows is what the build would have made of the file."""
    from rockforge.infrastructure.rsxml.vocals import parse_lyrics

    events = [e for e in parse_lyrics(payload.text, payload.offset_s) if e.time >= 0]
    if not events:
        raise HTTPException(422, "no timed lines in that text (it has no LRC timestamps)")
    return LyricsParseOut(
        events=[LyricEventOut(time=e.time, length=e.length, lyric=e.lyric) for e in events]
    )


# NOTE: these three detection-status polls (/lyrics, /detected-tones, /stems)
# read job.params, which deserializes the whole JSON column. A dedicated
# *_status column was considered (to avoid that on each ~few-second poll) and
# deliberately NOT added: each endpoint also RETURNS payload that lives in
# params (the events + log, the detected-tones blob, the stem names + log), so
# params is loaded regardless — a status column would save nothing here while
# duplicating the status into a second source of truth to keep in sync (exactly
# the params-copy trap documented in CLAUDE.md). Revisit only if a status-ONLY
# poll path is ever added under real Postgres concurrency.
@router.get("/jobs/{job_id}/lyrics", response_model=LyricsOut)
def get_lyrics(job_id: str) -> LyricsOut:
    """Current lyric-detection status and events (raw, before pad_start_s shift
    for GP jobs). Used by the in-app lyrics editor."""
    with api._session_factory() as session:
        job = api._job_or_404(session, job_id)
        params = job.params or {}
        status = str(params.get("lyrics_status", "none"))
        rows = cast("list[dict[str, object]]", params.get("lyrics_events") or [])

        def _num(v: object) -> float:
            return float(v) if isinstance(v, (int, float, str)) else 0.0

        events = [
            LyricEventOut(
                time=_num(r.get("time", 0.0)),
                length=_num(r.get("length", 0.0)),
                lyric=str(r.get("lyric", "")),
            )
            for r in rows
        ]
        # No edited/detected events yet: fall back to lyrics supplied with the
        # job (LRC/UltraStar TXT upload), so the editor and tab view show
        # what will actually be used at build time.
        if not events:
            lrc_text = params.get("lrc_text")
            if isinstance(lrc_text, str) and lrc_text.strip():
                from rockforge.infrastructure.rsxml.vocals import parse_lyrics

                events = [
                    LyricEventOut(time=e.time, length=e.length, lyric=e.lyric)
                    for e in parse_lyrics(lrc_text)
                ]
        log = cast("list[str]", params.get("lyrics_log") or [])
        return LyricsOut(
            status=status, events=events, log=[str(line) for line in log],
            follow_chart=_lyrics_follow_chart(params),
        )


def _lyrics_follow_chart(params: dict[str, Any]) -> bool:
    """Whether the lyric rows are timed on the score (and so must move with its
    sync corrections) rather than to the recording. Set by whoever filled the
    rows; a job from before the flag existed follows the chart when its lyrics
    came from the GP file and not from an LRC or a detection."""
    if "lyrics_follow_chart" in params:
        return bool(params["lyrics_follow_chart"])
    return (
        bool(params.get("gp_has_lyrics"))
        and not params.get("lrc_text")
        and params.get("lyrics_status") != "ready"
    )


@router.get("/jobs/{job_id}/vocal-line", response_model=VocalLineOut)
def get_vocal_line(job_id: str) -> VocalLineOut:
    """The notes of the track the GP lyrics are sung on, in the lyrics' own
    recording clock, as of the last build — played by the viewer as "Voz
    (sintetizada)" to hear where the words should fall. Empty when the file
    names no such track (or the job was never built)."""
    with api._session_factory() as session:
        job = api._job_or_404(session, job_id)
        params = job.params or {}
        rows = cast("list[dict[str, Any]]", params.get("vocal_melody") or [])
        notes = []
        for r in rows:
            try:
                midi = r.get("midi")
                notes.append(VocalNoteOut(
                    time=float(r["time"]), length=float(r["length"]),
                    midi=int(midi) if midi is not None else None,
                ))
            except (KeyError, TypeError, ValueError):
                continue  # a malformed row is skipped, never a 500
        return VocalLineOut(notes=notes, gp_has_lyrics=bool(params.get("gp_has_lyrics")))
