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
    # Two bars, then the closing bar line where bar 2 ends (close_beat_grid).
    assert [b.measure for b in downbeats] == [1, 2, 3]
    assert downbeats[1].time == pytest.approx(2.0)
    assert downbeats[2].time == pytest.approx(4.0)
    assert parsed.tempo_map.average_bpm == 120.0


def test_gpx_rejected_with_clear_message(tmp_path: Path) -> None:
    fake = tmp_path / "song.gpx"
    fake.write_bytes(b"BCFS")
    with pytest.raises(IngestionError, match="GP5"):
        inspect_gp(fake)


def test_track_index_out_of_range(gp5_file: Path) -> None:
    with pytest.raises(IngestionError, match="out of range"):
        parse_gp_track(gp5_file, 7)


def test_dropped_out_of_range_note_does_not_desync_subsequent_timing(
    tmp_path: Path,
) -> None:
    """A beat with an out-of-range note must still advance the tick by exactly
    one beat duration, not two — regression for a bug where dropping the note
    advanced `tick` once inside the drop branch AND once more after the note
    loop, pushing every later note in the measure one full beat late."""
    song = gp.Song()
    song.title, song.artist, song.tempo = "T", "A", 120
    track = song.tracks[0]
    v = track.measures[0].voices[0]
    _add_beat(v, 4, [(6, 30)])  # fret 30 is off the 24-fret neck -> dropped
    _add_beat(v, 4, [(6, 5)])  # must land at t=0.5s (quarter note @ 120bpm)
    _add_beat(v, 4, [(6, 7)])  # must land at t=1.0s

    path = tmp_path / "song.gp5"
    gp.write(song, str(path))

    tab = parse_gp_track(path, 0)
    assert any("dropped" in w for w in tab.warnings)
    times = sorted(n.time for n in tab.notes)
    assert times == [pytest.approx(0.5), pytest.approx(1.0)]


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


def _add_tie(voice, duration_value: int, string: int, **effects):  # noqa: ANN001
    beat = gp.Beat(voice)
    beat.status = gp.BeatStatus.normal
    beat.duration = gp.Duration(value=duration_value)
    note = gp.Note(beat)
    note.string, note.value, note.type = string, 0, gp.NoteType.tie
    for key, val in effects.items():
        setattr(note.effect, key, val)
    beat.notes.append(note)
    voice.beats.append(beat)


def test_bend_and_pull_off_on_a_tied_note_are_kept(tmp_path: Path) -> None:
    """Held, then bent ½ and released on the TIED note, then pulled off (Daughtry
    'September', bar 4 — as alphaTab and Guitar Pro draw it). Folding the tie into
    the held note must keep the bend (re-timed onto the whole note) and the pull-off,
    not drop them with the tie."""
    song = gp.Song()
    song.title, song.artist, song.tempo = "Tie bend", "B", 120
    v = song.tracks[0].measures[0].voices[0]
    _add_beat(v, 4, [(3, 3)])  # quarter, G string fret 3 (0.5 s)
    release = gp.BendEffect(
        type=gp.BendType.bendRelease,
        value=50,
        points=[gp.BendPoint(0, 0), gp.BendPoint(3, 2), gp.BendPoint(6, 2),
                gp.BendPoint(9, 0), gp.BendPoint(12, 0)],
    )
    _add_tie(v, 4, 3, bend=release)  # tied quarter: bend ½ and release
    _add_tie(v, 8, 3, hammer=True)  # tied eighth, pull-off to the next note
    _add_beat(v, 8, [(3, 1)])
    path = tmp_path / "tie_bend.gp5"
    gp.write(song, str(path))

    held, pulled = parse_gp_track(path, 0).notes
    assert (held.fret, pulled.fret) == (3, 1)
    assert Technique.BEND in held.techniques and held.bend_semitones == pytest.approx(1.0)
    # the bend is on the second quarter (0.5..1.0 s into the held note): flat until
    # 0.5 s, up by 0.625 s, held to 0.75 s, back by 0.875 s — at those moments even
    # after the sustain is trimmed before the next note
    curve = [(round(p.position * held.sustain, 3), p.step) for p in held.bend_points]
    assert curve == [(0.0, 0.0), (0.5, 0.0), (0.625, 1.0), (0.75, 1.0), (0.875, 0.0), (1.0, 0.0)]
    assert Technique.PULL_OFF in pulled.techniques


def test_a_pre_bend_is_bent_from_the_attack(tmp_path: Path) -> None:
    """A pre-bend held at one value keeps its curve: bent from the attack, as
    alphaTab plays it, not a rise across the note."""
    song = gp.Song()
    song.title, song.artist, song.tempo = "Pre-bend", "B", 120
    pre = gp.BendEffect(
        type=gp.BendType.prebend, value=50, points=[gp.BendPoint(0, 2), gp.BendPoint(12, 2)]
    )
    _add_beat(song.tracks[0].measures[0].voices[0], 4, [(3, 7)], bend=pre)
    path = tmp_path / "pre_bend.gp5"
    gp.write(song, str(path))

    (note,) = parse_gp_track(path, 0).notes
    assert note.bend_semitones == pytest.approx(1.0)
    assert [(p.position, p.step) for p in note.bend_points] == [(0.0, 1.0), (1.0, 1.0)]


