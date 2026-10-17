"""Check a built ``.psarc`` before it goes to the game.

Every native-SNG crash that cost a session was a broken invariant in our own
file — a note pointing at a phrase that does not exist, an anchor across a
phrase boundary, a phrase with notes and no level to climb, a template whose
unused strings carry a real pitch, a hand shape over the wrong notes — and the
only way to find one was to play up to it. :func:`check_sng` holds those rules
in ONE place (``tests/test_hand_shape_fuzz.py`` runs it on hundreds of random
charts, so the checker and the builder are tested against each other), and
:func:`verify_psarc` reads the archive the user is about to copy, exactly as
written, and runs them on every chart in it.

Honest limit: this is OUR reading of the file. It catches what we know the
game trips on; it cannot catch what the game reads differently from us
(``VOCAL_NOTE = 254`` and the partial-block ``zlength`` were of that kind), so
it never replaces playing the song.
"""

from __future__ import annotations

import bisect
import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from rockforge.i18n import tr
from rockforge.infrastructure.packaging.psarc.sng import (
    CHORD_MASK_ARPEGGIO,
    NOTE_MASK_ARPEGGIO,
    NOTE_MASK_CHILD,
    NOTE_MASK_PARENT,
    SngArrangementLevel,
    SngFingerprint,
    SngModel,
    SngNote,
)
from rockforge.infrastructure.rsxml.vocals import VOCAL_NOTE

# Float32 times read back from the file.
_EPS = 1e-4


@dataclass(frozen=True)
class Problem:
    """One broken rule. ``code`` is stable (tests and the UI key on it);
    ``arrangement`` is the chart's asset name inside the archive."""

    code: str
    level: int | None = None
    time: float | None = None
    detail: str = ""
    arrangement: str = ""


@dataclass
class PsarcReport:
    path: str
    charts: list[str] = field(default_factory=list)
    problems: list[Problem] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


def _s8(v: int) -> int:
    """A signed byte, whichever way it was handed back (255 on disk = -1)."""
    return v - 256 if v >= 128 else v


def _find_fingerprint(time: float, fps: list[SngFingerprint]) -> int:
    """DLC Builder's ``findFingerPrintId``: the first shape with start <= t < end."""
    for i, fp in enumerate(fps):
        if fp.start_time > time:
            return -1
        if fp.start_time <= time < fp.end_time:
            return i
    return -1


def check_sng(model: SngModel, *, bass: bool = False) -> list[Problem]:
    """Every rule a chart must hold, level by level (``bass``: a Bass chart)."""
    out: list[Problem] = []
    add = out.append
    phrases, pis = model.phrases, model.phrase_iterations

    if bass:
        # DLC Builder's I36: Rocksmith's bass has strings 0-3, chords included.
        for lv in model.arrangements:
            for n in lv.notes:
                tpl = model.chord_templates[n.chord_id] if 0 <= n.chord_id < len(
                    model.chord_templates) else None
                high = n.string >= 4 if n.chord_id < 0 else (
                    tpl is not None and any(_s8(f) >= 0 for f in tpl.frets[4:]))
                if high:
                    add(Problem("bass_string", level=lv.difficulty, time=n.time))
                    break

    for v in model.vocals:
        if v.note != VOCAL_NOTE:
            add(Problem("vocal_note", time=v.time, detail=str(v.note)))

    for i, pi in enumerate(pis):
        if not 0 <= pi.phrase_id < len(phrases):
            add(Problem("phrase_out_of_range", time=pi.start_time, detail=str(pi.phrase_id)))
        if i and pi.start_time < pis[i - 1].start_time - _EPS:
            add(Problem("iterations_out_of_order", time=pi.start_time))
    for i, s in enumerate(model.sections):
        if i and s.start_time < model.sections[i - 1].start_time - _EPS:
            add(Problem("section_out_of_order", time=s.start_time, detail=s.name))
        if not (0 <= s.start_phrase_iteration_id <= s.end_phrase_iteration_id < len(pis)):
            add(Problem("section_bad_range", time=s.start_time, detail=s.name))
    for t in model.tones:
        if not 0 <= t.tone_id <= 3:
            add(Problem("tone_slot", time=t.time, detail=str(t.tone_id)))

    templates = model.chord_templates
    for k, ct in enumerate(templates):
        for fret, midi in zip(ct.frets, ct.notes, strict=True):
            fret = _s8(fret)
            if (fret < 0 and midi != -1) or (fret >= 0 and not 0 <= midi <= 127):
                add(Problem("template_pitch", detail=f"{k}: {ct.name or '?'}"))
                break

    # A phrase with notes and nothing to climb to: the September crash.
    if len(model.arrangements) > 1:
        with_notes = {n.phrase_iteration_id for lv in model.arrangements for n in lv.notes}
        for i in sorted(with_notes):
            if (
                0 <= i < len(pis) and 0 <= pis[i].phrase_id < len(phrases)
                and phrases[pis[i].phrase_id].max_difficulty < 1
            ):
                add(Problem("phrase_without_levels", time=pis[i].start_time))

    bounds = [pi.start_time for pi in pis]
    for lv in model.arrangements:
        out.extend(_check_level(lv, model, bounds))
    return out


