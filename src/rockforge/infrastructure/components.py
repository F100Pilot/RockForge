"""The `.exe`'s extra components, installed by the app itself.

The standalone build carries the core (Guitar Pro → bundle + `.psarc`, with
its own ffmpeg) but not the heavy, optional parts: the ML stack (Demucs,
librosa, WhisperX — gigabytes, and a GPU build that differs per machine), the
PDF converter, yt-dlp and the JavaScript runtime YouTube's challenge needs.
Each of them already runs, or can run, in ANOTHER Python
(``ml_python.py``), so instead of asking the user to install Python and pip by
hand, the app installs a private one and points itself at it:

1. **Python 3.11** — the official ``python`` package on NuGet (a complete,
   relocatable Python published by the CPython release team: no installer, no
   registry, nothing outside its folder), unpacked into ``home()/python``;
2. **PyTorch** — the CUDA 12.1 build when an NVIDIA driver is present
   (``nvidia-smi``), otherwise PyPI's (CPU on Windows);
3. **the packages of the [ml], [lyrics], [youtube] and [pdf] extras** — the
   exact requirement strings of ``pyproject.toml`` (bundled at build time by
   ``rockforge.spec``), a ``git+`` URL turned into its GitHub archive so no git
   is needed;
4. **Deno** — yt-dlp's JavaScript runtime, into ``home()/tools`` (put on PATH
   at start, ``add_tools_to_path``).

Then ``ml_python`` is set to that interpreter. Wwise is NOT here and cannot be:
Audiokinetic's licence forbids redistributing it, and its launcher needs an
account — the app says so instead.

Runs on a background thread in the API process, like the tone-collection scan,
polled through ``GET /components``; every step's output goes to the log the UI
shows. Only offered in the Windows `.exe` (``supported``): a Python install has
``start.bat``, which installs the same extras into its own Python.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from rockforge.i18n import tr

EXTRAS = ("ml", "lyrics", "youtube", "pdf")
PYTHON_VERSION = "3.11.9"  # the last 3.11 with Windows binaries
PYTHON_PACKAGE_URL = f"https://www.nuget.org/api/v2/package/python/{PYTHON_VERSION}"
DENO_URL = (
    "https://github.com/denoland/deno/releases/latest/download/"
    "deno-x86_64-pc-windows-msvc.zip"
)
TORCH_CUDA_INDEX = "https://download.pytorch.org/whl/cu121"
# The [lyrics] extra pins torch/torchaudio below 2.5; 2.4.1 is the newest
# cu121 pair under it (the same pair docs/TECNICO.md tells start.bat users).
TORCH_CUDA = ("torch==2.4.1", "torchaudio==2.4.1")
STEP_TIMEOUT_S = 3600.0  # a CUDA torch is ~2.5 GB on a slow line
REQUIREMENTS_FILE = "components_requirements.json"
LOG_LINES = 400

Log = Callable[[str], None]


def supported() -> bool:
    """Only the Windows `.exe` installs its own components."""
    return bool(getattr(sys, "frozen", False)) and sys.platform == "win32"


def home() -> Path:
    """Where the components live: the user's local app data (not the work
    folder, which is in Downloads and holds the user's projects)."""
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / "RockForge" / "components"
    from rockforge import config

    return config.settings.work_dir / "components"


def python_exe(root: Path | None = None) -> Path:
    return (root or home()) / "python" / "python.exe"


def tools_dir(root: Path | None = None) -> Path:
    return (root or home()) / "tools"


def add_tools_to_path(root: Path | None = None) -> bool:
    """Put the components' tools (Deno) on PATH, so yt-dlp finds its runtime."""
    folder = tools_dir(root)
    if not folder.is_dir():
        return False
    parts = os.environ.get("PATH", "").split(os.pathsep)
    if str(folder) not in parts:
        os.environ["PATH"] = str(folder) + os.pathsep + os.environ.get("PATH", "")
    return True


def nvidia_gpu() -> bool:
    """Whether an NVIDIA driver is installed (it ships nvidia-smi)."""
    if shutil.which("nvidia-smi"):
        return True
    system = Path(os.environ.get("SYSTEMROOT", r"C:\Windows")) / "System32" / "nvidia-smi.exe"
    return system.exists()


# ── what to install ──────────────────────────────────────────────────────────


def _github_archive(requirement: str) -> str:
    """``pkg @ git+https://github.com/o/r@commit`` → the commit's zip archive,
    which pip installs without git on the machine."""
    name, sep, url = requirement.partition(" @ ")
    if not sep or not url.startswith("git+https://github.com/"):
        return requirement
    repo, _, ref = url[len("git+"):].rpartition("@")
    return f"{name} @ {repo}/archive/{ref}.zip" if repo and ref else requirement


