from rockforge.domain.arrangement import (
    Arrangement,
    ArrangementKind,
    SongMetadata,
    ToneChange,
)
from rockforge.domain.music import TabNote, TempoMap, Tuning
from rockforge.infrastructure.packaging.gear.gear_catalogue import (
    TONE_DESCRIPTORS,
    catalogue_for_ui,
    knob_defaults,
    tone_from_dict,
    tones_from_dicts,
)
from rockforge.infrastructure.packaging.rs2dlc import build_rs2dlc


def _arr(**kw: object) -> Arrangement:
    base = dict(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="S", artist="A", song_length=10.0),
        tuning=Tuning(),
        tempo_map=TempoMap(beats=(), average_bpm=120.0),
        notes=[TabNote(string=0, fret=2, time=0.0, sustain=0.5)],
    )
    base.update(kw)
    return Arrangement(**base)  # type: ignore[arg-type]


def test_catalogue_groups_gear_by_type() -> None:
    cat = catalogue_for_ui()
    assert len(cat["amps"]) > 0
    assert len(cat["cabinets"]) > 0
    assert len(cat["pedals"]) > 0
    assert len(cat["racks"]) > 0
    # Every amp exposes its knobs with range + default.
    amp = next(a for a in cat["amps"] if a["key"] == "Amp_MarshallJCM800")
    gain = next(k for k in amp["knobs"] if k["key"] == "Amp_MarshallJCM800_Gain")
    assert gain["default"] == 88
    assert gain["max"] == 100


def test_knob_defaults_use_authoritative_keys() -> None:
    # The JCM800 "Presence" knob key is _Pres, NOT _Presence (TONE.md prose is
    # approximate; the catalogue is the source of truth).
    defaults = knob_defaults("Amp_MarshallJCM800")
    assert "Amp_MarshallJCM800_Pres" in defaults
    assert "Amp_MarshallJCM800_Presence" not in defaults


def test_tone_from_dict_fills_missing_knobs_from_defaults() -> None:
    tone = tone_from_dict(
        {
            "key": "lead",
            "name": "Lead",
            "amp": {"key": "Amp_MarshallJCM800", "knobs": {"Amp_MarshallJCM800_Gain": 95}},
            "cabinet": {"key": "Cab_Marshall1960TV_Ribbon_Cone"},
        }
    )
    assert tone is not None
    # User-set knob preserved, the rest filled from catalogue defaults.
    assert tone.gear.amp.knob_values["Amp_MarshallJCM800_Gain"] == 95.0
    assert tone.gear.amp.knob_values["Amp_MarshallJCM800_Bass"] == 75.0
    assert tone.gear.amp.gear_type == "Amps"
    assert tone.gear.cabinet.gear_type == "Cabinets"


def test_tone_from_dict_requires_amp_and_cabinet() -> None:
    assert tone_from_dict({"key": "x", "name": "x"}) is None
    assert tone_from_dict({"amp": {"key": "Amp_MarshallJCM800"}}) is None  # no cab
    assert tone_from_dict({"amp": {"key": "NOPE"}, "cabinet": {"key": "NOPE"}}) is None


def test_descriptor_catalogue_has_known_entries() -> None:
    assert TONE_DESCRIPTORS["Clean"] == "$[35720]CLEAN"
    assert TONE_DESCRIPTORS["Lead"] == "$[35724]LEAD"


