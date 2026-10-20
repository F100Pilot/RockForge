<!-- Generated from tracking/bugs.json by `python -m tools.tracking render`. Do not edit by hand: edit the JSON and render again. -->

# Bugs: release

Building and publishing releases. Index: [BUG_LOG.md](../BUG_LOG.md).

## BUG-0164

**CI was green while never running the native PSARC tests**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | cff0f84ff2bfbe789c6f69ca678df121ad5acf81 |
| Severity | Medium |
| Priority | P3 |
| Status | Fixed |

CI installed only [dev], without cryptography, so test_psarc_packer.py and test_psarc_crypto.py skipped themselves entirely: 17 tests over the encrypted container and the SNG binary never ran.

**Steps to reproduce:** _pending_

**Expected:** CI runs the PSARC tests.

**Observed:** They were silently skipped.

**Root cause:** importorskip('cryptography') with the [psarc] extra not installed in CI.

**Fixes:** [FIX-0164](../FIX_LOG.md#fix-0164) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-08-24 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Coverage gap on the most delicate output.

**Evidence:**

- CLAUDE.md § Commands — '**Install `[psarc]`, not bare `[dev]`.**'
- commit 93c0a5083d Fix the standalone .exe's missing web assets, and stop CI skipping the PSARC tests
- found_in_version: the fix commit 93c0a5083d is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent cff0f84ff2

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-08-24 — Fixed: commit 93c0a5083d

## BUG-0267

**Release workflow ignored a tag without the leading v; the beta 3 release had no files**

| | |
|---|---|
| Detected | 2026-10-15 |
| Reported by | pending (not recorded) |
| Found in | 0.10.0-beta.3 |
| Build / commit | bebcf2b5d6e7d074829b4c01106ada00a7fcdb97 |
| Severity | High |
| Priority | P2 |
| Status | Closed |

The release workflow only listened for tags "v*"; the beta 3 release was created on GitHub's page as "0.10.0-beta.3", so the workflow never ran and the release had no downloads.

**Steps to reproduce:** 

1. Create a release on GitHub's page with the tag 0.10.0-beta.3

**Expected:** The workflow builds and attaches the downloads.

**Observed:** The workflow never ran; the release has no files.

**Root cause:** .github/workflows/release.yml triggered on 'v*' only.

**Fixes:** [FIX-0267](../FIX_LOG.md#fix-0267) (0.10.0-beta.5)

**Verified:** release.yml listens to tags with and without the leading v and compares the version with the v stripped. A v-less tag run on GitHub was not observed (by the developer (pytest))

**Resolved:** 2026-10-15 · **Closed:** 2026-10-20

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: A published release without its downloads; fixed by a manual run.

**Evidence:**

- commit 3e1fac60aa Release workflow: a tag without the leading v builds too
- commit ed59086740 Release workflow: run by hand, it can attach the files to an existing release ("the beta 3 one")
- detected 2026-10-15: beta 3 (bebcf2b) and the fix are both dated 2026-10-15
- found_in_version: the fault showed in the publication of beta 3 itself; its workflow at bebcf2b has the v* filter
- not in the changelog
- pytest 2026-10-20: passes; full suite passes
- Mutation: tags ['v*'] alone fails the test

**History:**

- 2026-10-15 — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-10-15 — Fixed: commit 3e1fac60aa, ed59086740
- 2026-10-20 — Verified: regression check re-run (pytest/Playwright)
- 2026-10-20 — Closed: released in 0.10.0-beta.5
