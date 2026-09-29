"""Tone over time and the per-part, per-track tone suggestions (pure halves).

The librosa measurement itself cannot run in CI; what is tested here is what
turns its numbers into a suggestion: the window profiles anchored on the whole
song's calibration, and the engine that reads them against each track's chart.
"""

from __future__ import annotations

import pytest

from rockforge.domain.music import TabNote, Technique
from rockforge.infrastructure.tone_analysis.analyzer import (
    WindowProfile,
    profile_from_features,
    window_profiles,
)
from rockforge.infrastructure.tone_analysis.sections import (
    MAX_TONES,
    Segment,
    SegmentSuggestion,
    TrackChart,
    _fold_tones,
    audio_in,
    choose_role,
    plan_tones,
    plan_track,
    play_style,
    segments_for,
)

SONG = {
    "zcr": 0.08, "centroid": 2600.0, "contrast": 18.0, "rolloff": 5200.0,
    "flatness": 0.01, "crest": 2.1, "rms_std_ratio": 0.3,
}


def _window(t: float, active: bool = True, **kw: float) -> dict[str, float]:
    w: dict[str, float] = {"t": t, "active": float(active), **SONG, "crest": 1.6}
    w.update(kw)
    return w


def test_a_window_like_the_song_reads_the_songs_gain() -> None:
    """A 4 s window holds less dynamics than the whole song (its crest is lower
    on any real recording), so run through the song calibration every window
    would read more distorted. Anchored, a window that differs from the others
    in nothing reads exactly the song's gain."""
    song = profile_from_features(**SONG)
    out = window_profiles(SONG, [_window(0.0), _window(1.0)])
    assert [w.gain_level for w in out] == [song.gain_level, song.gain_level]
    # The raw per-window calibration would have read it hotter — the bias removed.
    raw = profile_from_features(**{**SONG, "crest": 1.6})
    assert raw.gain_level > song.gain_level + 0.05


def test_a_cleaner_or_dirtier_window_moves_away_from_the_song() -> None:
    windows = [
        _window(0.0),
        _window(1.0, crest=2.4, contrast=26.0, flatness=0.003, zcr=0.05),  # clean break
        _window(2.0, crest=1.0, contrast=12.0, flatness=0.03, zcr=0.12),  # hotter chorus
    ]
    base, clean, hot = window_profiles(SONG, windows)
    assert clean.gain_level < base.gain_level < hot.gain_level
    assert clean.brightness == base.brightness  # brightness is the song formula as is


def test_inactive_windows_do_not_set_the_reference_crest() -> None:
    """Silences have a crest of their own; they must not move what "a normal
    window of this song" means, or the whole song shifts with the intro's length."""
    active = [_window(0.0), _window(1.0)]
    with_silence = active + [_window(2.0, active=False, crest=6.0)]
    a = window_profiles(SONG, active)
    b = window_profiles(SONG, with_silence)
    assert [w.gain_level for w in b[:2]] == [w.gain_level for w in a]
    assert b[2].active is False


# --- the engine ------------------------------------------------------------

def _chug(start: float, end: float, fret: int = 3) -> list[TabNote]:
    """Palm-muted power chords on the low strings, every eighth."""
    out: list[TabNote] = []
    t = start
    while t < end - 1e-9:
        for s in (0, 1):
            out.append(TabNote(s, fret + 2 * s, round(t, 3), 0.2,
                               frozenset({Technique.PALM_MUTE})))
        t += 0.25
    return out


def _arpeggio(start: float, end: float) -> list[TabNote]:
    out: list[TabNote] = []
    t, s = start, 2
    while t < end - 1e-9:
        out.append(TabNote(s, 0, round(t, 3), 0.4, frozenset({Technique.LET_RING})))
        s = 2 + (s - 1) % 4
        t += 0.5
    return out


def _solo(start: float, end: float) -> list[TabNote]:
    out: list[TabNote] = []
    t = start
    while t < end - 1e-9:
        out.append(TabNote(4, 15, round(t, 3), 0.2, frozenset({Technique.BEND})))
        t += 0.25
    return out


def _windows(spans: list[tuple[float, float, float]], pad: float = 0.0) -> list[WindowProfile]:
    """One window per second of the recording, gain per span (bundle times)."""
    out: list[WindowProfile] = []
    for start, end, gain in spans:
        t = start
        while t < end:
            out.append(WindowProfile(t=t - pad, active=True, gain_level=gain,
                                     brightness=0.5, low_end=0.5))
            t += 1.0
    return out


SONG_SOUND = (0.4, 0.5, 0.5)


def test_what_a_track_plays_decides_its_role() -> None:
    assert choose_role(play_style(_chug(0, 8), 8), 0.55)[0] == "rhythm"
    assert choose_role(play_style(_arpeggio(0, 8), 8), 0.35)[0] == "clean"
    assert choose_role(play_style(_solo(0, 8), 8), 0.55)[0] == "lead"
    assert choose_role(play_style([], 8), 0.55)[0] == "silent"
    # A quiet recording is clean whatever is played on it.
    assert choose_role(play_style(_chug(0, 8), 8), 0.1)[0] == "clean"


def test_a_role_says_why() -> None:
    role, reasons = choose_role(play_style(_chug(0, 8), 8), 0.55)
    codes = {r.code for r in reasons}
    assert role == "rhythm" and {"gain", "chords", "palm_mute"} <= codes
    role, reasons = choose_role(play_style(_solo(0, 8), 8), 0.55)
    assert role == "lead" and {"lead", "high"} <= {r.code for r in reasons}


