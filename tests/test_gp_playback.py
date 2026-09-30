"""Bars in the order they are played: repeats, voltas and jumps unrolled.

The expected orders are what alphaTab 1.8.4's MidiFileGenerator plays for the
same bars (checked against it for every case below, and for alphaTab's own
test-data/guitarpro5/directions.gp5).
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import guitarpro as gp
import pytest

from rockforge.domain.errors import IngestionError
from rockforge.infrastructure.gpexport.tempo_writer import TempoCorrection, write_tempo_corrections
from rockforge.infrastructure.gpimport.parser import parse_gp_track
from rockforge.infrastructure.gpimport.playback import BarFlow, playback_order

START = BarFlow(repeat_start=True)


def _flow(count: int = 0, endings: int = 0, start: bool = False, *directions: str) -> BarFlow:
    return BarFlow(start, count, endings, frozenset(directions))


def _to(*directions: str, start: bool = False) -> BarFlow:
    return _flow(0, 0, start, *directions)


A_B_A_C = [(0.0, 0), (2.0, 1), (4.0, 0), (6.0, 2)]  # (time, fret): |: A [1. B :| [2. C


@pytest.mark.parametrize(
    ("bars", "expected"),
    [
        ([START, _flow(2), _flow()], [0, 1, 0, 1, 2]),
        ([START, _flow(3), _flow()], [0, 1, 0, 1, 0, 1, 2]),
        ([START, _flow(2, 1), _flow(0, 2), _flow()], [0, 1, 0, 2, 3]),  # 1st / 2nd ending
        ([START, _flow(3, 3), _flow(0, 4), _flow()], [0, 1, 0, 1, 0, 2, 3]),  # 1.-2. / 3.
        ([START, _flow(2, 0, True), _flow(2), _flow()], [0, 1, 1, 2, 0, 1, 1, 2, 3]),  # nested
        ([_flow(2, 0, True), _flow(2), _flow()], [0, 0, 1, 0, 0, 1, 2]),  # two closings
        ([_flow(), _flow(2), _flow()], [0, 1, 0, 1, 2]),  # repeat end without a start
        ([_flow(), _to("TargetFine"), _to("JumpDaCapoAlFine"), _flow()], [0, 1, 2, 0, 1]),
        ([_flow(), _to("TargetSegno"), _to("JumpDaCoda"), _to("JumpDalSegnoAlCoda"),
          _to("TargetCoda"), _flow(), _flow()], [0, 1, 2, 3, 1, 2, 4, 5, 6]),
        ([_flow(2, 0, True), _to("JumpDaCapo"), _flow()], [0, 0, 1, 0, 1, 2]),
        ([_to("TargetSegno", start=True), _flow(2, 1), _flow(0, 2), _to("JumpDalSegno"),
          _flow(), _flow()], [0, 1, 0, 2, 3, 0, 1, 2, 3, 4, 5]),  # after a jump: no repeats
        ([_flow(), _flow()], [0, 1]),
    ],
)
def test_playback_order_is_alphatabs(bars: list[BarFlow], expected: list[int]) -> None:
    assert playback_order(bars) == expected


def test_a_repeat_forever_is_bounded() -> None:
    assert len(playback_order([START, _flow(10_000)])) <= 2 * 64


def _gp5(tmp_path: Path, bars: int, headers: dict[int, dict]) -> Path:
    """One whole note per bar at 120 BPM (2 s), fret = the written bar's index."""
    song = gp.Song()
    song.title, song.artist, song.tempo = "Repeats", "B", 120
    for _ in range(1, bars):
        song.newMeasure()
    for i, measure in enumerate(song.tracks[0].measures):
        beat = gp.Beat(measure.voices[0])
        beat.status, beat.duration = gp.BeatStatus.normal, gp.Duration(value=1)
        note = gp.Note(beat)
        note.string, note.value = 1, i
        beat.notes.append(note)
        measure.voices[0].beats = [beat]
    for i, header in enumerate(song.measureHeaders):
        for key, value in headers.get(i, {}).items():
            setattr(header, key, value)
    path = tmp_path / "repeats.gp5"
    gp.write(song, str(path))
    return path


def test_gp5_repeats_and_voltas_are_played(tmp_path: Path) -> None:
    """|: A [1. B :| [2. C — the chart plays A B A C, each bar 2 s later, with
    the section and the beat grid following the bars as heard."""
    path = _gp5(tmp_path, 3, {
        0: {"isRepeatOpen": True, "marker": gp.Marker(title="Verse")},
        1: {"repeatAlternative": 1, "repeatClose": 1},
        2: {"repeatAlternative": 2},
    })
    parsed = parse_gp_track(path, 0)
    assert [(round(n.time, 3), n.fret) for n in parsed.notes] == A_B_A_C
    assert [(s.name, s.start_time) for s in parsed.sections] == [("Verse", 0.0), ("Verse", 4.0)]
    downbeats = [b.measure for b in parsed.tempo_map.beats if b.measure > 0]
    assert downbeats[:4] == [1, 2, 3, 4]


def test_gp5_da_capo_al_fine(tmp_path: Path) -> None:
    path = _gp5(tmp_path, 3, {
        1: {"direction": gp.DirectionSign("Fine")},
        2: {"fromDirection": gp.DirectionSign("Da Capo al Fine")},
    })
    assert [n.fret for n in parse_gp_track(path, 0).notes] == [0, 1, 2, 0, 1]


