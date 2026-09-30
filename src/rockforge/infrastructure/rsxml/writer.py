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

from rockforge.domain.arrangement import Arrangement, ArrangementKind, Section, number_sections
from rockforge.domain.music import TabNote, Technique, high_density_flags, is_plain_rise

CHORD_EPSILON_S = 0.03  # notes starting within 30 ms form a chord (matches fret mapper)


def _fmt(x: float) -> str:
    return f"{x:.3f}"


# A tone switch must NOT land exactly on a note time — DLC Builder errors on a
# tone change coinciding with a note. Place it just before the note it starts on
# (nearest note to the requested time), but strictly after the previous note so
# it never overlaps it. Per-arrangement (each arrangement has its own notes).
TONE_SWITCH_GAP_S = 0.02
TONE_COLLISION_S = 0.01  # within this of a note = "on the note", must be nudged


def _safe_tone_time(t: float, note_times: list[float]) -> float:
    if not note_times:
        return round(max(0.0, t), 3)
    target = min(note_times, key=lambda nt: abs(nt - t))  # nearest note
    if abs(target - t) > TONE_COLLISION_S:
        return round(max(0.0, t), 3)  # not on a note — already safe, leave it
    prev = max((nt for nt in note_times if nt < target - 1e-4), default=None)
    safe = target - TONE_SWITCH_GAP_S
    lo = prev if prev is not None else target - 2 * TONE_SWITCH_GAP_S
    if safe <= lo + 1e-4:  # previous note too close — sit halfway between them
        safe = (lo + target) / 2.0
    return round(max(0.0, safe), 3)


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


def _anchor_for_frets(frets: list[int]) -> tuple[int, int]:
    """Fretboard position (fret, width) covering the given fret positions.

    Open strings (fret 0) don't constrain the anchor position. width is
    clamped to the 1-24 fret range Rocksmith's fretboard highlight covers.
    """
    used = [f for f in frets if f > 0]
    if not used:
        return 1, 4
    lo, hi = min(used), max(used)
    width = min(max(4, hi - lo + 1), 24)
    fret = max(1, min(lo, 25 - width))
    return fret, width


def _build_anchors(groups: list[list[TabNote]]) -> list[tuple[float, int, int]]:
    """One anchor per note group whose frets fall outside the current anchor.

    Without per-position anchors, Rocksmith keeps the fretboard highlight
    fixed at the song's first position regardless of where notes actually
    are — this is what makes the highlight "follow" the played frets.
    """
    anchors: list[tuple[float, int, int]] = []
    current: tuple[int, int] | None = None
    for g in groups:
        used = [n.fret for n in g if n.fret > 0]
        if not used:
            continue
        if current is not None and all(
            current[0] <= f <= current[0] + current[1] - 1 for f in used
        ):
            continue
        fret, width = _anchor_for_frets(used)
        anchors.append((g[0].time, fret, width))
        current = (fret, width)
    if not anchors and groups:
        anchors.append((groups[0][0].time, 1, 4))
    return anchors


def _chord_template_key(group: list[TabNote]) -> tuple[int, ...]:
    """Fret per string (-1 = unused) — identifies a chordTemplate."""
    frets = [-1] * 6
    for n in group:
        frets[n.string] = n.fret
    return tuple(frets)


def _drop_defaults(attrs: dict[str, str], required: set[str]) -> dict[str, str]:
    """Editor on Fire (the reference DLC Builder source) omits note/chord
    attributes that equal the Song2014 XML schema default ("0"/"-1"); the mere
    *presence* of some of them (even ="0") makes the in-game highway pick a
    non-default sprite — a plain sustained note then renders with a spurious
    technique glyph inside its box. Keep `required` keys regardless of value."""
    return {k: v for k, v in attrs.items() if k in required or v not in ("0", "-1")}


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
        "harmonicPinch": "1" if has(Technique.PINCH_HARMONIC) else "0",
        "palmMute": "1" if has(Technique.PALM_MUTE) else "0",
        "vibrato": "1" if has(Technique.VIBRATO) else "0",
        "tremolo": "1" if has(Technique.TREMOLO) else "0",
        "tap": "1" if has(Technique.TAP) else "0",
        "slap": "1" if has(Technique.SLAP) else "0",
        "pluck": "1" if has(Technique.POP) else "0",
        "linkNext": "0",
        "accent": "1" if has(Technique.ACCENT) else "0",
        "hopo": "1" if has(Technique.HAMMER_ON) or has(Technique.PULL_OFF) else "0",
        "slideTo": str(n.slide_to_fret) if n.slide_to_fret is not None else "-1",
        "slideUnpitchTo": str(n.slide_unpitch_to) if n.slide_unpitch_to is not None else "-1",
        "mute": "1" if has(Technique.FRET_MUTE) else "0",
        "leftHand": str(n.left_hand) if n.left_hand >= 0 else "-1",
        # A single bit, set for an upstroke: DLC Builder reads it with
        # ParseBinary(v) << 10, so our "2" (= up) landed on bit 11, SLAP.
        "pickDirection": "1" if n.pick_direction == 2 else "0",
    }
    return _drop_defaults(attrs, {"time", "string", "fret", "sustain"})


