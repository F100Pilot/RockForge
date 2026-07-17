"""GenerateFromGpUseCase — the high-fidelity alternative to the audio-ML path.

Notes/frets/techniques/tempo/sections come exactly from a GP3/GP4/GP5 file;
the recording is only normalized and packaged. Synchronization is the one thing
the GP file cannot know, so it is a single user-supplied number: offset_s = the
moment (seconds) at which the song's first note is actually heard in the
recording. The score (note/beat/section times) and the GP's measure-anchored
lyrics are shifted forward to land there, so note 0 lines up with where the
music starts; the recording itself is left untouched (its own intro provides the
lead-in). Crucially we do NOT pad the audio by offset_s as well — doing so would
move the music forward by the same amount and re-open the gap, which is the bug
that made the chart and audio drift apart.

The one exception is the minimum lead-in: DLC Builder's phrase generator needs
room before the first note for the count-in (it errors outright when content
starts at time 0). When offset_s is below MIN_LEAD_S we prepend just the
shortfall as silence so there is always room — see MIN_LEAD_S.
"""

from __future__ import annotations

import bisect
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from rockforge.application.ports import (
    AudioIngestor,
    AudioNormalizer,
    Packager,
    PackagingResult,
    VocalEvent,
)
from rockforge.domain.arrangement import (
    Arrangement,
    ArrangementKind,
    ConfidenceLabel,
    Section,
    SongMetadata,
    ToneChange,
)
from rockforge.domain.errors import IngestionError
from rockforge.domain.music import TabNote, Technique, Tuning, apply_sustain_gap
from rockforge.domain.tone import Tone
from rockforge.infrastructure.gpimport.parser import (
    GpSection,
    ParsedGpTrack,
    inspect_gp,
    parse_gp_track,
)
from rockforge.infrastructure.rsxml.vocals import (
    distribute_syllables,
    enforce_max_line_words,
    parse_lyrics,
)


@dataclass(frozen=True)
class PipelineResult:
    packaging: PackagingResult
    note_counts: dict[str, int]
    warnings: tuple[str, ...]
    # Lyrics extracted from a GP file (recording clock, i.e. un-padded), so the
    # worker can surface them in the "Letras" editor / tab viewer. Empty unless
    # GP-embedded lyrics were used (not when the user supplied LRC/editor rows).
    gp_lyrics: tuple[VocalEvent, ...] = ()

# Minimum lead-in before the first note. DLC Builder's PhraseGenerator inserts a
# count-in phrase before the arrangement content and fails ("no room for an empty
# phrase before the arrangement content starts") when content begins at time 0;
# EOF likewise advises a few seconds of silence at the start. When the user's
# sync point is below this, the shortfall is added as silence.
MIN_LEAD_S = 2.0


# Metrical ratios a beat tracker confuses the true pulse with — not just the
# octave (½/2) but also the triplet / compound-meter grid (⅓, ⅔, 3/2, 3). A
# GP file whose recording is the SAME song has a true tempo ratio near 1, so a
# detected tempo that lands 50% high (3/2) or a third off is almost always one
# of these grid confusions, NOT a real tempo difference. Including them lets the
# suggestion snap back to ~1.0 instead of proposing a bogus ×1.5 scale.
_TEMPO_METRICAL_FACTORS = (1 / 4, 1 / 3, 1 / 2, 2 / 3, 1.0, 3 / 2, 2.0, 3.0, 4.0)


def suggest_tempo_scale(gp_bpm: float, detected_bpm: float) -> float:
    """Metrically-corrected tempo_scale aligning the GP tempo to a detected one.

    Beat trackers routinely report a tempo at the wrong metrical level — an
    octave off (half/double) or on the triplet/compound grid (e.g. 1.5× the true
    pulse). Since the GP file and the recording are the same song, the true ratio
    is near 1, so we pick the metrical multiple of ``detected_bpm``
    (``_TEMPO_METRICAL_FACTORS``) whose resulting scale sits closest to 1.0 —
    fixing the "auto-sync jumps the BPM ~50%" case where only ½/1/2 were tried
    and a 3/2 detection had no nearby octave to snap to.
    ``tempo_scale = gp_bpm / effective_recording_bpm`` because the GP timeline is
    stretched/compressed to the recording's tempo (parser scales the effective BPM
    inversely). Used both for whole-song sync and for a local re-tempo from a point.
    """
    if gp_bpm <= 0 or detected_bpm <= 0:
        raise IngestionError("gp_bpm and detected_bpm must be positive to suggest a tempo")
    candidates = [detected_bpm * f for f in _TEMPO_METRICAL_FACTORS]
    best = min(candidates, key=lambda b: abs((gp_bpm / b) - 1.0))
    return gp_bpm / best


def suggest_sync(
    gp_bpm: float, detected_bpm: float, first_onset_s: float
) -> tuple[float, float]:
    """Propose (tempo_scale, offset_s) aligning the GP chart to a recording.

    ``offset_s`` is where audible content begins in the recording — the second the
    first note should be heard. This is a *suggestion*: the user reviews it in the
    tab viewer before rebuilding, never silently applied.
    """
    return suggest_tempo_scale(gp_bpm, detected_bpm), max(0.0, first_onset_s)


