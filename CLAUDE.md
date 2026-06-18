# CLAUDE.md

Guidance for working in this repository. Read this before making changes.

## What RockForge is

A pipeline that turns an audio recording (or a Guitar Pro file) into a Rocksmith
2014 CDLC arrangement bundle, importable into DLC Builder. It is deliberately
**honest about limits**: every ML stage carries an explicit confidence label and
nothing is silently defaulted. Read `docs/RELATORIO-TECNICO.md` and
`docs/research/` for the grounding (with sources) behind every technical claim.

See `TODO.md` for proposed (not yet implemented) future features.

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

`POST /jobs/{id}/detect-tempo` (`{from_s}`) backs the tab viewer's per-point
"Novo beat (detetar)" mode: it measures the recording's tempo from a clicked
instant (`detect_tempo_from`) and returns `suggested_factor =
suggest_tempo_scale(gp_bpm, detected_bpm)`. The UI turns that into two anchors —
a fixed pivot at the click and the last note stretched by `factor` — so the
existing `_build_time_warp` linearly re-tempos only `[click, last]` and nothing
before the click moves. No new warp semantics; the per-point tools (drag, tap,
move-from-here, re-tempo) all compile down to ordinary `sync_anchors`.

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
shared offset/tuning in a single rebuild. When there are multiple arrangements,
a checkbox "Aplicar sync a todos" appears; when checked, `RebuildIn.apply_to_all`
is set and the `rebuild_job` endpoint propagates `tempo_scale` and
`sync_anchors` to every existing per-arrangement override AND the job-level
defaults, so all charts share the same correction in one rebuild instead of
requiring the user to adjust each arrangement separately.

The tab viewer's x-axis is **recording time** (0s at the left edge): notes are
drawn via `timeToX` (which subtracts the lead-in `viewOrigin` from the
bundle-time positions), so the playhead starts at 0 instead of at the first
note. Anchor math stays in bundle time so corrections round-trip through a
rebuild unchanged.

Playback in the tab viewer goes through the **Web Audio API**
(`AudioBufferSourceNode` over the buffer already decoded for the waveform),
driven by a custom transport (`audioPlay`/`audioPause`/`audioSeek`), NOT the
HTML `<audio>` element. The element seeks by estimating a byte offset from
time, which is accurate near the start but drifts further in for VBR /
seek-table-less sources — the "aligned from the start, off in the middle"
symptom. A buffer source seeks sample-accurately and its clock is
`audioCtx.currentTime`, so playback, the waveform and the notes share one exact
timeline. The `<audio>` element survives only as a decode-failure fallback
(`playBuffer === null`), where seeking is codec-imprecise again. Don't revert
playback to the `<audio>` element's `currentTime`/seek.

### Lyrics formats (`infrastructure/rsxml/vocals.py`)

`parse_lyrics` auto-detects **LRC** (`[mm:ss.xx]` lines) vs **UltraStar/USDX
TXT** (`#BPM:`/`#GAP:` header + `: start length pitch text` / `-` line-break
note lines; beat→seconds via `15 / BPM`). Rocksmith's vocals XML is
per-syllable: `expand_to_words` splits line-level events (LRC, GP-embedded
lyrics) into one `<vocal>` per word and appends `+` to the last word of each
line — that trailing `+` is what makes the in-game lyric display break to a
new line. UltraStar input is already per-syllable and is NOT re-expanded.

### Automatic lyric detection + in-app editor

`POST /jobs/{id}/detect-lyrics` runs `rockforge.detect_lyrics` (an async Celery
task, GP and audio-ML jobs both) — Demucs isolates the vocals stem and WhisperX
force-aligns it. Progress is tracked via `params["lyrics_status"]`
(`detecting`/`ready`/`empty`/`unavailable`), never `JobStatus`, so detection
never hides a completed bundle or disables `/arrangements`. Results land in
`params["lyrics_events"]` (JSON rows `{"time","length","lyric"}`), readable via
`GET /jobs/{id}/lyrics`.

**Speed.** This is the slow path on CPU; the heaviest stage is the Demucs
separation. Detection uses `DemucsSeparator.separate_vocals` — the lighter
4-source `htdemucs` with `--two-stems=vocals` — NOT `separate_guitar`'s 6-source
`htdemucs_6s` (which would compute drums/bass/other/guitar/piano just to throw
them away). htdemucs' vocal quality is also better than the 6s model's, so it is
faster *and* more accurate for transcription. The WhisperX model size
(`ROCKFORGE_WHISPER_MODEL`, default `small`) and the detection device
(`ROCKFORGE_WHISPERX_DEVICE`, falling back to `demucs_device` via
`settings.lyrics_device()`) are configurable — on CPU drop the model to
`base`/`tiny` to trade accuracy for speed.

