"""Celery application and the long-running pipeline task."""

from __future__ import annotations

import contextlib
import copy
from datetime import UTC, datetime
from functools import cache
from pathlib import Path
from typing import Any, cast

from celery import Celery
from celery.signals import after_setup_logger

from rockforge.config import settings
from rockforge.i18n import tr
from rockforge.infrastructure.db.models import Job, JobStatus, make_session_factory

celery_app = Celery(
    "rockforge", broker=settings.broker_url, backend=settings.result_backend
)
celery_app.conf.task_track_started = True


@after_setup_logger.connect
def _technical_log(logger: Any, **_kw: Any) -> None:
    """A Celery worker is a process of its own: its technical log is
    rockforge-worker.log, beside the API's (rockforge/app_logging.py). Not used
    by the in-process worker, which logs with the API."""
    from rockforge import app_logging

    app_logging.configure(settings.work_dir, level=settings.log_level,
                          file_name="rockforge-worker.log", loggers=("",))
    for line in app_logging.startup_lines("RockForge worker"):
        logger.info(line)

# WhisperX runs as a subprocess (avoids faster-whisper CUDA deadlock in Celery).
# 20 min ceiling: model download on first run + transcription of a long song.
WHISPERX_TIMEOUT_S = 1200

# No warm-up signal: the on_after_finalize/worker_ready CUDA probe was removed
# because two concurrent cuInit() calls (warm-up thread + first task) can deadlock
# on Windows. The first task pays the 30-60s CUDA init cost once; subsequent calls
# hit the @cache.


def _build_packager():  # noqa: ANN202 - heavy imports deferred to worker runtime
    from rockforge import runtime_settings
    from rockforge.infrastructure.packaging.wwise import WwiseWemConverter

    wem_converter = WwiseWemConverter(wwise_root=runtime_settings.wwise_root())

    if settings.psarc_mode == "native":
        from rockforge.infrastructure.packaging.psarc.packer import NativePsarcPacker

        return NativePsarcPacker(wem_converter=wem_converter)

    from rockforge.infrastructure.packaging.dlcbuilder import DlcBuilderPackager

    return DlcBuilderPackager(
        psarc_packer_cmd=settings.psarc_packer_cmd,
        wem_converter=wem_converter,
    )


def _resolve_device(requested: str) -> str:
    """Resolve a configured device to a concrete one for the ML adapters.

    "cpu"/"cuda" pass through unchanged; "auto" picks "cuda" when a usable
    CUDA GPU (NVIDIA) is present and "cpu" otherwise. Additionally, once the
    GPU has been recorded as broken on this machine (a native crash tripped the
    marker — see _cuda_broken_marker), a resolved "cuda" is downgraded to "cpu"
    so the whole ML stack (Demucs + WhisperX) stops retrying the flaky GPU.
    Delete the marker to re-enable the GPU after fixing the CUDA/cuDNN install.
    """
    dev = _detect_device(requested)
    if dev == "cuda" and _cuda_known_broken():
        return "cpu"
    return dev


@cache
def _detect_device(requested: str) -> str:
    """CUDA auto-detection (cached: the torch import + CUDA init are heavy).

    The torch import is deferred (worker-only) and any failure degrades to CPU —
    so "auto" is always safe even without the ml/lyrics extras installed.

    Cached per-process: torch import + CUDA init happen only once, not on
    every job (CUDA init on Windows can take 30–60s the first time).
    """
    if requested != "auto":
        return requested
    # Asked of the interpreter that runs the stages, not of this process: in the
    # .exe torch is only in the extra components' Python.
    from rockforge.infrastructure import ml_python

    return "cuda" if ml_python.cuda_available() else "cpu"


def _cuda_broken_marker() -> Path:
    """Marker file recording that the GPU ML path crashed on this machine.

    Both Demucs (torch) and WhisperX (faster-whisper/ctranslate2) can die with a
    NATIVE crash we can only observe after it happens — e.g. the Windows exit
    0xC0000409 from a torch/cuDNN mismatch on Turing / RTX 20-series cards. Once
    seen, we persist it here so `_resolve_device` downgrades the WHOLE ML stack
    (Demucs + WhisperX) to CPU on later runs — no more repeated GPU crashes.
    Delete the file to retry the GPU after fixing the CUDA/cuDNN install.
    """
    return settings.work_dir / ".gpu_ml_broken"


def _cuda_known_broken() -> bool:
    try:
        if _cuda_broken_marker().exists():
            return True
        # Honour the pre-generalisation marker so existing installs stay degraded.
        return (settings.work_dir / ".whisperx_cuda_broken").exists()
    except OSError:
        return False


def _mark_cuda_broken() -> None:
    try:
        m = _cuda_broken_marker()
        m.parent.mkdir(parents=True, exist_ok=True)
        m.touch()
    except OSError:
        pass


