"""Per-measure timestamps from Songsterr — human-marked sync, fetched, not guessed.

Songsterr stores, for each song, the instant EVERY MEASURE starts in one or
more YouTube videos, marked by people. That is what makes a chart line up with
a recording "perfectly": nobody estimated anything. It is the principle behind
``teaqu/guitar-pro-youtube-sync``, which this module follows for the API shape
(``/api/meta/{id}`` for the latest revision, then
``/api/video-points/{id}/{revision}/list`` for the timestamps), and for which
video to prefer.

What this module takes is ONLY the timestamps (and, in ``fetch_tab``, the tab).
The recording must be that same YouTube video's audio — Songsterr's own audio
is a different recording and does not match these times — which
``youtube_audio`` fetches, or the user converts; nothing HERE downloads audio.

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

import math
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import requests

from rockforge.domain.errors import IngestionError
from rockforge.i18n import tr
from rockforge.infrastructure._https import network_error_message

BASE_URL = "https://www.songsterr.com"
TIMEOUT_S = 20.0


class SongsterrError(IngestionError):
    """Songsterr could not be reached, or answered in a shape we do not know."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        #: The HTTP status when the failure was an HTTP answer (403, 404…).
        self.status = status


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
    raise SongsterrError(tr(
        "não percebi o link do Songsterr — cola o endereço da música "
        "(termina em -s<número>, ex. …-tab-s23063) ou só o número",
        "could not read the Songsterr link — paste the song's address "
        "(it ends in -s<number>, e.g. …-tab-s23063) or just the number",
    ))


# What Songsterr's API says when it refuses a song, in the user's language.
# It answers JSON with a ``code`` (seen: ERR_UNPUBLISHED on a 403 for a tab
# only its author may view); anything else is shown with its own ``reason``.
# A function, not a table built at import, so it reads the language of the
# request asking.
def _refusal_code(code: str) -> str | None:
    if code == "ERR_UNPUBLISHED":
        return tr(
            "esta tab do Songsterr não está publicada — só o autor a pode ver. "
            "Usa o link de uma tab publicada da mesma música",
            "this Songsterr tab is not published — only its author can see it. "
            "Use the link of a published tab of the same song",
        )
    return None


def _refusal(response: Any, url: str) -> str:
    try:
        body = response.json()
    except ValueError:
        body = None
    if isinstance(body, dict):
        known = _refusal_code(str(body.get("code") or ""))
        if known:
            return known
        reason = body.get("reason") or body.get("error")
        if isinstance(reason, str) and reason.strip():
            return tr(
                f"o Songsterr recusou ({response.status_code}): {reason.strip()}",
                f"Songsterr refused ({response.status_code}): {reason.strip()}",
            )
    return tr(
        f"o Songsterr respondeu {response.status_code} a {url}",
        f"Songsterr answered {response.status_code} to {url}",
    )


def _revision(meta: Any) -> int:
    if not isinstance(meta, dict) or "revisionId" not in meta:
        raise SongsterrError(tr(
            "o Songsterr não devolveu a revisão da música (a API mudou?)",
            "Songsterr did not return the song's revision (did the API change?)",
        ))
    try:
        return int(meta["revisionId"])
    except (TypeError, ValueError) as exc:
        raise SongsterrError(tr(
            "revisão da música ilegível (a API mudou?)",
            "unreadable song revision (did the API change?)",
        )) from exc


def _http_get_json(url: str) -> Any:
    # ``requests`` with its DEFAULT headers, exactly as
    # teaqu/guitar-pro-youtube-sync fetches these same endpoints — the client
    # proven to get answers from the user's machine.
    try:
        response = requests.get(url, timeout=TIMEOUT_S)
    except requests.RequestException as exc:
        raise SongsterrError(network_error_message(exc, "Songsterr")) from exc
    if response.status_code >= 400:
        raise SongsterrError(_refusal(response, url), response.status_code)
    try:
        return response.json()
    except ValueError as exc:
        raise SongsterrError(tr(
            f"resposta do Songsterr ilegível em {url}",
            f"unreadable answer from Songsterr at {url}",
        )) from exc


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
    revision_id = _revision(meta)
    entries = get_json(f"{BASE_URL}/api/video-points/{song_id}/{revision_id}/list")
    if not isinstance(entries, list):
        raise SongsterrError(tr(
            "o Songsterr não devolveu a lista de vídeos (a API mudou?)",
            "Songsterr did not return the list of videos (did the API change?)",
        ))

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
        raise SongsterrError(tr(
            "esta música não tem tempos por compasso no Songsterr (nenhum vídeo sincronizado)",
            "this song has no per-bar times on Songsterr (no synced video)",
        ))
    return SongsterrSong(
        song_id=song_id,
        revision_id=revision_id,
        title=str(meta.get("title") or ""),
        artist=str(meta.get("artist") or ""),
        videos=tuple(videos),
    )


