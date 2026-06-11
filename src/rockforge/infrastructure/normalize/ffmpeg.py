"""Audio normalization to 44.1 kHz stereo WAV with EBU R128 loudness via ffmpeg."""

from __future__ import annotations

import subprocess
from pathlib import Path

from rockforge.domain.errors import NormalizationError


class FfmpegNormalizer:
    """Implements rockforge.application.ports.AudioNormalizer."""

    def normalize(self, audio: Path, workdir: Path) -> Path:
        out = workdir / "normalized.wav"
        cmd = [
            "ffmpeg", "-y", "-i", str(audio),
            "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
            "-ar", "44100", "-ac", "2",
            str(out),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except FileNotFoundError as exc:
            raise NormalizationError("ffmpeg is not installed") from exc
        except subprocess.CalledProcessError as exc:
            raise NormalizationError(f"ffmpeg failed: {exc.stderr[-2000:]}") from exc
        return out