def _clear_cuda_broken() -> None:
    """Delete the GPU-broken marker(s) so the ML stack retries the GPU on the
    next run — after the user fixed their CUDA/cuDNN install. Also clears the
    cached device resolution so the change takes effect without a restart."""
    for p in (_cuda_broken_marker(), settings.work_dir / ".whisperx_cuda_broken"):
        with contextlib.suppress(OSError):
            p.unlink()
    _detect_device.cache_clear()


def _whisperx_attempts(device: str, configured: str) -> list[tuple[str, str]]:
    """The GPU→CPU escalation ladder for WhisperX transcription, as (device,
    compute_type) rungs tried in order. On the GPU, the configured compute type
    (usually float16) is tried first, then the more cuDNN-tolerant int8_float16
    — which dodges the native float16 crash on Turing / RTX 20-series — before
    falling back to CPU. When ``device`` is already ``"cpu"`` (no GPU, or the
    GPU-broken marker downgraded it), only the CPU rung remains."""
    attempts: list[tuple[str, str]] = []
    if device == "cuda":
        attempts.append(("cuda", configured))
        if configured.lower() != "int8_float16":
            attempts.append(("cuda", "int8_float16"))
    attempts.append(("cpu", ""))
    return attempts


def _demucs_stems_cache_dir(job_id: str) -> Path:
    """Shared Demucs working directory for a job's guitar-stem separation.

    Both detect_tones and separate_stems (demucs backend) run the same
    htdemucs_6s pass over the same normalized recording; pointing them at the
    same workdir/filename lets DemucsSeparator.separate_guitar's on-disk cache
    (an existing guitar.wav) skip the second, redundant multi-minute pass
    instead of the two tasks each separating the recording from scratch."""
    return settings.work_dir / job_id / "demucs_stems"


def _make_demucs(device: str) -> Any:  # heavy import deferred to worker
    """DemucsSeparator wired to trip the shared GPU-broken marker on a CUDA
    crash, so a native GPU failure retries on CPU AND later runs skip the GPU."""
    from rockforge.infrastructure.separation.demucs_adapter import DemucsSeparator

    return DemucsSeparator(device=device, on_cuda_crash=_mark_cuda_broken)


def _build_stem_separator() -> tuple[Any, str, str]:  # heavy imports deferred to worker
    """The configured stem separator for /separate-stems, with its resolved
    device and a human label for the log. ``demucs`` (default, one aggregated
    guitar stem) or the experimental ``banquet`` (query-based, finer classes)."""
    from rockforge import runtime_settings

    if runtime_settings.stem_separator() == "banquet":
        from rockforge.infrastructure.separation.banquet_adapter import BanquetSeparator

        repo, ckpt, queries = runtime_settings.banquet_paths()
        device = _resolve_device(settings.banquet_stem_device())
        return (
            BanquetSeparator(
                repo=repo,
                ckpt=ckpt,
                queries_dir=queries,
                device=device,
                batch_size=settings.banquet_batch_size,
            ),
            device,
            tr("banquet (separação fina, EM TESTES)", "banquet (fine separation, IN TESTING)"),
        )
    device = _resolve_device(settings.demucs_device)
    return _make_demucs(device), device, "demucs htdemucs_6s"


def _build_detection(device: str) -> tuple[Any, Any]:  # heavy imports deferred to worker
    # WhisperX itself runs in a subprocess (_whisperx_runner.py), not from here.
    from rockforge.infrastructure.normalize.ffmpeg import FfmpegNormalizer

    return FfmpegNormalizer(), _make_demucs(device)


def _build_gp_use_case():  # noqa: ANN202
    from rockforge.application.gp_pipeline import GenerateFromGpUseCase
    from rockforge.infrastructure.ingestion.sources import LocalFileIngestor
    from rockforge.infrastructure.normalize.ffmpeg import FfmpegNormalizer

    return GenerateFromGpUseCase(
        ingestor=LocalFileIngestor(),
        normalizer=FfmpegNormalizer(),
        packager=_build_packager(),
    )


def _gp_carries_sync(gp_path: Path) -> bool:
    """Whether a GP8 file carries its own audio sync points (synced in Guitar
    Pro). A hint for the checklist, so never a reason to fail a build."""
    from rockforge.infrastructure.gpimport.gpif_parser import sync_start_s

    try:
        return sync_start_s(gp_path) is not None
    except Exception:
        return False


