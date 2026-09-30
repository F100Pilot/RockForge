"""A Songsterr tab written as a Guitar Pro 5 file.

Songsterr's web player draws each track from a JSON "part" (measures → voices
→ beats → notes). Rebuilding a Guitar Pro file from those parts is what
``teaqu/guitar-pro-youtube-sync`` does (it writes GP7 XML); this module does the
same job its own way, writing **GP5** with PyGuitarPro — the library RockForge
already reads GP5 with and writes it with (``gpexport/arrangement_writer``) —
so the result goes through the SAME importer as an uploaded file, and every
existing tool (track choice, Songsterr bar times, reload, export) applies
unchanged. The field meanings below were read off that tool's converter; the
code is not copied from it.

What a part carries, and how it maps:

- track: ``strings``, ``tuning`` (MIDI, HIGHEST string first — Songsterr's
  string 0 is the high e, which is GP5's string 1), ``instrument``; no tuning
  or a drum instrument = percussion, skipped (RockForge charts guitars).
- measure: ``signature`` ``[n, d]`` (carries forward until changed),
  ``marker.text`` (a section), ``voices[].beats[]``.
- beat: ``type`` (1, 2, 4 … 64 = whole … 64th), ``dots``, ``tuplet`` (3, 5,
  6, 7, 9), ``rest``, ``letRing``, ``graceNote``, ``notes[]``.
- note: ``fret``, ``string``, ``tie`` (a held continuation), ``hp`` (this note
  is the TARGET of a hammer-on/pull-off — GP5 marks the ORIGIN, the previous
  note on the string), ``slide``, ``bend.points[]`` (``position`` 0..60,
  ``tone`` 50 = half tone), ``vibrato``, ``ghost``, ``staccato``,
  ``accentuated`` (1 normal, 2 heavy); ``dead``/``palmMute``/``harmonic`` are
  read when present.
- tempo: the first track's ``automations.tempo[]`` ``{measure, bpm}``; the
  first one is the song tempo, later ones a mix-table change on that measure's
  first beat, exactly how GP5 stores it (see ``gpexport/tempo_writer``).

- lyrics: a part's ``newLyrics[]`` ``{text, offset}`` — the sung text (words
  by spaces, syllables by hyphens; extra spaces skip notes) and the 0-based
  measure it starts on. Written as the GP5 song lyrics, bound to THAT part's
  track (``trackChoice``), so the importer hands each syllable to the next note
  of the part it was written for — normally the vocal line — exactly as
  Guitar Pro would. GP5 holds five lines; more are dropped and counted.

Honest limits, all counted in the report rather than hidden: grace notes are
dropped (in GP5 they are an ornament on the NEXT note, not a beat, and writing
them as beats would push the rhythm late); a mid-measure tempo change is moved
to its measure's start; lyrics on a part that could not be written (no strings)
fall back to the first track's notes; text GP5 cannot store (it is cp1252)
becomes "?".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rockforge.domain.errors import IngestionError
from rockforge.i18n import tr

QUARTER_TICKS = 960  # PyGuitarPro's Duration.quarterTime; bar 1 starts here
_DURATIONS = {1, 2, 4, 8, 16, 32, 64}
_TUPLETS = {3: (3, 2), 5: (5, 4), 6: (6, 4), 7: (7, 4), 9: (9, 8), 10: (10, 8), 12: (12, 8)}
# Songsterr slide names → PyGuitarPro SlideType member names.
_SLIDES = {
    "shift": "shiftSlideTo", "toNext": "shiftSlideTo", "legato": "legatoSlideTo",
    "below": "intoFromBelow", "above": "intoFromAbove",
    "downwards": "outDownwards", "upwards": "outUpwards",
    "belowshift": "intoFromBelow",
}


@dataclass
class SongsterrGpReport:
    tracks: int = 0
    measures: int = 0
    notes: int = 0
    skipped_tracks: list[str] = field(default_factory=list)
    grace_dropped: int = 0
    tempo_moved: int = 0
    lyric_lines: int = 0
    warnings: list[str] = field(default_factory=list)


def _gp5_text(value: str) -> str:
    """Text GP5 can store: its strings are cp1252 (PyGuitarPro encodes them
    strictly), so anything outside it — a Cyrillic or Japanese title, say —
    would abort the whole write. It becomes "?" instead."""
    return value.encode("cp1252", "replace").decode("cp1252")


def _lyrics(
    parts: list[dict[str, Any]],
    kept: list[tuple[str, dict[str, Any]]],
    report: SongsterrGpReport,
    guitarpro: Any,
) -> Any | None:
    """The first part's ``newLyrics`` as GP5 song lyrics, bound to its track."""
    for part in parts:
        lines = [
            ln for ln in part.get("newLyrics") or []
            if isinstance(ln, dict) and str(ln.get("text") or "").strip()
        ]
        if not lines:
            continue
        lyrics = guitarpro.Lyrics()
        index = next((i for i, (_n, p) in enumerate(kept) if p is part), None)
        if index is None:
            index = 0
            name = str(part.get("name") or part.get("instrument") or "?")
            report.warnings.append(tr(
                f"a letra está numa pista que não foi incluída ({name}): as sílabas "
                "seguem as notas da primeira pista",
                f"the lyrics are on a track that was not included ({name}): the "
                "syllables follow the notes of the first track",
            ))
        lyrics.trackChoice = index + 1  # GP5 counts tracks from 1; 0 = none
        for slot, line in zip(lyrics.lines, lines, strict=False):
            slot.startingMeasure = max(0, _int(line.get("offset"), 0)) + 1
            slot.lyrics = _gp5_text(str(line["text"]))
        report.lyric_lines = min(len(lines), guitarpro.Lyrics.maxLineCount)
        if len(lines) > guitarpro.Lyrics.maxLineCount:
            cap = guitarpro.Lyrics.maxLineCount
            extra = len(lines) - cap
            report.warnings.append(tr(
                f"{extra} linha(s) de letra a mais não incluídas (o GP5 guarda {cap})",
                f"{extra} extra lyric line(s) not included (GP5 holds {cap})",
            ))
        return lyrics
    return None


