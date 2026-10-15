"""The `.exe` installs its own extra components (infrastructure/components.py).

The real install only runs on Windows in the frozen app (the release workflow's
smoke test does it for real); here the two side effects — downloading and
running a command — are replaced, and everything around them is checked.
"""

from __future__ import annotations

import importlib
import io
import zipfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from rockforge.infrastructure import components


def _zip(members: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return buf.getvalue()


class _Fake:
    def __init__(self) -> None:
        self.urls: list[str] = []
        self.commands: list[list[str]] = []

    def get(self, url: str, dest: Path, log: object) -> None:
        self.urls.append(url)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if url == components.PYTHON_PACKAGE_URL:
            dest.write_bytes(_zip({
                "tools/python.exe": b"MZ", "tools/Lib/os.py": b"", "python.nuspec": b"",
                "tools/../../escape.txt": b"never outside",
            }))
        else:
            dest.write_bytes(_zip({"deno.exe": b"MZ"}))

    def run(self, cmd: list[str], log: object) -> None:
        self.commands.append(cmd)


def test_the_extras_are_installed_from_pyproject_without_git() -> None:
    reqs = components.requirements()
    root = Path(__file__).resolve().parents[1]
    expected = components.requirements_from_pyproject(root / "pyproject.toml")
    assert len(reqs) == len(expected) and any(r.startswith("demucs") for r in reqs)
    assert any(r.startswith("whisperx") for r in reqs) and any(r.startswith("yt-dlp") for r in reqs)
    pdf = next(r for r in reqs if r.startswith("pdf-to-gp5"))
    # A git+ URL needs git on the machine; the commit's archive does not.
    assert "git+" not in pdf and "/archive/" in pdf and pdf.endswith(".zip")
    assert components._github_archive("x>=1") == "x>=1"


@pytest.mark.parametrize("gpu", [False, True])
def test_the_install_puts_a_private_python_the_packages_and_deno_in_place(
    tmp_path: Path, gpu: bool
) -> None:
    fake = _Fake()
    log: list[str] = []
    py = components.install(log.append, root=tmp_path, gpu=gpu, get=fake.get, execute=fake.run)
    assert py == tmp_path / "python" / "python.exe" and py.exists()
    assert (tmp_path / "python" / "Lib" / "os.py").exists()
    assert not (tmp_path.parent / "escape.txt").exists()  # nothing written outside
    assert (tmp_path / "tools" / "deno.exe").exists()
    assert not (tmp_path / "downloads").exists()
    first = [c[1:4] for c in fake.commands[:2]]
    assert first == [["-m", "ensurepip", "--upgrade"], ["-m", "pip", "install"]]
    cuda = [c for c in fake.commands if components.TORCH_CUDA_INDEX in c]
    assert bool(cuda) is gpu
    if gpu:
        assert cuda[0][-2:] == list(components.TORCH_CUDA)
    packages = fake.commands[-1]
    assert packages[:4] == [str(py), "-m", "pip", "install"]
    assert set(components.requirements()) <= set(packages)
    assert fake.urls == [components.PYTHON_PACKAGE_URL, components.DENO_URL]
    # A second run repairs: no download again, the packages again.
    fake2 = _Fake()
    components.install(log.append, root=tmp_path, gpu=False, get=fake2.get, execute=fake2.run)
    assert fake2.urls == [] and fake2.commands[-1][4:] == packages[4:]


def test_a_python_package_without_python_exe_fails_clearly(tmp_path: Path) -> None:
    def broken(url: str, dest: Path, log: object) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(_zip({"other.txt": b""}))

    with pytest.raises(RuntimeError, match="python.exe"):
        components.install(lambda _: None, root=tmp_path, gpu=False, get=broken,
                           execute=lambda cmd, log: None)


def test_deno_on_path_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", "/usr/bin")
    assert not components.add_tools_to_path(tmp_path)
    (tmp_path / "tools").mkdir()
    assert components.add_tools_to_path(tmp_path)
    assert components.add_tools_to_path(tmp_path)
    import os

    assert os.environ["PATH"].split(os.pathsep).count(str(tmp_path / "tools")) == 1


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("ROCKFORGE_DATABASE_URL", f"sqlite:///{tmp_path}/test.db")
    monkeypatch.setenv("ROCKFORGE_WORK_DIR", str(tmp_path / "work"))
    import rockforge.config as config

    importlib.reload(config)
    import rockforge.runtime_settings as rs

    importlib.reload(rs)
    import rockforge.interfaces.api.app as app_module

    importlib.reload(app_module)
    with TestClient(app_module.app) as c:
        yield c


def test_a_python_install_is_sent_to_start_bat(client: TestClient) -> None:
    status = client.get("/components").json()
    assert status["supported"] is False
    refused = client.post("/components/install")
    assert refused.status_code == 409 and "start.bat" in refused.json()["detail"]


def test_the_exe_installs_in_the_background_and_then_uses_that_python(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from rockforge import runtime_settings
    from rockforge.infrastructure import ml_python

    root = tmp_path / "components"
    monkeypatch.setattr(components, "supported", lambda: True)
    monkeypatch.setattr(components, "home", lambda: root)
    monkeypatch.setattr(components, "nvidia_gpu", lambda: False)
    fake = _Fake()
    monkeypatch.setattr(components, "download", fake.get)
    monkeypatch.setattr(components, "run", fake.run)
    every = dict.fromkeys(("python", *ml_python.PACKAGES), True)
    monkeypatch.setattr(ml_python, "probe", lambda interpreter=None: every)

    before = client.get("/components").json()
    assert before["supported"] and not before["declined"]
    assert client.post("/components/install").status_code == 202
    for _ in range(200):
        status = client.get("/components").json()
        if status["status"] != "running":
            break
        import time

        time.sleep(0.02)
    assert status["status"] == "done", status
    assert status["complete"] and status["installed"]["pdf"] and status["installed"]["deno"]
    assert runtime_settings.ml_python() == root / "python" / "python.exe"
    # A Python the user chose by hand is never replaced.
    runtime_settings.save({**runtime_settings.load(), "ml_python": "C:/mine/python.exe"})
    components._use(root / "python" / "python.exe")
    assert str(runtime_settings.ml_python()) == "C:/mine/python.exe"


def test_not_now_stops_the_home_page_offering_them(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(components, "supported", lambda: True)
    monkeypatch.setattr(components, "installed", lambda root=None: {"python": False})
    assert client.get("/components").json()["declined"] is False
    assert client.post("/components/decline").json()["declined"] is True
