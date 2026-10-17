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
