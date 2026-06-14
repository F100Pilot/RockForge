# CLAUDE.md

Guidance for working in this repository. Read this before making changes.

## What RockForge is

A pipeline that turns an audio recording (or a Guitar Pro file) into a Rocksmith
2014 CDLC arrangement bundle, importable into DLC Builder. It is deliberately
**honest about limits**: every ML stage carries an explicit confidence label and
nothing is silently defaulted. Read `docs/RELATORIO-TECNICO.md` and
`docs/research/` for the grounding (with sources) behind every technical claim.

## Architecture (Clean Architecture — respect the layering)

```
domain/         pure music model (Arrangement, TabNote, Tuning, TempoMap) — no I/O, no frameworks
application/    ports.py (Protocols) + pipeline.py / gp_pipeline.py (use cases) — orchestration only
infrastructure/ adapters implementing the ports (Demucs, Basic Pitch, librosa, ffmpeg, Wwise, RS XML, DB)
interfaces/     api/ (FastAPI) and worker/ (Celery) — the boundary; wiring lives here
```

Rules:
- `domain/` and `application/` must not import frameworks or `infrastructure/`.
  Each ML stage is a swappable `Protocol` in `application/ports.py`.
- A COMBINED arrangement is always produced as the trustworthy fallback; the
  Lead/Rhythm split is EXPERIMENTAL (no published method exists) and additive.
- Heavy imports (torch, demucs, basic-pitch, whisperx) are deferred into the
  Celery worker's `_build_use_case()` — never import them at module top level in
  the API path, or the web process pays the cost and may fail without the ML extra.

## The two generation paths

1. **Audio → ML** (`pipeline.py`): ingest → normalize → separate (Demucs) →
   transcribe (Basic Pitch) → beat track + tuning (librosa) → fret mapping →
   optional lyrics (WhisperX) → package. Timing is automatic: every timestamp is
   seconds from the start of the normalized audio.
2. **Guitar Pro** (`gp_pipeline.py`): notes/frets/techniques/sections come exact
   from the GP3/GP4/GP5 file; audio sync is a manual offset. High fidelity,
   preferred when a GP file exists. GPX/GP6/GP7 are NOT supported (PyGuitarPro).

### Tempo scaling (`tempo_scale`)

`GpJobSpec.tempo_scale` (default 1.0) multiplies the whole musical timeline at
parse time, around the song's start and before `offset_s` — it corrects a
constant GP-vs-recording tempo mismatch (the linearly-growing part of sync
drift) in one move. `>1` stretches (slower); `<1` compresses (faster). The
effective `average_bpm` is scaled inversely. The tab viewer exposes it as an
editable BPM/% control with live preview (notes slide over the fixed waveform).
Use it *before* the per-note `sync_anchor_stages` below, which then only need to
clean up residual non-linear drift.

### Automatic sync proposal (`/jobs/{id}/auto-sync`)

`POST /jobs/{id}/auto-sync` (GP jobs only) detects the recording's tempo and
first onset with librosa (`detect_tempo_and_onset`, ml extra) and combines them
with the GP file's authored tempo via the pure `suggest_sync(gp_bpm,
detected_bpm, first_onset_s)` (in `gp_pipeline.py`) into a proposed
`(tempo_scale, offset_s)`. Beat trackers report octave-off tempos, so
`suggest_sync` picks the octave of `detected_bpm` whose `tempo_scale` lands
closest to 1.0 (same song → ratio near unity). The endpoint **returns the
proposal only** — the tab viewer loads it into the live preview so the user
confirms over the waveform and commits via the normal rebuild; nothing is
silently applied (honesty principle). Detection is a module-level function so
tests monkeypatch it without librosa (`test_auto_sync_proposes_alignment`).

### Manual drift correction (`sync_anchor_stages`)

A single `offset_s` only fixes a constant lead-in; if the GP file's tempo map
doesn't exactly match the recording, drift grows over the song. The tab viewer
lets the user drag a note (or a rubber-band-selected excerpt) to where it
should play; each drag/excerpt becomes a `(chart_time, corrected_time)` anchor,
and `_build_time_warp` remaps notes, beats, sections and lyrics
(`_warp_parsed_track`):
- **One anchor** (single-note drag) is a uniform shift applied to the whole
  timeline — for "the whole song's lead-in is off by X".
- **Two-or-more anchors** (excerpt drag) rigidly shift/stretch only the
  excerpt between the first and last anchor; everything before/after is left
  untouched (identity) so unrelated parts of the song don't move.

`GpJobSpec.sync_anchor_stages: list[list[tuple[float, float]]]` is a list of
correction *rounds*, applied in order. Each round's anchors are expressed in
the timeline produced by the *previous* round (i.e. exactly what the tab
viewer shows when the user draws them). `/jobs/{id}/rebuild` appends a new
round to `params["sync_anchor_stages"]` rather than overwriting it, so
reopening a completed job, loading its arrangement (already reflecting prior
rounds), and adding more corrections composes correctly instead of discarding
earlier work. Do not collapse this back to a single `sync_anchors` list —
anchors from different rounds live in different (already-warped) coordinate
systems and cannot simply be concatenated.

### Per-arrangement sync (`arrangement_sync`)

`tempo_scale` and `sync_anchor_stages` are **per-arrangement**: each chart
(Lead/Rhythm/Combined) is parsed and drift-corrected independently, so dragging
a Lead note never moves the Rhythm chart. `GpJobSpec.arrangement_sync: dict[str,
ArrangementSync]` is keyed by `ArrangementKind.value`; an arrangement absent
from it falls back to the job-level `tempo_scale`/`sync_anchor_stages` defaults
(`GpJobSpec.sync_for`). `offset_s` is deliberately NOT per-arrangement — all
arrangements share one `.wem`, so the recording's start is common to all; a
per-arrangement uniform shift is just a single-anchor round. `/jobs/{id}/rebuild`
takes an optional `arrangement` to scope `tempo_scale`/`sync_anchors` to one
chart (seeding its entry from the job-level defaults on first edit). The tab
viewer keeps a separate pending-anchor set per tab and exposes one
"Aplicar e reconstruir" that commits the current tab's tempo+anchors plus the
shared offset/tuning in a single rebuild.

The tab viewer's x-axis is **recording time** (0s at the left edge): notes are
drawn via `timeToX` (which subtracts the lead-in `viewOrigin` from the
bundle-time positions), so the playhead starts at 0 instead of at the first
note. Anchor math stays in bundle time so corrections round-trip through a
rebuild unchanged.

### Lyrics formats (`infrastructure/rsxml/vocals.py`)

`parse_lyrics` auto-detects **LRC** (`[mm:ss.xx]` lines) vs **UltraStar/USDX
TXT** (`#BPM:`/`#GAP:` header + `: start length pitch text` / `-` line-break
note lines; beat→seconds via `15 / BPM`). Rocksmith's vocals XML is
per-syllable: `expand_to_words` splits line-level events (LRC, GP-embedded
lyrics) into one `<vocal>` per word and appends `+` to the last word of each
line — that trailing `+` is what makes the in-game lyric display break to a
new line. UltraStar input is already per-syllable and is NOT re-expanded.

