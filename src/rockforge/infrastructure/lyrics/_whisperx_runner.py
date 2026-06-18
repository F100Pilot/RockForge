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
import sys


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vocals", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model", default="small")
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()

    from pathlib import Path

    from rockforge.infrastructure.lyrics.whisperx_adapter import (
        WhisperXLyricTranscriber,
    )

    transcriber = WhisperXLyricTranscriber(
        model_size=args.model, device=args.device
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
