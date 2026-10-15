"""Direct unit tests for the Celery task bodies in celery_app.py.

Before this file, generate_cdlc/detect_tones/separate_stems/detect_lyrics were
only exercised indirectly through test_api.py's stubbed _enqueue*/_enqueue_detect*
callbacks — meaning the actual @celery_app.task function BODIES never ran in
the test suite at all. These tests call each task function directly (never
.delay()) against a Job row in a fresh per-test SQLite DB, faking the heavy
adapters (Demucs, ffmpeg, GP packaging) at the port boundary — the same
"inject fakes" style as test_gp_pipeline.py / test_api.py (see TESTING.md §2).
"""

from __future__ import annotations

from pathlib import Path

import guitarpro as gp
import pytest

from rockforge.application.ports import PackagingResult
from rockforge.infrastructure.db.models import Job, JobStatus, make_session_factory
from rockforge.interfaces.worker import celery_app as ca


def _make_gp5(tmp_path: Path) -> Path:
    song = gp.Song()
    song.title, song.artist, song.tempo = "T", "A", 120
    song.tracks[0].name = "Lead"
    v = song.tracks[0].measures[0].voices[0]
    b = gp.Beat(v)
    b.status = gp.BeatStatus.normal
    b.duration = gp.Duration(value=4)
    n = gp.Note(b)
    n.string, n.value, n.type = 1, 3, gp.NoteType.normal
    b.notes.append(n)
    v.beats.append(b)
    path = tmp_path / "song.gp5"
    gp.write(song, str(path))
    return path


class _FakeIngestor:
    def fetch(self, source: str, workdir: Path) -> Path:
        workdir.mkdir(parents=True, exist_ok=True)
        p = workdir / "input.wav"
        p.write_bytes(b"RIFF")
        return p


class _FakeNormalizer:
    def normalize(
        self, audio: Path, workdir: Path, offset_s: float = 0.0, pad_start_s: float = 0.0
    ) -> Path:
        return audio


class _FakePackager:
    def package(self, arrangements, audio, out_dir, vocals=None, cover_art=None,
                dynamic_difficulty=True):
        out_dir.mkdir(parents=True, exist_ok=True)
        return PackagingResult(
            bundle_dir=out_dir, xml_paths=(), wem_path=None, psarc_path=None,
        )


class _FailingPackager:
    def package(self, *args, **kwargs):
        raise RuntimeError("packaging exploded")


class _FakeStemSeparator:
    """Stands in for DemucsSeparator/BanquetSeparator without running Demucs."""

    def has_cached_guitar_stem(self, audio: Path, workdir: Path) -> bool:
        return False

    def separate_guitar(self, audio: Path, workdir: Path) -> Path:
        return workdir / "guitar.wav"

    def separate_stems(self, audio: Path, workdir: Path) -> dict[str, Path]:
        return {name: workdir / f"{name}.wav" for name in ("guitar", "bass", "drums", "vocals")}


@pytest.fixture()
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(ca.settings, "database_url", f"sqlite:///{tmp_path}/celery_tasks.db")
    monkeypatch.setattr(ca.settings, "work_dir", tmp_path / "work")
    return make_session_factory(ca.settings.database_url)


def _job(db, *, source_type: str = "gp", params: dict | None = None) -> str:
    with db() as session:
        job = Job(
            source="unused-for-fakes",
            source_type=source_type,
            title="Song", artist="Artist",
            params=params or {},
        )
        session.add(job)
        session.commit()
        return job.id


def _reload(db, job_id: str) -> Job:
    with db() as session:
        return session.get(Job, job_id)


# --- generate_cdlc --------------------------------------------------------

def test_generate_cdlc_gp_job_completes(db, tmp_path, monkeypatch) -> None:
    from rockforge.application.gp_pipeline import GenerateFromGpUseCase

    gp_path = _make_gp5(tmp_path)
    monkeypatch.setattr(
        ca, "_build_gp_use_case",
        lambda: GenerateFromGpUseCase(
            ingestor=_FakeIngestor(), normalizer=_FakeNormalizer(), packager=_FakePackager()
        ),
    )
    job_id = _job(db, params={"gp_path": str(gp_path), "lead_track": 0})

    ca.generate_cdlc(job_id)

    job = _reload(db, job_id)
    assert job.status == JobStatus.COMPLETED
    assert job.bundle_dir is not None
    assert job.error is None


