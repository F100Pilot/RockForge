"""What external software this machine has, and what each missing piece costs.

RockForge deliberately does NOT bundle most of what it depends on: Wwise cannot
be redistributed (Audiokinetic's EULA), the ML stack is gigabytes, and ffmpeg is
better taken from the system. Each of those already degrades cleanly on its own
— the bundle is still produced without Wwise, a missing `[ml]` extra is a 503
naming it, no `[psarc]` means only the `.psarc` is skipped — but until now
nothing told the user WHICH ones were missing or what they were losing. The
symptom is always downstream and looks like a bug: "o PSARC não é jogável",
"a deteção de letra não faz nada".

So this module answers one question — *what is installed, and what does each
absence cost me?* — in one place, honestly:

- **Nothing heavy is imported.** `importlib.util.find_spec` locates a package
  without importing it (the same trick `whisperx_adapter.available()` uses),
  which matters because the API process must never pay for torch (see
  CLAUDE.md's layering rules). The price is that we can report whether PyTorch
  is *installed*, never whether its CUDA build works — that is only knowable by
  importing it, in the worker.
- **`found` is a tri-state.** `None` means "cannot be checked from here", which
  is a different and more useful answer than `False`. The Rocksmith CDLC loader
  patch is the clearest case: it is the single most common reason a song never
  appears in game, and we have no idea where the user's game is installed.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rockforge.config import Settings

# ffmpeg -version is instant; the ceiling is only so a wedged binary cannot hang
# the endpoint. stdin is closed for the reason in CLAUDE.md's hard constraints:
# a console tool that inherits stdin can go interactive and block forever.
_FFMPEG_PROBE_TIMEOUT_S = 5.0


@dataclass(frozen=True)
class Requirement:
    """One piece of external software, and what hangs off it."""

    key: str
    name: str
    #: True = present, False = absent, None = not checkable from this process.
    found: bool | None
    #: Version, path, or why it could not be determined.
    detail: str
    #: True when RockForge cannot produce anything at all without it.
    required: bool
    #: What having it enables.
    unlocks: str
    #: What actually happens when it is missing — the honest cost, not a scare.
    without_it: str
    #: How to get it.
    install: str
    extras: list[str] = field(default_factory=list)


def _has(*modules: str) -> bool:
    """Whether every module can be located WITHOUT importing it."""
    for name in modules:
        try:
            if importlib.util.find_spec(name) is None:
                return False
        except (ImportError, ValueError):
            # A broken/partial install raises rather than returning None.
            return False
    return True


def _ffmpeg() -> Requirement:
    path = shutil.which("ffmpeg")
    detail = "não encontrado no PATH"
    if path:
        detail = path
        try:
            proc = subprocess.run(
                [path, "-version"],
                capture_output=True,
                text=True,
                timeout=_FFMPEG_PROBE_TIMEOUT_S,
                stdin=subprocess.DEVNULL,
            )
            first = (proc.stdout or "").splitlines()
            if first:
                detail = f"{first[0].strip()}  ({path})"
        except (OSError, subprocess.SubprocessError):
            detail = f"{path} (encontrado, mas não respondeu a -version)"
    return Requirement(
        key="ffmpeg",
        name="ffmpeg",
        found=bool(path),
        detail=detail,
        required=True,
        unlocks="Normalizar e converter a gravação — todo o pipeline passa por aqui.",
        without_it="Nenhum job chega ao fim: falha na fase de normalização.",
        install="winget install ffmpeg  (ou pôr o ffmpeg.exe no PATH)",
    )


def _wwise(settings: Settings) -> Requirement:
    from rockforge.infrastructure.packaging.wwise import WwiseWemConverter

    root = settings.resolved_wwise_root()
    console = WwiseWemConverter(root).console_path() if root else None
    if console is not None:
        detail = str(console)
    elif root is not None:
        detail = f"{root} — não contém Authoring/x64/Release/bin/WwiseConsole"
    else:
        detail = "ROCKFORGE_WWISE_ROOT (ou WWISEROOT) não está definido"
    return Requirement(
        key="wwise",
        name="Audiokinetic Wwise (2019/2021/2022/2023)",
        found=console is not None,
        detail=detail,
        required=False,
        unlocks="Converte o áudio para .wem, o que torna o .psarc JOGÁVEL.",
        without_it=(
            "O bundle para o DLC Builder continua a ser produzido, mas o .psarc "
            "nativo fica sem áudio e o jogo não o toca."
        ),
        install=(
            "Instalar o Wwise (Audiokinetic Launcher) e apontar "
            "ROCKFORGE_WWISE_ROOT à raiz da instalação. Não pode ser "
            "distribuído com a app — a licença não o permite."
        ),
    )


def _psarc() -> Requirement:
    ok = _has("cryptography", "PIL")
    return Requirement(
        key="psarc",
        name="Encriptação do PSARC + capa (cryptography, Pillow)",
        found=ok,
        detail="instalado" if ok else "em falta",
        required=False,
        unlocks="Escrever o .psarc nativo (SNG encriptado) e a capa em DDS.",
        without_it="Só sai o bundle do DLC Builder; o .psarc é omitido, sem crash.",
        install='pip install -e ".[psarc]"',
        extras=["psarc"],
    )


def _ml() -> Requirement:
    ok = _has("demucs", "librosa")
    return Requirement(
        key="ml",
        name="Separação de stems e deteção de tom (Demucs, librosa)",
        found=ok,
        detail="instalado" if ok else "em falta",
        required=False,
        unlocks=(
            "Separar instrumentos, detetar o tom da guitarra e medir o "
            "andamento a partir de um ponto (Corrigir daqui)."
        ),
        without_it="Esses botões respondem 503 a dizer que falta o extra; o resto funciona.",
        install='pip install -e ".[ml]"',
        extras=["ml"],
    )


def _lyrics() -> Requirement:
    ok = _has("whisperx")
    return Requirement(
        key="lyrics",
        name="Deteção automática de letra (WhisperX)",
        found=ok,
        detail="instalado" if ok else "em falta",
        required=False,
        unlocks="Transcrever a letra da gravação e alinhá-la palavra a palavra.",
        without_it=(
            "A letra continua a poder vir do ficheiro GP, de um LRC/UltraStar, "
            "ou ser escrita à mão no editor."
        ),
        install='pip install -e ".[ml,lyrics]"  (precisa também do [ml])',
        extras=["ml", "lyrics"],
    )


def _gpu(gpu_broken: bool) -> Requirement:
    installed = _has("torch")
    if not installed:
        detail = "PyTorch não está instalado"
    elif gpu_broken:
        detail = (
            "PyTorch instalado, mas a GPU está marcada como avariada depois de "
            "um crash — tudo corre em CPU até carregares em «Reativar GPU»"
        )
    else:
        detail = (
            "PyTorch instalado. Se é a build CUDA ou a CPU não é verificável "
            "aqui (importar o torch no processo da API é proibido) — o log de "
            "deteção escreve «device: cuda (GPU)» quando a GPU está a ser usada"
        )
    # Installed-but-unverifiable is genuinely UNKNOWN, not "yes": claiming the
    # GPU works when we only know torch is importable would be the kind of
    # confident-and-wrong answer this app exists to avoid.
    found: bool | None = False if (not installed or gpu_broken) else None
    return Requirement(
        key="gpu",
        name="Aceleração por GPU (PyTorch CUDA)",
        found=found,
        detail=detail,
        required=False,
        unlocks="Separação e transcrição em minutos em vez de dezenas de minutos.",
        without_it="Tudo funciona na mesma, em CPU — só demora muito mais.",
        install=(
            "pip install torch==2.4.1 torchaudio==2.4.1 --index-url "
            "https://download.pytorch.org/whl/cu121   (o pip install torch "
            "normal no Windows é só-CPU)"
        ),
    )


def _loader_patch() -> Requirement:
    return Requirement(
        key="cdlc_patch",
        name="Patch de CDLC do Rocksmith (D3DX9_42.dll)",
        found=None,
        detail="não é detetável daqui — não sabemos onde tens o jogo instalado",
        required=False,
        unlocks="Sem ele o Rocksmith recusa qualquer CDLC, venha de onde vier.",
        without_it=(
            "A música nunca aparece na lista do jogo, por mais correto que o "
            ".psarc esteja. É a causa nº1 de «não aparece»."
        ),
        install=(
            "Instalar o patch na pasta do Rocksmith 2014 (CustomsForge). "
            "Confirma também que tens o DLC cujo appid o .psarc reutiliza."
        ),
    )


def check_requirements(settings: Settings, *, gpu_broken: bool = False) -> list[Requirement]:
    """Probe every external dependency, most consequential first."""
    return [
        _ffmpeg(),
        _wwise(settings),
        _psarc(),
        _ml(),
        _lyrics(),
        _gpu(gpu_broken),
        _loader_patch(),
    ]


def missing_required(requirements: list[Requirement]) -> list[Requirement]:
    """The ones whose absence stops RockForge producing anything at all."""
    return [r for r in requirements if r.required and r.found is False]
