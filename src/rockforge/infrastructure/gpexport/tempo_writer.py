"""Write a corrected tempo map back into a Guitar Pro file.

The sync analysis produces per-span BPM recommendations; this puts them into a
COPY of the user's file so the correction is permanent in Guitar Pro itself,
not only inside RockForge. The original is never touched.

What is possible per format, established by testing rather than assumption:

============  ======  =========================================================
format        write   how
============  ======  =========================================================
.gp3/4/5      yes     PyGuitarPro. A tempo change is a ``MixTableChange`` on a
                      beat, not a measure-header field; the song header carries
                      the initial tempo. Re-serialising from the object model is
                      semantically lossless for what PyGuitarPro models (upstream
                      asserts read==write on its corpus), but it is a rewrite,
                      not a patch: private blocks it does not model are zeroed.
.gp (GP7/8)   yes     The container is a plain ZIP. Every entry is copied
                      byte-for-byte and ONLY ``Content/score.gpif`` is replaced,
                      so nothing outside the tempo automation can change. Tempo
                      lives in ``MasterTrack/Automations``.
.gpx (GP6)    NO      A proprietary binary container nobody writes — not
                      alphaTab, not TuxGuitar, not MuseScore. Refused, with the
                      same advice the importer gives (export as GP5 or GP7).
============  ======  =========================================================
"""

from __future__ import annotations

import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET

from rockforge.domain.errors import IngestionError

# The GPIF tempo reference index meaning "the number is a quarter-note BPM".
_QUARTER_REFERENCE = 2


@dataclass(frozen=True)
class TempoCorrection:
    """A tempo to set from ``measure`` (1-based, as the user sees it) onward."""

    measure: int
    bpm: float


@dataclass(frozen=True)
class AppliedCorrection:
    """What was actually written, which is not always what was asked for.

    GP3/GP4/GP5 store tempo as an INTEGER, so a recommendation of 119.085 BPM is
    written as 119. Over a long song that residual is real (~0.07% here, about
    0.13 s over three minutes), so it is reported rather than hidden — the .gp
    (GPIF) format keeps the decimals.
    """

    measure: int
    requested_bpm: float
    written_bpm: float

    @property
    def rounded(self) -> bool:
        return abs(self.requested_bpm - self.written_bpm) > 1e-6


def _validate(corrections: list[TempoCorrection]) -> list[TempoCorrection]:
    if not corrections:
        raise IngestionError("no tempo corrections to write")
    for c in corrections:
        if c.measure < 1:
            raise IngestionError(f"measure must be 1 or greater, got {c.measure}")
        if not 10.0 <= c.bpm <= 400.0:
            raise IngestionError(f"implausible tempo {c.bpm} BPM at measure {c.measure}")
    # One correction per measure, in order; a later one for the same measure wins.
    by_measure = {c.measure: c for c in corrections}
    return [by_measure[m] for m in sorted(by_measure)]


def _write_binary_gp(
    src: Path, dst: Path, corrections: list[TempoCorrection]
) -> list[AppliedCorrection]:
    """gp3/gp4/gp5 via PyGuitarPro. Tempo is an integer in these formats."""
    import guitarpro

    song = guitarpro.parse(str(src))
    version = song.versionTuple
    applied: list[AppliedCorrection] = []
    for c in corrections:
        applied.append(AppliedCorrection(c.measure, c.bpm, float(round(c.bpm))))
        idx = c.measure - 1
        if c.measure == 1:
            # Measure 1 is the song's initial tempo, not a mid-song change.
            song.tempo = int(round(c.bpm))
            continue
        # A tempo change is global, so it only needs to exist on one track — but
        # it must land on a beat that actually exists.
        beat = None
        for track in song.tracks:
            if idx >= len(track.measures):
                continue
            for voice in track.measures[idx].voices:
                if voice.beats:
                    beat = voice.beats[0]
                    break
            if beat is not None:
                break
        if beat is None:
            raise IngestionError(
                f"measure {c.measure} has no beat to attach a tempo change to"
            )
        # Preserve any existing mix-table change on this beat (it may carry an
        # instrument/volume/wah change); only its tempo is ours to set.
        mtc = beat.effect.mixTableChange
        if mtc is None:
            mtc = guitarpro.MixTableChange()
            # A fresh MixTableChange has wah=None, but GP5 always stores a wah
            # byte, so it reads back as WahEffect(-1) and the file no longer
            # round-trips. hideTempo defaults True but does not exist before
            # GP5.1, so it reads back False. Set both to what the format writes.
            mtc.wah = guitarpro.WahEffect.none
            mtc.hideTempo = False
            beat.effect.mixTableChange = mtc
        mtc.tempo = guitarpro.MixTableItem(value=int(round(c.bpm)), duration=0, allTracks=False)
    with open(dst, "wb") as fh:
        guitarpro.write(song, fh, version=version)
    return applied