def is_percussion(part: dict[str, Any]) -> bool:
    return not part.get("tuning") or "drum" in str(part.get("instrument", "")).lower()


def _int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _duration(beat: dict[str, Any], guitarpro: Any) -> Any:
    value = _int(beat.get("type"), 4)
    if value not in _DURATIONS:
        value = 4
    enters, times = _TUPLETS.get(_int(beat.get("tuplet"), 0), (1, 1))
    return guitarpro.Duration(
        value=value,
        isDotted=_int(beat.get("dots"), 0) >= 1,
        tuplet=guitarpro.Tuplet(enters=enters, times=times),
    )


def _tempo_change(bpm: int, guitarpro: Any) -> Any:
    mtc = guitarpro.MixTableChange()
    mtc.wah = guitarpro.WahEffect.none  # GP5 always stores a wah byte
    mtc.hideTempo = False
    mtc.tempo = guitarpro.MixTableItem(value=bpm, duration=0, allTracks=False)
    return mtc


def _fill_voice(
    gp_voice: Any,
    beats: list[Any],
    tuning: list[int],
    last_on_string: dict[int, Any],
    report: SongsterrGpReport,
    guitarpro: Any,
) -> None:
    """One Songsterr voice's beats into a GP5 voice."""
    for b in beats:
        if not isinstance(b, dict):
            continue
        if b.get("graceNote"):
            report.grace_dropped += 1
            continue
        beat = guitarpro.Beat(gp_voice)
        beat.duration = _duration(b, guitarpro)
        notes = [] if b.get("rest") else [
            n for n in b.get("notes") or [] if isinstance(n, dict) and not n.get("rest")
        ]
        for n in notes:
            string = _int(n.get("string"), -1)
            if not 0 <= string < len(tuning):
                continue
            gp_note = guitarpro.Note(beat)
            gp_note.string = string + 1
            gp_note.value = max(0, _int(n.get("fret"), 0))
            _apply_note(gp_note, n, guitarpro, bool(b.get("letRing")))
            if n.get("hp") and string in last_on_string:
                last_on_string[string].effect.hammer = True
            last_on_string[string] = gp_note
            beat.notes.append(gp_note)
            report.notes += 1
        beat.status = guitarpro.BeatStatus.normal if beat.notes else guitarpro.BeatStatus.rest
        gp_voice.beats.append(beat)


