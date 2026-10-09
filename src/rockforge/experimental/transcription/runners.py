"""The transcribers under test, each run as a subprocess of the ML Python.

Each one is an optional install in the interpreter RockForge already uses for
its ML stages (``ml_python``), never imported here — the same rule as Demucs
and WhisperX. Each writes a .mid; ``midi.guitar_notes`` takes the guitar part.
"""

from __future__ import annotations

import os
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path

TIMEOUT_S = 30 * 60


@dataclass(frozen=True)
class Runner:
    name: str
    about: str
    install: str
    script: str  # python -c body; argv[1] = audio, argv[2] = output .mid


RUNNERS: dict[str, Runner] = {r.name: r for r in (
    Runner(
        "gaps",
        "Riley et al. (ISMIR 2024) guitar CRNN, trained on GAPS — notes only",
        'pip install "hf-midi-transcription @ git+https://github.com/xavriley/hf_midi_transcription"',
        "import sys\n"
        "from hf_midi_transcription import MidiTranscriptionModel\n"
        "dev = sys.argv[3]\n"
        "m = MidiTranscriptionModel(instrument='guitar', device=dev)\n"
        "m.transcribe(sys.argv[1], sys.argv[2])\n",
    ),
    Runner(
        "yourmt3",
        "YourMT3+ (MLSP 2024), multi-instrument — its guitar programs",
        'pip install "mt3-infer @ git+https://github.com/openmirlab/mt3-infer.git"',
        "import sys, librosa\n"
        "from mt3_infer import transcribe\n"
        "audio, _ = librosa.load(sys.argv[1], sr=16000)\n"
        "transcribe(audio, sr=16000, model='yourmt3').save(sys.argv[2])\n",
    ),
    Runner(
        "mr_mt3",
        "MR-MT3 (2024), multi-instrument — its guitar programs",
        'pip install "mt3-infer @ git+https://github.com/openmirlab/mt3-infer.git"',
        "import sys, librosa\n"
        "from mt3_infer import transcribe\n"
        "audio, _ = librosa.load(sys.argv[1], sr=16000)\n"
        "transcribe(audio, sr=16000, model='mr_mt3').save(sys.argv[2])\n",
    ),
    Runner(
        "basic_pitch",
        "Spotify Basic Pitch — the baseline RockForge dropped",
        "pip install basic-pitch   (needs tensorflow<2.15.1)",
        "import sys\n"
        "from basic_pitch.inference import predict\n"
        "_, midi, _ = predict(sys.argv[1])\n"
        "midi.write(sys.argv[2])\n",
    ),
)}


class RunnerError(RuntimeError):
    pass


def _tail(text: str, lines: int = 12) -> str:
    return "\n".join(text.strip().splitlines()[-lines:])


def run(name: str, audio: Path, out: Path, python: str, device: str) -> None:
    runner = RUNNERS[name]
    cmd = [python, "-c", runner.script, str(audio), str(out), device]
    _execute(cmd, out, runner.install)


def run_command(template: str, audio: Path, out: Path) -> None:
    """Any other tool, as a command line with {audio} and {midi} in it."""
    parts = shlex.split(template, posix=os.name != "nt")
    cmd = [p.replace("{audio}", str(audio)).replace("{midi}", str(out)) for p in parts]
    _execute(cmd, out, "")


def _execute(cmd: list[str], out: Path, install: str) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        proc = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True,
                              text=True, timeout=TIMEOUT_S, check=False)
    except FileNotFoundError as exc:
        raise RunnerError(str(exc)) from exc
    except subprocess.TimeoutExpired as exc:
        raise RunnerError(f"timed out after {TIMEOUT_S // 60} min") from exc
    if proc.returncode != 0 or not out.is_file():
        detail = _tail(proc.stderr or proc.stdout or "")
        if "ModuleNotFoundError" in detail and install:
            detail = f"{detail}\n→ {install}"
        raise RunnerError(detail or f"exit code {proc.returncode}, no MIDI written")


def cuda_available(python: str) -> bool:
    try:
        proc = subprocess.run(
            [python, "-c", "import torch; print(torch.cuda.is_available())"],
            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=120, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.stdout.strip().endswith("True")
