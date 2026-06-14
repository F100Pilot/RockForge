import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from rockforge.infrastructure.rsxml.vocals import (
    VocalEvent,
    events_from_dicts,
    expand_to_words,
    parse_lrc,
    parse_lyrics,
    parse_ultrastar_txt,
    write_vocals_xml,
)

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
