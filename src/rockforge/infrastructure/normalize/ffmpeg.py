"""Audio normalization to 44.1 kHz stereo WAV with EBU R128 loudness via ffmpeg."""

from __future__ import annotations

import subprocess
from pathlib import Path

from rockforge.domain.errors import NormalizationError

# Generous ceiling so a genuinely long file still normalizes, but a stuck ffmpeg
# fails loudly instead of hanging the stage forever (matches wwise.py's 600s).
FFMPEG_TIMEOUT_S = 600


class FfmpegNormalizer:
    """Implements rockforge.application.ports.AudioNormalizer."""

    def normalize(
        self, audio: Path, workdir: Path, offset_s: float = 0.0, pad_start_s: float = 0.0
    ) -> Path:
        out = workdir / "normalized.wav"
        filters = []
        if pad_start_s > 0:
            filters.append(f"adelay={int(pad_start_s * 1000)}:all=1")
        # Normalize to the configured loudness (default -12 LUFS, a music-game
        # level — see runtime_settings). One shared target with the Wwise volume
        # calibration so the .wem and the volume never drift apart.
        from rockforge import runtime_settings

        filters.append(f"loudnorm=I={runtime_settings.loudness_target():.1f}:TP=-1.5:LRA=11")
        cmd = [
            # -nostdin: never read stdin. Run from a console (the Windows
            # start.bat worker), ffmpeg inherits the console's stdin and goes
            # interactive, blocking forever — the "stuck at normalizing" hang.
            "ffmpeg", "-nostdin", "-y",
            *(["-ss", str(offset_s)] if offset_s > 0 else []),
            "-i", str(audio),
            "-af", ",".join(filters),
            "-ar", "44100", "-ac", "2",
            str(out),
        ]
        try:
            subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                stdin=subprocess.DEVNULL,
                timeout=FFMPEG_TIMEOUT_S,
            )
        except FileNotFoundError as exc:
            raise NormalizationError("ffmpeg is not installed") from exc
        except subprocess.TimeoutExpired as exc:
            raise NormalizationError(
                f"ffmpeg timed out after {FFMPEG_TIMEOUT_S}s normalizing {audio.name}"
            ) from exc
        except subprocess.CalledProcessError as exc:
            raise NormalizationError(f"ffmpeg failed: {exc.stderr[-2000:]}") from exc
        return out
