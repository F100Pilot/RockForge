"""Where a project's Guitar Pro file comes from before the job exists: an upload,
a Songsterr tab, a PDF or picture of the tab, and the lookups the wizard runs
(Songsterr's per-measure times, the video's audio, the album)."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from rockforge import i18n
from rockforge.interfaces.api import app as api
from rockforge.interfaces.api.schemas import (
    AlbumCandidateOut,
    AlbumLookupOut,
    GpInspectOut,
    GpTrackOut,
    SongsterrImportIn,
    SongsterrOut,
    SongsterrVideoOut,
    YouTubeAudioIn,
    YouTubeAudioOut,
)

router = APIRouter()


@router.post("/gp/inspect", response_model=GpInspectOut)
def inspect_gp_file(file: UploadFile = File(...)) -> GpInspectOut:
    """Upload a Guitar Pro file, get its tracks for selection. The file is kept
    server-side and referenced by gp_token when creating the job."""
    suffix = Path(file.filename or "").suffix.lower()
    if suffix in api.GP_REJECTED_SUFFIXES:
        raise HTTPException(
            415,
            "GP6 (.gpx) is not supported (proprietary binary container). "
            "Export as GP5 or GP7 (.gp) from Guitar Pro or TuxGuitar and upload again.",
        )
    if suffix not in api.GP_SUFFIXES:
        raise HTTPException(415, f"unsupported Guitar Pro format: {suffix or '(none)'}")
    gp_dir = api.settings.work_dir / "gp"
    gp_dir.mkdir(parents=True, exist_ok=True)
    dest = gp_dir / f"{uuid.uuid4()}{suffix}"
    api._copy_upload_capped(file, dest)
    return _inspect_stored_gp(dest)


@router.get("/gp/bars")
def gp_bars(gp_token: str) -> dict[str, object]:
    """Notes per bar of every track of an inspected GP file — for the merge
    picker, before the job exists."""
    gp_path = api.settings.work_dir / "gp" / Path(gp_token).name
    if not gp_path.is_file():
        raise HTTPException(404, "gp_token not found — upload the GP file via /gp/inspect first")
    return _bar_map_or_422(gp_path)


def _bar_map_or_422(gp_path: Path) -> dict[str, object]:
    from rockforge.domain.errors import IngestionError

    try:
        return api._gp_bar_map(gp_path)
    except IngestionError as exc:
        raise HTTPException(422, str(exc)) from exc


def _inspect_stored_gp(dest: Path) -> GpInspectOut:
    """The wizard's track list for a GP file already stored under work_dir/gp."""
    from rockforge.domain.errors import IngestionError
    from rockforge.infrastructure.gpimport.parser import inspect_gp

    try:
        info = inspect_gp(dest)
    except IngestionError as exc:
        dest.unlink(missing_ok=True)
        raise HTTPException(422, str(exc)) from exc
    from rockforge.infrastructure.gpimport.gpif_parser import (
        BackingTrackInfo,
        backing_track,
        sync_start_s,
    )

    # Both are hints for the wizard, never a reason to refuse a file that parsed.
    try:
        synced_start = sync_start_s(dest)
    except Exception:
        synced_start = None
    try:
        backing = backing_track(dest)
    except Exception:
        backing = BackingTrackInfo()
    embedded = backing.audio
    return GpInspectOut(
        gp_token=dest.name,
        sync_start_s=synced_start,
        backing_youtube_url=backing.youtube_url,
        backing_external_path=backing.external_path,
        backing_disabled=backing.disabled,
        embedded_audio=(
            {"name": Path(embedded.member).name, "size_bytes": embedded.size_bytes}
            if embedded is not None
            else None
        ),
        title=info.title,
        artist=info.artist,
        album=info.album,
        tempo=info.tempo,
        has_lyrics=info.has_lyrics,
        tracks=[
            GpTrackOut(
                index=t.index,
                name=t.name,
                is_percussion=t.is_percussion,
                string_count=t.string_count,
                tuning_midi=list(t.tuning_midi),
            )
            for t in info.tracks
        ],
    )