def align_chart_to_recording(
    gp_beats: list[float],
    rec_beats: list[float],
    chart_onsets: list[float],
    rec_onsets: list[float],
    *,
    chart_start: float,
    rec_start: float,
    stride: int = 10,
    win: float = 0.12,
    rho_min: float = 0.75,
    rho_max: float = 1.30,
    ema: float = 0.25,
    corr_window: int = 10,
) -> list[tuple[float, float, float]]:
    """Map the chart onto the recording's real tempo curve, starting at the
    user's confirmed first note. Returns ``(chart_time, recording_time,
    confidence)`` anchors the tab viewer previews — never applied silently.

    The alignment is driven by ONSET CORRESPONDENCE, not by integrating the beat
    tracker's grid. Walking the chart's own note onsets in order, each is
    *predicted* into the recording at the running tempo ratio ``rho`` (recording
    seconds per chart second) and *snapped* to the nearest real attack within
    ``±win``; the accepted (chart, recording) pairs are the drift curve. ``rho``
    starts at **1.0** — the authored tempo the user's pin already confirmed — and
    is nudged toward the robust (Theil–Sen) slope of the recent correspondences,
    clamped to ``[rho_min, rho_max]`` and EMA-smoothed. This is deliberate: the
    beat tracker's *tempo* is biased (it read ~184 BPM on a genuine 175 BPM song),
    so integrating its intervals over-compressed the opening — the chart rushed
    ahead from the very first bar. Deriving tempo from actual chart↔recording
    onset matches instead keeps the opening at the authored tempo and still tracks
    real mid-song drift, because the correspondences themselves move with it.

    Roles of the four inputs:

    - ``chart_onsets`` vs ``rec_onsets`` (the notes the tab HAS vs the attacks
      the audio HAS) are the primary signal: they set both the phase (the snap)
      and the local tempo (the recent-correspondence slope). ``win`` is a short
      leash so a repeated riff can't pull a match onto a neighbouring repetition.
    - ``rec_beats`` (the beat tracker's grid) is only a TEMPO PRIOR for
      note-sparse passages: where the chart has too few onsets to estimate a
      slope, ``rho`` relaxes toward the recording's local beat-interval tempo
      (vs the chart's own local beat interval) rather than freezing. Its beat
      *count* is never trusted (a missed/doubled beat would slip a 1:1 mapping).
    - ``chart_start``/``rec_start`` (the user's Step-1 pin) fix the absolute
      position: the first anchor is the pin verbatim, so replacing the pending
      anchors preserves it, and the whole curve grows from there.

    Each anchor's ``confidence`` is the fraction of the surrounding chart onsets
    (±4 s) that snapped to a real attack. Low confidence flags a span where the
    tab does not correspond to the audio (wrong notes / extra or missing bars) —
    no time-warp can fix content, so the UI surfaces those ranges for the user to
    fix in Guitar Pro instead; the anchor there keeps its predicted position.

    Validated against a real AI-generated song (200 s, tempo drifting 175→191 BPM
    with an intro absent from the tab): the opening now holds ~175.8 BPM (was
    ~172 with the old beat-integration) and the per-20 s median onset error drops
    to ~10–20 ms (was 30–60 ms), while its genuinely-mismatched tab sections stay
    flagged with confidence < 0.5. Honest limit: anchors in flagged spans are
    best-effort interpolation; refine by ear or fix the tab there.
    """
    import bisect

    gpb = sorted(gp_beats)
    rbt = sorted(rec_beats)
    co = [c for c in sorted(set(chart_onsets)) if c >= chart_start - 1e-9]
    ro = sorted(rec_onsets)
    if len(gpb) < 2 or len(rbt) < 2:
        return []

    def _local(mids: list[float], ints: list[float], fb: float, x: float) -> float:
        """Local median interval (±7) of a beat grid at position ``x``."""
        i = bisect.bisect_left(mids, x)
        lo, hi = max(0, i - 7), min(len(ints), i + 8)
        seg = sorted(ints[lo:hi])
        return seg[len(seg) // 2] if seg else fb

    r_int = [rbt[i + 1] - rbt[i] for i in range(len(rbt) - 1)]
    r_mid = [(rbt[i] + rbt[i + 1]) / 2 for i in range(len(rbt) - 1)]
    g_int = [gpb[i + 1] - gpb[i] for i in range(len(gpb) - 1)]
    g_mid = [(gpb[i] + gpb[i + 1]) / 2 for i in range(len(gpb) - 1)]
    r_fb = sorted(r_int)[len(r_int) // 2]
    g_fb = sorted(g_int)[len(g_int) // 2]

    def rec_tempo_ratio(chart_t: float, rec_t: float) -> float:
        """The recording's local tempo relative to the chart's (the beat-prior
        used only when onset correspondences run out)."""
        g = _local(g_mid, g_int, g_fb, chart_t)
        return _local(r_mid, r_int, r_fb, rec_t) / g if g > 1e-6 else 1.0

    def theil_sen(pts: list[tuple[float, float]]) -> float:
        slopes = [
            (pts[j][1] - pts[i][1]) / (pts[j][0] - pts[i][0])
            for i in range(len(pts))
            for j in range(i + 1, len(pts))
            if pts[j][0] - pts[i][0] > 1e-6
        ]
        return sorted(slopes)[len(slopes) // 2] if slopes else 1.0

    k0 = min(range(len(gpb)), key=lambda k: abs(gpb[k] - chart_start))

    # Walk the chart onsets, snapping each to the nearest real attack; the
    # accepted pairs are the drift curve. ``matched`` records which onsets found
    # an attack (for per-anchor confidence).
    corr: list[tuple[float, float]] = [(chart_start, rec_start)]
    matched: list[tuple[float, bool]] = []
    last_c, last_r, rho = chart_start, rec_start, 1.0
    recent: list[tuple[float, float]] = [(chart_start, rec_start)]
    for c in co:
        r_pred = last_r + rho * (c - last_c)
        i = bisect.bisect_left(ro, r_pred)
        cand = [ro[j] for j in (i - 1, i) if 0 <= j < len(ro) and abs(ro[j] - r_pred) <= win]
        if cand:
            r_val = min(cand, key=lambda x: abs(x - r_pred))
            matched.append((c, True))
            recent.append((c, r_val))
            if len(recent) > corr_window:
                recent.pop(0)
            target = theil_sen(recent) if len(recent) >= 4 else rho
            rho = (1 - ema) * rho + ema * max(rho_min, min(rho_max, target))
        else:
            matched.append((c, False))
            # No attack to lock onto: relax the tempo toward the recording's own
            # beat grid so a note-sparse passage still follows its drift, then
            # carry the prediction forward onto the drift curve (so a whole section
            # without matchable onsets — or a recording the onset detector yielded
            # nothing for — still tracks the beat grid rather than collapsing to a
            # flat identity between matched points).
            prior = max(rho_min, min(rho_max, rec_tempo_ratio(c, r_pred)))
            rho = (1 - 0.05) * rho + 0.05 * prior
            r_val = r_pred
        last_c, last_r = c, r_val
        # Only extend the curve when chart time strictly advances (the first
        # onset can coincide with the pinned chart_start) — a duplicate x would
        # make the piecewise slope divide by zero.
        if c > corr[-1][0] + 1e-9:
            corr.append((c, r_val))

    if not any(ok for _, ok in matched):
        # No onset correspondence anywhere (the chart has no matchable notes, or
        # the onset detector returned nothing): there is no phase signal to derive
        # tempo from, so fall back to the beat prior — walk the chart beats,
        # advancing by the recording's local beat interval (median-robust to a
        # missed/doubled tracker beat) so the drift still follows the recording's
        # tempo grid instead of collapsing to a flat identity.
        r = rec_start
        corr = [(chart_start, rec_start)]
        for idx in range(k0 + 1, len(gpb)):
            c = gpb[idx]
            r += _local(r_mid, r_int, r_fb, r)
            if c > corr[-1][0] + 1e-9:
                corr.append((c, r))

    xs = [p[0] for p in corr]
    ys = [p[1] for p in corr]

    def interp(t: float) -> float:
        k = bisect.bisect_right(xs, t)
        if k <= 0:
            return ys[0] + (t - xs[0])
        if k >= len(xs):
            dx = xs[-1] - xs[-2] if len(xs) >= 2 else 0.0
            s = (ys[-1] - ys[-2]) / dx if dx > 1e-9 else 1.0
            return ys[-1] + s * (t - xs[-1])
        dx = xs[k] - xs[k - 1]
        s = (ys[k] - ys[k - 1]) / dx if dx > 1e-9 else 1.0
        return ys[k - 1] + s * (t - xs[k - 1])

    anchors: list[tuple[float, float, float]] = [(chart_start, rec_start, 1.0)]
    for idx in range(k0 + stride, len(gpb), stride):
        c = gpb[idx]
        r = interp(c)
        near = [m for m in matched if c - 4.0 <= m[0] < c + 4.0]
        conf = sum(1 for _, ok in near if ok) / len(near) if near else 0.0
        if c > anchors[-1][0] and r > anchors[-1][1]:
            anchors.append((c, r, conf))
    return anchors


def align_chart_to_midi(
    gp_bars: list[float],
    midi_measures: list[float],
    *,
    chart_start: float,
    rec_start: float,
    stride: int = 1,
) -> list[tuple[float, float, float]]:
    """Align the chart to a MIDI tempo map — the ground-truth alternative to the
    librosa estimate of :func:`align_chart_to_recording`. Returns the same
    ``(chart_time, recording_time, confidence)`` anchors the tab viewer previews.

    ``gp_bars`` are the chart's measure-downbeat times (the ebeats with a real
    measure number); ``midi_measures`` are the recording-second times of each
    measure downbeat read from the MIDI (``parse_midi_tempo``). One anchor per
    measure makes every bar play at its own real tempo — literally the "BPM por
    compasso" the MIDI carries — instead of one averaged tempo.

    The user's Step-1 pin (``chart_start``/``rec_start``) fixes the absolute
    position: the first anchor is the pin verbatim, the chart's pinned measure is
    taken to be the MIDI's first measure, and each later bar is placed at
    ``rec_start`` plus that measure's elapsed time in the MIDI (a *relative*
    offset, so it works whether the MIDI clock is absolute to the recording or
    starts at its own zero). ``confidence`` is 1.0: the MIDI is user-provided
    ground truth, not an estimate, so no span is flagged weak.

    Honest limit: the MIDI must begin at the tab's first measure (trim any
    recording intro the tab does not transcribe), and the two must share a
    measure structure — where the tab has extra/missing bars the mapping drifts
    there (the tab is wrong, not the warp). Preview-only, never applied silently.
    """
    bars = sorted(gp_bars)
    mm = sorted(midi_measures)
    if len(bars) < 1 or len(mm) < 2:
        return []
    # The chart measure the pin sits in = the MIDI's first measure.
    b0 = max((i for i, t in enumerate(bars) if t <= chart_start + 1e-9), default=0)
    anchors: list[tuple[float, float, float]] = [(chart_start, rec_start, 1.0)]
    for b in range(b0 + stride, len(bars), stride):
        d = b - b0
        if d >= len(mm):
            break
        c = bars[b]
        r = rec_start + (mm[d] - mm[0])
        if c > anchors[-1][0] and r > anchors[-1][1]:
            anchors.append((c, r, 1.0))
    return anchors


def align_bars_to_downbeats(
    bars: list[float],
    downbeats: list[float],
    *,
    chart_start: float,
    rec_start: float,
) -> tuple[list[tuple[float, float, float]], list[tuple[float, float]]]:
    """Align a chart's measure downbeats to a detected/recorded downbeat grid by
    TIME correspondence (predict + snap) — tolerant of a DIFFERENT measure/meter
    structure, unlike the 1:1 index mapping of :func:`align_chart_to_midi`.

    Many AI/DAW tabs notate a song with a different bar structure than a drum
    tracker (or a DAW) reads — e.g. a lot of 2/4 bars where the drums read a
    steady 4/4 — so tab bar N does NOT correspond to detected downbeat N and the
    index mapping drifts wildly (a real case measured +58 s of error by bar 113).
    Here each tab bar (after the pin) is PREDICTED into the recording at the
    global tempo ratio and SNAPPED to the nearest detected downbeat within a
    window, with a monotonic guard keeping each downbeat used once: where the tab
    has more bars than the recording has measures, the extra (e.g. 2/4) bars find
    no free downbeat and are skipped, riding the interpolation between the anchors
    that did match. The result follows the recording's real (locally varying)
    tempo instead of one average.

    Returns ``(anchors, weak_spans)``: ``anchors`` are ``(chart, recording, 1.0)``
    triples (the pin first); ``weak_spans`` are chart-time ranges of >= 3
    consecutive UNMATCHED bars — a genuine structure mismatch (wrong/missing bars
    in the tab), distinct from the odd single skipped odd-meter bar.
    """
    bars = sorted(b for b in bars if b >= chart_start - 1e-9)
    db = sorted(downbeats)
    if len(bars) < 2 or len(db) < 2:
        return [(chart_start, rec_start, 1.0)], []
    span_c = bars[-1] - chart_start
    ratio = ((db[-1] - rec_start) / span_c) if span_c > 1e-9 else 1.0
    med = sorted(db[i + 1] - db[i] for i in range(len(db) - 1))[len(db) // 2]
    win = 0.6 * med

    anchors: list[tuple[float, float, float]] = [(chart_start, rec_start, 1.0)]
    weak_spans: list[tuple[float, float]] = []
    skip_run: list[float] = []

    def _flush() -> None:
        if len(skip_run) >= 3:
            weak_spans.append((skip_run[0], skip_run[-1]))
        skip_run.clear()

    for c in bars:
        if c <= chart_start + 1e-9:
            continue
        pred = rec_start + (c - chart_start) * ratio
        lo = bisect.bisect_left(db, pred)
        cand = [db[i] for i in (lo, lo - 1) if 0 <= i < len(db)]
        d = min(cand, key=lambda x: abs(x - pred))
        if abs(d - pred) <= win and c > anchors[-1][0] + 1e-6 and d > anchors[-1][1] + 1e-6:
            anchors.append((c, d, 1.0))
            _flush()
        else:
            skip_run.append(c)
    _flush()
    return anchors, weak_spans


@dataclass(frozen=True)
class ArrangementSync:
    """Per-arrangement chart-timing overrides (tempo + drift anchors).

    These only touch one arrangement's own note/beat/section/lyric times, so
    dragging a note in the Lead chart never moves the Rhythm chart. The sync
    *offset* is deliberately NOT here: all arrangements share one audio track,
    so where the recording starts is a property of the recording, shared by
    every arrangement (a per-arrangement offset would desync the charts from
    each other against the same .wem). Per-arrangement uniform shifts are still
    available as a single-anchor round.
    """

    tempo_scale: float = 1.0
    sync_anchor_stages: list[list[tuple[float, float]]] = field(default_factory=list)


@dataclass(frozen=True)
class NoteOverride:
    """One in-app note-editor edit: upserts a note at (time, string), or
    deletes the note already there when ``deleted`` is True (the other fields
    are then ignored). Bundle-clock time, like tone_changes/section_overrides
    — the note editor places these directly on the already-warped score, so
    no extra per-arrangement time-warp is applied to them."""

    time: float
    string: int
    fret: int = 0
    sustain: float = 0.0
    techniques: frozenset[Technique] = field(default_factory=frozenset)
    bend_semitones: float = 0.0
    slide_to_fret: int | None = None
    deleted: bool = False


def _apply_note_overrides(
    notes: list[TabNote], overrides: list[NoteOverride]
) -> list[TabNote]:
    """Merge in-app note edits on top of the GP-parsed notes.

    Keyed by (time, string) — an override either replaces the note already at
    that exact position (upsert) or removes it (deleted=True). Not applied
    inside _warp_parsed_track: overrides are placed by the user on the
    ALREADY-warped score, so they land directly in the final coordinate space
    rather than needing to be warped again.
    """
    by_key: dict[tuple[float, int], TabNote] = {
        (round(n.time, 6), n.string): n for n in notes
    }
    for ov in overrides:
        key = (round(ov.time, 6), ov.string)
        if ov.deleted:
            by_key.pop(key, None)
        else:
            by_key[key] = TabNote(
                string=ov.string,
                fret=ov.fret,
                time=ov.time,
                sustain=ov.sustain,
                techniques=ov.techniques,
                bend_semitones=ov.bend_semitones,
                slide_to_fret=ov.slide_to_fret,
            )
    return sorted(by_key.values(), key=lambda n: (n.time, n.string))


@dataclass(frozen=True)
class GpJobSpec:
    gp_path: Path
    audio_source: str
    # Each arrangement is an OPTIONAL, independently-assigned slot: the user maps a
    # GP track to it (or leaves it empty). Nothing is auto-generated — the song
    # gets exactly the arrangements assigned here. When ALL are empty, tracks are
    # auto-picked as a convenience (lead+rhythm, or a lone track → Combined).
    lead_track: int | None = None
    rhythm_track: int | None = None
    combo_track: int | None = None
    # Optional SECOND Lead/Rhythm charts from other GP tracks — produced as
    # non-representative "Alternate" arrangements the player can pick in game.
    alt_lead_track: int | None = None
    alt_rhythm_track: int | None = None
    offset_s: float = 0.0  # second in the recording where the song's first note is heard
    # Extra silence (seconds) prepended at the very start, on top of the
    # automatic MIN_LEAD_S lead-in — user-controlled "intro silence" that pushes
    # the whole bundle (audio + notes + lyrics) later together. 0 = none.
    lead_in_s: float = 0.0
    # Multiplicative stretch (>1) / compression (<1) of the whole musical
    # timeline, applied at parse time around the song's start — corrects a
    # constant GP-vs-recording tempo mismatch (the linear part of sync drift)
    # in one move, before any sync_anchor_stages fine-tuning. Used as the
    # default for arrangements without an explicit arrangement_sync override.
    tempo_scale: float = 1.0
    lrc_text: str | None = None
    tone_base: str | None = None
    tone_names: list[str] = field(default_factory=list)
    tone_changes: list[ToneChange] = field(default_factory=list)
    # Full gear definitions for the referenced tones (built in the tone editor).
    # When present they are serialized into the .rs2dlc so the tones work in-game;
    # tone_base/tone_names reference these by key.
    tones: list[Tone] = field(default_factory=list)
    # Manual drift-correction rounds. Each round is a list of (chart_time_s,
    # corrected_time_s) anchor pairs, expressed in the timeline produced by the
    # *previous* round (i.e. as shown in the tab viewer at the time the user
    # drew them) — round 0 is in the raw post-offset_s timeline. Rounds are
    # applied in order via piecewise-linear stretch/compress, so corrections
    # made in separate sessions (after reloading a completed job) compose
    # correctly instead of overwriting each other. Default for arrangements
    # without an explicit arrangement_sync override.
    sync_anchor_stages: list[list[tuple[float, float]]] = field(default_factory=list)
    # Per-arrangement tempo + drift overrides, keyed by ArrangementKind.value
    # ("Lead"/"Rhythm"/"Combined"). An arrangement absent here falls back to the
    # job-level tempo_scale / sync_anchor_stages above.
    arrangement_sync: dict[str, ArrangementSync] = field(default_factory=dict)
    # When False, the mute/attack techniques (palm mute, slap, pop, tap) are
    # stripped from every note so they import as plain notes. These are the
    # techniques that change the Rocksmith note sprite (the palm-mute chevron
    # looks like pop/slap "wings"); some GP files mark them where the user wants
    # clean notes, so this is an opt-out.
    import_mute_techniques: bool = True
    # Edited per-word lyrics from the in-app lyrics editor (recording-clock
    # times, before pad_start_s). Takes precedence over lrc_text and GP-embedded
    # lyrics when present.
    lyrics_events: list[VocalEvent] | None = None
    # Optional cover-art image (jpg/png), copied into the bundle and recorded
    # in rockforge_project.json; see Packager.package's cover_art parameter.
    cover_art: Path | None = None
    # When False, the native PSARC's SNG is built with a single full-chart level
    # (no Dynamic Difficulty) — a safety valve for songs where DD misbehaves.
    dynamic_difficulty: bool = True
    # Per-arrangement tuning override, keyed by ArrangementKind.value → the six
    # MIDI pitches (low to high). An arrangement absent here keeps the tuning read
    # from its GP track. Lets the user re-tune an arrangement in the song settings
    # without touching the GP file.
    tuning_overrides: dict[str, tuple[int, int, int, int, int, int]] = field(
        default_factory=dict
    )
    # In-app section-editor overrides (bundle-clock times, like tone_changes —
    # no per-arrangement warp applied). When set (even to an empty list),
    # REPLACES the GP-parsed section markers for EVERY arrangement; None keeps
    # each arrangement's own GP-authored sections untouched.
    section_overrides: list[Section] | None = None
    # In-app note-editor edits, keyed by ArrangementKind.value — unlike
    # tone_changes/section_overrides these are genuinely per-arrangement (Lead
    # and Rhythm have entirely different note content), so each kind's list is
    # independent; an arrangement absent here (or with an empty list) is
    # completely unaffected. Applied AFTER parsing/warp/mute-stripping, so the
    # user always edits the FINAL note set, and a manual edit is never
    # silently stripped by import_mute_techniques=False.
    note_overrides: dict[str, list[NoteOverride]] = field(default_factory=dict)

    def sync_for(self, kind: ArrangementKind) -> ArrangementSync:
        """Resolve the tempo/drift overrides for one arrangement, falling back
        to the job-level defaults when no per-arrangement entry exists."""
        override = self.arrangement_sync.get(kind.value)
        if override is not None:
            return override
        return ArrangementSync(
            tempo_scale=self.tempo_scale, sync_anchor_stages=self.sync_anchor_stages
        )



# Techniques that alter the in-game note sprite (chevron/"wings"); dropped when
# import_mute_techniques is False.
_MUTE_TECHNIQUES = frozenset(
    {Technique.PALM_MUTE, Technique.SLAP, Technique.POP, Technique.TAP}
)


def _build_time_warp(anchors: list[tuple[float, float]]) -> Callable[[float], float]:
    """Piecewise-linear remap built from (chart_time, corrected_time) points.

    A single anchor is a uniform shift applied everywhere (e.g. "the whole
    song's lead-in is off by X"). With two or more anchors (an excerpt drag),
    notes outside the anchor range are left untouched (identity) — only the
    excerpt between the first and last anchor is rigidly shifted/stretched;
    notes before/after it keep their original position.
    """
    if not anchors:
        return lambda t: t
    pts = sorted(anchors, key=lambda p: p[0])

    def warp(t: float) -> float:
        if len(pts) == 1:
            x0, y0 = pts[0]
            return t + (y0 - x0)
        if t < pts[0][0]:
            return t
        if t > pts[-1][0]:
            return t
        (x0, y0), (x1, y1) = next(
            (a, b) for a, b in zip(pts, pts[1:], strict=False) if a[0] <= t <= b[0]
        )
        if x1 == x0:
            return t + (y0 - x0)
        return y0 + (y1 - y0) * (t - x0) / (x1 - x0)

    return warp


def _check_anchor_order(anchors: list[tuple[float, float]]) -> None:
    """Reject a round of sync anchors whose corrected times contradict their
    chart-time order (e.g. a later note anchored to an earlier recording instant
    than an earlier note) — such a pair makes ``_build_time_warp`` fold back on
    itself, warping the beat grid out of chronological order and crashing deep
    inside ``TempoMap`` with no clue which correction caused it. Two clicks of
    "Mover seguintes" that both touch the arrangement's last note (each anchoring
    it at a different moment) are the usual way to create this by accident.

    Also rejects two anchors sharing the EXACT SAME chart time but anchored to
    different recording instants: the strict ``x1 > x0`` comparison below skips
    a tied pair entirely, so that contradiction previously passed validation
    unnoticed and ``_build_time_warp`` silently picked whichever of the two
    matched first in its scan — exactly the "warped into nonsense" outcome this
    check exists to prevent.
    """
    pts = sorted(anchors, key=lambda p: p[0])
    for (x0, y0), (x1, y1) in zip(pts, pts[1:], strict=False):
        if x1 == x0:
            if y1 != y0:
                raise IngestionError(
                    "sync corrections conflict: two corrections both anchor "
                    f"chart time {x0:.2f}s, but to different recording instants "
                    f"({y0:.2f}s and {y1:.2f}s). Remove or adjust one of "
                    "these corrections (check the pending anchors list)."
                )
            continue
        if y1 < y0:
            raise IngestionError(
                "sync corrections conflict: the point at "
                f"{x1:.2f}s (chart time) is anchored to {y1:.2f}s, which is BEFORE "
                f"the point at {x0:.2f}s anchored to {y0:.2f}s — later chart time "
                "cannot land earlier in the recording. Remove or adjust one of "
                "these corrections (check the pending anchors list)."
            )


def _strip_mute_techniques(p: ParsedGpTrack) -> ParsedGpTrack:
    """Return a copy of the track with palm mute / slap / pop / tap removed."""
    notes = [
        TabNote(
            string=n.string, fret=n.fret, time=n.time, sustain=n.sustain,
            techniques=frozenset(n.techniques - _MUTE_TECHNIQUES),
            bend_semitones=n.bend_semitones, slide_to_fret=n.slide_to_fret,
        )
        if n.techniques & _MUTE_TECHNIQUES else n
        for n in p.notes
    ]
    return ParsedGpTrack(
        notes=notes, tuning=p.tuning, tempo_map=p.tempo_map,
        sections=p.sections, lyrics=p.lyrics,
    )


def _warp_parsed_track(p: ParsedGpTrack, warp: Callable[[float], float]) -> ParsedGpTrack:
    """Apply a time remap to every timestamp of a parsed track (notes, beats, sections, lyrics).

    A sync correction can locally stretch the timeline (a chart interval mapped
    to a wider corrected interval): a note's warped sustain scales by that same
    local factor, which can re-inflate — or even exceed — a sustain that
    ``apply_sustain_gap`` already trimmed to a small gap at parse time (the
    "tall sustain pillars"/fused chord boxes bug, first fixed for the un-warped
    timeline in 4147d89). Re-applying the gap AFTER warping restores the
    invariant regardless of what the correction did to the local tempo.
    """
    from rockforge.domain.music import Beat, TempoMap

    notes = apply_sustain_gap([
        TabNote(
            string=n.string, fret=n.fret, time=warp(n.time),
            sustain=max(0.0, warp(n.time + n.sustain) - warp(n.time)),
            techniques=n.techniques, bend_semitones=n.bend_semitones,
            slide_to_fret=n.slide_to_fret,
        )
        for n in p.notes
    ])
    beats = tuple(Beat(time=warp(b.time), measure=b.measure) for b in p.tempo_map.beats)
    sections = [GpSection(name=s.name, start_time=warp(s.start_time)) for s in p.sections]
    lyrics = [type(line)(time=warp(line.time), text=line.text) for line in p.lyrics]
    return ParsedGpTrack(
        notes=notes,
        tuning=p.tuning,
        tempo_map=TempoMap(
            beats=beats,
            average_bpm=p.tempo_map.average_bpm,
            beats_per_measure=p.tempo_map.beats_per_measure,
        ),
        sections=sections,
        lyrics=lyrics,
    )


def auto_pick_tracks(gp_path: Path) -> tuple[int | None, int | None]:
    """Heuristic track selection by name when the user does not choose.

    Returns (lead, rhythm); falls back to the first 6-string non-percussion
    track as a combined arrangement (rhythm slot left None).
    """
    info = inspect_gp(gp_path)
    eligible = [t for t in info.tracks if not t.is_percussion and t.string_count == 6]
    if not eligible:
        return None, None
    lead = next((t.index for t in eligible if "lead" in t.name.lower()), None)
    rhythm = next((t.index for t in eligible if "rhythm" in t.name.lower()), None)
    if lead is None and rhythm is None:
        return eligible[0].index, None
    return lead, rhythm


@dataclass
class GenerateFromGpUseCase:
    ingestor: AudioIngestor
    normalizer: AudioNormalizer
    packager: Packager

    def run(
        self,
        spec: GpJobSpec,
        metadata: SongMetadata,
        workdir: Path,
        on_stage: Callable[[str], None] | None = None,
    ) -> PipelineResult:
        def stage(name: str) -> None:
            if on_stage is not None:
                on_stage(name)

        if spec.offset_s < 0.0:
            raise IngestionError(
                "sync offset must be >= 0 — it is the second in the recording where the "
                "song starts, never a negative time"
            )

        warnings: list[str] = []
        # Place the first note at the recording's music start (offset_s); pad only
        # the shortfall up to MIN_LEAD_S so the count-in phrase always has room.
        # The score shifts by the full content time; the audio (and thus an LRC
        # synced to it) shifts only by what silence we actually prepend.
        pad_start_s = max(0.0, MIN_LEAD_S - spec.offset_s) + max(0.0, spec.lead_in_s)
        score_shift = spec.offset_s + pad_start_s  # max(offset_s, MIN_LEAD_S) + lead_in_s

        stage("ingest")
        raw = self.ingestor.fetch(spec.audio_source, workdir)
        stage("normalize")
        normalized = self.normalizer.normalize(raw, workdir, pad_start_s=pad_start_s)

        stage("parse_gp")
        # Explicit per-arrangement track assignment: each slot the user filled maps
        # its track to that arrangement kind, verbatim. Combo is a first-class slot,
        # not derived. Only when NOTHING is assigned do we auto-pick a sensible
        # default (lead+rhythm, or a lone track → Combined).
        slots: list[tuple[ArrangementKind, int | None]] = [
            (ArrangementKind.LEAD, spec.lead_track),
            (ArrangementKind.RHYTHM, spec.rhythm_track),
            (ArrangementKind.COMBINED, spec.combo_track),
            (ArrangementKind.ALTERNATE_LEAD, spec.alt_lead_track),
            (ArrangementKind.ALTERNATE_RHYTHM, spec.alt_rhythm_track),
        ]
        if all(idx is None for _, idx in slots):
            lead_idx, rhythm_idx = auto_pick_tracks(spec.gp_path)
            if lead_idx is None and rhythm_idx is None:
                raise IngestionError("no eligible 6-string guitar track found in the GP file")
            warnings.append(
                "tracks auto-selected by name heuristic — confirm they are the right ones"
            )
            slots = [(ArrangementKind.LEAD, lead_idx), (ArrangementKind.RHYTHM, rhythm_idx)]

        tracks: list[tuple[ArrangementKind, int]] = [
            (kind, idx) for kind, idx in slots if idx is not None
        ]
        # A lone Lead (nothing else assigned) is a single all-in-one chart →
        # Combined, the conventional single-arrangement choice.
        if len(tracks) == 1 and tracks[0][0] is ArrangementKind.LEAD:
            tracks = [(ArrangementKind.COMBINED, tracks[0][1])]
        chosen = [idx for _, idx in tracks]
        if len(chosen) != len(set(chosen)):
            raise IngestionError("each arrangement must use a different GP track")

        # Each arrangement is parsed and drift-corrected independently with its
        # own tempo_scale / sync_anchor_stages, so corrections never leak
        # between charts. The offset (and thus the shared audio lead-in) is
        # common to all of them.
        parsed: dict[ArrangementKind, ParsedGpTrack] = {}
        for kind, idx in tracks:
            sync = spec.sync_for(kind)
            p = parse_gp_track(spec.gp_path, idx, score_shift, sync.tempo_scale)
            warnings.extend(f"{kind.value}: {w}" for w in p.warnings)
            for stage_anchors in sync.sync_anchor_stages:
                if not stage_anchors:
                    continue
                _check_anchor_order(stage_anchors)
                p = _warp_parsed_track(p, _build_time_warp(stage_anchors))
            parsed[kind] = p

            if sync.tempo_scale != 1.0:
                warnings.append(
                    f"{kind.value}: tempo scaled by {sync.tempo_scale:.3f}× "
                    f"({1.0 / sync.tempo_scale:.1%} of the GP tempo) to match the recording"
                )
            points = sum(len(s) for s in sync.sync_anchor_stages)
            if points:
                rounds = sum(1 for s in sync.sync_anchor_stages if s)
                warnings.append(
                    f"{kind.value}: {points} manual drift-correction point(s) across "
                    f"{rounds} round(s) applied to the chart"
                )

        if not spec.import_mute_techniques:
            stripped = sum(
                1 for p in parsed.values() for n in p.notes if n.techniques & _MUTE_TECHNIQUES
            )
            parsed = {kind: _strip_mute_techniques(p) for kind, p in parsed.items()}
            if stripped:
                warnings.append(
                    f"palm mute / slap / pop / tap removed from {stripped} note(s) on request "
                    "(imported as plain notes)"
                )

        for kind_value, note_ov in spec.note_overrides.items():
            match = next((k for k in parsed if k.value == kind_value), None)
            if match is None or not note_ov:
                continue
            p = parsed[match]
            parsed[match] = ParsedGpTrack(
                notes=_apply_note_overrides(p.notes, note_ov),
                tuning=p.tuning,
                tempo_map=p.tempo_map,
                sections=p.sections,
                lyrics=p.lyrics,
                warnings=p.warnings,
            )
            warnings.append(
                f"{kind_value}: {len(note_ov)} manual note edit(s) from the in-app editor applied"
            )

        stage("build_arrangements")
        first = next(iter(parsed.values()))
        song_length = (
            max(
                max((n.time + n.sustain for n in p.notes), default=0.0)
                for p in parsed.values()
            )
            + 1.0
        )
        metadata = SongMetadata(
            title=metadata.title,
            artist=metadata.artist,
            album=metadata.album,
            year=metadata.year,
            song_length=song_length,
        )
        confidence = {
            "notes": ConfidenceLabel.MEASURED,  # exact from the authored GP file
            "sync_offset": ConfidenceLabel.HEURISTIC,  # manual user offset
            "lyrics": ConfidenceLabel.HEURISTIC if not spec.lrc_text else ConfidenceLabel.MEASURED,
        }
        def _tuning_for(kind: ArrangementKind, parsed_tuning: Tuning) -> Tuning:
            override = spec.tuning_overrides.get(kind.value)
            if override is None or len(override) != 6:
                return parsed_tuning
            return Tuning(midi=override, cent_offset=parsed_tuning.cent_offset)

        # Section-editor overrides replace the GP-parsed markers identically for
        # EVERY arrangement (job-level, like tone_changes — no per-arrangement
        # warp applied to the override times, which are already in bundle
        # clock). None keeps each arrangement's own GP-authored sections.
        override_sections = (
            [
                Section(name=s.name, start_time=s.start_time, number=i + 1)
                for i, s in enumerate(sorted(spec.section_overrides, key=lambda s: s.start_time))
            ]
            if spec.section_overrides is not None
            else None
        )

        def _sections_for(p: ParsedGpTrack) -> list[Section]:
            if override_sections is not None:
                return override_sections
            return [
                Section(name=s.name, start_time=s.start_time, number=i + 1)
                for i, s in enumerate(p.sections)
            ]

        arrangements = [
            Arrangement(
                kind=kind,
                metadata=metadata,
                tuning=_tuning_for(kind, p.tuning),
                tempo_map=p.tempo_map,
                notes=p.notes,
                sections=_sections_for(p),
                stage_confidence=dict(confidence),
                tone_base=spec.tone_base,
                tone_names=list(spec.tone_names),
                tone_changes=list(spec.tone_changes),
                tones=list(spec.tones),
            )
            for kind, p in parsed.items()
        ]

        stage("lyrics")
        vocals: list[VocalEvent] = []
        lyrics_from_gp = False
        if spec.lyrics_events:
            vocals = [
                VocalEvent(time=e.time + pad_start_s, length=e.length, lyric=e.lyric)
                for e in spec.lyrics_events
            ]
            warnings.append("lyrics from the in-app editor (per-word timing) used")
        elif spec.lrc_text:
            # Lyric timestamps (LRC or UltraStar TXT) are synced to the recording as
            # supplied, so they only move by the silence we actually prepended
            # (pad_start_s) — not by the full score shift, which also absorbs the
            # score's own zero offset.
            vocals = parse_lyrics(spec.lrc_text, pad_start_s)
            if not vocals:
                warnings.append("lyrics file contained no recognizable timestamped lines")
        elif first.lyrics:
            # GP lyrics carry per-syllable note alignment implicitly: each
            # syllable lands on the next note attack. Distribute the line text
            # over the actual (already warped + offset) note onsets so the
            # timing matches what the GP file shows, rather than an even spread.
            onsets = sorted({n.time for n in first.notes})
            vocals = distribute_syllables(
                [(line.time, line.text) for line in first.lyrics], onsets
            )
            lyrics_from_gp = True
            warnings.append(
                "lyrics taken from the GP file, aligned per syllable to the note "
                "onsets (melismas — one syllable held over several notes — are not "
                "modelled and may drift until the next line)"
            )

        if pad_start_s > 0.0:
            warnings.append(
                f"sync offset was {spec.offset_s:.2f}s; added {pad_start_s:.2f}s of silence to "
                f"reach the {MIN_LEAD_S:.0f}s minimum lead-in DLC Builder needs for the "
                f"count-in. The song's first note now plays at {score_shift:.2f}s — use the "
                f"visual sync tool if the chart and audio still drift."
            )

        vocals = enforce_max_line_words(vocals)  # cap long lyric lines in-game

        stage("package")
        packaging = self.packager.package(
            arrangements,
            normalized,
            workdir / "bundle",
            vocals=vocals or None,
            cover_art=spec.cover_art,
            dynamic_difficulty=spec.dynamic_difficulty,
        )
        if packaging.wem_path is None:
            warnings.append(
                "no .wem produced: no local Wwise installation found "
                "(set ROCKFORGE_WWISE_ROOT or WWISEROOT)"
            )
        if packaging.psarc_path is None:
            warnings.append(
                "no PSARC produced: final packing is delegated to DLC Builder "
                "(bundle is import-ready); configure ROCKFORGE_PSARC_PACKER_CMD to automate it"
            )
        # Surface GP-embedded lyrics to the editor/tab viewer in the recording
        # clock (un-padded): the build re-adds pad_start_s, so subtract it here
        # to round-trip correctly. Only when the lyrics actually came from the GP
        # file (not user-supplied LRC/editor rows, which the editor already has).
        gp_lyrics = (
            tuple(
                VocalEvent(time=max(0.0, v.time - pad_start_s), length=v.length, lyric=v.lyric)
                for v in vocals
            )
            if lyrics_from_gp
            else ()
        )
        return PipelineResult(
            packaging=packaging,
            note_counts={a.kind.value: len(a.notes) for a in arrangements},
            warnings=tuple(warnings),
            gp_lyrics=gp_lyrics,
        )
