import json

from rockforge.domain.arrangement import Arrangement, ArrangementKind, SongMetadata
from rockforge.domain.music import TempoMap, Tuning
from rockforge.infrastructure.packaging.psarc.container import pack_entries, unpack
from rockforge.infrastructure.packaging.psarc.manifest import (
    arrangement_asset_name,
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
    # No gear definitions on the base arrangement → tone slots stay empty.
    assert attrs["Tone_Base"] == "" and attrs["Tones"] == []


def test_manifest_serializes_custom_tones_into_gearlist() -> None:
    """A tone with full gear must land in the manifest's Tones array + slots, so
    the native PSARC applies the user's tone in-game (not a default)."""
    from rockforge.domain.tone import Gear, Pedal, Tone

    tone = Tone(
        key="RFLead_Crunch",
        name="Lead - Crunch",
        gear=Gear(
            amp=Pedal(gear_type="Amps", key="Amp_MarshallJCM800",
                      knob_values={"Amp_MarshallJCM800_Gain": 65.0}),
            cabinet=Pedal(gear_type="Cabinets", key="Cab_Marshall1960a_57_Cone"),
        ),
        descriptors=("$[27156]CRUNCH",),
        volume=-14.0,
    )
    arrangement = _arrangement(ArrangementKind.LEAD)
    arrangement.tone_base = "RFLead_Crunch"
    arrangement.tone_names = ["RFLead_Crunch"]
    arrangement.tones = [tone]
    attrs = next(iter(
        build_arrangement_manifest(arrangement, "MySong", "Lead")["Entries"].values()
    ))["Attributes"]
    assert attrs["Tone_Base"] == "RFLead_Crunch"
    assert attrs["Tone_A"] == "RFLead_Crunch"
    assert len(attrs["Tones"]) == 1
    dto = attrs["Tones"][0]
    assert dto["Key"] == "RFLead_Crunch"
    assert dto["GearList"]["Amp"]["Key"] == "Amp_MarshallJCM800"
    assert dto["GearList"]["Cabinet"]["Key"] == "Cab_Marshall1960a_57_Cone"
    assert dto["Volume"] == "-14.000"  # string-formatted like Rocksmith2014.NET
    assert dto["IsCustom"] is True


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


def test_manifest_reports_nonzero_song_difficulty() -> None:
    # SongDifficulty / EasyMastery / MediumMastery feed the game's skill-based DD
    # starting level. Zero (the old value) made every song start from difficulty 0
    # regardless of the player's history.
    from rockforge.domain.music import Beat, TabNote

    arrangement = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="S", artist="A", song_length=40.0),
        tuning=Tuning(),
        tempo_map=TempoMap(
            beats=tuple(Beat(time=i * 0.5, measure=i // 4 + 1 if i % 4 == 0 else -1)
                        for i in range(80)),
            average_bpm=120.0,
        ),
        notes=[TabNote(string=i % 6, fret=(i % 7) + 1, time=round(i * 0.5, 3), sustain=0.2)
               for i in range(60)],
    )
    attrs = list(
        build_arrangement_manifest(arrangement, "MySong", "Lead")["Entries"].values()
    )[0]["Attributes"]
    assert 0 < attrs["SongDifficulty"] <= 0.95
    assert attrs["SongDiffHard"] == attrs["SongDifficulty"]
    assert 0 < attrs["EasyMastery"] <= 1.0
    assert attrs["MediumMastery"] >= attrs["EasyMastery"]


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


def test_build_manifest_files_reuses_a_precomputed_sng_model(monkeypatch) -> None:
    """Passing `models=` must skip compiling the SNG a second time — the packer
    already builds one per arrangement (up to ~21 Dynamic Difficulty levels of
    phrase-linking/anchor/chord-notes work) to write the .sng payload, and
    arrangement_stats used to redundantly rebuild it just to read note/phrase
    counts for the manifest."""
    from rockforge.infrastructure.packaging.psarc import sng as sng_mod

    arrangements = [
        (_arrangement(ArrangementKind.LEAD), "Lead"),
        (_arrangement(ArrangementKind.RHYTHM), "Rhythm"),
    ]
    precomputed = [sng_mod.from_arrangement(arr) for arr, _ in arrangements]

    def boom(*args, **kwargs):
        raise AssertionError("from_arrangement should not be called when models= is given")

    monkeypatch.setattr(sng_mod, "from_arrangement", boom)

    files = build_manifest_files(arrangements, "MySong", models=precomputed)
    assert "manifests/songs_dlc_mysong/mysong_lead.json" in files


def test_alternate_arrangement_is_nonrepresentative_same_path() -> None:
    # An Alternate Lead shares the Lead ArrangementName/RouteMask/Type but is
    # non-representative (Representative 0, represent 0, bonusArr 1), with its own
    # `lead2` asset and a distinct persistent ID — matching a decoded DLC Builder
    # CDLC (AAL "Tempting Time" lead vs lead2).
    lead = _arrangement(ArrangementKind.LEAD)
    alt = _arrangement(ArrangementKind.ALTERNATE_LEAD)
    la = list(build_arrangement_manifest(
        lead, "MySong", arrangement_asset_name("MySong", ArrangementKind.LEAD),
    )["Entries"].values())[0]["Attributes"]
    aa = list(build_arrangement_manifest(
        alt, "MySong", arrangement_asset_name("MySong", ArrangementKind.ALTERNATE_LEAD),
    )["Entries"].values())[0]["Attributes"]
    assert aa["ArrangementName"] == "Lead" and aa["ArrangementType"] == 0 and aa["RouteMask"] == 1
    assert la["Representative"] == 1 and aa["Representative"] == 0
    assert la["ArrangementProperties"]["represent"] == 1
    assert aa["ArrangementProperties"]["represent"] == 0
    assert aa["ArrangementProperties"]["bonusArr"] == 1
    assert la["PersistentID"] != aa["PersistentID"]
    assert arrangement_asset_name("MySong", ArrangementKind.ALTERNATE_LEAD) == "mysong_lead2"
    assert arrangement_asset_name("MySong", ArrangementKind.ALTERNATE_RHYTHM) == "mysong_rhythm2"


def test_build_manifest_files_emits_distinct_lead_and_alternate() -> None:
    files = build_manifest_files(
        [
            (_arrangement(ArrangementKind.LEAD), "mysong_lead"),
            (_arrangement(ArrangementKind.ALTERNATE_LEAD), "mysong_lead2"),
        ],
        "MySong",
    )
    assert "manifests/songs_dlc_mysong/mysong_lead.json" in files
    assert "manifests/songs_dlc_mysong/mysong_lead2.json" in files
    hsan = json.loads(files["manifests/songs_dlc_mysong/songs_dlc_mysong.hsan"])
    assert len(hsan["Entries"]) == 2  # both leads listed, distinct persistent IDs


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
