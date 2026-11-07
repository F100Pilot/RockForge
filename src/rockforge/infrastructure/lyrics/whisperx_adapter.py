"""WhisperX-based automatic lyric transcription (optional, EXPERIMENTAL).

Runs over the *isolated vocals stem* that Demucs htdemucs_6s already produces
alongside the guitar stem — never over the full mix. The LRC path remains the
preferred, measured-timing source (rsxml/vocals.py); this adapter is a
fallback for when no LRC exists.

Approach validated against slopsmith's production pipeline
(slopsmith/lib/lyrics_transcribe.py), which settled on the same two gates
against Whisper's known failure mode of hallucinating plausible lyrics on
near-silent or instrumental input:

1. RMS signal gate before inference — skip stems below an energy threshold
   (Demucs returns near-silent vocals for instrumentals).
2. Per-word confidence filter — WhisperX's forced alignment (wav2vec2) emits
   a score per word; words below `min_word_score` are dropped (0.35 default,
   the value slopsmith's reference prototype settled on).

Timestamps come from forced alignment against the audio itself, so the words
share the recording's clock — the same timeline the note XML uses.

whisperx is NOT a base dependency (it pulls torch + ~GB of model weights);
install via `pip install -e ".[lyrics]"`. All imports are deferred.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rockforge.application.ports import VocalEvent
from rockforge.infrastructure.lyrics import _whisperx_runner as _runner
from rockforge.infrastructure.lyrics._whisperx_runner import (  # noqa: F401 — the public names
    ALIGN_LAST_LINE_S,
    ALIGN_MARGIN_S,
    DEFAULT_MIN_WORD_SCORE,
    DEFAULT_RMS_THRESHOLD,
    DEFAULT_WORD_LENGTH_S,
    LINE_BREAK_GAP_S,
    LINE_MAX_WORDS,
    MAX_WORD_LENGTH_S,
    alignment_segments,
)

# The implementation is in _whisperx_runner.py, which must run in a Python that
# has whisperx but not RockForge (the .exe's extra components): ONE copy. The
# detection task runs it as a script; these wrap its pure helpers for the app.


def _events(rows: list[dict[str, Any]]) -> list[VocalEvent]:
    return [VocalEvent(time=r["time"], length=r["length"], lyric=r["lyric"]) for r in rows]


def vocals_has_signal(path: Path, threshold: float = DEFAULT_RMS_THRESHOLD) -> bool:
    return _runner.vocals_has_signal(str(path), threshold)


def segments_to_vocal_events(
    segments: list[dict[str, Any]], min_word_score: float = DEFAULT_MIN_WORD_SCORE
) -> list[VocalEvent]:
    return _events(_runner.segments_to_events(segments, min_word_score))


def aligned_lines_to_events(
    segments: list[dict[str, Any]], *, one_line_per_segment: bool
) -> list[VocalEvent]:
    return _events(_runner.aligned_lines_to_events(
        segments, one_line_per_segment=one_line_per_segment))

