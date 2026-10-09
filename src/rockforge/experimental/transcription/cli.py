"""``python -m rockforge.experimental.transcription`` — list / run / score."""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from rockforge.experimental.transcription.midi import MidiNote, guitar_notes, read_midi, write_midi
from rockforge.experimental.transcription.runners import (
    RUNNERS,
    RunnerError,
    cuda_available,
    run,
    run_command,
)
from rockforge.experimental.transcription.score import (
    Note,
    best_shift,
    match_score,
    pitch_class,
    tab_position,
)
from rockforge.experimental.transcription.truth import Song, load_songs
from rockforge.i18n import tr

if TYPE_CHECKING:
    from rockforge.config import Settings

# A transcriber hears the recording itself, so only its latency is searched;
# a tab made elsewhere (Songsterr AI, Klangio) can start anywhere.
MODEL_MAX_SHIFT_S = 0.25
FILE_MAX_SHIFT_S = 60.0


@dataclass
class Row:
    song: str
    job_id: str
    source: str  # stem / mix / file
    model: str
    synced: bool
    shift: float
    pred: int
    ref: int
    precision: float
    recall: float
    f1: float
    f1_pitch_class: float
    tab_f1: float | None
    chart_recall: dict[str, float]


def evaluate(song: Song, notes: list[Note], *, source: str, model: str,
             max_shift: float) -> Row:
    ref = song.guitar_part()
    shift = best_shift(ref, notes, max_shift=max_shift)
    s = match_score(ref, notes, shift=shift)
    has_tab = any(n.string is not None for n in notes)
    return Row(
        song.label, song.job_id, source, model,
        all(c.synced for c in song.charts) and bool(song.charts),
        shift, s.predicted, s.reference, s.precision, s.recall, s.f1,
        match_score(ref, notes, shift=shift, key=pitch_class).f1,
        match_score(ref, notes, shift=shift, key=tab_position).f1 if has_tab else None,
        {c.kind.value: match_score(c.notes, notes, shift=shift).recall for c in song.charts},
    )


def midi_notes(path: Path) -> list[Note]:
    return [Note(n.start, n.pitch) for n in guitar_notes(read_midi(path))]


def gp_notes(path: Path) -> list[Note]:
    """Every guitar track of a Guitar Pro file (an exported AI tab), with its
    strings and frets, bar 1 at 0 s."""
    from rockforge.infrastructure.gpimport.parser import inspect_gp, parse_gp_track

    notes: list[Note] = []
    for track in inspect_gp(path).tracks:
        if track.is_percussion or track.string_count < 6:
            continue
        parsed = parse_gp_track(path, track.index)
        notes += [Note(n.time, parsed.tuning.midi[n.string] + n.fret, n.string, n.fret)
                  for n in parsed.notes]
    return sorted(notes, key=lambda n: (n.time, n.pitch))


def _pct(v: float | None) -> str:
    return "—" if v is None else f"{100 * v:5.1f}%"


def print_rows(rows: list[Row]) -> None:
    head = tr("música | fonte | modelo | F1 | precisão | recall | F1 sem oitava | F1 tab | "
              "recall por pista | desvio",
              "song | source | model | F1 | precision | recall | F1 octave-free | tab F1 | "
              "recall per chart | shift")
    print(head)
    for r in rows:
        charts = " ".join(f"{k}:{_pct(v).strip()}" for k, v in r.chart_recall.items())
        mark = "" if r.synced else " (*)"
        print(f"{r.song}{mark} | {r.source} | {r.model} | {_pct(r.f1)} | {_pct(r.precision)} | "
              f"{_pct(r.recall)} | {_pct(r.f1_pitch_class)} | {_pct(r.tab_f1)} | {charts} | "
              f"{r.shift:+.2f}s")
    if any(not r.synced for r in rows):
        print(tr("(*) nem todas as pistas desta música estão marcadas como sincronizadas — "
                 "a resposta certa pode estar desfasada",
                 "(*) not every chart of this song is marked as in sync — the right answer "
                 "may be off"))


