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


def test_gp7_bend_on_a_tied_note_is_kept(tmp_path: Path) -> None:
    """Held, then bent a whole step on the tied note: the bend survives the fold,
    placed on the second half of the held note (as in the GP5 path)."""
    bend = (
        '<Property name="Bended"><Enable/></Property>'
        '<Property name="BendOriginValue"><Float>0</Float></Property>'
        '<Property name="BendDestinationValue"><Float>100</Float></Property>'
    )
    tail = '<Property name="Fret"><Fret>7</Fret></Property></Properties></Note>\n  </Notes>'
    gpif = TIE_GPIF.replace(tail, tail.replace("</Properties>", f"{bend}</Properties>"))
    assert gpif != TIE_GPIF
    path = tmp_path / "tie_bend.gp"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("VERSION", "7.0")
        z.writestr("Content/score.gpif", gpif)
    (n,) = parse_gp_track(path, 0).notes
    assert n.sustain == pytest.approx(1.0)
    assert Technique.BEND in n.techniques and n.bend_semitones == pytest.approx(2.0)
    curve = [(round(p.position, 2), p.step) for p in n.bend_points]
    assert curve == [(0.0, 0.0), (0.5, 0.0), (1.0, 2.0)]


def test_gp7_bend_release_keeps_both_middle_points(tmp_path: Path) -> None:
    """A ½ bend-and-release as alphaTab's .gp export writes it: two middle offsets
    (25, 50) share the middle value. Both are points, as alphaTab's GpifParser reads
    them — the bend holds at the top before the release, not a plain up-and-down."""
    bend = (
        '<Property name="Bended"><Enable/></Property>'
        '<Property name="BendOriginOffset"><Float>0</Float></Property>'
        '<Property name="BendOriginValue"><Float>0</Float></Property>'
        '<Property name="BendMiddleOffset1"><Float>25</Float></Property>'
        '<Property name="BendMiddleOffset2"><Float>50</Float></Property>'
        '<Property name="BendMiddleValue"><Float>50</Float></Property>'
        '<Property name="BendDestinationOffset"><Float>75</Float></Property>'
        '<Property name="BendDestinationValue"><Float>0</Float></Property>'
    )
    head = '<Property name="Fret"><Fret>7</Fret></Property></Properties></Note>\n    <Note id="1">'
    gpif = TIE_GPIF.replace(head, head.replace("</Properties>", f"{bend}</Properties>"))
    assert gpif != TIE_GPIF
    path = tmp_path / "bend_release.gp"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("VERSION", "7.0")
        z.writestr("Content/score.gpif", gpif)
    (n,) = parse_gp_track(path, 0).notes  # the bent quarter, tied on to a half
    assert n.bend_semitones == pytest.approx(1.0)
    curve = [(round(p.position, 3), p.step) for p in n.bend_points]
    assert curve == [(0.0, 0.0), (0.125, 1.0), (0.25, 1.0), (0.375, 0.0)]


# --- Tempo automation semantics (GPIF) ------------------------------------
# Two independent details that both used to be read wrong, and which silently
# corrupt the whole GP timeline (and therefore any sync analysis built on it).

def _tempo_gpif(automations: str, bars: str = "4/4") -> str:
    """A minimal 2-bar GPIF with a caller-supplied <Automations> block."""
    return f"""<?xml version="1.0" encoding="utf-8"?>
<GPIF>
  <Score><Title>T</Title><Artist>A</Artist></Score>
  <MasterTrack><Automations>{automations}</Automations></MasterTrack>
  <Tracks><Track id="0"><Name>Guitar</Name>
    <InstrumentSet><Type>electricGuitar</Type></InstrumentSet>
    <Staves><Staff><Properties>
      <Property name="Tuning"><Pitches>40 45 50 55 59 64</Pitches></Property>
    </Properties></Staff></Staves></Track></Tracks>
  <MasterBars>
    <MasterBar><Time>{bars}</Time><Bars>0</Bars></MasterBar>
    <MasterBar><Time>{bars}</Time><Bars>1</Bars></MasterBar>
  </MasterBars>
  <Bars><Bar id="0"><Voices>-1</Voices></Bar><Bar id="1"><Voices>-1</Voices></Bar></Bars>
  <Voices/><Beats/><Notes/><Rhythms/>
</GPIF>
"""


