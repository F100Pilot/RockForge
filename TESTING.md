# TESTING.md

How RockForge is tested, how to run the suite, and how to verify the parts that
CI cannot. Read this before adding or changing a test.

> **Why this doc exists:** the test suite is the contract. ML, Wwise and DLC
> Builder cannot run in CI, so the tests encode *every* invariant we can check
> without them. If a regression test fails, a real, documented failure mode has
> returned — fix the code, never the test (unless the contract genuinely
> changed). The "Manual / end-to-end" section covers everything CI can't.

---

## 1. Quick start

```bash
pip install -e ".[dev,psarc]"  # core + test tooling + cryptography/Pillow, NO ML stack
pytest                       # the suite, ~10s, all ML/Wwise/external tools faked
ruff check src tests start_standalone.py build_exe.py   # lint
mypy                         # type check
```

**All three gates (pytest, ruff, mypy) must be green before every commit.** CI
runs exactly these. There is no separate "ML test" job — the ML stages are
*faked* (see §3), so the full suite runs on a plain Python 3.11 with no torch,
no GPU, no ffmpeg, no Wwise.

**Install `[psarc]`, not just `[dev]`.** `test_psarc_packer.py` and
`test_psarc_crypto.py` open with `pytest.importorskip("cryptography")`, so
without that extra they skip themselves entirely — **17 tests**, covering the
encrypted PSARC container and the Sng2014 binary, the most delicate output in
the project. CI installed only `[dev]` for a long time and was green the whole
while, having never run any of it; it now installs `[dev,psarc]`, asserts
`import cryptography, PIL` succeeds as its own step (so losing the extra fails
loudly instead of silently dropping the tests), and runs `pytest -rs` so any
remaining skip is printed with its reason. A silent skip is worse than a
failure: it reads as coverage. The one skip that remains is
`test_lyrics_transcribe.py`'s numpy/soundfile case — a deliberate ML boundary.

- **Python 3.11 only** (`requires-python = ">=3.11,<3.12"`). On Windows:
  `py -3.11 -m pytest`. Do not test on 3.12+ — the ml/lyrics stack
  (`torch<2.5`/demucs/whisperx) targets 3.11 wheels and the install itself fails.
- **mypy is pinned** (`mypy~=1.19.0`). Do not bump it casually — CI must match
  local exactly, and minor mypy versions flag different issues.

---

## 2. The philosophy: inject fakes at the port boundary

The architecture (see `CLAUDE.md`) makes every external dependency a `Protocol`
in `application/ports.py`. Tests exploit this: instead of mocking deep library
internals, they **substitute a fake adapter** at the same boundary the real one
plugs into.

- **ML stages** (Demucs, librosa, WhisperX) → passthrough/stub adapters that
  return canned data (`test_lyrics_transcribe.py`, `test_tone_detection.py`).
- **WwiseConsole** → a Python-based fake console that mimics the CLI
  (`test_wwise.py`).
- **Celery enqueue** → monkeypatched so `POST /jobs/...` returns without a
  broker; the task body is then tested separately or directly
  (`test_api.py`).
- **Database** → a fresh in-memory/temp SQLite per test (`test_api.py`).
- **Subprocess tools** (ffmpeg, demucs CLI) → the *command construction* is
  asserted (correct flags, `-nostdin`, `stdin=DEVNULL`, timeout) without
  actually running the binary (`test_ffmpeg_normalizer.py`,
  `test_demucs_adapter.py`).

**Rule:** when you add an adapter, add a fake-driven test at that adapter's
boundary. Do not reach into a third-party library's internals — if the library
changes, the test should still describe *our* contract, not theirs.

The pure layers (`domain/`, parts of `application/`, the rs2dlc/sng/manifest
serializers) need no fakes — they are deterministic and tested directly.

---

## 3. What each gate enforces

