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

import copy
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from rockforge.domain.alphatab import alphatab_bend
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
    extend_through_tie,
    is_composite_bend,
)
from rockforge.infrastructure.gpimport.playback import (
    GP5_DIRECTIONS,
    BarFlow,
    jump_convention_warning,
    jump_skips_repeats,
    playback_order,
)
from rockforge.infrastructure.gpimport.strings import (
    apply_capo,
    check_track_strings,
    fold_strings,
)
from rockforge.infrastructure.gpimport.sync_map import (
    bar_time_points,
    bar_times_warnings,
    relative_to_bar_one,
)

QUARTER_TICKS = 960


def _bend_curve(eff: Any) -> list[BendPoint]:
    """A note's bend curve as alphaTab plays it: position 0..12 → fraction;
    value/2 → half-steps."""
    if not (eff.isBend and eff.bend is not None and eff.bend.points):
        return []
    return list(alphatab_bend(
        [BendPoint(position=p.position / 12.0, step=p.value / 2.0) for p in eff.bend.points]
    ))


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
class LyricNote:
    """One note of the track the lyrics are sung on — the attack a syllable
    takes. ``end`` is when the note stops (its written length), ``midi`` its
    pitch when the file says it, and ``rest_before`` whether the vocal line
    rests between the previous note and this one (a breath: where a phrase
    usually ends)."""

    time: float
    end: float
    midi: int | None = None
    rest_before: bool = False


@dataclass(frozen=True)
class ParsedGpTrack:
    notes: list[TabNote]
    tuning: Tuning
    tempo_map: TempoMap
    sections: list[GpSection]
    lyrics: list[GpLyricLine] = field(default_factory=list)
    # The notes of the track the lyrics BELONG to (its first voice, rests
    # skipped) — the attacks Guitar Pro hands the syllables to, one each.
    # Usually a vocal track, not the charted guitar; None when the file does not
    # say which track that is, and the syllables fall back to the chart's notes.
    lyric_notes: tuple[LyricNote, ...] | None = None
    # Non-fatal notices from parsing (e.g. notes dropped for being off the
    # 24-fret neck) — surfaced to the user instead of silently swallowed.
    warnings: list[str] = field(default_factory=list)
    # The capo fret (0 = none). The notes' frets are already counted from the
    # nut, as Rocksmith counts them (``strings.apply_capo``).
    capo: int = 0


def close_beat_grid(beats: list[Beat], bar_end: float, last_note: float | None) -> None:
    """Add the song's final bar line to the grid, in place.

    The grid holds one beat per counted beat of every bar, so without this it
    stops at the LAST BEAT of the last bar, not at its end — and a note after
    that beat (an eighth on the "and" of 4, the ordinary way a song ends in a
    strummed pattern) lay past the final ebeat, which ``Arrangement.validate``
    rightly refuses. The closing line is a downbeat, numbered as the bar that
    would follow (how EOF-authored charts carry a grid past the last bar). A
    last bar holding more than its time signature (an overfull bar, which a
    converter can write) keeps the grid going at the last spacing until it
    covers the final note."""
    if not beats:
        return
    if bar_end > beats[-1].time + 1e-6:
        number = max(b.measure for b in beats) + 1
        beats.append(Beat(time=bar_end, measure=max(1, number)))
    step = beats[-1].time - beats[-2].time if len(beats) > 1 else 0.5
    step = step if step > 0 else 0.5
    while last_note is not None and last_note > beats[-1].time:
        beats.append(Beat(time=beats[-1].time + step, measure=-1))


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


def _bar_flows(song: Any) -> list[BarFlow]:
    """Repeats, voltas and jumps of each bar, in alphaTab's terms.

    PyGuitarPro's ``repeatClose`` is the number of repeats (plays - 1, -1 = no
    repeat end) and ``repeatAlternative`` already the voltas bitmask (it converts
    the GP3/GP4 volta number the way alphaTab does)."""
    flows = []
    for h in song.measureHeaders:
        names = {getattr(d, "name", "") for d in (h.direction, h.fromDirection) if d is not None}
        flows.append(BarFlow(
            repeat_start=bool(h.isRepeatOpen),
            repeat_count=h.repeatClose + 1 if h.repeatClose >= 0 else 0,
            alternate_endings=int(h.repeatAlternative or 0),
            directions=frozenset(GP5_DIRECTIONS[n] for n in names if n in GP5_DIRECTIONS),
        ))
    return flows


