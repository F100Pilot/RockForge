"""Committing the user's corrections: the rebuild (sync, tempo, notes, tones,
lyrics, sections), the sync state's export/import, and the per-chart marks
("sincronizada", the main chart for sync)."""

from __future__ import annotations

import math
import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import cast

from fastapi import APIRouter, HTTPException

from rockforge.infrastructure.db.models import Job
from rockforge.interfaces.api import app as api
from rockforge.interfaces.api.schemas import (
    MAX_CENT_OFFSET,
    JobOut,
    MarkedAttacksIn,
    MarkedAttacksOut,
    RebuildIn,
    SyncConfirmedIn,
    SyncMainIn,
    SyncStateIn,
    SyncStateOut,
)

router = APIRouter()


# Keys that only make sense for a Guitar Pro job (dropped when importing into a
# non-GP job, mirroring rebuild's per-field 422s).
_SYNC_STATE_GP_ONLY: frozenset[str] = frozenset({
    "tuning_overrides",
    "lead_track", "rhythm_track", "combo_track", "alt_lead_track", "alt_rhythm_track",
    "bass_track", "merge_tracks",
})


def _tuning_strings(kind: object) -> int:
    """How many MIDI pitches a chart's tuning override carries (a bass has 4)."""
    return 4 if kind == "Bass" else 6


def _sanitize_sync_state(incoming: dict[str, object]) -> dict[str, object]:
    """Keep only whitelisted keys and validate the shapes that would 422 on a
    rebuild, so a hand-edited or foreign JSON can never corrupt a job."""
    out = {k: incoming[k] for k in api._SYNC_STATE_KEYS if k in incoming}
    cents = out.get("cent_offset")
    if cents is not None and (
        not isinstance(cents, (int, float)) or isinstance(cents, bool)
        or not abs(cents) <= MAX_CENT_OFFSET
    ):
        bound = f"{MAX_CENT_OFFSET:g}"
        raise HTTPException(422, f"cent_offset must be a number between -{bound} and {bound}")
    if "merge_tracks" in out:
        out["merge_tracks"] = api._clean_merge_tracks(out["merge_tracks"])
    to = out.get("tuning_overrides")
    if to is not None:
        if not isinstance(to, dict):
            raise HTTPException(422, "tuning_overrides must be an object keyed by arrangement")
        for kind, midi in to.items():
            n = _tuning_strings(kind)
            if not isinstance(midi, list) or len(midi) != n:
                raise HTTPException(422, f"tuning for {kind} must have {n} MIDI pitches")
            api._reject_bad_midi(f"tuning for {kind}", midi)
    # This path takes a raw JSON blob, so none of the ``Finite`` models apply:
    # a hand-edited or foreign file could otherwise restore a NaN offset/tempo
    # or a NaN drift anchor straight into the job's params.
    api._reject_non_finite(
        **{
            k: float(v)
            for k in ("offset_s", "lead_in_s", "tempo_scale", "cent_offset")
            if isinstance(v := out.get(k), (int, float))
        }
    )
    for key in ("sync_anchor_stages", "arrangement_sync"):
        for value in _iter_floats(out.get(key)):
            if not math.isfinite(value):
                raise HTTPException(422, f"{key} contains a non-finite time")
    api._check_imported_params(out)
    return out


