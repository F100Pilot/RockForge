"""Native GP7/GP8 (.gp / GPIF) parser — built without PyGuitarPro.

A self-contained minimal GPIF document is zipped into a .gp and parsed, so the
test needs no external fixture or library.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from rockforge.domain.errors import IngestionError
from rockforge.domain.music import Technique
from rockforge.infrastructure.gpimport.parser import inspect_gp, parse_gp_track

# Minimal GPIF: 1 guitar track (standard tuning), 1 bass track (4 strings),
# two 4/4 bars at 120 BPM. Bar 0: two quarter notes on the low E string
# (fret 3 then fret 5 with a Hopo destination → hammer-on). Bar 1: a
# palm-muted note and a shift-slide note. One lyric line.
GPIF = """<?xml version="1.0" encoding="utf-8"?>
<GPIF>
  <Score><Title>Test Song</Title><Artist>Tester</Artist><Album>Demo</Album></Score>
  <MasterTrack>
    <Automations>
      <Automation><Type>Tempo</Type><Bar>0</Bar><Position>0</Position>
        <Value>120 2</Value></Automation>
    </Automations>
  </MasterTrack>
  <Tracks>
    <Track id="0">
      <Name>Guitar</Name>
      <InstrumentSet><Type>electricGuitar</Type></InstrumentSet>
      <Lyrics><Line><Text><![CDATA[he-llo world]]></Text><Offset>0</Offset></Line></Lyrics>
      <Staves><Staff><Properties>
        <Property name="Tuning"><Pitches>40 45 50 55 59 64</Pitches></Property>
      </Properties></Staff></Staves>
    </Track>
    <Track id="1">
      <Name>Bass</Name>
      <InstrumentSet><Type>electricBass</Type></InstrumentSet>
      <Staves><Staff><Properties>
        <Property name="Tuning"><Pitches>28 33 38 43</Pitches></Property>
      </Properties></Staff></Staves>
    </Track>
  </Tracks>
  <MasterBars>
    <MasterBar><Time>4/4</Time><Bars>0 2</Bars></MasterBar>
    <MasterBar><Time>4/4</Time><Bars>1 3</Bars></MasterBar>
  </MasterBars>
  <Bars>
    <Bar id="0"><Voices>0 -1 -1 -1</Voices></Bar>
    <Bar id="1"><Voices>1 -1 -1 -1</Voices></Bar>
    <Bar id="2"><Voices>-1 -1 -1 -1</Voices></Bar>
    <Bar id="3"><Voices>-1 -1 -1 -1</Voices></Bar>
  </Bars>
  <Voices>
    <Voice id="0"><Beats>0 1</Beats></Voice>
    <Voice id="1"><Beats>2 3</Beats></Voice>
  </Voices>
  <Beats>
    <Beat id="0"><Rhythm ref="0"/><Notes>0</Notes></Beat>
    <Beat id="1"><Rhythm ref="0"/><Notes>1</Notes></Beat>
    <Beat id="2"><Rhythm ref="0"/><Notes>2</Notes></Beat>
    <Beat id="3"><Rhythm ref="0"/><Notes>3</Notes></Beat>
  </Beats>
  <Notes>
    <Note id="0"><Properties>
      <Property name="String"><String>0</String></Property>
      <Property name="Fret"><Fret>3</Fret></Property>
    </Properties></Note>
    <Note id="1"><Properties>
      <Property name="String"><String>0</String></Property>
      <Property name="Fret"><Fret>5</Fret></Property>
      <Property name="HopoDestination"><Enable/></Property>
    </Properties></Note>
    <Note id="2"><Properties>
      <Property name="String"><String>1</String></Property>
      <Property name="Fret"><Fret>7</Fret></Property>
      <Property name="PalmMuted"><Enable/></Property>
      <Property name="Slide"><Flags>1</Flags></Property>
    </Properties></Note>
    <Note id="3"><Properties>
      <Property name="String"><String>1</String></Property>
      <Property name="Fret"><Fret>9</Fret></Property>
    </Properties></Note>
  </Notes>
  <Rhythms>
    <Rhythm id="0"><NoteValue>Quarter</NoteValue></Rhythm>
  </Rhythms>
