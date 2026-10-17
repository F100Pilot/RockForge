<!-- Generated from tracking/bugs.json by `python -m tools.tracking render`. Do not edit by hand: edit the JSON and render again. -->

# Bugs: audio

Audio: loudness, Wwise, stems, ML stages. Index: [BUG_LOG.md](../BUG_LOG.md).

## BUG-0002

**Silent in-game audio: the .wem had no seek table**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer (in game) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | e3b016023d03f170bce94abe503aa4acde7deb68 |
| Severity | Critical |
| Priority | P1 |
| Status | Closed |

Converting through a blank Wwise project produced a Vorbis .wem without a seek table; Rocksmith loaded the song but played silence, the note highway did not advance and the game exited seconds in.

**Steps to reproduce:** _pending_

**Expected:** The song's audio plays in game.

**Observed:** Silence, a frozen note highway and the game exiting seconds in.

**Root cause:** The convert-external-source flow used a blank project's 'Vorbis Quality High' preset, which writes no seek table.

**Fixes:** [FIX-0002](../FIX_LOG.md#fix-0002) (0.10.0-beta.1)

**Verified:** regression test(s) test_convert_extracts_template_and_patches_header, test_unsupported_wwise_version_rejected pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-06-12 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: No song built this way could be played.

**Evidence:**

- CLAUDE.md § Hard constraints (these have bitten us — keep them) — 'The .wem must have a seek table.'
- commit 42e525bedd Fix silent in-game audio: convert .wem via DLC Builder's Wwise template
- found_in_version: the fix commit 42e525bedd is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent e3b016023d

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-06-12 — Fixed: commit 42e525bedd
- 2026-06-12 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0021

**Jobs stuck at the normalize/lyrics stage: ffmpeg inherited the console's stdin**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | pending (not recorded) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 6479f405b1463a10536305b6d4c138a02b061553 |
| Severity | High |
| Priority | P2 |
| Status | Closed |

Run as a subprocess from the start.bat worker, ffmpeg inherited the console's stdin, went interactive and blocked forever, so a job sat at the normalize / lyrics 'normalizing' stage with no error and no progress.

**Steps to reproduce:** _pending_

**Expected:** Normalization finishes and the job moves on.

**Observed:** The job stayed at the normalize stage indefinitely.

**Root cause:** ffmpeg (and Demucs) were started without -nostdin / stdin=DEVNULL, so they read the inherited console stdin.

**Fixes:** [FIX-0021](../FIX_LOG.md#fix-0021) (0.10.0-beta.1)

**Verified:** regression test(s) test_normalize_never_reads_stdin, test_normalize_timeout_raises, test_normalize_missing_ffmpeg_raises pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-06-16 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Builds and lyric detection hung with no error on the main Windows setup.

**Evidence:**

- CLAUDE.md § Hard constraints (these have bitten us — keep them) — 'External CLIs must not inherit stdin.'
- commit f72672ee99 Fix ffmpeg hang at the normalize/lyrics stage (inherited stdin)
- found_in_version: the fix commit f72672ee99 is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent 6479f405b1

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-06-16 — Fixed: commit f72672ee99
- 2026-06-16 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0065

**Song-select preview played the full track over itself**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | pending (not recorded) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | eef98455148ecd9abcea5a931e9a8293a55ad550 |
| Severity | Low |
| Priority | P4 |
| Status | Closed |

The preview bank reused the full-song .wem.

**Steps to reproduce:** _pending_

**Expected:** Short clip

**Observed:** Whole track as preview

**Root cause:** No preview clip.

**Fixes:** [FIX-0065](../FIX_LOG.md#fix-0065) (0.10.0-beta.1)

**Verified:** regression test(s) test_preview_uses_a_trimmed_clip_not_the_full_stream pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-07-07 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Annoying, not blocking.

**Evidence:**

- commit a1a67acce4 Native PSARC: preview bank uses a real trimmed clip, not the full stream
- found_in_version: fix a1a67acce4 (2026-07-07) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent eef9845514, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-07 — Fixed: commit a1a67acce4
- 2026-07-07 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0066

**Overlapping copies of the preview played while browsing**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | pending (not recorded) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | a1a67acce4477215f4278a5fc5fb5c319d443428 |
| Severity | Low |
| Priority | P4 |
| Status | Closed |

The preview .bnk lacked the toolkit's single-instance HIRC flags, so the game layered copies.

**Steps to reproduce:** _pending_

**Expected:** One preview at a time

**Observed:** Layered previews

**Root cause:** Missing preview flags.

**Fixes:** [FIX-0066](../FIX_LOG.md#fix-0066) (0.10.0-beta.1)

**Verified:** regression test(s) test_preview_bank_limits_itself_to_one_instance pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-07-07 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Annoying.

**Evidence:**

- commit 55b720b86f Native PSARC: mark the preview SoundBank single-instance (fix overlap)
- found_in_version: fix 55b720b86f (2026-07-07) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent a1a67acce4, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-07 — Fixed: commit 55b720b86f
- 2026-07-07 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0097

**Song-select preview blasted over the song list (uncalibrated bus volume)**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | pending (not recorded) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | d7a842003af389a63a25d13d95444c55ec4fcb0f |
| Severity | Low |
| Priority | P4 |
| Status | Closed |

Every .bnk shipped a neutral 0 dB volume; the trimmed preview's own loudness differed from the song's.

**Steps to reproduce:** _pending_

**Expected:** Preview level matched

**Observed:** Loud preview

**Root cause:** No loudness calibration.

**Fixes:** [FIX-0097](../FIX_LOG.md#fix-0097) (0.10.0-beta.1)

**Verified:** regression test(s) test_volume_offsets_loudness_to_target pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-07-10 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Annoyance.

**Evidence:**

- commit 6f078e2c55 Calculate Volumes: set the .bnk bus volume from measured loudness
- found_in_version: fix 6f078e2c55 (2026-07-10) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent d7a842003a, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-10 — Fixed: commit 6f078e2c55
- 2026-07-10 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0099

**Songs sounded quiet in game next to official DLC (-16 LUFS target)**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer (in game) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 45f1062efa8dee75d87e75e1acaaaaa4698b10a4 |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

Normalizing to -16 LUFS (broadcast level) played audibly quieter than retail's loud masters.

**Steps to reproduce:** _pending_

**Expected:** Retail-like level

**Observed:** Quiet songs

**Root cause:** Broadcast target.

**Fixes:** [FIX-0099](../FIX_LOG.md#fix-0099) (0.10.0-beta.1)

**Verified:** regression test(s) test_loudness_target_default_and_override, test_loudness_target_is_clamped pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-07-10 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Quality.

**Evidence:**

- CLAUDE.md § Wwise SoundBank (Volume)
- commit f4b38f613e Louder default + editable loudness target (songs read quiet vs retail)
- found_in_version: fix f4b38f613e (2026-07-10) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 45f1062efa, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-10 — Fixed: commit f4b38f613e
- 2026-07-10 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0120

**detect_tones and separate_stems ran the same Demucs separation twice**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | ba7edb0a08a3738f3516c69b0dc960f13b9918c0 |
| Severity | Low |
| Priority | P4 |
| Status | Closed |

Both tasks ran the same htdemucs_6s pass over the same recording into different workdirs, so running one after the other paid several minutes of Demucs twice for identical output.

**Steps to reproduce:** _pending_

**Expected:** The second task reuses the separated stems.

**Observed:** A second multi-minute separation.

**Root cause:** No shared cache between the two tasks.

**Fixes:** [FIX-0120](../FIX_LOG.md#fix-0120) (0.10.0-beta.1)

**Verified:** regression test(s) test_separate_guitar_reuses_an_existing_stem_without_rerunning, test_separate_stems_reuses_a_guitar_stem_from_a_prior_separate_guitar_call pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-07-13 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Wasted time only.

**Evidence:**

- CLAUDE.md § Stem separation — '**`detect_tones` and `separate_stems` (demucs backend) share one guitar-stem cache.**'
- commit message: '(MAJ-6)'
- commit 04e4bd999e Reuse an already-separated guitar stem between detect_tones/separate_stems (MAJ-6)
- found_in_version: the fix commit 04e4bd999e is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent ba7edb0a08

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-13 — Fixed: commit 04e4bd999e
- 2026-07-13 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0217

**Recording squashed by loudnorm: PSARC audio noisy and not clean**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 03eb8aa3526e60663a3a026729682ec8af8686d5 |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

The recording went through a single-pass loudnorm (a gain that moves with the music plus a limiter), which reshaped every song: on the user's mp3 LRA fell from 5.0 to 3.1 and it missed its own target.

**Steps to reproduce:** _pending_

**Expected:** The recording keeps its dynamics, only a fixed gain.

**Observed:** Audio with noise and no clean tone ('os PSARC criados pelo rockforge têm algum ruído e não têm uma tonalidade limpa').

**Root cause:** FfmpegNormalizer used loudnorm=I=-12:TP=-1.5:LRA=11 instead of one linear gain.

**Fixes:** [FIX-0217](../FIX_LOG.md#fix-0217) (0.10.0-beta.1)

**Verified:** regression test(s) test_the_recording_gets_a_linear_gain_not_loudnorm, test_the_gain_never_pushes_a_peak_over_the_ceiling, test_an_unmeasurable_recording_is_passed_through_untouched, test_the_recording_gain_goes_to_the_target_but_stops_at_the_peak_ceiling, test_the_true_peak_is_read_from_the_ebur128_summary pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-09-30 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Degraded audio in every song; playable.

**Evidence:**

- CLAUDE.md § Wwise SoundBank (`infrastructure/packaging/psarc/soundbank.py`) — '**The recording is NOT dynamics-processed — one linear gain (`recording_gain_db`).**'
- tasks/todo.md — 'Ruído / tom pouco limpo nos PSARC do RockForge'
- commit cad648e4a4 Cleaner PSARC audio and tones: linear gain, default tones, SNG tone changes
- found_in_version: the fix commit cad648e4a4 is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent 03eb8aa352

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-09-30 — Fixed: commit cad648e4a4
- 2026-09-30 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0277

**librosa runner failed with an external ML Python: its packaging folder shadowed pip's**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | _pending_ |
| Build / commit | cb00653bedba4cd2f9070ceb2acb8e925c883319 |
| Severity | High |
| Priority | P2 |
| Status | Fixed |

Run as a script, _librosa_runner.py has its own folder as sys.path[0], which holds RockForge's packaging package; it shadowed the pip packaging librosa imports, so every runner command failed from a source install with an external ML Python.

**Steps to reproduce:** 

1. Run from source with ROCKFORGE_ML_PYTHON pointing at another interpreter
2. Use a librosa stage (e.g. /detect-tempo)

**Expected:** The runner measures.

**Observed:** The runner command failed.

**Root cause:** sys.path[0] = infrastructure/, whose packaging/ package shadowed pip's packaging.

**Fixes:** [FIX-0277](../FIX_LOG.md#fix-0277) (0.10.0-beta.7)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-10-15 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Every librosa measurement unavailable in that configuration.

**Evidence:**

- CLAUDE.md § Automatic sync with a variable tempo — EXPERIMENTAL (2026-10-15): "Found on the way: run as a script, the runner's own folder is sys.path[0] ..."
- commit cfe40199df: "The librosa runner, run as a script, had its own folder first on sys.path, whose packaging package shadowed the one librosa imports; it now drops it."
- not in the changelog; found_in_version pending: faulty code present at cb00653 (no sys.path handling in _librosa_runner.py)

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-10-15 — Fixed: commit cfe40199df

## BUG-0286

**Separated stems showed many false attacks from the separation's residue**

| | |
|---|---|
| Detected | 2026-10-16 |
| Reported by | found during development |
| Found in | _pending_ |
| Build / commit | ba8f5fc7180b87c6d1da0b7f89ea321b6ca593e2 |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

librosa averages the log-mel flux over every band, and the faint residue a separation leaves (a hi-hat 30 dB down) filled bands the instrument never reaches, so a separated bass showed 0.87 and a guitar stem 0.39 strong false attacks per note of an in-sync chart.

**Steps to reproduce:** _pending_

**Expected:** Few false attacks on a separated instrument.

**Observed:** 0.87 (bass) / 0.39 (guitar) false strong attacks per note on synthesized songs.

**Root cause:** Onset envelope computed over all mel bands with no floor relative to the stem's loudest.

**Fixes:** [FIX-0286](../FIX_LOG.md#fix-0286) (0.10.0-beta.10)

**Verified:** regression test(s) test_a_separated_instrument_is_read_with_the_residue_floor_on_either_path pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-10-16 · **Closed:** 2026-10-16

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: A noisy overlay; nothing in the chart was changed.

**Evidence:**

- CLAUDE.md § The recording's attacks over the score ("Ataques da gravação"): "A separated instrument is read with a floor (ATTACK_STEM_FLOOR_DB = 40 ...)"
- CHANGELOG.en.md 0.10.0 beta 10 — New: "... On a separated instrument, the faint leftovers of the others ... no longer show as false attacks."
- commit e84a40c132 Recording attacks: read a separated instrument with a 40 dB floor
- detected 2026-10-16: the attacks feature was added in 4a6a026 (2026-10-16), fixed in e84a40c the same day
- found_in_version pending: measured in development on synthesized songs

**History:**

- 2026-10-16 — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-10-16 — Fixed: commit e84a40c132
- 2026-10-16 — Verified: automated
- 2026-10-16 — Closed: released in 0.10.0-beta.10
