import bisect
import struct
from dataclasses import replace

import pytest

from rockforge.domain.arrangement import Arrangement, ArrangementKind, Section, SongMetadata
from rockforge.domain.music import Beat, TabNote, Technique, TempoMap, Tuning
from rockforge.infrastructure.packaging.psarc.sng import (
    NOTE_MASK_BEND,
    NOTE_MASK_CHORD,
    NOTE_MASK_CHORDNOTES,
    NOTE_MASK_DOUBLESTOP,
    NOTE_MASK_FRETHANDMUTE,
    NOTE_MASK_HAMMERON,
    NOTE_MASK_HIGHDENSITY,
    NOTE_MASK_OPEN,
    NOTE_MASK_PINCHHARMONIC,
    NOTE_MASK_SINGLE,
    NOTE_MASK_SLIDEUNPITCHEDTO,
    NOTE_MASK_STRUM,
    NOTE_MASK_SUSTAIN,
    NOTE_MASK_TREMOLO,
    TECHNIQUE_BITS,
    TECHNIQUE_TO_MASK,
    SngBeat,
    _note_tier,
    _pack_str,
    _unpack_str,
    from_arrangement,
    from_vocals,
    read_sng,
    write_sng,
)
from rockforge.infrastructure.packaging.psarc.verify import check_sng
from rockforge.infrastructure.rsxml.vocals import VocalEvent


def test_note_tier_at_song_end_uses_the_last_beat_not_the_first() -> None:
    """A note at/after the song's final beat must be scored against the LAST
    beat, not beats[0]. The old fallback always compared to beats[0], so a note
    on the final downbeat was mis-scored as tier 1 instead of 0 (cosmetic DD
    note-intro ordering, but a real logic bug)."""
    beats = [
        SngBeat(time=0.0, measure=1, mask=1),   # downbeat
        SngBeat(time=1.0, measure=1, mask=0),
        SngBeat(time=10.0, measure=2, mask=1),  # final downbeat
    ]
    # On / just past the final downbeat → tier 0 (it IS a downbeat).
    assert _note_tier(10.0, beats) == 0
    assert _note_tier(10.02, beats) == 0
    # Well past it, not near any edge downbeat → tier 1.
    assert _note_tier(10.5, beats) == 1
    # Before the first downbeat still resolves against beats[0].
    assert _note_tier(-0.02, beats) == 0


def test_note_tier_after_a_non_downbeat_last_beat_is_tier_one() -> None:
    """If the final beat is NOT a downbeat, an end-of-song note is tier 1, not
    0 — proving the fix reads the last beat's mask, not beats[0]'s."""
    beats = [
        SngBeat(time=0.0, measure=1, mask=1),   # downbeat
        SngBeat(time=10.0, measure=1, mask=0),  # final beat, NOT a downbeat
    ]
    assert _note_tier(10.0, beats) == 1


def test_pack_str_truncates_on_a_utf8_character_boundary() -> None:
    """A raw byte slice can split a multi-byte UTF-8 character in half, shipping
    invalid bytes into the packed .sng and crashing read-back (_unpack_str)."""
    # "ção" is 2+2+1 = 5 bytes ('ç'/'ã' are each 2 bytes); 46 ASCII 'a's + that
    # = 51 bytes. A raw byte slice to 47 bytes (_LYRIC_LEN - 1) lands 1 byte
    # into 'ç', splitting it — the exact bug this guards against.
    value = "a" * 46 + "ção"
    packed = _pack_str(value, 48)
    assert len(packed) == 48
    # Must decode cleanly (no UnicodeDecodeError from a split character); the
    # incomplete trailing 'ç' is dropped rather than emitted half-broken.
    assert _unpack_str(packed) == "a" * 46


def test_pack_str_keeps_a_multi_byte_char_that_fits_whole() -> None:
    """Sanity check the boundary isn't overly conservative: a multi-byte
    character that fits entirely within the limit is kept, not dropped."""
    value = "a" * 42 + "ção"  # 42 + 5 = 47 bytes == exactly length - 1
    packed = _pack_str(value, 48)
    assert _unpack_str(packed) == value


def test_pack_str_exact_fit_and_empty_are_unaffected() -> None:
    assert _unpack_str(_pack_str("hello", 32)) == "hello"
    assert _unpack_str(_pack_str("", 32)) == ""
    exact = "x" * 31
    assert _unpack_str(_pack_str(exact, 32)) == exact


def _arrangement() -> Arrangement:
    return Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="Song", artist="Artist", song_length=10.0),
        tuning=Tuning(),
        tempo_map=TempoMap(
            beats=(Beat(time=0.0, measure=1), Beat(time=0.5, measure=-1)), average_bpm=120.0
        ),
        notes=[
            TabNote(
                string=0,
                fret=2,
                time=0.0,
                sustain=0.5,
                techniques=frozenset({Technique.HAMMER_ON}),
            ),
            TabNote(string=1, fret=0, time=1.0, sustain=0.0, bend_semitones=1.5),
        ],
        sections=[
            Section(name="riff", start_time=0.0, number=1),
            Section(name="verse", start_time=5.0, number=1),
        ],
        capo=2,
    )


def _bars(n: int) -> tuple[Beat, ...]:
    """One beat per bar, a bar a second: the native SNG cuts a phrase every 8
    bars (DLC Builder's PhraseGenerator), so with the first note at 1.0 s the
    phrases start at 1, 9, 17… s."""
    return tuple(Beat(time=float(i), measure=i + 1) for i in range(n))


def test_from_arrangement_round_trips_through_write_read() -> None:
    arrangement = _arrangement()
    vocals = [VocalEvent(time=1.0, length=0.5, lyric="hi+")]
    model = from_arrangement(arrangement, vocals=vocals)
    data = write_sng(model)
    restored = read_sng(data)

    assert len(restored.beats) == len(model.beats)
    for orig, rest in zip(model.beats, restored.beats, strict=True):
        assert abs(orig.time - rest.time) < 1e-6
        assert orig.measure == rest.measure
        assert orig.beat == rest.beat

    assert len(restored.phrases) == len(model.phrases)
    for orig, rest in zip(model.phrases, restored.phrases, strict=True):
        assert orig.name == rest.name

    assert len(restored.phrase_iterations) == len(model.phrase_iterations)
    assert len(restored.sections) == len(model.sections)

    assert len(restored.arrangements) == len(model.arrangements)
    level = restored.arrangements[-1]
    orig_level = model.arrangements[-1]
    assert len(level.notes) == len(orig_level.notes)
    assert len(level.anchors) == len(orig_level.anchors)

    assert restored.metadata.capo_fret == 2
    assert restored.metadata.song_length == 10.0


def test_note_mask_uses_real_rocksmith_values() -> None:
    arrangement = _arrangement()
    model = from_arrangement(arrangement)
    notes = model.arrangements[-1].notes
    # First note: hammer-on, fret 2, sustain 0.5 → SINGLE | HAMMERON | SUSTAIN
    assert notes[0].mask & NOTE_MASK_HAMMERON
    assert notes[0].mask & NOTE_MASK_SINGLE
    assert notes[0].mask & NOTE_MASK_SUSTAIN
    assert not (notes[0].mask & NOTE_MASK_CHORD)
    # Second note: open string (fret 0), half-step bend → OPEN | BEND, peak in the
    # maxBend field (matches a decoded DLC Builder SNG: bent string 0x3000).
    assert notes[1].mask & NOTE_MASK_BEND
    assert notes[1].mask & NOTE_MASK_OPEN
    assert notes[1].bend == 1.5


def test_technique_bits_alias_matches_technique_to_mask() -> None:
    assert TECHNIQUE_BITS is TECHNIQUE_TO_MASK


def test_section_end_times_use_next_section_or_song_length() -> None:
    model = from_arrangement(_arrangement())
    secs = model.sections
    for a, b in zip(secs, secs[1:], strict=False):
        assert a.end_time == b.start_time
    assert secs[-1].end_time == model.metadata.song_length


def test_metadata_reflects_capo_and_tuning() -> None:
    arrangement = _arrangement()
    model = from_arrangement(arrangement)
    assert model.metadata.capo_fret == 2
    assert model.metadata.song_length == 10.0
    assert model.metadata.tuning == (0, 0, 0, 0, 0, 0)


def test_anchors_generated_from_notes() -> None:
    arrangement = _arrangement()
    model = from_arrangement(arrangement)
    level = model.arrangements[-1]
    assert len(level.anchors) >= 1
    assert level.anchors[0].fret >= 1
    assert level.anchors[0].width >= 4


def test_chords_produce_templates_with_fingers_and_a_hand_shape() -> None:
    """The game draws a chord's fingers from a hand shape (fingerprint) over it
    and the fingers of its template — both were empty, so Rocksmith showed no
    finger positions on our charts while its own songs and hand-made CDLC
    carry them (two Daughtry CDLC: every chord inside a hand shape)."""
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="Song", artist="A", song_length=5.0),
        tuning=Tuning(),
        tempo_map=TempoMap(
            beats=(Beat(time=0.0, measure=1), Beat(time=0.5, measure=-1)), average_bpm=120.0
        ),
        notes=[
            TabNote(string=0, fret=3, time=0.0, sustain=0.5),
            TabNote(string=1, fret=5, time=0.0, sustain=0.5),
            TabNote(string=2, fret=5, time=0.0, sustain=0.5),
        ],
        sections=[Section(name="riff", start_time=0.0)],
    )
    model = from_arrangement(arr)
    assert len(model.chord_templates) == 1
    template = model.chord_templates[0]
    assert template.frets[:3] == (3, 5, 5)
    assert template.fingers == (1, 3, 4, -1, -1, -1)
    assert template.name == "G5"

    level = model.arrangements[-1]
    assert len(level.fingerprints1) == 1 and level.fingerprints2 == []
    fp = level.fingerprints1[0]
    assert (fp.chord_id, fp.start_time, fp.first_note_time) == (0, 0.0, 0.0)
    assert fp.end_time == pytest.approx(0.501)
    assert fp.last_note_time == pytest.approx(0.5)  # convertHandshape: last + sustain
    assert level.notes[0].fingerprint_id == (0, -1)

    # The note entry should be a chord
    chord_note = level.notes[0]
    assert chord_note.mask & NOTE_MASK_CHORD
    assert chord_note.mask & NOTE_MASK_STRUM
    assert chord_note.chord_id == 0


def test_repeated_chords_marked_high_density_but_not_the_first() -> None:
    """A fast repeated chord run condenses via HIGH_DENSITY (the first hit keeps
    its full box); without it the stacked full chord boxes render as a corrupt
    lateral highway sprite. Isolated on a real GP7 rhythm chug."""
    # Four identical power chords a 16th apart (fast chug), then one distinct chord.
    def pc(t: float, fret: int) -> list[TabNote]:
        return [TabNote(string=s, fret=fret, time=t, sustain=0.1) for s in (0, 1, 2)]

    notes = pc(0.0, 3) + pc(0.15, 3) + pc(0.30, 3) + pc(0.45, 3) + pc(2.0, 5)
    arr = Arrangement(
        kind=ArrangementKind.RHYTHM,
        metadata=SongMetadata(title="Song", artist="A", song_length=5.0),
        tuning=Tuning(),
        tempo_map=TempoMap(
            beats=(Beat(time=0.0, measure=1), Beat(time=0.5, measure=-1)), average_bpm=120.0
        ),
        notes=notes,
        sections=[Section(name="riff", start_time=0.0)],
    )
    level = from_arrangement(arr).arrangements[-1]
    chords = sorted((n for n in level.notes if n.chord_id >= 0), key=lambda n: n.time)
    # First hit of the run: full box (low density). Repeats: condensed (high density).
    assert not (chords[0].mask & NOTE_MASK_HIGHDENSITY)
    assert all(c.mask & NOTE_MASK_HIGHDENSITY for c in chords[1:4])
    # The distinct chord far later starts a new run — full box again.
    assert not (chords[4].mask & NOTE_MASK_HIGHDENSITY)


