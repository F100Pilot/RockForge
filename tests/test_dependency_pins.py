"""BUG-0015: whisperx>=3.4 needs pyannote-audio>=4 / numpy>=2.1, which
conflicts with the [ml] stack's numpy<2, and pip's resolver gave up with
ResolutionTooDeep on `pip install ".[ml,lyrics]"`."""

import tomllib
from pathlib import Path

from packaging.requirements import Requirement
from packaging.version import Version

PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def test_whisperx_stays_below_the_release_that_needs_numpy_2() -> None:
    project = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]
    extras = project["optional-dependencies"]
    reqs = {Requirement(r).name: Requirement(r) for r in extras["lyrics"] + extras["ml"]}
    assert not reqs["whisperx"].specifier.contains(Version("3.4.0"))
    assert reqs["whisperx"].specifier.contains(Version("3.3.1"))  # what the components install
    assert not reqs["numpy"].specifier.contains(Version("2.1.0"))
