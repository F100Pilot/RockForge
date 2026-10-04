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
triples. Musically-identical iterations are collapsed onto a shared phrase
(``_phrase_signature``), so a repeated riff is ONE phrase with many iterations —
learned once and mastered everywhere, like a real DDC — instead of a separate
re-ramping phrase per repeat. The finer NLinkedDifficulty section (linking the
levels of *different* phrases) is still not emitted. See ``_DD_LEVEL_CAP`` and
``_level_notes``.

Intentionally absent — correct given the domain model, not defects:
- No NLinkedDifficulty section (phrases ARE linked by shared id; the finer
  cross-phrase level linkage is not).
- ``ChordNotesId = -1`` for simple chords (matches DLC Builder/EOF).
- Arpeggio fingerprints (Fingerprints2): the domain has no arpeggio marking.
- ParentPrevNote / linkNext: the domain has no note-link concept.
- Note Hash = 0: the two reference tools compute mutually different,
  non-validated hashes, so 0 is the safe, source-consistent choice.

The layout is round-trip-tested but not byte-diffed against a retail SNG.
"""

from __future__ import annotations

import bisect
import struct
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from functools import lru_cache
from pathlib import Path

from rockforge.application.ports import VocalEvent
from rockforge.domain.arrangement import Arrangement, Section, number_sections
from rockforge.domain.chords import chord_display, hand_shape_spans
from rockforge.domain.music import TabNote, Technique, high_density_flags, is_plain_rise
from rockforge.infrastructure.rsxml.vocals import VOCAL_NOTE
from rockforge.infrastructure.rsxml.writer import _safe_tone_time

# The vocals SNG's Symbols sections (SymbolsHeader/Texture/Definition) are the
# lyric font's glyph atlas: without them the game has no glyphs to draw the
# lyrics with, so the letra silently never appears even though the vocals
# arrangement is present. The atlas is song-independent (the default Latin font,
# referencing the built-in game asset ``assets\ui\lyrics\lyrics.dds``); it is
# byte-identical across DLC Builder builds (verified md5-equal between a DLC
# Builder "Free" and "Pride" vocals SNG). Vendored verbatim from a DLC Builder
# build and emitted for every vocals SNG.
_SYMBOLS_BLOCK_PATH = Path(__file__).with_name("vocals_symbols.bin")


@lru_cache(maxsize=1)
def _vocals_symbols_block() -> bytes:
    """The default Latin lyric-font symbol sections, ready to splice into a
    vocals SNG (SymbolsHeader + SymbolsTexture + SymbolsDefinition, counts
    included)."""
    return _SYMBOLS_BLOCK_PATH.read_bytes()


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
    Technique.FRET_MUTE: NOTE_MASK_FRETHANDMUTE,
    Technique.PINCH_HARMONIC: NOTE_MASK_PINCHHARMONIC,
    Technique.TREMOLO: NOTE_MASK_TREMOLO,
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
# sparse one — this is what gives each phrase's bar its own HEIGHT on the in-game
# difficulty graph instead of a flat top. Set to 20 to match a real DDC's range (a
# professional CDLC of Animals As Leaders "Tempting Time" decodes to phrase
# max-difficulties spread 0..18, mode 6). A HARD cap (not a proportional rescale)
# is deliberate: it preserves the natural 0..~18 spread of most phrases and only
# flattens the handful of extreme-density outliers (a fast tapping run can hit
# 50-70 notes/iteration) at the top, where a single outlier would otherwise squash
# every other phrase toward zero. Still a simplified DDC — graduated phrases and
# correct hero triples, no NLinkedDifficulty linkage.
_DD_LEVEL_CAP = 22
# Notes admitted per difficulty level. The game promotes a phrase ONE level per
# successful play of it, so the ceiling is literally how many times the passage
# must be played to reach the full chart. Ramping one note per level (the original
# rule) put the ceiling of almost every phrase at the cap: measured on a realistic
# 756-note chart the ceilings came out spread 11..20 with mode 20, i.e. TWENTY
# perfect playthroughs to see the whole song, and only ~15% of the notes after
# two — which reads in-game as "the difficulty never moves off the minimum", the
# reported bug. Admitting a small GROUP of notes per level reproduces the real
# DDC's shape instead: at 3 the same chart gives ceilings spread 3..15 with mode 7
# against the reference's 0..18 / mode 6. The top level is still the complete
# chart either way (``_level_notes`` saturates at the phrase ceiling) — this only
# sets how fast the player climbs to it.
_NOTES_PER_DD_LEVEL = 2
# Floor on the ceiling of a phrase that HAS notes. Without it a short phrase gets
# (n-1)//NOTES_PER_LEVEL == 0 levels — one level, no ramp, permanently pinned at
# the minimum no matter how well it is played. Byte-diffing a DLC Builder build
# of the user's own song against ours (both decoded from the shipped .psarc)
# showed this directly: a real DDC pass gives EVERY phrase with notes a ceiling
# of at least 4 (its 3-note phrase gets 4), while ours handed out 0 to four
# phrases and 1 to three more out of 29. Its ceilings also run about twice ours
# for the same note count (a 30-note phrase: 16 there, 9 here; a 63-note phrase:
# 22 there, 20 here), which is what _NOTES_PER_DD_LEVEL 3 -> 2 and the cap
# 20 -> 22 close. HONEST LIMIT: this is calibrated against that one reference
# file, not against the game — it removes phrases that provably cannot level up
# and brings the ramp's shape into the reference's range, but whether it is the
# whole of the reported "DD never leaves the minimum" is unverified in-game.
# NOT bounded by the note count: a one-note phrase gets the floor too, its note
# shown at every level up to it. It used to get ceiling 0 ("five identical levels
# would be no ramp") and a phrase with a note but no level to climb crashed the
# game the moment its difficulty was raised in Riff Repeater (September: the
# Lead's one-note phrase at 43.6 s, the Alternate Rhythm's pickup before the
# chorus). DLC Builder's build of that song gives its own one-note phrase SIX
# identical levels, and every phrase with notes there has a ceiling of 3 or more.
_DD_MIN_LEVELS = 4
# DLC Builder's phrase generator (Rocksmith2014.XML.Processing/PhraseGenerator.fs),
# which the native PSARC now follows: a new phrase every 8 measures, never
# closer than this to the previous one, and a "noguitar" phrase over a gap in
# the playing at least this long.
_MIN_PHRASE_SEPARATION_S = 2.0
_MIN_NOGUITAR_PHRASE_S = 2.5
_MEASURES_PER_PHRASE = 8
# Entry sizes of the Sng2014 sections RockForge writes empty but a real file may
# populate. Needed to SKIP them when reading someone else's SNG (see read_sng).
_PHRASE_EXTRA_SIZE = 12   # PhraseExtraInfoByLevel
_ACTION_SIZE = 260        # float time + char[256] name
LAST_CONVERSION = "01-01-00 00:00"   # see SngMetadata.last_conversion
_EVENT_CODE_LEN = 256     # the cue string's fixed field width
_EVENT_SIZE = 4 + _EVENT_CODE_LEN   # float time + char[256] (e2/E3/E13/D3 crowd cues)
_SNG_TONE_SIZE = 8        # float time + int32 tone id
_DNA_SIZE = 8             # float time + int32 dna id
# The SNG's CapoFret byte when the arrangement has no capo (a DLC Builder
# build writes 255; 0 would mean a capo placed at fret 0).
NO_CAPO = 255
_BEND_DATA_COUNT = 32  # fixed-size bend array per string in ChordNotes


def _pack_str(value: str, length: int) -> bytes:
    # A raw byte slice can split a multi-byte UTF-8 character in half, shipping
    # invalid bytes into the packed .sng and crashing _unpack_str on read-back.
    # Decoding with errors="ignore" drops only the incomplete trailing
    # sequence the slice may have cut into, leaving everything before intact.
    raw = value.encode("utf-8")[: length - 1]
    raw = raw.decode("utf-8", errors="ignore").encode("utf-8")
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
    # -1 = none, as DLC Builder writes them (XmlToSngNote.fs): we wrote 0,
    # which is a real value for each (finger 0, and a byte the game reads as a
    # tap/slap/pluck index) — found byte-diffing its September build.
    left_hand: int = -1
    tap: int = -1
    pick_direction: int = -1
    slap: int = -1
    pluck: int = -1
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
    # The reference writes its build time as MM-DD-YY HH:MM. Ours is FIXED, not
    # a timestamp: a value that changes on every rebuild is the kind of thing
    # that could invalidate saved per-song progress, and a deterministic build
    # is worth more here than an accurate date (same reasoning as the
    # deterministic persistent IDs). The format now matches the reference.
    last_conversion: str = LAST_CONVERSION
    part: int = 1
    song_length: float = 0.0
    string_count: int = 6
    tuning: tuple[int, ...] = (0, 0, 0, 0, 0, 0)
    first_note_time: float = 0.0
    first_note_time2: float = 0.0
    max_difficulty: int = 0


@dataclass(frozen=True)
class SngEvent:
    """One stage/crowd cue on the song timeline (SNG section 10)."""

    time: float
    code: str


# The crowd/stage cue track a DLC Builder build carries. Ours shipped an EMPTY
# Events section, which leaves the venue inert. The rule below is not invented:
# it is read off a DLC Builder build of the user's song and confirmed to hold
# independently on BOTH of its arrangements, whose start/first-note times differ
# (lead 6.421/8.0, rhythm 5.0/13.421):
#
#   e2  at the arrangement's start_time      (6.421 / 5.0)
#   E3  at first_note + _EVENT_INTRO_LEAD_S  (8.6   / 14.021)
#   E13 at E3 + _EVENT_INTRO_HOLD_S          (11.1  / 16.521)
#   D3  at song_length - _EVENT_OUTRO_LEAD_S (193.509 both)
#   E13 at song_length                       (202.509 both)
#
# What each code MEANS to the game is not documented anywhere we can cite, so
# nothing here is derived from the codes' semantics — only their placement is
# reproduced. They are inert 256-byte strings in a section the game reads for
# venue/crowd staging, not note geometry.
_EVENT_INTRO_LEAD_S = 0.6
_EVENT_INTRO_HOLD_S = 2.5
_EVENT_OUTRO_LEAD_S = 9.0


def _build_tones(arr: Arrangement) -> list[SngTone]:
    """The arrangement's tone changes as the game reads them. This section went
    out EMPTY, so no tone change ever happened in game from the native PSARC —
    only the base tone played, whatever was marked on the score. The id is the
    change's slot in ``switch_slots`` (Tone_A..D in the manifest); a change to a
    tone outside those slots has nothing to switch to and is left out. The time
    is the XML writer's, nudged off a note (DLC Builder refuses a change on one)."""
    slots = arr.switch_slots()
    note_times = sorted(n.time for n in arr.notes)
    return [
        SngTone(time=_safe_tone_time(tc.time, note_times), tone_id=slots.index(tc.name))
        for tc in sorted(arr.tone_changes, key=lambda c: c.time)
        if tc.name in slots
    ]


