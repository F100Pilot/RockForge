"""PSARC container format: header, zlib-compressed blocks and TOC.

Ported (format layout) from the open Rocksmith2014.NET implementation (DLC
Builder, MIT licence). Phase 1 of the native-PSARC plan (TODO.md) established
the container layout with an unencrypted TOC; phase 4 added optional
AES-256-CFB TOC encryption (``crypto.py``, ``pack_entries(..., encrypt=True)``),
matching real Rocksmith PSARCs (``archive_flags=4``). The 32-byte header is
always plaintext.

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

import hashlib
import struct
import zlib

MAGIC = b"PSAR"
VERSION = (1, 4)
COMPRESSION = b"zlib"
HEADER_SIZE = 32
TOC_ENTRY_SIZE = 30
BLOCK_SIZE = 65536
# The name-block entry (index 0) has no archive path. Both a real DLC Builder
# PSARC and the toolkit's re-pack write this same fixed 16-byte name hash for it,
# so we replicate it verbatim rather than zeroing it.
_NAME_BLOCK_DIGEST = bytes.fromhex("4d3d4000dd8eed661b5cfe5f4abc924b")


def _uint40(value: int) -> bytes:
    return value.to_bytes(5, "big")


def _from_uint40(data: bytes) -> int:
    return int.from_bytes(data, "big")


def _split_blocks(content: bytes) -> list[bytes]:
    return [content[i : i + BLOCK_SIZE] for i in range(0, len(content), BLOCK_SIZE)] or [b""]


def _compress_block(block: bytes) -> tuple[bytes, int]:
    """Return ``(stored_bytes, zlength)`` for one block.

    ``zlength`` is the compressed size, or — for a block kept uncompressed — the
    block's OWN size. Rocksmith reserves ``zlength == 0`` for a *full* block_size
    block (65536, which wraps the 2-byte field to 0); a *partial* uncompressed
    block (e.g. the 6-byte ``appid.appid``) must carry its real size. Writing 0
    for a partial raw block made the game read it as a full 65536-byte block, so
    the appid came back corrupt and the song was silently dropped from the list —
    byte-verified against a working PSARC (which stores `appid.appid` with
    ``zlength = 6``) and the toolkit's re-pack of our own output (which rewrites
    exactly this). ``% BLOCK_SIZE`` maps a full block to 0 and a partial one to
    its length.
    """
    compressed = zlib.compress(block, level=9)
    if len(compressed) < len(block):
        return compressed, len(compressed)
    return block, len(block) % BLOCK_SIZE


def pack_entries(files: dict[str, bytes], encrypt: bool = False) -> bytes:
    """Pack ``{archive_path: content}`` into a PSARC container.

    If ``encrypt`` is true, the TOC (entries + block-length table) is
    AES-256-CFB encrypted with the key ported from DLC Builder (see
    ``crypto.py``, phase 4) and ``archive_flags`` is set to 4, matching real
    Rocksmith PSARCs. The 32-byte header itself is always plaintext.
    """
    paths = list(files.keys())
    # No trailing newline — a real DLC Builder PSARC and the toolkit both store
    # the name block as exactly "\n".join(paths) (byte-verified).
    name_block = "\n".join(paths).encode("utf-8")
    contents = [name_block, *(files[p] for p in paths)]
    # Each TOC entry carries a 16-byte name hash = MD5 of the archive path.
    # Rocksmith resolves every asset (SNG/manifest/xblock/…) THROUGH this hash,
    # so leaving it zero made the game unable to find the files and silently drop
    # the whole song from the list — even with a correct appid (this cost us the
    # "runs, but not in the list until re-packed by the toolkit" bug). Verified by
    # byte-diffing a working DLC Builder PSARC and the toolkit's re-pack of our own
    # output: both give every file entry ``md5(path)``. The name-block entry
    # (index 0) has no path and both tools write this fixed constant for it.
    digests = [_NAME_BLOCK_DIGEST] + [hashlib.md5(p.encode("utf-8")).digest() for p in paths]

    zlengths: list[int] = []
    block_section = bytearray()
    toc_rows: list[tuple[bytes, int, int, int]] = []  # md5, zindex_begin, length, offset

    for idx, content in enumerate(contents):
        zindex_begin = len(zlengths)
        offset = len(block_section)
        for block in _split_blocks(content):
            stored, zlength = _compress_block(block)
            zlengths.append(zlength)
            block_section.extend(stored)
        toc_rows.append((digests[idx], zindex_begin, len(content), offset))

    num_entries = len(toc_rows)

    # Real Rocksmith PSARCs store the entry data offset as ABSOLUTE from the
    # start of the file (the game seeks to it directly). The TOC has a fixed
    # size given the entry/block counts, so compute it up front and add it to
    # each block-section-relative offset.
    raw_toc_length = num_entries * TOC_ENTRY_SIZE + len(zlengths) * 2
    toc_length = HEADER_SIZE + raw_toc_length

    toc_body = bytearray()
    for md5, zindex_begin, length, offset in toc_rows:
        toc_body += md5
        toc_body += struct.pack(">I", zindex_begin)
        toc_body += _uint40(length)
        toc_body += _uint40(toc_length + offset)
    for zlength in zlengths:
        toc_body += struct.pack(">H", zlength)

    archive_flags = 0
    toc_bytes: bytes = bytes(toc_body)
    if encrypt:
        from rockforge.infrastructure.packaging.psarc.crypto import encrypt_psarc_toc

        # AES-256-CFB is a stream mode; trim the encryptor's block padding back
        # to the exact TOC length (retail PSARCs are not block-padded here).
        toc_bytes = encrypt_psarc_toc(toc_bytes)[:raw_toc_length]
        archive_flags = 4

    assert toc_length == HEADER_SIZE + len(toc_bytes)

    out = bytearray()
    out += MAGIC
    out += struct.pack(">HH", VERSION[0], VERSION[1])
    out += COMPRESSION
    out += struct.pack(">IIII", toc_length, TOC_ENTRY_SIZE, num_entries, BLOCK_SIZE)
    out += struct.pack(">I", archive_flags)
    out += toc_bytes
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
    (archive_flags,) = struct.unpack_from(">I", data, 28)

    toc_bytes = data[HEADER_SIZE:toc_length]
    if archive_flags & 4:
        from rockforge.infrastructure.packaging.psarc.crypto import decrypt_psarc_toc

        toc_bytes = decrypt_psarc_toc(toc_bytes)

    toc_rows: list[tuple[int, int, int]] = []  # zindex_begin, length, offset
    pos = 0
    for _ in range(num_entries):
        _md5 = toc_bytes[pos : pos + 16]
        zindex_begin = struct.unpack_from(">I", toc_bytes, pos + 16)[0]
        length = _from_uint40(toc_bytes[pos + 20 : pos + 25])
        offset = _from_uint40(toc_bytes[pos + 25 : pos + 30])
        toc_rows.append((zindex_begin, length, offset))
        pos += TOC_ENTRY_SIZE

    num_blocks = sum(-(-length // block_size) or 1 for _, length, _ in toc_rows)
    zlengths = list(struct.unpack_from(f">{num_blocks}H", toc_bytes, pos))

    contents: list[bytes] = []
    for zindex_begin, length, offset in toc_rows:
        out = bytearray()
        block_index = zindex_begin
        block_offset = offset  # absolute from the start of the file
        remaining = length
        while remaining > 0:
            zlength = zlengths[block_index]
            raw_size = min(block_size, remaining)
            if zlength == 0:
                chunk = data[block_offset : block_offset + raw_size]
                consumed = raw_size
            else:
                # A block may be stored raw even with zlength != 0 (compression
                # didn't shrink it); fall back to the raw bytes if it isn't zlib.
                segment = data[block_offset : block_offset + zlength]
                try:
                    chunk = zlib.decompress(segment)
                except zlib.error:
                    chunk = segment
                consumed = zlength
            out.extend(chunk)
            remaining -= len(chunk)
            block_offset += consumed
            block_index += 1
        contents.append(bytes(out))

    name_block = contents[0].decode("utf-8")
    paths = [line for line in name_block.split("\n") if line]
    return dict(zip(paths, contents[1:], strict=True))