def _iter_floats(value: object) -> Iterator[float]:
    """Every number nested anywhere inside a decoded-JSON structure."""
    if isinstance(value, bool):
        return
    if isinstance(value, (int, float)):
        yield float(value)
    elif isinstance(value, dict):
        for v in value.values():
            yield from _iter_floats(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            yield from _iter_floats(v)


@router.post("/jobs/{job_id}/rebuild", response_model=JobOut, status_code=202)
def rebuild_job(job_id: str, payload: RebuildIn) -> JobOut:
    """Re-run the pipeline on the same source with human-confirmed overrides."""
    with api._session_factory() as session:
        original = api._job_or_404(session, job_id)
        if original.source_type in {"upload", "gp"} and not Path(original.source).exists():
            raise HTTPException(409, "original upload no longer exists on the work volume")
        from rockforge.application.gp_pipeline import MIN_OFFSET_S

        params: dict[str, object] = dict(original.params or {})
        # Snapshot the PRE-EDIT timeline parameters before anything below mutates
        # them (dict() is shallow, so nested entries are shared). They are needed
        # to conjugate already-committed anchor stages — see _remap_committed_anchors.
        _old_scale = float(cast(float, params.get("tempo_scale", 1.0) or 1.0))
        _old_shift = api._score_shift(params)
        _old_arr_scales: dict[str, float] = {
            k: float(cast(float, (v or {}).get("tempo_scale", _old_scale) or _old_scale))
            for k, v in cast(
                "dict[str, dict[str, object]]", params.get("arrangement_sync", {}) or {}
            ).items()
        }
        if payload.cent_offset is not None:
            params["cent_offset"] = payload.cent_offset
        if payload.offset_s is not None:
            if payload.offset_s < MIN_OFFSET_S:
                raise HTTPException(422, f"offset_s must be >= {MIN_OFFSET_S:g}")
            params["offset_s"] = payload.offset_s
        if payload.lead_in_s is not None:
            if payload.lead_in_s < 0.0:
                raise HTTPException(422, "lead_in_s must be >= 0")
            params["lead_in_s"] = payload.lead_in_s
        if payload.arrangement is not None and original.source_type != "gp":
            raise HTTPException(422, "arrangement scoping only applies to Guitar Pro jobs")

        _TRACK_SLOTS = {
            "lead": "lead_track", "rhythm": "rhythm_track", "combo": "combo_track",
            "alt_lead": "alt_lead_track", "alt_rhythm": "alt_rhythm_track",
            "bass": "bass_track",
        }
        if payload.tracks is not None:
            if original.source_type != "gp":
                raise HTTPException(422, "track assignment only applies to Guitar Pro jobs")
            unknown = set(payload.tracks) - set(_TRACK_SLOTS)
            if unknown:
                raise HTTPException(422, f"unknown arrangement slot(s): {sorted(unknown)}")
            chosen = [v for v in payload.tracks.values() if v is not None]
            if len(chosen) != len(set(chosen)):
                raise HTTPException(422, "each arrangement must use a different GP track")
            for slot, key in _TRACK_SLOTS.items():  # replace the whole assignment
                idx = payload.tracks.get(slot)
                if idx is None:
                    params.pop(key, None)
                else:
                    params[key] = int(idx)
        if payload.merge_tracks is not None:
            if original.source_type != "gp":
                raise HTTPException(422, "merging tracks only applies to Guitar Pro jobs")
            merge = api._clean_merge_tracks(payload.merge_tracks)
            if merge:
                params["merge_tracks"] = merge
            else:
                params.pop("merge_tracks", None)
        if payload.tuning_overrides is not None:
            if original.source_type != "gp":
                raise HTTPException(422, "tuning overrides only apply to Guitar Pro jobs")
            for kind, midi in payload.tuning_overrides.items():
                n = _tuning_strings(kind)
                if len(midi) != n:
                    raise HTTPException(422, f"tuning for {kind} must have {n} MIDI pitches")
            params["tuning_overrides"] = {k: list(v) for k, v in payload.tuning_overrides.items()}

        def _arr_entry(kind: str) -> dict[str, object]:
            # Per-arrangement tempo/drift overrides live under params["arrangement_sync"].
            # Seed a new entry from the job-level defaults so corrections already
            # applied to every arrangement are inherited (not dropped) the first
            # time this arrangement is edited on its own.
            store = cast(
                "dict[str, dict[str, object]]", params.setdefault("arrangement_sync", {})
            )
            if kind not in store:
                store[kind] = {
                    "tempo_scale": params.get("tempo_scale", 1.0),
                    "sync_anchor_stages": [
                        list(s)
                        for s in cast(
                            "list[list[object]]", params.get("sync_anchor_stages", [])
                        )
                    ],
                }
            return store[kind]

        def _sync_targets() -> list[dict[str, object]]:
            """Return the target dicts that tempo_scale/sync_anchors should be
            written to.  When ``apply_to_all`` is set (with ``arrangement``),
            the change propagates to every existing per-arrangement override
            *and* the job-level defaults, so both current and future
            arrangements share the same correction."""
            if payload.apply_to_all and payload.arrangement is not None:
                targets: list[dict[str, object]] = [params]
                store = cast(
                    "dict[str, dict[str, object]]",
                    params.get("arrangement_sync", {}),
                )
                for entry in store.values():
                    targets.append(entry)
                return targets
            if payload.arrangement is not None:
                return [_arr_entry(payload.arrangement)]
            return [params]

        if payload.tempo_scale is not None:
            if original.source_type != "gp":
                raise HTTPException(422, "tempo_scale only applies to Guitar Pro jobs")
            if payload.tempo_scale <= 0.0:
                raise HTTPException(422, "tempo_scale must be > 0")
            for target in _sync_targets():
                target["tempo_scale"] = payload.tempo_scale

        other_sync = (
            {}
            if original.source_type != "gp" or payload.apply_to_all or payload.arrangement is None
            else {k: v for k, v in (payload.other_sync or {}).items() if k != payload.arrangement}
        )
        for kind, pending in other_sync.items():
            if pending.tempo_scale is not None:
                if pending.tempo_scale <= 0.0:
                    raise HTTPException(422, "tempo_scale must be > 0")
                _arr_entry(kind)["tempo_scale"] = pending.tempo_scale

        def _remap_committed_anchors() -> None:
            """Re-express already-committed anchor stages in the NEW timeline.

            The build applies ``W(x·s + S)`` — parse at tempo_scale ``s`` with
            score shift ``S``, THEN warp — while the tab viewer previews
            ``R(W(x·s_built + S_built))``: it rescales the ALREADY-WARPED times it
            read back from the built XML. Function composition does not commute
            (``R∘W ≠ W∘R``), so as soon as ONE anchor stage is committed, changing
            the tempo or the offset makes the rebuild differ from the preview by
            ``d·(r−1)`` on EVERY note (``d`` = net shift the committed anchors
            introduce, ``r`` = the tempo ratio) — a CONSTANT desync, invisible in
            the viewer (which never re-derives the raw GP times) but plainly
            audible in game. That is the "no programa está sincronizado, no
            Rocksmith não" bug.

            Mapping every stored anchor pair through the viewer's own map
            ``φ(t) = (t − S_old)·r + S_new`` makes each stage ``W' = φ∘W∘φ⁻¹``,
            hence ``W'∘φ = φ∘W`` exactly — the rebuild then reproduces the
            preview. Each arrangement is conjugated with ITS OWN tempo ratio
            (tempo_scale is per-arrangement) but the shared job-level shift.
            """
            new_scale = float(cast(float, params.get("tempo_scale", 1.0) or 1.0))
            new_shift = api._score_shift(params)
            store = cast(
                "dict[str, dict[str, object]]", params.get("arrangement_sync", {}) or {}
            )
            targets: list[tuple[dict[str, object], float, float]] = [
                (params, _old_scale, new_scale)
            ]
            for kind, entry in store.items():
                targets.append((
                    entry,
                    _old_arr_scales.get(kind, _old_scale),
                    float(cast(float, entry.get("tempo_scale", new_scale) or new_scale)),
                ))
            for target, s_old, s_new in targets:
                stages = cast(
                    "list[list[list[float]]]", target.get("sync_anchor_stages") or []
                )
                if not stages or s_old <= 0.0:
                    continue
                ratio = s_new / s_old
                if abs(ratio - 1.0) < 1e-12 and abs(new_shift - _old_shift) < 1e-12:
                    continue  # timeline unchanged for this arrangement
                target["sync_anchor_stages"] = [
                    [
                        [
                            (float(a) - _old_shift) * ratio + new_shift,
                            (float(b) - _old_shift) * ratio + new_shift,
                        ]
                        for a, b in stage
                    ]
                    for stage in stages
                ]

        if original.source_type == "gp":
            _remap_committed_anchors()
        if payload.sync_anchors is not None:
            if original.source_type != "gp":
                raise HTTPException(422, "sync_anchors only apply to Guitar Pro jobs")
            if payload.sync_anchors:
                for target in _sync_targets():
                    stages = [
                        list(s)
                        for s in cast(
                            "list[list[object]]", target.get("sync_anchor_stages", [])
                        )
                    ]
                    stages.append([list(a) for a in payload.sync_anchors])
                    target["sync_anchor_stages"] = stages
        for kind, pending in other_sync.items():
            if pending.sync_anchors:
                entry = _arr_entry(kind)
                done = cast("list[list[object]]", entry.get("sync_anchor_stages", []))
                entry["sync_anchor_stages"] = [
                    *[list(s) for s in done], [list(a) for a in pending.sync_anchors],
                ]
        if payload.import_mutes is not None:
            params["import_mute_techniques"] = payload.import_mutes
        if payload.dynamic_difficulty is not None:
            params["dynamic_difficulty"] = payload.dynamic_difficulty
        if payload.lyrics_events is not None:
            params["lyrics_events"] = [e.model_dump() for e in payload.lyrics_events]
            params.pop("lyrics_status", None)
        if payload.lyrics_follow_chart is not None:
            params["lyrics_follow_chart"] = payload.lyrics_follow_chart
        touches_tones = any(
            v is not None
            for v in (
                payload.tones,
                payload.tone_changes,
                payload.tone_base,
                payload.tone_names,
                payload.arrangement_tones,
            )
        )
        if touches_tones and original.source_type != "gp":
            raise HTTPException(422, "tones only apply to Guitar Pro jobs")
        if payload.tone_base is not None:
            params["tone_base"] = payload.tone_base or None
        if payload.tone_names is not None:
            if len(payload.tone_names) > 4:
                raise HTTPException(422, "Rocksmith supports at most 4 switchable tones")
            params["tone_names"] = payload.tone_names
        if payload.tones is not None:
            api._check_tones(payload.tones)
            params["tones"] = payload.tones
        if payload.tone_changes is not None:
            params["tone_changes"] = [c.model_dump() for c in payload.tone_changes]
        if payload.arrangement_tones is not None:
            params["arrangement_tones"] = {
                kind: t.model_dump() for kind, t in payload.arrangement_tones.items()
            }
        if payload.section_overrides is not None:
            params["section_overrides"] = [s.model_dump() for s in payload.section_overrides]
        if payload.note_overrides is not None:
            params["note_overrides"] = {
                kind: [n.model_dump() for n in notes]
                for kind, notes in payload.note_overrides.items()
            }
        if payload.hand_positions is not None:
            params["hand_positions"] = {
                kind: [h.model_dump() for h in sorted(rows, key=lambda h: h.time)]
                for kind, rows in payload.hand_positions.items()
                if rows
            }
        params["rebuilt_from"] = original.id
        job = Job(
            source=original.source,
            source_type=original.source_type,
            title=original.title,
            artist=original.artist,
            album=original.album,
            year=original.year,
            params=params,
        )
        session.add(job)
        session.commit()

        # Rebuild creates a fresh work directory (job.id != original.id); the
        # cover image referenced by params["cover_art"] lives under the
        # original job's directory, so copy it across or the worker's
        # candidate.exists() check (celery_app.generate_cdlc) silently finds
        # nothing and the bundle ends up without album art.
        cover_art_name = params.get("cover_art")
        if cover_art_name:
            src = api.settings.work_dir / original.id / cast(str, cover_art_name)
            if src.exists():
                dest_dir = api.settings.work_dir / job.id
                dest_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest_dir / cast(str, cover_art_name))

        api._enqueue(job)
        return api._to_out(job)


