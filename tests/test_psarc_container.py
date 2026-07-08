import hashlib
import struct

from rockforge.infrastructure.packaging.psarc.container import (
    BLOCK_SIZE,
    HEADER_SIZE,
    TOC_ENTRY_SIZE,
    pack_entries,
    unpack,
)


def test_round_trip_small_files() -> None:
    files = {
        "a.txt": b"hello world",
        "dir/b.bin": bytes(range(256)) * 4,
        "empty.txt": b"",
    }
    packed = pack_entries(files)
    assert unpack(packed) == files


def test_round_trip_large_file_spans_multiple_blocks() -> None:
    big = (b"abcdefgh" * (BLOCK_SIZE // 8)) + b"tail-bytes"
    files = {"big.bin": big, "small.txt": b"x"}
    packed = pack_entries(files)
    result = unpack(packed)
    assert result == files
    assert len(big) > BLOCK_SIZE


def test_round_trip_incompressible_data() -> None:
    import os

    data = os.urandom(BLOCK_SIZE + 100)
    files = {"random.bin": data}
    assert unpack(pack_entries(files)) == files


def test_partial_uncompressed_block_zlength_is_its_size_not_zero() -> None:
    # Rocksmith reserves zlength 0 for a FULL block_size block; a partial
    # uncompressed block (e.g. the 6-byte appid.appid) must carry its real size,
    # or the game reads it as a full 65536-byte block and the appid comes back
    # corrupt (song dropped from the list). Verified against a working PSARC.
    files = {"appid.appid": b"492989"}  # tiny + incompressible → stored raw
    packed = pack_entries(files)
    (toc_length, entry_size, num) = struct.unpack_from(">III", packed, 12)
    toc = packed[HEADER_SIZE:toc_length]
    # zlength table follows the num TOC entries.
    zpos = num * TOC_ENTRY_SIZE
    zlengths = struct.unpack_from(f">{(len(toc) - zpos) // 2}H", toc, zpos)
    # Block 0 is the name block, block 1 is appid.appid — both partial + raw here.
    assert zlengths[1] == len(b"492989")  # == 6, not 0
    assert unpack(packed) == files


def test_toc_entries_carry_md5_of_path() -> None:
    # Rocksmith resolves every asset through the TOC's 16-byte name hash =
    # md5(path). A zeroed hash makes the game unable to find the files and drops
    # the song from the list even with a correct appid (the toolkit re-pack fixed
    # exactly this). The name-block entry (index 0) uses the fixed retail hash.
    files = {
        "songs/bin/generic/mysong_lead.sng": b"x" * 10,
        "appid.appid": b"492989",
    }
    packed = pack_entries(files)  # plaintext TOC — no crypto needed
    (toc_length, entry_size, num) = struct.unpack_from(">III", packed, 12)
    toc = packed[HEADER_SIZE:toc_length]
    assert entry_size == TOC_ENTRY_SIZE
    assert num == len(files) + 1  # +1 for the name-block entry
    # Index 0 is the name block: the fixed hash both DLC Builder and the toolkit
    # write (0x4d3d4000…), not zero.
    assert toc[0:16] == bytes.fromhex("4d3d4000dd8eed661b5cfe5f4abc924b")
    for i, path in enumerate(files, start=1):
        got = toc[i * TOC_ENTRY_SIZE : i * TOC_ENTRY_SIZE + 16]
        assert got == hashlib.md5(path.encode("utf-8")).digest(), path
