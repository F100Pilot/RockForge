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
- tempo: the first track's ``automations.tempo[]`` ``{measure, position,
  bpm}`` (a quarter-note BPM, which may carry decimals; ``position`` read as
  the fraction of the bar, as ``teaqu/guitar-pro-youtube-sync`` hands it to
  GPIF's ``<Position>``); the first one is the song tempo, later ones a
  mix-table change on that measure's first beat, exactly how GP5 stores it
  (see ``gpexport/tempo_writer``). GP5 holds a WHOLE BPM at a bar's start, so
  the file alone cannot follow a tab whose tempo map tracks a recording (a
  tab Songsterr's AI made from it: 117.85 BPM, a change mid-bar). The exact
  map is therefore also returned as ``report.bar_times`` — where every bar
  starts, in seconds from bar 1 — which the wizard can send as ``bar_times``,
  the machinery that re-times the chart bar by bar (``sync_map``).

- lyrics: a part's ``newLyrics[]`` ``{text, offset}`` — the sung text (words
  by spaces, syllables by hyphens; extra spaces skip notes) and the 0-based
  measure it starts on. Written as the GP5 song lyrics, bound to the track
  that SINGS them (``trackChoice``), so the importer hands each syllable to the
  next note of the vocal line, exactly as Guitar Pro would. Songsterr shows the
  lyrics over every track (a guitar resting through the verse still has the
  words under it), so the text may come in a part that does not sing it: a
  vocal part (``is_vocal``) is preferred, else the part the text came in. GP5
  holds five lines; more are dropped and counted.

Grace notes become GP5 grace effects on the note they lead into (in GP5 a
grace is an ornament of the NEXT note, not a beat — writing them as beats would
push the rhythm late); one with no note on its string after it is dropped and
counted. Honest limits, all counted in the report rather than hidden: a
mid-measure tempo change is moved to its measure's start in the GP5
(``bar_times`` keep its timing); lyrics on a part that could not be written
(no strings) fall back to the first track's notes; text GP5 cannot store (it
is cp1252) becomes "?".
"""

from __future__ import annotations

import math
import re
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
    graces: int = 0
    tempo_moved: int = 0
    #: Tempo changes whose ``position`` is no fraction of a bar (≥ 1: a unit
    #: never seen), read as the bar's start and counted, never silently.
    tempo_position_unknown: int = 0
    #: Distinct tempos the tab's map holds, and whether any has decimals.
    tempo_count: int = 1
    tempo_decimal: bool = False
    #: Where each bar starts, in seconds from bar 1, from the tab's own tempo
    #: map at full precision (see the module docstring).
    bar_times: list[float] = field(default_factory=list)
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
    """The tab's ``newLyrics`` as GP5 song lyrics, bound to the part that sings them.

    Songsterr shows the lyrics over every track, timed by the vocal line — a
    guitar part resting while the verse is sung still carries the words — so
    the text can come in a part that does not sing it. The syllables are bound
    to a vocal part when the tab has one (its own lyrics first), else to the
    part the text came in."""
    with_text = [
        p for p in parts
        if any(isinstance(ln, dict) and str(ln.get("text") or "").strip()
               for ln in p.get("newLyrics") or [])
    ]
    if not with_text:
        return None
    vocal_kept = [i for i, (_n, p) in enumerate(kept) if is_vocal(p)]
    source = next((p for p in with_text if is_vocal(p)), with_text[0])
    lines = [
        ln for ln in source.get("newLyrics") or []
        if isinstance(ln, dict) and str(ln.get("text") or "").strip()
    ]
    lyrics = guitarpro.Lyrics()
    index = next((i for i, (_n, p) in enumerate(kept) if p is source), None)
    if (index is None or index not in vocal_kept) and vocal_kept:
        sung = vocal_kept[0]
        if index is not None:
            report.warnings.append(tr(
                f"a letra vinha na pista {kept[index][0]}; as sílabas seguem as notas "
                f"da pista de voz {kept[sung][0]}",
                f"the lyrics came in the {kept[index][0]} track; the syllables follow "
                f"the notes of the vocal track {kept[sung][0]}",
            ))
        index = sung
    if index is None:
        index = 0
        name = str(source.get("name") or source.get("instrument") or "?")
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


# General MIDI voices (0-based programs): Choir Aahs, Voice Oohs, Synth Voice,
# Lead 6 (voice).
_VOCAL_PROGRAMS = frozenset({52, 53, 54, 85})
_VOCAL_WORDS = re.compile(
    r"voice|vocal|vox|\bvoz|singer|sing\b|choir|\bcoro\b|canto|aahs|oohs", re.IGNORECASE
)


def is_vocal(part: dict[str, Any]) -> bool:
    """A part that carries the sung line: a voice instrument, or named like one."""
    program = part.get("instrumentId")
    if isinstance(program, int) and not isinstance(program, bool) and program in _VOCAL_PROGRAMS:
        return True
    return bool(_VOCAL_WORDS.search(f"{part.get('name') or ''} {part.get('instrument') or ''}"))


def is_percussion(part: dict[str, Any]) -> bool:
    return not part.get("tuning") or "drum" in str(part.get("instrument", "")).lower()


def _int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _bpm(value: Any, default: float) -> float:
    """A tempo as Songsterr wrote it, decimals kept, bounded like GP5's."""
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return max(10.0, min(400.0, out)) if math.isfinite(out) else default


def _bar_fraction(value: Any) -> tuple[float, bool]:
    """Where in its bar a tempo change falls, 0 = the downbeat, and whether the
    value could not be read as that. Only a value strictly between 0 and 1 is a
    place inside the bar; 1 or more is a unit never seen (beats? ticks?), read
    as the bar's start but reported, since a mid-bar change may be lost."""
    try:
        out = float(value)
    except (TypeError, ValueError):
        return 0.0, False
    if not math.isfinite(out):
        return 0.0, True
    if 0.0 < out < 1.0:
        return out, False
    return 0.0, out >= 1.0


