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
from collections.abc import Sequence
from dataclasses import dataclass, replace
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
        rest = line.strip()
        times: list[float] = []
        # a line sung several times carries every time in front of it
        # ("[00:12.00][01:10.00]chorus"): one stamp per time, the text without them
        while (m := _LRC_LINE.match(rest)) is not None:
            times.append(int(m.group(1)) * 60 + float(m.group(2)) + offset_s)
            rest = m.group(3).strip()
        if rest:
            stamps.extend((t, rest) for t in times)
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


_PRONOUN_I = {"i", "i'm", "i'll", "i've", "i'd"}


def _capitalised(text: str) -> bool:
    letters = text.lstrip("\"'“‘(¿¡[-")
    return bool(letters) and letters[0].isupper()


def _pronoun_i(text: str) -> bool:
    return text.strip("\"'“”‘’(),.!?;:+-").replace("’", "'").lower() in _PRONOUN_I


def _break_fit(events: list[VocalEvent], word_end: int) -> int:
    """How good a line break after event *word_end* is: before a capitalised
    word (not "I") best, after punctuation next, anywhere else last."""
    nxt = events[word_end + 1].lyric
    if _capitalised(nxt) and not _pronoun_i(nxt):
        return 2
    return 1 if events[word_end].lyric.rstrip("+ ")[-1:] in ",;.!?" else 0


