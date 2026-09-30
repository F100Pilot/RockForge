"""Which Python interpreter runs the heavy ML stages.

Every ML stage RockForge has already runs, or can run, in a **subprocess**:
Demucs through ``_demucs_patcher.py``, WhisperX through ``_whisperx_runner.py``
(that one for the faster-whisper/ctranslate2 CUDA deadlock, see CLAUDE.md),
Banquet through the query-bandit repo's own ``train.py``, and — since this
module — librosa through ``_librosa_runner.py``. None of them needs the heavy
package importable in the calling process.

That matters because of one line repeated at each of those call sites:
``sys.executable``. In a PyInstaller build **that is the `.exe` itself**, not a
Python interpreter, so the subprocess would relaunch RockForge instead of
running Demucs. Combined with a frozen app's inability to see the system's
site-packages (`sys.path` is just the bundle's `_internal`), the standalone
build simply had no ML — and the ⚙️ panel said so, correctly but bluntly.

``ROCKFORGE_ML_PYTHON`` (editable in ⚙️ Definições) closes that: point it at a
Python 3.11 that has ``pip install rockforge[ml,lyrics]`` and the `.exe`
delegates the heavy stages to it. It is exactly the arrangement ffmpeg and
Wwise already have — external software, installed once, outside the app.

Two deliberate properties:

- **Nothing changes when it is unset and we are not frozen.** ``resolve()``
  returns ``sys.executable``, which is what every call site passed before, so
  running from a Python install (``start.bat``) is byte-for-byte the old path.
- **Nothing heavy is imported here.** ``probe`` asks the *other* interpreter
  what it has, in a subprocess — the API process must never import torch.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from rockforge.i18n import tr

#: A probe only imports a few packages; a ceiling so a wedged interpreter (or
#: one on a sleeping network drive) cannot hang the settings page.
PROBE_TIMEOUT_S = 60.0
#: librosa feature extraction on a full song is seconds, not minutes.
LIBROSA_TIMEOUT_S = 600.0


def frozen() -> bool:
    """Whether this is the PyInstaller build rather than a Python install."""
    return bool(getattr(sys, "frozen", False))


def configured() -> Path | None:
    """The interpreter the user pointed us at, if any (runtime override first,
    then ``ROCKFORGE_ML_PYTHON``)."""
    from rockforge import runtime_settings

    return runtime_settings.ml_python()


def resolve() -> str | None:
    """The interpreter to run ML subprocesses with, or None if there is none.

    None means "this build cannot run that stage at all", which callers turn
    into the same 503-naming-the-missing-piece they already raise for a missing
    extra — never a crash.
    """
    cfg = configured()
    if cfg is not None:
        return str(cfg)
    if frozen():
        # sys.executable is the .exe: running it would relaunch RockForge.
        return None
    return sys.executable


def missing_message(feature: str) -> str:
    """Why ``feature`` is unavailable, phrased as the thing to go and do."""
    if frozen():
        return tr(
            f"{feature} precisa do Python 3.11 com os extras [ml,lyrics]. "
            "O .exe tem o seu próprio Python e não os pode instalar — indica "
            "em ⚙️ Definições o caminho para um python.exe que os tenha "
            "(ROCKFORGE_ML_PYTHON).",
            f"{feature} needs Python 3.11 with the [ml,lyrics] extras. "
            "The .exe has its own Python and cannot install them — set the "
            "path to a python.exe that has them in ⚙️ Settings "
            "(ROCKFORGE_ML_PYTHON).",
        )
    return tr(
        f"{feature} precisa dos extras de ML (pip install -e \".[ml,lyrics]\").",
        f"{feature} needs the ML extras (pip install -e \".[ml,lyrics]\").",
    )


def runner_path(package_dir: Path, name: str) -> Path:
    """Locate a standalone runner script that sits beside ``package_dir``.

    Inside a PyInstaller bundle the package's modules live in the archive, not
    on disk, so a runner has to be shipped as a DATA file at its package path
    (``rockforge.spec``, guarded by ``test_standalone_spec.py``). ``__file__``
    already points under ``sys._MEIPASS`` there, so the ordinary path works;
    the explicit fallback covers a bundle laid out differently rather than
    failing with a confusing "no such file".
    """
    candidate = package_dir / name
    if candidate.exists():
        return candidate
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        try:
            rel = package_dir.relative_to(Path(meipass))
        except ValueError:
            rel = Path(*package_dir.parts[-3:])
        alt = Path(meipass) / rel / name
        if alt.exists():
            return alt
    return candidate


#: The packages any ML stage needs, reported per interpreter.
PACKAGES = ("demucs", "librosa", "whisperx", "torch")


def here(module: str) -> bool:
    """Whether THIS process can import ``module``, checked WITHOUT importing it
    (``find_spec`` locates a package but does not run it — the API process must
    never pay for torch, see CLAUDE.md's layering rule)."""
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        # A half-removed install raises rather than returning None.
        return False


def availability() -> dict[str, Any]:
    """What the interpreter that will RUN the ML stages has.

    The ONE place that decides whom to ask, so the diagnostics page and the
    settings page can never disagree about it:

    - running from a Python install with nothing configured, this process IS
      that interpreter, so ``find_spec`` answers exactly and instantly — there
      is nothing to gain from spawning a subprocess to ask ourselves, and
      ``/settings`` is opened often enough for that to be felt;
    - otherwise (the `.exe`, or an explicitly configured Python) the packages
      live somewhere else and only that interpreter can answer.

    ``external`` says which happened; ``python`` is False for a configured path
    that is not a working interpreter at all — a different fix from "it runs
    but has no demucs".
    """
    cfg = configured()
    if cfg is None and not frozen():
        return {
            "python": True,
            "external": False,
            "interpreter": sys.executable,
            **{name: here(name) for name in PACKAGES},
        }
    return {
        "external": True,
        "interpreter": str(cfg) if cfg else "",
        **probe(),
    }


def probe(interpreter: str | None = None) -> dict[str, bool]:
    """Which extras the ML interpreter has, asked of IT rather than of us.

    Returns a flag per package plus ``python`` (the interpreter ran at all).
    Every failure mode — no such file, not a Python, a timeout, garbage on
    stdout — is a False, never an exception: this backs a diagnostics page,
    which must not be the thing that breaks.
    """
    empty = dict.fromkeys(("python", *PACKAGES), False)
    py = interpreter if interpreter is not None else resolve()
    if not py:
        return empty
    script = (
        "import importlib.util as u, json, sys;"
        "print(json.dumps({n: u.find_spec(n) is not None for n in "
        f"{list(PACKAGES)!r}}}))"
    )
    try:
        # stdin=DEVNULL for the reason in _subprocess.HARDENED_RUN_KWARGS (a CLI
        # that inherits a console's stdin can go interactive and block forever).
        # check=True is deliberately NOT used: a failing probe is a False.
        proc = subprocess.run(
            [py, "-c", script],
            capture_output=True,
            text=True,
            timeout=PROBE_TIMEOUT_S,
            stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.SubprocessError):
        return empty
    if proc.returncode != 0:
        return empty
    try:
        found = json.loads(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return empty
    if not isinstance(found, dict):
        return empty
    return {"python": True, **{n: bool(found.get(n)) for n in PACKAGES}}


def run_json(
    runner: Path, args: list[str], *, timeout_s: float = LIBROSA_TIMEOUT_S
) -> dict[str, Any]:
    """Run a standalone runner script on the ML interpreter and parse its JSON.

    Raises ``RuntimeError`` with the interpreter's own stderr tail — the useful
    half of a failure here is always what the other process said.
    """
    py = resolve()
    if not py:
        raise RuntimeError(missing_message(tr("Esta análise", "This analysis")))
    try:
        proc = subprocess.run(
            [py, str(runner), *args],
            capture_output=True,
            text=True,
            timeout=timeout_s,
            stdin=subprocess.DEVNULL,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            tr(f"não consegui executar {py}: {exc}", f"could not run {py}: {exc}")
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            tr(f"a análise excedeu {timeout_s:.0f}s", f"the analysis took over {timeout_s:.0f}s")
        ) from exc
    if proc.returncode != 0:
        raise RuntimeError(
            (proc.stderr or "").strip()[-2000:] or tr("a análise falhou", "the analysis failed")
        )
    try:
        return dict(json.loads(proc.stdout.strip().splitlines()[-1]))
    except (ValueError, IndexError) as exc:
        raise RuntimeError(
            tr(
                f"resposta ilegível da análise: {proc.stdout[:200]}",
                f"unreadable answer from the analysis: {proc.stdout[:200]}",
            )
        ) from exc


def librosa_here() -> bool:
    """Whether the measurements can be called in-process rather than shelled out.

    True for a Python install with the ``[ml]`` extra, where a per-click tool
    like "Corrigir daqui" would otherwise pay an interpreter start plus a
    librosa import on EVERY click. False in the `.exe`, which delegates.
    """
    return here("librosa")


def run_librosa(command: str, audio: Path, **opts: float) -> dict[str, Any]:
    """Run one ``_librosa_runner`` measurement on the ML interpreter."""
    runner = runner_path(Path(__file__).resolve().parent, "_librosa_runner.py")
    args = [command, "--audio", str(audio)]
    for name, value in opts.items():
        args += [f"--{name.replace('_', '-')}", repr(float(value))]
    return run_json(runner, args)


__all__ = [
    "PACKAGES",
    "availability",
    "configured",
    "frozen",
    "here",
    "librosa_here",
    "missing_message",
    "probe",
    "resolve",
    "run_json",
    "run_librosa",
    "runner_path",
]
