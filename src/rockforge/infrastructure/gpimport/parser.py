"""Guitar Pro (GP3/GP4/GP5) import via PyGuitarPro (LGPL-3.0, used as a library).

This is the high-fidelity alternative to the audio-ML path: notes, strings,
frets, techniques, tempo, sections and lyrics come EXACTLY from the authored
file — no transcription uncertainty.

Honest limitation: PyGuitarPro does not read GPX/GP6/GP7 containers. Uploading
a .gpx raises a clear error telling the user to export as GP5 (Guitar Pro and
TuxGuitar can both do this). No silent fallback.

Verified library facts (inspected in pyguitarpro 0.11 source):
- string numbering: 1 = highest-pitched; RockForge uses 0 = lowest → reversed;
- ticks: quarter note = 960 (`Duration.quarterTime`); measure 1 starts at 960;
- bend points: value unit = half-semitone (file value / 25, semitoneLength=1).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from rockforge.domain.errors import IngestionError
from rockforge.domain.music import (
    Beat,
    BendPoint,
    TabNote,
    Technique,
    TempoMap,
    Tuning,
    apply_sustain_gap,
    expand_slide_ins,
    expand_trills,
    is_composite_bend,
)

QUARTER_TICKS = 960


@dataclass(frozen=True)
class GpTrackInfo:
    index: int
    name: str
    is_percussion: bool
    string_count: int
    tuning_midi: tuple[int, ...]  # low to high


@dataclass(frozen=True)
class GpSongInfo:
    title: str
    artist: str
    album: str
    tempo: int
    tracks: tuple[GpTrackInfo, ...]
    has_lyrics: bool


@dataclass(frozen=True)
class GpLyricLine:
    time: float
    text: str


@dataclass(frozen=True)
class GpSection:
    name: str
    start_time: float


@dataclass(frozen=True)
class ParsedGpTrack:
    notes: list[TabNote]
    tuning: Tuning
    tempo_map: TempoMap
    sections: list[GpSection]
    lyrics: list[GpLyricLine] = field(default_factory=list)
    # Non-fatal notices from parsing (e.g. notes dropped for being off the
    # 24-fret neck) — surfaced to the user instead of silently swallowed.
    warnings: list[str] = field(default_factory=list)


def _load(path: Path) -> Any:  # guitarpro.models.Song (untyped library)
    try:
        import guitarpro
    except ImportError as exc:
        raise IngestionError("pyguitarpro is not installed") from exc
    # GP7/GP8 (.gp, ZIP+score.gpif) is handled natively by gpif_parser, dispatched
    # in inspect_gp/parse_gp_track before _load is reached. A .gp that is NOT a
    # GPIF zip, or a .gpx (GP6 binary container), is genuinely unsupported here.
    if path.suffix.lower() in {".gpx", ".gp"}:
        raise IngestionError(
            "GP6 (.gpx) is not supported. Export the file as GP5 or GP7 (.gp) in "
            "Guitar Pro or TuxGuitar."
        )
    try:
        return guitarpro.parse(str(path))
    except Exception as exc:
        raise IngestionError(f"could not parse Guitar Pro file: {exc}") from exc


def _track_info(index: int, track: Any) -> GpTrackInfo:
    tuning = tuple(s.value for s in sorted(track.strings, key=lambda s: -s.number))
    return GpTrackInfo(
        index=index,
        name=track.name,
        is_percussion=bool(track.isPercussionTrack),
        string_count=len(track.strings),
        tuning_midi=tuning,
    )


def inspect_gp(path: Path) -> GpSongInfo:
    from rockforge.infrastructure.gpimport.gpif_parser import _is_gpif, inspect_gpif

    if _is_gpif(path):
        return inspect_gpif(path)
    song = _load(path)
    return GpSongInfo(
        title=song.title or "",
        artist=song.artist or "",
        album=song.album or "",
        tempo=int(song.tempo),
        tracks=tuple(_track_info(i, t) for i, t in enumerate(song.tracks)),
        has_lyrics=any(line.lyrics.strip() for line in song.lyrics.lines),
    )


def _tempo_events(track: Any) -> list[tuple[int, float]]:
    """(tick, bpm) change points, starting with the song tempo at tick 0.

    Tempo changes are GLOBAL, but GP5 stores each as a per-beat mixTableChange on
    whatever track it was authored on — frequently NOT the instrument track we
    parse (a dedicated tempo track, or another instrument). So scan ALL tracks,
    not just this one, or a mid-song tempo change authored elsewhere is silently
    lost and the beat grid stays stuck at the initial tempo (guarded by
    test_tempo_change_on_other_track_is_detected).
    """
    events: dict[int, float] = {0: float(track.song.tempo)}
    for tr in track.song.tracks:
        for measure in tr.measures:
            for voice in measure.voices:
                tick = measure.start
                for beat in voice.beats:
                    mtc = beat.effect.mixTableChange
                    if mtc is not None and mtc.tempo is not None:
                        events[tick] = float(mtc.tempo.value)
                    tick += beat.duration.time
    return sorted(events.items())


def _make_ticks_to_seconds(events: list[tuple[int, float]]) -> Callable[[int], float]:
    segments: list[tuple[int, float, float]] = []  # (tick, seconds_at_tick, bpm)
    seconds = 0.0
    for i, (tick, bpm) in enumerate(events):
        if i > 0:
            prev_tick, prev_bpm = events[i - 1]
            seconds += (tick - prev_tick) / QUARTER_TICKS * 60.0 / prev_bpm
        segments.append((tick, seconds, bpm))

    def convert(tick: int) -> float:
        seg = segments[0]
        for s in segments:
            if s[0] <= tick:
                seg = s
            else:
                break
        return seg[1] + (tick - seg[0]) / QUARTER_TICKS * 60.0 / seg[2]

    return convert


# outDownwards (3) / outUpwards (4) — an unpitched slide OFF the fret with a
# direction but no landing note → Rocksmith slideUnpitchTo.
_SLIDE_OUT_DOWN = 3
_SLIDE_OUT_UP = 4
_SLIDE_SHIFT_TYPES = {1, 2}  # shiftSlideTo / legatoSlideTo — a pitched slide


def _finger_value(finger: object) -> int:
    """Fretting-hand finger (0-4) from a PyGuitarPro Fingering, else -1.

    PyGuitarPro Fingering: -2 unknown, -1 open, 0 thumb, 1-4 fingers. Rocksmith's
    leftHand takes 0-4, so pass through valid finger numbers and drop the rest."""
    v = getattr(finger, "value", finger)
    if not isinstance(v, int | float | str):
        return -1
    try:
        iv = int(v)
    except (TypeError, ValueError):
        return -1
    return iv if 0 <= iv <= 4 else -1


def _pick_direction(beat_effect: object) -> int:
    """0 = unspecified, 1 = down, 2 = up, from a GP beat's pick stroke."""
    stroke = getattr(beat_effect, "pickStroke", None)
    v = int(getattr(stroke, "value", stroke) or 0)
    # PyGuitarPro BeatStrokeDirection: 1 = up, 2 = down → RS 1 = down, 2 = up.
    if v == 2:
        return 1
    if v == 1:
        return 2
    return 0


