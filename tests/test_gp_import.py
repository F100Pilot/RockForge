"""GP import tests against real GP5 files built with pyguitarpro itself."""

from __future__ import annotations

from pathlib import Path

import guitarpro as gp
import pytest

from rockforge.domain.errors import IngestionError
from rockforge.domain.music import Technique
from rockforge.infrastructure.gpimport.parser import inspect_gp, parse_gp_track


def _add_beat(voice, duration_value: int, notes: list[tuple[int, int]], **effects):  # noqa: ANN001
    beat = gp.Beat(voice)
    beat.status = gp.BeatStatus.normal
    beat.duration = gp.Duration(value=duration_value)
    for string, fret in notes:
        note = gp.Note(beat)
        note.string, note.value, note.type = string, fret, gp.NoteType.normal
        for key, val in effects.items():
            setattr(note.effect, key, val)
        beat.notes.append(note)
    voice.beats.append(beat)
    return beat


@pytest.fixture()
def gp5_file(tmp_path: Path) -> Path:
    song = gp.Song()
    song.title, song.artist, song.album, song.tempo = "GP Song", "GP Band", "GP Album", 120
    track = song.tracks[0]
    track.name = "Lead Guitar"

    m1 = track.measures[0]
    m1.header.marker = gp.Marker(title="Intro")
    v = m1.voices[0]
    # quarter low-E open (GP string 6 = lowest), quarter A-string fret 2 w/ hammer flag,
    # then destination note fret 4, then E-major-ish chord
    _add_beat(v, 4, [(6, 0)])
    _add_beat(v, 4, [(5, 2)], hammer=True)
    _add_beat(v, 4, [(5, 4)])
    _add_beat(v, 4, [(6, 0), (5, 2), (4, 2)])

    # second measure: bend (full = 2 half-semitone points => 1.0 st? value 4 = 2 st)
    header2 = gp.MeasureHeader()
    header2.number = 2
    header2.start = m1.start + m1.length
    song.measureHeaders.append(header2)
    m2 = gp.Measure(track, header2)
    track.measures.append(m2)
    v2 = m2.voices[0]
    bend = gp.BendEffect(
        type=gp.BendType.bend,
        value=4,
        points=[gp.BendPoint(0, 0), gp.BendPoint(6, 4)],
    )
    _add_beat(v2, 4, [(3, 7)], bend=bend)
    _add_beat(v2, 4, [(3, 5)], palmMute=True)

    song.lyrics.lines[0].startingMeasure = 2
    song.lyrics.lines[0].lyrics = "hello world"

    path = tmp_path / "song.gp5"
    gp.write(song, str(path))
    return path


def test_inspect_reads_metadata_and_tracks(gp5_file: Path) -> None:
    info = inspect_gp(gp5_file)
    assert info.title == "GP Song"
    assert info.artist == "GP Band"
    assert info.tempo == 120
    assert info.has_lyrics
    t = info.tracks[0]
    assert t.name == "Lead Guitar"
    assert t.string_count == 6
    assert t.tuning_midi == (40, 45, 50, 55, 59, 64)  # low to high


def test_parse_maps_strings_times_and_chords(gp5_file: Path) -> None:
    parsed = parse_gp_track(gp5_file, 0)
    # 4 single/chord beats in m1 (3 + 3-note chord) + 2 in m2 = 8 notes
    assert len(parsed.notes) == 8
    first = parsed.notes[0]
    assert (first.string, first.fret) == (0, 0)  # GP string 6 -> our string 0 (low E)
    assert first.time == 0.0
    assert first.sustain == pytest.approx(0.5)  # quarter at 120 BPM
    # chord at beat 4 of measure 1 => t = 1.5s, three notes share the onset
    chord_notes = [n for n in parsed.notes if n.time == pytest.approx(1.5)]
    assert len(chord_notes) == 3
    assert {n.string for n in chord_notes} == {0, 1, 2}


def test_parse_techniques(gp5_file: Path) -> None:
    parsed = parse_gp_track(gp5_file, 0)
    # hammer flag on origin (t=0.5) must tag the DESTINATION note (t=1.0)
    dest = next(n for n in parsed.notes if n.time == pytest.approx(1.0))
    assert Technique.HAMMER_ON in dest.techniques
    bend_note = next(n for n in parsed.notes if n.time == pytest.approx(2.0))
    assert Technique.BEND in bend_note.techniques
    assert bend_note.bend_semitones == pytest.approx(2.0)  # GP point value 4 = 2 semitones
    pm = next(n for n in parsed.notes if n.time == pytest.approx(2.5))
    assert Technique.PALM_MUTE in pm.techniques


def test_parse_sections_lyrics_and_offset(gp5_file: Path) -> None:
    parsed = parse_gp_track(gp5_file, 0, offset_s=1.25)
    assert parsed.sections[0].name == "Intro"
    assert parsed.sections[0].start_time == pytest.approx(1.25)
    assert parsed.notes[0].time == pytest.approx(1.25)
    assert parsed.lyrics[0].text == "hello world"
    assert parsed.lyrics[0].time == pytest.approx(2.0 + 1.25)  # measure 2 start + offset


def test_tempo_scale_stretches_timeline_and_scales_bpm(gp5_file: Path) -> None:
    # tempo_scale=2.0 stretches the musical timeline to twice its length
    # (around the start), so measure 2 lands at 4.0s instead of 2.0s, and the
    # effective average tempo halves. offset_s is applied after the scale.
    base = parse_gp_track(gp5_file, 0)
    stretched = parse_gp_track(gp5_file, 0, offset_s=1.0, tempo_scale=2.0)
    assert base.notes[0].time == pytest.approx(0.0)
    assert stretched.notes[0].time == pytest.approx(1.0)  # only the lead-in
    base_m2 = next(b.time for b in base.tempo_map.beats if b.measure == 2)
    scaled_m2 = next(b.time for b in stretched.tempo_map.beats if b.measure == 2)
    assert scaled_m2 - 1.0 == pytest.approx((base_m2) * 2.0)
    assert stretched.tempo_map.average_bpm == pytest.approx(60.0)


def test_tempo_scale_must_be_positive(gp5_file: Path) -> None:
    from rockforge.domain.errors import IngestionError

    with pytest.raises(IngestionError, match="tempo_scale must be positive"):
        parse_gp_track(gp5_file, 0, tempo_scale=0.0)


def test_tempo_map_has_measure_numbers(gp5_file: Path) -> None:
    parsed = parse_gp_track(gp5_file, 0)
    downbeats = [b for b in parsed.tempo_map.beats if b.measure != -1]
    assert [b.measure for b in downbeats] == [1, 2]
    assert downbeats[1].time == pytest.approx(2.0)
    assert parsed.tempo_map.average_bpm == 120.0


def test_gpx_rejected_with_clear_message(tmp_path: Path) -> None:
    fake = tmp_path / "song.gpx"
    fake.write_bytes(b"BCFS")
    with pytest.raises(IngestionError, match="GP5"):
        inspect_gp(fake)


def test_track_index_out_of_range(gp5_file: Path) -> None:
    with pytest.raises(IngestionError, match="out of range"):
        parse_gp_track(gp5_file, 7)
