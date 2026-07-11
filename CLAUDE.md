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

### Automatic sync proposal (`/jobs/{id}/auto-sync`)

`POST /jobs/{id}/auto-sync` (GP jobs only) detects the recording's tempo and
first onset with librosa (`detect_tempo_and_onset`, ml extra) and combines them
with the GP file's authored tempo via the pure `suggest_sync(gp_bpm,
detected_bpm, first_onset_s)` (in `gp_pipeline.py`) into a proposed
`(tempo_scale, offset_s)`. Beat trackers report the tempo at the wrong metrical
level, so `suggest_sync` picks the multiple of `detected_bpm` from
`_TEMPO_METRICAL_FACTORS` — not just the octave (½/2) but the triplet/compound
grid (⅓, ⅔, 3/2, 3) — whose `tempo_scale` lands closest to 1.0 (same song →
ratio near unity). Including the triplet grid fixes the "auto-sync jumps the BPM
~50%" case: a 3/2 detection had no nearby octave to snap to, so the old ½/1/2
set proposed a bogus ×1.5. The endpoint **returns the
proposal only** — the tab viewer loads it into the live preview so the user
confirms over the waveform and commits via the normal rebuild; nothing is
silently applied (honesty principle). Detection is a module-level function so
tests monkeypatch it without librosa (`test_auto_sync_proposes_alignment`).

**Pinpointing the first note (offset_s).** Because `offset_s` is *the recording
second the first note is heard* and `audioTime()` is exactly that (the un-padded
recording clock behind the sample-accurate Web Audio playhead), the sync panel
has a **"Início = cursor"** button that sets `offset_s` to the current playhead:
scrub/click the waveform (zoom in for precision) or play to the first attack,
then lock it — far more precise than typing a number by ear. **±0.01** buttons
fine-nudge it. **"Detetar 1ª nota"** is a guided 3-click flow (`firstNoteFlow`):
arm it, click the waveform where the first note's sound starts (a green dashed
marker; re-click to adjust), then click the first note — a single uniform-shift
anchor moves it (and every note with it) onto that instant. All feed the same
live preview + normal rebuild.

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
path.) True note *editing* — moving a note to a different beat in the chart
itself, not just for sync — remains a separate, larger future feature; today
notes come exact from the GP file.

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
once at job creation (and by "✨ Sincronização automática", a distinct
whole-recording proposal); but Step 1's runtime precision tools in the tab
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
(which now only fires from `initSync`'s initial load and the auto-sync
proposal). All write into the SAME per-tab pending anchor array Step 3
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

The viewer's **playback + waveform work for audio-ML jobs too** (upload/YouTube),
not just GP — the notes were transcribed FROM the recording so they're already
at recording time. For non-GP jobs the frontend uses identity sync
(`isGpJob()` guards `previewScale`/`playheadDisplay`/`viewOrigin`), hides the GP
sync controls (`#gpSyncControls`), and still decodes the recording for playback.
`GET /jobs/{id}/source-audio` serves `job.source` when it's a real file
(upload/gp) and otherwise falls back to the ingested `input.*` / `normalized.wav`
in the job's work dir — so YouTube jobs (whose `job.source` is a URL) are still
playable.

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

### Web UI: creation wizard + "Estado do PSARC" completeness panel

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
creating/updating the DLC Builder project (DLC Builder generates the in-game DDS
textures itself). Honesty note: this is NOT yet converted to an in-game DDS
texture/`albumArt` URN — the Song2014 XML `albumArt` field
(`infrastructure/rsxml/writer.py`) stays empty in both DLC Builder and native
PSARC output, same as building without a cover set.

### Automatic tone detection (`/jobs/{id}/detect-tones`)

`POST /jobs/{id}/detect-tones` (any job type: GP, audio, YouTube) runs Demucs
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

`decodeWaveform` branches on `audioSourceName`: `synth:<kind>` → synthesize,
else fetch `/stem/{name}` or `/source-audio`. Changing the dropdown re-decodes
and restores the playhead; `loadStems` repopulates the selector on reopen (synth
options always; stems if already computed) without re-running Demucs.

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
notes), ChordNotes, Vocals (+ symbol stubs if present), PhraseIterations, 6 ×
empty (PhraseExtraInfo/NLD/Actions/Events/Tones/DNAs), Sections,
ArrangementLevels (anchors, **anchor extensions**, notes with NextIter/PrevIter
linkage), Metadata. `NoteMask` values are the real Rocksmith constants (ported
from Constants.cs).

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
- **Simplified DDC (Dynamic Difficulty)**: `from_arrangement` emits several
  `ArrangementLevels` shaped like a real DDC pass (verified by decoding a DLC
  Builder reference SNG: 23 levels, per-phrase ceilings graduated by density,
  per-iteration hero triples of ~(¼,½,1)·max). Each **phrase's** ceiling scales
  with the note count of its BUSIEST iteration (`phrase_max = min(_DD_LEVEL_CAP,
  busiest-1)`), so each phrase's difficulty bar gets its own HEIGHT instead of a
  flat top. `_DD_LEVEL_CAP = 20` matches a real DDC's range — a decoded pro CDLC
  (Animals As Leaders "Tempting Time") spreads phrase max-difficulties 0..18. The
  cap is a HARD clamp (not a proportional rescale): it preserves the natural
  0..~18 spread of most phrases and only flattens the handful of extreme-density
  outliers (a fast tapping run can hit 50-70 notes/iteration) at the top. The
  song's `max_difficulty` is the max over phrases, and there are
  `max_difficulty + 1` levels (up to 21). At level `d`, each iteration shows the strongest-beat prefix of its
  notes scaled by `d` against that phrase's ceiling (`_level_notes`, ranked by
  `_note_tier` then time), so level 0 is the strongest beats and the top level is
  the full chart. `phrase_iterations[].difficulty` is the `(round(max/4),
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
Remaining honest gaps: the Dynamic Difficulty is a simple mechanical density
ramp (not a musical DDC pass — see the SNG note); and the SNG binary is
round-tripped but not byte-diffed against retail. The **trustworthy path remains
the DLC Builder bundle** (import it and let DLC Builder build the PSARC + a real
DDC pass).

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
  `YouTubeIngestor` runs yt-dlp as a subprocess with `stdin=subprocess.DEVNULL`
  + `YOUTUBE_TIMEOUT_S` + `--no-playlist` (a `watch?v=…&list=…` URL otherwise
  downloads the whole playlist and looks like an endless hang at `ingest`) — it
  used to call the yt_dlp *library*, whose internal ffmpeg child could inherit
  stdin and hang. Guarded by `test_ffmpeg_normalizer.py`. Don't drop these when
  touching the subprocess calls.
- **YouTube ingestion is gated by `ROCKFORGE_ENABLE_YOUTUBE`** (currently
  defaulting on at the operator's request) — downloading audio violates the
  YouTube ToS, so the gate stays so it can be turned off. PSARC/.wem packing
  needs a local Wwise (Audiokinetic EULA forbids redistribution); RockForge only
  *invokes* an installed copy.
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
fake WwiseConsole (`test_wwise.py`), passthrough stages (`test_pipeline.py`),
stubbed Celery enqueue + per-test SQLite (`test_api.py`). When you add an
adapter, add a fake-driven test at the same boundary rather than mocking deep
internals. 233 tests; `pytest` + `ruff check src tests` + `mypy` must all be
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