def test_double_stop_gets_mask() -> None:
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="Song", artist="A", song_length=5.0),
        tuning=Tuning(),
        tempo_map=TempoMap(
            beats=(Beat(time=0.0, measure=1), Beat(time=0.5, measure=-1)), average_bpm=120.0
        ),
        notes=[
            TabNote(string=0, fret=2, time=0.0, sustain=0.5),
            TabNote(string=1, fret=2, time=0.0, sustain=0.5),
        ],
        sections=[Section(name="riff", start_time=0.0)],
    )
    model = from_arrangement(arr)
    level = model.arrangements[-1]
    assert level.notes[0].mask & NOTE_MASK_DOUBLESTOP


def test_sustained_chord_gets_chord_notes_with_per_string_sustain() -> None:
    """A plain sustained chord (no technique) must still get a ChordNotes entry
    carrying the per-string SUSTAIN bit — byte-diffing a DLC Builder build of a
    real song showed it emits one for EVERY sustained chord (masks 0x2000 /
    0x2004 with no technique). Without it, chord_notes_id stayed -1, the game
    had no per-string sustain to render, and drew corrupt vertical/lateral bars
    on a sustained power-chord chug (visible while scrubbing in Riff Repeater)."""
    arr = Arrangement(
        kind=ArrangementKind.RHYTHM,
        metadata=SongMetadata(title="Song", artist="A", song_length=5.0),
        tuning=Tuning(),
        tempo_map=TempoMap(beats=(Beat(time=0.0, measure=1),), average_bpm=120.0),
        notes=[
            # A plain fretted power chord with sustain, no technique.
            TabNote(string=0, fret=3, time=0.0, sustain=0.4),
            TabNote(string=1, fret=3, time=0.0, sustain=0.4),
        ],
        sections=[Section(name="riff", start_time=0.0)],
    )
    model = from_arrangement(arr)
    assert len(model.chord_notes) == 1
    # Both used strings carry SUSTAIN (0x2000); unused strings stay 0.
    assert model.chord_notes[0].note_mask[0] & NOTE_MASK_SUSTAIN
    assert model.chord_notes[0].note_mask[1] & NOTE_MASK_SUSTAIN
    assert model.chord_notes[0].note_mask[2] == 0
    # BUG-0078: technique bits only — the SINGLE note-kind bit inside a
    # ChordNotes entry drew a corrupt full-height bar at a palm-muted chord run.
    assert not any(m & NOTE_MASK_SINGLE for m in model.chord_notes[0].note_mask)
    chord_note = model.arrangements[-1].notes[0]
    assert chord_note.chord_notes_id == 0
    assert chord_note.mask & NOTE_MASK_CHORDNOTES


def test_an_open_string_chord_without_sustain_still_gets_its_chord_notes() -> None:
    """DLC Builder (XmlToSngNote.createChordNotes) writes a ChordNotes entry
    unless every string's mask is empty, and an open string always carries
    OPEN. A drop-tuned 0-0-0 power chord with no sustain (every short note
    since `drop_short_sustains`) went out with none, and the game drew those
    chords painted solid from the top string to the bottom ("Behind",
    Kills Birds, a user's report). A fully fretted unsustained chord has
    nothing per string to say and still gets none."""
    def chord(frets: tuple[int, ...]):
        arr = Arrangement(
            kind=ArrangementKind.RHYTHM,
            metadata=SongMetadata(title="Song", artist="A", song_length=5.0),
            tuning=Tuning(),
            tempo_map=TempoMap(beats=(Beat(time=0.0, measure=1),), average_bpm=120.0),
            notes=[TabNote(string=s, fret=f, time=1.0, sustain=0.0)
                   for s, f in enumerate(frets)],
            sections=[Section(name="riff", start_time=0.0)],
        )
        model = from_arrangement(arr)
        return model, next(n for n in model.arrangements[-1].notes if n.chord_id >= 0)

    model, note = chord((0, 0, 0))
    assert note.chord_notes_id == 0
    assert note.mask & NOTE_MASK_CHORDNOTES
    masks = model.chord_notes[0].note_mask
    assert all(masks[s] & NOTE_MASK_OPEN for s in range(3))
    assert not any(masks[s] & NOTE_MASK_SUSTAIN for s in range(3))
    assert masks[3] == masks[4] == masks[5] == 0
    assert check_sng(model) == []

    model, note = chord((5, 7, 7))
    assert note.chord_notes_id == -1 and not model.chord_notes
    assert not note.mask & NOTE_MASK_CHORDNOTES


def test_chord_with_techniques_produces_chord_notes() -> None:
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="Song", artist="A", song_length=5.0),
        tuning=Tuning(),
        tempo_map=TempoMap(
            beats=(Beat(time=0.0, measure=1),), average_bpm=120.0
        ),
        notes=[
            TabNote(string=0, fret=2, time=0.0, sustain=0.5, bend_semitones=1.0),
            TabNote(string=1, fret=3, time=0.0, sustain=0.5),
        ],
        sections=[Section(name="riff", start_time=0.0)],
    )
    model = from_arrangement(arr)
    assert len(model.chord_notes) == 1
    assert model.chord_notes[0].note_mask[0] & NOTE_MASK_BEND  # string 0 bends

    level = model.arrangements[-1]
    chord_note = level.notes[0]
    assert chord_note.chord_notes_id == 0
    assert chord_note.mask & NOTE_MASK_CHORDNOTES


def test_note_exactly_on_a_phrase_boundary_belongs_to_the_later_iteration() -> None:
    """_build_level locates each phrase iteration's notes via binary search on
    the time-sorted note list (a rewrite from a per-phrase O(notes) rescan, for
    speed on a long song) — the boundary semantics must stay EXACTLY the
    original `pi.start_time <= n.time < pi.end_time`: a note landing precisely
    on the shared instant between two contiguous iterations belongs to the
    iteration it STARTS, not the one it ends, and must never be double-counted
    or dropped."""
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="Song", artist="A", song_length=20.0),
        tuning=Tuning(),
        tempo_map=TempoMap(beats=_bars(20), average_bpm=60.0),
        notes=[
            TabNote(string=0, fret=1, time=1.0, sustain=0.2),
            TabNote(string=0, fret=2, time=8.9, sustain=0.05),
            TabNote(string=0, fret=3, time=9.0, sustain=0.2),  # exactly the boundary
            TabNote(string=0, fret=4, time=11.0, sustain=0.2),
        ],
    )
    model = from_arrangement(arr)
    assert [round(pi.start_time, 3) for pi in model.phrase_iterations][1:3] == [1.0, 9.0]
    top = model.arrangements[-1]
    assert len(top.notes) == 4  # nothing dropped or duplicated
    counts = top.notes_in_iteration1
    assert sum(counts) == 4  # every note attributed to exactly one iteration
    assert counts[1] == 2  # 1.0 and 8.9
    assert counts[2] == 2  # 9.0 (the boundary) and 11.0


def test_note_linkage_within_phrase() -> None:
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="Song", artist="A", song_length=5.0),
        tuning=Tuning(),
        tempo_map=TempoMap(
            beats=(Beat(time=0.0, measure=1), Beat(time=1.0, measure=-1)), average_bpm=120.0
        ),
        notes=[
            TabNote(string=0, fret=2, time=0.0, sustain=0.3),
            TabNote(string=0, fret=3, time=0.5, sustain=0.3),
            TabNote(string=0, fret=5, time=1.0, sustain=0.3),
        ],
        sections=[Section(name="riff", start_time=0.0)],
    )
    model = from_arrangement(arr)
    notes = model.arrangements[-1].notes
    assert len(notes) == 3
    # First note: no prev, has next
    assert notes[0].prev_iter_note == -1
    assert notes[0].next_iter_note == 1
    # Middle note: has both
    assert notes[1].prev_iter_note == 0
    assert notes[1].next_iter_note == 2
    # Last note: has prev, no next
    assert notes[2].prev_iter_note == 1
    assert notes[2].next_iter_note == -1


def test_vocals_round_trip() -> None:
    arrangement = _arrangement()
    vocals = [VocalEvent(time=1.0, length=0.5, lyric="hello+")]
    model = from_arrangement(arrangement, vocals=vocals)
    data = write_sng(model)
    restored = read_sng(data)
    assert len(restored.vocals) == 1
    assert restored.vocals[0].lyric == "hello+"
    assert abs(restored.vocals[0].time - 1.0) < 1e-6


def test_empty_arrangement_produces_valid_sng() -> None:
    arr = Arrangement(
        kind=ArrangementKind.COMBINED,
        metadata=SongMetadata(title="Empty", artist="A", song_length=5.0),
        tuning=Tuning(),
        tempo_map=TempoMap(beats=(Beat(time=0.0, measure=1),), average_bpm=120.0),
        notes=[TabNote(string=0, fret=2, time=0.0, sustain=0.5)],
        sections=[],
    )
    model = from_arrangement(arr)
    data = write_sng(model)
    restored = read_sng(data)
    # One note still gets levels to climb (the DD floor), its note on each.
    assert len(restored.arrangements) == restored.metadata.max_difficulty + 1
    assert all(len(lv.notes) == 1 for lv in restored.arrangements)
    assert restored.metadata.song_length == 5.0
    # A song with no section markers must STILL get a phrase timeline, or the
    # game loads the fretboard, shows no notes and crashes. The last phrase
    # iteration ends at the song's end so playback doesn't stop early.
    assert len(restored.phrases) >= 1
    assert len(restored.phrase_iterations) >= 1
    assert restored.phrase_iterations[-1].end_time == 5.0


def test_arrangement_level_has_phrase_counts() -> None:
    arrangement = _arrangement()
    model = from_arrangement(arrangement)
    level = model.arrangements[-1]
    assert level.phrase_count == len(model.phrases)
    assert len(level.avg_notes_per_iteration) == level.phrase_count
    assert len(level.notes_in_iteration1) == len(model.phrase_iterations)


def test_dynamic_difficulty_generates_ramping_levels() -> None:
    # Notes on downbeats/beats/half/quarter should produce several DD levels,
    # each with more notes than the last, the top level being the full chart.
    beats = []
    for meas in range(6):
        for b in range(4):
            beats.append(Beat(time=meas * 2.0 + b * 0.5, measure=meas + 1 if b == 0 else -1))
    times = []
    for meas in range(6):
        base = meas * 2.0
        times += [base, base + 0.5, base + 0.75, base + 1.0, base + 1.25]
    arr = Arrangement(
        kind=ArrangementKind.COMBINED,
        metadata=SongMetadata(title="S", artist="A", song_length=12.0),
        tuning=Tuning(),
        tempo_map=TempoMap(beats=tuple(beats), average_bpm=120.0),
        notes=[TabNote(string=i % 6, fret=(i % 10) + 1, time=times[i], sustain=0.2)
               for i in range(len(times))],
    )
    model = from_arrangement(arr)
    counts = [len(lvl.notes) for lvl in model.arrangements]
    assert len(counts) >= 2                       # DD actually kicked in
    assert counts == sorted(counts)               # each level adds notes
    assert counts[-1] == len(times)               # top level is the full chart
    assert model.metadata.max_difficulty == len(counts) - 1
    # Round-trips with all levels intact.
    restored = read_sng(write_sng(model))
    assert [len(lvl.notes) for lvl in restored.arrangements] == counts