def bars_as_played(song: Any) -> list[int]:
    """The written bar (0-based) heard at each played position: ``order[n - 1]`` is the
    written bar that the chart's bar ``n`` comes from (the order ``_as_played`` lays out)."""
    return playback_order(_bar_flows(song))


def _as_played(song: Any) -> Any:
    """``song`` with its bars in the order they are played (repeats, voltas and
    D.C./D.S./Coda/Fine unrolled, as alphaTab plays them — see ``playback``).

    Bar N of the result is the N-th bar HEARD, so the chart, its beat grid, its
    sections and per-bar times (Songsterr's are per played bar too) follow the
    recording. A lyric line starts again on every pass of the bar it starts on
    (the syllables belong to the written beats, as in alphaTab). A score without
    repeats comes back unchanged."""
    order = bars_as_played(song)
    if order == list(range(len(song.measureHeaders))):
        return song
    headers = []
    start = song.measureHeaders[0].start
    for number, index in enumerate(order, start=1):
        header = copy.copy(song.measureHeaders[index])
        header.number, header.start = number, start
        header.isRepeatOpen, header.repeatClose, header.repeatAlternative = False, -1, 0
        header.direction = header.fromDirection = None
        headers.append(header)
        start += header.length
    for track in song.tracks:
        measures = []
        for header, index in zip(headers, order, strict=True):
            measure = copy.copy(track.measures[index])
            measure.header = header
            measures.append(measure)
        track.measures = measures
    song.measureHeaders = headers
    lines = []
    for line in song.lyrics.lines:
        first = max(1, line.startingMeasure) - 1
        for number, index in enumerate(order, start=1):
            if index == first:
                replayed = copy.copy(line)
                replayed.startingMeasure = number
                lines.append(replayed)
    song.lyrics.lines = lines
    return song


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
                # RELATIVE to the song's origin, because that is the scale the
                # caller looks tempo up on: notes and beats are timed with
                # ``to_seconds(tick - QUARTER_TICKS)``. Keying these events at the
                # ABSOLUTE ``measure.start`` (bar 1 begins at tick 960) mixed the
                # two scales and applied every mid-song tempo change one quarter
                # note LATE — so a song drifted by the difference between one beat
                # at the old tempo and one at the new, at every change, and it
                # accumulated. Invisible in a constant-tempo file, which is how it
                # survived. Guarded by
                # test_a_mid_song_tempo_change_takes_effect_on_its_own_beat.
                tick = measure.start - QUARTER_TICKS
                for beat in voice.beats:
                    mtc = beat.effect.mixTableChange
                    if mtc is not None and mtc.tempo is not None:
                        events[max(0, tick)] = float(mtc.tempo.value)
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
# legatoSlideTo: the landing note is not picked again — Rocksmith's linkNext.
_SLIDE_LEGATO = 2


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
    """0 = unspecified, 1 = down, 2 = up, from a GP beat's brush (strum / arpeggio)
    or pick stroke — the brush first, as the GPIF path reads them."""
    v = 0
    for name in ("stroke", "pickStroke"):
        stroke = getattr(beat_effect, name, None)
        stroke = getattr(stroke, "direction", stroke)  # BeatStroke → its direction
        v = int(getattr(stroke, "value", stroke) or 0)
        if v:
            break
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
    path: Path,
    track_index: int,
    offset_s: float = 0.0,
    tempo_scale: float = 1.0,
    bar_times: Sequence[float] | None = None,
    *,
    bass: bool = False,
) -> ParsedGpTrack:
    """Convert one Guitar Pro track to RockForge domain objects.

    ``bass`` reads it as a bass chart: a 4- or 5-string track, folded onto four
    strings with a bass tuning (``strings.fold_strings``); otherwise a guitar's
    six strings.

    offset_s shifts everything to align the score with the actual recording
    (manual synchronization; the score has no knowledge of the audio).

    tempo_scale stretches (>1) or compresses (<1) the musical timeline around
    its start, before offset_s — it corrects a constant mismatch between the
    GP file's authored tempo and the recording's real tempo (the dominant,
    linearly-growing component of sync drift). The effective average tempo is
    scaled inversely (stretching the timeline means a slower song).

    bar_times, when given, are where each bar starts in the recording (e.g.
    Songsterr's human-marked measure timestamps); the score is re-timed onto
    them relative to bar 1, exactly like Guitar Pro 8's own sync points, so
    offset_s still means "where bar 1 is". See ``sync_map``.
    """
    if tempo_scale <= 0:
        raise IngestionError(f"tempo_scale must be positive, got {tempo_scale}")
    from rockforge.infrastructure.gpimport.gpif_parser import _is_gpif, parse_gpif_track

    if _is_gpif(path):
        return parse_gpif_track(path, track_index, offset_s, tempo_scale, bar_times, bass=bass)
    written = _load(path)
    jump_convention = jump_skips_repeats(_bar_flows(written))
    song = _as_played(written)
    if not 0 <= track_index < len(song.tracks):
        raise IngestionError(f"track index {track_index} out of range")
    track = song.tracks[track_index]
    if track.isPercussionTrack:
        raise IngestionError(f"track {track_index} ('{track.name}') is percussion")
    check_track_strings(len(track.strings), bass=bass, label=f"{track_index} ('{track.name}')")

    n_strings = len(track.strings)
    tuning_midi = tuple(s.value for s in sorted(track.strings, key=lambda s: -s.number))
    to_seconds = _make_ticks_to_seconds(_tempo_events(track))
    origin = QUARTER_TICKS  # measure 1 starts at tick 960; song time 0
    bar_ticks = [m.start - origin for m in track.measures]
    bar_points, bar_skipped = bar_time_points(bar_ticks, bar_times or [])
    to_seconds = relative_to_bar_one(to_seconds, bar_points)

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
                    # Its own bend and hammer/pull (held, then bent / pulled off:
                    # drawn on the tied note by alphaTab and Guitar Pro) carry over
                    # to the held note instead of being dropped.
                    if getattr(note.type, "name", "") == "tie":
                        prev = last_on_string.get(string)
                        if prev is not None:
                            pn, hammer = raw[prev]
                            tie_bend = _bend_curve(note.effect)
                            held = extend_through_tie(pn, start, start + sustain, tie_bend)
                            if note.effect.vibrato:  # vibrato on the held part
                                held = replace(
                                    held, techniques=held.techniques | {Technique.VIBRATO}
                                )
                            # A slide drawn on the held part slides out of the
                            # whole held note (and a legato one links it on).
                            tie_slides = {int(sl.value) for sl in note.effect.slides}
                            if tie_slides & _SLIDE_SHIFT_TYPES:
                                held = replace(
                                    held, techniques=held.techniques | {Technique.SLIDE},
                                    link_next=_SLIDE_LEGATO in tie_slides,
                                )
                            raw[prev] = (held, hammer or bool(note.effect.hammer))
                        continue
                    fret = int(note.value)
                    if not 0 <= fret <= 24:
                        dropped_out_of_range += 1
                        continue
                    eff = note.effect
                    techs: set[Technique] = set()
                    bend_semitones = 0.0
                    bend_points: tuple[BendPoint, ...] = ()
                    pts = _bend_curve(eff)
                    if pts:
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
                        # PyGuitarPro HarmonicType: 1 natural, 2 artificial, 3 tapped,
                        # 4 pinch, 5 semi (as the GPIF path: artificial/pinch → pinch).
                        techs.add(Technique.PINCH_HARMONIC if htype in (2, 4)
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
                    note_start, note_sustain = start, sustain
                    grace = eff.grace
                    if grace is not None and 0 <= int(grace.fret) <= 24:
                        # A grace note is a short note of its own, as alphaTab plays
                        # it: before the beat it takes the end of the previous
                        # note's time; on the beat it delays this note.
                        g_ticks = grace.durationTime
                        if grace.isOnBeat:
                            g_start = start
                            g_len = min(sustain, max(0.0, t(tick + g_ticks) - start))
                            note_start, note_sustain = start + g_len, sustain - g_len
                        else:
                            g_start = t(max(origin, tick - g_ticks))
                            g_len = max(0.0, start - g_start)
                        transition = int(getattr(grace.transition, "value", 0) or 0)
                        g_techs: set[Technique] = set()
                        if transition == 1:  # slide into the note
                            g_techs.add(Technique.SLIDE)
                        if grace.isDead:
                            g_techs.add(Technique.FRET_MUTE)
                        raw.append((
                            TabNote(string=string, fret=int(grace.fret), time=g_start,
                                    sustain=g_len, techniques=frozenset(g_techs)),
                            transition == 3,  # hammer/pull into the note
                        ))
                    last_on_string[string] = len(raw)
                    raw.append(
                        (
                            TabNote(
                                string=string,
                                fret=fret,
                                time=note_start,
                                sustain=note_sustain,
                                techniques=frozenset(techs),
                                bend_semitones=bend_semitones,
                                slide_unpitch_to=slide_unpitch,
                                bend_points=bend_points,
                                left_hand=left_hand,
                                pick_direction=pick_dir,
                                slide_in_from=slide_in,
                                trill_fret=trill_fret,
                                link_next=any(
                                    int(sl.value) == _SLIDE_LEGATO for sl in eff.slides
                                ),
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
    if track.measures:
        last = track.measures[-1]
        close_beat_grid(
            beats_grid, t(last.start + last.length), notes[-1].time if notes else None
        )
    base_bpm = float(song.tempo)
    if bar_points and track.measures:
        # Re-timed from outside, the header tempo is not what plays.
        last = track.measures[-1]
        total_ticks = last.start + last.length - origin
        total_s = float(to_seconds(total_ticks))
        if total_ticks > 0 and total_s > 0:
            base_bpm = (total_ticks / QUARTER_TICKS) / (total_s / 60.0)
    avg_bpm = base_bpm / tempo_scale
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
    lyric_notes = _lyric_notes(song, t) if lyrics else None

    warnings: list[str] = []
    if jump_convention:
        warnings.append(jump_convention_warning())
    if bar_times:
        warnings.extend(bar_times_warnings(len(bar_ticks), len(bar_times), bar_skipped))
    if dropped_out_of_range:
        warnings.append(
            f"{dropped_out_of_range} note(s) dropped: off the 24-fret neck "
            f"(fret < 0 or > 24) — likely an extended-range/bass part on this track"
        )
    notes, tuning, fold_warnings = fold_strings(notes, tuning_midi, bass=bass)
    warnings.extend(fold_warnings)
    capo = max(0, int(getattr(track, "offset", 0) or 0))  # PyGuitarPro: Track.offset = capo
    notes, capo_warnings = apply_capo(notes, capo)
    warnings.extend(capo_warnings)
    return ParsedGpTrack(
        notes=notes, tuning=tuning, tempo_map=tempo_map, sections=sections,
        lyrics=lyrics, lyric_notes=lyric_notes, warnings=warnings, capo=capo,
    )


def _lyric_notes(song: Any, t: Callable[[int], float]) -> tuple[LyricNote, ...] | None:
    """Every note-bearing beat in the first voice of the lyrics' track.

    GP3-5 store the lyrics once per song with the (1-based) track they are
    sung on — ``trackChoice``, 0 meaning none — and Guitar Pro hands one
    syllable to each beat of that track that is not a rest (alphaTab's
    ``Track.applyLyrics`` does the same). Ticks are song-wide, so the charted
    track's own clock ``t`` times them. The pitch is the beat's highest note
    (string tuning + fret) — a vocal line is one note at a time."""
    index = int(getattr(song.lyrics, "trackChoice", 0) or 0) - 1
    if not 0 <= index < len(song.tracks):
        return None
    track = song.tracks[index]
    tuning = {s.number: s.value for s in track.strings}
    out: list[LyricNote] = []
    rest = False
    for measure in track.measures:
        if not measure.voices:
            continue
        tick = measure.start
        for beat in measure.voices[0].beats:
            length = beat.duration.time
            if beat.notes:
                pitches = [
                    tuning[n.string] + n.value for n in beat.notes if n.string in tuning
                ]
                out.append(LyricNote(
                    time=t(tick), end=t(tick + length),
                    midi=max(pitches) if pitches else None, rest_before=rest,
                ))
                rest = False
            else:
                rest = True
            tick += length
    return tuple(out) or None
