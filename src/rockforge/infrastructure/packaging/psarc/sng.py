"""SNG compilation: ``Arrangement`` → Rocksmith's binary SNG payload.

Binary layout ported from the Rocksmith2014.NET / DLC Builder project (MIT).
Section ordering and field sizes match the real Sng2014 format so the game
can parse the result. Sections RockForge's domain model cannot populate
(PhraseExtraInfo, NLD, Actions, Events, Tones, DNAs) are emitted as empty
(count=0).

Limitations:
- Single difficulty level (RockForge has no dynamic-difficulty model).
- ChordNotes are emitted only when a chord has per-string bend/slide data;
  simple chords use ``ChordNotesId = -1``.
- AnchorExtensions, arpeggio fingerprints: always empty.
- Note Hash: always 0 (the game does not validate it critically).
- ParentPrevNote / linkNext linkage: not modelled in the domain.
"""

from __future__ import annotations

import struct
from collections.abc import Sequence
from dataclasses import dataclass, field

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
    measure: int  # short; -1 for non-downbeat
    beat: int = 0  # beat within measure (short)
    phrase_iteration: int = -1


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
    slide_to: int = 0
    slide_unpitch_to: int = 0
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


def _note_mask(n: TabNote, is_chord: bool = False, is_double_stop: bool = False) -> int:
    mask = 0
    for tech in n.techniques:
        mask |= TECHNIQUE_TO_MASK.get(tech, 0)
    if n.bend_semitones > 0:
        mask |= NOTE_MASK_BEND
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


def _section_end_times(sections: list[Section], song_length: float) -> list[float]:
    if not sections:
        return []
    return [s.start_time for s in sections[1:]] + [song_length]


def _find_phrase_iteration(phrase_iters: list[SngPhraseIteration], time: float) -> int:
    for i, pi in enumerate(phrase_iters):
        if pi.start_time <= time < pi.end_time:
            return i
    return max(0, len(phrase_iters) - 1)


