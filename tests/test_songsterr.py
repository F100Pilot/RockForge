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


class _Answer:
    def __init__(self, status: int, body: Any = None) -> None:
        self.status_code, self._body = status, body

    def json(self) -> Any:
        if isinstance(self._body, Exception):
            raise self._body
        return self._body


def test_songsterr_is_asked_with_the_default_requests_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The reference tool's exact call (requests, default headers). A custom
    # browser-looking User-Agent is what Songsterr answered 403 to.
    import requests

    from rockforge.infrastructure import songsterr

    calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    def fake_get(*a: Any, **k: Any) -> _Answer:
        calls.append((a, k))
        return _Answer(200, {"ok": True})

    monkeypatch.setattr(requests, "get", fake_get)
    assert songsterr._http_get_json("https://www.songsterr.com/api/meta/1") == {"ok": True}
    assert calls == [(("https://www.songsterr.com/api/meta/1",), {"timeout": songsterr.TIMEOUT_S})]


@pytest.mark.parametrize(
    ("answer", "match", "status"),
    [
        (_Answer(403), "recusou o pedido \\(403\\)", 403),
        (_Answer(404), "respondeu 404", 404),
        (_Answer(200, ValueError("not json")), "ilegível", None),
    ],
)
def test_a_refusal_or_an_unreadable_answer_is_a_clear_error(
    monkeypatch: pytest.MonkeyPatch, answer: _Answer, match: str, status: int | None
) -> None:
    import requests

    from rockforge.infrastructure import songsterr

    monkeypatch.setattr(requests, "get", lambda *_a, **_k: answer)
    with pytest.raises(SongsterrError, match=match) as info:
        songsterr._http_get_json("https://www.songsterr.com/api/meta/1")
    assert info.value.status == status


def test_an_unreachable_songsterr_is_a_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    import requests

    def refuse(*_a: Any, **_k: Any) -> Any:
        raise requests.ConnectionError("connection refused")

    monkeypatch.setattr(requests, "get", refuse)
    with pytest.raises(SongsterrError, match="não consegui contactar o Songsterr"):
        fetch_song("1")


def test_a_refused_certificate_is_explained(monkeypatch: pytest.MonkeyPatch) -> None:
    import requests

    def refuse(*_a: Any, **_k: Any) -> Any:
        raise requests.exceptions.SSLError(
            "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: certificate has expired"
        )

    monkeypatch.setattr(requests, "get", refuse)
    with pytest.raises(SongsterrError, match="ligação segura ao Songsterr"):
        fetch_song("1")


# --- the tab itself (fetch_tab) ---------------------------------------------

def _tab_fetcher(answers: dict[str, Any], seen: list[str] | None = None):  # noqa: ANN202
    def get_json(url: str) -> Any:
        if seen is not None:
            seen.append(url)
        answer = answers.get(url)
        if isinstance(answer, Exception):
            raise answer
        if answer is None:
            raise SongsterrError(f"o Songsterr respondeu 403 a {url}", 403)
        return answer
    return get_json


_META = {"revisionId": 55, "title": "T", "artist": "A", "image": "abc123",
         "tracks": [{"name": "Lead", "instrument": "Distortion Guitar",
                     "tuning": [64, 59, 55, 50, 45, 40]},
                    {"name": "Drums", "instrument": "Drums"}]}


def test_the_tab_parts_are_fetched_trying_each_distribution_in_turn() -> None:
    from rockforge.infrastructure.songsterr import fetch_tab, part_urls

    lead_urls = part_urls(9, 55, "abc123", 0)
    drum_urls = part_urls(9, 55, "abc123", 1)
    seen: list[str] = []
    tab = fetch_tab("https://www.songsterr.com/a/wsa/x-tab-s9", get_json=_tab_fetcher({
        "https://www.songsterr.com/api/meta/9": _META,
        lead_urls[1]: {"measures": [{}]},            # the first distribution says 403
        drum_urls[0]: {"measures": [{}]},
    }, seen))
    assert (tab.song_id, tab.revision_id, tab.title, tab.artist) == (9, 55, "T", "A")
    assert [p["name"] for p in tab.parts] == ["Lead", "Drums"]
    # The meta's tuning/instrument reach the part when the part lacks them.
    assert tab.parts[0]["tuning"] == [64, 59, 55, 50, 45, 40]
    assert lead_urls[0] in seen and lead_urls[1] in seen
    assert lead_urls[0] == "https://dqsljvtekg760.cloudfront.net/9/55/abc123/0.json"


def test_an_older_revision_without_an_image_uses_the_legacy_addresses() -> None:
    from rockforge.infrastructure.songsterr import part_urls

    assert part_urls(9, 55, None, 2)[0] == "https://d3rrfvx08uyjp1.cloudfront.net/part/55/2"


def test_a_track_that_will_not_download_is_named_not_fatal() -> None:
    from rockforge.infrastructure.songsterr import fetch_tab, part_urls

    tab = fetch_tab("9", get_json=_tab_fetcher({
        "https://www.songsterr.com/api/meta/9": _META,
        part_urls(9, 55, "abc123", 0)[0]: {"measures": [{}]},
    }))
    assert [p["name"] for p in tab.parts] == ["Lead"] and tab.missing == ("Drums",)


def test_no_track_at_all_or_a_real_failure_is_an_error() -> None:
    from rockforge.infrastructure.songsterr import fetch_tab, part_urls

    with pytest.raises(SongsterrError, match="nenhuma pista"):
        fetch_tab("9", get_json=_tab_fetcher({"https://www.songsterr.com/api/meta/9": _META}))
    boom = SongsterrError("não consegui contactar o Songsterr (timeout)")
    with pytest.raises(SongsterrError, match="timeout"):
        fetch_tab("9", get_json=_tab_fetcher({
            "https://www.songsterr.com/api/meta/9": _META,
            part_urls(9, 55, "abc123", 0)[0]: boom,
        }))
    with pytest.raises(SongsterrError, match="pistas"):
        fetch_tab("9", get_json=_tab_fetcher({
            "https://www.songsterr.com/api/meta/9": {"revisionId": 1, "tracks": []}}))
