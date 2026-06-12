"""Deterministic string/fret assignment via dynamic programming over hand positions.

Audio->tablature models are research-grade only and generalize poorly to electric
guitar (docs/research/02-transcription.md §2), so RockForge takes the MIDI->tab
route: assign strings/frets by minimizing a playability cost. The same approach
(optimize playability over transcribed MIDI) is used by the QMUL tablature
transformer; this implementation is a transparent, testable DP, not a model.
"""

from __future__ import annotations

from dataclasses import dataclass

from rockforge.domain.music import NoteEvent, TabNote, Technique, Tuning

CHORD_EPSILON_S = 0.03  # onsets within 30 ms are treated as one chord
HAND_SPAN_FRETS = 3  # frets reachable from an anchor without shifting
MAX_ANCHOR = 21
MOVE_WEIGHT = 1.0  # cost per fret of hand movement
HEIGHT_WEIGHT = 0.15  # cost per fret of absolute height (prefer lower positions)
LEGATO_MAX_GAP_S = 0.12
LEGATO_MAX_INTERVAL = 4


@dataclass(frozen=True)
class _Assigned:
    note: NoteEvent
    string: int
    fret: int


def _group_by_onset(notes: list[NoteEvent]) -> list[list[NoteEvent]]:
    ordered = sorted(notes, key=lambda n: (n.start, n.pitch))
    groups: list[list[NoteEvent]] = []
    for n in ordered:
        if groups and n.start - groups[-1][0].start <= CHORD_EPSILON_S:
            groups[-1].append(n)
        else:
            groups.append([n])
    return groups


def _assign_group(
    group: list[NoteEvent], anchor: int, tuning: Tuning
) -> list[_Assigned] | None:
    """Assign distinct strings to all notes of a chord at a given hand anchor.

    A fret is reachable if it is 0 (open) or within [anchor, anchor + span].
    Most-constrained-first backtracking; groups have at most 6 notes.
    """

    candidates: list[tuple[NoteEvent, list[tuple[int, int]]]] = []
    for note in group:
        opts = [
            (s, f)
            for s, f in tuning.candidate_positions(note.pitch)
            if f == 0 or anchor <= f <= anchor + HAND_SPAN_FRETS
        ]
        if not opts:
            return None
        candidates.append((note, opts))
    candidates.sort(key=lambda c: len(c[1]))

    used: set[int] = set()
    result: list[_Assigned] = []

    def backtrack(i: int) -> bool:
        if i == len(candidates):
            return True
        note, opts = candidates[i]
        for s, f in sorted(opts, key=lambda sf: (sf[1], sf[0])):
            if s in used:
                continue
            used.add(s)
            result.append(_Assigned(note, s, f))
            if backtrack(i + 1):
                return True
            used.remove(s)
            result.pop()
        return False

    return result if backtrack(0) else None


def _group_cost(assigned: list[_Assigned]) -> float:
    return sum(HEIGHT_WEIGHT * a.fret for a in assigned if a.fret > 0)


def _note_constraint(note: NoteEvent, tuning: Tuning) -> int:
    """Count candidate (string, fret) positions for a note across all anchors."""
    return sum(
        1
        for s, f in tuning.candidate_positions(note.pitch)
        for a in range(MAX_ANCHOR + 1)
        if f == 0 or a <= f <= a + HAND_SPAN_FRETS
    )


def _build_dp_row(
    group: list[NoteEvent],
    tuning: Tuning,
    anchors: range,
    prev_cost: list[float],
    gi: int,
    INF: float,
) -> tuple[list[tuple[list[_Assigned] | None, int]], list[float]]:
    """Build one DP row for a group. Returns (row, cur_cost)."""
    row: list[tuple[list[_Assigned] | None, int]] = []
    cur_cost: list[float] = []
    for a in anchors:
        assigned = _assign_group(group, a, tuning)
        if assigned is None:
            cur_cost.append(INF)
            row.append((None, -1))
            continue
        base = _group_cost(assigned)
        best, best_prev = INF, -1
        for p in anchors:
            if prev_cost[p] == INF:
                continue
            c = prev_cost[p] + base + (MOVE_WEIGHT * abs(a - p) if gi > 0 else 0.0)
            if c < best:
                best, best_prev = c, p
        cur_cost.append(best)
        row.append((assigned, best_prev))
    return row, cur_cost


