"""End-to-end GP use case test: real parser + real packager, fake audio stages."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import guitarpro as gp
import pytest

from rockforge.application.gp_pipeline import GenerateFromGpUseCase, GpJobSpec, NoteOverride
from rockforge.domain.arrangement import Section, SongMetadata, ToneChange
from rockforge.domain.music import Technique
from rockforge.infrastructure.packaging.dlcbuilder import DlcBuilderPackager


class FakeIngestor:
    def fetch(self, source: str, workdir: Path) -> Path:
        workdir.mkdir(parents=True, exist_ok=True)
        p = workdir / "input.wav"
        p.write_bytes(b"RIFF")
        return p


class FakeNormalizer:
    def normalize(
        self, audio: Path, workdir: Path, offset_s: float = 0.0, pad_start_s: float = 0.0
    ) -> Path:
        return audio


@pytest.fixture()
def two_track_gp5(tmp_path: Path) -> Path:
    song = gp.Song()
    song.title, song.artist, song.tempo = "Two", "Tracks", 120
    lead = song.tracks[0]
    lead.name = "Lead Gtr"
    v = lead.measures[0].voices[0]
    for fret in [5, 7, 8]:
        b = gp.Beat(v)
        b.status = gp.BeatStatus.normal
        b.duration = gp.Duration(value=4)
        n = gp.Note(b)
        n.string, n.value, n.type = 1, fret, gp.NoteType.normal
        b.notes.append(n)
        v.beats.append(b)

    rhythm = gp.Track(song)
    rhythm.name = "Rhythm Gtr"
    rhythm.number = 2
    song.tracks.append(rhythm)
    v2 = rhythm.measures[0].voices[0]
    b = gp.Beat(v2)
    b.status = gp.BeatStatus.normal
    b.duration = gp.Duration(value=1)
    for string, fret in [(6, 0), (5, 2), (4, 2)]:
        n = gp.Note(b)
        n.string, n.value, n.type = string, fret, gp.NoteType.normal
        b.notes.append(n)
    v2.beats.append(b)

    path = tmp_path / "two.gp5"
    gp.write(song, str(path))
    return path


@pytest.fixture()
def palm_muted_gp5(tmp_path: Path) -> Path:
    song = gp.Song()
    song.title, song.artist, song.tempo = "PM", "Band", 120
    lead = song.tracks[0]
    lead.name = "Lead Gtr"
    v = lead.measures[0].voices[0]
    for fret in [5, 7, 8]:
        b = gp.Beat(v)
        b.status = gp.BeatStatus.normal
        b.duration = gp.Duration(value=4)
        n = gp.Note(b)
        n.string, n.value, n.type = 1, fret, gp.NoteType.normal
        n.effect.palmMute = True
        b.notes.append(n)
        v.beats.append(b)
    path = tmp_path / "pm.gp5"
    gp.write(song, str(path))
    return path


def make_use_case() -> GenerateFromGpUseCase:
    return GenerateFromGpUseCase(
        ingestor=FakeIngestor(),
        normalizer=FakeNormalizer(),
        packager=DlcBuilderPackager(),
    )


def test_gp_pipeline_full_bundle(two_track_gp5: Path, tmp_path: Path) -> None:
    spec = GpJobSpec(
        gp_path=two_track_gp5,
        audio_source="x.wav",
        lead_track=0,
        rhythm_track=1,
        offset_s=0.5,
        lrc_text="[00:01.00]hello\n[00:02.00]world\n",
        tone_base="clean",
        tone_names=["dist"],
        tone_changes=[ToneChange(time=1.0, name="dist")],
    )
    stages: list[str] = []
    result = make_use_case().run(
        spec, SongMetadata(title="Two", artist="Tracks"), tmp_path / "w", on_stage=stages.append
    )
    assert stages == ["ingest", "normalize", "parse_gp", "build_arrangements", "lyrics", "package"]
    assert result.note_counts == {"Lead": 3, "Rhythm": 3}

    names = {p.name for p in result.packaging.xml_paths}
    assert names == {"arrangement_lead.xml", "arrangement_rhythm.xml", "arrangement_vocals.xml"}

    lead_xml = next(p for p in result.packaging.xml_paths if p.name == "arrangement_lead.xml")
    root = ET.parse(lead_xml).getroot()
    # Bar numbering source for the viewer: ebeats carry 1-based measure numbers
    # on downbeats (the /arrangements endpoint filters measure>0 into `bars`).
    bars = [
        int(eb.get("measure", "-1"))
        for eb in root.findall("ebeats/ebeat")
        if int(eb.get("measure", "-1")) > 0
    ]
    assert bars and bars[0] == 1 and bars == sorted(bars)
    assert root.findtext("tonebase") == "clean"
    assert root.findtext("tonea") == "dist"
    tone = root.find("tones/tone")
    assert tone is not None and tone.get("name") == "dist"
    # sync: first note placed at max(offset_s, MIN_LEAD_S) = 2.0 (offset_s=0.5
    # is below the 2.0s minimum lead-in, so content is pushed to 2.0)
    first = root.find("levels/level/notes/note")
    assert first is not None and float(first.get("time", "0")) == pytest.approx(2.0)

    rhythm_xml = next(p for p in result.packaging.xml_paths if p.name == "arrangement_rhythm.xml")
    r = ET.parse(rhythm_xml).getroot()
    assert len(r.findall("levels/level/chords/chord")) == 1  # whole-note chord

    vocals_xml = next(p for p in result.packaging.xml_paths if p.name == "arrangement_vocals.xml")
    v = ET.parse(vocals_xml).getroot()
    # LRC shifts only by the prepended silence (pad = 2.0 - 0.5 = 1.5): 1.0 + 1.5
    assert float(v.findall("vocal")[0].get("time", "0")) == pytest.approx(2.5)


def _section_rows(xml_path: Path) -> list[tuple[str, int, float]]:
    root = ET.parse(xml_path).getroot()
    return [
        (el.get("name", "?"), int(el.get("number", "0")), float(el.get("startTime", "0")))
        for el in root.findall("sections/section")
    ]


def test_section_overrides_replace_gp_parsed_sections_on_every_arrangement(
    two_track_gp5: Path, tmp_path: Path
) -> None:
    """The section editor's overrides are job-level (like tone_changes): when
    set, they replace the GP-parsed section markers identically on every
    arrangement, renumbered/sorted by time regardless of input order."""
    spec = GpJobSpec(
        gp_path=two_track_gp5,
        audio_source="x.wav",
        lead_track=0,
        rhythm_track=1,
        section_overrides=[
            Section(name="Solo", start_time=3.0, number=0),
            Section(name="Intro", start_time=0.5, number=0),
        ],
    )
    result = make_use_case().run(
        spec, SongMetadata(title="Two", artist="Tracks"), tmp_path / "w"
    )
    for name in ("arrangement_lead.xml", "arrangement_rhythm.xml"):
        xml_path = next(p for p in result.packaging.xml_paths if p.name == name)
        rows = _section_rows(xml_path)
        # sorted by time, renumbered 1-based, plus the writer's own trailing
        # "noguitar" end sentinel (always appended, untouched by the override).
        assert rows[:-1] == [("Intro", 1, pytest.approx(0.5)), ("Solo", 2, pytest.approx(3.0))]
        assert rows[-1][0] == "noguitar"


def test_section_overrides_none_keeps_default_gp_parsed_sections(
    two_track_gp5: Path, tmp_path: Path
) -> None:
    """The default (no section_overrides) is unaffected: the two_track_gp5
    fixture has no GP marker, so the writer's fallback single "riff" section
    (plus the trailing "noguitar" sentinel) is unchanged."""
    spec = GpJobSpec(gp_path=two_track_gp5, audio_source="x.wav", lead_track=0, rhythm_track=1)
    result = make_use_case().run(
        spec, SongMetadata(title="Two", artist="Tracks"), tmp_path / "w"
    )
    lead_xml = next(p for p in result.packaging.xml_paths if p.name == "arrangement_lead.xml")
    assert [name for name, _, _ in _section_rows(lead_xml)] == ["riff", "noguitar"]


def _lead_notes(xml_path: Path) -> list[tuple[float, int, int, str]]:
    root = ET.parse(xml_path).getroot()
    return [
        (float(el.get("time", "0")), int(el.get("string", "0")), int(el.get("fret", "0")),
         el.get("hammerOn", "0"))
        for el in root.findall("levels/level/notes/note")
    ]


def test_note_overrides_add_edit_and_delete_are_per_arrangement(
    two_track_gp5: Path, tmp_path: Path
) -> None:
    """The note editor's overrides upsert/delete notes at (time, string), only
    on the arrangement they're keyed to — Rhythm is untouched."""
    base_spec = GpJobSpec(gp_path=two_track_gp5, audio_source="x.wav", lead_track=0, rhythm_track=1)
    base_result = make_use_case().run(
        base_spec, SongMetadata(title="Two", artist="Tracks"), tmp_path / "base"
    )
    lead_xml = next(p for p in base_result.packaging.xml_paths if p.name == "arrangement_lead.xml")
    base_notes = _lead_notes(lead_xml)
    assert len(base_notes) == 3
    del_time, del_string, _, _ = base_notes[0]
    edit_time, edit_string, _, _ = base_notes[1]

    spec = GpJobSpec(
        gp_path=two_track_gp5,
        audio_source="x.wav",
        lead_track=0,
        rhythm_track=1,
        note_overrides={
            "Lead": [
                NoteOverride(time=del_time, string=del_string, deleted=True),
                NoteOverride(
                    time=edit_time, string=edit_string, fret=12, sustain=0.3,
                    techniques=frozenset({Technique.HAMMER_ON}),
                ),
                # A time strictly between two existing beats, on a string none
                # of the base notes use — within the tempo map's beat range
                # (Arrangement.validate() rejects a note past the final ebeat).
                NoteOverride(time=2.75, string=2, fret=3, sustain=0.2),
            ]
        },
    )
    result = make_use_case().run(spec, SongMetadata(title="Two", artist="Tracks"), tmp_path / "w")

    lead_xml2 = next(p for p in result.packaging.xml_paths if p.name == "arrangement_lead.xml")
    notes = _lead_notes(lead_xml2)
    assert len(notes) == 3  # 3 base - 1 deleted + 1 edited (same slot) + 1 added
    assert not any(t == del_time and s == del_string for t, s, _, _ in notes)
    edited = next(n for n in notes if n[0] == edit_time and n[1] == edit_string)
    assert edited[2] == 12 and edited[3] == "1"
    assert any(t == 2.75 and s == 2 and f == 3 for t, s, f, _ in notes)

    # Rhythm has no note_overrides entry — its chord is unaffected.
    rhythm_xml = next(p for p in result.packaging.xml_paths if p.name == "arrangement_rhythm.xml")
    assert len(ET.parse(rhythm_xml).getroot().findall("levels/level/chords/chord")) == 1


