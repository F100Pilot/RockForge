"""WhisperX adapter unit tests — pure mapping/gating logic, no model needed."""

from __future__ import annotations

import pytest

from rockforge.infrastructure.lyrics.whisperx_adapter import segments_to_vocal_events


def seg(words: list[dict], **extra: object) -> dict:
    return {"words": words, **extra}


def test_words_become_events_with_line_break_suffix() -> None:
    events = segments_to_vocal_events(
        [
            seg([
                {"word": "Hello", "start": 1.0, "end": 1.4, "score": 0.9},
                {"word": "world", "start": 1.5, "end": 1.9, "score": 0.8},
            ]),
            seg([{"word": "again", "start": 3.0, "end": 3.3, "score": 0.9}]),
        ]
    )
    assert [e.lyric for e in events] == ["Hello", "world+", "again+"]
    assert events[0].time == 1.0
    assert events[0].length == pytest.approx(0.4)


def test_low_confidence_words_are_dropped() -> None:
    events = segments_to_vocal_events(
        [
            seg([
                {"word": "real", "start": 1.0, "end": 1.2, "score": 0.9},
                {"word": "hallucinated", "start": 1.3, "end": 1.5, "score": 0.1},
            ])
        ],
        min_word_score=0.35,
    )
    assert [e.lyric for e in events] == ["real+"]


def test_words_without_timestamps_are_dropped() -> None:
    events = segments_to_vocal_events(
        [seg([{"word": "ghost", "start": None, "score": 0.9}])]
    )
    assert events == []


def test_empty_segments_yield_no_events() -> None:
    assert segments_to_vocal_events([]) == []
    assert segments_to_vocal_events([seg([])]) == []


def test_length_is_capped_and_has_floor() -> None:
    events = segments_to_vocal_events(
        [
            seg([
                {"word": "loong", "start": 0.0, "end": 30.0, "score": 0.9},
                {"word": "blip", "start": 31.0, "end": 31.001, "score": 0.9},
            ])
        ]
    )
    assert events[0].length == pytest.approx(4.0)  # MAX_WORD_LENGTH_S cap
    assert events[1].length == pytest.approx(0.1)  # floor


def test_long_segment_is_split_into_lines_by_word_cap() -> None:
    """A long, gapless segment must not scroll as one wall of text — it breaks
    every LINE_MAX_WORDS words."""
    words = [
        {"word": f"w{i}", "start": float(i) * 0.3, "end": float(i) * 0.3 + 0.2, "score": 0.9}
        for i in range(16)
    ]
    events = segments_to_vocal_events([seg(words)])
    breaks = [i for i, e in enumerate(events) if e.lyric.endswith("+")]
    # 16 words, cap 7 → line breaks after words 7, 14, and the final word (16).
    assert breaks == [6, 13, 15]


def test_segment_breaks_on_a_sung_pause() -> None:
    """A gap between words (a sung pause) ends a line even under the word cap."""
    events = segments_to_vocal_events(
        [
            seg([
                {"word": "stay", "start": 1.0, "end": 1.3, "score": 0.9},
                {"word": "with", "start": 1.4, "end": 1.6, "score": 0.9},
                # 1.5s gap here → line break after "me"
                {"word": "me", "start": 1.7, "end": 2.0, "score": 0.9},
                {"word": "tonight", "start": 3.5, "end": 3.9, "score": 0.9},
            ])
        ]
    )
    assert [e.lyric for e in events] == ["stay", "with", "me+", "tonight+"]


def test_add_cuda_dll_dirs_is_noop_off_windows(monkeypatch) -> None:
    """The CUDA DLL-path shim (which lets ctranslate2 find cuDNN 9 in torch/lib
    on Windows) must be a safe no-op on non-Windows so CI/Linux is unaffected."""
    from rockforge.infrastructure.lyrics import _whisperx_runner as runner

    monkeypatch.setattr(runner.sys, "platform", "linux")
    assert runner._add_cuda_dll_dirs() == []


def test_rms_gate_rejects_silence(tmp_path) -> None:
    np = pytest.importorskip("numpy")
    sf = pytest.importorskip("soundfile")
    from rockforge.infrastructure.lyrics.whisperx_adapter import vocals_has_signal

    sr = 22050
    silent = tmp_path / "silent.wav"
    sf.write(silent, np.zeros(sr, dtype="float32"), sr)
    assert not vocals_has_signal(silent)

    loud = tmp_path / "loud.wav"
    t = np.linspace(0, 1, sr, dtype="float32")
    sf.write(loud, (0.5 * np.sin(2 * np.pi * 220 * t)).astype("float32"), sr)
    assert vocals_has_signal(loud)


def test_known_lines_are_aligned_in_windows_around_their_timestamps() -> None:
    from rockforge.infrastructure.lyrics.whisperx_adapter import (
        ALIGN_LAST_LINE_S,
        ALIGN_MARGIN_S,
        alignment_segments,
    )

    segs = alignment_segments(
        [{"time": 20.0, "text": "second line"}, {"time": 10.0, "text": "first line"},
         {"time": 30.0, "text": "  "}],
        duration=40.0,
    )
    assert segs == [
        {"start": 10.0 - ALIGN_MARGIN_S, "end": 20.0 + ALIGN_MARGIN_S, "text": "first line"},
        {"start": 20.0 - ALIGN_MARGIN_S,
         "end": min(40.0, 20.0 + ALIGN_LAST_LINE_S + ALIGN_MARGIN_S), "text": "second line"},
    ]


def test_plain_lyrics_are_aligned_over_the_whole_recording() -> None:
    from rockforge.infrastructure.lyrics.whisperx_adapter import alignment_segments

    segs = alignment_segments(
        [{"time": None, "text": "hello darkness"}, {"time": None, "text": "my old friend"}], 180.0)
    assert segs == [{"start": 0.0, "end": 180.0, "text": "hello darkness my old friend"}]
    assert alignment_segments([], 180.0) == []


def test_aligned_known_lyrics_keep_every_word_and_their_lines() -> None:
    from rockforge.infrastructure.lyrics.whisperx_adapter import aligned_lines_to_events

    events = aligned_lines_to_events([
        {"start": 9.0, "words": [
            {"word": "hello", "start": 10.0, "end": 10.4, "score": 0.1},  # low score: kept
            {"word": "99"},                                             # unplaceable: kept
            {"word": "friends", "start": 11.0, "end": 11.5},
        ]},
        {"start": 12.0, "words": [{"word": "again", "start": 12.2, "end": 12.8}]},
    ], one_line_per_segment=True)
    assert [(e.lyric, round(e.time, 2)) for e in events] == [
        ("hello", 10.0), ("99", 10.4), ("friends+", 11.0), ("again+", 12.2)]
