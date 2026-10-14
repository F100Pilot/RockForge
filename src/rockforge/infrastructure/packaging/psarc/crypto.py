"""AES primitives for PSARC TOC and SNG encryption (phase 4, TODO.md).

Keys and algorithms are ported from the open Rocksmith2014.NET project (DLC
Builder, MIT licence), per the user's decision to handle keys "the way DLC
Builder does": as constants in code, with documented provenance.

Provenance (as of 2026, MIT licence):
- ``ARC_KEY``: ``src/Rocksmith2014.PSARC/Cryptography.fs`` — AES-256-CFB
  (128-bit segment/full-block feedback), zero IV, zero padding. Used to
  encrypt/decrypt the PSARC table of contents (header stays plaintext).
- ``SNG_PC_KEY``: ``src/Rocksmith2014.SNG/Cryptography.fs`` — AES-256-CTR,
  16-byte IV. Used to encrypt/decrypt ``.sng`` payloads on PC.

Legal/honesty note (CLAUDE.md): these keys are published widely in MIT-licensed
CDLC tooling and are required to produce/read Rocksmith-compatible archives;
they are not a circumvention of any RockForge-specific protection. RockForge
does not bundle or redistribute Ubisoft's copyrighted audio/note data — see
the Wwise notes in docs/TECHNICAL.md.

``cryptography`` is imported lazily (new ``[psarc]`` extra) so importing this
module does not require it unless these functions are called.

:func:`pack_sng`/:func:`unpack_sng` implement the full retail ``.sng`` file
format (8-byte header + zero IV + AES-256-CTR of a zlib-compressed,
size-prefixed payload), verified byte-for-byte against a real DLC Builder SNG
header — this is what the packer writes.
"""

from __future__ import annotations

import struct
import zlib
from typing import Any

# Retail .sng file wrapper (Rocksmith2014.NET SngFile): an 8-byte header
# (magic 0x4A, platform 3 = PC) + a 16-byte zero IV + AES-256-CTR of a
# zlib-compressed payload prefixed with its uint32 uncompressed size.
_SNG_MAGIC = 0x4A
_SNG_PLATFORM_PC = 3

ARC_KEY = (
    b"\xc5\x3d\xb2\x38\x70\xa1\xa2\xf7\x1c\xae\x64\x06\x1f\xdd\x0e\x11"
    b"\x57\x30\x9d\xc8\x52\x04\xd4\xc5\xbf\xdf\x25\x09\x0d\xf2\x57\x2c"
)
SNG_PC_KEY = (
    b"\xcb\x64\x8d\xf3\xd1\x2a\x16\xbf\x71\x70\x14\x14\xe6\x96\x19\xec"
    b"\x17\x1c\xca\x5d\x2a\x14\x2e\x3e\x59\xde\x7a\xdd\xa1\x8a\x3a\x30"
)

_BLOCK_SIZE = 16


def _cfb_mode(iv: bytes) -> Any:
    """``modes.CFB`` moved to ``hazmat.decrepit`` in cryptography 43+."""
    try:
        from cryptography.hazmat.decrepit.ciphers.modes import CFB
    except ImportError:
        from cryptography.hazmat.primitives.ciphers.modes import CFB

    return CFB(iv)


def _zero_pad(data: bytes) -> bytes:
    remainder = len(data) % _BLOCK_SIZE
    if remainder == 0:
        return data
    return data + b"\x00" * (_BLOCK_SIZE - remainder)


def encrypt_psarc_toc(data: bytes) -> bytes:
    """AES-256-CFB encrypt the PSARC TOC (zero IV, zero-padded to 16 bytes)."""
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms

    cipher = Cipher(algorithms.AES(ARC_KEY), _cfb_mode(b"\x00" * 16))
    encryptor = cipher.encryptor()
    return bytes(encryptor.update(_zero_pad(data)) + encryptor.finalize())


def decrypt_psarc_toc(data: bytes) -> bytes:
    """Inverse of :func:`encrypt_psarc_toc`. Caller trims any zero padding."""
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms

    cipher = Cipher(algorithms.AES(ARC_KEY), _cfb_mode(b"\x00" * 16))
    decryptor = cipher.decryptor()
    return bytes(decryptor.update(data) + decryptor.finalize())


def pack_sng(raw: bytes) -> bytes:
    """Wrap a raw Sng2014 payload as a game-loadable ``.sng`` file.

    Layout (Rocksmith 2014 PC, matching a retail SNG): ``[uint32 magic=0x4A]
    [uint32 platform=3][16-byte zero IV][AES-256-CTR( [uint32 uncompressed size]
    + zlib(raw) )]``. The previous packer wrote only the raw AES-CTR primitive
    (no header/zlib), which the game cannot parse — the note highway froze on
    load. Uses a zero IV, as retail does.
    """
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    inner = struct.pack("<I", len(raw)) + zlib.compress(raw, level=9)
    iv = b"\x00" * 16
    cipher = Cipher(algorithms.AES(SNG_PC_KEY), modes.CTR(iv))
    encryptor = cipher.encryptor()
    body = bytes(encryptor.update(inner) + encryptor.finalize())
    return struct.pack("<II", _SNG_MAGIC, _SNG_PLATFORM_PC) + iv + body


def unpack_sng(data: bytes) -> bytes:
    """Inverse of :func:`pack_sng` — recover the raw Sng2014 payload."""
    magic, _platform = struct.unpack_from("<II", data, 0)
    if magic != _SNG_MAGIC:
        raise ValueError(f"not a Rocksmith .sng (magic {magic:#x})")
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    iv = data[8:24]
    cipher = Cipher(algorithms.AES(SNG_PC_KEY), modes.CTR(iv))
    decryptor = cipher.decryptor()
    inner = bytes(decryptor.update(data[24:]) + decryptor.finalize())
    uncompressed_size = struct.unpack_from("<I", inner, 0)[0]
    raw = zlib.decompress(inner[4:])
    if len(raw) != uncompressed_size:
        raise ValueError("SNG uncompressed size mismatch")
    return raw
