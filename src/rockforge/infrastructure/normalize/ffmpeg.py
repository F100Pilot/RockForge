"""Audio normalization to 44.1 kHz stereo WAV with EBU R128 loudness via ffmpeg."""

from __future__ import annotations

import subprocess
from pathlib import Path

from rockforge.domain.errors import NormalizationError


class FfmpegNormalizer:
    """Implements rockforge.application.ports.AudioNormalizer."""

    def normalize(
        self, audio: Path, workdir: Path, offset_s: float = 0.0, pad_start_s: float = 0.0
    ) -> Path:
        out = workdir / "normalized.wav"
        filters = []
        if pad_start_s > 0:
            filters.append(f"adelay={int(pad_start_s * 1000)}:all=1")
        filters.append("loudnorm=I=-16:TP=-1.5:LRA=11")
        cmd = [
            "ffmpeg", "-y",
            *(["-ss", str(offset_s)] if offset_s > 0 else []),
            "-i", str(audio),
            "-af", ",".join(filters),
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
