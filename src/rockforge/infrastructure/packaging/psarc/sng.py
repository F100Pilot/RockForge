"""SNG compilation: ``Arrangement`` → Rocksmith's binary SNG payload.

Binary layout ported from the Rocksmith2014.NET / DLC Builder project (MIT).
Section ordering and field sizes match the real Sng2014 format so the game
can parse the result. Sections RockForge's domain model cannot populate
(PhraseExtraInfo, NLD, Actions, Events, Tones, DNAs) are emitted as empty
(count=0).

Emitted: chord templates (with per-string MIDI notes), chord notes (for chords
with per-string techniques), anchors, anchor extensions (per sliding note),
fingerprints/hand shapes, notes with NextIter/PrevIter linkage, and a separate
vocals model (:func:`from_vocals`).

Dynamic Difficulty is a SIMPLIFIED DDC pass: notes ramp in over several levels
per phrase (ceiling scaled by the phrase's note density), with retail-shaped hero
triples, but no NLinkedDifficulty linkage — a mechanical density ramp, not a
musical phrase-leveling pass. See ``_DD_LEVEL_CAP`` and ``_level_notes``.

Intentionally absent — correct given the domain model, not defects:
- No NLinkedDifficulty / cross-phrase difficulty linking (simplified DD).
- ``ChordNotesId = -1`` for simple chords (matches DLC Builder/EOF).
- Arpeggio fingerprints (Fingerprints2): the domain has no arpeggio marking.
- ParentPrevNote / linkNext: the domain has no note-link concept.
- Note Hash = 0: the two reference tools compute mutually different,
  non-validated hashes, so 0 is the safe, source-consistent choice.

The layout is round-trip-tested but not byte-diffed against a retail SNG.
"""

from __future__ import annotations

import struct
from collections.abc import Sequence
from dataclasses import dataclass, field, replace

from rockforge.domain.arrangement import Arrangement, Section
from rockforge.domain.music import TabNote, Technique
from rockforge.infrastructure.rsxml.vocals import VocalEvent

# ---------------------------------------------------------------------------
# Real Rocksmith 2014 NoteMask values (from Rocksmith2014.NET Constants.cs)
# ---------------------------------------------------------------------------
NOTE_MASK_CHORD = 0x00000002
NOTE_MASK_OPEN = 0x00000004
NOTE_MASK_FRETHANDMUTE = 0x00000008
NOTE_MASK_TREMOLO = 0x00000010
NOTE_MASK_HARMONIC = 0x00000020
NOTE_MASK_PALMMUTE = 0x00000040
NOTE_MASK_SLAP = 0x00000080
NOTE_MASK_PLUCK = 0x00000100
NOTE_MASK_HAMMERON = 0x00000200
NOTE_MASK_PULLOFF = 0x00000400
NOTE_MASK_SLIDE = 0x00000800
NOTE_MASK_BEND = 0x00001000
NOTE_MASK_SUSTAIN = 0x00002000
NOTE_MASK_TAP = 0x00004000
NOTE_MASK_PINCHHARMONIC = 0x00008000
NOTE_MASK_VIBRATO = 0x00010000
NOTE_MASK_MUTE = 0x00020000
NOTE_MASK_IGNORE = 0x00040000
NOTE_MASK_HIGHDENSITY = 0x00200000
NOTE_MASK_SLIDEUNPITCHEDTO = 0x00400000
NOTE_MASK_SINGLE = 0x00800000
NOTE_MASK_CHORDNOTES = 0x01000000
NOTE_MASK_DOUBLESTOP = 0x02000000
NOTE_MASK_ACCENT = 0x04000000
NOTE_MASK_PARENT = 0x08000000
NOTE_MASK_CHILD = 0x10000000
NOTE_MASK_ARPEGGIO = 0x20000000
NOTE_MASK_STRUM = 0x80000000

TECHNIQUE_TO_MASK: dict[Technique, int] = {
    Technique.HAMMER_ON: NOTE_MASK_HAMMERON,
    Technique.PULL_OFF: NOTE_MASK_PULLOFF,
    Technique.SLIDE: NOTE_MASK_SLIDE,
    Technique.BEND: NOTE_MASK_BEND,
    Technique.HARMONIC: NOTE_MASK_HARMONIC,
    Technique.PALM_MUTE: NOTE_MASK_PALMMUTE,
    Technique.VIBRATO: NOTE_MASK_VIBRATO,
    Technique.TAP: NOTE_MASK_TAP,
    Technique.SLAP: NOTE_MASK_SLAP,
    Technique.POP: NOTE_MASK_PLUCK,
    Technique.ACCENT: NOTE_MASK_ACCENT,
}

# Back-compat alias for existing test imports.
TECHNIQUE_BITS = TECHNIQUE_TO_MASK

_NAME_LEN = 32
_LYRIC_LEN = 48
_CHORD_EPSILON_S = 0.03
# Max frets a MERGED anchor spans before a new one is emitted. 4 = the standard
# Rocksmith fret-hand window; a wider (5) merge let a stray low note (e.g. a
# lone fret-1) get folded in with a fret 3-5 chord run, so the whole anchor sat
# a fret or two below the notes actually played (the "anchor shows fret 1 for a
# 2-5 chord" glitch). A single chord that genuinely spans more than 4 frets still
# keeps its own full width — this cap only limits merging neighbours together.
_MAX_ANCHOR_SPAN = 4
# Dynamic Difficulty ceiling: the most difficulty levels a single phrase can
# ramp its notes in over (0..CAP). A phrase's ceiling scales with the note count
# of its busiest iteration, so a dense phrase reaches a higher difficulty than a
# sparse one; this bound keeps the ramp SIMPLE (a retail DDC pass goes ~20+, we
# stop lower on purpose — a "simplified DDC": graduated phrases and correct hero
# triples, no NLinkedDifficulty linkage). Keeps the SNG small and the risk low.
_DD_LEVEL_CAP = 11
# Target phrase length (seconds) when auto-segmenting a section-less song, so DD
# ramps per-phrase as the player progresses instead of over the whole song at once.
_DEFAULT_PHRASE_S = 13.0
# Max phrase length before it is subdivided (applies to GP sections too), so DD
# has many short phrases like a real DDC — roughly doubles a typical GP's sections.
_PHRASE_TARGET_S = 8.0
_BEND_DATA_COUNT = 32  # fixed-size bend array per string in ChordNotes


def _pack_str(value: str, length: int) -> bytes:
    raw = value.encode("utf-8")[: length - 1]
    return raw + b"\x00" * (length - len(raw))


def _unpack_str(raw: bytes) -> str:
    return raw.split(b"\x00", 1)[0].decode("utf-8")


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SngBendData32:
    time: float
    step: float
    unk3: int = 0
    unk4: int = 0
    unk5: int = 0


@dataclass(frozen=True)
class SngBeat:
    time: float
    measure: int  # short; the beat's measure number (real, not -1)
    beat: int = 0  # beat within measure (short)
    phrase_iteration: int = -1
    # Bit 0 = first beat of the measure (downbeat), bit 1 = even measure. The
    # real Sng2014 Bpm carries this trailing int32; omitting it made every beat
    # 4 bytes short and misaligned the whole SNG, crashing the game on load.
    mask: int = 0


@dataclass(frozen=True)
class SngPhrase:
    name: str
    solo: int = 0
    disparity: int = 0
    ignore: int = 0
    max_difficulty: int = 0
    phrase_iteration_links: int = 0


@dataclass(frozen=True)
class SngPhraseIteration:
    phrase_id: int
    start_time: float
    end_time: float
    difficulty: tuple[int, int, int] = (0, 0, 0)


@dataclass(frozen=True)
class SngChordTemplate:
    mask: int
    frets: tuple[int, ...]  # 6 bytes
    fingers: tuple[int, ...]  # 6 bytes
    notes: tuple[int, ...]  # 6 × int32 (MIDI note per string)
    name: str


@dataclass
class SngChordNotes:
    note_mask: list[int]  # 6 × uint32
    bend_data: list[list[SngBendData32]]  # 6 strings × up to 32 bends
    slide_to: list[int]  # 6 bytes
    slide_unpitch_to: list[int]  # 6 bytes
    vibrato: list[int]  # 6 × int16


