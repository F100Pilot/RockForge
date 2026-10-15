"""EXPERIMENTAL automatic sync with a variable tempo (``align_beats``).

The chart's own beats are moved to where the recording plays them, keeping
their number and order, so the notes land on the attacks heard and the tempo
changes slowly. The removed whole-song estimators failed on real songs by
reading the wrong metrical level and by scattering corrections; here the
number of beats cannot change, and the measurements below pin what it does on
recordings with a known answer. Synthetic recordings, plain Python — the
alignment needs no ML stack; the librosa half is tested where librosa is.
"""

from __future__ import annotations

import json
import math
import random
import subprocess
import sys
from pathlib import Path

import pytest

from rockforge.infrastructure._librosa_runner import align_beats

RUNNER = Path(__file__).resolve().parents[1] / "src/rockforge/infrastructure/_librosa_runner.py"


def _recording(
    seed: int, *, drift: float = 0.06, scale: float = 1.03, drums: float = 0.5,
    rest_every: int = 10, bars: int = 64,
) -> tuple[list[float], float, list[float], list[float], list[float]]:
    """A chart shown at 120 BPM against a recording whose tempo wanders
    (``scale`` overall, ±``drift`` over 40 s), played as two-bar riffs of
    sixteenths with a resting two bars now and then, attacks missed and
    spurious ones added, and (``drums``) a hit on part of the beats."""
    rnd = random.Random(seed)
    hop = 0.01
    shown = [i * 0.5 for i in range(bars * 4 + 1)]
    riffs = [
        [(b, s / 4) for b in range(8) for s in range(4) if rnd.random() < (0.9 if s == 0 else 0.45)]
        for _ in range(3)
    ]
    played = [
        (pair * 8 + b, f)
        for pair in range(bars // 2) if pair % rest_every != 6
        for b, f in riffs[(pair // 4) % 3]
    ]
    true = [0.2]
    for _ in range(len(shown) - 1):
        t = true[-1]
        true.append(t + 0.5 * scale * (1 + drift * math.sin(2 * math.pi * t / 40)))
    dur = true[-1] + 2
    env = [rnd.random() * 0.25 for _ in range(int(dur / hop))]

    def hit(t: float, v: float) -> None:
        i = int(round(t / hop))
        for k, w in ((-1, 0.5), (0, 1.0), (1, 0.5)):
            if 0 <= i + k < len(env):
                env[i + k] = max(env[i + k], v * w)

    for b, f in played:
        if rnd.random() < 0.15:
            continue
        hit(true[b] + f * (true[b + 1] - true[b]) + rnd.gauss(0, 0.008), rnd.uniform(0.7, 1.0))
    for t in true:
        if rnd.random() < drums:
            hit(t + rnd.gauss(0, 0.005), rnd.uniform(0.6, 1.0))
    for _ in range(int(dur)):
        hit(rnd.uniform(0, dur), rnd.uniform(0.4, 1.0))
    # The chart shows its first beat 0.2 s early, as a rough "Início" would.
    notes = [shown[b] + f * 0.5 for b, f in played]
    return env, hop, shown, notes, true


def _bar_errors(res: dict, true: list[float]) -> list[float]:
    times, support = res["times"], res["support"]
    return [abs(times[i] - true[i]) for i in range(0, len(true), 4) if support[i] is not None]


@pytest.mark.parametrize("drums", [0.5, 0.0])
def test_a_wandering_tempo_is_followed_bar_by_bar(drums: float) -> None:
    """Off by up to 4.3 s as shown; every bar with notes back within 50 ms."""
    for seed in range(4):
        env, hop, shown, notes, true = _recording(seed, drums=drums)
        assert max(abs(a - b) for a, b in zip(shown, true, strict=True)) > 3.0
        res = align_beats(env, hop, shown, notes)
        errs = _bar_errors(res, true)
        assert len(errs) > 40
        assert max(errs) < 0.05, (seed, max(errs))
        assert res["evidence_after"] > 1.5 * res["evidence_before"]


def test_a_chart_already_in_time_is_left_where_it_is() -> None:
    env, hop, shown, notes, true = _recording(1, drift=0.0, scale=1.0)
    shown = [t + 0.2 for t in shown]  # exactly the recording's beats
    notes = [t + 0.2 for t in notes]
    res = align_beats(env, hop, shown, notes)
    assert max(abs(a - b) for a, b in zip(res["times"], true, strict=True)) < 0.02
    assert 0.98 < res["ratio_min"] <= res["ratio_max"] < 1.02


def test_the_beats_right_after_a_rest_are_named_to_check() -> None:
    """Through a silent rest nothing holds the tempo, and the first notes after
    it can lock a subdivision off while looking supported: those beats are the
    ones the user is told to check."""
    env, hop, shown, notes, _ = _recording(0)
    res = align_beats(env, hop, shown, notes)
    # Rests: the two bars of each tenth riff pair (pairs 6, 16, 26 → beats 48, 128, 208).
    assert res["after_gap"] == [56, 136, 216]
    assert all(res["support"][i] is None for i in range(48, 56))


def test_a_single_beat_cannot_be_aligned() -> None:
    with pytest.raises(ValueError):
        align_beats([0.0] * 100, 0.01, [0.5], [0.5])


def test_the_runner_aligns_a_real_recording_as_a_script(tmp_path: Path) -> None:
    """End to end with librosa (skipped without it): plucked notes and a
    thump on each beat at a wandering tempo, written to a WAV, analysed by the
    runner AS A SCRIPT — the way the .exe's ML interpreter runs it, where its
    folder (which holds RockForge's own ``packaging``) is sys.path[0]."""
    np = pytest.importorskip("numpy")
    sf = pytest.importorskip("soundfile")
    pytest.importorskip("librosa")
    sr = 22050
    rnd = random.Random(1)
    shown = [0.2 + i * 0.5 for i in range(24 * 4 + 1)]
    riff = [
        (b, s / 4) for b in range(8) for s in range(4)
        if rnd.random() < (0.9 if s == 0 else 0.4)
    ]
    played = [(g * 8 + b, f) for g in range(12) for b, f in riff]
    true = [0.3]
    for _ in range(len(shown) - 1):
        t = true[-1]
        true.append(t + 0.5 * 1.04 * (1 + 0.05 * math.sin(2 * math.pi * t / 30)))
    y = np.zeros(int((true[-1] + 2) * sr))
    for b, f in played:
        i = int((true[b] + f * (true[b + 1] - true[b])) * sr)
        tt = np.arange(int(0.25 * sr)) / sr
        f0 = rnd.choice([110, 147, 165, 196, 220])
        tone = sum(np.sin(2 * np.pi * f0 * k * tt) / k for k in range(1, 6))
        y[i:i + len(tt)] += 0.2 * tone * np.exp(-tt * 12)
    for t in true:
        tt = np.arange(int(0.1 * sr)) / sr
        i = int(t * sr)
        y[i:i + len(tt)] += 0.3 * np.sin(2 * np.pi * 60 * tt) * np.exp(-tt * 30)
    wav = tmp_path / "take.wav"
    sf.write(wav, 0.8 * y / np.max(np.abs(y)), sr)
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps({"beats": shown, "notes": [shown[b] + f * 0.5 for b, f in played]}))
    out = subprocess.run(
        [sys.executable, str(RUNNER), "beatalign", "--audio", str(wav), "--spec", str(spec)],
        capture_output=True, text=True, timeout=300, stdin=subprocess.DEVNULL,
    )
    assert out.returncode == 0, out.stderr[-2000:]
    res = json.loads(out.stdout.strip().splitlines()[-1])
    errs = [abs(a - b) for a, b in zip(res["times"], true, strict=True)]
    assert max(errs) < 0.05
