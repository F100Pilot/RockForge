import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from rockforge.domain.arrangement import Arrangement, ArrangementKind, SongMetadata
from rockforge.domain.music import Beat, TabNote, Technique, TempoMap, Tuning
from rockforge.infrastructure.rsxml.writer import _fmt, write_arrangement_xml


def make_arrangement() -> Arrangement:
    beats = tuple(Beat(time=0.5 * i, measure=(i // 4 + 1) if i % 4 == 0 else -1) for i in range(40))
    return Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="Test Song", artist="Tester", song_length=20.0),
        tuning=Tuning(),
        tempo_map=TempoMap(beats=beats, average_bpm=120.0),
        notes=[
            TabNote(string=0, fret=3, time=1.0, sustain=0.5),
            TabNote(
                string=2, fret=7, time=2.0, sustain=0.25,
                techniques=frozenset({Technique.BEND}), bend_semitones=2.0,
            ),
            TabNote(string=4, fret=5, time=3.0, sustain=0.1,
                    techniques=frozenset({Technique.HAMMER_ON})),
        ],
    )


def test_writes_valid_xml(tmp_path: Path) -> None:
    out = write_arrangement_xml(make_arrangement(), tmp_path / "lead.xml")
    root = ET.parse(out).getroot()
    assert root.tag == "song" and root.get("version") == "8"
    assert root.findtext("title") == "Test Song"
    assert root.findtext("arrangement") == "Lead"


def test_offset_matches_negated_start_beat(tmp_path: Path) -> None:
    """offset = -startBeat, so DLC Builder/EOF preserve a sync lead-in instead
    of re-zeroing all times on import (which discarded the lead-in silence)."""
    arr = make_arrangement()
    lead_in = 3.0
    arr.tempo_map = TempoMap(
        beats=tuple(Beat(time=b.time + lead_in, measure=b.measure) for b in arr.tempo_map.beats),
        average_bpm=arr.tempo_map.average_bpm,
    )
    arr.notes = [
        TabNote(string=n.string, fret=n.fret, time=n.time + lead_in, sustain=n.sustain,
                techniques=n.techniques, bend_semitones=n.bend_semitones)
        for n in arr.notes
    ]
    out = write_arrangement_xml(arr, tmp_path / "lead.xml")
    root = ET.parse(out).getroot()
    assert root.findtext("startBeat") == _fmt(lead_in)
    assert root.findtext("offset") == _fmt(-lead_in)


def test_structure_matches_song2014_documented_elements(tmp_path: Path) -> None:
    out = write_arrangement_xml(make_arrangement(), tmp_path / "lead.xml")
    root = ET.parse(out).getroot()
    for el in ["tuning", "ebeats", "phrases", "phraseIterations", "sections",
               "chordTemplates", "levels"]:
        assert root.find(el) is not None, f"missing element {el}"
    ebeats = root.find("ebeats")
    assert ebeats is not None and int(ebeats.get("count", "0")) == 40
    notes = root.find("levels/level/notes")
    assert notes is not None and len(notes) == 3


def test_note_attributes(tmp_path: Path) -> None:
    out = write_arrangement_xml(make_arrangement(), tmp_path / "lead.xml")
    notes = ET.parse(out).getroot().findall("levels/level/notes/note")
    bend_note = notes[1]
    assert bend_note.get("bend") == "2"
    assert bend_note.get("string") == "2" and bend_note.get("fret") == "7"
    assert notes[2].get("hammerOn") == "1"
    assert notes[0].get("hammerOn") == "0"


def test_standard_tuning_attributes(tmp_path: Path) -> None:
    out = write_arrangement_xml(make_arrangement(), tmp_path / "lead.xml")
    tuning = ET.parse(out).getroot().find("tuning")
    assert tuning is not None
    assert all(tuning.get(f"string{i}") == "0" for i in range(6))


def test_anchors_follow_fret_position(tmp_path: Path) -> None:
    """The fretboard highlight must move with the played frets, not stay fixed
    at the first note's position (see make_arrangement: notes at frets 3,7,5)."""
    out = write_arrangement_xml(make_arrangement(), tmp_path / "lead.xml")
    anchors = ET.parse(out).getroot().findall("levels/level/anchors/anchor")
    assert len(anchors) > 1
    for a in anchors:
        fret, width = int(a.get("fret", "0")), int(float(a.get("width", "0")))
        assert fret >= 1 and fret + width - 1 <= 24
    times = [float(a.get("time", "0")) for a in anchors]
    assert times == sorted(times)


def make_chord_arrangement() -> Arrangement:
    arr = make_arrangement()
    arr.notes = [
        # E5 power chord (simultaneous) + one single note after
        TabNote(string=0, fret=0, time=1.0, sustain=0.5),
        TabNote(string=1, fret=2, time=1.0, sustain=0.5),
        TabNote(string=2, fret=2, time=1.01, sustain=0.5),
        TabNote(string=0, fret=0, time=2.0, sustain=0.5),
        TabNote(string=1, fret=2, time=2.0, sustain=0.5),
        TabNote(string=2, fret=2, time=2.0, sustain=0.5),
        TabNote(string=5, fret=12, time=3.0, sustain=0.3),
    ]
    return arr


def test_simultaneous_notes_become_chords_with_templates(tmp_path: Path) -> None:
    out = write_arrangement_xml(make_chord_arrangement(), tmp_path / "c.xml")
    root = ET.parse(out).getroot()
    templates = root.findall("chordTemplates/chordTemplate")
    assert len(templates) == 1  # same shape twice -> one deduplicated template
    t = templates[0]
    assert [t.get(f"fret{i}") for i in range(6)] == ["0", "2", "2", "-1", "-1", "-1"]
    chords = root.findall("levels/level/chords/chord")
    assert len(chords) == 2
    assert all(c.get("chordId") == "0" for c in chords)
    assert len(chords[0].findall("chordNote")) == 3
    # the lone melody note stays a plain note
    notes = root.findall("levels/level/notes/note")
    assert len(notes) == 1 and notes[0].get("fret") == "12"


def test_chord_counts_are_consistent(tmp_path: Path) -> None:
    out = write_arrangement_xml(make_chord_arrangement(), tmp_path / "c.xml")
    root = ET.parse(out).getroot()
    notes_el = root.find("levels/level/notes")
    chords_el = root.find("levels/level/chords")
    assert notes_el is not None and notes_el.get("count") == "1"
    assert chords_el is not None and chords_el.get("count") == "2"


# Every attribute ArrangementProperties.ReadXml (Rocksmith2014.XML, used by
# DLC Builder) dereferences without a null check — all must be present or
# import fails with "Object reference not set to an instance of an object".
DLC_BUILDER_REQUIRED_ARRPROP_ATTRS = [
    "represent", "bonusArr", "standardTuning", "nonStandardChords",
    "barreChords", "powerChords", "dropDPower", "openChords", "fingerPicking",
    "pickDirection", "doubleStops", "palmMutes", "harmonics", "pinchHarmonics",
    "hopo", "tremolo", "slides", "unpitchedSlides", "bends", "tapping",
    "vibrato", "fretHandMutes", "slapPop", "twoFingerPicking",
    "fifthsAndOctaves", "syncopation", "bassPick", "sustain",
    "pathLead", "pathRhythm", "pathBass",
]


def test_arrangement_properties_has_all_dlc_builder_attributes(tmp_path: Path) -> None:
    out = write_arrangement_xml(make_arrangement(), tmp_path / "lead.xml")
    props = ET.parse(out).getroot().find("arrangementProperties")
    assert props is not None
    for attr in DLC_BUILDER_REQUIRED_ARRPROP_ATTRS:
        assert props.get(attr) in {"0", "1"}, f"missing/invalid attribute {attr}"
    assert props.get("pathLead") == "1" and props.get("pathRhythm") == "0"
    # technique flags derived from the actual notes
    assert props.get("bends") == "1" and props.get("hopo") == "1"
    assert props.get("tapping") == "0"


def test_phrase_structure_marks_song_end(tmp_path: Path) -> None:
    """Rocksmith ends the song at the last phraseIteration: COUNT/default/END
    must exist with END placed after the last note, else the game finishes
    seconds in with the note highway frozen."""
    out = write_arrangement_xml(make_arrangement(), tmp_path / "lead.xml")
    root = ET.parse(out).getroot()
    names = [p.get("name") for p in root.findall("phrases/phrase")]
    assert names == ["COUNT", "default", "END"]
    iters = root.findall("phraseIterations/phraseIteration")
    assert [i.get("phraseId") for i in iters] == ["0", "1", "2"]
    times = [float(i.get("time", "0")) for i in iters]
    assert times == sorted(times)
    last_note_end = max(
        float(n.get("time", "0")) + float(n.get("sustain", "0"))
        for n in root.findall("levels/level/notes/note")
    )
    assert times[-1] > last_note_end
    # sections close with the conventional "noguitar" at the END time
    sections = root.findall("sections/section")
    assert sections and sections[-1].get("name") == "noguitar"
    assert float(sections[-1].get("startTime", "0")) == times[-1]


def test_rejects_invalid_arrangement(tmp_path: Path) -> None:
    arr = make_arrangement()
    arr.notes = []
    with pytest.raises(ValueError, match="no notes"):
        write_arrangement_xml(arr, tmp_path / "bad.xml")