def _gp_with(tmp_path: Path, gpif: str) -> Path:
    path = tmp_path / "tempo.gp"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("VERSION", "7.0")
        z.writestr("Content/score.gpif", gpif)
    return path


def test_gpif_tempo_reference_multiplier_is_applied(tmp_path: Path) -> None:
    """<Value> is "<number> <reference>" — the reference says WHICH note value
    the number counts per minute, not always the quarter. Ignoring it reads a
    score authored in half notes (reference 4, x2.0) at half the real tempo."""
    from rockforge.infrastructure.gpimport.gpif_parser import _tempo_bpm

    assert _tempo_bpm(["120", "2"]) == 120.0     # quarter (the ordinary case)
    assert _tempo_bpm(["60", "4"]) == 120.0      # half note = 2x
    assert _tempo_bpm(["120", "1"]) == 60.0      # x0.5
    assert _tempo_bpm(["80", "3"]) == 120.0      # dotted quarter = 1.5x
    assert _tempo_bpm(["40", "5"]) == 120.0      # x3.0
    assert _tempo_bpm(["120", "9"]) == 120.0     # out of range clamps to quarter
    assert _tempo_bpm(["120"]) == 60.0           # single token = reference 1

    # End to end: a half-note-referenced tempo must reach the parsed track.
    gp = _gp_with(tmp_path, _tempo_gpif(
        "<Automation><Type>Tempo</Type><Bar>0</Bar><Position>0</Position>"
        "<Value>60 4</Value></Automation>"
    ))
    assert inspect_gp(gp).tempo == pytest.approx(120.0)


