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
    assert attrs["ArrangementType"] == 0  # int enum (Lead=0), not a string
    assert attrs["ArtistName"] == "My Artist"
    assert attrs["SongKey"] == "MySong"
    assert attrs["SongLength"] == 120.0
    assert attrs["PersistentID"] == pid
    assert attrs["Tuning"]["string0"] == 0


def test_manifest_reports_note_count_and_phrase_structure() -> None:
    from rockforge.domain.music import Beat, TabNote

    arrangement = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="S", artist="A", song_length=10.0),
        tuning=Tuning(),
        tempo_map=TempoMap(
            beats=tuple(Beat(time=i * 0.5, measure=1 if i == 0 else -1) for i in range(20)),
            average_bpm=120.0,
        ),
        notes=[TabNote(string=0, fret=i % 12, time=i * 0.5, sustain=0.4) for i in range(12)],
    )
    attrs = list(
        build_arrangement_manifest(arrangement, "MySong", "Lead")["Entries"].values()
    )[0]["Attributes"]
    # The song list shows "0 notes" and a blank difficulty bar if these are empty.
    assert attrs["NotesHard"] == 12
    assert attrs["Score_MaxNotes"] == 12
    assert len(attrs["PhraseIterations"]) >= 1
    assert len(attrs["Phrases"]) >= 1


def test_build_manifest_files_packs_and_round_trips() -> None:
    files = build_manifest_files(
        [
            (_arrangement(ArrangementKind.LEAD), "Lead"),
            (_arrangement(ArrangementKind.RHYTHM), "Rhythm"),
        ],
        "MySong",
    )
    assert "toolkit.version" in files
    # The "Toolkit version:" line must be a numeric RocksmithToolkitLib version —
    # the CDLC loader patch reads it to whitelist the PSARC; a non-numeric value
    # makes the game drop the song from the list (even with a correct appid).
    version_line = files["toolkit.version"].decode("utf-8").splitlines()[0]
    assert version_line.startswith("Toolkit version: 2.9.2.1")
    # Train "Drops of Jupiter" appid, written to the root `appid.appid` file —
    # the game won't list CDLC without it.
    assert files["appid.appid"] == b"492989"
    assert "manifests/songs_dlc_mysong/songs_dlc_mysong.hsan" in files
    assert "manifests/songs_dlc_mysong/mysong_lead.json" in files
    assert "manifests/songs_dlc_mysong/mysong_rhythm.json" in files

    hsan = json.loads(files["manifests/songs_dlc_mysong/songs_dlc_mysong.hsan"])
    assert len(hsan["Entries"]) == 2
    # The .hsan aggregates *headers*; the per-arrangement .json carries entries.
    assert hsan["InsertRoot"] == "Static.Songs.Headers"

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
    assert attrs["ArrangementType"] is None  # vocals have no instrument type
    assert attrs["ArrangementName"] == "Vocals"
    assert attrs["SongAsset"] == "urn:application:musicgame-song:mysong_vocals"
    # The vocals arrangement carries no tuning/capo.
    assert "Tuning" not in attrs

    hsan = json.loads(files["manifests/songs_dlc_mysong/songs_dlc_mysong.hsan"])
    assert len(hsan["Entries"]) == 2  # instrument + vocals