def _check_level(lv: SngArrangementLevel, model: SngModel, bounds: list[float]) -> list[Problem]:
    out: list[Problem] = []
    d = lv.difficulty
    pis, phrases = model.phrase_iterations, model.phrases

    def add(code: str, time: float | None = None, detail: str = "") -> None:
        out.append(Problem(code, level=d, time=time, detail=detail))

    anchors = lv.anchors
    starts = [a.start_time for a in anchors]
    for a in anchors:
        if any(a.start_time + _EPS < b < a.end_time - _EPS for b in bounds):
            add("anchor_crosses_phrase", a.start_time)
        if not 0 <= a.phrase_iteration_id < len(pis):
            add("anchor_phrase_out_of_range", a.start_time)

    for i, n in enumerate(lv.notes):
        t = n.time
        if i and t < lv.notes[i - 1].time - _EPS:
            add("notes_out_of_order", t)
        if not 0 <= n.phrase_id < len(phrases):
            add("note_phrase_out_of_range", t, str(n.phrase_id))
        if not 0 <= n.phrase_iteration_id < len(pis):
            add("note_phrase_out_of_range", t, str(n.phrase_iteration_id))
        else:
            pi = pis[n.phrase_iteration_id]
            if not (pi.start_time - _EPS <= t < pi.end_time + _EPS) or pi.phrase_id != n.phrase_id:
                add("note_outside_its_phrase", t)
        if n.chord_id >= len(model.chord_templates):
            add("note_template_out_of_range", t, str(n.chord_id))
        if n.chord_notes_id >= len(model.chord_notes):
            add("note_chord_notes_out_of_range", t, str(n.chord_notes_id))
        elif (
            n.chord_notes_id < 0 and 0 <= n.chord_id < len(model.chord_templates)
            and 0 in model.chord_templates[n.chord_id].frets
        ):
            # DLC Builder always carries an open string's OPEN bit in the chord's
            # notes; without them the game paints the chord solid.
            add("open_chord_without_chord_notes", t, model.chord_templates[n.chord_id].name)
        if (n.tap, n.slap, n.pluck) != (-1, -1, -1):
            add("note_unused_byte", t)
        if not anchors:
            add("note_without_anchor", t)
        else:
            a = anchors[max(0, bisect.bisect_right(starts, t) - 1)]
            if not (a.start_time - _EPS <= t < a.end_time + _EPS):
                add("note_without_anchor", t)
            elif (n.anchor_fret, n.anchor_width) != (a.fret, a.width):
                add("note_anchor_mismatch", t, f"{n.anchor_fret}/{a.fret}")

    slide_ends = []
    for n in lv.notes:
        sliding = n.slide_to >= 0 or (
            0 <= n.chord_notes_id < len(model.chord_notes)
            and any(s != 0xFF for s in model.chord_notes[n.chord_notes_id].slide_to)
        )
        if sliding:
            slide_ends.append(n.time + n.sustain)
    for ext in lv.anchor_extensions:
        if not any(abs(ext.beat_time - e) < 1e-3 for e in slide_ends):
            add("extension_without_note", ext.beat_time)

    for code, t in _check_shapes(lv.fingerprints1, lv.notes, model, arpeggio=False):
        add(code, t)
    for code, t in _check_shapes(lv.fingerprints2, lv.notes, model, arpeggio=True):
        add(code, t)

    out.extend(Problem(code, level=d, time=t) for code, t in _check_links(lv, model, bounds))
    return out