# The tab itself — the JSON "parts" Songsterr's own player draws each track
# from. They are served from CloudFront, not www.songsterr.com; these are the
# distributions the player's bundle names (read from guitar-pro-youtube-sync,
# which found them there). A revision with an ``image`` hash uses the first
# list, an older one without it the second; each list is tried in turn because
# a distribution answers 403 for revisions it does not hold. If Songsterr moves
# them, every attempt fails and the error says so — nothing is guessed.
_PART_CDNS = ("dqsljvtekg760", "d34shlm8p2ums2", "d3cqchs6g3b5ew")
_PART_CDNS_STAGE = ("d3d3l6a6rcgkaf",)
_PART_CDNS_LEGACY = ("d3rrfvx08uyjp1", "dodkcbujl0ebx", "dj1usja78sinh")


@dataclass(frozen=True)
class SongsterrTab:
    song_id: int
    revision_id: int
    title: str
    artist: str
    #: One JSON part per track, in Songsterr's order; None for a track that
    #: could not be fetched (named in ``missing``).
    parts: tuple[dict[str, Any], ...]
    missing: tuple[str, ...]


def part_urls(song_id: int, revision_id: int, image: str | None, index: int) -> list[str]:
    """Every address a track's part may be at, in the order to try them."""
    if image:
        cdns = _PART_CDNS_STAGE if image.endswith("-stage") else _PART_CDNS
        return [f"https://{c}.cloudfront.net/{song_id}/{revision_id}/{image}/{index}.json"
                for c in cdns]
    return [f"https://{c}.cloudfront.net/part/{revision_id}/{index}" for c in _PART_CDNS_LEGACY]


def fetch_tab(
    song: str, *, get_json: Callable[[str], Any] = _http_get_json
) -> SongsterrTab:
    """The tab of a Songsterr song — every track's part, for writing a GP file."""
    song_id = parse_song_id(song)
    meta = get_json(f"{BASE_URL}/api/meta/{song_id}")
    revision_id = _revision(meta)
    tracks = meta.get("tracks")
    if not isinstance(tracks, list) or not tracks:
        raise SongsterrError(tr(
            "o Songsterr não devolveu as pistas da música (a API mudou?)",
            "Songsterr did not return the song's tracks (did the API change?)",
        ))
    image = meta.get("image") if isinstance(meta.get("image"), str) else None

    parts: list[dict[str, Any]] = []
    missing: list[str] = []
    for index, info in enumerate(tracks):
        fallback = tr(f"Pista {index + 1}", f"Track {index + 1}")
        name = str(info.get("name") or info.get("instrument") or fallback) \
            if isinstance(info, dict) else fallback
        part: dict[str, Any] | None = None
        for url in part_urls(song_id, revision_id, image, index):
            try:
                got = get_json(url)
            except SongsterrError as exc:
                if exc.status in (403, 404):
                    continue  # not on this distribution — try the next one
                raise
            if isinstance(got, dict):
                part = got
                break
        if part is None:
            missing.append(name)
            continue
        part.setdefault("name", name)
        if isinstance(info, dict):
            for key in ("instrument", "tuning", "strings"):
                if key in info:
                    part.setdefault(key, info[key])
        parts.append(part)
    if not parts:
        raise SongsterrError(tr(
            "não consegui descarregar nenhuma pista desta tab — o Songsterr pode ter "
            "mudado onde as guarda",
            "could not download any track of this tab — Songsterr may have "
            "changed where it keeps them",
        ))
    return SongsterrTab(
        song_id=song_id,
        revision_id=revision_id,
        title=str(meta.get("title") or ""),
        artist=str(meta.get("artist") or ""),
        parts=tuple(parts),
        missing=tuple(missing),
    )
