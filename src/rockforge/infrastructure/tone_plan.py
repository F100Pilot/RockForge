"""Tones written as text — what a chatbot answers when asked for a song's tones
and where each one comes in — turned into the project's tones and tone changes.

Two halves, both pure apart from reading the gear catalogue:

* :func:`build_prompt` writes the request the user pastes into ChatGPT (or any
  assistant): the song, its charts, its sections with their bars and times,
  the answer format and the game's gear with every knob's range.
* :func:`read_plan` reads the answer back: the JSON block wherever it sits in
  the text, gear and knobs matched to the catalogue, bars/sections/times turned
  into the build's own times per chart, at most four tones per chart. Every
  adaptation (a gear name read as its closest, a knob out of range, a cabinet
  chosen for the amp, a tone a chart could not keep) is said in ``warnings``;
  a text it does not recognise is refused (:class:`TonePlanError`), never
  guessed at.

Nothing here knows whether the assistant was right about the song: the tones
are its opinion, said so in the UI.
"""

from __future__ import annotations

import difflib
import json
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from rockforge.i18n import tr
from rockforge.infrastructure.packaging.gear import gear_catalogue

MAX_TEXT = 200_000
MAX_TONES = 4             # Rocksmith switches between Tone_A..D
MAX_SLOTS = 4             # pre pedals / post pedals / racks
MAX_PLAN_TONES = 24
MAX_CHANGES = 400
DEFAULT_VOLUME = -18.0    # DLC Builder's new-tone level (more negative = louder)
DEFAULT_MIC = "57_Cone"   # what every RockForge preset uses
_START_SLACK_S = 0.5      # a change this close to bar 1 (or the first note) is the start


class TonePlanError(ValueError):
    """The text is not a tone plan RockForge can read."""


@dataclass(frozen=True)
class ChartContext:
    """One built chart: its bars and sections in the BUILD's clock."""

    kind: str
    game_name: str
    bars: list[float]                    # bar 1 at index 0
    sections: list[tuple[str, float]]
    end: float
    first_note: float | None = None

    @property
    def bass(self) -> bool:
        return self.kind == "Bass"


@dataclass(frozen=True)
class PlanContext:
    title: str
    artist: str
    pad_s: float                         # the recording sits this much later in the build
    charts: list[ChartContext]
    album: str = ""


@dataclass
class TrackSet:
    kind: str
    game_name: str
    tone_base: str | None
    tone_names: list[str]
    tone_changes: list[tuple[float, str]]


@dataclass
class PlanResult:
    tones: list[dict[str, Any]] = field(default_factory=list)
    tracks: list[TrackSet] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: dict[str, str] = field(default_factory=dict)
    sources: list[str] = field(default_factory=list)


# --- reading the text ------------------------------------------------------

_QUOTES = str.maketrans({"“": '"', "”": '"', "„": '"', "‟": '"', "″": '"',
                         "‘": "'", "’": "'", "‚": "'", "‛": "'", " ": " "})


def _clean_json(text: str) -> str:
    """Drop comments and trailing commas outside strings (what chatbots add)."""
    out: list[str] = []
    i, n = 0, len(text)
    in_str = False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True
            out.append(c)
        elif c == "/" and text.startswith("//", i):
            while i < n and text[i] != "\n":
                i += 1
            continue
        elif c == "/" and text.startswith("/*", i):
            end = text.find("*/", i + 2)
            i = n if end < 0 else end + 2
            continue
        elif c in "}]":
            j = len(out) - 1
            while j >= 0 and out[j].isspace():
                j -= 1
            if j >= 0 and out[j] == ",":
                del out[j]
            out.append(c)
        else:
            out.append(c)
        i += 1
    return "".join(out)