def _slide_out_target(slides: object, fret: int) -> int | None:
    """Unpitched slide-out target fret for a GP note, or None.

    Down slides head toward the nut, up slides toward the bridge; the exact fret
    is cosmetic (the slide is unpitched), so use a fixed 5-fret offset clamped to
    the neck and guaranteed distinct from the note's own fret."""
    vals = {int(s.value) for s in slides}  # type: ignore[attr-defined]
    if _SLIDE_OUT_DOWN in vals:
        return max(1, fret - 5)
    if _SLIDE_OUT_UP in vals:
        return min(22, fret + 5)
    return None


# pyguitarpro SlideType: intoFromBelow = -1, intoFromAbove = -2 (a scoop INTO the
# note, no source note of its own).
_SLIDE_IN_BELOW = -1
_SLIDE_IN_ABOVE = -2


def _slide_in_source(slides: object, fret: int) -> int | None:
    """Scoop source fret for a slide-INTO a GP note, or None (see expand_slide_ins).

    A slide from below starts a few frets lower, from above a few frets higher —
    a short lead-in slide, clamped to the neck."""
    vals = {int(s.value) for s in slides}  # type: ignore[attr-defined]
    if _SLIDE_IN_BELOW in vals:
        return max(1, fret - 3)
    if _SLIDE_IN_ABOVE in vals:
        return min(22, fret + 3)
    return None


