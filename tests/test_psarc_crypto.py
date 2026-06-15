import pytest

cryptography = pytest.importorskip("cryptography")

from rockforge.infrastructure.packaging.psarc.container import pack_entries, unpack  # noqa: E402
from rockforge.infrastructure.packaging.psarc.crypto import (  # noqa: E402
    ARC_KEY,
    SNG_PC_KEY,
    decrypt_psarc_toc,
    decrypt_sng,
    encrypt_psarc_toc,
    encrypt_sng,
)


def test_keys_are_32_bytes() -> None:
    assert len(ARC_KEY) == 32
    assert len(SNG_PC_KEY) == 32


def test_psarc_toc_round_trip() -> None:
    data = b"some table-of-contents bytes, not block aligned"
    encrypted = encrypt_psarc_toc(data)
    assert len(encrypted) % 16 == 0
    decrypted = decrypt_psarc_toc(encrypted)
    assert decrypted[: len(data)] == data


def test_sng_round_trip_with_random_iv() -> None:
    payload = b"compiled sng payload bytes" * 10
    encrypted = encrypt_sng(payload)
    assert encrypted[:16] != encrypt_sng(payload)[:16]  # fresh IV each time
    assert decrypt_sng(encrypted) == payload


def test_pack_entries_with_encryption_round_trips() -> None:
    files = {"a.txt": b"hello", "b/c.bin": b"world" * 100}
    packed = pack_entries(files, encrypt=True)
    assert unpack(packed) == files

    unencrypted = pack_entries(files, encrypt=False)
    assert unpack(unencrypted) == files
    assert packed != unencrypted