| Gate | Command | Enforces |
|---|---|---|
| **Lint** | `ruff check src tests start_standalone.py build_exe.py` | style, unused imports/vars, import order, obvious bugs |
| **Types** | `mypy` | strict on `domain/`/`application/`/`infrastructure/`; relaxed at framework boundaries (FastAPI/SQLAlchemy/Pydantic) via per-module overrides in `pyproject.toml` |
| **Tests** | `pytest` | the functional suite (see §4) |
| **Web lint** | `npm ci && npm run lint` | `web/app.js` (the UI's client script) via ESLint — real-bug rules only (`no-undef`, `no-redeclare`, …), not a style reformat. CI job `web-lint`. |

mypy strictness is deliberate: the `domain` and `application` layers carry the
music model and orchestration logic and must be fully typed. The
`interfaces/api` boundary is relaxed because FastAPI/Pydantic/SQLAlchemy resolve
to `Any` in places mypy can't follow — that's why the JSON-column endpoints use
explicit `cast(...)`.

---

## 4. Coverage map (by file)

Per-file counts below reflect the suite at the time of writing; run
`pytest --co -q` for the live totals.

| File | Tests | Guards |
|---|---:|---|
| `test_domain.py` | 18 | pure music model: `Tuning`, `TabNote`, `TempoMap`, `Arrangement` invariants, sustain gap, high-density flags |
| `test_chords.py` | 10 | `domain/chords.py` `name_chord`: triads, power chords, inversions, chord naming |
| `test_gp_import.py` | 15 | PyGuitarPro (GP3/4/5) parsing: notes/frets/techniques/sections/tempo; per-bar times from outside (Songsterr) re-timing the chart relative to bar 1, and a bar-count mismatch reported |
| `test_gp_arrangement_writer.py` | 7 | generating a NEW GP5 from an `Arrangement`: notes/times/strings/frets and the corrected tempo map round-trip through our own importer, techniques, chords-as-one-beat, tuning/metadata/sections, reported quantization, the always-stated single-track cost, empty beat grid refused |
| `test_gpif_import.py` | 20 | native GP7/GP8 (`.gp`) GPIF/XML parser: tuning, timing, Hopo/slide/palm-mute, lyric sourcing, bass rejection; Guitar Pro 8 audio-track SYNC POINTS re-timing the chart (relative to bar 1), the backing-track padding, repeat/backwards points skipped and counted, the synced average BPM, an unsynced file timed exactly as before, and the recording EMBEDDED in a GP8 file found and extracted (disabled / YouTube-linked / missing / non-audio members read as "none", never an error) |
| `test_gp_pipeline.py` | 38 | GP use case: `tempo_scale`, `sync_anchor_stages`, `arrangement_sync`, lyrics precedence, `pad_start_s` shift, tied notes, section-editor overrides (`section_overrides`), note-editor overrides (`note_overrides` add/edit/delete, per-arrangement) |
| `test_rsxml_writer.py` | 18 | Song2014 XML: the **32 arrangementProperties** attrs, COUNT/default/END phrase structure, chords |
| `test_vocals.py` | 22 | `parse_lyrics` (LRC + UltraStar), `expand_to_words` (trailing `+`), `events_from_dicts`, `distribute_syllables` (GP lyrics → note-onset alignment, melisma `_`) |
| `test_lyrics_transcribe.py` | 9 | WhisperX adapter: RMS gate, per-word confidence filter, segment→event mapping (whisperx itself stubbed) |
| `test_tone_gear.py` | 11 | `domain/tone.py` gear model + `tone_from_dict`/`tones_from_dicts` |
| `test_tone_detection.py` | 11 | spectral `analyze_guitar_tone` → category → `suggest_tones` + ranked `rank_tones` candidates |
| `test_tone_library.py` | 5 | cross-project tone library (`/tone-library`): save/read-back, key overwrite, validation |
| `test_rs2dlc.py` | 6 | `.rs2dlc` `DLCProject.Dto` shape, Name/RouteMask per kind, vocals case, **`.phrase-levels`** companion |
| `test_gamedata.py` | 11 | native-PSARC enumeration assets: flatmodels, solid DDS, xblock, aggregategraph, showlights, **real-cover DXT1 conversion** (needs Pillow, from `[psarc]`) |
| `test_psarc_container.py` | 5 | PSARC v1.4 pack/unpack round-trip |
| `test_psarc_manifest.py` | 10 | runtime manifests (`.hsan`, `_aggregategraph.nt`, per-arr JSON) |
| `test_psarc_sng.py` | 50 | Sng2014 binary `write_sng`∘`read_sng` = identity, NoteMask, anchor extensions, DD levels, vocals SNG |
| `test_psarc_crypto.py` | 5 | AES-256-CFB TOC + AES-256-CTR SNG (needs `[psarc]`) |
| `test_psarc_packer.py` | 12 | `NativePsarcPacker` wiring; graceful degrade without `[psarc]` |
| `test_packer_resilience.py` | 1 | the Bundle is still produced when the `.psarc` build raises |
| `test_soundbank.py` | 8 | ported Wwise `.bnk` generator: chunk order, BKHD version, DIDX↔wem id |
| `test_loudness.py` | 6 | `parse_ebur128_i` / `volume_for_loudness` loudness calc (pure, no ffmpeg) |
| `test_wwise.py` | 6 | `.wem` conversion via **fake** WwiseConsole; seek-table header patch |
| `test_ffmpeg_normalizer.py` | 3 | command build: `-nostdin`, `stdin=DEVNULL`, `FFMPEG_TIMEOUT_S` |
| `test_demucs_adapter.py` | 9 | demucs CLI command build, `stdin=DEVNULL`, timeout, vocals vs guitar models, `separate_stems` returns all stems, guitar-stem cache reuse |
| `test_banquet_adapter.py` | 5 | Banquet (EM TESTES) `inference_byoq` command build, one pass per query clip, device→`use_cuda`, missing-setup errors |
| `test_device_resolution.py` | 8 | `_resolve_device` auto/cpu/cuda + degrade-to-CPU on import failure |
| `test_tags.py` | 2 | audio metadata tag extraction |
| `test_api.py` | 105 | every endpoint (§6): job lifecycle, rebuild composition, detect-* / separate-stems enqueue (mocked), auto-sync + dynamic beat-alignment (faked librosa) + MIDI-tempo-map sync, section + note overrides, lyrics/tones/stems status, gear images, deletion, per-test SQLite |
| `test_settings.py` | 10 | in-app settings (`/settings`): default demucs, persist+read-back, invalid separator 422, Banquet path validation, empty-string clears override |
| `test_diagnostics.py` | 15 | the external-software report (`/system-check`): every row carries its cost and its fix, what cannot be checked reports UNKNOWN rather than missing (the CDLC patch, a CUDA build of torch), ffmpeg's version parsed and a non-answering binary still reported as found, Wwise distinguishing unset-variable from wrong-folder, a broken install reading as absent instead of raising; that the ML rows follow the interpreter that will RUN the work (in the `.exe` a different Python entirely) and say where they looked, that one which does not start is reported as that rather than as a missing Demucs, that nothing is probed when this process IS that interpreter, and that the `.exe`'s install instruction points at ⚙️ Definições instead of claiming the feature is unreachable — and a guard that fails if the probe ever starts IMPORTING torch/demucs/librosa/whisperx |
| `test_celery_tasks.py` | 9 | the actual `@celery_app.task` function BODIES — `generate_cdlc`/`detect_tones`/`separate_stems`/`detect_lyrics` called directly (not `.delay()`) against a per-test SQLite `Job` row, heavy adapters faked; success + never-crashes-on-failure paths |
| `test_db_schema.py` | 3 | the startup schema check: fresh DB accepted, a column dropped from an existing DB fails loudly naming it, and the check itself never blocks startup |
| `test_architecture.py` | 2 | Clean Architecture layering: `application/ports.py` imports zero `infrastructure/`; other `application/` files only the explicitly-accepted exceptions |
| `test_standalone_spec.py` | 4 | the PyInstaller spec bundles EVERY file under `web/` (executes `rockforge.spec` with stubbed builders and inspects the real `datas`), puts them where the server looks, index.html references nothing that isn't bundled, and every ML runner (`_*_runner.py`/`_demucs_patcher.py`) ships as a real file at its package path — another interpreter has to be able to EXECUTE it |
| `test_songsterr.py` | 12 | Songsterr's per-measure timestamps, against a FAKE `get_json` (the API is undocumented and unreachable from CI and the sandbox): the song id from a link or a number (the LAST `-s<digits>`), videos ordered like guitar-pro-youtube-sync picks them (default → worldwide alternative → alternatives → the rest; not-done, point-less and duplicate entries dropped), the revision taken from `meta` and used for the points, and every changed shape or unreachable host as a clear `SongsterrError` |
| `test_ml_python.py` | 16 | which interpreter the heavy ML stages run on: a Python install resolves to itself (the old path, byte for byte), a frozen build to None rather than to the `.exe` (running it would relaunch RockForge), a configured path wins over both; the per-extra probe and its failure modes (not a Python / non-zero / non-JSON / missing — every one a False, never an exception); the real subprocess transport, driven against `_librosa_runner.py` with a stub librosa; that a missing librosa fails loudly instead of printing a fabricated tempo; that the librosa measurements have ONE implementation (neither adapter may grow its own `import librosa`); and — by PARSING the call sites, since they now explain in comments why it is gone — that none of them passes `sys.executable` |
| `test_standalone_launcher.py` | 18 | the standalone launcher's decisions, with no GUI: the worker-mode/idle-shutdown defaults (and that an explicit setting still wins), the close-confirmation logic, the readiness poll, the ffmpeg PATH order, the log fallback, and — against a fake `webview` — that the window opens on the local API, that its close handler is wired to `work_in_flight`, and that both failure paths release the port |

### Key regression tests — do not delete these without understanding why

These guard failure modes that **shipped broken once**. The test name is the
incident report.

- `test_phrase_structure_marks_song_end` — Rocksmith ends playback at the last
  `phraseIteration`; removing the END phrase makes the song never end.
- `DLC_BUILDER_REQUIRED_ARRPROP_ATTRS` (in `test_rsxml_writer.py`) — all 32
  `arrangementProperties` attrs must be emitted or DLC Builder import throws an
  NRE (it dereferences each without a null check).
- `test_ffmpeg_normalizer.py` — the `-nostdin`/`stdin=DEVNULL` guards; without
  them ffmpeg goes interactive and hangs the `normalize` stage forever.
- `test_write_rs2dlc_creates_phrase_levels` — DLC Builder needs a
  `.phrase-levels` companion file or the build throws `FileNotFoundException`.
- `test_gp_lyrics_events_precedence` — edited lyrics must win over
  LRC/GP-embedded/auto-WhisperX.
- `test_spec_bundles_every_web_file` (`test_standalone_spec.py`) — the
  PyInstaller spec listed its web files BY HAND, so when 4107 lines of JS were
  extracted out of `index.html` into `web/app.js` the list silently didn't
  follow. The shipped `.exe` served an `index.html` whose `<script src="/app.js">`
  had nothing behind it: the whole UI was inert, and no gate could see it. The
  spec now walks `web/` and this test executes it (with the PyInstaller builders
  stubbed) to check the real `datas` against the folder.
- `test_work_in_flight_defers_every_shutdown_trigger` (`test_api.py`) — in the
  standalone `.exe` the worker shares the API's process, so closing the tab
  aborted a running build and left its job at `RUNNING` forever. Asserts each
  trigger still fires once the queue drains, so the deferral can't become a
  server that never exits.
- `test_tuning_rejects_an_impossible_pitch_at_construction` (`test_domain.py`) —
  `Tuning` had no invariant, so a nonsense pitch reached the SNG writer's int16
  pack and died there as a `struct.error` pointing at nothing. Pins real drop
  tunings as still valid, so the guard can't be tightened into a regression.
- `test_deleting_a_job_removes_its_gp_file_but_not_a_forks` (`test_api.py`) —
  the GP upload lives outside the job's work dir, so deleting a job used to leak
  it forever; and a rebuild fork shares `gp_path`, so the delete must be
  reference-counted or it pulls the file out from under the fork.
- `test_the_orphan_sweep_actually_runs_on_startup` (`test_api.py`) — drives a
  real lifespan. Nothing else calls the sweep, so testing the function alone
  would pass while the feature did nothing.
- `test_non_finite_floats_are_rejected_at_the_boundary` (`test_api.py`) — JSON
  carries `NaN`/`Infinity`, Pydantic accepted them, and `NaN <= 0` is False, so
  the tempo guard waved them through into the persisted params. It also asserts
  the 422 BODY encodes: FastAPI echoes the rejected input and Starlette uses
  `allow_nan=False`, so without `_json_safe` the refusal came back as a 500.
- `test_missing_ml_extra_reports_503_not_a_confusing_422` (`test_api.py`) — the
  ImportError must be caught around the CALL; a module-level import guard is
  dead code, because the adapters import librosa inside their function bodies.
- `test_bundled_web_files_are_found_in_the_pyinstaller_bundle`
  (`test_api.py`) — the other half of the same incident: inside the `.exe` the
  UI lives under `sys._MEIPASS/web`, which neither of the other two path
  candidates reaches (`__file__` points into the frozen archive; the launcher
  never chdirs). `_web_file_candidates()` must try `_MEIPASS` first.

---

## 5. How to add a test

1. **Find the boundary.** Is it pure logic (`domain`/serializer) or an adapter
   over an external tool?
2. **Pure logic** → call it directly, assert the output. No fakes.
3. **Adapter** → either (a) assert the *command/payload it builds* without
   running the tool (ffmpeg/demucs pattern), or (b) inject a fake implementing
   the same `Protocol` and assert the use case threads data correctly
   (pipeline pattern).
4. **Endpoint** → use the FastAPI `TestClient` in `test_api.py`, monkeypatch
   the enqueue function, and use the per-test SQLite fixture. Assert status
   code + the `params` mutation, not the async task result.
5. **Name the test after the behaviour/incident**, not the function. A future
   reader should understand *why it exists* from the name.

Example — adding an adapter test at the port boundary:

```python
def test_new_separator_builds_correct_command(monkeypatch):
    captured = {}
    def fake_run(cmd, **kw):
        captured["cmd"] = cmd; captured["kw"] = kw
        return subprocess.CompletedProcess(cmd, 0, "", "")
    monkeypatch.setattr(subprocess, "run", fake_run)
    MySeparator(device="cuda").separate(Path("in.wav"), tmp_path)
    assert "-d" in captured["cmd"] and "cuda" in captured["cmd"]
    assert captured["kw"]["stdin"] is subprocess.DEVNULL   # never inherit stdin
```

---

## 6. API endpoints (all exercised by `test_api.py`)

```
POST   /gp/inspect                   list tracks in a GP file (pre-job)
POST   /jobs/gp                      create job from GP file + recording
GET    /jobs                         list all jobs
GET    /jobs/{id}                    one job
DELETE /jobs/{id}                    delete job + its files
POST   /jobs/{id}/rebuild            rebuild with new params (composes sync rounds)
POST   /jobs/{id}/reload-gp          swap the GP file, keep all overrides   [GP]
GET    /jobs/{id}/sync-state         export hand-tuned sync as portable JSON
POST   /jobs/{id}/import-sync        apply an exported sync + rebuild (202)
POST   /jobs/{id}/detect-tempo       per-point tempo from a clicked instant [GP, ml]
POST   /jobs/{id}/detect-tuning      propose cent offset               [ml extra]
POST   /jobs/{id}/detect-lyrics      async lyric detection (202)       [ml+lyrics]
GET    /jobs/{id}/lyrics             lyric status + events + log
POST   /jobs/{id}/detect-tones       async tone detection (202)        [ml extra]
GET    /jobs/{id}/detected-tones     tone status + suggested presets + log
POST   /jobs/{id}/separate-stems     async stem separation (202)       [ml extra]
GET    /jobs/{id}/stems              stem status + available stem names + log
GET    /jobs/{id}/stem/{name}        one separated stem (audio-source selector)
GET    /jobs/{id}/tones              current tone setup
POST   /jobs/{id}/export-gp          write tempo fixes into a copy of the GP [GP]
POST   /jobs/{id}/export-arrangement-gp  generate a new GP5 from one built chart [GP]
GET    /jobs/{id}/corrected-gp       download whichever GP export ran last  [GP]
GET    /jobs/{id}/arrangements       per-arrangement tab/sync data for the viewer
GET    /jobs/{id}/source-audio       the recording (for the waveform)
GET    /jobs/{id}/bundle             the DLC Builder bundle zip
GET    /jobs/{id}/psarc              the native .psarc (if produced)
POST   /jobs/{id}/cover              upload album art
GET    /jobs/{id}/cover              serve album art
GET    /gear-catalogue               tone gear catalogue (for the tone editor)
GET    /system-check                 what external software this machine has
POST   /heartbeat                    idle-shutdown ping (UI keepalive)
GET    /version  GET  /              version + the web UI
```

---

## 7. Manual / end-to-end testing (what CI CANNOT cover)

CI fakes everything heavy. These checks need a real machine and must be done by
hand when touching the relevant path. **Nothing below runs in CI.**

### 7a. GP → CDLC (the high-fidelity, ML-free path — test this first)

1. `start.bat` (Windows) or `docker compose up`. Open `http://localhost:8000`.
2. "Inspecionar pistas" on a GP3/GP4/GP5 + recording → pick Lead/Rhythm → create.
3. Open the job → tab viewer: drag "Início da música", adjust BPM, drag notes
   to correct drift, "Aplicar e reconstruir".
4. Download the bundle → open `arrangement_*.xml` in EOF, or import into DLC
   Builder. **This is the validation that counts** — the XML format is de facto.

#### GP sync gotcha: constant tempo vs. tempo changes

A **single offset** aligns the whole song ONLY when the recording's tempo
matches the GP's at every point. This is true for a **constant-tempo** GP
(one `<Automation Type="Tempo">`): align the first note and you're done.

A GP with **tempo changes** (multiple tempo automations, e.g. a half-time intro
at 94 BPM that jumps to 186) is different: the parser places every note at the
correct tick *per the GP's tempo map* (verified — bar downbeats land exactly,
the bundle's `<ebeats>` carry the speed-up), but if the *recording's* tempo
deviates even ~1–3% from the GP, or its tempo change lands a beat off, the chart
will "sync at the start, then drift." This is **not a parser bug** — it's a
GP-vs-recording mismatch, and it's exactly what the drift-correction tools are
for:

- Leave the **BPM/`tempo_scale`** at the built value unless the drift is uniform
  across the whole song (then nudge it ±a few %).
- Use the **measure numbers** in the viewer to find where it slips, then drop a
  **sync anchor** there. Anchor the slow section and the fast section
  independently (anchors compose across rebuilds).

To diagnose a specific pair offline: the recording's onset grid can be compared
to the GP note onsets (`parse_gp_track`), but a dense full-mix (drums/vocals/two
guitars) makes a sub-3% tempo difference hard to measure reliably — the
interactive tab viewer with live preview is the practical tool.

**To verify (manual):** open a GP job whose file has a mid-song tempo change
authored on a NON-instrument track (a dedicated tempo track, or another guitar)
— e.g. 93 BPM → 186 at bar 64. In the tab viewer the `♩=NNN` markers must switch
at the change (not stay at the initial BPM), the bars must bunch up in the fast
section, and the beat spacing must halve. Regression-guarded for the parser by
`test_tempo_change_on_other_track_is_detected`, but confirm the full build →
viewer path on a real file.

#### Out-of-range notes are dropped **with a warning**

Both GP parsers skip notes off the 24-fret neck (fret < 0 or > 24, or — GP7 — on
a string beyond the tuning); this used to be silent. Now the job's warnings list
carries `"<Kind>: N note(s) dropped: off the 24-fret neck…"`. **Manual check:**
pick a track that has an extended-range/bass passage (or a note above fret 24)
and confirm the warning appears (and the rest of the chart still builds).
`TabNote` still rejects an invalid fret at construction, so this is transparency
about the drop, not new validation. Guarded by
`test_gp7_out_of_range_note_dropped_with_warning`.

### 7a-bis. Per-track note start + note-adjustment precision (browser only, no ML/Wwise)

Pure `web/index.html` changes — no backend/model change, so there's nothing
for `pytest` to guard here; verify by hand in the browser on a GP job with at
least Lead + Rhythm.

1. **"Passo 1 — Início da música" is per-track (ONE field, not two)** — on the
   Lead tab, use the numeric field, "Início = cursor", and the guided "🎯
   Detetar 1ª nota" flow to move Lead's first note — confirm Rhythm's chart
   does NOT move. Switch to the Rhythm tab and confirm Step 1's field now
   shows RHYTHM's own first-note position (not Lead's, and not frozen at
   whatever Lead was set to), independently adjustable. Switch back to Lead
   and confirm its value is still what was set. Confirm the correction rides
   the normal "Aplicar e reconstruir" (no separate commit button) and
   survives a rebuild + reopen. There must be exactly ONE "first note time"
   control in the sync panel.