def _check_shapes(
    fps: list[SngFingerprint], notes: list[SngNote], model: SngModel, *, arpeggio: bool
) -> list[tuple[str, float]]:
    """Hand shapes (Fingerprints1) or arpeggio shapes (Fingerprints2), as DLC
    Builder converts them: in order, apart, each over notes of its own (chords
    of its own template for a hand shape, single notes for an arpeggio, whose
    template is marked Arpeggio), first/last note times as ``convertHandshape``,
    and every note pointing at the shape ``findFingerPrintId`` finds — for an
    arpeggio also carrying the Arpeggio mask exactly when inside one."""
    out: list[tuple[str, float]] = []
    p = "arpeggio" if arpeggio else "handshape"
    slot = 1 if arpeggio else 0
    for prev, nxt in zip(fps, fps[1:], strict=False):
        if nxt.start_time < prev.start_time or prev.end_time > nxt.start_time + 1e-6:
            out.append((f"{p}_overlap", nxt.start_time))
    templates = model.chord_templates
    for fp in fps:
        if not 0 <= fp.chord_id < len(templates) or (
                bool(templates[fp.chord_id].mask & CHORD_MASK_ARPEGGIO) != arpeggio):
            out.append((f"{p}_bad_chord", fp.start_time))
            continue
        inside = [n for n in notes if fp.start_time <= n.time < fp.end_time]
        if fp.end_time <= fp.start_time or not inside:
            out.append((f"{p}_empty", fp.start_time))
            continue
        if any((n.chord_id >= 0) if arpeggio else (n.chord_id != fp.chord_id) for n in inside):
            out.append((f"{p}_wrong_notes", fp.start_time))
        last = inside[-1]
        if abs(fp.first_note_time - inside[0].time) > _EPS or not (
            fp.last_note_time == -1 or (
                abs(fp.last_note_time - (last.time + last.sustain)) < _EPS
                and fp.last_note_time < fp.end_time)):
            out.append((f"{p}_times", fp.start_time))
    for n in notes:
        expected = _find_fingerprint(n.time, fps)
        if n.fingerprint_id[slot] != expected:
            out.append((f"note_{p}_mismatch", n.time))
        elif arpeggio:
            if bool(n.mask & NOTE_MASK_ARPEGGIO) != (expected >= 0):
                out.append(("note_arpeggio_mask", n.time))
        elif n.chord_id >= 0 and expected < 0:
            out.append(("chord_outside_handshape", n.time))
        elif n.chord_id < 0 and expected >= 0:
            out.append(("single_note_in_handshape", n.time))
    return out


def _parent_strings(n: SngNote, model: SngModel) -> set[int]:
    """The strings a note hands a link on from: a single note's own string,
    a chord's strings whose ChordNotes mark Parent."""
    if not n.mask & NOTE_MASK_PARENT:
        return set()
    if n.chord_id < 0:
        return {n.string}
    if not 0 <= n.chord_notes_id < len(model.chord_notes):
        return set()
    masks = model.chord_notes[n.chord_notes_id].note_mask
    return {s for s in range(6) if masks[s] & NOTE_MASK_PARENT}


def _check_links(
    lv: SngArrangementLevel, model: SngModel, bounds: list[float]
) -> list[tuple[str, float]]:
    """Linked notes, as XmlToSngNote writes them and InstrumentalChecker allows
    them: a Child points back (ParentPrevNote) at an earlier Parent on its
    string whose end it starts at; every Parent hands on to a Child at this
    level; nothing else carries a ParentPrevNote; no phrase starts on a Child."""
    out: list[tuple[str, float]] = []
    notes = lv.notes
    taken: set[tuple[int, int]] = set()
    for i, n in enumerate(notes):
        if not n.mask & NOTE_MASK_CHILD:
            if n.parent_prev_note != -1:
                out.append(("link_stray_parent_index", n.time))
            continue
        p = n.parent_prev_note
        if n.chord_id >= 0 or not 0 <= p < i or n.string not in _parent_strings(notes[p], model):
            out.append(("link_child_without_parent", n.time))
            continue
        parent = notes[p]
        if parent.chord_id < 0 and abs(parent.time + parent.sustain - n.time) > 0.002 + _EPS:
            out.append(("link_gap", n.time))
        if any(abs(b - n.time) < _EPS for b in bounds):
            out.append(("phrase_on_link", n.time))
        taken.add((p, n.string))
    for i, n in enumerate(notes):
        if any((i, s) not in taken for s in _parent_strings(n, model)):
            out.append(("link_parent_without_child", n.time))
    return out


_TOOLKIT_LINE = re.compile(r"^Toolkit version:\s*\d+(\.\d+)+")


