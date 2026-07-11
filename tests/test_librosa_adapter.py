"""LibrosaRhythmAdapter's beat-order defense — pure logic, no librosa import needed."""

from rockforge.infrastructure.rhythm.librosa_adapter import _strictly_increasing


def test_strictly_increasing_passes_through_sorted_unique_times() -> None:
    assert _strictly_increasing([0.0, 0.5, 1.0, 1.5]) == [0.0, 0.5, 1.0, 1.5]


def test_strictly_increasing_sorts_out_of_order_input() -> None:
    """A real user recording made librosa's beat tracker return times not in
    chronological order, crashing the job on TempoMap's invariant."""
    assert _strictly_increasing([0.0, 1.0, 0.5, 1.5]) == [0.0, 0.5, 1.0, 1.5]


def test_strictly_increasing_drops_duplicates() -> None:
    assert _strictly_increasing([0.0, 0.5, 0.5, 1.0]) == [0.0, 0.5, 1.0]


def test_strictly_increasing_empty() -> None:
    assert _strictly_increasing([]) == []