@dataclass(frozen=True)
class SngSection:
    name: str
    number: int
    start_time: float
    end_time: float
    start_phrase_iteration_id: int = 0
    end_phrase_iteration_id: int = 0
    string_mask: bytes = b"\x00" * 36


@dataclass(frozen=True)
class SngAnchor:
    start_time: float
    end_time: float
    first_note_time: float
    last_note_time: float
    fret: int
    width: int
    phrase_iteration_id: int = 0


@dataclass(frozen=True)
class SngAnchorExtension:
    """Slide anchor follow-through: the fretboard re-anchors to the slide's
    destination at the moment the slide ends (Rocksmith2014.NET
    ``AnchorExtension.fs`` / toolkit ``Sng2014FileWriter``)."""

    beat_time: float  # note.time + note.sustain (when the slide ends)
    fret: int  # the slide destination fret


@dataclass(frozen=True)
class SngFingerprint:
    chord_id: int
    start_time: float
    end_time: float
    first_note_time: float
    last_note_time: float


@dataclass
class SngNote:
    time: float
    string: int  # 0-5 for single, -1 (255 unsigned) for chord
    fret: int
    sustain: float
    bend: float
    mask: int
    note_flags: int = 0
    hash: int = 0
    anchor_fret: int = 0
    anchor_width: int = 4
    chord_id: int = -1
    chord_notes_id: int = -1
    phrase_id: int = 0
    phrase_iteration_id: int = 0
    fingerprint_id: tuple[int, int] = (-1, -1)
    next_iter_note: int = -1
    prev_iter_note: int = -1
    parent_prev_note: int = -1
    slide_to: int = -1          # -1 = no slide (a signed byte, 0xFF on disk)
    slide_unpitch_to: int = -1  # -1 = no unpitched slide
    left_hand: int = 0
    tap: int = 0
    pick_direction: int = 0
    slap: int = 0
    pluck: int = 0
    vibrato: int = 0
    bend_data: list[SngBendData32] = field(default_factory=list)


@dataclass(frozen=True)
class SngVocal:
    time: float
    note: int
    length: float
    lyric: str


@dataclass
class SngArrangementLevel:
    difficulty: int = 0
    anchors: list[SngAnchor] = field(default_factory=list)
    anchor_extensions: list[SngAnchorExtension] = field(default_factory=list)
    fingerprints1: list[SngFingerprint] = field(default_factory=list)
    fingerprints2: list[SngFingerprint] = field(default_factory=list)
    notes: list[SngNote] = field(default_factory=list)
    phrase_count: int = 0
    avg_notes_per_iteration: list[float] = field(default_factory=list)
    notes_in_iteration1: list[int] = field(default_factory=list)
    notes_in_iteration2: list[int] = field(default_factory=list)


@dataclass
class SngMetadata:
    max_score: float = 100_000.0
    max_notes_and_chords: float = 0.0
    max_notes_and_chords_real: float = 0.0
    points_per_note: float = 0.0
    first_beat_length: float = 0.5
    start_time: float = 0.0
    capo_fret: int = 0
    last_conversion: str = "1-1-2000 00:00:00"
    part: int = 1
    song_length: float = 0.0
    string_count: int = 6
    tuning: tuple[int, ...] = (0, 0, 0, 0, 0, 0)
    first_note_time: float = 0.0
    first_note_time2: float = 0.0
    max_difficulty: int = 0


@dataclass
class SngModel:
    beats: list[SngBeat] = field(default_factory=list)
    phrases: list[SngPhrase] = field(default_factory=list)
    chord_templates: list[SngChordTemplate] = field(default_factory=list)
    chord_notes: list[SngChordNotes] = field(default_factory=list)
    vocals: list[SngVocal] = field(default_factory=list)
    phrase_iterations: list[SngPhraseIteration] = field(default_factory=list)
    sections: list[SngSection] = field(default_factory=list)
    arrangements: list[SngArrangementLevel] = field(default_factory=list)
    metadata: SngMetadata = field(default_factory=SngMetadata)


# ---------------------------------------------------------------------------
# Building from domain model
# ---------------------------------------------------------------------------

def _group_chords(
    notes: Sequence[TabNote],
) -> list[list[TabNote]]:
    """Group simultaneous notes; mirrors ``writer.py._group_chords``."""
    ordered = sorted(notes, key=lambda n: (n.time, n.string))
    groups: list[list[TabNote]] = []
    for n in ordered:
        if groups and n.time - groups[-1][0].time <= _CHORD_EPSILON_S:
            groups[-1].append(n)
        else:
            groups.append([n])
    return groups


def _chord_template_key(group: list[TabNote]) -> tuple[int, ...]:
    frets = [-1] * 6
    for n in group:
        frets[n.string] = n.fret
    return tuple(frets)


def _anchor_for_frets(frets: list[int]) -> tuple[int, int]:
    used = [f for f in frets if f > 0]
    if not used:
        return 1, 4
    lo, hi = min(used), max(used)
    width = min(max(4, hi - lo + 1), 24)
    fret = max(1, min(lo, 25 - width))
    return fret, width


def _spread_order(n: int) -> list[int]:
    """A permutation of ``range(n)`` in bisection order (mid, then quarters, …).

    Taking any prefix yields indices spread roughly evenly across ``[0, n)`` — so
    when a DD level shows only the first ``k`` notes of a same-strength group, they
    are distributed across the phrase's timeline instead of clustered at its start
    (the "low difficulty only shows the first half of the song" bug)."""
    order: list[int] = []
    queue: list[tuple[int, int]] = [(0, n - 1)]
    while queue:
        lo, hi = queue.pop(0)
        if lo > hi:
            continue
        mid = (lo + hi) // 2
        order.append(mid)
        queue.append((lo, mid - 1))
        queue.append((mid + 1, hi))
    return order


def _note_tier(time: float, beats: list[SngBeat]) -> int:
    """A note's beat-strength tier for DD: 0 = downbeat (strongest), 1 = on a
    beat, 2 = half-beat, 3 = quarter, 4 = finer. Lower tiers appear first as the
    difficulty ramps up, so the easiest level is just the downbeats."""
    eps = 0.06
    for i in range(len(beats) - 1):
        b0, b1 = beats[i], beats[i + 1]
        if b0.time <= time < b1.time:
            span = b1.time - b0.time
            if span <= 0:
                return 1
            frac = (time - b0.time) / span
            if frac < eps:
                return 0 if (b0.mask & 1) else 1
            if frac > 1 - eps:
                return 0 if (b1.mask & 1) else 1
            if abs(frac - 0.5) < eps:
                return 2
            if abs(frac - 0.25) < eps or abs(frac - 0.75) < eps:
                return 3
            return 4
    # Before the first beat or after the last — treat as a beat-strength note.
    return 0 if (beats and beats[0].mask & 1 and abs(time - beats[0].time) < eps) else 1


def _note_mask(n: TabNote, is_chord: bool = False, is_double_stop: bool = False) -> int:
    mask = 0
    for tech in n.techniques:
        mask |= TECHNIQUE_TO_MASK.get(tech, 0)
    # The native SNG does NOT emit bends (see _bend_points): the binary bend layout
    # is unvalidated against a retail bent SNG and crashed the game at the first
    # bent chord even with EOF-faithful point placement. Strip the bit here so the
    # mask never claims a bend the payload doesn't carry. Bends still reach the
    # game through the DLC Builder bundle (the XML keeps its <bendValues>).
    mask &= ~NOTE_MASK_BEND
    if n.sustain > 0:
        mask |= NOTE_MASK_SUSTAIN
    if n.fret == 0:
        mask |= NOTE_MASK_OPEN
    if is_chord:
        mask |= NOTE_MASK_CHORD
    else:
        mask |= NOTE_MASK_SINGLE
    if is_double_stop:
        mask |= NOTE_MASK_DOUBLESTOP
    return mask


def _bend_points(n: TabNote) -> list[SngBendData32]:
    """Bends are NOT emitted in the native SNG.

    We tried two EOF-faithful placements — a point at the attack and a single
    point one third through the sustain (Editor on Fire's own convention) — and
    both still crashed the game at the entry of the first bent chord (Beartooth
    "Free" C-part). The SNG binary bend layout is round-tripped but has never been
    byte-diffed against a retail SNG that actually contains bends (none exists in
    CI), so it stays disabled here as the honest, stable choice. The bends are not
    lost: the XML writer keeps its <bendValues>, so the DLC Builder bundle (the
    trustworthy path) reproduces them and DLC Builder builds a validated SNG.
    """
    return []