def requirements_from_pyproject(pyproject: Path, extras: tuple[str, ...] = EXTRAS) -> list[str]:
    import tomllib

    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    optional = data.get("project", {}).get("optional-dependencies", {})
    out: list[str] = []
    for extra in extras:
        for req in optional.get(extra, []):
            if req not in out:
                out.append(req)
    return out


def requirements() -> list[str]:
    """The requirement strings of the extras, ready for pip. Read from the copy
    bundled with the `.exe`, or from ``pyproject.toml`` in a source checkout."""
    bundled = Path(__file__).resolve().parent / REQUIREMENTS_FILE
    if bundled.exists():
        reqs = [str(r) for r in json.loads(bundled.read_text(encoding="utf-8"))]
    else:
        reqs = requirements_from_pyproject(Path(__file__).resolve().parents[3] / "pyproject.toml")
    return [_github_archive(r) for r in reqs]


# ── state (one install at a time, polled by the UI) ──────────────────────────

_lock = threading.Lock()
_state: dict[str, Any] = {"status": "idle", "step": "", "log": [], "error": "", "started": 0.0}


def _log(line: str) -> None:
    with _lock:
        log = _state["log"]
        log.append(line.rstrip())
        del log[:-LOG_LINES]


def _set(**values: Any) -> None:
    with _lock:
        _state.update(values)


def busy() -> bool:
    with _lock:
        return bool(_state["status"] == "running")


# ── the two side effects, replaceable in tests ───────────────────────────────


def download(url: str, dest: Path, log: Log) -> None:
    """Stream ``url`` to ``dest`` over verified HTTPS, logging every 20 MB."""
    from rockforge.infrastructure._https import ssl_context

    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "RockForge components"})
    part = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(req, timeout=60, context=ssl_context()) as resp, \
            open(part, "wb") as out:
        done, next_mark = 0, 20 << 20
        while chunk := resp.read(1 << 20):
            out.write(chunk)
            done += len(chunk)
            if done >= next_mark:
                log(tr(f"  {done >> 20} MB descarregados", f"  {done >> 20} MB downloaded"))
                next_mark += 20 << 20
    part.replace(dest)


def run(cmd: list[str], log: Log, *, timeout_s: float = STEP_TIMEOUT_S) -> None:
    """Run a command, streaming its output into the log; raise on failure."""
    env = dict(os.environ, PYTHONNOUSERSITE="1", PIP_NO_INPUT="1",
               PIP_DISABLE_PIP_VERSION_CHECK="1", PYTHONIOENCODING="utf-8")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
        text=True, encoding="utf-8", errors="replace", env=env, creationflags=flags,
    )
    deadline = time.monotonic() + timeout_s
    assert proc.stdout is not None
    for line in proc.stdout:
        if line.strip():
            log("  " + line.rstrip())
        if time.monotonic() > deadline:
            proc.kill()
            raise RuntimeError(tr("o passo excedeu o tempo limite", "the step took too long"))
    code = proc.wait()
    if code != 0:
        raise RuntimeError(tr(f"terminou com o código {code}", f"ended with code {code}"))


def _extract(archive: Path, prefix: str, dest: Path) -> None:
    """Unpack the members under ``prefix`` into ``dest`` (never outside it)."""
    dest.mkdir(parents=True, exist_ok=True)
    root = dest.resolve()
    with zipfile.ZipFile(archive) as zf:
        for info in zf.infolist():
            name = info.filename.replace("\\", "/")
            if not name.startswith(prefix) or name.endswith("/"):
                continue
            target = (dest / name[len(prefix):]).resolve()
            if root not in target.parents:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, open(target, "wb") as out:
                shutil.copyfileobj(src, out)


# ── the install ──────────────────────────────────────────────────────────────