def test_gpif_tempo_position_is_a_fraction_of_the_bar(tmp_path: Path) -> None:
    """<Position> is a fraction of that bar's OWN duration, not a quarter-note
    count. A change at half of bar 1 must land at bar 1 + half a bar."""
    from rockforge.infrastructure.gpimport.gpif_parser import _tempo_events
    from rockforge.infrastructure.gpimport.parser import QUARTER_TICKS

    bar = 4 * QUARTER_TICKS                      # one 4/4 bar in ticks
    gpif = _tempo_gpif(
        "<Automation><Type>Tempo</Type><Bar>0</Bar><Position>0</Position>"
        "<Value>120 2</Value></Automation>"
        "<Automation><Type>Tempo</Type><Bar>1</Bar><Position>0.5</Position>"
        "<Value>150 2</Value></Automation>"
    )
    import xml.etree.ElementTree as ET
    root = ET.fromstring(gpif)
    events = _tempo_events(root, [0, bar], [bar, bar])
    assert events[0] == (0, 120.0)
    # Half of a 4/4 bar = 2 quarters past the bar start — NOT 0.5 quarters.
    assert events[1] == (bar + bar // 2, 150.0)

    # In 3/4 the same ratio is a shorter distance: the bar's own duration rules.
    bar34 = 3 * QUARTER_TICKS
    events34 = _tempo_events(root, [0, bar34], [bar34, bar34])
    assert events34[1] == (bar34 + bar34 // 2, 150.0)


def _synced_gpif(sync_points: str, backing: str = "") -> str:
    """Three 4/4 bars at a single authored 120 BPM (2 s per bar by the score),
    one whole note opening each bar, plus Guitar Pro 8 sync points."""
    bars = "".join(
        f'<MasterBar><Time>4/4</Time><Bars>{i}</Bars></MasterBar>' for i in range(3)
    )
    return f"""<?xml version="1.0" encoding="utf-8"?>
<GPIF>
  <Score><Title>T</Title><Artist>A</Artist></Score>
  <MasterTrack><Automations>
    <Automation><Type>Tempo</Type><Bar>0</Bar><Position>0</Position>
      <Value>120 2</Value></Automation>
    {sync_points}
  </Automations></MasterTrack>
  {backing}
  <Tracks><Track id="0"><Name>Guitar</Name>
    <InstrumentSet><Type>electricGuitar</Type></InstrumentSet>
    <Staves><Staff><Properties>
      <Property name="Tuning"><Pitches>40 45 50 55 59 64</Pitches></Property>
    </Properties></Staff></Staves></Track></Tracks>
  <MasterBars>{bars}</MasterBars>
  <Bars>
    <Bar id="0"><Voices>0 -1 -1 -1</Voices></Bar>
    <Bar id="1"><Voices>1 -1 -1 -1</Voices></Bar>
    <Bar id="2"><Voices>2 -1 -1 -1</Voices></Bar>
  </Bars>
  <Voices>
    <Voice id="0"><Beats>0</Beats></Voice>
    <Voice id="1"><Beats>1</Beats></Voice>
    <Voice id="2"><Beats>2</Beats></Voice>
  </Voices>
  <Beats>
    <Beat id="0"><Rhythm ref="0"/><Notes>0</Notes></Beat>
    <Beat id="1"><Rhythm ref="0"/><Notes>1</Notes></Beat>
    <Beat id="2"><Rhythm ref="0"/><Notes>2</Notes></Beat>
  </Beats>
  <Notes>
    <Note id="0"><Properties><Property name="String"><String>0</String></Property>
      <Property name="Fret"><Fret>3</Fret></Property></Properties></Note>
    <Note id="1"><Properties><Property name="String"><String>0</String></Property>
      <Property name="Fret"><Fret>5</Fret></Property></Properties></Note>
    <Note id="2"><Properties><Property name="String"><String>0</String></Property>
      <Property name="Fret"><Fret>7</Fret></Property></Properties></Note>
  </Notes>
  <Rhythms><Rhythm id="0"><NoteValue>Whole</NoteValue></Rhythm></Rhythms>
</GPIF>
"""


def _sync(bar: int, audio_s: float, occurrence: int = 0, position: float = 0.0) -> str:
    frame = audio_s * 44100
    return (
        f"<Automation><Type>SyncPoint</Type><Linear>false</Linear><Bar>{bar}</Bar>"
        f"<Position>{position}</Position><Visible>true</Visible><Value>"
        f"<BarIndex>{bar}</BarIndex><BarOccurrence>{occurrence}</BarOccurrence>"
        f"<ModifiedTempo>0</ModifiedTempo><OriginalTempo>120</OriginalTempo>"
        f"<FrameOffset>{frame}</FrameOffset></Value></Automation>"
    )


def test_gp8_sync_points_retime_the_chart_to_the_synced_audio(tmp_path: Path) -> None:
    """Guitar Pro 8 aligns a score to its audio track with SYNC POINTS, not tempo
    markings: the authored tempo stays one number (here 120 — two seconds a bar)
    and GP shows a varying BPM computed from the points. Ignoring them locked the
    chart to that one number, so a file the user had synced perfectly in Guitar
    Pro drifted in RockForge.

    Bar 1 is pinned at 1.0 s of audio, bar 2 at 3.5 s, bar 3 at 5.0 s: the first
    bar really lasts 2.5 s (96 BPM) and the second 1.5 s (160 BPM). Times are
    relative to bar 1, so ``offset_s`` still means "where bar 1 is".
    """
    gp = _gp_with(tmp_path, _synced_gpif(_sync(0, 1.0) + _sync(1, 3.5) + _sync(2, 5.0)))
    parsed = parse_gp_track(gp, 0, offset_s=1.0)

    assert [round(n.time, 3) for n in parsed.notes] == [1.0, 3.5, 5.0]
    downbeats = [b.time for b in parsed.tempo_map.beats if b.measure > 0]
    assert downbeats[:3] == pytest.approx([1.0, 3.5, 5.0])
    # Past the last point the final span's stretch continues (1.5 s a bar).
    assert parsed.notes[-1].sustain == pytest.approx(1.5, abs=0.1)
    assert any("sync" in w.lower() for w in parsed.warnings)

    from rockforge.infrastructure.gpimport.gpif_parser import sync_start_s

    # The exact offset for that same audio file — what the wizard pre-fills.
    assert sync_start_s(gp) == pytest.approx(1.0)


def test_gp8_sync_points_respect_the_backing_track_padding(tmp_path: Path) -> None:
    """alphaTab subtracts <FramePadding> from every sync point's frame offset
    before using it as a position in the audio file."""
    backing = (
        "<BackingTrack><Enabled>true</Enabled><Source>Local</Source>"
        "<FramePadding>22050</FramePadding></BackingTrack>"
    )
    gp = _gp_with(tmp_path, _synced_gpif(_sync(0, 1.0) + _sync(1, 3.5), backing))
    from rockforge.infrastructure.gpimport.gpif_parser import sync_start_s

    assert sync_start_s(gp) == pytest.approx(0.5)
    # The spacing is unaffected — padding moves every point equally.
    parsed = parse_gp_track(gp, 0)
    assert parsed.notes[1].time - parsed.notes[0].time == pytest.approx(2.5)


def test_bar_1_before_the_audio_starts_is_a_negative_start(tmp_path: Path) -> None:
    """alphaTab saves a start of -2.1 s (bar 1 before the recording, e.g. the
    PDF-to-GP5 player's "Início") as <FramePadding> +2.1 s and one point at bar 1
    with frame 0. Clamping it to 0 put every note 2.1 s late in RockForge."""
    backing = (
        "<BackingTrack><Enabled>true</Enabled><Source>Local</Source>"
        "<FramePadding>92610</FramePadding></BackingTrack>"
    )
    gp = _gp_with(tmp_path, _synced_gpif(_sync(0, 0.0), backing))
    from rockforge.infrastructure.gpimport.gpif_parser import sync_start_s

    assert sync_start_s(gp) == pytest.approx(-2.1)


def test_gp8_sync_points_on_repeats_or_running_backwards_are_skipped(
    tmp_path: Path,
) -> None:
    """A point for a bar's SECOND pass in a score without repeats names a pass
    that is never played; and a point earlier in the audio than its predecessor
    would fold the timeline back. Both are dropped and COUNTED, never silently."""
    gp = _gp_with(tmp_path, _synced_gpif(
        _sync(0, 1.0) + _sync(1, 3.5) + _sync(1, 9.0, occurrence=1) + _sync(2, 2.0)
    ))
    parsed = parse_gp_track(gp, 0)
    assert parsed.notes[1].time - parsed.notes[0].time == pytest.approx(2.5)
    assert any("2 Guitar Pro sync point(s) ignored" in w for w in parsed.warnings)


def test_a_file_without_sync_points_is_timed_exactly_as_before(tmp_path: Path) -> None:
    gp = _gp_with(tmp_path, _synced_gpif(""))
    parsed = parse_gp_track(gp, 0)
    assert [round(n.time, 3) for n in parsed.notes] == [0.0, 2.0, 4.0]
    assert not any("sync" in w.lower() for w in parsed.warnings)
    from rockforge.infrastructure.gpimport.gpif_parser import sync_start_s

    assert sync_start_s(gp) is None


def test_gp8_synced_average_bpm_is_what_plays_not_the_header(tmp_path: Path) -> None:
    """12 quarters over 4.0 + 1.5 s = 5.5 s of audio is 130.9 BPM on average;
    the header's 120 is a number nothing plays at."""
    gp = _gp_with(tmp_path, _synced_gpif(_sync(0, 1.0) + _sync(1, 3.5) + _sync(2, 5.0)))
    assert parse_gp_track(gp, 0).tempo_map.average_bpm == pytest.approx(12 / 5.5 * 60)


_BACKING = (
    "<BackingTrack><Enabled>{enabled}</Enabled><Source>{source}</Source>"
    "<AssetId>0</AssetId><FramePadding>0</FramePadding></BackingTrack>"
    "<Assets><Asset id=\"0\"><EmbeddedFilePath><![CDATA[{member}]]></EmbeddedFilePath>"
    "</Asset></Assets>"
)


def _gp_with_audio(
    tmp_path: Path, *, enabled: str = "true", source: str = "Local",
    member: str = "Content/Assets/abc.mp3", store: str | None = "Content/Assets/abc.mp3",
) -> Path:
    backing = _BACKING.format(enabled=enabled, source=source, member=member)
    gpif = _synced_gpif(_sync(0, 0.0), backing)
    path = tmp_path / "with_audio.gp"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("VERSION", "7.0")
        z.writestr("Content/score.gpif", gpif)
        if store:
            z.writestr(store, b"ID3fake-mp3-bytes")
    return path


def test_the_audio_embedded_in_a_gp8_file_is_found_and_extracted(tmp_path: Path) -> None:
    """A GP8 file carries its own recording, and that copy is what its sync
    points describe. guitar-pro-youtube-sync, for one, trims the video's intro
    before embedding it — so the ORIGINAL download starts earlier, and uploading
    it put a real user's chart exactly one bar late. The embedded copy is the
    one to use."""
    from rockforge.infrastructure.gpimport.gpif_parser import (
        embedded_audio,
        extract_embedded_audio,
    )

    gp = _gp_with_audio(tmp_path)
    found = embedded_audio(gp)
    assert found is not None
    assert found.suffix == ".mp3" and found.size_bytes == len(b"ID3fake-mp3-bytes")

    out = extract_embedded_audio(gp, tmp_path / "out" / "recording")
    assert out.suffix == ".mp3"
    assert out.read_bytes() == b"ID3fake-mp3-bytes"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"source": "YouTube"},                              # a link, not a file
        {"store": None},                                    # referenced but absent
        {"member": "Content/Assets/abc.exe", "store": "Content/Assets/abc.exe"},
    ],
)
def test_no_usable_embedded_audio_is_none_never_an_error(tmp_path: Path, kwargs: dict) -> None:
    """Anything short of a real, local audio member is simply "no embedded
    audio" — the user can still upload a recording."""
    from rockforge.infrastructure.gpimport.gpif_parser import embedded_audio

    assert embedded_audio(_gp_with_audio(tmp_path, **kwargs)) is None


