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
pip install -e ".[dev]"     # core + test tooling, NO ML stack — this is all CI needs
pytest                       # 279 tests, ~10s, all ML/Wwise/external tools faked
ruff check src tests         # lint
mypy                         # type check
```

**All three gates (pytest, ruff, mypy) must be green before every commit.** CI
runs exactly these. There is no separate "ML test" job — the ML stages are
*faked* (see §3), so the full suite runs on a plain Python 3.11 with no torch,
no GPU, no ffmpeg, no Wwise.

- **Python 3.11 only** (`requires-python = ">=3.11,<3.12"`). On Windows:
  `py -3.11 -m pytest`. Do not test on 3.12+ — `basic-pitch`/`tensorflow` have
  no wheels there and the install itself fails.
- **mypy is pinned** (`mypy~=1.19.0`). Do not bump it casually — CI must match
  local exactly, and minor mypy versions flag different issues.

---

## 2. The philosophy: inject fakes at the port boundary

The architecture (see `CLAUDE.md`) makes every external dependency a `Protocol`
in `application/ports.py`. Tests exploit this: instead of mocking deep library
internals, they **substitute a fake adapter** at the same boundary the real one
plugs into.

- **ML stages** (Demucs, Basic Pitch, librosa, WhisperX) → passthrough/stub
  adapters that return canned data (`test_pipeline.py`).
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
| **Lint** | `ruff check src tests` | style, unused imports/vars, import order, obvious bugs |
| **Types** | `mypy` | strict on `domain/`/`application/`/`infrastructure/`; relaxed at framework boundaries (FastAPI/SQLAlchemy/Pydantic) via per-module overrides in `pyproject.toml` |
| **Tests** | `pytest` | 279 functional tests (see §4) |

mypy strictness is deliberate: the `domain` and `application` layers carry the
music model and orchestration logic and must be fully typed. The
`interfaces/api` boundary is relaxed because FastAPI/Pydantic/SQLAlchemy resolve
to `Any` in places mypy can't follow — that's why the JSON-column endpoints use
explicit `cast(...)`.

---

## 4. Coverage map (279 tests across 27 files)

| File | Tests | Guards |
|---|---:|---|
| `test_domain.py` | 7 | pure music model: `Tuning`, `TabNote`, `TempoMap`, `Arrangement` invariants |
| `test_fret_mapper.py` | 10 | string/fret playability optimization (DP), tuning-aware |
| `test_rolesplit.py` | 3 | EXPERIMENTAL Lead/Rhythm heuristic split |
| `test_pipeline.py` | 10 | audio→ML use case end-to-end with **faked** stages; supplied `lyrics_events` precedence |
| `test_gp_import.py` | 9 | PyGuitarPro (GP3/4/5) parsing: notes/frets/techniques/sections/tempo |
| `test_gpif_import.py` | 6 | native GP7/GP8 (`.gp`) GPIF/XML parser: tuning, timing, Hopo/slide/palm-mute, lyric sourcing, bass rejection |
| `test_gp_pipeline.py` | 16 | GP use case: `tempo_scale`, `sync_anchor_stages`, `arrangement_sync`, lyrics precedence, `pad_start_s` shift |
| `test_rsxml_writer.py` | 15 | Song2014 XML: the **32 arrangementProperties** attrs, COUNT/default/END phrase structure, chords |
| `test_vocals.py` | 19 | `parse_lyrics` (LRC + UltraStar), `expand_to_words` (trailing `+`), `events_from_dicts`, `distribute_syllables` (GP lyrics → note-onset alignment, melisma `_`) |
| `test_lyrics_transcribe.py` | 6 | WhisperX adapter: RMS gate, per-word confidence filter, segment→event mapping (whisperx itself stubbed) |
| `test_tone_gear.py` | 11 | `domain/tone.py` gear model + `tone_from_dict`/`tones_from_dicts` |
| `test_tone_detection.py` | 7 | spectral `analyze_guitar_tone` → category → `suggest_tones` presets |
| `test_rs2dlc.py` | 6 | `.rs2dlc` `DLCProject.Dto` shape, Name/RouteMask per kind, vocals case, **`.phrase-levels`** companion |
| `test_psarc_container.py` | 3 | PSARC v1.4 pack/unpack round-trip |
| `test_psarc_manifest.py` | 5 | runtime manifests (`.hsan`, `_aggregategraph.nt`, per-arr JSON) |
| `test_psarc_sng.py` | 17 | Sng2014 binary `write_sng`∘`read_sng` = identity, NoteMask, anchor extensions, vocals SNG |
| `test_psarc_crypto.py` | 4 | AES-256-CFB TOC + AES-256-CTR SNG (needs `[psarc]`) |
| `test_psarc_packer.py` | 7 | `NativePsarcPacker` wiring; graceful degrade without `[psarc]` |
| `test_wwise.py` | 6 | `.wem` conversion via **fake** WwiseConsole; seek-table header patch |
| `test_ffmpeg_normalizer.py` | 3 | command build: `-nostdin`, `stdin=DEVNULL`, `FFMPEG_TIMEOUT_S` |
| `test_demucs_adapter.py` | 5 | demucs CLI command build, `stdin=DEVNULL`, timeout, vocals vs guitar models, `separate_stems` returns all stems |
| `test_banquet_adapter.py` | 5 | Banquet (EM TESTES) `inference_byoq` command build, one pass per query clip, device→`use_cuda`, missing-setup errors |
| `test_device_resolution.py` | 4 | `_resolve_device` auto/cpu/cuda + degrade-to-CPU on import failure |
| `test_tags.py` | 2 | audio metadata tag extraction |
| `test_api.py` | 60 | every endpoint (§6): job lifecycle, rebuild composition, detect-* / separate-stems enqueue (mocked), lyrics/tones/stems status, deletion, per-test SQLite |
| `test_settings.py` | 5 | in-app settings (`/settings`): default demucs, persist+read-back, invalid separator 422, Banquet path validation, empty-string clears override |

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
- `test_supplied_lyrics_events_emits_vocals_xml` / `test_gp_lyrics_events_precedence`
  — edited lyrics must win over LRC/GP-embedded/auto-WhisperX.

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
POST   /jobs/upload                  create job from uploaded audio
POST   /jobs/youtube                 create job from YouTube URL (gated)
POST   /gp/inspect                   list tracks in a GP file (pre-job)
POST   /jobs/gp                      create job from GP file + recording
GET    /jobs                         list all jobs
GET    /jobs/{id}                    one job
DELETE /jobs/{id}                    delete job + its files
POST   /jobs/{id}/rebuild            rebuild with new params (composes sync rounds)
POST   /jobs/{id}/reload-gp          swap the GP file, keep all overrides   [GP]
POST   /jobs/{id}/auto-sync          propose (tempo_scale, offset_s)   [GP, ml extra]
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
GET    /jobs/{id}/arrangements       per-arrangement tab/sync data for the viewer
GET    /jobs/{id}/source-audio       the recording (for the waveform)
GET    /jobs/{id}/bundle             the DLC Builder bundle zip
GET    /jobs/{id}/psarc              the native .psarc (if produced)
POST   /jobs/{id}/cover              upload album art
GET    /jobs/{id}/cover              serve album art
GET    /gear-catalogue               tone gear catalogue (for the tone editor)
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

### 7b. Audio → ML (needs `[ml]`, ideally a GPU)

1. Start with a **simple, clean** recording (single guitar, low distortion) in
   FLAC/WAV — the scenario where transcription has evidence of working.
2. Watch the stage bar through `separate`/`transcribe`. On CPU a 4-min song
   takes several minutes per stage; the first run also downloads ~2 GB of
   models.
3. Review the tab, fix tuning, rebuild.

### 7c. Automatic lyric detection (needs `[ml,lyrics]`)

1. Open a completed job → "Letras" → "Detetar letra".
2. **Watch the log panel** (the black box) — it shows timestamped, per-step
   progress (`torch ready (Xs)`, `demucs ready (Xs)`, `whisperx ready`,
   `separating`, `transcribing`, `done — N words`). Also in `logs\worker.log`.
3. Without `[lyrics]` it must report `unavailable` gracefully (no crash).
4. Edit words/timings, drag lyric words on the tab viewer, "Aplicar e
   reconstruir", confirm the vocals XML reflects the edits.

**GPU crash → CPU fallback.** WhisperX runs in a subprocess; on Windows a CUDA
run can crash natively (e.g. exit `3221226505` / `0xC0000409` from a
cuDNN/ctranslate2 DLL mismatch) without a Python traceback. The task now
auto-retries on CPU (the log shows "GPU transcription crashed … retrying on
CPU"), so detection still completes, just slower. If the CPU run also fails, the
error carries the subprocess's stderr tail. To use the GPU, the user needs a
matching CUDA build of torch/ctranslate2 and the cuDNN DLLs on PATH (README
§2b); otherwise set `ROCKFORGE_WHISPERX_DEVICE=cpu` to skip the GPU attempt.

### 7d. Automatic tone detection (needs `[ml]`)

1. "Detetar tom" → poll → "Aplicar tons sugeridos" loads presets into the tone
   editor → adjust → "Aplicar e reconstruir".
2. Confirm the `.rs2dlc` `Tones` array carries the gear.

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

### 7e. Wwise `.wem` (needs a local Wwise 2019/2021/2022/2023, Windows)

Run with `WWISEROOT` set. The bundle must contain `audio.wem`. **In-game check:**
the song must play audio, not silence — a seek-table-less `.wem` loads but plays
silence and exits seconds in. If that happens, in DLC Builder pick the bundle's
`audio.wav` (not `.wem`) and let DLC Builder convert.

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
- **Slide-out** (`slideUnpitchTo`) — a note that slides off into nowhere (GP `9\`)
  shows the unpitched slide tail.
- **Slide-in / scoop** — a note slid *into* from below/above either gets a short
  lead-in note that slides into it, or (in a dense lick) the previous note slides
  into it. Big pitch jumps with no room stay plain (honest limit).
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

---

## 8. Debugging the async detection tasks

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
