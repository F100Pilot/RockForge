"""EXPERIMENTAL lead/rhythm partitioning of transcribed guitar notes.

No published method, benchmark, or labelled dataset exists for lead-vs-rhythm
separation (docs/research/01-source-separation.md §Q2 — only the closed-source
Moises service offers it, with no public metrics). This module is therefore an
explicit heuristic with NO accuracy claim: windows dominated by chords (high
simultaneous-note density) are labelled rhythm; windows dominated by single-line
playing in a higher register are labelled lead. Results MUST be human-reviewed;
the pipeline also always offers the COMBINED single-arrangement fallback.
"""

from __future__ import annotations

from rockforge.domain.music import NoteEvent

WINDOW_S = 1.0
CHORD_EPSILON_S = 0.03
POLYPHONY_RHYTHM_THRESHOLD = 0.5  # fraction of chordal onsets above which a window is rhythm


def _onset_groups(notes: list[NoteEvent]) -> list[list[NoteEvent]]:
    ordered = sorted(notes, key=lambda n: n.start)
    groups: list[list[NoteEvent]] = []
    for n in ordered:
        if groups and n.start - groups[-1][0].start <= CHORD_EPSILON_S:
            groups[-1].append(n)
        else:
            groups.append([n])
    return groups


class HeuristicRoleSplitter:
    """Implements rockforge.application.ports.GuitarRoleSplitter."""

    def split(self, notes: list[NoteEvent]) -> tuple[list[NoteEvent], list[NoteEvent]]:
        if not notes:
            return [], []
        groups = _onset_groups(notes)
        end = max(n.start + n.duration for n in notes)
        n_windows = int(end // WINDOW_S) + 1

        chordal = [0] * n_windows
        total = [0] * n_windows
        for g in groups:
            w = int(g[0].start // WINDOW_S)
            total[w] += 1
            if len(g) >= 2:
                chordal[w] += 1

        lead: list[NoteEvent] = []
        rhythm: list[NoteEvent] = []
        for g in groups:
            w = int(g[0].start // WINDOW_S)
            ratio = chordal[w] / total[w] if total[w] else 0.0
            target = rhythm if ratio >= POLYPHONY_RHYTHM_THRESHOLD else lead
            target.extend(g)
        return lead, rhythm
