"""DLC Builder project (.rs2dlc) generation — format reverse-engineered from a
real DLC Builder file (see infrastructure/packaging/rs2dlc.py)."""

from __future__ import annotations

import json
from pathlib import Path

from rockforge.domain.arrangement import Arrangement, ArrangementKind, SongMetadata
from rockforge.domain.music import Beat, TabNote, TempoMap, Tuning
from rockforge.infrastructure.packaging.rs2dlc import build_rs2dlc, write_rs2dlc


def _arr(kind: ArrangementKind, tuning: Tuning | None = None) -> Arrangement:
    return Arrangement(
        kind=kind,
        metadata=SongMetadata(
            title="About us", artist="Ayla Chan", album="About us", year=2026, song_length=210.0
        ),
        tuning=tuning or Tuning(),
        tempo_map=TempoMap(beats=(Beat(time=0.0, measure=1),), average_bpm=120.0),
        notes=[TabNote(string=0, fret=2, time=0.0, sustain=0.5)],
    )


def test_build_rs2dlc_top_level_shape() -> None:
    project = build_rs2dlc(
        [_arr(ArrangementKind.LEAD)],
        ["arrangement_lead.xml"],
        "audio.wav",
        "AylaChanAboutus",
        cover_art_name="cover.png",
    )
    assert project["Version"] == "1"
    assert project["DLCKey"] == "AylaChanAboutus"
    assert project["ArtistName"] == {"Value": "Ayla Chan", "SortValue": ""}
    assert project["Title"] == {"Value": "About us", "SortValue": ""}
    assert project["Year"] == 2026
    assert project["AlbumArtFile"] == "cover.png"
    assert project["AudioFile"]["Path"] == "audio.wav"  # type: ignore[index]
    assert project["AudioFileLength"] == 210.0
    assert project["Tones"] == []


def test_instrumental_name_and_routemask_per_kind() -> None:
    project = build_rs2dlc(
        [
            _arr(ArrangementKind.LEAD),
            _arr(ArrangementKind.RHYTHM),
            _arr(ArrangementKind.COMBINED),
        ],
        ["arrangement_lead.xml", "arrangement_rhythm.xml", "arrangement_combined.xml"],
        "audio.wav",
        "Key",
    )
    arrs = project["Arrangements"]
    assert [a["Case"] for a in arrs] == ["Instrumental"] * 3  # type: ignore[index]
    lead, rhythm, combo = (a["Fields"][0] for a in arrs)  # type: ignore[index]
    assert (lead["Name"], lead["RouteMask"]) == (0, 1)
    assert (rhythm["Name"], rhythm["RouteMask"]) == (2, 2)
    assert (combo["Name"], combo["RouteMask"]) == (1, 1)


def test_instrumental_id_equals_persistent_id() -> None:
    project = build_rs2dlc(
        [_arr(ArrangementKind.LEAD)], ["arrangement_lead.xml"], "audio.wav", "Key"
    )
    field = project["Arrangements"][0]["Fields"][0]  # type: ignore[index]
    assert field["ID"] == field["PersistentID"]
    assert isinstance(field["MasterID"], int) and field["MasterID"] > 0


def test_tuning_offsets_and_pitch() -> None:
    drop_d = Tuning(midi=(38, 45, 50, 55, 59, 64))  # low string down a tone
    project = build_rs2dlc(
        [_arr(ArrangementKind.LEAD, drop_d)], ["arrangement_lead.xml"], "audio.wav", "Key"
    )
    field = project["Arrangements"][0]["Fields"][0]  # type: ignore[index]
    assert field["Tuning"] == [-2, 0, 0, 0, 0, 0]
    assert field["TuningPitch"] == 440.0


def test_vocals_appended_as_separate_case() -> None:
    project = build_rs2dlc(
        [_arr(ArrangementKind.LEAD)],
        ["arrangement_lead.xml"],
        "audio.wav",
        "Key",
        vocals_xml_name="arrangement_vocals.xml",
    )
    arrs = project["Arrangements"]
    assert arrs[-1]["Case"] == "Vocals"  # type: ignore[index]
    vocals = arrs[-1]["Fields"][0]  # type: ignore[index]
    assert vocals["XML"] == "arrangement_vocals.xml"
    assert vocals["Japanese"] is False
    assert vocals["ID"] == vocals["PersistentID"]


def test_write_rs2dlc_creates_phrase_levels(tmp_path: Path) -> None:
    out = tmp_path / "rockforge.rs2dlc"
    write_rs2dlc(
        [_arr(ArrangementKind.LEAD), _arr(ArrangementKind.RHYTHM)],
        ["arrangement_lead.xml", "arrangement_rhythm.xml"],
        "audio.wav",
        "Key",
        out,
    )
    phrase_levels_path = tmp_path / ".phrase-levels"
    assert phrase_levels_path.exists()
    levels = json.loads(phrase_levels_path.read_text(encoding="utf-8"))
    # One entry per instrumental arrangement (Lead + Rhythm)
    assert len(levels) == 2
    for _guid, phrases in levels.items():
        assert set(phrases.keys()) == {"COUNT", "default", "END"}
        assert all(v == 0 for v in phrases.values())
