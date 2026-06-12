"""Vocals (lyrics) support: LRC parsing and the Rocksmith vocals XML.

The vocals XML format (<vocals><vocal time note length lyric/></vocals>) is
documented de facto in community tooling (rs-utils, Rocksmith2014.NET's
Vocals module); note 254 is the conventional value for non-pitched vocals.
There is no official spec — validate in DLC Builder.

Lyric timing sources, by reliability:
- LRC file ([mm:ss.xx] lines): timestamps authored against the actual
  recording — preferred.
- Guitar Pro lyrics: anchored only to a starting measure; line-level timing
  derived from the score (HEURISTIC, no per-word sync).
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

VOCAL_NOTE = 254
DEFAULT_LAST_LENGTH_S = 2.0
MAX_LENGTH_S = 4.0

_LRC_LINE = re.compile(r"\[(\d+):(\d+(?:\.\d+)?)\](.*)")


@dataclass(frozen=True)
class VocalEvent:
    time: float
    length: float
    lyric: str


def parse_lrc(text: str, offset_s: float = 0.0) -> list[VocalEvent]:
    """Parse simple LRC ([mm:ss.xx] line) into vocal events.

    Event length = gap to the next event, capped at MAX_LENGTH_S; the last
    event gets DEFAULT_LAST_LENGTH_S. These are display durations, not pitch.
    Lines that land before time 0 after applying offset_s (e.g. lyrics for a
    lead-in trimmed from the audio) are dropped.
    """
    stamps: list[tuple[float, str]] = []
    for line in text.splitlines():
        m = _LRC_LINE.match(line.strip())
        if not m:
            continue
        t = int(m.group(1)) * 60 + float(m.group(2)) + offset_s
        lyric = m.group(3).strip()
        if lyric and t >= 0:
            stamps.append((t, lyric))
    stamps.sort(key=lambda s: s[0])

    events: list[VocalEvent] = []
    for i, (t, lyric) in enumerate(stamps):
        if i + 1 < len(stamps):
            length = min(MAX_LENGTH_S, max(0.1, stamps[i + 1][0] - t))
        else:
            length = DEFAULT_LAST_LENGTH_S
        events.append(VocalEvent(time=t, length=length, lyric=lyric))
    return events


def write_vocals_xml(events: list[VocalEvent], path: Path) -> Path:
    root = ET.Element("vocals", count=str(len(events)))
    for e in sorted(events, key=lambda v: v.time):
        ET.SubElement(
            root,
            "vocal",
            time=f"{e.time:.3f}",
            note=str(VOCAL_NOTE),
            length=f"{e.length:.3f}",
            lyric=e.lyric,
        )
    tree = ET.ElementTree(root)
    ET.indent(tree)
    path.parent.mkdir(parents=True, exist_ok=True)
    tree.write(path, encoding="utf-8", xml_declaration=True)
    return path
