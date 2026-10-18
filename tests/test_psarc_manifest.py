import json

import pytest

from rockforge.domain.arrangement import Arrangement, ArrangementKind, Section, SongMetadata
from rockforge.domain.music import Beat, TabNote, Technique, TempoMap, Tuning
from rockforge.infrastructure.packaging.psarc import manifest
from rockforge.infrastructure.packaging.psarc.container import pack_entries, unpack
from rockforge.infrastructure.packaging.psarc.manifest import (
    arrangement_asset_name,
    arrangement_stats,
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
    # No gear of its own → DLC Builder's default Lead tone, never no tone.
    assert attrs["Tone_Base"] == "Default_Lead"
    assert [t["Key"] for t in attrs["Tones"]] == ["Default_Lead"]
    assert attrs["Tones"][0]["GearList"]["Amp"]["Key"] == "Amp_MarshallPlexi"


def test_arrangement_properties_report_the_techniques_actually_played() -> None:
    """The technique flags were all hard-zero, so every chart advertised itself as
    using no techniques at all — a false claim about the arrangement's content
    (a DLC Builder build of the same song sets palmMutes/powerChords/slides/
    sustain/vibrato/hopo/openChords from the notes). They must be derived from
    the chart, and a technique the chart does NOT use must stay 0."""
    notes = [
        # A power chord (root + fifth on the adjacent string, two frets up).
        TabNote(string=0, fret=5, time=0.0, sustain=0.5,
                techniques=frozenset({Technique.PALM_MUTE})),
        TabNote(string=1, fret=7, time=0.0, sustain=0.5),
        # A slide with vibrato.
        TabNote(string=2, fret=3, time=1.0, sustain=0.4, slide_to_fret=7,
                techniques=frozenset({Technique.VIBRATO})),
    ]
    arrangement = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="My Song", artist="My Artist", song_length=10.0),
        tuning=Tuning(),
        tempo_map=TempoMap(beats=(Beat(time=0.0, measure=1),), average_bpm=120.0),
        notes=notes,
    )
    (entry,) = build_arrangement_manifest(arrangement, "MySong", "Lead")["Entries"].values()
    props = entry["Attributes"]["ArrangementProperties"]
    assert props["palmMutes"] == 1
    assert props["powerChords"] == 1
    assert props["slides"] == 1
    assert props["vibrato"] == 1
    assert props["sustain"] == 1
    # Not played here — must not be claimed.
    assert props["tapping"] == 0
    assert props["harmonics"] == 0
    assert props["bends"] == 0
    assert props["hopo"] == 0


def test_manifest_reports_the_lead_in_and_a_real_target_score() -> None:
    """SongOffset (the recording's lead-in, which the game shifts its clock by)
    and TargetScore (the score counting as full mastery) were both hard 0. A DLC
    Builder build of the same song writes -startTime and 100000."""
    arrangement = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="My Song", artist="My Artist", song_length=120.0),
        tuning=Tuning(),
        tempo_map=TempoMap(
            beats=(Beat(time=6.421, measure=1), Beat(time=6.921, measure=-1)),
            average_bpm=120.0,
        ),
        notes=[TabNote(string=0, fret=2, time=6.421, sustain=0.5)],
    )
    (entry,) = build_arrangement_manifest(arrangement, "MySong", "Lead")["Entries"].values()
    attrs = entry["Attributes"]
    assert attrs["SongOffset"] == -6.421
    assert attrs["TargetScore"] == 100_000
    assert attrs["SongPartition"] == 1


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


def test_each_chart_carries_its_number_on_its_path() -> None:
    """SongPartition is the chart's number among the charts of its path (DLC
    Builder's Partitioner: the alternate Lead is 2) — it was 1 on every chart.
    The main chart is 1 whatever order the list is in."""
    def partitions(kinds: list[ArrangementKind]) -> dict[str, int]:
        files = build_manifest_files(
            [(_arrangement(k), arrangement_asset_name("MySong", k)) for k in kinds], "MySong",
        )
        out = {}
        for k in kinds:
            name = arrangement_asset_name("MySong", k)
            doc = json.loads(files[f"manifests/songs_dlc_mysong/{name}.json"])
            out[name] = next(iter(doc["Entries"].values()))["Attributes"]["SongPartition"]
        return out

    assert partitions([
        ArrangementKind.ALTERNATE_LEAD, ArrangementKind.RHYTHM,
        ArrangementKind.LEAD, ArrangementKind.COMBINED,
    ]) == {"mysong_lead2": 2, "mysong_rhythm": 1, "mysong_lead": 1, "mysong_combo": 1}
    assert partitions([ArrangementKind.RHYTHM, ArrangementKind.ALTERNATE_RHYTHM]) == {
        "mysong_rhythm": 1, "mysong_rhythm2": 2,
    }


