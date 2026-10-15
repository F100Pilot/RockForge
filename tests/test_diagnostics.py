"""The external-software report.

RockForge ships almost none of its dependencies, and every absence surfaces
downstream as something that reads like a bug ("o PSARC não é jogável", "a
deteção de letra não faz nada"). These tests pin the two properties that make
the report worth having: it must never lie about what it cannot know, and it
must never import the heavy stack to find out.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from rockforge import config
from rockforge.config import Settings
from rockforge.infrastructure import diagnostics


def _by_key(reqs: list[diagnostics.Requirement]) -> dict[str, diagnostics.Requirement]:
    return {r.key: r for r in reqs}


def test_every_requirement_says_what_it_costs_and_how_to_get_it() -> None:
    """A report that only says "missing" is the same dead end as the downstream
    symptom. Each row has to carry the consequence AND the fix."""
    reqs = diagnostics.check_requirements(Settings())
    assert reqs, "the report must not be empty"
    for r in reqs:
        assert r.name and r.detail, r.key
        assert r.unlocks and r.without_it and r.install, r.key
        assert r.found in (True, False, None), r.key


def test_probing_never_imports_the_heavy_stack(monkeypatch: pytest.MonkeyPatch) -> None:
    """The API process must never pay for torch/demucs/whisperx (CLAUDE.md's
    layering rule), so detection uses `find_spec`, which locates without
    importing. If this ever regresses to a real import, the API gets seconds
    slower and can fail outright on a broken ML install."""
    heavy = ("torch", "demucs", "librosa", "whisperx")
    for name in heavy:
        monkeypatch.delitem(sys.modules, name, raising=False)

    real_import = __import__
    imported: list[str] = []

    def watch(name: str, *args: Any, **kwargs: Any) -> Any:
        if name.split(".")[0] in heavy:
            imported.append(name)
        return real_import(name, *args, **kwargs)

    import builtins

    monkeypatch.setattr(builtins, "__import__", watch)
    diagnostics.check_requirements(Settings())
    monkeypatch.undo()
    assert imported == [], f"the probe imported {imported}"


def test_what_cannot_be_checked_reports_unknown_not_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`found is None` is a real third answer. The CDLC loader patch is the
    clearest case: with no Rocksmith on this machine (RockForge may run on a
    laptop without the game) calling it "missing" would be a confident guess
    about someone else's machine."""
    from rockforge.infrastructure import tone_collection

    monkeypatch.setattr(config.settings, "work_dir", tmp_path)
    monkeypatch.setattr(tone_collection, "rocksmith_game_folders", lambda: [])
    reqs = _by_key(diagnostics.check_requirements(Settings()))
    patch = reqs["cdlc_patch"]
    assert patch.found is None
    assert "não foi encontrado" in patch.detail, "it must say WHY it is unknown"


