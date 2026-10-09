"""How many of the right notes a transcription found — onset-only note F1.

The usual measure (mir_eval's onset-only note F1): a predicted note matches a
reference note when the pitch is the same and the onsets are within ``tol``
seconds, each note matched at most once. Per pitch, the notes on each side are
points on a line and two of them may pair when they are close; walking both
sorted lists and pairing greedily is a maximum matching for that kind of graph,
so no matching library is needed.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable, Hashable, Sequence
from dataclasses import dataclass

ONSET_TOL_S = 0.05


@dataclass(frozen=True)
class Note:
    time: float
    pitch: int
    string: int | None = None
    fret: int | None = None


@dataclass(frozen=True)
class Score:
    matched: int
    predicted: int
    reference: int

    @property
    def precision(self) -> float:
        return self.matched / self.predicted if self.predicted else 0.0

    @property
    def recall(self) -> float:
        return self.matched / self.reference if self.reference else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if p + r else 0.0


def _by_key(notes: Sequence[Note], key: Callable[[Note], Hashable | None],
            shift: float = 0.0) -> dict[Hashable, list[float]]:
    groups: dict[Hashable, list[float]] = defaultdict(list)
    for n in notes:
        k = key(n)
        if k is not None:
            groups[k].append(n.time + shift)
    for times in groups.values():
        times.sort()
    return groups


def _matches(ref: list[float], pred: list[float], tol: float) -> int:
    i = j = count = 0
    while i < len(ref) and j < len(pred):
        if pred[j] < ref[i] - tol:
            j += 1
        elif pred[j] > ref[i] + tol:
            i += 1
        else:
            count += 1
            i += 1
            j += 1
    return count


def match_score(reference: Sequence[Note], predicted: Sequence[Note], *,
                tol: float = ONSET_TOL_S, shift: float = 0.0,
                key: Callable[[Note], Hashable | None] = lambda n: n.pitch) -> Score:
    """F1 of ``predicted`` (moved by ``shift`` seconds) against ``reference``;
    ``key`` decides what has to agree besides the onset (the pitch, the pitch
    class, the string and fret)."""
    ref = _by_key(reference, key)
    pred = _by_key(predicted, key, shift)
    matched = sum(_matches(times, pred.get(k, []), tol) for k, times in ref.items())
    return Score(matched, sum(map(len, pred.values())), sum(map(len, ref.values())))


def pitch_class(n: Note) -> int:
    return n.pitch % 12


def tab_position(n: Note) -> tuple[int, int] | None:
    return None if n.string is None or n.fret is None else (n.string, n.fret)


def best_shift(reference: Sequence[Note], predicted: Sequence[Note], *,
               max_shift: float, tol: float = ONSET_TOL_S, candidates: int = 25) -> float:
    """The constant time shift that lines ``predicted`` up with ``reference``
    best, within ±``max_shift`` s — a transcriber's latency (a few tens of ms),
    or a tab from another tool whose bar 1 sits somewhere else. Only a shift:
    a different tempo is not searched, and shows as a poor score."""
    if max_shift <= 0 or not reference or not predicted:
        return 0.0
    ref, pred = _by_key(reference, lambda n: n.pitch), _by_key(predicted, lambda n: n.pitch)
    votes: Counter[float] = Counter()
    for k, rt in ref.items():
        for p in pred.get(k, []):
            for r in rt:
                d = r - p
                if -max_shift <= d <= max_shift:
                    votes[round(d, 2)] += 1
    trials = [0.0, *(d for d, _ in votes.most_common(candidates))]
    return max(trials, key=lambda d: (match_score(reference, predicted, tol=tol, shift=d).f1,
                                      -abs(d)))