def _apply_note(gp_note: Any, note: dict[str, Any], guitarpro: Any, let_ring: bool) -> None:
    eff = gp_note.effect
    if note.get("tie"):
        gp_note.type = guitarpro.NoteType.tie
    elif note.get("dead"):
        gp_note.type = guitarpro.NoteType.dead
    eff.vibrato = bool(note.get("vibrato"))
    eff.ghostNote = bool(note.get("ghost"))
    eff.staccato = bool(note.get("staccato"))
    eff.palmMute = bool(note.get("palmMute"))
    eff.letRing = let_ring or bool(note.get("letRing"))
    accent = _int(note.get("accentuated"), 0)
    eff.accentuatedNote = accent == 1
    eff.heavyAccentuatedNote = accent >= 2
    slide = _SLIDES.get(str(note.get("slide") or ""))
    if slide:
        eff.slides = [getattr(guitarpro.SlideType, slide)]
    harmonic = str(note.get("harmonic") or "").lower()
    if harmonic == "natural":
        eff.harmonic = guitarpro.NaturalHarmonic()
    elif harmonic in {"pinch", "artificial"}:
        eff.harmonic = guitarpro.PinchHarmonic()
    bend = note.get("bend")
    points = bend.get("points") if isinstance(bend, dict) else None
    if isinstance(points, list) and len(points) >= 2:
        # Songsterr: position 0..60, tone 50 = half tone (one semitone).
        # GP5 (as our importer reads it): position 0..12, value 2 = one semitone.
        gp_points = [
            guitarpro.BendPoint(
                position=max(0, min(12, round(_int(p.get("position"), 0) / 5))),
                value=round(_int(p.get("tone"), 0) / 25),
            )
            for p in points if isinstance(p, dict)
        ]
        peak = max((p.value for p in gp_points), default=0)
        if peak:
            eff.bend = guitarpro.BendEffect(
                type=guitarpro.BendType.bend, value=peak, points=gp_points
            )