def test_gp5_a_lyric_line_starts_again_on_every_pass(tmp_path: Path) -> None:
    path = _gp5(tmp_path, 3, {0: {"isRepeatOpen": True}, 1: {"repeatClose": 1}})
    song = gp.parse(str(path))
    song.lyrics.trackChoice = 1
    song.lyrics.lines[0] = gp.LyricLine(1, "la la")  # GP5 holds exactly 5 lines
    gp.write(song, str(path))
    assert [line.time for line in parse_gp_track(path, 0).lyrics] == [0.0, 4.0]


_GPIF = """<?xml version="1.0" encoding="utf-8"?>
<GPIF>
  <Score><Title>T</Title><Artist>A</Artist><Album>B</Album></Score>
  <MasterTrack><Automations>
    <Automation><Type>Tempo</Type><Bar>0</Bar><Position>0</Position>
      <Value>120 2</Value></Automation>
    {sync}
  </Automations></MasterTrack>
  <Tracks><Track id="0"><Name>Guitar</Name>
    <InstrumentSet><Type>electricGuitar</Type></InstrumentSet>
    <Staves><Staff><Properties>
      <Property name="Tuning"><Pitches>40 45 50 55 59 64</Pitches></Property>
    </Properties></Staff></Staves></Track></Tracks>
  <MasterBars>
    <MasterBar><Time>4/4</Time><Bars>0</Bars>
      <Repeat start="true" end="false" count="0"/></MasterBar>
    <MasterBar><Time>4/4</Time><Bars>1</Bars><Repeat start="false" end="true" count="2"/>
      <AlternateEndings>1</AlternateEndings></MasterBar>
    <MasterBar><Time>4/4</Time><Bars>2</Bars><AlternateEndings>2</AlternateEndings></MasterBar>
  </MasterBars>
  <Bars>
    <Bar id="0"><Voices>0 -1 -1 -1</Voices></Bar>
    <Bar id="1"><Voices>1 -1 -1 -1</Voices></Bar>
    <Bar id="2"><Voices>2 -1 -1 -1</Voices></Bar>
  </Bars>
  <Voices>
    <Voice id="0"><Beats>0</Beats></Voice><Voice id="1"><Beats>1</Beats></Voice>
    <Voice id="2"><Beats>2</Beats></Voice>
  </Voices>
  <Beats>
    <Beat id="0"><Rhythm ref="0"/><Notes>0</Notes></Beat>
    <Beat id="1"><Rhythm ref="0"/><Notes>1</Notes></Beat>
    <Beat id="2"><Rhythm ref="0"/><Notes>2</Notes></Beat>
  </Beats>
  <Notes>
    <Note id="0"><Properties><Property name="String"><String>0</String></Property>
      <Property name="Fret"><Fret>0</Fret></Property></Properties></Note>
    <Note id="1"><Properties><Property name="String"><String>0</String></Property>
      <Property name="Fret"><Fret>1</Fret></Property></Properties></Note>
    <Note id="2"><Properties><Property name="String"><String>0</String></Property>
      <Property name="Fret"><Fret>2</Fret></Property></Properties></Note>
  </Notes>
  <Rhythms><Rhythm id="0"><NoteValue>Whole</NoteValue></Rhythm></Rhythms>
</GPIF>
"""


def _gp7(tmp_path: Path, sync: str = "") -> Path:
    path = tmp_path / "repeats.gp"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("VERSION", "7.0")
        z.writestr("Content/score.gpif", _GPIF.format(sync=sync))
    return path


def _sync_point(bar: int, occurrence: int, seconds: float) -> str:
    frame = int(seconds * 44100)
    return (f"<Automation><Type>SyncPoint</Type><Bar>{bar}</Bar><Position>0</Position><Value>"
            f"<BarIndex>{bar}</BarIndex><BarOccurrence>{occurrence}</BarOccurrence>"
            f"<FrameOffset>{frame}</FrameOffset></Value></Automation>")


def test_gp7_repeats_and_voltas_are_played(tmp_path: Path) -> None:
    parsed = parse_gp_track(_gp7(tmp_path), 0)
    assert [(round(n.time, 3), n.fret) for n in parsed.notes] == A_B_A_C


def test_gp8_sync_point_on_a_second_pass_is_used(tmp_path: Path) -> None:
    """A sync point on bar 1's SECOND pass pins the 3rd played bar (it used to be
    dropped: repeats were not unrolled)."""
    sync = _sync_point(0, 0, 0.0) + _sync_point(0, 1, 5.0)  # the 2nd pass comes 1 s late
    parsed = parse_gp_track(_gp7(tmp_path, sync), 0)
    times = [round(n.time, 3) for n in parsed.notes]
    assert times[2] == pytest.approx(5.0)
    assert not any("ignored" in w for w in parsed.warnings)


def test_tempo_corrections_go_to_the_written_bar_of_a_played_bar(tmp_path: Path) -> None:
    """The user numbers bars as played; played bar 4 is written bar 3 (A B A C)."""
    src = _gp5(tmp_path, 3, {
        0: {"isRepeatOpen": True}, 1: {"repeatAlternative": 1, "repeatClose": 1},
        2: {"repeatAlternative": 2},
    })
    dst = tmp_path / "out.gp5"
    applied = write_tempo_corrections(src, dst, [TempoCorrection(measure=4, bpm=90.0)])
    assert [(a.measure, a.written_bpm) for a in applied] == [(4, 90.0)]
    song = gp.parse(str(dst))
    beat = song.tracks[0].measures[2].voices[0].beats[0]
    assert beat.effect.mixTableChange.tempo.value == 90
    # passes of one written bar cannot hold two tempos
    with pytest.raises(IngestionError, match="same written measure 1"):
        write_tempo_corrections(
            src, tmp_path / "bad.gp5",
            [TempoCorrection(measure=1, bpm=90.0), TempoCorrection(measure=3, bpm=100.0)],
        )