def _section_end_times(sections: list[Section], song_length: float) -> list[float]:
    if not sections:
        return []
    return [s.start_time for s in sections[1:]] + [song_length]


def _find_phrase_iteration(phrase_iters: list[SngPhraseIteration], time: float) -> int:
    for i, pi in enumerate(phrase_iters):
        if pi.start_time <= time < pi.end_time:
            return i
    return max(0, len(phrase_iters) - 1)


def _default_sections(arrangement: Arrangement, song_length: float) -> list[Section]:
    """A COUNT / riff… / END timeline when the arrangement has no sections.

    Rocksmith drives playback off phrase iterations and ends the song at the
    LAST one; an SNG with zero phrases loads the fretboard but shows no notes and
    then crashes. But a SINGLE body phrase spanning the whole song gives a poor
    Dynamic Difficulty — the whole song ramps as one unit. A real DDC
    auto-segments a section-less song into many musical phrases (the DLC Builder
    made 11 for a 215 s song), so DD ramps as the player progresses. We mirror
    that: a COUNT phrase, then a new "riff" phrase every ~``_DEFAULT_PHRASE_S``
    seconds aligned to a measure downbeat, then an END phrase. Times stay strictly
    increasing so each phrase is real.
    """
    beats = arrangement.tempo_map.beats
    start = beats[0].time if beats else 0.0
    notes = arrangement.notes
    first_note = min((n.time for n in notes), default=start)
    last_note_end = max((n.time + max(n.sustain, 0.0) for n in notes), default=start)
    last_beat = beats[-1].time if beats else 0.0
    end_time = last_beat if last_beat > last_note_end else last_note_end + 0.1
    if song_length > 0:
        end_time = min(end_time, song_length)
    body = max(first_note, start)

    secs = [Section(name="COUNT", number=1, start_time=start)]
    if body > start:
        secs.append(Section(name="riff", number=1, start_time=body))
    # Segment the body into ~_DEFAULT_PHRASE_S phrases at measure downbeats,
    # starting from wherever the last phrase begins (the body, or the count-in
    # when the first note lands right at the song start).
    last_cut = secs[-1].start_time
    for t in (b.time for b in beats if b.measure >= 0):
        if last_cut < t < end_time and t - last_cut >= _DEFAULT_PHRASE_S \
                and end_time - t >= _DEFAULT_PHRASE_S / 2:
            secs.append(Section(name="riff", number=len(secs), start_time=t))
            last_cut = t
    if end_time > secs[-1].start_time:
        secs.append(Section(name="END", number=1, start_time=end_time))
    return secs


def _build_anchors(
    positions: list[tuple[float, float, list[int]]],
    phrase_iterations: list[SngPhraseIteration],
    song_length: float,
) -> list[SngAnchor]:
    """Anchors (fret-hand windows) for a set of note positions. ``positions`` is
    ``(first_time, last_time, [frets])`` per chord/note group, time-sorted.

    An anchor is active from its own time until the next; RockForge can't plan
    real hand positions, so it greedily groups consecutive positions into one
    window spanning ≤ _MAX_ANCHOR_SPAN frets (a STABLE window stops the fretboard
    from thrashing note-to-note). Built PER difficulty level from that level's own
    notes — sharing the full-chart anchors on a thinned low level ships anchors
    framing notes that don't exist there, which crashes the game on phrase entry
    (a real DDC sizes anchors to each level: 34 for level 0's 42 notes, ~89 at
    the top). Anchors never span a phrase-iteration boundary (the game re-anchors
    at each phrase start), so any crossing anchor is split into per-phrase pieces.
    """
    positions = [(t, lt, fr) for t, lt, fr in positions if fr]
    raw: list[tuple[float, float, int, int]] = []  # (start, last_note, fret, width)
    i = 0
    while i < len(positions):
        lo = min(positions[i][2])
        hi = max(positions[i][2])
        last_note = positions[i][1]
        j = i + 1
        while j < len(positions):
            cand_lo = min(lo, *positions[j][2])
            cand_hi = max(hi, *positions[j][2])
            if cand_hi - cand_lo + 1 > _MAX_ANCHOR_SPAN:
                break
            lo, hi, last_note = cand_lo, cand_hi, positions[j][1]
            j += 1
        width = min(max(4, hi - lo + 1), 24)
        fret = max(1, min(lo, 25 - width))
        raw.append((positions[i][0], last_note, fret, width))
        i = j

    anchors: list[SngAnchor] = []
    for k, (t, last_note, fret, width) in enumerate(raw):
        # The first anchor covers from the song start so the opening notes are
        # framed before they reach the strike line.
        start = 0.0 if k == 0 else t
        end = raw[k + 1][0] if k + 1 < len(raw) else song_length
        anchors.append(SngAnchor(
            start_time=start, end_time=end, first_note_time=t, last_note_time=last_note,
            fret=fret, width=width,
            phrase_iteration_id=_find_phrase_iteration(phrase_iterations, t),
        ))
    if not anchors and positions:
        anchors.append(SngAnchor(
            start_time=0.0, end_time=song_length,
            first_note_time=positions[0][0], last_note_time=positions[0][0], fret=1, width=4,
        ))

    boundaries = sorted({pi.start_time for pi in phrase_iterations})
    split_anchors: list[SngAnchor] = []
    for a in anchors:
        seg_start = a.start_time
        cuts = [x for x in boundaries if a.start_time < x < a.end_time]
        for seg_end in [*cuts, a.end_time]:
            split_anchors.append(replace(
                a, start_time=seg_start, end_time=seg_end,
                first_note_time=max(a.first_note_time, seg_start),
                phrase_iteration_id=_find_phrase_iteration(phrase_iterations, seg_start),
            ))
            seg_start = seg_end
    return split_anchors


def _level_positions(
    notes: list[SngNote], chord_templates: list[SngChordTemplate], song_length: float
) -> list[tuple[float, float, list[int]]]:
    """``(time, time, [fretted frets])`` per note for :func:`_build_anchors`."""
    out: list[tuple[float, float, list[int]]] = []
    for n in sorted(notes, key=lambda x: x.time):
        if n.chord_id >= 0:
            frets = [f for f in chord_templates[n.chord_id].frets if 0 < f < 250]
        elif n.fret > 0:
            frets = [n.fret]
        else:
            continue
        if frets:
            out.append((n.time, n.time, frets))
    return out


def _build_level(
    difficulty: int,
    notes: list[SngNote],
    phrase_iterations: list[SngPhraseIteration],
    phrase_count: int,
    chord_templates: list[SngChordTemplate],
    song_length: float,
    chord_notes_list: list[SngChordNotes],
) -> SngArrangementLevel:
    """One difficulty level over the given note subset.

    Anchors AND slide anchor-extensions are rebuilt from THIS level's own notes
    (a real DDC sizes them to each level; sharing the full-chart set on a thinned
    low level ships anchors/extensions framing notes that don't exist there,
    crashing the game on phrase entry). Fingerprints (handshapes)
    are NOT emitted at all: both working references — a real CDLC SNG and a DLC
    Builder build of our own XML (which carries ``handShapes count="0"``) — ship
    zero fingerprints on every level, while our one-fingerprint-per-chord run
    (dozens of back-to-back handshapes, including gapped octave shapes) crashed
    the game at the first octave riff. Chords still render via their chord
    template + CHORD/STRUM masks.
    """
    linked = list(notes)
    for pi in phrase_iterations:
        idxs = [i for i, n in enumerate(linked) if pi.start_time <= n.time < pi.end_time]
        for j, gi in enumerate(idxs):
            linked[gi] = replace(
                linked[gi],
                prev_iter_note=idxs[j - 1] if j > 0 else -1,
                next_iter_note=idxs[j + 1] if j < len(idxs) - 1 else -1,
            )
    notes_in_iter = [
        sum(1 for n in linked if pi.start_time <= n.time < pi.end_time)
        for pi in phrase_iterations
    ]
    avg_per_iter = []
    for p_idx in range(phrase_count):
        counts = [
            notes_in_iter[i] for i, pi in enumerate(phrase_iterations) if pi.phrase_id == p_idx
        ]
        avg_per_iter.append(sum(counts) / max(1, len(counts)))

    # Slide anchor-extensions for THIS level's notes: a single note carries its
    # slide in slide_to; a chord's per-string slides live in its ChordNotes entry
    # (0xFF = no slide on that string). One extension per sliding string, at the
    # moment the slide ends (time + sustain), sorted as the game expects.
    anchor_extensions: list[SngAnchorExtension] = []
    for n in linked:
        if n.slide_to >= 0:
            targets = [n.slide_to]
        elif n.chord_notes_id >= 0:
            targets = [s for s in chord_notes_list[n.chord_notes_id].slide_to if s != 0xFF]
        else:
            continue
        anchor_extensions.extend(
            SngAnchorExtension(beat_time=n.time + n.sustain, fret=t) for t in targets
        )
    anchor_extensions.sort(key=lambda ae: ae.beat_time)

    anchors = _build_anchors(
        _level_positions(linked, chord_templates, song_length), phrase_iterations, song_length
    )

    return SngArrangementLevel(
        difficulty=difficulty,
        anchors=anchors,
        anchor_extensions=anchor_extensions,
        fingerprints1=[],
        fingerprints2=[],
        notes=linked,
        phrase_count=phrase_count,
        avg_notes_per_iteration=avg_per_iter,
        notes_in_iteration1=notes_in_iter,
        notes_in_iteration2=notes_in_iter,
    )


