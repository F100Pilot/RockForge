"""Picking the recording's attacks out of its onset envelope
(``_librosa_runner.pick_attacks``) — plain Python, so it runs without librosa."""

from __future__ import annotations

import random

from rockforge.infrastructure._librosa_runner import pick_attacks

HOP = 0.01


def _envelope(seconds: float, floor: float, hits: dict[float, float], seed: int = 1) -> list[float]:
    """A floor with a little noise, and each hit a burst that decays over 40 ms
    (spectral flux rises at the attack and falls within a few frames)."""
    rng = random.Random(seed)
    env = [floor + rng.uniform(0, 0.03) for _ in range(int(seconds / HOP))]
    for t, peak in hits.items():
        i = int(round(t / HOP))
        for k, share in enumerate((1.0, 0.55, 0.3, 0.15)):
            if i + k < len(env):
                env[i + k] = max(env[i + k], peak * share)
    return env


def test_each_strum_is_one_attack_at_its_instant() -> None:
    hits = {0.5: 1.0, 1.0: 0.9, 1.25: 1.0, 1.5: 0.8, 2.0: 1.0}
    found = pick_attacks(_envelope(3.0, 0.05, hits), HOP)
    assert [t for t, _ in found] == sorted(hits)
    assert all(0 < s <= 1 for _, s in found)


def test_two_peaks_closer_than_the_minimum_gap_are_one_attack() -> None:
    found = pick_attacks(_envelope(2.0, 0.05, {1.0: 1.0, 1.03: 0.9}), HOP)
    assert [t for t, _ in found] == [1.0]


def test_a_quiet_passage_keeps_its_attacks_beside_a_loud_one() -> None:
    loud = {0.25 * k: 1.0 for k in range(2, 20)}
    quiet = {6.0: 0.35, 6.5: 0.35, 7.0: 0.35}
    found = [t for t, _ in pick_attacks(_envelope(8.0, 0.03, {**loud, **quiet}), HOP)]
    assert all(t in found for t in quiet)


def test_a_raised_floor_between_strums_gives_only_the_strums() -> None:
    """A distorted wall keeps some new energy flowing between strums; only the
    bursts on top of it are attacks, not the floor."""
    strums = {round(0.5 + 0.37 * k, 2): 1.0 for k in range(8)}
    env = _envelope(4.0, 0.45, strums)
    assert [t for t, _ in pick_attacks(env, HOP)] == sorted(strums)


def test_a_dense_run_of_sixteenths_keeps_its_softer_strokes() -> None:
    """The floor is the median around a hit, so the accented hits of a riff do
    not raise it past the softer strokes between them (the mean would)."""
    hits = {round(1.0 + 0.12 * k, 2): (1.0 if k % 2 == 0 else 0.3) for k in range(24)}
    assert [t for t, _ in pick_attacks(_envelope(5.0, 0.05, hits), HOP)] == sorted(hits)


def test_the_padded_start_is_not_an_attack() -> None:
    """librosa pads the start with silence, so a recording that opens on its
    noise floor shows a jump in the first frames."""
    env = [0.0] * 5 + [1.4, 0.8, 0.4] + _envelope(3.0, 0.05, {1.5: 1.0})
    assert [t for t, _ in pick_attacks(env, HOP)] == [1.58]


def test_noise_alone_and_silence_have_no_attacks() -> None:
    assert pick_attacks(_envelope(3.0, 0.05, {}), HOP) == []
    assert pick_attacks([0.0] * 300, HOP) == []
    assert pick_attacks([], HOP) == []


def test_a_separated_instrument_is_read_with_the_residue_floor_on_either_path(monkeypatch):
    """In this process or on the ML interpreter, "separated" reaches the runner,
    which then floors the bands (ATTACK_STEM_FLOOR_DB); the mix is read as is."""
    from pathlib import Path

    import rockforge.infrastructure._librosa_runner as runner
    from rockforge.infrastructure import ml_python
    from rockforge.infrastructure.rhythm import librosa_adapter

    floors: list[object] = []
    def _envelope(audio, floor_db=None):
        floors.append(floor_db)
        return [], 0.01

    monkeypatch.setattr(runner, "onset_envelope", _envelope)
    runner.main(["attacks", "--audio", "x.wav"])
    runner.main(["attacks", "--audio", "x.wav", "--separated", "1.0"])
    assert floors == [None, runner.ATTACK_STEM_FLOOR_DB]

    sent: list[dict] = []
    monkeypatch.setattr(ml_python, "librosa_here", lambda: False)
    monkeypatch.setattr(
        ml_python, "run_librosa", lambda cmd, audio, **opts: sent.append(opts) or {}
    )
    librosa_adapter.detect_attacks(Path("x.wav"), separated=True)
    librosa_adapter.detect_attacks(Path("x.wav"))
    assert sent == [{"separated": 1.0}, {"separated": 0.0}]