def from_arrangement(
    arrangement: Arrangement, vocals: list[VocalEvent] | None = None
) -> SngModel:
    """Build the SNG model from a RockForge ``Arrangement``."""
    song_length = arrangement.metadata.song_length

    # --- Beats ---
    beat_in_measure = 0
    beats: list[SngBeat] = []
    for b in arrangement.tempo_map.beats:
        if b.measure >= 0:
            beat_in_measure = 0
        beats.append(SngBeat(time=b.time, measure=b.measure, beat=beat_in_measure))
        beat_in_measure += 1

    # --- Phrases & PhraseIterations ---
    phrases = [SngPhrase(name=s.name) for s in arrangement.sections]
    ends = _section_end_times(arrangement.sections, song_length)
    phrase_iterations = [
        SngPhraseIteration(phrase_id=i, start_time=s.start_time, end_time=end)
        for i, (s, end) in enumerate(zip(arrangement.sections, ends, strict=True))
    ]

    # Assign phrase_iteration to beats
    beats = [
        SngBeat(
            time=b.time,
            measure=b.measure,
            beat=b.beat,
            phrase_iteration=_find_phrase_iteration(phrase_iterations, b.time),
        )
        for b in beats
    ]

    # --- Chord grouping ---
    groups = _group_chords(arrangement.notes)
    single_groups = [g for g in groups if len(g) == 1]
    chord_groups = [g for g in groups if len(g) > 1]

    # --- Chord templates ---
    template_ids: dict[tuple[int, ...], int] = {}
    chord_templates: list[SngChordTemplate] = []
    for g in chord_groups:
        key = _chord_template_key(g)
        if key not in template_ids:
            template_ids[key] = len(template_ids)
            frets_bytes = tuple(max(0, f) if f >= 0 else 255 for f in key)
            chord_templates.append(SngChordTemplate(
                mask=0,
                frets=frets_bytes,
                fingers=tuple([-1] * 6),
                notes=tuple([0] * 6),
                name="",
            ))

    # --- ChordNotes (for chords with per-string techniques) ---
    chord_notes_list: list[SngChordNotes] = []
    chord_notes_map: dict[int, int] = {}  # group_index -> chord_notes_id

    for gi, g in enumerate(chord_groups):
        has_techniques = any(
            n.techniques or n.bend_semitones > 0 or n.slide_to_fret is not None
            for n in g
        )
        if not has_techniques:
            continue
        cn = SngChordNotes(
            note_mask=[0] * 6,
            bend_data=[[] for _ in range(6)],
            slide_to=[0] * 6,
            slide_unpitch_to=[0] * 6,
            vibrato=[0] * 6,
        )
        for n in g:
            cn.note_mask[n.string] = _note_mask(n)
            if n.bend_semitones > 0:
                cn.bend_data[n.string] = [
                    SngBendData32(time=0.0, step=n.bend_semitones)
                ]
            if n.slide_to_fret is not None:
                cn.slide_to[n.string] = n.slide_to_fret
            if Technique.VIBRATO in n.techniques:
                cn.vibrato[n.string] = 80
        chord_notes_map[gi] = len(chord_notes_list)
        chord_notes_list.append(cn)

    # --- Build anchors ---
    anchors: list[SngAnchor] = []
    current_anchor: tuple[int, int] | None = None
    for g in groups:
        used = [n.fret for n in g if n.fret > 0]
        if not used:
            continue
        if current_anchor is not None and all(
            current_anchor[0] <= f <= current_anchor[0] + current_anchor[1] - 1 for f in used
        ):
            continue
        fret, width = _anchor_for_frets(used)
        pi_id = _find_phrase_iteration(phrase_iterations, g[0].time)
        pi = phrase_iterations[pi_id] if phrase_iterations else None
        anchors.append(SngAnchor(
            start_time=pi.start_time if pi else g[0].time,
            end_time=pi.end_time if pi else song_length,
            first_note_time=g[0].time,
            last_note_time=g[-1].time,
            fret=fret,
            width=width,
            phrase_iteration_id=pi_id,
        ))
        current_anchor = (fret, width)
    if not anchors and groups:
        anchors.append(SngAnchor(
            start_time=0.0,
            end_time=song_length,
            first_note_time=groups[0][0].time,
            last_note_time=groups[0][0].time,
            fret=1,
            width=4,
        ))

    # --- Fingerprints / handshapes (one per chord group) ---
    fingerprints: list[SngFingerprint] = []
    chord_group_fp_map: dict[int, int] = {}
    all_note_times = sorted(n.time for n in arrangement.notes)

    for gi, g in enumerate(chord_groups):
        key = _chord_template_key(g)
        chord_id = template_ids[key]
        start_t = g[0].time
        # End at next note/chord time or start + 0.5s
        idx = next((i for i, t in enumerate(all_note_times) if t > start_t + _CHORD_EPSILON_S), -1)
        end_t = all_note_times[idx] if idx >= 0 else start_t + 0.5
        chord_group_fp_map[gi] = len(fingerprints)
        fingerprints.append(SngFingerprint(
            chord_id=chord_id,
            start_time=start_t,
            end_time=end_t,
            first_note_time=start_t,
            last_note_time=g[-1].time,
        ))

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
        sn_bends: list[SngBendData32] = []
        if sn.bend_semitones > 0:
            sn_bends = [SngBendData32(time=0.0, step=sn.bend_semitones)]
        sng_notes.append(SngNote(
            time=sn.time,
            string=sn.string,
            fret=sn.fret,
            sustain=sn.sustain,
            bend=sn.bend_semitones,
            mask=mask,
            anchor_fret=a_fret,
            anchor_width=a_width,
            phrase_id=pi_id,
            phrase_iteration_id=pi_id,
            slide_to=sn.slide_to_fret if sn.slide_to_fret is not None else 0,
            slap=1 if Technique.SLAP in sn.techniques else 0,
            pluck=1 if Technique.POP in sn.techniques else 0,
            tap=1 if Technique.TAP in sn.techniques else 0,
            vibrato=80 if Technique.VIBRATO in sn.techniques else 0,
            bend_data=sn_bends,
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
        # Mirror techniques from individual notes onto chord mask
        for n in g:
            for tech in n.techniques:
                mask |= TECHNIQUE_TO_MASK.get(tech, 0)
        if any(n.sustain > 0 for n in g):
            mask |= NOTE_MASK_SUSTAIN
        fp_id = chord_group_fp_map.get(gi, -1)
        mask |= NOTE_MASK_STRUM
        a_fret, a_width = _find_anchor(g[0].time)
        pi_id = _find_phrase_iteration(phrase_iterations, g[0].time)
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
            phrase_id=pi_id,
            phrase_iteration_id=pi_id,
            fingerprint_id=(fp_id, -1),
            bend_data=[],
        ))

    sng_notes.sort(key=lambda n: n.time)

    # --- Note linkage within phrase iterations ---
    for _pi_idx, pi in enumerate(phrase_iterations):
        pi_notes = [
            (i, n) for i, n in enumerate(sng_notes)
            if pi.start_time <= n.time < pi.end_time
        ]
        for j, (_ni, note) in enumerate(pi_notes):
            note.prev_iter_note = pi_notes[j - 1][0] if j > 0 else -1
            note.next_iter_note = pi_notes[j + 1][0] if j < len(pi_notes) - 1 else -1

    # --- Sections ---
    sections: list[SngSection] = []
    for sec, end in zip(arrangement.sections, ends, strict=True):
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

    # --- ArrangementLevel ---
    note_count = len(sng_notes)
    avg_per_iter = []
    notes_in_iter: list[int] = []
    for pi in phrase_iterations:
        count = sum(1 for n in sng_notes if pi.start_time <= n.time < pi.end_time)
        notes_in_iter.append(count)
    for p_idx in range(len(phrases)):
        iters_for_phrase = [
            notes_in_iter[i] for i, pi in enumerate(phrase_iterations) if pi.phrase_id == p_idx
        ]
        avg_per_iter.append(
            sum(iters_for_phrase) / max(1, len(iters_for_phrase))
        )

    level = SngArrangementLevel(
        difficulty=0,
        anchors=anchors,
        fingerprints1=fingerprints,
        fingerprints2=[],
        notes=sng_notes,
        phrase_count=len(phrases),
        avg_notes_per_iteration=avg_per_iter,
        notes_in_iteration1=notes_in_iter,
        notes_in_iteration2=notes_in_iter,
    )

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
        max_difficulty=0,
    )

    return SngModel(
        beats=beats,
        phrases=phrases,
        chord_templates=chord_templates,
        chord_notes=chord_notes_list,
        vocals=sng_vocals,
        phrase_iterations=phrase_iterations,
        sections=sections,
        arrangements=[level],
        metadata=metadata,
    )