def from_arrangement(
    arrangement: Arrangement,
    vocals: list[VocalEvent] | None = None,
    *,
    dynamic_difficulty: bool = True,
) -> SngModel:
    """Build the SNG model from a RockForge ``Arrangement``.

    With ``dynamic_difficulty=False`` a single level holding the full chart is
    emitted (max_difficulty 0, no ramp) — a safety valve for songs where the
    simplified DD misbehaves; the chart always plays at full density.
    """
    song_length = arrangement.metadata.song_length

    # --- Beats ---
    # The SNG stores the real measure number on EVERY beat (not -1 for off-beats
    # as the domain does), the beat-within-measure, and a mask (bit0 = downbeat,
    # bit1 = even measure). Track the running measure to fill both.
    beat_in_measure = 0
    current_measure = 1
    beats: list[SngBeat] = []
    for b in arrangement.tempo_map.beats:
        downbeat = b.measure >= 0
        if downbeat:
            current_measure = b.measure
            beat_in_measure = 0
        mask = 0
        if downbeat:
            mask |= 1
            if current_measure % 2 == 0:
                mask |= 2
        beats.append(SngBeat(
            time=b.time, measure=current_measure, beat=beat_in_measure, mask=mask
        ))
        beat_in_measure += 1

    # --- Phrases & PhraseIterations ---
    # A song with no section markers still needs a valid phrase timeline, or the
    # game crashes on the note highway (see _default_sections).
    sections_src = list(
        arrangement.sections or _default_sections(arrangement, song_length)
    )
    # Retail structure brackets the body with a COUNT phrase (the count-in, max
    # difficulty 0) and an END phrase after the last note. Without COUNT, a GP
    # whose first section starts at 0 puts the silent intro inside a high-
    # difficulty phrase (an all-black bar in the Riff Repeater); without END the
    # song has no closing empty phrase. _default_sections already emits both;
    # bracket real GP sections the same way.
    if arrangement.sections:
        first_note = min((n.time for n in arrangement.notes), default=0.0)
        last_note_end = max(
            (n.time + max(n.sustain, 0.0) for n in arrangement.notes), default=0.0
        )
        if sections_src[0].name != "COUNT" and first_note - sections_src[0].start_time > 1.0:
            count_start = sections_src[0].start_time
            sections_src[0] = replace(sections_src[0], start_time=first_note)
            sections_src.insert(0, Section(name="COUNT", number=1, start_time=count_start))
        if sections_src[-1].name != "END" and song_length - last_note_end > 0.5:
            end_start = min(last_note_end + 0.1, song_length)
            if end_start > sections_src[-1].start_time:
                sections_src.append(Section(name="END", number=1, start_time=end_start))

    # Subdivide long body phrases into ~_PHRASE_TARGET_S chunks at measure
    # downbeats, so DD ramps in finer steps as the player progresses — a real
    # DDC splits a song into many short phrases (roughly double the GP sections).
    # COUNT/END and their surrounding structure stay whole.
    downbeats = [b.time for b in arrangement.tempo_map.beats if b.measure >= 0]
    refined: list[Section] = []
    for idx, sec in enumerate(sections_src):
        refined.append(sec)
        if sec.name in ("COUNT", "END"):
            continue
        sec_end = sections_src[idx + 1].start_time if idx + 1 < len(sections_src) else song_length
        last = sec.start_time
        for t in downbeats:
            if t <= last + _PHRASE_TARGET_S:
                continue
            if t >= sec_end - _PHRASE_TARGET_S / 2:
                break
            refined.append(Section(name=sec.name, number=len(refined), start_time=t))
            last = t
    sections_src = refined

    phrases = [SngPhrase(name=s.name) for s in sections_src]
    ends = _section_end_times(sections_src, song_length)
    phrase_iterations = [
        SngPhraseIteration(phrase_id=i, start_time=s.start_time, end_time=end)
        for i, (s, end) in enumerate(zip(sections_src, ends, strict=True))
    ]
    # Each phrase's PhraseIterationLinks = how many iterations reference it (a
    # decoded retail CDLC carries the real counts; writing 0 breaks the Riff
    # Repeater's phrase navigation — the game crashed entering the next phrase).
    _links = [0] * len(phrases)
    for pi in phrase_iterations:
        _links[pi.phrase_id] += 1
    phrases = [
        replace(p, phrase_iteration_links=_links[i]) for i, p in enumerate(phrases)
    ]

    # Assign phrase_iteration to beats (preserving measure/beat/mask)
    beats = [
        SngBeat(
            time=b.time,
            measure=b.measure,
            beat=b.beat,
            phrase_iteration=_find_phrase_iteration(phrase_iterations, b.time),
            mask=b.mask,
        )
        for b in beats
    ]

    # --- Chord grouping ---
    groups = _group_chords(arrangement.notes)
    single_groups = [g for g in groups if len(g) == 1]
    chord_groups = [g for g in groups if len(g) > 1]

    # --- Chord templates ---
    template_ids: dict[tuple[int, ...], int] = {}
    open_midi = arrangement.tuning.midi  # MIDI pitch of each open string
    chord_templates: list[SngChordTemplate] = []
    for g in chord_groups:
        key = _chord_template_key(g)
        if key not in template_ids:
            template_ids[key] = len(template_ids)
            frets_bytes = tuple(max(0, f) if f >= 0 else 255 for f in key)
            # MIDI note sounding on each used string (open pitch + fret); 0 for
            # unused strings, mirroring the toolkit's ChordTemplate.Notes.
            notes_midi = tuple(
                open_midi[i] + f if f >= 0 else 0 for i, f in enumerate(key)
            )
            chord_templates.append(SngChordTemplate(
                mask=0,
                frets=frets_bytes,
                fingers=tuple([-1] * 6),
                notes=notes_midi,
                name="",
            ))

    # --- ChordNotes (for chords with per-string techniques) ---
    chord_notes_list: list[SngChordNotes] = []
    chord_notes_map: dict[int, int] = {}  # group_index -> chord_notes_id
    # Identical entries are deduplicated by content, as retail does (a decoded
    # CDLC carries 11 entries for ~2200 chords).
    cn_ids: dict[tuple[object, ...], int] = {}

    def _cn_key(cn: SngChordNotes) -> tuple[object, ...]:
        return (
            tuple(cn.note_mask),
            tuple(tuple((b.time, b.step) for b in s) for s in cn.bend_data),
            tuple(cn.slide_to),
            tuple(cn.slide_unpitch_to),
            tuple(cn.vibrato),
        )

    for gi, g in enumerate(chord_groups):
        # Bends are not emitted in the SNG (see _bend_points), so a bend-only chord
        # needs no ChordNotes entry.
        has_techniques = any(
            (n.techniques - {Technique.BEND}) or n.slide_to_fret is not None
            for n in g
        )
        if not has_techniques:
            continue
        cn = SngChordNotes(
            note_mask=[0] * 6,
            bend_data=[[] for _ in range(6)],
            slide_to=[0xFF] * 6,          # 0xFF (= -1) per string = no slide
            slide_unpitch_to=[0xFF] * 6,
            vibrato=[0] * 6,
        )
        for n in g:
            # Technique bits only — NEVER the SINGLE note-kind bit. A decoded
            # retail CDLC carries e.g. OPEN|PALMMUTE|SUSTAIN per string; our
            # extra SINGLE (0x800000) told the game each string was a standalone
            # single note inside a chord, drawing a corrupt vertical bar on the
            # highway and crashing mid-riff.
            cn.note_mask[n.string] = _note_mask(n) & ~NOTE_MASK_SINGLE
            if n.slide_to_fret is not None:
                cn.slide_to[n.string] = n.slide_to_fret
            if Technique.VIBRATO in n.techniques:
                cn.vibrato[n.string] = 80
        cn_key = _cn_key(cn)
        if cn_key not in cn_ids:
            cn_ids[cn_key] = len(chord_notes_list)
            chord_notes_list.append(cn)
        chord_notes_map[gi] = cn_ids[cn_key]

    # --- Build anchors ---
    # Full-chart anchors, only to stamp each NOTE's anchor_fret/anchor_width hint
    # (via _find_anchor). The per-LEVEL anchor arrays the game actually uses are
    # rebuilt from each level's own notes inside _build_level — see _build_anchors.
    anchors = _build_anchors(
        [(g[0].time, g[-1].time, [n.fret for n in g if n.fret > 0]) for g in groups],
        phrase_iterations,
        song_length,
    )

    # (Anchor extensions — the slide re-anchors — are built per difficulty level
    # inside _build_level, from each level's own notes.)

    # (Fingerprints / handshapes are deliberately NOT emitted — see _build_level's
    # docstring: both working references ship zero, and our per-chord handshapes
    # crashed the game at a dense octave riff.)

    # --- Build SNG notes ---
    sng_notes: list[SngNote] = []

    def _find_anchor(time: float) -> tuple[int, int]:
        for a in reversed(anchors):
            if a.first_note_time <= time:
                return a.fret, a.width
        return anchors[0].fret if anchors else 1, anchors[0].width if anchors else 4

    # Single notes
    for g in single_groups:
        sn = g[0]
        mask = _note_mask(sn, is_chord=False)
        a_fret, a_width = _find_anchor(sn.time)
        pi_id = _find_phrase_iteration(phrase_iterations, sn.time)
        sng_notes.append(SngNote(
            time=sn.time,
            string=sn.string,
            fret=sn.fret,
            sustain=sn.sustain,
            bend=0.0,  # bends not emitted in the SNG — see _bend_points
            mask=mask,
            anchor_fret=a_fret,
            anchor_width=a_width,
            phrase_id=pi_id,
            phrase_iteration_id=pi_id,
            slide_to=sn.slide_to_fret if sn.slide_to_fret is not None else -1,
            slap=1 if Technique.SLAP in sn.techniques else 0,
            pluck=1 if Technique.POP in sn.techniques else 0,
            tap=1 if Technique.TAP in sn.techniques else 0,
            vibrato=80 if Technique.VIBRATO in sn.techniques else 0,
            bend_data=_bend_points(sn),
        ))

    # Chord notes
    for gi, g in enumerate(chord_groups):
        key = _chord_template_key(g)
        chord_id = template_ids[key]
        cn_id = chord_notes_map.get(gi, -1)
        is_double = len(g) == 2
        mask = NOTE_MASK_CHORD
        if is_double:
            mask |= NOTE_MASK_DOUBLESTOP
        if cn_id >= 0:
            mask |= NOTE_MASK_CHORDNOTES
        # Mirror techniques from individual notes onto chord mask (never BEND —
        # bends are not emitted in the SNG; see _bend_points).
        for n in g:
            for tech in n.techniques:
                mask |= TECHNIQUE_TO_MASK.get(tech, 0)
        mask &= ~NOTE_MASK_BEND
        if any(n.sustain > 0 for n in g):
            mask |= NOTE_MASK_SUSTAIN
        mask |= NOTE_MASK_STRUM
        a_fret, a_width = _find_anchor(g[0].time)
        pi_id = _find_phrase_iteration(phrase_iterations, g[0].time)
        sng_notes.append(SngNote(
            time=g[0].time,
            string=-1,
            fret=-1,
            sustain=max(n.sustain for n in g),
            bend=0.0,  # bends not emitted in the SNG — see _bend_points
            mask=mask,
            anchor_fret=a_fret,
            anchor_width=a_width,
            chord_id=chord_id,
            chord_notes_id=cn_id,
            phrase_id=pi_id,
            phrase_iteration_id=pi_id,
            bend_data=[],
        ))

    sng_notes.sort(key=lambda n: n.time)

    # --- Sections ---
    sections: list[SngSection] = []
    for sec, end in zip(sections_src, ends, strict=True):
        start_pi = _find_phrase_iteration(phrase_iterations, sec.start_time)
        end_pi = _find_phrase_iteration(phrase_iterations, end - 0.001) if end > 0 else start_pi
        sections.append(SngSection(
            name=sec.name,
            number=sec.number,
            start_time=sec.start_time,
            end_time=end,
            start_phrase_iteration_id=start_pi,
            end_phrase_iteration_id=end_pi,
        ))

    # --- Dynamic Difficulty (DDC-style graduated levels) ---
    # A real Rocksmith DD ramps each note in over many levels, per phrase, so the
    # in-game difficulty slider spans 0..songMax (verified against a DLC Builder /
    # DDC reference SNG: 23 levels, per-phrase ceilings graduated by density, and
    # per-iteration hero triples of (~¼, ~½, 1)·max). We reproduce that shape.
    note_count = len(sng_notes)
    note_tiers = [_note_tier(sngn.time, beats) for sngn in sng_notes]

    # Notes of each phrase iteration, ranked by importance so the earliest DD
    # levels introduce the strongest beats first. Within a beat-strength tier the
    # notes are visited in bisection order (`_spread_order`), NOT plain time order,
    # so a level that shows only part of a tier spreads those notes across the
    # whole phrase instead of clustering them at its start (which left low
    # difficulties showing only the first half of a long single-phrase song).
    per_iter_notes: list[list[int]] = [[] for _ in phrase_iterations]
    for idx, sngn in enumerate(sng_notes):
        per_iter_notes[sngn.phrase_iteration_id].append(idx)
    for pi_id, lst in enumerate(per_iter_notes):
        by_tier: dict[int, list[int]] = {}
        for i in sorted(lst, key=lambda i: sng_notes[i].time):
            by_tier.setdefault(note_tiers[i], []).append(i)
        ordered: list[int] = []
        for tier in sorted(by_tier):
            grp = by_tier[tier]
            ordered.extend(grp[pos] for pos in _spread_order(len(grp)))
        per_iter_notes[pi_id] = ordered

    # Per-phrase ceiling: one difficulty step per note the BUSIEST iteration must
    # ramp in, capped. Repeated phrases share a ceiling (busiest, not summed); a
    # silent COUNT/END phrase stays at 0.
    busiest = [0] * len(phrases)
    for pi_id, pi in enumerate(phrase_iterations):
        busiest[pi.phrase_id] = max(busiest[pi.phrase_id], len(per_iter_notes[pi_id]))
    phrase_max = [min(_DD_LEVEL_CAP, max(0, b - 1)) for b in busiest]
    if not dynamic_difficulty:
        # One full-chart level: every phrase saturates at difficulty 0.
        phrase_max = [0] * len(phrases)
    song_max = max(phrase_max, default=0)

    def _level_notes(d: int) -> list[SngNote]:
        """The notes visible at difficulty ``d``: each iteration shows the
        strongest-beat prefix scaled by ``d`` against its phrase's ceiling."""
        keep: set[int] = set()
        for pi_id, lst in enumerate(per_iter_notes):
            m = len(lst)
            if m == 0:
                continue
            pm = phrase_max[phrase_iterations[pi_id].phrase_id]
            if pm <= 0:
                shown = m
            else:
                shown = round((min(d, pm) + 1) / (pm + 1) * m)
                shown = max(0, min(m, shown))
            keep.update(lst[:shown])
        return [sngn for i, sngn in enumerate(sng_notes) if i in keep]

    phrases = [replace(p, max_difficulty=phrase_max[i]) for i, p in enumerate(phrases)]
    phrase_iterations = [
        replace(pi, difficulty=(
            round(phrase_max[pi.phrase_id] / 4),
            round(phrase_max[pi.phrase_id] / 2),
            phrase_max[pi.phrase_id],
        ))
        for pi in phrase_iterations
    ]

    arrangements = [
        _build_level(
            d, _level_notes(d), phrase_iterations, len(phrases),
            chord_templates, song_length, chord_notes_list,
        )
        for d in range(song_max + 1)
    ]

    # --- Vocals ---
    sng_vocals = [
        SngVocal(time=v.time, note=0, length=v.length, lyric=v.lyric)
        for v in (vocals or [])
    ]

    # --- Metadata ---
    first_note = min((n.time for n in arrangement.notes), default=0.0)
    first_beat_len = 0.5
    if len(arrangement.tempo_map.beats) >= 2:
        first_beat_len = arrangement.tempo_map.beats[1].time - arrangement.tempo_map.beats[0].time
    points = 100_000.0 / max(1, note_count) if note_count else 0.0
    metadata = SngMetadata(
        max_score=100_000.0,
        max_notes_and_chords=float(note_count),
        max_notes_and_chords_real=float(note_count),
        points_per_note=points,
        first_beat_length=first_beat_len,
        start_time=arrangement.tempo_map.beats[0].time if arrangement.tempo_map.beats else 0.0,
        capo_fret=arrangement.capo,
        part=1,
        song_length=song_length,
        tuning=arrangement.tuning.offsets_from_standard(),
        first_note_time=first_note,
        first_note_time2=first_note,
        max_difficulty=song_max,
    )

    return SngModel(
        beats=beats,
        phrases=phrases,
        chord_templates=chord_templates,
        chord_notes=chord_notes_list,
        vocals=sng_vocals,
        phrase_iterations=phrase_iterations,
        sections=sections,
        arrangements=arrangements,
        metadata=metadata,
    )


