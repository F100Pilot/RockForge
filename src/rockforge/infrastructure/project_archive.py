"""A whole project in one file (``.rfproj``) — to move it to another computer,
keep a copy, or send it to someone.

The file is a ZIP: ``project.json`` (the song, and the job's ``params`` with
every correction made to it) and the files those corrections are about —
``files/recording.<ext>``, ``files/score.<ext>``, optionally
``files/cover.<ext>`` and ``files/stems/<name>.wav``. The built bundle is not
inside: an imported project is built again from the same params, so the file
stays small and never carries a build of an older RockForge.

Reading one is reading untrusted input — a project can come from anyone:
- only the member names above are read, and an output path is never built
  from a member name (a stem's name must match ``STEM_NAME`` first);
- ``params`` keep only the keys in ``PORTABLE_KEYS``: anything that names a
  file on the machine that exported it (the GP file, the stems, the copy
  installed in the game…) is dropped and set again by the importer, so an
  imported project can never point the server at a path of its choosing;
- sizes are capped as declared AND as read, ``NaN``/``Infinity`` refused, an
  encrypted member refused, a newer format refused with a sentence that says so.
"""

from __future__ import annotations

import json
import re
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rockforge import __version__, i18n

FORMAT = "rockforge-project"
FORMAT_VERSION = 1
SUFFIX = ".rfproj"

MANIFEST = "project.json"
MAX_MANIFEST_BYTES = 20 * 1024 * 1024
MAX_MEMBER_BYTES = 800 * 1024 * 1024
MAX_TOTAL_BYTES = 2 * 1024 * 1024 * 1024
MAX_STEMS = 8
STEM_NAME = re.compile(r"^[a-z0-9_]{1,32}$")

RECORDING_SUFFIXES = frozenset({
    ".mp3", ".flac", ".wav", ".ogg", ".m4a", ".aiff", ".aif",
    ".opus", ".webm", ".aac", ".mp4", ".wma",
})
GP_SUFFIXES = frozenset({".gp3", ".gp4", ".gp5", ".gp"})
COVER_SUFFIXES = frozenset({".jpg", ".jpeg", ".png"})

# Every params key that travels as it is: corrections, choices and results
# that mean the same on any machine. Anything else is either handled below
# (HANDLED_KEYS) or dropped — tests/test_project_archive.py fails when the code
# starts writing a key that is in neither list.
PORTABLE_KEYS = frozenset({
    "offset_s", "lead_in_s", "tempo_scale", "cent_offset",
    "sync_anchor_stages", "arrangement_sync", "sync_main",
    "sync_confirmed", "synced_arrangements", "gp_synced",
    "bar_times", "bar_times_source", "estimated_bars",
    "lead_track", "rhythm_track", "combo_track", "alt_lead_track", "alt_rhythm_track",
    "bass_track", "merge_tracks", "tuning_overrides", "bass_reference",
    "import_mute_techniques",
    "dynamic_difficulty",
    "recording_from_gp",
    "tones", "tone_base", "tone_names", "tone_changes", "arrangement_tones", "tone_swaps",
    "detected_tones",
    "lrc_text", "lyrics_events", "lyrics_follow_chart", "gp_has_lyrics", "vocal_melody",
    "section_overrides", "note_overrides", "hand_positions", "marked_attacks",
})
# Keys the importer sets itself (files of this machine), statuses kept only
# when they describe a finished result, and what belongs to one machine or one
# version chain (the copy in the game, the previous version, a build's outcome,
# the logs of background tasks, a one-shot alignment request).
FINISHED_STATUSES = {
    "lyrics_status": frozenset({"ready", "empty"}),
    "tone_detection_status": frozenset({"ready"}),
}
HANDLED_KEYS = frozenset({
    "gp_path", "cover_art", "stems", "stems_status",
    *FINISHED_STATUSES,
    "installed_psarc", "installed_from", "corrected_gp", "rebuilt_from",
    "psarc_has_audio", "wem_error",
    "lyrics_log", "tone_detection_log", "stems_log", "lyrics_align",
})


