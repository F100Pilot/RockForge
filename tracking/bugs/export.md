<!-- Generated from tracking/bugs.json by `python -m tools.tracking render`. Do not edit by hand: edit the JSON and render again. -->

# Bugs: export

Export back to Guitar Pro. Index: [BUG_LOG.md](../BUG_LOG.md).

## BUG-0166

**Corrected-GP export had no entry point in the UI**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 74247718fad03ebf54e5eaad1caf127e96027f6b |
| Severity | Low |
| Priority | P4 |
| Status | Fixed |

After the analysis panel was removed, /export-gp sat unreachable.

**Steps to reproduce:** _pending_

**Expected:** Export button

**Observed:** No way to export

**Root cause:** Feed removed.

**Fixes:** [FIX-0166](../FIX_LOG.md#fix-0166) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-08-24 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Dead feature.

**Evidence:**

- commit f159fb23f2 Wire /export-gp to a button in the sync panel
- found_in_version: fix f159fb23f2 (2026-08-24) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 74247718fa, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-08-24 — Fixed: commit f159fb23f2

## BUG-0224

**Corrected-GP export wrote bends 50 times too big**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 34b604fb4c66880d010c225390349d37d2e4c959 |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

Every bend was written as a rise to semitones×100 quarter tones and the curve ignored.

**Steps to reproduce:** _pending_

**Expected:** Real size and shape

**Observed:** Huge bends in Guitar Pro

**Root cause:** Wrong unit.

**Fixes:** [FIX-0224](../FIX_LOG.md#fix-0224) (0.10.0-beta.1)

**Verified:** regression test(s) test_a_bend_keeps_its_size_and_curve pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-09-30 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Export corrupt for bends.

**Evidence:**

- commit 4eae9ccb10 Corrected-GP export: bends at their real size and shape
- found_in_version: fix 4eae9ccb10 (2026-09-30) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 34b604fb4c, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-09-30 — Fixed: commit 4eae9ccb10
- 2026-09-30 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0230

**Charts read back from the XML lost their bend curves**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | f5fa599f336eb573f596565f6dc20b67cf78999f |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

read_arrangement_xml dropped <bendValues>, so the viewer and corrected-GP export saw only the peak.

**Steps to reproduce:** _pending_

**Expected:** Curve read back

**Observed:** Bend-and-release became a rise

**Root cause:** Reader ignored bendValues.

**Fixes:** [FIX-0230](../FIX_LOG.md#fix-0230) (0.10.0-beta.1)

**Verified:** regression test(s) test_the_bend_on_the_tie_is_bent_and_released_on_time pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-09-30 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Export accuracy.

**Evidence:**

- commit 8cda047d1c Bend curves keep their timing to the chart; GP5 → XML → SNG test
- found_in_version: fix 8cda047d1c (2026-09-30) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent f5fa599f33, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-09-30 — Fixed: commit 8cda047d1c
- 2026-09-30 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0304

**The Guitar Pro export of the edited notes lost the capo**

| | |
|---|---|
| Detected | 2026-10-18 |
| Reported by | code review (Claude, on the maintainer's request) |
| Found in | 0.11.0-beta.2 |
| Build / commit | f64c45e8e176c44bd87c7c7866f741330b443011 |
| Severity | Medium |
| Priority | P2 |
| Status | Verified |

The XML reader looked for the capo as an attribute of <song>, but the writer emits a <capo> element, so the export wrote no capo and open strings came out a capo too low.

**Steps to reproduce:** 

1. Build a chart with a capo
2. Export "Guitar Pro with the edited notes"

**Expected:** The exported file has the capo.

**Observed:** capo 2 read back as 0.

**Root cause:** reader.py read root.get('capo').

**Fixes:** [FIX-0304](../FIX_LOG.md#fix-0304) (0.11.0-beta.3)

**Verified:** tests/test_capo.py::test_the_capo_survives_the_built_xml_read_back passed, and fails with the fix reverted (by pytest (the test fails on the old code))

**Resolved:** 2026-10-18 · **Closed:** _pending_

**Evidence:**

- code review of the whole codebase (six reviewers), confirmed by reading the code

**History:**

- 2026-10-18 — Open: reported
- 2026-10-18 — Fixed: commit f907982d0f
- 2026-10-18 — Verified: its test passes and fails on the old code

## BUG-0313

**The GP5 export of edited notes could write an unreadable file**

| | |
|---|---|
| Detected | 2026-10-18 |
| Reported by | code review (Claude, on the maintainer's request) |
| Found in | 0.11.0-beta.2 |
| Build / commit | f64c45e8e176c44bd87c7c7866f741330b443011 |
| Severity | Medium |
| Priority | P2 |
| Status | Verified |

Two onsets snapped onto one tick on one string became two notes on one string in one beat, which the GP5 reader refuses (fast triplets, 32nd runs).

**Steps to reproduce:** 

1. See the description (found by reading the code)

**Expected:** As described in the solution.

**Observed:** Two onsets snapped onto one tick on one string became two notes on one string in one beat, which the GP5 reader refuses (fast triplets, 32nd runs).

**Root cause:** Notes of one snapped tick were merged without checking strings.

**Fixes:** [FIX-0313](../FIX_LOG.md#fix-0313) (0.11.0-beta.4)

**Verified:** tests/test_gp_arrangement_writer.py::test_fast_notes_snapped_onto_one_string_still_give_a_readable_file passed, and fails with the fix reverted (by pytest (the test fails on the old code))

**Resolved:** 2026-10-18 · **Closed:** _pending_

**Evidence:**

- code review of the whole codebase (six reviewers), confirmed by reading the code

**History:**

- 2026-10-18 — Open: reported
- 2026-10-18 — Fixed: commit 9fff3a3837
- 2026-10-18 — Verified: its test passes and fails on the old code

## BUG-0314

**The GP5 export drifted with whole-BPM rounding and lost the tempo of bars without notes**

| | |
|---|---|
| Detected | 2026-10-18 |
| Reported by | code review (Claude, on the maintainer's request) |
| Found in | 0.11.0-beta.2 |
| Build / commit | f64c45e8e176c44bd87c7c7866f741330b443011 |
| Severity | Medium |
| Priority | P2 |
| Status | Verified |

Each bar's tempo was rounded on its own (90 bars at 119.52 BPM came back 0.67 s off), and a bar's tempo change rode its first NOTE, so a bar with none lost it.

**Steps to reproduce:** 

1. See the description (found by reading the code)

**Expected:** As described in the solution.

**Observed:** Each bar's tempo was rounded on its own (90 bars at 119.52 BPM came back 0.67 s off), and a bar's tempo change rode its first NOTE, so a bar with none lost it.

**Root cause:** Rounding without carrying the error; the MixTableChange attached to the first note beat.

**Fixes:** [FIX-0314](../FIX_LOG.md#fix-0314) (0.11.0-beta.4)

**Verified:** tests/test_gp_arrangement_writer.py::test_the_rounding_of_each_bars_tempo_does_not_add_up passed, and fails with the fix reverted (by pytest (the test fails on the old code))

**Resolved:** 2026-10-18 · **Closed:** _pending_

**Evidence:**

- code review of the whole codebase (six reviewers), confirmed by reading the code

**History:**

- 2026-10-18 — Open: reported
- 2026-10-18 — Fixed: commit 9fff3a3837
- 2026-10-18 — Verified: its test passes and fails on the old code

## BUG-0315

**A tempo correction in the GP5 export lost to a tempo left on another track**

| | |
|---|---|
| Detected | 2026-10-18 |
| Reported by | code review (Claude, on the maintainer's request) |
| Found in | 0.11.0-beta.2 |
| Build / commit | f64c45e8e176c44bd87c7c7866f741330b443011 |
| Severity | Medium |
| Priority | P3 |
| Status | Verified |

The corrected file kept a tempo change authored on another track (or on bar 1's first beat), which the importer reads after the correction.

**Steps to reproduce:** 

1. See the description (found by reading the code)

**Expected:** As described in the solution.

**Observed:** The corrected file kept a tempo change authored on another track (or on bar 1's first beat), which the importer reads after the correction.

**Root cause:** Only track 0's first beat was set.

**Fixes:** [FIX-0315](../FIX_LOG.md#fix-0315) (0.11.0-beta.4)

**Verified:** tests/test_gp_tempo_writer.py::test_a_correction_wins_over_a_tempo_left_on_another_track passed, and fails with the fix reverted (by pytest (the test fails on the old code))

**Resolved:** 2026-10-18 · **Closed:** _pending_

**Evidence:**

- code review of the whole codebase (six reviewers), confirmed by reading the code

**History:**

- 2026-10-18 — Open: reported
- 2026-10-18 — Fixed: commit 9fff3a3837
- 2026-10-18 — Verified: its test passes and fails on the old code
