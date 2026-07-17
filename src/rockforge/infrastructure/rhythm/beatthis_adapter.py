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
import shutil
import urllib.request
from pathlib import Path

# A Beat This! shortname (e.g. "final0") resolves to "{_CHECKPOINT_BASE}/{name}.ckpt"
# (CPJKU cloud, WebDAV public share). beat_this fetches it via torch.hub on first
# use, which fails on some networks (redirects/headers on the Nextcloud link); we
# download it ourselves with a plain redirect-following urllib GET instead.
_CHECKPOINT_BASE = "https://cloud.cp.jku.at/public.php/dav/files/7ik4RrBKTS273gp"


def _cache_dir() -> Path:
    return Path(
        os.environ.get("ROCKFORGE_BEATTHIS_CACHE")
        or (Path.home() / ".cache" / "rockforge" / "beat_this")
    )


def _resolve_checkpoint(name: str) -> str:
    """Return a local ``.ckpt`` path for ``name``.

    A local file (or an explicit path) is used as-is. A bare shortname like
    ``final0`` is downloaded once from ``_CHECKPOINT_BASE`` to the cache dir and
    reused — a redirect-following ``urllib`` GET, more robust than torch.hub's
    downloader which fails on some networks. Anything path-like or ending in
    ``.ckpt`` that does not exist is left to beat_this to resolve/report.
    """
    if os.path.exists(name):
        return name
    if os.sep in name or (os.altsep and os.altsep in name) or name.endswith(".ckpt"):
        return name  # an explicit (missing) path — let beat_this report it

    cache_dir = _cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)
    dest = cache_dir / f"{name}.ckpt"
    if dest.exists() and dest.stat().st_size > 0:
        return str(dest)

    url = f"{_CHECKPOINT_BASE}/{name}.ckpt"
    tmp = dest.with_name(dest.name + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": "RockForge/beat_this"})
    with urllib.request.urlopen(req, timeout=180) as resp:  # noqa: S310 (fixed https host)
        head = resp.read(2)
        if head[:1] == b"<":  # an HTML error/login page, not a checkpoint
            raise RuntimeError(f"checkpoint URL returned a non-file response: {url}")
        with open(tmp, "wb") as f:
            f.write(head)
            shutil.copyfileobj(resp, f)
    os.replace(tmp, dest)
    return str(dest)


def detect_downbeats(audio: Path) -> list[float]:
    """Detect measure-downbeat times (seconds from the recording start) with the
    Beat This! neural tracker. Standalone (not a port method) so the API can call
    it directly and tests can monkeypatch it without beat_this/torch installed.

    Runs on CPU by default: the model is small and this sidesteps the Turing /
    cuDNN native GPU crashes documented for the torch stack (see CLAUDE.md).
    Overridable via ``ROCKFORGE_BEATTHIS_DEVICE`` and, for the checkpoint,
    ``ROCKFORGE_BEATTHIS_CHECKPOINT`` (default ``final0``). A shortname checkpoint
    is downloaded once from cloud.cp.jku.at (by us, then cached); if even that
    fails, set ``ROCKFORGE_BEATTHIS_CHECKPOINT`` to a manually-downloaded ``.ckpt``.

    ``dbn=False`` keeps the pure-torch "minimal" post-processor: the DBN
    post-processor would pull in madmom, whose models are CC BY-NC-SA
    (non-commercial) and which the project deliberately excludes.
    """
    from beat_this.inference import File2Beats

    checkpoint = os.environ.get("ROCKFORGE_BEATTHIS_CHECKPOINT", "final0")
    device = os.environ.get("ROCKFORGE_BEATTHIS_DEVICE", "cpu")
    try:
        local_ckpt = _resolve_checkpoint(checkpoint)
        file2beats = File2Beats(checkpoint_path=local_ckpt, device=device, dbn=False)
    except Exception as exc:
        # Download or load failed (offline, firewall, corrupt cache). Re-raise
        # with the manual-download fallback so the user can fix it, unless they
        # already pointed us at an explicit local file (then surface the real error).
        if not os.path.exists(checkpoint):
            raise RuntimeError(
                f"could not load the Beat This! checkpoint {checkpoint!r} — it is "
                "downloaded from cloud.cp.jku.at on first use. If that keeps failing, "
                f"download https://cloud.cp.jku.at/public.php/dav/files/7ik4RrBKTS273gp/"
                f"{checkpoint}.ckpt manually and set ROCKFORGE_BEATTHIS_CHECKPOINT to "
                "the saved file path."
            ) from exc
        raise
    # File2Beats returns (beats, downbeats) in seconds (README usage order); take
    # the downbeats (measure starts) as the per-measure tempo map.
    _beats, downbeats = file2beats(str(audio))
    return sorted(float(t) for t in downbeats)
