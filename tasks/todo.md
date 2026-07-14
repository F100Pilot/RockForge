# Working scratchpad

Short-lived plan/checklist for the change in progress. `TODO.md` (repo root) is
the durable feature list; this file is the working notes for the current task.

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
