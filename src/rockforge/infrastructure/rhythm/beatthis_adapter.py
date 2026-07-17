"""Neural downbeat tracking via "Beat This!" (CPJKU/beat_this, MIT).

librosa's ``beat_track`` locks onto the wrong metrical level on fast, dense
music (it read ~184 BPM on a genuine ~175 BPM metal song, even on the isolated
drum stem), which is what breaks the automatic tempo detection for AI-generated
tabs. A modern neural tracker is far more robust there, so this derives a
per-measure tempo map straight from the recording — ideally the isolated drum
stem the app already separates — WITHOUT the user having to export a MIDI from a
DAW (RIPX). The detected measure-downbeat times feed the exact same
``align_chart_to_midi`` machinery as the MIDI import: this is the in-app
equivalent of that ground-truth path.

Same honesty caveat as every ML stage: a neural estimate is strong but NOT
ground truth like a hand-checked RIPX MIDI — the user confirms the proposal over
the waveform before rebuilding.

beat_this is an OPTIONAL extra (torch-based, licence MIT); imported lazily so
the core GP pipeline and the librosa-only ``[ml]`` path never pay for it, and so
tests can monkeypatch :func:`detect_downbeats` without torch installed — exactly
like the librosa detection functions.
"""

from __future__ import annotations

import os
from pathlib import Path


def detect_downbeats(audio: Path) -> list[float]:
    """Detect measure-downbeat times (seconds from the recording start) with the
    Beat This! neural tracker. Standalone (not a port method) so the API can call
    it directly and tests can monkeypatch it without beat_this/torch installed.

    Runs on CPU by default: the model is small and this sidesteps the Turing /
    cuDNN native GPU crashes documented for the torch stack (see CLAUDE.md).
    Overridable via ``ROCKFORGE_BEATTHIS_DEVICE`` and, for the checkpoint,
    ``ROCKFORGE_BEATTHIS_CHECKPOINT`` (default ``final0``). A shortname checkpoint
    is downloaded from cloud.cp.jku.at on first use; if that download fails, set
    ``ROCKFORGE_BEATTHIS_CHECKPOINT`` to a manually-downloaded local ``.ckpt``.

    ``dbn=False`` keeps the pure-torch "minimal" post-processor: the DBN
    post-processor would pull in madmom, whose models are CC BY-NC-SA
    (non-commercial) and which the project deliberately excludes.
    """
    from beat_this.inference import File2Beats

    checkpoint = os.environ.get("ROCKFORGE_BEATTHIS_CHECKPOINT", "final0")
    device = os.environ.get("ROCKFORGE_BEATTHIS_DEVICE", "cpu")
    try:
        file2beats = File2Beats(checkpoint_path=checkpoint, device=device, dbn=False)
    except Exception as exc:
        # A shortname like "final0" is downloaded from cloud.cp.jku.at on first
        # use (torch.hub). If that download fails (offline, firewall, transient
        # server error) beat_this raises a terse "Could not load the checkpoint";
        # re-raise with the manual-download fallback so the user can fix it.
        if isinstance(checkpoint, str) and not os.path.exists(checkpoint):
            raise RuntimeError(
                f"could not load the Beat This! checkpoint {checkpoint!r} — on first "
                "use it is downloaded from cloud.cp.jku.at. If that fails, download "
                f"https://cloud.cp.jku.at/public.php/dav/files/7ik4RrBKTS273gp/{checkpoint}.ckpt "
                "manually and set ROCKFORGE_BEATTHIS_CHECKPOINT to the saved file path."
            ) from exc
        raise
    # File2Beats returns (beats, downbeats) in seconds (README usage order); take
    # the downbeats (measure starts) as the per-measure tempo map.
    _beats, downbeats = file2beats(str(audio))
    return sorted(float(t) for t in downbeats)