def _bend_time(n: TabNote) -> float:
    """When a simple bend reaches its peak: the note's END (attack + sustain), as
    a decoded DLC Builder SNG places it — the pitch ramps UP across the note (a
    visible bend). A bendValue AT the attack is a prebend (already-bent, smaller
    looking). Floored for a staccato note so the point still lands after the
    attack."""
    return n.time + (n.sustain if n.sustain > 0.03 else 0.1)


def _bend_curve(n: TabNote) -> list[tuple[float, float]]:
    """(time, step) bend points for a note, in absolute song time.

    A full ``bend_points`` curve (pre-bend / release / multi-step) is emitted as
    given, its fractional positions scaled onto the note's duration. Otherwise a
    single peak reached at the note's END (the DLC Builder shape — a visible
    bend-up rather than an already-bent prebend), which is also how a plain rise
    across the note is written."""
    dur = n.sustain if n.sustain > 0.03 else 0.1
    if n.bend_points and not is_plain_rise(n.bend_points):
        return [(n.time + p.position * dur, p.step) for p in n.bend_points]
    return [(_bend_time(n), n.bend_semitones)]


def _append_note_el(parent: ET.Element, tag: str, n: TabNote) -> ET.Element:
    """Create a <note>/<chordNote> and, for a bend, its <bendValues> curve.

    The `bend="N"` attribute alone is only the peak; Rocksmith/DLC Builder read
    the actual pitch from <bendValues>. Emitting the flag WITHOUT the curve (the
    previous behaviour) made DLC Builder build the arrangement with no real bend
    at all — the half-step bends in the chart simply disappeared.
    """
    el = ET.SubElement(parent, tag, _note_attrs(n))
    if Technique.BEND in n.techniques and n.bend_semitones > 0:
        curve = _bend_curve(n)
        bends = ET.SubElement(el, "bendValues", count=str(len(curve)))
        for t, step in curve:
            # unk5="0" mirrors DLC Builder / a pro chart's <bendValue> format.
            ET.SubElement(bends, "bendValue", time=_fmt(t), step=_fmt(step), unk5="0")
    return el


