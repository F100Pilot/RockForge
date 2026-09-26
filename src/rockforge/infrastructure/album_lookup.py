"""Album name, year and cover art for a song — looked up, never invented.

Two free services that need no key are asked, and the user CHOOSES between
what they return; nothing is written into a project without that choice:

- **iTunes Search API** (Apple, documented: ``itunes.apple.com/search``): one
  request returns the album (``collectionName``), the release date and an
  artwork URL. The documented field is ``artworkUrl100`` (100 px); the same
  path with ``600x600bb`` in place of ``100x100bb`` is the larger rendition
  Apple's CDN serves — widely relied on, but not in the documentation, so a
  URL that does not follow that pattern is kept at its documented size.
- **MusicBrainz** (open data, documented ``/ws/2/recording`` search) for the
  releases a recording appears on, and the **Cover Art Archive** for their
  front covers (``/release/<mbid>/front-500``). Not every release has a cover
  there; the UI simply drops an image that does not load.

Honest limits: the match is by title and artist text, so a cover song, a
remaster or a compilation can come back first — which is why the result is a
LIST to choose from. **Never verified against the live services from here**:
the sandbox's network policy blocks all of them, so the response shapes come
from the services' documentation and the tests use recorded-shape fakes.
Downloading a chosen cover goes through ``fetch_cover``, which only follows
URLs on these services' own image hosts.
"""

from __future__ import annotations

import json
import re
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import IO, Any

from rockforge.domain.errors import IngestionError

ITUNES_URL = "https://itunes.apple.com/search"
MUSICBRAINZ_URL = "https://musicbrainz.org/ws/2/recording/"
COVER_ART_URL = "https://coverartarchive.org/release"
TIMEOUT_S = 15.0
MAX_CANDIDATES = 12
MAX_COVER_BYTES = 10 * 1024 * 1024
# MusicBrainz asks every client for a meaningful User-Agent with a contact.
_USER_AGENT = "RockForge ( https://github.com/F100Pilot/RockForge )"

# The only hosts a chosen cover may be downloaded from (and redirected to):
# Apple's artwork CDN and the Cover Art Archive, which redirects into
# archive.org. Anything else is refused, so the download can never be pointed
# at an arbitrary address.
_COVER_HOST_SUFFIXES = (".mzstatic.com", ".archive.org")
_COVER_HOSTS = {"coverartarchive.org", "archive.org"}


class AlbumLookupError(IngestionError):
    """The services could not be reached, or a cover could not be fetched."""


@dataclass(frozen=True)
class AlbumCandidate:
    source: str  # "itunes" | "musicbrainz"
    album: str
    artist: str
    year: int | None
    #: The image to download when this candidate is chosen (None: no cover).
    cover_url: str | None
    #: A small rendition for the list the user chooses from.
    thumb_url: str | None
    #: The track title the service matched, so a wrong match is visible.
    track: str
    #: "album", "single", "compilation"… as far as the service says.
    kind: str