**Device selection (`_resolve_device`).** `demucs_device` defaults to `"auto"`:
`celery_app._resolve_device` (deferred torch import, worker-only) returns
`"cuda"` when `torch.cuda.is_available()` and `"cpu"` otherwise; explicit
`"cpu"`/`"cuda"` pass through. Any import/CUDA failure degrades to CPU, so
`"auto"` is safe even without the ml/lyrics extras. Resolution happens *before*
the adapters are built (the WhisperX adapter keys `compute_type` off the
concrete device — `float16` on cuda, `int8` on cpu — so it must never see the
literal `"auto"`). The resolved device is written to the lyrics log
(`device: cuda (GPU)`), so the user can confirm the GPU is in use. With an
NVIDIA GPU this is the ~3-minute path online tools get — but note the default
`pip install torch` on Windows is CPU-only; the CUDA build is needed (e.g.
`pip install torch==2.4.1 torchaudio==2.4.1 --index-url
https://download.pytorch.org/whl/cu121`, respecting the `<2.5` pin).

The web UI's "Letras" panel lets the user edit words and per-word timings (and
add/remove rows) regardless of whether detection ran. `applyAll()` sends the
edited rows as `RebuildIn.lyrics_events`; `rebuild_job` stores them in
`params["lyrics_events"]` and clears `lyrics_status` so the next build picks
them up via `events_from_dicts`. These edited events take **top precedence**
over `lrc_text`/GP-embedded lyrics (GP pipeline) and over automatic WhisperX
transcription (audio pipeline) — see `GpJobSpec.lyrics_events` and
`GenerateCdlcUseCase.run(lyrics_events=...)`.

Coordinate space: events from `/lyrics` and the editor are in the **un-padded
recording clock**. For GP jobs, `gp_pipeline` shifts edited times by
`pad_start_s` at build time, same as `lrc_text`. For the audio-ML path, note
that (like the existing automatic-WhisperX path) `offset_s` trimming is not
subtracted from word times — a known limitation.

Detection needs both `[lyrics]` (WhisperX) and `[ml]` (Demucs) extras in the
worker, even for GP jobs whose own build stays ML-free.

### Album cover art

`POST /jobs/{id}/cover` (multipart `file`, jpg/png) stores the image as
`<work_dir>/<job_id>/cover<ext>` and records the filename in
`params["cover_art"]`; `GET /jobs/{id}/cover` serves it back for the web UI's
preview. Uploading does not trigger a rebuild — the next build/rebuild picks it
up via the worker's `params.get("cover_art")` lookup and passes it as
`Packager.package(..., cover_art=Path)`.

Both `DlcBuilderPackager` and `NativePsarcPacker` copy the image into the bundle
as `cover.<ext>` and record it in `rockforge_project.json["cover_art"]` (via the
shared `build_project_metadata()`), so it's available as the album art when
creating/updating the DLC Builder project (DLC Builder generates the in-game DDS
textures itself). Honesty note: this is NOT yet converted to an in-game DDS
texture/`albumArt` URN — the Song2014 XML `albumArt` field
(`infrastructure/rsxml/writer.py`) stays empty in both DLC Builder and native
PSARC output, same as building without a cover set.

### Automatic tone detection (`/jobs/{id}/detect-tones`)

`POST /jobs/{id}/detect-tones` (any job type: GP, audio, YouTube) runs Demucs
guitar separation (`htdemucs_6s`) on the recording and analyzes the guitar
stem's spectral characteristics (zero-crossing rate, spectral contrast,
centroid, rolloff) to classify the tone into one of three categories: `clean`,
`crunch`, or `high_gain`. The classification drives a preset suggestion: curated
Lead + Rhythm tones from the Rocksmith gear catalogue (real amp/cabinet/pedal
keys with knob values) are proposed and stored in `params["detected_tones"]`.

Progress is tracked via `params["tone_detection_status"]`
(`detecting`/`normalizing`/`separating`/`analyzing`/`ready`/`unavailable`),
never `JobStatus`. The web UI's "Detetar tom" button triggers detection and
polls `GET /jobs/{id}/detected-tones` for the result; "Aplicar tons sugeridos"
loads the presets into the tone editor so the user confirms/adjusts, then
"Aplicar e reconstruir" commits them.