class _ParamsWriter:
    """Writes a long task's changes to ``Job.params`` without undoing what the
    API wrote meanwhile.

    A task copies the params once and runs for minutes; writing that whole copy
    back on every progress line erased anything the user did in between — a
    cover uploaded, "Marcar como sincronizada", the main chart, tone swaps,
    "Instalar no jogo", another detection's status. Each commit re-reads the
    row's params and applies only the keys THIS task changed since its last
    commit (a fresh dict, as the JSON column needs)."""

    def __init__(self, session: Any, job: Job) -> None:
        self.session, self.job = session, job
        self.base: dict[str, Any] = copy.deepcopy(dict(job.params or {}))

    def commit(self, params: dict[str, Any]) -> None:
        self.session.refresh(self.job, attribute_names=["params"])
        current = dict(self.job.params or {})
        for key in set(self.base) | set(params):
            if key not in params:
                if key in self.base:
                    current.pop(key, None)
            elif key not in self.base or params[key] != self.base[key]:
                current[key] = copy.deepcopy(params[key])
        self.job.params = current
        self.session.commit()
        self.base = copy.deepcopy(params)


@celery_app.task(name="rockforge.generate_cdlc")
def generate_cdlc(job_id: str) -> None:
    session_factory = make_session_factory(settings.database_url)
    with session_factory() as session:
        job = session.get(Job, job_id)
        if job is None:  # deleted while queued — nothing to do
            return
        job.status = JobStatus.RUNNING
        session.commit()

        try:
            workdir = settings.work_dir / job.id
            workdir.mkdir(parents=True, exist_ok=True)
            # params is an untyped JSON boundary (values arrive as `object`);
            # cast once and coerce explicitly below. A COPY: the session keeps
            # the loaded dict as the column's committed value (expire_on_commit
            # is off), so writing into it in place made the later
            # `job.params = {**params}` compare equal to "what is already
            # stored" and never reach the database — the GP file's lyrics were
            # built into the bundle but never shown in the editor.
            params = dict(cast(dict[str, Any], job.params or {}))
            writer = _ParamsWriter(session, job)

            def on_stage(name: str) -> None:
                job.stage = name
                session.commit()

            cover_art: Path | None = None
            if params.get("cover_art"):
                candidate = Path(workdir) / cast(str, params["cover_art"])
                if candidate.exists():
                    cover_art = candidate

            if job.source_type == "gp":
                from rockforge.application.gp_pipeline import (
                    ArrangementSync,
                    ArrangementTones,
                    GenerateFromGpUseCase,
                    GpJobSpec,
                    NoteOverride,
                    track_merges,
                )
                from rockforge.domain.arrangement import ArrangementKind, Section, ToneChange
                from rockforge.domain.arrangement import SongMetadata as Meta
                from rockforge.domain.hand import HandPosition
                from rockforge.domain.music import BASS_REFERENCES, Technique
                from rockforge.infrastructure.packaging.gear.gear_catalogue import (
                    tones_from_dicts,
                )
                from rockforge.infrastructure.rsxml.vocals import events_from_dicts

                def _stages(raw: Any) -> list[list[tuple[float, float]]]:
                    return [
                        [(float(a[0]), float(a[1])) for a in stage] for stage in (raw or [])
                    ]

                gp_use_case: GenerateFromGpUseCase = _build_gp_use_case()
                spec = GpJobSpec(
                    gp_path=Path(params["gp_path"]),
                    audio_source=job.source,
                    lead_track=params.get("lead_track"),
                    rhythm_track=params.get("rhythm_track"),
                    combo_track=params.get("combo_track"),
                    alt_lead_track=params.get("alt_lead_track"),
                    alt_rhythm_track=params.get("alt_rhythm_track"),
                    bass_track=params.get("bass_track"),
                    merge_tracks=track_merges(params.get("merge_tracks")),
                    tuning_overrides={
                        k: tuple(int(x) for x in v)
                        for k, v in (params.get("tuning_overrides") or {}).items()
                        if len(v) == (4 if k == ArrangementKind.BASS.value else 6)
                    },
                    cent_offset=(
                        float(cast(float, params["cent_offset"]))
                        if isinstance(params.get("cent_offset"), (int, float)) else None
                    ),
                    bass_reference=(
                        str(params["bass_reference"])
                        if params.get("bass_reference") in BASS_REFERENCES else "auto"
                    ),
                    offset_s=float(params.get("offset_s", 0.0)),
                    lead_in_s=float(params.get("lead_in_s", 0.0)),
                    song_end_s=(
                        float(cast(float, params["song_end_s"]))
                        if isinstance(params.get("song_end_s"), (int, float))
                        and not isinstance(params.get("song_end_s"), bool)
                        and float(params["song_end_s"]) > 0 else None
                    ),
                    tempo_scale=float(params.get("tempo_scale", 1.0)),
                    lrc_text=params.get("lrc_text"),
                    tone_base=params.get("tone_base"),
                    tone_names=list(params.get("tone_names", [])),
                    tone_changes=[
                        ToneChange(time=float(c["time"]), name=str(c["name"]))
                        for c in params.get("tone_changes", [])
                    ],
                    tones=tones_from_dicts(list(params.get("tones") or [])),
                    sync_anchor_stages=_stages(params.get("sync_anchor_stages")),
                    arrangement_tones={
                        str(kind): ArrangementTones(
                            tone_base=ov.get("tone_base") or None,
                            tone_names=[str(n) for n in ov.get("tone_names") or []],
                            tone_changes=[
                                ToneChange(time=float(c["time"]), name=str(c["name"]))
                                for c in ov.get("tone_changes") or []
                            ],
                        )
                        for kind, ov in (params.get("arrangement_tones") or {}).items()
                        if isinstance(ov, dict)
                    },
                    arrangement_sync={
                        str(kind): ArrangementSync(
                            tempo_scale=float(ov.get("tempo_scale", 1.0)),
                            sync_anchor_stages=_stages(ov.get("sync_anchor_stages")),
                        )
                        for kind, ov in (params.get("arrangement_sync") or {}).items()
                    },
                    import_mute_techniques=bool(params.get("import_mute_techniques", True)),
                    bar_times=tuple(float(x) for x in params.get("bar_times") or ()),
                    section_overrides=(
                        [
                            Section(name=str(s["name"]), start_time=float(s["time"]), number=0)
                            for s in params["section_overrides"]
                        ]
                        if params.get("section_overrides") is not None
                        else None
                    ),
                    note_overrides={
                        kind: [
                            NoteOverride(
                                time=float(n["time"]),
                                string=int(n["string"]),
                                fret=int(n.get("fret", 0)),
                                sustain=float(n.get("sustain", 0.0)),
                                techniques=frozenset(
                                    Technique(t) for t in n.get("techniques", [])
                                ),
                                bend_semitones=float(n.get("bend_semitones", 0.0)),
                                slide_to_fret=(
                                    int(n["slide_to_fret"])
                                    if n.get("slide_to_fret") is not None
                                    else None
                                ),
                                deleted=bool(n.get("deleted", False)),
                                link_next=(
                                    bool(n["link_next"])
                                    if n.get("link_next") is not None else None
                                ),
                                slide_unpitch_to=(
                                    int(n["slide_unpitch_to"])
                                    if n.get("slide_unpitch_to") is not None else None
                                ),
                            )
                            for n in note_list
                        ]
                        for kind, note_list in (params.get("note_overrides") or {}).items()
                    },
                    hand_positions={
                        str(kind): [
                            HandPosition(
                                time=float(h["time"]), fret=int(h["fret"]),
                                width=int(h.get("width", 4)),
                            )
                            for h in rows
                        ]
                        for kind, rows in (params.get("hand_positions") or {}).items()
                        if isinstance(rows, list)
                    },
                    lyrics_events=(
                        events_from_dicts(params["lyrics_events"])
                        if params.get("lyrics_events")
                        else None
                    ),
                    cover_art=cover_art,
                    dynamic_difficulty=bool(params.get("dynamic_difficulty", True)),
                )
                result = gp_use_case.run(
                    spec=spec,
                    metadata=Meta(
                        title=job.title, artist=job.artist, album=job.album, year=job.year
                    ),
                    workdir=Path(workdir),
                    on_stage=on_stage,
                )
                job.status = JobStatus.COMPLETED
                job.warnings = list(result.warnings)
                job.note_counts = result.note_counts
                job.bundle_dir = str(result.packaging.bundle_dir)
                job.psarc_path = (
                    str(result.packaging.psarc_path) if result.packaging.psarc_path else None
                )
                # Surface GP-embedded lyrics in the "Letras" editor / tab viewer:
                # store them as lyrics_events (recording clock) so the user can
                # see/adjust them. Only when the user hasn't supplied their own.
                if result.gp_lyrics and not params.get("lyrics_events"):
                    params["lyrics_events"] = [
                        {"time": e.time, "length": e.length, "lyric": e.lyric}
                        for e in result.gp_lyrics
                    ]
                    # Timed on the score's notes: a sync correction of the chart
                    # has to move them too (the viewer does, while it is pending).
                    params["lyrics_follow_chart"] = True
                # The vocal line is re-read on every build (it follows the
                # sync corrections), so it is replaced, never kept from before.
                if result.vocal_melody:
                    params["vocal_melody"] = [
                        {"time": t, "length": ln, "midi": m}
                        for t, ln, m in result.vocal_melody
                    ]
                else:
                    params.pop("vocal_melody", None)
                params["gp_has_lyrics"] = result.gp_has_lyrics
                # Whether the .psarc has sound, and why not: a silent .psarc
                # must not read as playable, nor a failed conversion as "no Wwise".
                params["psarc_has_audio"] = result.packaging.wem_path is not None
                params["wem_error"] = result.packaging.wem_error
                # Synced to its audio in Guitar Pro 8: the file's own sync points
                # time the chart, which counts as synchronised (the checklist).
                params["gp_synced"] = _gp_carries_sync(Path(params["gp_path"]))
                writer.commit(params)
                return

            # Audio→note transcription was removed; only Guitar Pro jobs build an
            # arrangement. (Stem separation / tone / lyric detection run as their
            # own tasks on any job's recording — see separate_stems/detect_*.)
            raise ValueError(
                f"unsupported source_type {job.source_type!r}: only Guitar Pro "
                "jobs build an arrangement"
            )
        except Exception as exc:  # report faithfully; never mask failures
            job.status = JobStatus.FAILED
            job.error = f"{type(exc).__name__}: {exc}"
        session.commit()


