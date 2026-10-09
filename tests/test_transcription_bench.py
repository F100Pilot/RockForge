"""The experimental transcription bench (phase 0): MIDI reading, scoring, the
right answer read from built charts, the transcriber runners and the CLI."""

import struct
import sys
from pathlib import Path

import pytest

from rockforge.domain.arrangement import Arrangement, ArrangementKind, SongMetadata
from rockforge.domain.music import Beat, TabNote, TempoMap, Tuning
from rockforge.experimental.transcription import cli
from rockforge.experimental.transcription.midi import (
    MidiNote,
    guitar_notes,
    parse_midi,
    read_midi,
    write_midi,
)
from rockforge.experimental.transcription.runners import RunnerError, run, run_command
from rockforge.experimental.transcription.score import (
    Note,
    best_shift,
    match_score,
    pitch_class,
)
from rockforge.experimental.transcription.truth import song_from_job
from rockforge.infrastructure.rsxml.writer import write_arrangement_xml


def _vl(v: int) -> bytes:
    out = [v & 0x7F]
    v >>= 7
    while v:
        out.append((v & 0x7F) | 0x80)
        v >>= 7
    return bytes(reversed(out))


def _smf(*tracks: bytes, ppq: int = 96) -> bytes:
    body = b"".join(b"MTrk" + struct.pack(">I", len(t)) + t for t in tracks)
    return b"MThd" + struct.pack(">IHHH", 6, 1, len(tracks), ppq) + body


def test_a_midi_file_reads_back_with_its_tempo_programs_and_running_status() -> None:
    # 120 BPM, then 60 BPM from tick 96 (one quarter = 0.5 s, then 1 s).
    tempo = (b"\x00\xff\x51\x03" + (500_000).to_bytes(3, "big")
             + _vl(96) + b"\xff\x51\x03" + (1_000_000).to_bytes(3, "big") + b"\x00\xff\x2f\x00")
    guitar = (b"\x00\xc0\x1d"                       # program 29 on channel 0
              + b"\x00\x90\x40\x64"                 # E4 on at 0
              + _vl(96) + b"\x40\x00"               # running status: off at tick 96 (0.5 s)
              + b"\x00\x43\x50"                     # running status: G4 on at 0.5 s
              + _vl(96) + b"\x80\x43\x00"           # off at tick 192 (1.5 s)
              + b"\x00\xff\x2f\x00")
    others = (b"\x00\xc1\x21" + b"\x00\x91\x28\x64" + _vl(48) + b"\x81\x28\x00"   # bass
              + b"\x00\x99\x24\x64" + _vl(10) + b"\x89\x24\x00"                  # drums
              + b"\x00\xff\x2f\x00")
    notes = parse_midi(_smf(tempo, guitar, others))
    by_pitch = {n.pitch: n for n in notes}
    assert by_pitch[0x40].start == 0.0 and by_pitch[0x40].end == pytest.approx(0.5)
    assert by_pitch[0x43].start == pytest.approx(0.5) and by_pitch[0x43].end == pytest.approx(1.5)
    assert [n.pitch for n in guitar_notes(notes)] == [0x40, 0x43]  # bass and drums left out
    # No guitar program at all (a guitar-only model leaves it at 0): every pitched note.
    plain = parse_midi(_smf(b"\x00\x90\x40\x64" + _vl(96) + b"\x80\x40\x00"
                            + b"\x00\x99\x24\x64" + _vl(10) + b"\x89\x24\x00\x00\xff\x2f\x00"))
    assert [n.pitch for n in guitar_notes(plain)] == [0x40]


def test_written_midi_reads_back_note_for_note(tmp_path: Path) -> None:
    lead = [MidiNote(0.0, 0.5, 64), MidiNote(1.25, 1.5, 67)]
    rhythm = [MidiNote(0.5, 2.0, 40)]
    write_midi([("Lead", lead), ("Rhythm", rhythm)], tmp_path / "t.mid")
    back = read_midi(tmp_path / "t.mid")
    assert [(round(n.start, 3), round(n.end, 3), n.pitch) for n in back] == [
        (0.0, 0.5, 64), (0.5, 2.0, 40), (1.25, 1.5, 67)]
    assert {n.program for n in back} == {29} and len(guitar_notes(back)) == 3