def _build_events(
    start_time: float, first_note_time: float, song_length: float
) -> list[SngEvent]:
    """The five stage cues, in the reference's order and placement."""
    if song_length <= 0:
        return []
    intro = first_note_time + _EVENT_INTRO_LEAD_S
    candidates = [
        SngEvent(time=start_time, code="e2"),
        SngEvent(time=intro, code="E3"),
        SngEvent(time=intro + _EVENT_INTRO_HOLD_S, code="E13"),
        SngEvent(time=song_length - _EVENT_OUTRO_LEAD_S, code="D3"),
        SngEvent(time=song_length, code="E13"),
    ]
    # The cues are defined in CHRONOLOGICAL order above, and the game expects
    # the track that way. On a song shorter than the intro+outro leads the
    # outro cue's natural time falls before the intro ones; DROP it rather than
    # clamping it to 0, which would emit a "nine seconds from the end" cue at
    # the very start. Same for any cue past the end.
    ordered: list[SngEvent] = []
    for ev in candidates:
        if 0.0 <= ev.time <= song_length and (not ordered or ev.time >= ordered[-1].time):
            ordered.append(ev)
    return ordered


@dataclass
class SngTone:
    """A tone change: at ``time`` switch to slot ``tone_id`` (0-3 = Tone_A..D)."""

    time: float
    tone_id: int


@dataclass
class SngModel:
    beats: list[SngBeat] = field(default_factory=list)
    phrases: list[SngPhrase] = field(default_factory=list)
    chord_templates: list[SngChordTemplate] = field(default_factory=list)
    chord_notes: list[SngChordNotes] = field(default_factory=list)
    vocals: list[SngVocal] = field(default_factory=list)
    phrase_iterations: list[SngPhraseIteration] = field(default_factory=list)
    events: list[SngEvent] = field(default_factory=list)
    tones: list[SngTone] = field(default_factory=list)
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


def _phrase_signature(
    notes: list[TabNote], start: float, end: float
) -> tuple[tuple[object, ...], ...] | None:
    """A hashable fingerprint of the notes in ``[start, end)``, relative to
    ``start``, so two iterations of the SAME riff match and can share one phrase.

    Returns ``None`` for a span with no notes — a COUNT/END/no-guitar gap stays a
    distinct phrase rather than collapsing all silences onto one. Relative times
    are quantised to 10 ms (identical riffs at the same tempo line up; a tempo
    change shifts them and correctly keeps them separate). Sustain, techniques,
    slide and bend count too: a linked phrase is ONE phrase to the game, and
    September's shipped two "identical" passages where one had a pull-off (or a
    let-ring sustain) the other did not — a DLC Builder build links only equals."""
    span = [n for n in notes if start <= n.time < end]
    if not span:
        return None
    return tuple(sorted(
        (
            round((n.time - start) * 100), n.string, n.fret, round(n.sustain * 100),
            tuple(sorted(t.value for t in n.techniques)),
            n.slide_to_fret, n.slide_unpitch_to, round(n.bend_semitones * 100),
        )
        for n in span
    ))


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
    # Before the first beat or after the last — treat as a beat-strength note by
    # proximity to the NEAREST edge beat: beats[0] before the song starts,
    # beats[-1] after it ends. The old code always compared to beats[0], so a
    # note near the song's FINAL downbeat never registered as a downbeat (tier 0)
    # and always fell to tier 1 regardless of where it actually sat.
    if not beats:
        return 1
    edge = beats[0] if time < beats[0].time else beats[-1]
    return 0 if (edge.mask & 1 and abs(time - edge.time) < eps) else 1


