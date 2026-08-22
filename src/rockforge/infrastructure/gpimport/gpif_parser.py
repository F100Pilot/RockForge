"""Guitar Pro 7/8 (`.gp`) import — native GPIF (XML) parser.

PyGuitarPro reads only the GP3/GP4/GP5 *binary* formats; the modern `.gp`
container (Guitar Pro 7 and 8) is a ZIP whose ``Content/score.gpif`` is plain
XML, so RockForge parses it directly here — no extra dependency. GP6 (`.gpx`)
uses a different proprietary binary container and is still NOT supported.

This produces the SAME domain outputs as ``parser.py`` (``GpSongInfo`` /
``ParsedGpTrack``), so the rest of the GP pipeline is format-agnostic. The
GPIF model is reference-based: ``MasterBars`` point at ``Bars`` (one per track),
``Bars`` at ``Voices``, ``Voices`` at ``Beats``, ``Beats`` at ``Notes`` and a
``Rhythm``; we resolve those id maps and walk them per track.

Honest limits (mirrors the GP5 parser): 6-string guitar tracks only (no bass);
techniques covered are hammer-on/pull-off (Hopo), palm mute, slide and bend —
the same set the GP5 path emits. Melody/rhythm timing is exact from the file.
"""

from __future__ import annotations

import dataclasses
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Callable
from pathlib import Path

from rockforge.domain.errors import IngestionError
from rockforge.domain.music import (
    Beat,
    BendPoint,
    TabNote,
    Technique,
    TempoMap,
    Tuning,
    apply_sustain_gap,
    expand_slide_ins,
    expand_trills,
    is_composite_bend,
)
from rockforge.infrastructure.gpimport.parser import (  # shared model + helpers
    QUARTER_TICKS,
    GpLyricLine,
    GpSection,
    GpSongInfo,
    GpTrackInfo,
    ParsedGpTrack,
    _make_ticks_to_seconds,
)

# NoteValue name -> ticks (quarter = 960).
_NOTE_VALUE_TICKS = {
    "Whole": 4 * QUARTER_TICKS,
    "Half": 2 * QUARTER_TICKS,
    "Quarter": QUARTER_TICKS,
    "Eighth": QUARTER_TICKS // 2,
    "16th": QUARTER_TICKS // 4,
    "32nd": QUARTER_TICKS // 8,
    "64th": QUARTER_TICKS // 16,
    "128th": QUARTER_TICKS // 32,
    "256th": QUARTER_TICKS // 64,
}

# Slide Flags bitmask (GPIF): 1=shift, 2=legato are the pitched slides Rocksmith
# represents as a slide-to; out/in slides (4/8/16/32) are not slide-to targets.
_SLIDE_TO_BITS = 1 | 2


def _is_gpif(path: Path) -> bool:
    """True if *path* is a GP7/GP8 ``.gp`` container (ZIP with score.gpif)."""
    if not zipfile.is_zipfile(path):
        return False
    try:
        with zipfile.ZipFile(path) as z:
            return "Content/score.gpif" in z.namelist()
    except (zipfile.BadZipFile, OSError):
        return False


# A real score.gpif is plain markup, typically well under 1 MB even for a long
# song — generous ceiling so a maliciously crafted small-ZIP/huge-decompressed
# member ("zip bomb") can't be used to exhaust worker memory.
_MAX_GPIF_BYTES = 50 * 1024 * 1024


def _load_gpif(path: Path) -> ET.Element:
    try:
        with zipfile.ZipFile(path) as z:
            info = z.getinfo("Content/score.gpif")
            if info.file_size > _MAX_GPIF_BYTES:
                raise IngestionError(
                    f"GP7 score.gpif is implausibly large ({info.file_size} bytes "
                    "uncompressed) — refusing to decompress"
                )
            xml = z.read(info).decode("utf-8")
    except (zipfile.BadZipFile, KeyError, OSError) as exc:
        raise IngestionError(f"could not read GP7 file: {exc}") from exc
    # A GPIF score has no legitimate DOCTYPE/internal-entity declaration; reject
    # either outright rather than let the stdlib parser expand an entity bomb
    # ("billion laughs") — xml.etree.ElementTree has no built-in guard for this.
    if "<!DOCTYPE" in xml or "<!ENTITY" in xml:
        raise IngestionError("GP7 score.gpif contains a DOCTYPE/ENTITY declaration — rejected")
    try:
        return ET.fromstring(xml)
    except ET.ParseError as exc:
        raise IngestionError(f"could not parse GP7 score.gpif XML: {exc}") from exc


