"""DLC Builder's default tones, given to a chart that has none of its own."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rockforge.domain.arrangement import ArrangementKind
from rockforge.infrastructure.packaging.gear import default_tones
from rockforge.infrastructure.packaging.gear.default_tones import default_tone
from rockforge.infrastructure.packaging.tone_dto import tone_dto

_DIR = Path(default_tones.__file__).parent / "default_tones"


@pytest.mark.parametrize(
    ("kind", "route"),
    [
        (ArrangementKind.LEAD, "lead"),
        (ArrangementKind.COMBINED, "lead"),  # Combo shares the Lead route mask
        (ArrangementKind.ALTERNATE_LEAD, "lead"),
        (ArrangementKind.RHYTHM, "rhythm"),
        (ArrangementKind.ALTERNATE_RHYTHM, "rhythm"),
        (ArrangementKind.BASS, "bass"),
    ],
)
def test_the_default_tone_is_dlc_builders_own_for_the_path(
    kind: ArrangementKind, route: str
) -> None:
    """Serialized, it is the reference file's gear, descriptors and volume —
    what DLC Builder's ``addDefaultTonesIfNeeded`` gives the same chart."""
    ref = json.loads((_DIR / f"default_{route}.json").read_text(encoding="utf-8"))
    dto = tone_dto(default_tone(kind))
    assert dto["GearList"] == {k: v for k, v in ref["GearList"].items() if v is not None}
    assert dto["ToneDescriptors"] == ref["ToneDescriptors"]
    assert float(str(dto["Volume"])) == float(ref["Volume"])


def test_the_default_tone_takes_the_charts_base_tone_name() -> None:
    assert default_tone(ArrangementKind.LEAD, "MyBase").key == "MyBase"
    assert default_tone(ArrangementKind.LEAD).key == "Default_Lead"
