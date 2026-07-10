import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from rockforge.infrastructure.rsxml.vocals import (
    VocalEvent,
    distribute_syllables,
    enforce_max_line_words,
    events_from_dicts,
    expand_to_words,
    parse_lrc,
    parse_lyrics,
    parse_ultrastar_txt,
    write_vocals_xml,
)


def _words(text: str) -> list[VocalEvent]:
    return [VocalEvent(time=float(i), length=0.5, lyric=w) for i, w in enumerate(text.split())]


def test_enforce_max_line_words_breaks_long_lines() -> None:
    # A 16-word line with no break gets a "+" every max_words (7 here); the final
    # word is left to the source (the cap only splits over-long lines, it doesn't
    # add a trailing line-end).
    events = enforce_max_line_words(_words("a b c d e f g h i j k l m n o p"), max_words=7)
    breaks = [i for i, e in enumerate(events) if e.lyric.endswith("+")]
    assert breaks == [6, 13]  # after word 7, then word 14 (words 15-16 remain)


def test_enforce_max_line_words_keeps_authored_breaks_and_short_lines() -> None:
    events = enforce_max_line_words(
        [VocalEvent(time=0, length=0.5, lyric="short"),
         VocalEvent(time=1, length=0.5, lyric="line+"),
         VocalEvent(time=2, length=0.5, lyric="ok")],
        max_words=7,
    )
    # The authored "+" is kept; a short line is untouched; the counter reset after it.
    assert [e.lyric for e in events] == ["short", "line+", "ok"]


def test_enforce_max_line_words_never_breaks_mid_word() -> None:
    # A syllable-join "-" must not receive a "+" (it would split the word).
    events = enforce_max_line_words(
        [VocalEvent(time=float(i), length=0.5, lyric=("syl-" if i == 6 else f"w{i}"))
         for i in range(9)],
        max_words=7,
    )
    assert events[6].lyric == "syl-"  # not "syl-+"

LRC = """
[ar:Band]
[00:12.50]First line
[00:15.00]Second line
[01:02.25]Last line
not a timestamp
"""


def test_parse_lrc_times_and_lengths() -> None:
    events = parse_lrc(LRC)
    assert [e.lyric for e in events] == ["First line", "Second line", "Last line"]
    assert events[0].time == 12.5
    assert events[0].length == 2.5  # gap to next
    assert events[1].time == 15.0
    assert events[1].length == 4.0  # capped at MAX_LENGTH_S
    assert events[2].length == 2.0  # default for last


def test_parse_lrc_offset() -> None:
    events = parse_lrc(LRC, offset_s=0.5)
    assert events[0].time == 13.0


def test_expand_to_words_splits_lines_and_marks_end() -> None:
    events = expand_to_words([VocalEvent(time=10.0, length=2.0, lyric="hello world")])
    assert [e.lyric for e in events] == ["hello", "world+"]
    assert events[0].time == pytest.approx(10.0)
    assert events[1].time == pytest.approx(11.0)
    assert events[0].length == pytest.approx(1.0)


def test_expand_to_words_single_word_gets_line_break() -> None:
    events = expand_to_words([VocalEvent(time=1.0, length=2.0, lyric="hello")])
    assert events == [VocalEvent(time=1.0, length=2.0, lyric="hello+")]


def test_distribute_syllables_aligns_to_note_onsets() -> None:
    # "loo-king a-way" over four note onsets: one syllable per note.
    onsets = [10.0, 11.0, 12.0, 13.0, 14.0]
    events = distribute_syllables([(10.0, "loo-king a-way")], onsets)
    assert [e.lyric for e in events] == ["loo-", "king", "a-", "way+"]
    assert [e.time for e in events] == [10.0, 11.0, 12.0, 13.0]
    assert events[0].length == pytest.approx(1.0)  # gap to next onset


def test_distribute_syllables_two_lines_start_at_their_measures() -> None:
    onsets = [5.0, 6.0, 20.0, 21.0]
    events = distribute_syllables(
        [(5.0, "first line"), (20.0, "second line")], onsets
    )
    assert [(e.time, e.lyric) for e in events] == [
        (5.0, "first"),
        (6.0, "line+"),
        (20.0, "second"),
        (21.0, "line+"),
    ]