def write_report(rows: list[Row], out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    with (out / "results.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["song", "job_id", "source", "model", "synced", "shift_s", "pred", "ref",
                    "precision", "recall", "f1", "f1_pitch_class", "tab_f1", "chart_recall"])
        for r in rows:
            w.writerow([r.song, r.job_id, r.source, r.model, r.synced, f"{r.shift:.3f}", r.pred,
                        r.ref, f"{r.precision:.4f}", f"{r.recall:.4f}", f"{r.f1:.4f}",
                        f"{r.f1_pitch_class:.4f}", "" if r.tab_f1 is None else f"{r.tab_f1:.4f}",
                        ";".join(f"{k}={v:.4f}" for k, v in r.chart_recall.items())])
    by_model: dict[tuple[str, str], list[Row]] = {}
    for r in rows:
        by_model.setdefault((r.source, r.model), []).append(r)
    lines = [tr("# Banco de ensaio da transcrição", "# Transcription bench"), "",
             tr("Média por fonte e modelo (F1 de inícios de nota, ±50 ms, altura exata):",
                "Mean per source and model (onset note F1, ±50 ms, exact pitch):"), ""]
    lines += ["| source | model | songs | F1 | precision | recall | F1 octave-free |",
              "|---|---|---|---|---|---|---|"]
    for (src, model), group in sorted(by_model.items()):
        n = len(group)

        def mean(attr: str, g: list[Row] = group, k: int = n) -> float:
            return float(sum(getattr(x, attr) for x in g) / k)

        lines.append(f"| {src} | {model} | {n} | {_pct(mean('f1'))} | {_pct(mean('precision'))} "
                     f"| {_pct(mean('recall'))} | {_pct(mean('f1_pitch_class'))} |")
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _settings() -> Settings:
    from rockforge.config import settings

    return settings


def _python() -> str:
    from rockforge.infrastructure.ml_python import resolve

    return resolve() or sys.executable


def cmd_list(args: argparse.Namespace) -> int:
    songs = load_songs(_settings().database_url, args.projects or ())
    if not songs:
        print(tr("Nenhum projeto Guitar Pro construído encontrado.",
                 "No built Guitar Pro project found."))
        return 1
    for s in songs:
        charts = ", ".join(f"{c.kind.value}{' ✓' if c.synced else ''} ({len(c.notes)})"
                           for c in s.charts)
        audio = s.audio.name if s.audio else tr("SEM GRAVAÇÃO", "NO RECORDING")
        print(f"{s.job_id}  {s.label}  [{charts}]  {audio}")
    print(tr("✓ = pista marcada como sincronizada (resposta certa fiável)",
             "✓ = chart marked as in sync (trustworthy right answer)"))
    return 0


def _stem(song: Song, out: Path, device: str) -> Path:
    from rockforge.infrastructure.separation.demucs_adapter import DemucsSeparator

    assert song.audio is not None
    return DemucsSeparator(device=device).separate_guitar(song.audio, out / "demucs")