@pytest.mark.parametrize(
    "kwargs",
    [
        # The audio track switched off in Guitar Pro: still the audio it was synced to.
        {"enabled": "false"},
        # What a YouTube download is when embedded as-is, and a path whose case
        # and leading slash differ from the ZIP member's.
        {"member": "/content/assets/ABC.opus", "store": "Content/Assets/abc.opus"},
        # The asset names another file, but the one audio file in Assets is there.
        {"member": "Content/Assets/gone.mp3", "store": "Content/Assets/other.m4a"},
    ],
)
def test_the_embedded_audio_is_found_despite_details_that_used_to_hide_it(
    tmp_path: Path, kwargs: dict,
) -> None:
    """A user's GP8 file with its audio "was not detected": the old check wanted
    an enabled track, one of six extensions and the exact member name."""
    from rockforge.infrastructure.gpimport.gpif_parser import backing_track, extract_embedded_audio

    gp = _gp_with_audio(tmp_path, **kwargs)
    info = backing_track(gp)
    assert info.audio is not None and info.audio.size_bytes == len(b"ID3fake-mp3-bytes")
    assert info.disabled == (kwargs.get("enabled") == "false")
    out = extract_embedded_audio(gp, tmp_path / "out" / "recording")
    assert out.read_bytes() == b"ID3fake-mp3-bytes"


