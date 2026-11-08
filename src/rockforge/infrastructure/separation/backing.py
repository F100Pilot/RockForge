"""A backing track: the recording without one of its separated instruments.

"The option to generate a .psarc without one of the stems would be HIGHLY
appreciated. Like a bass backing track without original bass stem to play bass"
(r/rocksmith, 2026-11-08). A Demucs pass writes every instrument it separates
into ONE folder, and those stems add back up to the recording; so the recording
without the bass is the sum of the bass's siblings in that folder (drums
included — "Separar instrumentos" only keeps them out of the player's list). The
sum is written as 32-bit float, which cannot clip; the build's normalizer then
gives it its gain like any recording. Separation is never perfect, so a faint
trace of the instrument taken out may remain — said where the option is offered.

The stems were separated from the recording untrimmed, so the mix keeps the
recording's clock: the start, the offset and every sync correction stay valid.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from rockforge.domain.errors import SeparationError
from rockforge.i18n import tr
from rockforge.infrastructure._subprocess import HARDENED_RUN_KWARGS, map_external_errors

MIX_TIMEOUT_S = 600


def backing_parts(stem: Path) -> list[Path]:
    """The other stems of the separation ``stem`` came out of, in name order."""
    return sorted(p for p in stem.parent.glob("*.wav") if p.name != stem.name)


def mix_backing(parts: list[Path], out: Path, ffmpeg: str = "ffmpeg") -> Path:
    """Sum ``parts`` sample by sample into ``out`` (32-bit float WAV)."""
    if not parts:
        raise SeparationError(tr(
            "Não há outros instrumentos separados para juntar.",
            "There are no other separated instruments to put together.",
        ))
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-y"]
    for p in parts:
        cmd += ["-i", str(p)]
    if len(parts) > 1:
        # normalize=0: a plain sum, as the stems add up to the recording
        # (amix otherwise divides every input by their number).
        cmd += ["-filter_complex", f"amix=inputs={len(parts)}:duration=longest:normalize=0"]
    cmd += ["-c:a", "pcm_f32le", str(out)]
    with map_external_errors(
        error_cls=SeparationError,
        not_installed_msg=tr("o ffmpeg não está instalado", "ffmpeg is not installed"),
        timeout_msg=tr(
            "juntar os instrumentos demorou demasiado",
            "putting the instruments together took too long",
        ),
        fail_msg_prefix=tr(
            "não foi possível juntar os instrumentos: ",
            "could not put the instruments together: ",
        ),
    ):
        subprocess.run(cmd, timeout=MIX_TIMEOUT_S, **HARDENED_RUN_KWARGS)
    return out


# The instruments htdemucs_6s separates, as the built song's title names them.
_WITHOUT = {
    "bass": ("sem baixo", "no bass"),
    "guitar": ("sem guitarra", "no guitar"),
    "vocals": ("sem voz", "no vocals"),
    "piano": ("sem piano", "no piano"),
    "other": ("sem outros", "no other"),
    "drums": ("sem bateria", "no drums"),
}


def without_label(stem: str) -> str:
    """"no bass" — what the built song's title says it leaves out."""
    pt, en = _WITHOUT.get(stem, (f"sem {stem}", f"no {stem}"))
    return tr(pt, en)