def _balanced(text: str, start: int) -> str | None:
    """The {...} starting at ``start``, braces inside strings ignored."""
    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        c = text[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


def extract_plan(text: str) -> dict[str, Any]:
    """The JSON object in a chatbot's answer: inside a ``` fence or surrounded by
    prose, with typographic quotes, comments and trailing commas forgiven."""
    if len(text) > MAX_TEXT:
        raise TonePlanError(tr(f"o texto é demasiado longo (máximo {MAX_TEXT} caracteres)",
                               f"the text is too long (at most {MAX_TEXT} characters)"))
    text = text.translate(_QUOTES)
    candidates = [m.group(1) for m in re.finditer(r"```[a-zA-Z0-9_-]*\s*\n?(.*?)```", text, re.S)]
    candidates.append(text)
    for cand in candidates:
        for m in re.finditer(r"\{", cand):
            block = _balanced(cand, m.start())
            if block is None:
                continue
            try:
                data = json.loads(_clean_json(block))
            except ValueError:
                continue
            if isinstance(data, dict) and _get(data, "tones") is not None:
                return data
    raise TonePlanError(tr(
        "não encontrei no texto um bloco de tons no formato do RockForge — usa «Copiar o "
        "pedido» e cola a resposta toda, com o bloco JSON",
        "no RockForge tone block found in the text — use «Copy the request» and paste "
        "the whole answer, with its JSON block",
    ))


# --- small helpers ---------------------------------------------------------

def _norm(s: object) -> str:
    """Lower case, no accents, single spaces."""
    t = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return " ".join(t.lower().split())


def _alnum(s: object) -> str:
    return re.sub(r"[^a-z0-9]", "", _norm(s))


_ALIASES: dict[str, tuple[str, ...]] = {
    "tones": ("tones", "tons"),
    "changes": ("changes", "mudancas", "trocas", "timeline", "switches"),
    "sources": ("sources", "fontes", "references", "referencias"),
    "name": ("name", "nome"),
    "description": ("description", "descricao", "notes", "notas"),
    "amp": ("amp", "amplifier", "amplificador"),
    "cabinet": ("cabinet", "cab", "coluna", "cabine", "colunas"),
    "pre": ("prepedals", "pre", "pedaispre", "pedalspre", "pedals", "pedais"),
    "post": ("postpedals", "post", "pedaispos", "pedalspost", "pos"),
    "racks": ("racks", "rack"),
    "volume": ("volume", "level", "nivel"),
    "descriptors": ("descriptors", "descritores", "tags"),
    "key": ("key", "chave", "id"),
    "gear": ("name", "nome", "model", "modelo"),
    "knobs": ("knobs", "settings", "definicoes", "controls", "controlos", "controles"),
    "mic": ("mic", "microfone", "microphone"),
    "track": ("track", "tracks", "pista", "pistas", "arrangement", "chart", "faixa"),
    "at": ("at", "em", "when", "quando", "start", "inicio"),
    "bar": ("bar", "measure", "compasso"),
    "section": ("section", "seccao", "secao", "parte", "part"),
    "time": ("time", "tempo", "seconds", "segundos"),
    "tone": ("tone", "tom"),
}


def _get(obj: dict[str, Any], what: str) -> Any:
    keys = {_alnum(k): k for k in obj}
    for alias in _ALIASES[what]:
        if alias in keys:
            return obj[keys[alias]]
    return None


def _num(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if value == value and abs(value) != float("inf") else None
    m = re.fullmatch(r"\s*([+-]?\d+(?:[.,]\d+)?)\s*(?:db|dB|DB)?\s*", str(value))
    return float(m.group(1).replace(",", ".")) if m else None


def _fmt(s: float) -> str:
    s = max(0.0, s)
    tenths = round(s * 10)
    m, rest = divmod(tenths, 600)
    return f"{m}:{rest / 10:04.1f}"


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", _norm(name)).strip("_") or "tom"


# --- gear ------------------------------------------------------------------

_PREFIX = re.compile(r"^(bass_|di_)?(amp|cab|pedal|rack)_", re.I)


def _stem(key: str) -> str:
    return _alnum(_PREFIX.sub("", key))


def _entries(gtype: str) -> list[dict[str, Any]]:
    return [g for g in gear_catalogue._raw_catalogue() if g["Type"] == gtype]


def _is_bass_gear(key: str) -> bool:
    return key.startswith(("Bass_", "DI_"))


def match_gear(query: str, gtype: str, *, bass: bool = False) -> tuple[dict[str, Any] | None, bool]:
    """The catalogue entry a written gear name means, and whether it was exact.
    Exact: its key, its game name, or its key without the prefix
    ("Marshall JCM800" for ``Amp_MarshallJCM800``). Otherwise the closest name
    or key — preferring gear of the chart's instrument."""
    entries = _entries(gtype)
    q = str(query).strip()
    if not q:
        return None, False
    for g in entries:
        if g["Key"].lower() == q.lower():
            return g, True
    qa = _alnum(q)
    for g in entries:
        if _alnum(g["Name"]) == qa or _stem(g["Key"]) == qa:
            return g, True
    pool = [g for g in entries if _is_bass_gear(g["Key"]) == bass] or entries
    contained = [g for g in pool if len(_stem(g["Key"])) >= 4 and
                 (_stem(g["Key"]) in qa or (len(qa) >= 4 and qa in _stem(g["Key"])))]
    if contained:
        return max(contained, key=lambda g: len(_stem(g["Key"]))), False
    names: dict[str, dict[str, Any]] = {}
    for g in pool:
        names.setdefault(_alnum(g["Name"]), g)
        names.setdefault(_stem(g["Key"]), g)
    close = difflib.get_close_matches(qa, list(names), n=1, cutoff=0.72)
    return (names[close[0]], False) if close else (None, False)


def _cab_model(key: str) -> str:
    return re.sub(r"_(57|Condenser|Ribbon|Tube)_[A-Za-z]+$", "", key)


def _cabinet(query: str, mic: object, bass: bool) -> tuple[dict[str, Any] | None, bool]:
    """A cabinet by full key, or by model (name or key) plus a microphone."""
    entries = _entries("Cabinets")
    q = str(query).strip()
    for g in entries:
        if g["Key"].lower() == q.lower():
            return g, True
    models: dict[str, list[dict[str, Any]]] = {}
    for g in entries:
        models.setdefault(_cab_model(g["Key"]), []).append(g)
    qa = _alnum(q)
    model = next((m for m, gs in models.items()
                  if _alnum(gs[0]["Name"]) == qa or _stem(m) == qa), None)
    exact = model is not None
    if model is None:
        pool = [m for m in models if _is_bass_gear(m) == bass] or list(models)
        contained = [m for m in pool if len(_stem(m)) >= 4 and (_stem(m) in qa or
                     (len(qa) >= 4 and qa in _stem(m)))]
        if contained:
            model = max(contained, key=lambda m: len(_stem(m)))
        else:
            names = {_alnum(models[m][0]["Name"]): m for m in pool}
            names.update({_stem(m): m for m in pool})
            close = difflib.get_close_matches(qa, list(names), n=1, cutoff=0.72)
            model = names[close[0]] if close else None
    if model is None:
        return None, False
    return _pick_mic(models[model], mic), exact


def _pick_mic(cabs: list[dict[str, Any]], mic: object) -> dict[str, Any]:
    if mic:
        want = _alnum(str(mic)).replace("dynamic", "57").replace("sm57", "57")
        for g in cabs:
            tail = _alnum(g["Key"][len(_cab_model(g["Key"])):])
            cat = _alnum(g.get("Category") or "").replace("dynamic", "57")
            if want in (tail, cat):
                return g
    for g in cabs:
        if g["Key"].endswith("_" + DEFAULT_MIC):
            return g
    return cabs[0]


def cabinet_for_amp(amp_key: str) -> dict[str, Any]:
    """The cabinet RockForge's own presets pair with this amp; else one of the
    amp's own family (``Amp_CA100`` → a ``Cab_CA…``, a 4x12 or a 1x12 first);
    else the one the presets use most (the bass default for a bass)."""
    from rockforge.infrastructure.packaging.gear import tone_presets

    by_key = gear_catalogue._by_key()
    for tone, _ in tone_presets._LEAD_LIBRARY + tone_presets._RHYTHM_LIBRARY:
        if tone["amp"]["key"] == amp_key and tone["cabinet"]["key"] in by_key:
            return by_key[tone["cabinet"]["key"]]
    bass = _is_bass_gear(amp_key)
    stem = _PREFIX.sub("", amp_key)
    m = re.match(r"[A-Z][a-z]+|[A-Z]+(?=\d|[A-Z][a-z]|$)", stem)
    family = m.group(0) if m else stem
    prefix = ("Bass_Cab_" if bass else "Cab_") + family
    cabs = [g for g in _entries("Cabinets") if g["Key"].startswith(prefix)]
    if cabs:
        models = list(dict.fromkeys(_cab_model(g["Key"]) for g in cabs))
        model = next((mo for pref in ("1960a", "412", "112") for mo in models if pref in mo),
                     models[0])
        return _pick_mic([g for g in cabs if _cab_model(g["Key"]) == model], None)
    fallback = "Bass_Cab_EdenD610XST_Condenser_Edge" if bass else "Cab_Marshall1960a_57_Cone"
    return by_key[fallback]


# --- knobs -----------------------------------------------------------------

def _knob_items(raw: object) -> list[tuple[str, object]]:
    if isinstance(raw, dict):
        return [(str(k), v) for k, v in raw.items()]
    if isinstance(raw, list):
        out = []
        for it in raw:
            if isinstance(it, dict):
                name = _get(it, "name") or _get(it, "key")
                value = it.get("value", it.get("valor"))
                if name is not None:
                    out.append((str(name), value))
        return out
    return []


def _knob_value(knob: dict[str, Any], value: object) -> float | None:
    lo, hi = float(knob["MinValue"]), float(knob["MaxValue"])
    enum = knob.get("EnumValues")
    if enum and isinstance(value, str):
        for i, label in enumerate(enum):
            if _norm(label) == _norm(value):
                return float(i)
    if isinstance(value, str):
        s = value.strip().replace(",", ".")
        frac = re.fullmatch(r"([+-]?\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)", s)
        if frac and float(frac.group(2)) > 0:
            return lo + (hi - lo) * float(frac.group(1)) / float(frac.group(2))
        pct = re.fullmatch(r"([+-]?\d+(?:\.\d+)?)\s*%", s)
        if pct and knob.get("UnitType") != "%":
            return lo + (hi - lo) * float(pct.group(1)) / 100.0
        m = re.fullmatch(r"([+-]?\d+(?:\.\d+)?)\s*[a-zA-Z%]*", s)
        return float(m.group(1)) if m else None
    return _num(value)


def _knobs(entry: dict[str, Any], given: list[tuple[str, object]], label: str,
           warn: list[str]) -> dict[str, float]:
    knobs = entry.get("Knobs") or []
    values = gear_catalogue.knob_defaults(entry["Key"])
    by_name: dict[str, dict[str, Any]] = {}
    for k in knobs:
        by_name[_alnum(k["Name"])] = k
        by_name[_alnum(k["Key"])] = k
        by_name[_alnum(k["Key"][len(entry["Key"]):])] = k
    for name, raw in given:
        knob = by_name.get(_alnum(name))
        if knob is None:
            close = difflib.get_close_matches(_alnum(name), list(by_name), n=1, cutoff=0.8)
            knob = by_name[close[0]] if close else None
            if knob is not None:
                warn.append(tr(f"{label}: o controlo «{name}» lido como «{knob['Name']}»",
                               f"{label}: knob “{name}” read as “{knob['Name']}”"))
        if knob is None:
            have = ", ".join(k["Name"] for k in knobs) or "—"
            warn.append(tr(f"{label}: não tem o controlo «{name}» (tem: {have}) — ignorado",
                           f"{label}: has no knob “{name}” (it has: {have}) — ignored"))
            continue
        v = _knob_value(knob, raw)
        if v is None:
            warn.append(tr(f"{label}: valor «{raw}» de {knob['Name']} não é um número — fica "
                           f"{values[knob['Key']]:g}",
                           f"{label}: value “{raw}” of {knob['Name']} is not a number — left at "
                           f"{values[knob['Key']]:g}"))
            continue
        lo, hi = float(knob["MinValue"]), float(knob["MaxValue"])
        if v < lo or v > hi:
            c = min(hi, max(lo, v))
            warn.append(tr(f"{label}: {knob['Name']} {v:g} fora de {lo:g}–{hi:g} — fica {c:g}",
                           f"{label}: {knob['Name']} {v:g} outside {lo:g}–{hi:g} — set to {c:g}"))
            v = c
        step = float(knob.get("ValueStep") or 0)
        if step > 0:
            v = lo + round((v - lo) / step) * step
            v = round(min(hi, max(lo, v)), 6)
        values[knob["Key"]] = v
    return values


def _gear_spec(raw: object) -> tuple[str, list[tuple[str, object]], object]:
    """(name or key, knobs, mic) from a string or an object; unknown fields of an
    object that look like knob values count as knobs."""
    if isinstance(raw, str):
        return raw, [], None
    if not isinstance(raw, dict):
        return "", [], None
    name = _get(raw, "key") or _get(raw, "gear") or ""
    given = _knob_items(_get(raw, "knobs"))
    known = {a for w in ("key", "gear", "knobs", "mic", "description") for a in _ALIASES[w]}
    known |= {"type", "tipo", "category", "categoria", "slot", "brand", "marca", "real", "realgear"}
    for k, v in raw.items():
        if _alnum(k) not in known and isinstance(v, (int, float, str)) and not isinstance(v, bool):
            given.append((str(k), v))
    return str(name), given, _get(raw, "mic")


# --- one tone --------------------------------------------------------------

def _label(tone: str, gear: dict[str, Any]) -> str:
    return tr(f"«{tone}» ({gear['Name']})", f"“{tone}” ({gear['Name']})")


def _tone(raw: dict[str, Any], key: str, warn: list[str]) -> dict[str, Any] | None:
    name = str(_get(raw, "name") or key).strip()[:80] or key
    amp_name, amp_knobs, _ = _gear_spec(_get(raw, "amp"))
    if not amp_name:
        warn.append(tr(f"«{name}»: sem amplificador — o tom não foi importado",
                       f"“{name}”: no amp — the tone was not imported"))
        return None
    amp, exact = match_gear(amp_name, "Amps")
    if amp is None:
        warn.append(tr(f"«{name}»: o amplificador «{amp_name}» não existe no jogo — o tom não "
                       "foi importado",
                       f"“{name}”: the amp “{amp_name}” is not in the game — the tone was not "
                       "imported"))
        return None
    if not exact:
        warn.append(tr(f"«{name}»: amplificador «{amp_name}» lido como {amp['Name']} "
                       f"({amp['Key']}), o mais parecido",
                       f"“{name}”: amp “{amp_name}” read as {amp['Name']} ({amp['Key']}), the "
                       "closest"))
    bass = _is_bass_gear(amp["Key"])
    tone: dict[str, Any] = {
        "key": key, "name": name,
        "amp": {"key": amp["Key"], "knobs": _knobs(amp, amp_knobs, _label(name, amp), warn)},
    }
    cab_raw = _get(raw, "cabinet")
    cab_name, _, mic = _gear_spec(cab_raw)
    cab = None
    if cab_name:
        cab, exact = _cabinet(cab_name, mic, bass)
        if cab is None:
            warn.append(tr(f"«{name}»: a coluna «{cab_name}» não existe no jogo",
                           f"“{name}”: the cabinet “{cab_name}” is not in the game"))
        elif not exact:
            warn.append(tr(f"«{name}»: coluna «{cab_name}» lida como {cab['Name']} "
                           f"({cab['Key']}), a mais parecida",
                           f"“{name}”: cabinet “{cab_name}” read as {cab['Name']} ({cab['Key']}), "
                           "the closest"))
    if cab is None:
        cab = cabinet_for_amp(amp["Key"])
        warn.append(tr(f"«{name}»: coluna escolhida para o amplificador: {cab['Name']} "
                       f"({cab['Key']})",
                       f"“{name}”: cabinet chosen for the amp: {cab['Name']} ({cab['Key']})"))
    tone["cabinet"] = {"key": cab["Key"], "knobs": {}}
    moved_items: list[tuple[str, dict[str, Any]]] = []
    for slot, gtype in (("pre", "Pedals"), ("post", "Pedals"), ("racks", "Racks")):
        items = _get(raw, slot)
        items = items if isinstance(items, list) else ([items] if items else [])
        out: list[dict[str, Any]] = []
        for it in items:
            gname, gknobs, _ = _gear_spec(it)
            if not gname:
                continue
            entry, exact = match_gear(gname, gtype, bass=bass)
            other = "Racks" if gtype == "Pedals" else "Pedals"
            moved = False
            if entry is None or not exact:
                alt, alt_exact = match_gear(gname, other, bass=bass)
                if alt is not None and alt_exact:
                    entry, exact, moved = alt, True, True
            if entry is None:
                warn.append(tr(f"«{name}»: «{gname}» não existe no jogo — ignorado",
                               f"“{name}”: “{gname}” is not in the game — ignored"))
                continue
            if not exact:
                warn.append(tr(f"«{name}»: «{gname}» lido como {entry['Name']} ({entry['Key']}), "
                               "o mais parecido",
                               f"“{name}”: “{gname}” read as {entry['Name']} ({entry['Key']}), the "
                               "closest"))
            pedal = {"key": entry["Key"], "knobs": _knobs(entry, gknobs, _label(name, entry), warn)}
            if moved:
                target = "racks" if entry["Type"] == "Racks" else "pre"
                warn.append(tr(f"«{name}»: {entry['Name']} é um "
                               f"{'rack' if target == 'racks' else 'pedal'} — posto com esses",
                               f"“{name}”: {entry['Name']} is a "
                               f"{'rack' if target == 'racks' else 'pedal'} — placed with those"))
                moved_items.append((target, pedal))
                continue
            out.append(pedal)
        tone[slot] = out
    for target, pedal in moved_items:
        tone[target].append(pedal)
    for slot, label in (("pre", tr("pedais antes do amplificador", "pedals before the amp")),
                        ("post", tr("pedais depois do amplificador", "pedals after the amp")),
                        ("racks", "racks")):
        if len(tone[slot]) > MAX_SLOTS:
            dropped = ", ".join(gear_catalogue.gear_name(p["key"]) for p in tone[slot][MAX_SLOTS:])
            warn.append(tr(f"«{name}»: só cabem {MAX_SLOTS} {label} — ficou de fora: {dropped}",
                           f"“{name}”: only {MAX_SLOTS} {label} fit — left out: {dropped}"))
            tone[slot] = tone[slot][:MAX_SLOTS]
    vol_raw = _get(raw, "volume")
    vol = DEFAULT_VOLUME
    if vol_raw is not None:
        v = _num(vol_raw)
        if v is None or v == 0:
            warn.append(tr(f"«{name}»: volume «{vol_raw}» não lido — fica 18",
                           f"“{name}”: volume “{vol_raw}” not read — set to 18"))
        else:
            level = abs(v)
            if level < 0.1 or level > 36:
                c = min(36.0, max(0.1, level))
                warn.append(tr(f"«{name}»: volume {level:g} fora de 0,1–36 — fica {c:g}",
                               f"“{name}”: volume {level:g} outside 0.1–36 — set to {c:g}"))
                level = c
            vol = -level
    tone["volume"] = round(vol, 2)
    descs = _get(raw, "descriptors")
    if isinstance(descs, str):
        descs = re.split(r"[,;/]", descs)
    descs = [str(d).strip() for d in descs if str(d).strip()] if isinstance(descs, list) else []
    codes: list[str] = []
    table = {_norm(k): v for k, v in gear_catalogue.TONE_DESCRIPTORS.items()}
    known_codes = set(gear_catalogue.TONE_DESCRIPTORS.values())
    for d in descs:
        code = str(d) if str(d) in known_codes else table.get(_norm(d))
        if code is None:
            warn.append(tr(f"«{name}»: descritor «{d}» não existe no jogo — ignorado",
                           f"“{name}”: descriptor “{d}” is not in the game — ignored"))
        elif code not in codes:
            codes.append(code)
    tone["descriptors"] = codes
    if gear_catalogue.tone_from_dict(tone) is None:  # the catalogue disagrees: never ship it
        return None
    return tone


# --- when ------------------------------------------------------------------

_BAR = re.compile(r"^(?:c|comp|compasso|bar|measure|m)\.?\s*#?\s*(\d+)$")
_CLOCK = re.compile(r"^(\d+):(\d{1,2}(?:[.,]\d+)?)$")
_SECS = re.compile(r"^(\d+(?:[.,]\d+)?)\s*(?:s|seg|sec|segundos|seconds)?$")
_START = {"start", "inicio", "beginning", "comeco", "intro start", "song start",
          "inicio da musica", "from the start", "desde o inicio"}
_SECTION = re.compile(r"^(?:seccao|secao|section)\s*[:\-]?\s*(.+)$")


def parse_when(change: dict[str, Any]) -> tuple[str, Any] | None:
    """("start",) / ("bar", n) / ("time", s) / ("section", label) from a change."""
    for what, kind in (("bar", "bar"), ("section", "section"), ("time", "time")):
        v = _get(change, what)
        if v is None:
            continue
        if kind == "bar":
            n = _num(v)
            if n is None:
                m = _BAR.match(_norm(v))
                n = float(m.group(1)) if m else None
            return ("bar", int(n)) if n is not None else None
        if kind == "time":
            return _when_text(v) if isinstance(v, str) else (("time", float(v))
                                                             if _num(v) is not None else None)
        return ("section", str(v))
    v = _get(change, "at")
    if v is None:
        return None
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return ("time", float(v))
    return _when_text(str(v))


def _when_text(text: str) -> tuple[str, Any] | None:
    t = _norm(text)
    if not t:
        return None
    if t in _START:
        return ("start", None)
    if m := _BAR.match(t):
        return ("bar", int(m.group(1)))
    if m := _CLOCK.match(t):
        return ("time", int(m.group(1)) * 60 + float(m.group(2).replace(",", ".")))
    if m := _SECS.match(t):
        return ("time", float(m.group(1).replace(",", ".")))
    if m := _SECTION.match(t):
        return ("section", m.group(1))
    return ("section", text.strip())


def section_labels(sections: list[tuple[str, float]]) -> list[tuple[str, float]]:
    """Each section with the label the prompt gives it: its name, or "name #k"
    when the name repeats."""
    counts: dict[str, int] = {}
    for name, _ in sections:
        counts[_norm(name)] = counts.get(_norm(name), 0) + 1
    seen: dict[str, int] = {}
    out = []
    for name, t in sections:
        n = _norm(name)
        seen[n] = seen.get(n, 0) + 1
        out.append((name if counts[n] == 1 else f"{name} #{seen[n]}", t))
    return out


def _section_time(label: str, chart: ChartContext) -> tuple[float | None, str | None]:
    """The time of a section of the chart, and a note when the label was read loosely."""
    want = _norm(label)
    for lab, t in section_labels(chart.sections):
        if _norm(lab) == want:
            return t, None
    same = [t for name, t in chart.sections if _norm(name) == want]
    if same:
        return same[0], tr(f"«{label}» aparece {len(same)} vezes — usada a primeira (escreve "
                           f"«{label} #2» para outra)",
                           f"“{label}” occurs {len(same)} times — used the first (write "
                           f"“{label} #2” for another)")
    m = re.match(r"^(.*?)\s*(?:#|\(|n\.?o?\s*)?(\d+)\)?$", want)
    if m and m.group(1):
        base, k = m.group(1).strip(), int(m.group(2))
        times = [t for name, t in chart.sections if _norm(name) == base]
        if 1 <= k <= len(times):
            return times[k - 1], None
    return None, None


# --- the plan --------------------------------------------------------------

def _tracks_for(value: object, charts: list[ChartContext]) -> tuple[list[ChartContext], list[str]]:
    """The charts a change names, and the names it gave that match none."""
    guitar = [c for c in charts if not c.bass] or charts
    if value is None:
        return guitar, []
    items = value if isinstance(value, list) else [value]
    out: list[ChartContext] = []
    unknown: list[str] = []
    every = {"all", "todas", "todos", "ambas", "both", "every", "*", "all tracks",
             "todas as pistas", "all charts", "guitarras", "guitars", "all guitars"}
    alias = {"ritmo": "rhythm", "baixo": "bass", "combo": "combined", "combinado": "combined"}
    for it in items:
        t = _norm(it)
        if t in every:
            out.extend(c for c in guitar if c not in out)
            continue
        t = alias.get(t, t)
        hit = [c for c in charts if t in (_norm(c.kind), _norm(c.game_name))]
        if not hit:
            unknown.append(str(it))
        out.extend(c for c in hit if c not in out)
    return out, unknown


def read_plan(text: str, ctx: PlanContext) -> PlanResult:
    """The tones and each chart's tone changes a pasted answer describes."""
    data = extract_plan(text)
    res = PlanResult()
    warn = res.warnings
    raw_tones = _get(data, "tones")
    if not isinstance(raw_tones, list) or not raw_tones:
        raise TonePlanError(tr("o bloco não tem nenhum tom em «tones»",
                               "the block has no tone in “tones”"))
    by_ref: dict[str, str] = {}
    for raw in raw_tones[:MAX_PLAN_TONES]:
        if not isinstance(raw, dict):
            continue
        name = str(_get(raw, "name") or "").strip()
        ref = _norm(name)
        if ref and ref in by_ref:
            warn.append(tr(f"o tom «{name}» aparece duas vezes — fica o primeiro",
                           f"the tone “{name}” is given twice — the first is kept"))
            continue
        base = "rf_" + _slug(name or f"tom {len(res.tones) + 1}")
        key, n = base, 1
        while any(t["key"] == key for t in res.tones):
            n += 1
            key = f"{base}_{n}"
        tone = _tone(raw, key, warn)
        if tone is None:
            continue
        res.tones.append(tone)
        by_ref[ref or key] = key
        by_ref[key] = key
        desc = _get(raw, "description")
        if desc:
            res.notes[key] = str(desc)[:600]
    if len(raw_tones) > MAX_PLAN_TONES:
        warn.append(tr(f"só são lidos os primeiros {MAX_PLAN_TONES} tons",
                       f"only the first {MAX_PLAN_TONES} tones are read"))
    if not res.tones:
        raise TonePlanError(tr("nenhum dos tons do bloco pôde ser construído com o equipamento "
                               "do jogo", "none of the block's tones could be built from the "
                               "game's gear") + (": " + "; ".join(warn) if warn else ""))

    src = _get(data, "sources")
    if isinstance(src, list):
        res.sources = [str(s)[:300] for s in src if str(s).strip()][:20]
    elif isinstance(src, str) and src.strip():
        res.sources = [src.strip()[:300]]

    raw_changes = _get(data, "changes")
    raw_changes = raw_changes if isinstance(raw_changes, list) else []
    if len(raw_changes) > MAX_CHANGES:
        warn.append(tr(f"só são lidas as primeiras {MAX_CHANGES} mudanças",
                       f"only the first {MAX_CHANGES} changes are read"))
    per_chart: dict[str, list[tuple[float | None, int, str]]] = {}
    for order, ch in enumerate(raw_changes[:MAX_CHANGES]):
        if not isinstance(ch, dict):
            continue
        tone_ref = _get(ch, "tone")
        target = by_ref.get(_norm(tone_ref)) if tone_ref is not None else None
        if target is None:
            warn.append(tr(f"mudança para «{tone_ref}», um tom que não está em «tones» — ignorada",
                           f"change to “{tone_ref}”, a tone not in “tones” — ignored"))
            continue
        when = parse_when(ch)
        if when is None:
            warn.append(tr(f"mudança para «{tone_ref}» sem momento («at») — ignorada",
                           f"change to “{tone_ref}” with no moment (“at”) — ignored"))
            continue
        charts, unknown = _tracks_for(_get(ch, "track"), ctx.charts)
        for u in unknown:
            names = ", ".join(c.game_name for c in ctx.charts)
            warn.append(tr(f"a pista «{u}» não existe neste projeto (há: {names})",
                           f"there is no chart “{u}” in this project (there are: {names})"))
        for chart in charts:
            placed, t = _resolve(when, chart, ctx.pad_s, str(tone_ref), warn)
            if placed:
                per_chart.setdefault(chart.kind, []).append((t, order, target))

    used: set[str] = set()
    for chart in ctx.charts:
        entries = per_chart.get(chart.kind)
        if not entries:
            continue
        track = _track_set(chart, entries, warn)
        used.update(track.tone_names)
        res.tracks.append(track)
    if raw_changes and not res.tracks:
        warn.append(tr("nenhuma mudança se aplica a uma pista deste projeto",
                       "no change applies to a chart of this project"))
    named = {t.kind for t in res.tracks}
    for chart in ctx.charts:
        if res.tracks and chart.kind not in named:
            warn.append(tr(f"{chart.game_name} não é referida — fica com os tons que tem",
                           f"{chart.game_name} is not mentioned — it keeps the tones it has"))
    for tone in res.tones:
        if tone["key"] not in used:
            warn.append(tr(f"«{tone['name']}» não é usado por nenhuma pista — fica só nos tons do "
                           "projeto",
                           f"“{tone['name']}” is used by no chart — it is only added to the "
                           "project's tones"))
    return res


def _resolve(when: tuple[str, Any], chart: ChartContext, pad_s: float, tone: str,
             warn: list[str]) -> tuple[bool, float | None]:
    """(placed, the change's time in the chart — None = the start); not placed
    is said in ``warn``."""
    kind, value = when
    who = chart.game_name
    if kind == "start":
        return True, None
    if kind == "bar":
        if not 1 <= value <= len(chart.bars):
            warn.append(tr(f"{who}: o compasso {value} não existe (vai de 1 a {len(chart.bars)}) "
                           f"— «{tone}» ignorado",
                           f"{who}: bar {value} does not exist (bars 1 to {len(chart.bars)}) — "
                           f"“{tone}” ignored"))
            return False, None
        return True, (None if value == 1 else chart.bars[value - 1])
    if kind == "time":
        t = float(value) + pad_s
        if value < 0 or t > chart.end:
            warn.append(tr(f"{who}: {_fmt(float(value))} fica fora da música — «{tone}» ignorado",
                           f"{who}: {_fmt(float(value))} is outside the song — “{tone}” ignored"))
            return False, None
        return True, t
    at, note = _section_time(str(value), chart)
    if at is None:
        labels = ", ".join(lab for lab, _ in section_labels(chart.sections)) or "—"
        warn.append(tr(f"{who}: não há a secção «{value}» (há: {labels}) — «{tone}» ignorado",
                       f"{who}: there is no section “{value}” (there are: {labels}) — “{tone}” "
                       "ignored"))
        return False, None
    if note:
        warn.append(f"{who}: {note}")
    return True, at


def _track_set(chart: ChartContext, entries: list[tuple[float | None, int, str]],
               warn: list[str]) -> TrackSet:
    who = chart.game_name
    start_at = max(chart.bars[0] if chart.bars else 0.0, 0.0)
    if chart.first_note is not None:
        start_at = max(start_at, chart.first_note)
    base: str | None = None
    timed: dict[float, tuple[int, str]] = {}
    for t, order, key in entries:
        if t is None or t <= start_at + _START_SLACK_S:
            base = key  # the last one given for the start wins
            continue
        slot = round(t, 3)
        if slot in timed and timed[slot][1] != key:
            warn.append(tr(f"{who}: duas mudanças em {_fmt(t)} — fica a última",
                           f"{who}: two changes at {_fmt(t)} — the last is kept"))
        timed[slot] = (order, key)
    changes = sorted((t, k) for t, (_, k) in timed.items())
    if base is None and changes:
        base = changes.pop(0)[1]
        warn.append(tr(f"{who}: sem tom para o início — toca «{base}» desde o início",
                       f"{who}: no tone for the start — it plays “{base}” from the start"))
    changes = _drop_repeats(base, changes)
    names = [base] if base else []
    for _, k in changes:
        if k not in names:
            names.append(k)
    if len(names) > MAX_TONES:
        keep = _longest(base, changes, chart.end, MAX_TONES)
        dropped = [k for k in names if k not in keep]
        warn.append(tr(f"{who}: o Rocksmith só troca entre {MAX_TONES} tons por pista — ficaram "
                       f"de fora (o tom anterior continua): {', '.join(dropped)}",
                       f"{who}: Rocksmith switches between {MAX_TONES} tones per chart — left "
                       f"out (the tone before carries on): {', '.join(dropped)}"))
        changes = _drop_repeats(base, [(t, k) for t, k in changes if k in keep])
        names = [k for k in names if k in keep]
    return TrackSet(kind=chart.kind, game_name=chart.game_name, tone_base=base,
                    tone_names=names, tone_changes=[(round(t, 3), k) for t, k in changes])


def _drop_repeats(base: str | None, changes: list[tuple[float, str]]) -> list[tuple[float, str]]:
    out, current = [], base
    for t, k in changes:
        if k != current:
            out.append((t, k))
            current = k
    return out


def _longest(base: str | None, changes: list[tuple[float, str]], end: float, n: int) -> set[str]:
    """The base and the n-1 other tones that sound longest."""
    played: dict[str, float] = {}
    marks = [(0.0, base)] + list(changes)
    for i, (t, k) in enumerate(marks):
        if k is None:
            continue
        nxt = marks[i + 1][0] if i + 1 < len(marks) else max(end, t)
        played[k] = played.get(k, 0.0) + max(0.0, nxt - t)
    keep = {base} if base else set()
    for k in sorted((k for k in played if k != base), key=lambda k: -played[k]):
        if len(keep) >= n:
            break
        keep.add(k)
    return {k for k in keep if k}


# --- the request -----------------------------------------------------------

def _knob_line(g: dict[str, Any]) -> str:
    parts = []
    for k in g.get("Knobs") or []:
        lo, hi, d = k["MinValue"], k["MaxValue"], k["DefaultValue"]
        if k.get("EnumValues"):
            parts.append(f"{k['Name']} [{'/'.join(k['EnumValues'])}; {k['EnumValues'][int(d)]}]")
        else:
            unit = k.get("UnitType")
            u = "" if unit in (None, "number", "enum") else f" {unit}"
            parts.append(f"{k['Name']} [{lo:g}–{hi:g}{u}; {d:g}]")
    return ", ".join(parts)


def gear_list(bass: bool) -> str:
    """The game's gear, compact: amps, cabinet models and microphones, pedals by
    family, racks — each with its knobs [range; default]."""
    def keep(g: dict[str, Any]) -> bool:
        return bass or not _is_bass_gear(g["Key"])

    lines = ["AMPS:"]
    lines += [f"- {g['Key']} ({g['Name']}): {_knob_line(g)}" for g in _entries("Amps") if keep(g)]
    lines.append("CABINETS (key = model + _mic; mics: 57_Cone, 57_Edge, 57_OffAxis, "
                 "Condenser_Cone, Condenser_Edge, Condenser_OffAxis, Ribbon_…, Tube_… — not every "
                 "model has every mic):")
    models: dict[str, str] = {}
    for g in _entries("Cabinets"):
        if keep(g):
            models.setdefault(_cab_model(g["Key"]), g["Name"])
    lines += [f"- {m} ({n})" for m, n in models.items()]
    pedals = [g for g in _entries("Pedals") if keep(g)]
    for cat in sorted({str(g.get("Category")) for g in pedals}):
        lines.append(f"PEDALS — {cat}:")
        lines += [f"- {g['Key']} ({g['Name']}): {_knob_line(g)}"
                  for g in pedals if str(g.get("Category")) == cat]
    lines.append("RACKS:")
    lines += [f"- {g['Key']} ({g['Name']}): {_knob_line(g)}" for g in _entries("Racks") if keep(g)]
    return "\n".join(lines)


_EXAMPLE = """{
  "tones": [
    {
      "name": "Verse crunch",
      "description": "why this tone, and how sure you are",
      "amp": {"key": "Amp_MarshallJCM800",
              "knobs": {"Gain": 62, "Bass": 55, "Mid": 70, "Treble": 60}},
      "cabinet": "Cab_Marshall1960a_57_Cone",
      "pre_pedals": [{"key": "Pedal_…", "knobs": {"…": 50}}],
      "post_pedals": [],
      "racks": [],
      "volume": 18,
      "descriptors": ["Crunch"]
    }
  ],
  "changes": [
    {"track": "all", "at": "start", "tone": "Verse crunch"},
    {"track": "LEAD", "at": "bar 49", "tone": "Solo lead"},
    {"track": "all", "at": "Chorus #2", "tone": "Chorus distortion"},
    {"track": "RHYTHM", "at": "2:31.5", "tone": "Verse crunch"}
  ],
  "sources": ["where the information comes from, if anywhere"]
}"""


def build_prompt(ctx: PlanContext) -> str:
    """The request for an assistant, in the user's language (the format and the
    gear list stay in English: they are what its answer must use verbatim)."""
    bass = any(c.bass for c in ctx.charts)
    ref = next((c for c in ctx.charts if not c.bass), ctx.charts[0] if ctx.charts else None)
    song_end = max((c.end for c in ctx.charts), default=ctx.pad_s) - ctx.pad_s
    charts = "\n".join(
        f"- {c.game_name}" + (f" — {tr('baixo', 'bass')}" if c.bass else "")
        + f" ({tr('compassos', 'bars')} 1–{len(c.bars)})" for c in ctx.charts)
    if ref and ref.sections:
        rows = []
        for label, t in section_labels(ref.sections):
            bar = sum(1 for b in ref.bars if b <= t + 1e-3) or 1
            rows.append(f"- {label} — bar {bar} — {_fmt(t - ctx.pad_s)}")
        sections = "\n".join(rows)
    else:
        sections = tr("(a pauta não tem secções: usa compassos ou tempos)",
                      "(the score has no sections: use bars or times)")
    album = f" ({ctx.album})" if ctx.album else ""
    descriptors = ", ".join(gear_catalogue.TONE_DESCRIPTORS)
    fence = f"```json\n{_EXAMPLE}\n```"
    rules_pt = "\n".join([
        "Responde com UM bloco JSON, exatamente neste formato (chaves em inglês), e nada fora "
        "dele além de uma frase, se quiseres:", "", fence, "", "Regras:",
        "- Usa só equipamento da lista abaixo, pela chave (\"key\"). Os nomes são os do jogo; a "
        "chave diz muitas vezes o equipamento real que imita (Amp_MarshallJCM800). Escolhe o "
        "mais parecido com o que foi usado na gravação.",
        "- Controlos (\"knobs\") pelo nome, dentro dos limites indicados [mín–máx; valor por "
        "omissão]; um controlo que não indicares fica no valor por omissão.",
        "- No máximo 4 pedais antes do amplificador, 4 depois e 4 racks.",
        "- \"volume\": de 0.1 a 36, mais alto é mais forte; 18 é o nível normal.",
        f"- \"descriptors\": um a três de: {descriptors}.",
        "- No máximo 4 tons diferentes por pista (o Rocksmith só troca entre 4).",
        "- \"track\": o nome de uma pista abaixo, ou \"all\" (todas as guitarras; o baixo só "
        "quando nomeado).",
        "- \"at\": \"start\", \"bar N\", o nome de uma secção exatamente como está abaixo, ou "
        "um tempo da gravação \"m:ss.s\".",
        "- Diz em \"description\" quando não tens a certeza. Não inventes fontes: \"sources\" "
        "só com o que conheces de facto (entrevistas, rig rundowns, a página do equipamento do "
        "artista).",
    ])
    rules_en = "\n".join([
        "Answer with ONE JSON block, exactly in this format, and nothing outside it but a "
        "sentence if you like:", "", fence, "", "Rules:",
        "- Use only gear from the list below, by its \"key\". The names are the game's; the key "
        "often names the real gear it imitates (Amp_MarshallJCM800). Pick what is closest to "
        "what the recording used.",
        "- Knobs by name, within the limits shown [min–max; default]; a knob you leave out "
        "stays at its default.",
        "- At most 4 pedals before the amp, 4 after and 4 racks.",
        "- \"volume\": 0.1 to 36, higher is louder; 18 is the usual level.",
        f"- \"descriptors\": one to three of: {descriptors}.",
        "- At most 4 different tones per track (Rocksmith switches between 4).",
        "- \"track\": the name of a track below, or \"all\" (every guitar; the bass only when "
        "named).",
        "- \"at\": \"start\", \"bar N\", a section name exactly as written below, or a time "
        "in the recording \"m:ss.s\".",
        "- Say in \"description\" when you are not sure. Do not invent sources: \"sources\" "
        "only with what you actually know (interviews, rig rundowns, the artist's gear page).",
    ])
    head = tr(
        f"Estou a fazer uma música para o Rocksmith 2014 com o RockForge e preciso dos tons de "
        f"guitarra de «{ctx.title}» de {ctx.artist}{album}: que tons a gravação usa, como está "
        "cada um regulado e onde entra cada um.",
        f"I am making a Rocksmith 2014 custom song with RockForge and need the guitar tones of "
        f"“{ctx.title}” by {ctx.artist}{album}: which tones the recording uses, how each one is "
        "set, and where each one comes in.",
    )
    song = tr("A música", "The song")
    dur = tr("Duração", "Length")
    tracks = tr("Pistas", "Tracks")
    secs = tr("Secções (compasso — tempo na gravação)", "Sections (bar — time in the recording)")
    gear = tr("Equipamento do jogo (chave (nome): controlos [mín–máx; por omissão])",
              "The game's gear (key (name): knobs [min–max; default])")
    return "\n\n".join([
        head,
        tr(rules_pt, rules_en),
        f"{song}:\n- {dur}: {_fmt(song_end)}\n{tracks}:\n{charts}\n{secs}:\n{sections}",
        f"{gear}:\n{gear_list(bass)}",
    ])
