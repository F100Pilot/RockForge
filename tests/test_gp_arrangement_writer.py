"""Writing an Arrangement back out as a fresh Guitar Pro 5 file.

Every test round-trips through RockForge's OWN importer: what we write has to
come back as the same notes, at the same times, on the same strings. That is the
only check available here — no Guitar Pro exists in CI or in the sandbox, so the
files have not been opened in Guitar Pro itself (same standing caveat as
tempo_writer's exports).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from rockforge.domain.arrangement import Arrangement, ArrangementKind, Section, SongMetadata
from rockforge.domain.errors import IngestionError
from rockforge.domain.music import Beat, TabNote, Technique, TempoMap, Tuning
from rockforge.infrastructure.gpexport.arrangement_writer import write_arrangement_gp5
from rockforge.infrastructure.gpimport.parser import inspect_gp, parse_gp_track


def _steady(bars: int = 4, bpm: float = 120.0) -> tuple[Beat, ...]:
    step = 60.0 / bpm
    return tuple(
        Beat(time=i * step, measure=(i // 4) + 1 if i % 4 == 0 else -1)
        for i in range(bars * 4 + 1)
    )


def _arrangement(notes: list[TabNote], **kw: object) -> Arrangement:
    beats = kw.pop("beats", None) or _steady()
    return Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="Song", artist="Band", album="Album", song_length=8.0),
        tuning=kw.pop("tuning", None) or Tuning(),
        tempo_map=TempoMap(beats=beats, average_bpm=120.0),
        notes=notes,
        sections=kw.pop("sections", None) or [],
    )


def test_notes_survive_the_round_trip(tmp_path: Path) -> None:
    """Times, strings and frets must come back exactly — this is the whole point
    of exporting: the user's edited chart, as a real Guitar Pro score."""
    notes = [
        TabNote(string=i % 6, fret=(i % 7) + 1, time=i * 0.5, sustain=0.4)
        for i in range(16)
    ]
    dst = tmp_path / "out.gp5"
    report = write_arrangement_gp5(_arrangement(notes), dst)
    assert report.notes_written == 16
    assert report.quantized == 0, "notes already on the beat must not be moved"

    parsed = parse_gp_track(dst, 0)
    assert len(parsed.notes) == 16
    for original, got in zip(notes, parsed.notes, strict=True):
        assert got.time == pytest.approx(original.time, abs=1e-3)
        assert (got.string, got.fret) == (original.string, original.fret)


