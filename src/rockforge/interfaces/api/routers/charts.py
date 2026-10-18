"""The built charts as the viewer reads them: the GP file's tracks and every
arrangement's notes, bars, beats, sections, tuning and pending-edit state."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import ValidationError

from rockforge.domain.chords import name_chord
from rockforge.domain.music import BASS_STANDARD_MIDI, STANDARD_E_MIDI
from rockforge.infrastructure.db.models import Job, JobStatus
from rockforge.interfaces.api import app as api
from rockforge.interfaces.api.schemas import (
    ArpeggioOut,
    ArrangementNoteOut,
    ArrangementOut,
    BarOut,
    HandPositionOut,
    NoteOverrideIn,
    SectionOut,
)

router = APIRouter()


@router.get("/jobs/{job_id}/gp-tracks")
def get_gp_tracks(job_id: str) -> dict[str, object]:
    """The GP file's tracks plus the current track→arrangement assignment and
    per-arrangement tuning, so the song settings can re-map them post-creation."""
    from rockforge.infrastructure.gpimport.parser import inspect_gp

    with api._session_factory() as session:
        job = api._job_or_404(session, job_id)
        if job.source_type != "gp":
            raise HTTPException(422, "not a Guitar Pro job")
        params = dict(job.params or {})
    gp_path = Path(str(params.get("gp_path", "")))
    if not gp_path.exists():
        raise HTTPException(409, "the Guitar Pro file is no longer on the work volume")
    info = inspect_gp(gp_path)
    return {
        "tracks": [
            {"index": t.index, "name": t.name, "string_count": t.string_count,
             "is_percussion": t.is_percussion, "tuning_midi": list(t.tuning_midi)}
            for t in info.tracks
        ],
        "assignment": {
            "lead": params.get("lead_track"), "rhythm": params.get("rhythm_track"),
            "combo": params.get("combo_track"), "alt_lead": params.get("alt_lead_track"),
            "alt_rhythm": params.get("alt_rhythm_track"), "bass": params.get("bass_track"),
        },
        "tuning_overrides": params.get("tuning_overrides") or {},
        "merge_tracks": params.get("merge_tracks") or {},
    }


# The GP track each arrangement is built from, as /jobs/gp stores the choice.
_TRACK_PARAM_OF_KIND = {
    "Lead": "lead_track",
    "Rhythm": "rhythm_track",
    "Combined": "combo_track",
    "Alternate Lead": "alt_lead_track",
    "Alternate Rhythm": "alt_rhythm_track",
    "Bass": "bass_track",
}


def _track_of_kind(params: dict[str, object], kind: str) -> int | None:
    """The GP track arrangement ``kind`` was built from, as ``gp_pipeline`` assigns
    them: a lone Lead (no other guitar chart; a Bass does not count) is built as
    Combined. None when the tracks were auto-picked."""
    assigned = {
        k: v for k, p in _TRACK_PARAM_OF_KIND.items()
        if isinstance(v := params.get(p), int) and not isinstance(v, bool)
    }
    if kind == "Combined" and [k for k in assigned if k != "Bass"] == ["Lead"]:
        return assigned["Lead"]
    return assigned.get(kind)


@router.get("/jobs/{job_id}/arrangements", response_model=list[ArrangementOut])
def get_arrangements(job_id: str) -> list[ArrangementOut]:
    """Parsed arrangement data for human review (tab viewer, tuning confirmation)."""
    import xml.etree.ElementTree as ET

    with api._session_factory() as session:
        job = session.get(Job, job_id)
        if job is None or job.status is not JobStatus.COMPLETED or not job.bundle_dir:
            raise HTTPException(404, "arrangements not available")
        job_params = dict(job.params or {})

    # Per-arrangement tempo scale, falling back to the job-level default.
    raw_default_scale = job_params.get("tempo_scale", 1.0) or 1.0
    default_scale = (
        float(raw_default_scale) if isinstance(raw_default_scale, (int, float, str)) else 1.0
    )
    arr_sync = job_params.get("arrangement_sync") or {}

    raw_hand_ov = job_params.get("hand_positions")
    hand_ov = raw_hand_ov if isinstance(raw_hand_ov, dict) else {}
    raw_note_ov = job_params.get("note_overrides")
    note_ov = raw_note_ov if isinstance(raw_note_ov, dict) else {}

    def committed_note_overrides(kind: str) -> list[NoteOverrideIn]:
        rows = note_ov.get(kind)
        if not isinstance(rows, list):
            return []
        out_rows: list[NoteOverrideIn] = []
        for row in rows:
            if isinstance(row, dict):
                try:
                    out_rows.append(NoteOverrideIn(**row))
                except ValidationError:  # a hand-edited params row; skip it
                    continue
        return out_rows

    def scale_for(kind: str) -> float:
        entry = arr_sync.get(kind) if isinstance(arr_sync, dict) else None
        if isinstance(entry, dict):
            return float(entry.get("tempo_scale", default_scale) or default_scale)
        return default_scale

    raw_estimated = job_params.get("estimated_bars")
    estimated = raw_estimated if isinstance(raw_estimated, dict) else {}

    def estimated_bars_for(kind: str) -> list[int]:
        track = _track_of_kind(job_params, kind)
        bars = estimated.get(str(track)) if track is not None else None
        return [b for b in bars if isinstance(b, int)] if isinstance(bars, list) else []

    synced_kinds = api._synced_arrangements(job_params, job.bundle_dir)
    out: list[ArrangementOut] = []
    for xml_path in sorted(Path(job.bundle_dir).glob("arrangement_*.xml")):
        root = ET.parse(xml_path).getroot()
        if root.tag != "song":
            continue  # skip the vocals XML (root <vocals>) — not an instrument tab
        tuning_el = root.find("tuning")
        offsets = (
            [int(tuning_el.get(f"string{i}", "0")) for i in range(6)]
            if tuning_el is not None
            else [0] * 6
        )
        props = root.find("arrangementProperties")
        is_bass = props is not None and props.get("pathBass") == "1"
        open_midi = BASS_STANDARD_MIDI if is_bass else STANDARD_E_MIDI

        def parse_note(el: ET.Element, chord: bool) -> ArrangementNoteOut:
            techs = [
                t for t in (
                    "hammerOn", "pullOff", "harmonic", "palmMute", "vibrato",
                    "tap", "slap", "pluck", "accent",
                )
                if el.get(t) == "1"
            ]
            bend = el.get("bend", "0")
            try:
                bend_semitones = int(round(float(bend)))
            except ValueError:
                bend_semitones = 0
            if bend_semitones:
                techs.append("bend")
            if el.get("slideTo", "-1") != "-1":
                techs.append("slide")
            slide_to = int(el.get("slideTo", "-1"))
            if slide_to < 0:
                slide_to = int(el.get("slideUnpitchTo", "-1"))
            return ArrangementNoteOut(
                time=float(el.get("time", "0")),
                string=int(el.get("string", "0")),
                fret=int(el.get("fret", "0")),
                sustain=float(el.get("sustain", "0")),
                chord=chord,
                techniques=techs,
                bend_semitones=bend_semitones,
                slide_to=slide_to,
                link_next=el.get("linkNext") == "1",
            )

        notes = [parse_note(el, False) for el in root.findall("levels/level/notes/note")]
        # Chords: name each from the pitches its chordNotes actually sound
        # (RockForge stores no authored chord name). pitch = standard open-string
        # MIDI + this arrangement's tuning offset + fret.
        chord_notes: list[ArrangementNoteOut] = []
        for chord_el in root.findall("levels/level/chords/chord"):
            members = [parse_note(el, True) for el in chord_el.findall("chordNote")]
            pitches = [open_midi[m.string] + offsets[m.string] + m.fret for m in members]
            cname = name_chord(pitches)
            for m in members:
                m.chord_name = cname
            chord_notes.extend(members)
        all_notes = sorted(notes + chord_notes, key=lambda n: (n.time, n.string))
        kind = api._built_arrangement_kind(xml_path, root)
        # Bar downbeats for the viewer's measure numbering: ebeats with a real
        # measure number (>0); off-beats carry measure="-1".
        ebeats = root.findall("ebeats/ebeat")
        bars = [
            BarOut(measure=int(eb.get("measure", "-1")), time=float(eb.get("time", "0")))
            for eb in ebeats
            if int(eb.get("measure", "-1")) > 0
        ]
        if bars and ebeats and int(ebeats[-1].get("measure", "-1")) > 0:
            # The grid ends on the song's closing bar line (``close_beat_grid``):
            # the end of the last bar, not a bar of its own to number or align.
            bars.pop()
        # Every beat (downbeats + off-beats) — the snap grid the tab viewer's
        # note drag quantizes to.
        beats = [float(eb.get("time", "0")) for eb in ebeats]
        # Song-structure markers, for the section editor — the writer always
        # appends a synthetic "noguitar" sentinel at the very end (to mark
        # where the phrase timeline ends); that one is a structural closer,
        # not a user-facing section, so it's excluded here.
        sections = [
            SectionOut(
                time=float(el.get("startTime", "0")),
                name=el.get("name", "?"),
                number=int(el.get("number", "1")),
            )
            for el in root.findall("sections/section")
            if el.get("name") != "noguitar"
        ]
        # Arpeggios: the hand shapes over an "-arp" chord template.
        templates = root.findall("chordTemplates/chordTemplate")
        arpeggios = [
            ArpeggioOut(start=float(hs.get("startTime", "0")), end=float(hs.get("endTime", "0")),
                        name=templates[cid].get("chordName", "") or "")
            for hs in root.findall("levels/level/handShapes/handShape")
            if 0 <= (cid := int(hs.get("chordId", "-1"))) < len(templates)
            and (templates[cid].get("displayName", "") or "").endswith("-arp")
        ]
        out.append(
            ArrangementOut(
                kind=kind,
                tuning_offsets=offsets,
                string_count=4 if is_bass else 6,
                capo=int(root.findtext("capo", "0") or 0),
                cent_offset=float(root.findtext("centOffset", "0")),
                average_bpm=float(root.findtext("averageTempo", "0")),
                tempo_scale=scale_for(kind),
                note_count=len(notes),
                chord_count=len(root.findall("levels/level/chords/chord")),
                notes=all_notes,
                bars=bars,
                beats=beats,
                sections=sections,
                note_overrides=committed_note_overrides(kind),
                hand_positions=[
                    HandPositionOut(
                        time=float(a.get("time", "0")), fret=int(a.get("fret", "1")),
                        width=round(float(a.get("width", "4"))),
                    )
                    for a in root.findall("levels/level/anchors/anchor")
                ],
                hand_positions_edited=bool(hand_ov.get(kind)),
                sync_confirmed=kind in synced_kinds,
                estimated_bars=estimated_bars_for(kind),
                arpeggios=arpeggios,
            )
        )
    # The build's own order (Lead, Rhythm, Combined, the alternates), not the
    # file names' alphabetical one, which put the alternates first.
    out.sort(key=lambda a: api._build_order(a.kind))
    # What the game calls each chart ("LEAD 1", "LEAD 2", "RHYTHM") — the same
    # numbering the PSARC's SongPartition carries, so the tabs read as in game.
    from rockforge.domain.arrangement import ArrangementKind, game_names

    known = [a for a in out if a.kind in {k.value for k in ArrangementKind}]
    for a, name in zip(known, game_names([ArrangementKind(a.kind) for a in known]), strict=True):
        a.game_name = name
    return out
