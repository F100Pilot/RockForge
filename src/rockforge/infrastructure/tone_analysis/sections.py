"""Tone suggestions for the parts of each track (pure — no librosa, no I/O).

"sugestões para atribuir tons a partes específicas da música (track)". Two
sources, because neither alone can answer:

- **the recording** says how the guitars SOUND in each part (the per-window
  profile of the guitar stem, ``analyzer.window_profiles``) — but the stem is
  every guitar mixed together, so it cannot tell the Lead from the Rhythm;
- **the chart** says what each track PLAYS in that part — palm-muted chords,
  an open arpeggio left to ring, a solo of single high notes with bends — and
  that is what differs between two tracks playing over the same sound.

Per section and per track: its playing style + the recording's sound there →
a role (``clean``/``rhythm``/``lead``, or ``silent`` when the track does not
play) → the closest preset of that role's library, with the reasons and a
confidence the UI shows. A silent part keeps the tone before it; consecutive
parts with one tone merge; a track uses at most four tones (Rocksmith's slots
A-D, the base among them), the least-used folded into its nearest. Presets are chosen by
CHARACTER, like the whole-song detection: this proposes, it does not identify
the real amp.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rockforge.domain.music import TabNote, Technique
from rockforge.infrastructure.packaging.gear.tone_presets import preset_fingerprint, rank_role
from rockforge.infrastructure.tone_analysis.analyzer import WindowProfile

# Rocksmith switches only to the tones in slots A-D, so every tone a track
# uses — the base included, to switch back to it — has to fit in those four.
MAX_TONES = 4
CHORD_EPS = 0.005
BARS_PER_SEGMENT = 8  # parts for a chart without sections
# A part the recording barely covers (the guitar heard in less of it than this)
# gets the song's overall sound and a low confidence.
MIN_COVERAGE = 0.3

_LEAD_TECHNIQUES = frozenset({
    Technique.BEND, Technique.VIBRATO, Technique.SLIDE, Technique.HAMMER_ON,
    Technique.PULL_OFF, Technique.TAP,
})
_RING_TECHNIQUES = frozenset({Technique.LET_RING, Technique.HARMONIC})


@dataclass(frozen=True)
class Segment:
    name: str
    start: float  # bundle clock
    end: float


@dataclass(frozen=True)
class TrackChart:
    kind: str
    notes: list[TabNote]
    segments: list[Segment]


@dataclass(frozen=True)
class PlayStyle:
    """What a track plays in one part, as shares of its notes (0-1)."""

    notes: int
    chords: float = 0.0  # notes struck together with another
    palm_mute: float = 0.0
    lead: float = 0.0  # bends, vibrato, slides, hammer-ons/pull-offs, tapping
    high: float = 0.0  # fret 12 and up
    ring: float = 0.0  # let ring, harmonics
    density: float = 0.0  # notes per second


@dataclass(frozen=True)
class Reason:
    code: str  # chords, palm_mute, lead, high, ring, gain, no_audio
    value: float = 0.0


@dataclass(frozen=True)
class SegmentSuggestion:
    name: str
    start: float
    end: float
    role: str  # clean / rhythm / lead / silent
    tone_key: str | None
    tone_name: str | None
    match: int
    confidence: str  # high / medium / low
    reasons: list[Reason] = field(default_factory=list)
    gain: float = 0.0
    brightness: float = 0.0
    low_end: float = 0.0


@dataclass(frozen=True)
class TrackPlan:
    kind: str
    segments: list[SegmentSuggestion]
    base: str | None
    names: list[str]  # the tones in slots A-D, base first (every switch target)
    changes: list[tuple[float, str]]  # (bundle time, tone key)
    tones: list[dict[str, Any]]  # the gear definitions of those tones


def segments_for(
    sections: list[tuple[str, float]], bar_times: list[float], end: float
) -> list[Segment]:
    """A chart's parts: its sections, or groups of eight bars when it has fewer
    than two (a GP file without markers)."""
    marks = sorted((t, n) for n, t in sections if t < end)
    if len(marks) < 2:
        bars = sorted(t for t in bar_times if t < end)
        if not bars:
            return [Segment("1", 0.0, end)]
        marks = [
            (bars[i], str(i // BARS_PER_SEGMENT + 1))
            for i in range(0, len(bars), BARS_PER_SEGMENT)
        ]
    out: list[Segment] = []
    for i, (t, name) in enumerate(marks):
        stop = marks[i + 1][0] if i + 1 < len(marks) else end
        if stop > t:
            out.append(Segment(name, t, stop))
    return out


def play_style(notes: list[TabNote], seconds: float) -> PlayStyle:
    if not notes:
        return PlayStyle(notes=0)
    n = len(notes)
    times = sorted(x.time for x in notes)
    in_chord = 0
    for i, t in enumerate(times):
        before = i > 0 and t - times[i - 1] < CHORD_EPS
        after = i + 1 < n and times[i + 1] - t < CHORD_EPS
        if before or after:
            in_chord += 1
    return PlayStyle(
        notes=n,
        chords=in_chord / n,
        palm_mute=sum(Technique.PALM_MUTE in x.techniques for x in notes) / n,
        lead=sum(bool(x.techniques & _LEAD_TECHNIQUES) for x in notes) / n,
        high=sum(x.fret >= 12 for x in notes) / n,
        ring=sum(bool(x.techniques & _RING_TECHNIQUES) for x in notes) / n,
        density=n / seconds if seconds > 0 else 0.0,
    )


def audio_in(
    windows: list[WindowProfile], pad_s: float, start: float, end: float
) -> tuple[float, float, float, float] | None:
    """The recording's (gain, brightness, low end, coverage) over a part given in
    the bundle clock (the recording sits ``pad_s`` later there), or None when
    the analysis has no window there at all."""
    inside = [w for w in windows if start <= w.t + pad_s < end]
    if not inside:
        return None
    active = [w for w in inside if w.active]
    coverage = len(active) / len(inside)
    use = active or inside
    k = len(use)
    return (
        sum(w.gain_level for w in use) / k,
        sum(w.brightness for w in use) / k,
        sum(w.low_end for w in use) / k,
        coverage,
    )


def choose_role(style: PlayStyle, gain: float) -> tuple[str, list[Reason]]:
    """The part's role from what the track plays and how it sounds, with why."""
    if style.notes == 0:
        return "silent", []
    reasons = [Reason("gain", round(gain, 2))]
    if gain < 0.22 or (style.ring >= 0.3 and style.palm_mute < 0.1 and gain < 0.45):
        if style.ring >= 0.3:
            reasons.append(Reason("ring", round(style.ring, 2)))
        return "clean", reasons
    if style.chords < 0.25 and (style.lead >= 0.15 or style.high >= 0.4):
        if style.lead >= 0.15:
            reasons.append(Reason("lead", round(style.lead, 2)))
        if style.high >= 0.4:
            reasons.append(Reason("high", round(style.high, 2)))
        return "lead", reasons
    if style.chords >= 0.25:
        reasons.append(Reason("chords", round(style.chords, 2)))
    if style.palm_mute >= 0.2:
        reasons.append(Reason("palm_mute", round(style.palm_mute, 2)))
    return "rhythm", reasons


