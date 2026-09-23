"""The interpreter the heavy ML stages run on.

Every ML stage already ran as a subprocess (Demucs, WhisperX, Banquet) or was
moved to one (librosa), so none of them needs the package importable in the
calling process. What kept them out of the standalone build was a single
repeated argument: ``sys.executable``, which in a PyInstaller app is the `.exe`
itself — running it would relaunch RockForge instead of Demucs.

These tests pin the resolution rules and, just as importantly, that the call
sites actually go through them: a regression to ``sys.executable`` would be
invisible from a Python install (where the two are the same value) and would
break only the `.exe`, which CI never runs.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from rockforge.infrastructure import ml_python


@pytest.fixture(autouse=True)
def _unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default to "nothing configured" so a settings.json in the developer's
    work dir cannot change what these tests measure."""
    monkeypatch.setattr(ml_python, "configured", lambda: None)


def test_a_python_install_resolves_to_itself_exactly_as_before() -> None:
    """The whole point of the default: running from Python must be the same
    byte-for-byte path it was before this module existed."""
    assert ml_python.resolve() == sys.executable


def test_the_exe_resolves_to_nothing_rather_than_to_itself(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`sys.executable` in a frozen build is the .exe. Passing it to a
    subprocess would relaunch the whole app — a second window, not a
    separation — so the resolver has to return None and let the caller raise a
    clear "configure it" error."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert ml_python.resolve() is None
    assert "⚙️ Definições" in ml_python.missing_message("A separação")


def test_a_configured_interpreter_wins_everywhere(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ml_python, "configured", lambda: Path("/opt/py311/python"))
    assert ml_python.resolve() == "/opt/py311/python"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert ml_python.resolve() == "/opt/py311/python"


def test_probe_reports_what_the_other_interpreter_has(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """It must ask the OTHER Python, not answer from this one — the `.exe`'s
    own answer is always "nothing" and says nothing about whether the feature
    works."""
    seen: dict[str, Any] = {}

    def fake(cmd: list[str], **kwargs: Any) -> Any:
        seen["cmd"] = cmd
        seen["stdin"] = kwargs.get("stdin")
        return subprocess.CompletedProcess(
            cmd, 0,
            stdout='{"demucs": true, "librosa": true, "whisperx": false, "torch": true}\n',
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake)
    found = ml_python.probe("/opt/py311/python")
    assert found == {
        "python": True, "demucs": True, "librosa": True,
        "whisperx": False, "torch": True,
    }
    assert seen["cmd"][0] == "/opt/py311/python"
    # The anti-hang guard from CLAUDE.md's hard constraints applies here too.
    assert seen["stdin"] is subprocess.DEVNULL


@pytest.mark.parametrize(
    "outcome",
    [
        subprocess.CompletedProcess(["x"], 1, stdout="", stderr="boom"),
        subprocess.CompletedProcess(["x"], 0, stdout="not json at all", stderr=""),
        subprocess.CompletedProcess(["x"], 0, stdout="[1, 2, 3]", stderr=""),
    ],
)
def test_a_broken_ml_interpreter_probes_false_it_never_raises(
    monkeypatch: pytest.MonkeyPatch, outcome: Any
) -> None:
    """This backs the diagnostics page, which the user opens precisely when
    something is wrong. A page that 500s is worse than one that says "no"."""
    monkeypatch.setattr(subprocess, "run", lambda *_a, **_k: outcome)
    assert ml_python.probe("/opt/py311/python") == dict.fromkeys(
        ("python", "demucs", "librosa", "whisperx", "torch"), False
    )


def test_a_missing_interpreter_probes_false(monkeypatch: pytest.MonkeyPatch) -> None:
    def explode(*_a: Any, **_k: Any) -> Any:
        raise FileNotFoundError("no such file")

    monkeypatch.setattr(subprocess, "run", explode)
    assert ml_python.probe("/nope")["python"] is False
    # And with nothing to run at all, it does not even try.
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert ml_python.probe()["python"] is False


def test_run_json_reads_the_last_line_so_warnings_cannot_corrupt_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """librosa is chatty on import (numba/audioread deprecation warnings), and
    a backend can print to stdout. Only the final line is the answer."""
    monkeypatch.setattr(
        subprocess, "run",
        lambda *_a, **_k: subprocess.CompletedProcess(
            ["x"], 0, stdout='UserWarning: whatever\n{"bpm": 123.5}\n', stderr=""
        ),
    )
    assert ml_python.run_json(Path("r.py"), ["tempo"]) == {"bpm": 123.5}


def test_run_json_surfaces_the_other_process_stderr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The useful half of a failure here is always what the OTHER interpreter
    said — a bare "it failed" leaves the user with nothing to act on."""
    monkeypatch.setattr(
        subprocess, "run",
        lambda *_a, **_k: subprocess.CompletedProcess(
            ["x"], 1, stdout="", stderr="ModuleNotFoundError: No module named 'librosa'"
        ),
    )
    with pytest.raises(RuntimeError, match="No module named 'librosa'"):
        ml_python.run_json(Path("r.py"), ["tempo"])


def test_run_json_without_an_interpreter_says_how_to_get_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    with pytest.raises(RuntimeError, match="Definições"):
        ml_python.run_json(Path("r.py"), ["tempo"])


def test_runner_path_finds_a_script_shipped_as_bundle_data(tmp_path: Path) -> None:
    """Inside a PyInstaller bundle the package's modules live in the archive,
    not on disk, so each runner is shipped as a DATA file at its package path.
    `runner_path` must find it there."""
    pkg = tmp_path / "rockforge" / "infrastructure" / "lyrics"
    pkg.mkdir(parents=True)
    (pkg / "_whisperx_runner.py").write_text("x")
    assert ml_python.runner_path(pkg, "_whisperx_runner.py").exists()


def test_the_librosa_measurements_have_one_implementation() -> None:
    """The in-process and subprocess paths must not be two copies of the
    feature extraction — they would drift, and the .exe would then classify a
    tone differently from `start.bat` for no visible reason. Both go through
    `_librosa_runner`, so the adapters hold no librosa call of their own."""
    from rockforge.infrastructure.rhythm import librosa_adapter
    from rockforge.infrastructure.tone_analysis import analyzer

    for module in (librosa_adapter, analyzer):
        source = Path(module.__file__ or "").read_text(encoding="utf-8")
        assert "import librosa" not in source, module.__name__
        assert "_librosa_runner" in source, module.__name__


def test_the_ml_call_sites_never_pass_sys_executable() -> None:
    """A regression here is invisible from a Python install — `resolve()` and
    `sys.executable` are the same value there — and breaks only the `.exe`,
    which CI cannot build or run. So it is pinned as source, deliberately:
    this is the one property no behavioural test in CI can observe.
    """
    import ast

    root = Path(__file__).resolve().parent.parent / "src" / "rockforge"
    call_sites = [
        root / "infrastructure" / "separation" / "demucs_adapter.py",
        root / "infrastructure" / "separation" / "banquet_adapter.py",
        root / "interfaces" / "worker" / "celery_app.py",
    ]
    for path in call_sites:
        # Parsed, not grepped: these modules EXPLAIN in a comment why they no
        # longer use it, and a text match would fail on the explanation.
        tree = ast.parse(path.read_text(encoding="utf-8"))
        used = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute)
            and node.attr == "executable"
            and isinstance(node.value, ast.Name)
            and node.value.id == "sys"
        ]
        assert not used, f"{path.name}:{used[0].lineno}"


def test_the_runner_really_answers_over_the_subprocess_transport(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Drive the ACTUAL script with a real interpreter, not a patched
    ``subprocess.run``.

    Every other test here stubs the transport, so between them they never
    execute the contract the `.exe` depends on: that ``_librosa_runner.py``
    parses those arguments, and prints a JSON object as its last stdout line.
    A stub librosa stands in for the ML stack (CI has none) — what is being
    tested is the transport, not librosa.
    """
    stub = tmp_path / "stub"
    stub.mkdir()
    (stub / "librosa.py").write_text(
        "def load(path, **kw):\n"
        "    return ([0.0], 22050)\n"
        "def estimate_tuning(**kw):\n"
        "    return 0.125\n"
    )
    runner = Path(ml_python.__file__).resolve().parent / "_librosa_runner.py"
    proc = subprocess.run(
        [sys.executable, str(runner), "tuning", "--audio", "song.wav"],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(stub)},
        stdin=subprocess.DEVNULL,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout.strip().splitlines()[-1]) == {"cents": 12.5}


def test_the_runner_fails_loudly_rather_than_printing_a_wrong_number(
    tmp_path: Path,
) -> None:
    """With no librosa at all (this interpreter), the runner must exit non-zero
    with the ImportError on stderr — which is what ``run_json`` surfaces to the
    user. Printing a default would be the worst outcome: a tempo the user
    cannot tell is fabricated."""
    runner = Path(ml_python.__file__).resolve().parent / "_librosa_runner.py"
    proc = subprocess.run(
        [sys.executable, str(runner), "tempo", "--audio", "song.wav"],
        capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=60,
    )
    assert proc.returncode != 0
    assert "librosa" in proc.stderr
    assert proc.stdout.strip() == ""
