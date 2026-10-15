"""Read a built Song2014 XML back into a domain :class:`Arrangement`.

The inverse of ``writer.py``, and deliberately partial: it recovers what the
Guitar Pro export needs — tuning, the beat grid, notes with their techniques,
and the section markers — not the whole Rocksmith schema. Phrases, difficulty
levels, anchors and tone events are all derived data the exporter has no use
for, so they are not reconstructed and the round trip is NOT lossless.

Reading the BUILT file (rather than re-parsing the Guitar Pro source) is the
point: it already carries the user's tempo/drift corrections and note edits, so
what comes out is the chart as RockForge actually plays it.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from rockforge.domain.arrangement import Arrangement, ArrangementKind, Section, SongMetadata
from rockforge.domain.music import (
    BASS_STANDARD_MIDI,
    STANDARD_E_MIDI,
    Beat,
    BendPoint,
    TabNote,
    Technique,
    TempoMap,
    Tuning,
    is_composite_bend,
)

# The writer's attribute name per technique (see writer._note_attrs). Only the
# flags a note carries; BEND/SLIDE ride their own numeric attributes below.
_TECHNIQUE_ATTRS: dict[str, Technique] = {
    "hammerOn": Technique.HAMMER_ON,
    "pullOff": Technique.PULL_OFF,
    "harmonic": Technique.HARMONIC,
    "harmonicPinch": Technique.PINCH_HARMONIC,
    "palmMute": Technique.PALM_MUTE,
    "vibrato": Technique.VIBRATO,
    "tremolo": Technique.TREMOLO,
    "tap": Technique.TAP,
    "slap": Technique.SLAP,
    "pluck": Technique.POP,
    "accent": Technique.ACCENT,
    "mute": Technique.FRET_MUTE,
}


def _flag(el: ET.Element, name: str) -> bool:
    return el.get(name, "0") not in ("0", "", "false")


def _int(el: ET.Element, name: str, default: int = 0) -> int:
    try:
        return int(float(el.get(name, str(default))))
    except (TypeError, ValueError):
        return default


def _note_from_el(el: ET.Element) -> TabNote:
    techniques = {t for attr, t in _TECHNIQUE_ATTRS.items() if _flag(el, attr)}
    bend = float(el.get("bend", "0") or 0)
    if bend:
        techniques.add(Technique.BEND)
    slide_to = _int(el, "slideTo", -1)
    if slide_to >= 0:
        techniques.add(Technique.SLIDE)
    unpitched = _int(el, "slideUnpitchTo", -1)
    time = float(el.get("time", "0") or 0)
    sustain = float(el.get("sustain", "0") or 0)
    # The <bendValues> curve (absolute times) back to fractions of the sustain: a
    # bend-and-release or a late bend is a shape, not just its peak. The writer
    # emits a plain rise as one point at the end, which stays a peak here too.
    curve = [
        (float(b.get("time", "0") or 0), float(b.get("step", "0") or 0))
        for b in el.iter("bendValue")
    ]
    bend_points: tuple[BendPoint, ...] = ()
    if curve and sustain > 0:
        points = [
            BendPoint(min(1.0, max(0.0, (t - time) / sustain)), step) for t, step in curve
        ]
        bend = max(bend, max(p.step for p in points))
        if is_composite_bend(points):
            bend_points = tuple(points)
        if bend:
            techniques.add(Technique.BEND)
    return TabNote(
        string=_int(el, "string"),
        fret=_int(el, "fret"),
        time=time,
        sustain=sustain,
        techniques=frozenset(techniques),
        bend_semitones=bend,
        bend_points=bend_points,
        slide_to_fret=slide_to if slide_to >= 0 else None,
        slide_unpitch_to=unpitched if unpitched >= 0 else None,
        left_hand=_int(el, "leftHand", -1),
        pick_direction=2 if _int(el, "pickDirection") == 1 else 0,  # "1" = upstroke
        link_next=_flag(el, "linkNext"),
    )


def read_arrangement_xml(path: Path, kind: ArrangementKind | None = None) -> Arrangement:
    """Rebuild an :class:`Arrangement` from a built Song2014 XML file."""
    root = ET.parse(path).getroot()

    # `is None`, NOT a truth test: an ElementTree element with no children is
    # FALSY, and <tuning> has only attributes — so `find(...) or fallback` threw
    # the real tuning away and every export came back in standard E.
    tuning_el = root.find("tuning")
    if tuning_el is None:
        tuning_el = ET.Element("tuning")
    offsets = [_int(tuning_el, f"string{i}") for i in range(6)]
    props = root.find("arrangementProperties")
    tag = (root.findtext("arrangement", "") or "").strip().lower()
    bass = (kind is ArrangementKind.BASS if kind is not None else (
        tag == "bass" or (props is not None and props.get("pathBass") == "1")
    ))
    # A bass's offsets are measured from E1 A1 D2 G2 (the game's convention).
    standard = BASS_STANDARD_MIDI if bass else STANDARD_E_MIDI
    midi = tuple(base + off for base, off in zip(standard, offsets, strict=True))

    beats = tuple(
        Beat(time=float(el.get("time", "0") or 0), measure=_int(el, "measure", -1))
        for el in root.findall("ebeats/ebeat")
    )
    notes = [_note_from_el(el) for el in root.findall("levels/level/notes/note")]
    for chord in root.findall("levels/level/chords/chord"):
        notes.extend(_note_from_el(el) for el in chord.findall("chordNote"))
    notes.sort(key=lambda n: (n.time, n.string))

    sections = [
        Section(
            name=el.get("name", "?"),
            start_time=float(el.get("startTime", "0") or 0),
            number=_int(el, "number", 1),
        )
        for el in root.findall("sections/section")
        # The writer always appends a synthetic trailing "noguitar" to mark where
        # the phrase timeline ends — a structural closer, not a real section.
        if el.get("name") != "noguitar"
    ]

    if kind is None:
        kind = ArrangementKind.BASS if bass else {
            "lead": ArrangementKind.LEAD,
            "rhythm": ArrangementKind.RHYTHM,
            "combo": ArrangementKind.COMBINED,
        }.get(tag, ArrangementKind.COMBINED)

    return Arrangement(
        kind=kind,
        metadata=SongMetadata(
            title=root.findtext("title", "") or "",
            artist=root.findtext("artistName", "") or "",
            album=root.findtext("albumName", "") or "",
            year=int(root.findtext("albumYear") or 0) or None,
            song_length=float(root.findtext("songLength", "0") or 0),
        ),
        tuning=Tuning(
            midi=(midi[0], midi[1], midi[2], midi[3], midi[4], midi[5]),
            cent_offset=float(root.findtext("centOffset", "0") or 0),
            bass=bass,
        ),
        tempo_map=TempoMap(
            beats=beats, average_bpm=float(root.findtext("averageTempo", "120") or 120)
        ),
        notes=notes,
        sections=sections,
        capo=_int(root, "capo") if root.get("capo") else 0,
    )