def test_the_fhp_editors_hand_positions_reach_the_build(db, tmp_path, monkeypatch) -> None:
    """params["hand_positions"] (the FHP editor) becomes each chart's own
    fret-hand positions; a chart absent from it keeps the automatic ones."""
    from rockforge.application.gp_pipeline import GenerateFromGpUseCase

    seen: list = []

    class _Capture(_FakePackager):
        def package(self, arrangements, *args, **kwargs):
            seen.extend(arrangements)
            return super().package(arrangements, *args, **kwargs)

    gp_path = _make_gp5(tmp_path)
    monkeypatch.setattr(
        ca, "_build_gp_use_case",
        lambda: GenerateFromGpUseCase(
            ingestor=_FakeIngestor(), normalizer=_FakeNormalizer(), packager=_Capture()
        ),
    )
    job_id = _job(db, params={
        "gp_path": str(gp_path), "lead_track": 0,
        # A lone Lead is built as Combined; the Rhythm is not in this song.
        "hand_positions": {"Combined": [{"time": 0.0, "fret": 5, "width": 5}],
                           "Rhythm": [{"time": 0.0, "fret": 2}]},
    })

    ca.generate_cdlc(job_id)

    job = _reload(db, job_id)
    assert job.status == JobStatus.COMPLETED, job.error
    (combined,) = seen
    assert [(h.time, h.fret, h.width) for h in combined.hand_positions] == [(0.0, 5, 5)]
    # The note (fret 3) sits outside that window: said, not refused.
    assert any("1 note(s) outside" in w for w in job.warnings), job.warnings


def test_a_gp_files_lyrics_reach_the_editor_after_the_build(db, tmp_path, monkeypatch) -> None:
    """The build stores the GP file's own lyrics as the editor's rows. It never
    did in a real run: the task wrote into the very dict the session holds as
    the column's stored value, so the fresh copy it then assigned compared
    equal to "unchanged" and no UPDATE was issued."""
    from rockforge.application.gp_pipeline import GenerateFromGpUseCase

    song = gp.Song()
    song.title, song.artist, song.tempo = "T", "A", 120
    v = song.tracks[0].measures[0].voices[0]
    for fret in (3, 5):
        b = gp.Beat(v)
        b.status, b.duration = gp.BeatStatus.normal, gp.Duration(value=4)
        n = gp.Note(b)
        n.string, n.value, n.type = 1, fret, gp.NoteType.normal
        b.notes.append(n)
        v.beats.append(b)
    song.lyrics.trackChoice = 1
    song.lyrics.lines[0].lyrics = "hel-lo"
    gp_path = tmp_path / "lyrics.gp5"
    gp.write(song, str(gp_path))
    monkeypatch.setattr(
        ca, "_build_gp_use_case",
        lambda: GenerateFromGpUseCase(
            ingestor=_FakeIngestor(), normalizer=_FakeNormalizer(), packager=_FakePackager()
        ),
    )
    job_id = _job(db, params={"gp_path": str(gp_path), "lead_track": 0})

    ca.generate_cdlc(job_id)

    rows = _reload(db, job_id).params.get("lyrics_events")
    assert [(round(r["time"], 3), r["lyric"]) for r in rows or []] == [
        (0.0, "hel-"), (0.5, "lo+"),
    ]
    # The notes they are sung on travel too, for the viewer's "Voz" source.
    params = _reload(db, job_id).params
    assert params["gp_has_lyrics"] is True
    # Timed on the score, so the viewer moves them with the chart's corrections.
    assert params["lyrics_follow_chart"] is True
    assert params["gp_synced"] is False  # a GP5 cannot carry Guitar Pro 8 sync points
    assert [
        (round(r["time"], 3), round(r["length"], 3), r["midi"])
        for r in params["vocal_melody"]
    ] == [(0.0, 0.5, 67), (0.5, 0.5, 69)]


def test_generate_cdlc_never_crashes_on_packaging_failure(db, tmp_path, monkeypatch) -> None:
    """A heavy-stage exception must land the job in FAILED with the error
    recorded, not propagate out of the task (which would look like a crashed
    worker rather than a reported failure)."""
    from rockforge.application.gp_pipeline import GenerateFromGpUseCase

    gp_path = _make_gp5(tmp_path)
    monkeypatch.setattr(
        ca, "_build_gp_use_case",
        lambda: GenerateFromGpUseCase(
            ingestor=_FakeIngestor(), normalizer=_FakeNormalizer(), packager=_FailingPackager()
        ),
    )
    job_id = _job(db, params={"gp_path": str(gp_path), "lead_track": 0})

    ca.generate_cdlc(job_id)  # must not raise

    job = _reload(db, job_id)
    assert job.status == JobStatus.FAILED
    assert "packaging exploded" in job.error


