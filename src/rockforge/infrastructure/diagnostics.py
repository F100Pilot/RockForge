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
  appears in game, and it is only checkable when the game is in a Steam library
  on THIS machine (RockForge may run on another one).
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
from pathlib import Path
from typing import TYPE_CHECKING

from rockforge.i18n import tr
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
    return tr(
        f"O .exe tem o seu próprio Python e não instala pacotes. Para ter "
        f"{feature}: instala o Python 3.11, corre lá  {pip_command} , e indica "
        f"esse python.exe em ⚙️ Definições → «Python para o ML» "
        f"(ROCKFORGE_ML_PYTHON).",
        f"The .exe has its own Python and does not install packages. To get "
        f"{feature}: install Python 3.11, run  {pip_command}  there, and point "
        f"⚙️ Settings → «Python for ML» at that python.exe "
        f"(ROCKFORGE_ML_PYTHON).",
    )


def _installed(ok: bool) -> str:
    return tr("instalado", "installed") if ok else tr("em falta", "missing")


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
    detail = tr("não encontrado no PATH", "not found on PATH")
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
            detail = tr(
                f"{path} (encontrado, mas não respondeu a -version)",
                f"{path} (found, but did not answer -version)",
            )
    return Requirement(
        key="ffmpeg",
        name="ffmpeg",
        found=bool(path),
        detail=detail,
        required=True,
        unlocks=tr(
            "Normalizar e converter a gravação — todo o pipeline passa por aqui.",
            "Normalizing and converting the recording — the whole pipeline goes through it.",
        ),
        without_it=tr(
            "Nenhum job chega ao fim: falha na fase de normalização.",
            "No job finishes: it fails at the normalization stage.",
        ),
        install=tr(
            "winget install ffmpeg  (ou pôr o ffmpeg.exe no PATH)",
            "winget install ffmpeg  (or put ffmpeg.exe on the PATH)",
        ),
    )


def _wwise(settings: Settings) -> Requirement:
    from rockforge.infrastructure.packaging.wwise import WwiseWemConverter

    root = settings.resolved_wwise_root()
    console = WwiseWemConverter(root).console_path() if root else None
    if console is not None:
        detail = str(console)
    elif root is not None:
        detail = tr(
            f"{root} — não contém Authoring/x64/Release/bin/WwiseConsole",
            f"{root} — does not contain Authoring/x64/Release/bin/WwiseConsole",
        )
    else:
        detail = tr(
            "ROCKFORGE_WWISE_ROOT (ou WWISEROOT) não está definido",
            "ROCKFORGE_WWISE_ROOT (or WWISEROOT) is not set",
        )
    return Requirement(
        key="wwise",
        name="Audiokinetic Wwise (2019/2021/2022/2023)",
        found=console is not None,
        detail=detail,
        required=False,
        unlocks=tr(
            "Converte o áudio para .wem, o que torna o .psarc JOGÁVEL.",
            "Converts the audio to .wem, which makes the .psarc PLAYABLE.",
        ),
        without_it=tr(
            "O bundle para o DLC Builder continua a ser produzido, mas o .psarc "
            "nativo fica sem áudio e o jogo não o toca.",
            "The DLC Builder bundle is still produced, but the native .psarc "
            "has no audio and the game does not play it.",
        ),
        install=tr(
            "Instalar o Wwise (Audiokinetic Launcher) e apontar "
            "ROCKFORGE_WWISE_ROOT à raiz da instalação. Não pode ser "
            "distribuído com a app — a licença não o permite.",
            "Install Wwise (Audiokinetic Launcher) and point "
            "ROCKFORGE_WWISE_ROOT at the installation's root. It cannot be "
            "distributed with the app — its license does not allow it.",
        ),
    )