def test_note_overrides_empty_or_absent_kind_leaves_notes_untouched(
    two_track_gp5: Path, tmp_path: Path
) -> None:
    spec = GpJobSpec(
        gp_path=two_track_gp5,
        audio_source="x.wav",
        lead_track=0,
        rhythm_track=1,
        note_overrides={"Lead": []},  # present but empty — a no-op, same as absent
    )
    result = make_use_case().run(spec, SongMetadata(title="Two", artist="Tracks"), tmp_path / "w")
    lead_xml = next(p for p in result.packaging.xml_paths if p.name == "arrangement_lead.xml")
    assert len(_lead_notes(lead_xml)) == 3


def test_gp_embedded_lyrics_surface_as_recording_clock_events(
    tmp_path: Path,
) -> None:
    """GP-embedded lyrics are returned in result.gp_lyrics (recording clock) so
    the worker can show them in the editor; the build re-adds pad_start_s."""
    song = gp.Song()
    song.title, song.artist, song.tempo = "L", "B", 120
    lead = song.tracks[0]
    lead.name = "Lead Gtr"
    v = lead.measures[0].voices[0]
    for fret in [5, 7]:
        b = gp.Beat(v)
        b.status = gp.BeatStatus.normal
        b.duration = gp.Duration(value=4)  # quarter = 0.5s at 120 BPM
        n = gp.Note(b)
        n.string, n.value, n.type = 1, fret, gp.NoteType.normal
        b.notes.append(n)
        v.beats.append(b)
    song.lyrics.lines[0].startingMeasure = 1
    song.lyrics.lines[0].lyrics = "hello world"
    path = tmp_path / "lyr.gp5"
    gp.write(song, str(path))

    spec = GpJobSpec(gp_path=path, audio_source="x.wav", lead_track=0)
    result = make_use_case().run(
        spec, SongMetadata(title="L", artist="B"), tmp_path / "w"
    )
    # offset_s=0 → pad_start_s=2.0; gp_lyrics subtract it → recording clock.
    assert [e.lyric for e in result.gp_lyrics] == ["hello", "world+"]
    assert result.gp_lyrics[0].time == pytest.approx(0.0)
    assert result.gp_lyrics[1].time == pytest.approx(0.5)


