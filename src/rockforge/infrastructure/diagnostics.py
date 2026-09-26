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
- **Inside the `.exe`, a bare `pip install` instruction would be a lie.** A
  frozen PyInstaller app has its OWN Python: its `sys.path` is just the
  bundle's `_internal`, so the system's site-packages are never importable
  (verified by building a minimal frozen app and reading `sys.path` back).
  What it CAN do is hand the work to another interpreter — every ML stage
  already runs as a subprocess — so `_extras_install` rewrites those
  instructions to say where the packages have to go: the Python 3.11 that
  ``ROCKFORGE_ML_PYTHON`` points at. See ``infrastructure/ml_python.py``.
- **The ML rows report the interpreter that will actually run the work**, not
  this process. When that is another Python, it is asked in a subprocess what
  it has (`ml_python.probe`) — the API process must never import torch, and it
  could not answer for a different interpreter anyway.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from rockforge.infrastructure.ml_python import frozen

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


def _extras_install(pip_command: str, feature: str) -> str:
    """The install instruction, pointing at the interpreter that will run it.

    A `pip install` into the user's Python does nothing for the *frozen* `.exe`
    process — it has its own interpreter and never sees those packages. But the
    heavy stages all run as subprocesses, so the `.exe` can hand them to a
    Python that DOES have them: the instruction becomes "install there, and
    point ⚙️ Definições at it".
    """
    if not frozen():
        return pip_command
    return (
        f"O .exe tem o seu próprio Python e não instala pacotes. Para ter "
        f"{feature}: instala o Python 3.11, corre lá  {pip_command} , e indica "
        f"esse python.exe em ⚙️ Definições → «Python para o ML» "
        f"(ROCKFORGE_ML_PYTHON)."
    )


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
        install=_extras_install('pip install -e ".[psarc]"', "o .psarc nativo"),
        extras=["psarc"],
    )


@dataclass(frozen=True)
class _MlAvailability:
    """What the interpreter that will RUN the ML stages has.

    Not what this process has: in the `.exe` those are different interpreters,
    and reporting our own (empty) one would tell the user nothing about whether
    the feature works.
    """

    demucs: bool
    librosa: bool
    whisperx: bool
    torch: bool
    #: The interpreter's path, "" when there is none configured in a frozen build.
    interpreter: str
    #: Whether the work runs on a DIFFERENT interpreter from this process.
    external: bool
    #: Whether that interpreter could be run at all (False = wrong path / not a Python).
    reachable: bool


def _ml_availability() -> _MlAvailability:
    """Whom to ask is decided in ONE place (``ml_python.availability``), shared
    with the settings page — two answers to "does this machine have Demucs"
    would be worse than none."""
    from rockforge.infrastructure import ml_python

    found = ml_python.availability()
    return _MlAvailability(
        demucs=bool(found["demucs"]),
        librosa=bool(found["librosa"]),
        whisperx=bool(found["whisperx"]),
        torch=bool(found["torch"]),
        interpreter=str(found["interpreter"]),
        external=bool(found["external"]),
        reachable=bool(found["python"]),
    )


def _where(av: _MlAvailability) -> str:
    """The trailing "…, in <this/that> Python" half of a detail line."""
    if not av.external:
        return ""
    if not av.interpreter:
        return " — falta indicar o Python para o ML em ⚙️ Definições"
    if not av.reachable:
        return f" — {av.interpreter} não arrancou (não é um Python?)"
    return f" em {av.interpreter}"


