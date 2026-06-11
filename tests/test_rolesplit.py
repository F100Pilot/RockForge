from rockforge.domain.music import NoteEvent
from rockforge.infrastructure.rolesplit.heuristic import HeuristicRoleSplitter


def chord(t: float, pitches: tuple[int, ...] = (40, 47, 52)) -> list[NoteEvent]:
    return [NoteEvent(pitch=p, start=t, duration=0.4) for p in pitches]


def test_chordal_windows_go_to_rhythm_single_lines_to_lead() -> None:
    notes = chord(0.0) + chord(0.5) + [
        NoteEvent(pitch=p, start=2.0 + i * 0.2, duration=0.1)
        for i, p in enumerate([64, 66, 67, 69])
    ]
    lead, rhythm = HeuristicRoleSplitter().split(notes)
    assert len(rhythm) == 6
    assert len(lead) == 4
    assert all(n.pitch >= 64 for n in lead)


def test_empty_input() -> None:
    assert HeuristicRoleSplitter().split([]) == ([], [])


def test_partition_is_complete_and_disjoint() -> None:
    notes = chord(0.0) + [NoteEvent(pitch=60, start=1.5, duration=0.2)]
    lead, rhythm = HeuristicRoleSplitter().split(notes)
    assert len(lead) + len(rhythm) == len(notes)