def test_sectionless_song_is_segmented_into_multiple_phrases() -> None:
    # A long GP with no section markers must still be split into many phrases so
    # DD ramps per-phrase as the player progresses (a real DDC auto-segments); one
    # giant phrase spanning the whole song gives a poor DD.
    beats = [Beat(time=i * 0.5, measure=i // 4 + 1 if i % 4 == 0 else -1) for i in range(400)]
    notes = [TabNote(string=i % 6, fret=(i % 7) + 1, time=round(i * 0.5, 3), sustain=0.2)
             for i in range(360)]
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="S", artist="A", song_length=190.0),
        tuning=Tuning(),
        tempo_map=TempoMap(beats=tuple(beats), average_bpm=120.0),
        notes=notes,
        sections=[],
    )
    model = from_arrangement(arr)
    # ~190 s / 13 s ≈ a dozen-plus segments (not just COUNT/body/END). Segments
    # are phrase ITERATIONS; identical iterations may share one phrase (dedup),
    # so assert on the iteration count, which measures the segmentation.
    assert len(model.phrase_iterations) >= 8
    # Phrase iterations stay ordered and non-overlapping.
    starts = [pi.start_time for pi in model.phrase_iterations]
    assert starts == sorted(starts)
    # No anchor crosses a phrase boundary and each phrase owns an anchor at start.
    bounds = {pi.start_time for pi in model.phrase_iterations}
    top = model.arrangements[-1]
    assert not any(a.start_time < b < a.end_time for a in top.anchors for b in bounds)
    # Every NOTE-BEARING phrase owns an anchor at its start (an empty END phrase
    # needs none — it has no notes to frame).
    for pi in model.phrase_iterations:
        if any(pi.start_time <= n.time < pi.end_time for n in top.notes):
            assert any(abs(a.start_time - pi.start_time) < 1e-9 for a in top.anchors)


def _phrase_heights_by_section(model, sections) -> dict[str, int]:
    """Max difficulty per SOURCE section name.

    Phrases are named p0…pN (unique per phrase, as a real DDC emits), so they can
    no longer be looked up by the section name they came from — map through the
    phrase iterations' start times instead, which is what actually ties a phrase
    back to its section.
    """
    starts = sorted((sec.start_time, sec.name) for sec in sections)
    out: dict[str, int] = {}
    for it in model.phrase_iterations:
        name = None
        for t, n in starts:
            if t <= it.start_time + 1e-6:
                name = n
            else:
                break
        if name is None:
            continue
        maxd = model.phrases[it.phrase_id].max_difficulty
        out[name] = max(out.get(name, 0), maxd)
    return out


def test_dd_phrase_heights_vary_with_density() -> None:
    # Variable-height DD: a phrase's max difficulty scales with ITS OWN note
    # density, so the in-game difficulty bars vary per phrase (matching a real
    # DDC) instead of a flat top. NOTE: this guards the ORDERING/spread, not an
    # absolute level count — the ceiling counts groups of notes
    # (_NOTES_PER_DD_LEVEL), because a level per single note made the ramp so
    # long the player never left the minimum difficulty in-game.
    notes = [TabNote(string=0, fret=3, time=1.0 + i, sustain=0.2) for i in range(6)]
    notes += [TabNote(string=i % 6, fret=(i % 10) + 1, time=9.0 + i * 0.5, sustain=0.15)
              for i in range(15)]
    notes += [TabNote(string=i % 6, fret=(i % 12) + 1, time=17.0 + i * 0.2, sustain=0.1)
              for i in range(36)]
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="S", artist="A", song_length=30.0),
        tuning=Tuning(),
        tempo_map=TempoMap(beats=_bars(30), average_bpm=60.0),
        notes=notes,
    )
    model = from_arrangement(arr)
    heights = _phrase_heights_by_section(model, [
        Section(name="sparse", start_time=1.0), Section(name="medium", start_time=9.0),
        Section(name="dense", start_time=17.0), Section(name="end", start_time=25.0),
    ])
    # Strictly increasing with density — the bars have their own heights.
    assert heights["sparse"] < heights["medium"] < heights["dense"]
    assert len({p.max_difficulty for p in model.phrases}) >= 3  # not a flat top
    # ...and the ramp is GROUPED: the densest phrase's ceiling is far below its
    # note count, so the player climbs it in a handful of plays, not ~36.
    assert heights["dense"] <= (36 - 1) // 2


def test_a_short_phrase_still_gets_levels_to_climb() -> None:
    """A phrase with only a handful of notes must still have a ramp. The ceiling
    was a bare (notes-1)//group, so a 3-note phrase got ZERO levels — one level,
    nothing to promote to, permanently stuck at the minimum however well it was
    played. A DLC Builder build of the user's own song gives every phrase that
    has notes a ceiling of at least 3 (a one-note phrase six); a phrase with NO
    notes (a gap, NOGUITAR) still stays at 0 — there is nothing to ramp."""
    notes = [TabNote(string=0, fret=3, time=1.0 + i * 0.5, sustain=0.2) for i in range(3)]
    notes += [TabNote(string=i % 6, fret=(i % 12) + 1, time=17.0 + i * 0.12, sustain=0.1)
              for i in range(36)]
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="S", artist="A", song_length=30.0),
        tuning=Tuning(),
        tempo_map=TempoMap(beats=_bars(30), average_bpm=60.0),
        notes=notes,
    )
    model = from_arrangement(arr)
    heights = _phrase_heights_by_section(model, [
        Section(name="tiny", start_time=1.0), Section(name="silent", start_time=9.0),
        Section(name="dense", start_time=17.0), Section(name="end", start_time=25.0),
    ])
    assert heights["tiny"] >= 4, "a phrase with notes must have levels to climb"
    assert heights["silent"] == 0, "a phrase with no notes has nothing to ramp"
    assert heights["dense"] > heights["tiny"]


def test_identical_riffs_share_one_phrase() -> None:
    """A riff repeated note-for-note must collapse to ONE phrase with several
    iterations (real-DDC phrase linking: learned once, mastered everywhere), not
    a separate re-ramping phrase per repeat. A different riff stays its own
    phrase."""
    riff = [(0, 3), (1, 5), (2, 7), (0, 3)]
    notes = []
    for base in (1.0, 9.0):
        notes += [TabNote(string=s, fret=f, time=base + j * 0.5, sustain=0.2)
                  for j, (s, f) in enumerate(riff)]
    other = [(3, 2), (4, 4), (5, 1), (3, 9)]
    notes += [TabNote(string=s, fret=f, time=17.0 + j * 0.5, sustain=0.2)
              for j, (s, f) in enumerate(other)]
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="S", artist="A", song_length=24.0),
        tuning=Tuning(),
        tempo_map=TempoMap(beats=_bars(24), average_bpm=60.0),
        notes=notes,
    )
    model = from_arrangement(arr)
    ids = {round(pi.start_time): pi.phrase_id for pi in model.phrase_iterations}
    assert ids[1] == ids[9]      # identical riffs → same phrase
    assert ids[17] != ids[1]     # different riff → different phrase
    assert len(model.phrases) < len(model.phrase_iterations)


def test_note_phrase_id_is_in_bounds_after_linking() -> None:
    """Every note's phrase_id must index a REAL phrase, not the iteration index —
    once phrase-linking makes fewer phrases than iterations, a note carrying its
    iteration index as phrase_id runs off the end of the Phrases array, and the
    game crashes reading it *while scoring* that note (a hands-off run never
    touches it). Regression for the octave-5/7 scoring crash."""
    # 8 sections, an identical riff repeated in most → phrases < iterations, and
    # late iterations get an index above the (reduced) phrase count.
    beats = tuple(Beat(time=i * 0.5, measure=i // 4 + 1 if i % 4 == 0 else -1)
                  for i in range(200))
    riff = [(0, 3), (1, 5), (2, 7)]
    notes: list[TabNote] = []
    for k in range(8):
        base = k * 8.0
        # Alternate an identical riff with a slightly different one so some
        # sections dedup and the iteration count outruns the phrase count.
        shape = riff if k % 2 == 0 else [(s, f + 1) for s, f in riff]
        notes += [TabNote(string=s, fret=f, time=base + j * 0.5, sustain=0.2)
                  for j, (s, f) in enumerate(shape)]
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="S", artist="A", song_length=68.0),
        tuning=Tuning(),
        tempo_map=TempoMap(beats=beats, average_bpm=120.0),
        notes=notes,
        sections=[Section(name=f"S{k}", start_time=k * 8.0) for k in range(8)],
    )
    for dd in (True, False):
        model = from_arrangement(arr, dynamic_difficulty=dd)
        n_phrases = len(model.phrases)
        assert n_phrases < len(model.phrase_iterations)  # linking happened
        for level in model.arrangements:
            for n in level.notes:
                assert 0 <= n.phrase_id < n_phrases, (
                    f"note phrase_id {n.phrase_id} out of range (phrases={n_phrases})"
                )


def test_dd_low_levels_spread_notes_across_the_phrase() -> None:
    # A long single-phrase song (no section markers): low DD levels must show the
    # strongest beats spread across the WHOLE phrase, not clustered in its first
    # part (the "low difficulty only shows the first half of the song" bug).
    beats = [Beat(time=i * 0.5, measure=i // 4 + 1 if i % 4 == 0 else -1) for i in range(200)]
    notes = [TabNote(string=i % 6, fret=(i % 7) + 1, time=round(i * 0.25, 3), sustain=0.1)
             for i in range(360)]
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="S", artist="A", song_length=95.0),
        tuning=Tuning(),
        tempo_map=TempoMap(beats=tuple(beats), average_bpm=120.0),
        notes=notes,
        sections=[],  # → one big phrase
    )
    model = from_arrangement(arr)
    song_len = max(n.time for n in notes)
    low = model.arrangements[0]
    assert 0 < len(low.notes) < len(notes)  # DD actually thinned it
    # Split the song into thirds; the low level must have notes in every third.
    thirds = [0, 0, 0]
    for n in low.notes:
        thirds[min(2, int(n.time / song_len * 3))] += 1
    assert all(t > 0 for t in thirds), thirds


def test_dd_hero_triples_and_density_graduated_ceilings() -> None:
    # A DDC-shaped DD: a dense phrase reaches a higher ceiling than a sparse one,
    # and each iteration's hero triple is (round(max/4), round(max/2), max) — the
    # Easy/Medium/Hard levels a retail SNG carries (verified against a reference).
    beats = [Beat(time=i * 0.5, measure=i // 4 + 1 if i % 4 == 0 else -1) for i in range(64)]
    # Phrase A (0..8s): busy — a note every 0.25s. Phrase B (8..end): sparse.
    dense = [round(t * 0.25, 3) for t in range(32)]  # 8s of 16th notes
    sparse = [8.0, 10.0, 12.0]
    notes = [TabNote(string=i % 6, fret=(i % 7) + 1, time=t, sustain=0.1)
             for i, t in enumerate(dense + sparse)]
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="S", artist="A", song_length=16.0),
        tuning=Tuning(),
        tempo_map=TempoMap(beats=tuple(beats), average_bpm=120.0),
        notes=notes,
        sections=[Section(name="busy", number=1, start_time=0.0),
                  Section(name="calm", number=1, start_time=8.0)],
    )
    model = from_arrangement(arr)
    by_name = _phrase_heights_by_section(model, arr.sections)
    assert by_name["busy"] > by_name["calm"]  # density graduates the ceiling
    for pi in model.phrase_iterations:
        pmax = model.phrases[pi.phrase_id].max_difficulty
        assert pi.difficulty == (round(pmax / 4), round(pmax / 2), pmax)
    # Consistent song-wide max across levels + metadata.
    assert model.metadata.max_difficulty == len(model.arrangements) - 1
    assert model.metadata.max_difficulty == max(
        p.max_difficulty for p in model.phrases
    )


