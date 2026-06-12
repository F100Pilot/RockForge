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

CHORD_EPSILON_S = 0.03  # notes starting within 30 ms form a chord (matches fret mapper)


def _fmt(x: float) -> str:
    return f"{x:.3f}"


def _group_chords(notes: list[TabNote]) -> list[list[TabNote]]:
    """Group simultaneous notes; singletons stay single notes, groups become chords."""
    ordered = sorted(notes, key=lambda n: (n.time, n.string))
    groups: list[list[TabNote]] = []
    for n in ordered:
        if groups and n.time - groups[-1][0].time <= CHORD_EPSILON_S:
            groups[-1].append(n)
        else:
            groups.append([n])
    return groups


def _chord_template_key(group: list[TabNote]) -> tuple[int, ...]:
    """Fret per string (-1 = unused) — identifies a chordTemplate."""
    frets = [-1] * 6
    for n in group:
        frets[n.string] = n.fret
    return tuple(frets)


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
    ET.SubElement(song, "part").text = "1"
    ET.SubElement(song, "offset").text = "0.000"
    ET.SubElement(song, "centOffset").text = _fmt(arr.tuning.cent_offset)
    ET.SubElement(song, "songLength").text = _fmt(arr.metadata.song_length)
    ET.SubElement(song, "songNameSort").text = arr.metadata.title
    ET.SubElement(song, "startBeat").text = (
        _fmt(arr.tempo_map.beats[0].time) if arr.tempo_map.beats else "0.000"
    )
    ET.SubElement(song, "averageTempo").text = _fmt(arr.tempo_map.average_bpm)

    offsets = arr.tuning.offsets_from_standard()
    ET.SubElement(
        song, "tuning", {f"string{i}": str(off) for i, off in enumerate(offsets)}
    )
    ET.SubElement(song, "capo").text = str(arr.capo)
    ET.SubElement(song, "artistName").text = arr.metadata.artist
    ET.SubElement(song, "artistNameSort").text = arr.metadata.artist
    ET.SubElement(song, "albumName").text = arr.metadata.album
    ET.SubElement(song, "albumNameSort").text = arr.metadata.album
    if arr.metadata.year is not None:
        ET.SubElement(song, "albumYear").text = str(arr.metadata.year)
    ET.SubElement(song, "albumArt").text = ""
    ET.SubElement(song, "crowdSpeed").text = "1"

    # arrangementProperties: per Song2014.cs (SongArrangementProperties2014),
    # only bonusArr/Metronome/pathLead/pathRhythm/pathBass/routeMask exist.
    # routeMask: 1=lead, 2=rhythm, 4=bass.
    route_mask = "2" if arr.kind is ArrangementKind.RHYTHM else "1"
    props = ET.SubElement(song, "arrangementProperties")
    props.set("bonusArr", "0")
    props.set("Metronome", "0")
    props.set("pathLead", "1" if arr.kind is not ArrangementKind.RHYTHM else "0")
    props.set("pathRhythm", "1" if arr.kind is ArrangementKind.RHYTHM else "0")
    props.set("pathBass", "0")
    props.set("routeMask", route_mask)

    ET.SubElement(song, "lastConversionDateTime").text = "1-1-2000 00:00:00"

    phrases = ET.SubElement(song, "phrases", count="1")
    ET.SubElement(
        phrases, "phrase",
        name="default", maxDifficulty="0", disparity="0", ignore="0", solo="0",
    )
    iters = ET.SubElement(song, "phraseIterations", count="1")
    start = arr.tempo_map.beats[0].time if arr.tempo_map.beats else 0.0
    ET.SubElement(iters, "phraseIteration", time=_fmt(start), phraseId="0", variation="")

    ET.SubElement(song, "newLinkedDiffs", count="0")
    ET.SubElement(song, "linkedDiffs", count="0")
    ET.SubElement(song, "phraseProperties", count="0")

    # Chord handling: simultaneous notes become <chord> entries referencing a
    # chordTemplate (documented in Song2014.cs / Rocksmith2014.XML). Finger
    # assignments are unknown from audio — emitted as -1, to be refined in EOF.
    groups = _group_chords(arr.notes)
    single_notes = [g[0] for g in groups if len(g) == 1]
    chord_groups = [g for g in groups if len(g) > 1]

    template_ids: dict[tuple[int, ...], int] = {}
    for g in chord_groups:
        key = _chord_template_key(g)
        if key not in template_ids:
            template_ids[key] = len(template_ids)

    templates_el = ET.SubElement(song, "chordTemplates", count=str(len(template_ids)))
    for key, _tid in sorted(template_ids.items(), key=lambda kv: kv[1]):
        attrs = {"chordName": "", "displayName": ""}
        for i in range(6):
            attrs[f"fret{i}"] = str(key[i])
            attrs[f"finger{i}"] = "-1"
        ET.SubElement(templates_el, "chordTemplate", attrs)

    ET.SubElement(song, "fretHandMuteTemplates", count="0")

    ebeats = ET.SubElement(song, "ebeats", count=str(len(arr.tempo_map.beats)))
    for b in arr.tempo_map.beats:
        ET.SubElement(ebeats, "ebeat", time=_fmt(b.time), measure=str(b.measure))

    # Tones: <tonebase> + tonea-toned slots + timed <tones> switches. Element
    # names per Song2014.cs (research §5 — inference from toolkit releases).
    if arr.tone_base:
        ET.SubElement(song, "tonebase").text = arr.tone_base
    for slot, name in zip(("tonea", "toneb", "tonec", "toned"), arr.tone_names, strict=False):
        ET.SubElement(song, slot).text = name
    tones_el = ET.SubElement(song, "tones", count=str(len(arr.tone_changes)))
    for tc in sorted(arr.tone_changes, key=lambda c: c.time):
        ET.SubElement(tones_el, "tone", time=_fmt(tc.time), name=tc.name)

    sections = ET.SubElement(song, "sections", count=str(len(arr.sections)))
    for s in arr.sections:
        ET.SubElement(
            sections, "section", name=s.name, number=str(s.number), startTime=_fmt(s.start_time)
        )

    ET.SubElement(song, "events", count="0")

    transcription = ET.SubElement(song, "transcriptionTrack", difficulty="-1")
    ET.SubElement(transcription, "notes", count="0")
    ET.SubElement(transcription, "chords", count="0")
    ET.SubElement(transcription, "anchors", count="0")
    ET.SubElement(transcription, "handShapes", count="0")

    levels = ET.SubElement(song, "levels", count="1")
    level = ET.SubElement(levels, "level", difficulty="0")
    notes_el = ET.SubElement(level, "notes", count=str(len(single_notes)))
    for n in single_notes:
        ET.SubElement(notes_el, "note", _note_attrs(n))
    chords_el = ET.SubElement(level, "chords", count=str(len(chord_groups)))
    for g in chord_groups:
        chord_id = template_ids[_chord_template_key(g)]
        chord_el = ET.SubElement(
            chords_el, "chord",
            time=_fmt(g[0].time), chordId=str(chord_id), linkNext="0", accent="0",
            fretHandMute="0", highDensity="0", ignore="0", palmMute="0",
            hopo="0", strum="down",
        )
        for n in g:  # chordNote children preserve per-string technique data
            ET.SubElement(chord_el, "chordNote", _note_attrs(n))
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
