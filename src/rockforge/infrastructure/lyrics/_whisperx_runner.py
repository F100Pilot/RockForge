"""Subprocess runner for WhisperX transcription.

Runs WhisperX in a **fresh process** — not inside the Celery worker. This
avoids the known hang where faster-whisper / ctranslate2 deadlocks during
CUDA initialisation inside a Celery child process (faster-whisper #907,
celery #3402). The Celery task spawns this script via ``subprocess.run``
with a timeout, collects the JSON output, and continues.

Usage:
    python -m rockforge.infrastructure.lyrics._whisperx_runner \
        --vocals /path/to/vocals.wav \
        --output /path/to/events.json \
        --model small --device cuda \
        [--align-json /path/to/lines.json]   # align known lyrics instead
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any


def _add_cuda_dll_dirs() -> list[str]:
    """Windows: put the CUDA 12 / cuDNN 9 DLLs on the process DLL search path.

    ctranslate2 4.x crashes NATIVELY (Windows exit 0xC0000409) when it can't
    load ``cudnn_ops64_9.dll`` / ``cublas64_12.dll`` — even a matching cuDNN 9
    isn't found if it only lives in ``torch/lib`` (torch's cu12x wheels bundle
    it there, but that dir is not on the DLL search path). Add torch's lib dir,
    and any standalone ``nvidia-cudnn``/``nvidia-cublas`` pip packages, via
    ``os.add_dll_directory`` so ctranslate2 resolves them instead of crashing.
    No-op off Windows or when the dirs are absent. Returns the dirs added (for
    logging)."""
    if sys.platform != "win32":
        return []
    import importlib.util
    from pathlib import Path

    candidates: list[Path] = []
    torch_spec = importlib.util.find_spec("torch")
    if torch_spec and torch_spec.submodule_search_locations:
        candidates.append(Path(next(iter(torch_spec.submodule_search_locations))) / "lib")
    for pkg in ("nvidia.cudnn", "nvidia.cublas"):
        try:
            spec = importlib.util.find_spec(pkg)
        except ModuleNotFoundError:
            spec = None
        if spec and spec.submodule_search_locations:
            candidates.append(Path(next(iter(spec.submodule_search_locations))) / "bin")

    added: list[str] = []
    for d in candidates:
        if d.is_dir():
            try:
                os.add_dll_directory(str(d))
                added.append(str(d))
            except OSError:
                pass
    return added


# ---------------------------------------------------------------------------
# The implementation. It lives HERE, importing nothing from RockForge: in the
# .exe this file is run by the extra components' Python, which has whisperx but
# not the rockforge package (it used to import whisperx_adapter, so every lyric
# detection in the .exe failed after minutes of separation). Events are plain
# dicts {"time", "length", "lyric"}; whisperx_adapter wraps them for the app.
# ---------------------------------------------------------------------------

DEFAULT_MIN_WORD_SCORE = 0.35
DEFAULT_RMS_THRESHOLD = 0.01
MAX_WORD_LENGTH_S = 4.0
DEFAULT_WORD_LENGTH_S = 0.3
# WhisperX segments can be long sentences; Rocksmith shows lyrics a line at a
# time, so a long segment scrolls as one wall of text. Break each segment into
# shorter display lines on a sung pause (gap between words) or a word cap.
LINE_BREAK_GAP_S = 0.6
LINE_MAX_WORDS = 7
# Forced alignment of KNOWN lyrics (found on LRCLIB, or typed): each line is
# aligned inside a window around where it is believed to be sung. The margin
# lets a line whose timestamp is a little off (a different edit, a rough LRC)
# still find its words; overlapping windows are fine, each segment is aligned
# on its own.
ALIGN_MARGIN_S = 1.5
ALIGN_LAST_LINE_S = 12.0

Event = dict[str, Any]  # {"time": float, "length": float, "lyric": str}


def vocals_has_signal(path: str, threshold: float = DEFAULT_RMS_THRESHOLD) -> bool:
    """Cheap RMS check — False for (near-)silent stems, where Whisper would
    hallucinate lyrics instead of returning nothing."""
    import numpy as np
    import soundfile as sf

    data, _sr = sf.read(str(path), dtype="float32", always_2d=True)
    if data.size == 0:
        return False
    rms = float(np.sqrt(np.mean(np.square(data))))
    return rms >= threshold


def break_into_lines(words: list[Event]) -> list[Event]:
    """Suffix `+` (Rocksmith line break) on the last word of each display line.

    A segment becomes several lines: break on a sung pause (gap to the next word
    > ``LINE_BREAK_GAP_S``) or once a line reaches ``LINE_MAX_WORDS``; the last
    word of the segment always ends a line."""
    out: list[Event] = []
    line_words = 0
    for i, w in enumerate(words):
        line_words += 1
        is_last = i == len(words) - 1
        gap_break = (
            not is_last
            and (words[i + 1]["time"] - (w["time"] + w["length"])) > LINE_BREAK_GAP_S
        )
        if is_last or gap_break or line_words >= LINE_MAX_WORDS:
            out.append({**w, "lyric": w["lyric"] + "+"})
            line_words = 0
        else:
            out.append(w)
    return out


def segments_to_events(
    segments: list[dict[str, Any]], min_word_score: float = DEFAULT_MIN_WORD_SCORE
) -> list[Event]:
    """Map WhisperX aligned segments to Rocksmith vocal events.

    One event per word; each display line's last word gets the Rocksmith `+`
    suffix (the line-break marker rendered by the game) — long segments are
    split into short lines by :func:`break_into_lines` so the in-game lyrics
    don't scroll as one wall of text. Words without timestamps (alignment
    failure) or below the confidence threshold are dropped.
    """
    events: list[Event] = []
    for seg in segments:
        kept: list[Event] = []
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
            kept.append({"time": float(start), "length": length, "lyric": word})
        if kept:
            events.extend(break_into_lines(kept))
    return events


def alignment_segments(lines: list[dict[str, Any]], duration: float) -> list[dict[str, Any]]:
    """WhisperX segments for aligning known lyrics to a recording.

    ``lines`` are ``{"time": seconds | None, "text": str}``. With times, one
    segment per line spanning from a little before it to a little after the
    next line starts. Without them (plain lyrics), ONE segment over the whole
    recording — WhisperX can align that too, just less reliably, so the caller
    says so.
    """
    texts = [(ln.get("time"), str(ln.get("text") or "").strip()) for ln in lines]
    texts = [(t, x) for t, x in texts if x]
    if not texts:
        return []
    timed = [(float(t), x) for t, x in texts if isinstance(t, (int, float))]
    if len(timed) < len(texts):
        return [{"start": 0.0, "end": duration, "text": " ".join(x for _t, x in texts)}]
    timed.sort(key=lambda tx: tx[0])
    segs: list[dict[str, Any]] = []
    for i, (t, x) in enumerate(timed):
        nxt = timed[i + 1][0] if i + 1 < len(timed) else t + ALIGN_LAST_LINE_S
        segs.append({
            "start": max(0.0, t - ALIGN_MARGIN_S),
            "end": min(duration, max(nxt, t + 0.5) + ALIGN_MARGIN_S),
            "text": x,
        })
    return [s for s in segs if s["end"] > s["start"]]


def aligned_lines_to_events(
    segments: list[dict[str, Any]], *, one_line_per_segment: bool
) -> list[Event]:
    """Vocal events from aligned KNOWN lyrics — every word kept.

    Unlike transcription, the words are right by construction, so no
    confidence filter: a word the aligner could not place (a number, a symbol)
    is put right after the previous one instead of being dropped. With one
    segment per lyric line, each segment's last word ends the in-game line;
    a single whole-song segment falls back to the pause/word-count breaking.
    """
    events: list[Event] = []
    for seg in segments:
        words: list[Event] = []
        cursor = float(seg.get("start") or 0.0)
        for w in seg.get("words", []):
            word = str(w.get("word", "")).strip()
            if not word:
                continue
            start, end = w.get("start"), w.get("end")
            if start is None:
                t, length = cursor, DEFAULT_WORD_LENGTH_S
            else:
                t = float(start)
                length = (min(MAX_WORD_LENGTH_S, max(0.1, float(end) - t))
                          if end is not None else DEFAULT_WORD_LENGTH_S)
            words.append({"time": t, "length": length, "lyric": word})
            cursor = t + length
        if not words:
            continue
        if one_line_per_segment:
            words[-1] = {**words[-1], "lyric": words[-1]["lyric"] + "+"}
            events.extend(words)
        else:
            events.extend(break_into_lines(words))
    return events


def transcribe(vocals: str, model_size: str, device: str, compute_type: str | None = None,
               min_word_score: float = DEFAULT_MIN_WORD_SCORE,
               rms_threshold: float = DEFAULT_RMS_THRESHOLD) -> list[Event]:
    if not vocals_has_signal(vocals, rms_threshold):
        return []

    import whisperx

    compute_type = compute_type or ("int8" if device == "cpu" else "float16")
    model = whisperx.load_model(model_size, device, compute_type=compute_type)
    audio = whisperx.load_audio(str(vocals))
    result = model.transcribe(audio, batch_size=8)
    align_model, align_meta = whisperx.load_align_model(
        language_code=result["language"], device=device
    )
    aligned = whisperx.align(result["segments"], align_model, align_meta, audio, device)
    return segments_to_events(aligned["segments"], min_word_score)


def align(vocals: str, lines: list[dict[str, Any]], language: str, device: str,
          rms_threshold: float = DEFAULT_RMS_THRESHOLD) -> list[Event]:
    """Place KNOWN lyrics on the recording (forced alignment, no transcription)."""
    if not vocals_has_signal(vocals, rms_threshold):
        return []

    import whisperx

    audio = whisperx.load_audio(str(vocals))
    duration = len(audio) / 16000  # whisperx.load_audio resamples to 16 kHz
    segments = alignment_segments(lines, duration)
    if not segments:
        return []
    align_model, align_meta = whisperx.load_align_model(language_code=language, device=device)
    aligned = whisperx.align(segments, align_model, align_meta, audio, device)
    return aligned_lines_to_events(aligned["segments"], one_line_per_segment=len(segments) > 1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vocals", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model", default="small")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--compute-type", default="")  # "" → pick by device
    # Align KNOWN lyrics instead of transcribing: a JSON file of
    # {"lines": [{"time", "text"}], "language": "pt"}.
    parser.add_argument("--align-json", default="")
    args = parser.parse_args()

    # Must happen BEFORE whisperx/ctranslate2 load their CUDA libs (below).
    if args.device != "cpu":
        added = _add_cuda_dll_dirs()
        if added:
            print(f"CUDA DLL dirs added: {added}", file=sys.stderr)

    from pathlib import Path

    if args.align_json:
        spec = json.loads(Path(args.align_json).read_text(encoding="utf-8"))
        result = align(args.vocals, list(spec.get("lines") or []),
                       str(spec.get("language") or "en"), args.device)
    else:
        result = transcribe(args.vocals, args.model, args.device, args.compute_type or None)
    Path(args.output).write_text(
        json.dumps(result, ensure_ascii=False), encoding="utf-8"
    )
    print(f"OK: {len(result)} events", file=sys.stderr)


if __name__ == "__main__":
    main()