def test_lead_in_pushes_song_later(two_track_gp5: Path, tmp_path: Path) -> None:
    """User-defined intro silence shifts the whole bundle (notes + audio) later
    on top of the automatic MIN_LEAD_S lead-in."""
    spec = GpJobSpec(
        gp_path=two_track_gp5, audio_source="x.wav", lead_track=0,
        offset_s=0.5, lead_in_s=1.0,
    )
    result = make_use_case().run(spec, SongMetadata(title="T", artist="A"), tmp_path / "w")
    xml = next(p for p in result.packaging.xml_paths if "vocals" not in p.name)
    first = ET.parse(xml).getroot().find("levels/level/notes/note")
    # score_shift = max(offset_s, MIN_LEAD_S) + lead_in_s = max(0.5, 2.0) + 1.0
    assert first is not None and float(first.get("time", "0")) == pytest.approx(3.0)


def test_gp_pipeline_auto_track_selection(two_track_gp5: Path, tmp_path: Path) -> None:
    spec = GpJobSpec(gp_path=two_track_gp5, audio_source="x.wav")
    result = make_use_case().run(spec, SongMetadata(title="T", artist="A"), tmp_path / "w")
    assert set(result.note_counts) == {"Lead", "Rhythm"}  # picked by name heuristic
    assert any("auto-selected" in w for w in result.warnings)


def test_gp_pipeline_same_track_rejected(two_track_gp5: Path, tmp_path: Path) -> None:
    from rockforge.domain.errors import IngestionError

    spec = GpJobSpec(gp_path=two_track_gp5, audio_source="x.wav", lead_track=0, rhythm_track=0)
    with pytest.raises(IngestionError, match="different GP track"):
        make_use_case().run(spec, SongMetadata(title="T", artist="A"), tmp_path / "w")


