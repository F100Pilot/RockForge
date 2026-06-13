"""Vocals (lyrics) support: LRC parsing and the Rocksmith vocals XML.

The vocals XML format (<vocals><vocal time note length lyric/></vocals>) is
documented de facto in community tooling (rs-utils, Rocksmith2014.NET's
Vocals module); note 254 is the conventional value for non-pitched vocals.
There is no official spec — validate in DLC Builder.

Lyric timing sources, by reliability:
- LRC file ([mm:ss.xx] lines): timestamps authored against the actual
  recording — preferred.
- UltraStar TXT (UltraStar Creator/USDX): per-syllable timing in beats,
  converted via BPM/GAP — preferred when per-word sync is needed.
- Guitar Pro lyrics: anchored only to a starting measure; line-level timing
  derived from the score (HEURISTIC, no per-word sync).

Rocksmith's vocals XML is per-syllable: each <vocal> is one word/syllable, and
a trailing "+" on the lyric text marks the end of a displayed line (the
in-game lyric display starts a new line after such an event). `expand_to_words`
turns line-level events (from LRC or GP lyrics) into this per-word form.
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
_USTAR_NOTE = re.compile(r"^([:*FRG])\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s?(.*)$")
_USTAR_HEADER = re.compile(r"^#(TITLE|ARTIST|BPM|GAP)\s*:", re.IGNORECASE)


@dataclass(frozen=True)
class VocalEvent:
    time: float
    length: float
    lyric: str


def parse_lrc(text: str, offset_s: float = 0.0) -> list[VocalEvent]:
    """Parse simple LRC ([mm:ss.xx] line) into vocal events.

    Event length = gap to the next event, capped at MAX_LENGTH_S; the last
    event gets DEFAULT_LAST_LENGTH_S. These are display durations, not pitch.
    """
    stamps: list[tuple[float, str]] = []
    for line in text.splitlines():
        m = _LRC_LINE.match(line.strip())
        if not m:
            continue
        t = int(m.group(1)) * 60 + float(m.group(2)) + offset_s
        lyric = m.group(3).strip()
        if lyric:
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


def expand_to_words(events: list[VocalEvent]) -> list[VocalEvent]:
    """Split line-level events into one VocalEvent per word.

    Rocksmith vocals are per-syllable/word; a trailing "+" on the lyric marks
    the end of a displayed line. Word timings are spread evenly across the
    line's length.
    """
    out: list[VocalEvent] = []
    for e in events:
        words = e.lyric.split()
        if not words:
            continue
        word_len = e.length / len(words)
        for i, w in enumerate(words):
            lyric = f"{w}+" if i == len(words) - 1 else w
            out.append(VocalEvent(time=e.time + i * word_len, length=word_len, lyric=lyric))
    return out


def parse_ultrastar_txt(text: str, offset_s: float = 0.0) -> list[VocalEvent]:
    """Parse an UltraStar/USDX .txt lyric file (per-syllable timing).

    Timings are stored as "beats" relative to #GAP (ms of silence before beat
    0); seconds-per-beat = 15 / BPM (UltraStar's BPM is 4x the musical BPM by
    convention). A "-" line marks the end of a display line — the preceding
    syllable's lyric is suffixed with "+" to match Rocksmith's convention.
    """
    bpm = 0.0
    gap_s = 0.0
    for line in text.splitlines():
        line = line.strip()
        if line[:5].upper() == "#BPM:":
            bpm = float(line.split(":", 1)[1].strip().replace(",", "."))
        elif line[:5].upper() == "#GAP:":
            gap_s = float(line.split(":", 1)[1].strip().replace(",", ".")) / 1000.0
    if bpm <= 0.0:
        return []
    sec_per_beat = 15.0 / bpm

    # [time, length, lyric] rows; lyric is mutated in place to append "+" on line breaks.
    syllables: list[list[float | str]] = []
    for raw in text.splitlines():
        line = raw.rstrip("\r\n")
        if not line or _USTAR_HEADER.match(line):
            continue
        m = _USTAR_NOTE.match(line)
        if m:
            _kind, start, length, _pitch, lyric = m.groups()
            lyric = lyric.strip()
            if not lyric:
                continue
            time = gap_s + int(start) * sec_per_beat + offset_s
            syllables.append([time, max(0.1, float(length) * sec_per_beat), lyric])
        elif line.startswith("-"):
            if syllables:
                syllables[-1][2] = f"{syllables[-1][2]}+"
        elif line.startswith("E"):
            break

    return [
        VocalEvent(time=float(t), length=float(ln), lyric=str(lyric))
        for t, ln, lyric in syllables
    ]


def parse_lyrics(text: str, offset_s: float = 0.0) -> list[VocalEvent]:
    """Parse a lyrics file, auto-detecting UltraStar TXT vs LRC.

    UltraStar files are already per-syllable; LRC files are line-level and get
    expanded to one event per word via `expand_to_words`.
    """
    if any(_USTAR_HEADER.match(line.strip()) for line in text.splitlines()):
        return parse_ultrastar_txt(text, offset_s)
    return expand_to_words(parse_lrc(text, offset_s))


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