def _note_mask(n: TabNote, is_chord: bool = False, is_double_stop: bool = False) -> int:
    mask = 0
    for tech in n.techniques:
        mask |= TECHNIQUE_TO_MASK.get(tech, 0)
    # BEND keys off the actual bend amount, not only Technique.BEND, so the mask
    # agrees with the emitted bend point. A DLC Builder SNG of a bent chord marks
    # the bent string 0x3000 (BEND | SUSTAIN); we mirror that.
    if n.bend_semitones > 0:
        mask |= NOTE_MASK_BEND
    if n.slide_to_fret is not None:
        mask |= NOTE_MASK_SLIDE
    if n.slide_unpitch_to is not None:
        mask |= NOTE_MASK_SLIDEUNPITCHEDTO
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
    """The bend curve for a note, matching a decoded DLC Builder SNG.

    Byte-diffing a DLC Builder build of this chart: a bent note carries a SINGLE
    bend point at the note's END (attack + sustain) with step = the bend in
    half-steps (a half-step bend → 1.0). The lone point at the end makes the game
    ramp the pitch UP across the whole note — a visible bend. Placing it at the
    ATTACK instead (our first working attempt) is a prebend: the note starts
    already bent, so the bend looks smaller. Floored for a staccato note.
    """
    if n.bend_semitones <= 0:
        return []
    dur = n.sustain if n.sustain > 0.03 else 0.1
    if n.bend_points and not is_plain_rise(n.bend_points):
        # Full curve (pre-bend / release / multi-step): fractional positions
        # scaled onto the note's duration. A plain rise across the note is the
        # single point at the end.
        return [SngBendData32(time=n.time + p.position * dur, step=p.step)
                for p in n.bend_points]
    return [SngBendData32(time=n.time + dur, step=n.bend_semitones)]


def _section_end_times(sections: list[Section], song_length: float) -> list[float]:
    if not sections:
        return []
    return [s.start_time for s in sections[1:]] + [song_length]


def _find_phrase_iteration(
    phrase_iters: list[SngPhraseIteration],
    time: float,
    starts: list[float] | None = None,
) -> int:
    """Index of the phrase iteration containing ``time``.

    A time BEFORE the first iteration's start (e.g. the silent pad before the
    COUNT phrase, at the very start of the song) must resolve to the FIRST
    index, not fall through to the "after everything" fallback below — that
    wrapped a song-start anchor/beat onto the phrase_iteration_id of the LAST
    phrase in the song (index len-1, e.g. 26 on a real chart), corrupting the
    fret-hand anchor box and the beat grid right at the opening notes with a
    context from the song's ending. Only a time genuinely PAST the last
    iteration's end falls to that fallback.

    Iterations tile [first.start, song_length] contiguously (each end_time is
    the next start_time — see ``_section_end_times``), so a single
    ``bisect_right`` on the start times reproduces the old linear containment
    scan exactly (before-first → 0, past-end → last), in O(log n) instead of
    O(n) per call — this is called once per note/beat across up to ~21 DD
    levels. Pass a precomputed ``starts`` (the iteration start times) to avoid
    rebuilding it on every call inside a hot loop; it is built on demand when
    omitted.
    """
    if not phrase_iters:
        return 0
    if starts is None:
        starts = [pi.start_time for pi in phrase_iters]
    return min(len(phrase_iters) - 1, max(0, bisect.bisect_right(starts, time) - 1))


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
    pi_starts = [pi.start_time for pi in phrase_iterations]
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
            phrase_iteration_id=_find_phrase_iteration(phrase_iterations, t, pi_starts),
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
                phrase_iteration_id=_find_phrase_iteration(phrase_iterations, seg_start, pi_starts),
            ))
            seg_start = seg_end
    return split_anchors


# What DLC Builder writes for an anchor with no note in it (XmlToSng.fs's
# UninitFirstNote/UninitLastNote: float32 max and the smallest normal float32).
ANCHOR_NO_NOTE_FIRST = 3.4028234663852886e38
ANCHOR_NO_NOTE_LAST = 1.1754943508222875e-38


def _anchor_note_times(anchors: list[SngAnchor], notes: list[SngNote]) -> list[SngAnchor]:
    """Each anchor's first/last note time, over the notes INSIDE it
    (``start <= t < end``), as DLC Builder's ``convertAnchor`` computes them.

    ``_build_anchors`` carried the times of the whole greedy window into every
    per-phrase piece it was split into, so a piece could claim a last note a
    minute past its own end, or a first note after its last. The last note's
    sustain counts unless it slides (DLC Builder's rule); an anchor with no
    note gets DLC Builder's uninitialised pair, not a made-up time.
    """
    times = [n.time for n in notes]
    out: list[SngAnchor] = []
    for a in anchors:
        lo = bisect.bisect_left(times, a.start_time)
        hi = bisect.bisect_left(times, a.end_time)
        if lo >= hi:
            out.append(replace(
                a, first_note_time=ANCHOR_NO_NOTE_FIRST, last_note_time=ANCHOR_NO_NOTE_LAST,
            ))
            continue
        last = notes[hi - 1]
        slides = last.mask & (NOTE_MASK_SLIDE | NOTE_MASK_PARENT)
        out.append(replace(
            a, first_note_time=notes[lo].time,
            last_note_time=last.time if slides else last.time + last.sustain,
        ))
    return out


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