def from_vocals(vocals: list[VocalEvent]) -> SngModel:
    """Build a vocals-only SNG model for a separate ``<key>_vocals.sng``.

    A Rocksmith vocals ``.sng`` is the same Sng2014 container as an instrument
    arrangement, but only the Vocals section is populated (every other section
    is empty / count=0); the container still ends with a Metadata section
    (neutral values — the game does not read tuning/length from the vocals SNG).
    Ported from the toolkit's ``ReadVocals`` over the ``VOCALS_RS2`` template.
    """
    return SngModel(
        vocals=[
            SngVocal(time=v.time, note=0, length=v.length, lyric=v.lyric)
            for v in vocals
        ],
        arrangements=[],
        metadata=SngMetadata(),
    )


# ---------------------------------------------------------------------------
# Binary serialization (write)
# ---------------------------------------------------------------------------

_BEND32_FMT = "<ffhBB"
_BEND32_SIZE = struct.calcsize(_BEND32_FMT)  # 12

_BEAT_FMT = "<fhhii"
_PHRASE_FMT = "<BBBBii32s"
_PHRASE_ITER_FMT = "<iffiii"
_CHORD_TEMPLATE_FMT = "<I6s6s6i32s"
_SECTION_FMT = "<32siffii36s"
_ANCHOR_FMT = "<ffffBBBBii"
# AnchorExtension: BeatTime(float) + FretId(int8) + 7 bytes of zero unknowns
# (int32 + int16 + int8) = 12 bytes (Rocksmith2014.NET AnchorExtension.fs).
_ANCHOR_EXT_FMT = "<fbihb"
_FINGERPRINT_FMT = "<iffff"
_VOCAL_FMT = f"<fif{_LYRIC_LEN}s"
# slide_to / slide_unpitch_to are SIGNED bytes: -1 (0xFF) means "no slide".
# Writing 0 (unsigned) told the game every note slides to fret 0 — a slide
# streak on every note, and slide geometry the game chokes on at load.
_NOTE_FIXED_FMT = "<IIIfBBBBiiiihhhhh" "bbBBBBBhff"

