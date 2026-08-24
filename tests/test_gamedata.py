"""Game-enumeration assets (xblock, flat models, aggregategraph, DDS, showlights).

These are the files that make a native PSARC's song *appear* in-game. They can't
be validated in the game from CI, so we check the structural invariants: valid
XML, matching DDS sizes, and that every referenced asset appears in the graph.
"""

from __future__ import annotations

import xml.dom.minidom as minidom

import pytest

from rockforge.infrastructure.packaging.psarc import gamedata


def test_flat_models_load() -> None:
    models = gamedata.load_flat_models()
    assert set(models) == {
        "flatmodels/rs/rsenumerable_root.flat",
        "flatmodels/rs/rsenumerable_song.flat",
    }
    # They are the model schema — song-independent, so never mention a song.
    assert all(len(v) > 0 for v in models.values())
    assert b"RSEnumerable_Song" in models["flatmodels/rs/rsenumerable_song.flat"]


def test_solid_dds_is_valid_dxt1_of_the_right_size() -> None:
    # DXT1 = 0.5 bytes/pixel; DDS header is 128 bytes. Matches retail sizes.
    for size, total in ((64, 2176), (128, 8320), (256, 32896)):
        dds = gamedata.solid_dds(size)
        assert dds[:4] == b"DDS "
        assert dds[84:88] == b"DXT1"
        assert len(dds) == total


def test_xblock_is_valid_xml_with_one_entity_per_arrangement() -> None:
    xblock = gamedata.build_xblock(
        "MySong",
        [("AAAA1111", "MySong_Combo"), ("BBBB2222", "MySong_Vocals")],
        has_album_art=True,
    )
    dom = minidom.parseString(xblock.encode("utf-8"))
    assert len(dom.getElementsByTagName("entity")) == 2
    # URNs derive from the (lowercased) entity name so they match the manifests.
    assert "urn:application:musicgame-song:mysong_combo" in xblock
    assert "urn:image:dds:album_mysong_64" in xblock


def test_xblock_omits_album_art_when_absent() -> None:
    xblock = gamedata.build_xblock("MySong", [("AAAA1111", "MySong_Combo")], has_album_art=False)
    assert "AlbumArt" not in xblock


def test_aggregategraph_references_every_asset() -> None:
    graph = gamedata.build_aggregategraph(
        "MySong", ["mysong_combo"], include_vocals=True, has_album_art=True
    )
    for relpath in (
        "/gamexblocks/nsongs/mysong.xblock",
        "/songs/arr/mysong_showlights.xml",
        "/manifests/songs_dlc_mysong/mysong_combo.json",
        "/songs/bin/generic/mysong_combo.sng",
        "/songs/bin/generic/mysong_vocals.sng",
        "/manifests/songs_dlc_mysong/songs_dlc_mysong.hsan",
        "/gfxassets/album_art/album_mysong_64.dds",
        "/audio/windows/song_mysong.bnk",
        "/audio/windows/song_mysong_preview.bnk",
    ):
        assert relpath in graph, relpath


def test_showlights_is_valid_xml() -> None:
    minidom.parseString(gamedata.build_showlights().encode("utf-8"))
    # No arrangement → the valid empty track.
    assert 'count="0"' in gamedata.build_showlights()


def test_showlights_generated_from_arrangement() -> None:
    """With an arrangement, the stage-light track carries fog + beam events
    (start fog, per-section fog, a pitch-coloured beam per onset, end fog),
    time-ordered and using valid showlight note ranges — not an empty track."""
    import re

    from rockforge.domain.arrangement import (
        Arrangement,
        ArrangementKind,
        Section,
        SongMetadata,
    )
    from rockforge.domain.music import Beat, TabNote, TempoMap, Tuning

    notes = [
        TabNote(string=i % 6, fret=(i * 2) % 12, time=5.0 + i * 0.4, sustain=0.1)
        for i in range(40)
    ]
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="T", artist="A", song_length=40.0),
        tuning=Tuning(),
        tempo_map=TempoMap(beats=[Beat(time=5.0, measure=1)], average_bpm=120.0),
        notes=notes,
        sections=[Section(name="COUNT", start_time=5.0), Section(name="riff", start_time=15.0)],
    )
    xml = gamedata.build_showlights(arr)
    minidom.parseString(xml.encode("utf-8"))
    times = [float(t) for t in re.findall(r'time="([\d.]+)"', xml)]
    vals = [int(n) for n in re.findall(r'note="(\d+)"', xml)]
    assert len(vals) > 10
    assert times == sorted(times)  # showlights must be time-ordered
    assert all(24 <= v <= 35 or 42 <= v <= 59 for v in vals)  # fog or beam ranges
    assert times[0] == 5.0 and times[-1] == 40.0  # lights from the intro to the end


def test_dxt1_from_rgb_is_a_valid_dds_of_the_right_size() -> None:
    # A 4×4 red image → one DXT1 block; header 128 + 8 bytes.
    red = [(255, 0, 0)] * 16
    dds = gamedata.dxt1_from_rgb(red, 4)
    assert dds[:4] == b"DDS "
    assert dds[84:88] == b"DXT1"
    assert len(dds) == 128 + 8
    # A flat block encodes both endpoints to the same 565 colour, indices 0.
    import struct

    c0, c1, bits = struct.unpack_from("<HHI", dds, 128)
    assert c0 == c1
    assert bits == 0


def test_album_art_falls_back_to_placeholder_without_a_cover() -> None:
    # No cover path → the neutral solid placeholder (never a broken URN).
    assert gamedata.album_art_dds(64, None) == gamedata.solid_dds(64)


def test_album_art_converts_a_real_cover(tmp_path) -> None:
    """The Pillow conversion path — the only part of album_art_dds that was
    never executed by any test, because the fallback above needs no Pillow and
    CI ran without the [psarc] extra that provides it. It stayed unexercised
    long enough to accumulate a type error nobody could see (Image.open returns
    an ImageFile, convert() an Image; the resampling filters moved under
    Image.Resampling in Pillow 9.1)."""
    Image = pytest.importorskip("PIL.Image")

    cover = tmp_path / "cover.png"
    Image.new("RGB", (300, 220), (200, 40, 60)).save(cover)

    dds = gamedata.album_art_dds(64, cover)
    assert dds[:4] == b"DDS "
    assert dds[84:88] == b"DXT1"
    assert len(dds) == len(gamedata.solid_dds(64))  # same DXT1 geometry
    # ...but the real cover's pixels, not the neutral placeholder's.
    assert dds != gamedata.solid_dds(64)
    # Non-square input is squashed to size×size (Rocksmith wants square art).
    assert len(gamedata.album_art_dds(128, cover)) == len(gamedata.solid_dds(128))


def test_album_art_falls_back_when_the_cover_is_not_an_image(tmp_path) -> None:
    """A corrupt or non-image file must degrade to the placeholder, not raise —
    the cover is user-uploaded and must never sink the build."""
    pytest.importorskip("PIL.Image")

    junk = tmp_path / "cover.png"
    junk.write_bytes(b"this is not a PNG")
    assert gamedata.album_art_dds(64, junk) == gamedata.solid_dds(64)