</GPIF>
"""


@pytest.fixture
def gp7_file(tmp_path: Path) -> Path:
    path = tmp_path / "song.gp"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("VERSION", "7.0")
        z.writestr("Content/score.gpif", GPIF)
    return path


def test_gp7_oversized_score_gpif_is_rejected(tmp_path: Path) -> None:
    """A small ZIP whose score.gpif entry decompresses far past the sane
    ceiling (a 'zip bomb') is rejected before decompression, not read fully
    into memory."""
    path = tmp_path / "song.gp"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("VERSION", "7.0")
        # Highly compressible, but declares (via ZipInfo.file_size, read from
        # the local file header before any decompression) a size over the cap.
        z.writestr("Content/score.gpif", "x" * (10**8))
    import rockforge.infrastructure.gpimport.gpif_parser as gpif_parser

    monkey_cap = 1024  # tiny cap so the test doesn't need a real 50 MB payload
    orig_cap = gpif_parser._MAX_GPIF_BYTES
    gpif_parser._MAX_GPIF_BYTES = monkey_cap
    try:
        with pytest.raises(IngestionError, match="implausibly large"):
            inspect_gp(path)
    finally:
        gpif_parser._MAX_GPIF_BYTES = orig_cap


def test_gp7_doctype_declaration_is_rejected(tmp_path: Path) -> None:
    """A score.gpif carrying a DOCTYPE/internal-entity declaration ("billion
    laughs") is rejected outright — a real GP7 export never has one."""
    path = tmp_path / "song.gp"
    bomb = (
        '<?xml version="1.0"?>'
        "<!DOCTYPE GPIF [<!ENTITY a \"lol\"><!ENTITY b \"&a;&a;&a;&a;&a;\">]>"
        "<GPIF>&b;</GPIF>"
    )
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("VERSION", "7.0")
        z.writestr("Content/score.gpif", bomb)
    with pytest.raises(IngestionError, match="DOCTYPE/ENTITY"):
        inspect_gp(path)


def test_inspect_gp7_reads_metadata_and_tracks(gp7_file: Path) -> None:
    info = inspect_gp(gp7_file)
    assert (info.title, info.artist, info.album, info.tempo) == (
        "Test Song", "Tester", "Demo", 120,
    )
    assert info.has_lyrics
    assert [t.string_count for t in info.tracks] == [6, 4]
    assert info.tracks[0].tuning_midi == (40, 45, 50, 55, 59, 64)
    assert not info.tracks[0].is_percussion


def test_parse_gp7_notes_timing_and_techniques(gp7_file: Path) -> None:
    parsed = parse_gp_track(gp7_file, 0)
    # Track 0 spans both master bars (4 quarter notes total).
    assert len(parsed.notes) == 4
    assert parsed.tuning.midi == (40, 45, 50, 55, 59, 64)
    assert parsed.tempo_map.average_bpm == 120.0
    by_time = sorted(parsed.notes, key=lambda n: n.time)
    # Quarter note at 120 BPM = 0.5s; bar 1 (4 beats) starts at 2.0s.
    assert [round(n.time, 2) for n in by_time] == [0.0, 0.5, 2.0, 2.5]
    # note 1: fret 3 -> 5 with HopoDestination is a hammer-on (higher fret).
    assert Technique.HAMMER_ON in by_time[1].techniques


def test_parse_gp7_palm_mute_and_slide(gp7_file: Path) -> None:
    parsed = parse_gp_track(gp7_file, 0)
    slide_note = next(n for n in parsed.notes if Technique.PALM_MUTE in n.techniques)
    assert Technique.SLIDE in slide_note.techniques
    assert slide_note.slide_to_fret == 9  # next note on the same string


def test_parse_gp7_offset_shifts_all_notes(gp7_file: Path) -> None:
    parsed = parse_gp_track(gp7_file, 0, offset_s=2.0)
    assert min(n.time for n in parsed.notes) == pytest.approx(2.0)


def test_parse_gp7_rejects_four_string_bass(gp7_file: Path) -> None:
    with pytest.raises(Exception, match="6"):
        parse_gp_track(gp7_file, 1)


def test_gp7_lyrics_sourced_from_track(gp7_file: Path) -> None:
    parsed = parse_gp_track(gp7_file, 0)
    assert len(parsed.lyrics) == 1
    assert parsed.lyrics[0].text == "he-llo world"


def test_gp7_out_of_range_note_dropped_with_warning(tmp_path: Path) -> None:
    # A note above the 24-fret neck is skipped (it can't be placed), but the drop
    # is surfaced as a warning instead of vanishing silently.
    path = tmp_path / "oor.gp"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("VERSION", "7.0")
        z.writestr("Content/score.gpif", GPIF.replace("<Fret>9</Fret>", "<Fret>30</Fret>"))
    parsed = parse_gp_track(path, 0)
    assert len(parsed.notes) == 3  # the fret-30 note was dropped (was 4)
    assert parsed.warnings and "off the 24-fret neck" in parsed.warnings[0]


# A tied note: bar 0 has two quarter notes on string 0 — fret 7, then fret 7
# again flagged Tie destination="true" (a held continuation, drawn "(7)" in GP).
# It must NOT become a second attack; it extends the first note's sustain.
TIE_GPIF = """<?xml version="1.0" encoding="utf-8"?>
<GPIF>
  <Score><Title>T</Title><Artist>A</Artist><Album>B</Album></Score>
  <MasterTrack><Automations><Automation><Type>Tempo</Type><Bar>0</Bar>
    <Position>0</Position><Value>120 2</Value></Automation></Automations></MasterTrack>
  <Tracks><Track id="0"><Name>Guitar</Name>
    <InstrumentSet><Type>electricGuitar</Type></InstrumentSet>
    <Staves><Staff><Properties>
      <Property name="Tuning"><Pitches>40 45 50 55 59 64</Pitches></Property>
    </Properties></Staff></Staves></Track></Tracks>
  <MasterBars><MasterBar><Time>4/4</Time><Bars>0</Bars></MasterBar></MasterBars>
  <Bars><Bar id="0"><Voices>0 -1 -1 -1</Voices></Bar></Bars>
  <Voices><Voice id="0"><Beats>0 1</Beats></Voice></Voices>
  <Beats>
    <Beat id="0"><Rhythm ref="0"/><Notes>0</Notes></Beat>
    <Beat id="1"><Rhythm ref="0"/><Notes>1</Notes></Beat>
  </Beats>
  <Notes>
    <Note id="0"><Properties>
      <Property name="String"><String>0</String></Property>
      <Property name="Fret"><Fret>7</Fret></Property></Properties></Note>
    <Note id="1"><Tie origin="false" destination="true"/><Properties>
      <Property name="String"><String>0</String></Property>
      <Property name="Fret"><Fret>7</Fret></Property></Properties></Note>
  </Notes>
  <Rhythms><Rhythm id="0"><NoteValue>Quarter</NoteValue></Rhythm></Rhythms>
</GPIF>
"""


def test_gp7_tied_note_extends_not_duplicates(tmp_path: Path) -> None:
    path = tmp_path / "tie.gp"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("VERSION", "7.0")
        z.writestr("Content/score.gpif", TIE_GPIF)
    parsed = parse_gp_track(path, 0)
    # Two beats, but the second is a tie continuation → ONE attack, held longer.
    assert len(parsed.notes) == 1
    n = parsed.notes[0]
    assert n.fret == 7
    assert n.sustain == pytest.approx(1.0)  # two quarters at 120 BPM held together
