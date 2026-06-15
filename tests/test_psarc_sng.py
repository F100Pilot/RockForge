from rockforge.domain.arrangement import Arrangement, ArrangementKind, Section, SongMetadata
from rockforge.domain.music import Beat, TabNote, Technique, TempoMap, Tuning
from rockforge.infrastructure.packaging.psarc.sng import (
    TECHNIQUE_BITS,
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

    assert restored.beats == model.beats
    assert restored.phrases == model.phrases
    assert restored.phrase_iterations == model.phrase_iterations
    assert restored.sections == model.sections
    assert restored.notes == model.notes
    assert restored.vocals == model.vocals
    assert restored.metadata == model.metadata


def test_note_mask_encodes_techniques() -> None:
    arrangement = _arrangement()
    model = from_arrangement(arrangement)
    assert model.notes[0].mask & TECHNIQUE_BITS[Technique.HAMMER_ON]
    assert model.notes[1].bend == 1.5


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
