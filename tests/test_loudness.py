"""Loudness parsing + Wwise volume formula ("Calculate Volumes").

ffmpeg isn't available in CI, so the subprocess is not exercised; the stderr
parse and the volume math (the parts that decide the shipped value) are pure and
tested directly, with a captured ebur128 summary block.
"""

from __future__ import annotations

from rockforge.infrastructure.normalize.loudness import (
    TARGET_LUFS,
    VOLUME_CLAMP_DB,
    calculate_volume,
    parse_ebur128_i,
    volume_for_loudness,
)

# A real ffmpeg `-af ebur128` summary tail (running frames omitted).
_EBUR128_SUMMARY = """\
[Parsed_ebur128_0 @ 0x55] t: 4.7   TARGET:-23 LUFS    M: -19.0 S: -19.2     I: -18.3 LUFS
[Parsed_ebur128_0 @ 0x55]
[Parsed_ebur128_0 @ 0x55] Summary:

  Integrated loudness:
    I:         -12.4 LUFS
    Threshold: -22.7 LUFS

  Loudness range:
    LRA:         6.1 LU
"""


def test_parse_ebur128_takes_the_summary_integrated_value() -> None:
    # The last `I:` line is the whole-file summary, not a running frame value.
    assert parse_ebur128_i(_EBUR128_SUMMARY) == -12.4


def test_parse_ebur128_none_when_absent() -> None:
    assert parse_ebur128_i("no loudness here") is None
    assert parse_ebur128_i("") is None


def test_volume_offsets_loudness_to_target() -> None:
    # Formula is target-relative (explicit target keeps this independent of the
    # configurable default).
    assert volume_for_loudness(-12.4, target=-16.0) == -3.6
    assert volume_for_loudness(-16.0, target=-16.0) == 0.0  # already at target
    assert volume_for_loudness(-20.0, target=-16.0) == 4.0  # quiet mix boosted
    # Default target is the louder music-game level, so a -16 clip is pushed up.
    assert volume_for_loudness(-16.0) == round(TARGET_LUFS - (-16.0), 1) == 4.0


def test_volume_is_clamped_both_ways() -> None:
    # A wildly hot clip cannot be cut past the clamp (and vice-versa).
    assert volume_for_loudness(20.0) == -VOLUME_CLAMP_DB
    assert volume_for_loudness(-40.0) == VOLUME_CLAMP_DB


def test_unknown_loudness_is_a_safe_noop() -> None:
    assert volume_for_loudness(None) == 0.0


def test_calculate_volume_falls_back_to_zero_without_ffmpeg(tmp_path) -> None:
    # A missing ffmpeg binary must degrade to 0 dB, never raise.
    silent = tmp_path / "x.wav"
    silent.write_bytes(b"")
    assert calculate_volume(silent, ffmpeg="definitely-not-ffmpeg") == 0.0


_SUMMARY = """[Parsed_ebur128_0 @ 0x1] Summary:

  Integrated loudness:
    I:          -9.5 LUFS
    Threshold: -19.6 LUFS

  Loudness range:
    LRA:         5.0 LU

  True peak:
    Peak:        0.5 dBFS
"""


def test_the_true_peak_is_read_from_the_ebur128_summary() -> None:
    from rockforge.infrastructure.normalize.loudness import parse_ebur128_true_peak

    assert parse_ebur128_true_peak(_SUMMARY) == 0.5
    assert parse_ebur128_true_peak(_SUMMARY.replace("0.5 dBFS", "-inf dBFS")) == float("-inf")
    assert parse_ebur128_true_peak("no summary") is None


def test_the_recording_gain_goes_to_the_target_but_stops_at_the_peak_ceiling() -> None:
    from rockforge.infrastructure.normalize.loudness import (
        PEAK_CEILING_DBTP,
        recording_gain_db,
    )

    assert recording_gain_db(-16.0, -6.0, -12.0) == 4.0  # room to spare: all the way
    assert recording_gain_db(-16.0, -3.0, -12.0) == 2.0  # stops at the ceiling
    assert recording_gain_db(-9.5, 0.5, -12.0) == -2.5  # an over pulled under it
    assert recording_gain_db(-9.5, 0.5, -12.0) + 0.5 <= PEAK_CEILING_DBTP
    assert recording_gain_db(-16.0, None, -12.0) == 4.0
    assert recording_gain_db(None, -3.0) == 0.0
    assert recording_gain_db(float("-inf"), float("-inf")) == 0.0