def test_generate_cdlc_rejects_unsupported_source_type(db) -> None:
    job_id = _job(db, source_type="not-gp")

    ca.generate_cdlc(job_id)

    job = _reload(db, job_id)
    assert job.status == JobStatus.FAILED
    assert "unsupported source_type" in job.error


def test_generate_cdlc_missing_job_is_a_silent_no_op(db) -> None:
    """A job deleted while queued (e.g. the user removed it before the worker
    picked up the task) must not raise — there's nothing left to update."""
    ca.generate_cdlc("does-not-exist")  # must not raise


# --- detect_tones ----------------------------------------------------------

def test_detect_tones_success_populates_ranked_candidates(db, monkeypatch) -> None:
    from rockforge.infrastructure.normalize.ffmpeg import FfmpegNormalizer
    from rockforge.infrastructure.tone_analysis import analyzer as analyzer_mod

    monkeypatch.setattr(ca, "_make_demucs", lambda device: _FakeStemSeparator())
    monkeypatch.setattr(
        FfmpegNormalizer, "normalize",
        lambda self, audio, workdir, offset_s=0.0, pad_start_s=0.0: workdir / "normalized.wav",
    )
    monkeypatch.setattr(
        analyzer_mod, "analyze_guitar_timeline",
        lambda guitar_stem: (
            analyzer_mod.ToneProfile(
                gain_level=0.35, brightness=0.5, low_end=0.4, dynamic_range=0.3,
            ),
            [
                analyzer_mod.WindowProfile(
                    t=2.0, active=False, gain_level=0.1, brightness=0.4, low_end=0.3,
                ),
                analyzer_mod.WindowProfile(
                    t=3.0, active=True, gain_level=0.6, brightness=0.5, low_end=0.4,
                ),
            ],
        ),
    )
    job_id = _job(db)

    ca.detect_tones(job_id)

    job = _reload(db, job_id)
    assert job.params["tone_detection_status"] == "ready"
    detected = job.params["detected_tones"]
    assert detected["category"] == "crunch"  # 0.25 <= gain_level=0.35 < 0.5 -> crunch
    assert detected["lead_candidates"] and detected["rhythm_candidates"]
    # The tone over time is kept, in the recording's clock, for /tone-suggestions.
    assert detected["timeline"] == [[2.0, 0.1, 0.4, 0.3, 0], [3.0, 0.6, 0.5, 0.4, 1]]
    assert any("done" in line for line in job.params["tone_detection_log"])


def test_detect_tones_failure_sets_unavailable_not_job_status(db, monkeypatch) -> None:
    """Progress lives in params, never JobStatus, so a failed detection never
    hides an otherwise-completed job (see CLAUDE.md's async-detection pattern)."""
    from rockforge.infrastructure.normalize.ffmpeg import FfmpegNormalizer

    monkeypatch.setattr(ca, "_make_demucs", lambda device: _FakeStemSeparator())

    def _boom(self, audio, workdir, offset_s=0.0, pad_start_s=0.0):
        raise RuntimeError("ffmpeg not found")

    monkeypatch.setattr(FfmpegNormalizer, "normalize", _boom)
    job_id = _job(db)
    original_status = _reload(db, job_id).status

    ca.detect_tones(job_id)  # must not raise

    job = _reload(db, job_id)
    assert job.status == original_status  # JobStatus untouched
    assert job.params["tone_detection_status"] == "unavailable"
    assert any("tone detection failed" in w for w in job.warnings)


# --- separate_stems ----------------------------------------------------------

def test_separate_stems_success_drops_drums(db, monkeypatch) -> None:
    from rockforge.infrastructure.normalize.ffmpeg import FfmpegNormalizer

    monkeypatch.setattr(
        ca, "_build_stem_separator", lambda: (_FakeStemSeparator(), "cpu", "demucs htdemucs_6s")
    )
    monkeypatch.setattr(
        FfmpegNormalizer, "normalize",
        lambda self, audio, workdir, offset_s=0.0, pad_start_s=0.0: workdir / "normalized.wav",
    )
    job_id = _job(db)

    ca.separate_stems(job_id)

    job = _reload(db, job_id)
    assert job.params["stems_status"] == "ready"
    assert "drums" not in job.params["stems"]
    assert set(job.params["stems"]) == {"guitar", "bass", "vocals"}


def test_separate_stems_failure_sets_unavailable(db, monkeypatch) -> None:
    def _boom():
        raise RuntimeError("demucs is not installed")

    monkeypatch.setattr(ca, "_build_stem_separator", _boom)
    job_id = _job(db)

    ca.separate_stems(job_id)  # must not raise

    job = _reload(db, job_id)
    assert job.params["stems_status"] == "unavailable"
    assert any("stem separation failed" in w for w in job.warnings)


