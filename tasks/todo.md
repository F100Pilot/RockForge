# Working scratchpad

Short-lived plan/checklist for the change in progress. `TODO.md` (repo root) is
the durable feature list; this file is the working notes for the current task.

## Done: sync from the drum stem via a neural downbeat tracker (Beat This!)

Motivation: the user's AI-generated tabs only align via a RIPX-exported MIDI
tempo map, because librosa reads the wrong metrical level on fast/dense metal
(184.6 BPM on a ~175 song) even on the isolated drum stem. "Create a MIDI from
the stem" = detect downbeats with a proper neural tracker on the drum stem the
app already separates, then feed those measure-downbeats into the SAME
`align_chart_to_midi` path as the MIDI import — an in-app RIPX equivalent, no
DAW export needed. The MIDI is just a format; the real lever is a better
detector than librosa.

- [x] `pyproject.toml`: new optional extra `beatthis` (CPJKU/beat_this, MIT,
      torch-based; `dbn=False` so it does NOT pull madmom).
- [x] `infrastructure/rhythm/beatthis_adapter.py`: module-level
      `detect_downbeats(audio) -> list[float]` (measure-downbeat seconds), lazy
      import, CPU by default (sidesteps the Turing/cuDNN torch crashes),
      monkeypatchable like the librosa fns.
- [x] `interfaces/api/app.py`: `POST /jobs/{id}/sync-from-stem` → `DynamicSyncOut`.
      Reuses `_drum_stem(params)` (falls back to full mix), reads `gp_bars` like
      `sync_from_midi`, trims detected downbeats so `measures[0]` = the pinned
      bar (nearest rec_start), then `align_chart_to_midi(gp_bars, measures, …)`.
      `used_drum_stem` in the response; 503 when beat_this absent.
- [x] `web/index.html` + `web/app.js`: "🥁 Sincronizar pela bateria (IA)" button
      next to the MIDI import, `wireSyncFromStem` mirroring `wireSyncFromMidi`
      (POST, no upload; same pin + preview + "Aplicar e reconstruir"). New INFO
      entry `sync-from-stem` (honest: neural estimate, not ground truth like the
      RIPX MIDI; separate instruments first for a cleaner drum signal).
- [x] Tests: `test_api.py` monkeypatching `detect_downbeats` (maps bars to
      detected downbeats; respects the pin; uses the drum stem when present;
      rejects non-GP). Full-mix fallback exercised by the map/pin tests (no stem).
- [x] Docs: CLAUDE.md (new section under the sync features), TESTING.md
      (7a-quater-bis + endpoint table), TODO.md.
- [x] Verify: ruff/mypy/pytest(new)/node --check/eslint green. NOTE: one
      PRE-EXISTING unrelated failure on main (`test_psarc_packer.py::
      test_vocals_get_a_separate_sng_and_manifest`, KeyError 'ArrangementType')
      — confirmed failing before this change via `git stash`; not touched here.

## Done: beat/tempo detection on the isolated Demucs DRUM stem

Motivation: proven that librosa's beat_track fails on fast dense metal (read
123 BPM on a genuine ~180 BPM song), breaking /auto-sync AND /auto-sync-dynamic.
Fix: run the tempo-critical detection on an isolated drum stem (drums = the
cleanest beat signal) instead of the full mix. We already have Demucs; the
drums.wav is already produced by htdemucs_6s and persists on disk (sibling of
guitar.wav), just omitted from the playback list. No new dependency.

Design (no detection-function signature changes — endpoints choose the audio):
- [x] `app.py` helpers: `_beat_audio(job)` → drums stem (sibling of the stored
      guitar stem) if on disk, else the source; `_onset_audio(job)` → guitar
      stem if on disk, else the source.
- [x] `/auto-sync`: `detect_tempo_and_onset(_beat_audio)` (tempo+onset from drums).
- [x] `/auto-sync-dynamic`: `detect_beats(_beat_audio)` (grid from drums) +
      `detect_onsets(_onset_audio)` (guitar attacks for phase).
- [x] `/detect-tempo`: `detect_tempo_from(_beat_audio, from_s)`.
- [x] Surface in the responses whether drums were used (transparency), and a
      one-line warning/hint when the full mix was used (separate first).
- [x] Tests: with a fake guitar+drums stem on disk, the endpoint passes the
      drums/guitar paths to the (monkeypatched) detection fns; fall back to
      source when absent.
- [x] Frontend: hint in the auto-sync / dynamic-sync info that separating
      instruments first makes detection much more reliable (uses isolated drums).
- [x] Docs: CLAUDE.md (detection-on-drums section), TESTING.md.
- [x] Verify: ruff/mypy/pytest/node --check/eslint green.

## Done: copy/paste notes (extends the note editor)

- [x] "📋 Copiar" / "📥 Colar no cursor" buttons + Ctrl+C/Ctrl+V. Frontend
      only — no backend change (a pasted note is just another
      `note_overrides` upsert). `copySelectedNotes()` reads `selectedTimes`
      from the live merged note list, normalizes to `dTime` offsets;
      `pasteNotesAtCursor()` re-anchors at the playhead (only the first note
      snaps to the grid, `nearestGridChartTime`; the rest keep relative
      spacing). Works across arrangements (copy Lead, paste into Rhythm).
      Clipboard (`noteClipboard`) is in-memory JS state, cleared on job load.