@router.get("/jobs/{job_id}/sync-state", response_model=SyncStateOut)
def get_sync_state(job_id: str) -> SyncStateOut:
    """Export a job's hand-tuned sync (anchors/tempo/offset/tuning/lyrics/tracks)
    as a portable JSON blob, so it can be re-imported into another job for the
    same song instead of redoing every manual correction."""
    with api._session_factory() as session:
        job = api._job_or_404(session, job_id)
        song = " - ".join(p for p in (job.artist, job.title) if p)
        return SyncStateOut(
            version=1, song=song, sync=api._extract_sync_state(dict(job.params or {}))
        )


@router.post("/jobs/{job_id}/import-sync", response_model=JobOut, status_code=202)
def import_sync_state(job_id: str, payload: SyncStateIn) -> JobOut:
    """Apply a previously-exported sync state to this job and rebuild (fork),
    so hand-tuned drift/tempo/offset/lyrics/tracks survive re-creating a job."""
    clean = _sanitize_sync_state(payload.sync)
    with api._session_factory() as session:
        original = api._job_or_404(session, job_id)
        if original.source_type in {"upload", "gp"} and not Path(original.source).exists():
            raise HTTPException(409, "original upload no longer exists on the work volume")
        if original.source_type != "gp":
            for k in _SYNC_STATE_GP_ONLY:  # track/tuning-override keys need a GP file
                clean.pop(k, None)
        params: dict[str, object] = dict(original.params or {})
        params.update(clean)
        if "lyrics_events" in clean:
            # Let the next build use the imported lyrics (see rebuild_job).
            params.pop("lyrics_status", None)
        params["rebuilt_from"] = original.id
        job = Job(
            source=original.source, source_type=original.source_type,
            title=original.title, artist=original.artist, album=original.album,
            year=original.year, params=params,
        )
        session.add(job)
        session.commit()

        cover_art_name = params.get("cover_art")
        if cover_art_name:
            src = api.settings.work_dir / original.id / cast(str, cover_art_name)
            if src.exists():
                dest_dir = api.settings.work_dir / job.id
                dest_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest_dir / cast(str, cover_art_name))

        api._enqueue(job)
        return api._to_out(job)


