"""The Sng2014 binary codec: :func:`write_sng` and :func:`read_sng`.
"""

from __future__ import annotations

import struct
from functools import lru_cache
from pathlib import Path

from rockforge.infrastructure.packaging.psarc.sng_model import (
    _ACTION_SIZE,
    _BEND_DATA_COUNT,
    _DNA_SIZE,
    _EVENT_CODE_LEN,
    _EVENT_SIZE,
    _LYRIC_LEN,
    _NAME_LEN,
    _PHRASE_EXTRA_SIZE,
    _SNG_TONE_SIZE,
    SngAnchor,
    SngAnchorExtension,
    SngArrangementLevel,
    SngBeat,
    SngBendData32,
    SngChordNotes,
    SngChordTemplate,
    SngEvent,
    SngFingerprint,
    SngMetadata,
    SngModel,
    SngNote,
    SngPhrase,
    SngPhraseIteration,
    SngSection,
    SngTone,
    SngVocal,
)

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