def test_dd_levels_have_their_own_hand_shapes_and_slide_extensions() -> None:
    # Hand shapes and slide anchor-extensions are both built per level from
    # that level's own notes: an extension (or a hand shape) over a note the
    # level dropped points the game at nothing.
    beats = [Beat(time=i * 0.5, measure=i // 4 + 1 if i % 4 == 0 else -1) for i in range(64)]
    notes = []
    # A dense double-stop riff (chords on every 8th) + a sliding single note.
    for i in range(32):
        t = round(i * 0.25, 3)
        notes.append(TabNote(string=2, fret=7, time=t, sustain=0.1))
        notes.append(TabNote(string=1, fret=5, time=t, sustain=0.1))
    notes.append(TabNote(string=0, fret=5, time=8.5, sustain=0.5, slide_to_fret=9))
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="S", artist="A", song_length=16.0),
        tuning=Tuning(),
        tempo_map=TempoMap(beats=tuple(beats), average_bpm=120.0),
        notes=notes,
    )
    model = from_arrangement(arr)
    assert len(model.arrangements) >= 2
    top = model.arrangements[-1]
    assert len(top.anchor_extensions) == 1  # the slide
    for lvl in model.arrangements:
        assert lvl.fingerprints2 == []
        # Every chord sits inside its own level's hand shape of that chord; no
        # single note does, and the shapes run in order without overlapping.
        fps = lvl.fingerprints1
        for n in lvl.notes:
            if n.chord_id >= 0:
                fp = fps[n.fingerprint_id[0]]
                assert fp.chord_id == n.chord_id
                assert fp.start_time <= n.time < fp.end_time
            else:
                assert n.fingerprint_id == (-1, -1)
        assert all(a.end_time <= b.start_time for a, b in zip(fps, fps[1:], strict=False))
        assert all(
            any(fp.start_time <= n.time < fp.end_time for n in lvl.notes) for fp in fps
        )
        # Every extension matches a sliding note present in THIS level.
        slide_ends = {
            round(n.time + n.sustain, 4)
            for n in lvl.notes
            if n.slide_to >= 0 or n.chord_notes_id >= 0
        }
        assert all(round(ae.beat_time, 4) in slide_ends for ae in lvl.anchor_extensions)


def test_dd_ramp_is_grouped_not_one_level_per_note() -> None:
    """A phrase's DD ceiling counts GROUPS of notes, not single notes.

    The game promotes a phrase one level per successful play, so a ceiling of
    (notes - 1) meant ~20 perfect playthroughs to reach the full chart and only a
    sliver of the notes after two — in-game that reads as "the difficulty never
    leaves the minimum" (the reported bug). Guards the ramp shape AND that the
    top level is still the complete chart.
    """
    beats = [Beat(time=i * 0.5, measure=i // 4 + 1 if i % 4 == 0 else -1) for i in range(64)]
    # One dense phrase: 31 single notes inside the first section.
    notes = [TabNote(string=2, fret=7, time=round(i * 0.25, 3), sustain=0.1) for i in range(31)]
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="S", artist="A", song_length=16.0),
        tuning=Tuning(),
        tempo_map=TempoMap(beats=tuple(beats), average_bpm=120.0),
        notes=notes,
    )
    model = from_arrangement(arr)
    busiest = max(len(n.notes) for n in [model.arrangements[-1]])
    ceiling = max(p.max_difficulty for p in model.phrases)
    # Grouped: roughly notes/3, decisively fewer levels than one-per-note.
    assert 0 < ceiling <= (busiest - 1) // 2, f"ramp too long: {ceiling} for {busiest} notes"
    # The top level is still 100% of the chart — the fix changes only how fast the
    # player climbs, never what the summit contains.
    assert len(model.arrangements[-1].notes) == len(notes)
    assert len(model.arrangements) == model.metadata.max_difficulty + 1


def test_sections_carry_per_difficulty_string_masks() -> None:
    """Each section's 36-byte StringMask must say which strings are played at
    each difficulty level.

    It used to be written as 36 zero bytes — i.e. "no string is played at any
    difficulty in this section" — which is per-DD data the engine reads. Guards
    that byte d is populated for every emitted level, that the bits are a subset
    of the strings the chart actually uses, and that it survives the binary
    round-trip.
    """
    beats = [Beat(time=i * 0.5, measure=i // 4 + 1 if i % 4 == 0 else -1) for i in range(64)]
    notes = [
        TabNote(string=i % 4, fret=(i % 9) + 1, time=round(i * 0.25, 3), sustain=0.1)
        for i in range(28)
    ]
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="S", artist="A", song_length=16.0),
        tuning=Tuning(),
        tempo_map=TempoMap(beats=tuple(beats), average_bpm=120.0),
        notes=notes,
        sections=[Section(name="a", start_time=0.0), Section(name="b", start_time=4.0)],
    )
    model = from_arrangement(arr)
    assert any(any(s.string_mask) for s in model.sections), "all masks were blank"
    for s in model.sections:
        assert len(s.string_mask) == 36
        # Only strings 0-3 are used by this chart, so bits 4/5 must never be set.
        assert all(b & ~0b1111 == 0 for b in s.string_mask)
    # A section with notes has a mask byte for every emitted difficulty level.
    busy = next(s for s in model.sections if any(s.string_mask))
    for lvl in model.arrangements:
        if any(busy.start_time - 1e-6 <= n.time < busy.end_time - 1e-6 for n in lvl.notes):
            assert busy.string_mask[lvl.difficulty] != 0
    back = read_sng(write_sng(model))
    assert [s.string_mask for s in back.sections] == [s.string_mask for s in model.sections]


def test_gp_sections_are_bracketed_with_count_and_end_and_links() -> None:
    # Real GP sections must still be bracketed by a COUNT phrase (count-in, max
    # difficulty 0 — without it the silent intro sits inside a high-difficulty
    # phrase, an all-black bar in the Riff Repeater) and an END phrase after the
    # last note. Every phrase carries PhraseIterationLinks = its iteration count
    # (retail values; 0 broke Riff Repeater phrase navigation → crash entering
    # the next phrase).
    beats = [Beat(time=i * 0.5, measure=i // 4 + 1 if i % 4 == 0 else -1) for i in range(80)]
    notes = [TabNote(string=i % 6, fret=(i % 5) + 2, time=round(4.0 + i * 0.5, 3), sustain=0.3)
             for i in range(40)]  # first note at 4.0s — a silent intro
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="S", artist="A", song_length=40.0),
        tuning=Tuning(),
        tempo_map=TempoMap(beats=tuple(beats), average_bpm=120.0),
        notes=notes,
        sections=[Section(name="Verse", number=1, start_time=0.0),
                  Section(name="Chorus", number=1, start_time=12.0)],
    )
    model = from_arrangement(arr)
    names = [p.name for p in model.phrases]
    assert names[0] == "COUNT" and names[-1] == "END"
    assert model.phrases[0].max_difficulty == 0
    assert model.phrases[-1].max_difficulty == 0
    # COUNT covers the silent intro; the body starts at the first note.
    assert model.phrase_iterations[0].start_time == 0.0
    assert model.phrase_iterations[0].end_time == 4.0
    # Links = per-phrase iteration count, never 0.
    assert all(p.phrase_iteration_links >= 1 for p in model.phrases)


def test_bend_point_reaches_peak_at_note_end_like_dlc_builder() -> None:
    # A decoded DLC Builder SNG of a bent note carries a single bend point at the
    # note's END (attack + sustain) with step = the bend in half-steps — a bend-UP
    # across the note, not a prebend at the attack.
    beats = tuple(Beat(time=i * 0.5, measure=1 if i == 0 else -1) for i in range(20))
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="S", artist="A", song_length=10.0),
        tuning=Tuning(),
        tempo_map=TempoMap(beats=beats, average_bpm=120.0),
        notes=[
            TabNote(string=0, fret=5, time=3.0, sustain=0.6, bend_semitones=1.0),  # single
            TabNote(string=1, fret=5, time=6.0, sustain=0.6, bend_semitones=1.0),  # chord…
            TabNote(string=2, fret=7, time=6.0, sustain=0.6),                      # …mate
        ],
    )
    model = from_arrangement(arr)
    top = model.arrangements[-1]
    single = next(n for n in top.notes if n.string == 0)
    assert len(single.bend_data) == 1
    assert single.bend_data[0].step == 1.0
    assert single.bend_data[0].time == 3.6  # attack 3.0 + sustain 0.6, not the attack
    chord = next(n for n in top.notes if n.chord_id >= 0)
    cn = model.chord_notes[chord.chord_notes_id]
    assert len(cn.bend_data[1]) == 1
    assert cn.bend_data[1][0].step == 1.0 and cn.bend_data[1][0].time == 6.6


def test_a_plain_rise_is_the_single_point_at_the_note_end() -> None:
    """A straight rise from the attack to the end (alphaTab's reading of "bend up
    and hold") is the same bend as the single peak at the end: one point, none at
    the attack. Same in the XML."""
    from rockforge.domain.music import BendPoint
    from rockforge.infrastructure.rsxml.writer import _bend_curve

    beats = tuple(Beat(time=i * 0.5, measure=1 if i == 0 else -1) for i in range(20))
    note = TabNote(string=0, fret=5, time=3.0, sustain=0.6, bend_semitones=1.0,
                   bend_points=(BendPoint(0.0, 0.0), BendPoint(1.0, 1.0)))
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="S", artist="A", song_length=10.0),
        tuning=Tuning(),
        tempo_map=TempoMap(beats=beats, average_bpm=120.0),
        notes=[note],
    )
    (single,) = from_arrangement(arr).arrangements[-1].notes
    assert [(b.time, b.step) for b in single.bend_data] == [(3.6, 1.0)]
    assert _bend_curve(note) == [(3.6, 1.0)]


def test_a_pre_bend_is_bent_at_the_attack_in_sng_and_xml(tmp_path) -> None:  # noqa: ANN001
    """A flat pre-bend: bent from the attack to the end, in the SNG and the XML,
    and read back from the XML as the same curve."""
    from rockforge.domain.music import BendPoint
    from rockforge.infrastructure.rsxml.reader import read_arrangement_xml
    from rockforge.infrastructure.rsxml.writer import write_arrangement_xml

    beats = tuple(Beat(time=i * 0.5, measure=1 if i == 0 else -1) for i in range(20))
    note = TabNote(string=0, fret=5, time=3.0, sustain=0.6, bend_semitones=1.0,
                   techniques=frozenset({Technique.BEND}),
                   bend_points=(BendPoint(0.0, 1.0), BendPoint(1.0, 1.0)))
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="S", artist="A", song_length=10.0),
        tuning=Tuning(),
        tempo_map=TempoMap(beats=beats, average_bpm=120.0),
        notes=[note],
    )
    (single,) = from_arrangement(arr).arrangements[-1].notes
    assert [(b.time, b.step) for b in single.bend_data] == [(3.0, 1.0), (3.6, 1.0)]
    back = read_arrangement_xml(write_arrangement_xml(arr, tmp_path / "lead.xml"))
    (read,) = [n for n in back.notes if n.bend_semitones]
    assert [(p.position, p.step) for p in read.bend_points] == [(0.0, 1.0), (1.0, 1.0)]


def test_fret_mute_slide_unpitch_and_composite_bend_in_sng() -> None:
    from rockforge.domain.music import BendPoint

    beats = tuple(Beat(time=i * 0.5, measure=1 if i == 0 else -1) for i in range(20))
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="S", artist="A", song_length=10.0),
        tuning=Tuning(),
        tempo_map=TempoMap(beats=beats, average_bpm=120.0),
        notes=[
            TabNote(string=0, fret=5, time=1.0, sustain=0.4,
                    techniques=frozenset({Technique.FRET_MUTE})),        # dead X
            TabNote(string=1, fret=9, time=2.0, sustain=0.4, slide_unpitch_to=4),  # slide-out
            TabNote(string=2, fret=7, time=3.0, sustain=0.4, bend_semitones=1.0,   # bend-and-
                    bend_points=(BendPoint(0.0, 0.0), BendPoint(0.5, 1.0),         # release
                                 BendPoint(1.0, 0.0))),
        ],
    )
    top = from_arrangement(arr).arrangements[-1]
    mute = next(n for n in top.notes if n.string == 0)
    assert mute.mask & NOTE_MASK_FRETHANDMUTE
    slide = next(n for n in top.notes if n.string == 1)
    assert slide.slide_unpitch_to == 4 and slide.mask & NOTE_MASK_SLIDEUNPITCHEDTO
    bend = next(n for n in top.notes if n.string == 2)
    assert len(bend.bend_data) == 3  # full curve, not collapsed to a single point
    assert [round(b.step, 1) for b in bend.bend_data] == [0.0, 1.0, 0.0]


