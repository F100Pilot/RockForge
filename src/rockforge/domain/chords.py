"""Best-effort chord naming from a set of sounding pitches.

RockForge does not carry authored chord names (the GP diagram names are dropped
and the Song2014 ``chordName`` is written empty), so the tab viewer's chord
labels are *derived* from the notes actually played. This is a heuristic:
inversions, added tensions and ambiguous voicings are only partially recovered,
and a voicing that matches no template returns ``None`` rather than inventing a
name (the honesty principle — never label what we cannot identify).
"""

from __future__ import annotations

from collections.abc import Sequence

from rockforge.domain.music import TabNote, Technique

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


# The open chords guitarists learn first, (frets, fingers) low string first. A
# shape in the first frets that is part of one of them is fingered as in it —
# how the hand-made charts finger an E or A power chord (2-3, not 1-2) and a
# C fragment (3-2): the hand is already in that chord. Two fretted notes at
# least — a single one belongs to too many chords to say which.
_OPEN_CHORDS: tuple[tuple[tuple[int, ...], tuple[int, ...]], ...] = (
    ((0, 2, 2, 1, 0, 0), (-1, 2, 3, 1, -1, -1)),   # E
    ((-1, 0, 2, 2, 1, 0), (-1, -1, 2, 3, 1, -1)),  # Am
    ((-1, 0, 2, 2, 2, 0), (-1, -1, 1, 2, 3, -1)),  # A
    ((-1, 3, 2, 0, 1, 0), (-1, 3, 2, -1, 1, -1)),  # C
    ((3, 2, 0, 0, 0, 3), (2, 1, -1, -1, -1, 3)),   # G
)


def _open_chord_fingering(frets: Sequence[int]) -> tuple[int, ...] | None:
    fretted = [(s, f) for s, f in enumerate(frets) if f > 0]
    if len(fretted) < 2 or len(frets) != 6 or max(f for _, f in fretted) > 3:
        return None
    for shape, fingers in _OPEN_CHORDS:
        if all(shape[s] == f for s, f in fretted):
            return tuple(fingers[s] if frets[s] > 0 else -1 for s in range(6))
    return None


def chord_fingering(frets: Sequence[int]) -> tuple[int, ...]:
    """The fretting fingers (1 index .. 4 pinky, -1 none) for a chord shape.

    ``frets`` is one fret per string, lowest string first (-1 not played, 0
    open). Rocksmith shows these numbers on the chord, and its own songs and
    hand-made CDLC carry them; RockForge wrote -1 everywhere. The rule is the
    one those charts follow (79 of the 100 fully fingered shapes in two
    community CDLC the user sent come out identical; the rest are single notes
    of an open chord and wide stretches, where hand-made charts disagree among
    themselves): a part of an open chord (``_OPEN_CHORDS``) as in that chord,
    a root-less power chord 2-3, otherwise finger 1 on the lowest fret, a barre only
    where one is needed — more than four fretted notes, or the top strings all
    on that fret — and the remaining notes by fret, then string, each finger
    at least one above the last and at least as far up as its fret. A shape
    that would need a fifth finger is left unfingered (all -1) rather than
    guessed.
    """
    open_chord = _open_chord_fingering(frets)
    if open_chord is not None:
        return open_chord
    fretted = [(s, f) for s, f in enumerate(frets) if f > 0]
    out = [-1] * len(frets)
    if not fretted:
        return tuple(out)
    if (
        len(fretted) == 2
        and fretted[0][1] == fretted[1][1]
        and fretted[1][0] == fretted[0][0] + 1
        and fretted[0][0] >= 1
    ):
        # A power chord without its root (fifth + octave on the next string
        # up): fingered 2-3, finger 1 kept for the root below — as the charts do.
        out[fretted[0][0]], out[fretted[1][0]] = 2, 3
        return tuple(out)
    low = min(f for _, f in fretted)
    at_low = [s for s, f in fretted if f == low]
    run = sorted(at_low)
    contiguous = run == list(range(run[0], run[-1] + 1))
    highest = max(s for s, _ in fretted)
    barre = 2 <= len(at_low) < len(fretted) and (
        len(fretted) > 4 or (contiguous and run[-1] == highest)
    )
    if barre:
        for s in at_low:
            out[s] = 1
        rest = sorted((f, s) for s, f in fretted if f != low)
    else:
        out[at_low[0]] = 1
        rest = sorted((f, s) for s, f in fretted if s != at_low[0])
    prev = 1
    for f, s in rest:
        finger = max(prev + 1, 1 + f - low)
        if finger > 4:
            return tuple([-1] * len(frets))
        out[s] = finger
        prev = finger
    return tuple(out)


def group_fingering(
    frets: Sequence[int], left_hands: Sequence[int]
) -> tuple[int, ...]:
    """The chord's fingers: the Guitar Pro file's own (``left_hands``, one per
    string, -1 where unknown) when it fingers every fretted note, else
    :func:`chord_fingering`."""
    fretted = [s for s, f in enumerate(frets) if f > 0]
    if fretted and all(0 <= left_hands[s] <= 4 for s in fretted):
        return tuple(left_hands[s] if s in fretted else -1 for s in range(len(frets)))
    return chord_fingering(frets)


