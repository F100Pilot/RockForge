"""The player's own guitar and bass, for the tones RockForge proposes.

A tone is set for an instrument: the same amp gain that is a clean crunch with
vintage single coils turns into fizz with hot active humbuckers, and single
coils bring hum a high-gain tone amplifies ("guitar tone/pickups too hot in
CDLC" is a recurring complaint). So the user says once, in Definições → Tons e
IA, what they play — pickups, how strong, a name — and that goes:

* into every request for an assistant (the song's tones, one tone from a
  description), so its answer is set for that instrument (:func:`describe`);
* into the curated presets the tone detection and the per-section suggestions
  hand out (:func:`fit_tone`): a starting point, said on the card, never stored
  over the preset itself.

The fit is a rule of thumb, not a measurement — nothing here hears the
player's guitar — so it is small and said: hot pickups (high output or active)
take 10 % of the range off the amp's gain and close the noise gate 5 dB; single
coils / P90s close the gate 5 dB for their hum; a low-output guitar gets 5 % more
gain. Only the driven presets (the ones that open with the gate) are touched,
and only their ``…_Gain`` knobs and the gate: a Plexi's Loudness knobs are its
volume as much as its drive, and are left alone.

Stored in ``work_dir/guitar_profile.json``, not ``settings.json``, which the
Definições page rewrites whole on every save.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from rockforge import config
from rockforge._atomic import write_text_atomic
from rockforge.i18n import tr

GUITAR_PICKUPS = ("humbucker", "single", "p90", "mixed", "active")
BASS_PICKUPS = ("passive", "active")
OUTPUTS = ("low", "medium", "high")
MAX_NAME = 80

HOT_GAIN_CUT = 0.10       # of the knob's range
LOW_GAIN_BOOST = 0.05
GATE_STEP_DB = 5.0
GATE_KEY = "Pedal_NoiseGate"
GATE_KNOB = "Pedal_NoiseGate_Thresh"

_EMPTY: dict[str, dict[str, str]] = {
    "guitar": {"pickups": "", "output": "", "name": ""},
    "bass": {"pickups": "", "output": "", "name": ""},
}


def _file() -> Path:
    return config.settings.work_dir / "guitar_profile.json"


def _clean(raw: object, pickups: tuple[str, ...]) -> dict[str, str]:
    src = raw if isinstance(raw, dict) else {}
    p = src.get("pickups")
    o = src.get("output")
    n = src.get("name")
    return {
        "pickups": p if isinstance(p, str) and p in pickups else "",
        "output": o if isinstance(o, str) and o in OUTPUTS else "",
        "name": " ".join(n.split())[:MAX_NAME] if isinstance(n, str) else "",
    }


def clean(raw: object) -> dict[str, dict[str, str]]:
    """A profile with only known values: anything else reads as not said."""
    src = raw if isinstance(raw, dict) else {}
    return {
        "guitar": _clean(src.get("guitar"), GUITAR_PICKUPS),
        "bass": _clean(src.get("bass"), BASS_PICKUPS),
    }


def load() -> dict[str, dict[str, str]]:
    try:
        data = json.loads(_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return copy.deepcopy(_EMPTY)
    return clean(data)


def save(raw: object) -> dict[str, dict[str, str]]:
    profile = clean(raw)
    write_text_atomic(_file(), json.dumps(profile, indent=2))
    return profile


def _said(part: dict[str, str]) -> bool:
    return any(part.values())


_PICKUP_WORDS = {
    "humbucker": ("captadores humbucker", "humbucker pickups"),
    "single": ("captadores single coil", "single-coil pickups"),
    "p90": ("captadores P90", "P90 pickups"),
    "mixed": ("humbucker e single coil (HSS)", "humbucker and single coils (HSS)"),
    "active": ("captadores ativos", "active pickups"),
    "passive": ("captadores passivos", "passive pickups"),
}
_OUTPUT_WORDS = {
    "low": ("saída fraca", "low output"),
    "medium": ("saída média", "medium output"),
    "high": ("saída forte", "high output"),
}


def _sentence(part: dict[str, str]) -> str:
    bits = []
    if part["name"]:
        bits.append(part["name"])
    if part["pickups"]:
        bits.append(tr(*_PICKUP_WORDS[part["pickups"]]))
    if part["output"]:
        bits.append(tr(*_OUTPUT_WORDS[part["output"]]))
    return ", ".join(bits)


def describe(profile: dict[str, dict[str, str]], *, guitar: bool = True,
             bass: bool = False) -> str:
    """The lines a request carries about the player's instruments ("" when the
    user said nothing): in the user's language, like the rest of the prose."""
    lines = []
    if guitar and _said(profile["guitar"]):
        lines.append(tr("- A minha guitarra: ", "- My guitar: ") + _sentence(profile["guitar"]))
    if bass and _said(profile["bass"]):
        lines.append(tr("- O meu baixo: ", "- My bass: ") + _sentence(profile["bass"]))
    if not lines:
        return ""
    head = tr(
        "O que eu toco (regula o ganho, o noise gate e o EQ para isto: captadores fortes ou "
        "ativos pedem menos ganho; single coils captam mais ruído):",
        "What I play (set the gain, the noise gate and the EQ for it: hot or active pickups "
        "need less gain; single coils pick up more hum):",
    )
    return head + "\n" + "\n".join(lines)