def test_pinch_tremolo_finger_and_pickdir_in_sng() -> None:
    beats = tuple(Beat(time=i * 0.5, measure=1 if i == 0 else -1) for i in range(20))
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="S", artist="A", song_length=10.0),
        tuning=Tuning(),
        tempo_map=TempoMap(beats=beats, average_bpm=120.0),
        notes=[
            TabNote(string=0, fret=5, time=1.0, sustain=0.4,
                    techniques=frozenset({Technique.PINCH_HARMONIC})),
            TabNote(string=1, fret=7, time=2.0, sustain=0.4,
                    techniques=frozenset({Technique.TREMOLO})),
            TabNote(string=2, fret=3, time=3.0, sustain=0.4, left_hand=2, pick_direction=2),
        ],
    )
    top = from_arrangement(arr).arrangements[-1]
    assert next(n for n in top.notes if n.string == 0).mask & NOTE_MASK_PINCHHARMONIC
    assert next(n for n in top.notes if n.string == 1).mask & NOTE_MASK_TREMOLO
    finger = next(n for n in top.notes if n.string == 2)
    assert finger.left_hand == 2 and finger.pick_direction == 1


def test_chord_notes_bend_usedcount_is_after_the_32_entry_array() -> None:
    # The Sng2014 ChordNotes BendData layout per string is 32 fixed BendData32
    # entries THEN the Int32 UsedCount — verified against a DLC Builder SNG.
    # Writing the count first put it where the game expects the first bend point,
    # crashing at the first bent chord. This locks the byte order.
    from rockforge.infrastructure.packaging.psarc.sng import (
        _BEND32_SIZE,
        _BEND_DATA_COUNT,
        SngBendData32,
        SngChordNotes,
        _read_chord_notes_entry,
        _write_chord_notes_entry,
    )

    cn = SngChordNotes(
        note_mask=[0, 0x3000, 0, 0, 0, 0],
        bend_data=[[], [SngBendData32(time=6.0, step=1.0)], [], [], [], []],
        slide_to=[0xFF] * 6,
        slide_unpitch_to=[0xFF] * 6,
        vibrato=[0] * 6,
    )
    blob = _write_chord_notes_entry(cn)
    # String 0 has no bend → UsedCount 0 sits right after its 32 empty entries.
    string_block = 32 * _BEND32_SIZE + 4
    s0_count_off = 24 + _BEND_DATA_COUNT * _BEND32_SIZE  # after masks + s0's 32 entries
    assert struct.unpack_from("<i", blob, s0_count_off)[0] == 0
    # String 1's UsedCount (1) is at the END of its 32-entry array, not the front.
    s1_count_off = 24 + string_block + _BEND_DATA_COUNT * _BEND32_SIZE
    assert struct.unpack_from("<i", blob, s1_count_off)[0] == 1
    # And the bend point is the FIRST entry of string 1's array.
    s1_first_entry_off = 24 + string_block
    t, step = struct.unpack_from("<ff", blob, s1_first_entry_off)
    assert t == 6.0 and step == 1.0
    # Round-trips.
    restored, _ = _read_chord_notes_entry(blob, 0)
    assert len(restored.bend_data[1]) == 1
    assert restored.bend_data[1][0].time == 6.0 and restored.bend_data[1][0].step == 1.0
    assert restored.bend_data[0] == []


def test_plain_notes_have_no_slide() -> None:
    # slide_to must be -1 (no slide) for ordinary notes; writing 0 told the game
    # every note slides to fret 0 — a slide streak on every note.
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="S", artist="A", song_length=5.0),
        tuning=Tuning(),
        tempo_map=TempoMap(beats=(Beat(time=0.0, measure=1),), average_bpm=120.0),
        notes=[TabNote(string=s, fret=s + 2, time=s * 0.3, sustain=0.2) for s in range(6)],
    )
    notes = read_sng(write_sng(from_arrangement(arr))).arrangements[-1].notes
    assert notes and all(n.slide_to == -1 for n in notes)


def test_real_slide_is_preserved() -> None:
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="S", artist="A", song_length=5.0),
        tuning=Tuning(),
        tempo_map=TempoMap(beats=(Beat(time=0.0, measure=1),), average_bpm=120.0),
        notes=[TabNote(string=0, fret=5, time=0.0, sustain=0.5, slide_to_fret=7)],
    )
    note = read_sng(write_sng(from_arrangement(arr))).arrangements[-1].notes[0]
    assert note.slide_to == 7


def test_beats_carry_real_measures_and_downbeat_mask() -> None:
    # The Sng2014 beat is 16 bytes: the trailing mask (bit0 downbeat, bit1 even
    # measure) must be present, or every beat is 4 bytes short and the whole SNG
    # misaligns — the game crashes on load with an access violation.
    from rockforge.infrastructure.packaging.psarc.sng import _BEAT_SIZE

    assert _BEAT_SIZE == 16
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="S", artist="A", song_length=8.0),
        tuning=Tuning(),
        tempo_map=TempoMap(
            beats=tuple(
                Beat(time=i * 0.5, measure=(i // 4) + 1 if i % 4 == 0 else -1) for i in range(12)
            ),
            average_bpm=120.0,
        ),
        notes=[TabNote(string=0, fret=2, time=0.0, sustain=0.5)],
    )
    beats = read_sng(write_sng(from_arrangement(arr))).beats
    # Every beat has a real measure number (never -1), beat-in-measure 0..3.
    assert all(b.measure >= 1 for b in beats)
    assert beats[0].mask == 1  # measure 1 downbeat
    assert beats[4].mask == 3  # measure 2 (even) downbeat
    assert beats[1].mask == 0  # off-beat


def test_anchors_have_distinct_increasing_times() -> None:
    # Anchors that share a start time (an earlier bug keyed them off the phrase
    # iteration) overlap and crash the note highway on load.
    frets = [1, 5, 9, 5, 1, 7, 12, 3]
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="S", artist="A", song_length=8.0),
        tuning=Tuning(),
        tempo_map=TempoMap(
            beats=tuple(Beat(time=i * 0.5, measure=1 if i == 0 else -1) for i in range(18)),
            average_bpm=120.0,
        ),
        notes=[TabNote(string=0, fret=frets[i], time=i * 0.5, sustain=0.4) for i in range(8)],
        sections=[],
    )
    anchors = from_arrangement(arr).arrangements[-1].anchors
    assert len(anchors) >= 2
    times = [a.start_time for a in anchors]
    assert times == sorted(times)
    assert len(set(times)) == len(times)  # strictly distinct
    # Each anchor ends where the next begins (contiguous coverage).
    for i in range(len(anchors) - 1):
        assert anchors[i].end_time == anchors[i + 1].start_time


def test_anchors_are_built_per_level_not_shared() -> None:
    # A real DDC sizes anchors to each level's notes; sharing the full-chart
    # anchor set on a thinned low level ships anchors framing notes that don't
    # exist there, crashing the game on phrase entry. Low levels must therefore
    # carry FEWER anchors than the top level, and each level's anchors must cover
    # only its own note positions.
    beats = [Beat(time=i * 0.5, measure=i // 4 + 1 if i % 4 == 0 else -1) for i in range(120)]
    notes = [TabNote(string=i % 6, fret=(i % 9) + 1, time=round(i * 0.25, 3), sustain=0.1)
             for i in range(200)]
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="S", artist="A", song_length=60.0),
        tuning=Tuning(),
        tempo_map=TempoMap(beats=tuple(beats), average_bpm=120.0),
        notes=notes,
    )
    model = from_arrangement(arr)
    assert len(model.arrangements) >= 3
    counts = [len(lvl.anchors) for lvl in model.arrangements]
    assert counts[0] < counts[-1]  # low levels have fewer anchors than the top
    # A level's anchors are derived from its OWN notes: each level has a distinct
    # anchor set (not the shared full-chart one), and every anchor is in range.
    assert len(set(counts)) > 1
    for lvl in model.arrangements:
        for a in lvl.anchors:
            assert 1 <= a.fret <= 24 and a.start_time < a.end_time


def test_find_phrase_iteration_before_first_start_returns_first_index() -> None:
    """A query time before the first phrase iteration's start (the silent pad
    before COUNT, at the very start of the song) must resolve to index 0, not
    fall through to the "after everything" branch — which wrapped it onto the
    LAST phrase's index (26 on a real chart), corrupting the song-start anchor
    box and beat grid with a context from the song's ending."""
    from rockforge.infrastructure.packaging.psarc.sng import (
        SngPhraseIteration,
        _find_phrase_iteration,
    )

    pis = [
        SngPhraseIteration(phrase_id=0, start_time=2.5, end_time=10.0, difficulty=(0, 0, 0)),
        SngPhraseIteration(phrase_id=1, start_time=10.0, end_time=18.0, difficulty=(0, 0, 0)),
    ]
    assert _find_phrase_iteration(pis, 0.0) == 0  # before the first phrase: first index
    assert _find_phrase_iteration(pis, 1.5) == 0  # still in the pre-COUNT gap
    assert _find_phrase_iteration(pis, 5.0) == 0  # inside the first phrase
    assert _find_phrase_iteration(pis, 12.0) == 1  # inside the second phrase
    assert _find_phrase_iteration(pis, 100.0) == 1  # after everything: last index
    assert _find_phrase_iteration([], 5.0) == 0  # no phrases at all


def test_find_phrase_iteration_precomputed_starts_matches_on_demand() -> None:
    """The optional precomputed ``starts`` (passed from hot loops to skip the
    O(n) rebuild) must give the identical index to the on-demand path."""
    from rockforge.infrastructure.packaging.psarc.sng import (
        SngPhraseIteration,
        _find_phrase_iteration,
    )

    pis = [
        SngPhraseIteration(phrase_id=0, start_time=2.5, end_time=10.0),
        SngPhraseIteration(phrase_id=1, start_time=10.0, end_time=18.0),
        SngPhraseIteration(phrase_id=2, start_time=18.0, end_time=25.0),
    ]
    starts = [pi.start_time for pi in pis]
    for t in (-1.0, 0.0, 2.5, 5.0, 10.0, 17.999, 18.0, 24.9, 25.0, 100.0):
        assert _find_phrase_iteration(pis, t) == _find_phrase_iteration(pis, t, starts)


def test_song_start_anchor_has_correct_phrase_iteration_not_the_last(
) -> None:
    """Reproduces a real corrupted chart: a beat grid that starts after t=0 (a
    GP lead-in pad) leaves a gap before the first phrase iteration; the anchor
    RockForge forces to start at absolute 0.0 (so the opening notes are framed
    before they reach the strike line) landed on phrase_iteration_id=len-1 (a
    phrase near the SONG'S END) instead of the first phrase — corrupting the
    fret-hand anchor box right at the opening of the song."""
    beats = [Beat(time=2.5 + i * 0.5, measure=i // 4 + 1 if i % 4 == 0 else -1) for i in range(48)]
    notes = [TabNote(string=0, fret=(i % 5) + 3, time=round(2.5 + i * 0.5, 3), sustain=0.4)
             for i in range(40)]
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="S", artist="A", song_length=26.5),
        tuning=Tuning(),
        tempo_map=TempoMap(beats=tuple(beats), average_bpm=120.0),
        notes=notes,
        sections=[Section(name="a", number=1, start_time=2.5),
                  Section(name="b", number=1, start_time=10.5),
                  Section(name="c", number=1, start_time=17.5)],
    )
    model = from_arrangement(arr)
    top = model.arrangements[-1]
    song_start_anchor = next(a for a in top.anchors if a.start_time == 0.0)
    assert song_start_anchor.phrase_iteration_id == 0
    assert song_start_anchor.phrase_iteration_id != len(model.phrase_iterations) - 1


