"""Per-measure timestamps from Songsterr — human-marked sync, fetched, not guessed.

Songsterr stores, for each song, the instant EVERY MEASURE starts in one or
more YouTube videos, marked by people. That is what makes a chart line up with
a recording "perfectly": nobody estimated anything. It is the principle behind
``teaqu/guitar-pro-youtube-sync``, which this module follows for the API shape
(``/api/meta/{id}`` for the latest revision, then
``/api/video-points/{id}/{revision}/list`` for the timestamps), and for which
video to prefer.

What RockForge takes is ONLY the timestamps. The recording comes from the user
(converted from that same YouTube video — Songsterr's own audio is a
different recording and does not match these times), so nothing here
downloads audio.

Honest limits, stated where they bite:

- **Undocumented API.** Songsterr publishes no API; these endpoints are what
  its own site uses. They can change or disappear without notice, and every
  failure here is a clear ``SongsterrError``, never a crash.
- **The times belong to ONE video.** A recording that is not that video's
  audio (a different upload, a trimmed copy) needs its start adjusted, and a
  different edit will drift.
- **Measure N must be measure N.** The times are per measure of Songsterr's
  tab, so the Guitar Pro file has to be that tab (exported from Songsterr, or
  built from it). The parser reports a bar-count mismatch.
"""

from __future__ import annotations

import json
import math
import re
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from rockforge.domain.errors import IngestionError

BASE_URL = "https://www.songsterr.com"
TIMEOUT_S = 20.0
# A plain browser UA: the site rejects some default library agents.
_USER_AGENT = "Mozilla/5.0 (RockForge)"


class SongsterrError(IngestionError):
    """Songsterr could not be reached, or answered in a shape we do not know."""


@dataclass(frozen=True)
class SongsterrVideo:
    video_id: str
    #: None for Songsterr's default video; otherwise e.g. "alternative",
    #: "backing", "solo", "playthrough".
    feature: str | None
    points: tuple[float, ...]

    @property
    def url(self) -> str:
        return f"https://youtu.be/{self.video_id}"


@dataclass(frozen=True)
class SongsterrSong:
    song_id: int
    revision_id: int
    title: str
    artist: str
    #: Most useful first — the same preference order the reference tool uses.
    videos: tuple[SongsterrVideo, ...]


def parse_song_id(text: str) -> int:
    """The numeric id from a Songsterr link (``…-tab-s23063``) or a bare number."""
    text = text.strip()
    if text.isdigit():
        return int(text)
    # The LAST "-s<digits>" — a slug may contain an earlier one by accident.
    found = re.findall(r"-s(\d+)", text)
    if found:
        return int(found[-1])
    raise SongsterrError(
        "não percebi o link do Songsterr — cola o endereço da música "
        "(termina em -s<número>, ex. …-tab-s23063) ou só o número"
    )


def _http_get_json(url: str) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise SongsterrError(f"o Songsterr respondeu {exc.code} a {url}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise SongsterrError(f"não consegui contactar o Songsterr ({exc})") from exc
    except ValueError as exc:
        raise SongsterrError(f"resposta do Songsterr ilegível em {url}") from exc


def _points(raw: Any) -> tuple[float, ...]:
    if not isinstance(raw, list):
        return ()
    out: list[float] = []
    for value in raw:
        try:
            f = float(value)
        except (TypeError, ValueError):
            return ()
        if not math.isfinite(f):
            return ()
        out.append(f)
    return tuple(out)


def _order(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Default video first, then alternatives (worldwide first), then the rest
    — guitar-pro-youtube-sync's ``select_video_entry`` order. Only entries
    Songsterr marks done count once past the default."""

    def rank(e: dict[str, Any]) -> tuple[int, int]:
        feature = e.get("feature")
        if feature is None:
            return (0, 0)
        if feature == "alternative":
            return (1, 0 if e.get("countries") == ["All"] else 1)
        return (2, 0)

    usable = [e for e in entries if e.get("feature") is None or e.get("status") == "done"]
    return sorted(usable, key=rank)


def fetch_song(
    song: str, *, get_json: Callable[[str], Any] = _http_get_json
) -> SongsterrSong:
    """Look a song up and return its videos with per-measure timestamps."""
    song_id = parse_song_id(song)
    meta = get_json(f"{BASE_URL}/api/meta/{song_id}")
    if not isinstance(meta, dict) or "revisionId" not in meta:
        raise SongsterrError("o Songsterr não devolveu a revisão da música (a API mudou?)")
    try:
        revision_id = int(meta["revisionId"])
    except (TypeError, ValueError) as exc:
        raise SongsterrError("revisão da música ilegível (a API mudou?)") from exc
    entries = get_json(f"{BASE_URL}/api/video-points/{song_id}/{revision_id}/list")
    if not isinstance(entries, list):
        raise SongsterrError("o Songsterr não devolveu a lista de vídeos (a API mudou?)")

    videos: list[SongsterrVideo] = []
    seen: set[tuple[str, str | None]] = set()
    for e in _order([e for e in entries if isinstance(e, dict)]):
        video_id = str(e.get("videoId") or "")
        points = _points(e.get("points"))
        feature = e.get("feature")
        key = (video_id, feature if isinstance(feature, str) else None)
        if not video_id or len(points) < 2 or key in seen:
            continue
        seen.add(key)
        videos.append(SongsterrVideo(video_id=video_id, feature=key[1], points=points))
    if not videos:
        raise SongsterrError(
            "esta música não tem tempos por compasso no Songsterr (nenhum vídeo sincronizado)"
        )
    return SongsterrSong(
        song_id=song_id,
        revision_id=revision_id,
        title=str(meta.get("title") or ""),
        artist=str(meta.get("artist") or ""),
        videos=tuple(videos),
    )
