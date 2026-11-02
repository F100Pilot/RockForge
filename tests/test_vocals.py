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
    # A 16-word line with no break becomes the fewest lines of at most
    # max_words (7 here) — three — of about equal length (5 + 6 + 5), not 7 + 7
    # + an orphaned 2; the final word is left to the source (the cap only splits
    # over-long lines, it doesn't add a trailing line-end).
    events = enforce_max_line_words(_words("a b c d e f g h i j k l m n o p"), max_words=7)
    breaks = [i for i, e in enumerate(events) if e.lyric.endswith("+")]
    assert breaks == [4, 10]  # 5 + 6 + 5: round(16/3) = 5, round(32/3) = 11


def test_a_long_line_is_split_evenly_counting_words_not_syllables() -> None:
    # "I don't know who broke up with who" is 8 words: 4 + 4, never 7 + "who".
    # A hyphenated word counts once, and a break prefers a comma nearby.
    events = enforce_max_line_words(
        _words("I don't know who broke up with who+")
        + [VocalEvent(time=20.0, length=0.2, lyric=w) for w in (
            "May-", "be", "five", "weeks", "or", "five", "min-", "utes,", "but", "it",
            "can't", "be", "too", "long+")],
        max_words=7,
    )
    text = " ".join(e.lyric for e in events).replace("- ", "")
    assert text == (
        "I don't know who+ broke up with who+ "
        "Maybe five weeks or five minutes,+ but it can't be too long+"
    )


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


def test_distribute_syllables_all_melisma_line_extends_previous_across_the_line() -> None:
    """A GP line consisting ONLY of "_" holds (a melisma spanning a whole
    authored line) used to be dropped entirely, so those note attacks never
    extended the previous line's last syllable. It now holds that syllable
    across the whole line instead of the line silently disappearing."""
    onsets = [0.0, 1.0, 2.0, 3.0, 4.0]
    events = distribute_syllables([(0.0, "sing high"), (2.0, "_ _"), (4.0, "again")], onsets)
    # "high+" carries line 1's break marker and is the syllable the melisma holds.
    assert [e.lyric for e in events] == ["sing", "high+", "again+"]
    high = next(e for e in events if e.lyric == "high+")
    assert high.time == 1.0
    assert high.length == pytest.approx(3.0)  # 1.0 -> end of the 3.0 note (4.0)
    # The all-hold line consumed onsets 2.0 and 3.0, so "again" lands on 4.0.
    assert next(e for e in events if e.lyric == "again+").time == 4.0


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
    assert [e.lyric for e in events] == ["Hel-", "lo+", "world"]
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
    assert [e.lyric for e in events] == ["Hel-", "lo+", "world"]


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


def test_extra_spaces_skip_notes_and_a_newline_ends_a_line() -> None:
    """Guitar Pro (and Songsterr) mark an unsung note in a vocal line with an
    extra space: N spaces skip N-1 notes, and every space around a line break
    skips one. A newline also ends the display line."""
    events = distribute_syllables(
        [(0.0, "Hel-lo  world\n Song")], [float(i) for i in range(10)]
    )
    assert [(e.time, e.lyric) for e in events] == [
        (0.0, "Hel-"), (1.0, "lo"), (3.0, "world+"), (5.0, "Song+"),
    ]


def test_comments_and_a_hyphen_before_a_space_are_read_like_guitar_pro() -> None:
    events = distribute_syllables(
        [(0.0, "[Chorus] Mo- ney _ now")], [0.0, 1.0, 2.0, 3.0, 4.0]
    )
    assert [(e.time, e.lyric) for e in events] == [
        (0.0, "Mo-"), (1.0, "ney"), (3.0, "now+"),
    ]
    assert events[1].length == pytest.approx(2.0)  # "_" held "ney" one more note


def _sing(text: str, rests: set[int], *, spacing: float = 0.5) -> list[VocalEvent]:
    """One eighth-long note per syllable of *text*, the vocal line resting
    before the notes whose index is in *rests*."""
    count = sum(len([p for p in w.split("-") if p]) for w in text.split())
    onsets = [i * spacing for i in range(count)]
    return distribute_syllables(
        [(0.0, text)], onsets,
        ends=[t + 0.25 for t in onsets],
        rests_before=[i in rests for i in range(count)],
    )


def test_a_vocal_lines_breaths_before_a_capital_end_the_lyric_lines() -> None:
    # "who (rest) But ... te-qui-la (rest) with High Noon (rest) Don't": a line
    # starts at a breath before a capital — not at "with" (a breath, lower
    # case) nor at "Noon" (a capital, no breath).
    events = _sing(
        "I don't know who But she's in here te-qui-la with High Noon Don't know",
        rests={4, 11, 14},
    )
    assert [e.lyric for e in events] == [
        "I", "don't", "know", "who+", "But", "she's", "in", "here", "te-", "qui-", "la",
        "with", "High", "Noon+", "Don't", "know+",
    ]