def test_gp_pipeline_explicit_combo_track(two_track_gp5: Path, tmp_path: Path) -> None:
    # Combo is a first-class, explicitly-assignable arrangement.
    spec = GpJobSpec(gp_path=two_track_gp5, audio_source="x.wav", combo_track=0)
    result = make_use_case().run(spec, SongMetadata(title="T", artist="A"), tmp_path / "w")
    assert set(result.note_counts) == {"Combined"}


def test_gp_pipeline_alternate_arrangement_from_chosen_track(
    two_track_gp5: Path, tmp_path: Path
) -> None:
    # The user maps whichever tracks they want to whichever arrangement: here
    # track 0 -> Lead, track 1 -> Alternate Lead (a second Lead chart).
    spec = GpJobSpec(
        gp_path=two_track_gp5, audio_source="x.wav", lead_track=0, alt_lead_track=1
    )
    result = make_use_case().run(spec, SongMetadata(title="T", artist="A"), tmp_path / "w")
    assert set(result.note_counts) == {"Lead", "Alternate Lead"}


def test_gp_pipeline_per_arrangement_tuning_override(
    two_track_gp5: Path, tmp_path: Path
) -> None:
    # Re-tune only the Lead arrangement to Drop D (low E -> D); Rhythm keeps the GP
    # file's tuning. Verifies the per-arrangement override reaches the XML.
    spec = GpJobSpec(
        gp_path=two_track_gp5, audio_source="x.wav", lead_track=0, rhythm_track=1,
        tuning_overrides={"Lead": (38, 45, 50, 55, 59, 64)},
    )
    result = make_use_case().run(spec, SongMetadata(title="T", artist="A"), tmp_path / "w")
    lead = ET.parse(
        next(p for p in result.packaging.xml_paths if p.name == "arrangement_lead.xml")
    ).getroot().find("tuning")
    rhythm = ET.parse(
        next(p for p in result.packaging.xml_paths if p.name == "arrangement_rhythm.xml")
    ).getroot().find("tuning")
    assert lead is not None and lead.get("string0") == "-2"     # dropped a whole step
    assert rhythm is not None and rhythm.get("string0") == "0"  # unchanged


def test_gp_pipeline_sync_anchors_shift_notes(two_track_gp5: Path, tmp_path: Path) -> None:
    # offset_s=0 -> score_shift=2.0 (MIN_LEAD_S); notes land at 2.0, 2.5, 3.0.
    # A single anchor (2.5 -> 3.0) is a uniform +0.5s shift applied everywhere.
    spec = GpJobSpec(
        gp_path=two_track_gp5, audio_source="x.wav", lead_track=0,
        sync_anchor_stages=[[(2.5, 3.0)]],
    )
    result = make_use_case().run(spec, SongMetadata(title="T", artist="A"), tmp_path / "w")
    assert any("1 manual drift-correction point(s) across 1 round(s)" in w for w in result.warnings)

    lead_xml = next(p for p in result.packaging.xml_paths if p.name == "arrangement_combined.xml")
    times = [float(n.get("time", "0")) for n in ET.parse(lead_xml).getroot().findall(".//note")]
    assert times == pytest.approx([2.5, 3.0, 3.5])


def test_per_arrangement_sync_is_independent(two_track_gp5: Path, tmp_path: Path) -> None:
    # A drift correction (and tempo scale) targeted at the Lead arrangement must
    # not touch the Rhythm arrangement, and vice versa.
    from rockforge.application.gp_pipeline import ArrangementSync

    spec = GpJobSpec(
        gp_path=two_track_gp5, audio_source="x.wav", lead_track=0, rhythm_track=1,
        arrangement_sync={
            "Lead": ArrangementSync(sync_anchor_stages=[[(2.0, 2.5)]]),  # +0.5 uniform shift
            # Rhythm left at defaults (no shift, tempo 1.0)
        },
    )
    result = make_use_case().run(spec, SongMetadata(title="T", artist="A"), tmp_path / "w")
    by_name = {p.name: p for p in result.packaging.xml_paths}

    def all_times(xml_path: Path) -> list[float]:
        root = ET.parse(xml_path).getroot()
        els = root.findall(".//note") + root.findall(".//chordNote")
        return [float(n.get("time", "0")) for n in els]

    lead_times = all_times(by_name["arrangement_lead.xml"])
    rhythm_times = all_times(by_name["arrangement_rhythm.xml"])
    # Lead's first note started at 2.0 (MIN_LEAD); the single anchor shifts it +0.5.
    assert min(lead_times) == pytest.approx(2.5)
    # Rhythm is untouched: its (whole-note) chord still starts at 2.0.
    assert min(rhythm_times) == pytest.approx(2.0)
    assert any("Lead:" in w and "drift-correction" in w for w in result.warnings)
    assert not any("Rhythm:" in w and "drift-correction" in w for w in result.warnings)