def test_two_tracks_over_the_same_sound_get_different_tones() -> None:
    """The stem is every guitar mixed: over one sound, the chart is what tells a
    solo from the chugging under it."""
    segs = [Segment("Verso", 0, 16), Segment("Solo", 16, 32)]
    lead = TrackChart("Lead", _chug(0, 16) + _solo(16, 32), segs)
    rhythm = TrackChart("Rhythm", _chug(0, 32), segs)
    lp, rp = plan_tones(_windows([(0, 32, 0.6)]), 0.0, SONG_SOUND, [lead, rhythm])
    assert [s.role for s in lp.segments] == ["rhythm", "lead"]
    assert [s.role for s in rp.segments] == ["rhythm", "rhythm"]
    assert lp.segments[1].tone_key.startswith("RFLead_")
    assert lp.changes == [(16, lp.segments[1].tone_key)]
    assert rp.changes == [] and rp.base == rp.segments[0].tone_key


def test_a_clean_intro_then_a_heavy_verse_switches_tone_where_it_changes() -> None:
    segs = [Segment("Intro", 0, 16), Segment("Verso", 16, 32)]
    chart = TrackChart("Rhythm", _arpeggio(0, 16) + _chug(16, 32), segs)
    plan = plan_track(chart, _windows([(0, 16, 0.12), (16, 32, 0.62)]), 0.0, SONG_SOUND)
    intro, verse = plan.segments
    assert (intro.role, verse.role) == ("clean", "rhythm")
    assert intro.gain < 0.2 < 0.5 < verse.gain
    assert plan.base == intro.tone_key and plan.changes == [(16, verse.tone_key)]
    assert plan.names == [intro.tone_key, verse.tone_key]  # the base is a slot too
    assert {t["key"] for t in plan.tones} == {intro.tone_key, verse.tone_key}
    assert all("match" not in t for t in plan.tones)  # gear definitions, not rankings


def test_a_part_the_track_rests_in_keeps_the_tone_before_it() -> None:
    segs = [Segment("A", 0, 8), Segment("Pausa", 8, 16), Segment("B", 16, 24)]
    chart = TrackChart("Rhythm", _chug(0, 8) + _chug(16, 24), segs)
    plan = plan_track(chart, _windows([(0, 24, 0.6)]), 0.0, SONG_SOUND)
    assert [s.role for s in plan.segments] == ["rhythm", "silent", "rhythm"]
    assert plan.segments[1].tone_key is None
    assert plan.changes == []  # no switch out and back in around a silence


def test_the_recording_is_read_on_the_bundle_clock() -> None:
    """Windows are in the recording's seconds; the build puts the recording
    ``pad_s`` later, so a part in the bundle reads the windows that far back."""
    windows = _windows([(0, 8, 0.1), (8, 16, 0.7)], pad=0.0)
    assert audio_in(windows, 0.0, 8, 16)[0] == pytest.approx(0.7)
    assert audio_in(windows, 4.0, 8, 16)[0] == pytest.approx((0.1 * 4 + 0.7 * 4) / 8)
    assert audio_in(windows, 0.0, 40, 48) is None


def test_a_part_the_recording_does_not_cover_says_so() -> None:
    chart = TrackChart("Rhythm", _chug(0, 16), [Segment("1", 0, 16)])
    silent_mix = [WindowProfile(t=float(t), active=False, gain_level=0.0, brightness=0.5,
                                low_end=0.5) for t in range(16)]
    seg = plan_track(chart, silent_mix, 0.0, SONG_SOUND).segments[0]
    assert seg.confidence == "low" and seg.gain == SONG_SOUND[0]
    assert "no_audio" in {r.code for r in seg.reasons}
    seg = plan_track(chart, [], 0.0, SONG_SOUND).segments[0]
    assert seg.confidence == "low" and "no_audio" in {r.code for r in seg.reasons}


def test_a_track_never_needs_more_than_rocksmiths_four_tone_slots() -> None:
    keys = ["RFLead_Clean", "RFLead_CleanBright", "RFLead_Crunch", "RFLead_Plexi",
            "RFLead_Overdrive", "RFLead_HighGain", "RFLead_Metal"]
    segs = [
        SegmentSuggestion(str(i), i * 10.0, i * 10.0 + (10 if i else 30), "lead", k, k, 90, "high")
        for i, k in enumerate(keys)
    ]
    folded = _fold_tones(segs)
    used = {s.tone_key for s in folded}
    assert len(used) == MAX_TONES
    assert folded[0].tone_key == "RFLead_Clean"  # the longest part keeps its tone
    assert all(s.tone_name == s.tone_key for s in folded)


def test_parts_are_the_sections_or_groups_of_eight_bars() -> None:
    assert segments_for([("Intro", 0.0), ("Verso", 10.0)], [], 30.0) == [
        Segment("Intro", 0.0, 10.0), Segment("Verso", 10.0, 30.0),
    ]
    bars = [2.0 + 2 * i for i in range(20)]  # 20 bars, no markers
    parts = segments_for([("riff", 2.0)], bars, 42.0)
    assert [(p.name, p.start, p.end) for p in parts] == [
        ("1", 2.0, 18.0), ("2", 18.0, 34.0), ("3", 34.0, 42.0),
    ]
    assert segments_for([], [], 12.0) == [Segment("1", 0.0, 12.0)]
