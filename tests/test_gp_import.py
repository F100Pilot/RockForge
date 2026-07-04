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


def test_tied_note_extends_previous_not_new_attack(tmp_path: Path) -> None:
    """A GP5 tie note continues the previous note on the same string (held) —
    it must not become a separate attack (the '4 notes shown as 5' bug)."""
    song = gp.Song()
    song.title, song.artist, song.tempo = "Tie", "B", 120
    v = song.tracks[0].measures[0].voices[0]
    _add_beat(v, 4, [(5, 7)])  # quarter on A string, fret 7
    tied = gp.Beat(v)
    tied.status = gp.BeatStatus.normal
    tied.duration = gp.Duration(value=4)
    n = gp.Note(tied)
    n.string, n.value, n.type = 5, 7, gp.NoteType.tie  # held continuation
    tied.notes.append(n)
    v.beats.append(tied)
    path = tmp_path / "tie.gp5"
    gp.write(song, str(path))

    parsed = parse_gp_track(path, 0)
    assert len(parsed.notes) == 1  # the tie folded into the first note
    assert parsed.notes[0].fret == 7
    assert parsed.notes[0].sustain == pytest.approx(1.0)  # two quarters held


def test_tempo_change_on_other_track_is_detected(tmp_path: Path) -> None:
    """A mid-song tempo change is GLOBAL but GP5 stores it on ONE track's beat —
    often not the instrument we parse. It must still reach the beat grid, or the
    grid stays stuck at the initial tempo (the '186 still shows 93' bug)."""
    song = gp.Song()
    song.title, song.artist, song.tempo = "Tempo", "B", 93
    rhythm = gp.Track(song)
    rhythm.name, rhythm.number = "Rhythm", 2
    song.tracks.append(rhythm)
    for _ in range(3):  # 4 measures total
        song.newMeasure()
    for tr in song.tracks:
        for mi, measure in enumerate(tr.measures):
            beat = gp.Beat(measure.voices[0])
            beat.status = gp.BeatStatus.normal
            beat.duration = gp.Duration(value=1)  # whole note
            if mi == 2 and tr is rhythm:  # tempo change authored on the OTHER track
                beat.effect.mixTableChange = gp.MixTableChange(tempo=gp.MixTableItem(value=186))
            note = gp.Note(beat)
            note.string, note.value, note.type = 1, 5, gp.NoteType.normal
            beat.notes.append(note)
            measure.voices[0].beats.append(beat)
    path = tmp_path / "tempo.gp5"
    gp.write(song, str(path))

    # Parse the LEAD track (0); the tempo change lives on the Rhythm track (1).
    beats = [b.time for b in parse_gp_track(path, 0).tempo_map.beats]
    intervals = [round(beats[i + 1] - beats[i], 3) for i in range(len(beats) - 1)]
    # 93 BPM whole-note beat ≈ 0.645s; after the change 186 BPM ≈ 0.323s.
    assert intervals[0] == pytest.approx(0.645, abs=0.01)
    assert intervals[-1] == pytest.approx(0.323, abs=0.01)
