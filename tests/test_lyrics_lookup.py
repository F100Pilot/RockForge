"""Lyrics lookup on LRCLIB.

lrclib.net cannot be reached from CI or the sandbox, so the module is driven
through an injected fetcher returning LRCLIB's documented ``/api/search``
response shape.
"""

from __future__ import annotations

import urllib.parse

import pytest

from rockforge.infrastructure import lyrics_lookup as ll

_SYNCED = "[00:12.00] Hello darkness\n[00:15.50] my old friend"


def _entry(**kw):  # noqa: ANN003, ANN202
    base = {"id": 1, "name": "Song", "trackName": "Song", "artistName": "Band",
            "albumName": "Album", "duration": 200.0, "instrumental": False,
            "plainLyrics": "Hello darkness\nmy old friend", "syncedLyrics": _SYNCED}
    return {**base, **kw}


def _fetcher(*answers, seen=None):  # noqa: ANN001, ANN002, ANN202
    queue = list(answers)

    def get_json(url: str):  # noqa: ANN202
        if seen is not None:
            seen.append(url)
        return queue.pop(0)
    return get_json


def test_synced_entries_first_then_the_length_closest_to_the_recording() -> None:
    data = [
        _entry(id=1, syncedLyrics=None, duration=200.0),       # plain only
        _entry(id=2, duration=260.0),                          # synced, extended mix
        _entry(id=3, duration=201.0),                          # synced, same edit
        _entry(id=4, artistName="Karaoke Stars"),              # someone else's
        _entry(id=5, syncedLyrics=None, plainLyrics=None),     # nothing to use
    ]
    found = ll.search_lyrics("Song", "Band", 200.5, get_json=_fetcher(data))
    assert [c.id for c in found] == [3, 2, 1]
    assert found[0].synced == _SYNCED and found[0].album == "Album"


def test_an_instrumental_is_an_answer_not_a_silence() -> None:
    data = [_entry(id=9, syncedLyrics=None, plainLyrics=None, instrumental=True)]
    [c] = ll.search_lyrics("Song", "Band", get_json=_fetcher(data))
    assert c.instrumental and c.synced is None and c.plain is None


def test_searched_by_main_artist_then_free_text_when_the_fields_find_nothing() -> None:
    seen: list[str] = []
    found = ll.search_lyrics(
        "Stan (feat. Dido)", "Eminem feat. Dido",
        get_json=_fetcher([], [_entry(trackName="Stan", artistName="Eminem")], seen=seen))
    assert [c.track for c in found] == ["Stan"]
    first = urllib.parse.parse_qs(urllib.parse.urlsplit(seen[0]).query)
    assert first == {"track_name": ["Stan"], "artist_name": ["Eminem"]}
    assert urllib.parse.parse_qs(urllib.parse.urlsplit(seen[1]).query) == {"q": ["Eminem Stan"]}


def test_a_changed_response_shape_is_an_error() -> None:
    with pytest.raises(ll.LyricsLookupError):
        ll.search_lyrics("Song", "Band", get_json=_fetcher({"oops": 1}))


def test_title_and_artist_are_required() -> None:
    with pytest.raises(ll.LyricsLookupError):
        ll.search_lyrics(" ", "Band", get_json=_fetcher([]))


@pytest.mark.parametrize(("text", "lang"), [
    ("Eu não sei o que fazer com o meu coração, está tudo sem ti", "pt"),
    ("Hello darkness my old friend, I've come to talk with you again", "en"),
    ("Yo no sé qué hacer con mi corazón, pero los días son como", "es"),
    ("Je ne sais pas, tu es dans mon coeur et le monde est pour", "fr"),
    ("la la la", "en"),
])
def test_the_alignment_language_is_guessed_from_the_words(text: str, lang: str) -> None:
    assert ll.guess_language(text) == lang
