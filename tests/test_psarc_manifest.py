import json

from rockforge.domain.arrangement import Arrangement, ArrangementKind, SongMetadata
from rockforge.domain.music import TempoMap, Tuning
from rockforge.infrastructure.packaging.psarc.container import pack_entries, unpack
from rockforge.infrastructure.packaging.psarc.manifest import (
    build_arrangement_manifest,
    build_manifest_files,
    persistent_id,
    song_key_from_title,
)


def _arrangement(kind: ArrangementKind) -> Arrangement:
    return Arrangement(
        kind=kind,
        metadata=SongMetadata(
            title="My Song", artist="My Artist", album="My Album", year=2024, song_length=120.0
        ),
        tuning=Tuning(),
        tempo_map=TempoMap(beats=(), average_bpm=120.0),
        notes=[],
    )


def test_song_key_from_title_is_alphanumeric() -> None:
    key = song_key_from_title("AC/DC", "T.N.T.")
    assert key.isalnum()
    assert key


def test_persistent_id_is_deterministic_and_stable_per_arrangement() -> None:
    a = persistent_id("MySong", "Lead")
    b = persistent_id("MySong", "Lead")
    c = persistent_id("MySong", "Rhythm")
    assert a == b
    assert a != c


def test_build_arrangement_manifest_fields() -> None:
    arrangement = _arrangement(ArrangementKind.LEAD)
    manifest = build_arrangement_manifest(arrangement, "MySong", "Lead")
    entries = manifest["Entries"]
    (pid, entry), = entries.items()
    attrs = entry["Attributes"]
    assert attrs["ArrangementName"] == "Lead"
    assert attrs["ArrangementType"] == "Lead"
    assert attrs["ArtistName"] == "My Artist"
    assert attrs["SongKey"] == "MySong"
    assert attrs["SongLength"] == 120.0
    assert attrs["PersistentID"] == pid
    assert attrs["Tuning"]["string0"] == 0


def test_build_manifest_files_packs_and_round_trips() -> None:
    files = build_manifest_files(
        [
            (_arrangement(ArrangementKind.LEAD), "Lead"),
            (_arrangement(ArrangementKind.RHYTHM), "Rhythm"),
        ],
        "MySong",
    )
    assert "toolkit.version" in files
    # Train "Drops of Jupiter" appid — the game won't list CDLC without an appid.
    assert files["appid"] == b"492989"
    assert "manifests/songs_dlc_mysong/songs_dlc_mysong.hsan" in files
    assert "manifests/songs_dlc_mysong/mysong_lead.json" in files
    assert "manifests/songs_dlc_mysong/mysong_rhythm.json" in files
    assert "flatmodels/rs/mysong_aggregategraph.nt" in files

    hsan = json.loads(files["manifests/songs_dlc_mysong/songs_dlc_mysong.hsan"])
    assert len(hsan["Entries"]) == 2
    assert hsan["InsertRoot"] == "Static.Songs.Entries"

    packed = pack_entries(files)
    assert unpack(packed) == files


def test_include_vocals_adds_vocals_manifest() -> None:
    files = build_manifest_files(
        [(_arrangement(ArrangementKind.COMBINED), "Combined")],
        "MySong",
        include_vocals=True,
    )
    assert "manifests/songs_dlc_mysong/mysong_vocals.json" in files

    vocals = json.loads(files["manifests/songs_dlc_mysong/mysong_vocals.json"])
    (_, entry), = vocals["Entries"].items()
    attrs = entry["Attributes"]
    assert attrs["ArrangementType"] == "Vocals"
    assert attrs["ArrangementName"] == "Vocals"
    assert attrs["SongAsset"] == "urn:application:musicgame-song:mysong_vocals"
    # The vocals arrangement carries no tuning/capo.
    assert "Tuning" not in attrs

    hsan = json.loads(files["manifests/songs_dlc_mysong/songs_dlc_mysong.hsan"])
    assert len(hsan["Entries"]) == 2  # instrument + vocals
    graph = files["flatmodels/rs/mysong_aggregategraph.nt"].decode()
    assert "mysong_vocals" in graph