def test_distribute_syllables_runs_out_of_notes_gracefully() -> None:
    # More syllables than onsets: the overflow falls back to a default spread.
    events = distribute_syllables([(0.0, "a b c")], [0.0])
    assert [e.lyric for e in events] == ["a", "b", "c+"]
    assert events[0].time == 0.0
    assert events[1].time > events[0].time and events[2].time > events[1].time


def test_distribute_syllables_no_lyrics_no_events() -> None:
    assert distribute_syllables([(0.0, "   ")], [1.0, 2.0]) == []


def test_distribute_syllables_melisma_extends_previous() -> None:
    # GP "_" = melisma: hold the previous syllable over the next note attack
    # instead of singing a new syllable.
    onsets = [0.0, 1.0, 2.0, 3.0]
    events = distribute_syllables([(0.0, "hold _ _ next")], onsets)
    assert [e.lyric for e in events] == ["hold", "next+"]
    assert events[0].time == 0.0
    assert events[0].length == pytest.approx(3.0)  # held over the two "_" notes
    assert events[1].time == 3.0


def test_parse_lyrics_lrc_expands_to_words() -> None:
    events = parse_lyrics(LRC)
    assert [e.lyric for e in events] == ["First", "line+", "Second", "line+", "Last", "line+"]


ULTRASTAR_TXT = """\
#TITLE:Song
#ARTIST:Band
#BPM:120
#GAP:1000
: 0 4 60 Hel
: 4 4 62 lo
- 8
: 8 8 60 world
E
"""


def test_parse_ultrastar_txt_converts_beats_to_seconds() -> None:
    events = parse_ultrastar_txt(ULTRASTAR_TXT)
    # sec_per_beat = 15 / 120 = 0.125; gap = 1.0s
    assert [e.lyric for e in events] == ["Hel", "lo+", "world"]
    assert events[0].time == pytest.approx(1.0)
    assert events[0].length == pytest.approx(0.5)
    assert events[1].time == pytest.approx(1.5)
    assert events[2].time == pytest.approx(2.0)
    assert events[2].length == pytest.approx(1.0)


def test_parse_ultrastar_txt_offset() -> None:
    events = parse_ultrastar_txt(ULTRASTAR_TXT, offset_s=0.5)
    assert events[0].time == pytest.approx(1.5)


def test_parse_lyrics_detects_ultrastar() -> None:
    events = parse_lyrics(ULTRASTAR_TXT)
    assert [e.lyric for e in events] == ["Hel", "lo+", "world"]


def test_events_from_dicts_basic_mapping() -> None:
    rows: list[dict[str, object]] = [{"time": 1.0, "length": 0.5, "lyric": "hello+"}]
    assert events_from_dicts(rows) == [VocalEvent(time=1.0, length=0.5, lyric="hello+")]


def test_events_from_dicts_applies_offset() -> None:
    rows: list[dict[str, object]] = [{"time": 1.0, "length": 0.5, "lyric": "hi"}]
    events = events_from_dicts(rows, offset_s=1.5)
    assert events[0].time == pytest.approx(2.5)


def test_events_from_dicts_sorts_by_time() -> None:
    rows: list[dict[str, object]] = [
        {"time": 2.0, "length": 0.5, "lyric": "second"},
        {"time": 1.0, "length": 0.5, "lyric": "first"},
    ]
    events = events_from_dicts(rows)
    assert [e.lyric for e in events] == ["first", "second"]


def test_events_from_dicts_drops_empty_lyric_rows() -> None:
    rows: list[dict[str, object]] = [
        {"time": 1.0, "length": 0.5, "lyric": "  "},
        {"time": 2.0, "length": 0.5, "lyric": "kept"},
    ]
    events = events_from_dicts(rows)
    assert [e.lyric for e in events] == ["kept"]


def test_events_from_dicts_clamps_length_minimum() -> None:
    rows: list[dict[str, object]] = [{"time": 1.0, "length": 0.0, "lyric": "x"}]
    assert events_from_dicts(rows)[0].length == pytest.approx(0.1)


def test_write_vocals_xml(tmp_path: Path) -> None:
    out = write_vocals_xml(
        [VocalEvent(time=1.0, length=2.0, lyric="word")], tmp_path / "v.xml"
    )
    root = ET.parse(out).getroot()
    assert root.tag == "vocals" and root.get("count") == "1"
    v = root.find("vocal")
    assert v is not None
    assert v.get("lyric") == "word" and v.get("note") == "254"
