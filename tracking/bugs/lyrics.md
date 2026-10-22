<!-- Generated from tracking/bugs.json by `python -m tools.tracking render`. Do not edit by hand: edit the JSON and render again. -->

# Bugs: lyrics

Lyrics: GP, LRCLIB, detection, editor. Index: [BUG_LOG.md](../BUG_LOG.md).

## BUG-0017

**LRC/UltraStar lyrics supplied at creation never shown in the editor**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | pending (not recorded) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | c5f20fc08b4aec26b58d9efd7c99745dd5e497a1 |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

GET /lyrics only read params['lyrics_events'], so lyrics uploaded as LRC/TXT at job creation were used at build time but never appeared in the Letras panel or on the score.

**Steps to reproduce:** _pending_

**Expected:** Uploaded lyrics shown and editable

**Observed:** Editor empty although the build had lyrics

**Root cause:** Endpoint ignored params['lrc_text'].

**Fixes:** [FIX-0017](../FIX_LOG.md#fix-0017) (0.10.0-beta.1)

**Verified:** regression test(s) test_lyrics_falls_back_to_supplied_lrc_text pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-06-15 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Lyrics invisible and uneditable.

**Evidence:**

- commit 72a7b01de6 fix(lyrics): show LRC/UltraStar-TXT lyrics in the editor and tab view
- found_in_version: fix 72a7b01de6 (2026-06-15) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent c5f20fc08b, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-06-15 — Fixed: commit 72a7b01de6
- 2026-06-15 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0020

**WhisperX silently unavailable: torchaudio 2.5 removed AudioMetaData**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | pending (not recorded) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | a3672d5813397a1352a485e09be357f09c135785 |
| Severity | Medium |
| Priority | P3 |
| Status | Fixed |

pyannote.audio 3.3.2 uses torchaudio.AudioMetaData, removed in 2.5+; the AttributeError made WhisperXLyricTranscriber.available() return False.

**Steps to reproduce:** _pending_

**Expected:** Detection available

**Observed:** Lyric detection 'unavailable' with the extras installed

**Root cause:** Unpinned torch/torchaudio.

**Fixes:** [FIX-0020](../FIX_LOG.md#fix-0020) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-06-15 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Lyric detection unusable.

**Evidence:**

- commit e849140be9 Pin torch<2.5 and torchaudio<2.5 in the lyrics extra
- found_in_version: fix e849140be9 (2026-06-15) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent a3672d5813, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-06-15 — Fixed: commit e849140be9

## BUG-0025

**Lyric detection hung for 40+ minutes at the WhisperX import (Celery CUDA deadlock)**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | b9a7e229d149c94678917c11abf67eaa3282444d |
| Severity | High |
| Priority | P2 |
| Status | Closed |

faster-whisper/ctranslate2 deadlocked during CUDA init inside the Celery child, so detection hung at ~8% (import phase) for 40+ minutes on GPU machines.

**Steps to reproduce:** 

1. Run 'Detetar letra' on a GPU machine

**Expected:** Detection completes.

**Observed:** Stuck at the import phase indefinitely.

**Root cause:** A known ctranslate2 CUDA-init deadlock in Celery child processes (faster-whisper #907, celery #3402).

**Fixes:** [FIX-0025](../FIX_LOG.md#fix-0025) (0.10.0-beta.1)

**Verified:** No module but the subprocess runner imports whisperx/faster_whisper/ctranslate2, and the availability check runs in a subprocess. The CUDA deadlock itself cannot be reproduced here (no GPU, no WhisperX) (by the developer (pytest))

**Resolved:** 2026-06-18 · **Closed:** 2026-10-20

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Lyric detection unavailable on GPU machines.

**Evidence:**

- CLAUDE.md § Automatic lyric detection + in-app editor (Subprocess isolation)
- commit 10b04691f9 Fix lyrics detection hang: run WhisperX in subprocess, not Celery worker
- found_in_version: the fix commit is an ancestor of cb00653 (the first public release, 0.10.0 beta 1, 2026-10-14), so the faulty code only existed in development builds before 0.10.0-beta.1
- found_in_build: b9a7e229d1 is the parent of the first fix commit 10b04691f9 and still carries the code the fix changes
- pytest 2026-10-20: passes; full suite passes
- Mutation: an `import whisperx` in whisperx_adapter fails the guard

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-06-18 — Fixed: commit 10b04691f9
- 2026-10-20 — Verified: regression check re-run (pytest/Playwright)
- 2026-10-20 — Closed: released in 0.10.0-beta.1

## BUG-0026

**A CUDA warm-up thread deadlocked the first detection on Windows**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 10b04691f99a5c7acdbf2c38ab020fafaeb374a9 |
| Severity | High |
| Priority | P2 |
| Status | Closed |

The worker_ready warm-up ran torch.cuda.is_available() concurrently with the first task's, and two simultaneous cuInit() calls deadlocked the NVIDIA driver on Windows — a hang at 'loading ML models'.

**Steps to reproduce:** 

1. Start the worker
2. Immediately run a detection

**Expected:** Detection starts.

**Observed:** Hang before 'importing torch'.

**Root cause:** Concurrent cuInit() from the warm-up thread and the task.

**Fixes:** [FIX-0026](../FIX_LOG.md#fix-0026) (0.10.0-beta.1)

**Verified:** No RockForge handler hangs off the worker's start signals. The Windows deadlock itself cannot be reproduced here (by the developer (pytest))

**Resolved:** 2026-06-18 · **Closed:** 2026-10-20

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Detection hung with no workaround but restarting.

**Evidence:**

- CLAUDE.md § Automatic lyric detection + in-app editor (Subprocess isolation: 'The CUDA warm-up probe was removed entirely')
- commit 6ad497b51f Remove CUDA warm-up probe — concurrent cuInit() deadlocks on Windows
- found_in_version: the fix commit is an ancestor of cb00653 (the first public release, 0.10.0 beta 1, 2026-10-14), so the faulty code only existed in development builds before 0.10.0-beta.1
- found_in_build: 10b04691f9 is the parent of the first fix commit 6ad497b51f and still carries the code the fix changes
- pytest 2026-10-20: passes; full suite passes
- Mutation: re-adding the worker_ready warm-up handler fails the test

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-06-18 — Fixed: commit 6ad497b51f
- 2026-10-20 — Verified: regression check re-run (pytest/Playwright)
- 2026-10-20 — Closed: released in 0.10.0-beta.1

## BUG-0029

**Lyric detection progress looked frozen at 8-10% with no feedback**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 47e0f0b4b7080c582b0099c61bae9ea7ca5d6593 |
| Severity | Low |
| Priority | P4 |
| Status | Fixed |

The progress bar jumped to fixed per-stage values and froze; heavy imports gave no feedback and a hung Demucs had no timeout, so detection looked stuck at ~8-10%.

**Steps to reproduce:** _pending_

**Expected:** Visible progress and a bounded run

**Observed:** Bar frozen at a fixed percentage

**Root cause:** Static per-stage percentages, no log during imports, unbounded Demucs subprocess.

**Fixes:** [FIX-0029](../FIX_LOG.md#fix-0029) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-06-18 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Perceived hang; real fix elsewhere.

**Evidence:**

- the real cause of the stall was the Job.params no-op (26e9886)
- commit 5dca471597 Redesign landing page with banner cards + fix lyrics progress stuck at 10%
- commit 405c6cb9b4 Fix lyrics detection stalling: timeout, early commit, progress tuning
- commit d556393ab6 Improve lyrics detection progress reporting and add hard timeout
- found_in_version: fix 5dca471597 (2026-06-17) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 47e0f0b4b7, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-06-18 — Fixed: commit 5dca471597, 405c6cb9b4, d556393ab6

## BUG-0032

**GP-embedded lyrics were never shown in the UI, so they looked missing**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 1e24332510e62e4a9732f46fb7c6838d4ab9f49c |
| Severity | Low |
| Priority | P3 |
| Status | Closed |

GP-embedded lyrics were written straight to the vocals XML at build time and never shown in the Letras editor or on the score, so they looked 'not captured'.

**Steps to reproduce:** 

1. Build a GP file with lyrics
2. Open the Letras panel

**Expected:** The lyrics appear, editable.

**Observed:** Nothing shown.

**Root cause:** The GP pipeline did not return the lyrics for storage in params.

**Fixes:** [FIX-0032](../FIX_LOG.md#fix-0032) (0.10.0-beta.1)

**Verified:** regression test(s) test_gp_embedded_lyrics_surface_as_recording_clock_events pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-06-29 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Lyrics were in the bundle; only invisible.

**Evidence:**

- CLAUDE.md § Lyrics formats (GP-embedded lyrics surface in the editor)
- commit b16853a message: 'so they looked "not captured"'
- commit b16853a479 Add playback speed control + surface GP-embedded lyrics in the editor
- found_in_version: the fix commit is an ancestor of cb00653 (the first public release, 0.10.0 beta 1, 2026-10-14), so the faulty code only existed in development builds before 0.10.0-beta.1
- found_in_build: 1e24332510 is the parent of the first fix commit b16853a479 and still carries the code the fix changes

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-06-29 — Fixed: commit b16853a479
- 2026-06-29 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0036

**Lyrics drawn early after a lead-in; added words landed off-cursor**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 19f40bfea96b1d17ed7fe624256a87e2359ec2b7 |
| Severity | Low |
| Priority | P4 |
| Status | Fixed |

After a lead-in rebuild lyrics were drawn at un-padded time ('adiantada'), and the add-word path stored a +viewOrigin-offset time.

**Steps to reproduce:** _pending_

**Expected:** Words track their notes

**Observed:** Lyrics early; new word not under cursor

**Root cause:** leadInBuilt not applied to lyric drawing; wrong clock on add.

**Fixes:** [FIX-0036](../FIX_LOG.md#fix-0036) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-06-30 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Visual misalignment.

**Evidence:**

- user quote: 'adiantada'
- commit 9c10711313 Lead-in: shift lyrics in the viewer + add the option to the GP create form
- found_in_version: fix 9c10711313 (2026-06-30) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 19f40bfea9, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-06-30 — Fixed: commit 9c10711313

## BUG-0084

**Native lyrics never appeared: vocal note was 0 instead of the 254 sentinel**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer (in game) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | daea573d85b9465ccecdda8dca10b924be86bf75 |
| Severity | High |
| Priority | P2 |
| Status | Closed |

Every syllable in the native vocals SNG had note 0, a real (absurdly low) MIDI pitch, so the game did not render scrolling lyrics even though the vocals arrangement, manifest and xblock were all present.

**Steps to reproduce:** _pending_

**Expected:** The lyrics scroll in game.

**Observed:** The lyrics never appeared.

**Root cause:** from_vocals wrote note 0 instead of VOCAL_NOTE = 254.

**Fixes:** [FIX-0084](../FIX_LOG.md#fix-0084) (0.10.0-beta.1)

**Verified:** TESTING.md §7f-bis: 'Confirmed in-game (vocals, multiple songs — native PSARC): the scrolling lyrics now appear (needed BOTH `SngVocal.note = 254` ... AND the vendored lyric-font symbol atlas)' (by the maintainer (in game))

**Resolved:** 2026-07-09 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Lyrics were missing from every native PSARC.

**Evidence:**

- CLAUDE.md § SNG binary compilation (`infrastructure/packaging/psarc/sng.py`) — 'Each `SngVocal.note` is the non-pitched sentinel **`VOCAL_NOTE = 254`**, NOT 0'
- commit 7568ddde07 Fix native-PSARC lyrics not appearing: vocals note must be 254, not 0
- found_in_version: the fix commit 7568ddde07 is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent daea573d85

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-09 — Fixed: commit 7568ddde07
- 2026-07-09 — Verified: confirmed by user
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0085

**Native lyrics never appeared: vocals SNG had an empty glyph atlas**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer (in game) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 7568ddde07ec30e41dd789b4c55044a69cd5406e |
| Severity | High |
| Priority | P2 |
| Status | Closed |

The vocals SNG wrote the Symbols sections (the lyric font's glyph atlas) empty, leaving the game no glyphs to draw, so the lyrics silently never appeared even with note 254.

**Steps to reproduce:** _pending_

**Expected:** The lyrics scroll in game.

**Observed:** The lyrics never appeared.

**Root cause:** SymbolsHeader/Texture/Definition were written empty.

**Fixes:** [FIX-0085](../FIX_LOG.md#fix-0085) (0.10.0-beta.1)

**Verified:** TESTING.md §7f-bis: 'Confirmed in-game (vocals, multiple songs — native PSARC): the scrolling lyrics now appear' (by the maintainer (in game))

**Resolved:** 2026-07-09 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Lyrics were missing from every native PSARC.

**Evidence:**

- CLAUDE.md § SNG binary compilation (`infrastructure/packaging/psarc/sng.py`) — 'The vocals SNG also embeds the **lyric-font glyph atlas**'
- commit b752651569 Embed the lyric-font glyph atlas in the vocals SNG so the letra renders
- found_in_version: the fix commit b752651569 is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent 7568ddde07

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-09 — Fixed: commit b752651569
- 2026-07-09 — Verified: confirmed by user
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0093

**Lyrics scrolled in game as a wall of text (no line breaks within long lines)**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer (in game) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | feb6390a64d3a73339aff7a6e0cf53c2f509798e |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

WhisperX segments are whole sentences and the '+' line break went only at segment ends, so long segments (~13 words) scrolled as one wall of text; lyrics detected earlier or from long-lined sources kept the problem.

**Steps to reproduce:** 

1. Detect lyrics (or use a long-lined source)
2. Play the song in Rocksmith

**Expected:** Short display lines.

**Observed:** One long line of text scrolling.

**Root cause:** segments_to_vocal_events broke only at segment ends; no cap at build time.

**Fixes:** [FIX-0093](../FIX_LOG.md#fix-0093) (0.10.0-beta.1)

**Verified:** regression test(s) test_long_segment_is_split_into_lines_by_word_cap, test_segment_breaks_on_a_sung_pause, test_enforce_max_line_words_breaks_long_lines, test_enforce_max_line_words_keeps_authored_breaks_and_short_lines, test_enforce_max_line_words_never_breaks_mid_word pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-07-10 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Lyrics hard to read in game.

**Evidence:**

- CLAUDE.md § Automatic lyric detection + in-app editor (Line breaks; Build-time line cap)
- commit d2e8199: 'seen on "Awaken the Giant"'
- commit 4eb877b: 'seen on "Free"'
- commit d2e81991a8 Break long WhisperX segments into short lyric lines
- commit 4eb877bc41 Cap lyric line length at build time (fix wall-of-text without re-detect)
- found_in_version: the fix commits are ancestor of cb00653 (the first public release, 0.10.0 beta 1, 2026-10-14), so the faulty code only existed in development builds before 0.10.0-beta.1
- found_in_build: feb6390a64 is the parent of the first fix commit d2e81991a8 and still carries the code the fix changes

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-10 — Fixed: commit d2e81991a8, 4eb877bc41
- 2026-07-10 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0109

**A native GPU crash (Turing/cuDNN) aborted lyric detection and recurred on every run**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 8a54d0693ccae28f61496dc4f449a7df380c2679 |
| Severity | High |
| Priority | P2 |
| Status | Closed |

On the maintainer's RTX 2060 Super, WhisperX (and Demucs) crashed natively on CUDA (exit 0xC0000409/3221226505) with no traceback; detection failed, and once a fallback existed the doomed GPU attempt was repeated on every song.

**Steps to reproduce:** 

1. Run lyric detection on a GPU with the torch/cuDNN mismatch

**Expected:** Detection completes (on GPU if possible, else CPU) and remembers a broken GPU.

**Observed:** The run crashed with only an exit code; later every run retried the GPU first.

**Root cause:** A cuDNN/ctranslate2 native crash in the float16 GPU path with no fallback, no marker and no Demucs retry.

**Fixes:** [FIX-0109](../FIX_LOG.md#fix-0109) (0.10.0-beta.1)

**Verified:** regression test(s) test_cuda_crash_falls_back_to_cpu_and_marks, test_cpu_crash_does_not_retry, test_cuda_broken_marker_round_trips, test_broken_marker_downgrades_cuda_to_cpu, test_legacy_marker_still_honoured, test_whisperx_attempts_escalation_ladder, test_whisperx_compute_type_override_round_trips pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-07-11 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Lyric detection failed on that GPU.

**Evidence:**

- CLAUDE.md § Automatic lyric detection + in-app editor (GPU crash → CPU fallback; the escalation ladder)
- commit 9e53400442 Lyric detection: fall back to CPU when the GPU WhisperX subprocess crashes
- commit 314e09eef9 WhisperX GPU crash: remember it and skip the doomed GPU attempt next time
- commit d4aab16257 Robust GPU→CPU fallback for the whole ML stack + completeness lyrics fix
- commit 07cf50ee50 WhisperX GPU: escalate float16→int8_float16 before falling to CPU
- found_in_version: the fix commits are ancestor of cb00653 (the first public release, 0.10.0 beta 1, 2026-10-14), so the faulty code only existed in development builds before 0.10.0-beta.1
- found_in_build: 8a54d0693c is the parent of the first fix commit 9e53400442 and still carries the code the fix changes

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-11 — Fixed: commit 9e53400442, 314e09eef9, d4aab16257, 07cf50ee50
- 2026-07-11 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0110

**ctranslate2 could not load torch's bundled cuDNN on Windows and crashed**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | d45d10a5ad473bd517e55ad7aff2a31881d04605 |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

Even with a matching stack (torch cu121 with cuDNN 9.1, ctranslate2 4.4.0), the GPU WhisperX run crashed (0xC0000409) because cudnn_ops64_9.dll/cublas64_12.dll only live in torch/lib, which is not on the Windows DLL search path.

**Steps to reproduce:** 

1. Run lyric detection on the GPU on Windows

**Expected:** GPU transcription works.

**Observed:** Native crash.

**Root cause:** torch/lib was not on the DLL search path for ctranslate2.

**Fixes:** [FIX-0110](../FIX_LOG.md#fix-0110) (0.10.0-beta.1)

**Verified:** regression test(s) test_add_cuda_dll_dirs_is_noop_off_windows pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-07-11 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: A CPU fallback existed.

**Evidence:**

- CLAUDE.md § Automatic lyric detection + in-app editor (Windows cuDNN DLL discovery)
- commit c323bad409 WhisperX GPU: put torch's bundled cuDNN 9 on the DLL search path (Windows)
- found_in_version: the fix commit is an ancestor of cb00653 (the first public release, 0.10.0 beta 1, 2026-10-14), so the faulty code only existed in development builds before 0.10.0-beta.1
- found_in_build: d45d10a5ad is the parent of the first fix commit c323bad409 and still carries the code the fix changes

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-11 — Fixed: commit c323bad409
- 2026-07-11 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0132

**All-melisma GP lyric line dropped instead of holding the previous syllable**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 44123dc84fa3526c459f2e1b4ed079ef2200188d |
| Severity | Low |
| Priority | P4 |
| Status | Closed |

distribute_syllables skipped a line made only of '_' holds, so those attacks never extended the previous syllable.

**Steps to reproduce:** _pending_

**Expected:** Syllable held across the line

**Observed:** Held syllable too short

**Root cause:** Early continue.

**Fixes:** [FIX-0132](../FIX_LOG.md#fix-0132) (0.10.0-beta.1)

**Verified:** regression test(s) test_distribute_syllables_all_melisma_line_extends_previous_across_the_line pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-07-13 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Lyric timing.

**Evidence:**

- commit 7bbe5e6179 Extend the previous syllable across an all-melisma GP lyric line (MIN-13)
- found_in_version: fix 7bbe5e6179 (2026-07-13) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 44123dc84f, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-13 — Fixed: commit 7bbe5e6179
- 2026-07-13 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0185

**Lyric edits showed no pending sign**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | pending (not recorded) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 607ee320289532986b0adcd9c903d867d96bdf29 |
| Severity | Low |
| Priority | P4 |
| Status | Fixed |

Editing lyrics did not light 'Pendente', unlike every other pending edit.

**Steps to reproduce:** 

1. Edit a lyric word
2. Look at the pending indicator

**Expected:** 'Pendente: letra' shown.

**Observed:** No pending sign.

**Root cause:** No serialized baseline of the lyric rows to compare against.

**Fixes:** [FIX-0185](../FIX_LOG.md#fix-0185) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-09-27 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Indicator only; edits were still applied on rebuild.

**Evidence:**

- CLAUDE.md § Adjusting the lyric beside the score (the inspector's "Letra" tab)
- CLAUDE.md: 'before, a lyric edit showed no pending sign at all'
- commit 15e703bb48 Adjust the lyric beside the score: a Letra tab in the Partitura inspector
- found_in_version: the fix commit is an ancestor of cb00653 (the first public release, 0.10.0 beta 1, 2026-10-14), so the faulty code only existed in development builds before 0.10.0-beta.1
- found_in_build: 607ee32028 is the parent of the first fix commit 15e703bb48 and still carries the code the fix changes

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-09-27 — Fixed: commit 15e703bb48

## BUG-0190

**GP-embedded lyrics never reached the editor (params dict mutated in place)**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 65527dd20cec9e4f9742eac458e76a7daf4c6af1 |
| Severity | High |
| Priority | P2 |
| Status | Closed |

The build task wrote lyrics_events into job.params' own dict, so the {**params} it then assigned compared equal and no UPDATE was issued; the lyrics reached the bundle but never the editor in a real run.

**Steps to reproduce:** 

1. Build a GP file with lyrics
2. Open the Letra page

**Expected:** The file's lyrics are listed in the editor.

**Observed:** The editor was empty.

**Root cause:** With expire_on_commit off the dict read is the committed value; mutating it before reassigning hid the change from SQLAlchemy.

**Fixes:** [FIX-0190](../FIX_LOG.md#fix-0190) (0.10.0-beta.1)

**Verified:** regression test(s) test_a_gp_files_lyrics_reach_the_editor_after_the_build pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-09-28 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: GP lyrics could not be edited at all.

**Evidence:**

- CLAUDE.md § Lyrics formats (GP-embedded lyrics surface in the editor)
- CLAUDE.md: 'That store silently never happened in a real run until 2026-09-28'
- commit deb168f158 Lyrics from the score: Songsterr tabs bring theirs, and syllables follow the vocal line
- found_in_version: the fix commit is an ancestor of cb00653 (the first public release, 0.10.0 beta 1, 2026-10-14), so the faulty code only existed in development builds before 0.10.0-beta.1
- found_in_build: 65527dd20c is the parent of the first fix commit deb168f158 and still carries the code the fix changes

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-09-28 — Fixed: commit deb168f158
- 2026-09-28 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0191

**GP lyrics timed on the guitar chart's notes instead of the vocal line**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | pending (not recorded) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 65527dd20cec9e4f9742eac458e76a7daf4c6af1 |
| Severity | Medium |
| Priority | P2 |
| Status | Closed |

Syllables were distributed over the charted guitar's attacks, so a vocal line with a different rhythm slid off.

**Steps to reproduce:** 

1. Import a GP file whose lyrics are written on a vocal track
2. Build and view the lyrics

**Expected:** Each syllable on a note of the track the lyrics are written on.

**Observed:** Syllables drifted off the singing.

**Root cause:** The pipeline ignored GP5 trackChoice / GPIF <Lyrics> track and used the chart's notes.

**Fixes:** [FIX-0191](../FIX_LOG.md#fix-0191) (0.10.0-beta.1)

**Verified:** regression test(s) test_gp_lyrics_are_sung_on_the_vocal_line_not_the_charted_guitar, test_gp7_lyrics_are_timed_on_the_notes_of_their_own_track, test_extra_spaces_skip_notes_and_a_newline_ends_a_line, test_comments_and_a_hyphen_before_a_space_are_read_like_guitar_pro pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-09-28 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Wrong lyric timing; editable by hand.

**Evidence:**

- CLAUDE.md § Lyrics formats (GP-embedded lyrics → per-syllable note alignment)
- CLAUDE.md: 'Before 2026-09-28 it always used the guitar chart's notes'
- commit deb168f158 Lyrics from the score: Songsterr tabs bring theirs, and syllables follow the vocal line
- found_in_version: the fix commit is an ancestor of cb00653 (the first public release, 0.10.0 beta 1, 2026-10-14), so the faulty code only existed in development builds before 0.10.0-beta.1
- found_in_build: 65527dd20c is the parent of the first fix commit deb168f158 and still carries the code the fix changes

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-09-28 — Fixed: commit deb168f158
- 2026-09-28 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0197

**Lyric line cap counted syllables, splitting mid-phrase and leaving orphan words**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 133ed79ff436812bc898ce6146d3277e4cba87e6 |
| Severity | Low |
| Priority | P3 |
| Status | Closed |

enforce_max_line_words counted every syllable event, so 'chas-in' te-qui-la' used five of seven slots, and split an 8-word line as 7 + an orphan ('with+ / who').

**Steps to reproduce:** _pending_

**Expected:** Long lines split evenly by words.

**Observed:** Mid-phrase breaks and orphaned words.

**Root cause:** The cap counted syllable events instead of words and cut at the first overflow.

**Fixes:** [FIX-0197](../FIX_LOG.md#fix-0197) (0.10.0-beta.1)

**Verified:** regression test(s) test_a_long_line_is_split_evenly_counting_words_not_syllables pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-09-29 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Lyric readability only.

**Evidence:**

- CLAUDE.md § Automatic lyric detection + in-app editor (Build-time line cap)
- CLAUDE.md § Lyrics formats (The vocal line also gives each syllable its length and the lyric its phrases)
- commit 3a3357b8a6 Use the vocal track: lyric phrases, syllable lengths and a "Voz" source; YouTube audio for any GP file
- found_in_version: the fix commit is an ancestor of cb00653 (the first public release, 0.10.0 beta 1, 2026-10-14), so the faulty code only existed in development builds before 0.10.0-beta.1
- found_in_build: 133ed79ff4 is the parent of the first fix commit 3a3357b8a6 and still carries the code the fix changes

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-09-29 — Fixed: commit 3a3357b8a6
- 2026-09-29 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0198

**Lyrics stayed put when the notes' sync was corrected**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 3a3357b8a6bc6ff9e1a1a383bdf6a38d08cd03a8 |
| Severity | Medium |
| Priority | P2 |
| Status | Closed |

After the first build the GP lyrics live as editor rows in the recording clock, and nothing moved them when notes were re-timed — not in the preview, not in the rebuild.

**Steps to reproduce:** 

1. Correct the 'Início' or tempo of the chart
2. Look at the lyric words / rebuild

**Expected:** Lyrics timed on the score move with the notes.

**Observed:** Words stayed where they were.

**Root cause:** Editor rows were not carried through the reference chart's pending sync map.

**Fixes:** [FIX-0198](../FIX_LOG.md#fix-0198) (0.10.0-beta.1)

**Verified:** regression test(s) test_lyrics_say_whether_they_follow_the_charts_sync_corrections pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-09-29 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Lyrics desynced by every sync correction; fixable by hand.

**Evidence:**

- CLAUDE.md § Adjusting the lyric beside the score (Lyrics timed on the score follow the chart's sync corrections)
- user quote (undated): 'Quando corrijo o início das notas, a letra não se está a mover'
- commit 4ed26393c4 Lyrics timed on the score follow the chart's sync corrections
- found_in_version: the fix commit is an ancestor of cb00653 (the first public release, 0.10.0 beta 1, 2026-10-14), so the faulty code only existed in development builds before 0.10.0-beta.1
- found_in_build: 3a3357b8a6 is the parent of the first fix commit 4ed26393c4 and still carries the code the fix changes

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-09-29 — Fixed: commit 4ed26393c4
- 2026-09-29 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0254

**Times rounded to "1:60" in lyric lengths and "[00:60.00]" in the exported LRC**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | _pending_ |
| Build / commit | cb00653bedba4cd2f9070ceb2acb8e925c883319 |
| Severity | Low |
| Priority | P4 |
| Status | Fixed |

fmtMinSec and the LRC export split minutes and seconds before rounding, so a value just under a whole minute was shown as 1:60 and exported as [00:60.00].

**Steps to reproduce:** 

1. Show or export a time just below a whole minute (e.g. 119.996 s)

**Expected:** 2:00 / [02:00.00].

**Observed:** 1:60 / [00:60.00].

**Root cause:** Rounding happened after splitting into minutes and seconds.

**Fixes:** [FIX-0254](../FIX_LOG.md#fix-0254) (0.10.0-beta.2)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-10-14 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: A formatting error; the LRC line still carried a valid time value.

**Evidence:**

- CHANGELOG.en.md 0.10.0 beta 2 — Fixed: "`1:60` in the length of lyrics found online and `[00:60.00]` in the exported LRC."
- commit 2d0b87ef91: "fmtMinSec and the LRC export round before splitting (1:60, [00:60.00])"
- found_in_version pending: faulty code present at cb00653 (beta 1); found by an audit, detection date not documented

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-10-14 — Fixed: commit 2d0b87ef91

## BUG-0262

**Letra table showed times like 1:010.0**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 47a28cae4f8cdbb1e99dc187e9c0f748f599c289 |
| Severity | Low |
| Priority | P4 |
| Status | Closed |

fmtClockTenths rounded the tenths after deciding the leading zero, so 69.96 s read 1:010.0.

**Steps to reproduce:** _pending_

**Expected:** 1:10.0

**Observed:** 1:010.0

**Root cause:** Rounding order.

**Fixes:** [FIX-0262](../FIX_LOG.md#fix-0262) (0.10.0-beta.1)

**Verified:** commit 7413013: found walking the guides with Playwright (by the developer (manual check))

**Resolved:** 2026-10-14 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Cosmetic.

**Evidence:**

- commit 74130132ec Guide checked in the browser; fixes it turned up
- found_in_version: fix 74130132ec (2026-10-14) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 47a28cae4f, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-10-14 — Fixed: commit 74130132ec
- 2026-10-14 — Verified: manual
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0317

**A GP7 lyric line on a bar never played appeared at the start**

| | |
|---|---|
| Detected | 2026-10-18 |
| Reported by | code review (Claude, on the maintainer's request) |
| Found in | 0.11.0-beta.2 |
| Build / commit | f64c45e8e176c44bd87c7c7866f741330b443011 |
| Severity | Low |
| Priority | P3 |
| Status | Verified |

A line on a bar after Fine or in an ending not taken fell back to tick 0, on top of the first line.

**Steps to reproduce:** 

1. See the description (found by reading the code)

**Expected:** As described in the solution.

**Observed:** A line on a bar after Fine or in an ending not taken fell back to tick 0, on top of the first line.

**Root cause:** An `or [0]` fallback.

**Fixes:** [FIX-0317](../FIX_LOG.md#fix-0317) (0.11.0-beta.4)

**Verified:** tests/test_gpif_import.py::test_a_lyric_line_on_a_bar_never_played_is_not_put_at_the_start passed, and fails with the fix reverted (by pytest (the test fails on the old code))

**Resolved:** 2026-10-18 · **Closed:** _pending_

**Evidence:**

- code review of the whole codebase (six reviewers), confirmed by reading the code

**History:**

- 2026-10-18 — Open: reported
- 2026-10-18 — Fixed: commit 9fff3a3837
- 2026-10-18 — Verified: its test passes and fails on the old code

## BUG-0320

**UltraStar syllables of one word were shown as separate words**

| | |
|---|---|
| Detected | 2026-10-18 |
| Reported by | code review (Claude, on the maintainer's request) |
| Found in | 0.11.0-beta.2 |
| Build / commit | f64c45e8e176c44bd87c7c7866f741330b443011 |
| Severity | Medium |
| Priority | P3 |
| Status | Verified |

A syllable with no space before it continues the word in UltraStar; it was written without the Rocksmith "-" join, so "Hel" "lo" showed "Hel lo".

**Steps to reproduce:** 

1. See the description (found by reading the code)

**Expected:** As described in the solution.

**Observed:** A syllable with no space before it continues the word in UltraStar; it was written without the Rocksmith "-" join, so "Hel" "lo" showed "Hel lo".

**Root cause:** The leading/trailing spaces were stripped before deciding.

**Fixes:** [FIX-0320](../FIX_LOG.md#fix-0320) (0.11.0-beta.4)

**Verified:** tests/test_vocals.py::test_ultrastar_syllables_of_one_word_are_joined_and_words_are_not passed, and fails with the fix reverted (by pytest (the test fails on the old code))

**Resolved:** 2026-10-18 · **Closed:** _pending_

**Evidence:**

- code review of the whole codebase (six reviewers), confirmed by reading the code

**History:**

- 2026-10-18 — Open: reported
- 2026-10-18 — Fixed: commit 0b354c27fe
- 2026-10-18 — Verified: its test passes and fails on the old code

## BUG-0321

**An LRC line with several times put a time into the lyric**

| | |
|---|---|
| Detected | 2026-10-18 |
| Reported by | code review (Claude, on the maintainer's request) |
| Found in | 0.11.0-beta.2 |
| Build / commit | f64c45e8e176c44bd87c7c7866f741330b443011 |
| Severity | Medium |
| Priority | P3 |
| Status | Verified |

"[00:12.00][01:10.00]Hello" kept "[01:10.00]Hello" as text and never placed the second time.

**Steps to reproduce:** 

1. See the description (found by reading the code)

**Expected:** As described in the solution.

**Observed:** "[00:12.00][01:10.00]Hello" kept "[01:10.00]Hello" as text and never placed the second time.

**Root cause:** Only the first tag was parsed.

**Fixes:** [FIX-0321](../FIX_LOG.md#fix-0321) (0.11.0-beta.4)

**Verified:** tests/test_vocals.py::test_an_lrc_line_with_several_times_is_sung_at_each_of_them passed, and fails with the fix reverted (by pytest (the test fails on the old code))

**Resolved:** 2026-10-18 · **Closed:** _pending_

**Evidence:**

- code review of the whole codebase (six reviewers), confirmed by reading the code

**History:**

- 2026-10-18 — Open: reported
- 2026-10-18 — Fixed: commit 0b354c27fe
- 2026-10-18 — Verified: its test passes and fails on the old code

## BUG-0352

**Lyrics of a Songsterr tab land later and later: a grace note in the vocal line gets no syllable**

| | |
|---|---|
| Detected | 2026-10-21 |
| Reported by | the maintainer (Songsterr song: the lyric always late, words off their notes) |
| Found in | 0.11.1-beta.3 |
| Build / commit | _pending_ |
| Severity | Medium |
| Priority | P2 |
| Status | Verified |

Guitar Pro and Songsterr give every beat of the lyrics' track that is not a rest a syllable, grace beats included. The Songsterr import dropped grace notes and both parsers skipped grace beats when timing the lyrics, so every syllable after a grace landed one note late, and the lag grew with each grace. Whether the reporter's song has grace notes in its vocal line is not known.

**Steps to reproduce:** 

1. Import from Songsterr a tab whose vocal line has a grace note, with lyrics
2. Build it and look at where each word sits

**Expected:** Each syllable on its own note, the grace note's included.

**Observed:** From the grace note on, every syllable sits on the next note: the lyric runs late.

**Root cause:** songsterr_gp dropped graceNote beats; parser._lyric_notes only counted beats with notes in the measure (GP5 grace effects ignored) and gpif_parser._lyric_notes skipped GraceNotes beats.

**Fixes:** [FIX-0350](../FIX_LOG.md#fix-0350) (0.11.1-beta.4)

**Verified:** test_a_grace_note_in_the_vocal_line_takes_its_own_syllable and test_gp7_a_grace_beat_in_the_vocal_line_takes_a_syllable, each failing with its parser's change reverted (by the developer (pytest))

**Resolved:** 2026-10-21 · **Closed:** _pending_

**Evidence:**

- 2026-10-21: a Songsterr vocal part 'one two three four five' with a grace before beat 2 — syllables at 0, 0.375, 0.5, 1.0, 1.5 s (old: the grace had none and 'two' sat on beat 2)
- 2026-10-21: full pytest suite green

**History:**

- 2026-10-21 — Open: reported in conversation
- 2026-10-21 — Fixed: commit ae9cd83ae8
- 2026-10-21 — Verified: pytest 2026-10-21

## BUG-0353

**Lyrics of a Songsterr tab follow the guitar's notes when the text comes in the guitar's part**

| | |
|---|---|
| Detected | 2026-10-22 |
| Reported by | the maintainer (Songsterr song: the lyric still late after BUG-0352; a screenshot of Songsterr showing the words under an empty guitar staff) |
| Found in | 0.11.1-beta.4 |
| Build / commit | _pending_ |
| Severity | Medium |
| Priority | P2 |
| Status | Fixed |

Songsterr shows the lyrics over every track, so the text can come in a part that does not sing it. The import bound the syllables to the first part with text; when that was a guitar, every syllable waited for a guitar note and ran late through the guitar's rests. Whether the reporter's tab carries the text in its guitar part is not known.

**Steps to reproduce:** 

1. Import from Songsterr a tab whose guitar part carries the lyrics and whose vocal part sings them
2. Build it and look at where each word sits

**Expected:** Each syllable on its note of the vocal line.

**Observed:** The syllables sit on the guitar's notes and wait out its rests: the lyric runs late.

**Root cause:** songsterr_gp._lyrics took the first part with newLyrics as the part whose notes time the syllables, whatever instrument it was.

**Fixes:** [FIX-0351](../FIX_LOG.md#fix-0351) (unreleased)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-10-22 · **Closed:** _pending_

**Evidence:**

- 2026-10-22: test_lyrics_that_come_in_a_guitar_part_follow_the_vocal_line (text in both parts, only in the guitar's, a vocal part known only by its GM program) passes, and fails with the vocal preference removed
- 2026-10-22: full pytest suite green

**History:**

- 2026-10-22 — Open: reported in conversation with a Songsterr screenshot
- 2026-10-22 — Fixed: commit ac46f8b0f2

## BUG-0355

**Lyrics drift further off along the song: a tied note in the vocal line takes a syllable**

| | |
|---|---|
| Detected | 2026-10-22 |
| Reported by | the maintainer (Songsterr project "Just an ordinary man": the lyric late, the synthesized voice drifting too; .rfproj sent) |
| Found in | 0.11.1-beta.4 |
| Build / commit | _pending_ |
| Severity | Medium |
| Priority | P2 |
| Status | Verified |

Both parsers gave every beat of the lyrics' track that has notes a syllable, tied beats included. Each tie moved every later syllable one note off; a lyric written as one line never starts again from a bar, so the offset kept growing (33 s at the end of the user's song).

**Steps to reproduce:** 

1. Import a Songsterr tab whose vocal line has tied notes and whose lyric is one line
2. Build it and compare each word with its vocal note

**Expected:** Each syllable on its own untied vocal note.

**Observed:** From the first tie on, the words sit on the wrong notes, further off with every tie.

**Root cause:** parser._lyric_notes and gpif_parser._lyric_notes appended a lyric note for every beat with notes, including beats whose notes are all tie destinations.

**Fixes:** [FIX-0353](../FIX_LOG.md#fix-0353) (unreleased)

**Verified:** test_a_tied_note_in_the_vocal_line_takes_no_syllable and test_gp7_a_tied_beat_in_the_vocal_line_takes_no_syllable, each failing with its parser's change reverted (by the developer (pytest))

**Resolved:** 2026-10-22 · **Closed:** _pending_

**Evidence:**

- 2026-10-22: the user's file: 509 syllable slots, 581 vocal beats with notes, 72 of them only ties — after the fix 509 lyric notes and all 489 syllable events on a vocal attack (before: the last word 33 s away)
- 2026-10-22: full pytest suite green

**History:**

- 2026-10-22 — Open: reported in conversation with the project file
- 2026-10-22 — Fixed: commit c869d4c570
- 2026-10-22 — Verified: pytest 2026-10-22