def test_anchors_do_not_cross_phrase_iteration_boundaries() -> None:
    # An anchor that spans a phrase-iteration boundary leaves the new phrase's
    # opening notes covered only by the PREVIOUS phrase's anchor; the game
    # re-anchors at each phrase start, finds none of its own, and crashes on
    # entry (seen exactly at a section / tone-change boundary). Every anchor must
    # stay within one phrase iteration, and each phrase must own an anchor at its
    # start.
    beats = [Beat(time=i * 0.5, measure=i // 4 + 1 if i % 4 == 0 else -1) for i in range(48)]
    notes = [TabNote(string=0, fret=(i % 5) + 3, time=round(i * 0.5, 3), sustain=0.4)
             for i in range(40)]
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="S", artist="A", song_length=24.0),
        tuning=Tuning(),
        tempo_map=TempoMap(beats=tuple(beats), average_bpm=120.0),
        notes=notes,
        # Sections carve the song into several phrase iterations.
        sections=[Section(name="a", number=1, start_time=0.0),
                  Section(name="b", number=1, start_time=8.0),
                  Section(name="c", number=1, start_time=15.0)],
    )
    model = from_arrangement(arr)
    pis = model.phrase_iterations
    bounds = {round(pi.start_time, 6) for pi in pis}
    for lvl in model.arrangements:
        for a in lvl.anchors:
            assert not any(a.start_time < b < a.end_time for b in bounds)
    # Each phrase iteration owns an anchor starting exactly at its start.
    top = model.arrangements[-1]
    for pi in pis:
        assert any(abs(a.start_time - pi.start_time) < 1e-6 for a in top.anchors)


def test_anchor_does_not_sit_below_a_chord_run() -> None:
    # A fret 3-5 chord run followed by a lone low (fret 1) note must NOT be folded
    # into one wide fret 1-5 anchor — the chords would then sit two frets below
    # where they're played ("anchor shows fret 1 for a 2-5 chord" glitch). The
    # chord run gets its own anchor that does not extend below fret 3.
    beats = [Beat(time=i * 0.5, measure=i // 4 + 1 if i % 4 == 0 else -1) for i in range(24)]
    notes = []
    for i in range(8):  # a 3-5 power-chord run
        t = round(i * 0.5, 3)
        notes.append(TabNote(string=4, fret=3, time=t, sustain=0.3))
        notes.append(TabNote(string=3, fret=5, time=t, sustain=0.3))
    notes.append(TabNote(string=5, fret=1, time=4.5, sustain=0.3))  # lone low note
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="S", artist="A", song_length=8.0),
        tuning=Tuning(),
        tempo_map=TempoMap(beats=tuple(beats), average_bpm=120.0),
        notes=notes,
    )
    anchors = from_arrangement(arr).arrangements[-1].anchors
    # The anchor active while the 3-5 chords play (t≈1.0) must not start at fret 1.
    active = [a for a in anchors if a.start_time <= 1.0 < a.end_time]
    assert active and active[0].fret >= 2
    assert all(a.width <= 4 for a in anchors)


def test_slide_notes_produce_anchor_extensions() -> None:
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="Song", artist="A", song_length=5.0),
        tuning=Tuning(),
        tempo_map=TempoMap(
            beats=(Beat(time=0.0, measure=1), Beat(time=1.0, measure=-1)), average_bpm=120.0
        ),
        notes=[
            TabNote(string=0, fret=5, time=0.0, sustain=0.5,
                    techniques=frozenset({Technique.SLIDE}), slide_to_fret=7),
            TabNote(string=1, fret=3, time=1.0, sustain=0.2),  # no slide
        ],
        sections=[Section(name="riff", start_time=0.0)],
    )
    model = from_arrangement(arr)
    exts = model.arrangements[-1].anchor_extensions
    assert len(exts) == 1
    # BeatTime is when the slide ends (time + sustain), fret is the destination.
    assert abs(exts[0].beat_time - 0.5) < 1e-6
    assert exts[0].fret == 7


def test_anchor_extensions_round_trip() -> None:
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="Song", artist="A", song_length=5.0),
        tuning=Tuning(),
        tempo_map=TempoMap(
            beats=(Beat(time=0.0, measure=1), Beat(time=1.0, measure=-1)), average_bpm=120.0
        ),
        notes=[
            TabNote(string=0, fret=5, time=0.0, sustain=0.5,
                    techniques=frozenset({Technique.SLIDE}), slide_to_fret=9),
        ],
        sections=[Section(name="riff", start_time=0.0)],
    )
    model = from_arrangement(arr)
    restored = read_sng(write_sng(model))
    exts = restored.arrangements[-1].anchor_extensions
    assert len(exts) == 1
    assert exts[0].fret == 9
    assert abs(exts[0].beat_time - 0.5) < 1e-6


def test_chord_template_notes_are_real_midi() -> None:
    # Drop-D-ish chord on standard tuning: open E (40), A fret2 (47), D fret2 (52)
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="Song", artist="A", song_length=5.0),
        tuning=Tuning(),  # standard: 40,45,50,55,59,64
        tempo_map=TempoMap(beats=(Beat(time=0.0, measure=1),), average_bpm=120.0),
        notes=[
            TabNote(string=0, fret=0, time=0.0, sustain=0.5),
            TabNote(string=1, fret=2, time=0.0, sustain=0.5),
            TabNote(string=2, fret=2, time=0.0, sustain=0.5),
        ],
        sections=[Section(name="riff", start_time=0.0)],
    )
    model = from_arrangement(arr)
    notes_midi = model.chord_templates[0].notes
    assert notes_midi[0] == 40  # open low E
    assert notes_midi[1] == 47  # A + 2
    assert notes_midi[2] == 52  # D + 2
    # Unused strings MUST be -1, not 0 — byte-verified against a DLC Builder
    # build of the same song. A 0 there (a real, absurdly low MIDI pitch on a
    # string that shouldn't sound) crashed the game at a gapped 5/7 octave's
    # entry, but only while the player was actually playing (the scoring path
    # dereferences the per-string MIDI; a spectating run never touches it).
    assert notes_midi[3] == -1
    assert notes_midi[4] == -1 and notes_midi[5] == -1


def test_from_vocals_only_populates_vocals() -> None:
    vocals = [
        VocalEvent(time=0.5, length=0.3, lyric="hel"),
        VocalEvent(time=0.8, length=0.4, lyric="lo+"),
    ]
    model = from_vocals(vocals)
    assert len(model.vocals) == 2
    assert model.beats == []
    assert model.arrangements == []
    assert model.chord_templates == []

    restored = read_sng(write_sng(model))
    assert len(restored.vocals) == 2
    assert restored.vocals[0].lyric == "hel"
    assert restored.vocals[1].lyric == "lo+"
    assert restored.arrangements == []


def test_vocals_note_is_non_pitched_sentinel() -> None:
    """Scroll lyrics must carry note 254 (Rocksmith's non-pitched sentinel),
    not 0. A DLC Builder-built vocals SNG uses 254; note 0 is a real (absurdly
    low) MIDI pitch, and the game then fails to render the lyric as a scroll —
    the "letra não aparece" symptom on a native PSARC."""
    from rockforge.infrastructure.rsxml.vocals import VOCAL_NOTE

    model = from_vocals([VocalEvent(time=0.5, length=0.3, lyric="hi+")])
    assert model.vocals[0].note == VOCAL_NOTE == 254
    assert read_sng(write_sng(model)).vocals[0].note == 254


def test_vocals_sng_carries_the_lyric_font_symbol_atlas() -> None:
    """A vocals SNG must embed the Symbols sections (the lyric font glyph
    atlas). With them empty the game has no glyphs and the letra never shows.
    The atlas is the vendored default Latin font (SymbolsHeader=2, Texture=1,
    Definition=192) referencing the built-in assets\\ui\\lyrics\\lyrics.dds, and
    it round-trips through read_sng."""
    import struct as _struct

    payload = write_sng(from_vocals([VocalEvent(time=0.5, length=0.3, lyric="hi+")]))
    # The symbol block sits right after the single vocal (4 zero counts +
    # vocal count + one 60-byte vocal). Header/Texture/Definition counts:
    pos = 4 * 4 + 4 + 60
    sh, = _struct.unpack_from("<I", payload, pos)
    st, = _struct.unpack_from("<I", payload, pos + 4 + sh * 32)
    sd, = _struct.unpack_from("<I", payload, pos + 4 + sh * 32 + 4 + st * 144)
    assert (sh, st, sd) == (2, 1, 192)
    assert b"lyrics.dds" in payload
    # Round-trips: the reader skips the populated symbol entries and still finds
    # the downstream sections intact.
    assert read_sng(payload).vocals[0].lyric == "hi+"


def test_instrument_sng_has_no_vocals_symbol_block() -> None:
    """Only vocals SNGs carry the symbol atlas — an instrument SNG (no vocals)
    must not, or the reader would desync."""
    arrangement = _arrangement()
    payload = write_sng(from_arrangement(arrangement))
    assert b"lyrics.dds" not in payload
    assert read_sng(payload).vocals == []


def test_build_chord_data_is_independently_callable() -> None:
    """from_arrangement's chord-template/ChordNotes logic (_build_chord_data)
    is now a standalone helper — construct it directly from a chord group
    without going through the whole pipeline, and confirm the ChordNotes
    sustain bit + template MIDI notes it's guarded to always emit."""
    from rockforge.infrastructure.packaging.psarc.sng import _build_chord_data

    arrangement = Arrangement(
        kind=ArrangementKind.RHYTHM,
        metadata=SongMetadata(title="S", artist="A", song_length=4.0),
        tuning=Tuning(),
        tempo_map=TempoMap(beats=(Beat(time=0.0, measure=1),), average_bpm=120.0),
        notes=[],
    )
    group = [
        TabNote(string=0, fret=0, time=0.0, sustain=0.5),
        TabNote(string=1, fret=2, time=0.0, sustain=0.5),
    ]
    template_ids, templates, chord_notes, chord_notes_map = _build_chord_data(
        arrangement, [group]
    )
    assert len(templates) == 1
    key = (0, 2, -1, -1, -1, -1)
    assert template_ids[key] == 0
    # Open string (fret 0) keeps its real open-string MIDI note, not -1.
    assert templates[0].notes[0] == arrangement.tuning.midi[0]
    assert templates[0].notes[1] == arrangement.tuning.midi[1] + 2
    # A sustained chord gets a ChordNotes entry even with no technique.
    assert 0 in chord_notes_map
    assert chord_notes[chord_notes_map[0]].note_mask[0] & NOTE_MASK_SUSTAIN


def test_build_sng_notes_is_independently_callable() -> None:
    """The single-note/chord SngNote assembly (_build_sng_notes) is now a
    standalone helper — feed it pre-built groups/anchors/phrase data directly."""
    from rockforge.infrastructure.packaging.psarc.sng import (
        SngAnchor,
        SngPhraseIteration,
        _build_sng_notes,
    )

    single = [[TabNote(string=0, fret=3, time=0.0, sustain=0.0)]]
    anchors = [SngAnchor(
        start_time=0.0, end_time=4.0, first_note_time=0.0, last_note_time=0.0,
        fret=3, width=4,
    )]
    phrase_iterations = [SngPhraseIteration(phrase_id=0, start_time=0.0, end_time=4.0)]
    notes = _build_sng_notes(single, [], anchors, phrase_iterations, {}, {})
    assert len(notes) == 1
    assert notes[0].string == 0 and notes[0].fret == 3
    assert notes[0].anchor_fret == 3 and notes[0].anchor_width == 4
    assert notes[0].phrase_iteration_id == 0


def _count_at(data: bytes, pos: int) -> int:
    import struct

    return int(struct.unpack_from("<i", data, pos)[0])