## Commands

```bash
pip install -e ".[dev]"          # core + tests, no ML
pip install -e ".[dev,ml]"       # adds Demucs/Basic Pitch/librosa
pip install -e ".[lyrics]"       # adds WhisperX (optional automatic lyrics)
pytest                           # full suite (ML stages are faked in tests)
ruff check src tests             # lint — must pass
mypy                             # strict on domain/application/infra; relaxed at boundaries
```

CI runs ruff + mypy + pytest. All three must be green before committing. mypy is
pinned (`mypy~=1.19.0`) so local matches CI — do not bump it casually.

## Hard constraints (these have bitten us — keep them)

- **Python 3.11 only** (`requires-python = ">=3.11,<3.12"`). `basic-pitch` needs
  `tensorflow<2.15.1`, whose newest wheels target 3.11. On Windows use
  `py -3.11 -m pip ...`; the user does NOT want virtualenvs.
- **The .wem must have a seek table.** Converting through a blank Wwise project
  produces a seek-table-less Vorbis .wem; Rocksmith loads the song but plays
  silence, freezes the note highway and exits seconds in. `wwise.py` extracts the
  vendored DLC Builder template project (`wwise_templates/*.zip`, MIT) per Wwise
  version, runs `generate-soundbank`, and patches the header word at offset 40 to
  3. Do not "simplify" this back to convert-external-source.
- **Song2014 XML completeness for DLC Builder.** `ArrangementProperties.ReadXml`
  (Rocksmith2014.XML) dereferences all 32 arrangementProperties attributes
  without null checks — every one must be emitted or import throws an NRE. There
  is a test (`DLC_BUILDER_REQUIRED_ARRPROP_ATTRS`) guarding this.
- **Phrase structure ends the song.** Rocksmith ends playback at the last
  `phraseIteration`. The writer emits COUNT/default/END phrases with END placed
  after the last note, plus a closing `noguitar` section. Guarded by
  `test_phrase_structure_marks_song_end`. Don't remove the END phrase.
- **YouTube ingestion is gated by `ROCKFORGE_ENABLE_YOUTUBE`** (currently
  defaulting on at the operator's request) — downloading audio violates the
  YouTube ToS, so the gate stays so it can be turned off. PSARC/.wem packing
  needs a local Wwise (Audiokinetic EULA forbids redistribution); RockForge only
  *invokes* an installed copy.

## Testing approach

ML/Wwise/external tools cannot run in CI. Tests inject fakes: a Python-based fake
WwiseConsole (`test_wwise.py`), passthrough stages (`test_pipeline.py`), stubbed
Celery enqueue + per-test SQLite (`test_api.py`). When you add an adapter, add a
fake-driven test at the same boundary rather than mocking deep internals.

## Running locally (Windows, native, no Docker)

`start.bat` launches Redis (Memurai) + Celery worker (background) + the API
(foreground) from a single window; it auto-selects `py -3.11`. Requires ffmpeg
(`winget install ffmpeg`) and a running Redis. See README for the full guide.

## Conventions

- Keep the honesty: surface warnings via the pipeline's `warnings` list, never
  invent metadata, label confidence explicitly.
- Match surrounding code style. The codebase comments only to state non-obvious
  constraints (often citing the research doc section), not to narrate.