Honesty note: spectral analysis does NOT identify the actual amp/pedal used in
the recording — it classifies the *character* of the guitar sound and suggests
a plausible Rocksmith gear match. Detection needs the `[ml]` extra (Demucs +
librosa).

### DLC Builder project file (`rockforge.rs2dlc`)

`rockforge_project.json` is RockForge's *own* descriptor — DLC Builder can't
open it, so without help the user must recreate a project and "Add Arrangement"
each XML by hand. `infrastructure/packaging/rs2dlc.py` additionally emits the
**real** DLC Builder project format (`rockforge.rs2dlc`) so the whole song
(every instrumental, the vocals, audio and cover) loads in one "Open project".
Both `DlcBuilderPackager` and `NativePsarcPacker` write it.

The format is the `DLCProject.Dto` from Rocksmith2014.NET, serialized the way
DLC Builder does (System.Text.Json + FSharp.SystemTextJson defaults): arrangements
are an adjacent-tag discriminated union
(`{"Case":"Instrumental"|"Vocals"|"Showlights","Fields":[{…}]}`), `null` members
are omitted, `SortableString` is `{"Value","SortValue"}`, `AudioFile` is
`{"Path","Volume"}`. `ArrangementName`/`RouteMask` per kind: Lead→0/1, Combo
(our COMBINED)→1/1, Rhythm→2/2 (from `Arrangement.fs`). `Tuning` is the six
semitone offsets (`Tuning.offsets_from_standard`), `TuningPitch` from
`cent_offset`. `ID`==`PersistentID` (one GUID), `MasterID` random positive int —
matching a real captured `.rs2dlc`.

