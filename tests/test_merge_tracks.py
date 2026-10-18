"""Two Guitar Pro tracks charted as one (``GpJobSpec.merge_tracks``): a part
split across two tracks — Songsterr often splits one guitarist into "Lead" and
"Rhythm" — becomes a single arrangement."""

from __future__ import annotations

import importlib
from collections.abc import Iterator
from pathlib import Path

import guitarpro as gp
import pytest
from fastapi.testclient import TestClient

from rockforge.application.gp_pipeline import (
    GenerateFromGpUseCase,
    GpJobSpec,
    merge_parsed_tracks,
)
from rockforge.domain.arrangement import SongMetadata
from rockforge.domain.music import Beat, TabNote, TempoMap, Tuning
from rockforge.infrastructure.gpimport.parser import ParsedGpTrack
from rockforge.infrastructure.packaging.dlcbuilder import DlcBuilderPackager


class _Ingest:
    def fetch(self, source: str, workdir: Path) -> Path:
        workdir.mkdir(parents=True, exist_ok=True)
        p = workdir / "a.wav"
        p.write_bytes(b"RIFF0000WAVE")
        return p


class _Normalize:
    def normalize(self, audio: Path, workdir: Path, offset_s: float = 0.0,
                  pad_start_s: float = 0.0) -> Path:
        return audio


def _beat(voice: gp.Voice, value: int, notes: list[tuple[int, int]]) -> None:
    b = gp.Beat(voice)
    b.status = gp.BeatStatus.normal
    b.duration = gp.Duration(value=value)
    for string, fret in notes:  # GP strings: 1 = high e … 6 = low E
        n = gp.Note(b)
        n.string, n.value, n.type = string, fret, gp.NoteType.normal
        b.notes.append(n)
    voice.beats.append(b)


def _split_part(path: Path, second_tuning: list[int] | None = None) -> Path:
    """One guitarist split over two tracks: the first plays beats 1-2 of the bar
    and the second beats 2-4 — beat 2 on the SAME string and fret in both."""
    song = gp.Song()
    song.title, song.artist, song.tempo = "Split", "Band", 120
    first = song.tracks[0]
    first.name = "Lead"
    v = first.measures[0].voices[0]
    _beat(v, 4, [(2, 5)])
    _beat(v, 4, [(2, 7)])
    _beat(v, 2, [])  # rest
    v.beats[-1].status = gp.BeatStatus.rest
    second = gp.Track(song)
    second.name, second.number = "Rhythm", 2
    if second_tuning is not None:
        for s, midi in zip(second.strings, second_tuning, strict=True):
            s.value = midi
    song.tracks.append(second)
    v2 = second.measures[0].voices[0]
    _beat(v2, 4, [])
    v2.beats[-1].status = gp.BeatStatus.rest
    _beat(v2, 4, [(2, 7)])  # the same note the first track plays
    _beat(v2, 4, [(3, 7)])
    _beat(v2, 4, [(3, 9)])
    gp.write(song, str(path))
    return path


def _run(gp_path: Path, tmp_path: Path, **spec: object):
    use_case = GenerateFromGpUseCase(
        ingestor=_Ingest(), normalizer=_Normalize(), packager=DlcBuilderPackager())
    return use_case.run(GpJobSpec(gp_path=gp_path, audio_source="a.wav", **spec),
                        SongMetadata(title="Split", artist="Band"), tmp_path / "w")


def _track(notes: list[TabNote]) -> ParsedGpTrack:
    return ParsedGpTrack(
        notes=notes, tuning=Tuning(midi=(40, 45, 50, 55, 59, 64)),
        tempo_map=TempoMap(beats=(Beat(time=0.0, measure=1), Beat(time=4.0, measure=2)),
                           average_bpm=60.0),
        sections=[],
    )