def test_warp_re_trims_sustain_after_a_local_stretch() -> None:
    """A sync correction that locally stretches an excerpt (a chart interval
    mapped to a wider corrected interval) scales each note's warped sustain by
    that same factor — which can re-inflate a sustain apply_sustain_gap already
    trimmed at parse time, fusing the note into the next one on the highway
    ("tall sustain pillars", first fixed pre-warp in 4147d89). _warp_parsed_track
    must re-trim after warping so the gap survives any local stretch."""
    from rockforge.application.gp_pipeline import _build_time_warp, _warp_parsed_track
    from rockforge.domain.music import Beat, TabNote, TempoMap, Tuning
    from rockforge.infrastructure.gpimport.parser import ParsedGpTrack

    # Two notes on the same string 0.5s apart, already gap-trimmed (sustain
    # leaves a small gap before the next attack).
    notes = [
        TabNote(string=0, fret=3, time=1.0, sustain=0.45),
        TabNote(string=0, fret=3, time=1.5, sustain=0.45),
    ]
    track = ParsedGpTrack(
        notes=notes, tuning=Tuning(),
        tempo_map=TempoMap(beats=(Beat(time=0.0, measure=1),), average_bpm=120.0),
        sections=[],
    )
    # A 2-anchor excerpt correction that stretches [1.0, 1.5] to [1.0, 2.5]:
    # a 3x local stretch. Without re-trimming, the first note's warped sustain
    # (0.45 * 3 = 1.35s) would run well past the second note's new time (2.5s).
    warp = _build_time_warp([(1.0, 1.0), (1.5, 2.5)])
    warped = _warp_parsed_track(track, warp)
    first, second = sorted(warped.notes, key=lambda n: n.time)
    assert first.time + first.sustain < second.time


def test_conflicting_sync_anchors_raise_clear_error(
    two_track_gp5: Path, tmp_path: Path
) -> None:
    """Two anchors whose corrected times contradict their chart-time order (a
    later chart point mapped to an earlier recording instant than an earlier
    point) used to fold the beat grid out of order and crash deep inside
    TempoMap with "beats must be in chronological order" — no clue which
    correction caused it. Now it's rejected with an actionable message at the
    point the conflicting round is applied."""
    from rockforge.domain.errors import IngestionError

    spec = GpJobSpec(
        gp_path=two_track_gp5, audio_source="x.wav", lead_track=0,
        sync_anchor_stages=[[(2.5, 4.0), (3.0, 3.5)]],  # later chart time, earlier target
    )
    with pytest.raises(IngestionError, match="sync corrections conflict"):
        make_use_case().run(spec, SongMetadata(title="T", artist="A"), tmp_path / "w")


def test_check_anchor_order_accepts_valid_and_rejects_crossing() -> None:
    from rockforge.application.gp_pipeline import _check_anchor_order
    from rockforge.domain.errors import IngestionError

    _check_anchor_order([(2.0, 2.5), (5.0, 6.0)])  # monotonic — fine
    _check_anchor_order([(2.0, 2.5)])  # single anchor — fine
    _check_anchor_order([])  # no anchors — fine
    with pytest.raises(IngestionError, match="sync corrections conflict"):
        _check_anchor_order([(2.0, 5.0), (3.0, 4.0)])  # later chart time, earlier target


def test_check_anchor_order_rejects_same_chart_time_different_targets() -> None:
    """Two anchors at the IDENTICAL chart time with different targets used to
    slip past validation entirely: the strict `x1 > x0` comparison skipped a
    tied pair, so `_build_time_warp` silently picked whichever matched first."""
    from rockforge.application.gp_pipeline import _check_anchor_order
    from rockforge.domain.errors import IngestionError

    # A duplicate anchor (same x, same y) is harmless — no contradiction.
    _check_anchor_order([(5.0, 5.0), (5.0, 5.0), (10.0, 10.0)])
    with pytest.raises(IngestionError, match="sync corrections conflict"):
        _check_anchor_order([(5.0, 5.0), (5.0, 3.0), (10.0, 10.0)])
    # Order-independent: the same conflict, points given the other way round.
    with pytest.raises(IngestionError, match="sync corrections conflict"):
        _check_anchor_order([(5.0, 3.0), (5.0, 5.0), (10.0, 10.0)])


def test_build_time_warp_leaves_notes_outside_excerpt_untouched() -> None:
    # Two-anchor (excerpt) correction: notes between the anchors are rigidly
    # shifted/stretched, but notes before/after the excerpt must NOT move at
    # all — dragging an excerpt corrects only that excerpt.
    from rockforge.application.gp_pipeline import _build_time_warp

    warp = _build_time_warp([(10.0, 11.0), (12.0, 12.5)])
    assert warp(10.0) == pytest.approx(11.0)
    assert warp(12.0) == pytest.approx(12.5)
    assert warp(11.0) == pytest.approx(11.75)  # midpoint, interpolated
    assert warp(5.0) == pytest.approx(5.0)  # before: untouched
    assert warp(20.0) == pytest.approx(20.0)  # after: untouched