def write_songsterr_gp5(
    parts: list[dict[str, Any]], dst: Path, *, title: str = "", artist: str = ""
) -> SongsterrGpReport:
    """Write Songsterr parts as a GP5 file at ``dst`` — one GP track per
    non-percussion part, in Songsterr's order."""
    try:
        import guitarpro
    except ImportError as exc:  # pragma: no cover - pyguitarpro is a core dep
        raise IngestionError("pyguitarpro is a core dependency") from exc

    report = SongsterrGpReport()
    kept = []
    for i, part in enumerate(parts):
        name = str(part.get("name") or part.get("instrument")
                   or tr(f"Pista {i + 1}", f"Track {i + 1}"))
        if is_percussion(part):
            report.skipped_tracks.append(tr(f"{name} (percussão)", f"{name} (percussion)"))
        elif not isinstance(part.get("measures"), list) or not part["measures"]:
            report.skipped_tracks.append(tr(f"{name} (sem compassos)", f"{name} (no bars)"))
        else:
            kept.append((name, part))
    if not kept:
        raise IngestionError(tr(
            "esta tab do Songsterr não tem nenhuma pista com cordas",
            "this Songsterr tab has no stringed track",
        ))

    song = guitarpro.Song()
    song.title, song.artist = _gp5_text(title), _gp5_text(artist)
    first = kept[0][1]
    tempos = [t for t in (first.get("automations") or {}).get("tempo") or [] if isinstance(t, dict)]
    song.tempo = max(10, min(400, _int(tempos[0].get("bpm"), 120) if tempos else 120))
    tempo_at: dict[int, int] = {}
    for t in tempos[1:]:
        measure = _int(t.get("measure"), 0)
        if _int(t.get("position"), 0):
            report.tempo_moved += 1
        tempo_at[measure] = max(10, min(400, _int(t.get("bpm"), song.tempo)))

    n_measures = max(len(p["measures"]) for _n, p in kept)
    report.measures = n_measures
    song.measureHeaders = []
    start, sig = QUARTER_TICKS, (4, 4)
    for m in range(n_measures):
        src = first["measures"][m] if m < len(first["measures"]) else {}
        raw_sig = src.get("signature")
        if isinstance(raw_sig, list) and len(raw_sig) == 2:
            num, den = _int(raw_sig[0], 4), _int(raw_sig[1], 4)
            if num > 0 and den in _DURATIONS:
                sig = (num, den)
        header = guitarpro.MeasureHeader()
        header.number = m + 1
        # Set by hand: a hand-built header does not accumulate its own start
        # (see arrangement_writer), and every beat's time derives from it.
        header.start = start
        header.timeSignature = guitarpro.TimeSignature()
        header.timeSignature.numerator = sig[0]
        header.timeSignature.denominator = guitarpro.Duration(value=sig[1])
        marker = src.get("marker")
        if isinstance(marker, dict) and str(marker.get("text") or "").strip():
            header.marker = guitarpro.Marker(title=_gp5_text(str(marker["text"]).strip()))
        song.measureHeaders.append(header)
        start += sig[0] * QUARTER_TICKS * 4 // sig[1]

    song.tracks = []
    for t_idx, (name, part) in enumerate(kept):
        tuning = [_int(v, 0) for v in part["tuning"]]  # highest string first
        track = guitarpro.Track(song, number=t_idx + 1, name=_gp5_text(name[:40]))
        track.strings = [
            guitarpro.GuitarString(number=i + 1, value=v) for i, v in enumerate(tuning)
        ]
        ch = t_idx if t_idx < 9 else t_idx + 1  # MIDI channel 10 is percussion
        track.channel = guitarpro.MidiChannel(channel=ch % 16, effectChannel=ch % 16)
        track.measures = []
        last_on_string: dict[int, Any] = {}
        for m, header in enumerate(song.measureHeaders):
            measure = guitarpro.Measure(track, header)
            src = part["measures"][m] if m < len(part["measures"]) else {}
            voices = [v for v in src.get("voices") or [] if isinstance(v, dict)][:2]
            for v_idx, gp_voice in enumerate(measure.voices):
                gp_voice.beats = []
                beats = (voices[v_idx].get("beats") or []) if v_idx < len(voices) else []
                _fill_voice(gp_voice, beats, tuning, last_on_string, report, guitarpro)
                if v_idx == 0 and not gp_voice.beats:
                    # An empty bar still has to fill its time.
                    rest = guitarpro.Beat(gp_voice)
                    rest.duration = guitarpro.Duration(value=1)
                    rest.status = guitarpro.BeatStatus.rest
                    gp_voice.beats.append(rest)
                if v_idx == 0 and t_idx == 0 and m in tempo_at:
                    gp_voice.beats[0].effect.mixTableChange = _tempo_change(tempo_at[m], guitarpro)
            track.measures.append(measure)
        song.tracks.append(track)
    report.tracks = len(song.tracks)
    lyrics = _lyrics(parts, kept, report, guitarpro)
    if lyrics is not None:
        song.lyrics = lyrics

    if report.skipped_tracks:
        report.warnings.append(
            tr("pistas não incluídas: ", "tracks not included: ")
            + ", ".join(report.skipped_tracks)
        )
    if report.grace_dropped:
        report.warnings.append(tr(
            f"{report.grace_dropped} nota(s) de ornamento (grace) não incluídas",
            f"{report.grace_dropped} ornament (grace) note(s) not included",
        ))
    if report.tempo_moved:
        report.warnings.append(tr(
            f"{report.tempo_moved} mudança(s) de andamento a meio do compasso "
            "passadas para o início dele",
            f"{report.tempo_moved} mid-bar tempo change(s) moved to the start "
            "of their bar",
        ))
    dst.parent.mkdir(parents=True, exist_ok=True)
    with open(dst, "wb") as fh:
        guitarpro.write(song, fh, version=(5, 1, 0))
    return report
