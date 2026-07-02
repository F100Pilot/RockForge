"""Best-effort chord naming from a set of sounding pitches.

RockForge does not carry authored chord names (the GP diagram names are dropped
and the Song2014 ``chordName`` is written empty), so the tab viewer's chord
labels are *derived* from the notes actually played. This is a heuristic:
inversions, added tensions and ambiguous voicings are only partially recovered,
and a voicing that matches no template returns ``None`` rather than inventing a
name (the honesty principle — never label what we cannot identify).
"""

from __future__ import annotations

NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")

# Interval sets (semitones from the root, pitch-class) → quality suffix, in
# priority order: the first template that matches a given root wins, so simpler
# / more common chords are preferred over exotic supersets.
_TEMPLATES: tuple[tuple[frozenset[int], str], ...] = (
    (frozenset({0, 7}), "5"),  # power chord
    (frozenset({0, 4, 7}), ""),  # major
    (frozenset({0, 3, 7}), "m"),  # minor
    (frozenset({0, 3, 6}), "dim"),
    (frozenset({0, 4, 8}), "aug"),
    (frozenset({0, 2, 7}), "sus2"),
    (frozenset({0, 5, 7}), "sus4"),
    (frozenset({0, 4, 7, 11}), "maj7"),
    (frozenset({0, 4, 7, 10}), "7"),
    (frozenset({0, 3, 7, 10}), "m7"),
    (frozenset({0, 3, 6, 10}), "m7b5"),
    (frozenset({0, 3, 6, 9}), "dim7"),
    (frozenset({0, 4, 7, 9}), "6"),
    (frozenset({0, 3, 7, 9}), "m6"),
    (frozenset({0, 4, 7, 2}), "add9"),
    (frozenset({0, 3, 7, 2}), "madd9"),
    (frozenset({0, 4, 7, 10, 2}), "9"),
    (frozenset({0, 3, 7, 10, 2}), "m9"),
    (frozenset({0, 4, 7, 10, 5}), "11"),
)


def name_chord(pitches: list[int]) -> str | None:
    """Name the chord formed by ``pitches`` (MIDI note numbers), or ``None``.

    Needs at least two distinct pitch classes. The lowest pitch is treated as
    the bass: when the best-matching root is not the bass, a slash (e.g.
    ``C/E``) records the inversion. Returns ``None`` for a single pitch class or
    any voicing that matches no known template.
    """
    if len(pitches) < 2:
        return None
    pcs = {p % 12 for p in pitches}
    if len(pcs) < 2:
        return None
    bass_pc = min(pitches) % 12

    # A voicing rooted on the bass wins over an inversion reading of the same
    # notes (D-G-A is Dsus4, not Gsus2/D); only then does template priority
    # (simpler/common chords first) break the tie.
    best: tuple[int, int, int, str] | None = None  # (is_not_bass, priority, root, suffix)
    for root in pcs:
        rel = frozenset((pc - root) % 12 for pc in pcs)
        for priority, (template, suffix) in enumerate(_TEMPLATES):
            if rel == template:
                candidate = (0 if root == bass_pc else 1, priority, root, suffix)
                if best is None or candidate < best:
                    best = candidate
                break

    if best is None:
        return None
    root, suffix = best[2], best[3]
    name = NOTE_NAMES[root] + suffix
    if root != bass_pc:
        name += "/" + NOTE_NAMES[bass_pc]
    return name