class ProjectArchiveError(ValueError):
    """The file is not a project this RockForge can import (already worded
    for the user, in their language)."""


@dataclass
class ProjectFiles:
    recording: Path
    score: Path
    cover: Path | None = None
    stems: dict[str, Path] = field(default_factory=dict)


def portable_params(params: dict[str, Any]) -> dict[str, Any]:
    """What of a job's params travels: the portable keys, and the statuses
    that describe a finished result."""
    out = {k: v for k, v in params.items() if k in PORTABLE_KEYS}
    for key, finished in FINISHED_STATUSES.items():
        if params.get(key) in finished:
            out[key] = params[key]
    return out


def file_name(artist: str, title: str) -> str:
    """``Artist - Title.rfproj`` with what a file name cannot hold replaced."""
    stem = " - ".join(p.strip() for p in (artist, title) if p and p.strip()) or "projeto"
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", stem).strip(" .")[:120] or "projeto"
    return stem + SUFFIX


def write_project(
    dest: Path, *, job: dict[str, Any], params: dict[str, Any], files: ProjectFiles
) -> None:
    """Write the project file. ``job`` holds title/artist/album/year/source_type;
    ``files`` must exist (the caller checked)."""
    members: dict[str, str] = {
        "recording": f"files/recording{files.recording.suffix.lower()}",
        "score": f"files/score{files.score.suffix.lower()}",
    }
    if files.cover is not None:
        members["cover"] = f"files/cover{files.cover.suffix.lower()}"
    stems = {n: p for n, p in sorted(files.stems.items()) if STEM_NAME.match(n)}
    manifest = {
        "format": FORMAT,
        "version": FORMAT_VERSION,
        "app_version": __version__,
        "exported_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "job": {k: job.get(k) for k in ("title", "artist", "album", "year", "source_type")},
        "params": portable_params(params),
        "files": {**members, "stems": {n: f"files/stems/{n}.wav" for n in stems}},
    }
    tmp = dest.with_name(dest.name + ".part")
    try:
        with zipfile.ZipFile(tmp, "w", allowZip64=True) as zf:
            zf.writestr(MANIFEST, json.dumps(manifest, ensure_ascii=False, indent=1),
                        compress_type=zipfile.ZIP_DEFLATED)
            # Audio is compressed already (or barely compresses): stored, fast.
            zf.write(files.recording, members["recording"], compress_type=zipfile.ZIP_STORED)
            zf.write(files.score, members["score"], compress_type=zipfile.ZIP_DEFLATED)
            if files.cover is not None:
                zf.write(files.cover, members["cover"], compress_type=zipfile.ZIP_STORED)
            for name, path in stems.items():
                zf.write(path, f"files/stems/{name}.wav", compress_type=zipfile.ZIP_STORED)
        tmp.replace(dest)
    finally:
        tmp.unlink(missing_ok=True)


@dataclass
class ImportedProject:
    """What a project file holds, checked; the files are read with
    ``extract``."""

    path: Path
    job: dict[str, Any]
    params: dict[str, Any]
    recording: str
    score: str
    cover: str | None
    stems: dict[str, str]
    app_version: str

    def extract(self, member: str, dest: Path) -> Path:
        """Copy one member to ``dest`` (a path the caller chose), stopping at
        ``MAX_MEMBER_BYTES`` however big it claims to be."""
        written = 0
        with zipfile.ZipFile(self.path) as zf, zf.open(member) as src, dest.open("wb") as out:
            while chunk := src.read(1024 * 1024):
                written += len(chunk)
                if written > MAX_MEMBER_BYTES:
                    out.close()
                    dest.unlink(missing_ok=True)
                    raise _error("um ficheiro do projeto é demasiado grande",
                                 "a file in the project is too large")
                out.write(chunk)
        return dest