def test_audio_that_is_not_in_the_file_says_where_it_is(tmp_path: Path) -> None:
    """No recording inside, but the file says which one: a YouTube video (the
    wizard can fetch its audio) or a file elsewhere on the user's disk."""
    from rockforge.infrastructure.gpimport.gpif_parser import backing_track

    gpif = _synced_gpif(_sync(0, 0.0), (
        "<BackingTrack><Enabled>true</Enabled><Source>YouTube</Source>"
        "<YouTubeVideoUrl>https://www.youtube.com/watch?v=dQw4w9WgXcQ</YouTubeVideoUrl>"
        "<AssetId>0</AssetId></BackingTrack>"
    ))
    link = _gp_with(tmp_path, gpif)
    assert backing_track(link).youtube_url == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert backing_track(link).audio is None

    outside = _synced_gpif(_sync(0, 0.0), (
        "<BackingTrack><Enabled>true</Enabled><Source>Local</Source><AssetId>0</AssetId>"
        "</BackingTrack><Assets><Asset id=\"0\"><OriginalFilePath><![CDATA[C:\\m\\song.mp3]]>"
        "</OriginalFilePath></Asset></Assets>"
    ))
    info = backing_track(_gp_with(tmp_path, outside))
    assert info.audio is None and info.external_path == "C:\\m\\song.mp3"