def chord_display(
    frets: Sequence[int], notes: Sequence[object], open_midi: Sequence[int], capo: int = 0
) -> tuple[tuple[int, ...], str]:
    """``(fingers, name)`` of a chord template — what the game shows on the
    chord. ``notes`` are the chord's notes (anything with ``string`` and
    ``left_hand``), read for the Guitar Pro file's own fingering; the name is
    :func:`name_chord` of the sounding pitches, "" when it has none."""
    left = [-1] * len(frets)
    for n in notes:
        string, hand = getattr(n, "string", -1), getattr(n, "left_hand", -1)
        if 0 <= string < len(left):
            left[string] = hand
    # An open string under a capo sounds at the capo (it is held there, unfingered).
    pitches = [open_midi[s] + (f or capo) for s, f in enumerate(frets) if f >= 0]
    return group_fingering(frets, left), name_chord(pitches) or ""


# Two identical chords further apart than this (from the end of one to the
# start of the next) get a hand shape each: the hand has had time to leave.
HAND_SHAPE_BREAK_S = 1.0
# A hand shape ends this long after its last chord's sustain (DLC Builder's
# millisecond resolution; the community references end 1 ms after it).
HAND_SHAPE_TAIL_S = 0.001


def hand_shape_spans(
    groups: Sequence[tuple[float, float, int]],
) -> list[tuple[int, int, int, float]]:
    """The hand shapes over a time-sorted run of note groups.

    ``groups`` is ``(time, sustain, chord_id)`` per note or chord, ``chord_id``
    -1 for a single note. Returns ``(chord_id, first, last, end_time)``: one
    hand shape per run of consecutive identical chords (indices into
    ``groups``), ending just after the last one's sustain and never past the
    next note. That is how the hand-made CDLC the user sent carry them — every
    chord inside one, no single note starting one — and a hand shape is what
    makes the game draw the chord's fingers on the fretboard: the chord
    template alone only names the shape.
    """
    spans: list[tuple[int, int, int, float]] = []
    run: list[int] | None = None  # [chord_id, first, last]

    def close(r: list[int]) -> None:
        t, sus, _ = groups[r[2]]
        end = t + sus + HAND_SHAPE_TAIL_S
        if r[2] + 1 < len(groups):
            end = min(end, groups[r[2] + 1][0])
        spans.append((r[0], r[1], r[2], max(end, t + HAND_SHAPE_TAIL_S)))

    for i, (t, _sus, cid) in enumerate(groups):
        if run is not None and cid >= 0 and cid == run[0]:
            pt, psus, _ = groups[run[2]]
            if t - (pt + psus) <= HAND_SHAPE_BREAK_S:
                run[2] = i
                continue
        if run is not None:
            close(run)
        run = [cid, i, i] if cid >= 0 else None
    if run is not None:
        close(run)
    return spans


# An arpeggio: single notes let ring one after another across several strings,
# one fret per string, inside one hand position — a chord played a string at a
# time. Rocksmith draws it as a shape over those notes (an "-arp" chord
# template in a hand shape, the SNG's Fingerprints2). At least this many notes,
# on as many different strings:
ARPEGGIO_MIN_NOTES = 3
# Lowest to highest fretted note at most this far apart: four frets, one hand.
ARPEGGIO_MAX_FRET_SPAN = 3


def arpeggio_spans(
    groups: Sequence[Sequence[TabNote]],
) -> list[tuple[int, int, tuple[int, ...], float]]:
    """The arpeggios over a time-sorted run of note groups.

    ``groups`` are the notes at each instant; a group of more than one note is
    a chord. Returns ``(first, last, frets, end_time)``: indices into
    ``groups``, one fret per string (-1 unused), and where the shape ends —
    just after the last note's sustain and never past the next note, like
    :func:`hand_shape_spans`.

    Guitar Pro has no arpeggio marking a chart can be read from (its
    "arpeggio" is a strum of one chord), so it is derived: a run of single
    notes each let ring (the shape stays held — what makes it a chord rather
    than a melody), no slide (the hand moves), no rest longer than
    ``HAND_SHAPE_BREAK_S``, each string on one fret, inside
    ``ARPEGGIO_MAX_FRET_SPAN``, at least ``ARPEGGIO_MIN_NOTES`` notes on as many
    strings. A chord, or a note that breaks any of these, ends it.
    """
    def single(g: Sequence[TabNote]) -> TabNote | None:
        if len(g) != 1:
            return None
        n = g[0]
        if (Technique.LET_RING not in n.techniques or n.slide_to_fret is not None
                or n.slide_unpitch_to is not None):
            return None
        return n

    spans: list[tuple[int, int, tuple[int, ...], float]] = []
    run: list[int] = []
    frets: dict[int, int] = {}

    def close() -> None:
        if len(run) >= ARPEGGIO_MIN_NOTES and len(frets) >= ARPEGGIO_MIN_NOTES:
            last = groups[run[-1]][0]
            end = last.time + last.sustain + HAND_SHAPE_TAIL_S
            if run[-1] + 1 < len(groups):
                end = min(end, groups[run[-1] + 1][0].time)
            shape = tuple(frets.get(s, -1) for s in range(6))
            spans.append((run[0], run[-1], shape, max(end, last.time + HAND_SHAPE_TAIL_S)))

    for i, g in enumerate(groups):
        n = single(g)
        if n is not None and run:
            prev = groups[run[-1]][0]
            fretted = [x for x in (*frets.values(), n.fret) if x > 0]
            if (n.time - (prev.time + prev.sustain) <= HAND_SHAPE_BREAK_S
                    and frets.get(n.string, n.fret) == n.fret
                    and (not fretted or max(fretted) - min(fretted) <= ARPEGGIO_MAX_FRET_SPAN)):
                run.append(i)
                frets[n.string] = n.fret
                continue
        close()
        run, frets = ([i], {n.string: n.fret}) if n is not None else ([], {})
    close()
    return spans