@router.post("/youtube/audio", response_model=YouTubeAudioOut)
def youtube_audio(payload: YouTubeAudioIn) -> YouTubeAudioOut:
    """Fetch the audio of one YouTube video (the one Songsterr's bar times were
    marked on) with yt-dlp, for ``/jobs/gp``'s ``audio_token``. 422 for a bad id
    or browser name, 503 when yt-dlp is not installed, 502 when the download
    fails — its detail says when YouTube wants a browser login. See
    ``infrastructure/youtube_audio.py``."""
    from rockforge.infrastructure.youtube_audio import (
        COOKIE_BROWSERS,
        VIDEO_ID,
        YouTubeAudioError,
        YtDlpMissingError,
        download_audio,
    )

    if not VIDEO_ID.match(payload.video_id):
        raise HTTPException(422, "invalid YouTube video id")
    if payload.cookies_browser and payload.cookies_browser not in COOKIE_BROWSERS:
        raise HTTPException(422, f"unknown browser: {payload.cookies_browser}")
    try:
        path = download_audio(
            payload.video_id, api.settings.work_dir / "uploads",
            cookies_browser=payload.cookies_browser or None,
        )
    except YtDlpMissingError as exc:
        raise HTTPException(503, str(exc)) from exc
    except YouTubeAudioError as exc:
        hint = i18n.tr(
            " — o YouTube pediu uma sessão iniciada: escolhe um browser onde "
            "tenhas o YouTube aberto e tenta de novo",
            " — YouTube asked for a signed-in session: choose a browser where "
            "you have YouTube open and try again",
        ) if exc.needs_cookies else ""
        raise HTTPException(502, f"{exc}{hint}") from exc
    return YouTubeAudioOut(audio_token=path.name, name=path.name, size_bytes=path.stat().st_size)


@router.post("/songsterr/import", response_model=GpInspectOut)
def songsterr_import(payload: SongsterrImportIn) -> GpInspectOut:
    """Build a Guitar Pro file from a Songsterr tab, in place of uploading one.

    The tab's tracks are fetched (``songsterr.fetch_tab``), written as a GP5
    (``gpimport/songsterr_gp``) under ``work_dir/gp`` like an upload, and the
    answer is exactly ``/gp/inspect``'s — so the rest of the wizard, the job
    and every later tool see an ordinary GP file. No audio is fetched. 422 for
    a link we cannot read, 502 when Songsterr is unreachable or changed.
    """
    from rockforge.domain.errors import IngestionError
    from rockforge.infrastructure.gpimport.songsterr_gp import write_songsterr_gp5
    from rockforge.infrastructure.songsterr import SongsterrError, fetch_tab, parse_song_id

    try:
        parse_song_id(payload.song)
    except SongsterrError as exc:
        raise HTTPException(422, str(exc)) from exc
    try:
        tab = fetch_tab(payload.song)
    except SongsterrError as exc:
        raise HTTPException(502, str(exc)) from exc
    gp_dir = api.settings.work_dir / "gp"
    dest = gp_dir / f"{uuid.uuid4()}.gp5"
    try:
        report = write_songsterr_gp5(list(tab.parts), dest, title=tab.title, artist=tab.artist)
    except IngestionError as exc:
        dest.unlink(missing_ok=True)
        raise HTTPException(422, str(exc)) from exc
    out = _inspect_stored_gp(dest)
    warnings = list(report.warnings)
    if tab.missing:
        warnings.insert(
            0, i18n.tr("não consegui descarregar: ", "could not download: ")
            + ", ".join(tab.missing),
        )
    out.songsterr_song = str(tab.song_id)
    out.import_warnings = warnings
    return out