# --- detect_lyrics -----------------------------------------------------------

def test_detect_lyrics_reports_unavailable_when_whisperx_is_not_installed(db) -> None:
    """No mocking needed: whisperx isn't part of the base install (or this
    sandbox), so the real availability probe genuinely fails — exercising the
    task's actual subprocess-based check end to end."""
    job_id = _job(db)

    ca.detect_lyrics(job_id)  # must not raise

    job = _reload(db, job_id)
    assert job.params["lyrics_status"] == "unavailable"
    assert any("lyric detection requested but whisperx is not installed" in w
               for w in job.warnings)


def test_the_whisperx_runner_aligns_known_lyrics_only_when_asked(tmp_path) -> None:
    common = dict(model="small", device="cpu", compute_type="")
    cmd = ca._whisperx_command("py", Path("r.py"), Path("v.wav"), Path("o.json"), **common)
    assert "--align-json" not in cmd
    cmd = ca._whisperx_command("py", Path("r.py"), Path("v.wav"), Path("o.json"),
                               align_json=tmp_path / "lines.json", **common)
    assert cmd[-2:] == ["--align-json", str(tmp_path / "lines.json")]


def test_an_alignment_request_is_used_once_even_when_it_fails(db) -> None:
    """The request lives in params for exactly one run: a later plain
    "Detetar letra" must transcribe, not re-align stale lines."""
    job_id = _job(db, params={"lyrics_align": {"lines": [{"time": 1.0, "text": "hi"}],
                                               "language": "en"}})
    ca.detect_lyrics(job_id)  # whisperx is not installed here → unavailable
    job = _reload(db, job_id)
    assert job.params["lyrics_status"] == "unavailable"
    assert "lyrics_align" not in job.params


def test_a_gp8_file_synced_in_guitar_pro_is_recognised(tmp_path) -> None:
    """The build marks a file that carries its own Guitar Pro 8 sync points, so
    the checklist stops asking "confirmaste a sincronização?" about it."""
    import zipfile

    def gp(automations: str) -> Path:
        path = tmp_path / f"s{len(automations)}.gp"
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("VERSION", "7.0")
            z.writestr("Content/score.gpif", (
                '<?xml version="1.0" encoding="utf-8"?><GPIF><Score><Title>T</Title></Score>'
                "<MasterTrack><Automations><Automation><Type>Tempo</Type><Bar>0</Bar>"
                f"<Position>0</Position><Value>120 2</Value></Automation>{automations}"
                "</Automations></MasterTrack><MasterBars><MasterBar><Time>4/4</Time>"
                "<Bars>0</Bars></MasterBar></MasterBars></GPIF>"
            ))
        return path

    point = (
        "<Automation><Type>SyncPoint</Type><Bar>0</Bar><Position>0</Position><Value>"
        "<BarIndex>0</BarIndex><BarOccurrence>0</BarOccurrence>"
        "<FrameOffset>44100</FrameOffset></Value></Automation>"
    )
    assert ca._gp_carries_sync(gp(point)) is True
    assert ca._gp_carries_sync(gp("")) is False
    assert ca._gp_carries_sync(tmp_path / "missing.gp") is False


def test_each_tracks_own_tones_reach_the_build(db, tmp_path, monkeypatch) -> None:
    from rockforge.application.gp_pipeline import ArrangementTones, GenerateFromGpUseCase

    seen = []

    class _Recording(GenerateFromGpUseCase):
        def run(self, spec, *args, **kwargs):  # type: ignore[no-untyped-def]
            seen.append(spec)
            return super().run(spec, *args, **kwargs)

    monkeypatch.setattr(
        ca, "_build_gp_use_case",
        lambda: _Recording(
            ingestor=_FakeIngestor(), normalizer=_FakeNormalizer(), packager=_FakePackager()
        ),
    )
    job_id = _job(db, params={
        "gp_path": str(_make_gp5(tmp_path)), "lead_track": 0, "tone_base": "crunch",
        "arrangement_tones": {"Lead": {
            "tone_base": "clean", "tone_names": ["solo"],
            "tone_changes": [{"time": 1.5, "name": "solo"}],
        }},
    })
    ca.generate_cdlc(job_id)
    from rockforge.domain.arrangement import ArrangementKind, ToneChange

    spec = seen[0]
    assert spec.arrangement_tones == {"Lead": ArrangementTones(
        tone_base="clean", tone_names=["solo"], tone_changes=[ToneChange(1.5, "solo")],
    )}
    assert spec.tones_for(ArrangementKind.RHYTHM).tone_base == "crunch"
