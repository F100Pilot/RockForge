"""Songsterr per-measure timestamps.

The API is undocumented and unreachable from CI (and from the development
sandbox), so these drive the client with a fake ``get_json`` shaped like the
responses teaqu/guitar-pro-youtube-sync reads in production: ``/api/meta/{id}``
carries ``revisionId``/``title``/``artist``; ``/api/video-points/{id}/{rev}/list``
is a list of entries with ``videoId``, ``points``, ``feature``, ``status`` and
``countries``. What is pinned is our side of the contract — and that every way
the API can change reads as a clear SongsterrError, never a crash.
"""

from __future__ import annotations

from typing import Any

import pytest

from rockforge.infrastructure.songsterr import SongsterrError, fetch_song, parse_song_id


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("23063", 23063),
        (" 23063 ", 23063),
        ("https://www.songsterr.com/a/wsa/gary-moore-parisienne-walkways-tab-s23063", 23063),
        ("https://www.songsterr.com/a/wsa/metallica-enter-sandman-tab-s19?track=2", 19),
        # A slug that happens to contain "-s<digits>" earlier: the LAST one is the id.
        ("https://www.songsterr.com/a/wsa/band-s2-song-tab-s777", 777),
    ],
)
def test_the_song_id_is_read_from_a_link_or_a_number(text: str, expected: int) -> None:
    assert parse_song_id(text) == expected


def test_an_unreadable_link_says_what_to_paste() -> None:
    with pytest.raises(SongsterrError, match="-s<número>"):
        parse_song_id("https://www.youtube.com/watch?v=abc")


def _fake(meta: Any, entries: Any) -> Any:
    seen: list[str] = []

    def get_json(url: str) -> Any:
        seen.append(url)
        return meta if "/api/meta/" in url else entries

    get_json.seen = seen  # type: ignore[attr-defined]
    return get_json


def test_videos_come_back_most_useful_first_with_their_bar_times() -> None:
    """Songsterr's default video first, then alternatives (worldwide first),
    then everything else — the order the reference tool picks by. Entries not
    marked done, without usable points, or repeated, are left out."""
    get = _fake(
        {"revisionId": 555, "title": "Ocean Eyes", "artist": "Billie"},
        [
            {"videoId": "bk", "feature": "backing", "status": "done", "points": [1.0, 3.0]},
            {"videoId": "alt-pt", "feature": "alternative", "status": "done",
             "countries": ["PT"], "points": [0.5, 2.0]},
            {"videoId": "main", "feature": None, "points": [1.37, 2.77, 4.17]},
            {"videoId": "alt-all", "feature": "alternative", "status": "done",
             "countries": ["All"], "points": [2.0, 4.0]},
            {"videoId": "pending", "feature": "solo", "status": "processing", "points": [0, 1]},
            {"videoId": "nopoints", "feature": "playthrough", "status": "done", "points": []},
            {"videoId": "garbage", "feature": "solo", "status": "done", "points": ["x", 1]},
            {"videoId": "main", "feature": None, "points": [9.0, 10.0]},  # duplicate
        ],
    )
    song = fetch_song("https://www.songsterr.com/a/wsa/x-tab-s1234", get_json=get)
    assert (song.song_id, song.revision_id, song.title) == (1234, 555, "Ocean Eyes")
    assert [v.video_id for v in song.videos] == ["main", "alt-all", "alt-pt", "bk"]
    assert song.videos[0].points == (1.37, 2.77, 4.17)
    assert song.videos[0].url == "https://youtu.be/main"
    # Revision comes from meta; the points are asked for THAT revision.
    assert get.seen == [
        "https://www.songsterr.com/api/meta/1234",
        "https://www.songsterr.com/api/video-points/1234/555/list",
    ]


@pytest.mark.parametrize(
    ("meta", "entries", "match"),
    [
        ({"title": "no revision"}, [], "revisão"),
        ({"revisionId": "abc"}, [], "revisão"),
        ({"revisionId": 1}, {"not": "a list"}, "lista de vídeos"),
        ({"revisionId": 1}, [{"videoId": "v", "points": [1.0]}], "nenhum vídeo sincronizado"),
    ],
)
def test_an_api_that_changed_shape_is_a_clear_error(meta: Any, entries: Any, match: str) -> None:
    with pytest.raises(SongsterrError, match=match):
        fetch_song("1", get_json=_fake(meta, entries))


def test_an_unreachable_songsterr_is_a_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    import urllib.error
    import urllib.request

    def refuse(*_a: Any, **_k: Any) -> Any:
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    with pytest.raises(SongsterrError, match="não consegui contactar o Songsterr"):
        fetch_song("1")