def test_lyrics_without_capitals_break_at_every_breath_but_never_mid_word() -> None:
    events = _sing("i don't know who but she's te-qui-la now", rests={4, 7})
    # A breath before "but" ends a line; the one inside "tequila" does not.
    assert [e.lyric for e in events] == [
        "i", "don't", "know", "who+", "but", "she's", "te-", "qui-", "la", "now+",
    ]


def test_lines_the_text_already_has_are_kept_and_breaths_are_not_used() -> None:
    onsets = [0.0, 0.5, 1.0, 1.5]
    events = distribute_syllables(
        [(0.0, "One two\nthree Four")], onsets,
        ends=[t + 0.25 for t in onsets], rests_before=[False, False, False, True],
    )
    assert [e.lyric for e in events] == ["One", "two+", "three", "Four+"]


def test_a_syllable_lasts_as_long_as_its_note_not_until_the_next_one() -> None:
    events = distribute_syllables(
        [(0.0, "long short")], [0.0, 3.0], ends=[1.5, 3.25], rests_before=[False, True],
    )
    assert [(e.time, e.length) for e in events] == [(0.0, 1.5), (3.0, 0.25)]
    # Without the note ends it is still the gap to the next note, as before.
    events = distribute_syllables([(0.0, "long short")], [0.0, 3.0])
    assert events[0].length == 3.0


def test_an_lrc_line_with_several_times_is_sung_at_each_of_them() -> None:
    """A chorus written once with every time it is sung in front of it kept the
    second time inside the lyric ("[01:10.00]Hello") and was never placed there."""
    events = parse_lrc("[00:12.00][01:10.00]Hello world\n[00:20.00]Next")
    assert [(round(e.time, 2), e.lyric) for e in events] == [
        (12.0, "Hello world"), (20.0, "Next"), (70.0, "Hello world")]


def test_ultrastar_syllables_of_one_word_are_joined_and_words_are_not() -> None:
    txt = "#BPM:120\n#GAP:0\n: 0 2 60 Hel\n: 2 2 60 lo \n: 4 2 60 big\n: 6 2 60  world\nE\n"
    assert [e.lyric for e in parse_ultrastar_txt(txt)] == ["Hel-", "lo", "big", "world"]


def test_an_lrc_with_a_time_on_every_word_keeps_each_words_time() -> None:
    """GitHub issue #14: an "enhanced" LRC carries <mm:ss.xx> before each word
    (and often one after the last, where the line ends). Each word starts at
    its own time and lasts until the next — it used to show as "<00:41.81>She's",
    spread evenly over the line. A stamp right after a syllable splits a word
    ("-"), words under one stamp share it, a plain line in the same file is
    spread as before, and a line sung twice keeps its word spacing."""
    text = (
        "[00:41.81]<00:41.81>She's <00:42.30>got <00:43.05>it<00:43.60>\n"
        "[00:44.00]<00:44.00>Wel<00:44.50>come <00:45.00>to the <00:46.00>jun<00:46.40>gle\n"
        "[00:50.00]plain line here\n"
        "[00:55.00][01:30.00]<00:55.00>Hey <00:55.50>you<00:56.00>\n"
    )
    got = [(round(e.time, 3), round(e.length, 3), e.lyric) for e in parse_lyrics(text)]
    assert got == [
        (41.81, 0.49, "She's"), (42.3, 0.75, "got"), (43.05, 0.55, "it+"),
        (44.0, 0.5, "Wel-"), (44.5, 0.5, "come"), (45.0, 0.5, "to"), (45.5, 0.5, "the"),
        (46.0, 0.4, "jun-"), (46.4, 3.6, "gle+"),
        (50.0, 1.333, "plain"), (51.333, 1.333, "line"), (52.667, 1.333, "here+"),
        (55.0, 0.5, "Hey"), (55.5, 0.5, "you+"),
        (90.0, 0.5, "Hey"), (90.5, 0.5, "you+"),
    ]
    assert not any("<" in e.lyric for e in parse_lyrics(text))
    shifted = parse_lyrics(text, offset_s=2.0)
    assert round(shifted[0].time, 3) == 43.81


def test_a_plain_lrc_is_still_spread_over_its_lines() -> None:
    events = parse_lyrics("[00:10.00]one two\n[00:12.00]three\n")
    assert [(e.time, e.lyric) for e in events] == [(10.0, "one"), (11.0, "two+"), (12.0, "three+")]