2. **Cursor snap for dragging** — set "Encaixar em:" to "Cursor de reprodução",
   play the recording, drag a note mid-playback — it should land exactly on the
   playhead, not the nearest beat. This is the fix for "arrastar para o cursor
   nem sempre funciona".
3. **Numeric anchor editing** — drag a note to create a correction, then edit
   its target-time number directly in the pending-anchors list below the score
   and confirm the note redraws at the typed value. Also confirm the list
   updates IMMEDIATELY after a plain drag (previously it only refreshed after
   "Marcar"/"Mover seguintes"/"Novo beat" clicks, not a drag).
4. **Zoom keeps its place** — scroll to a specific passage, zoom in/out with
   `+`/`−`/keyboard shortcuts — the same passage should stay in view instead of
   jumping to an unrelated part of the song.
5. **No native text-selection** — Shift+click one note then another (range
   select), and click-drag a rubber-band box over several notes — confirm no
   browser text highlight appears over the technique letters/tuning
   labels/bar numbers, only the intended note selection.
6. **"Mover seguintes" lands on the cursor** (regression: it used to move notes
   the WRONG way once a pending anchor already existed). First set "Início
   desta pista" for the tab (creating a pending anchor), THEN pause playback
   somewhere later and use "Mover seguintes" on a note — it (and everything
   after it) must land exactly on the playhead, not somewhere else. Repeat for
   "Marcar" (tap) and "Novo beat (detetar)" — same underlying fix.