def _ml_interpreter(av: _MlAvailability) -> Requirement:
    """The Python the heavy stages run on — the `.exe`'s one prerequisite for
    having any ML at all, and invisible until it is named."""
    if not av.external:
        found: bool | None = True
        detail = f"o próprio Python do RockForge ({av.interpreter})"
    elif not av.interpreter:
        found = False
        detail = "não está definido"
    elif not av.reachable:
        found = False
        detail = f"{av.interpreter} — não arrancou (o caminho aponta para um Python 3.11?)"
    else:
        have = [n for n, ok in (("ml", av.demucs and av.librosa), ("lyrics", av.whisperx)) if ok]
        detail = f"{av.interpreter} — extras: {', '.join(have) if have else 'nenhum'}"
        found = True
    return Requirement(
        key="ml_python",
        name="Python 3.11 para o ML",
        found=found,
        detail=detail,
        required=False,
        unlocks=(
            "É o interpretador onde correm o Demucs, o WhisperX e o librosa. "
            "Todos já corriam em subprocesso, por isso não precisam de estar "
            "dentro da app — só de existir um Python que os tenha."
        ),
        without_it=(
            "No .exe, separação de stems, deteção de tom e de letra e «Corrigir "
            "daqui» respondem 503. A partir do Python 3.11 (start.bat) usa-se o "
            "próprio e isto não é preciso."
        ),
        install=(
            "Instalar o Python 3.11, correr lá  pip install "
            'rockforge[ml,lyrics]  e indicar esse python.exe em ⚙️ Definições.'
        ),
    )


def _ml(av: _MlAvailability) -> Requirement:
    ok = av.demucs and av.librosa
    return Requirement(
        key="ml",
        name="Separação de stems e deteção de tom (Demucs, librosa)",
        found=ok,
        detail=("instalado" if ok else "em falta") + _where(av),
        required=False,
        unlocks=(
            "Separar instrumentos, detetar o tom da guitarra e medir o "
            "andamento a partir de um ponto (Corrigir daqui)."
        ),
        without_it="Esses botões respondem 503 a dizer que falta o extra; o resto funciona.",
        install=_extras_install('pip install -e ".[ml]"', "separação e deteção de tom"),
        extras=["ml"],
    )


def _lyrics(av: _MlAvailability) -> Requirement:
    ok = av.whisperx
    return Requirement(
        key="lyrics",
        name="Deteção automática de letra (WhisperX)",
        found=ok,
        detail=("instalado" if ok else "em falta") + _where(av),
        required=False,
        unlocks="Transcrever a letra da gravação e alinhá-la palavra a palavra.",
        without_it=(
            "A letra continua a poder vir do ficheiro GP, de um LRC/UltraStar, "
            "ou ser escrita à mão no editor."
        ),
        install=_extras_install(
            'pip install -e ".[ml,lyrics]"  (precisa também do [ml])',
            "deteção de letra",
        ),
        extras=["ml", "lyrics"],
    )


def _gpu(gpu_broken: bool, av: _MlAvailability | None = None) -> Requirement:
    installed = av.torch if av is not None else _has("torch")
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
        install=_extras_install(
            "pip install torch==2.4.1 torchaudio==2.4.1 --index-url "
            "https://download.pytorch.org/whl/cu121   (o pip install torch "
            "normal no Windows é só-CPU)",
            "aceleração por GPU",
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


def _ytdlp() -> Requirement:
    from rockforge.infrastructure.youtube_audio import ytdlp_command

    try:
        cmd = ytdlp_command()
    except Exception:  # noqa: BLE001 — a diagnostics page must not 500
        cmd = None
    return Requirement(
        key="ytdlp",
        name="yt-dlp (áudio do YouTube)",
        found=cmd is not None,
        detail=" ".join(cmd) if cmd else "em falta",
        required=False,
        unlocks=(
            "Descarregar o áudio do vídeo do YouTube em que o Songsterr marcou os "
            "tempos por compasso, para usar como gravação."
        ),
        without_it="Tens de carregar tu o MP3 convertido desse vídeo.",
        install='pip install yt-dlp  (ou pip install -e ".[youtube]")',
    )


def check_requirements(settings: Settings, *, gpu_broken: bool = False) -> list[Requirement]:
    """Probe every external dependency, most consequential first."""
    av = _ml_availability()
    return [
        _ffmpeg(),
        _wwise(settings),
        _psarc(),
        _ml_interpreter(av),
        _ml(av),
        _lyrics(av),
        _gpu(gpu_broken, av),
        _ytdlp(),
        _loader_patch(),
    ]


def missing_required(requirements: list[Requirement]) -> list[Requirement]:
    """The ones whose absence stops RockForge producing anything at all."""
    return [r for r in requirements if r.required and r.found is False]