def render_arrangement(arr: Arrangement, album_art_urn: str | None = None) -> ET.Element:
    song = ET.Element("song", version="8")
    ET.SubElement(song, "title").text = arr.metadata.title
    # The <arrangement> tag carries the Rocksmith path name (Lead/Rhythm/Combo) —
    # an alternate folds onto its base name, not the display "Alternate Lead".
    ET.SubElement(song, "arrangement").text = arr.kind.base_kind.value
    ET.SubElement(song, "part").text = "1"
    # offset = -startBeat (negative of the first beat's time): DLC Builder/EOF
    # treat this as "song time 0 is `offset` seconds before audio time 0" and
    # use it to re-derive the lead-in on import. Leaving it at 0 while the
    # first beat/notes are shifted (sync lead-in) makes those tools re-zero
    # everything, discarding the lead-in.
    start_beat = arr.tempo_map.beats[0].time if arr.tempo_map.beats else 0.0
    ET.SubElement(song, "offset").text = _fmt(-start_beat)
    ET.SubElement(song, "centOffset").text = _fmt(arr.tuning.cent_offset)
    ET.SubElement(song, "songLength").text = _fmt(arr.metadata.song_length)
    ET.SubElement(song, "songNameSort").text = arr.metadata.title
    ET.SubElement(song, "startBeat").text = _fmt(start_beat)
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
    # The DDS album-art URN. Rocksmith resolves the in-game cover through the
    # MANIFEST's AlbumArt attribute, not this field, and the instrumental XML is
    # not even shipped inside the .psarc (only the showlights one is) — so this
    # is completeness for the DLC Builder path, which reads the XML on import.
    # Empty when the caller has no song key, exactly as before.
    ET.SubElement(song, "albumArt").text = album_art_urn or ""
    ET.SubElement(song, "crowdSpeed").text = "1"

    # arrangementProperties: the DLC Builder parser (Rocksmith2014.XML
    # ArrangementProperties.ReadXml) dereferences every attribute below without
    # a null check — ALL of them must be present or import fails with an NRE.
    techniques = {t for n in arr.notes for t in n.techniques}
    groups_preview = _group_chords(arr.notes)
    has_chords = any(len(g) > 1 for g in groups_preview)
    has_double_stops = any(len(g) == 2 for g in groups_preview)
    is_rhythm = arr.kind.base_kind is ArrangementKind.RHYTHM
    is_alt = arr.kind.is_alternate
    props = ET.SubElement(song, "arrangementProperties")
    for attr, value in (
        ("represent", "0" if is_alt else "1"),
        ("bonusArr", "1" if is_alt else "0"),
        ("standardTuning", "1" if all(o == 0 for o in offsets) else "0"),
        ("nonStandardChords", "0"),
        ("barreChords", "0"),
        ("powerChords", "1" if has_chords else "0"),
        ("dropDPower", "0"),
        ("openChords", "1" if has_chords else "0"),
        ("fingerPicking", "0"),
        ("pickDirection", "1" if any(n.pick_direction for n in arr.notes) else "0"),
        ("doubleStops", "1" if has_double_stops else "0"),
        ("palmMutes", "1" if Technique.PALM_MUTE in techniques else "0"),
        ("harmonics", "1" if Technique.HARMONIC in techniques else "0"),
        ("pinchHarmonics", "1" if Technique.PINCH_HARMONIC in techniques else "0"),
        ("hopo", "1" if {Technique.HAMMER_ON, Technique.PULL_OFF} & techniques else "0"),
        ("tremolo", "1" if Technique.TREMOLO in techniques else "0"),
        ("slides", "1" if Technique.SLIDE in techniques else "0"),
        ("unpitchedSlides", "1" if any(n.slide_unpitch_to is not None for n in arr.notes)
         else "0"),
        ("bends", "1" if Technique.BEND in techniques else "0"),
        ("tapping", "1" if Technique.TAP in techniques else "0"),
        ("vibrato", "1" if Technique.VIBRATO in techniques else "0"),
        ("fretHandMutes", "1" if Technique.FRET_MUTE in techniques else "0"),
        ("slapPop", "1" if {Technique.SLAP, Technique.POP} & techniques else "0"),
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
    start = start_beat
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
    tone_note_times = sorted(n.time for n in arr.notes)
    for tc in sorted(arr.tone_changes, key=lambda c: c.time):
        safe_t = _safe_tone_time(tc.time, tone_note_times)
        ET.SubElement(tones_el, "tone", time=_fmt(safe_t), name=tc.name)

    # Sections must cover the song and end with the conventional "noguitar"
    # closer at the END phrase time (Riff Repeater navigation + song-end cue).
    # Numbers are PER NAME, 1-based (domain.number_sections) — the same helper
    # the SNG path uses, so the two can't drift. Renumbering here also fixes the
    # closer: it was hard-coded to 1 and collided with a real "noguitar" section
    # of the same number.
    section_rows = [s for s in arr.sections if s.start_time < end_time]
    if not section_rows:
        section_rows = [Section(name="riff", start_time=default_t)]
    section_rows.append(Section(name="noguitar", start_time=end_time))
    numbered, _counts = number_sections(section_rows)
    sections = ET.SubElement(song, "sections", count=str(len(numbered)))
    for sec in numbered:
        ET.SubElement(
            sections, "section", name=sec.name, number=str(sec.number),
            startTime=_fmt(sec.start_time),
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
        _append_note_el(notes_el, "note", n)
    chords_el = ET.SubElement(level, "chords", count=str(len(chord_groups)))
    hd_flags = high_density_flags(chord_groups)
    for gi, g in enumerate(chord_groups):
        chord_id = template_ids[_chord_template_key(g)]
        # The game reads palm mute / accent / HOPO from the <chord> element, not
        # from its chordNote children; an inconsistency between the two renders
        # the chord with a corrupt highway sprite. Mirror the per-note technique
        # onto the chord when every note in it carries that technique.
        chord_pm = all(Technique.PALM_MUTE in n.techniques for n in g)
        chord_accent = all(Technique.ACCENT in n.techniques for n in g)
        chord_hopo = all(
            {Technique.HAMMER_ON, Technique.PULL_OFF} & n.techniques for n in g
        )
        chord_attrs = {
            "time": _fmt(g[0].time),
            "chordId": str(chord_id),
            "linkNext": "0",
            "accent": "1" if chord_accent else "0",
            "fretHandMute": "0",
            # Repeated identical chords in a fast run render condensed; emitting
            # them all as full boxes stacks the sprites into a corrupt blur.
            "highDensity": "1" if hd_flags[gi] else "0",
            "ignore": "0",
            "palmMute": "1" if chord_pm else "0",
            "hopo": "1" if chord_hopo else "0",
            "strum": "down",
        }
        chord_el = ET.SubElement(
            chords_el, "chord", _drop_defaults(chord_attrs, {"time", "chordId", "strum"})
        )
        for n in g:  # chordNote children preserve per-string technique data
            _append_note_el(chord_el, "chordNote", n)
    anchor_list = _build_anchors(groups)
    anchors = ET.SubElement(level, "anchors", count=str(len(anchor_list)))
    for time, fret, width in anchor_list:
        ET.SubElement(anchors, "anchor", time=_fmt(time), fret=str(fret), width=_fmt(float(width)))
    ET.SubElement(level, "handShapes", count="0")
    return song


def write_arrangement_xml(
    arr: Arrangement, path: Path, album_art_urn: str | None = None
) -> Path:
    problems = arr.validate()
    if problems:
        raise ValueError("invalid arrangement: " + "; ".join(problems))
    root = render_arrangement(arr, album_art_urn)
    tree = ET.ElementTree(root)
    ET.indent(tree)
    path.parent.mkdir(parents=True, exist_ok=True)
    tree.write(path, encoding="utf-8", xml_declaration=True)
    return path
