"""A whole project in one file (``infrastructure/project_archive.py``): what
travels, what never does, and how an untrusted file is read."""

from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path

import pytest

from rockforge import i18n
from rockforge.infrastructure import project_archive as pa

SRC = Path(__file__).resolve().parents[1] / "src" / "rockforge"


def _write(dest: Path, manifest: object, members: dict[str, bytes]) -> Path:
    with zipfile.ZipFile(dest, "w") as zf:
        zf.writestr(pa.MANIFEST, manifest if isinstance(manifest, str) else json.dumps(manifest))
        for name, data in members.items():
            zf.writestr(name, data)
    return dest


def _manifest(**over: object) -> dict[str, object]:
    base: dict[str, object] = {
        "format": pa.FORMAT, "version": pa.FORMAT_VERSION,
        "job": {"title": "Deriva", "artist": "Banda Inventada", "album": "", "year": 2026,
                "source_type": "gp"},
        "params": {"offset_s": 1.5},
    }
    base.update(over)
    return base


@pytest.fixture(autouse=True)
def _english():
    token = i18n.use("en")
    yield
    i18n.reset(token)


GOOD = {"files/recording.mp3": b"ID3", "files/score.gp5": b"FICHIER GUITAR PRO"}


def test_only_what_means_the_same_on_another_machine_travels() -> None:
    params = {
        "offset_s": 1.25, "tones": [{"key": "a"}], "lyrics_events": [{"time": 1}],
        "note_overrides": {"Lead": []}, "detected_tones": {"profile": {}},
        # this machine's files, version chain, build outcome, task logs
        "gp_path": "/home/x/gp/a.gp5", "cover_art": "cover.png",
        "stems": {"guitar": "/etc/passwd"}, "stems_status": "ready",
        "installed_psarc": "C:/Games/dlc/RockForge/x_p.psarc", "installed_from": "id",
        "corrected_gp": "corrected.gp5", "rebuilt_from": "an-old-id",
        "psarc_has_audio": False, "wem_error": "boom", "lyrics_log": ["…"],
        "lyrics_align": {"lines": []}, "something_new": "/anywhere",
        # a status describes a result only when that result is finished
        "lyrics_status": "detecting", "tone_detection_status": "ready",
    }
    out = pa.portable_params(params)
    assert out == {
        "offset_s": 1.25, "tones": [{"key": "a"}], "lyrics_events": [{"time": 1}],
        "note_overrides": {"Lead": []}, "detected_tones": {"profile": {}},
        "tone_detection_status": "ready",
    }
    assert pa.portable_params({"lyrics_status": "ready"}) == {"lyrics_status": "ready"}


def _dict_literal(text: str, start: int) -> str:
    """The text of the ``{…}`` literal opening at ``start``."""
    depth = 0
    for i in range(start, len(text)):
        depth += {"{": 1, "}": -1}.get(text[i], 0)
        if depth == 0:
            return text[start:i + 1]
    return text[start:]


def _keys_written_into_params() -> set[str]:
    assign = re.compile(r"\bparams\[\s*\"(\w+)\"\s*\]\s*=")
    default = re.compile(r"\bparams\.setdefault\(\s*\"(\w+)\"")
    # {**params, "x": …} / {**dict(job.params or {}), "x": …} and the dict a
    # project is created with (params: dict[str, object] = {…})
    literal = re.compile(r"\{\s*\*\*[^,\n]*params|params: dict\[str, object\] = \{")
    found: set[str] = set()
    for path in SRC.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        found.update(assign.findall(text))
        found.update(default.findall(text))
        for match in literal.finditer(text):
            start = text.index("{", match.start())
            found.update(re.findall(r"\"(\w+)\":", _dict_literal(text, start)))
    return found


def test_every_key_the_code_writes_into_params_is_classified() -> None:
    """A new params key must be put in PORTABLE_KEYS or HANDLED_KEYS, or an
    exported project would silently lose it (or carry a path of this machine)."""
    written = _keys_written_into_params()
    assert {"offset_s", "gp_path", "stems", "installed_psarc", "corrected_gp"} <= written
    unclassified = sorted(written - pa.PORTABLE_KEYS - pa.HANDLED_KEYS)
    assert not unclassified, f"classify these params keys in project_archive: {unclassified}"
    assert not pa.PORTABLE_KEYS & pa.HANDLED_KEYS


def test_a_project_written_is_read_back(tmp_path: Path) -> None:
    rec, score, cover = tmp_path / "a.MP3", tmp_path / "s.gp5", tmp_path / "c.png"
    rec.write_bytes(b"ID3" + b"\x00" * 100)
    score.write_bytes(b"GP")
    cover.write_bytes(b"\x89PNG\r\n\x1a\n")
    guitar, drums = tmp_path / "guitar.wav", tmp_path / "drums.wav"
    guitar.write_bytes(b"RIFF0000WAVE")
    drums.write_bytes(b"RIFF0000WAVE")
    dest = tmp_path / "p.rfproj"
    pa.write_project(
        dest,
        job={"title": "Deriva", "artist": "Banda", "album": "A", "year": 2026, "source_type": "gp"},
        params={"offset_s": 2.0, "gp_path": "/x", "rebuilt_from": "id"},
        files=pa.ProjectFiles(rec, score, cover, {"guitar": guitar, "drums": drums}),
    )
    project = pa.read_project(dest)
    assert project.job == {"title": "Deriva", "artist": "Banda", "album": "A", "year": 2026}
    assert project.params == {"offset_s": 2.0}
    assert (project.recording, project.score, project.cover) == (
        "files/recording.mp3", "files/score.gp5", "files/cover.png")
    assert project.stems == {"drums": "files/stems/drums.wav", "guitar": "files/stems/guitar.wav"}
    out = project.extract(project.recording, tmp_path / "back.mp3")
    assert out.read_bytes() == rec.read_bytes()
    assert not list(tmp_path.glob("*.part"))