def test_a_gp_without_a_backing_track_has_no_embedded_audio(tmp_path: Path) -> None:
    from rockforge.infrastructure.gpimport.gpif_parser import embedded_audio

    assert embedded_audio(_gp_with(tmp_path, _synced_gpif(""))) is None


def test_bar_times_retime_a_gp7_file_and_win_over_its_own_sync_points(tmp_path: Path) -> None:
    """Externally supplied bar times (Songsterr) are what the user chose for
    THIS recording, so they take precedence over the file's GP8 sync points."""
    gp = _gp_with(tmp_path, _synced_gpif(_sync(0, 1.0) + _sync(1, 3.5) + _sync(2, 5.0)))
    parsed = parse_gp_track(gp, 0, bar_times=[20.0, 21.0, 23.0])
    assert [round(n.time, 3) for n in parsed.notes] == [0.0, 1.0, 3.0]
    assert any("bar times" in w for w in parsed.warnings)
    assert not any("Guitar Pro 8 audio sync used" in w for w in parsed.warnings)


# Guitar strums quarters; the lyrics sit on a separate Vocals track whose
# rhythm differs (eighth, eighth rest, eighth, then a dotted half).
GPIF_VOCALS = """<?xml version="1.0" encoding="utf-8"?>
<GPIF>
  <Score><Title>V</Title><Artist>B</Artist></Score>
  <MasterTrack><Automations>
    <Automation><Type>Tempo</Type><Bar>0</Bar><Position>0</Position>
      <Value>120 2</Value></Automation>
  </Automations></MasterTrack>
  <Tracks>
    <Track id="0"><Name>Guitar</Name>
      <Staves><Staff><Properties>
        <Property name="Tuning"><Pitches>40 45 50 55 59 64</Pitches></Property>
      </Properties></Staff></Staves>
    </Track>
    <Track id="1"><Name>Vocals</Name>
      <Lyrics><Line><Text><![CDATA[sing  a song]]></Text><Offset>0</Offset></Line></Lyrics>
      <Staves><Staff><Properties>
        <Property name="Tuning"><Pitches>40 45 50 55 59 64</Pitches></Property>
      </Properties></Staff></Staves>
    </Track>
  </Tracks>
  <MasterBars><MasterBar><Time>4/4</Time><Bars>0 1</Bars></MasterBar></MasterBars>
  <Bars>
    <Bar id="0"><Voices>0 -1 -1 -1</Voices></Bar>
    <Bar id="1"><Voices>1 -1 -1 -1</Voices></Bar>
  </Bars>
  <Voices>
    <Voice id="0"><Beats>0 1 2 3</Beats></Voice>
    <Voice id="1"><Beats>4 5 6 7</Beats></Voice>
  </Voices>
  <Beats>
    <Beat id="0"><Rhythm ref="0"/><Notes>0</Notes></Beat>
    <Beat id="1"><Rhythm ref="0"/><Notes>0</Notes></Beat>
    <Beat id="2"><Rhythm ref="0"/><Notes>0</Notes></Beat>
    <Beat id="3"><Rhythm ref="0"/><Notes>0</Notes></Beat>
    <Beat id="4"><Rhythm ref="1"/><Notes>1</Notes></Beat>
    <Beat id="5"><Rhythm ref="1"/></Beat>
    <Beat id="6"><Rhythm ref="1"/><Notes>1</Notes></Beat>
    <Beat id="7"><Rhythm ref="2"/><Notes>1</Notes></Beat>
  </Beats>
  <Notes>
    <Note id="0"><Properties>
      <Property name="String"><String>0</String></Property>
      <Property name="Fret"><Fret>3</Fret></Property>
    </Properties></Note>
    <Note id="1"><Properties>
      <Property name="String"><String>5</String></Property>
      <Property name="Fret"><Fret>5</Fret></Property>
    </Properties></Note>
  </Notes>
  <Rhythms>
    <Rhythm id="0"><NoteValue>Quarter</NoteValue></Rhythm>
    <Rhythm id="1"><NoteValue>Eighth</NoteValue></Rhythm>
    <Rhythm id="2"><NoteValue>Half</NoteValue><AugmentationDot count="1"/></Rhythm>
  </Rhythms>
</GPIF>
"""


