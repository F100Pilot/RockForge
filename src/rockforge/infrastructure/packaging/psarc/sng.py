"""SNG compilation: ``Arrangement`` → Rocksmith's binary SNG payload.

Binary layout ported from the Rocksmith2014.NET / DLC Builder project (MIT).
Section ordering and field sizes match the real Sng2014 format so the game
can parse the result. Sections RockForge's domain model cannot populate
(PhraseExtraInfo, NLD, Actions, DNAs) are emitted as empty (count=0); Events
(the stage cues) and Tones (the mid-song tone switches) are built.

Emitted: chord templates (with per-string MIDI notes), chord notes (for chords
with per-string techniques), anchors, anchor extensions (per sliding note),
fingerprints/hand shapes, notes with NextIter/PrevIter linkage, and a separate
vocals model (:func:`from_vocals`).

Dynamic Difficulty is a SIMPLIFIED DDC pass: notes ramp in over several levels
per phrase (ceiling scaled by the phrase's note density), with retail-shaped hero
triples. Musically-identical iterations are collapsed onto a shared phrase
(``_phrase_signature``), so a repeated riff is ONE phrase with many iterations —
learned once and mastered everywhere, like a real DDC — instead of a separate
re-ramping phrase per repeat. The finer NLinkedDifficulty section (linking the
levels of *different* phrases) is still not emitted. See ``_DD_LEVEL_CAP`` and
``_level_notes``.

Intentionally absent — correct given the domain model, not defects:
- No NLinkedDifficulty section (phrases ARE linked by shared id; the finer
  cross-phrase level linkage is not).
- ``ChordNotesId = -1`` for simple chords (matches DLC Builder/EOF).
- Arpeggio fingerprints (Fingerprints2): the domain has no arpeggio marking.
- ParentPrevNote / linkNext: the domain has no note-link concept.
- Note Hash = 0: the two reference tools compute mutually different,
  non-validated hashes, so 0 is the safe, source-consistent choice.

The layout is round-trip-tested but not byte-diffed against a retail SNG.

This module is the entry point; the code is in three parts: ``sng_model`` (the
records and mask bits), ``sng_build`` (``from_arrangement``/``from_vocals`` and
their stages) and ``sng_io`` (``write_sng``/``read_sng``). Callers go through
``sng.<name>`` — the packer and the manifest call ``sng.from_arrangement``, so
replacing it here (as tests do) reaches them.
"""

from __future__ import annotations

from rockforge.infrastructure.packaging.psarc.sng_build import (
    ANCHOR_NO_NOTE_FIRST,
    ANCHOR_NO_NOTE_LAST,
    _build_chord_data,
    _build_events,
    _build_sng_notes,
    _find_phrase_iteration,
    _note_tier,
    from_arrangement,
    from_vocals,
    renumber_sections_across,
)
from rockforge.infrastructure.packaging.psarc.sng_io import (
    _BEAT_SIZE,
    _BEND32_SIZE,
    _PHRASE_ITER_SIZE,
    _pack_str,
    _read_chord_notes_entry,
    _unpack_str,
    _write_chord_notes_entry,
    read_sng,
    write_sng,
)
from rockforge.infrastructure.packaging.psarc.sng_model import (
    _ACTION_SIZE,
    _BEND_DATA_COUNT,
    _EVENT_SIZE,
    _NAME_LEN,
    LAST_CONVERSION,
    NO_CAPO,
    NOTE_MASK_ACCENT,
    NOTE_MASK_ARPEGGIO,
    NOTE_MASK_BEND,
    NOTE_MASK_CHILD,
    NOTE_MASK_CHORD,
    NOTE_MASK_CHORDNOTES,
    NOTE_MASK_DOUBLESTOP,
    NOTE_MASK_FRETHANDMUTE,
    NOTE_MASK_HAMMERON,
    NOTE_MASK_HARMONIC,
    NOTE_MASK_HIGHDENSITY,
    NOTE_MASK_IGNORE,
    NOTE_MASK_MUTE,
    NOTE_MASK_OPEN,
    NOTE_MASK_PALMMUTE,
    NOTE_MASK_PARENT,
    NOTE_MASK_PINCHHARMONIC,
    NOTE_MASK_PLUCK,
    NOTE_MASK_PULLOFF,
    NOTE_MASK_SINGLE,
    NOTE_MASK_SLAP,
    NOTE_MASK_SLIDE,
    NOTE_MASK_SLIDEUNPITCHEDTO,
    NOTE_MASK_STRUM,
    NOTE_MASK_SUSTAIN,
    NOTE_MASK_TAP,
    NOTE_MASK_TREMOLO,
    NOTE_MASK_VIBRATO,
    TECHNIQUE_BITS,
    TECHNIQUE_TO_MASK,
    SngAnchor,
    SngAnchorExtension,
    SngArrangementLevel,
    SngBeat,
    SngBendData32,
    SngChordNotes,
    SngChordTemplate,
    SngEvent,
    SngFingerprint,
    SngMetadata,
    SngModel,
    SngNote,
    SngPhrase,
    SngPhraseIteration,
    SngSection,
    SngTone,
    SngVocal,
)