def tab_bar_times(
    quarters: list[float], tempos: list[tuple[int, float, float]], start_bpm: float
) -> list[float]:
    """Where each bar starts, in seconds from bar 1, from the tab's tempo map.

    ``quarters[m]`` is bar m's length in quarter notes; ``tempos`` are
    ``(bar, fraction of the bar, quarter-note BPM)`` in order, applied from
    that point on. Pure, so the arithmetic is tested without Songsterr.
    """
    events: dict[int, list[tuple[float, float]]] = {}
    for bar, frac, bpm in tempos:
        events.setdefault(bar, []).append((frac, bpm))
    out: list[float] = []
    now, bpm = 0.0, start_bpm
    for m, q in enumerate(quarters):
        out.append(now)
        at = 0.0
        for frac, new_bpm in sorted(events.get(m, []), key=lambda e: e[0]):
            now += q * (frac - at) * 60.0 / bpm
            at, bpm = frac, new_bpm
        now += q * (1.0 - at) * 60.0 / bpm
    return out


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
    graces: list[dict[str, Any]] = []  # grace beats waiting for the note they lead into
    for b in beats:
        if not isinstance(b, dict):
            continue
        if b.get("graceNote"):
            graces.append(b)
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
        if graces:
            _attach_graces(beat, graces, report, guitarpro)
            graces = []
        gp_voice.beats.append(beat)
    report.grace_dropped += sum(_grace_count(g) for g in graces)  # nothing after them in the bar


def _grace_count(b: dict[str, Any]) -> int:
    return max(1, sum(1 for n in b.get("notes") or [] if isinstance(n, dict) and not n.get("rest")))


def _attach_graces(
    beat: Any, graces: list[dict[str, Any]], report: SongsterrGpReport, guitarpro: Any
) -> None:
    """Songsterr's grace beats as GP5 grace effects on the note they lead into.

    A Songsterr grace note is a beat of its own; in GP5 it is an effect of the
    NEXT note on the same string (one per note), so it takes none of the bar's
    time and the rhythm stays as written. It also takes a syllable of the
    lyrics, as in Songsterr and Guitar Pro (``parser._lyric_notes``) — dropping
    it put every following syllable one note late. A grace with no note on its
    string in the next beat, or a second one on the same note, has nowhere to
    go and is counted as dropped."""
    taken: set[int] = set()
    for g in graces:
        value = _int(g.get("type"), 32)
        duration = value if value in (8, 16, 32, 64) else 32
        for n in g.get("notes") or []:
            if not isinstance(n, dict) or n.get("rest"):
                continue
            string = _int(n.get("string"), -1) + 1
            target = next((x for x in beat.notes if x.string == string), None)
            if target is None or string in taken:
                report.grace_dropped += 1
                continue
            taken.add(string)
            grace = guitarpro.GraceEffect()
            grace.fret = max(0, _int(n.get("fret"), 0))
            grace.duration = duration
            grace.isOnBeat = g.get("graceNote") == "onBeat"
            grace.isDead = bool(n.get("dead"))
            target.effect.grace = grace
            report.graces += 1


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
    raw = [t for t in (first.get("automations") or {}).get("tempo") or [] if isinstance(t, dict)]
    start_bpm = _bpm(raw[0].get("bpm"), 120.0) if raw else 120.0
    # Rounded, not cut: int() made 117.85 BPM 117, a drift that grows bar by bar.
    song.tempo = round(start_bpm)
    changes: list[tuple[int, float, float]] = []
    tempo_at: dict[int, int] = {}
    for t in raw[1:]:
        measure = max(0, _int(t.get("measure"), 0))
        frac, unknown = _bar_fraction(t.get("position"))
        bpm = _bpm(t.get("bpm"), start_bpm)
        if frac:
            report.tempo_moved += 1
        if unknown:
            report.tempo_position_unknown += 1
        changes.append((measure, frac, bpm))
        tempo_at[measure] = round(bpm)
    bpms = {start_bpm, *(b for _m, _f, b in changes)}
    report.tempo_count = len(bpms)
    report.tempo_decimal = any(abs(b - round(b)) > 1e-6 for b in bpms)

    n_measures = max(len(p["measures"]) for _n, p in kept)
    report.measures = n_measures
    song.measureHeaders = []
    start, sig = QUARTER_TICKS, (4, 4)
    quarters: list[float] = []
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
        quarters.append(sig[0] * 4 / sig[1])
    report.bar_times = tab_bar_times(quarters, changes, start_bpm)

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
            "passadas para o início dele no ficheiro GP (o andamento da tab, no "
            "passo 3, mantém o tempo exato de cada compasso)",
            f"{report.tempo_moved} mid-bar tempo change(s) moved to the start "
            "of their bar in the GP file (the tab's tempo, in step 3, keeps "
            "each bar's exact time)",
        ))
    if report.tempo_position_unknown:
        report.warnings.append(tr(
            f"{report.tempo_position_unknown} mudança(s) de andamento numa posição do "
            "compasso que não sei ler — postas no início do compasso; se o Songsterr "
            "as tem a meio, esses compassos podem ficar desfasados",
            f"{report.tempo_position_unknown} tempo change(s) at a position in the bar "
            "I cannot read — placed at the bar's start; if Songsterr has them mid-bar, "
            "those bars may be off",
        ))
    dst.parent.mkdir(parents=True, exist_ok=True)
    with open(dst, "wb") as fh:
        guitarpro.write(song, fh, version=(5, 1, 0))
    return report