def test_game_names_number_only_a_path_with_two_charts() -> None:
    from rockforge.domain.arrangement import game_names

    k = ArrangementKind
    assert game_names([k.LEAD, k.RHYTHM, k.COMBINED]) == ["LEAD", "RHYTHM", "COMBO"]
    assert game_names([k.ALTERNATE_LEAD, k.LEAD, k.RHYTHM]) == ["LEAD 2", "LEAD 1", "RHYTHM"]
    assert game_names([k.ALTERNATE_RHYTHM]) == ["RHYTHM"]


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


def test_song_difficulty_easy_medium_hard_are_three_different_densities() -> None:
    """They used to be ONE value written three times.

    Byte-diffing a DLC Builder build of the same song gives the formula exactly:
    each is that difficulty's note density scaled back up by how much of the
    chart it shows — 4x NotesEasy, 2x NotesMedium, 1x NotesHard, each over
    10 x songLength. On the reference (182/331/623 notes over 202.509 s) that
    reproduces its 0.359490191 / 0.326899047 / 0.307640644 to the last digit,
    where we wrote 0.307641 for all three.
    """
    stats = {"note_count": 623, "easy_count": 182, "medium_count": 331}
    fields = manifest._difficulty_fields(stats, 202.509)
    assert fields["SongDiffEasy"] == pytest.approx(0.359490191, abs=5e-7)
    assert fields["SongDiffMed"] == pytest.approx(0.326899047, abs=5e-7)
    assert fields["SongDiffHard"] == pytest.approx(0.307640644, abs=5e-7)
    assert fields["SongDifficulty"] == fields["SongDiffHard"]
    assert len({fields["SongDiffEasy"], fields["SongDiffMed"], fields["SongDiffHard"]}) == 3


def _dd_arrangement() -> Arrangement:
    """A chart with enough variety that DD produces several levels and the
    phrases get genuinely different ceilings."""
    beats = tuple(Beat(time=round(i * 0.5, 4), measure=i // 4 + 1 if i % 4 == 0 else -1)
                  for i in range(96))
    notes: list[TabNote] = []
    t, i = 0.0, 0
    while t < 46.0:
        tech = set()
        if i % 5 == 1:
            tech.add(Technique.HAMMER_ON)
        if i % 5 == 2:
            tech.add(Technique.PULL_OFF)
        if i % 7 == 3:
            tech.add(Technique.VIBRATO)
        notes.append(TabNote(
            string=i % 6, fret=(i % 9) + 1, time=round(t, 4), sustain=0.15,
            techniques=frozenset(tech),
            slide_to_fret=(i % 9) + 3 if i % 11 == 4 else None,
        ))
        t += 0.125 if (int(t) // 12) % 2 == 0 else 0.5
        i += 1
    return Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="S", artist="A", song_length=48.0),
        tuning=Tuning(),
        tempo_map=TempoMap(beats=beats, average_bpm=120.0),
        notes=notes,
        sections=[Section(name=f"s{k}", start_time=round(k * 6.0, 3)) for k in range(8)],
    )