__all__ = [
    "ANCHOR_NO_NOTE_FIRST",
    "ANCHOR_NO_NOTE_LAST",
    "LAST_CONVERSION",
    "NOTE_MASK_ACCENT",
    "NOTE_MASK_ARPEGGIO",
    "NOTE_MASK_BEND",
    "NOTE_MASK_CHILD",
    "NOTE_MASK_CHORD",
    "NOTE_MASK_CHORDNOTES",
    "NOTE_MASK_DOUBLESTOP",
    "NOTE_MASK_FRETHANDMUTE",
    "NOTE_MASK_HAMMERON",
    "NOTE_MASK_HARMONIC",
    "NOTE_MASK_HIGHDENSITY",
    "NOTE_MASK_IGNORE",
    "NOTE_MASK_MUTE",
    "NOTE_MASK_OPEN",
    "NOTE_MASK_PALMMUTE",
    "NOTE_MASK_PARENT",
    "NOTE_MASK_PINCHHARMONIC",
    "NOTE_MASK_PLUCK",
    "NOTE_MASK_PULLOFF",
    "NOTE_MASK_SINGLE",
    "NOTE_MASK_SLAP",
    "NOTE_MASK_SLIDE",
    "NOTE_MASK_SLIDEUNPITCHEDTO",
    "NOTE_MASK_STRUM",
    "NOTE_MASK_SUSTAIN",
    "NOTE_MASK_TAP",
    "NOTE_MASK_TREMOLO",
    "NOTE_MASK_VIBRATO",
    "NO_CAPO",
    "SngAnchor",
    "SngAnchorExtension",
    "SngArrangementLevel",
    "SngBeat",
    "SngBendData32",
    "SngChordNotes",
    "SngChordTemplate",
    "SngEvent",
    "SngFingerprint",
    "SngMetadata",
    "SngModel",
    "SngNote",
    "SngPhrase",
    "SngPhraseIteration",
    "SngSection",
    "SngTone",
    "SngVocal",
    "TECHNIQUE_BITS",
    "TECHNIQUE_TO_MASK",
    "_ACTION_SIZE",
    "_BEAT_SIZE",
    "_BEND32_SIZE",
    "_BEND_DATA_COUNT",
    "_EVENT_SIZE",
    "_NAME_LEN",
    "_PHRASE_ITER_SIZE",
    "_build_chord_data",
    "_build_events",
    "_build_sng_notes",
    "_find_phrase_iteration",
    "_note_tier",
    "_pack_str",
    "_read_chord_notes_entry",
    "_unpack_str",
    "_write_chord_notes_entry",
    "from_arrangement",
    "from_vocals",
    "read_sng",
    "renumber_sections_across",
    "write_sng",
]