def _target(
    role: str, style: PlayStyle, gain: float, bright: float, low: float
) -> tuple[float, float, float]:
    """The sound to look for: the recording's, nudged by what the part plays."""
    if role == "clean":
        return min(gain, 0.18), bright, low
    if role == "lead":
        # A solo line usually sits on a hotter, brighter tone than the rhythm under it.
        return min(1.0, gain + 0.05), min(1.0, bright + 0.08 * (style.high >= 0.4)), low
    if style.palm_mute >= 0.35:  # a chugged part wants tighter, heavier lows
        return min(1.0, gain + 0.05), bright, min(1.0, low + 0.12)
    return gain, bright, low


def _suggest(seg: Segment, notes: list[TabNote], windows: list[WindowProfile], pad_s: float,
             song: tuple[float, float, float]) -> SegmentSuggestion:
    style = play_style(notes, seg.end - seg.start)
    heard = audio_in(windows, pad_s, seg.start, seg.end)
    if heard is None or heard[3] < MIN_COVERAGE:
        gain, bright, low = song
        coverage = heard[3] if heard else 0.0
    else:
        gain, bright, low, coverage = heard
    role, reasons = choose_role(style, gain)
    if role == "silent":
        return SegmentSuggestion(seg.name, seg.start, seg.end, role, None, None, 0, "low")
    if coverage < MIN_COVERAGE:
        reasons.append(Reason("no_audio"))
    library = "lead" if role == "lead" or (role == "clean" and style.chords < 0.25) else "rhythm"
    best = rank_role(library, *_target(role, style, gain, bright, low))[0]
    if coverage < MIN_COVERAGE:
        confidence = "low"
    elif coverage >= 0.6 and style.notes >= 8:
        confidence = "high"
    else:
        confidence = "medium"
    return SegmentSuggestion(
        seg.name, seg.start, seg.end, role, str(best["key"]), str(best.get("name", best["key"])),
        int(best.get("match", 0)), confidence, reasons,
        round(gain, 3), round(bright, 3), round(low, 3),
    )