_BEAT_SIZE = struct.calcsize(_BEAT_FMT)
_PHRASE_SIZE = struct.calcsize(_PHRASE_FMT)
_PHRASE_ITER_SIZE = struct.calcsize(_PHRASE_ITER_FMT)
_CHORD_TEMPLATE_SIZE = struct.calcsize(_CHORD_TEMPLATE_FMT)
_SECTION_SIZE = struct.calcsize(_SECTION_FMT)
_ANCHOR_SIZE = struct.calcsize(_ANCHOR_FMT)
_ANCHOR_EXT_SIZE = struct.calcsize(_ANCHOR_EXT_FMT)
_FINGERPRINT_SIZE = struct.calcsize(_FINGERPRINT_FMT)
_VOCAL_SIZE = struct.calcsize(_VOCAL_FMT)
_NOTE_FIXED_SIZE = struct.calcsize(_NOTE_FIXED_FMT)


def _write_count(count: int) -> bytes:
    return struct.pack("<I", count)


def _write_bend32(bd: SngBendData32) -> bytes:
    return struct.pack(_BEND32_FMT, bd.time, bd.step, bd.unk3, bd.unk4, bd.unk5)


def _write_chord_notes_entry(cn: SngChordNotes) -> bytes:
    out = bytearray()
    # NoteMask[6]
    for m in cn.note_mask:
        out += struct.pack("<I", m)
    # BendData[6] — fixed 32 entries per string
    for s in range(6):
        bends = cn.bend_data[s]
        out += struct.pack("<i", len(bends))
        for j in range(_BEND_DATA_COUNT):
            if j < len(bends):
                out += _write_bend32(bends[j])
            else:
                out += b"\x00" * _BEND32_SIZE
    # SlideTo[6], SlideUnpitchTo[6]
    out += bytes(cn.slide_to)
    out += bytes(cn.slide_unpitch_to)
    # Vibrato[6]
    for v in cn.vibrato:
        out += struct.pack("<h", v)
    return bytes(out)


def _write_note(n: SngNote) -> bytes:
    out = bytearray()
    string_byte = n.string & 0xFF  # -1 → 255
    fret_byte = n.fret & 0xFF
    out += struct.pack(
        _NOTE_FIXED_FMT,
        n.mask,
        n.note_flags,
        n.hash,
        n.time,
        string_byte,
        fret_byte,
        n.anchor_fret,
        n.anchor_width,
        n.chord_id,
        n.chord_notes_id,
        n.phrase_id,
        n.phrase_iteration_id,
        n.fingerprint_id[0],
        n.fingerprint_id[1],
        n.next_iter_note,
        n.prev_iter_note,
        n.parent_prev_note,
        n.slide_to,
        n.slide_unpitch_to,
        n.left_hand,
        n.tap,
        n.pick_direction,
        n.slap,
        n.pluck,
        n.vibrato,
        n.sustain,
        n.bend,
    )
    # BendData (variable-length)
    out += _write_count(len(n.bend_data))
    for bd in n.bend_data:
        out += _write_bend32(bd)
    return bytes(out)


def _write_arrangement_level(level: SngArrangementLevel) -> bytes:
    out = bytearray()
    out += struct.pack("<i", level.difficulty)

    # Anchors
    out += _write_count(len(level.anchors))
    for a in level.anchors:
        out += struct.pack(
            _ANCHOR_FMT,
            a.start_time, a.end_time, a.first_note_time, a.last_note_time,
            a.fret, 0, 0, 0,  # fret + 3 padding bytes
            a.width, a.phrase_iteration_id,
        )

    # AnchorExtensions (one per sliding note)
    out += _write_count(len(level.anchor_extensions))
    for ae in level.anchor_extensions:
        out += struct.pack(_ANCHOR_EXT_FMT, ae.beat_time, ae.fret, 0, 0, 0)

    # Fingerprints1
    out += _write_count(len(level.fingerprints1))
    for fp in level.fingerprints1:
        out += struct.pack(
            _FINGERPRINT_FMT,
            fp.chord_id, fp.start_time, fp.end_time,
            fp.first_note_time, fp.last_note_time,
        )

    # Fingerprints2 (arpeggios, always empty)
    out += _write_count(len(level.fingerprints2))
    for fp in level.fingerprints2:
        out += struct.pack(
            _FINGERPRINT_FMT,
            fp.chord_id, fp.start_time, fp.end_time,
            fp.first_note_time, fp.last_note_time,
        )

    # Notes
    out += _write_count(len(level.notes))
    for n in level.notes:
        out += _write_note(n)

    # Phrase counts and per-iteration note counts
    out += struct.pack("<i", level.phrase_count)
    for avg in level.avg_notes_per_iteration:
        out += struct.pack("<f", avg)
    out += struct.pack("<i", len(level.notes_in_iteration1))
    for c in level.notes_in_iteration1:
        out += struct.pack("<i", c)
    out += struct.pack("<i", len(level.notes_in_iteration2))
    for c in level.notes_in_iteration2:
        out += struct.pack("<i", c)

    return bytes(out)


