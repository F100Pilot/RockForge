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

MODEL = "htdemucs_6s"


class DemucsSeparator:
    """Implements rockforge.application.ports.StemSeparator via the demucs CLI."""

    def __init__(self, model: str = MODEL, device: str = "cpu") -> None:
        self._model = model
        self._device = device

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
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except FileNotFoundError as exc:
            raise SeparationError("demucs is not installed (pip install 'rockforge[ml]')") from exc
        except subprocess.CalledProcessError as exc:
            raise SeparationError(f"demucs failed: {exc.stderr[-2000:]}") from exc

        guitar = out_dir / self._model / audio.stem / "guitar.wav"
        if not guitar.exists():
            raise SeparationError(
                f"expected guitar stem not produced at {guitar} — "
                f"model '{self._model}' may not emit a guitar source"
            )
        return guitar