def test_the_corrected_tempo_map_is_what_gets_written(tmp_path: Path) -> None:
    """The arrangement is already in the BUILT clock, so its beat grid carries
    the user's tempo_scale and drift corrections. Writing that grid back out is
    exactly what makes the sync fix permanent in Guitar Pro, so a song whose
    tempo changes mid-way has to survive with its bars in the right places."""
    times: list[float] = []
    t = 0.0
    for bar in range(4):
        step = 0.5 if bar < 2 else 60.0 / 90.0  # 120 BPM, then 90
        for _ in range(4):
            times.append(t)
            t += step
    times.append(t)
    beats = tuple(
        Beat(time=v, measure=(i // 4) + 1 if i % 4 == 0 else -1)
        for i, v in enumerate(times)
    )
    notes = [TabNote(string=0, fret=3, time=v, sustain=0.2) for v in times[:16]]
    dst = tmp_path / "tempo.gp5"
    write_arrangement_gp5(_arrangement(notes, beats=beats), dst)

    parsed = parse_gp_track(dst, 0)
    for original, got in zip(times[:16], parsed.notes, strict=True):
        assert got.time == pytest.approx(original, abs=1e-3)


def test_tuning_metadata_and_sections_survive(tmp_path: Path) -> None:
    notes = [TabNote(string=0, fret=3, time=i * 0.5, sustain=0.2) for i in range(8)]
    drop_d = Tuning(midi=(38, 45, 50, 55, 59, 64))
    arr = _arrangement(
        notes,
        tuning=drop_d,
        sections=[Section(name="intro", start_time=0.0), Section(name="solo", start_time=2.0)],
    )
    dst = tmp_path / "meta.gp5"
    write_arrangement_gp5(arr, dst)

    info = inspect_gp(dst)
    assert (info.title, info.artist, info.album) == ("Song", "Band", "Album")
    assert info.tracks[0].tuning_midi == drop_d.midi
    parsed = parse_gp_track(dst, 0)
    assert [s.name for s in parsed.sections] == ["intro", "solo"]
    assert parsed.sections[1].start_time == pytest.approx(2.0, abs=1e-3)


def test_techniques_and_chords_survive(tmp_path: Path) -> None:
    notes = [
        # A chord: three notes at the same instant must become ONE beat.
        TabNote(string=0, fret=0, time=0.0, sustain=0.4),
        TabNote(string=1, fret=2, time=0.0, sustain=0.4),
        TabNote(string=2, fret=2, time=0.0, sustain=0.4),
        TabNote(string=3, fret=7, time=0.5, sustain=0.4,
                techniques=frozenset({Technique.PALM_MUTE})),
        TabNote(string=3, fret=9, time=1.0, sustain=0.4,
                techniques=frozenset({Technique.VIBRATO})),
        TabNote(string=4, fret=5, time=1.5, sustain=0.4,
                techniques=frozenset({Technique.FRET_MUTE})),
    ]
    dst = tmp_path / "tech.gp5"
    write_arrangement_gp5(_arrangement(notes), dst)

    parsed = parse_gp_track(dst, 0)
    at_zero = [n for n in parsed.notes if n.time == pytest.approx(0.0, abs=1e-3)]
    assert len(at_zero) == 3, "simultaneous notes must round-trip as one chord"
    by_time = {round(n.time, 2): n for n in parsed.notes if n.time > 0.1}
    assert Technique.PALM_MUTE in by_time[0.5].techniques
    assert Technique.VIBRATO in by_time[1.0].techniques
    assert Technique.FRET_MUTE in by_time[1.5].techniques


def test_an_off_grid_onset_is_quantized_and_the_shift_is_reported(tmp_path: Path) -> None:
    """Guitar Pro needs notated rhythm, so an onset between grid positions has to
    move. It must be REPORTED rather than silently re-timed — a score that looks
    authoritative but plays differently is the worst outcome here."""
    notes = [
        TabNote(string=0, fret=3, time=0.0, sustain=0.2),
        TabNote(string=0, fret=5, time=0.31, sustain=0.2),  # off the 16th grid
    ]
    dst = tmp_path / "q.gp5"
    report = write_arrangement_gp5(_arrangement(notes), dst)
    assert report.quantized >= 1
    assert report.max_shift_s > 0.0
    assert any("grelha" in w for w in report.warnings)


def test_the_single_track_limitation_is_always_stated(tmp_path: Path) -> None:
    """The export generates a new file rather than patching the user's, so it
    cannot carry their other tracks. That is a real loss and the report says so
    every time, not only when something went wrong."""
    dst = tmp_path / "warn.gp5"
    report = write_arrangement_gp5(
        _arrangement([TabNote(string=0, fret=3, time=0.0, sustain=0.2)]), dst
    )
    assert any("só esta pista" in w for w in report.warnings)


def test_an_arrangement_with_no_beat_grid_is_refused(tmp_path: Path) -> None:
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="S", artist="A", song_length=1.0),
        tuning=Tuning(),
        tempo_map=TempoMap(beats=(), average_bpm=120.0),
        notes=[],
    )
    with pytest.raises(IngestionError, match="beat grid"):
        write_arrangement_gp5(arr, tmp_path / "none.gp5")


def test_the_closing_bar_line_ends_the_last_bar_instead_of_adding_one(tmp_path: Path) -> None:
    """A built grid ends on the song's closing bar line — a downbeat with nothing
    after it (``close_beat_grid``). It is where the last bar ENDS; exporting it
    as a bar of its own tacked an empty one-beat bar onto every song."""
    import guitarpro

    notes = [TabNote(string=0, fret=3, time=7.75, sustain=0.2)]  # the "and" of 4, bar 4
    dst = tmp_path / "out.gp5"
    write_arrangement_gp5(_arrangement(notes), dst)  # _steady: 4 bars + the closing line
    assert len(guitarpro.parse(str(dst)).measureHeaders) == 4
    assert parse_gp_track(dst, 0).notes[0].time == pytest.approx(7.75, abs=1e-3)
