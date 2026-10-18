import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from rockforge.domain.arrangement import (
    Arrangement,
    ArrangementKind,
    SongMetadata,
    ToneChange,
)
from rockforge.domain.music import Beat, BendPoint, TabNote, Technique, TempoMap, Tuning
from rockforge.infrastructure.rsxml.writer import (
    _fmt,
    _safe_tone_time,
    render_arrangement,
    write_arrangement_xml,
)


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
    # The bend flag alone is only the peak; DLC Builder reads the actual pitch
    # from <bendValues>. Without it the bend disappears on import. A simple bend
    # is a single point reaching its peak at the note's end (a visible bend-up).
    bvs = bend_note.find("bendValues")
    assert bvs is not None and len(bvs) == 1
    assert bvs[0].get("step") == "2.000" and float(bvs[0].get("time")) > 2.0
    # A plain note carries no bend curve.
    assert notes[0].find("bendValues") is None
    assert notes[2].get("hammerOn") == "1"
    # default-valued attributes are omitted (Editor on Fire convention) so a
    # plain note never carries a spurious technique flag on the highway
    assert notes[0].get("hammerOn") is None


def test_mute_slide_unpitch_and_multipoint_bend(tmp_path: Path) -> None:
    beats = tuple(Beat(time=0.5 * i, measure=1 if i == 0 else -1) for i in range(20))
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="S", artist="A", song_length=10.0),
        tuning=Tuning(),
        tempo_map=TempoMap(beats=beats, average_bpm=120.0),
        notes=[
            TabNote(string=0, fret=5, time=1.0, sustain=0.4,
                    techniques=frozenset({Technique.FRET_MUTE})),
            TabNote(string=1, fret=9, time=2.0, sustain=0.4, slide_unpitch_to=4),
            TabNote(string=2, fret=7, time=3.0, sustain=0.4, bend_semitones=1.0,
                    techniques=frozenset({Technique.BEND}),
                    bend_points=(BendPoint(0.0, 0.0), BendPoint(0.5, 1.0),
                                 BendPoint(1.0, 0.0))),
        ],
    )
    root = ET.parse(write_arrangement_xml(arr, tmp_path / "lead.xml")).getroot()
    notes = root.findall("levels/level/notes/note")
    by_string = {int(n.get("string")): n for n in notes}
    assert by_string[0].get("mute") == "1"
    assert by_string[1].get("slideUnpitchTo") == "4"
    curve = by_string[2].find("bendValues")
    assert curve is not None and len(curve) == 3  # bend-and-release, full curve
    props = root.find("arrangementProperties")
    assert props.get("fretHandMutes") == "1"
    assert props.get("unpitchedSlides") == "1"


def test_pinch_tremolo_finger_and_pick_direction(tmp_path: Path) -> None:
    beats = tuple(Beat(time=0.5 * i, measure=1 if i == 0 else -1) for i in range(20))
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
    root = ET.parse(write_arrangement_xml(arr, tmp_path / "lead.xml")).getroot()
    by_string = {int(n.get("string")): n for n in root.findall("levels/level/notes/note")}
    assert by_string[0].get("harmonicPinch") == "1"
    assert by_string[1].get("tremolo") == "1"
    assert by_string[2].get("leftHand") == "2" and by_string[2].get("pickDirection") == "1"
    props = root.find("arrangementProperties")
    assert props.get("pinchHarmonics") == "1"
    assert props.get("tremolo") == "1"
    assert props.get("pickDirection") == "1"


def test_plain_note_emits_only_minimal_attributes(tmp_path: Path) -> None:
    # Regression: a clean sustained note must serialize exactly like Editor on
    # Fire's (time/string/fret/sustain only). Emitting palmMute="0", tap="0",
    # slap="0", pluck="0" etc. made Rocksmith draw a spurious technique glyph
    # inside the note box instead of a plain filled rectangle.
    out = write_arrangement_xml(make_arrangement(), tmp_path / "lead.xml")
    plain = ET.parse(out).getroot().findall("levels/level/notes/note")[0]
    assert set(plain.attrib) == {"time", "string", "fret", "sustain"}


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


def test_chord_element_mirrors_palm_mute_of_its_notes(tmp_path: Path) -> None:
    # The game reads palm mute from the <chord> element; if its chordNotes say
    # palmMute=1 but the chord says 0, the highway sprite renders corrupt.
    arr = make_arrangement()
    pm = frozenset({Technique.PALM_MUTE})
    arr.notes = [
        TabNote(string=0, fret=0, time=1.0, sustain=0.5, techniques=pm),
        TabNote(string=1, fret=2, time=1.0, sustain=0.5, techniques=pm),
        TabNote(string=0, fret=3, time=2.0, sustain=0.5),  # plain chord
        TabNote(string=1, fret=5, time=2.0, sustain=0.5),
    ]
    out = write_arrangement_xml(arr, tmp_path / "pm.xml")
    chords = ET.parse(out).getroot().findall("levels/level/chords/chord")
    assert len(chords) == 2
    pm_chord, plain_chord = chords
    assert pm_chord.get("palmMute") == "1"
    assert all(cn.get("palmMute") == "1" for cn in pm_chord.findall("chordNote"))
    # the plain chord omits palmMute entirely (default 0) rather than emitting
    # ="0", which would otherwise trigger the wrong highway sprite
    assert plain_chord.get("palmMute") is None
    assert all(cn.get("palmMute") is None for cn in plain_chord.findall("chordNote"))


