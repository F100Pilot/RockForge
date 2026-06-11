"""Song2014 arrangement XML generation.

There is no official Ubisoft spec. The element/attribute set below follows the
de-facto documentation in the community tooling sources (verified in
docs/research/03-rocksmith-cdlc.md §5): `Song2014.cs` (rscustom toolkit) and
`Rocksmith2014.XML` (iminashi/Rocksmith2014.NET). Output is meant to be opened
in EOF / DLC Builder for human review before packaging.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from rockforge.domain.arrangement import Arrangement, ArrangementKind
from rockforge.domain.music import TabNote, Technique


def _fmt(x: float) -> str:
    return f"{x:.3f}"


def _note_attrs(n: TabNote) -> dict[str, str]:
    has = n.techniques.__contains__
    attrs = {
        "time": _fmt(n.time),
        "string": str(n.string),
        "fret": str(n.fret),
        "sustain": _fmt(n.sustain),
        "bend": str(int(round(n.bend_semitones))) if has(Technique.BEND) else "0",
        "hammerOn": "1" if has(Technique.HAMMER_ON) else "0",
        "pullOff": "1" if has(Technique.PULL_OFF) else "0",
        "harmonic": "1" if has(Technique.HARMONIC) else "0",
        "palmMute": "1" if has(Technique.PALM_MUTE) else "0",
        "vibrato": "1" if has(Technique.VIBRATO) else "0",
        "linkNext": "0",
        "accent": "0",
        "slideTo": str(n.slide_to_fret) if n.slide_to_fret is not None else "-1",
    }
    return attrs


def render_arrangement(arr: Arrangement) -> ET.Element:
    song = ET.Element("song", version="8")
    ET.SubElement(song, "title").text = arr.metadata.title
    ET.SubElement(song, "arrangement").text = arr.kind.value
    ET.SubElement(song, "offset").text = "0.000"
    ET.SubElement(song, "centOffset").text = _fmt(arr.tuning.cent_offset)
    ET.SubElement(song, "songLength").text = _fmt(arr.metadata.song_length)
    ET.SubElement(song, "startBeat").text = (
        _fmt(arr.tempo_map.beats[0].time) if arr.tempo_map.beats else "0.000"
    )
    ET.SubElement(song, "averageTempo").text = _fmt(arr.tempo_map.average_bpm)
    ET.SubElement(song, "capo").text = str(arr.capo)
    ET.SubElement(song, "artistName").text = arr.metadata.artist
    ET.SubElement(song, "albumName").text = arr.metadata.album
    if arr.metadata.year is not None:
        ET.SubElement(song, "albumYear").text = str(arr.metadata.year)

    offsets = arr.tuning.offsets_from_standard()
    ET.SubElement(
        song, "tuning", {f"string{i}": str(off) for i, off in enumerate(offsets)}
    )

    props = ET.SubElement(song, "arrangementProperties")
    props.set("pathLead", "1" if arr.kind is ArrangementKind.LEAD else "0")
    props.set("pathRhythm", "1" if arr.kind is ArrangementKind.RHYTHM else "0")
    props.set("standardTuning", "1" if all(o == 0 for o in offsets) else "0")

    phrases = ET.SubElement(song, "phrases", count="1")
    ET.SubElement(
        phrases, "phrase",
        name="default", maxDifficulty="0", disparity="0", ignore="0", solo="0",
    )
    iters = ET.SubElement(song, "phraseIterations", count="1")
    start = arr.tempo_map.beats[0].time if arr.tempo_map.beats else 0.0
    ET.SubElement(iters, "phraseIteration", time=_fmt(start), phraseId="0", variation="")

    ET.SubElement(song, "chordTemplates", count="0")

    ebeats = ET.SubElement(song, "ebeats", count=str(len(arr.tempo_map.beats)))
    for b in arr.tempo_map.beats:
        ET.SubElement(ebeats, "ebeat", time=_fmt(b.time), measure=str(b.measure))

    sections = ET.SubElement(song, "sections", count=str(len(arr.sections)))
    for s in arr.sections:
        ET.SubElement(
            sections, "section", name=s.name, number=str(s.number), startTime=_fmt(s.start_time)
        )

    levels = ET.SubElement(song, "levels", count="1")
    level = ET.SubElement(levels, "level", difficulty="0")
    notes_el = ET.SubElement(level, "notes", count=str(len(arr.notes)))
    for n in arr.notes:
        ET.SubElement(notes_el, "note", _note_attrs(n))
    ET.SubElement(level, "chords", count="0")
    anchors = ET.SubElement(level, "anchors", count=str(len(arr.notes) and 1))
    if arr.notes:
        first_fretted = next((n for n in arr.notes if n.fret > 0), arr.notes[0])
        ET.SubElement(
            anchors,
            "anchor",
            time=_fmt(arr.notes[0].time),
            fret=str(max(1, first_fretted.fret)),
            width="4.000",
        )
    ET.SubElement(level, "handShapes", count="0")
    return song


def write_arrangement_xml(arr: Arrangement, path: Path) -> Path:
    problems = arr.validate()
    if problems:
        raise ValueError("invalid arrangement: " + "; ".join(problems))
    root = render_arrangement(arr)
    tree = ET.ElementTree(root)
    ET.indent(tree)
    path.parent.mkdir(parents=True, exist_ok=True)
    tree.write(path, encoding="utf-8", xml_declaration=True)
    return path