def _error(pt: str, en: str) -> ProjectArchiveError:
    return ProjectArchiveError(i18n.tr(pt, en))


def _refuse_constant(name: str) -> Any:
    raise ValueError(f"{name} is not allowed")


def read_project(path: Path) -> ImportedProject:
    """Open and check a project file (nothing is extracted yet)."""
    not_ours = _error(
        "este ficheiro não é um projeto do RockForge (.rfproj)",
        "this file is not a RockForge project (.rfproj)",
    )
    try:
        zf = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError) as exc:
        raise not_ours from exc
    with zf:
        infos = {i.filename: i for i in zf.infolist() if not i.is_dir()}
        if any(i.flag_bits & 0x1 for i in infos.values()):
            raise _error("o projeto tem ficheiros protegidos por palavra-passe",
                         "the project has password-protected files")
        if sum(i.file_size for i in infos.values()) > MAX_TOTAL_BYTES:
            raise _error("o projeto é demasiado grande", "the project is too large")
        if any(i.file_size > MAX_MEMBER_BYTES for i in infos.values()):
            raise _error("um ficheiro do projeto é demasiado grande",
                         "a file in the project is too large")
        info = infos.get(MANIFEST)
        if info is None or info.file_size > MAX_MANIFEST_BYTES:
            raise not_ours
        try:
            manifest = json.loads(zf.read(info).decode("utf-8"), parse_constant=_refuse_constant)
        except (ValueError, UnicodeDecodeError) as exc:
            raise not_ours from exc

    if not isinstance(manifest, dict) or manifest.get("format") != FORMAT:
        raise not_ours
    version = manifest.get("version")
    if not isinstance(version, int) or version < 1:
        raise not_ours
    if version > FORMAT_VERSION:
        raise _error(
            "este projeto foi feito por uma versão mais recente do RockForge"
            " — atualiza para o abrir",
            "this project was made by a newer RockForge — update to open it",
        )
    raw_job = manifest.get("job")
    raw_params = manifest.get("params")
    if not isinstance(raw_job, dict) or not isinstance(raw_params, dict):
        raise not_ours
    if raw_job.get("source_type", "gp") != "gp":
        raise _error("só se importam projetos feitos a partir de um ficheiro Guitar Pro",
                     "only projects made from a Guitar Pro file can be imported")

    def text(key: str) -> str:
        value = raw_job.get(key)
        return value.strip()[:255] if isinstance(value, str) else ""

    year = raw_job.get("year")
    job = {
        "title": text("title"),
        "artist": text("artist"),
        "album": text("album"),
        "year": year if isinstance(year, int) and not isinstance(year, bool) and 0 < year < 10000
        else None,
    }
    if not job["title"] or not job["artist"]:
        raise not_ours

    def one(prefix: str, suffixes: frozenset[str]) -> str | None:
        found = [n for n in infos if n.startswith(prefix) and "/" not in n[len("files/"):]
                 and Path(n).suffix.lower() in suffixes and Path(n).stem == Path(prefix).name]
        return found[0] if len(found) == 1 else None

    recording = one("files/recording", RECORDING_SUFFIXES)
    score = one("files/score", GP_SUFFIXES)
    if recording is None:
        raise _error("o projeto não traz a gravação", "the project has no recording")
    if score is None:
        raise _error("o projeto não traz o ficheiro Guitar Pro",
                     "the project has no Guitar Pro file")
    stems: dict[str, str] = {}
    for name in sorted(infos):
        match = re.fullmatch(r"files/stems/([^/]+)\.wav", name)
        if match and STEM_NAME.match(match.group(1)):
            stems[match.group(1)] = name
    if len(stems) > MAX_STEMS:
        raise not_ours
    return ImportedProject(
        path=path,
        job=job,
        params=portable_params(raw_params),
        recording=recording,
        score=score,
        cover=one("files/cover", COVER_SUFFIXES),
        stems=stems,
        app_version=str(manifest.get("app_version") or "")[:40],
    )