def _build_fingerprints(notes: list[SngNote]) -> list[SngFingerprint]:
    """The level's hand shapes, stamping each note inside one with its index
    (``notes`` is mutated in place: DLC Builder's ``findFingerPrintId`` gives
    every note in ``[start, end)`` that shape's index)."""
    spans = hand_shape_spans([(n.time, n.sustain, n.chord_id) for n in notes])
    fingerprints: list[SngFingerprint] = []
    for k, (chord_id, first, last, end) in enumerate(spans):
        start = notes[first].time
        last_end = notes[last].time + notes[last].sustain
        fingerprints.append(SngFingerprint(
            chord_id=chord_id,
            start_time=start,
            end_time=end,
            first_note_time=start,
            last_note_time=last_end if last_end < end else -1.0,
        ))
        for i in range(first, last + 1):
            notes[i] = replace(notes[i], fingerprint_id=(k, notes[i].fingerprint_id[1]))
    return fingerprints


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
    crashing the game on phrase entry). So are the hand shapes (fingerprints):
    one per run of identical chords among THIS level's notes
    (``hand_shape_spans``), each chord pointing at its own — the shape the game
    draws the chord's fingers from. Their first/last note times follow DLC
    Builder's ``convertHandshape`` (XmlToSng.fs).
    """
    linked = list(notes)
    # `linked` is time-sorted (guaranteed by the sng_notes.sort() upstream in
    # from_arrangement), so each phrase iteration's note range is a contiguous
    # slice locatable by binary search — O(phrases * log notes) — instead of
    # rescanning the WHOLE note list per phrase iteration (O(phrases * notes),
    # run again for the notes_in_iter count below: on a long song this was
    # tens of millions of comparisons per Dynamic Difficulty level, of which
    # there are up to ~21). The two rescans collapse into one pass here, since
    # notes_in_iter is just len(idxs).
    times = [n.time for n in linked]
    notes_in_iter: list[int] = []
    for pi in phrase_iterations:
        lo = bisect.bisect_left(times, pi.start_time)
        hi = bisect.bisect_left(times, pi.end_time)
        idxs = list(range(lo, hi))
        for j, gi in enumerate(idxs):
            linked[gi] = replace(
                linked[gi],
                prev_iter_note=idxs[j - 1] if j > 0 else -1,
                next_iter_note=idxs[j + 1] if j < len(idxs) - 1 else -1,
            )
        notes_in_iter.append(len(idxs))
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

    anchors = _anchor_note_times(_build_anchors(
        _level_positions(linked, chord_templates, song_length), phrase_iterations, song_length
    ), linked)

    # A note's anchor is the one of ITS level that it falls in (DLC Builder's
    # XmlToSngNote: `findAnchor timeCode level.Anchors`), not the full chart's:
    # a thinned level frames its notes differently (September's Alternate
    # Rhythm: fret 2 from level 17 up, while every note still said fret 1), and
    # the game crashed the moment the difficulty was raised into such a level.
    anchor_starts = [a.start_time for a in anchors]
    for gi, n in enumerate(linked):
        if not anchors:
            break
        a = anchors[max(0, bisect.bisect_right(anchor_starts, n.time) - 1)]
        if (n.anchor_fret, n.anchor_width) != (a.fret, a.width):
            linked[gi] = replace(n, anchor_fret=a.fret, anchor_width=a.width)

    fingerprints = _build_fingerprints(linked)

    return SngArrangementLevel(
        difficulty=difficulty,
        anchors=anchors,
        anchor_extensions=anchor_extensions,
        fingerprints1=fingerprints,
        fingerprints2=[],
        notes=linked,
        phrase_count=phrase_count,
        avg_notes_per_iteration=avg_per_iter,
        notes_in_iteration1=notes_in_iter,
        notes_in_iteration2=notes_in_iter,
    )


def _build_beats(arrangement: Arrangement) -> list[SngBeat]:
    """Beats with measure/beat-in-measure/mask filled. ``phrase_iteration``
    is stamped later by :func:`_assign_beat_phrase_iterations`, once the
    phrase timeline exists.

    The SNG stores the real measure number on EVERY beat (not -1 for off-beats
    as the domain does), the beat-within-measure, and a mask (bit0 = downbeat,
    bit1 = even measure). Track the running measure to fill both.
    """
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
    return beats


def _assign_beat_phrase_iterations(
    beats: list[SngBeat], phrase_iterations: list[SngPhraseIteration]
) -> list[SngBeat]:
    starts = [pi.start_time for pi in phrase_iterations]
    return [
        SngBeat(
            time=b.time,
            measure=b.measure,
            beat=b.beat,
            phrase_iteration=_find_phrase_iteration(phrase_iterations, b.time, starts),
            mask=b.mask,
        )
        for b in beats
    ]


def _chart_hand_shapes(groups: list[list[TabNote]]) -> list[tuple[float, float]]:
    """``(start, end)`` of the full chart's hand shapes — the ones the XML hands
    DLC Builder (same ``hand_shape_spans``), which its phrase generator avoids."""
    keys: dict[tuple[int, ...], int] = {}
    rows = []
    for g in groups:
        cid = keys.setdefault(_chord_template_key(g), len(keys)) if len(g) > 1 else -1
        rows.append((g[0].time, max(n.sustain for n in g), cid))
    return [(rows[a][0], end) for _, a, _, end in hand_shape_spans(rows)]


def _good_phrase_time(
    notes: list[TabNote], t: float, shapes: Sequence[tuple[float, float]] = ()
) -> tuple[float, float]:
    """The nearest times before and after ``t`` that are inside neither a
    single note's sustain nor a hand shape — PhraseGenerator.fs
    ``findGoodPhraseTime``, over ``level.Notes`` (the single notes: a chord is
    kept whole by its hand shape) and ``level.HandShapes``. The point is to
    land exactly where its build of our XML does."""
    def find(earlier: bool, time: float) -> float:
        for _ in range(20):  # the reference's own guard against a loop
            inside = next((n for n in notes if n.time < time < n.time + n.sustain), None)
            if inside is not None:
                time = inside.time if earlier else inside.time + inside.sustain
                continue
            shape = next((hs for hs in shapes if hs[0] < time < hs[1]), None)
            if shape is None:
                return time
            time = shape[0] if earlier else shape[1]
        return time
    return find(True, t), find(False, t)


def _prepare_sections(arrangement: Arrangement, song_length: float) -> list[Section]:
    """The phrase timeline, generated the way DLC Builder does when it builds a
    package (``PhraseGenerator.generate``) — the structure of the September
    build that plays, where ours crashed.

    COUNT from the first beat to the first note (every empty section before it
    is part of the count-in, not a phrase of its own); then a phrase at the
    first note and one every 8 measures, moved out of any sustained note and
    never within 2 s of the previous one; a "noguitar" section over any gap of
    2.5 s or more, with the next phrase where the playing resumes; END where
    the XML has it (the last beat, past the last note). Sections are "riff"/"noguitar" — names the
    game has localisation tokens for. The Guitar Pro section names do not reach
    the native SNG (DLC Builder's build does not carry them either); the XML
    for DLC Builder still has them.
    """
    notes = sorted(arrangement.notes, key=lambda n: n.time)
    beats = arrangement.tempo_map.beats
    if not notes or not beats:
        start = beats[0].time if beats else 0.0
        end = max(start + 0.1, min(song_length, beats[-1].time if beats else song_length))
        return [Section(name="COUNT", number=1, start_time=start),
                Section(name="END", number=1, start_time=end)]

    chart_groups = _group_chords(notes)
    singles = [g[0] for g in chart_groups if len(g) == 1]
    shapes = _chart_hand_shapes(chart_groups)
    content_start = notes[0].time
    content_end = max(n.time + max(n.sustain, 0.0) for n in notes)
    # END where the XML we hand DLC Builder puts it (the last beat, or just past
    # the last note's tail): its generator keeps an existing END that comes
    # after the content, and the XML always has one.
    last_beat = beats[-1].time
    end_t = last_beat if last_beat > content_end else content_end + 0.1
    if song_length > 0:
        # A last beat ON the song's end would make END empty; the reference's
        # own fallback stops 100 ms short of the end.
        end_t = min(end_t, song_length - 0.1)

    first_beat = beats[0].time
    if first_beat >= content_start:
        # The reference inserts a beat one beat-length earlier for the COUNT.
        step = beats[1].time - first_beat if len(beats) > 1 else 0.5
        count_t = max(0.0, first_beat - step)
    else:
        count_t = first_beat

    secs = [Section(name="riff", number=1, start_time=content_start)]
    if count_t < content_start:
        secs.insert(0, Section(name="COUNT", number=1, start_time=count_t))
    # else: a chart playing from time 0 has no room for a count-in (DLC Builder
    # refuses to build one); it starts on its first phrase.
    counter = 0
    next_t: float | None = None
    for beat in beats:
        if beat.time < content_start:
            continue
        if beat.time >= end_t:
            break
        if beat.measure >= 0 and next_t is None:
            counter += 1
        if counter > _MEASURES_PER_PHRASE or (next_t is not None and beat.time >= next_t):
            counter = 1
            prev = secs[-1].start_time
            if next_t is None:
                earlier, later = _good_phrase_time(singles, beat.time, shapes)
                closest = earlier if beat.time - earlier < later - beat.time else later
                if closest - prev > _MIN_PHRASE_SEPARATION_S:
                    ok, t = True, closest
                elif later - prev > _MIN_PHRASE_SEPARATION_S:
                    ok, t = True, later
                else:
                    ok, t = False, later
            else:
                ok, t, next_t = True, next_t, None
            if not ok or t >= end_t:
                continue
            upcoming = next((n.time for n in notes if n.time >= t), None)
            name = "riff"
            if upcoming is None:
                name = "noguitar"
            elif upcoming - t >= _MIN_NOGUITAR_PHRASE_S:
                next_t = upcoming
                name = "noguitar"
            secs.append(Section(name=name, number=1, start_time=t))
    secs.append(Section(name="END", number=1, start_time=end_t))
    # Strictly increasing, whatever the grid did.
    out = [secs[0]]
    for sec in secs[1:]:
        if sec.start_time > out[-1].start_time:
            out.append(sec)
    return out


# Phrase names are UNIQUE per phrase (p0, p1, …), not the section name repeated.
# A GP file with no section markers is auto-segmented into spans all called
# "riff" (see _default_sections), so a 200 s song shipped 27 phrases sharing one
# name while a real DDC emits p0…pN — all distinct — and keeps the descriptive
# names on the SECTIONS instead, which are a separate list. This is
# song-specific: a GP that DOES carry markers already produced varied names,
# which is why the symptom follows the song rather than the build.
_STRUCTURAL_PHRASE_NAMES = frozenset({"COUNT", "END", "NOGUITAR", "noguitar"})


def _body_count(names: list[str]) -> int:
    """How many non-structural phrases have been named so far."""
    return sum(1 for n in names if n not in _STRUCTURAL_PHRASE_NAMES)


def _phrase_name(section_name: str, body_index: int) -> str:
    """``COUNT``/``END``/``NOGUITAR`` keep their structural name; everything else
    becomes ``p<N>``, matching what a real DDC pass emits."""
    if section_name in _STRUCTURAL_PHRASE_NAMES:
        return section_name
    return f"p{body_index}"


def _link_phrases(
    arrangement: Arrangement, sections_src: list[Section], ends: list[float]
) -> tuple[list[SngPhrase], list[SngPhraseIteration]]:
    """Collapse musically-identical iterations onto ONE shared phrase: a real DDC
    recognises a repeated riff as a single phrase with many iterations, so it's
    learned once and every repeat plays at the mastered difficulty instead of
    re-ramping from scratch (and the difficulty graph / Riff Repeater show the
    song's true handful of unique phrases, not one bar per section). Note-less
    spans (COUNT/END/gaps) keep a distinct phrase each. This is phrase-level
    linking via shared phrase_id — NOT the finer NLinkedDifficulty section,
    which stays empty.
    """
    _sig_to_id: dict[tuple[tuple[object, ...], ...], int] = {}
    _phrase_names: list[str] = []
    _iter_phrase_id: list[int] = []
    noguitar_id: int | None = None
    for s, end in zip(sections_src, ends, strict=True):
        if s.name == "noguitar":
            # DLC Builder's build: every gap is an iteration of ONE phrase
            # named NOGUITAR (its section keeps the name "noguitar").
            if noguitar_id is None:
                noguitar_id = len(_phrase_names)
                _phrase_names.append("NOGUITAR")
            _iter_phrase_id.append(noguitar_id)
            continue
        sig = _phrase_signature(arrangement.notes, s.start_time, end)
        if sig is not None and sig in _sig_to_id:
            _iter_phrase_id.append(_sig_to_id[sig])
        else:
            pid = len(_phrase_names)
            _phrase_names.append(_phrase_name(s.name, _body_count(_phrase_names)))
            if sig is not None:
                _sig_to_id[sig] = pid
            _iter_phrase_id.append(pid)
    phrases = [SngPhrase(name=nm) for nm in _phrase_names]
    phrase_iterations = [
        SngPhraseIteration(phrase_id=_iter_phrase_id[i], start_time=s.start_time, end_time=end)
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
    return phrases, phrase_iterations


def _build_chord_data(
    arrangement: Arrangement, chord_groups: list[list[TabNote]]
) -> tuple[
    dict[tuple[int, ...], int],
    list[SngChordTemplate],
    list[SngChordNotes],
    dict[int, int],
]:
    """Chord templates (per-string MIDI/frets) and ChordNotes (per-string
    technique/sustain state) for every chord group. Returns
    ``(template_ids, chord_templates, chord_notes_list, chord_notes_map)``,
    where ``chord_notes_map`` keys the chord GROUP index (not the template).
    """
    template_ids: dict[tuple[int, ...], int] = {}
    open_midi = arrangement.tuning.midi  # MIDI pitch of each open string
    chord_templates: list[SngChordTemplate] = []
    for g in chord_groups:
        key = _chord_template_key(g)
        if key not in template_ids:
            template_ids[key] = len(template_ids)
            frets_bytes = tuple(max(0, f) if f >= 0 else 255 for f in key)
            # MIDI note sounding on each used string (open pitch + fret); -1 for
            # unused strings — byte-verified against a DLC Builder build of the
            # SAME song (its 5/7 octave template carries [-1, 50, -1, 62, -1, -1]).
            # Writing 0 (a real, absurdly low pitch on a string that shouldn't
            # sound) crashed the game at the octave's entry, but ONLY while the
            # player was actually scoring the chord — the per-string MIDI is
            # dereferenced by the note-detection/scoring path, so a spectating
            # run never touched it.
            notes_midi = tuple(
                open_midi[i] + f if f >= 0 else -1 for i, f in enumerate(key)
            )
            # The fingers and the name Rocksmith shows on the chord (they were
            # -1 and "": the game had nothing to show) — chords.py.
            fingers, name = chord_display(key, g, open_midi)
            chord_templates.append(SngChordTemplate(
                mask=0,
                frets=frets_bytes,
                fingers=fingers,
                notes=notes_midi,
                name=name,
            ))

    # Identical entries are deduplicated by content, as retail does (a decoded
    # CDLC carries 11 entries for ~2200 chords).
    chord_notes_list: list[SngChordNotes] = []
    chord_notes_map: dict[int, int] = {}  # group_index -> chord_notes_id
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
        # A chord needs a ChordNotes entry to carry per-string state the chord
        # TEMPLATE alone can't — not only techniques but SUSTAIN. Byte-diffing a
        # DLC Builder build of this song: every ChordNotes entry carries the
        # per-string SUSTAIN bit (0x2000), and there are entries with ONLY
        # sustain (no technique) — DLC Builder emits one for every sustained
        # chord. Omitting it (the old "techniques only" rule) left a sustained
        # power-chord chug with chord_notes_id = -1, so the game had no
        # per-string sustain to render and drew corrupt vertical/lateral bars on
        # the highway (visible only while streaming notes in Riff Repeater / when
        # scrubbing). _note_mask already yields SUSTAIN|OPEN|PALMMUTE per string,
        # matching DLC Builder's 0x2000/0x2004/0x2040/0x2044 exactly.
        needs_chord_notes = any(
            n.techniques or n.bend_semitones > 0
            or n.slide_to_fret is not None or n.slide_unpitch_to is not None
            or n.sustain > 0
            for n in g
        )
        if not needs_chord_notes:
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
            if n.bend_semitones > 0:
                cn.bend_data[n.string] = _bend_points(n)
            if n.slide_to_fret is not None:
                cn.slide_to[n.string] = n.slide_to_fret
            if n.slide_unpitch_to is not None:
                cn.slide_unpitch_to[n.string] = n.slide_unpitch_to
            if Technique.VIBRATO in n.techniques:
                cn.vibrato[n.string] = 80
        cn_key = _cn_key(cn)
        if cn_key not in cn_ids:
            cn_ids[cn_key] = len(chord_notes_list)
            chord_notes_list.append(cn)
        chord_notes_map[gi] = cn_ids[cn_key]

    return template_ids, chord_templates, chord_notes_list, chord_notes_map


def _build_sng_notes(
    single_groups: list[list[TabNote]],
    chord_groups: list[list[TabNote]],
    anchors: list[SngAnchor],
    phrase_iterations: list[SngPhraseIteration],
    template_ids: dict[tuple[int, ...], int],
    chord_notes_map: dict[int, int],
) -> list[SngNote]:
    """Single-note and chord SngNotes, time-sorted.

    ``anchor_fret``/``anchor_width`` here come from the full-chart ``anchors``
    and are provisional: ``_build_level`` rebuilds each level's anchors from its
    own notes and re-points every note at the anchor of ITS level.

    (Anchor extensions — the slide re-anchors — are built per difficulty level
    inside ``_build_level``, from each level's own notes, and so are the hand
    shapes and each note's ``fingerprint_id``.)
    """
    sng_notes: list[SngNote] = []
    # Precomputed once so the per-note lookups below are O(log n), not O(n):
    # both lists are already time-sorted (anchors by first_note_time, iterations
    # by start_time), and these run once per single note AND per chord.
    pi_starts = [pi.start_time for pi in phrase_iterations]
    anchor_first_times = [a.first_note_time for a in anchors]

    def _find_anchor(time: float) -> tuple[int, int]:
        # Last anchor whose first_note_time <= time (bisect reproduces the old
        # reversed-linear scan); a time before the first anchor falls to
        # anchors[0], and an empty anchor list to the neutral (1, 4) default.
        if not anchors:
            return 1, 4
        idx = max(0, bisect.bisect_right(anchor_first_times, time) - 1)
        return anchors[idx].fret, anchors[idx].width

    # Single notes
    for g in single_groups:
        sn = g[0]
        mask = _note_mask(sn, is_chord=False)
        a_fret, a_width = _find_anchor(sn.time)
        pi_id = _find_phrase_iteration(phrase_iterations, sn.time, pi_starts)
        sng_notes.append(SngNote(
            time=sn.time,
            string=sn.string,
            fret=sn.fret,
            sustain=sn.sustain,
            bend=sn.bend_semitones,
            mask=mask,
            anchor_fret=a_fret,
            anchor_width=a_width,
            phrase_id=phrase_iterations[pi_id].phrase_id,
            phrase_iteration_id=pi_id,
            slide_to=sn.slide_to_fret if sn.slide_to_fret is not None else -1,
            slide_unpitch_to=sn.slide_unpitch_to if sn.slide_unpitch_to is not None else -1,
            left_hand=sn.left_hand,
            # DLC Builder: 1 for an upstroke, else 0 (a single note always
            # carries one of the two; our 2 = up is not a value it writes).
            pick_direction=1 if sn.pick_direction == 2 else 0,
            slap=1 if Technique.SLAP in sn.techniques else -1,
            pluck=1 if Technique.POP in sn.techniques else -1,
            tap=1 if Technique.TAP in sn.techniques else -1,
            vibrato=80 if Technique.VIBRATO in sn.techniques else 0,
            bend_data=_bend_points(sn),
        ))

    # Chord notes
    hd_flags = high_density_flags(chord_groups)
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
        # Mirror techniques from individual notes onto chord mask
        for n in g:
            for tech in n.techniques:
                mask |= TECHNIQUE_TO_MASK.get(tech, 0)
        if any(n.sustain > 0 for n in g):
            mask |= NOTE_MASK_SUSTAIN
        # A repeated identical chord renders condensed; without this the full
        # chord boxes of a fast chug stack into a corrupt highway sprite.
        if hd_flags[gi]:
            mask |= NOTE_MASK_HIGHDENSITY
        mask |= NOTE_MASK_STRUM
        a_fret, a_width = _find_anchor(g[0].time)
        pi_id = _find_phrase_iteration(phrase_iterations, g[0].time, pi_starts)
        sng_notes.append(SngNote(
            time=g[0].time,
            string=-1,
            fret=-1,
            sustain=max(n.sustain for n in g),
            bend=max(n.bend_semitones for n in g),
            mask=mask,
            anchor_fret=a_fret,
            anchor_width=a_width,
            chord_id=chord_id,
            chord_notes_id=cn_id,
            phrase_id=phrase_iterations[pi_id].phrase_id,
            phrase_iteration_id=pi_id,
            bend_data=[],
        ))

    sng_notes.sort(key=lambda n: n.time)
    return sng_notes


# The SNG SECTION name for a structural phrase. A DLC Builder build keeps the
# COUNT phrase but gives it NO section at all (19 sections over 20 phrase
# iterations, starting at iteration 1), and names the END phrase's section
# "noguitar" — the same closer the XML writer already appends. The PHRASE keeps
# its structural name either way; only the section list differs.
_NO_SECTION_PHRASE_NAMES = frozenset({"COUNT"})
_SECTION_CLOSER_NAME = "noguitar"
_CLOSER_PHRASE_NAMES = frozenset({"END"})


def _build_sng_sections(
    sections_src: list[Section], ends: list[float], phrase_iterations: list[SngPhraseIteration]
) -> list[SngSection]:
    pi_starts = [pi.start_time for pi in phrase_iterations]
    named: list[Section] = []
    spans: list[tuple[float, float]] = []
    for sec, end in zip(sections_src, ends, strict=True):
        if sec.name in _NO_SECTION_PHRASE_NAMES:
            continue
        name = _SECTION_CLOSER_NAME if sec.name in _CLOSER_PHRASE_NAMES else sec.name
        named.append(replace(sec, name=name))
        spans.append((sec.start_time, end))

    # Per-NAME ordinals, not list indices — see domain.number_sections.
    numbered, _counts = number_sections(named)
    sections: list[SngSection] = []
    for sec, (start, end) in zip(numbered, spans, strict=True):
        start_pi = _find_phrase_iteration(phrase_iterations, start, pi_starts)
        end_pi = (
            _find_phrase_iteration(phrase_iterations, end - 0.001, pi_starts)
            if end > 0 else start_pi
        )
        sections.append(SngSection(
            name=sec.name,
            number=sec.number,
            start_time=start,
            end_time=end,
            start_phrase_iteration_id=start_pi,
            end_phrase_iteration_id=end_pi,
        ))
    return sections


def renumber_sections_across(models: Sequence[SngModel]) -> list[SngModel]:
    """Continue each section NAME's numbering across a song's arrangements.

    A DLC Builder build numbers sections once over the whole project rather
    than per arrangement: its Lead riffs run 1-17 and its Rhythm riffs continue
    18-34 (noguitars 1-2 then 3-4). Pure: returns new models, in the order
    given, so the packer can apply it before both the manifests and the .sng
    payloads are derived from them and the two can never disagree.
    """
    counts: dict[str, int] = {}
    out: list[SngModel] = []
    for model in models:
        plain = [Section(name=s.name, start_time=s.start_time) for s in model.sections]
        numbered, counts = number_sections(plain, counts)
        out.append(replace(model, sections=[
            replace(s, number=n.number) for s, n in zip(model.sections, numbered, strict=True)
        ]))
    return out


def _apply_section_string_masks(
    sections: list[SngSection],
    levels: list[SngArrangementLevel],
    chord_templates: list[SngChordTemplate],
) -> list[SngSection]:
    """Fill each section's 36-byte StringMask: one byte per difficulty level, a
    bitmask of the strings actually played in that section AT that level.

    This was left as 36 zero bytes, which tells the game "no string is played at
    any difficulty in this section". It is per-DIFFICULTY data the engine reads
    when deciding what a section contains at each level, so leaving it blank is
    unambiguously wrong versus the format (a real DDC-built SNG has non-zero
    entries for levels 0..maxDD of every section that has notes).

    A chord note carries string -1; its sounding strings come from its chord
    template's frets (a real fret is 0..24, the unused slots are the -1/255
    sentinel).
    """
    if not sections:
        return sections
    out: list[SngSection] = []
    for sec in sections:
        mask = bytearray(36)
        for lvl in levels:
            d = lvl.difficulty
            if not 0 <= d < 36:
                continue
            bits = 0
            for n in lvl.notes:
                if not (sec.start_time - 1e-6 <= n.time < sec.end_time - 1e-6):
                    continue
                if 0 <= n.string <= 5:
                    bits |= 1 << n.string
                elif 0 <= n.chord_id < len(chord_templates):
                    for si, fret in enumerate(chord_templates[n.chord_id].frets[:6]):
                        if 0 <= fret <= 24:
                            bits |= 1 << si
            mask[d] = bits
        out.append(replace(sec, string_mask=bytes(mask)))
    return out


def _build_difficulty_levels(
    sng_notes: list[SngNote],
    beats: list[SngBeat],
    phrases: list[SngPhrase],
    phrase_iterations: list[SngPhraseIteration],
    chord_templates: list[SngChordTemplate],
    chord_notes_list: list[SngChordNotes],
    song_length: float,
    dynamic_difficulty: bool,
) -> tuple[list[SngPhrase], list[SngPhraseIteration], list[SngArrangementLevel], int]:
    """DDC-style graduated levels: notes ramp in per phrase over several
    difficulty levels. A real Rocksmith DD ramps each note in over many
    levels, per phrase, so the in-game difficulty slider spans 0..songMax
    (verified against a DLC Builder / DDC reference SNG: 23 levels, per-phrase
    ceilings graduated by density, and per-iteration hero triples of
    (~¼, ~½, 1)·max). We reproduce that shape.

    Returns the updated ``phrases``/``phrase_iterations`` (stamped with
    ``max_difficulty``/``difficulty``), one ``SngArrangementLevel`` per level,
    and the song's ``max_difficulty``.
    """
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

    # Per-phrase ceiling: one difficulty step per GROUP of notes the BUSIEST
    # iteration must ramp in, floored and capped (see _NOTES_PER_DD_LEVEL /
    # _DD_MIN_LEVELS — a step per single note pins nearly every phrase at the cap,
    # while no floor leaves a SHORT phrase with zero levels, unable to leave the
    # minimum however well it is played). Repeated phrases share a ceiling
    # (busiest, not summed); a phrase with no notes at all stays at 0.
    busiest = [0] * len(phrases)
    for pi_id, pi in enumerate(phrase_iterations):
        busiest[pi.phrase_id] = max(busiest[pi.phrase_id], len(per_iter_notes[pi_id]))
    phrase_max = [
        min(_DD_LEVEL_CAP, max(_DD_MIN_LEVELS, (b - 1) // _NOTES_PER_DD_LEVEL))
        if b
        else 0
        for b in busiest
    ]
    if not dynamic_difficulty:
        # One full-chart level: every phrase saturates at difficulty 0.
        phrase_max = [0] * len(phrases)
    song_max = max(phrase_max, default=0)

    def _level_notes(d: int) -> list[SngNote]:
        """The notes visible at difficulty ``d``: each iteration shows the
        strongest-beat prefix scaled by ``d`` against its phrase's ceiling, and
        NOTHING once ``d`` passes that ceiling.

        Dropping out above the ceiling is the reference's shape, not an
        optimisation: byte-diffing a DLC Builder build of the same song, its top
        level holds 126 of the song's 623 notes - only the two phrases whose own
        ceiling is the song max - while every phrase that topped out earlier
        contributes zero. Ours used to clamp (``min(d, pm)``) and therefore
        repeat a saturated phrase's full content at every higher level, so
        ``Levels[max]`` was the whole chart. The ramp itself was identical up to
        each phrase's ceiling; what differed is that a phrase never disappeared,
        leaving every phrase present at all 23 levels regardless of its declared
        ``max_difficulty``.
        """
        keep: set[int] = set()
        for pi_id, lst in enumerate(per_iter_notes):
            m = len(lst)
            if m == 0:
                continue
            pm = phrase_max[phrase_iterations[pi_id].phrase_id]
            if d > pm:
                continue
            # d <= pm here, so d == pm yields the phrase's full content.
            # At least one note at every level up to the ceiling: a phrase
            # with notes is never empty below it (DLC Builder's never is).
            shown = m if pm <= 0 else max(1, min(m, round((d + 1) / (pm + 1) * m)))
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

    levels = [
        _build_level(
            d, _level_notes(d), phrase_iterations, len(phrases),
            chord_templates, song_length, chord_notes_list,
        )
        for d in range(song_max + 1)
    ]
    return phrases, phrase_iterations, levels, song_max


def _build_sng_metadata(
    arrangement: Arrangement, note_count: int, song_length: float, song_max: int
) -> SngMetadata:
    first_note = min((n.time for n in arrangement.notes), default=0.0)
    first_beat_len = 0.5
    if len(arrangement.tempo_map.beats) >= 2:
        first_beat_len = arrangement.tempo_map.beats[1].time - arrangement.tempo_map.beats[0].time
    points = 100_000.0 / max(1, note_count) if note_count else 0.0
    return SngMetadata(
        max_score=100_000.0,
        max_notes_and_chords=float(note_count),
        max_notes_and_chords_real=float(note_count),
        points_per_note=points,
        first_beat_length=first_beat_len,
        start_time=arrangement.tempo_map.beats[0].time if arrangement.tempo_map.beats else 0.0,
        # 255, not 0, when there is no capo. This is the same sentinel pattern
        # that already bit us twice: a chord template's unused strings need MIDI
        # -1 (0 is a real, absurdly low pitch and crashed the game), and a vocal
        # needs note 254 (0 is a real pitch and the lyrics silently never
        # appeared). Byte-diffing a DLC Builder build of the same song: it
        # writes CapoFret 255 where we wrote 0, i.e. "capo at fret 0" instead of
        # "no capo".
        capo_fret=arrangement.capo if arrangement.capo else NO_CAPO,
        part=1,
        song_length=song_length,
        tuning=arrangement.tuning.offsets_from_standard(),
        first_note_time=first_note,
        first_note_time2=first_note,
        max_difficulty=song_max,
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

    beats = _build_beats(arrangement)

    sections_src = _prepare_sections(arrangement, song_length)
    ends = _section_end_times(sections_src, song_length)
    phrases, phrase_iterations = _link_phrases(arrangement, sections_src, ends)
    beats = _assign_beat_phrase_iterations(beats, phrase_iterations)

    groups = _group_chords(arrangement.notes)
    single_groups = [g for g in groups if len(g) == 1]
    chord_groups = [g for g in groups if len(g) > 1]
    template_ids, chord_templates, chord_notes_list, chord_notes_map = _build_chord_data(
        arrangement, chord_groups
    )

    # Full-chart anchors, only to stamp each NOTE's anchor_fret/anchor_width
    # hint (via _find_anchor in _build_sng_notes). The per-LEVEL anchor arrays
    # the game actually uses are rebuilt from each level's own notes inside
    # _build_level — see _build_anchors.
    anchors = _build_anchors(
        [(g[0].time, g[-1].time, [n.fret for n in g if n.fret > 0]) for g in groups],
        phrase_iterations,
        song_length,
    )

    sng_notes = _build_sng_notes(
        single_groups, chord_groups, anchors, phrase_iterations, template_ids, chord_notes_map
    )
    sections = _build_sng_sections(sections_src, ends, phrase_iterations)

    note_count = len(sng_notes)
    phrases, phrase_iterations, arrangements, song_max = _build_difficulty_levels(
        sng_notes, beats, phrases, phrase_iterations,
        chord_templates, chord_notes_list, song_length, dynamic_difficulty,
    )
    # Per-difficulty string usage per section — needs the levels, so it runs after
    # them (see _apply_section_string_masks: blank masks tell the game no string
    # is ever played).
    sections = _apply_section_string_masks(sections, arrangements, chord_templates)

    sng_vocals = [
        SngVocal(time=v.time, note=VOCAL_NOTE, length=v.length, lyric=v.lyric)
        for v in (vocals or [])
    ]
    metadata = _build_sng_metadata(arrangement, note_count, song_length, song_max)

    return SngModel(
        beats=beats,
        phrases=phrases,
        chord_templates=chord_templates,
        chord_notes=chord_notes_list,
        vocals=sng_vocals,
        phrase_iterations=phrase_iterations,
        events=_build_events(metadata.start_time, metadata.first_note_time, song_length),
        tones=_build_tones(arrangement),
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
            SngVocal(time=v.time, note=VOCAL_NOTE, length=v.length, lyric=v.lyric)
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
# slide_to / slide_unpitch_to / left_hand are SIGNED bytes: -1 (0xFF) means
# "none". Writing 0 (unsigned) told the game every note slides to fret 0 — a
# slide streak on every note — and forced a fretting finger on notes that have
# none. tap/pickDirection/slap/pluck stay unsigned (0..4).
# LeftHand, Tap, PickDirection, Slap, Pluck are SIGNED: -1 is "none", the value
# DLC Builder writes for each when a note does not use it.
_NOTE_FIXED_FMT = "<IIIfBBBBiiiihhhhh" "bbbbbbbhff"

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
    # BendData[6] — per string: 32 fixed BendData32 entries THEN the Int32
    # UsedCount. The count is at the END of the array, not the front (verified by
    # decoding a DLC Builder SNG of a bent chord). Writing it first put the used
    # count where the game expects the first bend point, corrupting the chord and
    # crashing at the first bent chord — while unbent chords (all zeros either
    # way) were unaffected, which is exactly the symptom we saw.
    for s in range(6):
        bends = cn.bend_data[s]
        for j in range(_BEND_DATA_COUNT):
            if j < len(bends):
                out += _write_bend32(bends[j])
            else:
                out += b"\x00" * _BEND32_SIZE
        out += struct.pack("<i", len(bends))
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
    # Symbol sections (only when vocals are present): the lyric font glyph atlas
    # the game needs to draw the lyrics. Vendored default Latin font (see
    # _vocals_symbols_block) — empty sections here make the letra invisible.
    if model.vocals:
        out += _vocals_symbols_block()

    # 6. PhraseIterations
    out += _write_count(len(model.phrase_iterations))
    for pi in model.phrase_iterations:
        out += struct.pack(
            _PHRASE_ITER_FMT,
            pi.phrase_id, pi.start_time, pi.end_time,
            *pi.difficulty,
        )

    # 7-9. Empty: PhraseExtraInfo, NLinkedDifficulty, Actions.
    for _ in range(3):
        out += _write_count(0)

    # 10. Events (stage/crowd cues) — see _build_events.
    out += _write_count(len(model.events))
    for ev in model.events:
        out += struct.pack("<f", ev.time) + _pack_str(ev.code, _EVENT_CODE_LEN)

    # 11. Tones (mid-song tone changes) — see _build_tones.
    out += _write_count(len(model.tones))
    for tone in model.tones:
        out += struct.pack("<fi", tone.time, tone.tone_id)

    # 12. Empty: DNAs.
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
        entries = []
        for _j in range(_BEND_DATA_COUNT):
            bd, pos = _read_bend32(data, pos)
            entries.append(bd)
        (used,) = struct.unpack_from("<i", data, pos)  # UsedCount AFTER the array
        pos += 4
        bend_data.append(entries[:used])
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
        # SymbolsHeader (32-byte entries), SymbolsTexture (144), SymbolsDefinition (44)
        for entry_size in (32, 144, 44):
            sym_count, pos = _read_count(data, pos)
            pos += sym_count * entry_size

    # 6. PhraseIterations
    pi_count, pos = _read_count(data, pos)
    phrase_iterations = []
    for _ in range(pi_count):
        pid, st, et, d0, d1, d2 = struct.unpack_from(_PHRASE_ITER_FMT, data, pos)
        pos += _PHRASE_ITER_SIZE
        phrase_iterations.append(SngPhraseIteration(
            phrase_id=pid, start_time=st, end_time=et, difficulty=(d0, d1, d2),
        ))

    # 7-12. PhraseExtraInfo, NLinkedDifficulty, Actions, Events, Tones, DNAs.
    # RockForge populates only Events; the rest are written empty. A REAL file
    # populates several of them, so their entries must be skipped by size, not
    # assumed absent. Reading only the counts desynced the parser on every DLC
    # Builder SNG (its 5 crowd/stage Events alone), which made our own reader
    # useless for byte-diffing against a reference build — the one technique
    # that has isolated every native-SNG rendering bug so far.
    # Dispatch on the section's IDENTITY, not on its entry size: Actions and
    # Events are both 260 bytes, so keying off the size read the Actions
    # section as Events (and left the real ones unread).
    events: list[SngEvent] = []
    tones: list[SngTone] = []
    for kind, entry_size in (
        ("skip", _PHRASE_EXTRA_SIZE), ("nld", 0), ("skip", _ACTION_SIZE),
        ("events", _EVENT_SIZE), ("tones", _SNG_TONE_SIZE), ("skip", _DNA_SIZE),
    ):
        count, pos = _read_count(data, pos)
        if kind == "nld":
            # Variable-length: a header pair plus one int32 per linked phrase.
            for _ in range(count):
                _level_break, phrase_count = struct.unpack_from("<ii", data, pos)
                pos += 8 + 4 * phrase_count
        elif kind == "events":
            for _ in range(count):
                (ev_time,) = struct.unpack_from("<f", data, pos)
                events.append(SngEvent(
                    time=ev_time,
                    code=_unpack_str(data[pos + 4 : pos + 4 + _EVENT_CODE_LEN]),
                ))
                pos += _EVENT_SIZE
        elif kind == "tones":
            for _ in range(count):
                t_time, t_id = struct.unpack_from("<fi", data, pos)
                tones.append(SngTone(time=t_time, tone_id=t_id))
                pos += _SNG_TONE_SIZE
        else:
            pos += count * entry_size

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
        phrase_iterations=phrase_iterations, events=events, tones=tones, sections=sections,
        arrangements=arrangements, metadata=metadata,
    )
