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
        --model small --device cuda
"""

from __future__ import annotations

import argparse
import json
import os
import sys


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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vocals", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model", default="small")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--compute-type", default="")  # "" → pick by device
    args = parser.parse_args()

    # Must happen BEFORE whisperx/ctranslate2 load their CUDA libs (below).
    if args.device != "cpu":
        added = _add_cuda_dll_dirs()
        if added:
            print(f"CUDA DLL dirs added: {added}", file=sys.stderr)

    from pathlib import Path

    from rockforge.infrastructure.lyrics.whisperx_adapter import (
        WhisperXLyricTranscriber,
    )

    transcriber = WhisperXLyricTranscriber(
        model_size=args.model,
        device=args.device,
        compute_type=args.compute_type or None,
    )
    events = transcriber.transcribe(Path(args.vocals))
    result = [
        {"time": e.time, "length": e.length, "lyric": e.lyric} for e in events
    ]
    Path(args.output).write_text(
        json.dumps(result, ensure_ascii=False), encoding="utf-8"
    )
    print(f"OK: {len(result)} events", file=sys.stderr)


if __name__ == "__main__":
    main()