def test_note_counts_are_per_iteration_hero_totals_not_one_level() -> None:
    """NotesEasy/Medium/Hard are what the player SEES at each hero setting: for
    every phrase iteration, the count at ITS OWN hero level, summed.

    They used to be ``len(levels[k].notes)`` for a fixed k, which was only ever
    right for Hard while the top level held the whole chart. Now that a phrase
    drops out of the levels above its ceiling, NO single level is the full
    chart — the reference's top levels hold 126 of 623 and 99 of 525 notes —
    so reading a level would under-report Hard badly. Derived from a DLC
    Builder build and exact on both its arrangements (182/331/623 and
    155/283/525).
    """
    from rockforge.infrastructure.packaging.psarc.sng import from_arrangement

    arr = _dd_arrangement()
    model = from_arrangement(arr, dynamic_difficulty=True)
    assert len(model.arrangements) > 3, "precondition: the fixture must ramp"
    assert len(model.arrangements[-1].notes) < len(arr.notes), (
        "precondition: the top level must no longer be the whole chart"
    )
    stats = arrangement_stats(arr, model=model)
    assert stats["note_count"] == len(arr.notes), "Hard must still be the FULL chart"
    assert 0 < int(stats["easy_count"]) <= int(stats["medium_count"]) <= int(stats["note_count"])


def test_techniques_map_carries_only_the_derived_ids() -> None:
    """The per-difficulty technique map was ``{}``. It now carries the five ids
    that were derived at exact equivalence against a DLC Builder build
    (hammer-on 3, HOPO 6, pull-off 9, slide 11, vibrato 16) — and NOTHING else:
    the rest of that game-internal enum has no evidence behind it, and a
    guessed id in a field the game reads is how the earlier highway crashes
    happened.
    """
    from rockforge.infrastructure.packaging.psarc.sng import from_arrangement

    arr = _dd_arrangement()
    model = from_arrangement(arr, dynamic_difficulty=True)
    man = build_arrangement_manifest(
        arr, "Key", "Lead", stats=arrangement_stats(arr, model=model)
    )
    attrs = list(man["Entries"].values())[0]["Attributes"]
    tech = attrs["Techniques"]
    assert tech, "the fixture carries hammer-ons, pull-offs, slides and vibrato"
    used = {i for level in tech.values() for ids in level.values() for i in ids}
    assert used <= {3, 6, 9, 11, 16}, f"an unmapped technique id leaked out: {used}"
    assert {3, 9, 11, 16} <= used

    # A HOPO id must accompany every hammer-on / pull-off, and the keys must be
    # real level and phrase-iteration indices the game can dereference.
    for level_s, per_iter in tech.items():
        assert 0 <= int(level_s) < len(model.arrangements)
        for it_s, ids in per_iter.items():
            assert 0 <= int(it_s) < len(model.phrase_iterations)
            if 3 in ids or 9 in ids:
                assert 6 in ids
    # The stats dict carries the compiled model for this; it must not leak into
    # the JSON the game parses.
    assert "model" not in attrs
    assert json.dumps(attrs)


def test_last_conversion_is_present_and_stable_across_rebuilds() -> None:
    """It was missing entirely. It is emitted as a CONSTANT: a value that
    changes every rebuild is exactly what could make the game treat a rebuilt
    song as newly converted and drop its saved progress."""
    arr = _dd_arrangement()
    first = build_arrangement_manifest(arr, "Key", "Lead")
    second = build_arrangement_manifest(arr, "Key", "Lead")
    a = list(first["Entries"].values())[0]["Attributes"]
    b = list(second["Entries"].values())[0]["Attributes"]
    assert a["LastConversionDateTime"] == b["LastConversionDateTime"]
    assert a["LastConversionDateTime"]