@pytest.mark.parametrize(("manifest", "members", "says"), [
    (_manifest(format="something-else"), GOOD, "not a RockForge project"),
    (_manifest(version=pa.FORMAT_VERSION + 1), GOOD, "newer RockForge"),
    ('{"format": "rockforge-project", "version": 1, "job": {}, "params": {"x": NaN}}', GOOD,
     "not a RockForge project"),
    (_manifest(job={"title": "", "artist": "B"}), GOOD, "not a RockForge project"),
    (_manifest(job={"title": "T", "artist": "B", "source_type": "upload"}), GOOD,
     "Guitar Pro file can be imported"),
    (_manifest(), {"files/score.gp5": b"GP"}, "no recording"),
    (_manifest(), {"files/recording.mp3": b"ID3"}, "no Guitar Pro file"),
    (_manifest(), {**GOOD, "files/recording.wav": b"RIFF"}, "no recording"),  # two: ambiguous
    (_manifest(), {"files/recording.exe": b"MZ", "files/score.gp5": b"GP"}, "no recording"),
])
def test_a_file_that_is_not_an_importable_project_is_refused_in_words(
    tmp_path: Path, manifest: object, members: dict[str, bytes], says: str
) -> None:
    with pytest.raises(pa.ProjectArchiveError, match=says):
        pa.read_project(_write(tmp_path / "p.rfproj", manifest, members))


def test_not_a_zip_or_no_manifest_is_refused(tmp_path: Path) -> None:
    junk = tmp_path / "junk.rfproj"
    junk.write_bytes(b"not a zip at all")
    with pytest.raises(pa.ProjectArchiveError, match="not a RockForge project"):
        pa.read_project(junk)
    bare = tmp_path / "bare.rfproj"
    with zipfile.ZipFile(bare, "w") as zf:
        zf.writestr("files/recording.mp3", b"ID3")
    with pytest.raises(pa.ProjectArchiveError, match="not a RockForge project"):
        pa.read_project(bare)


def test_member_names_never_become_paths(tmp_path: Path) -> None:
    """Only the known names are read; a stem with a name that is not a plain
    word, or one reaching out of its folder, is not there at all."""
    project = pa.read_project(_write(tmp_path / "p.rfproj", _manifest(), {
        **GOOD,
        "files/../recording.mp3": b"x",
        "files/stems/../../evil.wav": b"RIFF",
        "files/stems/Not A Name.wav": b"RIFF",
        "files/stems/sub/guitar.wav": b"RIFF",
        "files/stems/bass.wav": b"RIFF",
        "/abs/files/score.gp5": b"x",
    }))
    assert project.recording == "files/recording.mp3"
    assert project.score == "files/score.gp5"
    assert project.stems == {"bass": "files/stems/bass.wav"}


def test_a_password_protected_member_is_refused(tmp_path: Path) -> None:
    dest = _write(tmp_path / "p.rfproj", _manifest(), {**GOOD, "files/cover.png": b"\x89PNG"})
    # zipfile cannot write an encrypted member: set the "encrypted" flag of the
    # cover's central directory entry by hand.
    data = bytearray(dest.read_bytes())
    at = data.index(b"PK\x01\x02")
    while not data[at + 46:].startswith(b"files/cover.png"):
        at = data.index(b"PK\x01\x02", at + 4)
    data[at + 8] |= 0x1
    dest.write_bytes(bytes(data))
    with pytest.raises(pa.ProjectArchiveError, match="password"):
        pa.read_project(dest)


def test_a_member_is_read_no_further_than_the_cap(tmp_path: Path, monkeypatch) -> None:
    project = pa.read_project(_write(tmp_path / "p.rfproj", _manifest(), {
        "files/recording.mp3": b"x" * 5000, "files/score.gp5": b"GP"}))
    monkeypatch.setattr(pa, "MAX_MEMBER_BYTES", 1000)
    with pytest.raises(pa.ProjectArchiveError, match="too large"):
        project.extract(project.recording, tmp_path / "out.mp3")
    assert not (tmp_path / "out.mp3").exists()


def test_the_file_is_named_after_the_song() -> None:
    assert pa.file_name("AC/DC", "T.N.T.") == "AC_DC - T.N.T.rfproj"
    assert pa.file_name("", "") == "projeto.rfproj"
    assert pa.file_name("Banda", 'Que "Nome"?') == "Banda - Que _Nome__.rfproj"
