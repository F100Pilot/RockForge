"""What the built .sng holds, for the 3D highway ("O que vai para o jogo").

The score and the highway draw the chart from the built XML; the game reads the
SNG, which the native packer compiles separately (dynamic-difficulty levels,
anchors per level, high-density chords, phrase iterations). Every native-SNG bug
that cost whole sessions was in that geometry, and the only way to see it was to
play the song in game. This reads the SNG back out of the .psarc the user is
about to install and hands one difficulty level to the viewer, so a level can
be looked at with a slider.

Honest limit: it is OUR reading of the binary (``read_sng``). Something the game
reads differently from us looks right here — it shortens the loop for geometry
bugs, it never replaces playing the song.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rockforge.infrastructure.packaging.psarc import sng_model as m

# The asset name ends in what the manifest calls the chart (manifest.arrangement_asset_name);
# the viewer names charts by ArrangementKind value.
SUFFIX_KIND = {
    "lead": "Lead", "rhythm": "Rhythm", "combo": "Combined", "bass": "Bass",
    "lead2": "Alternate Lead", "rhythm2": "Alternate Rhythm",
}

# Mask bits → the technique names the viewer and the highway already use.
_TECHNIQUES = (
    (m.NOTE_MASK_HAMMERON, "hammerOn"), (m.NOTE_MASK_PULLOFF, "pullOff"),
    (m.NOTE_MASK_HARMONIC, "harmonic"), (m.NOTE_MASK_PINCHHARMONIC, "pinchHarmonic"),
    (m.NOTE_MASK_PALMMUTE, "palmMute"), (m.NOTE_MASK_FRETHANDMUTE, "mute"),
    (m.NOTE_MASK_VIBRATO, "vibrato"), (m.NOTE_MASK_TREMOLO, "tremolo"),
    (m.NOTE_MASK_TAP, "tap"), (m.NOTE_MASK_SLAP, "slap"), (m.NOTE_MASK_PLUCK, "pluck"),
    (m.NOTE_MASK_ACCENT, "accent"), (m.NOTE_MASK_BEND, "bend"), (m.NOTE_MASK_SLIDE, "slide"),
    (m.NOTE_MASK_SLIDEUNPITCHEDTO, "slide"),
)


def kind_of_asset(asset: str) -> str | None:
    """'mysong_lead2' → 'Alternate Lead'; None for the vocals or anything else."""
    return SUFFIX_KIND.get(asset.rsplit("_", 1)[-1].lower())


def read_charts(path: Path) -> dict[str, m.SngModel]:
    """Every instrument chart of a .psarc, by ArrangementKind value (vocals left out)."""
    from rockforge.infrastructure.packaging.psarc import container, crypto
    from rockforge.infrastructure.packaging.psarc.sng import read_sng

    entries = container.read_entries(path, lambda n: n.endswith(".sng"))
    charts: dict[str, m.SngModel] = {}
    for name in sorted(entries):
        kind = kind_of_asset(Path(name).stem)
        if kind is not None:
            charts[kind] = read_sng(crypto.unpack_sng(entries[name]))
    return charts


def _techniques(mask: int) -> list[str]:
    seen: list[str] = []
    for bit, name in _TECHNIQUES:
        if mask & bit and name not in seen:
            seen.append(name)
    return seen


def _curve(bends: list[m.SngBendData32], at: float) -> list[list[float]]:
    return [[round(max(0.0, b.time - at), 4), round(b.step, 3)] for b in bends]


def _note(n: m.SngNote, string: int, fret: int, mask: int, bends: list[m.SngBendData32],
          slide_to: int, slide_unpitch: int, chord_name: str) -> dict[str, Any]:
    peak = max((b.step for b in bends), default=0.0)
    slide = slide_to if slide_to >= 0 else slide_unpitch
    return {
        "time": round(n.time, 4), "sustain": round(max(0.0, n.sustain), 4),
        "string": string, "fret": fret, "techniques": _techniques(mask),
        "bend": int(round(peak)), "bend_curve": _curve(bends, n.time) if peak > 0 else [],
        "slide_to": slide if slide >= 0 else -1, "chord_name": chord_name,
        "chord": n.chord_id >= 0, "high_density": bool(n.mask & m.NOTE_MASK_HIGHDENSITY),
    }


def _notes(model: m.SngModel, notes: list[m.SngNote]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for n in notes:
        if n.chord_id < 0:
            out.append(_note(n, n.string, n.fret, n.mask, n.bend_data, n.slide_to,
                             n.slide_unpitch_to, ""))
            continue
        if not 0 <= n.chord_id < len(model.chord_templates):
            continue  # a chord pointing past its templates: the check names it
        tpl = model.chord_templates[n.chord_id]
        cn = (model.chord_notes[n.chord_notes_id]
              if 0 <= n.chord_notes_id < len(model.chord_notes) else None)
        for s, fret in enumerate(tpl.frets):
            if fret < 0 or fret == 255:
                continue
            held = n.mask & (m.NOTE_MASK_PALMMUTE | m.NOTE_MASK_FRETHANDMUTE)
            mask = (cn.note_mask[s] if cn else 0) | held
            out.append(_note(
                n, s, fret, mask, cn.bend_data[s] if cn else [],
                cn.slide_to[s] if cn else -1, cn.slide_unpitch_to[s] if cn else -1, tpl.name,
            ))
    out.sort(key=lambda x: (x["time"], x["string"]))
    return out


def _ceiling(model: m.SngModel, iteration: int) -> int:
    its = model.phrase_iterations
    if not 0 <= iteration < len(its):
        return 0
    pid = its[iteration].phrase_id
    return model.phrases[pid].max_difficulty if 0 <= pid < len(model.phrases) else 0


def level_preview(model: m.SngModel, level: int) -> dict[str, Any]:
    """The chart a player set to difficulty ``level`` sees (bundle clock).

    Each phrase iteration shows its own level ``min(level, its phrase's
    ceiling)`` — a phrase leaves the levels above its ceiling, and the game then
    plays it at its ceiling — so the hardest level is the whole chart. The
    notes and anchors of an iteration are the ones the SNG tags with it."""
    levels = model.arrangements
    if not levels:
        raise ValueError("the chart has no difficulty levels")
    d = max(0, min(level, len(levels) - 1))
    iters = model.phrase_iterations
    notes: list[m.SngNote] = []
    anchors: list[m.SngAnchor] = []
    for i in range(len(iters)) if iters else [0]:
        lv = levels[min(d, _ceiling(model, i), len(levels) - 1)]
        notes += [n for n in lv.notes if n.phrase_iteration_id == i or not iters]
        anchors += [a for a in lv.anchors if a.phrase_iteration_id == i or not iters]
    notes.sort(key=lambda n: n.time)
    anchors.sort(key=lambda a: a.start_time)
    shown = sum(1 for i in range(len(iters)) if _ceiling(model, i) >= d)
    return {
        "level": d,
        "levels": len(levels),
        "max_difficulty": model.metadata.max_difficulty,
        "notes": _notes(model, notes),
        "anchors": [
            {"time": round(a.start_time, 4), "end": round(a.end_time, 4), "fret": a.fret,
             "width": a.width, "phrase_iteration": a.phrase_iteration_id}
            for a in anchors
        ],
        "phrases": [
            {"start": round(it.start_time, 4), "end": round(it.end_time, 4),
             "name": (model.phrases[it.phrase_id].name
                      if 0 <= it.phrase_id < len(model.phrases) else ""),
             "max_difficulty": _ceiling(model, i)}
            for i, it in enumerate(iters)
        ],
        "phrases_at_level": shown,
        # bit 0 of a beat's mask is a downbeat (sng_build._build_beats)
        "bars": [{"time": round(b.time, 4), "measure": b.measure}
                 for b in model.beats if b.mask & 1],
        "beats": [round(b.time, 4) for b in model.beats],
        "tuning": list(model.metadata.tuning),
        "capo": model.metadata.capo_fret if model.metadata.capo_fret != m.NO_CAPO else 0,
    }