def _write_gpif(
    src: Path, dst: Path, corrections: list[TempoCorrection]
) -> list[AppliedCorrection]:
    """GP7/GP8 (.gp) by replacing ONLY Content/score.gpif inside the ZIP.

    GPIF stores tempo as a decimal number, so nothing is rounded here.
    """
    with zipfile.ZipFile(src) as zin:
        names = zin.namelist()
        if "Content/score.gpif" not in names:
            raise IngestionError("not a Guitar Pro 7/8 file (no Content/score.gpif)")
        raw = zin.read("Content/score.gpif")
        if not raw.lstrip()[:1] == b"<":
            raise IngestionError(
                "this .gp is encrypted (a locked Guitar Pro 8 file) and cannot be edited"
            )
        root = ET.fromstring(raw.decode("utf-8"))
        master = root.find("MasterTrack")
        if master is None:
            raise IngestionError("the .gp has no MasterTrack to write tempo into")
        autos = master.find("Automations")
        if autos is None:
            autos = ET.SubElement(master, "Automations")

        for c in corrections:
            bar = c.measure - 1  # GPIF Bar is 0-based
            existing = None
            for auto in autos.findall("Automation"):
                if (auto.findtext("Type") or "") != "Tempo":
                    continue
                if int(auto.findtext("Bar") or "0") != bar:
                    continue
                if abs(float(auto.findtext("Position") or "0")) > 1e-9:
                    continue  # a mid-bar change is a different event; leave it
                existing = auto
                break
            if existing is None:
                existing = ET.SubElement(autos, "Automation")
                for tag, text in (
                    ("Type", "Tempo"), ("Linear", "false"), ("Bar", str(bar)),
                    ("Position", "0"), ("Visible", "true"), ("Value", ""),
                ):
                    ET.SubElement(existing, tag).text = text
            value = existing.find("Value")
            if value is None:
                value = ET.SubElement(existing, "Value")
            # "<bpm> <reference>": reference 2 = the number is a quarter-note BPM.
            value.text = f"{round(c.bpm, 3):g} {_QUARTER_REFERENCE}"

        # Keep the automations bar-ascending, the order Guitar Pro writes.
        ordered = sorted(
            autos.findall("Automation"),
            key=lambda a: (
                int(a.findtext("Bar") or "0"),
                float(a.findtext("Position") or "0"),
            ),
        )
        for a in ordered:
            autos.remove(a)
        for a in ordered:
            autos.append(a)

        new_gpif = ET.tostring(root, encoding="utf-8", xml_declaration=True)

        # Copy every other entry verbatim: the stylesheet, layout and part
        # configuration are opaque binaries unrelated to tempo, so touching
        # nothing else is the most faithful edit possible.
        with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
            for info in zin.infolist():
                data = new_gpif if info.filename == "Content/score.gpif" else zin.read(info)
                zout.writestr(info, data)
    return [AppliedCorrection(c.measure, c.bpm, round(c.bpm, 3)) for c in corrections]


def _played_bars(src: Path) -> list[int]:
    """The written bar (0-based) of each bar as played — the numbering the user
    sees, since the chart unrolls repeats, voltas and jumps (``gpimport.playback``)."""
    from rockforge.infrastructure.gpimport.playback import playback_order

    if src.suffix.lower() == ".gp":
        from rockforge.infrastructure.gpimport.gpif_parser import _bar_flow, _load_gpif

        root = _load_gpif(src)
        return playback_order([_bar_flow(mb) for mb in root.find("MasterBars") or []])
    import guitarpro

    from rockforge.infrastructure.gpimport.parser import _bar_flows

    return playback_order(_bar_flows(guitarpro.parse(str(src))))


def _to_written_bars(
    src: Path, corrections: list[TempoCorrection]
) -> tuple[list[TempoCorrection], dict[int, int]]:
    """Corrections moved from played bars to the written bars that hold them, and
    the written bar of each requested measure. A written bar played several times
    holds ONE tempo: different tempos for its passes cannot be written."""
    played = _played_bars(src)
    if played == list(range(len(played))):
        return corrections, {c.measure: c.measure for c in corrections}
    written: dict[int, TempoCorrection] = {}
    measure_of: dict[int, int] = {}
    for c in corrections:
        bar = played[c.measure - 1] + 1 if c.measure <= len(played) else c.measure
        measure_of[c.measure] = bar
        other = written.get(bar)
        if other is not None and abs(other.bpm - c.bpm) > 1e-6:
            passes = sorted(m for m, b in measure_of.items() if b == bar)
            raise IngestionError(
                f"measures {', '.join(map(str, passes))} are passes of the same written "
                f"measure {bar} (a repeat) with different tempos; a Guitar Pro file "
                "holds one tempo per written measure"
            )
        written[bar] = TempoCorrection(bar, c.bpm)
    return [written[b] for b in sorted(written)], measure_of


def write_tempo_corrections(
    src: Path, dst: Path, corrections: list[TempoCorrection]
) -> list[AppliedCorrection]:
    """Write ``corrections`` into a COPY of ``src`` at ``dst``.

    ``src`` is only ever read. Returns what was actually written per measure —
    the binary formats round the tempo to an integer, so the caller can tell the
    user rather than quietly delivering a different tempo. Raises
    :class:`IngestionError` for a format that cannot be written or a correction
    that does not fit the file.
    """
    ordered = _validate(corrections)
    suffix = src.suffix.lower()
    if suffix == ".gpx":
        raise IngestionError(
            "GP6 (.gpx) files cannot be written — no tool writes that format. "
            "Export the song as GP5 or GP7 (.gp) from Guitar Pro and try again."
        )
    if suffix not in {".gp", ".gp3", ".gp4", ".gp5"}:
        raise IngestionError(f"unsupported Guitar Pro format: {suffix or '(none)'}")
    # The measures are numbered as played (repeats unrolled); the file is written.
    written, measure_of = _to_written_bars(src, ordered)
    tmp = dst.with_name(dst.name + ".part")
    try:
        if suffix == ".gp":
            applied = _write_gpif(src, tmp, written)
        else:
            applied = _write_binary_gp(src, tmp, written)
        shutil.move(str(tmp), str(dst))
        by_bar = {a.measure: a for a in applied}
        return [
            AppliedCorrection(c.measure, c.bpm, by_bar[measure_of[c.measure]].written_bpm)
            for c in ordered
        ]
    finally:
        tmp.unlink(missing_ok=True)
