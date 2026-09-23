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
application/    ports.py (Protocols) + gp_pipeline.py (use case) — orchestration only
infrastructure/ adapters implementing the ports (Demucs, librosa, ffmpeg, Wwise, RS XML, DB)
interfaces/     api/ (FastAPI) and worker/ (Celery) — the boundary; wiring lives here
```

Rules:
- `domain/` and `application/` must not import frameworks or `infrastructure/`.
  Each ML stage is a swappable `Protocol` in `application/ports.py`.
- Heavy imports (torch, demucs, whisperx) are deferred into the Celery worker's
  builders (`_build_gp_use_case()`, `_build_detection()`, `_build_stem_separator()`)
  — never import them at module top level in the API path, or the web process
  pays the cost and may fail without the ML extra.

**`VocalEvent`/`PackagingResult` live in `application/ports.py`, not
`infrastructure/`.** They used to be defined inside
`infrastructure/rsxml/vocals.py` / `infrastructure/packaging/dlcbuilder.py`,
which forced `ports.py` (and `gp_pipeline.py`) to import them back FROM
infrastructure — the inverted, forbidden dependency direction: a `Protocol`
whose own signature imports its adapter's module isn't an abstraction the
adapter can be swapped behind. Both are plain data (no I/O, no framework),
so they belong on the application side of the boundary; infrastructure now
imports them from `application.ports`, same direction as everything else.
`gp_pipeline.py` keeps two narrow, deliberate exceptions to the no-infra-import
rule: `infrastructure/gpimport/parser.py` (`inspect_gp`/`parse_gp_track`) and
the lyric-format functions in `infrastructure/rsxml/vocals.py`
(`parse_lyrics`/`distribute_syllables`/`enforce_max_line_words`) are core,
deterministic, single-implementation format parsers — not a swappable ML
stage like `Packager`/`LyricTranscriber`/`AudioNormalizer` — so putting them
behind a `Protocol` would be indirection with no second implementation to
justify it. `tests/test_architecture.py` guards both: `ports.py` must import
zero `infrastructure/` modules, and any OTHER `application/` file's
infrastructure imports must be on the explicit allowlist above, so a future
accidental import (or an unnoted new exception) fails CI instead of quietly
re-inverting the dependency.

## The generation path

> **Audio→note transcription was removed.** RockForge previously had a second
> path that turned a raw MP3 into an arrangement via Basic Pitch (`pipeline.py`,
> the fret mapper, the role splitter, `clean_transcription`/`suggest_tuning`,
> `/jobs/upload` + `/jobs/upload-split`, YouTube ingestion). Basic Pitch's
> accuracy on a distorted electric-guitar mix was never good enough to be
> trustworthy, so the whole path was deleted to slim the codebase. What remains
> that still uses the recording: **stem separation** (`/jobs/{id}/separate-stems`),
> **tone detection** (`/detect-tones`), **lyric detection** (`/detect-lyrics`),
> and the per-point tempo / tuning-cents helpers — all operate on an
> existing GP job's recording, none transcribe notes. `[ml]` (Demucs/librosa)
> is still needed for those; `basic-pitch`/`onnxruntime` and the `[youtube]`
> extra are gone.

**Guitar Pro** (`gp_pipeline.py`): notes/frets/techniques/sections come exact
   from the GP file; audio sync is a manual offset. High fidelity, preferred
   when a GP file exists. Two parsers behind one API (`inspect_gp` /
   `parse_gp_track` dispatch on format): **GP3/GP4/GP5** binary via PyGuitarPro
   (`parser.py`), and **GP7/GP8 (`.gp`)** via a native GPIF/XML parser
   (`gpif_parser.py` — the `.gp` is a ZIP whose `Content/score.gpif` is XML, so
   no extra dependency). Only **GP6 (`.gpx`)** — a proprietary binary container —
   is unsupported; export it as GP5 or GP7.

   **Tied notes** (GP `(17)` in parentheses — a held continuation, not a
   re-pick) are folded into the note they extend in BOTH parsers, never emitted
   as a second attack: GP5 via `NoteType.tie` (inline, tracking the last note
   per string), GP7 via `<Tie destination="true">` (`gpif_parser._merge_ties`).
   Skipping this makes "4 notes show as 5" and throws the rhythm off — guarded by
   `test_tied_note_extends_previous_not_new_attack` (GP5) and
   `test_gp7_tied_note_extends_not_duplicates` (GP7).

### Reloading the GP file (`/jobs/{id}/reload-gp`)

`POST /jobs/{id}/reload-gp` (multipart `gp`, GP jobs only) swaps the Guitar Pro
file of an existing job for a re-exported one — for when you tweak a note in
Guitar Pro and don't want to recreate the job and redo all the alignment. It
writes the new file to a fresh `work_dir/gp/<uuid>` and, like `/rebuild`, **forks
a new job** that inherits ALL of the original's params (tuning, `offset_s`,
`tempo_scale`, `sync_anchor_stages`, `arrangement_sync`, tones, lyrics, cover) —
only `gp_path` changes. It validates the new file parses (`inspect_gp`) and that
the previously selected `lead_track`/`rhythm_track` indices still exist (a plain
note edit keeps the track layout; a restructured file 422s with a "create a new
job" message rather than silently building the wrong track). Exposed in the sync
panel as "Recarregar ficheiro GP".

### Intro silence (`lead_in_s`)

`GpJobSpec.lead_in_s` (default 0) is user-defined extra silence prepended at the
very start, ON TOP of the automatic `MIN_LEAD_S` lead-in:
`pad_start_s = max(0, MIN_LEAD_S - offset_s) + lead_in_s`. Because the score
shifts by the full `pad_start_s` and the audio is padded by the same amount,
the whole bundle (audio + notes + lyrics) moves later together — a way to "push
the music forward" with a silent intro. Exposed in the sync panel as "Silêncio
inicial (s)" (commit-on-rebuild, no live drag). The tab viewer's `viewOrigin`
and `playheadDisplay` add the built `lead_in_s` (`leadInBuilt`) so notes/playhead
stay aligned after a rebuild with it.

### Tempo scaling (`tempo_scale`)

`GpJobSpec.tempo_scale` (default 1.0) multiplies the whole musical timeline at
parse time, around the song's start and before `offset_s` — it corrects a
constant GP-vs-recording tempo mismatch (the linearly-growing part of sync
drift) in one move. `>1` stretches (slower); `<1` compresses (faster). The
effective `average_bpm` is scaled inversely. The tab viewer exposes it as an
editable BPM/% control with live preview (notes slide over the fixed waveform).
Use it *before* the per-note `sync_anchor_stages` below, which then only need to
clean up residual non-linear drift.

### Automatic sync was REMOVED (2026-08) — manual only

> Every **automatic** synchronisation feature was deleted at the user's explicit
> request after none of them produced a usable result on their real material:
> `/auto-sync` (one average tempo), `/auto-sync-dynamic` (onset-correspondence
> drift curve), `/sync-from-midi` (RIPX tempo-map import), `/sync-from-stem`
> (Beat This! neural downbeats) and `/analyse-sync` (drift diagnosis + graph +
> per-finding accept/reject), along with `application/sync_analysis.py`,
> `infrastructure/rhythm/{beatthis_adapter,midi_tempo}.py`, the
> `align_chart_to_recording`/`align_chart_to_midi`/`align_bars_to_downbeats`/
> `suggest_sync` helpers, the librosa whole-song estimators
> (`detect_beats`/`detect_onsets`/`detect_tempo_and_onset`) and the `beatthis`
> extra. The UI's automatic buttons and the drift-graph panel went with them.
>
> **Why, honestly:** on the user's songs (AI-generated tabs against their source
> recordings) the estimators either read the wrong metrical level, or produced
> so many corrections that applying them scrambled the score. They were correct
> on synthetic data and repeatedly wrong on real audio. Rather than ship
> plausible-looking machinery that misleads, the feature set was cut back to the
> tools the user can verify by ear.
>
> **What remains is deliberate and sufficient:** the whole manual toolkit — Step 1
> (first-note pin: field/slider, "Início = cursor", the guided 3-click "Detetar
> 1ª nota"), `tempo_scale` (BPM/%) for a uniform difference, the bar-align panel
> and 📏 popup, and the per-note modes (drag/tap/excerpt/move-from-here/new-beat)
> — plus `/detect-tempo` (local BPM from one clicked instant, which backs the
> per-point re-tempo) and `/detect-tuning`. `suggest_tempo_scale` stays because
> `/detect-tempo` uses it.
>
> Git history has all of it (`git log -- src/rockforge/application/sync_analysis.py`)
> if any of it is ever worth reviving — the algorithms are documented in those
> commit messages, including the measured failure modes.


### Exporting a corrected Guitar Pro file (`/export-gp`)

`infrastructure/gpexport/tempo_writer.py` writes the accepted tempo corrections
into a **copy** of the user's Guitar Pro file, so the fix is permanent in Guitar
Pro itself and not only inside RockForge. The uploaded original is only ever read.

| format | write | how |
|---|---|---|
| `.gp3`/`.gp4`/`.gp5` | yes | PyGuitarPro. A tempo change is a `MixTableChange` on a **beat** (there is no tempo field in the measure header); measure 1 is the song header's `tempo`. |
| `.gp` (GP7/8) | yes | The container is a plain ZIP: every entry is copied **byte-for-byte** and ONLY `Content/score.gpif` is replaced. Tempo is a `MasterTrack/Automations/Automation[Type=Tempo]`, `<Value>` = `"<bpm> 2"` (reference 2 = quarter). |
| `.gpx` (GP6) | **no** | A proprietary container nobody writes — not alphaTab, not TuxGuitar, not MuseScore. Refused, pointing at GP5/GP7 like the importer does. |

Routes ruled out by research, so nobody re-litigates them: MuseScore imports GP
but **cannot export it** (import-only module); MusicXML drops vibrato and palm
mute; MIDI loses tab/tuning/technique entirely. Neither leads back to a `.gp*`.

Details that were measured and will bite anyone editing this:
- **The binary formats store tempo as an INTEGER**, so 119.085 BPM is written as
  119. `write_tempo_corrections` returns an `AppliedCorrection` per measure with
  `requested_bpm`/`written_bpm`/`rounded` so the API and UI can say so instead of
  quietly handing back a different tempo. GPIF keeps the decimals.
- A fresh `MixTableChange` has `wah=None`, but GP5 always stores a wah byte, so
  it reads back as `WahEffect(-1)` and the file stops round-tripping; and
  `hideTempo` defaults `True` while the field does not exist before GP5.1. Both
  are set explicitly.
- An existing `MixTableChange` on the target beat is **mutated**, not replaced —
  it may carry an instrument/volume/wah change that is not ours to drop. A tempo
  change the user authored themselves survives untouched (guarded by
  `test_an_authored_tempo_change_is_preserved`), as does a mid-bar GPIF
  automation (only `Position == 0` entries are ours).
- Only **tempo** is exportable. A *jump* cannot be expressed as a BPM change (it
  would need a bar inserted or removed), so it stays a RockForge-side correction
  and the UI says so rather than approximating it.

`POST /jobs/{id}/export-gp` writes `work_dir/<job>/corrected.<ext>` and returns
the report; `GET /jobs/{id}/corrected-gp` downloads it. Wired to the sync panel's
**"🎼 Exportar GP corrigido"** button, which derives the `(measure, bpm)` list
from the pending sync: `retempoedBars()` returns exactly the bars the score
already draws in AMBER (the same `>= 2` BPM threshold), so what is marked on
screen is what gets written. Both the drawing and the export read one
`barTempoTable(a, warp)` — they were the same code inline in `showArr` before,
and two copies would silently drift until the exported file no longer matched
the score. Bars whose corrected tempo falls outside the endpoint's (10, 400)
bound are dropped with a count rather than 422-ing the whole export. Guarded by
`test_gp_tempo_writer.py` (preservation of notes/frets/techniques/tracks/tuning/
sections across a real write, byte-identity of the .gp ZIP's opaque entries,
rounding reported, `.gpx` refused, bad corrections rejected with nothing
half-written) and `test_export_gp_*` in `test_api.py`.

**Unverified by design:** no Guitar Pro is available in CI or in the sandbox, so
the exported files are round-trip-verified through our own parsers but have NOT
been opened in Guitar Pro itself. The `.gp` ZIP-surgery route in particular is
sound in theory (it is exactly what alphaTab's `Gp7Exporter` builds) but needs a
human to confirm against a real install.

### Exporting the EDITED chart as a new GP file (`/export-arrangement-gp`)

`/export-gp` above only ever writes **tempo** into a copy of the user's own
file, so the note editor's edits (and any note added/removed in the browser)
had no way back into Guitar Pro at all. `infrastructure/gpexport/
arrangement_writer.py` closes that: `write_arrangement_gp5(arrangement, dst)`
generates a **brand-new GP5** from what RockForge actually holds — notes,
frets, techniques, tuning, section markers and the corrected beat grid.

**It reads the BUILT XML, not the Guitar Pro source.** `infrastructure/rsxml/
reader.py`'s `read_arrangement_xml` is the partial inverse of `writer.py`: it
recovers tuning, ebeats, notes-with-techniques and sections — everything the
exporter needs — and deliberately NOT phrases/DD levels/anchors/tones, which
are derived data with no GP counterpart. Reading the built file is the whole
point: it already carries `tempo_scale`, every `sync_anchor_stages` round and
every `note_overrides` patch, so what comes out is the chart as RockForge
plays it. (`find("tuning") or fallback` is a trap here — an ElementTree
element with no children is **falsy**, and `<tuning>` has only attributes, so
the truth test threw the real tuning away and every export came back in
standard E. Use `is None`.)

**The two honest costs, stated on every export, not only on failure:**
- **One track.** A generated file cannot carry the user's other tracks,
  formatting or anything else from the original — it is this arrangement
  alone. That is why `/export-gp` still exists: use it when only the tempo is
  wrong and the original file must survive intact.
- **Quantization.** Guitar Pro stores *notated rhythm*, not absolute seconds,
  so an onset that falls between grid positions has to move. `_quantize`
  snaps to the measure grid and the report returns `quantized` +
  `max_shift_s`; the UI shows both. Silently re-timing notes into a score
  that looks authoritative but plays differently would be the worst outcome
  here. `_split_ticks` decomposes an arbitrary span into notatable durations
  (`Duration.fromTime` raises on anything it cannot represent).

PyGuitarPro details that were measured and will bite anyone editing this:
`MeasureHeader.start` does **not** auto-accumulate — each header's start tick
must be set explicitly, or the score drifts (166.7 ms on the first test song);
`MeasureHeader` has no `tempo` field at all, so a per-measure tempo is a
`MixTableChange` on the measure's first beat, same as `tempo_writer`; string
numbering is 1 = highest pitch.

`POST /jobs/{id}/export-arrangement-gp?arrangement=<Kind>` writes
`work_dir/<job>/corrected.gp5` and records it in `params["corrected_gp"]`, so
the existing `GET /jobs/{id}/corrected-gp` serves it — whichever export ran
last wins, each recording its own filename. Wired to the sync panel's **"🎸
Exportar GP com as notas editadas"**, beside the tempo-only button.
Guarded by `test_gp_arrangement_writer.py` (notes/times/strings/frets,
techniques, chords-as-one-beat, tuning/metadata/sections, a mid-song tempo
change, the reported quantization, the always-present single-track warning,
and an empty beat grid refused) and `test_export_arrangement_gp_*` in
`test_api.py`. Same **unverified-by-design** caveat as above: round-tripped
through our own importer, never opened in Guitar Pro itself.

### Clearing note edits (`🧹 Limpar edições`)

The companion to the seeding fix in the note-editor section: once committed
edits are seeded back into the viewer, discarding them has to be an explicit
action rather than a side effect of reopening the job. "🧹 Limpar edições"
drops the current arrangement's `note_overrides`, "🧹 Limpar em todas" drops
every arrangement's; both send the smaller dict on the next rebuild, which
genuinely removes them. `updateNoteEditsInfo` shows the per-arrangement count
and disables both buttons when there is nothing to clear.

### The recommended workflow: "Corrigir daqui" (`newbeat` mode, `/detect-tempo`)

This is the DEFAULT sync mode (`syncMode = 'newbeat'`), and it is the one the
user found actually holds up on real material — worth recording why, because it
is the same principle every removed automatic tool was trying and failing to
apply on its own.

The user listens until the chart starts drifting away from the recording and
clicks that note. `reTempoFromHere` then:

1. pins the clicked note **where it already sits** (`setAnchor(origT, dispT)`) —
   so nothing before the click can move, and whatever was already correct stays
   correct;
2. measures the recording's tempo **from that instant onward**
   (`/detect-tempo` → `detect_tempo_from`, metrically corrected by
   `suggest_tempo_scale`);
3. stretches only the tail `[click, last note]` by that factor.

**The factor is relative to the timeline on screen, and the detector's prior is
the chart's own tempo.** Both halves were wrong and both pushed the same way —
"dá sempre tempo maior e fica muito acelerado". (a) `/detect-tempo` measured the
factor against the GP file's **header** tempo, while the viewer applies it as a
relative stretch of the ALREADY-displayed tail: that double-counts the song's own
tempo changes (a section authored slower than bar 1 got "corrected" by that whole
difference) and, worse, re-applies the same absolute factor on every repeat, so
correcting one passage twice compounds (×0.9 → ×0.81 → ×0.73) into a chart
running away. The viewer now sends `chart_bpm` — the live BPM readout at the
click — and the factor is measured against that, so a second run on an
already-correct passage returns ×1.000. (b) librosa weights its tempo candidates
with a log-normal prior centred on `start_bpm`, which **defaults to 120**; left
there it reads a slow song at double time, which is literally "always a higher
tempo, never a lower one". `chart_bpm` is passed through as `start_bpm`, turning
the open question into the narrow one ("faster or slower than this?"). (c)
`suggest_tempo_scale` broke a genuinely ambiguous half/double pair with
`abs(scale - 1)`, which is asymmetric — an octave high scores 0.5, an octave low
scores 1.0 — so it always preferred the faster reading; it now compares
`abs(log(scale))`. Guarded by
`test_detect_tempo_measures_against_the_chart_bpm_not_the_header` and
`test_suggest_tempo_scale_does_not_favour_the_faster_reading_on_a_tie`.
`liveInfoAtTime` was also measuring the beat interval on the RAW beat times, so
the `♩ =` readout ignored every pending tempo/anchor edit; it now measures the
displayed spacing (which is what makes it usable as `chart_bpm`).

The division of labour is the point: the HUMAN supplies the one thing the
automatic tools kept getting wrong — WHERE the divergence starts — and the
machine answers the narrow, reliable question, "what is the tempo from here?".
Estimating a whole song's drift curve is hard and was consistently wrong;
measuring a local tempo from a known-good starting point is not.

It repeats safely: each application starts from the timeline the previous one
produced (`dispLast` is read through the current warp), so correcting the same
song four or five times along its length composes instead of fighting itself.

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

**A tempo/offset change RE-EXPRESSES the already-committed anchors (the preview
must equal the rebuild).** The build computes `W(x·s + S)` — parse at
`tempo_scale` `s` with score shift `S = max(offset_s, MIN_LEAD_S) + lead_in_s`,
THEN warp — while the tab viewer previews `R(W(x·s_built + S_built))`: it
rescales the ALREADY-WARPED times it read back from the built XML (it never
re-derives the raw GP times). Composition does not commute (`R∘W ≠ W∘R`), so once
ANY anchor stage is committed, changing the tempo made the rebuild differ from
the preview by **`d·(r−1)` on every note** (`d` = net shift the committed anchors
introduce, `r` = the tempo ratio) — a *constant* desync, invisible in the viewer
but plainly wrong in game. That was the "no programa está sincronizado, no
Rocksmith não" bug, and it fires on the ordinary workflow (drag → rebuild →
BPM change → rebuild). `rebuild_job._remap_committed_anchors` maps every
stored anchor pair through the viewer's own map `φ(t) = (t − S_old)·r + S_new`,
making each stage `W' = φ∘W∘φ⁻¹` so `W'∘φ = φ∘W` exactly; each arrangement is
conjugated with ITS OWN tempo ratio (tempo_scale is per-arrangement) but the
shared job-level shift. Guarded by
`test_tempo_change_reexpresses_committed_anchors_in_the_new_timeline` and
`test_committed_anchors_untouched_when_the_timeline_does_not_change`.
**The two halves of `S` must match on both sides**: `web/app.js`'s `scoreShift`
omitted `lead_in_s` (and `previewScale` did not re-add it), which desynced the
rebuild by `lead_in_s·(r−1)` on its own — both now include it. If you change how
`score_shift` is computed in `gp_pipeline`, change `scoreShift`/`previewScale`
in the same commit.

**Pending anchors are kept in CHART order, and a crossing is flagged in the
list.** `setAnchor` used to append, so the list showed insertion order — a real
case read "Correção 4: 196.93s" above "Correção 5: 195.88s", which makes the
numbering describe an order the music does not have and hides a correction that
crosses another. `setAnchor` now sorts by chart time (the warp sorts internally
on both sides, so no timing changes — only what is shown and the numbering that
follows), and `renderAnchorsList` marks any row whose target is at or before the
previous row's with "⚠ cruza a anterior". That is the same condition
`_check_anchor_order` rejects at build time; surfacing it in the list means it
is fixable while it is still pending, instead of failing at "Aplicar e
reconstruir".

**Conflicting anchors are rejected, not silently warped into nonsense.** Two
anchors whose corrected times contradict their chart-time order (a later chart
point mapped to an earlier recording instant than an earlier point) make
`_build_time_warp` fold back on itself — the beat grid comes out of
chronological order and construction crashes deep inside `TempoMap` with a
cryptic `ValueError`, giving no clue which correction caused it. Successive
"Mover seguintes" clicks are the usual way to create this by accident (each one
re-anchors the arrangement's LAST note to a new target, so two clicks can leave
it pointing at inconsistent targets). `_check_anchor_order` validates each
round before it's applied and raises `IngestionError` naming the two
conflicting points in seconds, so the user knows which correction to remove or
adjust. Guarded by `test_conflicting_sync_anchors_raise_clear_error` /
`test_check_anchor_order_accepts_valid_and_rejects_crossing`.

**A local stretch re-inflates sustain — re-trim after warping.** A correction
that maps a chart interval to a WIDER corrected interval (a local stretch
factor > 1) scales every note's warped sustain by that same factor
(`sustain = warp(time+sustain) - warp(time)`). This can re-inflate — or make
notes overlap outright — a sustain `apply_sustain_gap` already trimmed to a
small gap at parse time (first fixed, on the un-warped timeline, in commit
`4147d89`): on the highway, fused/overlapping sustain trails render as "tall
pillars" or a solid wall instead of separate note shapes. `_warp_parsed_track`
re-applies `apply_sustain_gap` to the warped notes so the gap invariant holds
regardless of what a sync correction did to the local tempo. Guarded by
`test_warp_re_trims_sustain_after_a_local_stretch`.

**Beat snapping (drag).** By default (checkbox "Encaixar em:") a note (or
selection) drag snaps its target to the nearest position of a grid, so
corrections jump grid-to-grid instead of sliding continuously — cleaner and
jitter-free for the common "align this note to a beat" correction. The grid
resolution is a dropdown (`snapDiv`): bars (downbeats only), whole beats, or
beats subdivided into 2/3/4 (`snapGridTimes` interpolates between the real
ebeats, so tempo changes are respected). The beat times come from
`ArrangementOut.beats` (ALL ebeats — downbeats + off-beats, distinct from
`bars`, which is downbeats only for numbering); the viewer warps each grid point
through the same `previewScale`+anchor warp as the notes, caches those display
positions at drag start (`snapPositions`), and `snapDisplay()` snaps to the
nearest. Holding **Alt** during a drag bypasses the snap for free placement. It
only changes the drag TARGET — the anchor/warp machinery is unchanged, so it
composes with everything else.

**Selecting notes.** Selection is modifier-driven and independent of the sync
mode: a plain click selects one note (and sets it as the pivot), **Shift+click**
selects the inclusive range from the pivot to the clicked note (`rangeSelect`),
**Ctrl/Cmd+click** toggles a single note, and a click on empty staff clears the
selection. Dragging any selected note moves the whole selection in one rigid
block (snapping the earliest to the grid) — but ONLY in the "Arrastar" mode;
re-clicking the active mode button deselects it to a neutral state (no mode
highlighted, note-drag disabled, selection still works), rather than falling
back to "Arrastar". (The older
rubber-band "Excerto" box-select still exists but Shift+click is the primary
path.) True note *editing* — moving a note to a different beat, changing its
fret/techniques, or inserting/removing one — is a separate mode ("Editar
notas", see "Note editor" below), no longer notes-come-exact-from-the-GP-only.

**Auto-scroll during a drag/box-select (fixes "só seleciono o que está
visível").** `#tabwrap` is a plain `overflow-x:auto` container around a
potentially very wide SVG (a long song can be thousands of pixels), and it
never scrolls on its own while a pointer-capture drag is in progress — so
before this fix, the rubber-band ("Excerto") box, a single-note drag, or a
selected-block drag could only ever reach whatever was already visible in the
current viewport; the mouse itself is bounded by the browser window, and
dragging to the screen edge did nothing. `handlePointerMove` (the pointermove
body, refactored into a named function so it can be re-invoked from a second
caller) is now also driven by a `requestAnimationFrame` loop
(`autoScrollStep`) that runs for as long as ANY of the four gestures
(`rubberBand`/`groupDrag`/`dragging`/`lyricDrag`) is active and the last known
pointer position sits within `AUTO_SCROLL_EDGE_PX` (48px) of `#tabwrap`'s left
or right edge: each frame it nudges `scrollLeft` (up to `AUTO_SCROLL_MAX_PX`,
scaling with proximity to the very edge) and re-runs `handlePointerMove` with
the cached last pointer position — necessary because the rubber-band box's
x/width are SVG-local coordinates (`clientX - rect.left`), and `rect.left`
itself shifts as the container scrolls, so the box must be recomputed even
though the mouse hasn't moved. Stops immediately on `pointerup`/`pointercancel`
(verified: no further `scrollLeft` change after release). Guarded manually via
Playwright (a 4000px-wide synthetic chart, a 600px viewport, holding the
rubber-band drag at the right edge reaches and selects a note far outside the
initial view) — no pytest coverage (pure `web/app.js`, same category as the
other browser-only interaction fixes in `TESTING.md`).

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