def parse_gp_track(
    path: Path, track_index: int, offset_s: float = 0.0, tempo_scale: float = 1.0
) -> ParsedGpTrack:
    """Convert one Guitar Pro track to RockForge domain objects.

    offset_s shifts everything to align the score with the actual recording
    (manual synchronization; the score has no knowledge of the audio).

    tempo_scale stretches (>1) or compresses (<1) the musical timeline around
    its start, before offset_s — it corrects a constant mismatch between the
    GP file's authored tempo and the recording's real tempo (the dominant,
    linearly-growing component of sync drift). The effective average tempo is
    scaled inversely (stretching the timeline means a slower song).
    """
    if tempo_scale <= 0:
        raise IngestionError(f"tempo_scale must be positive, got {tempo_scale}")
    from rockforge.infrastructure.gpimport.gpif_parser import _is_gpif, parse_gpif_track

    if _is_gpif(path):
        return parse_gpif_track(path, track_index, offset_s, tempo_scale)
    song = _load(path)
    if not 0 <= track_index < len(song.tracks):
        raise IngestionError(f"track index {track_index} out of range")
    track = song.tracks[track_index]
    if track.isPercussionTrack:
        raise IngestionError(f"track {track_index} ('{track.name}') is percussion")
    if len(track.strings) != 6:
        raise IngestionError(
            f"track {track_index} ('{track.name}') has {len(track.strings)} strings; "
            "Rocksmith 2014 guitar arrangements require 6 (bass support not implemented)"
        )

    n_strings = len(track.strings)
    tuning_midi = tuple(s.value for s in sorted(track.strings, key=lambda s: -s.number))
    tuning = Tuning(midi=tuning_midi)
    to_seconds = _make_ticks_to_seconds(_tempo_events(track))
    origin = QUARTER_TICKS  # measure 1 starts at tick 960; song time 0

    def t(tick: int) -> float:
        return max(0.0, tempo_scale * float(to_seconds(tick - origin))) + offset_s

    # First pass: collect raw notes with GP flags for legato post-processing.
    raw: list[tuple[TabNote, bool]] = []  # (note, hammer_flag_on_origin)
    sections: list[GpSection] = []
    beats_grid: list[Beat] = []
    last_on_string: dict[int, int] = {}  # string -> raw index, for tie continuation
    dropped_out_of_range = 0  # notes off the 24-fret neck (skipped, then warned)

    for measure in track.measures:
        header = measure.header
        if header.marker is not None and header.marker.title:
            sections.append(GpSection(name=header.marker.title, start_time=t(measure.start)))
        num = header.timeSignature.numerator
        beat_len = measure.length // num
        for i in range(num):
            beats_grid.append(
                Beat(time=t(measure.start + i * beat_len), measure=header.number if i == 0 else -1)
            )

        for voice in measure.voices:
            tick = measure.start
            for beat in voice.beats:
                start = t(tick)
                sustain = max(0.0, t(tick + beat.duration.time) - start)
                for note in beat.notes:
                    string = n_strings - note.string  # GP 1=high -> ours 0=low
                    # A tie note is a held continuation, not a new attack — extend
                    # the previous note on this string instead of re-articulating
                    # it (the "4 notes shown as 5" bug). pyguitarpro: NoteType.tie.
                    if getattr(note.type, "name", "") == "tie":
                        prev = last_on_string.get(string)
                        if prev is not None:
                            pn = raw[prev][0]
                            end = start + sustain
                            raw[prev] = (
                                replace(pn, sustain=max(pn.sustain, end - pn.time)),
                                raw[prev][1],
                            )
                        continue
                    fret = int(note.value)
                    if not 0 <= fret <= 24:
                        dropped_out_of_range += 1
                        tick += beat.duration.time
                        continue
                    eff = note.effect
                    techs: set[Technique] = set()
                    bend_semitones = 0.0
                    bend_points: tuple[BendPoint, ...] = ()
                    if eff.isBend and eff.bend is not None and eff.bend.points:
                        # Full curve: position 0..12 → fraction; value/2 → half-steps.
                        pts = [
                            BendPoint(position=p.position / 12.0, step=p.value / 2.0)
                            for p in eff.bend.points
                        ]
                        bend_semitones = max(p.step for p in pts)
                        if bend_semitones:
                            techs.add(Technique.BEND)
                            # Keep the curve only for real pre-bends/releases; a
                            # plain rise stays a single point downstream.
                            if is_composite_bend(pts):
                                bend_points = tuple(pts)
                    if eff.palmMute:
                        techs.add(Technique.PALM_MUTE)
                    if eff.isHarmonic:
                        # Artificial/pinch harmonics get the distinct pinch glyph;
                        # natural/tapped/semi map to the plain harmonic.
                        htype = getattr(getattr(eff, "harmonic", None), "type", 1)
                        techs.add(Technique.PINCH_HARMONIC if htype in (2, 3)
                                  else Technique.HARMONIC)
                    if eff.vibrato:
                        techs.add(Technique.VIBRATO)
                    if getattr(eff, "isTremoloPicking", False) or eff.tremoloPicking:
                        techs.add(Technique.TREMOLO)
                    if getattr(eff, "letRing", False):
                        techs.add(Technique.LET_RING)
                    # A dead note (NoteType.dead) is the muted "X" — a fret-hand mute.
                    if getattr(note.type, "name", "") == "dead":
                        techs.add(Technique.FRET_MUTE)
                    left_hand = _finger_value(getattr(eff, "leftHandFinger", None))
                    pick_dir = _pick_direction(beat.effect)
                    # Only a SHIFT/legato slide (types 1/2) is a pitched slide to a
                    # landing fret (slideTo, filled from the next note). A slide-OUT
                    # (types 3/4) slides off into nowhere — an UNPITCHED slide with a
                    # direction but no landing note; capture it as slideUnpitchTo.
                    if any(int(s.value) in _SLIDE_SHIFT_TYPES for s in eff.slides):
                        techs.add(Technique.SLIDE)
                    slide_unpitch = _slide_out_target(eff.slides, fret)
                    slide_in = _slide_in_source(eff.slides, fret)
                    trill = getattr(eff, "trill", None)
                    trill_fret = (int(trill.fret) if trill is not None
                                  and 0 <= int(trill.fret) <= 24 else None)
                    if eff.accentuatedNote or eff.heavyAccentuatedNote:
                        techs.add(Technique.ACCENT)
                    slap = int(beat.effect.slapEffect.value)
                    if slap == 1:
                        techs.add(Technique.TAP)
                    elif slap == 2:
                        techs.add(Technique.SLAP)
                    elif slap == 3:
                        techs.add(Technique.POP)
                    last_on_string[string] = len(raw)
                    raw.append(
                        (
                            TabNote(
                                string=string,
                                fret=fret,
                                time=start,
                                sustain=sustain,
                                techniques=frozenset(techs),
                                bend_semitones=bend_semitones,
                                slide_unpitch_to=slide_unpitch,
                                bend_points=bend_points,
                                left_hand=left_hand,
                                pick_direction=pick_dir,
                                slide_in_from=slide_in,
                                trill_fret=trill_fret,
                            ),
                            bool(eff.hammer),
                        )
                    )
                tick += beat.duration.time

    # GP marks hammer/pull on the ORIGIN note ("hammer to next"); Rocksmith tags
    # the DESTINATION. Move the flag to the next note on the same string.
    notes = [n for n, _ in raw]
    order = sorted(range(len(notes)), key=lambda i: (notes[i].string, notes[i].time))
    for a, b in zip(order, order[1:], strict=False):
        if notes[a].string != notes[b].string or not raw[a][1]:
            continue
        tech = Technique.HAMMER_ON if notes[b].fret > notes[a].fret else Technique.PULL_OFF
        notes[b] = replace(notes[b], techniques=notes[b].techniques | {tech})

    # GP marks a pitched slide on the ORIGIN note; Rocksmith's slideTo also
    # belongs on the origin note but needs the DESTINATION fret. Fill it in
    # from the next note on the same string.
    for a, b in zip(order, order[1:], strict=False):
        if notes[a].string != notes[b].string:
            continue
        if Technique.SLIDE not in notes[a].techniques:
            continue
        notes[a] = replace(notes[a], slide_to_fret=notes[b].fret)

    # Expand slide-into scoops into real lead-in slide notes before the gap trim.
    notes = expand_slide_ins(notes)
    # Trim sustains so they end a small gap before the next note on the string,
    # instead of running right into it (done after slideTo is filled so pitched
    # slides keep their reach).
    notes = apply_sustain_gap(notes)
    notes = expand_trills(notes)  # trills → alternating HO/PO runs (kept tight)
    notes.sort(key=lambda n: (n.time, n.string))
    beats_grid.sort(key=lambda b: b.time)
    avg_bpm = float(song.tempo) / tempo_scale
    numerator = track.measures[0].header.timeSignature.numerator if track.measures else 4
    tempo_map = TempoMap(
        beats=tuple(beats_grid), average_bpm=avg_bpm, beats_per_measure=numerator
    )

    lyrics: list[GpLyricLine] = []
    measure_start_by_number = {
        m.header.number: t(m.start) for m in track.measures
    }
    for line in song.lyrics.lines:
        text = (line.lyrics or "").strip()
        if text:
            start = measure_start_by_number.get(max(1, line.startingMeasure), offset_s)
            lyrics.append(GpLyricLine(time=start, text=text))

    warnings: list[str] = []
    if dropped_out_of_range:
        warnings.append(
            f"{dropped_out_of_range} note(s) dropped: off the 24-fret neck "
            f"(fret < 0 or > 24) — likely an extended-range/bass part on this track"
        )
    return ParsedGpTrack(
        notes=notes, tuning=tuning, tempo_map=tempo_map, sections=sections,
        lyrics=lyrics, warnings=warnings,
    )