def _knob(entry_key: str, knob_key: str) -> dict[str, Any] | None:
    from rockforge.infrastructure.packaging.gear import gear_catalogue

    entry = gear_catalogue._by_key().get(entry_key) or {}
    return next((k for k in entry.get("Knobs") or [] if k.get("Key") == knob_key), None)


def _fmt(v: float) -> str:
    return f"{v:g}"


def _snap(value: float, knob: dict[str, Any]) -> float:
    """``value`` on the knob's own step, inside its range."""
    lo, hi = float(knob["MinValue"]), float(knob["MaxValue"])
    step = float(knob.get("ValueStep") or 0) or 1.0
    snapped = lo + round((value - lo) / step) * step
    return round(min(hi, max(lo, snapped)), 3)


def fit_tone(tone: dict[str, Any], profile: dict[str, dict[str, str]]) -> tuple[
        dict[str, Any], list[str]]:
    """A curated guitar preset set for the player's guitar, and what changed (in
    the user's language). Anything else — the user's own tone, a bass preset, a
    clean preset, a profile that says nothing — comes back as it is."""
    from rockforge.infrastructure.packaging.gear import tone_presets

    guitar = profile.get("guitar") or {}
    pickups, output = guitar.get("pickups", ""), guitar.get("output", "")
    hot = output == "high" or pickups == "active"
    hum = pickups in ("single", "p90", "mixed")
    low = output == "low" and not hot
    if not (hot or hum or low):
        return tone, []
    if tone_presets.preset_fingerprint(str(tone.get("key", ""))) is None:
        return tone, []
    pre = tone.get("pre") or []
    if not pre or not isinstance(pre[0], dict) or pre[0].get("key") != GATE_KEY:
        return tone, []          # a clean preset: no drive to fit

    out = copy.deepcopy(tone)
    changes: list[str] = []
    amp = out.get("amp") or {}
    for knob_key, value in sorted((amp.get("knobs") or {}).items()) if hot or low else []:
        if not knob_key.endswith("_Gain") or not isinstance(value, (int, float)):
            continue
        knob = _knob(str(amp.get("key")), knob_key)
        if knob is None:
            continue
        lo, hi = float(knob["MinValue"]), float(knob["MaxValue"])
        step = (-HOT_GAIN_CUT if hot else LOW_GAIN_BOOST) * (hi - lo)
        new = _snap(float(value) + step, knob)
        if new != value:
            amp["knobs"][knob_key] = new
            why = (tr("captadores fortes", "hot pickups") if hot
                   else tr("captadores de saída fraca", "low-output pickups"))
            changes.append(tr(f"ganho do amplificador {_fmt(value)} → {_fmt(new)} ({why})",
                              f"amp gain {_fmt(value)} → {_fmt(new)} ({why})"))
    close = (GATE_STEP_DB if hot else 0.0) + (GATE_STEP_DB if hum else 0.0)
    gate = out["pre"][0].setdefault("knobs", {})
    thresh = gate.get(GATE_KNOB)
    knob = _knob(GATE_KEY, GATE_KNOB)
    if close and isinstance(thresh, (int, float)) and knob is not None:
        new = _snap(float(thresh) + close, knob)
        if new != thresh:
            gate[GATE_KNOB] = new
            why = ", ".join(w for w, on in (
                (tr("captadores fortes", "hot pickups"), hot),
                (tr("single coils captam mais ruído", "single coils pick up more hum"), hum),
            ) if on)
            changes.append(tr(f"noise gate {_fmt(thresh)} → {_fmt(new)} dB ({why})",
                              f"noise gate {_fmt(thresh)} → {_fmt(new)} dB ({why})"))
    return out, changes


def fit_tones(tones: list[dict[str, Any]], profile: dict[str, dict[str, str]]) -> list[
        dict[str, Any]]:
    """Every tone of a list fitted, each that changed carrying ``fitted`` (the
    changes, for the card). A tone that is not a dict is passed through."""
    out = []
    for t in tones:
        if not isinstance(t, dict):
            out.append(t)
            continue
        fitted, changes = fit_tone(t, profile)
        out.append({**fitted, "fitted": changes} if changes else t)
    return out