**"Passo 1 — Início da música" is per-arrangement.** `offset_s` itself stays
job-level for the reason above (one shared, once-padded `.wem`) and is set
once at job creation; but Step 1's runtime precision tools in the tab
viewer — the numeric field + slider, "Início = cursor", and the guided "🎯
Detetar 1ª nota" 3-click flow — pin just the CURRENT arrangement's first note
independently of the others, for GP files whose tracks were tabbed with a
different pickup/lead-in per instrument, where a single shared offset can't
fit both. There is deliberately only ONE "first note time" control in the UI
(an earlier version added a second, per-arrangement-only panel; users found
two confusing, so it was folded back into Step 1 — see git history if
resurrecting the idea). It reuses the existing single-anchor mechanism (a
lone `sync_anchor_stages` anchor = a uniform shift for that arrangement)
rather than a new field: `updateSyncOffsetDisplay()` (called from `showArr`
on every redraw/tab-switch) refreshes Step 1's field from
`buildTimeWarp(syncAnchors)(previewScale(firstNoteChartTime)) - viewOrigin`
— for the common case (no per-track anchor yet, the track's first note sits
at its own timeline's start) this equals `offsetLive` exactly, so switching
tabs looks unchanged until a track's first note genuinely has its own
pickup, at which point the field diverges to show and let you fix THAT
track's own value. Every edit — the field, the slider, "Início = cursor"
(`setTrackStart(audioTime())`), and the guided flow's final click — always
writes a per-arrangement anchor via `setAnchor`, never `setOffsetLive`
(which now only fires from `initSync`'s initial load). All write into the SAME per-tab pending anchor array Step 3
already uses (`syncAnchorsByKind[currentKind()]`), so they ride the existing
"Aplicar e reconstruir" commit — no separate button, no backend change.
`setTrackStart`/the guided flow both pass the note's UNwarped
`previewScale(chartT)` as the anchor's origin (matching `'drag'` mode's
convention, not `'tap'` mode's `buildTimeWarp`-wrapped one) specifically so
that repeatedly nudging the slider/re-running the guided flow updates the
SAME anchor slot instead of compounding into an unintended multi-point warp.

**All anchor-writing modes use the UNwarped origin (fixed "Mover seguintes"
moving notes the wrong way).** `'tap'`, `'movefrom'` and `'newbeat'` used to set
each anchor's ORIGIN to the WARPED position (`warp(previewScale(t))`); with no
pending anchors that coincides with the unwarped value so it looked fine, but
the moment a pending anchor already exists (e.g. Step 1's own "Início"), a
warped origin corrupts `buildTimeWarp`'s piecewise map and the clicked note
lands somewhere else entirely — the "notes moved away from the cursor instead
of onto it" bug. All three now use `previewScale(t)` (unwarped) as the origin,
same convention as `'drag'`/`setTrackStart` above, and compute the target from
the CURRENT `warp(...)` value + the intended delta.

**"Mover seguintes" pins the region BEFORE the click so it stays put.**
`'movefrom'` shifts the clicked note + everything after it by a delta, via two
anchors (clicked note → cursor, last note → same delta). But those two anchors
alone don't hold the region before the click: once a prior anchor exists (e.g.
Step 1's "Início", which as a lone anchor is a *uniform* shift), adding the
clicked/last anchors turns the previously-uniform pre-click segment into an
*interpolated* one, dragging the preceding notes along ("mover seguintes
atualizou também as notas que ficaram para trás"). The fix mirrors what
`'newbeat'`/`reTempoFromHere` already does with its pivot: also pin the note
immediately BEFORE the click at its CURRENT displayed position
(`setAnchor(previewScale(prevNoteTime), warp(previewScale(prevNoteTime)))`) —
a point already on the current warp curve, so everything up to it is unchanged
and only `[clicked, last]` shifts. (`'newbeat'` never had the bug because its
pivot anchor already pins the click to its unchanged position.)

### Sync by bar number (`barSyncPanel`)

For a track whose real content only starts several measures in — e.g. Rhythm
rests through the intro and its first real note coincides with **bar 7** — the
per-track "Início" tools above only pin the very FIRST note, which isn't
useful when the correction point is mid-song. A dedicated panel right after
Step 1 lets the user pick **any bar number** of the current arrangement and
align it two ways:
- **"= cursor"**: pause/scrub playback to where that bar should sound, click —
  same `setAnchor(previewScale(barChartTime), currentPlayheadT + viewOrigin)`
  pattern as `setTrackStart`, just for an arbitrary bar instead of the first
  note.
- **"Sincronizar" with another arrangement**: aligns the chosen bar directly to
  the SAME bar number's current position in an already-synced reference
  arrangement (e.g. Rhythm's bar 7 → Lead's bar 7) — no listening required.
  Sound because bar numbers come from ONE shared, song-level measure header in
  the GP file (`parser.py`: `for measure in track.measures: … header.number` —
  every track iterates the same measure sequence), so bar N is the same
  musical instant across every track before any per-track correction.

  Reading "where does the reference arrangement's bar N currently sit" requires
  that arrangement's OWN live tempo/anchors, independent of whichever tab is on
  screen — `arrangementPreviewScale(idx, t)`/`arrangementDisplayTime(idx, t)`
  generalize `previewScale`/`buildTimeWarp(syncAnchors)` to read `arrangements[
  idx]`'s own `tempo_scale`/`tempoScaleByKind`/`syncAnchorsByKind` instead of
  the current tab's live globals (`tempoScaleLive`/`syncAnchors`), which is only
  possible because every arrangement's pending edits stay in those `ByKind` maps
  for the whole session, not just the active tab's.

  `updateBarSyncPanel()` (called from `showArr`) repopulates the bar dropdown
  from `arrangements[currentArr].bars` and the reference dropdown from every
  OTHER arrangement. Both actions write into the SAME per-tab pending anchor
  array as everything else (`syncAnchorsByKind[currentKind()]`) — rides the
  normal "Aplicar e reconstruir", no backend change.

  Both the panel and the click-a-note popup below share one primitive —
  `alignBarTo(measure, target)`: a single anchor pinning that bar's downbeat
  (`setAnchor(previewScale(barChartTime), target)`) to a bundle-time display
  position, which is the cursor (`currentPlayheadT + viewOrigin`) or another
  arrangement's same bar (`refBarTarget`). Multiple pins compose into a
  piecewise drift correction.

**Bar-align popup (`'baralign'` mode, 📏).** For doing MANY bar-syncs quickly
without hunting the bar number in a dropdown each time: a sync mode where
clicking a note opens a small floating popup (`#barAlignPopup`) with the bar
numbers, the clicked note's OWN bar pre-selected (`openBarAlignPopup` finds the
containing bar). "= cursor" calls `alignBarTo(bar, currentPlayheadT +
viewOrigin)`; "= pista" (shown only with ≥2 arrangements) aligns to the same
bar of a chosen reference arrangement. It's the same `alignBarTo` primitive as
the panel — just a faster, note-driven entry meant to be repeated along the
song for progressive drift correction. Dismisses on Escape or an outside click
(a note click reopens/repositions it).

**Cursor as an explicit snap target (fixes unreliable "drag to the cursor").**
Before, only the click-based `'tap'`/`'movefrom'` modes snapped to the live
playhead (`currentPlayheadT`); the familiar drag gesture (`'drag'`/`'excerpt'`
modes) only ever snapped to the beat grid, with no visual difference between
the two gestures — the likely source of "arrastar para o cursor nem sempre
funciona". `#snapDiv` now has a `"cursor"` option; `snapDisplay` special-cases
it to return `currentPlayheadT + viewOrigin` directly (skipping the
nearest-neighbor grid search), so the ordinary drag gesture reliably lands on
the playhead when that option is picked, with no mode-switching required.

**Numeric anchor editing.** `renderAnchorsList` rows now show the target time
as an editable `<input type=number>` (was plain text) — typing an exact value
calls `setAnchor` the same as a drag would, so a correction no longer has to
be pixel-perfect by mouse, and an already-placed correction can be adjusted
without delete-and-redo. Also fixed: the single-note and group-drag `pointerup`
handlers redrew the score but never called `renderAnchorsList`/
`updatePendingChangesInfo`, so the pending-anchors list silently went stale
after a plain mouse drag (it only refreshed after `'tap'`/`'movefrom'`/
`'newbeat'` clicks) — both handlers now refresh it too.

**Zoom keeps its place.** `setZoom` used to rescale `tabPx` and redraw without
touching `#tabwrap`'s `scrollLeft`, so the same pixel offset silently mapped to
a different time after zooming — the view jumped away from whatever passage
you were trying to zoom into. It now captures the centered time before
changing `zoomLevel` and restores the equivalent `scrollLeft` after the
redraw, so zooming in/out keeps the same passage in view.

**No native text selection during score interaction.** Shift+click (a classic
browser text-selection trigger) or any click-drag over the SVG's `<text>`
labels (technique letters, tuning names, bar numbers) used to highlight them
like page text instead of purely driving the custom note-selection/drag logic.
Fixed with `user-select:none` on `#tabsvg` plus `e.preventDefault()` as the
first line of the SVG's `pointerdown` handler.

The tab viewer's x-axis is **recording time** (0s at the left edge): notes are
drawn via `timeToX` (which subtracts the lead-in `viewOrigin` from the
bundle-time positions), so the playhead starts at 0 instead of at the first
note. Anchor math stays in bundle time so corrections round-trip through a
rebuild unchanged.

The viewer's `isGpJob()` guard on `previewScale`/`playheadDisplay`/`viewOrigin`
(identity sync for non-GP jobs, hiding `#gpSyncControls`) remains for legacy
non-GP job rows; today only GP jobs are created. `GET /jobs/{id}/source-audio`
serves `job.source` when it's a real file and otherwise falls back to the
ingested `input.*` / `normalized.wav` in the job's work dir.

**String labels show the real tuning.** The staff labels each string with its
actual pitch (`stringLabel` = standard MIDI `[40,45,50,55,59,64]` + the
arrangement's `tuning_offsets`, mapped to a note name), so a Drop C# chart reads
`C# G# C# F# A# D#` instead of the fixed `E A D G B e`. Falls back to standard
if `tuning_offsets` is absent.

**Measure (bar) numbering.** The viewer draws a faint vertical line + bar number
at each measure downbeat. The source is the Song2014 `<ebeats>` (one `<ebeat
time measure>` per beat; downbeats carry the 1-based measure, off-beats `-1`),
which the GP parsers fill from `tempo_map.beats`. `/jobs/{id}/arrangements`
filters `measure>0` into `ArrangementOut.bars`; the viewer warps each bar time
through the same `previewScale`+`buildTimeWarp` as the notes, so bar lines track
pending sync edits. Bars make tempo changes and drift visible — the user can see
exactly which measure slips against the recording and drag-correct it there.

### Section editor — mark/rename song structure on the score

Sections (intro/verso/refrão/solo…) used to come **only** from the GP file's
own measure markers (`GpSection`, extracted in both parsers from a Guitar Pro
"marker" on a measure); there was no way to add, rename, or move one without
going back to Guitar Pro. A new **"🏷️ Secções"** panel (right below the tone
panel) plus a **"Secção" sync mode** (🏷️, click a note to name where it starts)
let the user edit them directly in the tab viewer, for Riff Repeater and
navigation.

**Job-level, shared across arrangements — same convention as `tone_changes`.**
`GpJobSpec.section_overrides: list[Section] | None = None` (bundle-clock
times, `application/gp_pipeline.py`): `None` keeps each arrangement's own
GP-parsed sections (today's default, unchanged); a list — even empty —
**replaces** the section markers identically on every arrangement, sorted by
time and renumbered. Times are NOT run through each arrangement's own
per-track warp (unlike notes/beats), exactly like `tone_changes` — an accepted
simplification (documented, not silently assumed): if arrangements have very
different `tempo_scale`/drift corrections, a shared section time may not land
on the same musical instant in every chart. `celery_app.py` reconstructs it
from `params.get("section_overrides")` (`None` vs an explicit list — the same
tri-state as `lyrics_events`).

**Surfaced via `ArrangementOut.sections`, not a new endpoint.** `GET
/jobs/{id}/arrangements` already parses each arrangement's built XML; it now
also reads `<sections><section>` into `SectionOut(time, name, number)`,
**excluding** the writer's synthetic trailing `"noguitar"` entry (`writer.py`
always appends one to mark where the phrase timeline ends — a structural
closer, never a user-facing section). `RebuildIn.section_overrides: list[
SectionOverrideIn] | None = None` follows the standard null-sentinel
convention (`None` = untouched; `rebuild_job` writes `params[
"section_overrides"]` only when not `None`).

**Frontend dirty-flag, not always-send.** Unlike `tuning_midi`/`tempo_scale`
(always sent, safe because they're always pre-filled with the live value),
sections have a real prior default (the GP file's own markers) that an
untouched, always-send round-trip could silently overwrite on an unrelated
rebuild. `songSections` (state, shared across tabs) is seeded from
`arrangements[0].sections` on job load; `sectionsTouched` only flips true once
the user actually adds/renames/moves/removes a marker, and `applyAll()` sends
`section_overrides: (isGpJob() && sectionsTouched) ? songSections : null` —
so a rebuild that never touches sections leaves the GP-authored ones alone.
Adding a marker: either the "Secção" sync mode (click a note, prompts for a
name) or "+ Adicionar no cursor" (places one at the current playhead without
needing to land exactly on a note); the list panel's time/name fields are
directly editable (like the sync-anchors list), each edit re-sorting by time.
On the score, section markers span the **full staff height** (distinct from
the tone-change markers, which live in a band below the staff) in teal, with
a `🏷️` label, so the song structure is visible at a glance while scrolling.

### Note editor — add/edit/remove notes and techniques on the score

Until now the tab viewer only ever corrected *sync* (moving a note in time);
the note's *content* — fret, sustain, techniques, bend/slide — always came
verbatim from the GP file, with no way to fix or add a note without
re-exporting from Guitar Pro. A new **"Editar notas" sync mode** (✏️) lets the
user click an existing note to edit or remove it, or click empty staff space
to insert a new one, directly in the browser.

**Genuinely per-arrangement, unlike `tone_changes`/`section_overrides`.**
`GpJobSpec.note_overrides: dict[str, list[NoteOverride]]` (`gp_pipeline.py`)
is keyed by `ArrangementKind.value` — Lead and Rhythm have entirely different
note content, so (unlike the job-level, shared-across-arrangements sections/
tone-changes convention) each kind's edit list is independent; an arrangement
absent from the dict (or with an empty list) is completely unaffected.
`NoteOverride(time, string, fret, sustain, techniques, bend_semitones,
slide_to_fret, deleted)` is a **patch keyed by `(time, string)`**: `deleted=
True` removes whatever note is at that exact slot, otherwise it upserts
(inserts if nothing was there, replaces if something was) — one primitive
covers add/edit/delete uniformly. `_apply_note_overrides` (pure) does the
merge; applied in `run()` **after** parsing, per-arrangement time-warp, tempo-
scale, AND the `import_mute_techniques` strip — so a manual edit is the final
say and is never silently stripped by that unrelated global checkbox. Times
are bundle-clock, same convention as `tone_changes`/`section_overrides` — the
editor places them directly on the already-warped score, no extra warp needed.

**Honest limit: still bound by the song's own tempo map.** `Arrangement.
validate()` already rejects a note past the arrangement's final ebeat
("note at Ns beyond final ebeat Ms") — a real, pre-existing invariant, not
new — so a note can only be added within the GP file's authored measure
range; extending the song itself still requires adding measures in Guitar
Pro first. Surfaced as a plain rebuild failure (`job.error`) if violated,
same as any other pipeline error.

**API**: `RebuildIn.note_overrides: dict[str, list[NoteOverrideIn]] | None =
None` (null-sentinel convention — `None` leaves `params["note_overrides"]`
untouched; a set dict, even `{}`, replaces it wholesale). `NoteOverrideIn`
Field-constrains `string` (0-5) and `fret`/`slide_to_fret` (0-24) so an
out-of-range value 422s immediately at rebuild time rather than surfacing as
a deferred build failure.

**Committed edits are SEEDED back into the viewer, or an unrelated rebuild
erases them.** `applyAll()` always sends the whole `note_overrides` dict and
`rebuild_job` REPLACES the stored value, so resetting the viewer's list to `{}`
on job load meant: edit notes → rebuild (stored) → reopen the job → change the
tuning → "Aplicar e reconstruir" sends `{}` → **every committed note edit is
silently gone**. `ArrangementOut.note_overrides` now returns each arrangement's
committed edits and `loadArrangements` seeds `noteOverridesByKind` from them, so
the always-send round-trip is lossless. `noteOverridesBuilt` (a JSON snapshot at
load) is what makes "Pendente" mean *changed since the build* rather than "this
job has note edits". Clearing them is then an explicit action — the "🧹 Limpar
edições" / "🧹 Limpar em todas" buttons — which sends the smaller dict and
genuinely removes them on the next rebuild. Guarded by
`test_committed_note_edits_survive_an_unrelated_rebuild`.

**Frontend**: `noteOverridesByKind` (state, per-kind, seeded on job load from the
committed edits) needs no dirty-flag/None-sentinel gymnastics the way
`section_overrides` does — like `tone_changes`, there's no prior non-user
default to lose (a note edit only ever originates from the user), so the
whole dict is simply sent every rebuild; an untouched job sends `{}`. A
single click on an existing note (in "Editar notas" mode) opens a small
floating popup (`#noteEditPopup`, styled like the bar-align popup) pre-filled
with its current fret/sustain/technique checkboxes/bend/slide-to; "Guardar"
upserts an override, "Remover nota" marks it deleted. **A single click on
EMPTY staff space still seeks (moves the playhead), same as every other
note-click mode — inserting a new note is a DOUBLE-click** (`svg`'s `dblclick`
handler). This is deliberate: an earlier version inserted on a single
empty-space click, which silently hijacked click-to-seek the moment the user
was in this mode ("não consigo clicar na partitura e o cursor mover-se") —
the one mode that broke the otherwise-universal "click empty space = move the
cursor" convention. The double-click insert defaults the string from the
click's Y position and the time from **`nearestGridChartTime`** — the nearest
sync-grid point (`snapGridTimes()`, the same bars/beats/subdivision grid
note-dragging already snaps to), found by forward-projecting each grid
candidate to display X and picking the closest, rather than inverting the
click position through the warp+tempo-scale chain (not cheaply invertible) —
so a new note always lands on a real chart time with no new coordinate
machinery.

**Preview merges visually without touching sync/playback.** `mergeNoteOverrides`
(pure, JS) is the client-side mirror of `_apply_note_overrides` — it's spliced
into `showArr`'s note-drawing loop only (chord grouping recomputed from the
merged set, so an edit that changes which notes are simultaneous updates the
chord bracket/shape correctly), while `dur` sizing, drag mechanics, and
synth/playback still read the untouched `a.notes` until an actual rebuild
bakes the edit in — a deliberate, low-risk scope: pending note edits are
visually accurate on the score but don't yet drive other machinery. A note
carrying a pending edit gets a dashed cyan ring (`.note-single[data-string]`,
added per-note so a specific note within a chord can be targeted precisely)
so it reads as "not yet rebuilt".

**Copy/paste ("📋 Copiar seleção" / "📥 Colar no cursor", Ctrl+C/Ctrl+V).**
Duplicates a selected excerpt elsewhere in the score — the same arrangement,
or a *different* one (e.g. copy a riff from Lead into Rhythm), without
re-entering it note by note. The two buttons live in their **own labelled
"Copiar/colar notas:" row** below the sync-mode buttons (not crammed into the
end of the 9-emoji mode row, where they were easy to miss when greyed-out).
`copySelectedNotes()` reads whichever notes are
currently in `selectedTimes` (the same selection Shift+click/Ctrl+click/
"Excerto" already populate) from the CURRENT arrangement's live
(`mergeNoteOverrides`-merged, so already-pending edits are copyable too) note
list, and normalizes each to a `dTime` offset from the earliest copied note —
`noteClipboard` is plain in-memory JS state, not the OS clipboard, so it's
session-only (cleared on a fresh job load, to avoid pasting one song's notes
into another). `pasteNotesAtCursor()` re-anchors the clipboard at the
playhead: only the FIRST copied note snaps to the sync grid
(`nearestGridChartTime`), and every other note keeps its original relative
spacing from it, so a copied riff's own rhythm survives the paste intact.
Each pasted note becomes an ordinary `note_overrides` upsert — no new
backend concept, it's a client-side composition over the same primitive the
single-note editor uses.

**The chart is sized to the whole song, not the last note.** `showArr`'s width
(`dur`) is the max of the last note end, the last bar/beat time, AND the
recording length (`waveDuration`) — NOT just `max(note.time)`. A track that
rests through the outro (e.g. a lead that stops at bar 120 of 146) still owns
all its bars in the grid, and the recording keeps playing; sizing to the last
note alone clipped those trailing (empty) bars and the waveform tail off the
right edge, making the track look shorter than the others ("o lead só aparece
até ao compasso 122"). All tracks now span the full song width.

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
per-syllable: `expand_to_words` splits line-level events (LRC) into one
`<vocal>` per word and appends `+` to the last word of each line — that
trailing `+` is what makes the in-game lyric display break to a new line.
UltraStar input is already per-syllable and is NOT re-expanded.

**GP-embedded lyrics surface in the editor.** GP-embedded lyrics used to be
written straight to the vocals XML at build time and never shown in the UI, so
they looked "missing". Now the GP build returns them on `PipelineResult.gp_lyrics`
(in the **recording clock** — `pipeline` subtracts `pad_start_s` so a rebuild
re-adds it cleanly), and the worker stores them in `params["lyrics_events"]`
when the user hasn't supplied their own — so they appear in the "Letras" editor
and on the tab viewer, editable. The melisma `_` marker (a syllable held over
several note attacks) extends the previous syllable's length instead of emitting
a new event.

**GP-embedded lyrics → per-syllable note alignment (`distribute_syllables`).**
A Guitar Pro file stores lyrics as a line of text per `startingMeasure`; the
per-syllable timing is *implicit* — GP/Songsterr distribute the syllables
across the note attacks (whitespace = word boundary, hyphen = syllable split
within a word: `loo-king a-way` → `loo`·`king`·`a`·`way`). `gp_pipeline`
replicates that: it takes the (already warped + offset) note onsets of the
chart (`sorted({n.time for n in first.notes})`) and places one syllable per
onset starting at each line's measure, so the words land on the actual notes
instead of an even spread. Rocksmith markers: a trailing `-` joins syllables
within a word (no space, hyphen shown in game), a trailing `+` on a line's last
syllable is the line break. Honest limit: it assumes **syllabic** singing (one
syllable per note attack); **melismas** (one syllable held over several notes)
are not recoverable from the GP text, so a melismatic passage drifts by the
number of extra notes until the next line resets it — supply an LRC/UltraStar
file or use the in-app editor for those. The in-app editor (`lyrics_events`)
and an LRC/UltraStar file both still take precedence over GP-embedded lyrics.

### Automatic lyric detection + in-app editor

`POST /jobs/{id}/detect-lyrics` runs `rockforge.detect_lyrics` (an async Celery
task, GP and audio-ML jobs both) — Demucs isolates the vocals stem and WhisperX
force-aligns it. Progress is tracked via `params["lyrics_status"]`
(`detecting`/`ready`/`empty`/`unavailable`), never `JobStatus`, so detection
never hides a completed bundle or disables `/arrangements`. Results land in
`params["lyrics_events"]` (JSON rows `{"time","length","lyric"}`), readable via
`GET /jobs/{id}/lyrics`.

**Line breaks.** WhisperX segments are whole sentences, so putting the `+` line
break only at segment ends made long segments scroll in-game as one wall of
text. `segments_to_vocal_events` splits each segment into short display lines
(`_break_into_lines`): a `+` on a sung pause (word gap > `LINE_BREAK_GAP_S`) or
every `LINE_MAX_WORDS` words. This is detection-only — LRC/UltraStar/GP-embedded
lyrics keep their authored line structure.

**Build-time line cap (`enforce_max_line_words`, `rsxml/vocals.py`).** The finer
breaking above only touches WhisperX *detection*. Both pipelines additionally run
every vocals list through `enforce_max_line_words` (cap `MAX_LINE_WORDS = 7`)
right before packaging, forcing a `+` once a line reaches the cap WITH NO break —
a safety net so lyrics from ANY source (old detection whose coarse `+`s are
already baked into `lyrics_events`, GP-embedded, a long-lined LRC) don't scroll
as a wall of text in-game **without needing a re-detect**. It never removes an
authored break, never breaks on a syllable-join `-` (mid-word) or on the last
event. Guarded by `test_enforce_max_line_words_*`.

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

**Subprocess isolation.** WhisperX transcription (and the `import whisperx`
availability check) runs in a **subprocess**, not inside the Celery worker.
faster-whisper / ctranslate2 has a known deadlock during CUDA initialisation
inside Celery child processes (faster-whisper #907, celery #3402) that hangs
the worker indefinitely at the import phase. The fix mirrors how Demucs already
runs — `_whisperx_runner.py` is spawned via `subprocess.run` with
`WHISPERX_TIMEOUT_S` (20 min, covers first-run model download + long songs).
The CUDA warm-up probe was removed entirely (two concurrent `cuInit()` calls —
warm-up thread vs first task — can deadlock on Windows); the first task pays the
one-time 30-60s CUDA init cost, and `@cache` avoids repeating it.

**Windows cuDNN DLL discovery (`_add_cuda_dll_dirs`).** ctranslate2 4.x crashes
natively (exit `0xC0000409`) when it can't load `cudnn_ops64_9.dll` /
`cublas64_12.dll` — and it can't even when a matching cuDNN 9 is installed, if
that copy only lives in `torch/lib` (the torch cu12x wheels bundle it there, but
that dir isn't on the Windows DLL search path). Before importing whisperx, the
runner adds torch's `lib` dir (and any standalone `nvidia-cudnn`/`nvidia-cublas`
pip packages) via `os.add_dll_directory`, so ctranslate2 resolves cuDNN/cuBLAS
instead of crashing. This is the fix for "GPU crashes even with torch cu121 (which
bundles cuDNN 9.1) + ctranslate2 4.4.0 (which needs cuDNN 9)". No-op off Windows;
guarded by `test_add_cuda_dll_dirs_is_noop_off_windows`.

**GPU crash → CPU fallback (WHOLE ML stack, not just WhisperX).** Both Demucs
(torch) and WhisperX (faster-whisper/ctranslate2) can crash natively on GPU
(e.g. exit `3221226505`/`0xC0000409` from a torch/cuDNN mismatch on Turing /
RTX 20-series cards) with no Python traceback. Two layers handle it:
- **In-run fallback.** Each GPU subprocess retries on CPU when a CUDA run
  crashes: `detect_lyrics`'s `_run_whisperx(dev)` (non-zero `cuda` exit →
  retry `cpu`, final failure raises with the stderr tail — don't restore
  `check=True`, it hides the stderr and kills the fallback), and
  `DemucsSeparator._run` (a `CalledProcessError` on a `cuda` device retries the
  same command on `cpu`; a *timeout* does NOT retry — no burning another 30 min).
  So the crashing run still completes.
- **Persisted marker degrades the whole stack.** The first crash drops a
  `work_dir/.gpu_ml_broken` marker (`_mark_cuda_broken`, wired into Demucs via
  `on_cuda_crash` in `_make_demucs` AND into the WhisperX fallback).
  `_resolve_device` consults it (`_cuda_known_broken`) and downgrades a resolved
  `cuda` to `cpu` — for **Demucs AND WhisperX**, in every task and the main
  build — so after ONE crash the flaky GPU is skipped everywhere instead of
  re-crashing each song. The legacy `.whisperx_cuda_broken` filename is still
  honoured so existing installs stay degraded. **The marker is a hidden dotfile
  in `work_dir` most users can't find, so the ⚙️ Definições modal surfaces its
  state ("GPU acelerada") + a "Reativar GPU" button** → `POST /gpu-reset`
  (`_clear_cuda_broken`, also clears the `_detect_device` cache so it takes
  effect without a restart). `SettingsOut.gpu_broken` carries the state.

**Making the GPU actually work — the escalation ladder + auto-persist.** The
float16 ctranslate2 path is the usual trigger of the Turing/cuDNN crash, so
`detect_lyrics` doesn't jump straight to CPU: `_whisperx_attempts(device,
configured)` builds a ladder — **cuda(configured/float16) → cuda(int8_float16)
→ cpu** — and the task runs each rung until one succeeds. `int8_float16` (lower
VRAM, more cuDNN-tolerant) often keeps the GPU working where float16 crashes.
Outcomes: if a non-default GPU compute type wins, it's **persisted to
`runtime_settings` (`whisperx_compute_type`)** so later runs skip the doomed
float16 attempt; if even int8_float16 crashes and it falls to CPU, the
GPU-broken marker is set (whole stack → CPU). The compute type is also settable
manually via `ROCKFORGE_WHISPERX_COMPUTE_TYPE` (env) — the runtime override
wins. Note it only affects the transcribe model — a torch-side cuDNN crash in
the wav2vec2 *alignment* step is unaffected, in which case the int8_float16 rung
also crashes and the CPU fallback is the answer. `_whisperx_attempts` guarded by
`test_whisperx_attempts_escalation_ladder`.

**Device selection (`_resolve_device`).** `demucs_device` defaults to `"auto"`:
`_detect_device` (deferred torch import, worker-only, `@cache`d) returns
`"cuda"` when `torch.cuda.is_available()` and `"cpu"` otherwise; explicit
`"cpu"`/`"cuda"` pass through — then `_resolve_device` downgrades any resolved
`"cuda"` to `"cpu"` when the GPU-broken marker is set. Any import/CUDA failure degrades to CPU, so
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

### The UI says when the server is gone (`getJSON` + the offline banner)

The app deliberately shuts itself down when the tab closes
(`ROCKFORGE_IDLE_SHUTDOWN_S`) and a machine can sleep, so the API really can
vanish while the page stays open. Several calls went `(await fetch(...)).json()`
with no check at all, so that threw an unhandled rejection and the action simply
did nothing — indistinguishable from a broken feature. `getJSON(url, opts)`
raises on a non-2xx (so a failure can never be mistaken for an empty result) and
flips a persistent `#serverOffline` banner on a network error, clearing it when
a request succeeds again. `selectJob`'s poll keeps retrying across a blip
instead of dying on the first failure, and a global `unhandledrejection`
listener toasts anything that still escapes. Browser-only, so there is no pytest
coverage: verified with Playwright against a live server — banner absent on load,
present once `/jobs` is routed to fail, gone again when it succeeds, no page
errors throughout.

### Web UI structure: `index.html` (markup) + `app.js` (script) + ESLint

The web UI's client-side script lives in **`web/app.js`**, not inline in
`web/index.html` — it used to be one ~4100-line inline `<script>` block, which
meant no linter could ever check it (ESLint parses files, not markup) and
every past JS change was verified only by `node --check` (syntax only) or by
hand. `index.html` now loads it via `<script src="/app.js"></script>`; the
FastAPI route `app_js()` (`interfaces/api/app.py`, alongside `index()`, both
now sharing `_web_file_candidates(name)`) serves it with a real
`text/javascript` content type, resolved the same repo-checkout-vs-installed
two-path lookup `_gear_image_dirs()` already used for gear images.

**`npm run lint`** (`eslint.config.js` at the repo root, scoped to
`web/app.js` only) is real-bug-focused — `no-undef`/`no-redeclare`/
`no-dupe-keys`/etc as errors, `no-unused-vars` as a warning rather than an
error (the file predates any lint config). It now reports **zero** problems:
the unused `catch (e)` bindings became bare `catch {}`, the genuinely dead
`clickSound()` was deleted, and `openMetaEdit` — a FALSE positive, reached from
an `onclick="…"` inside a template-literal string ESLint cannot trace — is
assigned to `window` explicitly, which is both what inline handlers actually
resolve against and honest about why it looked unused. It is **not** a stylistic
reformat/rewrite of the file — only real-bug rule categories are enabled, so
the existing code style is undisturbed. CI runs it as the `web-lint` job
(`.github/workflows/ci.yml`, Node 22 + `npm ci`), separate from the Python
`test` job. Run locally with `npm ci && npm run lint` (or a bare `eslint
web/app.js` if `eslint` is already on `PATH`); `node --check web/app.js`
remains a useful quick syntax-only sanity check but ESLint is the real gate
now. Verified the extraction preserves behavior: the full existing
`test_psarc_sng.py`-style discipline doesn't apply here (no pure-function
logic changed, it's a pure file-split), but the served page was driven with
Playwright (a real headless Chromium) confirming zero console/page errors and
that DOM wiring (e.g. `openNewJobModal`'s modal toggle) still works after the
split, plus two new API tests (`test_index_page_references_the_extracted_app_js`,
`test_app_js_is_served_with_a_javascript_content_type`).

The "Novo projeto" modal is a **4-step wizard** (`web/index.html`), not a flat
form, because the old single-form layout crammed ~15 fields (including a
`tone_base`/`tone_names` *text* box impossible to fill by hand) and gave no
guidance. Steps, each with a medium icon in a stepper header: **🎸 Ficheiro**
(pick the GP → inspect, which auto-assigns the first eligible track to Lead and
advances), **🎚️ Pistas** (assign Lead/Rhythm/Combo/Alt — needs ≥1), **💾
Gravação** (audio + approximate `offset_s`/`lead_in_s`; fine sync is deferred to
the tab viewer), **🏷️ Detalhes** (title/band/album/year, mutes, optional LRC).
The tone-base/tone-names text inputs were **removed** — tones are built
post-creation in the real tone editor. Step 1 is its own form (submit = inspect,
`/gp/inspect`); steps 2-4 share `gpJobForm` (submit = create, `/jobs/gp`). The
shared footer nav is `setWizardStep(n)` + `validateWizardStep()`; Enter on an
early step advances instead of creating (guarded in the submit handler).

### Batch processing (`📦 Processamento em lote`)

For an entire album: a second landing banner opens a batch modal
(`#batchOverlay`) that creates several GP jobs without repeating the wizard
per song. **Frontend-only — no new backend endpoint.** Each pair is created by
looping the exact same two calls the single-project wizard makes
(`POST /gp/inspect` → `POST /jobs/gp`), with the track fields left blank so
the pipeline's existing `auto_pick_tracks` name-heuristic fallback
(`gp_pipeline.py`, fires when every track slot is unassigned) fills in
Lead/Rhythm — the same thing that already happens for a lone-track GP in the
normal wizard. This keeps the batch path byte-for-byte the same code as
creating one job by hand; nothing new to guard in `pytest` (pure
`web/index.html`/`web/app.js`, same category as the other browser-only
sections in `TESTING.md`).

**Pairing (`pairBatchFiles`, pure, `web/app.js`).** The user picks multiple GP
files and multiple recordings; each GP file is matched to the recording
sharing its **filename stem** (case-insensitive, extension stripped — e.g.
`faixa1.gp5` ↔ `FAIXA1.wav`); any GP file left unmatched pairs with a leftover
recording **in the order both lists were chosen**, so an album where names
don't line up still gets a pair per song as long as the counts roughly match.
A GP file with no recording left at all shows "sem gravação — não vai ser
criado" in the preview list and is skipped on submit, never silently paired
with the wrong track. The preview list (`renderBatchPairs`) is the only
confirmation step — there is no per-pair track/metadata screen (that would be
the normal wizard, one song at a time).

Submission is **sequential**, one pair at a time (not `Promise.all`), so the
browser isn't uploading N recordings simultaneously; each pair's row updates
its own ⏳/✅/❌ status live. Album/artist/year fields in the modal are
**shared** across every pair (sent as the form fields on every `/jobs/gp`
call, same precedence rule the single-project endpoint already has — form
value beats the GP file beats the audio tags); title/artist otherwise come
from each song's own GP metadata or audio tags, exactly as for a single job.

**Honest limits:** the auto-pick heuristic is a name match ("lead"/"rhythm"
substrings), the same heuristic the single-project wizard falls back to and
already warns about (`"tracks auto-selected by name heuristic — confirm they
are the right ones"` in that job's warnings) — a wrong pick on an unusually
named track is fixed the same way as any other job: reopen it and use "✎
Editar info" to re-map tracks, which forks a rebuild. No dedicated track
review step exists for batch-created jobs; that's the whole point of skipping
per-song setup, and the completeness checklist plus that pre-existing warning
surface it rather than hiding it.

The **"Estado do PSARC" checklist** (`renderCompleteness`, rendered above the
download links on every completed job) reads completeness signals straight off
`JobOut` and surfaces what would leave the bundle incomplete/poor, each with a
jump-button to the right editor (`COMPLETE_ACTIONS`). Rows + alerts:
- ✅/❌ **PSARC jogável** ← `psarc_available` (❌ = no Wwise/.wem).
- ✅/⚠️ **Tons definidos** ← `has_tones` (new `JobOut` field = `params["tones"]`/
  `tone_base`/`tone_names` non-empty; else DLC Builder flags "tone missing").
- ✅/⚠️ **Capa** ← `cover_art` (else `albumArt` empty).
- ✅/⚠️ **Sincronização** ← `sync_edited` (new field; `_sync_edited(params)`:
  offset moved off 0, tempo scaled, or any drift anchor job-level/per-arrangement)
  — a **soft** "confirmaste a sincronização?" reminder, not a hard "desalinhado".
- ⓘ **Letra** ← `has_lyrics` (informational, never an alert). NOTE: read
  `has_lyrics` (new field: edited `lyrics_events` OR `lrc_text` OR
  `lyrics_status == "ready"`), NOT `lyrics_status` alone — GP-embedded / LRC /
  edited lyrics never set `lyrics_status="ready"` (that's WhisperX-detection
  only), so keying off it made a song WITH lyrics read "sem letra".
- ⓘ **AppID/propriedade** — informational: the `.psarc` reuses a specific DLC's
  appid the player must own (the #1 "não aparece no jogo" cause, otherwise
  invisible in the UI).

When any warn/err row exists, an amber banner over the downloads summarizes
what's missing. Nothing is blocked (honesty principle) — the user can still
download, but won't silently ship a tone-less/cover-less/unsynced PSARC.
`has_tones`/`sync_edited`/`has_lyrics` guarded by
`test_completeness_fields_reflect_job_state` /
`test_sync_edited_true_from_anchor_only` / `test_has_lyrics_true_from_edited_events`.

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
creating/updating the DLC Builder project (DLC Builder generates its own in-game
DDS textures on import).

**The native PSARC already ships the real cover as a game texture.**
`gamedata.album_art_dds(size, cover_path)` converts it to **DXT1** at 64/128/256
with Pillow (from the `[psarc]` extra) and the packer writes
`gfxassets/album_art/album_<key>_{64,128,256}.dds`; the manifest's `AlbumArt`
attribute carries `urn:image:dds:album_<key>` and the xblock's
`AlbumArtSmall`/`Medium`/`Large` point at it. Without Pillow, or with an
unreadable image, it degrades to the neutral solid placeholder rather than
failing the build — so the URN always resolves. Verified end to end by driving
the packer with a real image and decoding the DXT1 block colour back out of the
packed `.psarc`. (An earlier honesty note here claimed the opposite; it was
stale, and the recommendation built on it was wrong.)

The Song2014 XML's `<albumArt>` now carries the same URN
(`render_arrangement(arr, album_art_urn)`), which is **completeness for the DLC
Builder path only**: the game resolves the cover through the MANIFEST, and the
instrumental XML is not even shipped inside the `.psarc` (only
`<key>_showlights.xml` is). It stays empty when no key is supplied, so a direct
`write_arrangement_xml` call is unchanged.

### Automatic tone detection (`/jobs/{id}/detect-tones`)

`POST /jobs/{id}/detect-tones` (GP jobs) runs Demucs
guitar separation (`htdemucs_6s`) on the recording and analyzes the guitar
stem (`tone_analysis/analyzer.py`) to classify the tone into one of three
categories: `clean`, `crunch`, or `high_gain`. The classification drives a
preset suggestion: curated Lead + Rhythm tones from the Rocksmith gear catalogue
(real amp/cabinet/pedal keys with knob values) are proposed and stored in
`params["detected_tones"]`.

**Gain estimation (why it stopped reading "usually too clean").** The gain
estimate combines **brightness-independent distortion cues** — spectral
flatness (saturation packs the spectrum → higher) and dynamic compression via
the crest factor (distortion sustains/compresses → low crest) — with spectral
contrast and a low-weighted ZCR. Critically, the features are computed **only
over the frames where the guitar is actually playing loud** (RMS ≥ 30% of the
peak) after peak-normalizing, so silences, count-ins and clean breaks no longer
drag a mostly-distorted song down to `clean`. The old version averaged ZCR +
centroid over the WHOLE stem — both dominated by brightness — so a dark,
low-tuned or palm-muted high-gain tone was systematically under-read. The
crunch/high-gain boundary is `gain_level ≥ 0.5`; `flatness`/`compression` are
surfaced in the tone log and `detected_tones.profile` for transparency. Still a
heuristic — the character, not the actual amp.

Progress is tracked via `params["tone_detection_status"]`
(`detecting`/`normalizing`/`separating`/`analyzing`/`ready`/`unavailable`),
never `JobStatus`. The web UI's "Detetar tom" button triggers detection and
polls `GET /jobs/{id}/detected-tones` for the result; "Aplicar melhores"
loads the top presets into the tone editor so the user confirms/adjusts, then
"Aplicar e reconstruir" commits them.

**Ranked candidates, not one guess (`rank_tones`).** The old path mapped the
detected category 1:1 to a single Lead+Rhythm preset (`suggest_tones`), so when
the guess was off the user had nothing to browse ("dificuldade em encontrar os
tons semelhantes"). `tone_presets.rank_tones(gain, bright, low, category)` now
ranks the WHOLE curated library (`_LEAD_LIBRARY`/`_RHYTHM_LIBRARY`, several
presets spanning the gain axis with brightness/low-end variants, each carrying a
`(gain, bright, low)` fingerprint) by a **weighted distance** to the analyzer's
`ToneProfile` — gain dominates (`_W_GAIN=2.2` vs brightness/low `1.0/0.9`), each
candidate annotated with a 0-100 `match`. The worker stores `lead_candidates` /
`rhythm_candidates` (closest first) plus the detected `profile` in
`params["detected_tones"]`; `/detected-tones` returns them and the tab viewer
renders the profile bars + two ranked lists, each candidate with its `match %`
and a "usar" button that loads only that role's tone (Lead/Rhythm replaced
independently). `suggest_tones` is kept for the legacy one-per-category callers/
tests. Honesty unchanged: this proposes plausible catalogue matches by
character, it does NOT identify the real amp.

Honesty note: spectral analysis does NOT identify the actual amp/pedal used in
the recording — it classifies the *character* of the guitar sound and suggests
a plausible Rocksmith gear match. Detection needs the `[ml]` extra (Demucs +
librosa).

### Tone editor: rotary knobs + optional local gear images

Gear knobs (amp/effect Gain/Bass/Mid/…) render as **draggable rotary dials**
(`renderKnobs`/`wireKnob`, `web/index.html`): drag the dial (−135°..+135° sweep),
type the exact value, or double-click to reset to the catalogue default. The
value still lives in an `input[data-knob]` so `readKnobs` and the tone model are
unchanged — purely a UX layer. Each amp/cabinet **and every effect (pre-pedal,
post-pedal, rack)** can also show a **gear picture**: `GET /gear-image/{key}`
serves `<key>.<ext>` looking first in `work_dir/gear_images/` (the RUNTIME
override — the user drops their own photos there, named by the gear key, without
committing) then the **bundled `web/gear_images/`** shipped in the repo
(`_gear_image_dirs`, resolved the same way `index()` finds the web UI), so a
fresh install has art out of the box and a user file of the same key still wins.
The key is sanitised to a bare slug against path traversal. RockForge ships its
own hand-drawn rack faces there (`Rack_StudioCompressor`, `Rack_StudioGraphicEQ`,
`Rack_StudioEQ`, `Rack_TapeEcho`, `Rack_StudioPlate`, `Rack_StudioChamber`) — the
repo art is the user's OWN (no brand/Ubisoft assets committed).

**Two layouts, chosen by whether a REAL picture loads (`applyGearImageEl`).** A
real photo (user or bundled) already has its own knobs drawn on it, so overlaying
functional knobs would double them; when the `<img>` `onload`s a real image the
panel gets `.gear-photo` and switches to a **stacked** layout — picture on top
(shown whole, full opacity) with the functional rotary knobs BELOW it. The
knob-less generic SVG faceplate (`genericGearSvg`: amp head / speaker cab /
stompbox — our own art) keeps the **overlay** layout (knobs `.knob-face` sit on
the `.gear-bg` backdrop), so the knobs shown are always exactly the gear's own
controls — however many (3, 5, 8…). Effects pass `photoOnly=true`: with no real
image they show NOTHING (not the generic pedal SVG, which HAS drawn knobs that
would clash) — just the plain gradient knob strip; a real rack photo switches
that row to the stacked layout. `renderKnobs` hides an empty container so a
knob-less gear shows no empty bar. Honesty unchanged: this is visual only —
RockForge does not model the amp sound (the real tone comes from the gear keys
in-game / DLC Builder). Guarded by `test_gear_image_serves_local_file_or_404` /
`test_gear_image_falls_back_to_bundled_and_workdir_wins`.

### Tone preview on the score (`voiceNote` / "Testar tom")

The tab viewer's **"🎸 Testar tom" dropdown** lets the user audition a **created
tone**'s *character* on the note playback — both the per-note tick and the
"sintetizada" audio source route through the same `voiceNote(ctx, dest, hz, t0,
dur, peak, char)` voice — a **plucked-string (Karplus-Strong) note**
(`karplusBuffer`) through an optional waveshaper (drive) and a **shared cabinet
EQ** (`getCabinet`: low-mid body bump + mid scoop + 4 kHz speaker roll-off, one
per audio context), a far more guitar-like simulation than the old oscillators.
The selector is **disabled until the user creates a tone** (nothing to preview). With tones, it offers **"Seguir partitura"**
(`'__follow__'`) — the character follows the tones marked on the score, switching
per note via `activeToneKeyAt(chartTime)` (the last `toneChanges` entry at/before
that time, else `toneBase`; both share the chart timeline) — plus each tone to
audition alone. `toneCharForNote(chartTime)` resolves the per-note character, so
a chart with several tone changes mirrors each of them. It defaults to following
the score when tones are marked, unless the user picks otherwise
(`previewToneTouched`).

**On-score tone identification.** The active tone is shown on the tab viewer: an
amber 🎸 label per tone change (plus the base tone at the start,
`activeToneKeyAtDisplay`) and a live `#liveTone` label next to the BPM
(`updateLiveTone`, called from `updateLiveBpm`). `toneCharacter` derives `drive`
from the descriptor category refined by the amp's actual **Gain knob**
(continuous blend) + drive pedals, and `bright` from the amp's **treble/bass/
presence** knobs — so two tones of the same category still differ *if their gear
differs*. Two tones with identical settings sound identical (correct, not a bug). With no tone selected (`previewToneKey === ''`) it's the
plain oscillator pluck (sawtooth+triangle → lowpass); with one, `char =
{drive, bright}` from `toneCharacter(tone)` inserts a **WaveShaper** (drive) and
shifts the lowpass cutoff (brightness), plus a little makeup gain (distortion
compresses level). `toneCharacter` derives `drive` from the tone's **descriptors**
(CLEAN/CRUNCH/OVERDRIVE/DISTORTION/HIGH GAIN), its amp **Gain knob**, and any
drive/dist/fuzz **pedals**; `bright` from LEAD/BASS. Both the live tick
(`playNote`) and the offline render (`synthesizeArrangement`) call `voiceNote`,
so a synth source re-renders when the preview tone changes. `populatePreviewTones`
(called from `renderTonePanel`) keeps the selector in sync with `jobTones`.

Honesty note (surfaced in the "Testar tom" ⓘ): RockForge does **not** model amps
— this is a **character approximation** (gain/distortion + brightness), NOT the
real amp/cabinet sound. The true tone only exists in-game / DLC Builder, which
generates the audio from the gear keys we serialize into the bundle.

### Stem separation — selectable audio source (`/jobs/{id}/separate-stems`)

The tab viewer's **"Fonte de áudio" dropdown** (`populateAudioSources`) offers
three kinds of audio source, all decoded into the same `playBuffer` (which
shares the recording's clock, so the notes stay aligned):

1. **Mistura completa** — the original recording (`/source-audio`).
2. **`<Kind>` (sintetizada)** — a clean synthesized reference of ONE
   arrangement's notes, generated **in-browser** (`synthesizeArrangement`, an
   `OfflineAudioContext` render using the same oscillator voice as the per-note
   tick). No Demucs, always available. Each note is placed at the exact
   recording-clock position it's drawn at — `warp((t-scoreShift)*ratio+pad) -
   viewOrigin` for GP (parameterized by that arrangement's *own* pending
   `tempo_scale`/anchors from `tempoScaleByKind`/`syncAnchorsByKind`, so it's
   correct regardless of the open tab), raw `t` for audio-ML. It reflects the
   pending sync at selection time; re-pick to refresh after more edits. This is
   the honest answer to "isolate each guitar": the two guitars can't be split
   from the *recording*, but each arrangement's notes CAN be rendered alone.
3. **Separated stems** — `POST /jobs/{id}/separate-stems` runs ONE Demucs
   `htdemucs_6s` pass and keeps the stems it produces (`separate_stems` globs
   the output dir), **minus `drums`** (dropped in the task — noise for
   sync-checking a guitar part), storing `params["stems"] = {name: abs_path}`.
   Same async pattern as `detect_tones`: progress in `params["stems_status"]`
   (`detecting`/`normalizing`/`separating`/`ready`/`unavailable`) +
   `params["stems_log"]`, endpoint mutates the job → 202, heavy failure wrapped
   → `unavailable`. `GET /jobs/{id}/stems` returns the status + the names whose
   file still exists on disk; `GET /jobs/{id}/stem/{name}` serves the WAV.

**`detect_tones` and `separate_stems` (demucs backend) share one guitar-stem
cache.** Both run the exact same `htdemucs_6s` pass over the same normalized
recording, so running one after the other used to pay for Demucs twice —
several redundant minutes. `celery_app._demucs_stems_cache_dir(job_id)` points
both tasks' normalization output and `DemucsSeparator` workdir at the same
`work_dir/<job_id>/demucs_stems`, and `DemucsSeparator.separate_guitar` checks
for an existing `guitar.wav` before invoking the subprocess (htdemucs_6s writes
every source in one pass, so its presence means a full separation already ran)
— whichever task runs second reuses it instantly instead of recomputing.
`has_cached_guitar_stem` lets each task log "reusing an already-separated
guitar stem" instead of the normal "separating…" message when this happens.
Banquet (`separate_stems`' experimental backend) keeps its own `stem_separation`
workdir — its query-based, per-clip output isn't compatible with the shared
htdemucs_6s cache. Guarded by
`test_separate_guitar_reuses_an_existing_stem_without_rerunning` /
`test_separate_stems_reuses_a_guitar_stem_from_a_prior_separate_guitar_call`.

`decodeWaveform` branches on `audioSourceName`: `synth:<kind>` → synthesize,
else fetch `/stem/{name}` or `/source-audio`. Changing the dropdown re-decodes
and restores the playhead; `loadStems` repopulates the selector on reopen (synth
options always; stems if already computed) without re-running Demucs.

**`initSync` resets `audioSourceName` SYNCHRONOUSLY, before firing
`decodeWaveform`/`loadStems`.** Both are async and neither is awaited, so they
run concurrently; `loadStems` also resets `audioSourceName` to `''` once its
own fetch resolves. Without the synchronous reset, a stale `audioSourceName`
left over from a *previous* job (e.g. `"synth:Lead"`, still set from before
the user switched jobs) could still be in effect when `decodeWaveform` reads
it, decoding a synthesized buffer into `playBuffer`; `loadStems` then resets
the dropdown back to "Mistura completa" *without re-decoding*, leaving the
synth buffer silently playing under a selector that reads the full mix — the
"dá música sintetizada mas a seleção está em mistura" bug. `initSync` now
sets `audioSourceName = ''` and the `#audioSource` select's value before
either async call starts, closing the race regardless of which one resolves
first.

Honest limit (surfaced in the "Fonte de áudio" ⓘ and the done log): Demucs
separates by **instrument type**, not by individual track — the `guitar` stem is
ALL guitars mixed together; **Lead vs Rhythm cannot be split** from the
recording (the per-arrangement *synthesized* source is the workaround). Stem
separation needs the `[ml]` extra (Demucs) and takes minutes; the synthesized
source needs neither.

**Selectable separator backend (`ROCKFORGE_STEM_SEPARATOR`).** The `separate_stems`
task picks its adapter via `celery_app._build_stem_separator()`: `"demucs"`
(default, `htdemucs_6s`) or `"banquet"` (EXPERIMENTAL / IN TESTING —
`BanquetSeparator`, `infrastructure/separation/banquet_adapter.py`). Banquet
(query-bandit, MIT, MoisesDB-trained) is **query-based**: it shells out to the
repo's `train.py inference_byoq` once per `<class>.wav` reference clip in
`ROCKFORGE_BANQUET_QUERIES`, producing one finer stem per clip (electric vs
acoustic, clean vs distorted) — needs `ROCKFORGE_BANQUET_REPO`/`_CKPT`/`_QUERIES`
set (see TESTING.md §7g). Same fundamental limit holds: two guitars of the SAME
class stay inseparable. Command-construction is unit-tested
(`test_banquet_adapter.py`); the model never runs in CI.

**In-app settings (`runtime_settings.py` + `/settings`).** The separator backend
and Banquet paths are editable from the web UI's **"⚙️ Definições"** modal, not
only via env vars. `runtime_settings` persists them to `work_dir/settings.json`
(atomic write) and both the API and the Celery worker read it — an override wins
over the env `Settings`, empty string clears it back to the env default. `GET
/settings` returns the effective values plus per-path readiness (`banquet_validation`:
`repo_ok`/`ckpt_ok`/`queries_ok`/`query_names`/`ready`) so the modal shows ✓/✗;
`POST /settings` saves. `_build_stem_separator()` reads `runtime_settings`, so a
change takes effect on the next `separate_stems` run with no restart. Guarded by
`test_settings.py`.

### Tone library (`tone_library.py` + `/tone-library`)

A tone dialled in one project's tone editor can be saved to a **cross-project
library** and reloaded into any other song, so an amp/cabinet/pedal chain isn't
rebuilt per file (like DLC Builder's tone library). Persistence mirrors
`runtime_settings`: a shared `work_dir/tone_library.json` (a list of the same
tone dicts `Job.params["tones"]` holds), atomic writes. `GET /tone-library`
lists; `POST /tone-library` upserts one tone **by its key** (validated to carry a
real amp+cabinet via `tone_from_dict`, else 422); `DELETE /tone-library/{key}`
removes. The tone builder's "Biblioteca" block loads (⬇) / deletes (🗑) and
"★ Biblioteca" saves the tone in edit. **Loading copies into the project**
(suffixing a clashing key) so it's editable locally and never clobbers the
library original, and the project's own tone edits never write back to the
library unless explicitly saved. Guarded by `test_tone_library.py`.

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

**Alternate arrangements.** `ArrangementKind` also has `ALTERNATE_LEAD` /
`ALTERNATE_RHYTHM` — a SECOND Lead/Rhythm chart (from another GP track) the
player can pick in game. They `.base_kind` onto Lead/Rhythm for every format
detail (ArrangementName, RouteMask, ArrangementType, path flags, `<arrangement>`
tag) but are **non-representative**: `Representative=0`, `represent=0`,
`bonusArr=1`, a distinct persistent/master ID, a `lead2`/`rhythm2` asset stem,
and a unique xblock entity name (`…_Lead2`) while the manifest `FullName` stays
`…_Lead`. This is byte-for-byte how a decoded DLC Builder CDLC (Animals As
Leaders "Tempting Time") encodes its `lead`+`lead2`. Selected via
`GpJobSpec.alt_lead_track`/`alt_rhythm_track` (the "Pista Lead/Rhythm
alternativo" selectors); the `.rs2dlc` marks them `Priority=Bonus` (2).

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
notes), ChordNotes, Vocals (+ symbol stubs if present), PhraseIterations, 3 ×
empty (PhraseExtraInfo/NLD/Actions), **Events** (the stage/crowd cues — see
finding D in the DD section), 2 × empty (Tones/DNAs), Sections,
ArrangementLevels (anchors, **anchor extensions**, notes with NextIter/PrevIter
linkage), Metadata. `NoteMask` values are the real Rocksmith constants (ported
from Constants.cs).

**`from_arrangement` is an orchestrator over named stage helpers, not one
452-line function.** Each `# --- Section ---` block from the original single
function is its own module-level `_build_*` helper — `_build_beats`/
`_assign_beat_phrase_iterations`, `_prepare_sections`, `_link_phrases`,
`_build_chord_data`, `_build_sng_notes`, `_build_sng_sections`,
`_build_difficulty_levels`, `_build_sng_metadata` — called in sequence,
threading the same intermediate values (beats, phrase_iterations, sng_notes,
…) that the inline code used to share as locals. Pure extract-function: no
logic changed, verified by the full existing `test_psarc_sng.py` suite passing
unchanged plus two new tests exercising `_build_chord_data`/`_build_sng_notes`
directly (`test_build_chord_data_is_independently_callable`,
`test_build_sng_notes_is_independently_callable`) — each confirmed to fail
with the reverted logic before restoring it. Keep new stages as separate
`_build_*` helpers rather than growing `from_arrangement` itself; the binary
layout is delicate enough (see the crash-history notes throughout this
section) that a stage should stay independently readable and testable.

**`CapoFret` is 255 when there is no capo, NOT 0.** Same sentinel pattern as the
two below — 0 is a real value (a capo AT fret 0) where the format wants
"absent". Found by byte-diffing a DLC Builder build of the same song. Unlike the
two below, the in-game consequence is UNPROVEN: it was fixed because the value
was plainly wrong and the pattern identical, not because a symptom was traced
to it.

**A chord template's unused strings carry MIDI note -1, NOT 0.** The per-string
`Notes` of a template are dereferenced by the game's note-detection/scoring
path, so writing 0 (a real, absurdly low pitch on a string that shouldn't
sound) crashed the game at the entry of a gapped 5/7 octave — but ONLY while
the player was actually playing/scoring that chord; a hands-off run never
touched the field, which made the crash look intermittent ("fragile"). Isolated
by byte-diffing our native "Free" against a DLC Builder build of the same song:
its 5/7 octave template is `[-1, 50, -1, 62, -1, -1]` where ours was
`[0, 50, 0, 62, 0, 0]` — the only difference on that chord. Guarded by
`test_chord_template_notes_are_real_midi`.

**Fingerprints (handshapes) are deliberately NOT emitted** (empty on every
level). Both working references ship zero — a real CDLC SNG (decoded: 0
fingerprints across all 23 levels) and a DLC Builder build of our own XML (which
carries `handShapes count="0"`) — while our one-fingerprint-per-chord emission
(dozens of back-to-back handshapes, including gapped octave shapes) crashed the
game at the entry of a dense 5-7 octave riff. Chords render via their chord
template + CHORD/STRUM masks; notes carry `fingerprint_id = (-1, -1)`. Guarded by
`test_chords_produce_templates_and_no_fingerprints` /
`test_dd_levels_have_no_handshapes_and_per_level_slide_extensions`.

**Repeated chords are marked HIGH DENSITY (condensed rendering).** A fast
repeated identical chord — an 8th-note power-chord chug, say — must carry
`NOTE_MASK_HIGHDENSITY` on every hit AFTER the first, so the game draws it
condensed (a small strum marker) instead of a full chord box. Emitting them all
as full boxes (the old behaviour: the constant was defined but never applied)
stacks the sprites into a **corrupt lateral highway blur** on a dense chug — a
graphical glitch, NOT a sustain trail (which is longitudinal). The DLC Builder
path never showed it because its DDC pass recomputes high density; only the
native SNG (no DDC) was affected. `high_density_flags` (pure, in
`domain/music.py`) marks a chord high-density when it repeats the previous
chord's exact shape within `HIGH_DENSITY_MAX_GAP_S` (0.35 s) — the first hit of a
run stays low density so its shape is still shown, and a shape change or a wider
gap starts a fresh run. Applied in BOTH the native SNG (`sng.from_arrangement`)
and the XML writer (`writer.py`, `highDensity="1"`; DDC overrides it there but
the two paths stay consistent). Guarded by
`test_repeated_chords_marked_high_density_but_not_the_first` (SNG) /
`test_repeated_chords_get_high_density` (XML).

**Every SUSTAINED chord gets a ChordNotes entry, not just technique chords.**
A chord's per-string SUSTAIN lives in its ChordNotes entry, NOT in the chord
template (which only carries frets/fingers/MIDI). Emitting ChordNotes only for
chords with a bend/slide/vibrato/palm-mute technique (the old rule) left a
plain sustained power-chord chug with `chord_notes_id = -1`, so the game had no
per-string sustain to render and drew **corrupt vertical/lateral bars** on the
highway — visible only while streaming notes in Riff Repeater / when scrubbing
the position (the two guitars' Lead single-notes were fine; only the Rhythm
chords glitched). Byte-diffing a DLC Builder build of the same song is
conclusive: every one of its ChordNotes entries carries the per-string SUSTAIN
bit (`0x2000`), and several carry ONLY sustain (no technique) — DLC Builder
emits one for every sustained chord. `from_arrangement` now emits a ChordNotes
entry whenever any string sustains OR carries a technique; `_note_mask` already
yields `SUSTAIN|OPEN|PALMMUTE` per string, reproducing DLC Builder's
`0x2000/0x2004/0x2040/0x2044` masks exactly. Found by decrypting a real user
PSARC (AES-CFB TOC + AES-CTR SNG via `pycryptodome`) and comparing the
ChordNotes section directly. **Confirmed fixed in-game** — the corrupt bars are
gone on the native PSARC. Guarded by
`test_sustained_chord_gets_chord_notes_with_per_string_sustain`.

> **Debugging method that cracked this (reusable).** Several native-SNG highway
> glitches were mis-diagnosed by reasoning about our data alone (a symptom that
> *changes as you scrub the score in Riff Repeater, at a fixed DD level*, is the
> game misreading per-note geometry it streams — not a Dynamic Difficulty
> problem). What actually isolated it: get BOTH a native RockForge `.psarc` AND a
> DLC Builder rebuild of the SAME song from the user, **decrypt each** (PSARC TOC
> = AES-256-CFB, SNG payload = AES-256-CTR of a zlib blob — `pycryptodome` works
> in-sandbox where the `cryptography` pyo3 wheel panics), and **byte-diff the SNG
> section counts + struct fields**. The DLC Builder build is the ground truth; the
> first field that differs is the bug. Here it was ChordNotes (9 vs 3 entries).
> Reach for this before speculating whenever a native-only rendering glitch
> resists static analysis.

Anchors never span a phrase-iteration boundary: the game re-anchors at each
phrase start, so a phrase whose opening notes are covered only by the previous
phrase's anchor finds none of its own and crashes on entry (seen exactly at a
section / tone-change boundary). `from_arrangement` splits any anchor that
crosses a boundary into per-phrase pieces (same hand position, re-tagged with the
phrase iteration), so every phrase owns an anchor at its start. Guarded by
`test_anchors_do_not_cross_phrase_iteration_boundaries`.

**A song-start anchor before the first phrase must not wrap onto the LAST
phrase.** `_build_anchors` always starts the very first anchor at absolute
`0.0` (so the opening notes are framed before they reach the strike line) —
but when the beat grid itself starts after `0.0` (a GP lead-in pad, the usual
case), that leaves a real gap `[0.0, first_phrase.start_time)` with no phrase
covering it. `_find_phrase_iteration`'s "not found" fallback returned
`len(phrase_iterations) - 1` unconditionally — correct for a time genuinely
PAST the song's end, but wrong for a time BEFORE its start: it wrapped the
song-opening anchor (and any beat in that same gap) onto a phrase near the
SONG'S END (index 26 on a real chart), corrupting the fret-hand anchor box
with a context from the wrong end of the song — the reported "graphical
glitch"/corrupt highway sprite right at the arrangement's first notes.
`_find_phrase_iteration` now special-cases a time before the first iteration's
start to return index 0. Found by decoding a real user PSARC (AES-CFB TOC +
AES-CTR SNG, both `pycryptodome`-compatible without the sandboxed
`cryptography` package) and confirming the corrupted `phrase_iteration_id`
directly. Guarded by `test_find_phrase_iteration_before_first_start_returns_first_index`
/ `test_song_start_anchor_has_correct_phrase_iteration_not_the_last`.

Anchor extensions are generated one per sliding note (`BeatTime = time +
sustain`, `FretId = slideTo`), so the fretboard re-anchors where the slide lands
(Rocksmith2014.NET `AnchorExtension.fs`, 12-byte layout). Vocals are emitted as
a **separate `<key>_vocals.sng`** arrangement (same Sng2014 container, only the
Vocals section populated) with its own `Vocals` manifest entry — not embedded in
an instrument SNG (which the game would not read as vocals). `sng.from_vocals`
builds that vocals-only model. Each `SngVocal.note` is the non-pitched sentinel
**`VOCAL_NOTE = 254`**, NOT 0 — 254 is Rocksmith's "scroll lyric, no karaoke
pitch" marker (a DLC Builder vocals SNG writes 254; note 0 is a real, absurdly
low MIDI pitch that the game fails to render as a scrolling lyric, so the letra
silently never appears even though the arrangement/manifest/xblock are all
present — isolated by byte-diffing our native "Pride" against a DLC Builder
build). Guarded by `test_vocals_note_is_non_pitched_sentinel`.

The vocals SNG also embeds the **lyric-font glyph atlas** — the Symbols sections
(`SymbolsHeader`=2, `SymbolsTexture`=1, `SymbolsDefinition`=192) that map each
character to a rectangle in the font texture. Writing these **empty** (the old
behaviour) leaves the game with no glyphs to draw, so the letra silently never
appears *even with note 254 and a fully-registered arrangement* — the second
half of the same "Pride" bug. The atlas is **song-independent**: it is the
default Latin font referencing the built-in game asset
`assets\ui\lyrics\lyrics.dds` (NOT packed in the PSARC), and is byte-identical
across DLC Builder builds (md5-equal between a DLC Builder "Free" and "Pride"
vocals SNG). It is vendored verbatim as
`packaging/psarc/vocals_symbols.bin` (the SymbolsHeader+Texture+Definition byte
blob, counts included) and spliced in by `write_sng` for every vocals SNG;
`read_sng` skips the populated entries by their fixed sizes (32 / 144 / 44
bytes). Rebuilding DLC Builder's own 324 "Pride" syllables through
`from_vocals` reproduces its vocals + symbol block exactly. Guarded by
`test_vocals_sng_carries_the_lyric_font_symbol_atlas` /
`test_instrument_sng_has_no_vocals_symbol_block`.

What is intentionally absent (these are correct given the domain model, not
defects):
- **Simplified DDC (Dynamic Difficulty)** — **working in game as of
  2026-08-25** (it ramps and the level persists; see the resolution note at the
  end of this section). `from_arrangement` emits several
  `ArrangementLevels` shaped like a real DDC pass (verified by decoding a DLC
  Builder reference SNG: 23 levels, per-phrase ceilings graduated by density,
  per-iteration hero triples of ~(¼,½,1)·max). Each **phrase's** ceiling scales
  with the note count of its BUSIEST iteration (`phrase_max = min(_DD_LEVEL_CAP,
  busiest-1)`), so each phrase's difficulty bar gets its own HEIGHT instead of a
  flat top: `phrase_max = min(_DD_LEVEL_CAP, max(min(_DD_MIN_LEVELS, busiest-1),
  (busiest-1)//_NOTES_PER_DD_LEVEL))`, and a phrase with NO notes stays 0. The
  cap is a HARD clamp (not a proportional rescale): it preserves the natural
  spread of most phrases and only flattens the handful of extreme-density
  outliers (a fast tapping run can hit 50-70 notes/iteration) at the top. The
  song's `max_difficulty` is the max over phrases, and there are
  `max_difficulty + 1` levels (up to 23).

  **The constants are calibrated against a DLC Builder build of the user's own
  song** (both `.psarc`s decoded and byte-diffed — see the debugging-method note
  above). Two defects showed up directly in that diff and drove the reported "DD
  never leaves the minimum, even set to maximum":
  - `_DD_MIN_LEVELS = 4` (new). The ceiling was a bare `(busiest-1)//group`, so a
    SHORT phrase got **zero** levels — one level, nothing to be promoted to,
    permanently pinned at the minimum however well it was played. The reference
    gives every phrase that has notes a ceiling of at least 4 (its own 3-note
    phrase gets exactly 4). On the user's song this was 1 phrase at 0 and 5 at
    ≤2 out of 27; now 0 and 1. The floor is bounded by `busiest-1` so a one-note
    phrase does not get five identical levels, which would be no ramp either.
  - `_NOTES_PER_DD_LEVEL` 3 → 2 and `_DD_LEVEL_CAP` 20 → 22. The reference's
    ceilings run about twice ours for the same note count (a 30-note phrase: 16
    there, 9 here; 63 notes: 22 there, 20 here), so the whole ramp read lower
    than a real DDC's. On the user's song the song max now comes out 22 —
    exactly the reference's.

  **Unverified in-game.** This removes phrases that provably cannot level up and
  puts the ramp's shape in the reference's range; whether it is the whole of the
  reported symptom is not proven. The same byte-diff found further gaps that are
  NOT fixed and are candidates if it persists: the manifest `Techniques` map is
  `{}` (the reference fills `{level: {phraseIteration: [ids]}}` — a game-internal
  enum we have not mapped); the SNG note `Hash` is 0 and `NoteFlags`' numbered
  bit is never set (the reference writes both); our `Levels` REPEATED a saturated
  phrase's notes at every higher level instead of dropping it to zero once past
  its ceiling (**since fixed** — see B below); and the crowd/stage Events
  (`e2`/`E3`/`E13`/`D3`) are absent.

  **Phrase names are now unique (`p0`…`pN`) — the one SONG-SPECIFIC divergence
  found.** They used to be the section name repeated, and a GP with no section
  markers is auto-segmented into spans all called `riff`, so this song shipped
  **27 phrases sharing one name** where the reference has 20, all distinct. That
  shape matters: the user reports DD working on a DIFFERENT song and failing on
  this one, and a GP that DOES carry markers already produced varied names — so
  the symptom follows the song, not the build, and this is the only difference
  that behaves that way. `_phrase_name` keeps `COUNT`/`END`/`NOGUITAR` verbatim
  (the reference does too) and numbers the rest; the descriptive names stay on
  the SECTIONS, a separate list — again matching the reference, whose sections
  are `riff`/`noguitar` while its phrases are `p0`…`p16`. Unverified in-game.

  **The per-phrase ceiling is NOT the variable — established by elimination, so
  do not tune it again hoping to fix DD.** Git bisect over a fixed synthetic
  arrangement shows the DD output byte-identical from `5b975a7` (2026-07-11)
  through `aa09665` (2026-07-17) — the July 13 refactor batch (`from_arrangement`
  decomposition, the phrase-iteration bisect, the de-quadratic linking, the
  build-the-model-once packer change) altered nothing — and there are NO commits
  at all between 2026-07-17 and 2026-08-21. The ramp has now been shipped at
  three settings and the symptom appeared under all three: one level per note
  (cap 20, the July build), one per three notes (`0182312`), and one per two with
  a floor of 4 (`3c596f9`). Whatever pins the in-game difficulty is not the
  ceiling arithmetic.

  **The ceiling recalibration did NOT fix it.** A REBUILT PSARC was decoded and
  confirmed to carry it (23 levels, max 22, no phrase-with-notes left at ceiling
  0) and the in-game difficulty still sat at the minimum. So the ceilings were
  not the cause and every candidate above is still open. Two things were ruled
  OUT along the way and must not be re-investigated: `PersistentID` and
  `MasterID_RDV` are byte-identical across rebuilds (the game is NOT seeing each
  build as a new song and losing its progress), and `DynamicVisualDensity` is a
  fixed 20-element constant in both files, unrelated to `MaxPhraseDifficulty`.
  **The user ran the decisive experiment (2026-08-25): the DLC Builder build of
  the SAME song DOES ramp.** So the cause IS in our file, and the search space
  is halved. Byte-diffing that working build against our `.psarc` of the same
  song (the method above) leaves exactly these differences, all confirmed:

  | # | difference | status |
  |---|---|---|
  | A | 27 phrases all named `riff` vs `COUNT`/`p0`…`p16`/`NOGUITAR`/`END` | fixed (`_phrase_name`), unverified in game |
  | B | a saturated phrase never left the levels above its ceiling | **fixed below** |
  | C | manifest `Techniques` is `{}` vs 23 populated levels | **partly fixed** (5 derived ids) |
  | D | SNG `Events` empty vs `e2`/`E3`/`E13`/`D3`/`E13` | **fixed** |
  | E | `SongDiffEasy`/`Med`/`Hard` one value written three times | **fixed** (formula below) |
  | F | note `Hash` always 0, `NoteFlags` never sets its bit | **not fixable** — see below |
  | G | manifest `LastConversionDateTime` missing entirely | **fixed** (constant) |
  | H | raw `UIName`, a `COUNT` section, repeated section `Number`s | **fixed** |

  Two candidates were **eliminated** by that same diff and must not be
  re-investigated. The note `Hash` is NOT a stable cross-level note identity —
  the same `(time, string, fret)` carries different hashes at different levels
  in the reference (281 of 752 notes), and there are 1081 distinct hashes over
  6018 note instances, so zeroing it cannot be collapsing a per-note identity
  the DD engine relies on. And `NoteFlags`' set bit correlates with nothing
  legible: not "new at this level", not chord membership, not first-in-phrase
  (agreement 133/211) — so it cannot be reproduced without guessing, and
  guessing a flag the game dereferences is how the earlier highway crashes
  happened.

  **B — a phrase now DROPS OUT of every level above its own ceiling.** This was
  the largest structural difference. `_level_notes` clamped with `min(d, pm)`,
  so once a phrase saturated it repeated its full content at every higher level
  and `Levels[max]` was the entire chart; the reference's top level holds 126 of
  its 623 notes — only the two phrases whose ceiling IS the song max — and every
  phrase that topped out earlier contributes zero. The ramp UP to each ceiling
  was already identical between the two files (verified per phrase: both reach
  full content exactly AT the ceiling, never above it), so this changes nothing
  a player sees below a phrase's ceiling; what it fixes is that no phrase ever
  left, leaving all 29 present at all 23 levels regardless of their declared
  `max_difficulty`. Anchors follow for free (`_build_level` already derives them
  from that level's own notes), which reproduces the reference's declining
  anchor counts too. Guarded by
  `test_a_phrase_drops_out_of_levels_above_its_own_ceiling`, confirmed to fail
  on the old `min(d, pm)`.

  **E — the difficulty densities are three different values.** Each is that
  difficulty's note density scaled back up by how much of the chart it shows:
  `4 x NotesEasy`, `2 x NotesMedium`, `1 x NotesHard`, each over
  `10 x songLength`. Derived from the reference and checked to the last digit
  (182/331/623 notes over 202.509 s reproduces its 0.359490191 / 0.326899047 /
  0.307640644, where we wrote 0.307641 three times). Guarded by
  `test_song_difficulty_easy_medium_hard_are_three_different_densities`.

  **C — `Techniques`, five ids and no more.** The map is
  `{level: {phraseIteration: [ids]}}` over a game-internal enum. Five ids were
  DERIVED, not guessed: each was tested for exact equivalence ("this id is
  listed for this (level, iteration)" ⟺ "a note there carries this technique")
  across all 508 level×iteration pairs of BOTH reference arrangements, and each
  scored **1.000** — `3` hammer-on, `6` HOPO (hammer-on OR pull-off), `9`
  pull-off, `11` slide, `16` vibrato. The rest is deliberately NOT emitted: the
  reference song uses only a handful of techniques, so there is no evidence at
  all for bends/harmonics/tapping/tremolo/slap-pop/accents/unpitched slides, and
  three ids that DO appear (`7`, `13`, `33`, `35`) top out at 0.87–0.97 against
  their best-matching feature, i.e. their real definition is not pinned down.
  An omitted technique behaves exactly like the empty map we shipped before, so
  partial-but-certain beats complete-but-invented. `_techniques` in
  `manifest.py`; guarded by `test_techniques_map_carries_only_the_derived_ids`,
  which fails if an unmapped id ever leaks out.

  **D — the stage cues.** `_build_events` emits the reference's five, and the
  placement rule is read off the reference and confirmed to hold independently
  on BOTH its arrangements, whose start/first-note times differ: `e2` at
  `start_time`, `E3` at `first_note + 0.6`, `E13` at `E3 + 2.5`, `D3` at
  `song_length - 9`, `E13` at `song_length` (lead 6.421/8.6/11.1/193.509/202.509
  from 6.421/8.0; rhythm 5.0/14.021/16.521/193.509/202.509 from 5.0/13.421).
  Only the PLACEMENT is reproduced — what the codes mean to the game is not
  documented anywhere citable — and they are inert 256-byte strings in a
  venue/crowd-staging section, not note geometry. A song shorter than the
  intro+outro leads DROPS the outro cue rather than clamping it to 0, which
  would put a "nine seconds from the end" cue at the very start.
  **`read_sng` must dispatch on the section's IDENTITY, not its entry size:
  Actions and Events are both 260 bytes**, so keying off the size read the
  Actions section as Events and left the real ones unread (caught by
  `test_read_sng_skips_populated_sections_a_real_file_carries`).

  **F — not fixable without guessing, so not attempted.** The note `Hash` was
  brute-forced against the reference: no CRC-32 or adler32 over ANY contiguous
  byte range of the serialized note matches, and neither does the full standard
  CRC-32 catalogue (11 variants) crossed with every subset of plausibly-zeroed
  fields. It is computed over a representation we do not have. `NoteFlags`'
  bit is no better: "new at this level, per phrase iteration" agrees only
  0.695, and nothing else correlates. Writing a guessed value into a field the
  game dereferences is precisely how the earlier highway crashes happened, so
  both stay 0. Do not re-open this without a new source of truth.

  **G — `LastConversionDateTime`.** Was missing from the manifest entirely (the
  SNG's own copy also used a different format from the reference). Now emitted
  in both, as a **constant** (`LAST_CONVERSION`, kept in sync between `sng.py`
  and `manifest.py`) — a field named "last conversion" is exactly what a game
  could use to decide a song was re-authored and drop its saved progress, and a
  value that changed every rebuild would be the bug rather than the fix. Same
  reasoning as the deterministic persistent IDs. Unproven either way.

  **The note counts had to change with B.** `NotesEasy`/`Medium`/`Hard` were
  `len(levels[k].notes)` for a fixed `k` — only ever right for Hard while the
  top level held the whole chart. They are now what the player SEES at each
  hero setting: for every phrase iteration, the count at ITS OWN hero level,
  summed over the song. Derived from the reference and exact on both its
  arrangements (182/331/623 and 155/283/525, whose top levels hold just 126 and
  99 notes). Guarded by
  `test_note_counts_are_per_iteration_hero_totals_not_one_level`.

  **The symptom was isolated to PERSISTENCE, not level data (2026-08-25).**
  The user's later report is precise: the levels ARE there, Riff Repeater DOES
  raise them, and the new level is not kept — it zeroes every time. So the DD
  tables are being read correctly and something about how the song is
  identified or dated is stopping the profile write from sticking. Two more
  candidates were eliminated against the reference along the way: the `.hsan`
  header and the per-arrangement `.json` agree on `PersistentID`/`MasterID_RDV`
  in BOTH files (the game is not reading progress under one key and saving it
  under another), and `ArrangementProperties` is byte-identical between the two
  builds. `DynamicVisualDensity` is likewise the same fixed 20-element constant
  in both. The `Sections` divergences this left open are now fixed — H below.

  **H — the section list.** Three divergences, all fixed together because they
  are all about the same list, and all read off the reference:
  - **`UIName` is a localisation token**, not the raw string: the reference
    writes `$[34298] Riff [1]` / `$[6091] No Guitar [1]` where we wrote `riff` /
    `noguitar`. Only those two ids are known (the full name→id table is a game
    resource we do not have), so `_SECTION_UI_NAMES` carries exactly them and
    every other name falls back to the raw string — i.e. no worse than before.
    The trailing `[1]` is part of the token, NOT the number (the reference's
    "Riff 17" still ends `[1]`).
  - **The `COUNT` phrase gets no section.** The reference has 19 sections over
    20 phrase iterations, starting at iteration 1; the COUNT *phrase* stays. Its
    END phrase's section is named `noguitar`, the same closer the XML writer
    already appends.
  - **`Number` is an ordinal per NAME, not the list index.** Both callers passed
    the index, so with COUNT/END and several names mixed in the numbers
    duplicated and skipped — the shipped build had two consecutive sections both
    numbered 2, naming two different passages the same thing in Riff Repeater.
    `domain/arrangement.py`'s `number_sections` is the single pure
    implementation, used by BOTH the SNG builder and the XML writer so the two
    cannot drift, and it carries a running tally so the packer's
    `renumber_sections_across` can continue the numbering across the song's
    arrangements — which is what the reference does (Lead riffs 1-17, Rhythm
    riffs 18-34; noguitars 1-2 then 3-4). Applied before both the manifests and
    the `.sng` payloads are derived, so they can never disagree about what
    "Riff 18" is. `gp_pipeline` no longer numbers `section_overrides` by
    position either (it made the first Solo "Solo 2" just because an Intro
    preceded it). Guarded by
    `test_number_sections_counts_per_name_not_by_position`,
    `test_sections_match_the_reference_shape`,
    `test_section_numbers_continue_across_arrangements` and
    `test_section_ui_name_is_a_localisation_token_when_known`.

  **RESOLVED IN GAME (2026-08-25).** A rebuild carrying A, B, C, D, E, G and H
  ramps Dynamic Difficulty and KEEPS the level. The long-running symptom is
  closed.

  **Which one fixed it is NOT known, and that matters.** All seven shipped in
  one batch, so there is no evidence isolating the cause — do not "simplify"
  any of them away later on the grounds that it looks cosmetic. Each was an
  independently confirmed divergence from a build known to work; the ones with
  a plausible mechanism for the *final* symptom (the level rose and then
  zeroed, i.e. a persistence failure rather than missing level data) are G
  (`LastConversionDateTime` absent, so nothing pinned the song's conversion
  identity) and H (duplicate section numbers). B/C/D/E were structural
  correctness. If any of this is ever revisited, the only honest statement is
  "the batch fixed it".

  What stayed at 0 throughout and is therefore proven NOT to be required: the
  note `Hash`, the `NoteFlags` bit (finding F), `NLinkedDifficulty`,
  `PhraseExtraInfo`, Actions, Tones and DNAs. That is a useful negative
  result — F was the largest remaining unknown and it can now be closed rather
  than re-opened. The `.psarc` the user tested is byte-identical to their
  2026-08-24 one (same md5), so it predates even fix A — a rebuild on current
  `main` is what the next round of evidence has to come from.

  At level `d`, each iteration shows the strongest-beat prefix of its
  notes scaled by `d` against that phrase's ceiling (`_level_notes`, ranked by
  `_note_tier` then time), so level 0 is the strongest beats and a phrase's own
  ceiling is where it shows its full content (and above which it drops out). `phrase_iterations[].difficulty` is the `(round(max/4),
  round(max/2), max)` Easy/Medium/Hard hero triple. Anchors are shared across
  levels (fret-hand windows are valid at any density), but **slide
  anchor-extensions are rebuilt per level from that level's own notes**
  (`_build_level`): an extension pointing at a note the level dropped crashes
  the game on the first low-difficulty pass through the section. (Handshapes are
  not emitted at all — see the fingerprints note above.) Guarded by
  `test_dd_levels_have_no_handshapes_and_per_level_slide_extensions`. The manifest reports
  `MaxPhraseDifficulty` + `NotesEasy/Medium/Hard` from the levels.
  **Phrase linking:** musically-identical iterations are collapsed onto ONE
  shared phrase (`_phrase_signature` fingerprints each section's notes relative
  to its start; a match reuses the phrase id), so a repeated riff is a single
  phrase with many iterations — learned once and mastered on every repeat, and
  the difficulty graph / Riff Repeater show the song's true handful of unique
  phrases instead of one bar per section (a real CDLC has far fewer phrases than
  sections — decoded DLC Builder "Pride" lead: 12 phrases vs our old 29). The
  per-phrase ceiling is its BUSIEST iteration, so a repeated riff levels by its
  hardest occurrence. Note-less spans (COUNT/END/gaps) never dedup. Still a
  density ramp for the per-level note *selection* (density-ranked, not musically
  phrased), and the finer `NLinkedDifficulty` section (linking the levels of
  *different* phrases) is NOT emitted. The trustworthy full-DD path stays the
  DLC Builder bundle (it runs a real DDC). Guarded by
  `test_identical_riffs_share_one_phrase`.
  **A note's `phrase_id` is the linked phrase id, NOT its iteration index.**
  Once linking makes fewer phrases than iterations, setting a note's `PhraseId`
  to its phrase-*iteration* index (the pre-linking 1:1 shortcut) runs off the end
  of the Phrases array — the game dereferences it *while scoring that note* and
  crashes (a hands-off run never touches it, so it looks fragile/intermittent).
  `from_arrangement` sets `phrase_id = phrase_iterations[pi_id].phrase_id`.
  Guarded by `test_note_phrase_id_is_in_bounds_after_linking`.
  A section-less GP is auto-segmented into ~13 s phrases (`_default_sections`) so
  DD still ramps per-phrase, and within a phrase the shown notes are spread across
  its timeline (`_spread_order`) rather than clustered at its start. **DD is
  toggleable per song** (`GpJobSpec.dynamic_difficulty` / `RebuildIn`, the "DD"
  checkbox): off ⇒ a single full-chart level (`from_arrangement(...,
  dynamic_difficulty=False)`), a safety valve when DD misbehaves on a song.
- **Fingerprints2 (arpeggio) empty**: the domain has no arpeggio marking.
- **ParentPrevNote / linkNext absent**: the domain has no note-link concept (the
  XML writer hard-codes `linkNext="0"`), so this is correctly `-1`.
- **Note Hash = 0**: a deliberate choice — the two reference tools
  (Rocksmith2014.NET vs toolkit) compute mutually different, non-validated hash
  values, so 0 is safe and source-consistent. It was later brute-forced against
  a DLC Builder reference (no CRC-32/adler32 over any contiguous byte range of
  the serialized note matches, nor the full standard CRC-32 catalogue crossed
  with every subset of plausibly-zeroed fields) and is NOT reproducible — see
  finding F in the DD section.

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

**Rocksmith PC load requirements — the full enumeration layout (`gamedata.py`).**
A song not appearing in the in-game list was traced (by byte-diffing a working
DLC Builder PSARC against ours) to a large set of missing/wrong files, now
emitted so the native PSARC matches the retail layout file-for-file:
- filename `*_p.psarc` (the `_p` platform tag — `packer.py`);
- `appid.appid` at the root (`manifest.APP_ID`) — the Steam id of a DLC the game
  checks ownership of. Rocksmith only lists a CDLC whose appid the player
  **owns**, so CDLC reuses an owned DLC's appid. RockForge ships Train "Drops of
  Jupiter" (`492989`); swap it for one the target player owns (e.g. the free base
  song Smashing Pumpkins "Cherub Rock", `248750`) if the song doesn't appear;
- `gamexblocks/nsongs/<key>.xblock` — an `entitySet` with one `RSEnumerable_Song`
  entity per arrangement (this is what makes the engine enumerate the song);
- `flatmodels/rs/rsenumerable_{root,song}.flat` — the (song-independent) model
  schema, vendored verbatim under `psarc/flatmodels/`;
- `<key>_aggregategraph.nt` — the N-Triples asset table mapping every URN to its
  archive path;
- `manifests/…/<arr>.json` (full entries, `InsertRoot = Static.Songs.Entries`,
  `ArrangementType` an **int** enum not a string) **and** the aggregated
  `songs_dlc_<key>.hsan` (**header** subset, `InsertRoot = Static.Songs.Headers`)
  — two distinct layers;
- the SNG under **`songs/bin/generic/<asset>.sng`** (not `songs/arr/`, which now
  holds only the showlights), written as a **full retail `.sng` file**
  (`crypto.pack_sng`: 8-byte header `0x4A`/platform 3 + zero IV + AES-256-CTR of
  a zlib-compressed, size-prefixed payload — header byte-verified against a real
  SNG). The earlier bare-AES-CTR primitive produced an unparseable file: the game
  showed tuning then **froze on the note highway**;
- `songs/arr/<key>_showlights.xml` — the **stage-lighting track**, generated
  from the richest chart (`gamedata.build_showlights`): a fog colour (notes
  24-35) at the song start and at each section, plus a pitch-coloured beam
  (notes 42-59) at each note onset (thinned to `_SHOWLIGHT_MIN_GAP_S`), matching
  the fog-per-section + beam-per-onset shape DLC Builder emits. An **empty**
  showlights (the old behaviour) leaves the stage dark and the song can skip its
  lit intro — including the song-name/title card the game shows over the intro.
  Guarded by `test_showlights_generated_from_arrangement`;
- `gfxassets/album_art/album_<key>_{64,128,256}.dds`
  (a neutral solid-DXT1 **placeholder** — real cover DDS is a DLC Builder step),
  and the `song_<key>_preview.bnk` + its `.wem` alongside the main bank;
- the container's TOC entry offsets are **absolute** from the file start
  (`container.py`), as retail expects — not block-section-relative;
- **a partial uncompressed block stores its real size in the block table, not 0**
  (`container.py`, `_compress_block`). Rocksmith reserves `zlength == 0` for a
  *full* `block_size` block (65536, which wraps the 2-byte field to 0); writing 0
  for a *partial* raw block (e.g. the 6-byte `appid.appid`) made the game read it
  as a full 65536-byte block, so the appid came back corrupt and the song was
  silently dropped from the list **even with the right appid value**. Byte-diffing
  a working DLC Builder PSARC (stores `appid.appid` with `zlength = 6`) and the
  toolkit's re-pack of our own output (which rewrites exactly this) isolated it.
  Guarded by `test_partial_uncompressed_block_zlength_is_its_size_not_zero`;
- `toolkit.version`'s **`Toolkit version:` line must be a numeric
  RocksmithToolkitLib version** (`2.9.2.1-5df928a5`, `manifest.TOOLKIT_VERSION`).
  The Rocksmith CDLC loader patch (the `D3DX9_42.dll` proxy that disables the DLC
  signature check) reads this field to recognise a PSARC as legitimate CDLC and
  only then whitelists it; a custom non-numeric value (`RockForge-native`) made
  the patch skip our file, so the game silently dropped the song from the list
  **even with a correct appid** — the "plays only after re-packing with the Custom
  Song Toolkit / CustomsForge Song Manager" symptom. Byte-diffing the toolkit's
  re-pack of our own output isolated this as the sole meaningful change (it only
  rewrites this one line). Guarded by `test_build_manifest_files_packs_and_round_trips`;
- **`ArrangementProperties`' technique flags, `SongOffset` and `TargetScore` are
  real values, not zeros.** All the technique flags were hard 0, so every chart
  advertised itself as using no palm mutes, power chords, slides, sustain or
  vibrato — a false claim about its own content (byte-diffing a DLC Builder build
  of the same song: it sets all of those from the notes). `_technique_flags`
  derives them from the domain notes; the handful the domain cannot express
  (barre/non-standard chords, finger-picking, syncopation, bass pick) stay 0
  rather than being guessed. `SongOffset` (the recording's lead-in, which the
  game shifts its clock by) was 0 where the reference writes `-startTime`, and
  `TargetScore` (the score counting as full mastery) was 0 where it writes
  100000; `SongPartition` 0 → 1. The manifest `Techniques` map stays `{}` — see
  the DD note above;
- **every TOC entry carries a 16-byte name hash = `md5(archive_path)`**
  (`container.py`). Rocksmith resolves every asset (SNG/manifest/xblock/…)
  THROUGH this hash, so a zeroed hash makes the game unable to find the files and
  it silently drops the whole song from the list **even with a correct appid** —
  the exact "plays fine once re-packed by the Custom Song Toolkit, but our own
  `.psarc` never appears" symptom. The name-block entry (index 0) has no path and
  uses the fixed retail constant `0x4d3d4000dd8eed661b5cfe5f4abc924b` (both DLC
  Builder and the toolkit write it). Verified by byte-diffing a working DLC
  Builder PSARC and the toolkit's re-pack of our own output; guarded by
  `test_toc_entries_carry_md5_of_path`.

The SNG always emits a valid phrase timeline (`sng._default_sections` synthesizes
a COUNT/riff/END structure when the arrangement has no section markers — without
it the game loads the fretboard, shows no notes and crashes), and the manifest
reports the real note count + phrase/iteration/section tables
(`manifest.arrangement_stats`, from the compiled SNG) so the song-list screen
shows the note count instead of "0". Verified by unpacking our output and diffing
the file list + manifest fields against a real DLC Builder PSARC (they match bar
cosmetic `LastConversionDateTime`). Iterated to playability against a real
Rocksmith install (the SNG format/beat-mask/slide-sentinel/anchor fixes below
came from that loop). Custom tones the user builds ARE serialized into each
arrangement's runtime manifest (`Tones` array + `Tone_Base`/`Tone_A`..`Tone_D`,
via the shared `packaging/tone_dto.py` — the same `ToneDto` the `.rs2dlc` emits,
verified byte-identical against a DLC Builder build of our own tones), so the
in-game tone is the user's, not a default; the SNG's Tones section (mid-song
tone *changes*) stays empty until per-arrangement `tone_changes` are wired.
Remaining honest gaps: the Dynamic Difficulty ramps and persists in game
(confirmed 2026-08-25) but is still a mechanical DENSITY ramp, not a musical
DDC pass — it picks notes by strongest-beat rank, so it levels correctly
without phrasing the way a real DDC would; and the SNG binary is round-tripped
but not byte-diffed against retail. The DLC Builder bundle remains the route to
a real DDC pass if that phrasing matters for a given song.

### Wwise SoundBank (`infrastructure/packaging/psarc/soundbank.py`)

Rocksmith reads a song's audio through a Wwise SoundBank: `song_<key>.bnk`
carries a `Play_<key>` event plus a ~100 ms *prefetch* of the audio, and the
full stream lives beside it as `<fileID>.wem`. Without the `.bnk` the game can
list a song (once appid/manifests are right) but has no event to fire, so it
plays silence. Exactly as DLC Builder / Rocksmith2014.NET do, RockForge does NOT
ask Wwise to build the bank — Wwise (`wwise.py`) only produces the `.wem`; the
`.bnk` is generated in code (`soundbank.generate_soundbank`, ported from the
toolkit's `SoundBankGenerator2014`, MIT — same lineage as `sng.py`) with a
random `fileID`, and the packer emits `audio/windows/song_<key>.bnk` +
`audio/windows/<fileID>.wem`. The manifest points `SongBank` at the real `.bnk`
and adds `SongEvent = Play_<key>`. Layout (PC/little-endian):
`BKHD → DIDX → DATA → HIRC → STID`; HIRC holds Sound/ActorMixer/Action/Event
objects. Same honesty caveat as `sng.py`: round-tripped
(`read_wem_file_id`/`read_bkhd_version`) but **unverified-by-design** — no
reference bnk in CI. When no Wwise is available the packer falls back to the old
non-loading `audio/<key>.<ext>` path (bundle stays the trustworthy audio route).

**Volume ("Calculate Volumes", `normalize/loudness.py`).** The Sound object's
Wwise bus volume (dB) is no longer a neutral 0. **One target
(`runtime_settings.loudness_target()`, default -12 LUFS) drives BOTH the ffmpeg
`loudnorm` pass AND the volume calibration**, so the `.wem` and the bus volume
never drift: the audio is normalized to that loudness, then the packer measures
it with `ebur128` and offsets the bus volume to the same target (`calculate_volume`
→ `generate_soundbank(volume=…)`) — a normalized song lands near 0 dB, and the
song-select **preview** (a trimmed clip whose own loudness differs) is measured
separately and matched so it doesn't blast over the list. **Why -12, not the -16
EBU R128 broadcast reference:** retail Rocksmith ships loud music masters (DLC
Builder's Calculate Volumes lands ~-3/-4 dB of *attenuation* on such a master),
so -16 read audibly quiet in-game; -12 is a music-game level. The target is
**user-editable in the ⚙️ Definições modal** ("Volume alvo (LUFS)", clamped
-20..-6) — push toward -10/-9 if still quiet, back toward -14 if it pumps. Since
our `.wem` is *normalized* to the target (not just bus-boosted), raising it is
safe (loudnorm's limiter, not a post-gain that would clip the -1.5 dBTP peaks).
`parse_ebur128_i`/`volume_for_loudness` are pure and unit-tested without ffmpeg;
a missing ffmpeg degrades to 0 dB, never a crash. The `.rs2dlc` audio `Volume`
stays neutral (DLC Builder recomputes on import).

### What external software is installed (`/system-check` + `diagnostics.py`)

RockForge ships almost none of its dependencies — Wwise cannot legally be
redistributed, the ML stack is gigabytes, ffmpeg is better taken from the
system. Each already degrades cleanly ON ITS OWN (no Wwise still produces the
bundle, a missing `[ml]` extra is a 503 naming it, no `[psarc]` just omits the
`.psarc`), but every one of those symptoms surfaces DOWNSTREAM and reads as a
bug in RockForge: "o PSARC não é jogável", "a deteção de letra não faz nada".

`infrastructure/diagnostics.py` answers the one question that fixes that — *what
is installed, and what does each gap cost me?* — and `GET /system-check` serves
it to the ⚙️ Definições modal's **🩺 Software externo** block. Each
`Requirement` carries `unlocks` (what it enables), `without_it` (what actually
happens when absent — the honest cost, not a scare) and `install`.

**`found` is a TRI-STATE, and that is the point.** `None` means "cannot be
checked from this process", which is a different and more useful answer than
`False`:
- the **Rocksmith CDLC loader patch** is the single most common reason a song
  never appears in game, and we have no idea where the user installed
  Rocksmith — calling it "missing" would be a confident guess about someone
  else's machine;
- **PyTorch installed** tells us nothing about whether it is the CUDA build;
  only importing it would, and the API process must never import torch (the
  layering rule above). Installed-and-unverifiable is `None`; marked broken
  after a CUDA crash IS knowable, and is `False`.

**Nothing heavy is imported.** Detection uses `importlib.util.find_spec`, which
locates a package without importing it — the same trick
`whisperx_adapter.available()` already uses. `find_spec` RAISES on a
half-removed package rather than returning `None`, so `_has` catches that: a
diagnostics page that 500s is worse than one that says "missing", and a broken
install is exactly when the user opens it. The ffmpeg probe runs `-version`
with a timeout and `stdin=DEVNULL` (the hard constraint about console tools
inheriting stdin applies here too); a binary that will not answer is still
reported as FOUND, with the detail saying the probe failed.

**Inside the `.exe` an install instruction is rewritten, not printed.** The
frozen process cannot IMPORT a package the user pip-installs (see the
standalone section), so a bare `pip install` would be a lie — but it can hand
the work to another interpreter, so `_extras_install` rewrites the instruction
to say *where* the packages have to go (the Python `ROCKFORGE_ML_PYTHON` points
at) rather than claiming the feature is unreachable. ffmpeg and Wwise are
ordinary programs, so THEIR instructions are untouched.

**The ML rows report the interpreter that will RUN the work, not this
process.** In the `.exe` those are different Pythons, and our own answer
("nothing installed") says nothing about whether the feature works. They read
`ml_python.availability()`, which probes the other interpreter in a subprocess
when there is one — so the API still never imports torch, and could not answer
for a different interpreter anyway. A `ml_python` row names that interpreter
and its extras; it reads "o próprio Python do RockForge" under `start.bat`,
where the setting is unnecessary.

**Only ffmpeg is `required`** — everything else has a documented degraded path,
and `missing_required` is what the UI turns into the red banner. Guarded by
`test_diagnostics.py` (including a test that fails if the probe ever starts
importing torch/demucs/librosa/whisperx) and `test_system_check_*` in
`test_api.py`. This is the machine-level view; the per-job **"Estado do PSARC"**
checklist stays the per-song one.

### Optional API authentication (`ROCKFORGE_API_TOKEN`)

RockForge has **no authentication by design** for local single-user setups —
`start.bat` and the standalone `.exe` both bind `127.0.0.1`, so nothing outside
the machine can reach the API. Docker Compose is the one deployment path that
actually opens a network port (`8000:8000`), and a full-codebase audit found
that with no auth layer, every job (including uploaded GP files, cover art, and
built bundles) is readable/deletable by anyone who can reach the port, and the
unauthenticated `/settings` endpoint can repoint the Banquet stem-separator's
`banquet_repo` at an arbitrary filesystem path the worker then executes
`train.py` from.

`app._verify_api_auth` is a global FastAPI dependency (wired via
`FastAPI(dependencies=[...])`, so it runs before every route) gated on
`settings.api_token` (env `ROCKFORGE_API_TOKEN`): `None` (default) is a no-op —
zero behavior change for local setups. When set, it requires **HTTP Basic**
credentials whose password matches the token (any username;
`secrets.compare_digest` for a constant-time comparison) via
`fastapi.security.HTTPBasic`. Basic, not a custom bearer header, deliberately:
a plain browser gets a native login prompt on first visit and then
auto-attaches the credentials to every subsequent same-origin request
(including the page's own `fetch()` calls) — no frontend code needed.
`docker-compose.yml` requires `ROCKFORGE_API_TOKEN` via `${VAR:?…}` compose
syntax, so `docker compose up` refuses to start without a `.env`-supplied
secret rather than silently running exposed and unauthenticated. Guarded by
`test_no_auth_by_default` / `test_api_token_gates_every_route_when_set`.

### Standalone executable (`build_exe.py` / PyInstaller)

**It opens a NATIVE WINDOW, not a browser tab.** `start_standalone.py` runs
uvicorn on a daemon thread and shows the UI in a `pywebview` window
(`run_windowed`); `webview.start()` must own the main thread, which is why the
server is what moves aside. pywebview wraps the platform's OWN webview — Edge
WebView2 on Windows, which ships with the OS — so it costs a few MB rather than
bundling a second browser the way Electron would, and `web/` is served and
rendered completely unchanged. It is the optional `[desktop]` extra: without it
(or when the GUI backend cannot start — no WebView2 runtime, no display)
`run_in_browser` restores the old behaviour, serve-and-open-the-default-browser,
after releasing the port so the fallback can bind it.

**A window close is unambiguous, so windowed mode turns the idle-shutdown
watchdog OFF** (`ROCKFORGE_IDLE_SHUTDOWN_S=0`). That whole mechanism exists only
because "the browser tab closed" is a guess made from missing heartbeats — a
guess a backgrounded tab breaks, which needed its own guard. The window replaces
it, and `should_close_now` keeps the part that matters: in `inprocess` mode the
worker runs in the API's own process, so closing mid-build would abort it and
leave the job stuck at RUNNING, exactly what `_should_shutdown(work_in_flight)`
prevents on the browser path. The window's `closing` event (cancellable —
returning `False` vetoes) asks the user to confirm instead of silently
discarding the work or refusing to close at all.

**`console=False` means the process has NO stdout or stderr** — they are
`None`, and uvicorn's logging raises on the first line. `main()` redirects both
to `work_dir/rockforge.log` before anything can write (`redirect_output_to_log`),
falling back to a temp file if settings cannot even load: a crash with no console
AND no log is unreportable. pywebview needs no `hiddenimports` — its wheel
declares a `pyinstaller40` entry point pointing at its own hook directory, which
PyInstaller discovers automatically.

Everything in the launcher is a plain function called from `main()`, nothing runs
at import: the environment must be configured before anything imports
`rockforge.config` (pydantic-settings reads the environment once, at import), and
a module that did that on the way in could not be tested without side effects.
Guarded by `test_standalone_launcher.py` (the watchdog/worker-mode defaults and
that an explicit setting still wins, the close-confirmation logic, the readiness
poll, the ffmpeg PATH order, the log fallback, and — with a fake `webview` — that
the window opens on the local API, that the close handler is actually wired to
`work_in_flight`, and that BOTH failure paths release the port).

It sets `ROCKFORGE_WORKER_MODE=inprocess` before any import, so the API
dispatches tasks to a `ThreadPoolExecutor(max_workers=1)` inside the same process
instead of to Celery/Redis. The task functions themselves (`generate_cdlc`,
`detect_lyrics`) are identical — only the dispatch changes. `worker_mode`
(`config.py`) controls which path `_enqueue`/`_enqueue_detect` take:

- `"celery"` (default): `.delay(job.id)` via Celery (needs Redis + worker).
- `"inprocess"`: `inprocess.enqueue_generate(job.id)` via thread pool (no Redis).

The PyInstaller spec (`rockforge.spec`) excludes the ML stack (torch, demucs,
whisperx, scipy, numpy) — the `.exe` covers the GP pipeline + native PSARC core.

**The `.exe` cannot IMPORT the ML stack — and does not need to
(`infrastructure/ml_python.py`).** A PyInstaller build's `sys.path` is just its
own `_internal`, so the system's site-packages are never importable (verified
by building a minimal frozen app and reading `sys.path` back; an earlier note
claiming "ML extras work if installed separately on the user's Python" was
false about this). But **every ML stage runs, or now runs, as a subprocess** —
Demucs via `_demucs_patcher.py`, WhisperX via `_whisperx_runner.py` (for the
ctranslate2 CUDA deadlock), Banquet via query-bandit's own `train.py`, and
librosa via `_librosa_runner.py` — so none of them needs the package importable
in the calling process.

What actually kept them out of the standalone build was one argument repeated
at each of those call sites: **`sys.executable`, which in a frozen app is the
`.exe` itself**, so the subprocess would relaunch RockForge instead of running
Demucs. `ROCKFORGE_ML_PYTHON` (⚙️ Definições → "Python para o ML", persisted
via `runtime_settings`) closes that: point it at a Python 3.11 carrying
`[ml,lyrics]` and the `.exe` gains stem separation, tone detection, lyric
detection and "Corrigir daqui". It is the same arrangement ffmpeg and Wwise
already have — external software, installed once, outside the app.

`ml_python.resolve()` returns the configured interpreter, else `sys.executable`
when NOT frozen (so running from a Python install is the byte-for-byte old
path), else **None** — which callers turn into the ordinary "that extra is
missing" error naming the setting, never a crash. `test_ml_python.py` pins the
call sites by **parsing** them for a `sys.executable` attribute access (a text
grep would trip on the comments explaining why it is gone): a regression there
is invisible from a Python install, where the two values are equal, and breaks
only the `.exe`, which CI can neither build nor run.

**The librosa measurements have ONE implementation, reachable two ways.**
`infrastructure/_librosa_runner.py` holds `tempo_from`/`tuning_cents`/
`tone_features` and a `main()` that prints one line of JSON; it imports
**nothing from `rockforge`** (same rule as the other two runners — that is what
lets an interpreter which has librosa but has never heard of RockForge run it).
`librosa_adapter` and `tone_analysis/analyzer` call those functions **directly**
when this process has librosa and shell out otherwise, so `start.bat` keeps the
in-process path — "Corrigir daqui" is a per-click tool and paying an
interpreter start plus a librosa import on every click would make it unusable.
Two copies of the feature extraction would drift and silently classify a tone
differently in the `.exe`; `test_the_librosa_measurements_have_one_implementation`
fails if either adapter grows an `import librosa` of its own. The split of the
tone analyzer was already right for this: the librosa half produces seven
scalars, and the calibration that maps them to a `ToneProfile`
(`profile_from_features`) is pure and stays where CI can test it.

**`ml_python.availability()` is the ONE place that decides whom to ask.** With
nothing configured and not frozen, this process IS the interpreter that will do
the work, so `find_spec` answers exactly and instantly — spawning a probe to
ask ourselves would cost a subprocess on every `/settings` open. Otherwise the
packages live elsewhere and only that interpreter can answer, so it is asked in
a subprocess (`probe`) — the API process must never import torch. Both the ⚙️
diagnostics rows and the settings page's per-extra ✓/✗ read it, so the two
halves of the same modal cannot contradict each other. A configured path that
is not a working interpreter reports `python: False`, deliberately distinct
from "it runs but has no demucs": "Demucs em falta" would send the user to
reinstall Demucs instead of fixing the path.

**The runners must be shipped as real `.py` FILES.** Inside the bundle a
package's modules live in the archive, where no other interpreter can execute
them, so `rockforge.spec` WALKS for `_*_runner.py`/`_demucs_patcher.py` and
bundles each at its package path — which is where `ml_python.runner_path`
looks. Walked, not listed by hand, for the same reason `web/` is (below), and
guarded by `test_spec_bundles_every_ml_runner_at_its_package_path`, which
asserts the destination too: a runner bundled to the wrong folder is exactly as
broken as one not bundled at all.
ffmpeg is bundled from `ffmpeg/ffmpeg.exe` (placed by the user before build);
`start_standalone.py` prepends the bundled path to `$PATH` at launch.

**The spec WALKS `web/`; it must never list those files by hand again.** It used
to carry a single literal `("web/index.html", "web")`, so when `index.html`'s
~4100-line inline `<script>` was extracted into `web/app.js` the list did not
follow — the shipped `.exe` served an `index.html` whose `<script src="/app.js">`
had nothing behind it and **the entire UI was inert**, with `web/gear_images/`
missing too. Nothing could catch it: no gate ever looked at the spec.
`test_standalone_spec.py` now executes `rockforge.spec` with the PyInstaller
builders stubbed out and asserts its real `datas` covers every file under `web/`,
at the matching destination.

**`_web_file_candidates()` tries `sys._MEIPASS/web` FIRST** (`_web_dirs()`), which
is the other half of that bug: inside the bundle neither of the other candidates
resolves — `__file__` points into the frozen archive and `start_standalone.py`
never chdirs — so a bundled file would 404 even once the spec ships it.
`_gear_image_dirs()` shares the same list (after the `work_dir` override).
Guarded by `test_bundled_web_files_are_found_in_the_pyinstaller_bundle`.

## Commands

```bash
pip install -e ".[dev,psarc]"       # core + tests + cryptography/Pillow, no ML
pip install -e ".[dev,ml]"          # adds Demucs/librosa (stem separation, tone detection, per-point tempo/tuning)
pip install -e ".[dev,ml,lyrics]"   # + WhisperX (automatic lyric detection)
pytest                           # full suite (ML stages are faked in tests)
ruff check src tests start_standalone.py build_exe.py   # lint — must pass
                                 # (the root scripts are shipped code; rockforge.spec
                                 #  is excluded — it calls PyInstaller-injected names)
mypy                             # strict on domain/application/infra; relaxed at boundaries
```

CI runs ruff + mypy + pytest (+ ESLint on `web/app.js`, + a Docker build). All
must be green before committing. mypy is pinned (`mypy~=1.19.0`) so local matches
CI — do not bump it casually.

**Install `[psarc]`, not bare `[dev]`.** `test_psarc_packer.py` and
`test_psarc_crypto.py` `importorskip("cryptography")`, so without that extra
they skip themselves entirely — 17 tests covering the encrypted PSARC container
and the Sng2014 binary. CI installed only `[dev]` for a long time and was green
throughout while never running any of it. It now installs `[dev,psarc]`, asserts
`import cryptography, PIL` as its own step so losing the extra fails loudly, and
runs `pytest -rs` so any remaining skip is printed with its reason. A silent
skip reads as coverage, which is worse than a failure.

### Uploaded GP files are reference-counted and swept

The Guitar Pro upload lives OUTSIDE the job's work dir — `/gp/inspect` and
`/reload-gp` both write `work_dir/gp/<uuid>.gp*` — so `delete_job`'s
`rmtree(work_dir/<job_id>)` never touched it and every deleted job left its GP
behind forever. `delete_job` now removes it too, reference-counted like the
recording (`_gp_path_in_use`): a `/rebuild` or `/reload-gp` fork SHARES
`gp_path`, so deleting one of a pair must not pull the file out from under the
other. The check runs in Python over `(id, params)` rather than in SQL because
`gp_path` sits inside the JSON column and JSON-path querying differs between
SQLite and Postgres — this is a single-user app with a job list measured in
tens, so portability beats the scan.

The other half is orphans: `/gp/inspect` stores the file BEFORE the job exists
(the wizard inspects tracks first), so abandoning the wizard — or the batch
modal, which inspects one file per song — left an upload nothing would ever
collect. `_sweep_orphan_gp_uploads()` runs from the app's **lifespan** (nothing
else calls it; there is no scheduler here) and deletes only files that no job
references AND that are older than `GP_ORPHAN_MAX_AGE_S` (24 h) — a fresh upload
may still belong to an open wizard, including one left open across a restart. It
never raises: failed housekeeping must not stop the API from starting. Guarded by
`test_deleting_a_job_removes_its_gp_file_but_not_a_forks`,
`test_orphaned_gp_uploads_are_swept_but_referenced_ones_are_kept` and
`test_the_orphan_sweep_actually_runs_on_startup` (which drives a real startup,
because a sweep nothing calls is worthless).

### The database schema is frozen; drift fails loudly at startup

There is no migration tool, and `Base.metadata.create_all` creates missing
TABLES but never `ALTER`s an existing one. **This is a deliberate constraint,
not an oversight: the `jobs` schema is effectively frozen and everything that
varies lives in the `params` JSON column** — which is exactly why adding
features has never needed a migration. If a column ever is added anyway, every
query against an older database dies with a bare `no such column`, request after
request, saying nothing about why. `_check_schema` (`db/models.py`) compares the
model's columns against the real table at startup and raises
`SchemaOutOfDateError` naming the missing ones and what to do. **Detect-only on
purpose** — a hand-rolled auto-`ALTER` is a migration system in disguise, and
this app has no need of one; if that changes, adopt Alembic rather than growing
this. The check itself never blocks startup for any other reason (an inspector
that cannot read the dialect just yields nothing). Guarded by
`test_db_schema.py`.

### `Tuning` validates its own pitches (and the API range-checks them)

`Tuning` was the one pitch-carrying domain type with **no** `__post_init__`,
while `NoteEvent` (0-127), `TabNote` (string/fret) and `TempoMap` all check
theirs. Only the LENGTH of `tuning_midi` was validated at the API, so an absurd
pitch 202'd, was persisted into `params`, and only died much later inside
`struct.pack("<h", ...)` in the SNG writer — a `struct.error` with nothing
pointing back at the tuning. It now raises a plain `ValueError` (the project's
convention for a pure domain invariant) on a non-6-string tuning, a pitch
outside 0-127, or a non-finite `cent_offset`; the API's `MidiPitch =
Annotated[int, Field(ge=0, le=127)]` turns the same thing into a 422 at the
boundary, and `_reject_bad_midi` covers `/import-sync`, which takes raw JSON and
bypasses the models. Real drop/down tunings are unaffected — the guard is
against nonsense, and `test_tuning_rejects_an_impossible_pitch_at_construction`
pins a Drop C# and a Drop B as still-valid alongside the rejections.

### API input validation: every client float is `Finite`

`Finite = Annotated[float, Field(allow_inf_nan=False)]` (`interfaces/api/app.py`)
is what EVERY float a client can send is typed as — never a bare `float`. JSON
carries the literals `NaN`/`Infinity`, Pydantic accepts them in a float by
default, and `NaN <= 0` is False, so the `tempo_scale <= 0` guard waved NaN
straight through: the job forked, the value was persisted into the `params` JSON
column, and the build only failed much later with an error pointing nowhere
(`_build_time_warp` propagates a NaN silently across the whole timeline).

Two paths bypass the models and carry their own guard: **multipart form fields**
(`/jobs/gp`'s `offset_s`/`lead_in_s`/`tempo_scale` arrive as strings and coerce)
and **`/import-sync`** (a raw JSON blob a hand-edited file could poison), both
via `_reject_non_finite(**values)` / `_iter_floats`.

**Rejecting NaN needs the `RequestValidationError` handler too.** FastAPI echoes
the rejected input back inside the 422 body and Starlette serializes with
`allow_nan=False`, so a refused NaN crashed the encoder and surfaced as a bare
**500** — trading a silent accept for an unexplained crash. `_validation_error`
returns the same 422 through `_json_safe`, which replaces non-finite floats with
their name. Guarded by `test_non_finite_floats_are_rejected_at_the_boundary`
(which asserts the body says "finite", i.e. that it encoded at all) and
`test_non_finite_form_fields_and_imported_sync_are_rejected`.

### A missing ML extra is a 503, caught around the CALL

`/detect-tempo` and `/detect-tuning` used to wrap the ADAPTER IMPORT in
`try/except ImportError` to raise a 503 naming the extra. That was dead code:
the adapters `import librosa` **inside** their function bodies (deliberately —
the API process must never pay for the ML stack), so the module import always
succeeds and the real `ImportError` only surfaces on the call, where the generic
`except Exception` turned it into `422 could not analyse the recording: No
module named 'librosa'`. Catch `ImportError` around the CALL, ahead of that
handler, via `_ml_extra_missing(what, exc)`. Guarded by
`test_missing_ml_extra_reports_503_not_a_confusing_422`. Any future ML-backed
endpoint must follow the same shape — an import guard at module level is
guaranteed to be dead here.

## Hard constraints (these have bitten us — keep them)

- **Python 3.11 only** (`requires-python = ">=3.11,<3.12"`). The ml/lyrics stack
  (torch<2.5 / demucs / whisperx) targets 3.11 wheels. On Windows use
  `py -3.11 -m pip ...`; the user does NOT want virtualenvs. (The old, stricter
  reason — `basic-pitch`'s `tensorflow<2.15.1` — is gone now that audio note
  transcription was removed, so this pin *could* be relaxed after re-validating
  the full `[ml,lyrics]` install.)
- **`whisperx` is pinned `<3.4`** (the `lyrics` extra). `whisperx>=3.4` pulls
  `pyannote-audio>=4.0`/`numpy>=2.1`, which directly conflicts with the `[ml]`
  stack's `numpy<2` pin — installing `[ml,lyrics]`
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
- **A tone change must not coincide with a note.** DLC Builder errors when a
  `<tone time>` event lands exactly on a note's time. The writer nudges each
  tone change to `TONE_SWITCH_GAP_S` (20 ms) *before* the note it starts on, but
  strictly after the previous note (halfway between them if that gap is tighter
  than 20 ms) — per-arrangement, using that arrangement's own note times. A tone
  time not on any note (e.g. an arrangement silent there) is left untouched.
  `_safe_tone_time` in `rsxml/writer.py`, guarded by
  `test_tone_change_never_lands_on_a_note` / `test_safe_tone_time_uses_gap_then_midpoint`.
- **External CLIs must not inherit stdin.** ffmpeg (and any console tool) run as
  a subprocess from the Windows `start.bat` worker inherits the console's stdin,
  goes interactive and blocks forever — the symptom is a job stuck at the
  `normalize`/lyrics-`normalizing` stage. `FfmpegNormalizer` passes `-nostdin` +
  `stdin=subprocess.DEVNULL` (plus a `FFMPEG_TIMEOUT_S` ceiling so a genuine
  stall fails loudly); `DemucsSeparator` uses `stdin=subprocess.DEVNULL` too.
  Guarded by `test_ffmpeg_normalizer.py`. Don't drop these when touching the
  subprocess calls.
- PSARC/.wem packing needs a local Wwise (Audiokinetic EULA forbids
  redistribution); RockForge only *invokes* an installed copy.
- **`Job.params` (JSON column) needs a NEW dict object on every write.** It is a
  plain SQLAlchemy `JSON` column with NO `MutableDict` tracking, so reassigning
  the *same* dict object (`job.params = params`) is a silent no-op — SQLAlchemy
  compares by identity, sees no change, and skips the `UPDATE`. The symptom is
  the worst kind: the task runs fine but every progress update after the first
  commit is lost, so the UI freezes on the first log line while detection
  actually completes (or fails) invisibly. This cost a multi-session debug. The
  async detection tasks use a `_commit_params()` helper that assigns `{**params}`
  (a fresh copy) every time. ANY incremental write to `Job.params` must copy the
  dict (`{**params}`/`dict(params)`) on assignment. See `TESTING.md` §8.

## Async detection tasks (the `detect_lyrics` / `detect_tones` pattern)

Both lyric and tone detection are slow (minutes) Celery tasks that follow one
deliberate pattern — copy it for any future "analyze the recording in the
background" feature:

- **Progress lives in `Job.params`, never in `JobStatus`.** They write
  `params["<x>_status"]` (e.g. `detecting`/`separating`/`ready`/`unavailable`)
  and append timestamped lines to `params["<x>_log"]`. Using `params` (not
  `JobStatus`) means a long detection never hides a COMPLETED bundle or disables
  `/arrangements`.
- **Each step commits via `_commit_params()`** (assigns `{**params}` — see the
  hard constraint above) so the UI's polling sees live progress.
- **The endpoint mutates the existing job** (sets status to `detecting`, commits,
  enqueues) and returns 202 — it does NOT fork a new job like `rebuild` does.
- **Heavy ML failure never crashes the job:** the whole task body is wrapped in
  try/except that sets status `unavailable` + a warning and returns.
- **The UI polls** `GET /jobs/{id}/lyrics` or `/detected-tones` and renders the
  log; the progress *bar* is a client-side time animation and is NOT a real
  progress signal — the log is.

## Documentation map (read these to rebuild context)

- **`CLAUDE.md`** (this file) — architecture, every feature's design, hard
  constraints. The single source of truth for *why* the code is shaped as it is.
- **`README.md`** — user-facing: install, run, use, distribute. Start here to
  set up a machine.
- **`TESTING.md`** — how to run/extend the test suite, the coverage map, and the
  manual end-to-end checks CI cannot do (ML, Wwise, DLC Builder, in-game).
- **`TODO.md`** — done (`[x]`) and proposed (`[ ]`) features + current known
  limitations.
- **`TONE.md`** — deep dive on the tone-gear model and the `.rs2dlc` `Tones`
  serialization.
- **`docs/RELATORIO-TECNICO.md`** + **`docs/research/`** — the sourced grounding
  behind every technical/feasibility claim.

## Testing approach

**See `TESTING.md` for the full guide** (coverage map, how to add tests, manual
end-to-end checks, debugging the async tasks). In short: ML/Wwise/external tools
cannot run in CI, so tests inject fakes at the port boundary — a Python-based
fake WwiseConsole (`test_wwise.py`), a fake GP parser + packager (`test_gp_pipeline.py`),
stubbed Celery enqueue + per-test SQLite (`test_api.py`). When you add an
adapter, add a fake-driven test at the same boundary rather than mocking deep
internals. `pytest` + `ruff check src tests` + `mypy` must all be
green before committing.

## Running locally (Windows, native, no Docker)

`start.bat` launches Redis (Memurai) + Celery worker (background) + the API
(foreground) from a single window; it auto-selects `py -3.11`. Requires ffmpeg
(`winget install ffmpeg`) and a running Redis. See README for the full guide.

### Shutdown on tab close (`ROCKFORGE_IDLE_SHUTDOWN_S`)

`start.bat` sets `ROCKFORGE_IDLE_SHUTDOWN_S=15`: the web UI calls `POST
/heartbeat` every 4s while its tab is open; a background watchdog
(`_idle_shutdown_watchdog` in `interfaces/api/app.py`) decides via the pure
`_should_shutdown(...)` helper (unit-tested). The real close signal is the
`POST /closing` beacon on `pagehide` (tab close/navigate), which arms a
`CLOSE_GRACE_S` (~3s) deadline; a following **visible** `/heartbeat` (a refresh
that came back) clears it, so a refresh survives while a genuine close exits
after ~3s. Only a VISIBLE heartbeat cancels the close: on tab close the browser
fires `visibilitychange→hidden` (which beacons `/heartbeat?hidden=1`) *before*
`pagehide` (which beacons `/closing`), and the two beacons race on the server —
if a hidden heartbeat cleared `_closing_at` it could cancel the very close it
precedes, so the tab would never shut the server down (this regressed once).

**Work in flight defers the shutdown (the standalone `.exe`).** In `inprocess`
mode the worker runs in the API's OWN process, so exiting on a closed tab
aborted whatever it was doing — a build, or a 20-minute Demucs separation — and
left that job stuck at `RUNNING` in the database with nothing left to finish it.
`_should_shutdown` now takes `work_in_flight` and defers ALL THREE triggers
while it is true; the close reason is remembered and applied the moment the
queue drains, so closing the tab lets the work complete and the bundle is there
on the next launch. `inprocess.work_in_flight()` counts tasks that are **queued
as well as running** — the pool holds one worker, so a rebuild can sit behind a
separation, and exiting between the two would lose the queued one. Every heavy
stage is bounded by its own timeout (`DEMUCS_TIMEOUT_S`/`WHISPERX_TIMEOUT_S`/
`FFMPEG_TIMEOUT_S`), so this cannot defer forever. `_work_in_flight()` returns
False under **Celery**, deliberately: that worker is a separate process which
survives the API exiting, and a job left at `RUNNING` there is a stale row from
a dead worker — waiting on it would hang shutdown forever. `inprocess.shutdown()`
(which existed with no caller) is now wired to the lifespan teardown.

**Do NOT treat missing heartbeats as "closed."** A backgrounded/minimised tab
has its JS timers throttled or frozen by the browser, so its heartbeats stop
even though it's still open — treating that 15s silence as a close (the old
behaviour) killed the API out from under an idle-but-open tab, and every
subsequent rebuild/delete silently failed. Two guards fix this:
- The UI marks the tab hidden via Page Visibility: `ping(document.hidden)` sends
  `POST /heartbeat?hidden=1` (a `sendBeacon`) on `visibilitychange`, and
  `/heartbeat` sets `_tab_hidden`. While `_tab_hidden`, the idle-kill is
  suspended — only `/closing` (real close) or the long `HEARTBEAT_MAX_S`
  (30 min, crashed-browser safety net) stops the server.
- The watchdog resets its clock when a poll gap exceeds `SUSPEND_JUMP_S` (5s),
  i.e. the process was frozen by system sleep — waking never finds a dead
  server. `pageshow`/`visibilitychange→visible` also re-ping immediately.

So: the server stops on a real tab close (~3s) or after 30 min with no signal at
all, but never merely because you left an open tab backgrounded or the machine
slept. The foreground uvicorn then exits, and `start.bat`'s cleanup (after the
`uvicorn` line) stops the Celery worker and any Redis it launched too. Default
is `0` (disabled) — required for shared deployments (docker-compose) where one
user's closed tab must not stop the service for everyone.

`start.bat` runs uvicorn **without `--reload`**: the reloader's parent/child
split would fight the SIGTERM (the child gets restarted instead of exiting), so
a single uvicorn process is used for a clean tab-close shutdown. It also opens
the browser automatically — a background PowerShell one-liner polls port 8000
and launches `http://localhost:8000` once the API accepts connections.

## Conventions

- Keep the honesty: surface warnings via the pipeline's `warnings` list, never
  invent metadata, label confidence explicitly.
- Match surrounding code style. The codebase comments only to state non-obvious
  constraints (often citing the research doc section), not to narrate.
- **Errors: typed at port boundaries, `ValueError` for internal invariants.** A
  pipeline-stage adapter (an `application.ports` implementation) raises the
  matching `RockForgeError` subclass (`IngestionError`/`NormalizationError`/
  `SeparationError`/`PackagingError`) so the use case/API can map the failing
  stage; a pure `domain/` invariant or a fixed-spec binary parser/writer
  (`packaging/psarc` SNG/container/crypto) raises a bare `ValueError`. Full rule
  in `domain/errors.py`'s module docstring.

## Working method (how to make changes here)

A short playbook for working in this repo. It complements the hard constraints
above; when the two conflict, the constraints win.

- **Plan non-trivial work first.** For anything 3+ steps or with an
  architectural decision, write the plan down (`tasks/todo.md`, checkable items)
  before editing, and adjust it as you learn. Simple, obvious fixes skip this —
  don't over-engineer.
- **Use subagents to keep context clean.** Offload research, codebase mapping,
  and parallel analysis to subagents (one focused task each). Before deleting a
  module, have a subagent (or a grep sweep) map its full surface — *this repo
  shares symbols across "separate" modules* (e.g. `PipelineResult` lived in the
  audio `pipeline.py` but was imported by `gp_pipeline.py`), so "only X imports
  it" must be verified, not assumed.
- **Verify before calling it done.** Never mark work complete on a green
  typecheck alone. Run `pytest` + `ruff check src tests` + `mypy` (all three
  green — the hard rule), and for a behavioural change exercise the actual path
  (drive the endpoint / `node --check` the inline UI JS / diff behaviour vs the
  previous version). If tests fail, say so with the output.
- **Prefer the elegant, minimal-impact change.** Find the root cause, not a
  patch over it; touch only what's necessary and match the surrounding style, so
  a change introduces no new side effects. If a fix feels hacky, redo it properly.
- **Fix reported bugs autonomously.** Point at the failing test / error / log,
  diagnose, and resolve it without asking for hand-holding — then verify.
- **Capture lessons after a correction.** When the user corrects a mistake,
  append the pattern (and the rule that prevents it) to `tasks/lessons.md`, and
  skim that file at the start of a session. Ruthlessly iterate so the same
  mistake doesn't recur.