def _append_log(params: dict[str, Any], key: str, message: str) -> None:
    """Append a timestamped line to the progress log ``params[key]``, capped to
    the most recent 50 entries so the job row doesn't grow unbounded."""
    log = cast("list[str]", params.get(key) or [])
    stamp = datetime.now(UTC).strftime("%H:%M:%S")
    params[key] = [*log, f"[{stamp}] {message}"][-50:]


def _log_lyrics_stage(params: dict[str, Any], message: str) -> None:
    _append_log(params, "lyrics_log", message)


def _whisperx_command(
    python: str,
    runner: Path,
    vocals: Path,
    output: Path,
    *,
    model: str,
    device: str,
    compute_type: str,
    align_json: Path | None = None,
) -> list[str]:
    """The runner invocation — transcription, or alignment of KNOWN lyrics when
    ``align_json`` names the lines to place (``/detect-lyrics`` with
    ``align_lines``)."""
    cmd = [
        python, str(runner),
        "--vocals", str(vocals),
        "--output", str(output),
        "--model", model,
        "--device", device,
        "--compute-type", compute_type,
    ]
    if align_json is not None:
        cmd += ["--align-json", str(align_json)]
    return cmd


@celery_app.task(name="rockforge.detect_lyrics", time_limit=3600, soft_time_limit=3540)
def detect_lyrics(job_id: str) -> None:
    """Detect lyrics from a job's source recording (Demucs vocals + WhisperX).

    Slow (minutes); progress is reported via params["lyrics_status"] rather
    than JobStatus, so it never hides a completed build or disables /arrangements.
    Human-readable progress is appended to params["lyrics_log"].

    time_limit=3600: Hard timeout at 60 minutes. If the task runs longer,
    Celery/worker will force-kill it — which skips the task's own except, so
    soft_time_limit=3540 raises SoftTimeLimitExceeded a minute earlier, inside
    the task, and the status ends "unavailable" instead of polling forever. In
    inprocess mode both are advisory only.
    """
    session_factory = make_session_factory(settings.database_url)
    with session_factory() as session:
        job = session.get(Job, job_id)
        if job is None:  # deleted while queued — nothing to do
            return
        job.stage = "lyrics"
        writer = _ParamsWriter(session, job)
        params = dict(job.params or {})
        warnings = list(job.warnings or [])
        params["lyrics_log"] = []
        _log_lyrics_stage(params, "lyric detection started")

        def _commit_params() -> None:
            """Every log/status update reaches the DB (a fresh dict — the JSON
            column has no mutation tracking), merged over what the API wrote."""
            writer.commit(params)

        try:
            _log_lyrics_stage(params, "loading ML models (can take 30–60s on first run)…")
            _commit_params()

            import time as _time

            _log_lyrics_stage(params, "importing torch + resolving device…")
            _commit_params()
            t0 = _time.monotonic()
            device = _resolve_device(settings.lyrics_device())
            _log_lyrics_stage(
                params,
                f"torch ready ({_time.monotonic() - t0:.1f}s) — "
                f"device: {device} ({'GPU' if device == 'cuda' else 'CPU'})",
            )
            _commit_params()

            _log_lyrics_stage(params, "importing demucs…")
            _commit_params()
            t0 = _time.monotonic()
            normalizer, separator = _build_detection(device)
            _log_lyrics_stage(
                params, f"demucs ready ({_time.monotonic() - t0:.1f}s)"
            )
            _commit_params()

            # Check whisperx availability in a subprocess to avoid the
            # known faster-whisper/ctranslate2 CUDA deadlock inside Celery
            # workers (faster-whisper #907, celery #3402).
            _log_lyrics_stage(params, "checking whisperx availability…")
            _commit_params()
            import subprocess as _sp

            from rockforge.infrastructure import ml_python as _mlpy

            # NOT sys.executable: in the standalone build that is the .exe, so
            # this would relaunch RockForge. The resolver returns the configured
            # ML interpreter there (and sys.executable everywhere else), which
            # is what lets the .exe detect lyrics at all.
            _python = _mlpy.resolve()
            whisperx_check = (
                _sp.run(
                    [_python, "-c", "import whisperx; print('ok')"],
                    capture_output=True, text=True, timeout=180,
                    stdin=_sp.DEVNULL,
                )
                if _python
                else None
            )
            whisperx_ok = whisperx_check is not None and whisperx_check.returncode == 0
            _log_lyrics_stage(
                params,
                "whisperx ready" if whisperx_ok
                else f"whisperx NOT available: {whisperx_check.stderr[:200]}"
                if whisperx_check is not None
                else _mlpy.missing_message(tr("A deteção de letra", "Lyric detection")),
            )
            _commit_params()

            if not whisperx_ok:
                warnings.append(
                    "lyric detection requested but whisperx is not installed "
                    "(pip install 'rockforge[lyrics]')"
                    if whisperx_check is not None
                    else _mlpy.missing_message(tr("A deteção de letra", "Lyric detection"))
                )
                params["lyrics_status"] = "unavailable"
                _log_lyrics_stage(params, "whisperx is not installed — aborting")
            else:
                # whisperx_ok implies the check ran, which implies an interpreter.
                assert _python is not None
                workdir = settings.work_dir / job.id / "lyrics"
                workdir.mkdir(parents=True, exist_ok=True)

                params["lyrics_status"] = "normalizing"
                _log_lyrics_stage(params, "normalizing source audio (ffmpeg)")
                _commit_params()
                normalized = normalizer.normalize(Path(job.source), workdir)

                params["lyrics_status"] = "separating"
                _log_lyrics_stage(
                    params,
                    "isolating vocals (Demucs, 2-stem) — can take a while",
                )
                _commit_params()
                vocals_stem = separator.separate_vocals(normalized, workdir)

                # Run WhisperX in a SUBPROCESS to avoid the CUDA init
                # deadlock (faster-whisper #907). The runner script imports
                # whisperx in a fresh process and writes JSON to a temp file.
                # With lyrics to align (found online, or already in the
                # editor) it places THOSE words instead of transcribing.
                import json as _json

                align = params.get("lyrics_align")
                align_json: Path | None = None
                if isinstance(align, dict) and align.get("lines"):
                    align_json = workdir / "align_lines.json"
                    align_json.write_text(_json.dumps(align, ensure_ascii=False), encoding="utf-8")
                    params["lyrics_status"] = "aligning"
                    _log_lyrics_stage(
                        params,
                        f"aligning {len(align['lines'])} known line(s) to the vocals "
                        f"(WhisperX, language '{align.get('language') or 'en'}')",
                    )
                else:
                    params["lyrics_status"] = "transcribing"
                    _log_lyrics_stage(
                        params,
                        f"transcribing (WhisperX/{settings.whisper_model}, subprocess)",
                    )
                _commit_params()
                events_json = workdir / "whisperx_events.json"
                runner = _mlpy.runner_path(
                    Path(__file__).resolve().parent.parent.parent
                    / "infrastructure" / "lyrics",
                    "_whisperx_runner.py",
                )

                def _run_whisperx(dev: str, compute: str):  # type: ignore[no-untyped-def]
                    return _sp.run(
                        _whisperx_command(
                            _python, runner, vocals_stem, events_json,
                            model=settings.whisper_model, device=dev,
                            compute_type=compute, align_json=align_json,
                        ),
                        capture_output=True, text=True,
                        stdin=_sp.DEVNULL, timeout=WHISPERX_TIMEOUT_S,
                    )

                from rockforge import runtime_settings

                configured = runtime_settings.whisperx_compute_type()  # "" = by device
                # Escalation ladder. The float16 GPU path is what crashes natively
                # on Turing / RTX 20-series (Windows exit 0xC0000409); try the more
                # cuDNN-tolerant int8_float16 on the GPU BEFORE giving up on it, and
                # only fall to CPU (marking the whole GPU stack broken) if that also
                # crashes. `device` is already CPU here when the marker is set
                # (_resolve_device honours it), so the GPU rungs are skipped then.
                attempts = _whisperx_attempts(device, configured)

                proc = None
                used: tuple[str, str] | None = None
                for i, (dev, compute) in enumerate(attempts):
                    if i > 0:
                        _log_lyrics_stage(
                            params,
                            f"retrying transcription on {dev}"
                            + (f" (compute_type={compute})" if compute else "")
                            + " (slower)" * (dev == "cpu"),
                        )
                        _commit_params()
                    proc = _run_whisperx(dev, compute)
                    if proc.returncode == 0:
                        used = (dev, compute)
                        break
                    if dev == "cuda":
                        # Native GPU crash (e.g. cuDNN/ctranslate2 mismatch).
                        _log_lyrics_stage(
                            params,
                            f"GPU transcription crashed (exit {proc.returncode}) with "
                            f"compute_type '{compute or 'float16'}'.",
                        )
                        _commit_params()

                assert proc is not None
                if proc.returncode != 0:
                    tail = (proc.stderr or "").strip()[-600:]
                    raise RuntimeError(
                        f"whisperx exited {proc.returncode}: {tail or '(no stderr output)'}"
                    )
                if used is not None and used[0] == "cpu" and device == "cuda":
                    # Even int8_float16 crashed on the GPU — degrade the whole ML
                    # stack to CPU on later runs (mirrors the Demucs marker).
                    _mark_cuda_broken()
                    _log_lyrics_stage(
                        params,
                        "GPU unusable for transcription — skipping it on later runs. "
                        "Tip: a CUDA build of WhisperX's cuDNN/ctranslate2 may be "
                        "missing/mismatched. Reactivate the GPU in ⚙️ Definições "
                        "after fixing it.",
                    )
                    _commit_params()
                elif used is not None and used[0] == "cuda" and used[1] != configured:
                    # A non-default GPU compute type worked — persist it so the next
                    # run uses it directly instead of re-crashing on float16 first.
                    saved = {**runtime_settings.load(), "whisperx_compute_type": used[1]}
                    runtime_settings.save(saved)
                    _log_lyrics_stage(
                        params,
                        f"GPU works with compute_type '{used[1]}' — saved it as the "
                        "default so future detections skip the float16 crash.",
                    )
                    _commit_params()

                raw_events = _json.loads(events_json.read_text(encoding="utf-8"))
                params["lyrics_events"] = raw_events
                # Timed to the RECORDING, so a chart correction must not move them.
                params["lyrics_follow_chart"] = False
                params["lyrics_status"] = "ready" if raw_events else "empty"
                _log_lyrics_stage(
                    params,
                    f"done — {len(raw_events)} word(s) "
                    + ("aligned" if align_json is not None else "detected"),
                )
        except Exception as exc:  # never crash the job over lyric detection
            params["lyrics_status"] = "unavailable"
            warnings.append(f"lyric detection failed: {type(exc).__name__}: {exc}")
            _log_lyrics_stage(params, f"failed: {type(exc).__name__}: {exc}")
        # One request, one run: a later plain "Detetar letra" must transcribe.
        params.pop("lyrics_align", None)
        job.warnings = list(warnings)
        writer.commit(params)


