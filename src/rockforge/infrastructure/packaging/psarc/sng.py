"""SNG compilation: ``Arrangement`` -> Rocksmith's binary SNG payload.

Phase 3 of the native-PSARC plan (TODO.md). The real ``.sng`` file on disk is
this payload wrapped in a small header and then zlib-compressed + AES-256-CTR
encrypted (phase 4) — this module produces the **unencrypted structural
payload** only, plus a reader for round-trip testing.

Scope and limitations (honesty principle, CLAUDE.md): this is a *structural*
port — section ordering and the fields RockForge's domain model can populate
(beats, phrases/sections, notes' time/string/fret/sustain/bend/techniques,
vocals, song-level metadata) are emitted with a documented binary layout.
Several real Sng2014 sections/fields are deferred and are NOT emitted:
chord templates and chord notes (RockForge's domain model has no chord
aggregate), anchors/anchor-extensions, fingerprints (hand shapes), the
"NewLinkedDifficulty" table, and per-note linkage fields (next/prev note,
parent note). The technique bitmask in :data:`TECHNIQUE_BITS` is RockForge's
own encoding and has not been validated against retail SNGs — phases 4/5
must verify (or replace) it against the real Sng2014 ``NoteMask`` layout
before this can produce a SNG the game accepts.
"""

from __future__ import annotations

import struct
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from rockforge.domain.arrangement import Arrangement, Section
from rockforge.domain.music import Technique
from rockforge.infrastructure.rsxml.vocals import VocalEvent

# RockForge's own technique -> NoteMask bit assignment (see module docstring).
TECHNIQUE_BITS: dict[Technique, int] = {
    Technique.HAMMER_ON: 1 << 0,
    Technique.PULL_OFF: 1 << 1,
    Technique.SLIDE: 1 << 2,
    Technique.BEND: 1 << 3,
    Technique.HARMONIC: 1 << 4,
    Technique.PALM_MUTE: 1 << 5,
    Technique.VIBRATO: 1 << 6,
    Technique.TAP: 1 << 7,
    Technique.SLAP: 1 << 8,
    Technique.POP: 1 << 9,
    Technique.ACCENT: 1 << 10,
}

_NAME_LEN = 32
_LYRIC_LEN = 48


def _pack_str(value: str, length: int) -> bytes:
    raw = value.encode("utf-8")[: length - 1]
    return raw + b"\x00" * (length - len(raw))


def _unpack_str(raw: bytes) -> str:
    return raw.split(b"\x00", 1)[0].decode("utf-8")


@dataclass(frozen=True)
class SngBeat:
    time: float
    measure: int
    phrase_iteration: int = -1


@dataclass(frozen=True)
class SngPhrase:
    name: str
    max_difficulty: int = 0


@dataclass(frozen=True)
class SngPhraseIteration:
    phrase_id: int
    start_time: float
    end_time: float


@dataclass(frozen=True)
class SngSection:
    name: str
    number: int
    start_time: float
    end_time: float


@dataclass(frozen=True)
class SngNote:
    time: float
    string: int
    fret: int
    sustain: float
    bend: float
    mask: int


@dataclass(frozen=True)
class SngVocal:
    time: float
    note: int
    length: float
    lyric: str


@dataclass(frozen=True)
class SngMetadata:
    song_length: float
    capo_fret: int
    tuning: tuple[int, int, int, int, int, int]
    max_difficulty: int


@dataclass
class SngModel:
    beats: list[SngBeat] = field(default_factory=list)
    phrases: list[SngPhrase] = field(default_factory=list)
    phrase_iterations: list[SngPhraseIteration] = field(default_factory=list)
    sections: list[SngSection] = field(default_factory=list)
    notes: list[SngNote] = field(default_factory=list)
    vocals: list[SngVocal] = field(default_factory=list)
    metadata: SngMetadata = field(
        default_factory=lambda: SngMetadata(0.0, 0, (0, 0, 0, 0, 0, 0), 0)
    )


def _note_mask(note_techniques: frozenset[Technique]) -> int:
    mask = 0
    for technique in note_techniques:
        mask |= TECHNIQUE_BITS.get(technique, 0)
    return mask


def _section_end_times(sections: list[Section], song_length: float) -> list[float]:
    if not sections:
        return []
    return [s.start_time for s in sections[1:]] + [song_length]


def from_arrangement(
    arrangement: Arrangement, vocals: list[VocalEvent] | None = None
) -> SngModel:
    """Build the SNG model from a RockForge ``Arrangement``."""
    beats = [
        SngBeat(time=b.time, measure=b.measure)
        for b in arrangement.tempo_map.beats
    ]

    phrases = [SngPhrase(name=s.name) for s in arrangement.sections]
    ends = _section_end_times(arrangement.sections, arrangement.metadata.song_length)
    phrase_iterations = [
        SngPhraseIteration(phrase_id=i, start_time=s.start_time, end_time=end)
        for i, (s, end) in enumerate(zip(arrangement.sections, ends, strict=True))
    ]
    sections = [
        SngSection(name=s.name, number=s.number, start_time=s.start_time, end_time=end)
        for s, end in zip(arrangement.sections, ends, strict=True)
    ]

    notes = [
        SngNote(
            time=n.time,
            string=n.string,
            fret=n.fret,
            sustain=n.sustain,
            bend=n.bend_semitones,
            mask=_note_mask(n.techniques),
        )
        for n in arrangement.notes
    ]

    sng_vocals = [
        SngVocal(time=v.time, note=0, length=v.length, lyric=v.lyric)
        for v in (vocals or [])
    ]

    metadata = SngMetadata(
        song_length=arrangement.metadata.song_length,
        capo_fret=arrangement.capo,
        tuning=arrangement.tuning.offsets_from_standard(),  # type: ignore[arg-type]
        max_difficulty=0,
    )

    return SngModel(
        beats=beats,
        phrases=phrases,
        phrase_iterations=phrase_iterations,
        sections=sections,
        notes=notes,
        vocals=sng_vocals,
        metadata=metadata,
    )