- [x] Docs: CLAUDE.md ("Note editor" section, copy/paste paragraph),
      TESTING.md (7a-septies items 8-10), TODO.md (added under the note
      editor bullet).
- [x] Verify: node --check/eslint green (frontend-only change, no backend
      diff — pytest/ruff/mypy unaffected, re-ran anyway to confirm);
      Playwright smoke exercising copySelectedNotes/pasteNotesAtCursor
      end-to-end confirms relative spacing + note attributes preserved.

## Done: note editor (add/edit/delete notes + techniques on the score)

- [x] Backend: `GpJobSpec.note_overrides: dict[str, list[NoteOverride]]`
      (per-arrangement, unlike tone_changes/section_overrides), applied in
      `gp_pipeline.py` after parse+warp+mute-strip via `_apply_note_overrides`
      (keyed (time,string) upsert/delete patch). `RebuildIn.note_overrides`
      (null-sentinel, Field-constrained string 0-5 / fret 0-24). Celery
      reconstruction. Tests in `test_gp_pipeline.py`/`test_api.py`.
- [x] Frontend: "Editar notas" (✏️) sync mode, `#noteEditPopup` (mirrors the
      bar-align popup), `noteOverridesByKind` state (always-sent, no dirty
      flag needed — no prior default to lose), `mergeNoteOverrides` (visual
      merge only, spliced into showArr's note-drawing loop), per-note
      `data-string` click targeting, `nearestGridChartTime` for placing new
      notes on the snap grid without inverting the warp chain.
- [x] Docs: CLAUDE.md ("Note editor"), TESTING.md (7a-septies), TODO.md
      (marked done, honest limits noted: bound by the song's own tempo map,
      chords built one note at a time).
- [x] Verify: ruff/mypy/pytest/node --check/eslint all green; Playwright
      smoke of mergeNoteOverrides + nearestGridChartTime.

## Done: batch processing + section editor

### 1. Section editor (backend)
- [x] `application/gp_pipeline.py`: `GpJobSpec.section_overrides: list[Section] | None = None`.
      When not None, replaces the GP-parsed `p.sections` for EVERY arrangement
      (job-level convention, same as `tone_changes` — bundle-clock times, no
      per-arrangement warp applied to overrides).
- [x] `interfaces/worker/celery_app.py`: reconstruct `section_overrides` from
      `params.get("section_overrides")` (None vs explicit list).
- [x] `interfaces/api/app.py`:
      - `SectionOut` (time, name, number) + `ArrangementOut.sections`; parse
        `<sections><section>` in `get_arrangements`, excluding the writer's
        synthetic trailing `"noguitar"` sentinel.
      - `RebuildIn.section_overrides: list[SectionOverrideIn] | None = None`
        (null-sentinel convention); write into `params["section_overrides"]`
        in `rebuild_job` when not None.
- [x] Tests: `test_gp_pipeline.py` (override applied / None falls back / empty
      list clears), `test_api.py` (arrangements expose sections minus
      noguitar, rebuild round-trips section_overrides).

### 2. Section editor (frontend)
- [x] New sync-mode button "modeSection" (🏷️): click a note to add a section
      marker there (prompts for a name).
- [x] New panel "🏷️ Secções": editable rows (time, name, remove), "+
      Adicionar no cursor".
- [x] State: `songSections` (shared across arrangements like `toneChanges`),
      `sectionsTouched` dirty flag gating `section_overrides` on rebuild (None
      otherwise, so untouched GP sections survive unrelated rebuilds). Seeded
      from `arrangements[0].sections` in `loadArrangements`.
- [x] Score overlay: labeled marker (dashed line + badge), distinct from
      tone-change markers.
- [x] `applyAll()` sends `section_overrides: sectionsTouched ? songSections : null`.
- [x] New INFO entry "sections"; update "sync-modes" INFO body.

### 3. Batch processing (frontend only, loops existing endpoints)
- [x] "📦 Processamento em lote" modal: multi-file GP picker + multi-file
      audio picker, paired by matching filename stem (fallback: order),
      shared album/year fields.
- [x] Sequential loop: per pair, `POST /gp/inspect` then `POST /jobs/gp` with
      blank track fields (backend's `auto_pick_tracks` heuristic fills them
      in) — per-row status. No new backend code.
- [x] Honest note: track auto-pick is a name heuristic — fix a wrong pick via
      the existing "✎ Editar info" track re-map + rebuild.

### 4. Docs + verify
- [x] `CLAUDE.md`, `TESTING.md`, `TODO.md` updated for both features.
- [x] `ruff check src tests`, `mypy`, `pytest`, `node --check web/app.js`,
      `npm run lint` all green.

## In progress: aligned gear knobs, one device at a time

- [x] Studio Compressor — `KNOB_LAYOUTS` entry, aligned overlay, values below
- [ ] Studio Graphic EQ, Parametric EQ, Tape Echo, Plate, Chamber (see TODO.md
      for the per-device parameters)
- [ ] Then amps + cabinets

## Done: remove audio→note transcription

- [x] Delete `pipeline.py`, Basic Pitch adapter, role splitter, fret mapper
- [x] Remove `/jobs/upload`, `/jobs/upload-split`, `/jobs/youtube` + helpers
- [x] Trim ports / domain (`clean_transcription`, `suggest_tuning`) / librosa adapter
- [x] Remove audio-mode UI, `basic-pitch`/`onnxruntime`/`[youtube]` deps
- [x] Keep stem separation, tone/lyric detection, GP path — tests green
