"""BUG-0250: the Docker image installed RockForge without the [psarc] extra,
so its worker built the bundle and never a .psarc (cryptography/Pillow
missing degrades silently, by design). Every image stage must install it."""

import re
from pathlib import Path

DOCKERFILE = Path(__file__).resolve().parents[1] / "docker" / "Dockerfile"


def test_every_image_stage_installs_the_psarc_extra() -> None:
    text = DOCKERFILE.read_text(encoding="utf-8")
    installs = re.findall(r'pip install[^\n]*"\.\[([^\]]*)\]"', text)
    assert installs, "no pip install of RockForge found"
    for extras in installs:
        assert "psarc" in [e.strip() for e in extras.split(",")], extras