def _log_tone_stage(params: dict[str, Any], message: str) -> None:
    _append_log(params, "tone_detection_log", message)


@celery_app.task(name="rockforge.detect_tones", time_limit=3600, soft_time_limit=3540)
def detect_tones(job_id: str) -> None:
    """Detect guitar tone character from the recording (Demucs guitar separation
    + spectral analysis → preset suggestion).

    Slow (minutes for Demucs); progress tracked via
    params["tone_detection_status"]. Results land in params["detected_tones"]
    as lead + rhythm tone dicts ready for the tone editor.
    """
    session_factory = make_session_factory(settings.database_url)
    with session_factory() as session:
        job = session.get(Job, job_id)
        if job is None:
            return
        writer = _ParamsWriter(session, job)
        params = dict(job.params or {})
        warnings = list(job.warnings or [])
        params["tone_detection_log"] = []
        _log_tone_stage(params, "tone detection started")

        def _commit_params() -> None:
            writer.commit(params)

        try:
            _log_tone_stage(params, "importing ML models…")
            _commit_params()

            device = _resolve_device(settings.demucs_device)

            from rockforge.infrastructure.normalize.ffmpeg import FfmpegNormalizer

            normalizer = FfmpegNormalizer()
            separator = _make_demucs(device)

            # Shared with separate_stems (demucs backend) so a guitar stem
            # already separated by either task is reused, not recomputed.
            workdir = _demucs_stems_cache_dir(job.id)
            workdir.mkdir(parents=True, exist_ok=True)

            _log_tone_stage(
                params, f"device: {device} ({'GPU' if device == 'cuda' else 'CPU'})"
            )

            params["tone_detection_status"] = "normalizing"
            _log_tone_stage(params, "normalizing source audio (ffmpeg)")
            _commit_params()
            normalized = normalizer.normalize(Path(job.source), workdir)

            params["tone_detection_status"] = "separating"
            if separator.has_cached_guitar_stem(normalized, workdir):
                _log_tone_stage(params, "reusing an already-separated guitar stem")
            else:
                _log_tone_stage(params, "isolating guitar stem (Demucs, 6-stem)")
            _commit_params()
            guitar_stem = separator.separate_guitar(normalized, workdir)

            params["tone_detection_status"] = "analyzing"
            _log_tone_stage(params, "analyzing spectral characteristics")
            _commit_params()

            from rockforge.infrastructure.tone_analysis.analyzer import analyze_guitar_timeline

            profile, windows = analyze_guitar_timeline(guitar_stem)

            from rockforge.infrastructure.packaging.gear.tone_presets import rank_tones

            suggestion = rank_tones(
                profile.gain_level, profile.brightness, profile.low_end, profile.category
            )

            params["detected_tones"] = {
                "category": suggestion["category"],
                "lead": suggestion["lead"],
                "rhythm": suggestion["rhythm"],
                "lead_candidates": suggestion["lead_candidates"],
                "rhythm_candidates": suggestion["rhythm_candidates"],
                "profile": {
                    "gain_level": profile.gain_level,
                    "brightness": profile.brightness,
                    "low_end": profile.low_end,
                    "dynamic_range": profile.dynamic_range,
                    "flatness": profile.flatness,
                    "compression": profile.compression,
                },
                # The tone over time, in the RECORDING's clock (the stem is
                # the unpadded source): [t, gain, brightness, low end, active].
                # /tone-suggestions maps it onto the current build's parts.
                "timeline": [
                    [w.t, w.gain_level, w.brightness, w.low_end, 1 if w.active else 0]
                    for w in windows
                ],
            }
            params["tone_detection_status"] = "ready"
            heard = sum(1 for w in windows if w.active)
            _log_tone_stage(
                params, f"tone over time: {len(windows)} windows, guitar heard in {heard}"
            )
            _log_tone_stage(
                params,
                f"done — category: {profile.category} "
                f"(gain={profile.gain_level:.2f}, flatness={profile.flatness:.2f}, "
                f"compression={profile.compression:.2f}, brightness={profile.brightness:.2f})",
            )
        except Exception as exc:
            params["tone_detection_status"] = "unavailable"
            warnings.append(f"tone detection failed: {type(exc).__name__}: {exc}")
            _log_tone_stage(params, f"failed: {type(exc).__name__}: {exc}")
        job.warnings = list(warnings)
        writer.commit(params)


