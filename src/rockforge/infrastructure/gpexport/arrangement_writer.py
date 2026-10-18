"""Write a whole ``Arrangement`` out as a fresh Guitar Pro 5 file.

The companion to ``tempo_writer``, which patches tempo into a COPY of the user's
own file. This one generates a new ``.gp5`` from what RockForge holds, so the
in-app note edits (fret, sustain, techniques, added and removed notes) and the
manual sync corrections come out as a real Guitar Pro score.

**Why generate rather than patch.** Patching the original would preserve
everything RockForge does not model — other tracks, formatting, embedded lyrics
— but every edit would have to be mapped back to a measure/beat of the source
file, and INSERTING a note where the bar has no beat at that position means
rewriting the bar's rhythm. Generating is exact for what we do model and works
for any edit; the trade is stated up front to the user and repeated in the
export report: the output has ONE track — this arrangement — and nothing else
from the original file.

**The timeline is the corrected one.** ``Arrangement`` is already in the built
(bundle) clock, so its beat grid carries the tempo_scale and drift corrections
the user made. Writing that grid back out is precisely what makes the sync fix
permanent in Guitar Pro.

**Rhythm is quantised, and the report says by how much.** The domain stores note
onsets in SECONDS; Guitar Pro needs notated rhythm. Onsets are snapped to a grid
of ``QUANTIZE_DIV`` subdivisions per beat. A chart parsed from a GP file and
edited on the app's snap grid lands on that grid exactly; anything that does not
is moved, and ``ExportedArrangement.max_shift_s`` reports the worst case rather
than letting a silently re-timed score look authoritative.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from rockforge.domain.errors import IngestionError
from rockforge.domain.music import Technique
from rockforge.i18n import tr

if TYPE_CHECKING:  # pragma: no cover - typing only
    from rockforge.domain.arrangement import Arrangement
    from rockforge.domain.music import TabNote

QUARTER_TICKS = 960  # PyGuitarPro's Duration.quarterTime; mirrors gpimport.parser
# Subdivisions of a beat the exported rhythm is snapped to. 4 = sixteenth notes
# at a quarter-note beat, which covers the app's own snap grid (bars, beats, and
# beats split in 2/3/4) without inventing a precision the score does not have.
QUANTIZE_DIV = 4
_MIN_TICKS = QUARTER_TICKS // QUANTIZE_DIV


@dataclass
class ExportedArrangement:
    """What the export actually produced — reported, never assumed."""

    filename: str
    measures: int
    notes_written: int
    notes_dropped: int = 0  # onsets past the last measure, or on a missing string
    quantized: int = 0  # onsets that had to move to reach the rhythmic grid
    max_shift_s: float = 0.0
    # notes snapped onto a string already sounding at that tick (one dropped each)
    string_clashes: int = 0
    # how far the bars drifted from the chart's own times (integer BPM, the 10-400 clamp)
    tempo_drift_s: float = 0.0
    warnings: list[str] = field(default_factory=list)


# Techniques with a direct PyGuitarPro equivalent. The rest of our Technique
# enum (BEND/SLIDE carry their own dedicated fields; ACCENT/TAP/SLAP/POP live on
# the beat, not the note) is handled explicitly below or deliberately skipped.
_NOTE_EFFECT_FLAGS: dict[Technique, str] = {
    Technique.PALM_MUTE: "palmMute",
    Technique.HAMMER_ON: "hammer",
    Technique.PULL_OFF: "hammer",  # GP models both as the same "hammer" flag
    Technique.VIBRATO: "vibrato",
    Technique.TREMOLO: "tremoloPicking",
    Technique.LET_RING: "letRing",
}


def _measure_grid(arrangement: Arrangement) -> list[tuple[float, float, int]]:
    """``(start, end, beats)`` per measure, from the arrangement's own ebeats.

    Downbeats carry a measure number; the beats between two downbeats give the
    bar its beat count (so a 3/4 bar exports as 3/4, not as a padded 4/4).
    """
    beats = list(arrangement.tempo_map.beats)
    if not beats:
        raise IngestionError("the arrangement has no beat grid to write measures from")
    downbeat_idx = [i for i, b in enumerate(beats) if b.measure and b.measure > 0]
    if not downbeat_idx:
        raise IngestionError("the arrangement's beat grid has no measure downbeats")
    grid: list[tuple[float, float, int]] = []
    for n, i in enumerate(downbeat_idx):
        start = beats[i].time
        if n + 1 < len(downbeat_idx):
            j = downbeat_idx[n + 1]
            end, count = beats[j].time, j - i
        elif i == len(beats) - 1 and grid:
            # A downbeat with nothing after it is the closing bar line
            # (``close_beat_grid``): it ends the previous bar, it is not a bar.
            break
        else:
            # Last measure: keep the beat spacing of the one before it so the
            # trailing bar is a real bar rather than a zero-length stub.
            count = max(1, len(beats) - i)
            spacing = (
                (beats[-1].time - beats[i].time) / max(1, len(beats) - 1 - i)
                if len(beats) - 1 > i
                else (grid[-1][1] - grid[-1][0]) / max(1, grid[-1][2])
                if grid
                else 0.5
            )
            end = start + spacing * count
        if end > start:
            grid.append((start, end, count))
    return grid


# Tick spans Guitar Pro can notate as ONE figure: whole down to 64th, plus the
# dotted variants. An arbitrary gap (3.5 quarters, say) is none of these and
# Duration.fromTime raises on it, so a span is decomposed into these instead.
_NOTATABLE_TICKS: tuple[int, ...] = tuple(
    sorted(
        {t for base in (3840, 1920, 960, 480, 240, 120, 60) for t in (base, base * 3 // 2)},
        reverse=True,
    )
)


def _split_ticks(total: int) -> list[int]:
    """Decompose a tick span into notatable durations, largest first.

    Greedy, and it always terminates: the smallest unit (a 64th) divides every
    span the quantiser can produce, since that grid is coarser. A note takes the
    first chunk and the remainder becomes rests, so the NEXT note still starts on
    its own tick — which is what the timing depends on.
    """
    out: list[int] = []
    left = total
    while left >= _NOTATABLE_TICKS[-1]:
        for unit in _NOTATABLE_TICKS:
            if unit <= left:
                out.append(unit)
                left -= unit
                break
        else:  # pragma: no cover - unreachable while the loop guard holds
            break
    return out or [_NOTATABLE_TICKS[-1]]


def _quantize(offset_s: float, measure_s: float, measure_ticks: int) -> int:
    """A time offset inside a measure, snapped to the export grid, in ticks."""
    if measure_s <= 0:
        return 0
    raw = offset_s / measure_s * measure_ticks
    return int(round(raw / _MIN_TICKS)) * _MIN_TICKS


def _apply_note_effects(gp_note: Any, note: TabNote, guitarpro: Any, beat_s: float) -> None:
    """Map our techniques onto a PyGuitarPro note, mirroring the importer.

    ``beat_s``: how long the figure written for the note lasts (its bend's scale).
    """
    effect = gp_note.effect
    for tech, flag in _NOTE_EFFECT_FLAGS.items():
        if tech in note.techniques and hasattr(effect, flag):
            setattr(effect, flag, True)
    if Technique.FRET_MUTE in note.techniques:
        gp_note.type = guitarpro.NoteType.dead
    if Technique.HARMONIC in note.techniques:
        effect.harmonic = guitarpro.NaturalHarmonic()
    elif Technique.PINCH_HARMONIC in note.techniques:
        effect.harmonic = guitarpro.ArtificialHarmonic()
    if note.slide_to_fret is not None or Technique.SLIDE in note.techniques:
        # A slide that runs on into its landing note without a new pick is
        # Guitar Pro's legato slide — what the importer reads as link_next.
        effect.slides = [guitarpro.SlideType.legatoSlideTo if note.link_next
                         else guitarpro.SlideType.shiftSlideTo]
    if note.bend_semitones:
        points = _bend_shape(note, beat_s)
        values = [v for _, v in points]
        peak = max(values)
        if peak > 0:
            if values[0] > 0:
                kind = (guitarpro.BendType.prebendRelease if values[-1] < values[0]
                        else guitarpro.BendType.prebend)
            else:
                kind = (guitarpro.BendType.bendRelease if values[-1] < peak
                        else guitarpro.BendType.bend)
            effect.bend = guitarpro.BendEffect(
                type=kind,
                value=peak * 25,  # GP: 100 = a whole tone (4 quarter tones)
                points=[guitarpro.BendPoint(position=pos, value=v) for pos, v in points],
            )


# The .gp (GP7/8) format stores a bend as origin, two middle points and
# destination, and alphaTab's .gp export drops a bend with more points: keep the
# curve to this many so the file survives being saved as .gp.
MAX_BEND_POINTS = 4


def _bend_shape(note: TabNote, beat_s: float) -> list[tuple[int, int]]:
    """The note's bend over its written figure: (position 0..12, quarter tones).

    ``bend_points`` positions are fractions of the note's sustain; the figure
    written for it lasts ``beat_s``, so they are re-timed onto that (a part past
    the figure is cut, at its interpolated value). A note without a curve is the
    domain's single-peak bend: a rise to the peak across the note.
    """
    if note.bend_points:
        span = note.sustain if note.sustain > 0 else beat_s
        curve = [(p.position * span, p.step) for p in note.bend_points]
    else:
        curve = [(0.0, 0.0), (beat_s, note.bend_semitones)]
    if beat_s > 0 and curve[-1][0] > beat_s:
        inside = [c for c in curve if c[0] <= beat_s]
        (t0, v0), (t1, v1) = next(
            (curve[i - 1], curve[i]) for i in range(1, len(curve)) if curve[i][0] > beat_s
        )
        cut = v0 + (v1 - v0) * (beat_s - t0) / (t1 - t0) if t1 > t0 else v1
        curve = [*inside, (beat_s, cut)]
    points = [
        (round(min(max(t / beat_s, 0.0), 1.0) * 12) if beat_s > 0 else 0, round(v * 2))
        for t, v in curve
    ]
    return _fewer_bend_points(points)


def _fewer_bend_points(points: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """At most MAX_BEND_POINTS, same shape: flat stretches keep only their ends,
    and a flat start or end begins/ends the curve at its last/first point."""
    if len(points) <= MAX_BEND_POINTS:
        return points
    out = [
        p for i, p in enumerate(points)
        if i in (0, len(points) - 1) or not points[i - 1][1] == p[1] == points[i + 1][1]
    ]
    while len(out) > MAX_BEND_POINTS and out[0][1] == out[1][1]:
        out.pop(0)
    while len(out) > MAX_BEND_POINTS and out[-1][1] == out[-2][1]:
        out.pop()
    if len(out) > MAX_BEND_POINTS:
        # Still too many (several distinct steps): start, the top held, end.
        peak = max(v for _, v in out)
        tops = [p for p in out if p[1] == peak]
        out = list(dict.fromkeys([out[0], tops[0], tops[-1], out[-1]]))
    return out


def write_arrangement_gp5(
    arrangement: Arrangement, dst: Path, *, track_name: str | None = None
) -> ExportedArrangement:
    """Write ``arrangement`` as a new GP5 file at ``dst``.

    Raises :class:`IngestionError` when the arrangement cannot be notated at all
    (no beat grid). Anything it CAN write but had to change — a quantised onset,
    a dropped note — comes back in the report instead of failing silently.
    """
    try:
        import guitarpro
    except ImportError as exc:  # pragma: no cover - pyguitarpro is a core dep
        raise IngestionError(
            "writing Guitar Pro files needs pyguitarpro, which is a core dependency"
        ) from exc

    grid = _measure_grid(arrangement)
    song = guitarpro.Song()
    meta = arrangement.metadata
    song.title = meta.title
    song.artist = meta.artist
    song.album = meta.album
    song.tempo = max(10, min(400, int(round(arrangement.tempo_map.average_bpm or 120))))

    track = song.tracks[0]
    track.name = track_name or arrangement.kind.value
    track.offset = arrangement.capo  # PyGuitarPro: the capo
    # GP numbers strings 1 = highest pitch; our tuning is low → high, so reverse.
    # This is the exact inverse of the importer's `string = n_strings - note.string`.
    # A bass exports its four strings at the pitch they sound (the low-tuning
    # fix, an octave up at 220 Hz, is a Rocksmith encoding, not the tuning).
    midi = list(arrangement.tuning.sounding_midi)
    track.strings = [
        guitarpro.GuitarString(number=i + 1, value=v)
        for i, v in enumerate(reversed(midi))
    ]
    n_strings = len(midi)

    by_time: dict[float, list[TabNote]] = {}
    for n in arrangement.notes:
        by_time.setdefault(round(n.time, 4), []).append(n)
    onsets = sorted(by_time)

    sections_by_measure: dict[int, str] = {}
    for sec in arrangement.sections:
        for m, (start, end, _c) in enumerate(grid):
            if start - 1e-6 <= sec.start_time < end:
                sections_by_measure.setdefault(m, sec.name)
                break

    report = ExportedArrangement(filename=dst.name, measures=len(grid), notes_written=0)
    running_bpm = song.tempo
    measure_start_tick = QUARTER_TICKS  # the importer's origin: bar 1 at tick 960
    song.measureHeaders = []
    track.measures = []
    cursor = 0  # index into `onsets`
    written_at = grid[0][0] if grid else 0.0  # where the written bars have reached, in seconds

    for m, (start, end, beat_count) in enumerate(grid):
        measure_s = end - start
        measure_ticks = beat_count * QUARTER_TICKS
        header = guitarpro.MeasureHeader()
        header.number = m + 1
        # MeasureHeader.start does NOT accumulate on its own when the headers are
        # built by hand — it defaults to quarterTime for every one of them. The
        # importer reads a tempo change's tick from `measure.start`, so leaving
        # the default put every change at the same tick and the bars after the
        # first tempo change came back mis-timed (measure 3 read as 2.5 s
        # instead of 2.667 s). Measure 1 starts at QUARTER_TICKS, matching the
        # importer's own `origin`.
        header.start = measure_start_tick
        header.timeSignature = guitarpro.TimeSignature()
        header.timeSignature.numerator = beat_count
        header.timeSignature.denominator = guitarpro.Duration(value=4)
        if m in sections_by_measure:
            header.marker = guitarpro.Marker(title=sections_by_measure[m])
        song.measureHeaders.append(header)
        measure_start_tick += measure_ticks

        measure = guitarpro.Measure(track, header)
        voice = measure.voices[0]
        voice.beats = []

        # Every onset that falls in this measure, snapped to the grid.
        placed: dict[int, list[TabNote]] = {}
        while cursor < len(onsets) and onsets[cursor] < end - 1e-9:
            t = onsets[cursor]
            if t < start - 1e-9:  # before the first measure — cannot be notated
                report.notes_dropped += len(by_time[t])
                cursor += 1
                continue
            tick = min(_quantize(t - start, measure_s, measure_ticks), measure_ticks - _MIN_TICKS)
            shift = abs((tick / measure_ticks) * measure_s - (t - start))
            if shift > 1e-4:
                report.quantized += len(by_time[t])
                report.max_shift_s = max(report.max_shift_s, shift)
            placed.setdefault(max(0, tick), []).extend(by_time[t])
            cursor += 1

        # The bar's own tempo, rounded (these formats store tempo as an integer)
        # with the rounding error CARRIED: each bar aims at where the chart's
        # bar really ends, so 90 bars at 119.52 BPM do not come back 0.67 s late.
        aim = end - written_at
        bpm = int(round(beat_count * 60.0 / aim)) if aim > 0 else song.tempo
        bpm = max(10, min(400, bpm))
        written_at += beat_count * 60.0 / bpm
        report.tempo_drift_s = max(report.tempo_drift_s, abs(written_at - end))
        measure_bpm: int | None = None
        if m == 0:
            song.tempo = bpm
            running_bpm = bpm
        elif bpm != running_bpm:
            measure_bpm = bpm
            running_bpm = bpm

        # Beats fill the bar in order; a gap becomes a rest so the measure adds up.
        at = 0
        for tick in sorted(placed):
            if tick > at:
                for chunk in _split_ticks(tick - at):
                    rest = guitarpro.Beat(voice)
                    rest.duration = guitarpro.Duration.fromTime(chunk)
                    rest.status = guitarpro.BeatStatus.rest
                    voice.beats.append(rest)
                at = tick
            group = placed[tick]
            nxt = min((k for k in placed if k > tick), default=measure_ticks)
            beat = guitarpro.Beat(voice)
            span = _split_ticks(max(_MIN_TICKS, nxt - tick))
            beat.duration = guitarpro.Duration.fromTime(span[0])
            beat_s = span[0] / measure_ticks * measure_s
            beat.status = guitarpro.BeatStatus.normal
            used: set[int] = set()
            for n in group:
                if not 0 <= n.string < n_strings:
                    report.notes_dropped += 1
                    continue
                if n.string in used:
                    # two onsets snapped onto one tick on one string: a GP5 beat
                    # holds ONE note per string — a second one made the file
                    # unreadable — so the first is kept
                    report.string_clashes += 1
                    continue
                used.add(n.string)
                gp_note = guitarpro.Note(beat)
                gp_note.string = n_strings - n.string  # inverse of the importer
                # Guitar Pro counts frets from the capo (the importer's apply_capo, inverted).
                gp_note.value = n.fret - arrangement.capo if n.fret else 0
                _apply_note_effects(gp_note, n, guitarpro, beat_s)
                beat.notes.append(gp_note)
                report.notes_written += 1
            if beat.notes:
                voice.beats.append(beat)
                # Anything the note's own figure could not cover becomes rests,
                # so the next note still starts exactly on its tick.
                for chunk in span[1:]:
                    rest = guitarpro.Beat(voice)
                    rest.duration = guitarpro.Duration.fromTime(chunk)
                    rest.status = guitarpro.BeatStatus.rest
                    voice.beats.append(rest)
                at = nxt
        if at < measure_ticks:
            for chunk in _split_ticks(measure_ticks - at):
                rest = guitarpro.Beat(voice)
                rest.duration = guitarpro.Duration.fromTime(chunk)
                rest.status = guitarpro.BeatStatus.rest
                voice.beats.append(rest)
        if measure_bpm is not None and voice.beats:
            # These formats have NO tempo field in the measure header (see
            # tempo_writer): measure 1 is the song header's tempo and every later
            # change is a MixTableChange on a beat — the bar's FIRST beat, a rest
            # too (it used to ride the first NOTE, so a bar with no notes lost its
            # tempo). This is what makes the user's sync corrections permanent.
            mtc = guitarpro.MixTableChange()
            mtc.wah = guitarpro.WahEffect.none
            mtc.hideTempo = False
            mtc.tempo = guitarpro.MixTableItem(value=measure_bpm, duration=0, allTracks=False)
            voice.beats[0].effect.mixTableChange = mtc
        track.measures.append(measure)

    # Onsets past the final measure cannot be notated — say so rather than
    # dropping them quietly.
    for t in onsets[cursor:]:
        report.notes_dropped += len(by_time[t])

    if report.notes_dropped:
        report.warnings.append(tr(
            f"{report.notes_dropped} nota(s) fora dos compassos da música não foram escritas",
            f"{report.notes_dropped} note(s) outside the song's bars were not written",
        ))
    if report.quantized:
        shift_ms = f"{report.max_shift_s * 1000:.0f}"
        report.warnings.append(tr(
            f"{report.quantized} nota(s) ajustada(s) à grelha rítmica "
            f"(desvio máximo {shift_ms} ms)",
            f"{report.quantized} note(s) snapped to the rhythmic grid "
            f"(largest shift {shift_ms} ms)",
        ))
    if report.string_clashes:
        report.warnings.append(tr(
            f"{report.string_clashes} nota(s) caíram na mesma corda e no mesmo tempo de outra "
            "depois do ajuste à grelha e não foram escritas (notas muito rápidas)",
            f"{report.string_clashes} note(s) landed on the same string and tick as another "
            "after snapping to the grid and were not written (very fast notes)",
        ))
    if report.tempo_drift_s > 0.02:
        drift_ms = f"{report.tempo_drift_s * 1000:.0f}"
        report.warnings.append(tr(
            f"o andamento é guardado em BPM inteiros: os compassos afastam-se até {drift_ms} ms "
            "dos tempos da partitura",
            f"tempo is stored as whole BPM: the bars move up to {drift_ms} ms from the "
            "score's times",
        ))
    report.warnings.append(tr(
        "o ficheiro tem só esta pista — outras pistas, formatação e letra do "
        "ficheiro original não são incluídas",
        "the file holds only this track — other tracks, formatting and lyrics "
        "of the original file are not included",
    ))

    dst.parent.mkdir(parents=True, exist_ok=True)
    with open(dst, "wb") as fh:
        guitarpro.write(song, fh, version=(5, 1, 0))
    return report
