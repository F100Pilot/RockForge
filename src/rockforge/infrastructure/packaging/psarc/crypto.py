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
the operator gates documented for YouTube ingestion and Wwise.

``cryptography`` is imported lazily (new ``[psarc]`` extra) so importing this
module does not require it unless these functions are called.

Limitations: :func:`encrypt_sng`/:func:`decrypt_sng` implement only the
AES-256-CTR primitive over a payload; the retail ``.sng`` file additionally
wraps a zlib-compressed payload in a small plaintext header (magic/version)
that is not yet reproduced here — that wrapping is left to the phase 5
integration once validated against retail files.
"""

from __future__ import annotations

import os
from typing import Any

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
    return encryptor.update(_zero_pad(data)) + encryptor.finalize()


def decrypt_psarc_toc(data: bytes) -> bytes:
    """Inverse of :func:`encrypt_psarc_toc`. Caller trims any zero padding."""
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms

    cipher = Cipher(algorithms.AES(ARC_KEY), _cfb_mode(b"\x00" * 16))
    decryptor = cipher.decryptor()
    return decryptor.update(data) + decryptor.finalize()


def encrypt_sng(payload: bytes) -> bytes:
    """AES-256-CTR encrypt ``payload``, prefixing a fresh random 16-byte IV."""
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    iv = os.urandom(16)
    cipher = Cipher(algorithms.AES(SNG_PC_KEY), modes.CTR(iv))
    encryptor = cipher.encryptor()
    return iv + encryptor.update(payload) + encryptor.finalize()


def decrypt_sng(data: bytes) -> bytes:
    """Inverse of :func:`encrypt_sng`: ``data`` is ``iv (16 bytes) + ciphertext``."""
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    iv, ciphertext = data[:16], data[16:]
    cipher = Cipher(algorithms.AES(SNG_PC_KEY), modes.CTR(iv))
    decryptor = cipher.decryptor()
    return decryptor.update(ciphertext) + decryptor.finalize()
