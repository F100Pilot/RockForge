"""Thin wrapper that monkeypatches demucs.audio.save_audio to use soundfile
instead of torchaudio (which needs torchcodec — broken DLLs on Windows).

Run as: python _demucs_patcher.py [demucs args...]
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import soundfile as sf


def _patched_save(wav: Any, path: str | Path, samplerate: int, **kwargs: object) -> None:
    """soundfile-based replacement for demucs.audio.save_audio."""
    audio_np = wav.detach().cpu().numpy()
    # Demucs tensors are (channels, samples); soundfile expects (samples, channels)
    if audio_np.ndim == 2:
        audio_np = audio_np.T
    sf.write(str(path), audio_np, samplerate)


# -- patch before demucs imports anything else --------------------------------
import demucs.audio  # noqa: E402

demucs.audio.save_audio = _patched_save


if __name__ == "__main__":
    # Replace our wrapper script name with a dummy so Demucs' argparse
    # (which uses sys.argv[1:]) sees the correct flags and positional args.
    sys.argv[0] = "demucs"
    from demucs.separate import main

    main()
