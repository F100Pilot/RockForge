"""Game-enumeration assets (xblock, flat models, aggregategraph, DDS, showlights).

These are the files that make a native PSARC's song *appear* in-game. They can't
be validated in the game from CI, so we check the structural invariants: valid
XML, matching DDS sizes, and that every referenced asset appears in the graph.
"""

from __future__ import annotations

import xml.dom.minidom as minidom

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
