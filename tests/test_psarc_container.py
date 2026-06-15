from rockforge.infrastructure.packaging.psarc.container import (
    BLOCK_SIZE,
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