def _skip(data: bytes, pos: int, entry_size: int) -> int:
    """Advance past one counted, fixed-size SNG section."""
    return pos + 4 + _count_at(data, pos) * entry_size


def test_read_sng_skips_populated_sections_a_real_file_carries() -> None:
    """RockForge writes PhraseExtraInfo/NLD/Actions/Events/Tones/DNAs empty, and
    read_sng used to read only their COUNTS — fine for our own output, but it
    desynced on any real file: a DLC Builder SNG carries crowd/stage Events
    (e2/E3/E13/D3), and the parser then read the Sections count out of the
    middle of an event and came back with zero sections and zero levels. That
    made our own reader useless for byte-diffing against a reference build,
    which is the technique that has isolated every native-SNG rendering bug so
    far. The entries have to be skipped by SIZE.

    Builds the six sections by hand — their byte sizes are exactly what is under
    test — and checks the reader lands on the real data that follows.
    """
    import struct

    from rockforge.infrastructure.packaging.psarc import sng as sng_mod

    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="S", artist="A", song_length=8.0),
        tuning=Tuning(),
        tempo_map=TempoMap(
            beats=tuple(Beat(time=i * 0.5, measure=i // 4 + 1 if i % 4 == 0 else -1)
                        for i in range(16)),
            average_bpm=120.0,
        ),
        notes=[TabNote(string=0, fret=3, time=0.5 + i * 0.5, sustain=0.2) for i in range(6)],
        sections=[Section(name="riff", start_time=0.0)],
    )
    data = write_sng(from_arrangement(arr))
    plain = read_sng(data)
    assert plain.sections and plain.arrangements, "precondition: our own file parses"

    # Walk to the six empty counts our writer emits, rather than searching for a
    # zero run (an SNG is full of them). Every section before them is
    # fixed-size here: this arrangement has only single notes, so ChordNotes and
    # Vocals are both empty.
    at = _skip(data, 0, sng_mod._BEAT_SIZE)    # beats
    at = _skip(data, at, 12 + sng_mod._NAME_LEN)          # phrases
    at = _skip(data, at, 40 + sng_mod._NAME_LEN)          # chord templates
    assert _count_at(data, at) == 0, "expected no chord notes for a single-note chart"
    at = _skip(data, at, 0)                    # chord notes (none)
    assert _count_at(data, at) == 0, "expected no vocals"
    at = _skip(data, at, 0)                    # vocals (none)
    at = _skip(data, at, sng_mod._PHRASE_ITER_SIZE)       # phrase iterations

    # PhraseExtraInfo / NLinkedDifficulty / Actions, then OUR OWN Events, then
    # Tones / DNAs. Events are no longer empty — we emit the reference's stage
    # cues — so the round trip has to carry them back too.
    block_start = at
    assert data[at : at + 12] == struct.pack("<3i", 0, 0, 0)
    at += 12
    assert _count_at(data, at) == len(plain.events) > 0, "we now emit stage cues"
    at = _skip(data, at, sng_mod._EVENT_SIZE)
    assert data[at : at + 8] == struct.pack("<2i", 0, 0), "Tones/DNAs stay empty"
    block_end = at + 8

    # Replace the whole six-section block with one where EVERY section is
    # populated, including the five we don't model, and confirm the reader
    # skips those by size instead of desyncing on their contents.
    action = struct.pack("<f", 2.5) + b"action".ljust(256, b"\x00")
    assert len(action) == sng_mod._ACTION_SIZE
    event = struct.pack("<f", 1.25) + b"E3".ljust(256, b"\x00")
    assert len(event) == sng_mod._EVENT_SIZE
    block = (
        struct.pack("<i", 1) + struct.pack("<f", 1.0) + b"\x00" * 8  # PhraseExtraInfo
        + struct.pack("<ii", 1, 1) + struct.pack("<i", 0)             # NLD: 1 linked phrase
        + struct.pack("<i", 1) + action                               # Actions
        + struct.pack("<i", 1) + event                                # Events
        + struct.pack("<i", 1) + struct.pack("<fi", 3.0, 0)           # Tones
        + struct.pack("<i", 1) + struct.pack("<fi", 4.0, 0)           # DNAs
    )
    restored = read_sng(data[:block_start] + block + data[block_end:])
    assert [s.name for s in restored.sections] == [s.name for s in plain.sections]
    assert len(restored.arrangements) == len(plain.arrangements)
    assert restored.metadata.max_difficulty == plain.metadata.max_difficulty
    assert [(e.time, e.code) for e in restored.events] == [(1.25, "E3")]


def test_stage_cues_are_emitted_where_the_reference_puts_them() -> None:
    """Our Events section used to be EMPTY, which leaves the venue inert.

    The placement is read off a DLC Builder build of the user's song and holds
    independently on BOTH its arrangements, whose start/first-note times differ
    (lead 6.421/8.0 → 6.421/8.6/11.1/193.509/202.509; rhythm 5.0/13.421 →
    5.0/14.021/16.521/193.509/202.509). Only the PLACEMENT is reproduced —
    what the codes mean to the game is not documented anywhere we can cite.
    """
    from rockforge.infrastructure.packaging.psarc.sng import _build_events

    assert [(round(e.time, 3), e.code) for e in _build_events(6.421, 8.0, 202.509)] == [
        (6.421, "e2"), (8.6, "E3"), (11.1, "E13"), (193.509, "D3"), (202.509, "E13"),
    ]
    assert [(round(e.time, 3), e.code) for e in _build_events(5.0, 13.421, 202.509)] == [
        (5.0, "e2"), (14.021, "E3"), (16.521, "E13"), (193.509, "D3"), (202.509, "E13"),
    ]
    # A song shorter than the intro+outro leads DROPS the outro cue rather than
    # clamping it to 0, which would put a "nine seconds from the end" cue at the
    # very start. The track must stay chronological either way.
    short = _build_events(0.0, 0.5, 8.0)
    assert [e.code for e in short] == ["e2", "E3", "E13", "E13"]
    assert [e.time for e in short] == sorted(e.time for e in short)
    assert _build_events(0.0, 0.0, 0.0) == []


def test_phrase_names_are_unique_like_a_real_ddc() -> None:
    """A GP with no section markers is auto-segmented into spans all called
    "riff", so the shipped SNG carried 27 phrases sharing ONE name while a real
    DDC emits p0…pN, all distinct, and keeps the descriptive names on the
    SECTIONS (a separate list) instead. This is song-specific — a GP that does
    carry markers already produced varied names — which is why the reported
    Dynamic Difficulty symptom follows the song and not the build.

    The structural names stay: the reference keeps COUNT/END/NOGUITAR verbatim.
    """
    beats = tuple(Beat(time=i * 0.5, measure=i // 4 + 1 if i % 4 == 0 else -1)
                  for i in range(240))
    notes = [TabNote(string=i % 6, fret=(i % 9) + 1, time=2.0 + i * 0.7, sustain=0.2)
             for i in range(90)]
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="S", artist="A", song_length=118.0),
        tuning=Tuning(),
        tempo_map=TempoMap(beats=beats, average_bpm=120.0),
        notes=notes,
        sections=[],  # no markers -> auto-segmented, every span named "riff"
    )
    model = from_arrangement(arr)
    names = [p.name for p in model.phrases]
    assert len(names) > 3, "expected the song to be segmented into several phrases"
    assert len(set(names)) == len(names), f"phrase names must be unique: {names}"
    body = [n for n in names if n not in ("COUNT", "END", "NOGUITAR", "noguitar")]
    assert body == [f"p{i}" for i in range(len(body))], body
    # The SECTIONS keep their descriptive names — that is where they belong.
    assert {s.name for s in model.sections} & {"riff", "COUNT", "END"}


def test_a_phrase_drops_out_of_levels_above_its_own_ceiling() -> None:
    """A real DDC pass makes each phrase VANISH from every level above its own
    ``max_difficulty`` — it does not repeat the saturated content upward.

    Byte-diffing a DLC Builder build of the user's song against ours: its top
    level holds 126 of the song's 623 notes (only the two phrases whose ceiling
    is the song max), while ours held all 623 because ``_level_notes`` clamped
    with ``min(d, pm)`` instead of dropping the phrase. The ramp UP to each
    ceiling was already identical; what differed is that no phrase ever left,
    so every phrase was present at all 23 levels regardless of its declared
    ceiling.
    """
    beats = tuple(Beat(time=round(i * 0.5, 4), measure=i // 4 + 1 if i % 4 == 0 else -1)
                  for i in range(160))
    # Alternating dense/sparse spans, so the phrases get genuinely different
    # ceilings and there is something to drop out.
    notes: list[TabNote] = []
    t, i = 0.0, 0
    while t < 78.0:
        step = 0.125 if (int(t) // 20) % 2 == 0 else 0.5
        notes.append(TabNote(string=i % 6, fret=(i % 12) + 1, time=round(t, 4), sustain=0.1))
        t += step
        i += 1
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="S", artist="A", song_length=80.0),
        tuning=Tuning(),
        tempo_map=TempoMap(beats=beats, average_bpm=120.0),
        notes=notes,
        sections=[Section(name=f"s{k}", start_time=round(k * 8.0, 3)) for k in range(10)],
    )
    model = from_arrangement(arr, dynamic_difficulty=True)
    ceilings = [p.max_difficulty for p in model.phrases]
    assert len(set(ceilings)) > 1, "the fixture must produce differing ceilings"

    for d, level in enumerate(model.arrangements):
        for note in level.notes:
            phrase = model.phrase_iterations[note.phrase_iteration_id].phrase_id
            assert d <= ceilings[phrase], (
                f"level {d} carries a note of phrase {phrase}, whose ceiling is "
                f"{ceilings[phrase]} — a saturated phrase must drop out, not repeat"
            )

    # Each phrase must still reach its FULL content exactly at its own ceiling:
    # dropping out must not eat the top of the ramp.
    top = model.arrangements[-1]
    assert 0 < len(top.notes) < len(notes), (
        "the top level should hold only the phrases whose ceiling is the song max"
    )
    for pi_id, pi in enumerate(model.phrase_iterations):
        ceiling = ceilings[pi.phrase_id]
        counts = [
            sum(1 for n in lvl.notes if n.phrase_iteration_id == pi_id)
            for lvl in model.arrangements
        ]
        if not any(counts):
            continue
        assert counts[ceiling] == max(counts), (
            f"phrase iteration {pi_id} peaks at level {counts.index(max(counts))}, "
            f"not at its ceiling {ceiling}"
        )


def test_tone_changes_reach_the_sng_with_their_slot_and_off_the_note() -> None:
    """The SNG's Tones section used to go out empty, so no tone change happened
    in game from the native PSARC. Each change is written with its slot in
    Tone_A..D (the manifest's order) and nudged off a note, like the XML; a
    change to a tone with no slot has nothing to switch to and is left out."""
    from dataclasses import replace

    from rockforge.domain.arrangement import ToneChange
    from rockforge.infrastructure.packaging.gear.default_tones import default_tone

    clean = default_tone(ArrangementKind.LEAD, "Clean")
    heavy = default_tone(ArrangementKind.RHYTHM, "Heavy")
    arrangement = replace(
        _arrangement(),
        tone_base="Clean",
        tone_names=["Clean", "Heavy", "Ghost"],  # Ghost has no gear definition
        tones=[clean, heavy],
        tone_changes=[
            ToneChange(time=1.0, name="Heavy"),  # exactly on the second note
            ToneChange(time=3.0, name="Ghost"),
            ToneChange(time=6.0, name="Clean"),
        ],
    )
    assert arrangement.switch_slots() == ["Clean", "Heavy"]
    tones = read_sng(write_sng(from_arrangement(arrangement))).tones
    assert [t.tone_id for t in tones] == [1, 0]
    assert abs(tones[0].time - 0.98) < 1e-6  # 20 ms before the note it starts on
    assert abs(tones[1].time - 6.0) < 1e-6


def test_an_arrangement_without_tones_has_no_tone_changes() -> None:
    assert read_sng(write_sng(from_arrangement(_arrangement()))).tones == []


