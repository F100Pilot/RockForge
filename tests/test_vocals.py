import xml.etree.ElementTree as ET
from pathlib import Path

from rockforge.infrastructure.rsxml.vocals import VocalEvent, parse_lrc, write_vocals_xml

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


def test_write_vocals_xml(tmp_path: Path) -> None:
    out = write_vocals_xml(
        [VocalEvent(time=1.0, length=2.0, lyric="word")], tmp_path / "v.xml"
    )
    root = ET.parse(out).getroot()
    assert root.tag == "vocals" and root.get("count") == "1"
    v = root.find("vocal")
    assert v is not None
    assert v.get("lyric") == "word" and v.get("note") == "254"