def test_notes_match_on_pitch_within_the_onset_tolerance_once_each() -> None:
    ref = [Note(1.0, 60), Note(2.0, 62), Note(3.0, 64)]
    assert match_score(ref, ref).f1 == 1.0
    late = [Note(1.03, 60), Note(2.06, 62), Note(3.0, 64)]
    s = match_score(ref, late)
    assert (s.matched, s.precision, s.recall) == (2, pytest.approx(2 / 3), pytest.approx(2 / 3))
    doubled = [Note(1.0, 60), Note(1.01, 60)]  # a note found twice counts once
    assert match_score(ref, doubled).matched == 1 and match_score(ref, doubled).precision == 0.5
    octave = [Note(1.0, 72), Note(2.0, 74), Note(3.0, 76)]
    assert match_score(ref, octave).f1 == 0.0
    assert match_score(ref, octave, key=pitch_class).f1 == 1.0
    # Close pairs on one pitch: the greedy walk still finds the full matching.
    pair = match_score([Note(0.0, 60), Note(0.08, 60)], [Note(0.04, 60), Note(0.12, 60)])
    assert pair.matched == 2


def test_the_shift_that_lines_a_transcription_up_is_found() -> None:
    ref = [Note(1.0 + 0.37 * i, 50 + (i * 5) % 17) for i in range(60)]
    elsewhere = [Note(n.time - 12.3, n.pitch) for n in ref]  # a tab whose bar 1 sits at 0
    shift = best_shift(ref, elsewhere, max_shift=60)
    assert shift == pytest.approx(12.3, abs=0.01)
    assert match_score(ref, elsewhere, shift=shift).f1 == 1.0
    assert best_shift(ref, elsewhere, max_shift=0.25) == 0.0  # out of a model's latency range
    latent = [Note(n.time + 0.08, n.pitch) for n in ref]
    assert best_shift(ref, latent, max_shift=0.25) == pytest.approx(-0.08, abs=0.01)