_BEAT_FMT = "<fii"
_PHRASE_FMT = f"<{_NAME_LEN}si"
_PHRASE_ITER_FMT = "<iff"
_SECTION_FMT = f"<{_NAME_LEN}siff"
_NOTE_FMT = "<fbbffi"
_VOCAL_FMT = f"<fif{_LYRIC_LEN}s"
_METADATA_FMT = "<fb6hi"


def _write_records(
    records: Sequence[Any], fmt: str, to_tuple: Callable[[Any], tuple[Any, ...]]
) -> bytes:
    out = struct.pack("<I", len(records))
    for record in records:
        out += struct.pack(fmt, *to_tuple(record))
    return out


def write_sng(model: SngModel) -> bytes:
    """Serialize an :class:`SngModel` to RockForge's structural SNG payload."""
    out = bytearray()
    out += _write_records(model.beats, _BEAT_FMT, lambda b: (b.time, b.measure, b.phrase_iteration))
    out += _write_records(
        model.phrases, _PHRASE_FMT, lambda p: (_pack_str(p.name, _NAME_LEN), p.max_difficulty)
    )
    out += _write_records(
        model.phrase_iterations,
        _PHRASE_ITER_FMT,
        lambda pi: (pi.phrase_id, pi.start_time, pi.end_time),
    )
    out += _write_records(
        model.sections,
        _SECTION_FMT,
        lambda s: (_pack_str(s.name, _NAME_LEN), s.number, s.start_time, s.end_time),
    )
    out += _write_records(
        model.notes,
        _NOTE_FMT,
        lambda n: (n.time, n.string, n.fret, n.sustain, n.bend, n.mask),
    )
    out += _write_records(
        model.vocals,
        _VOCAL_FMT,
        lambda v: (v.time, v.note, v.length, _pack_str(v.lyric, _LYRIC_LEN)),
    )
    m = model.metadata
    out += struct.pack(_METADATA_FMT, m.song_length, m.capo_fret, *m.tuning, m.max_difficulty)
    return bytes(out)


def _read_records(
    data: bytes, pos: int, fmt: str, from_tuple: Callable[[tuple[Any, ...]], Any]
) -> tuple[list[Any], int]:
    (count,) = struct.unpack_from("<I", data, pos)
    pos += 4
    size = struct.calcsize(fmt)
    records = []
    for _ in range(count):
        values = struct.unpack_from(fmt, data, pos)
        records.append(from_tuple(values))
        pos += size
    return records, pos


def read_sng(data: bytes) -> SngModel:
    """Inverse of :func:`write_sng`."""
    pos = 0
    beats, pos = _read_records(
        data, pos, _BEAT_FMT, lambda v: SngBeat(time=v[0], measure=v[1], phrase_iteration=v[2])
    )
    phrases, pos = _read_records(
        data, pos, _PHRASE_FMT, lambda v: SngPhrase(name=_unpack_str(v[0]), max_difficulty=v[1])
    )
    phrase_iterations, pos = _read_records(
        data, pos, _PHRASE_ITER_FMT,
        lambda v: SngPhraseIteration(phrase_id=v[0], start_time=v[1], end_time=v[2]),
    )
    sections, pos = _read_records(
        data, pos, _SECTION_FMT,
        lambda v: SngSection(name=_unpack_str(v[0]), number=v[1], start_time=v[2], end_time=v[3]),
    )
    notes, pos = _read_records(
        data, pos, _NOTE_FMT,
        lambda v: SngNote(time=v[0], string=v[1], fret=v[2], sustain=v[3], bend=v[4], mask=v[5]),
    )
    vocals, pos = _read_records(
        data, pos, _VOCAL_FMT,
        lambda v: SngVocal(time=v[0], note=v[1], length=v[2], lyric=_unpack_str(v[3])),
    )
    song_length, capo_fret, *tuning_and_max = struct.unpack_from(_METADATA_FMT, data, pos)
    tuning = tuple(tuning_and_max[:6])
    max_difficulty = tuning_and_max[6]
    metadata = SngMetadata(
        song_length=song_length, capo_fret=capo_fret, tuning=tuning, max_difficulty=max_difficulty
    )
    return SngModel(
        beats=beats,
        phrases=phrases,
        phrase_iterations=phrase_iterations,
        sections=sections,
        notes=notes,
        vocals=vocals,
        metadata=metadata,
    )