def cmd_run(args: argparse.Namespace) -> int:
    settings = _settings()
    out_root = Path(args.out or settings.work_dir / "transcription_bench")
    models = [m.strip() for m in args.models.split(",") if m.strip()]
    unknown = [m for m in models if m not in RUNNERS]
    if unknown:
        print(tr("Modelos desconhecidos: {m}. Disponíveis: {all}",
                 "Unknown models: {m}. Available: {all}").format(
            m=", ".join(unknown), all=", ".join(RUNNERS)))
        return 2
    if args.cmd:
        models.append("cmd")
    sources = [s.strip() for s in args.input.split(",") if s.strip()]
    python = _python()
    device = args.device if args.device != "auto" else (
        "cuda" if cuda_available(python) else "cpu")
    songs = [s for s in load_songs(settings.database_url, args.projects or ())
             if s.audio and s.charts and (not args.only_synced or any(c.synced for c in s.charts))]
    if not songs:
        print(tr("Nenhum projeto com gravação e pistas para avaliar.",
                 "No project with a recording and charts to score."))
        return 1
    rows: list[Row] = []
    for song in songs:
        song_dir = out_root / song.job_id
        song_dir.mkdir(parents=True, exist_ok=True)
        write_midi([(c.kind.value, [MidiNote(n.time, n.time + 0.25, n.pitch) for n in c.notes])
                    for c in song.charts], song_dir / "truth.mid")
        print(f"\n== {song.label}")
        for source in sources:
            try:
                audio = song.audio if source == "mix" else _stem(song, song_dir, device)
            except Exception as exc:  # noqa: BLE001 — one song's failure is a line, not the end
                print(tr("  estema da guitarra falhou: {e}", "  guitar stem failed: {e}")
                      .format(e=exc))
                continue
            assert audio is not None
            for model in models:
                mid = song_dir / source / f"{model}.mid"
                if args.force or not mid.is_file():
                    print(tr("  {model} em {source}…", "  {model} on {source}…")
                          .format(model=model, source=source), flush=True)
                    try:
                        if model == "cmd":
                            run_command(args.cmd, audio, mid)
                        else:
                            run(model, audio, mid, python, device)
                    except RunnerError as exc:
                        print(tr("  {model} falhou:\n{e}", "  {model} failed:\n{e}")
                              .format(model=model, e=exc))
                        continue
                rows.append(evaluate(song, midi_notes(mid), source=source, model=model,
                                     max_shift=MODEL_MAX_SHIFT_S))
    print()
    print_rows(rows)
    write_report(rows, out_root)
    print(tr("\nRelatório: {path}", "\nReport: {path}").format(path=out_root / "report.md"))
    return 0


def cmd_score(args: argparse.Namespace) -> int:
    songs = load_songs(_settings().database_url, [args.project])
    if not songs:
        print(tr("Projeto não encontrado (ou não construído): {id}",
                 "Project not found (or not built): {id}").format(id=args.project))
        return 1
    path = Path(args.file)
    notes = gp_notes(path) if path.suffix.lower().startswith(".gp") else midi_notes(path)
    print_rows([evaluate(songs[0], notes, source="file", model=path.name,
                         max_shift=args.max_shift)])
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m rockforge.experimental.transcription",
        description=tr("Mede transcritores de guitarra nas tuas músicas (experimental).",
                       "Measures guitar transcribers on your own songs (experimental)."))
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("list", help=tr("projetos que servem de resposta certa",
                                        "projects that can be the right answer"))
    p.add_argument("--projects", nargs="*")
    p.set_defaults(func=cmd_list)
    p = sub.add_parser("run", help=tr("corre os transcritores e mede",
                                       "run the transcribers and score them"))
    p.add_argument("--models", default="gaps,yourmt3",
                   help=", ".join(f"{r.name}: {r.about}" for r in RUNNERS.values()))
    p.add_argument("--input", default="stem", help="stem,mix")
    p.add_argument("--projects", nargs="*")
    p.add_argument("--only-synced", action="store_true")
    p.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    p.add_argument("--out")
    p.add_argument("--force", action="store_true")
    p.add_argument("--cmd", help='"my-tool {audio} {midi}"')
    p.set_defaults(func=cmd_run)
    p = sub.add_parser("score", help=tr("mede um MIDI/GP feito por outra ferramenta",
                                         "score a MIDI/GP made by another tool"))
    p.add_argument("file")
    p.add_argument("--project", required=True)
    p.add_argument("--max-shift", type=float, default=FILE_MAX_SHIFT_S)
    p.set_defaults(func=cmd_score)
    args = parser.parse_args(argv)
    return int(args.func(args))
