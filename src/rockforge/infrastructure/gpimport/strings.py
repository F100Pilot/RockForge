"""Which strings of a Guitar Pro track become the chart's strings.

A guitar chart is the track's six strings. A bass chart is four (Rocksmith's
bass has four; DLC Builder's InstrumentalChecker refuses a bass note on string
4 or higher, I36, and says a bass with more strings is charted as a guitar).
A 5-string bass is folded onto the four consecutive strings that lose the
fewest notes — a part that never touches the high G is the low B E A D, one
that never touches the low B is E A D G — and anything left on the fifth
string is counted in a warning, never silently dropped.

Both parsers read every note on the track's own strings first and fold at the
end, so the per-note reading stays one code path.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

from rockforge.domain.errors import IngestionError
from rockforge.domain.music import BASS_STANDARD_MIDI, BASS_STRINGS, MAX_FRET, TabNote, Tuning
from rockforge.i18n import tr

_NOTE_NAMES = ("C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B")


def check_track_strings(count: int, *, bass: bool, label: str) -> None:
    """Refuse a track that cannot be the chart asked for, saying which it can be."""
    if bass:
        if count in (BASS_STRINGS, BASS_STRINGS + 1):
            return
        raise IngestionError(tr(
            f"a pista {label} tem {count} cordas: um arranjo Bass precisa de uma pista "
            "de baixo de 4 ou 5 cordas (um baixo de 6 cordas faz-se como guitarra)",
            f"track {label} has {count} strings: a Bass arrangement needs a 4- or "
            "5-string bass track (a 6-string bass is charted as a guitar)",
        ))
    if count == 6:
        return
    if count in (BASS_STRINGS, BASS_STRINGS + 1):
        raise IngestionError(tr(
            f"a pista {label} tem {count} cordas: é um baixo — escolhe-a como pista Bass",
            f"track {label} has {count} strings: it is a bass — pick it as the Bass track",
        ))
    raise IngestionError(tr(
        f"a pista {label} tem {count} cordas; os arranjos de guitarra do Rocksmith 2014 "
        "precisam de 6",
        f"track {label} has {count} strings; Rocksmith 2014 guitar arrangements require 6",
    ))


def apply_capo(notes: Sequence[TabNote], capo: int) -> tuple[list[TabNote], list[str]]:
    """Guitar Pro frets counted from the capo → Rocksmith's, counted from the nut.

    Guitar Pro writes a note's fret relative to the capo (alphaTab's
    ``Note.stringTuning`` adds ``staff.capo``); Rocksmith writes the fret the
    hand presses and plays an open string (fret 0) at the capo (Rocksmith2014.NET
    ``Midi.toMidiNote``: ``if capo > 0 && fret = 0 then capo``), with the capo
    fret in the arrangement. So every fretted note moves up by the capo and an
    open string stays 0; a note pushed past the 24th fret is dropped and counted.
    """
    if capo <= 0:
        return list(notes), []

    def up(fret: int | None) -> int | None:
        return fret + capo if fret else fret

    out: list[TabNote] = []
    dropped = 0
    for n in notes:
        if n.fret + (capo if n.fret else 0) > MAX_FRET:
            dropped += 1
            continue
        out.append(replace(
            n, fret=up(n.fret) or 0,
            slide_to_fret=up(n.slide_to_fret),
            slide_unpitch_to=up(n.slide_unpitch_to),
            slide_in_from=up(n.slide_in_from),
            trill_fret=up(n.trill_fret),
        ))
    warnings = []
    if dropped:
        warnings.append(tr(
            f"{dropped} nota(s) deixadas de fora: com o capo na casa {capo} passavam a casa 24",
            f"{dropped} note(s) left out: with the capo at fret {capo} they went past fret 24",
        ))
    return out, warnings


def fold_strings(
    notes: Sequence[TabNote], tuning_midi: Sequence[int], *, bass: bool
) -> tuple[list[TabNote], Tuning, list[str]]:
    """The chart's notes and tuning from the track's (strings 0 = lowest)."""
    if not bass:
        return list(notes), Tuning(midi=tuple(tuning_midi)), []  # type: ignore[arg-type]
    count = len(tuning_midi)
    if count == BASS_STRINGS:
        return list(notes), Tuning.for_bass(tuning_midi), []
    per_string = [0] * count
    for n in notes:
        per_string[n.string] += 1

    def cost(first: int) -> tuple[int, int, int]:
        lost = sum(per_string) - sum(per_string[first:first + BASS_STRINGS])
        off_standard = sum(
            abs(tuning_midi[first + i] - BASS_STANDARD_MIDI[i]) for i in range(BASS_STRINGS)
        )
        return lost, off_standard, -first

    first = min(range(count - BASS_STRINGS + 1), key=cost)
    lost = cost(first)[0]
    kept = [
        replace(n, string=n.string - first)
        for n in notes
        if first <= n.string < first + BASS_STRINGS
    ]
    window = tuning_midi[first:first + BASS_STRINGS]
    names = " ".join(_NOTE_NAMES[m % 12] for m in window)
    warnings = [tr(
        f"baixo de {count} cordas: o arranjo usa as quatro cordas {names}",
        f"{count}-string bass: the arrangement uses the four strings {names}",
    )]
    if lost:
        warnings.append(tr(
            f"{lost} nota(s) na corda que fica de fora foram deixadas de fora — o baixo "
            "do Rocksmith tem 4 cordas",
            f"{lost} note(s) on the string left out were dropped — Rocksmith's bass "
            "has 4 strings",
        ))
    return kept, Tuning.for_bass(window), warnings