@router.patch("/jobs/{job_id}/sync-confirmed", response_model=JobOut)
def set_sync_confirmed(job_id: str, payload: SyncConfirmedIn) -> JobOut:
    """Record that the user checked the chart against the recording.

    Only the checklist reads it — nothing in the bundle changes, so there is no
    rebuild. It lives in `params`, so a rebuild/reload fork inherits it.
    """
    with api._session_factory() as session:
        job = api._job_or_404(session, job_id)
        params = dict(job.params or {})
        built = api._built_kinds(job.bundle_dir)
        if payload.arrangement is None:
            synced = built if payload.confirmed else []
        else:
            if built and payload.arrangement not in built:
                raise HTTPException(422, f"no built arrangement named {payload.arrangement!r}")
            synced = [
                k for k in api._synced_arrangements(params, job.bundle_dir)
                if k != payload.arrangement
            ]
            if payload.confirmed:
                synced.append(payload.arrangement)
        params["synced_arrangements"] = synced
        # The song is confirmed once every chart is — that is what the card and
        # the checklist mean by it; marking one track does not speak for others.
        params["sync_confirmed"] = (
            payload.confirmed if payload.arrangement is None
            else bool(built) and all(k in synced for k in built)
        )
        job.params = params
        session.commit()
        return api._to_out(job)


