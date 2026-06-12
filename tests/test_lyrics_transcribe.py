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