def test_gp7_lyrics_are_timed_on_the_notes_of_their_own_track(tmp_path: Path) -> None:
    path = tmp_path / "vocals.gp"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("VERSION", "7.0")
        z.writestr("Content/score.gpif", GPIF_VOCALS)
    parsed = parse_gp_track(path, 0)  # the guitar chart
    assert parsed.lyrics[0].text == "sing  a song"
    # Vocals: eighth at 0, eighth REST at 0.25, eighth at 0.5, dotted half at
    # 0.75 — each with its end, its pitch (high E + 5 = A4) and the breath.
    assert parsed.lyric_notes is not None
    assert [(n.time, n.end, n.midi, n.rest_before) for n in parsed.lyric_notes] == [
        (0.0, 0.25, 69, False), (0.5, 0.75, 69, True), (0.75, 2.25, 69, False),
    ]


def test_gp7_grid_closes_the_last_bar_so_a_late_eighth_fits(tmp_path: Path) -> None:
    gpif = GPIF_VOCALS.replace(
        '<Voice id="0"><Beats>0 1 2 3</Beats></Voice>',
        '<Voice id="0"><Beats>0 1 2 3 8</Beats></Voice>',
    ).replace(
        '<Beat id="3"><Rhythm ref="0"/><Notes>0</Notes></Beat>',
        '<Beat id="3"><Rhythm ref="1"/><Notes>0</Notes></Beat>\n'
        '    <Beat id="8"><Rhythm ref="1"/><Notes>0</Notes></Beat>',
    )
    path = tmp_path / "late.gp"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("VERSION", "7.0")
        z.writestr("Content/score.gpif", gpif)
    parsed = parse_gp_track(path, 0)
    assert parsed.notes[-1].time == pytest.approx(1.75)  # the "and" of 4
    closing = parsed.tempo_map.beats[-1]
    assert (closing.time, closing.measure) == (pytest.approx(2.0), 2)


@pytest.mark.parametrize(
    ("head", "suffix"),
    [
        (b"ID3\x04\x00", ".mp3"),
        (b"\xff\xfb\x90\x00", ".mp3"),       # an mp3 with no ID3 tag
        (b"\xff\xf1\x50\x80", ".aac"),       # ADTS AAC
        (b"OggS\x00\x02", ".ogg"),
        (b"\x00\x00\x00\x20ftypM4A ", ".m4a"),
        (b"RIFF\x24\x00\x00\x00WAVEfmt ", ".wav"),
    ],
)
def test_an_embedded_recording_with_no_extension_is_recognised_by_its_bytes(
    tmp_path: Path, head: bytes, suffix: str,
) -> None:
    """The user's GP8 file stores its recording as "Content/Assets/backing-track",
    no extension, and the name check reported it as a file OUTSIDE the .gp
    ("continua a não detetar que o GP file tem o mp3 incluído")."""
    from rockforge.infrastructure.gpimport.gpif_parser import backing_track, extract_embedded_audio

    member = "Content/Assets/backing-track"
    backing = _BACKING.format(enabled="true", source="Local", member=member)
    gp = tmp_path / "no_ext.gp"
    with zipfile.ZipFile(gp, "w") as z:
        z.writestr("VERSION", "7.0")
        z.writestr("Content/score.gpif", _synced_gpif(_sync(0, 0.0), backing))
        z.writestr(member, head + b"audio")
    info = backing_track(gp)
    assert info.audio is not None and info.audio.suffix == suffix
    assert info.external_path is None
    out = extract_embedded_audio(gp, tmp_path / "out" / "recording")
    assert out.suffix == suffix and out.read_bytes() == head + b"audio"


def test_an_extensionless_member_that_is_not_audio_is_not_taken_for_one(tmp_path: Path) -> None:
    """Sniffing must not turn anything into a recording, and a path inside the
    .gp is never named as a file for the user to go and upload."""
    from rockforge.infrastructure.gpimport.gpif_parser import backing_track

    member = "Content/Assets/backing-track"
    backing = _BACKING.format(enabled="true", source="Local", member=member)
    gp = tmp_path / "junk.gp"
    with zipfile.ZipFile(gp, "w") as z:
        z.writestr("VERSION", "7.0")
        z.writestr("Content/score.gpif", _synced_gpif(_sync(0, 0.0), backing))
        z.writestr(member, b"just some text")
    info = backing_track(gp)
    assert info.audio is None and info.external_path is None


