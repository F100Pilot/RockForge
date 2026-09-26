"""Album/year/cover lookup: iTunes Search + MusicBrainz/Cover Art Archive.

The live services cannot be reached from CI or the sandbox, so every test
drives the module through an injected fetcher returning the services'
documented response shapes.
"""

from __future__ import annotations

import io
import urllib.parse
import urllib.request

import pytest

from rockforge.infrastructure import album_lookup as al

_ART = "https://is1-ssl.mzstatic.com/image/thumb/Music/v4/aa/bb/source/100x100bb.jpg"

ITUNES = {
    "resultCount": 4,
    "results": [
        {"wrapperType": "track", "kind": "song", "artistName": "Billie Eilish",
         "trackName": "ocean eyes", "collectionName": "ocean eyes - Single",
         "releaseDate": "2016-11-18T08:00:00Z", "artworkUrl100": _ART},
        {"wrapperType": "track", "kind": "song", "artistName": "Billie Eilish",
         "trackName": "ocean eyes", "collectionName": "dont smile at me",
         "releaseDate": "2017-08-11T07:00:00Z", "artworkUrl100": _ART},
        # a different artist singing it: not this recording
        {"wrapperType": "track", "kind": "song", "artistName": "Karaoke Stars",
         "trackName": "Ocean Eyes (Karaoke)", "collectionName": "Karaoke Hits",
         "releaseDate": "2019-01-01T00:00:00Z", "artworkUrl100": _ART},
        {"wrapperType": "track", "kind": "music-video", "artistName": "Billie Eilish",
         "trackName": "ocean eyes", "collectionName": "Videos"},
    ],
}

MUSICBRAINZ = {
    "recordings": [{
        "title": "ocean eyes",
        "artist-credit": [{"name": "Billie Eilish"}],
        "releases": [
            {"id": "mbid-ep", "title": "dont smile at me", "date": "2017-08-11",
             "status": "Official", "release-group": {"primary-type": "EP"}},
            {"id": "mbid-boot", "title": "Live Bootleg", "status": "Bootleg",
             "release-group": {"primary-type": "Album"}},
            {"id": "mbid-comp", "title": "Now 99", "date": "2018",
             "status": "Official",
             "release-group": {"primary-type": "Album", "secondary-types": ["Compilation"]}},
        ],
    }],
}


def _fetcher(itunes=ITUNES, musicbrainz=MUSICBRAINZ, seen=None):  # noqa: ANN001, ANN202
    def get_json(url: str):  # noqa: ANN202
        if seen is not None:
            seen.append(url)
        if url.startswith(al.ITUNES_URL):
            if isinstance(itunes, Exception):
                raise itunes
            return itunes
        if url.startswith(al.MUSICBRAINZ_URL):
            if isinstance(musicbrainz, Exception):
                raise musicbrainz
            return musicbrainz
        raise AssertionError(f"unexpected URL {url}")
    return get_json


def test_candidates_come_from_both_services_best_first() -> None:
    found = al.search_albums("Ocean Eyes", "Billie Eilish", get_json=_fetcher())

    # albums, then EPs, then singles, then compilations
    assert [(c.source, c.album, c.year, c.kind) for c in found] == [
        ("itunes", "dont smile at me", 2017, "album"),
        ("musicbrainz", "dont smile at me", 2017, "ep"),
        ("itunes", "ocean eyes - Single", 2016, "single"),
        ("musicbrainz", "Now 99", 2018, "compilation"),
    ]
    assert all(c.artist == "Billie Eilish" for c in found)
    assert "Karaoke Hits" not in {c.album for c in found}, "another artist is not a match"
    assert "Live Bootleg" not in {c.album for c in found}, "only official releases"


def test_itunes_artwork_is_asked_for_at_600px_and_kept_small_for_the_list() -> None:
    found = al.search_albums("ocean eyes", "billie eilish", get_json=_fetcher(musicbrainz={}))
    album = next(c for c in found if c.album == "dont smile at me")
    assert album.thumb_url == _ART
    assert album.cover_url == _ART.replace("100x100bb", "600x600bb")


def test_musicbrainz_covers_point_at_the_cover_art_archive() -> None:
    found = al.search_albums("ocean eyes", "billie eilish",
                             get_json=_fetcher(itunes={"results": []}))
    ep = next(c for c in found if c.source == "musicbrainz" and c.kind == "ep")
    assert ep.cover_url == f"{al.COVER_ART_URL}/mbid-ep/front-500"
    assert ep.thumb_url == f"{al.COVER_ART_URL}/mbid-ep/front-250"


def test_the_queries_carry_title_and_artist_and_quotes_cannot_break_the_search() -> None:
    seen: list[str] = []
    al.search_albums('Say "Hi"', "AC/DC", get_json=_fetcher(seen=seen))
    itunes = urllib.parse.parse_qs(urllib.parse.urlsplit(seen[0]).query)
    assert itunes["term"] == ['AC/DC Say "Hi"'] and itunes["entity"] == ["song"]
    mb = urllib.parse.parse_qs(urllib.parse.urlsplit(seen[1]).query)["query"][0]
    assert mb == 'recording:"Say  Hi" AND artist:"AC/DC"'


def test_matching_ignores_case_and_accents() -> None:
    data = {"results": [{"kind": "song", "artistName": "Xutos & Pontapés",
                         "trackName": "À Minha Maneira", "collectionName": "Gritos Mudos",
                         "releaseDate": "1990", "artworkUrl100": _ART}]}
    found = al.search_albums("a minha maneira", "xutos & pontapes",
                             get_json=_fetcher(itunes=data, musicbrainz={"recordings": []}))
    assert [c.album for c in found] == ["Gritos Mudos"]