RockForge now has a full tone-gear model (`domain/tone.py`, backed by the
vendored Rocksmith gear catalogue) — custom tones with real amp/cabinet/pedal
definitions are serialized into the `.rs2dlc`'s `Tones` array and flow through
to the PSARC. When no tones are defined, `Tones` stays empty and DLC Builder
flags a "tone missing" issue the user resolves with its tone library. `Volume`
uses a neutral default (DLC Builder's "Calculate Volumes" recomputes it) and the
audio preview is left empty (its "Create Preview Audio" generates it).

### SNG binary compilation (`infrastructure/packaging/psarc/sng.py`)

`NativePsarcPacker` compiles each `Arrangement` into a Rocksmith Sng2014 binary
payload via `sng.from_arrangement` + `sng.write_sng`. The binary layout
(section ordering, field sizes, struct formats) matches the real Sng2014 format
as ported from the Rocksmith2014.NET / DLC Builder source (MIT). `read_sng`
round-trips the payload for test verification.

Sections emitted (in order): BPMs, Phrases, ChordTemplates (with per-string MIDI
notes), ChordNotes, Vocals (+ symbol stubs if present), PhraseIterations, 6 ×
empty (PhraseExtraInfo/NLD/Actions/Events/Tones/DNAs), Sections,
ArrangementLevels (difficulty 0 — anchors, **anchor extensions**,
fingerprints/handshapes, notes with NextIter/PrevIter linkage), Metadata.
`NoteMask` values are the real Rocksmith constants (ported from Constants.cs).

Anchor extensions are generated one per sliding note (`BeatTime = time +
sustain`, `FretId = slideTo`), so the fretboard re-anchors where the slide lands
(Rocksmith2014.NET `AnchorExtension.fs`, 12-byte layout). Vocals are emitted as
a **separate `<key>_vocals.sng`** arrangement (same Sng2014 container, only the
Vocals section populated) with its own `Vocals` manifest entry — not embedded in
an instrument SNG (which the game would not read as vocals). `sng.from_vocals`
builds that vocals-only model.

What is intentionally absent (these are correct given the domain model, not
defects):
- **Single difficulty level**: RockForge has no dynamic-difficulty (DD) model;
  the chart plays at full density. A real feature gap, not a malformed file.
- **ChordNotesId = -1 for simple chords**: only chords with per-string
  bend/slide/vibrato get a ChordNotes entry — exactly what DLC Builder/EOF do.
- **Fingerprints2 (arpeggio) empty**: the domain has no arpeggio marking.
- **ParentPrevNote / linkNext absent**: the domain has no note-link concept (the
  XML writer hard-codes `linkNext="0"`), so this is correctly `-1`.
- **Note Hash = 0**: a deliberate choice — the two reference tools
  (Rocksmith2014.NET vs toolkit) compute mutually different, non-validated hash
  values, so 0 is safe and source-consistent.

Unverified-by-design: the binary layout is ported from the open format docs and
round-trip-tested (`read_sng` ∘ `write_sng` = identity), but is NOT byte-diffed
against a retail/DLC Builder SNG — no reference file exists in CI.

### Dual output: Bundle + PSARC always

`psarc_mode` defaults to `"native"`. Every completed job produces **both** a
Bundle zip (DLC Builder-importable: XMLs, `.rs2dlc`, audio, project metadata)
**and** a `.psarc` file (game-ready, encrypted SNG + manifest). The web UI shows
both download links when `psarc_available` is true. If the `[psarc]` extra
(`cryptography`) is missing, `NativePsarcPacker` gracefully degrades: the bundle
is still produced, only the `.psarc` is omitted (no crash).

### Standalone executable (`build_exe.py` / PyInstaller)

`start_standalone.py` is the entry point for the PyInstaller-built `.exe`. It
sets `ROCKFORGE_WORKER_MODE=inprocess` before any import, so the API dispatches
tasks to a `ThreadPoolExecutor(max_workers=1)` inside the same process instead
of to Celery/Redis. The task functions themselves (`generate_cdlc`,
`detect_lyrics`) are identical — only the dispatch changes. `worker_mode`
(`config.py`) controls which path `_enqueue`/`_enqueue_detect` take:

- `"celery"` (default): `.delay(job.id)` via Celery (needs Redis + worker).
- `"inprocess"`: `inprocess.enqueue_generate(job.id)` via thread pool (no Redis).

The PyInstaller spec (`rockforge.spec`) excludes the ML stack (torch, tensorflow,
demucs, basic-pitch, whisperx, scipy, numpy) — the `.exe` covers the GP pipeline
+ native PSARC core. ML extras work if installed separately on the user's Python.
ffmpeg is bundled from `ffmpeg/ffmpeg.exe` (placed by the user before build);
`start_standalone.py` prepends the bundled path to `$PATH` at launch.

## Commands

```bash
pip install -e ".[dev]"             # core + tests, no ML
pip install -e ".[dev,ml]"          # adds Demucs/Basic Pitch/librosa
pip install -e ".[dev,ml,lyrics]"   # + WhisperX (automatic lyric detection)
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
- **`whisperx` is pinned `<3.4`** (the `lyrics` extra). `whisperx>=3.4` pulls
  `pyannote-audio>=4.0`/`numpy>=2.1`, which directly conflicts with
  `basic-pitch`'s `tensorflow<2.15.1` (needs `numpy<2`) — installing `[ml,lyrics]`
  together then sends pip's resolver into `ResolutionTooDeep` (it backtracks
  over the whole `transformers`/`numpy` version range and never finishes). Don't
  bump this without re-checking the `numpy` ranges of both stacks.
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
- **External CLIs must not inherit stdin.** ffmpeg (and any console tool) run as
  a subprocess from the Windows `start.bat` worker inherits the console's stdin,
  goes interactive and blocks forever — the symptom is a job stuck at the
  `normalize`/lyrics-`normalizing` stage. `FfmpegNormalizer` passes `-nostdin` +
  `stdin=subprocess.DEVNULL` (plus a `FFMPEG_TIMEOUT_S` ceiling so a genuine
  stall fails loudly); `DemucsSeparator` uses `stdin=subprocess.DEVNULL` too.
  Guarded by `test_ffmpeg_normalizer.py`. Don't drop these when touching the
  subprocess calls.
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

### Shutdown on tab close (`ROCKFORGE_IDLE_SHUTDOWN_S`)

`start.bat` sets `ROCKFORGE_IDLE_SHUTDOWN_S=15`: the web UI calls `POST
/heartbeat` every 4s while its tab is open; a background watchdog
(`_idle_shutdown_watchdog` in `interfaces/api/app.py`) sends `SIGTERM` to the
API process if no heartbeat arrives within that window (i.e. the tab was
closed, not just refreshed). The foreground uvicorn then exits, and
`start.bat`'s existing cleanup (after the `uvicorn` line) stops the Celery
worker and any Redis it launched too. Default is `0` (disabled) — required for
shared deployments (docker-compose) where one user's closed tab must not stop
the service for everyone.

## Conventions

- Keep the honesty: surface warnings via the pipeline's `warnings` list, never
  invent metadata, label confidence explicitly.
- Match surrounding code style. The codebase comments only to state non-obvious
  constraints (often citing the research doc section), not to narrate.