def _auto_segmented_arrangement(kind: ArrangementKind = ArrangementKind.LEAD) -> Arrangement:
    """No section markers, so the pipeline auto-segments into COUNT / riff… /
    END — exactly the reference song's shape (a GP with no markers)."""
    beats = tuple(Beat(time=round(i * 0.5, 4), measure=i // 4 + 1 if i % 4 == 0 else -1)
                  for i in range(320))
    notes = [
        TabNote(string=i % 6, fret=(i % 9) + 1, time=round(8.0 + i * 0.4, 4), sustain=0.15)
        for i in range(240)
    ]
    return Arrangement(
        kind=kind,
        metadata=SongMetadata(title="S", artist="A", song_length=160.0),
        tuning=Tuning(),
        tempo_map=TempoMap(beats=beats, average_bpm=120.0),
        notes=notes,
    )


def test_sections_match_the_reference_shape() -> None:
    """Three divergences from a DLC Builder build of the same song, all fixed
    together because they are all about the SECTION list:

    - the COUNT phrase gets NO section (the reference has 19 sections over 20
      phrase iterations, starting at iteration 1) — the phrase itself stays;
    - the END phrase's section is named "noguitar", the same closer the XML
      writer already appends;
    - numbers are per NAME, so they no longer repeat (we shipped two
      consecutive sections both numbered 2).
    """
    from rockforge.infrastructure.packaging.psarc.sng import from_arrangement

    arr = _auto_segmented_arrangement()
    model = from_arrangement(arr, dynamic_difficulty=True)
    assert [p.name for p in model.phrases][0] == "COUNT", "the COUNT PHRASE stays"

    names = [s.name for s in model.sections]
    assert "COUNT" not in names, "the COUNT phrase must have no section"
    assert "END" not in names, "the END phrase's section is the noguitar closer"
    assert names[-1] == "noguitar"
    pairs = [(s.name, s.number) for s in model.sections]
    assert len(set(pairs)) == len(pairs), f"duplicate (name, number): {pairs}"
    riffs = [n for name, n in pairs if name == "riff"]
    assert riffs == list(range(1, len(riffs) + 1)), "per-name ordinals, 1-based, in order"


def test_section_numbers_continue_across_arrangements() -> None:
    """A DLC Builder build numbers sections once over the whole project, not per
    arrangement: its Lead riffs run 1-17 and its Rhythm riffs continue 18-34
    (noguitars 1-2 then 3-4). Applied in the packer before both the manifests
    and the .sng payloads are derived, so the two can never disagree."""
    from rockforge.infrastructure.packaging.psarc.sng import (
        from_arrangement,
        renumber_sections_across,
    )

    lead = _auto_segmented_arrangement()
    rhythm = _auto_segmented_arrangement(ArrangementKind.RHYTHM)
    models = renumber_sections_across([from_arrangement(a) for a in (lead, rhythm)])
    lead_riffs = [s.number for s in models[0].sections if s.name == "riff"]
    rhythm_riffs = [s.number for s in models[1].sections if s.name == "riff"]
    assert lead_riffs and rhythm_riffs
    assert rhythm_riffs[0] == lead_riffs[-1] + 1
    assert lead_riffs + rhythm_riffs == list(range(1, len(lead_riffs) + len(rhythm_riffs) + 1))
    # The closer's own counter continues too, independently of the riffs'.
    lead_ng = [s.number for s in models[0].sections if s.name == "noguitar"]
    rhythm_ng = [s.number for s in models[1].sections if s.name == "noguitar"]
    assert lead_ng and rhythm_ng
    assert lead_ng + rhythm_ng == list(range(1, len(lead_ng) + len(rhythm_ng) + 1))


def test_section_ui_name_is_a_localisation_token_when_known() -> None:
    """The game resolves a section's display name from a localisation token
    ("$[34298] Riff [1]"), not the raw string we used to write. Only the two ids
    a reference build actually contains are known; any other name falls back to
    the raw string, exactly as before, so it is no worse off."""
    from rockforge.infrastructure.packaging.psarc.sng import from_arrangement

    arr = _auto_segmented_arrangement()
    stats = arrangement_stats(arr, model=from_arrangement(arr))
    by_name = {s["Name"]: s["UIName"] for s in stats["sections"]}  # type: ignore[union-attr]
    assert by_name["riff"] == "$[34298] Riff [1]"
    assert by_name["noguitar"] == "$[6091] No Guitar [1]"
    assert manifest._section_ui_name("Chorus") == "Chorus", "unknown names fall back"


def test_a_song_key_is_ascii_even_for_an_accented_title() -> None:
    """The key names archive paths and the SoundBank (ASCII only): "Canção"
    kept its ç and the .psarc build died encoding it."""
    from rockforge.infrastructure.packaging.psarc.soundbank import generate_soundbank

    assert song_key_from_title("Beyoncé", "Canção") == "BeyonceCancao"
    assert song_key_from_title("Сплин", "Выхода нет") == "RockForgeSong"
    generate_soundbank(song_key_from_title("Sigur Rós", "Hoppípolla"), b"\x00" * 64)