def verify_psarc(
    path: Path, *, read: Callable[[Path], dict[str, bytes]] | None = None
) -> PsarcReport:
    """Open the archive and check every chart in it, plus the few container
    rules that silently keep a song out of the game list."""
    from rockforge.infrastructure.packaging.psarc import container, crypto
    from rockforge.infrastructure.packaging.psarc.sng import read_sng

    report = PsarcReport(path=str(path))

    def wanted(name: str) -> bool:
        return name.endswith((".sng", ".json", ".appid", ".version")) or name == "appid.appid"

    try:
        entries = (read or (lambda p: container.read_entries(p, wanted)))(path)
    except Exception as exc:  # noqa: BLE001 — anything unreadable is the finding
        report.problems.append(Problem("psarc_unreadable", detail=str(exc)))
        return report

    appid = entries.get("appid.appid", b"").decode("utf-8", "replace").strip()
    if not appid.isdigit():
        report.problems.append(Problem("no_appid", detail=appid))
    toolkit = entries.get("toolkit.version", b"").decode("utf-8", "replace")
    if not _TOOLKIT_LINE.match(toolkit):
        report.problems.append(Problem("bad_toolkit_version"))

    sngs = {n: data for n, data in entries.items() if n.endswith(".sng")}
    bass_assets: set[str] = set()
    for name, raw in entries.items():
        if not (name.startswith("manifests/") and name.endswith(".json")):
            continue
        try:
            doc = json.loads(raw)
            attrs = next(iter(doc["Entries"].values()))["Attributes"]
            asset = str(attrs["SongAsset"]).rsplit(":", 1)[-1]
            if (attrs.get("ArrangementProperties") or {}).get("pathBass") == 1:
                bass_assets.add(asset)
        except (ValueError, KeyError, StopIteration, TypeError, AttributeError):
            report.problems.append(Problem("bad_manifest", arrangement=Path(name).stem))
            continue
        if f"songs/bin/generic/{asset}.sng" not in sngs:
            report.problems.append(Problem("manifest_without_sng", arrangement=asset))

    for name in sorted(sngs):
        asset = Path(name).stem
        report.charts.append(asset)
        try:
            model = read_sng(crypto.unpack_sng(sngs[name]))
        except Exception as exc:  # noqa: BLE001
            report.problems.append(Problem("sng_unreadable", detail=str(exc), arrangement=asset))
            continue
        report.problems.extend(
            Problem(p.code, p.level, p.time, p.detail, asset)
            for p in check_sng(model, bass=asset in bass_assets)
        )
    return report


