"""A capo in the Guitar Pro file reaches the chart (a user's report: "It
doesn't understand the capo").

Guitar Pro counts a note's fret from the capo (alphaTab: the string's pitch
includes ``staff.capo``); Rocksmith counts it from the nut, plays an open
string at the capo (Rocksmith2014.NET ``Midi.toMidiNote``) and carries the capo
fret in the arrangement (XML ``<capo>``, SNG ``CapoFret``, manifest).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import guitarpro as gp

from rockforge.domain.arrangement import Arrangement, ArrangementKind, SongMetadata
from rockforge.domain.chords import chord_display
from rockforge.domain.music import Beat, TabNote, TempoMap, Tuning
from rockforge.infrastructure.gpimport.parser import parse_gp_track
from rockforge.infrastructure.packaging.psarc import sng
from rockforge.infrastructure.packaging.psarc.verify import check_sng
from rockforge.infrastructure.rsxml.writer import render_arrangement


def _gp5_with_capo(path: Path, capo: int, frets: list[tuple[int, int]]) -> Path:
    song = gp.Song()
    song.tempo = 120
    track = song.tracks[0]
    track.offset = capo
    voice = track.measures[0].voices[0]
    for string, fret in frets:  # (string 0 = low E, fret as Guitar Pro shows it)
        beat = gp.Beat(voice)
        beat.status = gp.BeatStatus.normal
        beat.duration = gp.Duration(value=4)
        note = gp.Note(beat)
        note.string, note.value, note.type = 6 - string, fret, gp.NoteType.normal
        beat.notes.append(note)
        voice.beats.append(beat)
    gp.write(song, str(path))
    return path


def test_a_gp5_capo_moves_the_fretted_notes_and_leaves_open_strings_open(tmp_path: Path) -> None:
    parsed = parse_gp_track(_gp5_with_capo(tmp_path / "c.gp5", 2, [(0, 0), (1, 3), (2, 2)]), 0)
    assert parsed.capo == 2
    assert [(n.string, n.fret) for n in parsed.notes] == [(0, 0), (1, 5), (2, 4)]
    no_capo = parse_gp_track(_gp5_with_capo(tmp_path / "n.gp5", 0, [(1, 3)]), 0)
    assert no_capo.capo == 0 and no_capo.notes[0].fret == 3


def test_a_note_pushed_past_the_neck_by_the_capo_is_counted_not_silently_kept(
    tmp_path: Path,
) -> None:
    parsed = parse_gp_track(_gp5_with_capo(tmp_path / "c.gp5", 5, [(0, 22), (0, 3)]), 0)
    assert [n.fret for n in parsed.notes] == [8]
    assert any("24" in w for w in parsed.warnings)


def test_a_gp7_capo_is_read_from_the_staff(tmp_path: Path) -> None:
    gpif = """<?xml version="1.0" encoding="utf-8"?>
<GPIF><Score><Title>T</Title></Score>
  <MasterTrack><Automations><Automation><Type>Tempo</Type><Bar>0</Bar><Position>0</Position>
    <Value>120 2</Value></Automation></Automations></MasterTrack>
  <Tracks><Track id="0"><Name>Guitar</Name>
    <InstrumentSet><Type>electricGuitar</Type></InstrumentSet>
    <Staves><Staff><Properties>
      <Property name="Tuning"><Pitches>40 45 50 55 59 64</Pitches></Property>
      <Property name="CapoFret"><Fret>3</Fret></Property>
    </Properties></Staff></Staves></Track></Tracks>
  <MasterBars><MasterBar><Time>4/4</Time><Bars>0</Bars></MasterBar></MasterBars>
  <Bars><Bar id="0"><Voices>0 -1 -1 -1</Voices></Bar></Bars>
  <Voices><Voice id="0"><Beats>0 1</Beats></Voice></Voices>
  <Beats><Beat id="0"><Rhythm ref="0"/><Notes>0</Notes></Beat>
    <Beat id="1"><Rhythm ref="0"/><Notes>1</Notes></Beat></Beats>
  <Notes>
    <Note id="0"><Properties><Property name="String"><String>1</String></Property>
      <Property name="Fret"><Fret>0</Fret></Property></Properties></Note>
    <Note id="1"><Properties><Property name="String"><String>1</String></Property>
      <Property name="Fret"><Fret>2</Fret></Property></Properties></Note>
  </Notes>
  <Rhythms><Rhythm id="0"><NoteValue>Half</NoteValue></Rhythm></Rhythms>
</GPIF>"""
    path = tmp_path / "c.gp"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("VERSION", "7.0")
        z.writestr("Content/score.gpif", gpif)
    parsed = parse_gp_track(path, 0)
    assert parsed.capo == 3
    assert [n.fret for n in parsed.notes] == [0, 5]


def _arr(notes: list[TabNote], capo: int) -> Arrangement:
    return Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="T", artist="A", song_length=10.0),
        tuning=Tuning(),
        tempo_map=TempoMap(beats=tuple(Beat(time=i * 0.5, measure=i // 4 + 1 if i % 4 == 0
                                            else -1) for i in range(16)), average_bpm=120.0),
        notes=notes,
        capo=capo,
    )


def test_the_capo_reaches_the_xml_and_the_sng_and_open_strings_sound_at_it() -> None:
    # An A minor shape with a capo at 2: open A and E strings sound at the capo,
    # so it is B minor, and the template's MIDI says so.
    am = [(1, 0), (2, 4), (3, 4), (4, 3), (5, 2)]  # frets counted from the nut
    notes = [TabNote(string=s, fret=f, time=1.0, sustain=0.4) for s, f in am]
    arr = _arr(notes, 2)
    root = render_arrangement(arr)
    assert root.findtext("capo") == "2"
    model = sng.from_arrangement(arr)
    assert model.metadata.capo_fret == 2
    (template,) = model.chord_templates
    assert template.notes[1] == 45 + 2  # the open A string, at the capo
    assert template.notes[5] == 64 + 2
    assert check_sng(model) == []
    _, name = chord_display([-1, 0, 4, 4, 3, 2], [], Tuning().midi, 2)
    assert name.startswith("B") and "m" in name
    xml_name = root.find("chordTemplates/chordTemplate")
    assert isinstance(xml_name, ET.Element) and xml_name.get("chordName", "").startswith("B")


def test_the_gp5_export_writes_the_capo_back(tmp_path: Path) -> None:
    from rockforge.infrastructure.gpexport.arrangement_writer import write_arrangement_gp5

    arr = _arr([TabNote(string=1, fret=0, time=1.0, sustain=0.4),
                TabNote(string=1, fret=5, time=2.0, sustain=0.4)], 2)
    dest = tmp_path / "out.gp5"
    write_arrangement_gp5(arr, dest)
    back = parse_gp_track(dest, 0)
    assert back.capo == 2
    assert [n.fret for n in back.notes] == [0, 5]
