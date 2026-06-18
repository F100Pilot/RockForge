"""Guitar stem extraction via Demucs htdemucs_6s (MIT).

Known, documented caveats (docs/research/01-source-separation.md §1):
- htdemucs_6s is the ONLY open model with an out-of-the-box guitar stem;
- its authors rate guitar quality as merely "okay" (bleeding expected);
- the upstream repo was archived in Jan 2025; no published guitar SDR exists.
The port boundary lets a better checkpoint (e.g. a BS-RoFormer guitar model)
replace this adapter without touching the rest of the system.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from rockforge.domain.errors import SeparationError

DEMUCS_TIMEOUT_S = 1800  # 30 min ceiling — Demucs on CPU is slow but shouldn't hang forever

MODEL = "htdemucs_6s"
# Lyric detection only needs the vocals stem, so it uses the 4-source htdemucs
# with --two-stems=vocals instead of the 6-source htdemucs_6s: the 6s model is
# the slowest Demucs variant and computing drums/bass/other/guitar/piano just to
# discard them is pure waste. htdemucs' vocal quality is also better than the
# 6s model's, so this is faster *and* more accurate for transcription.
VOCAL_MODEL = "htdemucs"


class DemucsSeparator:
    """Implements rockforge.application.ports.StemSeparator via the demucs CLI."""

    def __init__(
        self, model: str = MODEL, device: str = "cpu", vocal_model: str = VOCAL_MODEL
    ) -> None:
        self._model = model
        self._device = device
        self._vocal_model = vocal_model

    def separate_guitar(self, audio: Path, workdir: Path) -> Path:
        out_dir = workdir / "stems"
        patcher = Path(__file__).resolve().parent / "_demucs_patcher.py"
        cmd = [
            sys.executable, str(patcher),
            "-n", self._model,
            "-d", self._device,
            "-o", str(out_dir),
            str(audio),
        ]
        try:
            # stdin=DEVNULL: never inherit the worker console's stdin (an
            # inherited stdin can block a CLI subprocess indefinitely).
            subprocess.run(
                cmd, check=True, capture_output=True, text=True,
                stdin=subprocess.DEVNULL, timeout=DEMUCS_TIMEOUT_S,
            )
        except FileNotFoundError as exc:
            raise SeparationError("demucs is not installed (pip install 'rockforge[ml]')") from exc
        except subprocess.TimeoutExpired as exc:
            raise SeparationError(
                f"demucs timed out after {DEMUCS_TIMEOUT_S}s separating {audio.name}"
            ) from exc
        except subprocess.CalledProcessError as exc:
            raise SeparationError(f"demucs failed: {exc.stderr[-2000:]}") from exc

        guitar = out_dir / self._model / audio.stem / "guitar.wav"
        if not guitar.exists():
            raise SeparationError(
                f"expected guitar stem not produced at {guitar} — "
                f"model '{self._model}' may not emit a guitar source"
            )
        return guitar

    def separate_vocals(self, audio: Path, workdir: Path) -> Path:
        """Isolate just the vocals stem (for lyric transcription).

        Uses the lighter 4-source htdemucs with --two-stems=vocals rather than
        the 6-source htdemucs_6s: much faster (no drums/bass/other/guitar/piano)
        with better vocal quality. Returns the path to vocals.wav.
        """
        out_dir = workdir / "stems"
        patcher = Path(__file__).resolve().parent / "_demucs_patcher.py"
        cmd = [
            sys.executable, str(patcher),
            "-n", self._vocal_model,
            "-d", self._device,
            "--two-stems", "vocals",
            "-o", str(out_dir),
            str(audio),
        ]
        try:
            # stdin=DEVNULL: never inherit the worker console's stdin (an
            # inherited stdin can block a CLI subprocess indefinitely).
            subprocess.run(
                cmd, check=True, capture_output=True, text=True,
                stdin=subprocess.DEVNULL, timeout=DEMUCS_TIMEOUT_S,
            )
        except FileNotFoundError as exc:
            raise SeparationError("demucs is not installed (pip install 'rockforge[ml]')") from exc
        except subprocess.TimeoutExpired as exc:
            raise SeparationError(
                f"demucs timed out after {DEMUCS_TIMEOUT_S}s separating {audio.name}"
            ) from exc
        except subprocess.CalledProcessError as exc:
            raise SeparationError(f"demucs failed: {exc.stderr[-2000:]}") from exc

        vocals = out_dir / self._vocal_model / audio.stem / "vocals.wav"
        if not vocals.exists():
            raise SeparationError(
                f"expected vocals stem not produced at {vocals} — "
                f"model '{self._vocal_model}' may not emit a vocals source"
            )
        return vocals