def test_suggest_sync_octave_corrects_detected_tempo() -> None:
    # The beat tracker reported half the real tempo (60 vs ~120); the suggestion
    # must pick the octave nearest the GP tempo so tempo_scale stays near 1.
    from rockforge.application.gp_pipeline import suggest_sync

    scale, offset = suggest_sync(gp_bpm=120.0, detected_bpm=60.0, first_onset_s=1.4)
    assert scale == pytest.approx(1.0)  # 120 / (60 * 2)
    assert offset == pytest.approx(1.4)


def test_suggest_tempo_scale_octave_corrects() -> None:
    # The shared octave-correction helper (used by the per-point re-tempo tool):
    # 120 vs a detected 240 → pick the half-tempo octave so the scale stays ~1.
    from rockforge.application.gp_pipeline import suggest_tempo_scale

    assert suggest_tempo_scale(120.0, 240.0) == pytest.approx(1.0)  # 120 / (240 * 0.5)
    assert suggest_tempo_scale(120.0, 100.0) == pytest.approx(1.2)


def test_suggest_tempo_scale_triplet_grid_does_not_jump_bpm() -> None:
    # The reported "auto-sync jumps the BPM ~50%" bug: a beat tracker on a
    # triplet/compound feel reports 1.5× the true pulse. With only ½/1/2 octaves
    # the nearest candidate gave tempo_scale ~1.33/1.5; the triplet grid (2/3,
    # 3/2) must snap it back to ~1 instead.
    from rockforge.application.gp_pipeline import suggest_tempo_scale

    assert suggest_tempo_scale(120.0, 180.0) == pytest.approx(1.0)  # 120 / (180 * 2/3)
    assert suggest_tempo_scale(120.0, 80.0) == pytest.approx(1.0)   # 120 / (80 * 3/2)
    # A small, genuine tempo difference is still preserved (not over-snapped).
    assert suggest_tempo_scale(120.0, 126.0) == pytest.approx(120.0 / 126.0)


def test_suggest_sync_scales_to_recording_tempo() -> None:
    # Recording is genuinely slower than the GP file (100 vs 90): stretch the
    # chart (tempo_scale > 1) so its effective BPM matches the recording.
    from rockforge.application.gp_pipeline import suggest_sync

    scale, offset = suggest_sync(gp_bpm=100.0, detected_bpm=90.0, first_onset_s=-0.5)
    assert scale == pytest.approx(100.0 / 90.0)
    assert offset == 0.0  # negative onset clamped


def test_suggest_sync_rejects_nonpositive_bpm() -> None:
    from rockforge.application.gp_pipeline import suggest_sync
    from rockforge.domain.errors import IngestionError

    with pytest.raises(IngestionError):
        suggest_sync(gp_bpm=0.0, detected_bpm=120.0, first_onset_s=0.0)


def test_build_time_warp_single_anchor_shifts_everything() -> None:
    # A single anchor remains a uniform shift applied everywhere (e.g. "the
    # whole song's lead-in is off by X"), unlike the two-anchor excerpt case.
    from rockforge.application.gp_pipeline import _build_time_warp

    warp = _build_time_warp([(10.0, 11.0)])
    assert warp(5.0) == pytest.approx(6.0)
    assert warp(10.0) == pytest.approx(11.0)
    assert warp(20.0) == pytest.approx(21.0)


def test_gp_pipeline_sync_anchor_stages_compose(two_track_gp5: Path, tmp_path: Path) -> None:
    # Two successive correction rounds (as would happen across separate
    # sessions) must compose: round 1 shifts everything by +0.5s, round 2
    # (applied to that already-shifted timeline) shifts by another +0.5s.
    spec = GpJobSpec(
        gp_path=two_track_gp5, audio_source="x.wav", lead_track=0,
        sync_anchor_stages=[[(2.5, 3.0)], [(3.0, 3.5)]],
    )
    result = make_use_case().run(spec, SongMetadata(title="T", artist="A"), tmp_path / "w")
    assert any("2 manual drift-correction point(s) across 2 round(s)" in w for w in result.warnings)

    lead_xml = next(p for p in result.packaging.xml_paths if p.name == "arrangement_combined.xml")
    times = [float(n.get("time", "0")) for n in ET.parse(lead_xml).getroot().findall(".//note")]
    assert times == pytest.approx([3.0, 3.5, 4.0])


def test_gp_pipeline_strips_mute_techniques_when_disabled(
    palm_muted_gp5: Path, tmp_path: Path
) -> None:
    spec = GpJobSpec(
        gp_path=palm_muted_gp5, audio_source="x.wav", lead_track=0,
        import_mute_techniques=False,
    )
    result = make_use_case().run(spec, SongMetadata(title="T", artist="A"), tmp_path / "w")
    assert any("palm mute" in w and "removed" in w for w in result.warnings)
    lead_xml = next(p for p in result.packaging.xml_paths if p.name == "arrangement_combined.xml")
    notes = ET.parse(lead_xml).getroot().findall(".//note")
    # stripped notes carry no palmMute flag at all (default-valued attributes
    # are omitted, matching Editor on Fire's minimal note output)
    assert notes and all(n.get("palmMute") is None for n in notes)