def install(log: Log, *, root: Path | None = None, gpu: bool | None = None,
            get: Callable[[str, Path, Log], None] | None = None,
            execute: Callable[[list[str], Log], None] | None = None) -> Path:
    """Install everything; returns the private python.exe."""
    get = get or download
    execute = execute or run
    root = root or home()
    gpu = nvidia_gpu() if gpu is None else gpu
    downloads = root / "downloads"
    py = python_exe(root)

    _set(step="python")
    if not py.exists():
        log(tr(f"Python {PYTHON_VERSION}: a descarregar…",
               f"Python {PYTHON_VERSION}: downloading…"))
        pkg = downloads / f"python-{PYTHON_VERSION}.nupkg"
        get(PYTHON_PACKAGE_URL, pkg, log)
        _extract(pkg, "tools/", py.parent)
        if not py.exists():
            raise RuntimeError(tr("o pacote do Python não trazia python.exe",
                                  "the Python package had no python.exe"))
    else:
        log(tr(f"Python {PYTHON_VERSION}: já instalado",
               f"Python {PYTHON_VERSION}: already installed"))
    execute([str(py), "-m", "ensurepip", "--upgrade"], log)
    execute([str(py), "-m", "pip", "install", "--upgrade", "pip"], log)

    pip = [str(py), "-m", "pip", "install", "--prefer-binary", "--no-warn-script-location"]
    _set(step="torch")
    if gpu:
        log(tr("GPU NVIDIA encontrada: PyTorch com CUDA (cerca de 2,5 GB)…",
               "NVIDIA GPU found: PyTorch with CUDA (about 2.5 GB)…"))
        execute([*pip, "--index-url", TORCH_CUDA_INDEX, *TORCH_CUDA], log)
    else:
        log(tr("Sem GPU NVIDIA: PyTorch para CPU.", "No NVIDIA GPU: PyTorch for the CPU."))

    _set(step="packages")
    log(tr("Pacotes de ML, letra, YouTube e PDF…", "ML, lyrics, YouTube and PDF packages…"))
    execute([*pip, *requirements()], log)

    _set(step="deno")
    deno = tools_dir(root) / "deno.exe"
    if not deno.exists():
        log(tr("Deno (para o YouTube): a descarregar…", "Deno (for YouTube): downloading…"))
        archive = downloads / "deno.zip"
        get(DENO_URL, archive, log)
        _extract(archive, "", tools_dir(root))
    add_tools_to_path(root)
    shutil.rmtree(downloads, ignore_errors=True)
    size = sum(f.stat().st_size for f in root.rglob("*") if f.is_file())
    log(tr(f"Espaço ocupado: {size / 1e9:.1f} GB em {root}",
           f"Space used: {size / 1e9:.1f} GB in {root}"))
    return py


def _use(py: Path) -> None:
    """Point the ML stages at the new interpreter — unless the user chose
    another one by hand."""
    from rockforge import runtime_settings

    data = runtime_settings.load()
    current = str(data.get("ml_python") or "")
    if current and Path(current) != py:
        return
    runtime_settings.save({**data, "ml_python": str(py), "components_declined": False})


def _worker() -> None:
    try:
        py = install(_log)
        _use(py)
        _log(tr("Concluído.", "Done."))
        _set(status="done", step="", error="")
    except Exception as exc:  # noqa: BLE001 — shown in the UI, never raised
        _log(tr(f"Falhou: {exc}", f"Failed: {exc}"))
        _set(status="error", error=str(exc))


def start_install() -> bool:
    """Start the install in the background; False when one is running."""
    with _lock:
        if _state["status"] == "running":
            return False
        _state.update(status="running", step="", log=[], error="", started=time.time())
    threading.Thread(target=_worker, name="rockforge-components", daemon=True).start()
    return True


def installed(root: Path | None = None) -> dict[str, bool]:
    """What is in place, asked of the private Python itself."""
    from rockforge.infrastructure import ml_python

    py = python_exe(root)
    found = ml_python.probe(str(py)) if py.exists() else {}
    return {
        "python": bool(found.get("python")),
        "ml": bool(found.get("demucs") and found.get("librosa")),
        "lyrics": bool(found.get("whisperx")),
        "youtube": bool(found.get("yt_dlp")),
        "pdf": bool(found.get("pdf_to_gp5")),
        "deno": (tools_dir(root) / "deno.exe").exists() or bool(shutil.which("deno")),
    }


def status() -> dict[str, Any]:
    from rockforge import runtime_settings

    with _lock:
        snap = {k: (list(v) if isinstance(v, list) else v) for k, v in _state.items()}
    ok = supported()
    have = installed() if ok and snap["status"] != "running" else {}
    return {
        "supported": ok,
        **snap,
        "installed": have,
        "complete": bool(have) and all(have.values()),
        "gpu": nvidia_gpu() if ok else False,
        "home": str(home()) if ok else "",
        "declined": runtime_settings.load().get("components_declined") is True,
        # Set by the installer's "install the extra components" task.
        "auto_install": os.environ.get("ROCKFORGE_INSTALL_COMPONENTS") == "1",
    }