def map_to_fretboard(
    notes: list[NoteEvent],
    tuning: Tuning,
    warnings: list[str] | None = None,
) -> list[TabNote]:
    """Map note events to TabNotes, minimizing total movement + height cost.

    When a note group cannot be placed, the mapper attempts recovery:
    1. Remove the most constrained note and retry (Option A).
    2. If that still fails, skip the group entirely (Option B).
    Warnings are appended when notes are dropped or skipped.
    """
    if not notes:
        return []
    groups = _group_by_onset(notes)
    anchors = range(MAX_ANCHOR + 1)

    # dp[a] = (cost, assignment for current group, backpointer to previous anchor)
    INF = float("inf")
    prev_cost: list[float] = [0.0] * len(anchors)
    history: list[list[tuple[list[_Assigned] | None, int]]] = []

    for gi, group in enumerate(groups):
        row, cur_cost = _build_dp_row(group, tuning, anchors, prev_cost, gi, INF)

        if all(c == INF for c in cur_cost):
            # --- Recovery: try removing the most constrained note ---
            if len(group) > 1:
                dropped = min(group, key=lambda n: _note_constraint(n, tuning))
                reduced = [n for n in group if n is not dropped]
                row2, cur_cost2 = _build_dp_row(
                    reduced, tuning, anchors, prev_cost, gi, INF
                )
                if any(c != INF for c in cur_cost2):
                    if warnings is not None:
                        warnings.append(
                            f"dropped unplayable note MIDI {dropped.pitch} "
                            f"at t={dropped.start:.3f}s "
                            f"(could not fit chord "
                            f"{sorted(n.pitch for n in group)} "
                            f"with tuning {tuning.midi})"
                        )
                    row, cur_cost = row2, cur_cost2
                else:
                    # Still unplayable — skip entire group
                    if warnings is not None:
                        warnings.append(
                            f"skipped unplayable chord at t={group[0].start:.3f}s "
                            f"(MIDI pitches {sorted({n.pitch for n in group})})"
                        )
                    continue
            else:
                # Single unplayable note — skip it
                if warnings is not None:
                    warnings.append(
                        f"skipped unplayable note MIDI {group[0].pitch} "
                        f"at t={group[0].start:.3f}s"
                    )
                continue

        prev_cost = cur_cost
        history.append(row)

    # Backtrack the optimal anchor path.
    a = min(range(len(anchors)), key=lambda i: prev_cost[i])
    path: list[int] = []
    for gi in range(len(history) - 1, -1, -1):
        path.append(a)
        a = history[gi][a][1]
    path.reverse()

    tab: list[TabNote] = []
    for gi, a in enumerate(path):
        assigned = history[gi][a][0]
        assert assigned is not None
        for item in assigned:
            techniques: set[Technique] = set()
            if abs(item.note.bend_semitones) >= 0.5:
                techniques.add(Technique.BEND)
            tab.append(
                TabNote(
                    string=item.string,
                    fret=item.fret,
                    time=item.note.start,
                    sustain=item.note.duration,
                    techniques=frozenset(techniques),
                    bend_semitones=item.note.bend_semitones,
                )
            )
    tab.sort(key=lambda t: (t.time, t.string))
    return tab


def infer_legato(tab: list[TabNote]) -> list[TabNote]:
    """HEURISTIC hammer-on/pull-off inference (no published detector for mixtures).

    Two consecutive notes on the same string, with a short gap and a small
    interval, are tagged hammer-on (ascending) or pull-off (descending).
    """
    out = list(tab)
    by_string: dict[int, list[int]] = {}
    for i, n in enumerate(out):
        by_string.setdefault(n.string, []).append(i)
    for indices in by_string.values():
        for prev_i, cur_i in zip(indices, indices[1:], strict=False):
            prev, cur = out[prev_i], out[cur_i]
            gap = cur.time - (prev.time + prev.sustain)
            if gap > LEGATO_MAX_GAP_S or cur.fret == prev.fret:
                continue
            if abs(cur.fret - prev.fret) > LEGATO_MAX_INTERVAL:
                continue
            tech = Technique.HAMMER_ON if cur.fret > prev.fret else Technique.PULL_OFF
            out[cur_i] = TabNote(
                string=cur.string,
                fret=cur.fret,
                time=cur.time,
                sustain=cur.sustain,
                techniques=cur.techniques | {tech},
                bend_semitones=cur.bend_semitones,
                slide_to_fret=cur.slide_to_fret,
            )
    return out