def test_rs2dlc_emits_tone_dto_matching_dlc_builder_shape() -> None:
    tone = tone_from_dict(
        {
            "key": "JCM800Lead",
            "name": "JCM800 Lead",
            "volume": -12.0,
            "descriptors": ["$[35724]LEAD"],
            "amp": {"key": "Amp_MarshallJCM800", "knobs": {"Amp_MarshallJCM800_Gain": 95}},
            "cabinet": {"key": "Cab_Marshall1960TV_Ribbon_Cone"},
            "pre": [{"key": "Pedal_GermaniumDrive"}],
        }
    )
    assert tone is not None
    arr = _arr(tone_base="JCM800Lead", tone_names=["JCM800Lead"], tones=[tone])
    proj = build_rs2dlc([arr], ["arrangement_lead.xml"], "audio.wem", "Key")

    (dto,) = proj["Tones"]
    assert dto["IsCustom"] is True
    assert dto["NameSeparator"] == " - "
    assert dto["Volume"] == "-12.000"  # string, 3 decimals (volumeToString)
    assert dto["Key"] == "JCM800Lead"
    assert dto["ToneDescriptors"] == ["$[35724]LEAD"]

    gear = dto["GearList"]
    # Amp + cabinet present, identified by Key, with type but no Category.
    assert gear["Amp"]["Key"] == "Amp_MarshallJCM800"
    assert gear["Amp"]["Type"] == "Amps"
    assert "Category" not in gear["Amp"]
    assert gear["Cabinet"]["KnobValues"] == {}
    assert "Category" not in gear["Cabinet"]
    # The pre-pedal lands in PrePedal1 and keeps its effect Category.
    assert gear["PrePedal1"]["Key"] == "Pedal_GermaniumDrive"
    assert gear["PrePedal1"]["Category"] == "Distortion"
    # Empty slots are omitted entirely (not null).
    assert "PrePedal2" not in gear
    assert "Rack1" not in gear

    # The instrumental references the tone by key.
    inst = proj["Arrangements"][0]["Fields"][0]
    assert inst["BaseTone"] == "JCM800Lead"
    assert inst["Tones"] == ["JCM800Lead"]


def test_shared_tone_emitted_once_across_arrangements() -> None:
    tone = tone_from_dict(
        {
            "key": "shared",
            "name": "Shared",
            "amp": {"key": "Amp_MarshallJCM800"},
            "cabinet": {"key": "Cab_Marshall1960TV_Ribbon_Cone"},
        }
    )
    assert tone is not None
    lead = _arr(kind=ArrangementKind.LEAD, tone_base="shared", tones=[tone])
    rhythm = _arr(kind=ArrangementKind.RHYTHM, tone_base="shared", tones=[tone])
    proj = build_rs2dlc(
        [lead, rhythm], ["lead.xml", "rhythm.xml"], "audio.wem", "Key"
    )
    assert len(proj["Tones"]) == 1


def test_no_tones_keeps_empty_project_tones() -> None:
    arr = _arr(tone_base="clean", tone_names=["clean"])
    proj = build_rs2dlc([arr], ["lead.xml"], "audio.wem", "Key")
    assert proj["Tones"] == []
    # Names still flow through for DLC Builder to resolve from its library.
    assert proj["Arrangements"][0]["Fields"][0]["BaseTone"] == "clean"


def test_validate_flags_referenced_tone_without_definition() -> None:
    tone = tone_from_dict(
        {
            "key": "lead",
            "name": "Lead",
            "amp": {"key": "Amp_MarshallJCM800"},
            "cabinet": {"key": "Cab_Marshall1960TV_Ribbon_Cone"},
        }
    )
    assert tone is not None
    # tone_base "missing" has no definition among tones -> a problem.
    arr = _arr(tone_base="missing", tone_names=["lead"], tones=[tone])
    problems = arr.validate()
    assert any("missing" in p for p in problems)


def test_tone_changes_validate_against_known_names() -> None:
    arr = _arr(
        tone_base="clean",
        tone_names=["dist"],
        tone_changes=[ToneChange(time=1.0, name="dist"), ToneChange(time=2.0, name="ghost")],
    )
    problems = arr.validate()
    assert any("ghost" in p for p in problems)
    assert not any("dist" in p for p in problems)


def test_tones_from_dicts_drops_invalid() -> None:
    tones = tones_from_dicts(
        [
            {"key": "ok", "amp": {"key": "Amp_MarshallJCM800"},
             "cabinet": {"key": "Cab_Marshall1960TV_Ribbon_Cone"}},
            {"key": "bad"},  # no amp/cabinet
        ]
    )
    assert len(tones) == 1
    assert tones[0].key == "ok"