7. **Sync by bar number** (`barSyncPanel`, below Step 1) — on a job with Lead +
   Rhythm: sync Lead's start via Step 1, switch to Rhythm, pick bar 7 in
   "Sincronizar por compasso", pick "Lead" as the reference, click
   "Sincronizar" — confirm Rhythm's bar 7 visually lines up with Lead's bar 7
   on the score (no manual listening needed). Also try "= cursor": pause
   playback where a bar should sound and click it — that bar (and everything
   after) should jump to the cursor. Confirm the reference dropdown never
   offers the current tab itself.
8. **Bar-align popup** (📏 mode) — select the 📏 mode, pause playback where a
   bar should sound, click a note: a popup opens with the note's own bar
   pre-selected. "= cursor" pins that bar to the playhead; "= pista" (only with
   ≥2 arrangements) pins it to the reference track's same bar. Do it at several
   points along the song and confirm the drift is corrected piecewise (the
   pending-anchors list grows one entry per pin). The popup should close on
   Escape / outside click and reposition when you click another note.
9. **Full-song width** — open a track that rests through the outro (e.g. a lead
   that stops mid-song) and confirm the score + bar lines + waveform now extend
   to the LAST bar of the song, not just the last note. Guarded only by manual
   check (pure `web/index.html`).
10. **Auto-scroll reaches off-screen notes** (regression: "só dá para
    selecionar o que está visível, não dá para arrastar para o resto das
    notas") — on a long song zoomed in enough that it doesn't fully fit the
    viewport, activate "Excerto", start a rubber-band box near the LEFT edge
    of the visible score, then drag toward and HOLD at the right edge of
    `#tabwrap` (don't release) — the score must auto-scroll right while the
    selection box keeps growing, letting you reach and select notes that were
    off-screen at drag-start. Try the mirror case (hold at the left edge to
    scroll left). Also confirm a single-note drag and a selected-block drag
    ("Arrastar" mode) auto-scroll the same way when held near an edge, and
    that scrolling stops the instant you release the mouse (no runaway
    scroll after `pointerup`).
11. **Audio source doesn't leak across jobs** (regression: "dá música
    sintetizada, mas a seleção está em música mistura") — on job A, pick a
    synthesized source ("`<Kind>` (sintetizada)") in "Fonte de áudio" and
    confirm it plays. Close the job and open a DIFFERENT job B: confirm
    "Fonte de áudio" shows "Mistura completa" AND the full recording is what
    actually plays (not job A's leftover synthesized buffer) — the dropdown
    and the audible source must always agree, even right after switching.

### 7a-ter. Creation wizard + "Estado do PSARC" completeness panel (browser only)

Mostly `web/index.html`; the two completeness signals (`has_tones`,
`sync_edited`) are backend fields guarded by `test_completeness_fields_*` in
`test_api.py`. Manual browser checks:

1. **Wizard flow** — "A partir de Guitar Pro" opens the 4-step modal (🎸→🎚️→💾
   →🏷️). Step 1 requires a GP file; "Seguinte" inspects and advances to step 2
   with the first track auto-assigned to Lead. Step 2 blocks advancing with no
   track; step 3 blocks with no audio (toast). Step 4 shows "✓ Criar CDLC"
   instead of "Seguinte"; "Anterior" walks back. Create still works and opens
   the new job. (Driven headlessly in dev via Playwright against a served
   `index.html` with the API routes stubbed — no assertion errors.)
2. **Completeness checklist** — on a freshly created job (no tones/cover/sync),
   the "Estado do PSARC" card shows an amber banner listing "tons, capa,
   confirmar a sincronização" and three ⚠️ rows, each with a jump-button
   (Detetar tom / Carregar capa / Abrir partitura). Add a tone + a sync anchor +
   a cover, rebuild → those rows flip to ✅ and the banner shrinks/disappears.
   A build with no `.psarc` (no Wwise) shows a ❌ "PSARC não gerado" row. The
   AppID/letra rows are informational (ⓘ), never counted as alerts. The **Letra**
   row reads `has_lyrics` (edited/GP/LRC lyrics OR completed detection), so a
   song that already has lyrics from ANY source shows "✅ Letra incluída" — NOT
   "sem letra" (which used to happen when only `lyrics_status` was checked).

### 7a-quinquies. Section editor (browser only, no ML)

The pure alignment/precedence logic is covered by CI
(`test_section_overrides_*` in `test_gp_pipeline.py`, `test_rebuild_stores_
section_overrides` / `test_rebuild_without_section_overrides_leaves_them_
untouched` / `test_arrangements_excludes_the_noguitar_sentinel_from_sections`
in `test_api.py`). What CI cannot cover is the live tab-viewer wiring:

1. **Default (untouched) sections survive an unrelated rebuild** — open a GP
   job whose file has authored section markers (or none, in which case the
   panel shows the writer's single default "riff"), rebuild with an unrelated
   change (e.g. tuning), and confirm the section list is unchanged — proves
   the dirty-flag gate (`sectionsTouched`) works, not just the backend's
   None-sentinel.
2. **Add a section two ways** — activate the "Secção" (🏷️) sync mode and
   click a note: a prompt asks for a name, and a teal, full-staff-height
   marker appears at that note. Separately, use "+ Adicionar no cursor" while
   the recording is paused mid-song: a marker appears at the current playhead
   without needing to land on a note.
3. **Edit the list directly** — in the "🏷️ Secções" panel, change a marker's
   time number and name text in place; confirm the score marker moves/renames
   live and the list re-sorts by time. Remove one and confirm both the list
   and the score update.
4. **Shared across arrangements** — with Lead + Rhythm both present, add a
   section on the Lead tab, switch to Rhythm, and confirm the SAME marker
   shows there too (the job-level, tone_changes-style convention) — then
   "Aplicar e reconstruir" and reopen the job to confirm it persisted on both
   arrangements' built XML (via `/arrangements`' new `sections` field).
5. **The "noguitar" sentinel never appears** — whatever the song, the section
   list must never show an entry literally named "noguitar" (the writer's own
   end-of-phrase-timeline marker, filtered out server-side).
6. **Honest limit** — if Lead and Rhythm have very different pending
   `tempo_scale`/anchor corrections, confirm (and don't be surprised) that a
   shared section time can land at slightly different musical instants on
   each — documented in `CLAUDE.md`, same accepted simplification as
   `tone_changes`.

### 7a-sexies. Batch processing (browser only, no backend change)

Pure `web/index.html`/`web/app.js` — the batch modal loops the exact same
`/gp/inspect` + `/jobs/gp` calls the single-project wizard makes, so there is
nothing new for `pytest` to guard (same category as 7a-bis/7a-ter). Verify by
hand:

1. **Pairing by filename** — pick several GP files and several recordings
   named to match (`song1.gp5` / `song1.mp3`, case differences and different
   extensions both fine) plus one deliberately mismatched pair (different
   stems) — confirm the preview list pairs the matching ones by name and
   falls back to matching the mismatched one(s) by the order both lists were
   chosen. Pick one extra GP file with no corresponding recording at all and
   confirm its row reads "sem gravação — não vai ser criado" and it's
   excluded when clicking "Criar projetos" (not silently paired wrong).
2. **Shared fields** — fill in Banda/Álbum/Ano in the modal, submit, and
   confirm every created job carries them (still allowing each song's own GP
   file/audio tags to fill in title, per the existing per-job precedence).
3. **Sequential status** — confirm each row's icon goes ⏳ → ✅ (or ❌ with an
   error message) one at a time, not all at once, and that a failure on one
   pair (e.g. a corrupt GP file) doesn't stop the rest of the batch.
4. **Auto-picked tracks, fixable afterward** — open one of the created jobs
   and confirm its warnings mention "tracks auto-selected by name heuristic"
   (the same warning a single-track wizard job gets); if a track was picked
   wrong, confirm "✎ Editar info" can re-map it and rebuild, exactly as for
   any other job — batch doesn't need its own fix-up path.

### 7a-septies. Note editor (browser only + a pipeline-level pytest guard)

The merge/precedence logic is covered by CI
(`test_note_overrides_*` in `test_gp_pipeline.py`: add/edit/delete applied
per-arrangement, after mute-stripping; `test_rebuild_stores_note_overrides_
keyed_by_arrangement` / `test_rebuild_note_overrides_reject_out_of_range_
string_or_fret` in `test_api.py`). What CI cannot cover is the live tab-viewer
wiring and the visual preview:

1. **Edit an existing note** — activate "Editar notas" (✏️), click a note:
   the popup opens pre-filled with its current fret/sustain/technique
   checkboxes/bend/slide. Change the fret and toggle a technique (e.g. Palm
   mute), "Guardar" — confirm the note immediately shows the new fret AND a
   dashed cyan ring (pending, not yet built) without a rebuild.
2. **Add a note in empty space (double-click)** — DOUBLE-click on a string's
   line where there's no note: the popup opens blank (fret 0, sustain 0.25),
   with the STRING pre-selected from the click's row. Confirm the new note
   appears at the nearest beat/subdivision (per the current "Encaixar em:"
   grid setting), not exactly under the cursor pixel — the snap-to-grid
   behavior. A SINGLE click on empty space must NOT insert — it must move the
   playhead (seek), same as every other mode (regression guard for "não
   consigo clicar na partitura e o cursor mover-se").
3. **Delete a note** — click an existing note, "Remover nota": confirm it
   disappears from the score immediately (still just pending).
4. **Move a note to a different string** — edit an existing note and change
   its string in the dropdown, "Guardar": confirm the OLD position is now
   empty and the note reappears on the new string at the same time (both a
   delete-old + upsert-new override were created from one edit).
5. **Commit + persist** — after several pending edits (mix of add/edit/
   delete), "Aplicar e reconstruir": confirm the rebuild succeeds, reopening
   the job shows the edited notes baked into the real chart (no more dashed
   cyan rings — they're now ordinary built notes), and other arrangements
   (e.g. Rhythm) were completely unaffected.
6. **Chord-forming edits** — add two notes at the exact same time on
   different strings (one at a time, via two separate "add" edits at the
   snapped time): confirm they draw as a connected chord (square note-shapes
   + bracket), not two separate single notes — the merge recomputes the
   chord grouping, it isn't inherited from the server.
7. **Out-of-range rejected before rebuild fires** — try adding a note far
   past the end of the song (beyond the last authored measure): confirm the
   rebuild fails with a clear error mentioning "beyond final ebeat" (an
   existing `Arrangement.validate()` invariant, not a new one) rather than
   silently corrupting the chart or crashing without explanation.
8. **Copy/paste a riff** — Shift+click two notes to select the range between
   them (or use "Excerto"), click "📋 Copiar" ("N nota(s) copiada(s)" appears
   next to the button). Move the playhead somewhere else, click "📥 Colar no
   cursor": confirm the copied notes reappear starting at the cursor, with
   the SAME relative spacing/frets/techniques as the original — pending
   (dashed cyan rings), not yet rebuilt. Repeat with Ctrl+C/Ctrl+V instead of
   the buttons.
9. **Copy on one tab, paste on another** — copy a passage on Lead, switch to
   the Rhythm tab, "Colar no cursor": confirm the notes land on Rhythm and
   Lead is unaffected — copy/paste works across arrangements, not just
   within one.
10. **Clipboard doesn't leak across jobs** — copy some notes, close the job,
    open a different one: confirm "📥 Colar no cursor" is disabled again
    (the clipboard is cleared on job load, so you can't accidentally paste
    one song's notes into another).
11. **Clear the edits** — with several committed edits, "🧹 Limpar edições"
    then "Aplicar e reconstruir": confirm the chart comes back as the GP file
    authored it and the counter next to the button reads zero. Repeat with
    two arrangements edited and "🧹 Limpar em todas". Also confirm the
    reverse: edit notes, rebuild, reopen the job, change ONLY the tuning and
    rebuild — the note edits must still be there (the seeding fix; a
    regression here is silent data loss).

### 7a-octies. Guitar Pro export (browser + a real Guitar Pro install)

Two buttons, two different guarantees — check both, because CI can only
round-trip them through RockForge's own importer:

1. **"🎼 Exportar GP corrigido"** (tempo only) — re-tempo a few bars until
   they show AMBER on the score, export, then **open the file in Guitar
   Pro**: confirm those measures carry the new BPM, every other track /
   note / technique / marker is untouched, and the ORIGINAL upload is
   unchanged on disk. On a `.gp` (GP7/8) source, confirm the file still
   opens at all — that route is byte-copy ZIP surgery on `score.gpif` and
   has never been validated against a real install.
2. **"🎸 Exportar GP com as notas editadas"** (the whole arrangement) — make
   a few note edits (add, change a fret, delete), export, open in Guitar
   Pro: confirm the edits are there, the tuning matches, sections appear as
   markers, and the bars fall where the recording puts them. Then check the
   two costs are visible and honest: the report must say it carries only
   this track, and if any onset was off the grid it must report how many
   were moved and by how much — compare a quantized note's position by ear
   against RockForge's own playback.
3. **Download naming** — both write `corrected.*` and both come back through
   the same download link; export one, then the other, and confirm the link
   serves the MOST RECENT export, not the first.

### 7b-drums. Beat/tempo detection on the isolated drum stem (needs `[ml]`)

The endpoint wiring (which audio path is passed to the detection functions) is
covered by CI (`test_auto_sync_uses_the_drum_stem_when_available`,
`test_auto_sync_dynamic_uses_drum_and_guitar_stems`, with fake stem files).
What CI can't cover is whether isolated drums actually improve the detection —
verify by hand on a fast/dense song where librosa mis-reads the tempo:

1. On a GP job WITHOUT separating first, run "✨ Sincronização automática" —
   the info line should end with **"⚠ Medido na mistura completa — … Separar
   instrumentos primeiro"**. Note the detected BPM (on a hard song it's often
   at the wrong metrical level).
2. Click **"Separar instrumentos"** and wait for it to finish (Demucs, minutes).
3. Run "✨ Sincronização automática" again — now the info line should end with
   **"🥁 Medido na bateria isolada (mais fiável)"**, and the detected BPM should
   be more sensible (closer to the song's real tempo) than in step 1.
4. Same for "🎯 Sincronização dinâmica": after separating, its status shows
   "🥁 batidas da bateria isolada" and the alignment should track better.
5. Honest limit: on some songs even isolated-drum detection isn't perfect
   (blast beats, half/double-time feels) — the MIDI tempo-map import
   (`/sync-from-midi`) remains the ground-truth fallback.

### 7c. Automatic lyric detection (needs `[ml,lyrics]`)

1. Open a completed job → "Letras" → "Detetar letra".
2. **Watch the log panel** (the black box) — it shows timestamped, per-step
   progress (`torch ready (Xs)`, `demucs ready (Xs)`, `whisperx ready`,
   `separating`, `transcribing`, `done — N words`). Also in `logs\worker.log`.
3. Without `[lyrics]` it must report `unavailable` gracefully (no crash).
4. Edit words/timings, drag lyric words on the tab viewer, "Aplicar e
   reconstruir", confirm the vocals XML reflects the edits.
5. **Line-break marker (visual).** A word that ends a lyric line (the in-game
   `+` / the "Fim de linha" checkbox) now draws a **solid amber vertical bar +
   `¶`** on the score, where a mid-line word has only a faint dashed tick — so
   you can see where the lyric wraps on screen. Toggle a row's line-break and
   confirm the marker appears/disappears at that word.

**GPU crash → CPU fallback (whole ML stack).** Both Demucs (torch) and WhisperX
(ctranslate2) can crash natively on GPU (e.g. exit `3221226505` / `0xC0000409`
from a torch/cuDNN mismatch on Turing / RTX 20-series) without a Python
traceback. Behaviour to confirm on such a machine:
- The crashing run still completes — the failing CUDA subprocess auto-retries on
  CPU (WhisperX log: "GPU … retrying on CPU"; Demucs falls back silently).
- **After the first crash it stops using the GPU entirely.** A `work_dir/
  .gpu_ml_broken` marker is written, and `_resolve_device` then downgrades
  `cuda→cpu` for BOTH Demucs and WhisperX on every later run — so a second song
  does NOT re-crash on the GPU. To re-enable the GPU after fixing CUDA/cuDNN,
  use **⚙️ Definições → GPU acelerada → "Reativar GPU"** (it shows whether the
  GPU is currently marked broken) instead of hunting for the hidden marker file;
  `POST /gpu-reset` deletes it. Guarded (no GPU needed) by
  `test_broken_marker_downgrades_cuda_to_cpu`,
  `test_cuda_crash_falls_back_to_cpu_and_marks`, `test_legacy_marker_still_honoured`,
  `test_gpu_reset_clears_marker`.
- To actually *use* the RTX 20-series GPU, try
  `ROCKFORGE_WHISPERX_COMPUTE_TYPE=int8_float16` (lower-VRAM, more cuDNN-tolerant
  than the default `float16`) — passed through to the runner. It only helps the
  transcribe model; an alignment-step cuDNN crash still falls back to CPU. Needs
  a matching CUDA build of torch/ctranslate2 + cuDNN DLLs on PATH (README §2b);
  or `ROCKFORGE_WHISPERX_DEVICE=cpu` / `ROCKFORGE_DEMUCS_DEVICE=cpu` to force CPU.

### 7d. Automatic tone detection (needs `[ml]`)

1. "Detetar tom" → poll → the result now shows the detected **spectral profile**
   (ganho/brilho/graves bars) plus TWO ranked lists — "Lead — tons semelhantes"
   and "Rhythm — tons semelhantes" — each preset carrying a **% de semelhança**
   with the recording (closest first). "Aplicar melhores (Lead + Rhythm)" loads
   the top pair; each candidate's **"usar"** button loads just that one (Lead vs
   Rhythm replaced independently, so picking a different Lead keeps the Rhythm).
2. Adjust in the tone editor → "Aplicar e reconstruir".
3. Confirm the `.rs2dlc` `Tones` array carries the gear.

The ranking is a weighted distance from the analyzer's `ToneProfile`
(gain-dominant, then brightness/low-end): `rank_tones(gain, bright, low, cat)`
returns the whole `_LEAD_LIBRARY`/`_RHYTHM_LIBRARY` sorted by match. Guarded by
`test_rank_tones_returns_ranked_candidate_libraries` /
`test_rank_tones_clean_profile_ranks_clean_first` (no ML — pure ranking).

### 7d-bis. Testar tom na partitura ("🎸 Testar tom") — sem ML

No editor da partitura, o seletor **"🎸 Testar tom"** aplica o *carácter* de um
tom criado às notas (tique + fonte sintetizada). Não precisa de ML nem de
gravação — corre no browser.

**Verificar (manual):**
1. Sem tons criados → o seletor está **desativado**.
2. Cria dois tons de gain diferente (ex.: um CLEAN, um HIGH GAIN). O seletor
   passa a ativo e mostra "Seguir partitura", "Voz simples" e cada tom.
3. Escolhe cada tom e toca: as notas soam como uma **guitarra dedilhada**
   (Karplus-Strong + cabine); o distorcido deve soar **claramente** mais saturado
   que o limpo. É uma **aproximação** (não o amp real do jogo).
4. Marca uma **Mudança de tom** a meio da música (modo 🎸) e escolhe "Seguir
   partitura": ao tocar, o carácter deve **trocar** no ponto marcado.
5. Muda a fonte de áudio para "… (sintetizada)" e confirma que também reflete o
   tom escolhido (re-renderiza ao trocar de tom).

Honesto: é o carácter (ganho/brilho), NÃO o som verdadeiro do amp — esse só no
jogo/DLC Builder.

### 7d-ter. The standalone `.exe` opens a native window (Windows only)

CI cannot build or run it — PyInstaller cannot cross-compile, and there is no
Edge WebView2 on a Linux runner. The launcher's DECISIONS are covered by
`test_standalone_launcher.py` (including the window orchestration, against a
fake `webview`) and the bundled files by `test_standalone_spec.py`; what only a
real Windows build shows is whether the window actually comes up.

Build with `py -3.11 build_exe.py` after installing `.[dev,psarc,desktop]`, then:

1. **It opens in its own window** — no browser tab, and no black console box
   behind it. The UI inside must be the full app (a blank window means the
   spec is not shipping `web/`; §7 of the README covers that check).
2. **Closing the window exits the process.** Check Task Manager: no
   `rockforge.exe` left behind. The idle-shutdown watchdog is deliberately off
   in windowed mode, so the window IS the only exit signal — if it leaks, the
   next launch will fail to bind port 8000.
3. **Closing mid-build asks first.** Start a build, close the window while it
   runs: a confirmation dialog must appear. Cancel → the app stays open and the
   build finishes. Confirm → it exits (and that job is left unfinished, which
   is what the dialog says). In `inprocess` mode the worker is in the API's own
   process, so closing really does abort it — the dialog is the whole guard.
4. **Without `[desktop]` it still works.** Build once with pywebview NOT
   installed: `build_exe.py` must warn, and the `.exe` must fall back to
   serving and opening the default browser rather than failing.
5. **The log exists.** `%USERPROFILE%\Downloads\RockForge\rockforge.log`
   should have uvicorn's startup lines. With `console=False` there is no stdout
   at all, so if this file is missing or empty, any future crash is
   unreportable.

### 7d-quater. ML from the `.exe` via an external Python (Windows only)

The standalone build cannot IMPORT the ML stack, but every ML stage runs as a
subprocess, so it delegates them to the interpreter `ROCKFORGE_ML_PYTHON` names
(⚙️ Definições → "🐍 Python para o ML"). CI covers the resolution rules, the
per-extra probe, the real subprocess transport (`_librosa_runner.py` driven
with a stub librosa) and that no call site passes `sys.executable`
(`test_ml_python.py`) — what it cannot do is run a frozen build against a real
Demucs, which is exactly where the interesting failure would be.

With the `.exe` built and a Python 3.11 carrying `.[ml,lyrics]`:

1. **Empty field, `.exe`: the buttons fail honestly.** With nothing configured,
   "Detetar tom" / "Separar stems" / "Corrigir daqui" must report the missing
   ML Python and name ⚙️ Definições — not a traceback, and not silence.
2. **A wrong path is diagnosed as a wrong path.** Point it at `notepad.exe`:
   the panel must say it did not start as a Python, NOT "Demucs em falta"
   (which would send you to reinstall Demucs).
3. **A correct path lights the ✓ per extra**, and `/system-check`'s ML rows
   name that interpreter rather than reporting the `.exe`'s own (empty) one.
4. **"Corrigir daqui" actually re-tempos.** This is the one that exercises the
   new `_librosa_runner` transport end to end: click a drifting note, confirm
   the measured BPM is plausible and the tail moves. A per-click subprocess
   costs an interpreter start plus a librosa import (~2-4 s) — slower than
   `start.bat`, where the in-process path is kept precisely for this.
5. **Stem separation and lyric detection complete.** Both were already
   subprocesses; what is new is which interpreter runs them. Watch the job log
   for the device line, and confirm the `.exe` does NOT relaunch itself (the
   `sys.executable` bug's signature is a second RockForge window appearing
   instead of a separation starting).
6. **`start.bat` is unchanged.** Leave the field empty there and re-run one of
   each: the resolver returns that very interpreter, so this must be the same
   path it always was — no new subprocess, no behaviour change.

### 7d-quinquies. Songsterr bar times against the REAL API

CI and the development sandbox cannot reach songsterr.com, so the client was
built from teaqu/guitar-pro-youtube-sync's use of the same endpoints and tested
against a fake. On a real machine:

1. In the wizard's step 3, paste a Songsterr link and press **Procurar**: the
   videos must list, the default one first, each with its bar count.
2. With the GP exported from THAT Songsterr tab and an MP3 of THAT video (the
   whole video), create the project without touching "Início da música": the
   chart should follow the recording through tempo changes without a single
   manual correction.
3. The job's warnings must say "bar times from an external source … N times
   for N bars". A mismatch there means the GP is not that tab.
4. A trimmed MP3 needs "Início da música" moved back by what was trimmed; that
   is the one number the times cannot know.

### 7e. Wwise `.wem` (needs a local Wwise 2019/2021/2022/2023, Windows)

Run with `WWISEROOT` set. The bundle must contain `audio.wem`. **In-game check:**
the song must play audio, not silence — a seek-table-less `.wem` loads but plays
silence and exits seconds in. If that happens, in DLC Builder pick the bundle's
`audio.wav` (not `.wem`) and let DLC Builder convert.

**Volume ("Calculate Volumes", native `.psarc`).** The `.bnk` bus volume is now
computed from the audio's loudness (ffmpeg `ebur128` → offset to -16 LUFS),
where it shipped a neutral 0. **In-game check:** the song's loudness sits at a
sensible level next to official DLC (not obviously quiet/loud), and — the point
of the feature — the **song-select preview** plays at roughly the same loudness
as the song itself, instead of a loud chorus clip blasting over the list. If
songs feel systematically too quiet vs official DLC, raise `TARGET_LUFS` in
`normalize/loudness.py` (the references gave no verified retail figure to
calibrate to). Needs ffmpeg; without it the volume degrades to 0 dB (the old
behaviour), no crash.

### 7f. Final PSARC + in-game

Import the bundle into DLC Builder, or rely on the native `.psarc` (`psarc_mode
= native`, default). The native SNG layout is round-trip-tested but **NOT**
byte-validated against a retail SNG — the only true validation is loading the
CDLC in Rocksmith 2014.

### 7f-bis. Techniques + variable-height DD — in-game validation status

Everything below was implemented, unit-tested at the domain/XML/SNG boundary,
and verified to (a) parse the real GP files noted and (b) compile to a
round-tripping SNG. Validate each by building the song **both** ways and
comparing: the native `.psarc` (`psarc_mode=native`) AND the DLC Builder bundle.
If the native `.psarc` misbehaves, the DLC Builder bundle is the trustworthy
fallback.

**Confirmed in-game (Beartooth "Free", native PSARC):** the song lists and loads;
the ½-bends play with the right size (bend-up to peak, not a prebend) and no
longer crash at the C-part; slides, fret-mutes and the sustain gap render; the
variable-height DD works. This song does NOT exercise pinch harmonics, tremolo,
tap/slap/pop, trills or alternate arrangements — those remain to confirm on a
song that uses them (see below).

**Confirmed in-game (vocals, multiple songs — native PSARC):** the scrolling
lyrics now appear (needed BOTH `SngVocal.note = 254`, the non-pitched sentinel,
AND the vendored lyric-font symbol atlas in the vocals SNG — an empty symbol
block leaves the game with no glyphs and the letra silently never shows); the
song-name/title card and stage lighting appear over the intro now that
`build_showlights` emits a real fog+beam track (an empty showlights left the
stage dark and skipped the lit intro); WhisperX-detected long segments are now
broken into short display lines (no more wall-of-text scroll).

Good source files (already parsed correctly, in the uploads): Ozzy "No More
Tears" `.gp` (pinch harmonics, slides in/out, fret-mutes, bend-and-release,
trills), Animals As Leaders "Tempting Time" (tapping, fingering, DD reference).

**Per-note techniques** — for each, build a chart that uses it and confirm the
in-game note-highway glyph/behaviour matches Guitar Pro:

- **Bends** — a plain bend rises to its peak by the note's end (a visible
  bend-up, NOT an already-bent prebend); a **bend-and-release** rises then falls.
  Byte-matched to a DLC Builder SNG, but confirm the feel in-game.
- **Notes/chords while scoring** ✅ **Fixed & confirmed in-game.** A note must
  survive being PLAYED, not just watched. A crash that hit exactly when the
  player scored a note in a late section — but never on a hands-off run — was
  **the note's `PhraseId` set to its phrase-iteration index instead of the
  (phrase-linked) phrase id**: once DD phrase-linking makes fewer phrases than
  iterations, that index runs off the end of the Phrases array and the game
  crashes reading it during scoring. Happened **with DD on OR off**. Fixed
  (`phrase_id = phrase_iterations[pi].phrase_id`) and confirmed in-game on
  Beartooth "Free" (played through the octave section, no crash); guarded by
  `test_note_phrase_id_is_in_bounds_after_linking`. Affected **any** song with
  repeated riffs (almost all). (A separate, earlier byte-verified finding on the
  same octave: chord template unused strings must be MIDI **-1, not 0** —
  `test_chord_template_notes_are_real_midi`.)
- **Slide-out** (`slideUnpitchTo`) — a note that slides off into nowhere (GP `9\`)
  shows the unpitched slide tail. ✅ **Confirmed in-game.**
- **Slide-in / scoop** — a note slid *into* from below/above either gets a short
  lead-in note that slides into it, or (in a dense lick) the previous note slides
  into it. Big pitch jumps with no room stay plain (honest limit).
  ✅ **Confirmed in-game.**
- **Fret-hand mute** (dead "X" notes) — muted, not fretted.
- **Pinch / artificial harmonic** vs **natural harmonic** — the distinct pinch
  glyph. (Ozzy "No More Tears" has 9 pinch harmonics.)
- **Tremolo picking** — the tremolo (rapid-repick) marker.
- **Let-ring** — the note rings into the following notes (its sustain isn't
  trimmed).
- **Pick direction** (up/down) and **left-hand fingering** (0-4) — mostly
  cosmetic; confirm they don't corrupt anything.
- **Trill** — expands to an alternating hammer-on/pull-off run between the two
  frets. Confirm it reads as a trill, not a spurious note storm. (Ozzy rhythm
  track has 2.)
- **GP7/GPIF tap / slap / pop** — these had NO example file to validate against;
  the GPIF tag names (`Slapped`/`Popped`/`Tapped`, beat-level) are best-effort.
  If you have a `.gp` with slap-bass or tapping and the technique doesn't appear,
  send the file so the tag can be corrected. (GP5 tap/slap/pop is validated.)
- Slide flags **64 / 128** in some GP7 files are unidentified and ignored.

**Variable-height Dynamic Difficulty** (the big one — DD was a past crash source):

- Each **phrase's difficulty bar now varies in height** by that phrase's density
  instead of a flat top. The ceiling is `_DD_LEVEL_CAP = 20` (was 11), so a song
  now has **up to 21 DD levels** (was 12). Matches a decoded pro CDLC
  (AAL "Tempting Time": phrase max-difficulties spread 0..18).
- **In-game check:** the difficulty slider spans a wider range and the
  Riff Repeater / difficulty graph shows varied per-phrase bar heights (rising
  and falling), not a flat plateau.
- **Watch for:** a crash on entry to a dense phrase's higher levels, or a level
  that shows anchors/notes for notes it dropped. The per-level anchor/slide-
  extension rebuild (`_build_level`) and phrase-iteration links are unchanged —
  only the ceiling rose — so more levels of the *same* shape. If a specific song
  crashes, toggle **DD off** (the "DD" checkbox / `dynamic_difficulty=False`) to
  confirm DD is the cause, and report the song.
- The SNG is ~1.6× larger than before (more levels); still well under 1 MB per
  arrangement. Not a concern unless a song fails to load for size.

Guarded at unit level by `test_dd_phrase_heights_vary_with_density` and the
existing `test_dd_*` tests, but only in-game play confirms it.

**Phrase-linking (repeated riffs share one phrase):** identical iterations now
collapse onto a shared phrase (`_phrase_signature`), so a repeated riff is ONE
phrase with many iterations — learned once, mastered on every repeat — instead
of re-ramping each occurrence. **In-game check:** in the Riff Repeater / phrase
list the song shows a small handful of distinct phrases (a repeated riff appears
as the *same* phrase each time, not a new one), and raising your mastery on a
riff carries to its every repeat. **Watch for:** a phrase that should NOT be
linked (two riffs that merely look similar) sharing difficulty — the signature
is an exact (10 ms, string, fret) match so this should be rare; report a song
where distinct riffs collapse. Guarded by `test_identical_riffs_share_one_phrase`.

**Alternate arrangements** (`ALTERNATE_LEAD` / `ALTERNATE_RHYTHM`): pick a second
Lead/Rhythm GP track in the "Pista Lead/Rhythm alternativo" selectors. The build
emits `lead2`/`rhythm2` assets flagged non-representative (`Representative=0`,
`bonusArr=1`) — byte-for-byte the encoding of a decoded DLC Builder CDLC's
`lead2` (AAL "Tempting Time"). **In-game check:** both charts appear and are
selectable for the same song; the primary is the default. Guarded by
`test_alternate_arrangement_is_nonrepresentative_same_path` and
`test_build_manifest_files_emits_distinct_lead_and_alternate`, but confirm the
song shows two Lead entries in-game.

### 7f-ter. Custom tones in the native PSARC (in-game validation status)

The user's custom tones (amp/cabinet/pedal chain built in the tone editor) are
now serialized into each arrangement's **runtime manifest** (`Tones` array +
`Tone_Base`/`Tone_A`..`Tone_D`, via `packaging/tone_dto.py`). The manifest tone
DTO was verified **byte-identical** to a DLC Builder build of our own tones
(`emphaticpride_lead.json`'s `Tones`: `GearList` Amp/Cabinet/pedals,
`ToneDescriptors`, `NameSeparator`, `IsCustom`, `Volume` as a `"-14.000"`
string, `Key`, `Name`). Decoding that reference also confirmed the base tone is
applied entirely from the manifest `Tone_Base` (the reference lead SNG's Tones
section count is **0**), so a single-tone song is fully covered by the manifest.

**In-game check:** build a song with a tone dialled in the editor (amp + cabinet,
optionally pedals) as the **native `.psarc`** (not via DLC Builder). In-game the
guitar should sound like that gear — the amp/gain/cabinet you chose — NOT the
default clean tone. Confirm the tone name shows in the tone selector and that
switching arrangements (Lead/Rhythm) keeps each one's assigned tone.

**Not yet covered:** mid-song **tone changes** (the SNG's Tones section stays
empty — `tone_base` applies for the whole song). If a chart marks tone changes,
in-game the tone will NOT switch mid-song on the native path; the DLC Builder
bundle still handles tone changes (via the `<tones>` XML). Report if you need
mid-song switching on the native PSARC and it can be wired (needs the exact
Sng2014 Tones struct — the reference had none to byte-match).

Guarded at unit level by `test_manifest_serializes_custom_tones_into_gearlist`.

### 7g. Separação fina de guitarras — Banquet (⚠️ EM TESTES, precisa de setup manual)

An alternative stem-separation backend that separates guitars by **class**
(electric vs acoustic, clean vs distorted) — finer than Demucs's single "guitar"
stem. Selected with `ROCKFORGE_STEM_SEPARATOR=banquet`. **Not validated yet** —
this is here for the maintainer to test the quality on real files and report
back; Demucs stays the default. The command-construction is unit-tested
(`test_banquet_adapter.py`) but the model itself never runs in CI.

**Honest limit (unchanged):** separation is by instrument *class*, not track.
Two guitars of the *same* class (Lead + Rhythm, both distorted) still can't be
split — use the per-arrangement synthesized source for that.

**Setup (needs PyTorch; a CUDA GPU strongly recommended):**
1. Clone the model: `git clone https://github.com/kwatcharasupat/query-bandit`
   (MIT). Install its deps.
2. Download the checkpoint `ev-pre-aug.ckpt` from
   <https://zenodo.org/records/13694558>.
3. Prepare **query clips**: a dir with one short `<class>.wav` reference per stem
   you want — e.g. `electric_guitar.wav`, `acoustic_guitar.wav`, `bass.wav`,
   `vocals.wav`. Banquet is query-based: each clip is an *example* of the sound
   to extract; the produced stem is named after the clip's filename.
4. Enable it — **either** from the app's **"⚙️ Definições"** menu (choose
   Banquet, paste the three paths, "Guardar" shows ✓/✗ per path and the detected
   stems) **or** via env vars:
   ```
   ROCKFORGE_STEM_SEPARATOR=banquet
   ROCKFORGE_BANQUET_REPO=/path/to/query-bandit
   ROCKFORGE_BANQUET_CKPT=/path/to/ev-pre-aug.ckpt
   ROCKFORGE_BANQUET_QUERIES=/path/to/queries
   # optional: ROCKFORGE_BANQUET_DEVICE=cuda  ROCKFORGE_BANQUET_BATCH_SIZE=4
   ```
   The UI settings live in `work_dir/settings.json` and **override** the env
   vars; both the API and the worker read them (no restart needed).
5. In the tab viewer press **"Separar instrumentos"**. The stems log shows
   `backend: banquet (separação fina, EM TESTES)`. One inference pass runs per
   query clip (slow); the dropdown then lists the produced stems.

If any of the three paths is missing/unset, the task fails **gracefully** with a
clear message (`stems_status = unavailable`) — it never crashes the job. Missing
setup is guarded by `test_banquet_adapter.py::test_missing_setup_raises`.

### 7h. Export / import sync state (JSON)

The hand-tuned sync a user builds in the tab viewer (drift anchors, `tempo_scale`,
`offset_s`, intro silence, per-arrangement `arrangement_sync`, tuning, edited
`lyrics_events`, GP track assignment) can be saved to a JSON file and restored
into another job — so re-uploading the recording or re-exporting the GP doesn't
mean redoing all the alignment. Buttons **"⬇ Exportar sync" / "⬆ Importar sync"**
sit under "Aplicar e reconstruir".

Fully unit-tested (`test_api.py`: `test_extract_sync_state_is_whitelisted`,
`test_sync_state_export_and_import_round_trip`,
`test_import_sync_drops_gp_only_keys_and_validates`) — the whitelist, the
round-trip, the GP-only-key drop and the tuning validation. **Manual check (no
game needed):** tune a song's sync, click **Exportar sync** (downloads
`<artist>_<title>.sync.json`), create a NEW job for the same song, click
**Importar sync** and pick that file — it forks a rebuild and the tab viewer
comes back with the same anchors/tempo/offset/lyrics. Importing a GP-only key
(a track index / per-arrangement tuning) into a non-GP job silently drops it;
a malformed `tuning_midi` 422s instead of corrupting the job.

**Rebuild history (walk back a version).** rebuild / reload-gp / import-sync all
fork a NEW job and never delete the old one, so every version persists; the fork
records `rebuilt_from` (`JobOut`). The tab viewer shows a **"↩ Versão anterior"**
button that opens the job this one was rebuilt from — recover from a sync
correction that made things worse. Backend guarded by
`test_forked_jobs_link_back_to_the_original`; **manual check:** rebuild a job
twice, confirm the button walks back one version each click and the older bundle
still downloads.

**Tab-viewer keyboard shortcuts.** With the sync panel open and no text field
focused: **Space** play/pause, **←/→** scrub ∓1s (Shift = ∓5s), **Home** to the
start, **`+`/`-`** zoom. **Manual check:** the playhead moves visually with the
arrows even while paused, and the shortcuts do NOT fire while typing in an input
(word/timing fields, tuning boxes). Arrows are a fixed time-step, not
note-snapping (deliberate — the note↔playhead mapping shifts under pending sync
edits).

---

## 8. Debugging the async detection tasks

`test_celery_tasks.py` calls `generate_cdlc`/`detect_tones`/`separate_stems`/
`detect_lyrics` directly (not through Celery, not through the API's stubbed
`_enqueue*`) against a real per-test SQLite `Job` row, so the task body itself
— the try/except-never-crashes wrapper, the `params["*_status"]` transitions,
the drums-drop in `separate_stems`, `generate_cdlc`'s COMPLETED/FAILED
transitions — is exercised directly instead of only through mocks. Add a new
case there (rather than only in `test_api.py`) when changing what a task body
itself does, not just how the API enqueues it.

`detect_lyrics` and `detect_tones` are Celery tasks whose progress lives in
`Job.params` (`lyrics_status`/`lyrics_log`, `tone_detection_status`/
`tone_detection_log`), **never** in `JobStatus` — so detection never hides a
completed bundle. The UI polls `GET /jobs/{id}/lyrics` / `/detected-tones` and
renders the log.

**When a detection appears "stuck":**
1. Read the **last line of the log panel** (or `logs\worker.log`). It names the
   exact step. The progress bar is a client-side time animation — it does NOT
   reflect real backend progress; only the log does.
2. `loading ML models` with nothing after → the worker process didn't progress;
   check `logs\worker.log` for a traceback.
3. `torch ready — device: cpu (CPU)` on a GPU machine → torch is the CPU-only
   build; reinstall the CUDA build (README §2b). Verify:
   `py -3.11 -c "import torch; print(torch.__version__, torch.cuda.is_available())"`
   must print `...+cu121 True`.
4. `whisperx NOT available: ...` → the `[lyrics]` extra is missing or its import
   failed (stderr is in the log line).

### ⚠️ The SQLAlchemy JSON no-op trap (cost us a multi-session debug)

`Job.params` is a plain `JSON` column with **no `MutableDict` tracking**.
Reassigning the *same* dict object is a silent no-op — SQLAlchemy compares by
identity, sees no change, and skips the `UPDATE`:

```python
params = dict(job.params or {})
params["x"] = 1
job.params = params      # 1st commit works (new object)
session.commit()
params["x"] = 2
job.params = params      # NO-OP — same object → no UPDATE written
session.commit()         # commits nothing
```

The symptom is **the UI freezing on the first status/log line** while the task
actually runs to completion (or fails) invisibly. The fix is the
`_commit_params()` helper in both detection tasks, which assigns a **fresh
dict** every time:

```python
def _commit_params() -> None:
    job.params = {**params}   # new object → SQLAlchemy sees the change
    session.commit()
```

**Any new code that updates `Job.params` incrementally MUST copy the dict on
assignment** (`{**params}` / `dict(params)`), or wrap the column in
`MutableDict.as_mutable(JSON)` in `db/models.py`. There is no test guarding this
(it needs a real DB round-trip with the ORM identity behaviour) — so it is
documented here as a hard rule.

---

## 9. Common pitfalls when writing tests

- **Don't run the real ML/Wwise/ffmpeg** — fake at the port. CI has none of them.
- **Don't assert async task *results* in endpoint tests** — assert the enqueue
  happened and `params` was set; test the task body separately.
- **Don't mutate `Job.params` in place in a test that then re-reads via the ORM**
  without reassigning a new dict — same trap as §8.
- **Don't bump mypy or add Python 3.12 to the matrix.**
- **Keep tests deterministic** — no network, no real model downloads, no
  wall-clock sleeps.
