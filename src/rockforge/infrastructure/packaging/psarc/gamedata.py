"""Game-enumeration assets a Rocksmith PSARC needs to *list* a song.

Beyond the SNG + manifests, the game discovers a song through an entity graph:

- ``gamexblocks/nsongs/<key>.xblock`` — an ``entitySet`` with one
  ``RSEnumerable_Song`` entity per arrangement, wiring the arrangement to its
  header/manifest/SNG/soundbank/album-art/showlights URNs.
- ``flatmodels/rs/rsenumerable_{root,song}.flat`` — the (song-independent)
  model schema those entities instantiate; vendored verbatim (they never change
  per song).
- ``<key>_aggregategraph.nt`` — an N-Triples asset table mapping every URN to
  its archive path (``relpath``), so the engine can resolve them.
- ``gfxassets/album_art/album_<key>_{64,128,256}.dds`` — the cover textures the
  song list shows (a neutral placeholder here; DLC Builder generates real ones).
- ``songs/arr/<key>_showlights.xml`` — the stage-light track (a valid empty one).

Layout/URN conventions are matched to a real DLC Builder PSARC. This is the
"make the song appear" layer; the honesty caveat of the native PSARC still holds
(no in-game validation in CI — see ``packer.py``).
"""

from __future__ import annotations

import struct
import zlib
from importlib import resources

_FLAT_NAMES = ("rsenumerable_root.flat", "rsenumerable_song.flat")


def load_flat_models() -> dict[str, bytes]:
    """The two constant RSEnumerable flat models, keyed by their archive path."""
    out: dict[str, bytes] = {}
    for name in _FLAT_NAMES:
        res = resources.files("rockforge.infrastructure.packaging.psarc") / "flatmodels" / name
        out[f"flatmodels/rs/{name}"] = res.read_bytes()
    return out


def _llid(name: str) -> str:
    """A stable 32-bit logical-lookup id (as DLC Builder's ``llid``), rendered
    like ``789fe7bd-0000-0000-0000-000000000000``."""
    return f"{zlib.crc32(name.encode('utf-8')) & 0xFFFFFFFF:08x}-0000-0000-0000-000000000000"


def build_xblock(song_key: str, arrangements: list[tuple[str, str]], *, has_album_art: bool) -> str:
    """One ``RSEnumerable_Song`` entity per arrangement.

    ``arrangements`` is ``[(persistent_id_hex, entity_name)]``. ``entity_name``
    is e.g. ``BeartoothFREE_Combo``. Album-art properties are only emitted when
    ``has_album_art`` (a dangling DDS URN is worse than none).
    """
    key = song_key.lower()
    art = ""
    if has_album_art:
        art = (
            f'        <property name="AlbumArtSmall">\n'
            f'          <set value="urn:image:dds:album_{key}_64" />\n'
            f'        </property>\n'
            f'        <property name="AlbumArtMedium">\n'
            f'          <set value="urn:image:dds:album_{key}_128" />\n'
            f'        </property>\n'
            f'        <property name="AlbumArtLarge">\n'
            f'          <set value="urn:image:dds:album_{key}_256" />\n'
            f'        </property>\n'
        )
    entities = []
    for pid, name in arrangements:
        entities.append(
            f'    <entity id="{pid.lower()}" modelName="RSEnumerable_Song" '
            f'name="{name}" iterations="0">\n'
            f'      <properties>\n'
            f'        <property name="Header">\n'
            f'          <set value="urn:database:hsan-db:songs_dlc_{key}" />\n'
            f'        </property>\n'
            f'        <property name="Manifest">\n'
            f'          <set value="urn:database:json-db:{name.lower()}" />\n'
            f'        </property>\n'
            f'        <property name="SngAsset">\n'
            f'          <set value="urn:application:musicgame-song:{name.lower()}" />\n'
            f'        </property>\n'
            f'{art}'
            f'        <property name="LyricArt">\n'
            f'          <set value="" />\n'
            f'        </property>\n'
            f'        <property name="ShowLightsXMLAsset">\n'
            f'          <set value="urn:application:xml:{key}_showlights" />\n'
            f'        </property>\n'
            f'        <property name="SoundBank">\n'
            f'          <set value="urn:audio:wwise-sound-bank:song_{key}" />\n'
            f'        </property>\n'
            f'        <property name="PreviewSoundBank">\n'
            f'          <set value="urn:audio:wwise-sound-bank:song_{key}_preview" />\n'
            f'        </property>\n'
            f'      </properties>\n'
            f'    </entity>'
        )
    return (
        '﻿<?xml version="1.0" encoding="utf-8"?>\n'
        '<game>\n'
        '  <entitySet>\n'
        + "\n".join(entities)
        + "\n"
        '  </entitySet>\n'
        '</game>'
    )


_AWEB = "http://emergent.net/aweb/1.0"