def _http_get_json(url: str) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise AlbumLookupError(f"o serviço respondeu {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise AlbumLookupError(f"não consegui contactar o serviço ({exc})") from exc
    except ValueError as exc:
        raise AlbumLookupError("resposta ilegível do serviço") from exc


def _year(date: Any) -> int | None:
    match = re.match(r"(\d{4})", str(date or ""))
    if not match:
        return None
    year = int(match.group(1))
    return year if 1900 <= year <= 2100 else None


def _same(a: str, b: str) -> bool:
    """Loose text match: case- and accent-insensitive containment either way."""
    def norm(s: str) -> str:
        plain = "".join(
            ch for ch in unicodedata.normalize("NFKD", s) if not unicodedata.combining(ch)
        )
        return re.sub(r"[^\w]+", " ", plain.casefold()).strip()

    x, y = norm(a), norm(b)
    return bool(x and y) and (x in y or y in x)


# "Eminem feat. Avril Lavigne": the catalogues file the recording under the
# main artist, and a search term carrying the whole credit can miss it. Only
# the unambiguous featuring markers split the credit — "&" and "," are part of
# real band names ("Simon & Garfunkel", "Earth, Wind & Fire").
_FEATURING = re.compile(r"\s*[\(\[]?\s*\b(?:feat\.?|ft\.?|featuring)\s.*$", re.IGNORECASE)


def primary_artist(artist: str) -> str:
    """The credit without its featured artists: what the catalogues search by."""
    return _FEATURING.sub("", artist).strip() or artist.strip()


def search_title(title: str) -> str:
    """The title without a "(feat. …)" credit tacked on."""
    return _FEATURING.sub("", title).strip() or title.strip()


def _itunes(title: str, artist: str, get_json: Callable[[str], Any]) -> list[AlbumCandidate]:
    query = urllib.parse.urlencode(
        {"term": f"{artist} {title}", "media": "music", "entity": "song", "limit": 25}
    )
    data = get_json(f"{ITUNES_URL}?{query}")
    results = data.get("results") if isinstance(data, dict) else None
    if not isinstance(results, list):
        raise AlbumLookupError("o iTunes respondeu num formato desconhecido")
    out: list[AlbumCandidate] = []
    for r in results:
        if not isinstance(r, dict) or r.get("kind") != "song":
            continue
        track, found_artist = str(r.get("trackName") or ""), str(r.get("artistName") or "")
        album = str(r.get("collectionName") or "").strip()
        if not album or not (_same(track, title) and _same(found_artist, artist)):
            continue
        thumb = r.get("artworkUrl100")
        thumb = thumb if isinstance(thumb, str) and thumb.startswith("https://") else None
        cover = thumb.replace("100x100bb", "600x600bb") if thumb else None
        kind = "single" if album.endswith(" - Single") else (
            "compilation" if r.get("collectionArtistName") else "album")
        out.append(AlbumCandidate(
            source="itunes", album=album, artist=found_artist, year=_year(r.get("releaseDate")),
            cover_url=cover, thumb_url=thumb, track=track, kind=kind,
        ))
    return out


def _lucene_phrase(text: str) -> str:
    return '"' + text.replace("\\", " ").replace('"', " ").strip() + '"'


def _musicbrainz(
    title: str, artist: str, get_json: Callable[[str], Any]
) -> list[AlbumCandidate]:
    query = urllib.parse.urlencode({
        "query": f"recording:{_lucene_phrase(title)} AND artist:{_lucene_phrase(artist)}",
        "fmt": "json",
        "limit": 10,
    })
    data = get_json(f"{MUSICBRAINZ_URL}?{query}")
    recordings = data.get("recordings") if isinstance(data, dict) else None
    if not isinstance(recordings, list):
        raise AlbumLookupError("o MusicBrainz respondeu num formato desconhecido")
    out: list[AlbumCandidate] = []
    for rec in recordings:
        if not isinstance(rec, dict):
            continue
        credit = rec.get("artist-credit") or []
        found_artist = " ".join(
            str(c.get("name") or "") for c in credit if isinstance(c, dict)
        ).strip() or artist
        track = str(rec.get("title") or "")
        if not _same(track, title):
            continue
        for rel in rec.get("releases") or []:
            if not isinstance(rel, dict) or not rel.get("id"):
                continue
            if rel.get("status") not in (None, "Official"):
                continue
            group = rel.get("release-group") or {}
            kind = str(group.get("primary-type") or "").lower() or "album"
            if "Compilation" in (group.get("secondary-types") or []):
                kind = "compilation"
            mbid = urllib.parse.quote(str(rel["id"]), safe="")
            out.append(AlbumCandidate(
                source="musicbrainz", album=str(rel.get("title") or "").strip(),
                artist=found_artist, year=_year(rel.get("date")),
                cover_url=f"{COVER_ART_URL}/{mbid}/front-500",
                thumb_url=f"{COVER_ART_URL}/{mbid}/front-250",
                track=track, kind=kind,
            ))
    return [c for c in out if c.album]


_KIND_RANK = {"album": 0, "ep": 1, "single": 2, "compilation": 3}


def search_albums(
    title: str,
    artist: str,
    *,
    get_json: Callable[[str], Any] | None = None,
    failures: list[str] | None = None,
) -> list[AlbumCandidate]:
    """Candidates for the song's album, year and cover, best first.

    Albums before singles before compilations, and the earliest year first
    within each (a later date is usually a reissue); one service failing still
    returns the other's answers (its reason appended to ``failures``, so an
    empty list is never mistaken for "not in that catalogue"), both failing
    raises ``AlbumLookupError``. The search is by the MAIN artist and the title
    without a featuring credit.
    """
    get_json = get_json or _http_get_json
    title, artist = search_title(title), primary_artist(artist)
    if not title or not artist:
        raise AlbumLookupError("preciso do título e da banda para procurar")
    found: list[AlbumCandidate] = []
    errors: list[str] = []
    for name, source in (("iTunes", _itunes), ("MusicBrainz", _musicbrainz)):
        try:
            found.extend(source(title, artist, get_json))
        except AlbumLookupError as exc:
            errors.append(f"{name}: {exc}")
    if len(errors) == 2:
        raise AlbumLookupError("; ".join(errors))
    if failures is not None:
        failures.extend(errors)

    seen: set[tuple[str, str, int | None]] = set()
    unique: list[AlbumCandidate] = []
    for c in found:
        key = (c.source, c.album.casefold(), c.year)
        if key not in seen:
            seen.add(key)
            unique.append(c)
    unique.sort(key=lambda c: (_KIND_RANK.get(c.kind, 4), c.year or 9999))
    return unique[:MAX_CANDIDATES]


def cover_url_allowed(url: str) -> bool:
    """Whether a cover may be downloaded from (or redirected to) this URL."""
    parts = urllib.parse.urlsplit(url)
    host = (parts.hostname or "").lower()
    return parts.scheme == "https" and (
        host in _COVER_HOSTS or any(host.endswith(s) for s in _COVER_HOST_SUFFIXES)
    )


class _AllowlistRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]  # noqa: ANN001, ANN201, PLR0913
        if not cover_url_allowed(newurl):
            raise AlbumLookupError("a capa redirecionou para um endereço não permitido")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def read_capped(stream: IO[bytes], limit: int = MAX_COVER_BYTES) -> bytes:
    data = stream.read(limit + 1)
    if len(data) > limit:
        raise AlbumLookupError("a imagem da capa é demasiado grande")
    return data


def _open_url(url: str) -> bytes:
    opener = urllib.request.build_opener(_AllowlistRedirects)
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with opener.open(request, timeout=TIMEOUT_S) as response:
            return read_capped(response)
    except urllib.error.HTTPError as exc:
        raise AlbumLookupError(f"a capa não está disponível ({exc.code})") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise AlbumLookupError(f"não consegui descarregar a capa ({exc})") from exc


def image_suffix(data: bytes) -> str | None:
    """``.jpg``/``.png`` from the file's own bytes — the URL's name proves nothing."""
    if data[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    return None


def fetch_cover(
    url: str, *, open_url: Callable[[str], bytes] | None = None
) -> tuple[bytes, str]:
    """Download a chosen cover: its bytes and ``.jpg``/``.png`` suffix."""
    if not cover_url_allowed(url):
        raise AlbumLookupError("esse endereço de capa não é de um serviço conhecido")
    # Resolved at call time (not as a default argument) so the one network
    # function can be replaced as a whole.
    data = (open_url or _open_url)(url)
    suffix = image_suffix(data)
    if suffix is None:
        raise AlbumLookupError("o endereço não devolveu uma imagem JPEG ou PNG")
    return data, suffix