def enforce_max_line_words(
    events: list[VocalEvent], max_words: int = MAX_LINE_WORDS
) -> list[VocalEvent]:
    """Split every line longer than ``max_words`` words into the fewest lines
    that fit, of about equal length — an 8-word line becomes 4 + 4, not 7 + an
    orphaned last word. Within two words of an even split it prefers a break
    before a capitalised word (lyrics start their lines with one; the pronoun
    "I" aside), then after punctuation. A word is counted once however many
    syllables it has (a syllable-join ``-`` is not a word end). Never removes
    an authored break, never breaks mid-word and never adds one after the very
    last event."""
    out = list(events)
    start = 0
    for i, e in enumerate(out):
        if not (e.lyric.rstrip().endswith("+") or i == len(out) - 1):
            continue
        word_ends = [
            j for j in range(start, i + 1) if not out[j].lyric.rstrip().endswith("-")
        ]
        start = i + 1
        n = len(word_ends)
        if n <= max_words:
            continue
        lines = -(-n // max_words)
        before = 0  # words already placed on earlier lines
        for k in range(1, lines):
            left = lines - k  # lines still to fill after this break
            ok = [
                c for c in (round(k * n / lines) + d for d in (0, -1, 1, -2, 2))
                if 0 < c - before <= max_words and n - c <= left * max_words
            ]
            if not ok:
                continue
            # max() keeps the first (nearest the even split) of equals.
            fits = [_break_fit(out, word_ends[c - 1]) for c in ok]
            cut = ok[fits.index(max(fits))]
            j = word_ends[cut - 1]
            out[j] = VocalEvent(time=out[j].time, length=out[j].length, lyric=out[j].lyric + "+")
            before = cut
    return out


@dataclass(frozen=True)
class _Syllable:
    text: str
    joins_next: bool = False  # same word as the next syllable (Rocksmith "-")
    is_hold: bool = False  # "_" melisma: hold the previous syllable one more note
    skip_before: int = 0  # note attacks passed over, unsung, before this one
    line_end: bool = False  # a newline in the text follows (Rocksmith "+")
    starts_word: bool = False  # the first syllable of a word


_COMMENT = re.compile(r"[ \t]*\[[^\]]*\]")
_GAP = re.compile(r"[ \t\r\n]+")


def _split_syllables(text: str) -> list[_Syllable]:
    """Split a Guitar Pro lyric line into syllables, the way Guitar Pro reads it.

    Whitespace separates *words* and a hyphen separates *syllables within a
    word* (``loo-king a-way`` → loo · king · a · way; a hyphen before a space,
    ``Mo- ney``, still joins). Each syllable takes the next note attack, and
    the text says which attacks to pass over: a run of N spaces inside a line
    skips N-1 notes, and across a line break every space on either side of the
    newline skips one (Songsterr's rule too — its tabs mark rests in a vocal
    line exactly this way). A newline also ends a display line. ``[...]`` is a
    comment, and a standalone ``_`` is a melisma (the previous syllable held
    over one more note).
    """
    out: list[_Syllable] = []
    text = _COMMENT.sub("", text)
    tokens = _GAP.split(text)
    gaps = _GAP.findall(text)
    # gaps[i] separates tokens[i] and tokens[i + 1].
    skip = 0
    for i, token in enumerate(tokens):
        if token:
            if set(token) == {"_"}:
                out.append(_Syllable("", is_hold=True, skip_before=skip))
            else:
                parts = token.split("-")
                trailing_hyphen = token.endswith("-")
                real = [p for p in parts if p and set(p) != {"_"}]
                for k, part in enumerate(real):
                    last = k == len(real) - 1
                    out.append(_Syllable(
                        part,
                        joins_next=not last or trailing_hyphen,
                        skip_before=skip if k == 0 else 0,
                        starts_word=k == 0,
                    ))
            skip = 0
        if i < len(gaps) and out:  # space before the first syllable skips nothing
            gap = gaps[i].replace("\t", " ").replace("\r", "")
            spaces = gap.count(" ")
            if "\n" in gap:
                if out[-1].text:
                    out[-1] = replace(out[-1], line_end=True, joins_next=False)
                skip += spaces
            else:
                skip += spaces - 1
    return out


def distribute_syllables(
    lines: list[tuple[float, str]],
    onsets: Sequence[float],
    *,
    ends: Sequence[float] | None = None,
    rests_before: Sequence[bool] | None = None,
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

    When the onsets are the notes of a VOCAL line, two more things are read
    from it. `ends` (when each note stops) sets how long a syllable is shown,
    instead of stretching it over the rest that follows. `rests_before` (the
    line rests before this note) finds the phrases when the text has no line
    breaks of its own (one lyric line, no newline): a word starting with a
    capital — how lyrics mark a new line — begins one when the vocal line
    rests just before it. A capital alone is not enough ("High Noon" is not
    two lines) and neither is a rest (lines are breaths, but not every breath
    is a line: "tequila (breath) with High Noon"). Lyrics with no capitals to
    go by (all lower or all upper case; the pronoun "I" does not count) break
    at every rest before a word. Never inside a word.

    Honest limit: this assumes one syllable per note attack (syllabic singing).
    Melismas (one syllable held over several notes) are not modelled — the GP
    format does not record them recoverably here — so a melismatic passage will
    drift by the number of extra notes until the next line resets it.
    """
    by_time: dict[float, tuple[float | None, bool]] = {}
    for i, t in enumerate(onsets):
        if t not in by_time:
            by_time[t] = (
                ends[i] if ends is not None else None,
                bool(rests_before[i]) if rests_before is not None else False,
            )
    grid = sorted(by_time)
    note_end = [by_time[t][0] for t in grid]
    rest = [by_time[t][1] for t in grid]

    def onset_at(idx: int, fallback: float) -> tuple[float, float]:
        """(time, length) for the note onset at *idx*: until the note ends when
        that is known, else until the next note."""
        if idx < len(grid):
            t = grid[idx]
            stop = note_end[idx]
            if stop is None:
                stop = grid[idx + 1] if idx + 1 < len(grid) else t + DEFAULT_LAST_LENGTH_S
            return t, min(MAX_LENGTH_S, max(0.1, stop - t))
        anchor = grid[-1] if grid else fallback
        return anchor + (idx - len(grid) + 1) * DEFAULT_SYLLABLE_LENGTH_S, DEFAULT_SYLLABLE_LENGTH_S

    parsed = [(line_time, _split_syllables(text)) for line_time, text in lines]
    # Phrases from the vocal line's rests only when the text does not already
    # say where its lines end: a newline in it, or lyrics written as several
    # lines (each from its own bar), are the author's own choice.
    phrasing = (
        rests_before is not None
        and sum(1 for _t, syls in parsed if syls) == 1
        and not any(syl.line_end for _t, syls in parsed for syl in syls)
    )
    words = [
        syl.text for _t, syls in parsed for syl in syls
        if syl.starts_word and not _pronoun_i(syl.text)
    ][1:]
    capitals = sum(_capitalised(w) for w in words)
    by_capitals = 0 < capitals < len(words)

    def starts_phrase(syl: _Syllable, idx: int) -> bool:
        if not (phrasing and syl.starts_word and idx < len(grid) and rest[idx]):
            return False
        return _capitalised(syl.text) if by_capitals else True

    events: list[VocalEvent] = []
    cursor = 0
    for line_time, syllables in parsed:
        if not syllables:
            continue
        first = bisect.bisect_left(grid, line_time - 1e-3)
        idx = max(cursor, first)
        # An all-melisma line (only "_" holds — the tail of a melisma spanning a
        # whole authored line) has no real syllable to carry the line-break "+";
        # last_real stays -1 and the loop just extends the previous line's last
        # syllable over these attacks instead of dropping the line entirely.
        real_indices = [i for i, s in enumerate(syllables) if not s.is_hold]
        last_real = real_indices[-1] if real_indices else -1
        for k, syl in enumerate(syllables):
            idx += syl.skip_before  # rests in the vocal line: attacks nobody sings
            t, length = onset_at(idx, line_time)
            if syl.is_hold:
                # Melisma: hold the previous syllable over this note attack.
                if events:
                    prev = events[-1]
                    events[-1] = VocalEvent(
                        prev.time, min(MAX_LENGTH_S, t + length - prev.time), prev.lyric
                    )
                idx += 1
                continue
            if events and starts_phrase(syl, idx):
                prev = events[-1]
                if not prev.lyric.endswith(("+", "-")):
                    events[-1] = VocalEvent(prev.time, prev.length, prev.lyric + "+")
            if syl.joins_next and k != last_real:
                lyric = f"{syl.text}-"
            elif syl.line_end or k == last_real:
                lyric = f"{syl.text}+"
            else:
                lyric = syl.text
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
    prev_spaced = True
    for raw in text.splitlines():
        line = raw.rstrip("\r\n")
        if not line or _USTAR_HEADER.match(line):
            continue
        m = _USTAR_NOTE.match(line)
        if m:
            _kind, start, length, _pitch, raw_lyric = m.groups()
            lyric = raw_lyric.strip()
            if not lyric:
                continue
            # UltraStar marks a word boundary with a space at the end of one
            # syllable or the start of the next; without one the syllable goes
            # on the same word, which Rocksmith writes as a trailing "-"
            # ("Hel-" "lo"), or the game shows "Hel lo"
            if syllables and not prev_spaced and not raw_lyric[:1].isspace():
                prev = str(syllables[-1][2])
                if not prev.endswith(("+", "-")):
                    syllables[-1][2] = prev + "-"
            prev_spaced = raw_lyric[-1:].isspace()
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
