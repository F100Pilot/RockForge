"""PSARC container format: header, zlib-compressed blocks and TOC.

Ported (format layout) from the open Rocksmith2014.NET implementation (DLC
Builder, MIT licence). This is Phase 1 of the native-PSARC plan in TODO.md:
the TOC produced here is **unencrypted** — real Rocksmith PSARCs encrypt the
TOC with AES-256-CFB, which is added in a later phase. An unencrypted PSARC
is therefore not yet a valid game archive; this module only establishes the
container's binary layout, with a round-trip pack/unpack.

Layout:
- 32-byte header: magic "PSAR", version 1.4, compression "zlib", TOC length,
  TOC entry size (30), file count, block size, archive flags (0 = no
  encryption).
- TOC: one 30-byte entry per file, plus one extra entry (index 0) for the
  "name block" — a newline-separated list of archive paths, used to recover
  filenames on unpack. Entry layout: 16-byte MD5 (unused/zero for the name
  block), 4-byte index of the entry's first compressed block, 5-byte
  unpacked length, 5-byte offset of the entry's data within the block
  section.
- Block-length table: one entry per compressed block (2 bytes, big-endian).
  A value of 0 means the block is stored uncompressed, at its natural size
  (``block_size``, except for a final partial block).
- Block section: the concatenated (optionally compressed) blocks for the
  name block followed by each file, in order.
"""

from __future__ import annotations

import struct
import zlib

MAGIC = b"PSAR"
VERSION = (1, 4)
COMPRESSION = b"zlib"
HEADER_SIZE = 32
TOC_ENTRY_SIZE = 30
BLOCK_SIZE = 65536


def _uint40(value: int) -> bytes:
    return value.to_bytes(5, "big")


def _from_uint40(data: bytes) -> int:
    return int.from_bytes(data, "big")


def _split_blocks(content: bytes) -> list[bytes]:
    return [content[i : i + BLOCK_SIZE] for i in range(0, len(content), BLOCK_SIZE)] or [b""]


def _compress_block(block: bytes) -> tuple[bytes, int]:
    """Return (stored_bytes, zlength) where zlength=0 means stored raw."""
    compressed = zlib.compress(block, level=9)
    if len(compressed) < len(block):
        return compressed, len(compressed)
    return block, 0


def pack_entries(files: dict[str, bytes]) -> bytes:
    """Pack ``{archive_path: content}`` into a PSARC container (unencrypted TOC)."""
    paths = list(files.keys())
    name_block = ("\n".join(paths) + "\n").encode("utf-8")
    contents = [name_block, *(files[p] for p in paths)]

    zlengths: list[int] = []
    block_section = bytearray()
    toc_rows: list[tuple[bytes, int, int, int]] = []  # md5, zindex_begin, length, offset

    for content in contents:
        zindex_begin = len(zlengths)
        offset = len(block_section)
        for block in _split_blocks(content):
            stored, zlength = _compress_block(block)
            zlengths.append(zlength)
            block_section.extend(stored)
        toc_rows.append((b"\x00" * 16, zindex_begin, len(content), offset))

    num_entries = len(toc_rows)
    toc_length = HEADER_SIZE + num_entries * TOC_ENTRY_SIZE + len(zlengths) * 2

    out = bytearray()
    out += MAGIC
    out += struct.pack(">HH", VERSION[0], VERSION[1])
    out += COMPRESSION
    out += struct.pack(">IIII", toc_length, TOC_ENTRY_SIZE, num_entries, BLOCK_SIZE)
    out += struct.pack(">I", 0)  # archive_flags: unencrypted

    for md5, zindex_begin, length, offset in toc_rows:
        out += md5
        out += struct.pack(">I", zindex_begin)
        out += _uint40(length)
        out += _uint40(offset)

    for zlength in zlengths:
        out += struct.pack(">H", zlength)

    out += block_section
    return bytes(out)


def unpack(data: bytes) -> dict[str, bytes]:
    """Inverse of :func:`pack_entries`."""
    magic, _version_major, _version_minor, compression = struct.unpack_from(">4sHH4s", data, 0)
    if magic != MAGIC:
        raise ValueError("not a PSARC container (bad magic)")
    if compression != COMPRESSION:
        raise ValueError(f"unsupported compression {compression!r}")

    toc_length, toc_entry_size, num_entries, block_size = struct.unpack_from(">IIII", data, 12)
    if toc_entry_size != TOC_ENTRY_SIZE:
        raise ValueError(f"unsupported TOC entry size {toc_entry_size}")

    toc_rows: list[tuple[int, int, int]] = []  # zindex_begin, length, offset
    pos = HEADER_SIZE
    for _ in range(num_entries):
        _md5 = data[pos : pos + 16]
        zindex_begin = struct.unpack_from(">I", data, pos + 16)[0]
        length = _from_uint40(data[pos + 20 : pos + 25])
        offset = _from_uint40(data[pos + 25 : pos + 30])
        toc_rows.append((zindex_begin, length, offset))
        pos += TOC_ENTRY_SIZE

    zlengths_end = toc_length
    num_blocks = (zlengths_end - pos) // 2
    zlengths = list(struct.unpack_from(f">{num_blocks}H", data, pos))

    block_section = data[toc_length:]

    contents: list[bytes] = []
    for zindex_begin, length, offset in toc_rows:
        out = bytearray()
        block_index = zindex_begin
        block_offset = offset
        remaining = length
        while remaining > 0:
            zlength = zlengths[block_index]
            raw_size = min(block_size, remaining)
            if zlength == 0:
                chunk = block_section[block_offset : block_offset + raw_size]
                consumed = raw_size
            else:
                chunk = zlib.decompress(block_section[block_offset : block_offset + zlength])
                consumed = zlength
            out.extend(chunk)
            remaining -= len(chunk)
            block_offset += consumed
            block_index += 1
        contents.append(bytes(out))

    name_block = contents[0].decode("utf-8")
    paths = [line for line in name_block.split("\n") if line]
    return dict(zip(paths, contents[1:], strict=True))
