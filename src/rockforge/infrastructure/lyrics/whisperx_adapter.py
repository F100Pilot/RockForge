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

from rockforge.infrastructure.rsxml.vocals import VocalEvent

DEFAULT_MIN_WORD_SCORE = 0.35
DEFAULT_RMS_THRESHOLD = 0.01
MAX_WORD_LENGTH_S = 4.0
DEFAULT_WORD_LENGTH_S = 0.3
# WhisperX segments can be long sentences; Rocksmith shows lyrics a line at a
# time, so a long segment scrolls as one wall of text. Break each segment into
# shorter display lines on a sung pause (gap between words) or a word cap.
LINE_BREAK_GAP_S = 0.6
LINE_MAX_WORDS = 7


def vocals_has_signal(path: Path, threshold: float = DEFAULT_RMS_THRESHOLD) -> bool:
    """Cheap RMS check — False for (near-)silent stems, where Whisper would
    hallucinate lyrics instead of returning nothing."""
    import numpy as np
    import soundfile as sf

    data, _sr = sf.read(str(path), dtype="float32", always_2d=True)
    if data.size == 0:
        return False
    rms = float(np.sqrt(np.mean(np.square(data))))
    return rms >= threshold


def _break_into_lines(words: list[VocalEvent]) -> list[VocalEvent]:
    """Suffix `+` (Rocksmith line break) on the last word of each display line.

    A segment becomes several lines: break on a sung pause (gap to the next word
    > ``LINE_BREAK_GAP_S``) or once a line reaches ``LINE_MAX_WORDS``; the last
    word of the segment always ends a line."""
    out: list[VocalEvent] = []
    line_words = 0
    for i, w in enumerate(words):
        line_words += 1
        is_last = i == len(words) - 1
        gap_break = (
            not is_last
            and (words[i + 1].time - (w.time + w.length)) > LINE_BREAK_GAP_S
        )
        if is_last or gap_break or line_words >= LINE_MAX_WORDS:
            out.append(VocalEvent(time=w.time, length=w.length, lyric=w.lyric + "+"))
            line_words = 0
        else:
            out.append(w)
    return out


def segments_to_vocal_events(
    segments: list[dict[str, Any]], min_word_score: float = DEFAULT_MIN_WORD_SCORE
) -> list[VocalEvent]:
    """Map WhisperX aligned segments to Rocksmith vocal events.

    One event per word; each display line's last word gets the Rocksmith `+`
    suffix (the line-break marker rendered by the game) — long segments are
    split into short lines by :func:`_break_into_lines` so the in-game lyrics
    don't scroll as one wall of text. Words without timestamps (alignment
    failure) or below the confidence threshold are dropped.
    """
    events: list[VocalEvent] = []
    for seg in segments:
        kept: list[VocalEvent] = []
        for w in seg.get("words", []):
            word = str(w.get("word", "")).strip()
            start = w.get("start")
            if not word or start is None:
                continue
            score = w.get("score")
            if score is not None and float(score) < min_word_score:
                continue
            end = w.get("end")
            length = (
                min(MAX_WORD_LENGTH_S, max(0.1, float(end) - float(start)))
                if end is not None
                else DEFAULT_WORD_LENGTH_S
            )
            kept.append(VocalEvent(time=float(start), length=length, lyric=word))
        if kept:
            events.extend(_break_into_lines(kept))
    return events


class WhisperXLyricTranscriber:
    """Implements rockforge.application.ports.LyricTranscriber via WhisperX."""

    def __init__(
        self,
        model_size: str = "small",
        device: str = "cpu",
        min_word_score: float = DEFAULT_MIN_WORD_SCORE,
        rms_threshold: float = DEFAULT_RMS_THRESHOLD,
    ) -> None:
        self._model_size = model_size
        self._device = device
        self._min_word_score = min_word_score
        self._rms_threshold = rms_threshold

    @staticmethod
    def available() -> bool:
        """Whether whisperx is installed — WITHOUT importing it.

        `import whisperx` pulls pyannote/speechbrain into the worker process,
        and speechbrain 1.0's lazy `integrations.k2_fsa` loader then fails later
        (e.g. during Basic Pitch's transcribe in the SAME process) with an
        ImportError. `find_spec` only locates the package, so nothing heavy is
        imported; the actual whisperx import happens in the isolated subprocess
        (`_whisperx_runner.py`)."""
        import importlib.util

        try:
            return importlib.util.find_spec("whisperx") is not None
        except Exception:
            return False

    def transcribe(self, vocals_stem: Path) -> list[VocalEvent]:
        if not vocals_has_signal(vocals_stem, self._rms_threshold):
            return []

        import whisperx

        compute_type = "int8" if self._device == "cpu" else "float16"
        model = whisperx.load_model(self._model_size, self._device, compute_type=compute_type)
        audio = whisperx.load_audio(str(vocals_stem))
        result = model.transcribe(audio, batch_size=8)
        align_model, align_meta = whisperx.load_align_model(
            language_code=result["language"], device=self._device
        )
        aligned = whisperx.align(
            result["segments"], align_model, align_meta, audio, self._device
        )
        return segments_to_vocal_events(aligned["segments"], self._min_word_score)
