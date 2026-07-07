"""Native SoundBank (.bnk) generation — round-trip and structure checks.

A real Wwise-built bnk cannot be produced in CI; these validate the ported
toolkit layout: the BKHD magic/version, the DIDX wem cross-reference matching
the returned file id, the embedded prefetch, the STID name and the Play_ event
hash. Same approach as ``test_sng.py`` — verify by parsing our own output.
"""

from __future__ import annotations

import random
import struct

from rockforge.infrastructure.packaging.psarc import soundbank


def test_generate_soundbank_has_all_chunks_in_order() -> None:
    bnk, _ = soundbank.generate_soundbank("MySong", b"\x01" * 1000)
    # Walk the chunk list: 4-byte tag + int32 length + body.
    tags = []
    off = 0
    while off < len(bnk):
        tag = bnk[off:off + 4].decode("ascii")
        size = struct.unpack_from("<i", bnk, off + 4)[0]
        tags.append(tag)
        off += 8 + size
    assert tags == ["BKHD", "DIDX", "DATA", "HIRC", "STID"]


def test_bkhd_version_is_91() -> None:
    bnk, _ = soundbank.generate_soundbank("MySong", b"\x00" * 64)
    assert soundbank.read_bkhd_version(bnk) == 91


def test_didx_cross_references_the_returned_wem_id() -> None:
    bnk, file_id = soundbank.generate_soundbank("MySong", b"\x00" * 64)
    assert soundbank.read_wem_file_id(bnk) == file_id


def test_data_chunk_embeds_the_audio_prefetch() -> None:
    wem = bytes(range(256)) * 300  # > 51200 bytes
    bnk, _ = soundbank.generate_soundbank("MySong", wem)
    off = 0
    data = None
    while off < len(bnk):
        tag = bnk[off:off + 4].decode("ascii")
        size = struct.unpack_from("<i", bnk, off + 4)[0]
        if tag == "DATA":
            data = bnk[off + 8:off + 8 + size]
            break
        off += 8 + size
    assert data == wem[:51200]


def test_stid_carries_the_song_name() -> None:
    bnk, _ = soundbank.generate_soundbank("MySong", b"\x00" * 64)
    assert b"Song_MySong" in bnk


def test_event_hash_is_present() -> None:
    # The HIRC Event object stores the FNV-1 hash of "Play_<name>".
    bnk, _ = soundbank.generate_soundbank("MySong", b"\x00" * 64)
    expected = soundbank._fnv_hash("Play_MySong")
    assert struct.pack("<I", expected) in bnk


def test_preview_bank_limits_itself_to_one_instance() -> None:
    # The preview sound object must carry the single-instance markers, else the
    # game layers overlapping preview copies while browsing the song list.
    bnk, _ = soundbank.generate_soundbank("MySong_preview", b"\x00" * 64, preview=True)
    # unkID1 preview marker, present only for previews.
    assert struct.pack("<I", 4178100890) in bnk
    plain, _ = soundbank.generate_soundbank("MySong", b"\x00" * 64, preview=False)
    assert struct.pack("<I", 4178100890) not in plain


def test_generation_is_deterministic_with_seeded_rng() -> None:
    a, ida = soundbank.generate_soundbank("S", b"\x00" * 64, rng=random.Random(1))
    b, idb = soundbank.generate_soundbank("S", b"\x00" * 64, rng=random.Random(1))
    assert a == b
    assert ida == idb