def _nt_node(tags: list[str], canonical: str, name: str, relpath: str, llid: bool) -> str:
    import uuid as _uuid

    # Deterministic per (name, relpath) so rebuilds are stable.
    node = _uuid.uuid5(_uuid.NAMESPACE_URL, relpath)
    subj = f"<urn:uuid:{node}>"
    lines = [f'{subj} <{_AWEB}/tag> "{t}".' for t in tags]
    lines.append(f'{subj} <{_AWEB}/canonical> "{canonical}".')
    lines.append(f'{subj} <{_AWEB}/name> "{name}".')
    if llid:
        lines.append(f'{subj} <{_AWEB}/llid> "{_llid(name)}".')
        # The logical path drops the platform leaf dir (/generic for SNG,
        # /windows for audio), as DLC Builder writes it.
        logpath = relpath.replace("/generic", "").replace("/windows", "")
        lines.append(f'{subj} <{_AWEB}/logpath> "{logpath}".')
    lines.append(f'{subj} <{_AWEB}/relpath> "{relpath}".')
    return "\n".join(lines)


def build_aggregategraph(
    song_key: str,
    arrangements: list[str],
    *,
    include_vocals: bool,
    has_album_art: bool,
) -> str:
    """The N-Triples asset table. ``arrangements`` are the instrumental entity
    names (e.g. ``["beartoothfree_combo"]``, already lowercased)."""
    key = song_key.lower()
    nodes: list[str] = []
    # The xblock world.
    nodes.append(_nt_node(
        ["emergent-world", "x-world"], "/gamexblocks/nsongs", key,
        f"/gamexblocks/nsongs/{key}.xblock", llid=False))
    # Showlights.
    nodes.append(_nt_node(
        ["application", "xml"], "/songs/arr", f"{key}_showlights",
        f"/songs/arr/{key}_showlights.xml", llid=True))
    names = list(arrangements) + ([f"{key}_vocals"] if include_vocals else [])
    for nm in arrangements:
        nodes.append(_nt_node(
            ["database", "json-db"], f"/manifests/songs_dlc_{key}", nm,
            f"/manifests/songs_dlc_{key}/{nm}.json", llid=False))
        nodes.append(_nt_node(
            ["application", "musicgame-song"], "/songs/bin/generic", nm,
            f"/songs/bin/generic/{nm}.sng", llid=True))
    if include_vocals:
        nodes.append(_nt_node(
            ["database", "json-db"], f"/manifests/songs_dlc_{key}", f"{key}_vocals",
            f"/manifests/songs_dlc_{key}/{key}_vocals.json", llid=False))
        nodes.append(_nt_node(
            ["application", "musicgame-song"], "/songs/bin/generic", f"{key}_vocals",
            f"/songs/bin/generic/{key}_vocals.sng", llid=True))
    nodes.append(_nt_node(
        ["database", "hsan-db"], f"/manifests/songs_dlc_{key}", f"songs_dlc_{key}",
        f"/manifests/songs_dlc_{key}/songs_dlc_{key}.hsan", llid=False))
    if has_album_art:
        for res in (64, 128, 256):
            nodes.append(_nt_node(
                ["dds", "image"], "/gfxassets/album_art", f"album_{key}_{res}",
                f"/gfxassets/album_art/album_{key}_{res}.dds", llid=True))
    for suffix in ("", "_preview"):
        nodes.append(_nt_node(
            ["audio", "wwise-sound-bank", "dx9"], "/audio/windows", f"song_{key}{suffix}",
            f"/audio/windows/song_{key}{suffix}.bnk", llid=True))
    _ = names
    return "﻿" + "\n".join(nodes) + "\n"


def solid_dds(size: int, color: tuple[int, int, int] = (40, 42, 48)) -> bytes:
    """A neutral solid-colour DXT1 ``.dds`` of ``size``×``size`` — a placeholder
    cover so the song-list art URN resolves (DLC Builder makes the real one)."""
    r, g, b = color
    c565 = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
    block = struct.pack("<HHI", c565, c565, 0)  # both colours equal, all-index-0
    pixels = block * ((size // 4) * (size // 4))
    # 128-byte DDS header (magic + 124-byte DDS_HEADER), flags
    # CAPS|HEIGHT|WIDTH|PIXELFORMAT|LINEARSIZE (0x81007), DXT1 pixel format.
    header = struct.pack(
        "<4s 7I 44s 2I 4s 5I 5I",
        b"DDS ",
        124, 0x81007, size, size, (size * size) // 2, 0, 0,  # size,flags,h,w,pitch,depth,mips
        b"\x00" * 44,                                          # reserved1[11]
        32, 0x4, b"DXT1", 0, 0, 0, 0, 0,                       # pixelformat (fourCC=DXT1)
        0x1000, 0, 0, 0, 0,                                    # caps1..4 + reserved2
    )
    return header + pixels


def build_showlights() -> str:
    """A valid empty showlights track (no light events)."""
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<showlights count="0">\n'
        '</showlights>'
    )
