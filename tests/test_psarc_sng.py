from rockforge.domain.arrangement import Arrangement, ArrangementKind, Section, SongMetadata
from rockforge.domain.music import Beat, TabNote, Technique, TempoMap, Tuning
from rockforge.infrastructure.packaging.psarc.sng import (
    NOTE_MASK_BEND,
    NOTE_MASK_CHORD,
    NOTE_MASK_CHORDNOTES,
    NOTE_MASK_DOUBLESTOP,
    NOTE_MASK_HAMMERON,
    NOTE_MASK_OPEN,
    NOTE_MASK_SINGLE,
    NOTE_MASK_STRUM,
    NOTE_MASK_SUSTAIN,
    TECHNIQUE_BITS,
    TECHNIQUE_TO_MASK,
    from_arrangement,
    read_sng,
    write_sng,
)
from rockforge.infrastructure.rsxml.vocals import VocalEvent


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

    assert len(restored.arrangements) == 1
    level = restored.arrangements[0]
    orig_level = model.arrangements[0]
    assert len(level.notes) == len(orig_level.notes)
    assert len(level.anchors) == len(orig_level.anchors)

    assert restored.metadata.capo_fret == 2
    assert restored.metadata.song_length == 10.0


def test_note_mask_uses_real_rocksmith_values() -> None:
    arrangement = _arrangement()
    model = from_arrangement(arrangement)
    notes = model.arrangements[0].notes
    # First note: hammer-on, fret 2, sustain 0.5 → SINGLE | HAMMERON | SUSTAIN
    assert notes[0].mask & NOTE_MASK_HAMMERON
    assert notes[0].mask & NOTE_MASK_SINGLE
    assert notes[0].mask & NOTE_MASK_SUSTAIN
    assert not (notes[0].mask & NOTE_MASK_CHORD)
    # Second note: open string (fret 0), bend
    assert notes[1].mask & NOTE_MASK_BEND
    assert notes[1].mask & NOTE_MASK_OPEN
    assert notes[1].bend == 1.5


def test_technique_bits_alias_matches_technique_to_mask() -> None:
    assert TECHNIQUE_BITS is TECHNIQUE_TO_MASK


def test_section_end_times_use_next_section_or_song_length() -> None:
    arrangement = _arrangement()
    model = from_arrangement(arrangement)
    assert model.sections[0].end_time == 5.0
    assert model.sections[1].end_time == 10.0


def test_metadata_reflects_capo_and_tuning() -> None:
    arrangement = _arrangement()
    model = from_arrangement(arrangement)
    assert model.metadata.capo_fret == 2
    assert model.metadata.song_length == 10.0
    assert model.metadata.tuning == (0, 0, 0, 0, 0, 0)


def test_anchors_generated_from_notes() -> None:
    arrangement = _arrangement()
    model = from_arrangement(arrangement)
    level = model.arrangements[0]
    assert len(level.anchors) >= 1
    assert level.anchors[0].fret >= 1
    assert level.anchors[0].width >= 4


def test_chords_produce_templates_and_fingerprints() -> None:
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
            TabNote(string=2, fret=2, time=0.0, sustain=0.5),
        ],
        sections=[Section(name="riff", start_time=0.0)],
    )
    model = from_arrangement(arr)
    assert len(model.chord_templates) == 1
    assert model.chord_templates[0].frets[:3] == (2, 2, 2)

    level = model.arrangements[0]
    assert len(level.fingerprints1) == 1
    assert level.fingerprints1[0].chord_id == 0

    # The note entry should be a chord
    chord_note = level.notes[0]
    assert chord_note.mask & NOTE_MASK_CHORD
    assert chord_note.mask & NOTE_MASK_STRUM
    assert chord_note.chord_id == 0


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
    level = model.arrangements[0]
    assert level.notes[0].mask & NOTE_MASK_DOUBLESTOP


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
    assert model.chord_notes[0].note_mask[0] != 0  # string 0 has bend

    level = model.arrangements[0]
    chord_note = level.notes[0]
    assert chord_note.chord_notes_id == 0
    assert chord_note.mask & NOTE_MASK_CHORDNOTES


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
    notes = model.arrangements[0].notes
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
    assert len(restored.arrangements) == 1
    assert restored.metadata.song_length == 5.0


def test_arrangement_level_has_phrase_counts() -> None:
    arrangement = _arrangement()
    model = from_arrangement(arrangement)
    level = model.arrangements[0]
    assert level.phrase_count == len(model.phrases)
    assert len(level.avg_notes_per_iteration) == level.phrase_count
    assert len(level.notes_in_iteration1) == len(model.phrase_iterations)