@router.put("/jobs/{job_id}/marked-attacks", response_model=MarkedAttacksOut)
def set_marked_attacks(job_id: str, payload: MarkedAttacksIn) -> MarkedAttacksOut:
    """Store one chart's attacks marked by ear ("Marcar a ouvir" → Ataques):
    seconds of the recording, sorted, to the millisecond, a double tap (under
    1 ms apart) kept once. Nothing is rebuilt — they change no note; they live
    in `params`, so a fork inherits them. An empty list removes the chart's."""
    times: list[float] = []
    for t in sorted(round(float(t), 3) for t in payload.times):
        if not times or t - times[-1] >= 0.001:
            times.append(t)
    with api._session_factory() as session:
        job = api._job_or_404(session, job_id)
        built = api._built_kinds(job.bundle_dir)
        if built and payload.arrangement not in built:
            raise HTTPException(422, f"no built arrangement named {payload.arrangement!r}")
        params = dict(job.params or {})
        raw = params.get("marked_attacks")
        marked: dict[str, object] = dict(raw) if isinstance(raw, dict) else {}
        if times:
            marked[payload.arrangement] = times
        else:
            marked.pop(payload.arrangement, None)
        if marked:
            params["marked_attacks"] = marked
        else:
            params.pop("marked_attacks", None)
        job.params = params
        session.commit()
    return MarkedAttacksOut(arrangement=payload.arrangement, times=times)


@router.patch("/jobs/{job_id}/sync-main", response_model=JobOut)
def set_sync_main(job_id: str, payload: SyncMainIn) -> JobOut:
    """Choose the chart whose sync corrections the viewer carries onto the
    others ("Pista principal"). Nothing is rebuilt; it lives in `params`, so a
    fork inherits it."""
    with api._session_factory() as session:
        job = api._job_or_404(session, job_id)
        built = api._built_kinds(job.bundle_dir)
        if payload.arrangement is not None and built and payload.arrangement not in built:
            raise HTTPException(422, f"no built arrangement named {payload.arrangement!r}")
        params = dict(job.params or {})
        if payload.arrangement:
            params["sync_main"] = payload.arrangement
        else:
            params.pop("sync_main", None)
        job.params = params
        session.commit()
        return api._to_out(job)