def _psarc() -> Requirement:
    ok = _has("cryptography", "PIL")
    return Requirement(
        key="psarc",
        name=tr(
            "Encriptação do PSARC + capa (cryptography, Pillow)",
            "PSARC encryption + cover (cryptography, Pillow)",
        ),
        found=ok,
        detail=_installed(ok),
        required=False,
        unlocks=tr(
            "Escrever o .psarc nativo (SNG encriptado) e a capa em DDS.",
            "Writing the native .psarc (encrypted SNG) and the cover as DDS.",
        ),
        without_it=tr(
            "Só sai o bundle do DLC Builder; o .psarc é omitido, sem crash.",
            "Only the DLC Builder bundle comes out; the .psarc is left out, no crash.",
        ),
        install=_extras_install(
            'pip install -e ".[psarc]"', tr("o .psarc nativo", "the native .psarc"),
        ),
        extras=["psarc"],
    )


def _pdf_converter() -> Requirement:
    from rockforge.infrastructure.gpimport import pdf_import

    ok = pdf_import.available()
    ocr = ok and pdf_import.ocr_available()
    if not ok:
        detail = _installed(False)
    elif ocr:
        detail = tr("instalado, com OCR", "installed, with OCR")
    else:
        detail = tr("instalado, sem OCR (só PDFs com texto)", "installed, no OCR (text PDFs only)")
    # It runs in THIS process (not through «Python para o ML»), so in the .exe
    # it is there only when the build included it.
    install = (
        tr(
            "Este .exe foi construído sem o conversor de PDF.",
            "This .exe was built without the PDF converter.",
        )
        if frozen()
        else 'pip install -e ".[pdf]"'
    )
    return Requirement(
        key="pdf",
        name=tr("Conversor de PDF (PDF-to-GP5)", "PDF converter (PDF-to-GP5)"),
        found=ok,
        detail=detail,
        required=False,
        unlocks=tr(
            "No «Novo projeto», criar o ficheiro Guitar Pro a partir de um PDF ou de "
            "uma imagem da tablatura; com OCR, também imagens e PDFs só com imagens.",
            "In «New project», making the Guitar Pro file from a PDF or a picture of "
            "the tab; with OCR, pictures and image-only PDFs too.",
        ),
        without_it=tr(
            "Um PDF ou uma imagem é recusado com a indicação do que instalar; os "
            "ficheiros Guitar Pro e o Songsterr continuam a funcionar.",
            "A PDF or a picture is refused, saying what to install; Guitar Pro files "
            "and Songsterr still work.",
        ),
        install=install,
        extras=["pdf"],
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
        return tr(
            " — falta indicar o Python para o ML em ⚙️ Definições",
            " — the Python for ML has not been set in ⚙️ Settings",
        )
    if not av.reachable:
        return tr(
            f" — {av.interpreter} não arrancou (não é um Python?)",
            f" — {av.interpreter} did not start (is it not a Python?)",
        )
    return tr(f" em {av.interpreter}", f" in {av.interpreter}")


def _ml_interpreter(av: _MlAvailability) -> Requirement:
    """The Python the heavy stages run on — the `.exe`'s one prerequisite for
    having any ML at all, and invisible until it is named."""
    if not av.external:
        found: bool | None = True
        detail = tr(
            f"o próprio Python do RockForge ({av.interpreter})",
            f"RockForge's own Python ({av.interpreter})",
        )
    elif not av.interpreter:
        found = False
        detail = tr("não está definido", "not set")
    elif not av.reachable:
        found = False
        detail = tr(
            f"{av.interpreter} — não arrancou (o caminho aponta para um Python 3.11?)",
            f"{av.interpreter} — did not start (does the path point at a Python 3.11?)",
        )
    else:
        have = [n for n, ok in (("ml", av.demucs and av.librosa), ("lyrics", av.whisperx)) if ok]
        listed = ", ".join(have) if have else tr("nenhum", "none")
        detail = f"{av.interpreter} — extras: {listed}"
        found = True
    return Requirement(
        key="ml_python",
        name=tr("Python 3.11 para o ML", "Python 3.11 for ML"),
        found=found,
        detail=detail,
        required=False,
        unlocks=tr(
            "É o interpretador onde correm o Demucs, o WhisperX e o librosa. "
            "Todos já corriam em subprocesso, por isso não precisam de estar "
            "dentro da app — só de existir um Python que os tenha.",
            "It is the interpreter Demucs, WhisperX and librosa run on. "
            "They all already ran as subprocesses, so they do not need to be "
            "inside the app — only a Python that has them needs to exist.",
        ),
        without_it=tr(
            "No .exe, separação de stems, deteção de tom e de letra e «Corrigir "
            "daqui» respondem 503. A partir do Python 3.11 (start.bat) usa-se o "
            "próprio e isto não é preciso.",
            "In the .exe, stem separation, tone and lyric detection and «Fix "
            "from here» answer 503. From Python 3.11 (start.bat) its own "
            "Python is used and this is not needed.",
        ),
        install=tr(
            "Instalar o Python 3.11, correr lá  pip install "
            'rockforge[ml,lyrics]  e indicar esse python.exe em ⚙️ Definições.',
            "Install Python 3.11, run  pip install "
            'rockforge[ml,lyrics]  there and point ⚙️ Settings at that python.exe.',
        ),
    )


def _ml(av: _MlAvailability) -> Requirement:
    ok = av.demucs and av.librosa
    return Requirement(
        key="ml",
        name=tr(
            "Separação de stems e deteção de tom (Demucs, librosa)",
            "Stem separation and tone detection (Demucs, librosa)",
        ),
        found=ok,
        detail=_installed(ok) + _where(av),
        required=False,
        unlocks=tr(
            "Separar instrumentos, detetar o tom da guitarra e medir o "
            "andamento a partir de um ponto (Corrigir daqui).",
            "Separating instruments, detecting the guitar's tone and measuring "
            "the tempo from a point on (Fix from here).",
        ),
        without_it=tr(
            "Esses botões respondem 503 a dizer que falta o extra; o resto funciona.",
            "Those buttons answer 503 saying the extra is missing; the rest works.",
        ),
        install=_extras_install(
            'pip install -e ".[ml]"',
            tr("separação e deteção de tom", "separation and tone detection"),
        ),
        extras=["ml"],
    )


def _lyrics(av: _MlAvailability) -> Requirement:
    ok = av.whisperx
    return Requirement(
        key="lyrics",
        name=tr(
            "Deteção automática de letra (WhisperX)",
            "Automatic lyric detection (WhisperX)",
        ),
        found=ok,
        detail=_installed(ok) + _where(av),
        required=False,
        unlocks=tr(
            "Transcrever a letra da gravação e alinhá-la palavra a palavra.",
            "Transcribing the lyrics from the recording and aligning them word by word.",
        ),
        without_it=tr(
            "A letra continua a poder vir do ficheiro GP, de um LRC/UltraStar, "
            "ou ser escrita à mão no editor.",
            "The lyrics can still come from the GP file, from an LRC/UltraStar "
            "file, or be typed by hand in the editor.",
        ),
        install=_extras_install(
            tr(
                'pip install -e ".[ml,lyrics]"  (precisa também do [ml])',
                'pip install -e ".[ml,lyrics]"  (it needs [ml] too)',
            ),
            tr("deteção de letra", "lyric detection"),
        ),
        extras=["ml", "lyrics"],
    )


def _gpu(gpu_broken: bool, av: _MlAvailability | None = None) -> Requirement:
    installed = av.torch if av is not None else _has("torch")
    if not installed:
        detail = tr("PyTorch não está instalado", "PyTorch is not installed")
    elif gpu_broken:
        detail = tr(
            "PyTorch instalado, mas a GPU está marcada como avariada depois de "
            "um crash — tudo corre em CPU até carregares em «Reativar GPU»",
            "PyTorch installed, but the GPU is marked as broken after a "
            "crash — everything runs on the CPU until you press «Re-enable GPU»",
        )
    else:
        detail = tr(
            "PyTorch instalado. Se é a build CUDA ou a CPU não é verificável "
            "aqui (importar o torch no processo da API é proibido) — o log de "
            "deteção escreve «device: cuda (GPU)» quando a GPU está a ser usada",
            "PyTorch installed. Whether it is the CUDA or the CPU build cannot "
            "be checked here (importing torch in the API process is forbidden) — "
            "the detection log writes «device: cuda (GPU)» when the GPU is in use",
        )
    # Installed-but-unverifiable is genuinely UNKNOWN, not "yes": claiming the
    # GPU works when we only know torch is importable would be the kind of
    # confident-and-wrong answer this app exists to avoid.
    found: bool | None = False if (not installed or gpu_broken) else None
    return Requirement(
        key="gpu",
        name=tr("Aceleração por GPU (PyTorch CUDA)", "GPU acceleration (PyTorch CUDA)"),
        found=found,
        detail=detail,
        required=False,
        unlocks=tr(
            "Separação e transcrição em minutos em vez de dezenas de minutos.",
            "Separation and transcription in minutes instead of tens of minutes.",
        ),
        without_it=tr(
            "Tudo funciona na mesma, em CPU — só demora muito mais.",
            "Everything still works, on the CPU — it just takes much longer.",
        ),
        install=_extras_install(
            tr(
                "pip install torch==2.4.1 torchaudio==2.4.1 --index-url "
                "https://download.pytorch.org/whl/cu121   (o pip install torch "
                "normal no Windows é só-CPU)",
                "pip install torch==2.4.1 torchaudio==2.4.1 --index-url "
                "https://download.pytorch.org/whl/cu121   (the plain pip install "
                "torch on Windows is CPU-only)",
            ),
            tr("aceleração por GPU", "GPU acceleration"),
        ),
    )


PATCH_DLL = "D3DX9_42.dll"


def detected_rocksmith_folder() -> Path | None:
    """The game folder found without asking: the parent of the dlc folder the
    tone collection was pointed at (it may be in a Steam library we would not
    guess), else the one Steam knows about."""
    from rockforge import runtime_settings
    from rockforge.infrastructure.tone_collection import rocksmith_game_folders

    stored = runtime_settings.rocksmith_dlc_dir()
    if stored:
        parent = stored.parent
        if (parent / "Rocksmith2014.exe").is_file():
            return parent
    games = rocksmith_game_folders()
    return games[0] if games else None


def _has_file(folder: Path, name: str) -> bool:
    try:
        return any(p.name.lower() == name.lower() for p in folder.iterdir())
    except OSError:
        return False


def _loader_patch() -> Requirement:
    from rockforge.infrastructure.tone_collection import configured_game_folder

    configured = configured_game_folder()
    game = configured or detected_rocksmith_folder()
    found: bool | None
    if configured is not None and not configured.is_dir():
        found = None
        detail = tr(
            "a pasta do Rocksmith indicada nas Definições não existe: {path}",
            "the Rocksmith folder set in Settings does not exist: {path}",
        ).format(path=configured)
    elif game is None:
        found = None
        detail = tr(
            "o Rocksmith 2014 não foi encontrado neste computador (procurei nas "
            "bibliotecas do Steam) — indica a pasta em Definições → Geral; se o "
            "jogo está noutro computador, é lá que o patch tem de estar",
            "Rocksmith 2014 was not found on this computer (Steam libraries "
            "searched) — set its folder in Settings → General; if the game is on "
            "another computer, that is where the patch has to be",
        )
    elif _has_file(game, PATCH_DLL):
        found, detail = True, str(game / PATCH_DLL)
    else:
        found = False
        detail = tr(
            "não está na pasta do jogo: {path}",
            "not in the game folder: {path}",
        ).format(path=game)
    return Requirement(
        key="cdlc_patch",
        name=tr(
            "Patch de CDLC do Rocksmith (D3DX9_42.dll)",
            "Rocksmith CDLC patch (D3DX9_42.dll)",
        ),
        found=found,
        detail=detail,
        required=False,
        unlocks=tr(
            "Sem ele o Rocksmith recusa qualquer CDLC, venha de onde vier.",
            "Without it Rocksmith refuses any CDLC, wherever it comes from.",
        ),
        without_it=tr(
            "A música nunca aparece na lista do jogo, por mais correto que o "
            ".psarc esteja. É a causa nº1 de «não aparece».",
            "The song never shows up in the game's list, however correct the "
            ".psarc is. It is the no. 1 cause of «it does not show up».",
        ),
        install=tr(
            "Descarrega o «CDLC Enabler» do CustomsForge (customsforge.com) e "
            "copia o D3DX9_42.dll para a pasta do Rocksmith 2014 (no Steam: "
            "botão direito no jogo → Gerir → Procurar ficheiros locais). "
            "Confirma também que tens o DLC cujo appid o .psarc reutiliza.",
            "Download the «CDLC Enabler» from CustomsForge (customsforge.com) "
            "and copy D3DX9_42.dll into the Rocksmith 2014 folder (in Steam: "
            "right-click the game → Manage → Browse local files). Also make "
            "sure you own the DLC whose appid the .psarc reuses.",
        ),
    )


def _ytdlp() -> Requirement:
    from rockforge.infrastructure.youtube_audio import JS_RUNTIMES, ytdlp_command

    try:
        cmd = ytdlp_command()
    except Exception:  # noqa: BLE001 — a diagnostics page must not 500
        cmd = None
    runtimes = [name for name, program in JS_RUNTIMES if shutil.which(program)]
    # The solver can only be looked up when yt-dlp runs in THIS interpreter;
    # for a yt-dlp program or another Python it is unknown, not missing.
    in_process = cmd is not None and cmd[1:3] == ["-m", "yt_dlp"] and not frozen()
    solver = _has("yt_dlp_ejs") if in_process else None
    found: bool | None
    if cmd is None:
        found, detail = False, tr("em falta", "missing")
    elif not runtimes:
        found, detail = False, tr(
            "yt-dlp encontrado, mas sem motor JavaScript (Deno)",
            "yt-dlp found, but no JavaScript runtime (Deno)",
        )
    elif solver is False:
        found, detail = False, tr(
            "yt-dlp sem o solucionador do YouTube (yt-dlp-ejs)",
            "yt-dlp without the YouTube challenge solver (yt-dlp-ejs)",
        )
    else:
        found = True if solver else None
        detail = tr(
            f"{' '.join(cmd)} · motor JS: {', '.join(runtimes)}",
            f"{' '.join(cmd)} · JS runtime: {', '.join(runtimes)}",
        )
    return Requirement(
        key="ytdlp",
        name=tr("yt-dlp (áudio do YouTube)", "yt-dlp (YouTube audio)"),
        found=found,
        detail=detail,
        required=False,
        unlocks=tr(
            "Descarregar o áudio do vídeo do YouTube em que o Songsterr marcou os "
            "tempos por compasso, para usar como gravação.",
            "Downloading the audio of the YouTube video Songsterr marked the "
            "per-bar times on, to use as the recording.",
        ),
        without_it=tr(
            "Tens de carregar tu o MP3 convertido desse vídeo. Sem o motor "
            "JavaScript o YouTube recusa o download mesmo com o yt-dlp instalado.",
            "You have to upload the MP3 converted from that video yourself. Without "
            "the JavaScript runtime YouTube refuses the download even with yt-dlp "
            "installed.",
        ),
        install=tr(
            'pip install -U "yt-dlp[default]"  +  o Deno: winget install DenoLand.Deno',
            'pip install -U "yt-dlp[default]"  +  Deno: winget install DenoLand.Deno',
        ),
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
        _pdf_converter(),
        _loader_patch(),
    ]


def missing_required(requirements: list[Requirement]) -> list[Requirement]:
    """The ones whose absence stops RockForge producing anything at all."""
    return [r for r in requirements if r.required and r.found is False]
