from pathlib import Path

from rockforge.infrastructure.ingestion.tags import AudioTags, read_tags


def test_untagged_file_returns_empty_tags(tmp_path: Path) -> None:
    f = tmp_path / "x.wav"
    f.write_bytes(b"RIFF0000WAVEfmt ")
    assert read_tags(f) == AudioTags()


def test_mp3_id3_tags_are_read(tmp_path: Path) -> None:
    # Minimal ID3v2.3 header + TIT2/TPE1/TALB/TYER frames, followed by silence bytes
    def frame(fid: bytes, text: str) -> bytes:
        payload = b"\x00" + text.encode("latin-1")
        return fid + len(payload).to_bytes(4, "big") + b"\x00\x00" + payload

    frames = (
        frame(b"TIT2", "Song X")
        + frame(b"TPE1", "Band Y")
        + frame(b"TALB", "Album Z")
        + frame(b"TYER", "1991")
    )
    size = len(frames)
    # syncsafe size
    ss = bytes([(size >> 21) & 0x7F, (size >> 14) & 0x7F, (size >> 7) & 0x7F, size & 0x7F])
    f = tmp_path / "x.mp3"
    f.write_bytes(b"ID3\x03\x00\x00" + ss + frames + b"\xff\xfb\x90\x00" + b"\x00" * 64)

    tags = read_tags(f)
    assert tags.title == "Song X"
    assert tags.artist == "Band Y"
    assert tags.album == "Album Z"
    assert tags.year == 1991