def test_one_service_failing_still_returns_the_other() -> None:
    found = al.search_albums("ocean eyes", "billie eilish",
                             get_json=_fetcher(musicbrainz=al.AlbumLookupError("down")))
    assert found and {c.source for c in found} == {"itunes"}


def test_both_services_failing_is_an_error_not_an_empty_answer() -> None:
    boom = al.AlbumLookupError("down")
    with pytest.raises(al.AlbumLookupError):
        al.search_albums("ocean eyes", "billie eilish", get_json=_fetcher(boom, boom))


def test_a_changed_response_shape_counts_as_that_service_failing() -> None:
    with pytest.raises(al.AlbumLookupError):
        al.search_albums("x", "y", get_json=_fetcher(itunes=[1, 2], musicbrainz="?"))


def test_nothing_found_is_an_empty_list() -> None:
    assert al.search_albums("x", "y", get_json=_fetcher({"results": []}, {"recordings": []})) == []


def test_title_and_artist_are_required() -> None:
    with pytest.raises(al.AlbumLookupError):
        al.search_albums("  ", "Billie Eilish", get_json=_fetcher())


@pytest.mark.parametrize("url", [
    _ART,
    "https://coverartarchive.org/release/mbid/front-500",
    "https://archive.org/download/mbid/front.jpg",
    "https://ia800100.us.archive.org/1/items/mbid/front.jpg",
])
def test_cover_hosts_that_may_be_fetched(url: str) -> None:
    assert al.cover_url_allowed(url)


@pytest.mark.parametrize("url", [
    "http://is1-ssl.mzstatic.com/x.jpg",          # not https
    "https://evilmzstatic.com/x.jpg",              # not a subdomain
    "https://is1.mzstatic.com.evil.net/x.jpg",     # suffix trick
    "https://localhost/x.jpg",
    "https://127.0.0.1/x.jpg",
    "https://169.254.169.254/latest/meta-data",
    "file:///etc/passwd",
    "",
])
def test_every_other_address_is_refused(url: str) -> None:
    assert not al.cover_url_allowed(url)


def test_a_redirect_off_the_cover_hosts_is_refused() -> None:
    handler = al._AllowlistRedirects()
    req = urllib.request.Request("https://coverartarchive.org/release/x/front-500")
    with pytest.raises(al.AlbumLookupError):
        handler.redirect_request(req, None, 302, "Found", {}, "https://169.254.169.254/")
    ok = handler.redirect_request(req, None, 302, "Found", {},
                                  "https://ia800100.us.archive.org/x.jpg")
    assert ok is not None and ok.full_url.endswith("/x.jpg")


def test_fetch_cover_checks_the_address_before_opening_anything() -> None:
    opened: list[str] = []
    with pytest.raises(al.AlbumLookupError):
        al.fetch_cover("https://example.com/x.jpg", open_url=lambda u: opened.append(u) or b"")
    assert opened == []


def test_fetch_cover_trusts_the_bytes_not_the_name() -> None:
    jpeg, png = b"\xff\xd8\xff\xe0rest", b"\x89PNG\r\n\x1a\nrest"
    assert al.fetch_cover(_ART, open_url=lambda u: jpeg) == (jpeg, ".jpg")
    assert al.fetch_cover(_ART, open_url=lambda u: png) == (png, ".png")
    with pytest.raises(al.AlbumLookupError):
        al.fetch_cover(_ART, open_url=lambda u: b"<html>not an image</html>")


def test_an_oversized_cover_is_refused() -> None:
    with pytest.raises(al.AlbumLookupError):
        al.read_capped(io.BytesIO(b"x" * 11), limit=10)
    assert al.read_capped(io.BytesIO(b"x" * 10), limit=10) == b"x" * 10


@pytest.mark.parametrize(("credit", "main"), [
    ("Eminem feat. Avril Lavigne", "Eminem"),
    ("Eminem ft Rihanna", "Eminem"),
    ("Daft Punk featuring Pharrell Williams", "Daft Punk"),
    ("Simon & Garfunkel", "Simon & Garfunkel"),     # "&" is part of real names
    ("Earth, Wind & Fire", "Earth, Wind & Fire"),
    ("Little Feat", "Little Feat"),
])
def test_only_a_featuring_credit_is_dropped_from_the_artist(credit: str, main: str) -> None:
    assert al.primary_artist(credit) == main


def test_the_search_is_by_the_main_artist_and_a_featured_hit_still_matches() -> None:
    seen: list[str] = []
    data = {"results": [{"kind": "song", "artistName": "Eminem",
                         "trackName": "Love the Way You Lie", "collectionName": "Recovery",
                         "releaseDate": "2010-06-18", "artworkUrl100": _ART}]}
    found = al.search_albums("Love the Way You Lie (feat. Rihanna)", "Eminem feat. Rihanna",
                             get_json=_fetcher(data, {"recordings": []}, seen=seen))
    assert [c.album for c in found] == ["Recovery"]
    assert urllib.parse.parse_qs(urllib.parse.urlsplit(seen[0]).query)["term"] == [
        "Eminem Love the Way You Lie"]
    mb = urllib.parse.parse_qs(urllib.parse.urlsplit(seen[1]).query)["query"][0]
    assert mb == 'recording:"Love the Way You Lie" AND artist:"Eminem"'


def test_a_service_that_failed_is_reported_not_passed_off_as_nothing_found() -> None:
    failures: list[str] = []
    found = al.search_albums("x", "y", failures=failures, get_json=_fetcher(
        {"results": []}, al.AlbumLookupError("o serviço respondeu 503")))
    assert found == [] and failures == ["MusicBrainz: o serviço respondeu 503"]