def test_gp_pipeline_keeps_mute_techniques_by_default(
    palm_muted_gp5: Path, tmp_path: Path
) -> None:
    spec = GpJobSpec(gp_path=palm_muted_gp5, audio_source="x.wav", lead_track=0)
    result = make_use_case().run(spec, SongMetadata(title="T", artist="A"), tmp_path / "w")
    lead_xml = next(p for p in result.packaging.xml_paths if p.name == "arrangement_combined.xml")
    notes = ET.parse(lead_xml).getroot().findall(".//note")
    assert any(n.get("palmMute") == "1" for n in notes)


def test_gp_lyrics_events_precedence(two_track_gp5: Path, tmp_path: Path) -> None:
    from rockforge.infrastructure.rsxml.vocals import VocalEvent

    spec = GpJobSpec(
        gp_path=two_track_gp5, audio_source="x.wav", lead_track=0,
        lrc_text="[00:01.00]old\n",
        lyrics_events=[VocalEvent(time=1.0, length=0.5, lyric="new+")],
    )
    result = make_use_case().run(spec, SongMetadata(title="T", artist="A"), tmp_path / "w")
    vocals_xml = next(p for p in result.packaging.xml_paths if p.name == "arrangement_vocals.xml")
    root = ET.parse(vocals_xml).getroot()
    vocal = root.find("vocal")
    assert vocal is not None
    assert vocal.get("lyric") == "new+"
    # offset_s=0 -> pad_start_s=2.0; edited time (1.0) shifts to 3.0.
    assert float(vocal.get("time", "0")) == pytest.approx(3.0)
    assert any("in-app editor" in w for w in result.warnings)


def test_gp_pipeline_zero_offset_warns(two_track_gp5: Path, tmp_path: Path) -> None:
    spec = GpJobSpec(gp_path=two_track_gp5, audio_source="x.wav", lead_track=0)
    result = make_use_case().run(spec, SongMetadata(title="T", artist="A"), tmp_path / "w")
    # offset 0 => silence prepended up to the minimum lead-in (avoids the
    # DLC Builder "no room for an empty phrase" crash at content time 0)
    assert any("minimum" in w and "lead-in" in w and "2.00s" in w for w in result.warnings)
    assert result.note_counts == {"Combined": 3}  # single track => combined arrangement


# --- Dynamic sync (align_chart_to_recording) -----------------------------------
# The aligner walks the chart's note onsets from the user's pinned first note,
# snapping each to the nearest recording attack; the tempo ratio it carries
# forward is derived from those correspondences (start 1.0 = the authored tempo
# the pin confirmed), NOT from integrating the beat tracker's biased tempo. The
# detected beat grid is only a tempo prior for note-sparse passages. Each anchor
# reports a per-anchor confidence (how well the tab matches the audio there).

def _steady(interval: float, n: int, start: float = 0.0) -> list[float]:
    return [start + i * interval for i in range(n)]


def test_align_chart_pin_is_the_first_anchor_verbatim() -> None:
    from rockforge.application.gp_pipeline import align_chart_to_recording

    gp = _steady(0.5, 80)                      # 120 BPM chart
    rec = _steady(0.5, 80, start=4.2)          # same tempo, song starts at 4.2s
    onsets = gp
    rec_on = [t + 4.2 for t in gp]
    out = align_chart_to_recording(gp, rec, onsets, rec_on, chart_start=0.0, rec_start=4.2)
    assert out[0] == (0.0, 4.2, 1.0)
    # Same tempo → offset stays ~4.2 the whole way, monotonic, confident.
    for c, r, conf in out[1:]:
        assert r - c == pytest.approx(4.2, abs=0.06)
        assert conf >= 0.9
    assert all(out[i][1] < out[i + 1][1] for i in range(len(out) - 1))


def test_align_chart_follows_a_mid_song_tempo_change() -> None:
    """The whole point: the recording speeds up halfway; the anchors must track
    the curve (later chart beats land progressively earlier), not one average."""
    from rockforge.application.gp_pipeline import align_chart_to_recording

    gp = _steady(0.5, 120)
    rec, t = [], 2.0
    for i in range(120):
        rec.append(t)
        t += 0.5 if i < 60 else 0.4            # speeds up at beat 60 (chart 30s)
    onsets = gp
    rec_on = list(rec)                         # attacks exactly on the real beats
    out = align_chart_to_recording(gp, rec, onsets, rec_on, chart_start=0.0, rec_start=2.0)
    def at(chart_t: float) -> float:
        return next(r for c, r, _ in out if abs(c - chart_t) < 0.26)
    assert at(25.0) == pytest.approx(27.0, abs=0.15)   # before the change: +2.0
    # After the change the recording runs 0.4s/beat: chart 50s = beat 100 =
    # rec 2 + 60*0.5 + 40*0.4 = 48.0 — well before chart_t + 2.
    assert at(50.0) == pytest.approx(48.0, abs=0.3)