def _distance(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return sum((x - y) ** 2 for x, y in zip(a, b, strict=True))


def _fold_tones(segs: list[SegmentSuggestion]) -> list[SegmentSuggestion]:
    """At most MAX_TONES distinct tones: the least-used (by time) becomes its
    nearest remaining preset, until the track fits Rocksmith's slots."""
    from dataclasses import replace

    while True:
        use: dict[str, float] = {}
        for s in segs:
            if s.tone_key:
                use[s.tone_key] = use.get(s.tone_key, 0.0) + (s.end - s.start)
        if len(use) <= MAX_TONES:
            return segs
        drop = min(use, key=lambda k: use[k])
        fp = preset_fingerprint(drop) or (0.5, 0.5, 0.5)
        keep = min(
            (k for k in use if k != drop),
            key=lambda k: _distance(fp, preset_fingerprint(k) or (0.5, 0.5, 0.5)),
        )
        name = next(s.tone_name for s in segs if s.tone_key == keep)
        segs = [
            replace(s, tone_key=keep, tone_name=name) if s.tone_key == drop else s
            for s in segs
        ]


def plan_track(chart: TrackChart, windows: list[WindowProfile], pad_s: float,
               song: tuple[float, float, float]) -> TrackPlan:
    notes = sorted(chart.notes, key=lambda n: n.time)
    segs: list[SegmentSuggestion] = []
    for seg in chart.segments:
        inside = [n for n in notes if seg.start <= n.time < seg.end]
        segs.append(_suggest(seg, inside, windows, pad_s, song))
    segs = _fold_tones(segs)
    # A part where the track rests keeps the tone before it (the first rests
    # take the first tone played): no switch in and out around a silence.
    played = [s.tone_key for s in segs if s.tone_key]
    current = played[0] if played else None
    changes: list[tuple[float, str]] = []
    order: list[str] = []
    for s in segs:
        if s.tone_key is None:
            continue
        if s.tone_key not in order:
            order.append(s.tone_key)
        if s.tone_key != current:
            changes.append((s.start, s.tone_key))
            current = s.tone_key
    base = played[0] if played else None
    tones: list[dict[str, Any]] = []
    for key in order:
        for library in ("lead", "rhythm"):
            found = next((t for t in rank_role(library, 0.5, 0.5, 0.5) if t["key"] == key), None)
            if found:
                tones.append({k: v for k, v in found.items() if k != "match"})
                break
    return TrackPlan(
        kind=chart.kind, segments=segs, base=base, names=order,
        changes=changes, tones=tones,
    )


def plan_tones(windows: list[WindowProfile], pad_s: float, song: tuple[float, float, float],
               charts: list[TrackChart]) -> list[TrackPlan]:
    """A tone plan for every track: see the module docstring."""
    return [plan_track(c, windows, pad_s, song) for c in charts]