def test_repeated_chords_get_high_density(tmp_path: Path) -> None:
    # A fast repeated chord run condenses via highDensity="1" (first hit keeps a
    # full box); emitting them all as full boxes stacks into a corrupt sprite.
    arr = make_arrangement()
    arr.notes = [
        TabNote(string=s, fret=3, time=t, sustain=0.1)
        for t in (1.0, 1.15, 1.30, 1.45)
        for s in (0, 1, 2)
    ]
    out = write_arrangement_xml(arr, tmp_path / "hd.xml")
    chords = ET.parse(out).getroot().findall("levels/level/chords/chord")
    assert len(chords) == 4
    # The first is low density (attribute omitted, default 0); the repeats set 1.
    assert chords[0].get("highDensity") is None
    assert all(c.get("highDensity") == "1" for c in chords[1:])


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


def test_tone_change_never_lands_on_a_note(tmp_path: Path) -> None:
    """DLC Builder errors on a tone change coinciding with a note. The writer
    nudges it just before the note it starts on, after the previous note."""
    arr = make_arrangement()  # notes at 1.0, 2.0, 3.0
    arr.tone_names = ["dist"]
    arr.tone_changes = [ToneChange(time=2.0, name="dist")]  # exactly on the 2.0 note
    out = write_arrangement_xml(arr, tmp_path / "lead.xml")
    tone = ET.parse(out).getroot().find("tones/tone")
    assert tone is not None and tone.get("name") == "dist"
    t = float(tone.get("time", "0"))
    assert t not in {1.0, 2.0, 3.0}  # never exactly on a note
    assert 1.0 < t < 2.0  # immediately before its note, after the previous one


def test_safe_tone_time_uses_gap_then_midpoint() -> None:
    # comfortable gap before the target note
    assert _safe_tone_time(2.0, [1.0, 2.0, 3.0]) == pytest.approx(1.98)
    # previous note too close for the 20 ms gap → sit halfway between them
    assert _safe_tone_time(2.0, [1.99, 2.0]) == pytest.approx(1.995)
    # first note (no previous) still nudges before it, never negative
    assert _safe_tone_time(1.0, [1.0, 2.0]) == pytest.approx(0.98)
    assert _safe_tone_time(0.01, [0.01, 1.0]) >= 0.0
    # a time that isn't on any note is left untouched (e.g. a silent arrangement
    # there) — no dragging it to a far note
    assert _safe_tone_time(1.5, [1.0, 2.0]) == pytest.approx(1.5)


def test_album_art_urn_is_written_when_the_caller_knows_the_song_key() -> None:
    """``<albumArt>`` was always empty. It is completeness for the DLC Builder
    path only: the game resolves the in-game cover through the MANIFEST's
    AlbumArt attribute, and the instrumental XML is not even shipped inside the
    .psarc (only the showlights one is). Empty when no key is supplied, exactly
    as before."""
    arr = make_arrangement()
    assert render_arrangement(arr).findtext("albumArt") == ""
    urn = "urn:image:dds:album_artistsong"
    assert render_arrangement(arr, urn).findtext("albumArt") == urn


def test_chords_carry_fingers_a_name_and_a_hand_shape() -> None:
    """DLC Builder turns <handShape> into the SNG fingerprints the game draws
    a chord's fingers from; the template carries the fingers and the name."""
    beats = tuple(Beat(time=0.5 * i, measure=(i // 4 + 1) if i % 4 == 0 else -1) for i in range(20))
    power = [(0, 3), (1, 5), (2, 5)]
    notes = [
        TabNote(string=s, fret=f, time=t, sustain=0.0)
        for t in (1.0, 1.5, 2.0) for s, f in power
    ] + [TabNote(string=3, fret=7, time=3.0, sustain=0.2)]
    arr = Arrangement(
        kind=ArrangementKind.RHYTHM,
        metadata=SongMetadata(title="T", artist="A", song_length=10.0),
        tuning=Tuning(),
        tempo_map=TempoMap(beats=beats, average_bpm=120.0),
        notes=notes,
    )
    song = render_arrangement(arr)
    template = song.find("chordTemplates/chordTemplate")
    assert template is not None
    assert template.get("chordName") == "G5" == template.get("displayName")
    assert [template.get(f"finger{i}") for i in range(6)] == ["1", "3", "4", "-1", "-1", "-1"]
    shapes = song.findall("levels/level/handShapes/handShape")
    assert len(shapes) == 1  # three identical chords, one hand shape
    assert shapes[0].attrib == {"chordId": "0", "startTime": "1.000", "endTime": "2.001"}
    assert song.find("levels/level/handShapes").get("count") == "1"


def test_a_half_step_bend_and_a_muted_chord_say_so_in_the_xml() -> None:
    """int(round(0.5)) made a half-step bend "0", which dropped the attribute;
    a chord whose every string is fret-hand muted said fretHandMute="0"."""
    beats = tuple(Beat(time=0.5 * i, measure=(i // 4 + 1) if i % 4 == 0 else -1) for i in range(20))
    mute = frozenset({Technique.FRET_MUTE})
    notes = [TabNote(string=2, fret=7, time=1.0, sustain=0.4, bend_semitones=0.5,
                     techniques=frozenset({Technique.BEND})),
             *(TabNote(string=s, fret=0, time=2.0, sustain=0.0, techniques=mute)
               for s in (0, 1, 2))]
    song = render_arrangement(Arrangement(
        kind=ArrangementKind.RHYTHM,
        metadata=SongMetadata(title="T", artist="A", song_length=10.0),
        tuning=Tuning(), tempo_map=TempoMap(beats=beats, average_bpm=120.0), notes=notes))
    note = song.find("levels/level/notes/note")
    assert note is not None and note.get("bend") == "0.5"
    chord = song.find("levels/level/chords/chord")
    assert chord is not None and chord.get("fretHandMute") == "1"