def _log_stems_stage(params: dict[str, Any], message: str) -> None:
    _append_log(params, "stems_log", message)


@celery_app.task(name="rockforge.separate_stems", time_limit=3600, soft_time_limit=3540)
def separate_stems(job_id: str) -> None:
    """Split the recording into per-instrument stems (Demucs htdemucs_6s) so the
    sync viewer can solo the guitar (or mute drums/vocals) while the user
    fine-tunes the note alignment by ear.

    Slow (minutes for Demucs); progress tracked via params["stems_status"]
    rather than JobStatus, so it never hides a completed build. The resulting
    stem paths land in params["stems"] as {name: absolute path}.

    Honest limit: Demucs separates by INSTRUMENT TYPE, not by individual track —
    the guitar stem is ALL guitars mixed together; Lead vs Rhythm cannot be split.
    """
    session_factory = make_session_factory(settings.database_url)
    with session_factory() as session:
        job = session.get(Job, job_id)
        if job is None:
            return
        writer = _ParamsWriter(session, job)
        params = dict(job.params or {})
        warnings = list(job.warnings or [])
        params["stems_log"] = []
        _log_stems_stage(params, "stem separation started")

        def _commit_params() -> None:
            writer.commit(params)

        try:
            _log_stems_stage(params, "importing ML models…")
            _commit_params()

            from rockforge.infrastructure.normalize.ffmpeg import FfmpegNormalizer

            normalizer = FfmpegNormalizer()
            separator, device, backend = _build_stem_separator()

            # The demucs backend shares detect_tones' workdir so an already
            # separated guitar stem is reused instead of recomputed (see
            # _demucs_stems_cache_dir). Banquet is a different, query-based
            # mechanism with its own incompatible output layout — keep it in
            # its own workdir.
            workdir = (
                _demucs_stems_cache_dir(job.id)
                if backend.startswith("demucs")
                else settings.work_dir / job.id / "stem_separation"
            )
            workdir.mkdir(parents=True, exist_ok=True)

            _log_stems_stage(
                params,
                f"backend: {backend} · device: {device} "
                f"({'GPU' if device == 'cuda' else 'CPU'})",
            )

            params["stems_status"] = "normalizing"
            _log_stems_stage(params, "normalizing source audio (ffmpeg)")
            _commit_params()
            normalized = normalizer.normalize(Path(job.source), workdir)

            params["stems_status"] = "separating"
            if backend.startswith("demucs") and separator.has_cached_guitar_stem(
                normalized, workdir
            ):
                _log_stems_stage(params, "reusing an already-separated guitar stem")
            else:
                _log_stems_stage(
                    params, "separating instruments (Demucs, 6-stem) — can take a while"
                )
            _commit_params()
            stems = separator.separate_stems(normalized, workdir)

            # Drop the drums stem: it's noise for sync-checking a guitar part and
            # the user asked not to keep it. Demucs still computes it (one pass),
            # we just don't reference/serve it.
            stems = {name: path for name, path in stems.items() if name != "drums"}

            params["stems"] = {name: str(path) for name, path in stems.items()}
            params["stems_status"] = "ready"
            _log_stems_stage(
                params,
                f"done — {len(stems)} stem(s): {', '.join(sorted(stems))}. "
                f"Note: the guitar stem is ALL guitars mixed (Lead+Rhythm can't be split).",
            )
        except Exception as exc:
            params["stems_status"] = "unavailable"
            warnings.append(f"stem separation failed: {type(exc).__name__}: {exc}")
            _log_stems_stage(params, f"failed: {type(exc).__name__}: {exc}")
        job.warnings = list(warnings)
        writer.commit(params)