def test_align_chart_survives_missed_tracker_beats() -> None:
    """A beat MISSING from the detected grid must not slip the mapping (the old
    1:1 index method slipped one beat per miss, accumulating a multi-second
    rush). The interval median skips the gap and the onsets re-phase it."""
    from rockforge.application.gp_pipeline import align_chart_to_recording

    gp = _steady(0.5, 100)
    full = _steady(0.5, 100, start=1.0)
    rec = full[:40] + full[42:]                # tracker missed two beats mid-song
    onsets = gp
    rec_on = [t + 1.0 for t in gp]             # the MUSIC itself is intact
    out = align_chart_to_recording(gp, rec, onsets, rec_on, chart_start=0.0, rec_start=1.0)
    # End-of-song anchors still sit at +1.0 (no cumulative slip).
    c, r, conf = out[-1]
    assert r - c == pytest.approx(1.0, abs=0.08)
    assert conf >= 0.9


def test_align_chart_flags_a_mismatched_tab_section_with_low_confidence() -> None:
    """Where the tab's notes simply don't exist in the audio, no warp is right —
    the anchor keeps the integrated tempo position but reports low confidence so
    the UI can flag the span for the user to fix in Guitar Pro."""
    from rockforge.application.gp_pipeline import align_chart_to_recording

    gp = _steady(0.5, 100)
    rec = _steady(0.5, 100, start=2.0)
    onsets = [t for t in gp]
    # The audio has NO attacks where the tab claims notes in chart 20-32s (the
    # tab wrote a riff over what is actually a breakdown/different content).
    rec_on = sorted(t + 2.0 for t in gp if not (20.0 <= t < 32.0))
    out = align_chart_to_recording(gp, rec, onsets, rec_on, chart_start=0.0, rec_start=2.0)
    mid = [conf for c, _, conf in out if 24.0 <= c <= 28.0]
    good = [conf for c, _, conf in out if c >= 38.0]
    assert mid and max(mid) < 0.5              # mismatch flagged
    assert good and min(good) >= 0.8           # healthy sections stay confident


def test_align_chart_degenerate_inputs_return_no_anchors() -> None:
    from rockforge.application.gp_pipeline import align_chart_to_recording

    assert align_chart_to_recording([], [1, 2], [], [], chart_start=0, rec_start=0) == []
    assert align_chart_to_recording([1, 2], [], [], [], chart_start=0, rec_start=0) == []


# --- MIDI-driven sync (align_chart_to_midi) ------------------------------------
# A MIDI tempo map (e.g. exported from RIPX) gives the recording's real time for
# each measure downbeat — ground truth, not an estimate. align_chart_to_midi
# pins the chart's first measure to the recording and places every later bar at
# the MIDI's own measure time (one anchor per bar = "BPM por compasso").


def test_align_to_midi_pins_then_follows_the_midi_measures() -> None:
    from rockforge.application.gp_pipeline import align_chart_to_midi

    gp_bars = [0.0, 2.0, 4.0, 6.0, 8.0]           # chart measure downbeats
    midi = [10.0, 12.0, 14.5, 17.0]               # recording times (2.0, 2.5, 2.5s bars)
    out = align_chart_to_midi(gp_bars, midi, chart_start=0.0, rec_start=10.0)
    assert out[0] == (0.0, 10.0, 1.0)             # the pin, verbatim
    # Each later bar sits at rec_start + the MIDI measure's elapsed time.
    assert out == [
        (0.0, 10.0, 1.0),
        (2.0, 12.0, 1.0),
        (4.0, 14.5, 1.0),
        (6.0, 17.0, 1.0),
    ]


def test_align_to_midi_respects_a_mid_song_pin() -> None:
    """Pinning a bar mid-song maps THAT bar to the MIDI's first measure and the
    following bars to the subsequent MIDI measures (relative offset)."""
    from rockforge.application.gp_pipeline import align_chart_to_midi

    gp_bars = [0.0, 2.0, 4.0, 6.0, 8.0]
    midi = [10.0, 12.0, 14.5, 17.0]
    out = align_chart_to_midi(gp_bars, midi, chart_start=4.0, rec_start=20.0)
    assert out[0] == (4.0, 20.0, 1.0)
    assert out[1] == (6.0, 22.0, 1.0)             # +2.0s (MIDI measure 0→1)
    assert out[2] == (8.0, 24.5, 1.0)             # +4.5s (MIDI measure 0→2)


def test_align_to_midi_degenerate_inputs_return_no_anchors() -> None:
    from rockforge.application.gp_pipeline import align_chart_to_midi

    assert align_chart_to_midi([], [1.0, 2.0], chart_start=0, rec_start=0) == []
    assert align_chart_to_midi([0.0, 2.0], [1.0], chart_start=0, rec_start=0) == []