def test_the_cdlc_patch_is_looked_for_in_the_game_folder(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """With the game in a Steam library here, the patch is simply checked: the
    row used to say "por confirmar" even on the machine that has the game."""
    from rockforge.infrastructure import tone_collection

    monkeypatch.setattr(config.settings, "work_dir", tmp_path / "work")
    game = tmp_path / "Rocksmith2014"
    game.mkdir()
    monkeypatch.setattr(tone_collection, "rocksmith_game_folders", lambda: [game])
    missing = diagnostics._loader_patch()
    assert missing.found is False and str(game) in missing.detail
    (game / "d3dx9_42.dll").write_bytes(b"x")  # any case: Proton/Wine folders
    present = diagnostics._loader_patch()
    assert present.found is True and present.detail.endswith("D3DX9_42.dll")


def test_the_game_folder_the_tone_collection_was_pointed_at_wins(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A library Steam does not list (or a copy elsewhere) is still found
    through the dlc folder the user gave the tone collection."""
    from rockforge import runtime_settings
    from rockforge.infrastructure import tone_collection

    monkeypatch.setattr(config.settings, "work_dir", tmp_path / "work")
    game = tmp_path / "Games" / "Rocksmith2014"
    (game / "dlc").mkdir(parents=True)
    (game / "Rocksmith2014.exe").write_bytes(b"x")
    (game / "D3DX9_42.dll").write_bytes(b"x")
    monkeypatch.setattr(tone_collection, "rocksmith_game_folders", lambda: [])
    runtime_settings.save({"rocksmith_dlc_dir": str(game / "dlc")})
    assert diagnostics._loader_patch().found is True


def test_steam_libraries_on_other_drives_are_searched(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from rockforge.infrastructure import tone_collection

    steam = tmp_path / "Steam"
    (steam / "steamapps").mkdir(parents=True)
    other = tmp_path / "D" / "SteamLibrary"
    (other / "steamapps" / "common" / "Rocksmith2014" / "dlc").mkdir(parents=True)
    escaped = str(other).replace("\\", "\\\\")
    (steam / "steamapps" / "libraryfolders.vdf").write_text(
        f'"libraryfolders"\n{{\n\t"0"\n\t{{\n\t\t"path"\t\t"{steam}"\n\t}}\n'
        f'\t"1"\n\t{{\n\t\t"path"\t\t"{escaped}"\n\t}}\n}}\n'
    )
    monkeypatch.setattr(tone_collection, "_steam_roots", lambda: [steam])
    game = other / "steamapps" / "common" / "Rocksmith2014"
    assert tone_collection.rocksmith_game_folders() == [game]
    assert tone_collection.suggested_folder() == game / "dlc"


def test_torch_installed_is_unknown_not_a_working_gpu(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Whether torch is the CUDA build or the CPU one is only knowable by
    importing it, which this must not do. Claiming the GPU works because the
    package exists would be exactly the confident-and-wrong answer the app
    exists to avoid."""
    monkeypatch.setattr(diagnostics, "_has", lambda *m: "torch" in m)
    assert diagnostics._gpu(gpu_broken=False).found is None

    # Marked broken after a CUDA crash: that IS knowable, and it is a No.
    broken = diagnostics._gpu(gpu_broken=True)
    assert broken.found is False
    assert "cpu" in broken.detail.lower()

    monkeypatch.setattr(diagnostics, "_has", lambda *_m: False)
    assert diagnostics._gpu(gpu_broken=False).found is False


def test_ffmpeg_is_the_only_hard_requirement() -> None:
    """Everything else degrades: no Wwise still produces the bundle, no
    `[psarc]` just omits the .psarc, no `[ml]` 503s that one button. ffmpeg is
    different — the whole pipeline normalizes through it."""
    reqs = diagnostics.check_requirements(Settings())
    assert [r.key for r in reqs if r.required] == ["ffmpeg"]


def test_ffmpeg_reports_its_version_when_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = tmp_path / "ffmpeg"
    fake.write_text("#!/bin/sh\necho 'ffmpeg version 6.1.1 Copyright (c)'\n")
    fake.chmod(0o755)
    monkeypatch.setattr(shutil, "which", lambda _n: str(fake))

    req = diagnostics._ffmpeg()
    assert req.found is True
    assert "6.1.1" in req.detail and str(fake) in req.detail


def test_an_ffmpeg_that_will_not_answer_is_still_reported_as_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A binary that hangs or errors on -version is still a binary on PATH; the
    detail says the probe failed rather than the report claiming it is absent.
    The probe is also bounded — a wedged ffmpeg must not hang the endpoint."""
    fake = tmp_path / "ffmpeg"
    fake.write_text("x")
    monkeypatch.setattr(shutil, "which", lambda _n: str(fake))

    def explode(*_a: Any, **kwargs: Any) -> Any:
        assert kwargs["timeout"] == diagnostics._FFMPEG_PROBE_TIMEOUT_S
        # stdin closed: a console tool that inherits it can go interactive and
        # block forever (CLAUDE.md's hard constraint).
        assert kwargs["stdin"] is subprocess.DEVNULL
        raise subprocess.TimeoutExpired(cmd="ffmpeg", timeout=1)

    monkeypatch.setattr(subprocess, "run", explode)
    req = diagnostics._ffmpeg()
    assert req.found is True
    assert "não respondeu" in req.detail


def test_ffmpeg_absent_is_flagged_as_missing_required(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(shutil, "which", lambda _n: None)
    reqs = diagnostics.check_requirements(Settings())
    assert [r.key for r in diagnostics.missing_required(reqs)] == ["ffmpeg"]


def test_wwise_says_which_half_of_the_setup_is_missing(tmp_path: Path) -> None:
    """"Not found" is useless when the user HAS installed Wwise and only
    pointed the variable at the wrong folder — the two cases get different
    detail so the fix is obvious."""
    unset = _by_key(diagnostics.check_requirements(Settings(wwise_root=None)))["wwise"]
    assert unset.found is False
    assert "ROCKFORGE_WWISE_ROOT" in unset.detail

    wrong = _by_key(diagnostics.check_requirements(Settings(wwise_root=tmp_path)))["wwise"]
    assert wrong.found is False
    assert str(tmp_path) in wrong.detail and "WwiseConsole" in wrong.detail

    console = tmp_path / "Authoring" / "x64" / "Release" / "bin" / "WwiseConsole.exe"
    console.parent.mkdir(parents=True)
    console.write_text("")
    ok = _by_key(diagnostics.check_requirements(Settings(wwise_root=tmp_path)))["wwise"]
    assert ok.found is True
    assert str(console) in ok.detail


def test_a_broken_install_reads_as_absent_not_as_a_crash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`find_spec` RAISES on a half-removed package rather than returning None.
    A diagnostics page that 500s is worse than one that says "missing"."""
    import importlib.util

    def raising(name: str) -> Any:
        raise ValueError(f"{name} is in a broken state")

    monkeypatch.setattr(importlib.util, "find_spec", raising)
    assert diagnostics._has("anything") is False
    assert diagnostics.check_requirements(Settings())  # no exception


def test_inside_the_exe_a_pip_instruction_points_at_the_ml_interpreter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A frozen PyInstaller app has its OWN Python — `sys.path` is just the
    bundle's `_internal`, so the system's site-packages are never importable
    (verified by building a minimal frozen app and reading `sys.path` back). A
    bare `pip install` would therefore be a lie.

    But every ML stage runs as a SUBPROCESS, so the .exe can hand the work to a
    Python that does have the packages. The instruction has to say that — where
    to install them, and that the path goes in ⚙️ Definições — instead of the
    earlier flat "not possible in the .exe", which was true only of an
    in-process import and sent the user away from a setup that works. Since the
    .exe installs that Python itself, the instruction is its one-click
    «Instalar componentes extra» (components.py), with a Python of the user's
    own as the alternative.
    """
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    frozen = _by_key(diagnostics.check_requirements(Settings()))
    for key in ("ml", "lyrics", "gpu", "pdf", "ytdlp", "ml_python"):
        install = frozen[key].install
        assert "Python 3.11" in install, key
        assert "Definições" in install, key
        assert "Instalar componentes extra" in install, key
        # The old claim must not come back: it is reachable, just not in-process.
        assert "NÃO é possível" not in install, key

    monkeypatch.delattr(sys, "frozen", raising=False)
    plain = _by_key(diagnostics.check_requirements(Settings()))
    assert plain["ml"].install == 'pip install -e ".[ml]"'
    assert "Definições" not in plain["lyrics"].install


def test_the_ml_rows_describe_the_interpreter_that_runs_the_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """In the .exe the ML packages live in a DIFFERENT interpreter, so reporting
    what this process can import would answer a question nobody asked. The rows
    have to follow `ml_python.probe`, and say where they looked."""
    from rockforge.infrastructure import ml_python

    monkeypatch.setattr(ml_python, "configured", lambda: Path("/opt/py311/python"))
    monkeypatch.setattr(
        ml_python,
        "probe",
        lambda *_a: {
            "python": True, "demucs": True, "librosa": True,
            "whisperx": False, "torch": True,
        },
    )
    # _has must NOT be what decides: this process has none of them.
    monkeypatch.setattr(diagnostics, "_has", lambda *_m: False)

    reqs = _by_key(diagnostics.check_requirements(Settings()))
    assert reqs["ml"].found is True
    assert "/opt/py311/python" in reqs["ml"].detail
    assert reqs["lyrics"].found is False
    assert reqs["ml_python"].found is True
    # torch present but the CUDA build unverifiable — still the third answer.
    assert reqs["gpu"].found is None


def test_an_ml_interpreter_that_does_not_run_says_so(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pointing the setting at the wrong file is the likeliest mistake, and
    "Demucs em falta" would send the user to reinstall Demucs instead of fixing
    the path. The two cases get different detail."""
    from rockforge.infrastructure import ml_python

    monkeypatch.setattr(ml_python, "configured", lambda: Path("/nope/python.exe"))
    monkeypatch.setattr(ml_python, "probe", lambda *_a: dict.fromkeys(
        ("python", "demucs", "librosa", "whisperx", "torch"), False
    ))
    reqs = _by_key(diagnostics.check_requirements(Settings()))
    assert reqs["ml_python"].found is False
    assert "não arrancou" in reqs["ml_python"].detail
    assert "/nope/python.exe" in reqs["ml"].detail


def test_nothing_is_probed_when_this_process_is_the_ml_interpreter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Running from a Python install, `resolve()` returns this very
    interpreter — spawning a subprocess to ask ourselves what we can import
    would cost a second on every settings page for an answer `find_spec`
    already has exactly."""
    from rockforge.infrastructure import ml_python

    monkeypatch.setattr(ml_python, "configured", lambda: None)

    def fail(*_a: Any, **_k: Any) -> Any:
        raise AssertionError("probe spawned a subprocess against ourselves")

    monkeypatch.setattr(ml_python, "probe", fail)
    reqs = _by_key(diagnostics.check_requirements(Settings()))
    assert reqs["ml_python"].found is True
    assert "próprio Python" in reqs["ml_python"].detail


def test_the_hard_requirement_keeps_its_real_fix_inside_the_exe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ffmpeg and Wwise are ordinary programs, not Python packages — installing
    them works exactly the same for the .exe, so their instructions must NOT be
    rewritten."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    reqs = _by_key(diagnostics.check_requirements(Settings()))
    assert "winget install ffmpeg" in reqs["ffmpeg"].install
    assert "NÃO é possível" not in reqs["ffmpeg"].install
    assert "NÃO é possível" not in reqs["wwise"].install


def test_ytdlp_without_a_js_runtime_is_reported_missing(monkeypatch) -> None:  # noqa: ANN001
    # yt-dlp alone cannot get YouTube's audio: the JS challenge needs a runtime.
    from rockforge.infrastructure import diagnostics, youtube_audio

    monkeypatch.setattr(youtube_audio, "ytdlp_command", lambda: ["/bin/yt-dlp"])
    monkeypatch.setattr(diagnostics.shutil, "which", lambda _p: None)
    row = diagnostics._ytdlp()
    assert row.found is False and "motor JavaScript" in row.detail
    assert "Deno" in row.install

    monkeypatch.setattr(
        diagnostics.shutil, "which", lambda p: "/usr/bin/deno" if p == "deno" else None
    )
    row = diagnostics._ytdlp()
    # A yt-dlp program cannot be asked whether it has the solver: unknown.
    assert row.found is None and "deno" in row.detail


def test_the_rocksmith_folder_set_in_settings_is_where_the_patch_is_looked_for(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The user can name the game folder ("Mas eu posso colocar a diretoria onde
    está o rocksmith"): it wins over the Steam libraries, a folder that does not
    exist says so instead of passing for "patch missing", and the tone
    collection then suggests its dlc folder."""
    from rockforge import runtime_settings
    from rockforge.infrastructure import tone_collection

    monkeypatch.setattr(config.settings, "work_dir", tmp_path / "work")
    steam_game = tmp_path / "Steam" / "Rocksmith2014"
    steam_game.mkdir(parents=True)
    monkeypatch.setattr(tone_collection, "rocksmith_game_folders", lambda: [steam_game])
    mine = tmp_path / "Jogos" / "Rocksmith2014"
    (mine / "dlc").mkdir(parents=True)
    (mine / "D3DX9_42.dll").write_bytes(b"x")
    runtime_settings.save({"rocksmith_dir": str(mine)})
    assert diagnostics._loader_patch().found is True
    assert tone_collection.suggested_folder() == mine / "dlc"
    runtime_settings.save({"rocksmith_dir": str(tmp_path / "nowhere")})
    gone = diagnostics._loader_patch()
    assert gone.found is None and "não existe" in gone.detail


def test_a_windows_library_path_is_unescaped(tmp_path: Path) -> None:
    from rockforge.infrastructure import tone_collection

    (tmp_path / "steamapps").mkdir()
    (tmp_path / "steamapps" / "libraryfolders.vdf").write_text(
        '"libraryfolders"\n{\n\t"1"\n\t{\n\t\t"path"\t\t"D:\\\\SteamLibrary"\n\t}\n}\n'
    )
    assert tone_collection._steam_libraries(tmp_path) == [tmp_path, Path("D:\\SteamLibrary")]