def test_a_tie_after_a_bend_holds_it(tmp_path: Path) -> None:
    """A bent note tied on without a bend of its own stays bent (the tie keeps the
    pitch): the rise sits in the first half, then holds. The rise is alphaTab's:
    "up by the middle of the note, then held" (three points) is a straight rise
    across the whole bent note."""
    song = gp.Song()
    song.title, song.artist, song.tempo = "Tie hold", "B", 120
    v = song.tracks[0].measures[0].voices[0]
    rise = gp.BendEffect(
        type=gp.BendType.bend,
        value=100,
        points=[gp.BendPoint(0, 0), gp.BendPoint(6, 4), gp.BendPoint(12, 4)],
    )
    _add_beat(v, 4, [(2, 8)], bend=rise)
    _add_tie(v, 4, 2)
    path = tmp_path / "tie_hold.gp5"
    gp.write(song, str(path))

    (note,) = parse_gp_track(path, 0).notes
    curve = [(round(p.position, 2), p.step) for p in note.bend_points]
    assert curve == [(0.0, 0.0), (0.5, 2.0), (1.0, 2.0)]
    assert note.bend_semitones == pytest.approx(2.0)


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


def test_a_mid_song_tempo_change_takes_effect_on_its_own_beat(tmp_path: Path) -> None:
    """A tempo change must apply from the beat it sits on, not a quarter later.

    _tempo_events keys each change at ``measure.start``, which is ABSOLUTE (bar 1
    begins at tick 960), while notes and beats are looked up at ``tick - origin``
    with origin = 960. Mixing the two applied every mid-song tempo change one
    quarter note late, so a song drifted by the difference between one beat at
    the old tempo and one at the new — at EVERY change, cumulatively. That is
    invisible in a constant-tempo file, which is why it survived this long.
    """
    song = gp.Song()
    song.title, song.artist, song.tempo = "T", "A", 120
    track = song.tracks[0]
    for m in range(4):
        if m == 0:
            measure = track.measures[0]
        else:
            header = gp.MeasureHeader()
            header.number = m + 1
            header.start = track.measures[-1].start + track.measures[-1].length
            song.measureHeaders.append(header)
            measure = gp.Measure(track, header)
            track.measures.append(measure)
        voice = measure.voices[0]
        for k in range(4):
            beat = _add_beat(voice, 4, [(6, 0)])
            if m == 2 and k == 0:  # halve the tempo from bar 3
                mtc = gp.MixTableChange()
                mtc.wah = gp.WahEffect.none
                mtc.hideTempo = False
                mtc.tempo = gp.MixTableItem(value=60, duration=0, allTracks=False)
                beat.effect.mixTableChange = mtc
    path = tmp_path / "tempo.gp5"
    with open(path, "wb") as fh:
        gp.write(song, fh, version=(5, 1, 0))

    parsed = parse_gp_track(path, 0)
    downbeats = {b.measure: b.time for b in parsed.tempo_map.beats if b.measure > 0}
    # Bars 1-2 at 120 BPM: 4 quarters x 0.5 s each.
    assert downbeats[2] == pytest.approx(2.0, abs=1e-3)
    assert downbeats[3] == pytest.approx(4.0, abs=1e-3)
    # Bar 3 runs entirely at 60 BPM (1.0 s per quarter), so bar 4 starts 4 s later.
    # The bug made this 7.5 s: the first beat of bar 3 was still timed at 120.
    assert downbeats[4] == pytest.approx(8.0, abs=1e-3), (
        "the tempo change must apply from its own beat, not one quarter later"
    )


def test_gp5_bar_times_retime_the_chart_relative_to_bar_one(gp5_file: Path) -> None:
    """Songsterr's human-marked per-measure timestamps re-time a GP5 file the
    same way Guitar Pro 8's sync points re-time a .gp: bar N starts where the
    times say, relative to bar 1, so offset_s still means "where bar 1 is".

    The file is 120 BPM (2 s a bar); the times say bar 1 really lasts 3 s.
    """
    plain = parse_gp_track(gp5_file, 0)
    assert [round(n.time, 3) for n in plain.notes][:1] == [0.0]
    assert not any("bar times" in w for w in plain.warnings)

    timed = parse_gp_track(gp5_file, 0, offset_s=1.0, bar_times=[10.0, 13.0])
    onsets = sorted({round(n.time, 3) for n in timed.notes})
    # Bar 1's four quarters now span 3 s; bar 2 starts at 1.0 + 3.0.
    assert onsets[:4] == [1.0, 1.75, 2.5, 3.25]
    assert onsets[4] == 4.0
    downbeats = [b.time for b in timed.tempo_map.beats if b.measure > 0]
    assert downbeats[:2] == pytest.approx([1.0, 4.0])
    assert any("bar times" in w for w in timed.warnings)
    # What plays, not the header: 8 quarters over 3 s + 3 s = 80 BPM.
    assert timed.tempo_map.average_bpm == pytest.approx(80.0)