def _resting_track() -> Arrangement:
    """A track that only plays in the chorus: silent through the intro and verse,
    stopping before the outro — the shape of a rhythm that enters late."""
    beats = tuple(
        Beat(time=i * 0.5, measure=(i // 4 + 1) if i % 4 == 0 else -1) for i in range(101)
    )
    notes = [TabNote(string=1, fret=2, time=20.0 + i * 0.5, sustain=0.2) for i in range(20)]
    return Arrangement(
        kind=ArrangementKind.RHYTHM,
        metadata=SongMetadata(title="Song", artist="Artist", song_length=50.0),
        tuning=Tuning(),
        tempo_map=TempoMap(beats=beats, average_bpm=120.0),
        notes=notes,
        sections=[
            Section(name="Intro", start_time=0.0),
            Section(name="Verse", start_time=10.0),
            Section(name="Chorus", start_time=20.0),
            Section(name="Outro", start_time=40.0),
        ],
    )


def test_a_track_that_enters_late_keeps_its_sections_in_order() -> None:
    """September froze in game on every chart but the one that plays from the
    first section: the COUNT split moved "Intro" to the chart's first note, i.e.
    AFTER "Verse", so the section list ran backwards (Intro at the chorus, its
    phrase range 15→0). Phrases now come from DLC Builder's generator: COUNT
    from the first beat to the first note, every section in time order with a
    sane phrase range, and an END phrase last."""
    model = read_sng(write_sng(from_arrangement(_resting_track())))
    starts = [s.start_time for s in model.sections]
    assert starts == sorted(starts)
    for s in model.sections:
        assert s.start_phrase_iteration_id <= s.end_phrase_iteration_id
    pis = [pi.start_time for pi in model.phrase_iterations]
    assert pis == sorted(pis)
    names = [model.phrases[pi.phrase_id].name for pi in model.phrase_iterations]
    assert names[0] == "COUNT" and names[-1] == "END"
    # The COUNT runs up to the chart's first note, not into it.
    assert model.phrase_iterations[1].start_time == pytest.approx(20.0)


def _thinning_track() -> Arrangement:
    """A short fret-1 phrase, then a long fret-2/4 one: the full chart frames
    them in one fret-1 window, while the levels above the short phrase's
    ceiling hold only the long one — framed from fret 2."""
    beats = tuple(
        Beat(time=i * 0.5, measure=(i // 4 + 1) if i % 4 == 0 else -1) for i in range(101)
    )
    short = [TabNote(string=1, fret=1, time=10.0 + i, sustain=0.2) for i in range(4)]
    long = [
        TabNote(string=2, fret=2 if i % 2 else 4, time=20.0 + i * 0.5, sustain=0.2)
        for i in range(30)
    ]
    return Arrangement(
        kind=ArrangementKind.RHYTHM,
        metadata=SongMetadata(title="Song", artist="Artist", song_length=50.0),
        tuning=Tuning(),
        tempo_map=TempoMap(beats=beats, average_bpm=120.0),
        notes=short + long,
        sections=[
            Section(name="Intro", start_time=0.0),
            Section(name="Verse", start_time=10.0),
            Section(name="Chorus", start_time=20.0),
            Section(name="Outro", start_time=40.0),
        ],
    )


def test_a_notes_anchor_is_the_one_of_its_own_level() -> None:
    """September's Alternate Rhythm crashed the game the moment its difficulty
    was raised: from level 17 up its levels were framed from fret 2, but every
    note still carried the full chart's fret-1 anchor. DLC Builder takes a
    note's anchor from ITS level (XmlToSngNote's `findAnchor ... level.Anchors`)
    and each anchor's first/last note time from the notes inside it."""
    model = read_sng(write_sng(from_arrangement(_thinning_track())))
    frets = {a.fret for lv in model.arrangements for a in lv.anchors}
    assert frets == {1, 2}  # the shape that used to disagree is really there
    for lv in model.arrangements:
        starts = [a.start_time for a in lv.anchors]
        for n in lv.notes:
            a = lv.anchors[max(0, bisect.bisect_right(starts, n.time) - 1)]
            assert (n.anchor_fret, n.anchor_width) == (a.fret, a.width)
        for a in lv.anchors:
            inside = [n for n in lv.notes if a.start_time <= n.time < a.end_time]
            if not inside:
                assert a.first_note_time == pytest.approx(3.4028234663852886e38, rel=1e-6)
                continue
            assert a.first_note_time == pytest.approx(inside[0].time)
            assert a.last_note_time == pytest.approx(inside[-1].time + inside[-1].sustain)


def test_the_phrases_follow_dlc_builders_generator() -> None:
    """The native SNG's phrases are DLC Builder's (PhraseGenerator.fs), the
    structure of its September build that plays where ours crashed: COUNT from
    the first beat to the first note, a phrase every 8 bars moved out of any
    sustained single note and never within 2 s of the previous one, one
    NOGUITAR phrase for every gap of 2.5 s or more (its section "noguitar"),
    END at the last beat; sections "riff"/"noguitar" only. On the user's
    September the four charts come out identical to that build."""
    notes = [TabNote(string=0, fret=3, time=2.0 + i, sustain=0.2) for i in range(7)]
    notes.append(TabNote(string=1, fret=5, time=9.5, sustain=1.0))  # rings over bar 10
    notes += [TabNote(string=2, fret=2, time=20.0 + i, sustain=0.2) for i in range(6)]
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="S", artist="A", song_length=40.0),
        tuning=Tuning(),
        tempo_map=TempoMap(beats=_bars(40), average_bpm=60.0),
        notes=notes,
        sections=[Section(name="Verse 1", start_time=0.0), Section(name="Chorus", start_time=5.0)],
    )
    model = from_arrangement(arr)
    got = [(round(pi.start_time, 2), model.phrases[pi.phrase_id].name)
           for pi in model.phrase_iterations]
    # 10.0 is inside the 9.5 note's sustain: moved to its end, 10.5. The next
    # note is 9.5 s later, so that phrase is a gap; the playing resumes at 20.
    assert got == [(0.0, "COUNT"), (2.0, "p0"), (10.5, "NOGUITAR"), (20.0, "p1"),
                   (28.0, "NOGUITAR"), (36.0, "NOGUITAR"), (39.0, "END")]
    assert [s.name for s in model.sections] == [
        "riff", "noguitar", "riff", "noguitar", "noguitar", "noguitar"]
    assert model.phrases[model.phrase_iterations[2].phrase_id].max_difficulty == 0
    assert len({pi.phrase_id for pi in model.phrase_iterations
                if model.phrases[pi.phrase_id].name == "NOGUITAR"}) == 1


def test_a_phrase_is_not_cut_through_a_hand_shape() -> None:
    """DLC Builder's generator moves a phrase out of a hand shape as well as a
    sustain (``findGoodPhraseTime``); with hand shapes in our XML its build
    would, so the native SNG does too. The phrase due at 10 s falls inside a
    run of one chord (8.0-10.5 s) and moves to the run's end."""
    notes = [TabNote(string=0, fret=3, time=2.0 + i, sustain=0.2) for i in range(6)]
    for i in range(6):
        t = 8.0 + i * 0.5
        notes += [TabNote(string=0, fret=3, time=t, sustain=0.0),
                  TabNote(string=1, fret=5, time=t, sustain=0.0)]
    notes += [TabNote(string=2, fret=2, time=12.0 + i, sustain=0.2) for i in range(10)]
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="S", artist="A", song_length=30.0),
        tuning=Tuning(),
        tempo_map=TempoMap(beats=_bars(30), average_bpm=60.0),
        notes=notes,
    )
    model = from_arrangement(arr)
    starts = [round(pi.start_time, 3) for pi in model.phrase_iterations]
    assert starts[:3] == [0.0, 2.0, 10.501]


def test_a_one_note_phrase_has_levels_and_its_note_on_each() -> None:
    """September crashed the moment the difficulty was raised on a phrase that
    held one note (the Lead's at 43.6 s, the Alternate Rhythm's pickup before
    the chorus): its ceiling was 0 — a phrase with notes and no level to climb,
    which DLC Builder never writes. Its build of the same song gives a one-note
    phrase six identical levels, and every phrase with notes a ceiling of 3 or
    more. Every phrase with notes now gets the floor, its notes at every level
    up to it (never an empty level below the ceiling)."""
    arr = _resting_track()
    lone = TabNote(string=2, fret=3, time=12.0, sustain=0.5)  # alone in "Verse"
    model = from_arrangement(replace(arr, notes=[lone, *arr.notes]))
    for i, pi in enumerate(model.phrase_iterations):
        counts = [sum(1 for n in lv.notes if n.phrase_iteration_id == i)
                  for lv in model.arrangements]
        ceiling = model.phrases[pi.phrase_id].max_difficulty
        if any(counts):
            assert ceiling >= 4, f"a phrase with notes at {pi.start_time} has ceiling {ceiling}"
            assert all(c > 0 for c in counts[: ceiling + 1])
    verse = next(i for i, pi in enumerate(model.phrase_iterations)
                 if pi.start_time <= 12.0 < pi.end_time)
    assert model.phrases[model.phrase_iterations[verse].phrase_id].max_difficulty >= 4


def test_riffs_that_differ_by_a_technique_or_a_sustain_are_not_linked() -> None:
    """Linked iterations are ONE phrase to the game, so they must be equal at
    every level. September shipped "identical" passages where one had a
    pull-off (or a let-ring sustain) the other lacked: the signature only knew
    time/string/fret. Now each linked phrase's iterations carry the same notes
    at every level."""
    riff = [(0, 3), (1, 5), (2, 7), (0, 3)]
    notes = []
    for base in (1.0, 9.0, 17.0):
        notes += [TabNote(string=s, fret=f, time=base + j * 0.5, sustain=0.2)
                  for j, (s, f) in enumerate(riff)]
    notes[5] = replace(notes[5], techniques=frozenset({Technique.PULL_OFF}))  # 2nd pass
    notes[8] = replace(notes[8], sustain=0.4)  # 3rd pass, first note rings longer
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="S", artist="A", song_length=30.0),
        tuning=Tuning(),
        tempo_map=TempoMap(beats=_bars(30), average_bpm=60.0),
        notes=notes,
    )
    model = from_arrangement(arr)
    ids = {round(pi.start_time): pi.phrase_id for pi in model.phrase_iterations}
    assert len({ids[1], ids[9], ids[17]}) == 3
    by_phrase: dict[int, list[int]] = {}
    for i, pi in enumerate(model.phrase_iterations):
        by_phrase.setdefault(pi.phrase_id, []).append(i)
    for its in by_phrase.values():
        for lv in model.arrangements:
            shapes = [
                [(round(n.time - model.phrase_iterations[i].start_time, 3), n.string,
                  n.fret, n.mask, round(n.sustain, 3))
                 for n in lv.notes if n.phrase_iteration_id == i]
                for i in its
            ]
            assert all(sh == shapes[0] for sh in shapes)


def test_note_bytes_that_a_note_does_not_use_are_minus_one() -> None:
    """DLC Builder writes -1 (none) in Tap/Slap/Pluck of every note, and in
    LeftHand/PickDirection of every chord; we wrote 0, a real value for each."""
    arr = _resting_track()
    chord = [TabNote(string=s, fret=2, time=30.25, sustain=0.2) for s in (0, 1, 2)]
    model = read_sng(write_sng(from_arrangement(replace(arr, notes=[*arr.notes, *chord]))))
    notes = [n for lv in model.arrangements for n in lv.notes]
    assert all((n.tap, n.slap, n.pluck) == (-1, -1, -1) for n in notes)
    chords = [n for n in notes if n.chord_id >= 0]
    assert chords and all((n.left_hand, n.pick_direction) == (-1, -1) for n in chords)
    assert all(n.pick_direction == 0 for n in notes if n.chord_id < 0)