def describe(code: str) -> str:
    """What a rule means, in the user's language."""
    texts: dict[str, tuple[str, str]] = {
        "psarc_unreadable": ("o PSARC não se consegue abrir", "the PSARC cannot be opened"),
        "no_appid": ("falta o appid.appid (a música não aparece na lista)",
                     "appid.appid is missing (the song will not be listed)"),
        "bad_toolkit_version": (
            "o toolkit.version não tem uma versão numérica (o patch de CDLC ignora o ficheiro)",
            "toolkit.version has no numeric version (the CDLC patch skips the file)"),
        "bad_manifest": ("um manifesto não se lê", "a manifest cannot be read"),
        "manifest_without_sng": ("o manifesto aponta para um SNG que não está no PSARC",
                                 "the manifest points at an SNG that is not in the PSARC"),
        "sng_unreadable": ("o SNG não se lê", "the SNG cannot be read"),
        "vocal_note": ("sílaba da letra com uma nota que não é 254 (a letra não aparece)",
                       "a lyric syllable whose note is not 254 (the lyrics will not show)"),
        "phrase_out_of_range": ("uma iteração aponta para uma frase que não existe",
                                "an iteration points at a phrase that does not exist"),
        "iterations_out_of_order": ("frases fora de ordem", "phrases out of order"),
        "section_out_of_order": ("secções fora de ordem", "sections out of order"),
        "section_bad_range": ("secção com um intervalo de frases impossível",
                              "a section with an impossible phrase range"),
        "tone_slot": ("troca para um tom fora de A–D", "a tone switch outside A–D"),
        "bass_string": ("nota de baixo numa 5.ª ou 6.ª corda (o baixo do jogo tem 4)",
                        "a bass note on a 5th or 6th string (the game's bass has 4)"),
        "template_pitch": (
            "acorde com uma corda não usada com nota (deve ser -1) ou uma nota impossível",
            "a chord whose unused string has a pitch (should be -1), or an impossible pitch"),
        "phrase_without_levels": ("frase com notas sem níveis para subir (teto 0)",
                                  "a phrase with notes and no level to climb (ceiling 0)"),
        "anchor_crosses_phrase": ("âncora atravessa o início de uma frase",
                                  "an anchor crosses the start of a phrase"),
        "anchor_phrase_out_of_range": ("âncora aponta para uma frase que não existe",
                                       "an anchor points at a phrase that does not exist"),
        "notes_out_of_order": ("notas fora de ordem", "notes out of order"),
        "note_phrase_out_of_range": ("nota aponta para uma frase que não existe",
                                     "a note points at a phrase that does not exist"),
        "note_outside_its_phrase": ("nota fora da frase a que diz pertencer",
                                    "a note outside the phrase it claims"),
        "note_template_out_of_range": ("nota aponta para um acorde que não existe",
                                       "a note points at a chord that does not exist"),
        "note_chord_notes_out_of_range": (
            "acorde aponta para notas de acorde que não existem",
            "a chord points at chord notes that do not exist"),
        "open_chord_without_chord_notes": (
            "acorde com cordas soltas sem notas de acorde (o jogo pinta-o de cima a baixo)",
            "a chord with open strings and no chord notes (the game paints it top to bottom)"),
        "note_unused_byte": ("nota com tap/slap/pluck diferente de -1",
                             "a note with tap/slap/pluck other than -1"),
        "note_without_anchor": ("nota sem âncora", "a note with no anchor"),
        "note_anchor_mismatch": ("nota com a âncora errada para o seu nível",
                                 "a note with the wrong anchor for its level"),
        "extension_without_note": ("extensão de âncora sem o slide que a criou",
                                   "an anchor extension without the slide it belongs to"),
        "handshape_overlap": ("hand shapes sobrepostas", "overlapping hand shapes"),
        "handshape_bad_chord": ("hand shape aponta para um acorde que não existe",
                                "a hand shape points at a chord that does not exist"),
        "handshape_empty": ("hand shape sem notas", "a hand shape over no note"),
        "handshape_wrong_notes": ("hand shape sobre notas de outro acorde",
                                  "a hand shape over another chord's notes"),
        "handshape_times": ("hand shape com tempos de 1.ª/última nota errados",
                            "a hand shape with wrong first/last note times"),
        "note_handshape_mismatch": ("nota aponta para a hand shape errada",
                                    "a note points at the wrong hand shape"),
        "chord_outside_handshape": ("acorde fora de qualquer hand shape",
                                    "a chord outside every hand shape"),
        "single_note_in_handshape": ("nota solta dentro de uma hand shape",
                                     "a single note inside a hand shape"),
        "arpeggio_overlap": ("arpejos sobrepostos", "overlapping arpeggios"),
        "arpeggio_bad_chord": ("arpejo aponta para uma forma que não é de arpejo",
                               "an arpeggio points at a shape that is not an arpeggio's"),
        "arpeggio_empty": ("arpejo sem notas", "an arpeggio over no note"),
        "arpeggio_wrong_notes": ("arpejo sobre um acorde", "an arpeggio over a chord"),
        "arpeggio_times": ("arpejo com tempos de 1.ª/última nota errados",
                           "an arpeggio with wrong first/last note times"),
        "note_arpeggio_mismatch": ("nota aponta para o arpejo errado",
                                   "a note points at the wrong arpeggio"),
        "note_arpeggio_mask": ("nota de arpejo sem a marca de arpejo (ou ao contrário)",
                               "an arpeggio note without the arpeggio mark (or the other way)"),
        "link_child_without_parent": (
            "nota ligada sem a nota de onde vem (na mesma corda, antes dela)",
            "a linked note without the note it comes from (on its string, before it)"),
        "link_gap": ("nota ligada que não começa onde a anterior acaba",
                     "a linked note that does not start where the previous one ends"),
        "link_parent_without_child": ("nota com ligação sem a nota seguinte neste nível",
                                      "a note linked on with no next note at this level"),
        "link_stray_parent_index": ("nota não ligada que aponta para uma nota anterior",
                                    "an unlinked note pointing at an earlier note"),
        "phrase_on_link": ("frase que começa numa nota ligada",
                           "a phrase that starts on a linked note"),
    }
    pt, en = texts.get(code, (code, code))
    return tr(pt, en)