def test_gp5_bar_times_that_do_not_match_the_file_are_reported(gp5_file: Path) -> None:
    """Times marked on a different version of the tab do not line up bar for
    bar; that has to be said, not silently applied."""
    timed = parse_gp_track(gp5_file, 0, bar_times=[0.0, 2.0, 4.0, 6.0])
    assert any("do not match the file's bar count (4 vs 2)" in w for w in timed.warnings)


def test_an_overfull_last_bar_still_ends_inside_the_grid() -> None:
    """A converter can write a last bar holding more than its time signature;
    the grid keeps its spacing past the bar line until it covers the last note."""
    from rockforge.domain.music import Beat
    from rockforge.infrastructure.gpimport.parser import close_beat_grid

    beats = [Beat(0.0, 1), Beat(0.5, -1), Beat(1.0, -1), Beat(1.5, -1)]
    close_beat_grid(beats, bar_end=2.0, last_note=2.7)
    assert [(b.time, b.measure) for b in beats[4:]] == [(2.0, 2), (2.5, -1), (3.0, -1)]


def test_harmonic_types_map_like_the_gpif_path(tmp_path: Path) -> None:
    """PyGuitarPro harmonic types: artificial (2) and pinch (4) are the pinch
    glyph, natural (1) and tapped (3) the plain harmonic — as for .gp files."""
    song = gp.Song()
    song.title, song.artist, song.tempo = "Harmonics", "B", 120
    v = song.tracks[0].measures[0].voices[0]
    kinds = (gp.NaturalHarmonic(), gp.ArtificialHarmonic(), gp.TappedHarmonic(fret=17),
             gp.PinchHarmonic())
    for kind in kinds:
        _add_beat(v, 4, [(3, 5)], harmonic=kind)
    path = tmp_path / "harm.gp5"
    gp.write(song, str(path))
    got = [
        Technique.PINCH_HARMONIC in n.techniques
        for n in sorted(parse_gp_track(path, 0).notes, key=lambda n: n.time)
    ]
    assert got == [False, True, False, True]


def test_a_brush_stroke_gives_the_pick_direction(tmp_path: Path) -> None:
    """A strum / arpeggio arrow (GP5 beat stroke) is the chord's direction, as the
    GPIF path reads <Brush>: down → 1, up → 2."""
    song = gp.Song()
    song.title, song.artist, song.tempo = "Strum", "B", 120
    v = song.tracks[0].measures[0].voices[0]
    for direction in (gp.BeatStrokeDirection.down, gp.BeatStrokeDirection.up):
        beat = _add_beat(v, 2, [(6, 0), (5, 2), (4, 2)])
        beat.effect.stroke = gp.BeatStroke(direction, gp.Duration.thirtySecond)
    path = tmp_path / "strum.gp5"
    gp.write(song, str(path))
    notes = parse_gp_track(path, 0).notes
    assert {n.pick_direction for n in notes if n.time < 0.5} == {1}
    assert {n.pick_direction for n in notes if n.time >= 0.5} == {2}


def test_vibrato_on_a_tied_note_is_kept(tmp_path: Path) -> None:
    song = gp.Song()
    song.title, song.artist, song.tempo = "Tie vibrato", "B", 120
    v = song.tracks[0].measures[0].voices[0]
    _add_beat(v, 4, [(2, 10)])
    _add_tie(v, 2, 2, vibrato=True)  # held, vibrato on the tied part
    path = tmp_path / "tie_vib.gp5"
    gp.write(song, str(path))
    (note,) = parse_gp_track(path, 0).notes
    assert Technique.VIBRATO in note.techniques
    assert note.sustain == pytest.approx(1.5)


@pytest.mark.parametrize(
    ("on_beat", "grace_at", "main_at"), [(False, 0.4375, 0.5), (True, 0.5, 0.5625)]
)
def test_grace_notes_are_short_notes_of_their_own(
    tmp_path: Path, on_beat: bool, grace_at: float, main_at: float
) -> None:
    """A GP5 grace note (a 32nd, hammered into the note) becomes its own note, as
    alphaTab plays it: before the beat, or on it (delaying the main note)."""
    song = gp.Song()
    song.title, song.artist, song.tempo = "Grace", "B", 120
    v = song.tracks[0].measures[0].voices[0]
    _add_beat(v, 4, [(6, 3)])
    grace = gp.GraceEffect(fret=5, duration=32, isOnBeat=on_beat,
                           transition=gp.GraceEffectTransition.hammer)
    _add_beat(v, 4, [(3, 7)], grace=grace)
    path = tmp_path / "grace.gp5"
    gp.write(song, str(path))
    notes = {n.fret: n for n in parse_gp_track(path, 0).notes}
    assert notes[5].time == pytest.approx(grace_at)
    assert notes[7].time == pytest.approx(main_at)
    assert Technique.HAMMER_ON in notes[7].techniques