def write_sng(model: SngModel) -> bytes:
    """Serialize an :class:`SngModel` to the Rocksmith Sng2014 binary payload."""
    out = bytearray()

    # 1. BPMs
    out += _write_count(len(model.beats))
    for b in model.beats:
        out += struct.pack(_BEAT_FMT, b.time, b.measure, b.beat, b.phrase_iteration, b.mask)

    # 2. Phrases
    out += _write_count(len(model.phrases))
    for p in model.phrases:
        out += struct.pack(
            _PHRASE_FMT,
            p.solo, p.disparity, p.ignore, 0,  # padding
            p.max_difficulty, p.phrase_iteration_links,
            _pack_str(p.name, _NAME_LEN),
        )

    # 3. ChordTemplates
    out += _write_count(len(model.chord_templates))
    for ct in model.chord_templates:
        out += struct.pack(
            _CHORD_TEMPLATE_FMT,
            ct.mask,
            bytes(ct.frets[:6]),
            bytes(f & 0xFF for f in ct.fingers[:6]),
            *ct.notes[:6],
            _pack_str(ct.name, _NAME_LEN),
        )

    # 4. ChordNotes
    out += _write_count(len(model.chord_notes))
    for cn in model.chord_notes:
        out += _write_chord_notes_entry(cn)

    # 5. Vocals
    out += _write_count(len(model.vocals))
    for v in model.vocals:
        out += struct.pack(
            _VOCAL_FMT, v.time, v.note, v.length, _pack_str(v.lyric, _LYRIC_LEN)
        )
    # Symbol sections (only when vocals are present)
    if model.vocals:
        out += _write_count(0)  # SymbolsHeader
        out += _write_count(0)  # SymbolsTexture
        out += _write_count(0)  # SymbolsDefinition

    # 6. PhraseIterations
    out += _write_count(len(model.phrase_iterations))
    for pi in model.phrase_iterations:
        out += struct.pack(
            _PHRASE_ITER_FMT,
            pi.phrase_id, pi.start_time, pi.end_time,
            *pi.difficulty,
        )

    # 7-12. Empty sections: PhraseExtraInfo, NLD, Actions, Events, Tones, DNAs
    for _ in range(6):
        out += _write_count(0)

    # 13. Sections
    out += _write_count(len(model.sections))
    for s in model.sections:
        out += struct.pack(
            _SECTION_FMT,
            _pack_str(s.name, _NAME_LEN),
            s.number, s.start_time, s.end_time,
            s.start_phrase_iteration_id, s.end_phrase_iteration_id,
            s.string_mask,
        )

    # 14. Arrangements (difficulty levels)
    out += _write_count(len(model.arrangements))
    for level in model.arrangements:
        out += _write_arrangement_level(level)

    # 15. Metadata
    m = model.metadata
    out += struct.pack("<d", m.max_score)
    out += struct.pack("<d", m.max_notes_and_chords)
    out += struct.pack("<d", m.max_notes_and_chords_real)
    out += struct.pack("<d", m.points_per_note)
    out += struct.pack("<f", m.first_beat_length)
    out += struct.pack("<f", m.start_time)
    out += struct.pack("<B", m.capo_fret)
    out += _pack_str(m.last_conversion, _NAME_LEN)
    out += struct.pack("<h", m.part)
    out += struct.pack("<f", m.song_length)
    out += struct.pack("<i", m.string_count)
    for t in m.tuning[:m.string_count]:
        out += struct.pack("<h", t)
    out += struct.pack("<f", m.first_note_time)
    out += struct.pack("<f", m.first_note_time2)
    out += struct.pack("<i", m.max_difficulty)

    return bytes(out)


# ---------------------------------------------------------------------------
# Binary deserialization (read) — for round-trip testing
# ---------------------------------------------------------------------------

def _read_count(data: bytes, pos: int) -> tuple[int, int]:
    (count,) = struct.unpack_from("<I", data, pos)
    return count, pos + 4


def _read_bend32(data: bytes, pos: int) -> tuple[SngBendData32, int]:
    t, s, u3, u4, u5 = struct.unpack_from(_BEND32_FMT, data, pos)
    return SngBendData32(time=t, step=s, unk3=u3, unk4=u4, unk5=u5), pos + _BEND32_SIZE


def _read_note(data: bytes, pos: int) -> tuple[SngNote, int]:
    vals = struct.unpack_from(_NOTE_FIXED_FMT, data, pos)
    pos += _NOTE_FIXED_SIZE
    (
        mask, note_flags, hash_, time_,
        string_b, fret_b, anchor_fret, anchor_width,
        chord_id, chord_notes_id, phrase_id, phrase_iteration_id,
        fp0, fp1, next_iter, prev_iter, parent_prev,
        slide_to, slide_unpitch, left_hand, tap_, pick_dir, slap_, pluck_,
        vibrato_, sustain_, max_bend,
    ) = vals
    string_i = string_b if string_b < 128 else string_b - 256
    fret_i = fret_b if fret_b < 128 else fret_b - 256
    bd_count, pos = _read_count(data, pos)
    bend_data = []
    for _ in range(bd_count):
        bd, pos = _read_bend32(data, pos)
        bend_data.append(bd)
    return SngNote(
        time=time_, string=string_i, fret=fret_i, sustain=sustain_, bend=max_bend,
        mask=mask, note_flags=note_flags, hash=hash_,
        anchor_fret=anchor_fret, anchor_width=anchor_width,
        chord_id=chord_id, chord_notes_id=chord_notes_id,
        phrase_id=phrase_id, phrase_iteration_id=phrase_iteration_id,
        fingerprint_id=(fp0, fp1),
        next_iter_note=next_iter, prev_iter_note=prev_iter, parent_prev_note=parent_prev,
        slide_to=slide_to, slide_unpitch_to=slide_unpitch,
        left_hand=left_hand, tap=tap_, pick_direction=pick_dir,
        slap=slap_, pluck=pluck_, vibrato=vibrato_,
        bend_data=bend_data,
    ), pos


def _read_chord_notes_entry(data: bytes, pos: int) -> tuple[SngChordNotes, int]:
    masks = []
    for _ in range(6):
        (m,) = struct.unpack_from("<I", data, pos)
        masks.append(m)
        pos += 4
    bend_data: list[list[SngBendData32]] = []
    for _ in range(6):
        (used,) = struct.unpack_from("<i", data, pos)
        pos += 4
        bends = []
        for j in range(_BEND_DATA_COUNT):
            bd, pos = _read_bend32(data, pos)
            if j < used:
                bends.append(bd)
        bend_data.append(bends)
    slide_to = list(data[pos : pos + 6])
    pos += 6
    slide_unpitch_to = list(data[pos : pos + 6])
    pos += 6
    vibrato = []
    for _ in range(6):
        (v,) = struct.unpack_from("<h", data, pos)
        vibrato.append(v)
        pos += 2
    return SngChordNotes(
        note_mask=masks, bend_data=bend_data,
        slide_to=slide_to, slide_unpitch_to=slide_unpitch_to, vibrato=vibrato,
    ), pos