def test_merged_notes_join_the_chart_and_a_note_both_play_is_kept_once() -> None:
    primary = _track([TabNote(time=0.0, string=4, fret=5, sustain=1.0),
                      TabNote(time=1.0, string=4, fret=7, sustain=0.0)])
    extra = _track([TabNote(time=1.002, string=4, fret=7, sustain=0.0),  # the same note, 2 ms off
                    TabNote(time=0.5, string=4, fret=9, sustain=0.0),
                    TabNote(time=2.0, string=3, fret=7, sustain=0.0)])
    merged, dropped = merge_parsed_tracks(primary, extra)
    assert dropped == 1
    assert [(n.time, n.string, n.fret) for n in merged.notes] == [
        (0.0, 4, 5), (0.5, 4, 9), (1.0, 4, 7), (2.0, 3, 7)]
    # the first note no longer rings into the other track's note on its string
    assert merged.notes[0].time + merged.notes[0].sustain < 0.5


def test_a_part_split_over_two_tracks_is_built_as_one_chart(tmp_path: Path) -> None:
    gp_path = _split_part(tmp_path / "split.gp5")
    alone = _run(gp_path, tmp_path / "a", lead_track=0)
    assert alone.note_counts == {"Combined": 2}
    result = _run(gp_path, tmp_path / "b", lead_track=0, merge_tracks={"Lead": 1})
    # a lone Lead is built as Combined; the shared beat-2 note counts once
    assert result.note_counts == {"Combined": 4}
    said = " ".join(result.warnings)
    assert "2 note(s) of track 2 merged" in said and "1 left out" in said


def test_a_track_in_another_tuning_is_not_merged_and_says_why(tmp_path: Path) -> None:
    gp_path = _split_part(tmp_path / "split.gp5", second_tuning=[62, 57, 53, 48, 43, 38])
    result = _run(gp_path, tmp_path / "b", lead_track=0, merge_tracks={"Lead": 1})
    assert result.note_counts == {"Combined": 2}
    assert any("not merged" in w and "tuning" in w for w in result.warnings)


@pytest.fixture()
def client(tmp_path, monkeypatch) -> Iterator[TestClient]:
    monkeypatch.setenv("ROCKFORGE_DATABASE_URL", f"sqlite:///{tmp_path}/test.db")
    monkeypatch.setenv("ROCKFORGE_WORK_DIR", str(tmp_path / "work"))
    from rockforge import config

    importlib.reload(config)
    import rockforge.interfaces.api.app as app_module

    importlib.reload(app_module)
    monkeypatch.setattr(app_module, "_enqueue", lambda job: None)
    with TestClient(app_module.app) as c:
        yield c


def test_the_merge_is_chosen_in_the_wizard_and_changed_in_editar_info(
    client: TestClient, tmp_path: Path
) -> None:
    data = _split_part(tmp_path / "split.gp5").read_bytes()
    token = client.post(
        "/gp/inspect", files={"file": ("split.gp5", data, "application/octet-stream")}
    ).json()["gp_token"]
    form = {"gp_token": token, "lead_track": "0"}
    audio = {"audio": ("a.wav", b"RIFF0000WAVE", "audio/wav")}
    for bad in ('{"Lead": "x"}', '{"Drums": 1}', "[1]", "not json"):
        r = client.post("/jobs/gp", data={**form, "merge_tracks": bad}, files=audio)
        assert r.status_code == 422, bad
    job = client.post("/jobs/gp", data={**form, "merge_tracks": '{"Lead": 1}'},
                      files=audio).json()
    assert client.get(f"/jobs/{job['id']}/gp-tracks").json()["merge_tracks"] == {"Lead": 1}
    # "Editar info" can take it away again (a rebuild with {}), and a fork keeps it
    kept = client.post(f"/jobs/{job['id']}/rebuild", json={"offset_s": 1.0}).json()
    assert client.get(f"/jobs/{kept['id']}/gp-tracks").json()["merge_tracks"] == {"Lead": 1}
    cleared = client.post(f"/jobs/{kept['id']}/rebuild", json={"merge_tracks": {}}).json()
    assert client.get(f"/jobs/{cleared['id']}/gp-tracks").json()["merge_tracks"] == {}
    assert client.post(f"/jobs/{kept['id']}/rebuild",
                       json={"merge_tracks": {"Lead": -1}}).status_code == 422
