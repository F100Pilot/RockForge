<!-- Generated from tracking/bugs.json by `python -m tools.tracking render`. Do not edit by hand: edit the JSON and render again. -->

# Bugs: import

Creating a project: Guitar Pro, Songsterr, PDF, recording, wizard. Index: [BUG_LOG.md](../BUG_LOG.md).

## BUG-0008

**Minimum lead-in warning shown on every GP build**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | pending (not recorded) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | e37e999b021e0cbaa380e3e422dafa117deb2219 |
| Severity | Low |
| Priority | P4 |
| Status | Fixed |

The 'first note placed at Xs' warning fired on every GP build even when the offset already met the minimum.

**Steps to reproduce:** _pending_

**Expected:** Warning only when the pipeline adjusted the lead-in

**Observed:** Spurious warning on every build

**Root cause:** Warning emitted unconditionally.

**Fixes:** [FIX-0008](../FIX_LOG.md#fix-0008) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-06-13 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Cosmetic noise in warnings.

**Evidence:**

- commit f929c106a5 Only warn about the minimum lead-in when it actually changed something
- found_in_version: fix f929c106a5 (2026-06-13) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent e37e999b02, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-06-13 — Fixed: commit f929c106a5

## BUG-0031

**Tied notes emitted as extra attacks ('4 notes show as 5')**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | cb68cd3e7e76125d96eb5c00124bee0316971dde |
| Severity | High |
| Priority | P2 |
| Status | Closed |

A tied note (drawn '(17)' in Guitar Pro) is a held continuation, but both parsers emitted it as a new attack, so a 4-note passage rendered as 5 notes and the rhythm looked wrong/desynced.

**Steps to reproduce:** 

1. Import a GP file with tied notes
2. Look at the chart

**Expected:** The tie extends the previous note's sustain.

**Observed:** An extra note appeared at each tie (337 vs 312 notes on the user's file).

**Root cause:** GP5 NoteType.tie and GPIF <Tie destination="true"> were not handled.

**Fixes:** [FIX-0031](../FIX_LOG.md#fix-0031) (0.10.0-beta.1)

**Verified:** regression test(s) test_tied_note_extends_previous_not_new_attack, test_gp7_tied_note_extends_not_duplicates pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-06-29 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Wrong notes and rhythm throughout tied passages, no workaround.

**Evidence:**

- CLAUDE.md § The generation path (Tied notes)
- commit a3d7de25c6 Fix tied notes emitted as extra attacks (the "4 notes show as 5" bug)
- found_in_version: the fix commit is an ancestor of cb00653 (the first public release, 0.10.0 beta 1, 2026-10-14), so the faulty code only existed in development builds before 0.10.0-beta.1
- found_in_build: cb68cd3e7e is the parent of the first fix commit a3d7de25c6 and still carries the code the fix changes

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-06-29 — Fixed: commit a3d7de25c6
- 2026-06-29 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0033

**.gp (GP7/8) uploads rejected at the API although the parser supported them**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | pending (not recorded) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | aa3435e2c128e85a128549dd783973e5325b82df |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

/gp/inspect still rejected .gp by extension and the file picker filtered it out, so .gp uploads failed with the old 'GPX/GP7 is not supported' message.

**Steps to reproduce:** _pending_

**Expected:** .gp accepted

**Observed:** 'GPX/GP7 is not supported'

**Root cause:** Extension gate not updated after the GPIF parser landed.

**Fixes:** [FIX-0033](../FIX_LOG.md#fix-0033) (0.10.0-beta.1)

**Verified:** regression test(s) test_gp_inspect_accepts_gp7 pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-06-29 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: GP7/8 files unusable; workaround: export GP5.

**Evidence:**

- commit 1e24332510 Accept .gp (GP7/GP8) at the API + UI upload boundary
- found_in_version: fix 1e24332510 (2026-06-29) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent aa3435e2c1, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-06-29 — Fixed: commit 1e24332510
- 2026-06-29 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0034

**GP7 parser missed note-level vibrato**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | a3d7de25c6db0a9b1230230bec9fe885ac7dfa86 |
| Severity | Low |
| Priority | P4 |
| Status | Fixed |

Vibrato is a direct child of <Note> in GPIF, not a Property, so it was missed (27 vibrato notes in the test file).

**Steps to reproduce:** _pending_

**Expected:** Vibrato charted

**Observed:** Vibrato absent

**Root cause:** Looked only in Properties.

**Fixes:** [FIX-0034](../FIX_LOG.md#fix-0034) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-06-29 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Technique label only.

**Evidence:**

- commit 77ab383762 GP7 parser: detect note-level Vibrato
- found_in_version: fix 77ab383762 (2026-06-29) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent a3d7de25c6, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-06-29 — Fixed: commit 77ab383762

## BUG-0038

**YouTube ingest hung (whole playlist download, yt-dlp ffmpeg inherited stdin)**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 5d5d57e75598a259b8dbfd8f607c530c6e42eb6d |
| Severity | Medium |
| Priority | P3 |
| Status | Fixed |

A watch?v=…&list=… URL made yt-dlp download the whole playlist, and its ffmpeg child could inherit the worker's stdin and hang; jobs sat at ingest. (Removed path.)

**Steps to reproduce:** _pending_

**Expected:** One video downloaded or a clear error

**Observed:** Job stuck at ingest

**Root cause:** No --no-playlist, inherited stdin, no timeout.

**Fixes:** [FIX-0038](../FIX_LOG.md#fix-0038) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-07-02 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Removed feature; workaround: upload audio.

**Evidence:**

- commit d96ecc33aa Fix YouTube ingest hanging: run yt-dlp isolated (no-playlist, DEVNULL, timeout)
- found_in_version: fix d96ecc33aa (2026-07-02) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 5d5d57e755, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-02 — Fixed: commit d96ecc33aa

## BUG-0039

**Basic Pitch transcription failed: TF SavedModel 'nmp' would not load**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | d96ecc33aa889875f5b1ea8797e7c12f8ebc99bc |
| Severity | Medium |
| Priority | P3 |
| Status | Fixed |

Transcription failed with 'nmp cannot be loaded into TensorFlow' because basic-pitch defaulted to its TF SavedModel. (Removed audio path.)

**Steps to reproduce:** _pending_

**Expected:** Transcription runs

**Observed:** Transcription error

**Root cause:** TF SavedModel incompatible with the installed TF.

**Fixes:** [FIX-0039](../FIX_LOG.md#fix-0039) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-07-02 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Audio path unusable.

**Evidence:**

- commit 0d97472882 Basic Pitch: prefer the bundled ONNX model over the TF SavedModel
- found_in_version: fix 0d97472882 (2026-07-02) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent d96ecc33aa, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-02 — Fixed: commit 0d97472882

## BUG-0041

**Basic Pitch failed after WhisperX availability check imported speechbrain**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 0d7882dde9ecafa8f7e80b12d1cea340d0fc4fb7 |
| Severity | Medium |
| Priority | P3 |
| Status | Fixed |

available() imported whisperx in the worker; speechbrain's lazy integration loader then failed inside Basic Pitch ('Lazy import of speechbrain.integrations.k2_fsa failed').

**Steps to reproduce:** _pending_

**Expected:** Transcription runs

**Observed:** Transcription crash

**Root cause:** Heavy import as an availability check.

**Fixes:** [FIX-0041](../FIX_LOG.md#fix-0041) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-07-02 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Audio path unusable with [lyrics] installed.

**Evidence:**

- commit 6282ed5c7c Fix Basic Pitch failing after whisperx import + harden worker shutdown
- found_in_version: fix 6282ed5c7c (2026-07-02) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 0d7882dde9, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-02 — Fixed: commit 6282ed5c7c

## BUG-0049

**GP5 tempo change authored on another track was ignored (grid stuck at the first tempo)**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 770d51a9b2989aa2f29da7c15c5cc20abc669289 |
| Severity | High |
| Priority | P2 |
| Status | Closed |

A GP5 tempo change is global but stored as a mixTableChange on one track's beat; _tempo_events scanned only the parsed track, so a song going 93→186 BPM at bar 64 stayed at 93.

**Steps to reproduce:** _pending_

**Expected:** Grid follows the tempo change

**Observed:** Beat grid at 93 BPM throughout

**Root cause:** Tempo events read from the charted track only.

**Fixes:** [FIX-0049](../FIX_LOG.md#fix-0049) (0.10.0-beta.1)

**Verified:** regression test(s) test_tempo_change_on_other_track_is_detected pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-07-04 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Whole chart desynced after the change.

**Evidence:**

- commit 6f4814fbb6 Detetar mudança de tempo GP5 authored noutra pista (grelha ficava presa)
- found_in_version: fix 6f4814fbb6 (2026-07-04) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 770d51a9b2, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-04 — Fixed: commit 6f4814fbb6
- 2026-07-04 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0069

**Sustains ran into the next note on the same string**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer (in game) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | debd8856c9ffe40ccf39dd8a74e05747009ffce6 |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

A Guitar Pro note's duration fills its whole beat, so each sustain trail touched the following attack on the highway.

**Steps to reproduce:** _pending_

**Expected:** A small gap before the next note on the same string.

**Observed:** Sustain trails ran right into the next note.

**Root cause:** The parsers used the notated duration as sustain without any gap.

**Fixes:** [FIX-0069](../FIX_LOG.md#fix-0069) (0.10.0-beta.1)

**Verified:** regression test(s) test_sustain_gap_trims_before_next_note_on_same_string, test_sustain_gap_ignores_other_strings_and_slides, test_sustain_gap_keeps_short_staccato_notes pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-07-08 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Visual fidelity on the highway; playable.

**Evidence:**

- CLAUDE.md § Manual drift correction (A local stretch re-inflates sustain)
- commit ef36b61 message: 'Two chart-fidelity fixes from in-game comparison'
- commit ef36b61778 GP: slide-out notes render, and trim sustains to leave a gap
- found_in_version: the fix commit is an ancestor of cb00653 (the first public release, 0.10.0 beta 1, 2026-10-14), so the faulty code only existed in development builds before 0.10.0-beta.1
- found_in_build: debd8856c9 is the parent of the first fix commit ef36b61778 and still carries the code the fix changes

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-08 — Fixed: commit ef36b61778
- 2026-07-08 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0089

**GP7 pinch harmonics read as none (HType compared case-sensitively)**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 049b02e5b40418f72d099e21767f61f4ee4fa4db |
| Severity | Low |
| Priority | P4 |
| Status | Fixed |

GPIF writes <HType>pinch</HType> lower-case; the comparison used capitalised strings.

**Steps to reproduce:** _pending_

**Expected:** Pinch harmonics charted

**Observed:** 0 pinch harmonics

**Root cause:** Case-sensitive comparison.

**Fixes:** [FIX-0089](../FIX_LOG.md#fix-0089) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-07-09 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Lost technique.

**Evidence:**

- commit 1a8a02e976 Fix GPIF pinch-harmonic detection (HType is lower-case)
- found_in_version: fix 1a8a02e976 (2026-07-09) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 049b02e5b4, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-09 — Fixed: commit 1a8a02e976

## BUG-0090

**GP7 slide-out lost when combined with a slide-in flag**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 1a8a02e976d14f40ba175f872eeb3940dc23ebac |
| Severity | Low |
| Priority | P4 |
| Status | Fixed |

Out-down/out-up was checked only inside the pitched-slide branch, so a flag-20 note lost its slide-out.

**Steps to reproduce:** _pending_

**Expected:** Both slides kept

**Observed:** Slide-out missing

**Root cause:** Branch structure.

**Fixes:** [FIX-0090](../FIX_LOG.md#fix-0090) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-07-09 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Lost technique.

**Evidence:**

- commit 99d434f8be Implement slide-ins (scoops into a note)
- found_in_version: fix 99d434f8be (2026-07-09) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 1a8a02e976, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-09 — Fixed: commit 99d434f8be

## BUG-0098

**Notes off the 24-fret neck dropped silently**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | pending (not recorded) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | ac0e2ab0e1f5a51fad65babfd201568940573d0b |
| Severity | Low |
| Priority | P4 |
| Status | Closed |

Both parsers skipped out-of-range notes without a word, so the chart had fewer notes than the GP with no explanation.

**Steps to reproduce:** _pending_

**Expected:** A warning with the count

**Observed:** Missing notes, no warning

**Root cause:** Silent skip.

**Fixes:** [FIX-0098](../FIX_LOG.md#fix-0098) (0.10.0-beta.1)

**Verified:** regression test(s) test_gp7_out_of_range_note_dropped_with_warning pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-07-10 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Honesty/visibility.

**Evidence:**

- commit 2f28121a31 GP parsers: warn on notes dropped for being off the 24-fret neck
- found_in_version: fix 2f28121a31 (2026-07-10) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent ac0e2ab0e1, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-10 — Fixed: commit 2f28121a31
- 2026-07-10 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0117

**Audio-ML job crashed on out-of-order librosa beat times**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | ddcb6cf00153074ee31ddc48c1428a63de0e6b7c |
| Severity | Medium |
| Priority | P3 |
| Status | Fixed |

librosa returned beat times out of order on a real recording, crashing with 'beats must be in chronological order'. (Removed path.)

**Steps to reproduce:** _pending_

**Expected:** Job completes

**Observed:** Job failed at beat_track

**Root cause:** Detector output trusted as ordered.

**Fixes:** [FIX-0117](../FIX_LOG.md#fix-0117) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-07-11 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Job failure.

**Evidence:**

- commit dda9fafc41 Fix audio-ML jobs crashing on out-of-order librosa beat times
- found_in_version: fix dda9fafc41 (2026-07-11) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent ddcb6cf001, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-11 — Fixed: commit dda9fafc41

## BUG-0118

**Transcription flooded the chart and warnings with unplayable ghost notes**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 43508ecc1cf7a211611da61d6222e2bc35a32eed |
| Severity | Low |
| Priority | P4 |
| Status | Fixed |

Basic Pitch emitted sub-range, octave and fragment ghosts on a distorted mix, producing 200+ identical 'dropped unplayable note' warnings. (Removed path.)

**Steps to reproduce:** _pending_

**Expected:** Aggregated warnings, cleaner chart

**Observed:** Hundreds of warnings

**Root cause:** No pruning before fret mapping.

**Fixes:** [FIX-0118](../FIX_LOG.md#fix-0118) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-07-12 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Removed feature.

**Evidence:**

- commit 091855e356 Prune spurious transcription notes before fret mapping
- found_in_version: fix 091855e356 (2026-07-12) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 43508ecc1c, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-12 — Fixed: commit 091855e356

## BUG-0119

**Down-tuned songs read as standard; real low notes pruned**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 51a8f887a7bd4bffc4767d9fb6149bfea1a3494e |
| Severity | Low |
| Priority | P4 |
| Status | Fixed |

The tuning heuristic recognised only Drop D, so e.g. Drop C# was read as standard and clean_transcription pruned real low notes. (Removed path.)

**Steps to reproduce:** _pending_

**Expected:** Plausible tuning

**Observed:** Missing low notes

**Root cause:** Narrow heuristic.

**Fixes:** [FIX-0119](../FIX_LOG.md#fix-0119) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-07-12 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Removed feature.

**Evidence:**

- commit 4e9296a0c5 Infer the most viable tuning from transcribed pitches
- found_in_version: fix 4e9296a0c5 (2026-07-12) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 51a8f887a7, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-12 — Fixed: commit 4e9296a0c5

## BUG-0123

**GP5 notes after a dropped out-of-range note came one beat late**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 71238818efa88c126ba98c95cf1ef4bda9b1f67d |
| Severity | High |
| Priority | P2 |
| Status | Closed |

A beat dropping an out-of-range note advanced tick twice, pushing every later note in the measure one beat late.

**Steps to reproduce:** _pending_

**Expected:** Timing unaffected

**Observed:** Notes late in that measure

**Root cause:** Double tick advance in the drop branch.

**Fixes:** [FIX-0123](../FIX_LOG.md#fix-0123) (0.10.0-beta.1)

**Verified:** regression test(s) test_dropped_out_of_range_note_does_not_desync_subsequent_timing pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-07-13 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Silent timing corruption.

**Evidence:**

- commit 58b629466d fix: two critical corruption bugs found in a full-codebase audit
- found_in_version: fix 58b629466d (2026-07-13) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 71238818ef, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-13 — Fixed: commit 58b629466d
- 2026-07-13 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0147

**GP7/8 tempo: reference note value ignored (half-note tempo read at half speed)**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 0de5d4f7a23b9301390bbc55138985746fd15cc5 |
| Severity | High |
| Priority | P2 |
| Status | Closed |

GPIF tempo <Value> is '<number> <reference>'; the reference multiplier was dropped, so a half-note reference read 60 BPM instead of 120.

**Steps to reproduce:** _pending_

**Expected:** Correct tempo

**Observed:** Whole timeline at half tempo

**Root cause:** Second token ignored.

**Fixes:** [FIX-0147](../FIX_LOG.md#fix-0147) (0.10.0-beta.1)

**Verified:** regression test(s) test_gpif_tempo_reference_multiplier_is_applied pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-08-22 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Timeline corrupted for such files.

**Evidence:**

- commit 0cf69e4593 Fix two GP7/GP8 tempo-map read bugs that corrupt the whole timeline
- found_in_version: fix 0cf69e4593 (2026-08-22) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 0de5d4f7a2, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-08-22 — Fixed: commit 0cf69e4593
- 2026-08-22 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0148

**GP7/8 mid-bar tempo changes placed at the wrong tick**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 0de5d4f7a23b9301390bbc55138985746fd15cc5 |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

<Position> is a fraction of the bar's duration, but was read as quarter notes, so a mid-bar change landed early (1.5 quarters in 4/4).

**Steps to reproduce:** _pending_

**Expected:** Change at its position

**Observed:** Tempo change early

**Root cause:** Position misread.

**Fixes:** [FIX-0148](../FIX_LOG.md#fix-0148) (0.10.0-beta.1)

**Verified:** regression test(s) test_gpif_tempo_position_is_a_fraction_of_the_bar pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-08-22 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Timing drift after mid-bar changes.

**Evidence:**

- commit 0cf69e4593 Fix two GP7/GP8 tempo-map read bugs that corrupt the whole timeline
- found_in_version: fix 0cf69e4593 (2026-08-22) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 0de5d4f7a2, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-08-22 — Fixed: commit 0cf69e4593
- 2026-08-22 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0171

**Every mid-song GP5 tempo change applied one quarter note late**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | f845b9bec9d939d623633b01ca7f1fa865f7a36a |
| Severity | High |
| Priority | P2 |
| Status | Closed |

_tempo_events keyed changes at absolute measure.start while notes use tick − 960, so each change took effect a beat late and errors accumulated (bar 4 at 7.5 s instead of 8.0 s).

**Steps to reproduce:** _pending_

**Expected:** Change on its beat

**Observed:** Drift after each tempo change

**Root cause:** Mixed tick scales.

**Fixes:** [FIX-0171](../FIX_LOG.md#fix-0171) (0.10.0-beta.1)

**Verified:** regression test(s) test_a_mid_song_tempo_change_takes_effect_on_its_own_beat pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-08-25 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Timeline corrupted for multi-tempo songs.

**Evidence:**

- commit 8703d36e22 Fix every mid-song tempo change being applied one quarter note late
- found_in_version: fix 8703d36e22 (2026-08-25) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent f845b9bec9, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-08-25 — Fixed: commit 8703d36e22
- 2026-08-25 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0173

**Guitar Pro 8 SyncPoints ignored, so a chart synced in Guitar Pro drifted**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 99a969d3591a1648f913fa9bc1d6e89120a01aba |
| Severity | High |
| Priority | P2 |
| Status | Closed |

A .gp file synced to its recording in Guitar Pro 8 played at its single header BPM in RockForge: the parser read only Type=Tempo automations and never the SyncPoint automations that hold GP8's audio alignment, so the chart drifted against the recording.

**Steps to reproduce:** 

1. Sync a score to its audio in Guitar Pro 8 (SyncPoints) and save the .gp
2. Create a project from it with that recording
3. Play the chart against the recording

**Expected:** The chart follows the varying tempo Guitar Pro derives from the sync points.

**Observed:** The chart played at the one header tempo and drifted away from the recording.

**Root cause:** gpif_parser read only MasterTrack automations of Type=Tempo; GP8 keeps the alignment in Automation[Type=SyncPoint] (BarIndex/BarOccurrence/FrameOffset minus FramePadding) and never changes the authored <Tempo>.

**Fixes:** [FIX-0173](../FIX_LOG.md#fix-0173) (0.10.0-beta.1)

**Verified:** regression test(s) test_gp8_sync_points_retime_the_chart_to_the_synced_audio, test_gp8_sync_points_respect_the_backing_track_padding, test_gp8_synced_average_bpm_is_what_plays_not_the_header, test_a_file_without_sync_points_is_timed_exactly_as_before, test_gp_inspect_reports_where_a_gp8_synced_file_starts pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-09-25 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: A chart synced perfectly in Guitar Pro lost its sync; only manual re-syncing in RockForge worked around it.

**Evidence:**

- CLAUDE.md § The generation path (Guitar Pro 8 audio sync (`SyncPoint` automations) drives the timing)
- CLAUDE.md: 'Reading only `Type=Tempo` locked such a file to its header tempo, so a chart the user had synced perfectly in Guitar Pro drifted in RockForge.'
- commit 0a217a93a2 Read Guitar Pro 8 audio-sync points so a GP-synced chart keeps its tempo
- found_in_version: the fix commit is an ancestor of cb00653 (the first public release, 0.10.0 beta 1, 2026-10-14), so the faulty code only existed in development builds before 0.10.0-beta.1
- found_in_build: 99a969d359 is the parent of the first fix commit 0a217a93a2 and still carries the code the fix changes

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-09-25 — Fixed: commit 0a217a93a2
- 2026-09-25 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0176

**GP8 chart came out one bar late with the untrimmed recording**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 0a217a93a27e08631068a6a51c2e6985ee62573b |
| Severity | High |
| Priority | P2 |
| Status | Closed |

The user's .gp (guitar-pro-youtube-sync) embeds audio trimmed to bar 1; its sync points describe that copy, but the user uploaded the untrimmed download, so the chart was one bar late.

**Steps to reproduce:** _pending_

**Expected:** Chart on the file's own audio

**Observed:** Constant one-bar offset

**Root cause:** Embedded recording ignored.

**Fixes:** [FIX-0176](../FIX_LOG.md#fix-0176) (0.10.0-beta.1)

**Verified:** regression test(s) test_the_audio_embedded_in_a_gp8_file_is_found_and_extracted, test_a_gp8_job_can_use_the_audio_embedded_in_the_file pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-09-25 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Sync wrong by a bar.

**Evidence:**

- CLAUDE.md § The generation path (The recording INSIDE the .gp is the one to use)
- commit 0c4d431133 Use the recording embedded in a GP8 file instead of asking for an upload
- found_in_version: fix 0c4d431133 (2026-09-25) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 0a217a93a2, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-09-25 — Fixed: commit 0c4d431133
- 2026-09-25 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0183

**YouTube audio download failed: yt-dlp lacked the JavaScript challenge solver and runtime**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 21e11a6bed0cd8ec4abb982ce4c9d732f2d4804c |
| Severity | High |
| Priority | P2 |
| Status | Closed |

The first real YouTube download failed where the reference tool succeeded: RockForge installed bare yt-dlp with no challenge solver (yt-dlp-ejs) and no JS runtime, YouTube refused in a way that read like 'log in', and --no-warnings hid the line saying so, so the UI pointed to a browser session (whose Chrome cookies are unreadable on Windows).

**Steps to reproduce:** 

1. Import a Songsterr link and download the chosen video's audio in step 3

**Expected:** The video's audio downloads.

**Observed:** The download was refused and the UI asked for a browser session.

**Root cause:** [youtube] was 'yt-dlp>=2024.1' without [default] (no yt-dlp-ejs) and no JavaScript runtime was enabled; --no-warnings hid the cause.

**Fixes:** [FIX-0183](../FIX_LOG.md#fix-0183) (0.10.0-beta.1)

**Verified:** CLAUDE.md: 'Confirmed working by the user (2026-09-27) on their Windows machine after pip install -U "yt-dlp[default]" + winget install DenoLand.Deno' (by the maintainer)

**Resolved:** 2026-09-27 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Audio download unusable; workaround was converting the video by hand.

**Evidence:**

- CLAUDE.md § The generation path (YouTube's JavaScript challenge: yt-dlp needs a solver AND a runtime)
- CLAUDE.md: 'The user's first real download failed where the reference tool, on the same machine and video, succeeded.'
- commit 3a74220e28 Give yt-dlp the JavaScript runtime and solver YouTube now requires
- found_in_version: the fix commit is an ancestor of cb00653 (the first public release, 0.10.0 beta 1, 2026-10-14), so the faulty code only existed in development builds before 0.10.0-beta.1
- found_in_build: 21e11a6bed is the parent of the first fix commit 3a74220e28 and still carries the code the fix changes

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-09-27 — Fixed: commit 3a74220e28
- 2026-09-27 — Verified: confirmed by user
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0186

**Songsterr import failed with CERTIFICATE_VERIFY_FAILED: certificate has expired**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 8494dccb32d4e6939a57939eac2d62f785e95fc9 |
| Severity | High |
| Priority | P2 |
| Status | Closed |

Importing from Songsterr failed on the user's Windows machine with 'certificate has expired' while the album lookup worked: Python trusts only roots the OS store already holds, and Windows installs roots lazily.

**Steps to reproduce:** 

1. Import a Songsterr link on the affected Windows machine

**Expected:** The import connects.

**Observed:** CERTIFICATE_VERIFY_FAILED: certificate has expired.

**Root cause:** The system store lacked a current root but still carried an expired cross-signed path.

**Fixes:** [FIX-0186](../FIX_LOG.md#fix-0186) (0.10.0-beta.1)

**Verified:** TESTING.md: 'Status (2026-09-27): confirmed by the user on a real Windows machine' (the Songsterr link → times → audio flow; commit 765d904) (by the maintainer)

**Resolved:** 2026-09-27 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: The Songsterr import did not work on that machine.

**Evidence:**

- CLAUDE.md § Outbound HTTPS trusts the system roots PLUS certifi's (`infrastructure/_https.py`)
- commit 04f858b380 Trust certifi's roots alongside the system's for outbound HTTPS
- found_in_version: the fix commit 04f858b380 is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent 8494dccb32

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-09-27 — Fixed: commit 04f858b380
- 2026-09-27 — Verified: confirmed by user
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0187

**Songsterr refusals said only '403', hiding 'this tab is unpublished'**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 5be2c3941827ee44bfd976c60b2cc0794790fc82 |
| Severity | Low |
| Priority | P4 |
| Status | Closed |

Songsterr answered 403 with JSON ERR_UNPUBLISHED ('Only authors can view their own unpublished tabs'), but RockForge said only 'o Songsterr respondeu 403' and then a guessed 'may be blocking automated requests', sending the diagnosis the wrong way twice.

**Steps to reproduce:** 

1. Import the unpublished Songsterr tab 6019365

**Expected:** A message saying the tab is unpublished.

**Observed:** A bare 403 / a guessed bot-blocking message.

**Root cause:** _refusal ignored the JSON reason Songsterr sends with a refusal.

**Fixes:** [FIX-0187](../FIX_LOG.md#fix-0187) (0.10.0-beta.1)

**Verified:** regression test(s) test_a_refusal_or_an_unreadable_answer_is_a_clear_error pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-09-27 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: A misleading error message; the import could not succeed for that tab anyway.

**Evidence:**

- CLAUDE.md § Outbound HTTPS ... — '**A refusal says Songsterr's OWN reason (`_refusal`).**'
- commit 5be2c39 had switched to the requests client on the guess of bot protection
- commit 21e11a6bed Show Songsterr's own reason when it refuses a tab
- found_in_version: the fix commit 21e11a6bed is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent 5be2c39418

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-09-27 — Fixed: commit 21e11a6bed
- 2026-09-27 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0188

**Songsterr import aborted entirely on text GP5 cannot store (e.g. a Cyrillic title)**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | pending (not recorded) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 65527dd20cec9e4f9742eac458e76a7daf4c6af1 |
| Severity | High |
| Priority | P2 |
| Status | Closed |

Writing the Songsterr tab as GP5 (cp1252 text) raised on characters it cannot encode, so a tab with, e.g., a Cyrillic title failed the whole import.

**Steps to reproduce:** 

1. Import a Songsterr tab whose title or text has characters outside cp1252

**Expected:** The import succeeds with unrepresentable characters replaced.

**Observed:** The whole GP5 write aborted.

**Root cause:** songsterr_gp wrote strings straight into GP5, whose text is cp1252.

**Fixes:** [FIX-0188](../FIX_LOG.md#fix-0188) (0.10.0-beta.1)

**Verified:** regression test(s) test_text_gp5_cannot_store_does_not_abort_the_import pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-09-28 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: The import was unavailable for such tabs, with no workaround inside RockForge.

**Evidence:**

- CLAUDE.md § The generation path (Or no Guitar Pro file at all: the tab imported from Songsterr)
- CLAUDE.md: 'a Cyrillic title used to abort the whole write'
- commit deb168f158 Lyrics from the score: Songsterr tabs bring theirs, and syllables follow the vocal line
- found_in_version: the fix commit is an ancestor of cb00653 (the first public release, 0.10.0 beta 1, 2026-10-14), so the faulty code only existed in development builds before 0.10.0-beta.1
- found_in_build: 65527dd20c is the parent of the first fix commit deb168f158 and still carries the code the fix changes

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-09-28 — Fixed: commit deb168f158
- 2026-09-28 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0192

**Audio embedded in a GP8 file not detected (disabled track, other extensions, member name)**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 4ed26393c4f92fc652a035d9c08e2bc2cd4ae96b |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

The embedded-audio check wanted an enabled audio track, one of six extensions and the exact member name, so a GP8 file that carried its recording was reported as having none.

**Steps to reproduce:** 

1. Load a GP8 file whose backing track is switched off, or whose asset is .opus or named with different case/leading slash
2. Reach step 3 of the wizard

**Expected:** The audio inside the file is found and offered.

**Observed:** The audio was not detected and an upload was required.

**Root cause:** backing_track required Enabled, a fixed extension list and an exact asset path.

**Fixes:** [FIX-0192](../FIX_LOG.md#fix-0192) (0.10.0-beta.1)

**Verified:** regression test(s) test_the_embedded_audio_is_found_despite_details_that_used_to_hide_it, test_audio_that_is_not_in_the_file_says_where_it_is, test_gp_inspect_says_where_the_audio_is_when_it_is_not_inside pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-09-29 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Workaround: upload the audio separately (but only the embedded copy matches the sync points).

**Evidence:**

- CLAUDE.md § The generation path (Detection is tolerant, and says where the audio is when it is not inside)
- user quote (undated): 'Carreguei um ficheiro gp com áudio mas não foi detetado'
- commit cf06d659e3 Find a GP8 file's audio however it is stored, and show which charts are in sync
- found_in_version: the fix commit is an ancestor of cb00653 (the first public release, 0.10.0 beta 1, 2026-10-14), so the faulty code only existed in development builds before 0.10.0-beta.1
- found_in_build: 4ed26393c4 is the parent of the first fix commit cf06d659e3 and still carries the code the fix changes

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-09-29 — Fixed: commit cf06d659e3
- 2026-09-29 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0196

**Songs whose last notes fall after the last beat refused to build**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | deb168f1587cfdf67f70455a219af1070e03deec |
| Severity | Critical |
| Priority | P1 |
| Status | Closed |

The parsers' beat grid ended on the last beat of the last bar, not its end, so a final note on the 'and' of 4 failed validation ('note at 187.797s beyond final ebeat 187.542s') and the whole build was refused.

**Steps to reproduce:** 

1. Import a GP file ending in eighths (the user's PDF→GP5 file)
2. Build

**Expected:** The song builds.

**Observed:** Build failed: note beyond final ebeat.

**Root cause:** Both parsers stopped the grid at the last counted beat; an overfull last bar was not covered either.

**Fixes:** [FIX-0196](../FIX_LOG.md#fix-0196) (0.10.0-beta.1)

**Verified:** regression test(s) test_a_song_ending_on_the_and_of_four_builds, test_gp7_grid_closes_the_last_bar_so_a_late_eighth_fits, test_an_overfull_last_bar_still_ends_inside_the_grid, test_the_closing_bar_line_ends_the_last_bar_instead_of_adding_one, test_the_closing_bar_line_is_not_listed_as_a_bar pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-09-29 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: The song could not be built at all.

**Evidence:**

- CLAUDE.md § Note editor (The grid closes the last bar (`close_beat_grid`))
- CLAUDE.md: '"note at 187.797s beyond final ebeat 187.542s"'
- commit 133ed79ff4 Close the last bar in the beat grid, so a song ending in eighths builds
- found_in_version: the fix commit is an ancestor of cb00653 (the first public release, 0.10.0 beta 1, 2026-10-14), so the faulty code only existed in development builds before 0.10.0-beta.1
- found_in_build: deb168f158 is the parent of the first fix commit 133ed79ff4 and still carries the code the fix changes

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-09-29 — Fixed: commit 133ed79ff4
- 2026-09-29 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0201

**Bar 1 before the recording (negative GP start) clamped to 0, every note late**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 48b47e12bd8395209eb11a86314143b6420dcf51 |
| Severity | High |
| Priority | P2 |
| Status | Closed |

A .gp whose bar 1 comes before its recording starts (positive FramePadding, as alphaTab/PDF-to-GP5 save it) had sync_start_s clamped to 0, the wizard pre-filled 0 and offset_s refused negatives, so every note came about 2.1 s late on the user's song.

**Steps to reproduce:** 

1. Save a .gp from PDF-to-GP5's 'Descarregar .gp (com áudio)' whose bar 1 is before the audio
2. Create a project using that audio
3. Play the chart

**Expected:** The chart keeps the place the file's sync gives it (a negative start).

**Observed:** Every note was ~2.1 s late; the sync done in PDF-to-GP5 looked lost.

**Root cause:** sync_start_s clamped a negative bar-1 position to 0 and offset_s had a lower bound of 0.

**Fixes:** [FIX-0201](../FIX_LOG.md#fix-0201) (0.10.0-beta.1)

**Verified:** docs/TESTES-NO-JOGO.md Confirmado: 'Áudio dentro do .gp do PDF-to-GP5 (backing-track.mp3) detetado e usado, com o início antes da gravação (−2,15 s) a bater na página de sincronização' — Daughtry "September" (2026-09-30) (by the maintainer)

**Resolved:** 2026-09-30 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: The whole chart was out of sync by a constant; the start field could be nudged by hand only up to 0.

**Evidence:**

- CLAUDE.md § The generation path (Guitar Pro 8 audio sync)
- CLAUDE.md: 'clamping it to 0 had put every note that much late'
- commit 9fff993df4 A GP start before the recording (negative offset) keeps its sync
- found_in_version: the fix commit is an ancestor of cb00653 (the first public release, 0.10.0 beta 1, 2026-10-14), so the faulty code only existed in development builds before 0.10.0-beta.1
- found_in_build: 48b47e12bd is the parent of the first fix commit 9fff993df4 and still carries the code the fix changes

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-09-30 — Fixed: commit 9fff993df4
- 2026-09-30 — Verified: confirmed by user
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0203

**Three-point bends rose twice as fast as alphaTab/Guitar Pro play them**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 8cda047d1c6fcf2cb7a1eda90ae4532f8201fde4 |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

A three-point bend whose middle point is not a peak ('up by the middle of the note, then held', or a pre-bend released) was charted with its middle point, rising twice as fast as alphaTab plays it.

**Steps to reproduce:** _pending_

**Expected:** A non-peak middle point is ignored and the bend is a straight line from origin to destination, as alphaTab's Note.finish does.

**Observed:** The bend reached its peak by the middle of the note instead of across the whole note.

**Root cause:** Both parsers kept every bend point; alphaTab keeps the middle one only when it is a peak.

**Fixes:** [FIX-0203](../FIX_LOG.md#fix-0203) (0.10.0-beta.1)

**Verified:** regression test(s) test_alphatab_bend_reads_three_points_as_alphatab, test_gp7_bend_up_and_held_is_a_rise_across_the_note, test_a_plain_rise_is_the_single_point_at_the_note_end, test_is_plain_rise pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-09-30 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Wrong bend shape on some notes; the song still plays.

**Evidence:**

- CLAUDE.md § The generation path (Three-point bends are read as alphaTab plays them)
- commit ae9dab0a86 GP import: three-point bends read as alphaTab plays them
- found_in_version: the fix commit is an ancestor of cb00653 (the first public release, 0.10.0 beta 1, 2026-10-14), so the faulty code only existed in development builds before 0.10.0-beta.1
- found_in_build: 8cda047d1c is the parent of the first fix commit ae9dab0a86 and still carries the code the fix changes

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-09-30 — Fixed: commit ae9dab0a86
- 2026-09-30 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0204

**A flat pre-bend was charted as a rise across the note instead of bent from the attack**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | ae9dab0a86a2f5ca81f2a39bdec02216b89f85a2 |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

A pre-bend held at one value was written to the chart as the single point at the note's end (a rise across the note), while alphaTab plays it already bent at the attack.

**Steps to reproduce:** _pending_

**Expected:** The note is bent from the attack to its end.

**Observed:** The note rose across its length.

**Root cause:** is_composite_bend was false for a curve bent at the attack, so it was simplified to a plain rise.

**Fixes:** [FIX-0204](../FIX_LOG.md#fix-0204) (0.10.0-beta.1)

**Verified:** regression test(s) test_a_pre_bend_is_bent_from_the_attack, test_a_pre_bend_is_bent_at_the_attack_in_sng_and_xml, test_is_composite_bend_for_varying_strength_or_a_pre_bend pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-09-30 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Wrong bend shape on pre-bent notes; the song still plays.

**Evidence:**

- CLAUDE.md § The generation path (Three-point bends are read as alphaTab plays them)
- commit 513d65334d GP import: a flat pre-bend is bent from the attack, as alphaTab plays it
- found_in_version: the fix commit is an ancestor of cb00653 (the first public release, 0.10.0 beta 1, 2026-10-14), so the faulty code only existed in development builds before 0.10.0-beta.1
- found_in_build: ae9dab0a86 is the parent of the first fix commit 513d65334d and still carries the code the fix changes

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-09-30 — Fixed: commit 513d65334d
- 2026-09-30 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0205

**GP8 embedded audio with no file extension not recognised and offered as an external file**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | e814045b31b66bd6acf795e6df849cdb2c408553 |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

The user's file stores its audio as 'Content/Assets/backing-track' with no extension; the name check skipped it and then offered that in-file path as a file outside the .gp to go and upload.

**Steps to reproduce:** 

1. Load a GP8 file whose embedded audio member has no extension
2. Reach step 3 of the wizard

**Expected:** The embedded MP3 is recognised and used.

**Observed:** Not detected; step 3 asked to upload 'Content/Assets/backing-track' as an external file.

**Root cause:** Only known audio extensions were accepted, and a Content/ path could be reported as external_path.

**Fixes:** [FIX-0205](../FIX_LOG.md#fix-0205) (0.10.0-beta.1)

**Verified:** docs/TESTES-NO-JOGO.md Confirmado: 'Áudio dentro do .gp do PDF-to-GP5 (backing-track.mp3) detetado e usado' — Daughtry "September" (2026-09-30) (by the maintainer)

**Resolved:** 2026-09-30 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Workaround: extract and upload the audio by hand.

**Evidence:**

- CLAUDE.md § The generation path (Detection is tolerant)
- user quote (undated): 'continua a não detetar que o GP file tem o mp3 incluído'
- commit eda2146fc3 Find a GP8 file's embedded recording even when it has no extension
- found_in_version: the fix commit is an ancestor of cb00653 (the first public release, 0.10.0 beta 1, 2026-10-14), so the faulty code only existed in development builds before 0.10.0-beta.1
- found_in_build: e814045b31 is the parent of the first fix commit eda2146fc3 and still carries the code the fix changes

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-09-30 — Fixed: commit eda2146fc3
- 2026-09-30 — Verified: confirmed by user
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0206

**Repeats, voltas and jumps played once, putting everything after them early**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | pending (not recorded) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | f8f1537ea36197b90484bb235930ce98801633a4 |
| Severity | High |
| Priority | P2 |
| Status | Closed |

Rocksmith has no repeats and the parsers did not unroll them: a score with |: :|, voltas or D.C./D.S. played each repeated section once, and everything after it came early against the recording.

**Steps to reproduce:** 

1. Import a GP file with a repeat, volta or D.S.
2. Play the chart against the recording

**Expected:** Bars are laid out as played.

**Observed:** Repeated sections played once; the rest of the song was early.

**Root cause:** Both parsers laid out the written bars, not the played order.

**Fixes:** [FIX-0206](../FIX_LOG.md#fix-0206) (0.10.0-beta.1)

**Verified:** regression test(s) test_playback_order_is_alphatabs, test_gp5_repeats_and_voltas_are_played, test_gp7_repeats_and_voltas_are_played, test_gp5_da_capo_al_fine, test_gp5_a_lyric_line_starts_again_on_every_pass, test_gp8_sync_point_on_a_second_pass_is_used, test_tempo_corrections_go_to_the_written_bar_of_a_played_bar pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-09-30 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: The chart desynced after the first repeat with no workaround but editing the GP file.

**Evidence:**

- CLAUDE.md § The generation path (Repeats, voltas and jumps are unrolled, in alphaTab's order)
- commit 48b47e12bd Unroll repeats, voltas and jumps in alphaTab's playback order
- found_in_version: the fix commit is an ancestor of cb00653 (the first public release, 0.10.0 beta 1, 2026-10-14), so the faulty code only existed in development builds before 0.10.0-beta.1
- found_in_build: f8f1537ea3 is the parent of the first fix commit 48b47e12bd and still carries the code the fix changes

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-09-30 — Fixed: commit 48b47e12bd
- 2026-09-30 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0222

**Tied notes lost their bend and hammer/pull-off when folded**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | eda2146fc3cf1c31f1469a766f2e975c18d4ff56 |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

A note held then bent and released on the tie lost its bend ('September' bar 4), and a pull-off from the tied note was lost.

**Steps to reproduce:** _pending_

**Expected:** Effects kept

**Observed:** Bend/pull-off missing

**Root cause:** Tie fold dropped the tie's effects.

**Fixes:** [FIX-0222](../FIX_LOG.md#fix-0222) (0.10.0-beta.1)

**Verified:** regression test(s) test_bend_and_pull_off_on_a_tied_note_are_kept, test_gp7_bend_on_a_tied_note_is_kept pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-09-30 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Lost techniques.

**Evidence:**

- commit 028d004457 Keep the bend and hammer/pull of a tied note when folding ties
- found_in_version: fix 028d004457 (2026-09-30) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent eda2146fc3, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-09-30 — Fixed: commit 028d004457
- 2026-09-30 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0223

**GP7 bend-and-release lost its hold at the top**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 028d0044572a8f66f320d7d37b96607317446ecb |
| Severity | Low |
| Priority | P4 |
| Status | Closed |

Only the first of GPIF's two middle offsets was used.

**Steps to reproduce:** _pending_

**Expected:** 0→½→½→0

**Observed:** 0→½→0

**Root cause:** Second middle point ignored.

**Fixes:** [FIX-0223](../FIX_LOG.md#fix-0223) (0.10.0-beta.1)

**Verified:** regression test(s) test_gp7_bend_release_keeps_both_middle_points pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-09-30 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Bend shape.

**Evidence:**

- commit 34b604fb4c Read both middle points of a GP7 bend, as alphaTab does
- found_in_version: fix 34b604fb4c (2026-09-30) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 028d004457, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-09-30 — Fixed: commit 34b604fb4c
- 2026-09-30 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0225

**GP7 grace notes counted as bar time, shifting every later note**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 4eae9ccb10e471631a1709ffd52e9c6eee14aa6a |
| Severity | High |
| Priority | P2 |
| Status | Closed |

In .gp files grace beats consumed bar time, shifting later notes and lyrics by the grace's length.

**Steps to reproduce:** _pending_

**Expected:** Graces take no bar time

**Observed:** Notes late after a grace

**Root cause:** Grace beats advanced the clock.

**Fixes:** [FIX-0225](../FIX_LOG.md#fix-0225) (0.10.0-beta.1)

**Verified:** regression test(s) test_gp7_grace_notes_take_no_time_of_the_bar, test_grace_notes_are_short_notes_of_their_own pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-09-30 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Timing corruption.

**Evidence:**

- commit f8f1537ea3 GP import: grace notes, brush strokes, pinch harmonics, tied vibrato
- found_in_version: fix f8f1537ea3 (2026-09-30) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 4eae9ccb10, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-09-30 — Fixed: commit f8f1537ea3
- 2026-09-30 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0226

**GP5 pinch and tapped harmonic types swapped**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 4eae9ccb10e471631a1709ffd52e9c6eee14aa6a |
| Severity | Low |
| Priority | P4 |
| Status | Closed |

The code checked types 2 and 3; pinch is 4 and tapped 3.

**Steps to reproduce:** _pending_

**Expected:** Correct kind

**Observed:** Wrong harmonic kind

**Root cause:** Wrong enum values.

**Fixes:** [FIX-0226](../FIX_LOG.md#fix-0226) (0.10.0-beta.1)

**Verified:** regression test(s) test_harmonic_types_map_like_the_gpif_path pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-09-30 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Technique label.

**Evidence:**

- commit f8f1537ea3 GP import: grace notes, brush strokes, pinch harmonics, tied vibrato
- found_in_version: fix f8f1537ea3 (2026-09-30) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 4eae9ccb10, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-09-30 — Fixed: commit f8f1537ea3
- 2026-09-30 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0227

**Vibrato on a tied note lost when the tie folded**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 4eae9ccb10e471631a1709ffd52e9c6eee14aa6a |
| Severity | Low |
| Priority | P4 |
| Status | Closed |

Vibrato written on the tied note was dropped with the tie.

**Steps to reproduce:** _pending_

**Expected:** Vibrato kept

**Observed:** Vibrato missing

**Root cause:** Tie fold dropped it.

**Fixes:** [FIX-0227](../FIX_LOG.md#fix-0227) (0.10.0-beta.1)

**Verified:** regression test(s) test_vibrato_on_a_tied_note_is_kept pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-09-30 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Technique.

**Evidence:**

- commit f8f1537ea3 GP import: grace notes, brush strokes, pinch harmonics, tied vibrato
- found_in_version: fix f8f1537ea3 (2026-09-30) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 4eae9ccb10, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-09-30 — Fixed: commit f8f1537ea3
- 2026-09-30 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0228

**GP7/8 let ring lost (<LetRing/> inside the note)**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 9fff993df420bea8832644fe58d8cfab6df79d6c |
| Severity | Low |
| Priority | P4 |
| Status | Closed |

GP8 and alphaTab write <LetRing/> as a child of <Note>; only the Property form was read (344 notes of one track).

**Steps to reproduce:** _pending_

**Expected:** Let ring charted

**Observed:** Let ring missing

**Root cause:** One form only.

**Fixes:** [FIX-0228](../FIX_LOG.md#fix-0228) (0.10.0-beta.1)

**Verified:** regression test(s) test_let_ring_as_a_child_of_the_note_is_read pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-09-30 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Technique.

**Evidence:**

- commit f5fa599f33 GP7/8 import: let ring written as <LetRing/> inside the note
- found_in_version: fix f5fa599f33 (2026-09-30) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 9fff993df4, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-09-30 — Fixed: commit f5fa599f33
- 2026-09-30 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0229

**Bend-and-release happened early after the sustain trim**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | f5fa599f336eb573f596565f6dc20b67cf78999f |
| Severity | Low |
| Priority | P4 |
| Status | Closed |

apply_sustain_gap shortened notes without re-timing their bend curves (fractions of the sustain).

**Steps to reproduce:** _pending_

**Expected:** Curve keeps its moments

**Observed:** Release ~8% early

**Root cause:** Curve not re-timed.

**Fixes:** [FIX-0229](../FIX_LOG.md#fix-0229) (0.10.0-beta.1)

**Verified:** regression test(s) test_the_bend_on_the_tie_is_bent_and_released_on_time pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-09-30 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Bend timing.

**Evidence:**

- commit 8cda047d1c Bend curves keep their timing to the chart; GP5 → XML → SNG test
- found_in_version: fix 8cda047d1c (2026-09-30) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent f5fa599f33, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-09-30 — Fixed: commit 8cda047d1c
- 2026-09-30 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0251

**GP8 embedded audio in .opus/.webm/.aac/.mp4/.wma was detected, then refused by the build**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | _pending_ |
| Build / commit | cb00653bedba4cd2f9070ceb2acb8e925c883319 |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

The GP8 embedded-audio detection accepted .opus/.webm/.aac/.mp4/.wma (a YouTube download embedded as-is) but the ingestor and upload check had a shorter list, so such a recording was found and then rejected by the build.

**Steps to reproduce:** 

1. Import a GP8 file whose embedded recording is .opus or .webm
2. Create the project using the embedded audio

**Expected:** The project builds with that recording.

**Observed:** The ingestor refused the file's format.

**Root cause:** Three separate audio-format lists (upload, GP8 detection, ingestor) that disagreed.

**Fixes:** [FIX-0251](../FIX_LOG.md#fix-0251) (0.10.0-beta.2)

**Verified:** regression test(s) test_every_recording_the_gp8_detection_finds_can_be_built pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-10-14 · **Closed:** 2026-10-15

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: The build failed for those formats; converting the audio was a workaround.

**Evidence:**

- CHANGELOG.en.md 0.10.0 beta 2 — Fixed: "A GP8 file's audio in .opus, .webm, .aac, .mp4 or .wma ..."
- commit 2d0b87ef91 Fix the bugs the audit found: "an embedded .opus/.webm was detected, then refused by the ingestor"
- found_in_version pending: faulty code present at cb00653 (beta 1); found by an audit, detection date not documented

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-10-14 — Fixed: commit 2d0b87ef91
- 2026-10-14 — Verified: automated
- 2026-10-15 — Closed: released in 0.10.0-beta.2

## BUG-0261

**PDF import put the next staff's H/P letters into the lyrics**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | pending (not recorded) |
| Found in | _pending_ |
| Build / commit | b3e8f295e62fe4942dbaf055a11338cdb28f6502 |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

The pinned PDF-to-GP5 converter read hammer-on/pull-off letters printed at the height of a staff's lyrics as lyric text ("P P In P your P life").

**Steps to reproduce:** 

1. Import a PDF tab with lyrics under a staff and H/P marks on the next staff (e.g. Tantric "Breakdown")

**Expected:** "In your life you seem to ..."

**Observed:** "P P In P your P life"

**Root cause:** A misread in the PDF-to-GP5 converter pinned by the [pdf] extra (fixed upstream in 12e1f8e).

**Fixes:** [FIX-0261](../FIX_LOG.md#fix-0261) (0.10.0-beta.2)

**Verified:** commit cfb542d28f: 'Checked with the user's Tantric "Breakdown" PDF: its lyrics now start "In your life you seem to"' (by the developer (manual check))

**Resolved:** 2026-10-14 · **Closed:** 2026-10-15

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Garbled lyrics on import, editable afterwards.

**Evidence:**

- commit cfb542d28f [pdf] extra: take PDF-to-GP5 12e1f8e (lyrics without H/P letters)
- found_in_build: b3e8f29 pins PDF-to-GP5 8d355d4, the version the fix replaces
- not in the changelog; found_in_version pending: detection date not documented

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-10-14 — Fixed: commit cfb542d28f
- 2026-10-14 — Verified: manual
- 2026-10-15 — Closed: released in 0.10.0-beta.2

## BUG-0269

**The Guitar Pro file's capo was ignored**

| | |
|---|---|
| Detected | 2026-10-15 |
| Reported by | user report (r/rocksmith) |
| Found in | _pending_ |
| Build / commit | 25a67fbe730581db2109dc0d2d0eb3f3f5b687ea |
| Severity | High |
| Priority | P2 |
| Status | Closed |

Guitar Pro counts frets from the capo (GP3-5 Track.offset, GPIF CapoFret) but RockForge read them as from the nut and carried no capo, so a capo song's frets were all wrong for Rocksmith.

**Steps to reproduce:** 

1. Import a GP file with a capo
2. Build and look at the frets

**Expected:** Frets counted from the nut, the arrangement carrying the capo.

**Observed:** The capo was ignored.

**Root cause:** Neither parser read the capo; Arrangement.capo stayed 0.

**Fixes:** [FIX-0269](../FIX_LOG.md#fix-0269) (0.10.0-beta.5)

**Verified:** regression test(s) test_a_gp5_capo_moves_the_fretted_notes_and_leaves_open_strings_open, test_a_note_pushed_past_the_neck_by_the_capo_is_counted_not_silently_kept, test_a_gp7_capo_is_read_from_the_staff, test_the_capo_reaches_the_xml_and_the_sng_and_open_strings_sound_at_it, test_the_gp5_export_writes_the_capo_back pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-10-15 · **Closed:** 2026-10-15

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Every capo song charted at the wrong frets.

**Evidence:**

- CLAUDE.md § The generation path: "A capo is read and the frets are counted from the nut ... ('It doesn't understand the capo', r/rocksmith 2026-10-15)"
- user quote (2026-10-15): 'It doesn't understand the capo'
- CHANGELOG.en.md 0.10.0 beta 5 — Fixed: "The Guitar Pro file's capo was ignored. ..."
- commit 13a2c42b65 Fix the first public reports: downloads in the .exe, the capo, a 30 MB .psarc
- found_in_version pending: faulty code present at 25a67fb (beta 2) and bebcf2b (beta 3); the version used is not stated

**History:**

- 2026-10-15 — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-10-15 — Fixed: commit 13a2c42b65
- 2026-10-15 — Verified: automated
- 2026-10-15 — Closed: released in 0.10.0-beta.5

## BUG-0278

**After a D.C./D.S. the 1st-time ending was played again before the 2nd**

| | |
|---|---|
| Detected | 2026-10-16 |
| Reported by | user report |
| Found in | 0.10.0-beta.6 |
| Build / commit | 8494322e3f34a7427e9ed710687f2001493e9bb4 |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

On the return after a jump repeats were not taken, but every volta was played (alphaTab's order), so a 1st-time bar sounded again before the 2nd-time one, against the usual convention (no repeats, last ending only).

**Steps to reproduce:** 

1. Import a GP file with a D.C./D.S. returning through 1st/2nd endings

**Expected:** Only the last ending on the return.

**Observed:** The 1st ending played again before the 2nd.

**Root cause:** playback.py followed alphaTab, which plays every volta after a jump.

**Fixes:** [FIX-0278](../FIX_LOG.md#fix-0278) (0.10.0-beta.7)

**Verified:** regression test(s) test_after_a_jump_no_repeats_and_only_the_last_ending, test_a_jump_that_returns_through_no_repeat_needs_no_convention, test_gp5_says_which_convention_it_assumed_after_a_jump, test_gp7_says_which_convention_it_assumed_after_a_jump pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-10-16 · **Closed:** 2026-10-16

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Wrong bar order for songs with jumps through voltas.

**Evidence:**

- CLAUDE.md § The generation path: "One departure from alphaTab, on the return after a D.C./D.S. ... (user feedback, 2026-10-16)"
- CHANGELOG.en.md 0.10.0 beta 7 — Fixed: "Voltas (1st/2nd time) on the return after a D.C./D.S. ..."
- commit b6fcb5d103 After a D.C./D.S., play only the last ending and say which convention was assumed
- found_in_version: beta 7 was published after this fix (its release notes were edited in b6fcb5d and 4b63d25 on 2026-10-16), so the newest published release at the report was beta 6 (8494322), which has the faulty code

**History:**

- 2026-10-16 — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-10-16 — Fixed: commit b6fcb5d103
- 2026-10-16 — Verified: automated
- 2026-10-16 — Closed: released in 0.10.0-beta.7

## BUG-0280

**PDF import: a grace number drawn over the next note's digits joined into other frets**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | pending (not recorded) |
| Found in | _pending_ |
| Build / commit | 2d4d4bb5f5a41da9672b7ba5c08853befbb9f217 |
| Severity | Medium |
| Priority | P3 |
| Status | Fixed |

The pinned PDF-to-GP5 converter joined a small grace number drawn over the next note's digits ("18" over the "1" of "16") into other frets instead of reading it apart.

**Steps to reproduce:** _pending_

**Expected:** The grace number read apart.

**Observed:** It joined into other frets.

**Root cause:** A misread in the PDF-to-GP5 converter pinned by the [pdf] extra (fixed upstream in ac9047a).

**Fixes:** [FIX-0280](../FIX_LOG.md#fix-0280) (0.10.0-beta.7)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-10-16 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Wrong frets in converted tabs, editable afterwards.

**Evidence:**

- commit d1ff572c55 [pdf] extra: take PDF-to-GP5 ac9047a (grace notes printed over their note)
- found_in_build: 2d4d4bb pins PDF-to-GP5 12e1f8e, the version the fix replaces
- not in the changelog; found_in_version pending: detection date not documented

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-10-16 — Fixed: commit d1ff572c55

## BUG-0281

**PDF import (OCR): small 9/6/3 grace notes were read as normal notes**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | pending (not recorded) |
| Found in | _pending_ |
| Build / commit | d1ff572c5558f58a9b747763d918c5ea19582467 |
| Severity | Medium |
| Priority | P3 |
| Status | Fixed |

In a picture, a small 9/6/3 grace note stands taller than a small 1/4, so the converter's OCR read it as a normal note.

**Steps to reproduce:** _pending_

**Expected:** A grace note.

**Observed:** A normal note.

**Root cause:** The converter's small-number height limit was too low (moved to 85 % upstream in df6d182).

**Fixes:** [FIX-0281](../FIX_LOG.md#fix-0281) (0.10.0-beta.7)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-10-16 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Wrong rhythm/notes in converted pictures, editable afterwards.

**Evidence:**

- commit 3914f55301 [pdf] extra: take PDF-to-GP5 df6d182 (OCR grace notes with round digits)
- found_in_build: d1ff572 pins PDF-to-GP5 ac9047a, the version the fix replaces
- not in the changelog; found_in_version pending: detection date not documented

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-10-16 — Fixed: commit 3914f5530f

## BUG-0307

**A wrong value in an imported project broke the home page**

| | |
|---|---|
| Detected | 2026-10-18 |
| Reported by | code review (Claude, on the maintainer's request) |
| Found in | 0.11.0-beta.2 |
| Build / commit | f64c45e8e176c44bd87c7c7866f741330b443011 |
| Severity | High |
| Priority | P2 |
| Status | Verified |

/import-sync and a .rfproj's project.json are raw JSON and only numbers were checked for finiteness; a string such as "offset_s": "abc" was stored and every GET /jobs answered 500 until that project was deleted.

**Steps to reproduce:** 

1. Import a .rfproj whose project.json has "offset_s": "1e"
2. Open the home page

**Expected:** The import is refused with the key named; the home page works.

**Observed:** 500 on the import and on every GET /jobs.

**Root cause:** No type check on imported params; _to_out converted with float() unguarded.

**Fixes:** [FIX-0307](../FIX_LOG.md#fix-0307) (0.11.0-beta.3)

**Verified:** tests/test_api.py::test_imported_params_of_the_wrong_type_are_refused_and_never_break_the_home_page passed, and fails with the fix reverted (by pytest (the test fails on the old code))

**Resolved:** 2026-10-18 · **Closed:** _pending_

**Evidence:**

- code review of the whole codebase (six reviewers), confirmed by reading the code

**History:**

- 2026-10-18 — Open: reported
- 2026-10-18 — Fixed: commit f05b120399
- 2026-10-18 — Verified: its test passes and fails on the old code

## BUG-0308

**A GP7/8 file with a two-staff track before the guitar charted the wrong bars**

| | |
|---|---|
| Detected | 2026-10-18 |
| Reported by | code review (Claude, on the maintainer's request) |
| Found in | 0.11.0-beta.2 |
| Build / commit | f64c45e8e176c44bd87c7c7866f741330b443011 |
| Severity | High |
| Priority | P2 |
| Status | Verified |

MasterBar/<Bars> lists one bar per staff, track after track; the parser indexed it by track, so after a piano's grand staff every track read the bars of the staff before it (the guitar came out empty).

**Steps to reproduce:** 

1. Import a .gp whose first track is a piano (two staves)
2. Pick the guitar track

**Expected:** The guitar's notes.

**Observed:** An empty chart (test fixture).

**Root cause:** bar_ids[track_index] instead of the track's first staff slot.

**Fixes:** [FIX-0308](../FIX_LOG.md#fix-0308) (0.11.0-beta.3)

**Verified:** tests/test_gpif_import.py::test_bars_are_found_by_staff_so_a_two_staff_piano_before_the_guitar_changes_nothing passed, and fails with the fix reverted (by pytest (the test fails on the old code))

**Resolved:** 2026-10-18 · **Closed:** _pending_

**Evidence:**

- code review of the whole codebase (six reviewers), confirmed by reading the code

**History:**

- 2026-10-18 — Open: reported
- 2026-10-18 — Fixed: commit f05b120399
- 2026-10-18 — Verified: its test passes and fails on the old code

## BUG-0309

**Auto-pick put a "Lead/Rhythm" track in both slots and the build failed**

| | |
|---|---|
| Detected | 2026-10-18 |
| Reported by | code review (Claude, on the maintainer's request) |
| Found in | 0.11.0-beta.2 |
| Build / commit | f64c45e8e176c44bd87c7c7866f741330b443011 |
| Severity | Medium |
| Priority | P2 |
| Status | Verified |

Without a chosen track, a lone track named "Lead/Rhythm Guitar" was picked for Lead and for Rhythm, and the build refused two charts on one track.

**Steps to reproduce:** 

1. See the description (found by reading the code)

**Expected:** As described in the solution.

**Observed:** Without a chosen track, a lone track named "Lead/Rhythm Guitar" was picked for Lead and for Rhythm, and the build refused two charts on one track.

**Root cause:** auto_pick_tracks scanned for "lead" and "rhythm" independently.

**Fixes:** [FIX-0309](../FIX_LOG.md#fix-0309) (0.11.0-beta.4)

**Verified:** tests/test_merge_tracks.py::test_a_track_named_lead_and_rhythm_is_picked_once passed, and fails with the fix reverted (by pytest (the test fails on the old code))

**Resolved:** 2026-10-18 · **Closed:** _pending_

**Evidence:**

- code review of the whole codebase (six reviewers), confirmed by reading the code

**History:**

- 2026-10-18 — Open: reported
- 2026-10-18 — Fixed: commit d9ad9d0d24
- 2026-10-18 — Verified: its test passes and fails on the old code

## BUG-0310

**A scoop from its own fret turned a note seconds earlier into a long slide**

| | |
|---|---|
| Detected | 2026-10-18 |
| Reported by | code review (Claude, on the maintainer's request) |
| Found in | 0.11.0-beta.2 |
| Build / commit | f64c45e8e176c44bd87c7c7866f741330b443011 |
| Severity | Medium |
| Priority | P2 |
| Status | Verified |

A slide into fret 1 from below (source max(1, fret-3) = 1) with room before it fell through to "the previous note slides into it", whatever the gap, making a note 8 s earlier an 8 s slide.

**Steps to reproduce:** 

1. See the description (found by reading the code)

**Expected:** As described in the solution.

**Observed:** A slide into fret 1 from below (source max(1, fret-3) = 1) with room before it fell through to "the previous note slides into it", whatever the gap, making a note 8 s earlier an 8 s slide.

**Root cause:** expand_slide_ins took the previous-note branch without checking the room.

**Fixes:** [FIX-0310](../FIX_LOG.md#fix-0310) (0.11.0-beta.4)

**Verified:** tests/test_domain.py::test_a_scoop_from_its_own_fret_never_turns_an_earlier_note_into_a_slide passed, and fails with the fix reverted (by pytest (the test fails on the old code))

**Resolved:** 2026-10-18 · **Closed:** _pending_

**Evidence:**

- code review of the whole codebase (six reviewers), confirmed by reading the code

**History:**

- 2026-10-18 — Open: reported
- 2026-10-18 — Fixed: commit d9ad9d0d24
- 2026-10-18 — Verified: its test passes and fails on the old code

## BUG-0311

**A trilled note lost its fingering, pick direction, slide and link**

| | |
|---|---|
| Detected | 2026-10-18 |
| Reported by | code review (Claude, on the maintainer's request) |
| Found in | 0.11.0-beta.2 |
| Build / commit | f64c45e8e176c44bd87c7c7866f741330b443011 |
| Severity | Low |
| Priority | P3 |
| Status | Verified |

Each trill step was a bare TabNote; the first step kept SLIDE with no target and the last step had no slide or link.

**Steps to reproduce:** 

1. See the description (found by reading the code)

**Expected:** As described in the solution.

**Observed:** Each trill step was a bare TabNote; the first step kept SLIDE with no target and the last step had no slide or link.

**Root cause:** expand_trills built fresh notes.

**Fixes:** [FIX-0311](../FIX_LOG.md#fix-0311) (0.11.0-beta.4)

**Verified:** tests/test_domain.py::test_a_trill_keeps_the_notes_fingering_and_ends_with_its_slide passed, and fails with the fix reverted (by pytest (the test fails on the old code))

**Resolved:** 2026-10-18 · **Closed:** _pending_

**Evidence:**

- code review of the whole codebase (six reviewers), confirmed by reading the code

**History:**

- 2026-10-18 — Open: reported
- 2026-10-18 — Fixed: commit d9ad9d0d24
- 2026-10-18 — Verified: its test passes and fails on the old code

## BUG-0312

**A capo pushed slide and trill targets past fret 24**

| | |
|---|---|
| Detected | 2026-10-18 |
| Reported by | code review (Claude, on the maintainer's request) |
| Found in | 0.11.0-beta.2 |
| Build / commit | f64c45e8e176c44bd87c7c7866f741330b443011 |
| Severity | Low |
| Priority | P3 |
| Status | Verified |

Only the note's own fret was checked against 24; an unpitched slide-out capped at 22 became 27 with capo 5.

**Steps to reproduce:** 

1. See the description (found by reading the code)

**Expected:** As described in the solution.

**Observed:** Only the note's own fret was checked against 24; an unpitched slide-out capped at 22 became 27 with capo 5.

**Root cause:** apply_capo added the capo to targets without a bound.

**Fixes:** [FIX-0312](../FIX_LOG.md#fix-0312) (0.11.0-beta.4)

**Verified:** tests/test_domain.py::test_the_capo_keeps_slide_and_trill_targets_on_the_neck passed, and fails with the fix reverted (by pytest (the test fails on the old code))

**Resolved:** 2026-10-18 · **Closed:** _pending_

**Evidence:**

- code review of the whole codebase (six reviewers), confirmed by reading the code

**History:**

- 2026-10-18 — Open: reported
- 2026-10-18 — Fixed: commit d9ad9d0d24
- 2026-10-18 — Verified: its test passes and fails on the old code

## BUG-0316

**A locked .gp file gave a 500 and left its upload**

| | |
|---|---|
| Detected | 2026-10-18 |
| Reported by | code review (Claude, on the maintainer's request) |
| Found in | 0.11.0-beta.2 |
| Build / commit | f64c45e8e176c44bd87c7c7866f741330b443011 |
| Severity | Medium |
| Priority | P3 |
| Status | Verified |

A score.gpif that is not text (locked in Guitar Pro) raised UnicodeDecodeError, not IngestionError.

**Steps to reproduce:** 

1. See the description (found by reading the code)

**Expected:** As described in the solution.

**Observed:** A score.gpif that is not text (locked in Guitar Pro) raised UnicodeDecodeError, not IngestionError.

**Root cause:** _load_gpif caught only zip/OS errors.

**Fixes:** [FIX-0316](../FIX_LOG.md#fix-0316) (0.11.0-beta.4)

**Verified:** tests/test_gpif_import.py::test_a_locked_gp_file_is_refused_in_words_not_a_crash passed, and fails with the fix reverted (by pytest (the test fails on the old code))

**Resolved:** 2026-10-18 · **Closed:** _pending_

**Evidence:**

- code review of the whole codebase (six reviewers), confirmed by reading the code

**History:**

- 2026-10-18 — Open: reported
- 2026-10-18 — Fixed: commit 9fff3a3837
- 2026-10-18 — Verified: its test passes and fails on the old code

## BUG-0343

**A chart whose GP track has no notes fails with a bare 'arrangement has no notes' that names neither the chart nor the track**

| | |
|---|---|
| Detected | 2026-10-20 |
| Reported by | GitHub issue #7 (mongrelx) |
| Found in | 0.11.0-beta.4 |
| Build / commit | _pending_ |
| Severity | Low |
| Priority | P3 |
| Status | Verified |

When the GP track picked for an arrangement holds no notes, the build fails with 'invalid arrangement: arrangement has no notes' from Arrangement.validate, so a script driving the API cannot tell which of its tracks was empty. The issue attributed it to import_mutes; stripping mutes keeps every note (verified), so that part was another cause.

**Steps to reproduce:** 

1. Create a GP job whose lead_track is a track with no notes (a vocal or empty track)

**Expected:** An error naming the chart, its GP track and what to do.

**Observed:** 'invalid arrangement: arrangement has no notes'.

**Root cause:** No check before building; the domain validation's message has no track context.

**Fixes:** [FIX-0343](../FIX_LOG.md#fix-0343) (0.11.1-beta.2)

**Verified:** test_a_chart_whose_track_has_no_notes_is_named_with_its_track (fails without the check) (by the developer (pytest))

**Resolved:** 2026-10-20 · **Closed:** _pending_

**Evidence:**

- pytest 2026-10-20: full suite passes

**History:**

- 2026-10-20 — Open: reported
- 2026-10-20 — In Progress: from the GitHub issue
- 2026-10-20 — Fixed: commit 8dc5d4bb50
- 2026-10-20 — Verified: pytest