def _text(el: ET.Element | None, default: str = "") -> str:
    if el is None or el.text is None:
        return default
    return el.text.strip()


def _track_tuning(track: ET.Element) -> tuple[int, ...]:
    """The six MIDI pitches (low→high) from the track's Staff Tuning property."""
    staves = track.find("Staves")
    if staves is None:
        return ()
    for staff in staves.findall("Staff"):
        props = staff.find("Properties")
        if props is None:
            continue
        for prop in props.findall("Property"):
            if prop.attrib.get("name") == "Tuning":
                pitches = _text(prop.find("Pitches"))
                if pitches:
                    return tuple(int(x) for x in pitches.split())
    return ()


def _track_is_percussion(track: ET.Element) -> bool:
    instr = track.find("InstrumentSet")
    typ = _text(instr.find("Type")) if instr is not None else ""
    return "drum" in typ.lower() or "percussion" in typ.lower()


def _track_name(track: ET.Element) -> str:
    return _text(track.find("Name")) or f"Track {track.attrib.get('id', '?')}"


def _master_bar_durations(master_bars: list[ET.Element]) -> list[int]:
    """Tick length of each master bar from its time signature."""
    durations: list[int] = []
    for mb in master_bars:
        num, den = _time_signature(mb)
        durations.append(num * (4 * QUARTER_TICKS // den))
    return durations


def _time_signature(master_bar: ET.Element) -> tuple[int, int]:
    sig = _text(master_bar.find("Time"), "4/4")
    try:
        num_s, den_s = sig.split("/")
        return int(num_s), int(den_s)
    except (ValueError, AttributeError):
        return 4, 4


def inspect_gpif(path: Path) -> GpSongInfo:
    root = _load_gpif(path)
    score = root.find("Score")
    tracks_el = root.find("Tracks")
    tracks = list(tracks_el) if tracks_el is not None else []

    track_infos: list[GpTrackInfo] = []
    has_lyrics = False
    for i, track in enumerate(tracks):
        tuning = _track_tuning(track)
        track_infos.append(
            GpTrackInfo(
                index=i,
                name=_track_name(track),
                is_percussion=_track_is_percussion(track),
                string_count=len(tuning),
                tuning_midi=tuning,
            )
        )
        lyrics = track.find("Lyrics")
        if lyrics is not None and any(
            _text(line.find("Text")) for line in lyrics.findall("Line")
        ):
            has_lyrics = True

    return GpSongInfo(
        title=_text(score.find("Title")) if score is not None else "",
        artist=_text(score.find("Artist")) if score is not None else "",
        album=_text(score.find("Album")) if score is not None else "",
        tempo=int(round(_first_tempo(root))),
        tracks=tuple(track_infos),
        has_lyrics=has_lyrics,
    )


def _first_tempo(root: ET.Element) -> float:
    for tick, bpm in _tempo_events(root, [0]):
        if tick == 0:
            return bpm
    return 120.0


# GPIF tempo <Value> is "<number> <reference>", where the reference indexes a
# note-value multiplier: the authored number counts THAT note per minute, not
# always the quarter. Index 2 (x1.0) is the ordinary quarter-note BPM. Taken
# from alphaTab's model/Automation.ts; index 0 is unused, out-of-range clamps
# to 2, and a single-token <Value> (a GPX quirk) means reference 1.
_TEMPO_REFERENCES = (1.0, 0.5, 1.0, 1.5, 2.0, 3.0)


def _tempo_bpm(value: list[str]) -> float:
    """Quarter-note BPM from a GPIF <Value> token list."""
    bpm = float(value[0])
    ref = 1
    if len(value) > 1:
        try:
            ref = int(float(value[1]))
        except ValueError:
            ref = 2
    if not 1 <= ref <= 5:
        ref = 2
    return bpm * _TEMPO_REFERENCES[ref]


def _tempo_events(
    root: ET.Element,
    bar_start_ticks: list[int],
    bar_durations: list[int] | None = None,
) -> list[tuple[int, float]]:
    """(tick, bpm) change points; defaults to 120 at tick 0 if none authored."""
    events: list[tuple[int, float]] = []
    master = root.find("MasterTrack")
    autos = master.find("Automations") if master is not None else None
    if autos is not None:
        for auto in autos.findall("Automation"):
            if _text(auto.find("Type")) != "Tempo":
                continue
            value = _text(auto.find("Value")).split()
            if not value:
                continue
            bpm = _tempo_bpm(value)
            bar = int(_text(auto.find("Bar"), "0") or "0")
            ratio = float(_text(auto.find("Position"), "0") or "0")
            base = bar_start_ticks[bar] if 0 <= bar < len(bar_start_ticks) else 0
            # <Position> is a fraction of the BAR's own duration (alphaTab
            # MidiFileGenerator: barStartTick + ratioPosition * barDuration), not
            # a count of quarter notes — the two only coincide at Position 0 in
            # 4/4, so treating it as quarters put every mid-bar tempo change at
            # the wrong tick (and scaled it by the meter).
            span = (
                bar_durations[bar]
                if bar_durations is not None and 0 <= bar < len(bar_durations)
                else 4 * QUARTER_TICKS
            )
            events.append((base + int(ratio * span), bpm))
    if not any(tick == 0 for tick, _ in events):
        events.insert(0, (0, events[0][1] if events else 120.0))
    events.sort(key=lambda e: e[0])
    return events


def parse_gpif_track(
    path: Path, track_index: int, offset_s: float = 0.0, tempo_scale: float = 1.0
) -> ParsedGpTrack:
    """Convert one GP7/GP8 track to RockForge domain objects.

    Mirrors ``parser.parse_gp_track`` for the GPIF format. ``offset_s`` shifts
    the whole timeline to align with the recording; ``tempo_scale`` stretches
    (>1) / compresses (<1) the musical timeline before the offset.
    """
    if tempo_scale <= 0:
        raise IngestionError(f"tempo_scale must be positive, got {tempo_scale}")
    root = _load_gpif(path)

    tracks_el = root.find("Tracks")
    tracks = list(tracks_el) if tracks_el is not None else []
    if not 0 <= track_index < len(tracks):
        raise IngestionError(f"track index {track_index} out of range")
    track = tracks[track_index]
    if _track_is_percussion(track):
        raise IngestionError(f"track {track_index} ('{_track_name(track)}') is percussion")
    tuning_midi = _track_tuning(track)
    if len(tuning_midi) != 6:
        raise IngestionError(
            f"track {track_index} ('{_track_name(track)}') has {len(tuning_midi)} strings; "
            "Rocksmith 2014 guitar arrangements require 6 (bass support not implemented)"
        )
    tuning = Tuning(midi=tuning_midi)

    bars = {b.attrib["id"]: b for b in (root.find("Bars") or [])}
    voices = {v.attrib["id"]: v for v in (root.find("Voices") or [])}
    beats = {b.attrib["id"]: b for b in (root.find("Beats") or [])}
    notes_map = {n.attrib["id"]: n for n in (root.find("Notes") or [])}
    rhythms = {r.attrib["id"]: r for r in (root.find("Rhythms") or [])}

    master_bars = list(root.find("MasterBars") or [])
    durations = _master_bar_durations(master_bars)
    bar_start_ticks: list[int] = []
    acc = 0
    for d in durations:
        bar_start_ticks.append(acc)
        acc += d

    to_seconds = _make_ticks_to_seconds(_tempo_events(root, bar_start_ticks, durations))

    def t(tick: int) -> float:
        return max(0.0, tempo_scale * float(to_seconds(tick))) + offset_s

    raw: list[tuple[TabNote, bool, bool, bool]] = []  # (note, hopo, slide, tie_dest)
    dropped_out_of_range = 0  # notes off the 24-fret neck / beyond the tuning
    beats_grid: list[Beat] = []
    sections: list[GpSection] = []

    for mb_index, mb in enumerate(master_bars):
        bar_start = bar_start_ticks[mb_index]
        num, _den = _time_signature(mb)
        beat_len = durations[mb_index] // num if num else durations[mb_index]
        for i in range(num):
            beats_grid.append(
                Beat(time=t(bar_start + i * beat_len), measure=mb_index + 1 if i == 0 else -1)
            )
        section = mb.find("Section")
        if section is not None:
            name = _text(section.find("Text")) or _text(section.find("Letter"))
            if name:
                sections.append(GpSection(name=name, start_time=t(bar_start)))

        bar_ids = _text(mb.find("Bars")).split()
        if track_index >= len(bar_ids):
            continue
        bar = bars.get(bar_ids[track_index])
        if bar is None:
            continue
        voice_ids = _text(bar.find("Voices")).split()
        for vid in voice_ids:
            if vid == "-1":
                continue
            voice = voices.get(vid)
            if voice is None:
                continue
            tick = bar_start
            for bid in _text(voice.find("Beats")).split():
                beat = beats.get(bid)
                if beat is None:
                    continue
                rhythm = rhythms.get(_ref(beat.find("Rhythm")))
                dur = _rhythm_ticks(rhythm)
                start = t(tick)
                sustain = max(0.0, t(tick + dur) - start)
                dropped_out_of_range += _emit_beat_notes(
                    beat, notes_map, tuning_midi, start, sustain, raw
                )
                tick += dur

    merged = _merge_ties(raw)  # collapse tie continuations into the held note
    notes = _resolve_techniques([n for n, _, _ in merged], merged)
    notes = expand_slide_ins(notes)  # scoops → lead-in slide notes
    # Leave a small gap before the next note on the string (after slideTo is
    # resolved, so pitched slides keep their reach).
    notes = apply_sustain_gap(notes)
    notes = expand_trills(notes)  # trills → alternating HO/PO runs (kept tight)
    notes.sort(key=lambda n: (n.time, n.string))
    beats_grid.sort(key=lambda b: b.time)

    tempo_events = _tempo_events(root, bar_start_ticks, durations)
    avg_bpm = (tempo_events[0][1] if tempo_events else 120.0) / tempo_scale
    first_num = _time_signature(master_bars[0])[0] if master_bars else 4
    tempo_map = TempoMap(
        beats=tuple(beats_grid), average_bpm=avg_bpm, beats_per_measure=first_num
    )

    # GPIF lyrics live on whichever track carries them (usually a dedicated
    # Vocals track), not the charted instrument — so scan all tracks and use
    # the first with non-empty text.
    lyrics: list[GpLyricLine] = []
    for cand in tracks:
        lyrics = _track_lyrics(cand, bar_start_ticks, t)
        if lyrics:
            break

    warnings: list[str] = []
    if dropped_out_of_range:
        warnings.append(
            f"{dropped_out_of_range} note(s) dropped: off the 24-fret neck or on a "
            f"string beyond the tuning — likely an extended-range/bass part on this track"
        )
    return ParsedGpTrack(
        notes=notes, tuning=tuning, tempo_map=tempo_map, sections=sections,
        lyrics=lyrics, warnings=warnings,
    )


def _ref(el: ET.Element | None) -> str:
    return el.attrib.get("ref", "") if el is not None else ""


def _rhythm_ticks(rhythm: ET.Element | None) -> int:
    if rhythm is None:
        return QUARTER_TICKS
    base = _NOTE_VALUE_TICKS.get(_text(rhythm.find("NoteValue")), QUARTER_TICKS)
    dots = rhythm.find("AugmentationDot")
    if dots is not None:
        n = int(dots.attrib.get("count", "1") or "1")
        base = int(base * (2 - 0.5**n))
    tuplet = rhythm.find("PrimaryTuplet")
    if tuplet is not None:
        num = int(tuplet.attrib.get("num", "1") or "1")
        den = int(tuplet.attrib.get("den", "1") or "1")
        if num:
            base = int(base * den / num)
    return base


_GPIF_FINGERS = {"P": 0, "T": 0, "I": 1, "M": 2, "A": 3, "C": 4}  # letter fingerings


def _left_fingering(note: ET.Element) -> int:
    """Fretting finger (0-4) from a GPIF note, or -1. GPIF stores it as a letter
    (P/I/M/A/C) or a number in <LeftFingering>."""
    el = note.find("LeftFingering")
    if el is None:
        return -1
    raw = (el.text or "").strip().upper()
    if raw in _GPIF_FINGERS:
        return _GPIF_FINGERS[raw]
    try:
        v = int(raw)
    except ValueError:
        return -1
    return v if 0 <= v <= 4 else -1


def _beat_pick_direction(beat: ET.Element) -> int:
    """0 = unspecified, 1 = down, 2 = up, from a GPIF beat's brush/pick stroke."""
    brush = beat.find("Brush")
    direction = _text(brush) if brush is not None else ""
    if not direction:
        props = beat.find("Properties")
        for p in (props or []):
            if p.attrib.get("name") in ("Brush", "PickStroke"):
                direction = _text(p.find("Direction")) or _text(p)
                break
    d = direction.lower()
    if d.startswith("down"):
        return 1
    if d.startswith("up"):
        return 2
    return 0


def _note_props(note: ET.Element) -> dict[str, ET.Element]:
    props = note.find("Properties")
    if props is None:
        return {}
    return {p.attrib["name"]: p for p in props.findall("Property") if "name" in p.attrib}


def _emit_beat_notes(
    beat: ET.Element,
    notes_map: dict[str, ET.Element],
    tuning_midi: tuple[int, ...],
    start: float,
    sustain: float,
    raw: list[tuple[TabNote, bool, bool, bool]],
) -> int:
    """Append this beat's notes to ``raw``; return how many were dropped for
    being off the 24-fret neck / on a string beyond the tuning (so the caller
    can warn instead of silently swallowing them)."""
    note_ids = _text(beat.find("Notes"))
    if not note_ids:
        return 0  # rest
    dropped = 0
    # Slap/pop are beat-level in GP. GPIF has stored them as beat Properties
    # ("Slapped"/"Popped") and as direct <Slap>/<Pop> children across versions;
    # accept either so a slapped bassline isn't silently dropped.
    beat_props = {
        p.attrib["name"]
        for p in (beat.find("Properties") or [])
        if p.tag == "Property" and "name" in p.attrib
    }
    beat_slap = "Slapped" in beat_props or beat.find("Slap") is not None
    beat_pop = "Popped" in beat_props or beat.find("Pop") is not None
    beat_tremolo = beat.find("Tremolo") is not None  # tremolo picking (beat child)
    beat_pick = _beat_pick_direction(beat)
    for nid in note_ids.split():
        note = notes_map.get(nid)
        if note is None:
            continue
        props = _note_props(note)
        if "String" not in props or "Fret" not in props:
            continue
        string = int(_text(props["String"].find("String"), "0") or "0")
        fret = int(_text(props["Fret"].find("Fret"), "0") or "0")
        if not (0 <= string < len(tuning_midi) and 0 <= fret <= 24):
            dropped += 1
            continue

        techs: set[Technique] = set()
        bend_semitones = 0.0
        bend_points: tuple[BendPoint, ...] = ()
        if "PalmMuted" in props:
            techs.add(Technique.PALM_MUTE)
        if "Muted" in props:  # fret-hand mute / dead note (the "X")
            techs.add(Technique.FRET_MUTE)
        if "Harmonic" in props or "HarmonicType" in props:
            # Artificial/Pinch harmonics get the distinct pinch glyph. GPIF writes
            # the type lower-case (<HType>pinch</HType>), so compare case-folded.
            htype = (_text(props["HarmonicType"].find("HType"))
                     if "HarmonicType" in props else "").lower()
            techs.add(Technique.PINCH_HARMONIC if htype in ("artificial", "pinch")
                      else Technique.HARMONIC)
        if "LetRing" in props:
            techs.add(Technique.LET_RING)
        if note.find("Vibrato") is not None:  # direct child, not a Property
            techs.add(Technique.VIBRATO)
        if beat_tremolo:
            techs.add(Technique.TREMOLO)
        # <Accent> is a bitmask: 4 = accent, 8 = heavy accent; 1/2 (staccato/…)
        # are not Rocksmith accents.
        accent = note.find("Accent")
        if accent is not None and (int(_text(accent, "0") or "0") & 0b1100):
            techs.add(Technique.ACCENT)
        # Beat-level slap/pop and note-level tap.
        if beat_slap:
            techs.add(Technique.SLAP)
        if beat_pop:
            techs.add(Technique.POP)
        if "Tapped" in props or note.find("LeftHandTapped") is not None:
            techs.add(Technique.TAP)
        if "Bended" in props:
            techs.add(Technique.BEND)
            bend_semitones, bend_points = _bend_curve(props)
        slide_to = False
        slide_unpitch: int | None = None
        slide_in: int | None = None
        if "Slide" in props:
            flags = int(_text(props["Slide"].find("Flags"), "0") or "0")
            if flags & _SLIDE_TO_BITS:  # 1/2 = pitched shift/legato slide
                techs.add(Technique.SLIDE)
                slide_to = True
            if flags & 4:     # slide out downwards → unpitched, toward the nut
                slide_unpitch = max(1, fret - 5)
            elif flags & 8:   # slide out upwards → unpitched, toward the bridge
                slide_unpitch = min(22, fret + 5)
            if flags & 16:    # slide INTO from below → scoop up from a lower fret
                slide_in = max(1, fret - 3)
            elif flags & 32:  # slide INTO from above → scoop down from a higher fret
                slide_in = min(22, fret + 3)
        hopo_dest = "HopoDestination" in props
        left_hand = _left_fingering(note)
        # <Trill> holds the trill target's MIDI pitch; the fret is the base fret
        # shifted by the pitch difference (tuning-agnostic).
        trill_fret: int | None = None
        trill_el = note.find("Trill")
        if trill_el is not None and "Midi" in props:
            base_midi = int(_text(props["Midi"].find("Number"), "0") or "0")
            target = int(_text(trill_el, "0") or "0")
            tf = fret + (target - base_midi)
            if 0 <= tf <= 24:
                trill_fret = tf
        # A tie with destination="true" is a CONTINUATION of the previous note
        # on this string (held, not re-picked) — GP/Songsterr draw it in
        # parentheses. It must extend the previous note, not be a new attack.
        tie = note.find("Tie")
        tie_dest = tie is not None and tie.get("destination") == "true"

        raw.append(
            (
                TabNote(
                    string=string,
                    fret=fret,
                    time=start,
                    sustain=sustain,
                    techniques=frozenset(techs),
                    bend_semitones=bend_semitones,
                    slide_unpitch_to=slide_unpitch,
                    bend_points=bend_points,
                    left_hand=left_hand,
                    pick_direction=beat_pick,
                    slide_in_from=slide_in,
                    trill_fret=trill_fret,
                ),
                hopo_dest,
                slide_to,
                tie_dest,
            )
        )
    return dropped


def _merge_ties(
    raw: list[tuple[TabNote, bool, bool, bool]],
) -> list[tuple[TabNote, bool, bool]]:
    """Fold tie-continuation notes into the note they extend.

    A note flagged ``tie_dest`` is a held continuation (drawn in parentheses in
    GP/Songsterr), NOT a new attack. Extend the most recent surviving note on the
    same string to cover it and drop it — so a tie chain collapses into a single
    sustained note instead of several re-articulated notes (the "4 notes shown as
    5" bug). Orphan ties (no predecessor on the string) are kept as plain notes.
    """
    notes = [r[0] for r in raw]
    order = sorted(range(len(notes)), key=lambda i: (notes[i].string, notes[i].time))
    dropped: set[int] = set()
    for pos, idx in enumerate(order):
        if not raw[idx][3]:  # not a tie destination
            continue
        prev = None
        for k in range(pos - 1, -1, -1):
            j = order[k]
            if j not in dropped and notes[j].string == notes[idx].string:
                prev = j
                break
        if prev is None:
            continue  # orphan tie — keep as a normal note
        end = notes[idx].time + notes[idx].sustain
        notes[prev] = dataclasses.replace(
            notes[prev], sustain=max(notes[prev].sustain, end - notes[prev].time)
        )
        dropped.add(idx)
    return [
        (notes[i], raw[i][1], raw[i][2]) for i in range(len(raw)) if i not in dropped
    ]


def _bend_prop(props: dict[str, ET.Element], key: str) -> float | None:
    if key not in props:
        return None
    v = _text(props[key].find("Float")) or _text(props[key])
    try:
        return float(v)
    except ValueError:
        return None


def _bend_curve(props: dict[str, ET.Element]) -> tuple[float, tuple[BendPoint, ...]]:
    """(peak in half-steps, full curve). GPIF bend value 100 == one whole tone
    (2 half-steps); offsets are a 0..100 position along the note. Origin / Middle
    / Destination give up to three points, so pre-bends and releases survive."""
    steps = {  # position fraction (0..1) -> value (0..100)
        "origin": (_bend_prop(props, "BendOriginOffset") or 0.0,
                   _bend_prop(props, "BendOriginValue")),
        "middle": (_bend_prop(props, "BendMiddleOffset1")
                   or _bend_prop(props, "BendMiddleOffset2") or 50.0,
                   _bend_prop(props, "BendMiddleValue")),
        "dest": (_bend_prop(props, "BendDestinationOffset") or 100.0,
                 _bend_prop(props, "BendDestinationValue")),
    }
    pts = [
        BendPoint(position=min(max(off, 0.0), 100.0) / 100.0, step=val / 50.0)
        for off, val in steps.values()
        if val is not None
    ]
    if not pts:
        return 0.0, ()
    pts.sort(key=lambda p: p.position)
    peak = max(p.step for p in pts)
    return peak, (tuple(pts) if is_composite_bend(pts) else ())


def _resolve_techniques(
    notes: list[TabNote], raw: list[tuple[TabNote, bool, bool]]
) -> list[TabNote]:
    """Hammer/pull (from Hopo destination) and slide-to fret, like the GP5 path.

    GPIF tags the legato DESTINATION (``HopoDestination``); compare its fret to
    the previous note on the same string to pick HAMMER_ON vs PULL_OFF. For a
    slide note, the target fret is the next note on the same string.
    """
    order = sorted(range(len(notes)), key=lambda i: (notes[i].string, notes[i].time))
    for pos, idx in enumerate(order):
        note, hopo_dest, slide_to = raw[idx]
        prev_idx = order[pos - 1] if pos > 0 else None
        next_idx = order[pos + 1] if pos + 1 < len(order) else None

        if hopo_dest and prev_idx is not None and notes[prev_idx].string == note.string:
            tech = (
                Technique.HAMMER_ON
                if note.fret > notes[prev_idx].fret
                else Technique.PULL_OFF
            )
            notes[idx] = dataclasses.replace(
                notes[idx], techniques=notes[idx].techniques | {tech}
            )

        if slide_to and next_idx is not None and notes[next_idx].string == note.string:
            notes[idx] = dataclasses.replace(notes[idx], slide_to_fret=notes[next_idx].fret)
    return notes


def _track_lyrics(
    track: ET.Element, bar_start_ticks: list[int], t: Callable[[int], float]
) -> list[GpLyricLine]:
    lyrics_el = track.find("Lyrics")
    if lyrics_el is None:
        return []
    out: list[GpLyricLine] = []
    for line in lyrics_el.findall("Line"):
        text = _text(line.find("Text"))
        if not text:
            continue
        bar = int(_text(line.find("Offset"), "0") or "0")
        tick = bar_start_ticks[bar] if 0 <= bar < len(bar_start_ticks) else 0
        out.append(GpLyricLine(time=t(tick), text=text))
    return out
