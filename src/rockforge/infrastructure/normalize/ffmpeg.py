"""Audio normalization to 44.1 kHz stereo WAV via ffmpeg: a linear gain, no dynamics processing."""

from __future__ import annotations

import subprocess
from pathlib import Path

from rockforge.domain.errors import NormalizationError
from rockforge.infrastructure._subprocess import HARDENED_RUN_KWARGS, map_external_errors
from rockforge.infrastructure.normalize.loudness import measure_levels, recording_gain_db

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
        # The recording keeps its own dynamics: only a LINEAR gain toward the
        # loudness target, capped so no peak passes -1 dBTP, and the Wwise volume
        # does the rest (as DLC Builder does, which never touches the audio).
        # This used to be a single-pass `loudnorm`, whose moving gain and
        # true-peak limiter reshaped every song — "os PSARC têm algum ruído e
        # não têm uma tonalidade limpa". The gain runs in ffmpeg's float
        # pipeline, before the 16-bit write, so a master mastered over 0 dBFS
        # is brought under it instead of being clipped.
        from rockforge import runtime_settings

        loudness, true_peak = measure_levels(audio, start_s=offset_s)
        gain = recording_gain_db(loudness, true_peak, runtime_settings.loudness_target())
        if abs(gain) >= 0.05:
            filters.append(f"volume={gain:.2f}dB")
        cmd = [
            # -nostdin: never read stdin. Run from a console (the Windows
            # start.bat worker), ffmpeg inherits the console's stdin and goes
            # interactive, blocking forever — the "stuck at normalizing" hang.
            "ffmpeg", "-nostdin", "-y",
            *(["-ss", str(offset_s)] if offset_s > 0 else []),
            "-i", str(audio),
            *(["-af", ",".join(filters)] if filters else []),
            "-ar", "44100", "-ac", "2",
            str(out),
        ]
        with map_external_errors(
            error_cls=NormalizationError,
            not_installed_msg="ffmpeg is not installed",
            timeout_msg=f"ffmpeg timed out after {FFMPEG_TIMEOUT_S}s normalizing {audio.name}",
            fail_msg_prefix="ffmpeg failed: ",
        ):
            subprocess.run(cmd, timeout=FFMPEG_TIMEOUT_S, **HARDENED_RUN_KWARGS)
        return out