GRACE_GPIF = """<?xml version="1.0" encoding="utf-8"?>
<GPIF>
  <Score><Title>T</Title><Artist>A</Artist><Album>B</Album></Score>
  <MasterTrack><Automations><Automation><Type>Tempo</Type><Bar>0</Bar>
    <Position>0</Position><Value>120 2</Value></Automation></Automations></MasterTrack>
  <Tracks><Track id="0"><Name>Guitar</Name>
    <InstrumentSet><Type>electricGuitar</Type></InstrumentSet>
    <Staves><Staff><Properties>
      <Property name="Tuning"><Pitches>40 45 50 55 59 64</Pitches></Property>
    </Properties></Staff></Staves></Track></Tracks>
  <MasterBars><MasterBar><Time>2/4</Time><Bars>0</Bars></MasterBar></MasterBars>
  <Bars><Bar id="0"><Voices>0 -1 -1 -1</Voices></Bar></Bars>
  <Voices><Voice id="0"><Beats>0 1 2</Beats></Voice></Voices>
  <Beats>
    <Beat id="0"><Rhythm ref="0"/><Notes>0</Notes></Beat>
    <Beat id="1"><GraceNotes>{kind}</GraceNotes><Rhythm ref="1"/><Notes>1</Notes></Beat>
    <Beat id="2"><Rhythm ref="0"/><Notes>2</Notes></Beat>
  </Beats>
  <Notes>
    <Note id="0"><Properties>
      <Property name="String"><String>0</String></Property>
      <Property name="Fret"><Fret>3</Fret></Property></Properties></Note>
    <Note id="1"><Properties>
      <Property name="String"><String>1</String></Property>
      <Property name="Fret"><Fret>5</Fret></Property></Properties></Note>
    <Note id="2"><Properties>
      <Property name="String"><String>1</String></Property>
      <Property name="Fret"><Fret>7</Fret></Property></Properties></Note>
  </Notes>
  <Rhythms>
    <Rhythm id="0"><NoteValue>Quarter</NoteValue></Rhythm>
    <Rhythm id="1"><NoteValue>32nd</NoteValue></Rhythm>
  </Rhythms>
</GPIF>
"""


@pytest.mark.parametrize(("kind", "grace_at", "main_at"), [
    ("BeforeBeat", 0.5 - 0.0625, 0.5),  # takes the end of the previous beat
    ("OnBeat", 0.5, 0.5 + 0.0625),  # delays the beat it belongs to
])
def test_gp7_grace_notes_take_no_time_of_the_bar(
    tmp_path: Path, kind: str, grace_at: float, main_at: float
) -> None:
    """A grace beat is not part of the bar's rhythm (alphaTab/GP): counting it
    shifted every later note by the grace's length. It is a short note of its own."""
    path = tmp_path / "grace.gp"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("VERSION", "7.0")
        z.writestr("Content/score.gpif", GRACE_GPIF.format(kind=kind))
    parsed = parse_gp_track(path, 0)
    times = {n.fret: n.time for n in parsed.notes}
    assert times[3] == pytest.approx(0.0)
    assert times[5] == pytest.approx(grace_at)
    assert times[7] == pytest.approx(main_at)


def test_let_ring_as_a_child_of_the_note_is_read(tmp_path: Path) -> None:
    """Guitar Pro 8 and alphaTab write let ring as <LetRing/> inside the <Note>,
    not as a Property; it was missed (344 notes of one track in a real file)."""
    first = '<Property name="Fret"><Fret>7</Fret></Property></Properties></Note>\n    <Note id="1">'
    gpif = TIE_GPIF.replace(first, first.replace("</Properties>", "</Properties><LetRing/>"))
    assert gpif != TIE_GPIF
    path = tmp_path / "let_ring.gp"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("VERSION", "7.0")
        z.writestr("Content/score.gpif", gpif)
    (note,) = parse_gp_track(path, 0).notes
    assert Technique.LET_RING in note.techniques
