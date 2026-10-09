"""The right answer: the notes of the user's own built, synced charts.

A completed Guitar Pro project's built XMLs carry every note exactly where the
game plays it — tempo, sync corrections, note edits applied — on the BUNDLE
clock, which is the recording plus the silence the build put in front of it
(``pad_start_s``, gp_pipeline). Subtracting that pad puts them on the
recording's own clock, the one a transcriber hears. A chart the user marked as
in sync is the trustworthy kind; the others are listed but flagged.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rockforge.application.gp_pipeline import MIN_LEAD_S
from rockforge.domain.arrangement import ArrangementKind
from rockforge.experimental.transcription.score import Note
from rockforge.infrastructure.rsxml.reader import read_arrangement_xml

# Alternate charts repeat a path that a main chart already plays: they count on
# their own but stay out of the song's combined guitar part.
MAIN_KINDS = (ArrangementKind.LEAD, ArrangementKind.RHYTHM, ArrangementKind.COMBINED)
SAME_NOTE_S = 0.02


@dataclass
class Chart:
    kind: ArrangementKind
    notes: list[Note]
    synced: bool


@dataclass
class Song:
    job_id: str
    title: str
    artist: str
    audio: Path | None
    pad_s: float
    charts: list[Chart] = field(default_factory=list)

    @property
    def label(self) -> str:
        return f"{self.artist} – {self.title}".strip(" –") or self.job_id

    def guitar_part(self) -> list[Note]:
        """Every note any main chart plays, once (Lead and Combined often share
        notes; a transcriber of the guitar stem hears each of them once)."""
        merged: list[Note] = []
        for note in sorted(
            (n for c in self.charts if c.kind in MAIN_KINDS for n in c.notes),
            key=lambda n: (n.pitch, n.time),
        ):
            last = merged[-1] if merged else None
            if last and last.pitch == note.pitch and note.time - last.time < SAME_NOTE_S:
                continue
            merged.append(note)
        return sorted(merged, key=lambda n: (n.time, n.pitch))


def _num(params: dict[str, Any], key: str) -> float:
    try:
        return float(params.get(key) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def pad_seconds(params: dict[str, Any]) -> float:
    return max(0.0, MIN_LEAD_S - _num(params, "offset_s")) + max(0.0, _num(params, "lead_in_s"))


def chart_kind(xml_path: Path) -> ArrangementKind | None:
    """The build names each chart's XML by its kind (arrangement_alternate_lead.xml)."""
    try:
        return ArrangementKind[xml_path.stem.removeprefix("arrangement_").upper()]
    except KeyError:
        return None


def read_chart(xml_path: Path, pad_s: float) -> list[Note]:
    arr = read_arrangement_xml(xml_path)
    return sorted(
        (Note(n.time - pad_s, arr.tuning.midi[n.string] + n.fret, n.string, n.fret)
         for n in arr.notes),
        key=lambda n: (n.time, n.pitch),
    )


def song_from_job(job_id: str, title: str, artist: str, source: str,
                  params: dict[str, Any], bundle_dir: str) -> Song:
    pad = pad_seconds(params)
    synced_kinds = set(params.get("synced_arrangements") or [])
    whole_song = bool(params.get("sync_confirmed"))
    audio = Path(source) if source and Path(source).is_file() else None
    song = Song(job_id, title, artist, audio, pad)
    for xml_path in sorted(Path(bundle_dir).glob("arrangement_*.xml")):
        kind = chart_kind(xml_path)
        if kind is None or ET.parse(xml_path).getroot().tag != "song":
            continue
        song.charts.append(Chart(kind, read_chart(xml_path, pad),
                                 whole_song or kind.value in synced_kinds))
    order = list(ArrangementKind)
    song.charts.sort(key=lambda c: order.index(c.kind))
    return song


def load_songs(database_url: str, only: Iterable[str] = ()) -> list[Song]:
    """Every completed Guitar Pro project with a built bundle (read only)."""
    from rockforge.infrastructure.db.models import Job, JobStatus, make_session_factory

    wanted = set(only)
    factory = make_session_factory(database_url)
    songs: list[Song] = []
    with factory() as session:
        for job in session.query(Job).order_by(Job.created_at):
            if job.status is not JobStatus.COMPLETED or not job.bundle_dir:
                continue
            if job.source_type != "gp" or (wanted and job.id not in wanted):
                continue
            if not Path(job.bundle_dir).is_dir():
                continue
            songs.append(song_from_job(job.id, job.title or "", job.artist or "",
                                       job.source or "", dict(job.params or {}), job.bundle_dir))
    return songs
