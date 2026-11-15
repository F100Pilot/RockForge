"""A bar or beat inserted into a chart's grid or removed from it ("Compassos a
mais ou a menos"): the grid, how every other time moves, the build applying it
in its place among the sync rounds, and the API storing it as such a round.
The same cases are checked on the viewer's copy in tests/web/bar-edits.test.js.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from rockforge.application.gp_pipeline import (
    ArrangementSync,
    GpJobSpec,
    _apply_bar_edit,
)
from rockforge.domain.arrangement import SongMetadata
from rockforge.domain.bar_edits import BarEdit, bar_edit_from_stage, edit_grid, source_bars
from rockforge.domain.errors import IngestionError
from rockforge.domain.music import Beat, TabNote, TempoMap, Tuning
from rockforge.infrastructure.gpimport.parser import (
    GpLyricLine,
    GpSection,
    LyricNote,
    ParsedGpTrack,
)


def _grid(bars: int = 3, beats: int = 4, start: float = 2.0, beat_s: float = 0.5) -> list[Beat]:
    """``bars`` bars of ``beats`` beats from ``start``, and the closing bar line."""
    grid = [
        Beat(time=start + (b * beats + k) * beat_s, measure=b + 1 if k == 0 else -1)
        for b in range(bars) for k in range(beats)
    ]
    grid.append(Beat(time=start + bars * beats * beat_s, measure=bars + 1))
    return grid


def _shape(grid: list[Beat]) -> list[tuple[float, int]]:
    return [(round(b.time, 6), b.measure) for b in grid]


def test_a_bar_inserted_after_a_bar_copies_its_beats_and_moves_what_follows() -> None:
    # Bar 2 has a beat of its own spacing (a 3/4 bar of 0.6 s beats): the new
    # bar takes bar 2's beats, not bar 1's.
    grid = _grid()
    grid = grid[:4] + [Beat(4.0, 2), Beat(4.6, -1), Beat(5.2, -1)] + [
        Beat(5.8 + 0.5 * k, 3 if k == 0 else -1) for k in range(4)] + [Beat(7.8, 4)]
    new, steps = edit_grid(grid, BarEdit("insert_bar", bar=2))
    assert [(s.start, round(s.length, 6), s.insert) for s in steps] == [(5.8, 1.8, True)]
    assert _shape(new)[4:12] == [
        (4.0, 2), (4.6, -1), (5.2, -1),
        (5.8, 3), (6.4, -1), (7.0, -1),   # the inserted bar, bar 2's beats
        (7.6, 4), (8.1, -1),              # the old bar 3, moved and renumbered
    ]
    assert _shape(new)[-1] == (9.6, 5)    # the closing line too


def test_a_bar_inserted_before_bar_one_takes_bar_ones_length() -> None:
    new, steps = edit_grid(_grid(), BarEdit("insert_bar", bar=0, count=2))
    assert [(s.start, s.length) for s in steps] == [(2.0, 2.0), (2.0, 2.0)]
    assert [b.measure for b in new if b.measure > 0] == [1, 2, 3, 4, 5, 6]
    assert new[0].time == 2.0 and new[-1].time == 12.0


def test_a_removed_bar_brings_the_rest_back_by_its_length() -> None:
    new, steps = edit_grid(_grid(), BarEdit("remove_bar", bar=2))
    assert [(s.start, s.length, s.insert) for s in steps] == [(4.0, 2.0, False)]
    assert _shape(new) == [(2.0, 1), (2.5, -1), (3.0, -1), (3.5, -1),
                           (4.0, 2), (4.5, -1), (5.0, -1), (5.5, -1), (6.0, 3)]
    # The last bar: the closing line comes back to its start.
    last, _ = edit_grid(_grid(), BarEdit("remove_bar", bar=3))
    assert _shape(last)[-1] == (6.0, 3)


def test_a_beat_inserted_or_removed_changes_only_its_bar() -> None:
    added, steps = edit_grid(_grid(), BarEdit("insert_beat", bar=1, beat=4))
    assert [(s.start, s.length) for s in steps] == [(4.0, 0.5)]
    assert _shape(added)[:6] == [(2.0, 1), (2.5, -1), (3.0, -1), (3.5, -1), (4.0, -1), (4.5, 2)]
    # The downbeat taken out: the beat after it opens the bar.
    gone, steps = edit_grid(_grid(), BarEdit("remove_beat", bar=2, beat=1))
    assert [(s.start, s.length) for s in steps] == [(4.0, 0.5)]
    assert _shape(gone)[3:8] == [(3.5, -1), (4.0, 2), (4.5, -1), (5.0, -1), (5.5, 3)]


def test_an_edit_that_names_nothing_is_refused() -> None:
    for edit in (BarEdit("remove_bar", bar=9), BarEdit("insert_beat", bar=1, beat=5),
                 BarEdit("insert_bar", bar=3 + 1)):
        with pytest.raises(ValueError):
            edit_grid(_grid(), edit)
    with pytest.raises(ValueError):
        edit_grid(_grid(bars=1), BarEdit("remove_bar", bar=1))
    single = [Beat(2.0, 1), Beat(2.5, 2)]
    with pytest.raises(ValueError):
        edit_grid(single, BarEdit("remove_beat", bar=1, beat=1))
    for bad in ({"op": "nope", "bar": 1}, {"op": "insert_bar", "bar": -1},
                {"op": "remove_bar", "bar": 0}, {"op": "insert_bar", "bar": 1, "count": 17},
                {"op": "insert_bar", "bar": True}):
        with pytest.raises(ValueError):
            bar_edit_from_stage({"bar_edit": bad})
    assert bar_edit_from_stage([[1.0, 2.0]]) is None


def test_the_score_bar_each_built_bar_came_from() -> None:
    edits = [BarEdit("insert_bar", bar=2), BarEdit("remove_bar", bar=5, count=2)]
    assert source_bars(6, edits) == [1, 2, None, 3, 6, 7]
    assert source_bars(6, []) == [1, 2, 3, 4, 5, 6]
    assert source_bars(2, [BarEdit("remove_bar", bar=9)]) is None


def _track() -> ParsedGpTrack:
    return ParsedGpTrack(
        notes=[
            TabNote(string=0, fret=3, time=2.0, sustain=0.4),
            TabNote(string=0, fret=5, time=3.5, sustain=0.5),   # rings to bar 2's line
            TabNote(string=1, fret=7, time=3.5, sustain=1.0),   # rings into bar 2
            TabNote(string=0, fret=8, time=4.0, sustain=0.4),   # on bar 2's downbeat
            TabNote(string=0, fret=9, time=5.0, sustain=0.4),
            TabNote(string=0, fret=10, time=6.0, sustain=0.4),
        ],
        tuning=Tuning(),
        tempo_map=TempoMap(beats=tuple(_grid()), average_bpm=120.0),
        sections=[GpSection("Intro", 2.0), GpSection("Verse", 4.0), GpSection("Chorus", 6.0)],
        lyrics=[GpLyricLine(time=4.0, text="la la")],
        lyric_notes=(LyricNote(time=4.0, end=4.5), LyricNote(time=6.0, end=6.5)),
    )


def test_an_inserted_bar_moves_everything_from_its_line_on() -> None:
    warnings: list[str] = []
    out = _apply_bar_edit(_track(), BarEdit("insert_bar", bar=1), "Lead", warnings)
    assert [(n.time, round(n.sustain, 6)) for n in out.notes] == [
        (2.0, 0.4), (3.5, 0.5),   # ends on the line: not stretched over the new bar
        (3.5, 3.0),               # rang past it: rings through the new bar
        (6.0, 0.4), (7.0, 0.4), (8.0, 0.4),
    ]
    assert [s.start_time for s in out.sections] == [2.0, 6.0, 8.0]
    assert [line.time for line in out.lyrics] == [6.0]
    assert out.lyric_notes == (LyricNote(time=6.0, end=6.5), LyricNote(time=8.0, end=8.5))
    assert warnings == ["Lead: a bar inserted after bar 1"]


def test_a_removed_bar_takes_its_notes_and_its_section_goes_to_the_next() -> None:
    warnings: list[str] = []
    out = _apply_bar_edit(_track(), BarEdit("remove_bar", bar=2), "Lead", warnings)
    assert [(n.fret, n.time, round(n.sustain, 6)) for n in out.notes] == [
        (3, 2.0, 0.4),
        (5, 3.5, 0.45),          # the next note on its string is now right after it
        (7, 3.5, 0.5),           # cut where the removed bar began
        (10, 4.0, 0.4),
    ]
    # "Verse" was the removed bar's: "Chorus" now starts there.
    assert [(s.name, s.start_time) for s in out.sections] == [("Intro", 2.0), ("Chorus", 4.0)]
    assert out.lyric_notes == (LyricNote(time=4.0, end=4.5),)
    assert warnings == ["Lead: a bar removed from bar 2 (2 note(s) in it removed)"]


def test_an_edit_the_chart_cannot_take_says_which_and_what_to_do() -> None:
    with pytest.raises(IngestionError, match="Rhythm: cannot apply .*bar 9"):
        _apply_bar_edit(_track(), BarEdit("remove_bar", bar=9), "Rhythm", [])


def _built(tmp_path: Path, stages: list) -> ET.Element:
    from rockforge.infrastructure.example_song import write_example_gp5
    from test_gp_pipeline import make_use_case

    tmp_path.mkdir(parents=True, exist_ok=True)
    gp5 = write_example_gp5(tmp_path / "ex.gp5", "Ex", "RockForge")
    spec = GpJobSpec(
        gp_path=gp5, audio_source="x.wav", lead_track=0,
        arrangement_sync={"Combined": ArrangementSync(sync_anchor_stages=stages)},
    )
    result = make_use_case().run(spec, SongMetadata(title="Ex", artist="RF"), tmp_path / "w")
    xml = next(p for p in result.packaging.xml_paths if "vocals" not in p.name)
    return ET.parse(xml).getroot()


def _bars(root: ET.Element) -> list[tuple[int, float]]:
    return [(int(e.get("measure", "-1")), float(e.get("time", "0")))
            for e in root.findall("ebeats/ebeat") if int(e.get("measure", "-1")) > 0]


def _note_times(root: ET.Element) -> list[float]:
    times = [float(n.get("time", "0")) for n in root.findall("levels/level/notes/note")]
    times += [float(c.get("time", "0")) for c in root.findall("levels/level/chords/chord")]
    return sorted(times)


def test_the_build_applies_a_bar_edit_in_its_place_among_the_sync_rounds(tmp_path: Path) -> None:
    plain = _built(tmp_path / "a", [])
    bars = _bars(plain)
    bar = bars[1][1] - bars[0][1]   # 100 BPM, 4/4: 2.4 s
    assert bar == pytest.approx(2.4, abs=1e-3)
    # A round that moves everything 1 s later, then a bar after bar 4 — named in
    # the timeline that round left — then a round in the timeline the bar left.
    t5 = bars[4][1]
    edited = _built(tmp_path / "b", [
        [(0.0, 1.0)],
        BarEdit("insert_bar", bar=4),
        [(t5 + 1.0 + bar, t5 + 1.0 + bar + 0.5)],
    ])
    got = _bars(edited)
    assert len(got) == len(bars) + 1
    assert [m for m, _ in got] == list(range(1, len(got) + 1))
    assert got[4][1] == pytest.approx(t5 + 1.0 + 0.5, abs=2e-3)   # the inserted bar
    assert got[5][1] == pytest.approx(t5 + 1.0 + bar + 0.5, abs=2e-3)  # old bar 5
    before, after = _note_times(plain), _note_times(edited)
    assert len(after) == len(before)
    early = [t for t in before if t < t5 - 1e-3]
    assert after[:len(early)] == pytest.approx([t + 1.5 for t in early], abs=2e-3)
    assert after[len(early):] == pytest.approx(
        [t + 1.5 + bar for t in before[len(early):]], abs=2e-3)


def test_a_removed_bar_is_gone_from_the_built_chart(tmp_path: Path) -> None:
    plain = _built(tmp_path / "a", [])
    edited = _built(tmp_path / "b", [BarEdit("remove_bar", bar=3)])
    bars = _bars(plain)
    assert len(_bars(edited)) == len(bars) - 1
    t3, t4 = bars[2][1], bars[3][1]
    before = _note_times(plain)
    kept = [t for t in before if not t3 - 1e-3 <= t < t4 - 1e-3]
    assert _note_times(edited) == pytest.approx(
        [t if t < t3 else t - (t4 - t3) for t in kept], abs=2e-3)
