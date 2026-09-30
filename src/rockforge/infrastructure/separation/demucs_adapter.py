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
from collections.abc import Callable
from pathlib import Path

from rockforge.domain.errors import SeparationError
from rockforge.i18n import tr
from rockforge.infrastructure import ml_python
from rockforge.infrastructure._subprocess import HARDENED_RUN_KWARGS

DEMUCS_TIMEOUT_S = 1800  # 30 min ceiling — Demucs on CPU is slow but shouldn't hang forever

MODEL = "htdemucs_6s"
# Lyric detection only needs the vocals stem, so it uses the 4-source htdemucs
# with --two-stems=vocals instead of the 6-source htdemucs_6s: the 6s model is
# the slowest Demucs variant and computing drums/bass/other/guitar/piano just to
# discard them is pure waste. htdemucs' vocal quality is also better than the
# 6s model's, so this is faster *and* more accurate for transcription.
VOCAL_MODEL = "htdemucs"


def _is_cuda(device: str) -> bool:
    return device.split(":", 1)[0] == "cuda"


class DemucsSeparator:
    """Guitar/stem separation via the demucs CLI (used by the separate-stems,
    tone-detection and lyric-detection tasks).

    GPU→CPU fallback: a CUDA run that crashes (e.g. the Windows exit 0xC0000409
    native crash from a torch/cuDNN mismatch on Turing/RTX 20-series cards) is
    retried on CPU so separation still completes, and ``on_cuda_crash`` is
    invoked once so the worker can persist a "GPU broken" marker and skip the
    GPU on later runs — mirroring the WhisperX path.
    """

    def __init__(
        self,
        model: str = MODEL,
        device: str = "cpu",
        vocal_model: str = VOCAL_MODEL,
        on_cuda_crash: Callable[[], None] | None = None,
    ) -> None:
        self._model = model
        self._device = device
        self._vocal_model = vocal_model
        self._on_cuda_crash = on_cuda_crash

    def _run(self, model: str, extra_args: list[str], audio: Path, out_dir: Path) -> None:
        """Run the demucs CLI for ``model``, retrying on CPU if a CUDA run crashes."""
        patcher = ml_python.runner_path(Path(__file__).resolve().parent, "_demucs_patcher.py")
        # NOT sys.executable: in the standalone build that is the .exe itself,
        # so this would relaunch RockForge instead of running Demucs. The
        # resolver returns the configured ML interpreter there, and plain
        # sys.executable everywhere else. See infrastructure/ml_python.py.
        python = ml_python.resolve()
        if not python:
            raise SeparationError(ml_python.missing_message(
                tr("A separação de áudio", "Audio separation")
            ))

        def build(dev: str) -> list[str]:
            return [
                python, str(patcher),
                "-n", model, "-d", dev, *extra_args, "-o", str(out_dir), str(audio),
            ]

        # First attempt on the configured device; a CUDA crash falls back to CPU.
        devices = [self._device]
        if _is_cuda(self._device):
            devices.append("cpu")
        for i, dev in enumerate(devices):
            try:
                # HARDENED_RUN_KWARGS carries stdin=DEVNULL (never inherit the
                # worker console's stdin — it can block a CLI subprocess forever).
                # The error mapping stays inline (not the shared context manager)
                # because a CUDA CalledProcessError must be intercepted here to
                # retry on CPU rather than surface immediately.
                subprocess.run(build(dev), timeout=DEMUCS_TIMEOUT_S, **HARDENED_RUN_KWARGS)
                return
            except FileNotFoundError as exc:
                raise SeparationError(
                    "demucs is not installed (pip install 'rockforge[ml]')"
                ) from exc
            except subprocess.TimeoutExpired as exc:
                # A timeout is not a GPU crash — don't burn another 30 min on CPU.
                raise SeparationError(
                    f"demucs timed out after {DEMUCS_TIMEOUT_S}s separating {audio.name}"
                ) from exc
            except subprocess.CalledProcessError as exc:
                is_last = i == len(devices) - 1
                if _is_cuda(dev) and not is_last:
                    # GPU crashed — remember it (so later runs skip the GPU) and
                    # retry on CPU in the next loop iteration.
                    if self._on_cuda_crash is not None:
                        self._on_cuda_crash()
                    continue
                raise SeparationError(f"demucs failed: {exc.stderr[-2000:]}") from exc

    def has_cached_guitar_stem(self, audio: Path, workdir: Path) -> bool:
        """Whether a prior separate_guitar/separate_stems call already produced
        a guitar stem for this exact (audio, workdir) — lets a caller log an
        accurate "reusing" message before the (near-instant, cache-hit) call."""
        return (workdir / "stems" / self._model / audio.stem / "guitar.wav").exists()

    def separate_guitar(self, audio: Path, workdir: Path) -> Path:
        out_dir = workdir / "stems"
        guitar = out_dir / self._model / audio.stem / "guitar.wav"
        # htdemucs_6s writes every source in one pass, so an existing guitar.wav
        # means a full separation of this exact (audio, workdir) already ran —
        # e.g. tone detection and stem separation both ask for it on the same
        # recording. Skip the ~minutes-long re-run and reuse it.
        if not guitar.exists():
            self._run(self._model, [], audio, out_dir)
        if not guitar.exists():
            raise SeparationError(
                f"expected guitar stem not produced at {guitar} — "
                f"model '{self._model}' may not emit a guitar source"
            )
        return guitar

    def separate_stems(self, audio: Path, workdir: Path) -> dict[str, Path]:
        """Run the 6-source model once and return EVERY stem it produced —
        ``{'guitar': path, 'bass': …, 'drums': …, 'vocals': …, 'other': …,
        'piano': …}``. One Demucs pass yields all of them; used by the sync
        viewer's audio-source selector so the user can solo the guitar (or mute
        drums/vocals) while fine-tuning against the notes.

        Honest limit: Demucs separates by INSTRUMENT TYPE, not by individual
        track — ``guitar`` is ALL guitars mixed together; Lead vs Rhythm cannot
        be split from the recording.
        """
        self.separate_guitar(audio, workdir)  # runs htdemucs_6s + validates guitar.wav
        stem_dir = workdir / "stems" / self._model / audio.stem
        return {p.stem: p for p in sorted(stem_dir.glob("*.wav"))}

    def separate_vocals(self, audio: Path, workdir: Path) -> Path:
        """Isolate just the vocals stem (for lyric transcription).

        Uses the lighter 4-source htdemucs with --two-stems=vocals rather than
        the 6-source htdemucs_6s: much faster (no drums/bass/other/guitar/piano)
        with better vocal quality. Returns the path to vocals.wav.
        """
        out_dir = workdir / "stems"
        self._run(self._vocal_model, ["--two-stems", "vocals"], audio, out_dir)
        vocals = out_dir / self._vocal_model / audio.stem / "vocals.wav"
        if not vocals.exists():
            raise SeparationError(
                f"expected vocals stem not produced at {vocals} — "
                f"model '{self._vocal_model}' may not emit a vocals source"
            )
        return vocals
