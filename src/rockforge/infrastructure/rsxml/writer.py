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

    # arrangementProperties: the DLC Builder parser (Rocksmith2014.XML
    # ArrangementProperties.ReadXml) dereferences every attribute below without
    # a null check — ALL of them must be present or import fails with an NRE.
    techniques = {t for n in arr.notes for t in n.techniques}
    groups_preview = _group_chords(arr.notes)
    has_chords = any(len(g) > 1 for g in groups_preview)
    has_double_stops = any(len(g) == 2 for g in groups_preview)
    is_rhythm = arr.kind is ArrangementKind.RHYTHM
    props = ET.SubElement(song, "arrangementProperties")
    for attr, value in (
        ("represent", "1"),
        ("bonusArr", "0"),
        ("standardTuning", "1" if all(o == 0 for o in offsets) else "0"),
        ("nonStandardChords", "0"),
        ("barreChords", "0"),
        ("powerChords", "1" if has_chords else "0"),
        ("dropDPower", "0"),
        ("openChords", "1" if has_chords else "0"),
        ("fingerPicking", "0"),
        ("pickDirection", "0"),
        ("doubleStops", "1" if has_double_stops else "0"),
        ("palmMutes", "1" if Technique.PALM_MUTE in techniques else "0"),
        ("harmonics", "1" if Technique.HARMONIC in techniques else "0"),
        ("pinchHarmonics", "0"),
        ("hopo", "1" if {Technique.HAMMER_ON, Technique.PULL_OFF} & techniques else "0"),
        ("tremolo", "0"),
        ("slides", "1" if Technique.SLIDE in techniques else "0"),
        ("unpitchedSlides", "0"),
        ("bends", "1" if Technique.BEND in techniques else "0"),
        ("tapping", "0"),
        ("vibrato", "1" if Technique.VIBRATO in techniques else "0"),
        ("fretHandMutes", "0"),
        ("slapPop", "0"),
        ("twoFingerPicking", "0"),
        ("fifthsAndOctaves", "0"),
        ("syncopation", "0"),
        ("bassPick", "0"),
        ("sustain", "1" if any(n.sustain > 0 for n in arr.notes) else "0"),
        ("pathLead", "0" if is_rhythm else "1"),
        ("pathRhythm", "1" if is_rhythm else "0"),
        ("pathBass", "0"),
        ("routeMask", "2" if is_rhythm else "1"),
        ("Metronome", "0"),
    ):
        props.set(attr, value)

    ET.SubElement(song, "lastConversionDateTime").text = "1-1-2000 00:00:00"

    # Phrase structure drives the in-game timeline: Rocksmith ends the song at
    # the LAST phraseIteration (the conventional "END" phrase). With a single
    # iteration at the start beat the game finishes seconds in, with the note
    # highway frozen. Minimum viable structure (EOF/toolkit convention):
    # COUNT @ first beat -> default @ first note -> END @ song end.
    start = arr.tempo_map.beats[0].time if arr.tempo_map.beats else 0.0
    first_note_t = min((n.time for n in arr.notes), default=start)
    last_note_end = max((n.time + max(n.sustain, 0.0) for n in arr.notes), default=start)
    last_beat = arr.tempo_map.beats[-1].time if arr.tempo_map.beats else 0.0
    # Anchor END to the beat grid when it already covers the notes (the SNG
    # build maps phrase times onto beats); otherwise place it just past the
    # last note's tail.
    end_time = last_beat if last_beat > last_note_end else last_note_end + 0.1

    phrases = ET.SubElement(song, "phrases", count="3")
    for phrase_name in ("COUNT", "default", "END"):
        ET.SubElement(
            phrases, "phrase",
            name=phrase_name, maxDifficulty="0", disparity="0", ignore="0", solo="0",
        )
    iters = ET.SubElement(song, "phraseIterations", count="3")
    default_t = max(first_note_t, start)
    for time, phrase_id in ((start, "0"), (default_t, "1"), (end_time, "2")):
        ET.SubElement(iters, "phraseIteration", time=_fmt(time), phraseId=phrase_id, variation="")

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

    # Sections must cover the song and end with the conventional "noguitar"
    # closer at the END phrase time (Riff Repeater navigation + song-end cue).
    section_rows: list[tuple[str, int, float]] = [
        (s.name, s.number, s.start_time) for s in arr.sections if s.start_time < end_time
    ]
    if not section_rows:
        section_rows.append(("riff", 1, default_t))
    section_rows.append(("noguitar", 1, end_time))
    sections = ET.SubElement(song, "sections", count=str(len(section_rows)))
    for name, number, start_time in section_rows:
        ET.SubElement(
            sections, "section", name=name, number=str(number), startTime=_fmt(start_time)
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
