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
- ``songs/arr/<key>_showlights.xml`` — the stage-light track (fog + beam events
  generated from the arrangement, like DLC Builder; empty only when there are no
  notes to light).

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


def _dds_header(size: int) -> bytes:
    """128-byte DXT1 DDS header (magic + 124-byte DDS_HEADER), flags
    CAPS|HEIGHT|WIDTH|PIXELFORMAT|LINEARSIZE (0x81007), one mip level."""
    return struct.pack(
        "<4s 7I 44s 2I 4s 5I 5I",
        b"DDS ",
        124, 0x81007, size, size, (size * size) // 2, 0, 1,  # size,flags,h,w,pitch,depth,mips=1
        b"\x00" * 44,                                          # reserved1[11]
        32, 0x4, b"DXT1", 0, 0, 0, 0, 0,                       # pixelformat (fourCC=DXT1)
        0x1000, 0, 0, 0, 0,                                    # caps1..4 + reserved2
    )


def _rgb565(r: int, g: int, b: int) -> int:
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)


def _expand565(c: int) -> tuple[int, int, int]:
    r = (c >> 11) & 0x1F
    g = (c >> 5) & 0x3F
    b = c & 0x1F
    return (r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)


def _dxt1_block(px: list[tuple[int, int, int]]) -> bytes:
    """Compress 16 RGB pixels (row-major 4×4) into an 8-byte DXT1 block via
    range-fit: the two endpoints are the per-channel min/max, and each pixel
    takes the nearest of the 4 interpolated colours."""
    lo = (min(p[0] for p in px), min(p[1] for p in px), min(p[2] for p in px))
    hi = (max(p[0] for p in px), max(p[1] for p in px), max(p[2] for p in px))
    c0, c1 = _rgb565(*hi), _rgb565(*lo)
    if c0 < c1:
        c0, c1 = c1, c0
    if c0 == c1:  # flat block — all index 0 (colour0)
        return struct.pack("<HHI", c0, c1, 0)
    e0, e1 = _expand565(c0), _expand565(c1)
    palette = [
        e0, e1,
        tuple((2 * e0[i] + e1[i]) // 3 for i in range(3)),
        tuple((e0[i] + 2 * e1[i]) // 3 for i in range(3)),
    ]
    bits = 0
    for i, p in enumerate(px):
        best, bestd = 0, 1 << 30
        for idx, c in enumerate(palette):
            d = (p[0] - c[0]) ** 2 + (p[1] - c[1]) ** 2 + (p[2] - c[2]) ** 2
            if d < bestd:
                best, bestd = idx, d
        bits |= best << (2 * i)
    return struct.pack("<HHI", c0, c1, bits)


def dxt1_from_rgb(pixels: list[tuple[int, int, int]], size: int) -> bytes:
    """A full DXT1 ``.dds`` for a ``size``×``size`` RGB image (row-major)."""
    out = bytearray(_dds_header(size))
    for by in range(0, size, 4):
        for bx in range(0, size, 4):
            block = [pixels[(by + y) * size + (bx + x)] for y in range(4) for x in range(4)]
            out += _dxt1_block(block)
    return bytes(out)


def solid_dds(size: int, color: tuple[int, int, int] = (40, 42, 48)) -> bytes:
    """A neutral solid-colour DXT1 ``.dds`` of ``size``×``size`` — a placeholder
    cover so the song-list art URN resolves (used when no real cover is set)."""
    c565 = _rgb565(*color)
    return _dds_header(size) + struct.pack("<HHI", c565, c565, 0) * ((size // 4) * (size // 4))


def album_art_dds(size: int, cover_path: object = None) -> bytes:
    """Real cover converted to DXT1 at ``size``×``size`` if ``cover_path`` is a
    readable image and Pillow is installed; otherwise the solid placeholder."""
    if cover_path is None:
        return solid_dds(size)
    try:
        from PIL import Image  # optional; part of the [psarc] extra
    except ImportError:
        return solid_dds(size)
    try:
        with Image.open(str(cover_path)) as im:
            im = im.convert("RGB").resize((size, size), Image.LANCZOS)
            pixels = list(im.getdata())
    except (OSError, ValueError):
        return solid_dds(size)
    return dxt1_from_rgb(pixels, size)


# Showlight note conventions (the Rocksmith stage-lighting track): fog/stage
# colour = notes 24-35, beam colour = notes 42-59, laser = 66 (on) / 67 (off).
# DLC Builder generates a fog change per section plus a beam per note (coloured
# by the played pitch); an empty track leaves the stage dark and the song can
# skip its lit intro. We replicate the fog-per-section + beam-per-onset shape.
_SHOWLIGHT_FOG = (24, 26, 28, 30, 32, 34)
_SHOWLIGHT_BEAM_LO, _SHOWLIGHT_BEAM_HI = 42, 59
_SHOWLIGHT_MIN_GAP_S = 0.35  # thin dense passages so the track stays ~DLC-sized


def build_showlights(arrangement: object | None = None) -> str:
    """The stage-lighting track. With an ``arrangement`` (any object exposing
    ``notes``/``sections``/``tuning``/``metadata`` like the domain
    :class:`Arrangement`), generate fog + beam events the way DLC Builder does —
    a fog colour at the start and at each section, and a pitch-coloured beam at
    each note onset (thinned to ``_SHOWLIGHT_MIN_GAP_S``). Falls back to a valid
    empty track when there is nothing to light."""
    events: list[tuple[float, int]] = []
    notes = list(getattr(arrangement, "notes", None) or [])
    if arrangement is not None and notes:
        by_time = sorted(notes, key=lambda n: n.time)
        start = by_time[0].time
        events.append((start, _SHOWLIGHT_FOG[0]))
        fog_i = 1
        for sec in sorted(getattr(arrangement, "sections", []), key=lambda s: s.start_time):
            if sec.start_time > start:
                events.append((sec.start_time, _SHOWLIGHT_FOG[fog_i % len(_SHOWLIGHT_FOG)]))
                fog_i += 1
        midi = getattr(getattr(arrangement, "tuning", None), "midi", (40, 45, 50, 55, 59, 64))
        beam_span = _SHOWLIGHT_BEAM_HI - _SHOWLIGHT_BEAM_LO + 1
        last = float("-inf")
        for n in by_time:
            if n.time - last < _SHOWLIGHT_MIN_GAP_S:
                continue
            last = n.time
            pitch = midi[n.string] + n.fret if 0 <= n.string < len(midi) else 60
            events.append((n.time, _SHOWLIGHT_BEAM_LO + pitch % beam_span))
        song_len = float(getattr(getattr(arrangement, "metadata", None), "song_length", 0.0))
        end = max(song_len, by_time[-1].time)
        events.append((end, _SHOWLIGHT_FOG[fog_i % len(_SHOWLIGHT_FOG)]))

    events.sort(key=lambda e: e[0])
    rows = "".join(
        f'  <showlight time="{t:.3f}" note="{note}" />\n' for t, note in events
    )
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        f'<showlights count="{len(events)}">\n'
        f'{rows}'
        '</showlights>'
    )