def _built_song(tmp_path: Path):  # noqa: ANN202
    bundle = tmp_path / "bundle"
    beats = tuple(Beat(time=round(2.5 + 0.5 * i, 3), measure=(i // 4 + 1) if i % 4 == 0 else -1)
                  for i in range(20))
    drop_d = Tuning(midi=(38, 45, 50, 55, 59, 64))
    shared = TabNote(string=0, fret=0, time=3.0, sustain=0.2)  # in Lead AND Combined
    charts = {
        ArrangementKind.LEAD: [shared, TabNote(string=4, fret=5, time=4.0, sustain=0.2)],
        ArrangementKind.RHYTHM: [TabNote(string=1, fret=2, time=3.5, sustain=0.2)],
        ArrangementKind.COMBINED: [shared],
        ArrangementKind.ALTERNATE_LEAD: [TabNote(string=5, fret=12, time=5.0, sustain=0.2)],
    }
    for kind, notes in charts.items():
        write_arrangement_xml(Arrangement(
            kind=kind, metadata=SongMetadata(title="T", artist="A", song_length=12.0),
            tuning=drop_d, notes=notes, tempo_map=TempoMap(beats=beats, average_bpm=120.0),
        ), bundle / f"arrangement_{kind.name.lower()}.xml")
    audio = tmp_path / "rec.wav"
    audio.write_bytes(b"RIFF")
    params = {"offset_s": 0.5, "lead_in_s": 1.0, "synced_arrangements": ["Lead"]}
    return song_from_job("job1", "T", "A", str(audio), params, str(bundle))


def test_the_right_answer_is_the_built_charts_on_the_recordings_clock(tmp_path: Path) -> None:
    song = _built_song(tmp_path)
    assert song.pad_s == pytest.approx(2.5)  # (2 - 0.5) + 1 s of intro silence
    lead = next(c for c in song.charts if c.kind is ArrangementKind.LEAD)
    assert [(round(n.time, 3), n.pitch) for n in lead.notes] == [(0.5, 38), (1.5, 64)]
    assert {c.kind: c.synced for c in song.charts} == {
        ArrangementKind.LEAD: True, ArrangementKind.RHYTHM: False,
        ArrangementKind.COMBINED: False, ArrangementKind.ALTERNATE_LEAD: False}
    # The guitar part: each note once, the alternate (another take of the Lead) out.
    assert [(round(n.time, 3), n.pitch) for n in song.guitar_part()] == [
        (0.5, 38), (1.0, 47), (1.5, 64)]


def test_a_perfect_transcription_scores_every_chart(tmp_path: Path) -> None:
    song = _built_song(tmp_path)
    row = cli.evaluate(song, song.guitar_part(), source="stem", model="x", max_shift=0.25)
    assert (row.f1, row.shift, row.tab_f1) == (1.0, 0.0, 1.0)
    assert row.chart_recall == {"Lead": 1.0, "Rhythm": 1.0, "Combined": 1.0,
                                "Alternate Lead": 0.0}
    assert row.synced is False  # not every chart marked


def test_a_runner_reports_the_install_when_its_package_is_missing(tmp_path: Path) -> None:
    with pytest.raises(RunnerError) as err:
        run("gaps", tmp_path / "a.wav", tmp_path / "o.mid", sys.executable, "cpu")
    assert "ModuleNotFoundError" in str(err.value) and "pip install" in str(err.value)


def test_any_tool_can_be_run_as_a_command(tmp_path: Path) -> None:
    script = tmp_path / "tool.py"
    script.write_text(
        "import sys\n"
        "from rockforge.experimental.transcription.midi import MidiNote, write_midi\n"
        "from pathlib import Path\n"
        "write_midi([('g', [MidiNote(0.5, 1.0, 38)])], Path(sys.argv[2]))\n")
    out = tmp_path / "o.mid"
    run_command(f'"{sys.executable}" "{script}" {{audio}} {{midi}}', tmp_path / "a.wav", out)
    assert [n.pitch for n in read_midi(out)] == [38]
    with pytest.raises(RunnerError):
        run_command(f'"{sys.executable}" -c "raise SystemExit(3)"', tmp_path / "a.wav",
                    tmp_path / "none.mid")


def test_the_bench_runs_end_to_end_on_a_project(tmp_path: Path, monkeypatch, capsys) -> None:
    import rockforge.config as config
    from rockforge.infrastructure.db.models import Job, JobStatus, make_session_factory

    song = _built_song(tmp_path)
    url = f"sqlite:///{tmp_path}/bench.db"
    with make_session_factory(url)() as session:
        session.add(Job(id="job1", status=JobStatus.COMPLETED, source=str(song.audio),
                        source_type="gp", title="T", artist="A",
                        params={"offset_s": 0.5, "lead_in_s": 1.0},
                        bundle_dir=str(tmp_path / "bundle")))
        session.add(Job(id="job2", status=JobStatus.FAILED, source="x", source_type="gp",
                        title="F", artist="A"))
        session.commit()
    monkeypatch.setattr(config.settings, "database_url", url)
    monkeypatch.setattr(config.settings, "work_dir", tmp_path / "work")

    assert cli.main(["list"]) == 0
    assert "job1" in capsys.readouterr().out

    # A "transcriber" that hears the right answer 30 ms late and an octave off on one note.
    tool = tmp_path / "tool.py"
    tool.write_text(
        "import sys\n"
        "from rockforge.experimental.transcription.midi import MidiNote, write_midi\n"
        "from pathlib import Path\n"
        "notes = [MidiNote(0.53, 0.8, 38), MidiNote(1.03, 1.3, 47), MidiNote(1.53, 1.8, 76)]\n"
        "write_midi([('g', notes)], Path(sys.argv[2]))\n")
    assert cli.main(["run", "--models", "", "--input", "mix", "--cmd",
                     f'"{sys.executable}" "{tool}" {{audio}} {{midi}}']) == 0
    out = capsys.readouterr().out
    assert "66.7%" in out and "100.0%" in out  # F1, and F1 with the octave ignored
    report = (tmp_path / "work" / "transcription_bench" / "report.md").read_text("utf-8")
    assert "| mix | cmd | 1 |" in report
    assert (tmp_path / "work" / "transcription_bench" / "job1" / "truth.mid").is_file()
    assert "job2" not in out
