"""The Bass arrangement, encoded as DLC Builder encodes it (Rocksmith2014.NET).

ArrangementName 3 / ArrangementType 3 / RouteMask 4, pathBass, the `bass` asset,
tuning offsets measured from E1 A1 D2 G2 with strings 4-5 following string 3,
chord-template pitches an octave below the guitar's (Midi.toMidiNote with
isBass), DLC Builder's default bass tone, its low-tuning fix (220 Hz, +12) and
the checker's "no bass note on string 4 or higher" (I36).
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import guitarpro as gp
import pytest

from rockforge.application.gp_pipeline import GenerateFromGpUseCase, GpJobSpec
from rockforge.domain.arrangement import Arrangement, ArrangementKind, SongMetadata, game_names
from rockforge.domain.music import Beat, TabNote, TempoMap, Tuning
from rockforge.infrastructure.packaging.dlcbuilder import DlcBuilderPackager
from rockforge.infrastructure.packaging.psarc import sng
from rockforge.infrastructure.packaging.psarc.manifest import (
    arrangement_asset_name,
    build_arrangement_manifest,
)
from rockforge.infrastructure.packaging.psarc.verify import check_sng, describe
from rockforge.infrastructure.packaging.rs2dlc import build_rs2dlc
from rockforge.infrastructure.rsxml.reader import read_arrangement_xml
from rockforge.infrastructure.rsxml.writer import render_arrangement


class _Ingest:
    def fetch(self, source: str, workdir: Path) -> Path:
        workdir.mkdir(parents=True, exist_ok=True)
        (workdir / "in.wav").write_bytes(b"RIFF")
        return workdir / "in.wav"


class _Normalize:
    def normalize(self, audio: Path, workdir: Path, offset_s: float = 0.0,
                  pad_start_s: float = 0.0) -> Path:
        return audio


def _use_case() -> GenerateFromGpUseCase:
    return GenerateFromGpUseCase(ingestor=_Ingest(), normalizer=_Normalize(),
                                 packager=DlcBuilderPackager())


def _beat(voice: gp.Voice, notes: list[tuple[int, int]], value: int = 4) -> None:
    b = gp.Beat(voice)
    b.status = gp.BeatStatus.normal
    b.duration = gp.Duration(value=value)
    for string, fret in notes:  # GP strings: 1 = highest
        n = gp.Note(b)
        n.string, n.value, n.type = string, fret, gp.NoteType.normal
        b.notes.append(n)
    voice.beats.append(b)


@pytest.fixture()
def guitar_and_bass(tmp_path: Path) -> Path:
    """A guitar and a B-standard bass (low enough for the low-tuning fix)."""
    song = gp.Song()
    song.title, song.artist, song.tempo = "Low", "Band", 120
    gtr = song.tracks[0]
    gtr.name = "Guitar"
    for fret in (5, 7, 8, 7):
        _beat(gtr.measures[0].voices[0], [(1, fret)])
    bass = gp.Track(song, number=2, name="Bass",
                    strings=[gp.GuitarString(i + 1, p) for i, p in enumerate((38, 33, 28, 23))])
    song.tracks.append(bass)
    while len(bass.measures) < len(song.measureHeaders):
        bass.measures.append(gp.Measure(bass, song.measureHeaders[len(bass.measures)]))
    v = bass.measures[0].voices[0]
    _beat(v, [(4, 0)])  # low B
    _beat(v, [(4, 3), (3, 2)])  # a two-note chord: D1 + F#1
    _beat(v, [(1, 5)])
    _beat(v, [(2, 2)])
    path = tmp_path / "low.gp5"
    gp.write(song, str(path))
    return path


def _bass_arr(notes: list[TabNote], tuning: Tuning | None = None) -> Arrangement:
    return Arrangement(
        kind=ArrangementKind.BASS,
        metadata=SongMetadata(title="T", artist="A", song_length=10.0),
        tuning=tuning or Tuning.for_bass([28, 33, 38, 43]),
        tempo_map=TempoMap(beats=tuple(Beat(time=i * 0.5, measure=i // 4 + 1 if i % 4 == 0
                                            else -1) for i in range(16)), average_bpm=120.0),
        notes=notes,
    )


def test_a_song_builds_its_guitar_and_its_bass_from_their_own_tracks(
    guitar_and_bass: Path, tmp_path: Path
) -> None:
    spec = GpJobSpec(gp_path=guitar_and_bass, audio_source="x.wav", lead_track=0, bass_track=1)
    result = _use_case().run(spec, SongMetadata(title="Low", artist="Band"), tmp_path / "w")
    # A lone guitar chart beside a Bass is still the conventional Combo.
    assert result.note_counts == {"Combined": 4, "Bass": 5}
    bass_xml = next(p for p in result.packaging.xml_paths if p.name == "arrangement_bass.xml")
    root = ET.parse(bass_xml).getroot()
    assert root.findtext("arrangement") == "Bass"
    props = root.find("arrangementProperties")
    assert props is not None
    paths = (props.get("pathLead"), props.get("pathRhythm"), props.get("pathBass"))
    assert paths == ("0", "0", "1")
    assert props.get("routeMask") == "4"
    # B standard (-5) is below DLC Builder's -4 limit: written an octave up at 220 Hz.
    tuning = root.find("tuning")
    assert tuning is not None
    assert [tuning.get(f"string{i}") for i in range(6)] == ["7"] * 6
    assert float(root.findtext("centOffset") or 0) == pytest.approx(-1200.0)
    assert any("220 Hz" in w for w in result.warnings)


def _bass_tuning(result: object) -> tuple[list[str | None], float]:
    bass_xml = next(p for p in result.packaging.xml_paths  # type: ignore[attr-defined]
                    if p.name == "arrangement_bass.xml")
    root = ET.parse(bass_xml).getroot()
    tuning = root.find("tuning")
    assert tuning is not None
    return ([tuning.get(f"string{i}") for i in range(6)],
            float(root.findtext("centOffset") or 0))


def test_the_bass_can_be_written_at_a220_in_a_tuning_the_auto_rule_leaves_alone(
    guitar_and_bass: Path, tmp_path: Path
) -> None:
    # Drop D (-2 on the low string) is above the -4 limit: A440 by default, and
    # an octave up at 220 Hz when the user picks A220 (a forum request).
    drop_d = {"Bass": (26, 33, 38, 43)}
    meta = SongMetadata(title="Low", artist="Band")
    auto = _use_case().run(
        GpJobSpec(gp_path=guitar_and_bass, audio_source="x.wav", lead_track=0, bass_track=1,
                  tuning_overrides=drop_d), meta, tmp_path / "a")
    assert _bass_tuning(auto) == (["-2", "0", "0", "0", "0", "0"], 0.0)
    a220 = _use_case().run(
        GpJobSpec(gp_path=guitar_and_bass, audio_source="x.wav", lead_track=0, bass_track=1,
                  tuning_overrides=drop_d, bass_reference="a220", cent_offset=-10.0),
        meta, tmp_path / "b")
    assert _bass_tuning(a220) == (["10", "12", "12", "12", "12", "12"], -1210.0)
    assert any("A220" in w for w in a220.warnings)


def test_the_bass_can_stay_at_a440_below_the_limit_and_says_what_that_costs(
    guitar_and_bass: Path, tmp_path: Path
) -> None:
    result = _use_case().run(
        GpJobSpec(gp_path=guitar_and_bass, audio_source="x.wav", lead_track=0, bass_track=1,
                  bass_reference="a440"),
        SongMetadata(title="Low", artist="Band"), tmp_path / "w")
    assert _bass_tuning(result) == (["-5"] * 6, 0.0)
    assert any("A440" in w and "may not detect" in w for w in result.warnings)
    assert not any("220 Hz" in w for w in result.warnings)


def test_a_bass_track_is_picked_when_the_user_picks_nothing(
    guitar_and_bass: Path, tmp_path: Path
) -> None:
    spec = GpJobSpec(gp_path=guitar_and_bass, audio_source="x.wav")
    result = _use_case().run(spec, SongMetadata(title="Low", artist="Band"), tmp_path / "w")
    assert set(result.note_counts) == {"Combined", "Bass"}


def test_the_bass_is_named_and_routed_as_the_game_names_it() -> None:
    arr = _bass_arr([TabNote(string=0, fret=3, time=0.5, sustain=0.0)])
    asset = arrangement_asset_name("MySong", ArrangementKind.BASS)
    assert asset == "mysong_bass"
    (entry,) = build_arrangement_manifest(arr, "MySong", asset)["Entries"].values()
    attrs = entry["Attributes"]
    names = (attrs["ArrangementName"], attrs["ArrangementType"], attrs["RouteMask"])
    assert names == ("Bass", 3, 4)
    assert attrs["FullName"] == "MySong_Bass"
    props = attrs["ArrangementProperties"]
    assert (props["pathLead"], props["pathRhythm"], props["pathBass"], props["routeMask"]) == (
        0, 0, 1, 4)
    # No tone of its own → DLC Builder's default BASS tone, not a guitar amp.
    assert [t["Key"] for t in attrs["Tones"]] == ["Default_Bass"]
    assert attrs["Tones"][0]["GearList"]["Amp"]["Key"] == "Bass_Amp_EdenWT550"
    assert game_names([ArrangementKind.LEAD, ArrangementKind.BASS]) == ["LEAD", "BASS"]


def test_the_dlc_builder_project_lists_the_bass_with_its_name_and_route() -> None:
    project = build_rs2dlc([_bass_arr([TabNote(string=0, fret=3, time=0.5, sustain=0.0)])],
                           ["arrangement_bass.xml"], "audio.wav", "Key")
    fields = project["Arrangements"][0]["Fields"][0]  # type: ignore[index]
    assert (fields["Name"], fields["RouteMask"], fields["BassPicked"]) == (3, 4, False)
    assert fields["Tuning"] == [0, 0, 0, 0, 0, 0]


def test_a_drop_d_bass_writes_its_offsets_from_e1_and_reads_back_as_a_bass(tmp_path: Path) -> None:
    arr = _bass_arr([TabNote(string=0, fret=0, time=0.5, sustain=0.0)],
                    Tuning.for_bass([26, 33, 38, 43]))
    root = render_arrangement(arr)
    tuning = root.find("tuning")
    assert tuning is not None
    assert [tuning.get(f"string{i}") for i in range(6)] == ["-2", "0", "0", "0", "0", "0"]
    path = tmp_path / "arrangement_bass.xml"
    ET.ElementTree(root).write(path)
    back = read_arrangement_xml(path)
    assert back.kind is ArrangementKind.BASS
    assert back.tuning.bass and back.tuning.midi[:4] == (26, 33, 38, 43)


def test_bass_chord_templates_sound_an_octave_below_the_guitar() -> None:
    # Midi.toMidiNote with isBass: 40-std table + offset + fret - 12.
    arr = _bass_arr([
        TabNote(string=0, fret=3, time=0.5, sustain=0.0),
        TabNote(string=1, fret=5, time=0.5, sustain=0.0),
    ])
    model = sng.from_arrangement(arr)
    (template,) = model.chord_templates
    assert list(template.notes) == [31, 38, -1, -1, -1, -1]
    assert check_sng(model, bass=True) == []


def test_a_bass_note_on_a_fifth_string_is_a_known_fault() -> None:
    guitarish = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="T", artist="A", song_length=10.0),
        tuning=Tuning(),
        tempo_map=_bass_arr([]).tempo_map,
        notes=[TabNote(string=4, fret=2, time=0.5, sustain=0.0)],
    )
    model = sng.from_arrangement(guitarish)
    assert check_sng(model) == []
    assert {p.code for p in check_sng(model, bass=True)} == {"bass_string"}
    assert describe("bass_string") != "bass_string"
    assert _bass_arr([TabNote(string=4, fret=2, time=0.5, sustain=0.0)]).validate()


def test_a_bass_manifest_is_how_the_psarc_check_knows_the_chart_is_a_bass(tmp_path: Path) -> None:
    # verify_psarc reads pathBass from the manifest to apply the bass rule.
    arr = _bass_arr([TabNote(string=0, fret=3, time=0.5, sustain=0.0)])
    asset = arrangement_asset_name("MySong", ArrangementKind.BASS)
    doc = build_arrangement_manifest(arr, "MySong", asset)
    attrs = next(iter(doc["Entries"].values()))["Attributes"]  # type: ignore[attr-defined]
    assert json.loads(json.dumps(attrs))["ArrangementProperties"]["pathBass"] == 1


def test_a_level_of_only_open_strings_still_has_an_anchor() -> None:
    # A bass line's open roots are what its lowest DD levels keep: with no
    # fretted note to place a window, the level used to ship no anchor at all.
    notes = []
    for bar in range(3):
        t = 2.0 + bar * 2.0
        notes += [TabNote(string=0, fret=0, time=t, sustain=0.4),
                  TabNote(string=0, fret=3, time=t + 0.5, sustain=0.4),
                  TabNote(string=0, fret=5, time=t + 1.0, sustain=0.4),
                  TabNote(string=1, fret=2, time=t + 1.5, sustain=0.3),
                  TabNote(string=2, fret=2, time=t + 1.5, sustain=0.3)]
    arr = _bass_arr(notes)
    arr = Arrangement(kind=arr.kind, metadata=arr.metadata, tuning=arr.tuning,
                      tempo_map=TempoMap(beats=tuple(
                          Beat(time=i * 0.5, measure=i // 4 + 1 if i % 4 == 0 else -1)
                          for i in range(20)), average_bpm=120.0), notes=notes)
    model = sng.from_arrangement(arr)
    assert any(all(n.fret == 0 for n in lv.notes) and lv.notes for lv in model.arrangements)
    assert all(lv.anchors for lv in model.arrangements if lv.notes)
    assert check_sng(model, bass=True) == []


def test_the_bass_never_takes_the_songs_guitar_tones(guitar_and_bass: Path, tmp_path: Path) -> None:
    """GitHub issue #9: the tone detection proposes guitar tones, and a Bass
    with no tones of its own took them (a guitar amp on the bass chart). It
    now takes only the song's bass tones — the default bass tone when there
    are none — while a set chosen for the Bass itself is kept."""
    from rockforge.application.gp_pipeline import ArrangementTones
    from rockforge.infrastructure.packaging.gear.gear_catalogue import tones_from_dicts
    from rockforge.infrastructure.packaging.gear.tone_presets import suggest_tones

    guitar = suggest_tones("high_gain")
    tones = tones_from_dicts([guitar["lead"], guitar["rhythm"]])
    meta = SongMetadata(title="Low", artist="Band")

    def tonebase(result: object, name: str) -> str | None:
        xml = next(p for p in result.packaging.xml_paths  # type: ignore[attr-defined]
                   if p.name == name)
        return ET.parse(xml).getroot().findtext("tonebase")

    song_set = GpJobSpec(gp_path=guitar_and_bass, audio_source="x.wav", lead_track=0,
                         bass_track=1, tones=tones, tone_base=guitar["lead"]["key"],
                         tone_names=[guitar["lead"]["key"], guitar["rhythm"]["key"]])
    result = _use_case().run(song_set, meta, tmp_path / "a")
    assert tonebase(result, "arrangement_combined.xml") == guitar["lead"]["key"]
    assert tonebase(result, "arrangement_bass.xml") is None  # → the default bass tone
    assert any("guitar tones are left to the guitar charts" in w for w in result.warnings)

    own = GpJobSpec(gp_path=guitar_and_bass, audio_source="x.wav", lead_track=0,
                    bass_track=1, tones=tones, tone_base=guitar["lead"]["key"],
                    arrangement_tones={"Bass": ArrangementTones(tone_base=guitar["rhythm"]["key"])})
    result = _use_case().run(own, meta, tmp_path / "b")
    assert tonebase(result, "arrangement_bass.xml") == guitar["rhythm"]["key"]
