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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rockforge.domain.errors import IngestionError
from rockforge.domain.music import Beat, TabNote, Technique, TempoMap, Tuning

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
    """(tick, bpm) change points, starting with the song tempo at tick 0."""
    events: list[tuple[int, float]] = [(0, float(track.song.tempo))]
    for measure in track.measures:
        for voice in measure.voices:
            tick = measure.start
            for beat in voice.beats:
                mtc = beat.effect.mixTableChange
                if mtc is not None and mtc.tempo is not None:
                    events.append((tick, float(mtc.tempo.value)))
                tick += beat.duration.time
    events.sort(key=lambda e: e[0])
    return events


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


_SLIDE_OUT_TYPES = {3, 4}  # outDownwards / outUpwards
_SLIDE_SHIFT_TYPES = {1, 2}  # shiftSlideTo / legatoSlideTo


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
                    fret = int(note.value)
                    if not 0 <= fret <= 24:
                        tick += beat.duration.time
                        continue
                    eff = note.effect
                    techs: set[Technique] = set()
                    bend_semitones = 0.0
                    if eff.isBend and eff.bend is not None and eff.bend.points:
                        bend_semitones = max(p.value for p in eff.bend.points) / 2.0
                        if bend_semitones:
                            techs.add(Technique.BEND)
                    if eff.palmMute:
                        techs.add(Technique.PALM_MUTE)
                    if eff.isHarmonic:
                        techs.add(Technique.HARMONIC)
                    if eff.vibrato:
                        techs.add(Technique.VIBRATO)
                    if any(int(s.value) in _SLIDE_OUT_TYPES | _SLIDE_SHIFT_TYPES
                           for s in eff.slides):
                        techs.add(Technique.SLIDE)
                    if eff.accentuatedNote or eff.heavyAccentuatedNote:
                        techs.add(Technique.ACCENT)
                    slap = int(beat.effect.slapEffect.value)
                    if slap == 1:
                        techs.add(Technique.TAP)
                    elif slap == 2:
                        techs.add(Technique.SLAP)
                    elif slap == 3:
                        techs.add(Technique.POP)
                    raw.append(
                        (
                            TabNote(
                                string=string,
                                fret=fret,
                                time=start,
                                sustain=sustain,
                                techniques=frozenset(techs),
                                bend_semitones=bend_semitones,
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
        n = notes[b]
        notes[b] = TabNote(
            string=n.string, fret=n.fret, time=n.time, sustain=n.sustain,
            techniques=n.techniques | {tech},
            bend_semitones=n.bend_semitones, slide_to_fret=n.slide_to_fret,
        )

    # GP marks a pitched slide on the ORIGIN note; Rocksmith's slideTo also
    # belongs on the origin note but needs the DESTINATION fret. Fill it in
    # from the next note on the same string.
    for a, b in zip(order, order[1:], strict=False):
        if notes[a].string != notes[b].string:
            continue
        if Technique.SLIDE not in notes[a].techniques:
            continue
        n = notes[a]
        notes[a] = TabNote(
            string=n.string, fret=n.fret, time=n.time, sustain=n.sustain,
            techniques=n.techniques, bend_semitones=n.bend_semitones,
            slide_to_fret=notes[b].fret,
        )

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

    return ParsedGpTrack(
        notes=notes, tuning=tuning, tempo_map=tempo_map, sections=sections, lyrics=lyrics
    )
