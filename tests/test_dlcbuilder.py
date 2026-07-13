"""DlcBuilderPackager's external-packer invocation — argv construction and the
no-shell=True contract (MIN-15). The packer command is env-only and gets a
server-generated UUID path today, but building the argv as a list (never a
shell string) keeps it safe if a user-controlled string ever reaches it."""

from __future__ import annotations

from pathlib import Path

from rockforge.infrastructure.packaging import dlcbuilder
from rockforge.infrastructure.packaging.dlcbuilder import _build_packer_argv


def test_build_packer_argv_tokenises_then_substitutes() -> None:
    argv = _build_packer_argv("dlc-builder-cli pack {project}", "/data/jobs/abc-123")
    assert argv == ["dlc-builder-cli", "pack", "/data/jobs/abc-123"]


def test_build_packer_argv_keeps_a_spaced_path_as_one_argument() -> None:
    """The project path is substituted per-token AFTER tokenising, so a path
    with spaces stays a single argv entry instead of being split by the shell."""
    argv = _build_packer_argv("packer --in {project}", "/data/my jobs/abc 123")
    assert argv == ["packer", "--in", "/data/my jobs/abc 123"]


def test_build_packer_argv_does_not_treat_the_path_as_a_format_field() -> None:
    """Using str.replace (not str.format) means a path containing literal
    braces can't blow up or be re-interpreted as a format placeholder."""
    argv = _build_packer_argv("packer {project}", "/data/jobs/{weird}")
    assert argv == ["packer", "/data/jobs/{weird}"]


def test_external_packer_runs_as_a_list_without_shell(tmp_path: Path, monkeypatch) -> None:
    """The integration point: subprocess.run gets an argv LIST and shell is not
    enabled (a shell string here would be the injection surface the fix removes)."""
    from rockforge.domain.arrangement import Arrangement, ArrangementKind, SongMetadata
    from rockforge.domain.music import Beat, TabNote, TempoMap, Tuning

    captured: dict[str, object] = {}

    class _Done:
        stderr = ""
        returncode = 0

    def _fake_run(cmd, **kwargs):  # noqa: ANN001, ANN202
        captured["cmd"] = cmd
        captured["shell"] = kwargs.get("shell", False)
        # Pretend the packer produced its output so the caller doesn't error.
        (Path(tmp_path / "bundle") / "out.psarc").write_bytes(b"PSAR")
        return _Done()

    monkeypatch.setattr(dlcbuilder.subprocess, "run", _fake_run)

    arrangement = Arrangement(
        kind=ArrangementKind.COMBINED,
        metadata=SongMetadata(title="Song", artist="Artist", song_length=10.0),
        tuning=Tuning(),
        tempo_map=TempoMap(
            beats=(Beat(time=0.0, measure=1), Beat(time=0.5, measure=-1)), average_bpm=120.0
        ),
        notes=[TabNote(string=0, fret=2, time=0.0, sustain=0.5)],
    )
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"RIFF....WAVEfmt ")

    packager = dlcbuilder.DlcBuilderPackager(psarc_packer_cmd="mypacker pack {project}")
    packager.package([arrangement], audio, tmp_path / "bundle")

    assert isinstance(captured["cmd"], list)  # argv list, not a shell string
    assert captured["shell"] is False
    assert captured["cmd"][0] == "mypacker"
    assert str(tmp_path / "bundle") in captured["cmd"][-1]
