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

import bisect
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from rockforge.application.ports import VocalEvent

VOCAL_NOTE = 254
DEFAULT_LAST_LENGTH_S = 2.0
MAX_LENGTH_S = 4.0

_LRC_LINE = re.compile(r"\[(\d+):(\d+(?:\.\d+)?)\](.*)")
_USTAR_NOTE = re.compile(r"^([:*FRG])\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s?(.*)$")
_USTAR_HEADER = re.compile(r"^#(TITLE|ARTIST|BPM|GAP)\s*:", re.IGNORECASE)


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


DEFAULT_SYLLABLE_LENGTH_S = 0.3

# In-game the lyric bar shows one line at a time; a long line scrolls as a wall
# of text. This caps ANY line (from detection, GP or LRC) at build time — a
# safety net so a source with coarse/long lines is still readable, independent of
# the finer per-segment breaking WhisperX detection does.
MAX_LINE_WORDS = 7


def enforce_max_line_words(
    events: list[VocalEvent], max_words: int = MAX_LINE_WORDS
) -> list[VocalEvent]:
    """Force a line break (trailing ``+``) once a line reaches ``max_words``
    without one, so no lyric line runs longer than that on screen. Never removes
    an authored break, never breaks mid-word (a syllable-join ``-``) or on the
    very last event."""
    out = list(events)
    since_break = 0
    for i, e in enumerate(out):
        stripped = e.lyric.rstrip()
        if stripped.endswith("+"):
            since_break = 0
            continue
        since_break += 1
        if stripped.endswith("-"):
            continue  # mid-word syllable — a break here would split the word
        if since_break >= max_words and i < len(out) - 1:
            out[i] = VocalEvent(time=e.time, length=e.length, lyric=e.lyric + "+")
            since_break = 0
    return out


def _split_syllables(text: str) -> list[tuple[str, bool, bool]]:
    """Split a Guitar Pro lyric line into (syllable, joins_next, is_hold) items.

    GP lyric text separates *words* by whitespace and *syllables within a word*
    by a hyphen (``loo-king a-way`` → loo · king · a · way). ``joins_next`` is
    True when the syllable connects to the following one without a space (i.e.
    they belong to the same word) — that becomes Rocksmith's trailing ``-``.
    A standalone ``_`` is a melisma marker (``is_hold`` True): the previous
    syllable is held over one more note attack instead of a new one being sung.
    """
    out: list[tuple[str, bool, bool]] = []
    for word in text.split():
        if set(word) == {"_"}:
            out.append(("", False, True))
            continue
        parts = [p for p in word.split("-") if p and set(p) != {"_"}]
        for i, p in enumerate(parts):
            out.append((p, i < len(parts) - 1, False))
    return out


def distribute_syllables(
    lines: list[tuple[float, str]], onsets: list[float]
) -> list[VocalEvent]:
    """Align Guitar Pro line lyrics to real note onsets, one syllable per note.

    `lines` are ``(line_start_time, line_text)`` in the final bundle clock;
    `onsets` are the note attack times (also bundle clock). Each line's
    syllables are placed on consecutive onsets at/after the line's start —
    replicating how Guitar Pro/Songsterr distribute lyrics across the notes —
    so the per-syllable timing matches what the GP file shows instead of an
    even spread. Rocksmith markers: a trailing ``-`` joins syllables within a
    word (no space, hyphen shown in game), a trailing ``+`` on the last
    syllable of a line is the line break.

    Honest limit: this assumes one syllable per note attack (syllabic singing).
    Melismas (one syllable held over several notes) are not modelled — the GP
    format does not record them recoverably here — so a melismatic passage will
    drift by the number of extra notes until the next line resets it.
    """
    grid = sorted(set(onsets))

    def onset_at(idx: int, fallback: float) -> tuple[float, float]:
        """(time, length) for the note onset at *idx*; length = gap to next."""
        if idx < len(grid):
            t = grid[idx]
            nxt = grid[idx + 1] if idx + 1 < len(grid) else t + DEFAULT_LAST_LENGTH_S
            return t, min(MAX_LENGTH_S, max(0.1, nxt - t))
        anchor = grid[-1] if grid else fallback
        return anchor + (idx - len(grid) + 1) * DEFAULT_SYLLABLE_LENGTH_S, DEFAULT_SYLLABLE_LENGTH_S

    events: list[VocalEvent] = []
    cursor = 0
    for line_time, text in lines:
        syllables = _split_syllables(text)
        if not any(not is_hold for _, _, is_hold in syllables):
            continue
        first = bisect.bisect_left(grid, line_time - 1e-3)
        idx = max(cursor, first)
        last_real = next(
            i for i in range(len(syllables) - 1, -1, -1) if not syllables[i][2]
        )
        for k, (syl, joins_next, is_hold) in enumerate(syllables):
            t, length = onset_at(idx, line_time)
            if is_hold:
                # Melisma: hold the previous syllable over this note attack.
                if events:
                    prev = events[-1]
                    events[-1] = VocalEvent(
                        prev.time, min(MAX_LENGTH_S, t + length - prev.time), prev.lyric
                    )
                idx += 1
                continue
            lyric = f"{syl}-" if joins_next else (f"{syl}+" if k == last_real else syl)
            events.append(VocalEvent(time=t, length=length, lyric=lyric))
            idx += 1
        cursor = idx
    events.sort(key=lambda e: e.time)
    return events


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


def events_from_dicts(rows: list[dict[str, object]], offset_s: float = 0.0) -> list[VocalEvent]:
    """Build vocal events from JSON rows (e.g. the in-app lyrics editor).

    Rows are ``{"time": ..., "length": ..., "lyric": ...}``; rows with an empty
    (after stripping) lyric are dropped, ``offset_s`` is added to ``time``, and
    the result is sorted by time. Lengths are clamped to a 0.1s minimum.
    """
    def _num(v: object) -> float:
        return float(v) if isinstance(v, (int, float, str)) else 0.0

    events: list[VocalEvent] = []
    for row in rows:
        lyric = str(row.get("lyric", "")).strip()
        if not lyric:
            continue
        time = _num(row.get("time", 0.0)) + offset_s
        length = max(0.1, _num(row.get("length", 0.0)))
        events.append(VocalEvent(time=time, length=length, lyric=lyric))
    events.sort(key=lambda e: e.time)
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