# ---------------------------------------------------------------------------
# Binary serialization (write)
# ---------------------------------------------------------------------------

_BEND32_FMT = "<ffhBB"
_BEND32_SIZE = struct.calcsize(_BEND32_FMT)  # 12

_BEAT_FMT = "<fhhi"
_PHRASE_FMT = "<BBBBii32s"
_PHRASE_ITER_FMT = "<iffiii"
_CHORD_TEMPLATE_FMT = "<I6s6s6i32s"
_SECTION_FMT = "<32siffii36s"
_ANCHOR_FMT = "<ffffBBBBii"
_FINGERPRINT_FMT = "<iffff"
_VOCAL_FMT = f"<fif{_LYRIC_LEN}s"
_NOTE_FIXED_FMT = "<IIIfBBBBiiiihhhhh" "BBBBBBBhff"

_BEAT_SIZE = struct.calcsize(_BEAT_FMT)
_PHRASE_SIZE = struct.calcsize(_PHRASE_FMT)
_PHRASE_ITER_SIZE = struct.calcsize(_PHRASE_ITER_FMT)
_CHORD_TEMPLATE_SIZE = struct.calcsize(_CHORD_TEMPLATE_FMT)
_SECTION_SIZE = struct.calcsize(_SECTION_FMT)
_ANCHOR_SIZE = struct.calcsize(_ANCHOR_FMT)
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

    # AnchorExtensions (always empty)
    out += _write_count(0)

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
        out += struct.pack(_BEAT_FMT, b.time, b.measure, b.beat, b.phrase_iteration)

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

    # AnchorExtensions (skip)
    ae_count, pos = _read_count(data, pos)
    if ae_count > 0:
        pos += ae_count * 8  # BeatTime(4) + FretId(1) + padding(3)

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
        difficulty=difficulty, anchors=anchors,
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
        t, m, bt, pi = struct.unpack_from(_BEAT_FMT, data, pos)
        pos += _BEAT_SIZE
        beats.append(SngBeat(time=t, measure=m, beat=bt, phrase_iteration=pi))

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
