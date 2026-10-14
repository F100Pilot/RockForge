"""Song lyrics looked up on LRCLIB — found, then CHOSEN, then synchronised.

**LRCLIB** (``lrclib.net``, open, no key) stores lyrics per recording, often
with line-level timestamps (LRC, ``syncedLyrics``) and always the plain text
(``plainLyrics``). ``/api/search`` takes a track and artist name and returns
every matching entry; the user picks one, because a text match can return a
cover, a live take or a remaster whose timing differs.

The LRC timestamps are those of the recording LRCLIB's contributor used —
normally the official release. When the user's recording IS that release they
line up as they are; when it has a different intro (a YouTube upload, a fan
remix), the whole set needs a shift, and a different edit needs re-aligning,
which is what WhisperX forced alignment of the found text does
(``lyrics/whisperx_adapter.alignment_segments``).

Same honesty as ``album_lookup``: the sandbox's network policy blocks
lrclib.net, so the response shape comes from LRCLIB's documentation and the
tests use recorded-shape fakes. stdlib ``urllib``, no new dependency.
"""

from __future__ import annotations

import re
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from rockforge.domain.errors import IngestionError
from rockforge.i18n import tr
from rockforge.infrastructure._https import get_json as https_get_json
from rockforge.infrastructure.album_lookup import _same, primary_artist, search_title

LRCLIB_URL = "https://lrclib.net/api/search"
TIMEOUT_S = 15.0
MAX_CANDIDATES = 10
# LRCLIB asks clients to identify themselves with a name and a homepage.
_USER_AGENT = "RockForge (https://github.com/F100Pilot/RockForge)"


class LyricsLookupError(IngestionError):
    """LRCLIB could not be reached, or answered in a shape we do not know."""


@dataclass(frozen=True)
class LyricsCandidate:
    id: int
    track: str
    artist: str
    album: str
    #: The recording's length in seconds, as LRCLIB has it (None: unknown).
    duration: float | None
    #: LRC text with line timestamps, when the entry has them.
    synced: str | None
    #: The words without timing.
    plain: str | None
    instrumental: bool


def _http_get_json(url: str) -> Any:
    return https_get_json(
        url, user_agent=_USER_AGENT, timeout=TIMEOUT_S,
        error=LyricsLookupError, service=("LRCLIB", "LRCLIB"),
    )


def _text(value: Any) -> str | None:
    return value.strip() or None if isinstance(value, str) else None


def _candidates(data: Any, title: str, artist: str) -> list[LyricsCandidate]:
    if not isinstance(data, list):
        raise LyricsLookupError(tr(
            "o LRCLIB respondeu num formato desconhecido",
            "LRCLIB answered in an unknown format",
        ))
    out: list[LyricsCandidate] = []
    for r in data:
        if not isinstance(r, dict) or not isinstance(r.get("id"), int):
            continue
        track = str(r.get("trackName") or r.get("name") or "")
        found_artist = str(r.get("artistName") or "")
        if not (_same(track, title) and _same(found_artist, artist)):
            continue
        synced, plain = _text(r.get("syncedLyrics")), _text(r.get("plainLyrics"))
        instrumental = bool(r.get("instrumental"))
        if not (synced or plain or instrumental):
            continue
        duration = r.get("duration")
        out.append(LyricsCandidate(
            id=r["id"], track=track, artist=found_artist,
            album=str(r.get("albumName") or ""),
            duration=float(duration) if isinstance(duration, (int, float)) else None,
            synced=synced, plain=plain, instrumental=instrumental,
        ))
    return out


def search_lyrics(
    title: str,
    artist: str,
    duration: float | None = None,
    *,
    get_json: Callable[[str], Any] | None = None,
) -> list[LyricsCandidate]:
    """Lyrics candidates for a song, best first.

    Searched by the main artist and the title without a featuring credit (the
    same rule as the album lookup). Entries with timestamps come first, then
    the one whose length is closest to ``duration`` (the user's recording) —
    the likeliest to be the same edit. A song LRCLIB marks as instrumental is
    kept, so "no lyrics" is an answer rather than a silence.
    """
    get_json = get_json or _http_get_json
    title, artist = search_title(title), primary_artist(artist)
    if not title or not artist:
        raise LyricsLookupError(tr(
            "preciso do título e da banda para procurar",
            "I need the title and the band to search",
        ))
    query = urllib.parse.urlencode({"track_name": title, "artist_name": artist})
    found = _candidates(get_json(f"{LRCLIB_URL}?{query}"), title, artist)
    if not found:
        # The field search is exact-ish; the free-text one forgives a
        # slightly different spelling of either name.
        query = urllib.parse.urlencode({"q": f"{artist} {title}"})
        found = _candidates(get_json(f"{LRCLIB_URL}?{query}"), title, artist)

    def rank(c: LyricsCandidate) -> tuple[int, float]:
        gap = abs(c.duration - duration) if duration and c.duration else 9999.0
        return (0 if c.synced else 1 if c.plain else 2, gap)

    return sorted(found, key=rank)[:MAX_CANDIDATES]


# Stopwords per language WhisperX has a default alignment model for. Enough to
# tell these apart on a whole song's lyrics; anything else reads as English,
# which is also WhisperX's own default.
_STOPWORDS = {
    "pt": {"que", "não", "nao", "uma", "com", "para", "você", "voce", "meu", "minha",
           "está", "esta", "mas", "sem", "coração", "eu", "tu", "do", "da", "os", "é"},
    "es": {"que", "una", "con", "para", "pero", "mi", "tú", "yo", "está", "corazón",
           "los", "las", "del", "y", "el", "es", "como", "por"},
    "fr": {"je", "tu", "et", "le", "la", "les", "des", "une", "est", "pas", "que",
           "mon", "ma", "dans", "pour", "avec", "qui"},
    "de": {"ich", "du", "und", "der", "die", "das", "nicht", "ist", "ein", "eine",
           "mit", "mein", "dich", "mich", "sie", "auf"},
    "it": {"che", "non", "una", "con", "per", "il", "io", "tu", "mi", "sei", "della",
           "gli", "è", "come", "anche"},
    "en": {"the", "and", "you", "i", "me", "my", "is", "it", "to", "of", "in",
           "that", "your", "don't", "we", "on", "with"},
}


def guess_language(text: str) -> str:
    """The lyrics' language, for WhisperX's alignment model ('en' when unsure)."""
    # DISTINCT stopwords, so a refrain ("la la la") cannot outvote a verse.
    words = set(re.findall(r"[\w']+", text.casefold()))
    if not words:
        return "en"
    scores = {lang: len(words & stop) for lang, stop in _STOPWORDS.items()}
    best = max(scores, key=lambda lang: scores[lang])
    return best if scores[best] >= 3 else "en"