def _read_arrangement_level(data: bytes, pos: int) -> tuple[SngArrangementLevel, int]:
    (difficulty,) = struct.unpack_from("<i", data, pos)
    pos += 4

    # Anchors
    a_count, pos = _read_count(data, pos)
    anchors = []
    for _ in range(a_count):
        st, et, fnt, lnt, fret_b, _, _, _, width, pi_id = struct.unpack_from(_ANCHOR_FMT, data, pos)
        pos += _ANCHOR_SIZE
        anchors.append(SngAnchor(
            start_time=st, end_time=et, first_note_time=fnt, last_note_time=lnt,
            fret=fret_b, width=width, phrase_iteration_id=pi_id,
        ))

    # AnchorExtensions
    ae_count, pos = _read_count(data, pos)
    anchor_extensions = []
    for _ in range(ae_count):
        beat_time, fret_e, _, _, _ = struct.unpack_from(_ANCHOR_EXT_FMT, data, pos)
        pos += _ANCHOR_EXT_SIZE
        anchor_extensions.append(SngAnchorExtension(beat_time=beat_time, fret=fret_e))

    # Fingerprints1
    fp1_count, pos = _read_count(data, pos)
    fp1 = []
    for _ in range(fp1_count):
        ci, st, et, fnt, lnt = struct.unpack_from(_FINGERPRINT_FMT, data, pos)
        pos += _FINGERPRINT_SIZE
        fp1.append(SngFingerprint(chord_id=ci, start_time=st, end_time=et,
                                  first_note_time=fnt, last_note_time=lnt))

    # Fingerprints2
    fp2_count, pos = _read_count(data, pos)
    fp2 = []
    for _ in range(fp2_count):
        ci, st, et, fnt, lnt = struct.unpack_from(_FINGERPRINT_FMT, data, pos)
        pos += _FINGERPRINT_SIZE
        fp2.append(SngFingerprint(chord_id=ci, start_time=st, end_time=et,
                                  first_note_time=fnt, last_note_time=lnt))

    # Notes
    n_count, pos = _read_count(data, pos)
    notes = []
    for _ in range(n_count):
        note, pos = _read_note(data, pos)
        notes.append(note)

    # Phrase counts
    (phrase_count,) = struct.unpack_from("<i", data, pos)
    pos += 4
    avg = []
    for _ in range(phrase_count):
        (a,) = struct.unpack_from("<f", data, pos)
        avg.append(a)
        pos += 4
    (ni1_count,) = struct.unpack_from("<i", data, pos)
    pos += 4
    ni1 = []
    for _ in range(ni1_count):
        (c,) = struct.unpack_from("<i", data, pos)
        ni1.append(c)
        pos += 4
    (ni2_count,) = struct.unpack_from("<i", data, pos)
    pos += 4
    ni2 = []
    for _ in range(ni2_count):
        (c,) = struct.unpack_from("<i", data, pos)
        ni2.append(c)
        pos += 4

    return SngArrangementLevel(
        difficulty=difficulty, anchors=anchors, anchor_extensions=anchor_extensions,
        fingerprints1=fp1, fingerprints2=fp2, notes=notes,
        phrase_count=phrase_count, avg_notes_per_iteration=avg,
        notes_in_iteration1=ni1, notes_in_iteration2=ni2,
    ), pos


def read_sng(data: bytes) -> SngModel:
    """Inverse of :func:`write_sng`."""
    pos = 0

    # 1. Beats
    b_count, pos = _read_count(data, pos)
    beats = []
    for _ in range(b_count):
        t, m, bt, pi, mask = struct.unpack_from(_BEAT_FMT, data, pos)
        pos += _BEAT_SIZE
        beats.append(SngBeat(time=t, measure=m, beat=bt, phrase_iteration=pi, mask=mask))

    # 2. Phrases
    p_count, pos = _read_count(data, pos)
    phrases = []
    for _ in range(p_count):
        solo, disp, ign, _, max_d, pi_links = struct.unpack_from("<BBBBii", data, pos)
        pos += 12
        name = _unpack_str(data[pos : pos + _NAME_LEN])
        pos += _NAME_LEN
        phrases.append(SngPhrase(name=name, solo=solo, disparity=disp, ignore=ign,
                                 max_difficulty=max_d, phrase_iteration_links=pi_links))

    # 3. ChordTemplates
    ct_count, pos = _read_count(data, pos)
    chord_templates = []
    for _ in range(ct_count):
        (mask_,) = struct.unpack_from("<I", data, pos)
        pos += 4
        frets_ = tuple(data[pos : pos + 6])
        pos += 6
        fingers_ = tuple(data[pos : pos + 6])
        pos += 6
        notes_ = struct.unpack_from("<6i", data, pos)
        pos += 24
        name_ = _unpack_str(data[pos : pos + _NAME_LEN])
        pos += _NAME_LEN
        chord_templates.append(SngChordTemplate(
            mask=mask_, frets=frets_, fingers=fingers_, notes=notes_, name=name_,
        ))

    # 4. ChordNotes
    cn_count, pos = _read_count(data, pos)
    chord_notes = []
    for _ in range(cn_count):
        cn, pos = _read_chord_notes_entry(data, pos)
        chord_notes.append(cn)

    # 5. Vocals
    v_count, pos = _read_count(data, pos)
    vocals = []
    for _ in range(v_count):
        t, n, length = struct.unpack_from("<fif", data, pos)
        pos += 12
        lyric = _unpack_str(data[pos : pos + _LYRIC_LEN])
        pos += _LYRIC_LEN
        vocals.append(SngVocal(time=t, note=n, length=length, lyric=lyric))
    if v_count > 0:
        for _ in range(3):  # SymbolsHeader, SymbolsTexture, SymbolsDefinition
            sym_count, pos = _read_count(data, pos)
            # Skip entries (we emit 0 for all)

    # 6. PhraseIterations
    pi_count, pos = _read_count(data, pos)
    phrase_iterations = []
    for _ in range(pi_count):
        pid, st, et, d0, d1, d2 = struct.unpack_from(_PHRASE_ITER_FMT, data, pos)
        pos += _PHRASE_ITER_SIZE
        phrase_iterations.append(SngPhraseIteration(
            phrase_id=pid, start_time=st, end_time=et, difficulty=(d0, d1, d2),
        ))

    # 7-12. Empty sections
    for _ in range(6):
        skip_count, pos = _read_count(data, pos)

    # 13. Sections
    s_count, pos = _read_count(data, pos)
    sections = []
    for _ in range(s_count):
        name_ = _unpack_str(data[pos : pos + _NAME_LEN])
        pos += _NAME_LEN
        num, st, et, spi, epi = struct.unpack_from("<iffii", data, pos)
        pos += struct.calcsize("<iffii")
        sm = data[pos : pos + 36]
        pos += 36
        sections.append(SngSection(name=name_, number=num, start_time=st, end_time=et,
                                   start_phrase_iteration_id=spi, end_phrase_iteration_id=epi,
                                   string_mask=bytes(sm)))

    # 14. Arrangements
    arr_count, pos = _read_count(data, pos)
    arrangements = []
    for _ in range(arr_count):
        level, pos = _read_arrangement_level(data, pos)
        arrangements.append(level)

    # 15. Metadata
    max_sc, max_nc, max_ncr, ppn = struct.unpack_from("<dddd", data, pos)
    pos += 32
    fbl, start_t = struct.unpack_from("<ff", data, pos)
    pos += 8
    (capo,) = struct.unpack_from("<B", data, pos)
    pos += 1
    last_conv = _unpack_str(data[pos : pos + _NAME_LEN])
    pos += _NAME_LEN
    (part,) = struct.unpack_from("<h", data, pos)
    pos += 2
    (song_len,) = struct.unpack_from("<f", data, pos)
    pos += 4
    (str_count,) = struct.unpack_from("<i", data, pos)
    pos += 4
    tuning = []
    for _ in range(str_count):
        (t,) = struct.unpack_from("<h", data, pos)
        tuning.append(t)
        pos += 2
    fnt, fnt2 = struct.unpack_from("<ff", data, pos)
    pos += 8
    (max_diff,) = struct.unpack_from("<i", data, pos)
    pos += 4

    metadata = SngMetadata(
        max_score=max_sc, max_notes_and_chords=max_nc,
        max_notes_and_chords_real=max_ncr, points_per_note=ppn,
        first_beat_length=fbl, start_time=start_t, capo_fret=capo,
        last_conversion=last_conv, part=part, song_length=song_len,
        string_count=str_count, tuning=tuple(tuning),
        first_note_time=fnt, first_note_time2=fnt2, max_difficulty=max_diff,
    )

    return SngModel(
        beats=beats, phrases=phrases, chord_templates=chord_templates,
        chord_notes=chord_notes, vocals=vocals,
        phrase_iterations=phrase_iterations, sections=sections,
        arrangements=arrangements, metadata=metadata,
    )