@router.post("/pdf/import", response_model=GpInspectOut)
def pdf_import(files: list[UploadFile] = File(...)) -> GpInspectOut:
    """Build a Guitar Pro file from a PDF or a picture of the tab, in place of
    uploading one — PDF-to-GP5's converter (the ``[pdf]`` extra), one file per
    track in order. The GP5 lands in ``work_dir/gp`` like an upload and the
    answer is ``/gp/inspect``'s, plus what the conversion warns about. 503
    without the extra, 413/415 for a file it would not take, 422 for one the
    converter refused (its own message, in the user's language).
    """
    from rockforge.infrastructure.gpimport import pdf_import as converter

    if not converter.available():
        raise HTTPException(503, converter.missing_message())
    if not files:
        raise HTTPException(422, i18n.tr("Nenhum ficheiro enviado.", "No file uploaded."))
    if len(files) > converter.MAX_FILES:
        raise HTTPException(
            422,
            i18n.tr(
                f"No máximo {converter.MAX_FILES} ficheiros (um por pista).",
                f"At most {converter.MAX_FILES} files (one per track).",
            ),
        )
    read: list[tuple[str, bytes]] = []
    total = 0
    for upload in files:
        name = Path(upload.filename or "").name
        data = upload.file.read(converter.MAX_FILE_BYTES + 1)
        total += len(data)
        if len(data) > converter.MAX_FILE_BYTES or total > converter.MAX_TOTAL_BYTES:
            raise HTTPException(
                413, i18n.tr(f"Ficheiro demasiado grande: {name}.", f"File too large: {name}.")
            )
        if converter.file_kind(data) is None:
            raise HTTPException(
                415,
                i18n.tr(
                    f"Não é um PDF nem uma imagem PNG, JPEG ou WebP: {name}.",
                    f"Not a PDF or a PNG, JPEG or WebP picture: {name}.",
                ),
            )
        read.append((name, data))
    try:
        result = converter.convert(read)
    except converter.PdfConverterMissingError as exc:
        raise HTTPException(503, str(exc)) from exc
    except converter.PdfImportError as exc:
        raise HTTPException(422, str(exc)) from exc
    gp_dir = api.settings.work_dir / "gp"
    gp_dir.mkdir(parents=True, exist_ok=True)
    dest = gp_dir / f"{uuid.uuid4()}.gp5"
    dest.write_bytes(result.gp5)
    out = _inspect_stored_gp(dest)
    out.pdf_files = [name for name, _ in read]
    out.import_warnings = result.warnings
    out.estimated_bars = result.estimated_bars
    return out


@router.get("/songsterr", response_model=SongsterrOut)
def songsterr_lookup(song: str) -> SongsterrOut:
    """Per-measure timestamps Songsterr's users marked for a song's videos.

    Only the times are fetched — the recording is the user's own, converted
    from that YouTube video (Songsterr's own audio is a different recording
    and does not match these times). The API is undocumented, so
    a changed or unreachable Songsterr is a 502 saying so, never a crash; a
    link we cannot read is a 422. See ``infrastructure/songsterr.py``.
    """
    from rockforge.infrastructure.songsterr import SongsterrError, fetch_song, parse_song_id

    try:
        parse_song_id(song)
    except SongsterrError as exc:
        raise HTTPException(422, str(exc)) from exc
    try:
        found = fetch_song(song)
    except SongsterrError as exc:
        raise HTTPException(502, str(exc)) from exc
    return SongsterrOut(
        song_id=found.song_id,
        revision_id=found.revision_id,
        title=found.title,
        artist=found.artist,
        videos=[
            SongsterrVideoOut(
                video_id=v.video_id, url=v.url, feature=v.feature, points=list(v.points)
            )
            for v in found.videos
        ],
    )


@router.get("/album-lookup", response_model=AlbumLookupOut)
def album_lookup(title: str = "", artist: str = "") -> AlbumLookupOut:
    """Album name, year and cover candidates for a song, for the user to choose.

    Asks the iTunes Search API and MusicBrainz/Cover Art Archive (no keys);
    nothing is written anywhere until the user picks one. No results is an
    empty list; both services unreachable is a 502. See
    ``infrastructure/album_lookup.py``.
    """
    from rockforge.infrastructure.album_lookup import (
        AlbumLookupError,
        primary_artist,
        search_albums,
        search_title,
    )

    if not title.strip() or not artist.strip():
        raise HTTPException(422, "title and artist are required to look up an album")
    failures: list[str] = []
    try:
        found = search_albums(title, artist, failures=failures)
    except AlbumLookupError as exc:
        raise HTTPException(502, str(exc)) from exc
    return AlbumLookupOut(
        candidates=[AlbumCandidateOut(**vars(c)) for c in found],
        searched_title=search_title(title),
        searched_artist=primary_artist(artist),
        failures=failures,
    )
