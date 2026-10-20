<!-- Generated from tracking/bugs.json by `python -m tools.tracking render`. Do not edit by hand: edit the JSON and render again. -->

# Bugs: sync

Synchronisation tools on the score. Index: [BUG_LOG.md](../BUG_LOG.md).

## BUG-0005

**GP sync offset kept the recording's own intro gap, so chart and audio drifted apart**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | b60201dc7a224c55b6ee534930013fcbd50699c0 |
| Severity | High |
| Priority | P2 |
| Status | Fixed |

offset_s padded the audio by N seconds and shifted the score by N, preserving any gap between the recording's own intro and the score's note 0, so the chart and audio were off by exactly that gap.

**Steps to reproduce:** _pending_

**Expected:** offset_s places the first note where it is heard in the recording

**Observed:** Chart and audio offset by the recording's intro length

**Root cause:** The offset was applied to both audio and score instead of aligning the score to the recording.

**Fixes:** [FIX-0005](../FIX_LOG.md#fix-0005) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-06-13 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Every GP chart could be out of sync with no clean fix.

**Evidence:**

- commit 8f81303 and 215917c were earlier attempts (trim, then pad both) replaced by 95d2d20
- commit 8f8130396a Fix GP audio sync: trim audio lead-in instead of shifting score times
- commit 215917c389 Rework GP sync offset: add silent lead-in to audio, shift score+lyrics forward
- commit 95d2d20cc1 Fix GP sync: align score to recording, don't pad audio equally
- found_in_version: fix 8f8130396a (2026-06-12) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent b60201dc7a, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-06-13 — Fixed: commit 8f8130396a, 215917c389, 95d2d20cc1

## BUG-0011

**Drift correction shifted notes far outside the corrected excerpt**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | pending (not recorded) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 0dc76bcf4647278d9ae9f081675813c286ccaa13 |
| Severity | Medium |
| Priority | P2 |
| Status | Closed |

_build_time_warp extrapolated the boundary segment's slope outside the anchors, so notes far before/after a correction drifted further the larger it was; then a constant shift was still applied outside an excerpt.

**Steps to reproduce:** 

1. Drag a note or excerpt to correct it
2. Look at distant notes

**Expected:** Notes outside a multi-anchor excerpt are untouched.

**Observed:** Distant notes were shifted.

**Root cause:** The warp extrapolated (later: shifted) outside the anchor range.

**Fixes:** [FIX-0011](../FIX_LOG.md#fix-0011) (0.10.0-beta.1)

**Verified:** regression test(s) test_build_time_warp_leaves_notes_outside_excerpt_untouched, test_build_time_warp_single_anchor_shifts_everything pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-06-14 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Corrections disturbed unrelated parts of the song.

**Evidence:**

- CLAUDE.md § Manual drift correction (`sync_anchor_stages`)
- CLAUDE.md: 'Two-or-more anchors (excerpt drag) rigidly shift/stretch only the excerpt ...; everything before/after is left untouched (identity)'
- commit 58721bd3b9 Fix drift-correction to not shift distant notes; add zoom controls
- commit 2880c7f288 Excerpt drift corrections no longer shift notes outside the excerpt
- found_in_version: the fix commits are ancestor of cb00653 (the first public release, 0.10.0 beta 1, 2026-10-14), so the faulty code only existed in development builds before 0.10.0-beta.1
- found_in_build: 0dc76bcf46 is the parent of the first fix commit 58721bd3b9 and still carries the code the fix changes

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-06-14 — Fixed: commit 58721bd3b9, 2880c7f288
- 2026-06-14 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0013

**Pending drag anchors did not round-trip through a rebuild with a pending tempo/offset**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | ea51319369df042b446d32bf535fb1cb1b67c334 |
| Severity | Medium |
| Priority | P3 |
| Status | Fixed |

Pending drag anchors were captured in the built timeline while the backend applies the warp in the post-offset/post-tempo timeline, so with a tempo/offset change pending they landed elsewhere after rebuild.

**Steps to reproduce:** _pending_

**Expected:** Anchors land where previewed

**Observed:** Anchors shifted after rebuild

**Root cause:** Coordinate mismatch between viewer capture space and backend warp space.

**Fixes:** [FIX-0013](../FIX_LOG.md#fix-0013) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-06-14 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Preview did not match build.

**Evidence:**

- commit ce2918587b Make sync audible live (no rebuild) and round-trip anchors exactly
- found_in_version: fix ce2918587b (2026-06-14) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent ea51319369, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-06-14 — Fixed: commit ce2918587b

## BUG-0030

**Pending BPM edit lost on arrangement tab switch**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | pending (not recorded) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 405c6cb9b4668f453c41cb7c0f4b6ede6b37414a |
| Severity | Medium |
| Priority | P3 |
| Status | Fixed |

The tempo field reset to the built value whenever the user switched Lead/Rhythm tabs, losing the pending edit.

**Steps to reproduce:** _pending_

**Expected:** Pending BPM kept per arrangement

**Observed:** Pending BPM reset

**Root cause:** No per-arrangement store for the pending tempo.

**Fixes:** [FIX-0030](../FIX_LOG.md#fix-0030) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-06-18 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Silent loss of an edit.

**Evidence:**

- commit d3c8cb2eea Persist pending BPM/tempo across arrangement tab switches
- found_in_version: fix d3c8cb2eea (2026-06-18) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 405c6cb9b4, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-06-18 — Fixed: commit d3c8cb2eea

## BUG-0047

**Guided first-note flow created a hidden anchor instead of updating the start field**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | pending (not recorded) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 3f609a9c0561a103622e1a7a3c002e5a7a688cf1 |
| Severity | Low |
| Priority | P4 |
| Status | Fixed |

The guided 'Detetar 1ª nota' flow created a hidden anchor rather than updating 'Início da música', so the field did not reflect the alignment.

**Steps to reproduce:** _pending_

**Expected:** Field shows the new start

**Observed:** Field unchanged after the flow

**Root cause:** Wrote an anchor, not the offset.

**Fixes:** [FIX-0047](../FIX_LOG.md#fix-0047) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-07-04 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Confusing state.

**Evidence:**

- commit 770d51a9b2 Deteção da 1ª nota atualiza o offset; "remover" correção redesenha a partitura
- found_in_version: fix 770d51a9b2 (2026-07-04) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 3f609a9c05, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-04 — Fixed: commit 770d51a9b2

## BUG-0048

**Removing a single pending correction left its marker on the score**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | pending (not recorded) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 3f609a9c0561a103622e1a7a3c002e5a7a688cf1 |
| Severity | Low |
| Priority | P4 |
| Status | Fixed |

The 'remover' button on a correction removed it from the list but never called showArr, so its marker stayed drawn.

**Steps to reproduce:** _pending_

**Expected:** Marker disappears

**Observed:** Removed correction still drawn

**Root cause:** Missing redraw.

**Fixes:** [FIX-0048](../FIX_LOG.md#fix-0048) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-07-04 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Cosmetic/confusing.

**Evidence:**

- commit 770d51a9b2 Deteção da 1ª nota atualiza o offset; "remover" correção redesenha a partitura
- found_in_version: fix 770d51a9b2 (2026-07-04) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 3f609a9c05, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-04 — Fixed: commit 770d51a9b2

## BUG-0100

**Conflicting sync anchors crashed the build with a cryptic TempoMap error**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | pending (not recorded) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | dda9fafc4190b7058964854d3b00695afb221224 |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

Two anchors whose targets contradict their chart order made _build_time_warp fold back, and construction crashed deep inside TempoMap ('beats must be in chronological order') with no clue which correction caused it; successive 'Mover seguintes' clicks created this easily.

**Steps to reproduce:** 

1. Make two corrections that map a later chart point before an earlier one (e.g. two 'Mover seguintes')
2. Apply and rebuild

**Expected:** A clear error naming the two conflicting points.

**Observed:** A cryptic ValueError from TempoMap.

**Root cause:** Anchor rounds were applied without validating their order.

**Fixes:** [FIX-0100](../FIX_LOG.md#fix-0100) (0.10.0-beta.1)

**Verified:** regression test(s) test_conflicting_sync_anchors_raise_clear_error, test_check_anchor_order_accepts_valid_and_rejects_crossing pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-07-11 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Build failure with an unhelpful message; removing the corrections worked around it.

**Evidence:**

- CLAUDE.md § Manual drift correction (Conflicting anchors are rejected)
- commit a4b30b5c15 Reject conflicting sync anchors with a clear error instead of crashing
- found_in_version: the fix commit is an ancestor of cb00653 (the first public release, 0.10.0 beta 1, 2026-10-14), so the faulty code only existed in development builds before 0.10.0-beta.1
- found_in_build: dda9fafc41 is the parent of the first fix commit a4b30b5c15 and still carries the code the fix changes

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-11 — Fixed: commit a4b30b5c15
- 2026-07-11 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0101

**A local sync stretch re-inflated sustains into fused 'tall pillars'**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | pending (not recorded) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | a4b30b5c154633d04d4d9891b275ca8bd4124393 |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

A correction mapping a chart interval to a wider one scaled every warped sustain by that factor, re-inflating or overlapping sustains apply_sustain_gap had trimmed, so the highway drew fused/tall sustain shapes instead of separate notes.

**Steps to reproduce:** 

1. Make an excerpt correction that stretches a passage
2. Rebuild and view the highway

**Expected:** Separate note shapes with a gap.

**Observed:** Fused or overlapping sustain trails.

**Root cause:** _warp_parsed_track recomputed sustain as warp(time+sustain) − warp(time) without re-trimming.

**Fixes:** [FIX-0101](../FIX_LOG.md#fix-0101) (0.10.0-beta.1)

**Verified:** regression test(s) test_warp_re_trims_sustain_after_a_local_stretch pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-07-11 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Highway rendering fault in corrected passages.

**Evidence:**

- CLAUDE.md § Manual drift correction (A local stretch re-inflates sustain)
- commit 7aa075eeb6 Re-trim sustain after warping (fix fused/tall note boxes from sync corrections)
- found_in_version: the fix commit is an ancestor of cb00653 (the first public release, 0.10.0 beta 1, 2026-10-14), so the faulty code only existed in development builds before 0.10.0-beta.1
- found_in_build: a4b30b5c15 is the parent of the first fix commit 7aa075eeb6 and still carries the code the fix changes

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-11 — Fixed: commit 7aa075eeb6
- 2026-07-11 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0102

**"Mover seguintes", tap and re-tempo moved notes the wrong way once an anchor existed**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 07cf50ee50c56aeb64798e9c48b7ad7a1bb230d7 |
| Severity | High |
| Priority | P2 |
| Status | Fixed |

movefrom, tap and reTempoFromHere used the WARPED position as each anchor's origin; with a pending anchor (e.g. Step 1's 'Início') the piecewise map was corrupted and the clicked note landed elsewhere (38.5 instead of 40).

**Steps to reproduce:** 

1. Set 'Início' (a pending anchor)
2. Use 'Mover seguintes' on a note with the cursor elsewhere

**Expected:** The clicked note lands on the cursor.

**Observed:** Notes moved away from the cursor instead of onto it.

**Root cause:** Anchor origins were warp(previewScale(t)) instead of the unwarped previewScale(t).

**Fixes:** [FIX-0102](../FIX_LOG.md#fix-0102) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-07-11 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Core sync gestures misplaced notes.

**Evidence:**

- CLAUDE.md § Per-arrangement sync (All anchor-writing modes use the UNwarped origin)
- CLAUDE.md: 'the "notes moved away from the cursor instead of onto it" bug'
- commit d45d10a5ad Fix "Mover seguintes"/tap/re-tempo moving notes the wrong way
- found_in_version: the fix commit is an ancestor of cb00653 (the first public release, 0.10.0 beta 1, 2026-10-14), so the faulty code only existed in development builds before 0.10.0-beta.1
- found_in_build: 07cf50ee50 is the parent of the first fix commit d45d10a5ad and still carries the code the fix changes

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-11 — Fixed: commit d45d10a5ad

## BUG-0103

**"Mover seguintes" also moved the notes before the click**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 7a367d821b7a4e67275984d3dbacc9a7102731da |
| Severity | Medium |
| Priority | P2 |
| Status | Fixed |

With a prior anchor (a lone 'Início' is a uniform shift), adding the clicked/last anchors turned the pre-click segment into an interpolated one, dragging the preceding notes along.

**Steps to reproduce:** 

1. Set 'Início'
2. Use 'Mover seguintes' on a note mid-song

**Expected:** Only the clicked note and the following ones move.

**Observed:** Notes before the click moved too.

**Root cause:** Two anchors alone did not pin the region before the click.

**Fixes:** [FIX-0103](../FIX_LOG.md#fix-0103) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-07-11 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Corrections spoiled already-synced parts.

**Evidence:**

- CLAUDE.md § Per-arrangement sync ("Mover seguintes" pins the region BEFORE the click)
- user quote (undated): 'mover seguintes atualizou também as notas que ficaram para trás'
- commit d4fb3a9a8e Fix "Mover seguintes" dragging the notes before the click
- found_in_version: the fix commit is an ancestor of cb00653 (the first public release, 0.10.0 beta 1, 2026-10-14), so the faulty code only existed in development builds before 0.10.0-beta.1
- found_in_build: 7a367d821b is the parent of the first fix commit d4fb3a9a8e and still carries the code the fix changes

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-11 — Fixed: commit d4fb3a9a8e

## BUG-0104

**Dragging a note to the playback cursor was unreliable**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 8f9e18d0ff4f0154ca6adb10a337a3e01c0b061f |
| Severity | Medium |
| Priority | P3 |
| Status | Fixed |

Only the click modes snapped to the playhead; the ordinary drag snapped only to the beat grid, with no visual difference, so 'drag to the cursor' did not reliably land on it.

**Steps to reproduce:** 

1. Pause the cursor where a note should sound
2. Drag the note to the cursor

**Expected:** The note lands exactly on the cursor.

**Observed:** The note snapped to the nearest beat instead.

**Root cause:** snapDisplay had no cursor target for drags.

**Fixes:** [FIX-0104](../FIX_LOG.md#fix-0104) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-07-11 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Workaround: use the click modes.

**Evidence:**

- CLAUDE.md § Sync by bar number (Cursor as an explicit snap target)
- CLAUDE.md: 'the likely source of "arrastar para o cursor nem sempre funciona"'
- commit 1e02138b80 Tab viewer: per-track note start + more precise note adjustment
- found_in_version: the fix commit is an ancestor of cb00653 (the first public release, 0.10.0 beta 1, 2026-10-14), so the faulty code only existed in development builds before 0.10.0-beta.1
- found_in_build: 8f9e18d0ff is the parent of the first fix commit 1e02138b80 and still carries the code the fix changes

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-11 — Fixed: commit 1e02138b80

## BUG-0107

**Pending-corrections list went stale after a plain mouse drag**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 8f9e18d0ff4f0154ca6adb10a337a3e01c0b061f |
| Severity | Low |
| Priority | P3 |
| Status | Fixed |

The single-note and group-drag pointerup handlers redrew the score but never called renderAnchorsList/updatePendingChangesInfo, so the list only refreshed after click-mode corrections.

**Steps to reproduce:** 

1. Drag a note to make a correction
2. Look at the pending corrections list

**Expected:** The new correction appears.

**Observed:** The list did not update.

**Root cause:** pointerup handlers did not refresh the list.

**Fixes:** [FIX-0107](../FIX_LOG.md#fix-0107) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-07-11 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Display staleness; the correction itself was kept.

**Evidence:**

- CLAUDE.md § Sync by bar number (Numeric anchor editing)
- commit 1e02138b80 Tab viewer: per-track note start + more precise note adjustment
- found_in_version: the fix commit is an ancestor of cb00653 (the first public release, 0.10.0 beta 1, 2026-10-14), so the faulty code only existed in development builds before 0.10.0-beta.1
- found_in_build: 8f9e18d0ff is the parent of the first fix commit 1e02138b80 and still carries the code the fix changes

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-11 — Fixed: commit 1e02138b80

## BUG-0115

**Automatic sync jumped the BPM ~50% on triplet/compound feels**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 50abcb79f0af357755481407cdafe862770a3b4f |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

suggest_tempo_scale tried only ×0.5/1/2, so a tracker locked on a 3/2 pulse proposed tempo_scale ~1.33/1.5. (Auto-sync later removed.)

**Steps to reproduce:** _pending_

**Expected:** tempo_scale ≈ 1

**Observed:** BPM jump of ~50%

**Root cause:** Missing triplet-grid ratios.

**Fixes:** [FIX-0115](../FIX_LOG.md#fix-0115) (0.10.0-beta.1)

**Verified:** regression test(s) test_suggest_tempo_scale_triplet_grid_does_not_jump_bpm pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-07-11 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Wrong proposals; user could edit.

**Evidence:**

- commit b78cd5b644 Auto-sync: snap tempo to the triplet/compound grid, not just octaves
- found_in_version: fix b78cd5b644 (2026-07-11) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 50abcb79f0, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-11 — Fixed: commit b78cd5b644
- 2026-07-11 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0134

**Dynamic auto-sync discarded the pinned first note and realigned from 0 s**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | ce687e2866cfaa7e1fd5e3e02325af670610be4e |
| Severity | Medium |
| Priority | P3 |
| Status | Fixed |

librosa detected beats in the intro silence and the button replaced pending anchors, so the Step-1 pin and intro silence were lost. (Feature later removed.)

**Steps to reproduce:** _pending_

**Expected:** Alignment starts at the pin

**Observed:** Notes realigned from 0 s

**Root cause:** Detected grid anchored to the first detected beat; pin overwritten.

**Fixes:** [FIX-0134](../FIX_LOG.md#fix-0134) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-07-13 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Removed feature.

**Evidence:**

- commit efe11af2d4 Dynamic sync starts at the user's pinned first note, not at 0s
- found_in_version: fix efe11af2d4 (2026-07-13) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent ce687e2866, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-13 — Fixed: commit efe11af2d4

## BUG-0135

**Dynamic auto-sync rushed the chart ahead**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | efe11af2d4eb91b968c631629b6a2b3ec54f2b0a |
| Severity | Medium |
| Priority | P3 |
| Status | Fixed |

On a real song the beat-index mapping slipped on missed beats (~3 s rush), and the tracker's biased tempo (~184 on 175 BPM) over-compressed the opening ('começa logo a 177 quando deveria ser 175'). (Feature later removed.)

**Steps to reproduce:** _pending_

**Expected:** Chart follows the recording

**Observed:** Corrections rush the chart

**Root cause:** Trusted beat-tracker count and tempo.

**Fixes:** [FIX-0135](../FIX_LOG.md#fix-0135) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-07-13 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Removed feature.

**Evidence:**

- CLAUDE.md § Automatic sync was REMOVED (2026-08)
- commit 96c6524beb Dynamic sync v2: onset-refined tempo integration + confidence flags + per-bar BPM
- commit 98c3aab661 Dynamic sync: drive alignment by onset correspondence, not beat-tracker tempo
- found_in_version: fix 96c6524beb (2026-07-13) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent efe11af2d4, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-13 — Fixed: commit 96c6524beb, 98c3aab661

## BUG-0139

**Tempo detection read the wrong metrical level on dense mixes**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | e05cea0067b72ea3bb277401bb24422429b5e70d |
| Severity | Medium |
| Priority | P3 |
| Status | Fixed |

librosa read 123 BPM on a ~180 BPM metal recording from the full mix, so auto-sync proposals were nonsense. (Auto-sync later removed.)

**Steps to reproduce:** _pending_

**Expected:** Plausible BPM

**Observed:** Wrong BPM

**Root cause:** Full mix input.

**Fixes:** [FIX-0139](../FIX_LOG.md#fix-0139) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-07-16 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Removed feature.

**Evidence:**

- commit 26a8a1528a Detect beat/tempo on the isolated Demucs drum stem, not the full mix
- found_in_version: fix 26a8a1528a (2026-07-16) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent e05cea0067, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-16 — Fixed: commit 26a8a1528a

## BUG-0140

**Missing beatthis extra reported as 422 instead of 503**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | bd0dca16a64c53a958093481d682271a7826d391 |
| Severity | Low |
| Priority | P4 |
| Status | Fixed |

The lazy import failed inside the generic try → 422 'No module named beat_this'.

**Steps to reproduce:** _pending_

**Expected:** 503 naming the install

**Observed:** Confusing 422

**Root cause:** ImportError caught by generic handler.

**Fixes:** [FIX-0140](../FIX_LOG.md#fix-0140) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-07-17 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Error message.

**Evidence:**

- commit 9cc2351cd0 Fix /sync-from-stem: report a missing beatthis extra as 503, not 422
- found_in_version: fix 9cc2351cd0 (2026-07-17) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent bd0dca16a6, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-17 — Fixed: commit 9cc2351cd0

## BUG-0141

**Beat This! checkpoint download kept failing on the user's machine**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 9cc2351cd02337768b7954f355620a0bf130917e |
| Severity | Medium |
| Priority | P3 |
| Status | Fixed |

torch.hub choked on the JKU WebDAV link and the error hid the cause. (Feature later removed.)

**Steps to reproduce:** _pending_

**Expected:** Model loads

**Observed:** 'Could not load the checkpoint given the provided name'

**Root cause:** torch.hub downloader incompatible with the host.

**Fixes:** [FIX-0141](../FIX_LOG.md#fix-0141) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-07-17 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Removed feature.

**Evidence:**

- commit fc3866ed12 sync-from-stem: clearer error when the Beat This! checkpoint download fails
- commit ec158b79b7 sync-from-stem: download the Beat This! checkpoint ourselves (robust GET + cache)
- commit aa67ee55f5 sync-from-stem: surface the real checkpoint-load error, not just the fallback
- found_in_version: fix fc3866ed12 (2026-07-17) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 9cc2351cd0, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-17 — Fixed: commit fc3866ed12, ec158b79b7, aa67ee55f5

## BUG-0142

**Neural downbeat sync put the BPM off (wrong metrical level / mixed meter)**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | aa67ee55f598cda4bc068a07f92fe36944c7bef6 |
| Severity | Medium |
| Priority | P3 |
| Status | Fixed |

Bar-index→downbeat mapping compressed/stretched the tempo on a halved/doubled grid and drifted +58 s on a 2/4+4/4 tab ('longing'). (Feature later removed.)

**Steps to reproduce:** _pending_

**Expected:** Bars follow the recording

**Observed:** 'detects but the BPM is off'

**Root cause:** Index mapping assumed 1:1 bars to downbeats.

**Fixes:** [FIX-0142](../FIX_LOG.md#fix-0142) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-07-17 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Removed feature.

**Evidence:**

- commit 17fd285324 sync-from-stem: correct a wrong detected metrical level (fix halved/doubled BPM)
- commit b8113a347a sync-from-stem: align bars to downbeats by TIME, not index (fix meter-mismatch)
- found_in_version: fix 17fd285324 (2026-07-17) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent aa67ee55f5, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-17 — Fixed: commit 17fd285324, b8113a347a

## BUG-0143

**Synced in the app but desynced in Rocksmith after a tempo change with committed anchors**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer (in game) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 75913587eaeb5e7dcb29ea1038d9fc165327ae65 |
| Severity | High |
| Priority | P2 |
| Status | Closed |

Once any anchor stage was committed, changing the tempo made the rebuild differ from the preview by d·(r−1) on every note — a constant desync invisible in the viewer but plainly wrong in game.

**Steps to reproduce:** 

1. Drag/pin a correction and rebuild
2. Change the BPM/tempo and rebuild
3. Play in Rocksmith

**Expected:** The rebuilt chart equals the preview.

**Observed:** Every note shifted by a constant in game.

**Root cause:** The build computes W(x·s + S) while the viewer previews R(W(x·s_built + S_built)); the two do not commute, and committed anchors were not re-expressed in the new timeline.

**Fixes:** [FIX-0143](../FIX_LOG.md#fix-0143) (0.10.0-beta.1)

**Verified:** regression test(s) test_tempo_change_reexpresses_committed_anchors_in_the_new_timeline, test_committed_anchors_untouched_when_the_timeline_does_not_change pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-08-21 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Charts that looked synced played out of sync in game, on the ordinary workflow.

**Evidence:**

- CLAUDE.md § Manual drift correction (`sync_anchor_stages`)
- user quote (undated): 'no programa está sincronizado, no Rocksmith não'
- commit 45ce440b06 Fix chart synced in the app but desynced in Rocksmith (constant offset)
- found_in_version: the fix commit is an ancestor of cb00653 (the first public release, 0.10.0 beta 1, 2026-10-14), so the faulty code only existed in development builds before 0.10.0-beta.1
- found_in_build: 75913587ea is the parent of the first fix commit 45ce440b06 and still carries the code the fix changes

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-08-21 — Fixed: commit 45ce440b06
- 2026-08-21 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0144

**Viewer's scoreShift omitted lead_in_s, desyncing the rebuild by lead_in_s·(r−1)**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 75913587eaeb5e7dcb29ea1038d9fc165327ae65 |
| Severity | Medium |
| Priority | P2 |
| Status | Fixed |

web/app.js's scoreShift left out lead_in_s (and previewScale did not re-add it), so with an intro silence set a tempo change made the rebuild differ from the preview by a constant.

**Steps to reproduce:** _pending_

**Expected:** Preview equals rebuild.

**Observed:** A constant offset whenever a lead-in was set.

**Root cause:** scoreShift/previewScale did not match gp_pipeline's score_shift = max(offset_s, MIN_LEAD_S) + lead_in_s.

**Fixes:** [FIX-0144](../FIX_LOG.md#fix-0144) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-08-21 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Only with 'Silêncio inicial' set, but silently wrong in game.

**Evidence:**

- CLAUDE.md § Manual drift correction (`sync_anchor_stages`)
- CLAUDE.md: '`web/app.js`'s `scoreShift` omitted `lead_in_s` ... which desynced the rebuild by `lead_in_s·(r−1)` on its own'
- commit 45ce440b06 Fix chart synced in the app but desynced in Rocksmith (constant offset)
- found_in_version: the fix commit is an ancestor of cb00653 (the first public release, 0.10.0 beta 1, 2026-10-14), so the faulty code only existed in development builds before 0.10.0-beta.1
- found_in_build: 75913587ea is the parent of the first fix commit 45ce440b06 and still carries the code the fix changes

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-08-21 — Fixed: commit 45ce440b06

## BUG-0146

**Pending corrections listed in insertion order; a crossing correction was hidden**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 738e553c765a13a9907deceab8e7689dea24e4bb |
| Severity | Low |
| Priority | P4 |
| Status | Closed |

setAnchor appended, so the list read 'Correção 4: 196.93s' above 'Correção 5: 195.88s'; the numbering described an order the music does not have and a correction crossing another only surfaced as a build error.

**Steps to reproduce:** 

1. Add sync corrections out of chart order
2. Look at the pending corrections list

**Expected:** Corrections listed in chart order with crossings flagged.

**Observed:** Insertion order; no sign of a crossing until 'Aplicar e reconstruir' failed.

**Root cause:** setAnchor appended instead of sorting by chart time.

**Fixes:** [FIX-0146](../FIX_LOG.md#fix-0146) (0.10.0-beta.1)

**Verified:** commit 8afdadb: 'Verified in a real browser: anchors added as (196.93, 195.88, 10.00) store and render as 10.00 / 195.88 / 196.93, and a genuine crossing ... flags exactly one row.' (by the developer (manual check))

**Resolved:** 2026-08-22 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: List order and late error only; timing was unaffected.

**Evidence:**

- CLAUDE.md § Manual drift correction (Pending anchors are kept in CHART order)
- commit 8afdadb message: 'Reported with a screenshot'
- commit 8afdadbafa Keep pending corrections in chart order and flag one that crosses another
- found_in_version: the fix commit is an ancestor of cb00653 (the first public release, 0.10.0 beta 1, 2026-10-14), so the faulty code only existed in development builds before 0.10.0-beta.1
- found_in_build: 738e553c76 is the parent of the first fix commit 8afdadbafa and still carries the code the fix changes

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-08-22 — Fixed: commit 8afdadbafa
- 2026-08-22 — Verified: manual
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0151

**Sync analysis flooded the score with corrections on real audio**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 246ed7b5d737048b4e988e5104a186f03c72b9bf |
| Severity | Medium |
| Priority | P3 |
| Status | Fixed |

On the first real run the analysis reported dozens of jumps and over a hundred anchors; mis-snapped onsets looked like jumps. (Feature later removed.)

**Steps to reproduce:** _pending_

**Expected:** Only sustained jumps reported

**Observed:** Unreadable score with 100+ anchors

**Root cause:** Thresholds tuned on clean synthetic data.

**Fixes:** [FIX-0151](../FIX_LOG.md#fix-0151) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-08-22 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Removed feature.

**Evidence:**

- commit 997951ed26 Sync analysis: require a jump to be SUSTAINED, so real audio stops flooding the score with correction points
- found_in_version: fix 997951ed26 (2026-08-22) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 246ed7b5d7, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-08-22 — Fixed: commit 997951ed26

## BUG-0153

**"Corrigir daqui" always read a higher tempo and ran the chart fast**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | eda3d2339598a04721a00aa06eff03dba7ebd04c |
| Severity | High |
| Priority | P2 |
| Status | Closed |

The per-point re-tempo tool kept returning faster tempos and, applied repeatedly, compounded (x0.9 → x0.81 → x0.73) so the chart ran away. Three defects pushed the same way.

**Steps to reproduce:** 

1. Click a note in 'Corrigir daqui' mode where the chart starts drifting
2. Repeat on an already corrected passage

**Expected:** A factor relative to the chart on screen; x1.000 on a passage already in time.

**Observed:** Always a higher tempo; repeated use compounded.

**Root cause:** /detect-tempo measured against the GP header tempo instead of the displayed chart tempo; librosa's beat_track prior defaulted to start_bpm=120; suggest_tempo_scale broke half/double ties with asymmetric abs(scale-1).

**Fixes:** [FIX-0153](../FIX_LOG.md#fix-0153) (0.10.0-beta.1)

**Verified:** regression test(s) test_detect_tempo_measures_against_the_chart_bpm_not_the_header, test_suggest_tempo_scale_does_not_favour_the_faster_reading_on_a_tie pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-08-23 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: The recommended sync tool produced wrong corrections.

**Evidence:**

- CLAUDE.md § The recommended workflow: "Corrigir daqui" (`newbeat` mode, `/detect-tempo`)
- user quote (undated): 'dá sempre tempo maior e fica muito acelerado'
- commit 72ba5c049b Fix "Corrigir daqui" always reading a higher tempo and running the chart fast
- found_in_version: the fix commit is an ancestor of cb00653 (the first public release, 0.10.0 beta 1, 2026-10-14), so the faulty code only existed in development builds before 0.10.0-beta.1
- found_in_build: eda3d23395 is the parent of the first fix commit 72ba5c049b and still carries the code the fix changes

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-08-23 — Fixed: commit 72ba5c049b
- 2026-08-23 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0177

**UI said the MP3 could come from Songsterr, whose audio does not match the times**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 29f9d8845ebbf9924c216b1580ffc61350c96ac8 |
| Severity | Low |
| Priority | P4 |
| Status | Fixed |

UI, README and docs said the MP3 could come 'from the video or from Songsterr'; Songsterr's download is a different recording and would drift.

**Steps to reproduce:** _pending_

**Expected:** MP3 from the same YouTube video

**Observed:** Wrong guidance

**Root cause:** Incorrect assumption.

**Fixes:** [FIX-0177](../FIX_LOG.md#fix-0177) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-09-25 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Misleading instructions.

**Evidence:**

- commit c80dd0a680 Songsterr sync: an optional extra, and the MP3 must come from the video
- found_in_version: fix c80dd0a680 (2026-09-25) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 29f9d8845e, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-09-25 — Fixed: commit c80dd0a680

## BUG-0189

**Any sync correction dropped bend curves, fingering and pick direction**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 65527dd20cec9e4f9742eac458e76a7daf4c6af1 |
| Severity | High |
| Priority | P2 |
| Status | Closed |

The sync warp rebuilt each note from a hand-picked field list, so the moment a song had any sync correction every unnamed field — bend curves, fingering, pick direction, unpitched slide-outs — was lost (_strip_mute_techniques had the same shape).

**Steps to reproduce:** _pending_

**Expected:** Every note field survives a correction.

**Observed:** Those fields vanished from the built chart.

**Root cause:** _warp_parsed_track constructed fresh TabNote objects instead of dataclasses.replace.

**Fixes:** [FIX-0189](../FIX_LOG.md#fix-0189) (0.10.0-beta.1)

**Verified:** regression test(s) test_a_sync_correction_keeps_every_note_field_and_moves_the_lyric_notes pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-09-28 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Silent loss of chart content on any corrected song.

**Evidence:**

- CLAUDE.md § Manual drift correction (A local stretch re-inflates sustain)
- commit deb168f message: 'Found on the way: the sync warp rebuilt notes field by field and dropped bend curves, fingering and pick direction'
- commit deb168f158 Lyrics from the score: Songsterr tabs bring theirs, and syllables follow the vocal line
- found_in_version: the fix commit is an ancestor of cb00653 (the first public release, 0.10.0 beta 1, 2026-10-14), so the faulty code only existed in development builds before 0.10.0-beta.1
- found_in_build: 65527dd20c is the parent of the first fix commit deb168f158 and still carries the code the fix changes

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-09-28 — Fixed: commit deb168f158
- 2026-09-28 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0199

**Bar sync against another track and the synthesized source ignored the intro silence**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 3a3357b8a6bc6ff9e1a1a383bdf6a38d08cd03a8 |
| Severity | Medium |
| Priority | P3 |
| Status | Fixed |

arrangementPreviewScale and synthesizeArrangement left out leadInBuilt, which previewScale adds, so with a 'Silêncio inicial' the other track's bar and the synthesized notes sat that much early.

**Steps to reproduce:** _pending_

**Expected:** Same clock as the score.

**Observed:** Early by lead_in_s.

**Root cause:** leadInBuilt missing from two preview functions.

**Fixes:** [FIX-0199](../FIX_LOG.md#fix-0199) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-09-29 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Only with an intro silence set.

**Evidence:**

- CLAUDE.md § Adjusting the lyric beside the score ('Two lead-in slips surfaced on the way')
- commit 4ed26393c4 Lyrics timed on the score follow the chart's sync corrections
- found_in_version: the fix commit is an ancestor of cb00653 (the first public release, 0.10.0 beta 1, 2026-10-14), so the faulty code only existed in development builds before 0.10.0-beta.1
- found_in_build: 3a3357b8a6 is the parent of the first fix commit 4ed26393c4 and still carries the code the fix changes

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-09-29 — Fixed: commit 4ed26393c4

## BUG-0202

**Sync view clamped a negative start to 0 and a rebuild then lost the file's sync**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 2a24a6e0bcbc5e1c5caf42c5f7bb1cd41b5dd69f |
| Severity | High |
| Priority | P2 |
| Status | Closed |

setOffsetLive in the sync view clamped offset_s at 0, so for a .gp whose bar 1 is 2.15 s before the recording the preview padded the audio by 2 s instead of 4.15 s, every note showed 2.15 s late, 'offset' showed as pending and 'Aplicar e reconstruir' sent offset_s 0.

**Steps to reproduce:** 

1. Open a project built from a .gp with bar 1 before the recording (offset_s -2.15)
2. Look at the Partitura page
3. Press 'Aplicar e reconstruir'

**Expected:** The preview matches the build and nothing is pending.

**Observed:** Notes drawn 2.15 s late (Acoustic first note at 3.20 s instead of 1.05 s), offset pending, and a rebuild sent offset_s 0.

**Root cause:** web/app.js setOffsetLive clamped the offset at 0 while the pipeline accepts down to -60 s.

**Fixes:** [FIX-0202](../FIX_LOG.md#fix-0202) (0.10.0-beta.1)

**Verified:** docs/TESTES-NO-JOGO.md Confirmado: negative start (−2,15 s) 'a bater na página de sincronização' — Daughtry "September" (2026-09-30), 'Precisou de 39a5aa4' (by the maintainer)

**Resolved:** 2026-09-30 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: A rebuild silently discarded the file's sync.

**Evidence:**

- CLAUDE.md § The generation path (Guitar Pro 8 audio sync)
- CLAUDE.md: 'setOffsetLive did, so the preview padded the audio by 2 s instead of 4.15 s and a rebuild sent offset_s 0'
- docs/TESTES-NO-JOGO.md: 'Precisou de 39a5aa4'
- commit 39a5aa4911 Sync view keeps a negative GP start (bar 1 before the recording)
- found_in_version: the fix commit is an ancestor of cb00653 (the first public release, 0.10.0 beta 1, 2026-10-14), so the faulty code only existed in development builds before 0.10.0-beta.1
- found_in_build: 2a24a6e0bc is the parent of the first fix commit 39a5aa4911 and still carries the code the fix changes

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-09-30 — Fixed: commit 39a5aa4911
- 2026-09-30 — Verified: confirmed by user
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0207

**Rebuild committed only the on-screen chart's pending sync; other tabs' edits vanished**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 581429e52d3f574967f7b61418f1ac65097979f4 |
| Severity | High |
| Priority | P2 |
| Status | Closed |

Only the chart on screen was sent to the rebuild, so any other tab's pending corrections silently disappeared.

**Steps to reproduce:** 

1. Make pending sync corrections on two charts
2. Press 'Aplicar e reconstruir' from one of them

**Expected:** Every chart's pending sync is committed.

**Observed:** Corrections on the other tabs were lost.

**Root cause:** applyAll sent only the current arrangement's tempo/anchors.

**Fixes:** [FIX-0207](../FIX_LOG.md#fix-0207) (0.10.0-beta.1)

**Verified:** regression test(s) test_a_rebuild_commits_every_charts_pending_sync_not_only_the_one_on_screen pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-09-30 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Silent loss of the user's uncommitted sync work.

**Evidence:**

- CLAUDE.md § The main chart for sync ("Pista principal", `sync_main`)
- CLAUDE.md: 'before, only the chart on screen was sent and any other tab's pending corrections silently disappeared'
- commit e814045b31 Louder tones, a main chart for sync, and dropping the previous version
- found_in_version: the fix commit is an ancestor of cb00653 (the first public release, 0.10.0 beta 1, 2026-10-14), so the faulty code only existed in development builds before 0.10.0-beta.1
- found_in_build: 581429e52d is the parent of the first fix commit e814045b31 and still carries the code the fix changes

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-09-30 — Fixed: commit e814045b31
- 2026-09-30 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0252

**A double click on "Apply and rebuild" created two versions**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | _pending_ |
| Build / commit | cb00653bedba4cd2f9070ceb2acb8e925c883319 |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

applyAll ran once per click event with no guard, so a double click forked two rebuilt versions of the project.

**Steps to reproduce:** 

1. Open a project with pending edits
2. Double-click "Aplicar e reconstruir"

**Expected:** One rebuild.

**Observed:** Two rebuilds were sent (two new versions).

**Root cause:** applyAll was not guarded against re-entry.

**Fixes:** [FIX-0252](../FIX_LOG.md#fix-0252) (0.10.0-beta.2)

**Verified:** commit 2d0b87ef91: 'Checked with Playwright against the previous app.js ... a double click sent 2 rebuilds before and 1 now.' (by the developer (manual check))

**Resolved:** 2026-10-14 · **Closed:** 2026-10-15

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Duplicate versions and builds; the extra version could be deleted.

**Evidence:**

- CHANGELOG.en.md 0.10.0 beta 2 — Fixed: "A double click on \"Apply and rebuild\" created two versions."
- commit 2d0b87ef91: "applyAll runs once per click (a double click forked two versions)"
- found_in_version pending: faulty code present at cb00653 (beta 1); found by an audit, detection date not documented

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-10-14 — Fixed: commit 2d0b87ef91
- 2026-10-14 — Verified: manual
- 2026-10-15 — Closed: released in 0.10.0-beta.2

## BUG-0255

**Negative intro silence was accepted and misaligned sync corrections after a tempo change**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | _pending_ |
| Build / commit | cb00653bedba4cd2f9070ceb2acb8e925c883319 |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

/jobs/gp accepted a negative lead_in_s; the build clamps it, but the rebuild's anchor re-expression used the raw value, so after a tempo change the committed corrections no longer matched the build.

**Steps to reproduce:** 

1. Create a GP project with a negative "Silêncio inicial"
2. Commit a sync correction, then change the tempo and rebuild

**Expected:** The negative value is refused; anchors stay aligned.

**Observed:** Accepted; corrections out of line after the tempo change.

**Root cause:** lead_in_s was not validated and the anchor re-expression computed the score shift without the build's clamping.

**Fixes:** [FIX-0255](../FIX_LOG.md#fix-0255) (0.10.0-beta.2)

**Verified:** regression test(s) test_a_negative_intro_silence_is_refused_and_the_shift_matches_the_build pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-10-14 · **Closed:** 2026-10-15

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Desynced corrections in an uncommon input case.

**Evidence:**

- CHANGELOG.en.md 0.10.0 beta 2 — Fixed: "A negative intro silence was accepted when creating a project ..."
- commit 2d0b87ef91: "/jobs/gp refuses a negative lead_in_s, and the anchor re-expression uses the build's clamped score shift (_score_shift)"
- found_in_version pending: faulty code present at cb00653 (beta 1); found by an audit, detection date not documented

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-10-14 — Fixed: commit 2d0b87ef91
- 2026-10-14 — Verified: automated
- 2026-10-15 — Closed: released in 0.10.0-beta.2

## BUG-0276

**A sync mode was selected on entry, so the first click on a note re-timed the song**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | _pending_ |
| Build / commit | 8494322e3f34a7427e9ed710687f2001493e9bb4 |
| Severity | Medium |
| Priority | P3 |
| Status | Fixed |

"Corrigir daqui" (newbeat) was the default mode, so opening a project and clicking a note re-timed the song from there.

**Steps to reproduce:** 

1. Open a project
2. Click a note on the score

**Expected:** The click only selects or moves the cursor.

**Observed:** The song was re-timed from that note.

**Root cause:** let syncMode = 'newbeat' at load.

**Fixes:** [FIX-0276](../FIX_LOG.md#fix-0276) (0.10.0-beta.7)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-10-15 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Unwanted pending sync edits from an ordinary click; undoable.

**Evidence:**

- CLAUDE.md § The recommended workflow: "Corrigir daqui" (`newbeat` mode, `/detect-tempo`): "since 2026-10-15 no mode is ... because 'sempre que entro … existe um modo que está selecionado e não devia'"
- user quote (undated): 'sempre que entro … existe um modo que está selecionado e não devia'
- CHANGELOG.en.md 0.10.0 beta 7 — Fixed: "No mode is selected when a project opens. ..."
- commit cfe40199df Experimental automatic sync with a variable tempo; no mode selected on entry
- found_in_build: 8494322 web/app.js line 1531 let syncMode = 'newbeat'
- found_in_version pending: the version used and the date are not stated

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-10-15 — Fixed: commit cfe40199df

## BUG-0285

**Recording attacks (and the auto-sync) sat late by the intro silence**

| | |
|---|---|
| Detected | 2026-10-16 |
| Reported by | the maintainer |
| Found in | 0.10.0-beta.9 |
| Build / commit | ba8f5fc7180b87c6d1da0b7f89ea321b6ca593e2 |
| Severity | Medium |
| Priority | P2 |
| Status | Closed |

The decoded recording starts with the build's "Silêncio inicial", but the attacks overlay and the automatic sync converted recording seconds with playheadDisplay(0) alone, so every attack was drawn lead_in_s late and the auto-sync "corrected" charts that were in time.

**Steps to reproduce:** 

1. Build a project with a 0.5 s intro silence
2. Detect the recording's attacks

**Expected:** In-sync notes match the attack ticks.

**Observed:** "com as bolas no meio dos traços, a música estava sincronizada" (0 of 16 notes matched).

**Root cause:** Missing leadInBuilt in the recording-to-display conversion (playheadDisplay(0) instead of playheadDisplay(s + leadInBuilt)).

**Fixes:** [FIX-0285](../FIX_LOG.md#fix-0285) (0.10.0-beta.10)

**Verified:** CLAUDE.md: 'With Playwright on the invented riff rebuilt with a 0.5 s lead-in: 0 of 16 notes matched before, 15 of 16 after' (by the developer (manual check))

**Resolved:** 2026-10-16 · **Closed:** 2026-10-16

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: A misleading overlay and wrong auto-sync corrections for projects with a lead-in.

**Evidence:**

- CLAUDE.md § The recording's attacks over the score ("Ataques da gravação"): "Seconds of the recording FILE become display time through recordingDisplay ..."
- user quote (undated): 'com as bolas no meio dos traços, a música estava sincronizada'
- CHANGELOG.en.md 0.10.0 beta 10 — Fixed: "Recording attacks with an intro silence ..."
- commit e204d69872 Recording attacks: count the intro silence; drop stale stems on reload
- detected 2026-10-16: the attacks overlay was added in 4a6a026 (2026-10-16) and fixed in e204d69 the same day
- found_in_version: the overlay first shipped in beta 9 (ba8f5fc) and was fixed before beta 10; the only published version with it

**History:**

- 2026-10-16 — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-10-16 — Fixed: commit e204d69872
- 2026-10-16 — Verified: manual
- 2026-10-16 — Closed: released in 0.10.0-beta.10

## BUG-0287

**Reload GP with the file's own audio kept the old recording's stems and tone detection**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | _pending_ |
| Build / commit | ba8f5fc7180b87c6d1da0b7f89ea321b6ca593e2 |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

A /reload-gp that took the new file's embedded audio dropped nothing measured on the old recording, so its separated guitar kept feeding "Ataques da gravação" and the stem audio sources from a recording the chart no longer played against.

**Steps to reproduce:** 

1. Reload a GP file that carries its own audio into a project with separated stems
2. Detect attacks or pick a stem source

**Expected:** Stems and tone detection of the old recording are dropped.

**Observed:** The old recording's stems were still used.

**Root cause:** /reload-gp did not clear stems*, detected_tones and tone_detection_* when it replaced the recording.

**Fixes:** [FIX-0287](../FIX_LOG.md#fix-0287) (0.10.0-beta.10)

**Verified:** regression test(s) test_what_was_measured_on_the_old_recording_is_dropped_with_it pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-10-16 · **Closed:** 2026-10-16

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Wrong analysis source after a reload; re-separating fixed it.

**Evidence:**

- CLAUDE.md § Reloading the GP file (`/jobs/{id}/reload-gp`): "What was measured on the old recording goes with it ..."
- CHANGELOG.en.md 0.10.0 beta 10 — Fixed: "Reload GP file with the file's own audio ..."
- commit e204d69872 Recording attacks: count the intro silence; drop stale stems on reload
- found_in_version pending: detection date not documented

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-10-16 — Fixed: commit e204d69872
- 2026-10-16 — Verified: automated
- 2026-10-16 — Closed: released in 0.10.0-beta.10

## BUG-0291

**"Song start" after an automatic sync moved only the first stretch of the song**

| | |
|---|---|
| Detected | 2026-10-17 |
| Reported by | user report |
| Found in | _pending_ |
| Build / commit | 8b5b49a54bb03d085716b529abf41e671788c2fa |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

With several pending anchors (an auto-sync, taps, a bar alignment) the "Início" field and the guided first-note flow moved only the first note's anchor, so only the span up to the next anchor stretched.

**Steps to reproduce:** 

1. Run "Sincronizar automaticamente"
2. Change "Início da música"

**Expected:** The whole chart shifts.

**Observed:** "it only adjusts the first section"

**Root cause:** The start edit wrote one anchor at the first note, which in a multi-anchor warp only reaches the next anchor.

**Fixes:** [FIX-0291](../FIX_LOG.md#fix-0291) (0.10.0-beta.12)

**Verified:** CLAUDE.md: 'with Playwright on the invented "Deriva" project with the 31 anchors a real auto-sync left: "Início" +1 s moved all 277 notes and 32 bars by the same 1.002 s (the old code: most by 0)' (by the developer (manual check))

**Resolved:** 2026-10-17 · **Closed:** 2026-10-17

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: The start could not be moved after an auto-sync without breaking the first section.

**Evidence:**

- CLAUDE.md § Per-arrangement sync (`arrangement_sync`): "With other pending anchors the start moves the WHOLE chart (planStartShift, 2026-10-17: ...)"
- user quote (2026-10-17): 'when you do the sync automatically button and then want to go back and move the intro it only adjusts the first section'
- CHANGELOG.en.md 0.10.0 beta 12 — Fixed: "\"Song start\" after the automatic sync ..."
- commit d2c156a80e Song start after an auto-sync shifts the whole chart, not the first stretch
- found_in_version pending: faulty code present at d73ecc0 (beta 10) and 8b5b49a (beta 11)

**History:**

- 2026-10-17 — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-10-17 — Fixed: commit d2c156a80e
- 2026-10-17 — Verified: manual
- 2026-10-17 — Closed: released in 0.10.0-beta.12

## BUG-0295

**Dragging a selection stretched the notes before it when another correction was pending**

| | |
|---|---|
| Detected | 2026-10-17 |
| Reported by | found while answering a user report (r/rocksmith) |
| Found in | 0.10.0-beta.15 |
| Build / commit | c499bc4 |
| Severity | Medium |
| Priority | P2 |
| Status | Closed |

In "Drag" mode, dragging a multi-note selection added only two anchors (the selection's first and last note). With another pending correction — typically the lone "Song start" anchor, a uniform shift — the notes between that correction and the selection were dragged part of the way along, and notes after the selection lost the correction.

**Steps to reproduce:** 

1. Open a project, set "Song start" +1 s (one pending anchor)
2. Select notes in the middle of the chart (Shift+click)
3. In "Drag" mode drag one selected note +0.5 s

**Expected:** Only the selected notes move by 0.5 s; every other note stays where it was shown.

**Observed:** Notes between the start and the selection moved +0.17 s and +0.33 s (Node check of the old two-anchor rule); notes after a mid-song selection went back to their unshifted time.

**Root cause:** The multi-anchor warp is piecewise linear and the identity outside its range, so two new anchors next to a lone one interpolated between them and dropped the uniform shift beyond the last one.

**Fixes:** [FIX-0295](../FIX_LOG.md#fix-0295) (0.10.0-beta.16)

**Verified:** Node check of planBlockMove (three cases) and Playwright on an invented project, PT/EN: the selection moved by exactly the drag, every other note by 0 (by the developer (manual check))

**Resolved:** 2026-10-17 · **Closed:** 2026-10-17

**Evidence:**

- user report, r/rocksmith, 2026-10-17: 'knowing how to select all the notes after the cursor would be cool … then being able to move all the notes'
- Node check of buildTimeWarp with the old rule: [1, 1.167, 1.333, 1.5, …] instead of [1, 1, 1, 1.5, …]

**History:**

- 2026-10-17 — Open: reported
- 2026-10-17 — Fixed: commit 5a830bde54
- 2026-10-17 — Verified: manual
- 2026-10-17 — Closed: released in 0.10.0-beta.16

## BUG-0301

**The "Cursor" snap option snapped every drag to the song's last beat**

| | |
|---|---|
| Detected | 2026-10-18 |
| Reported by | code review (Claude, on the maintainer's request) |
| Found in | 0.11.0-beta.2 |
| Build / commit | f64c45e8e176c44bd87c7c7866f741330b443011 |
| Severity | Medium |
| Priority | P2 |
| Status | Fixed |

Choosing "Cursor" in the snap list set snapDiv to NaN, so the grid was the last beat only and every drag landed there.

**Steps to reproduce:** 

1. Pick "Cursor" in the snap list
2. Drag a note in "Drag"

**Expected:** The note lands on the playhead.

**Observed:** snapDiv was NaN; beatGridTimes returned only the last beat.

**Root cause:** The handler kept only 'bars' as a non-number value.

**Fixes:** [FIX-0301](../FIX_LOG.md#fix-0301) (0.11.0-beta.3)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-10-18 · **Closed:** _pending_

**Evidence:**

- code review of the whole codebase (six reviewers), confirmed by reading the code; Playwright: picking Cursor sets snapDiv to 'cursor'

**History:**

- 2026-10-18 — Open: reported
- 2026-10-18 — Fixed: commit f907982d0f

## BUG-0303

**A sync tool used beside a lone "Song start" folded the chart and failed the rebuild**

| | |
|---|---|
| Detected | 2026-10-18 |
| Reported by | code review (Claude, on the maintainer's request) |
| Found in | 0.11.0-beta.2 |
| Build / commit | f64c45e8e176c44bd87c7c7866f741330b443011 |
| Severity | High |
| Priority | P1 |
| Status | Verified |

Drag, Mark at cursor, Move following, Correct from here and taps added anchors without pinning the chart's ends; the multi-anchor warp is identity outside its range, so the notes after lost the start shift and the bars before the first note ran backwards, and the rebuild failed with "beats must be in chronological order". The server also accepted two corrections taking two notes to the same instant.

**Steps to reproduce:** 

1. Move the song start by -1.5 s
2. Pick "Drag" and drag a later note
3. Apply and rebuild

**Expected:** Only the dragged region changes; the rebuild completes.

**Observed:** Playwright on the old code: the last note lost the shift, one beat folded, the rebuild failed.

**Root cause:** The tools added one or two anchors with no end pins (only planBarRetempo/planStartShift/the group drag pinned them); _check_anchor_order allowed equal targets.

**Fixes:** [FIX-0303](../FIX_LOG.md#fix-0303) (0.11.0-beta.3)

**Verified:** tests/test_gp_pipeline.py::test_corrections_that_collapse_or_fold_the_chart_are_refused_by_name passed, and fails with the fix reverted (by pytest (the test fails on the old code))

**Resolved:** 2026-10-18 · **Closed:** _pending_

**Evidence:**

- code review of the whole codebase (six reviewers), confirmed by reading the code; Playwright on an invented GP5 built for real: start -1.5 s, a drag and Move following leave every beat in order and the rebuild completes (the old code failed it)

**History:**

- 2026-10-18 — Open: reported
- 2026-10-18 — Fixed: commit 9ef6aadeff
- 2026-10-18 — Verified: its test passes and fails on the old code

## BUG-0339

**A section marker does not follow a sync correction made in the same rebuild**

| | |
|---|---|
| Detected | 2026-10-19 |
| Reported by | Claude, while fixing BUG-0338 |
| Found in | 0.11.0-beta.4 |
| Build / commit | _pending_ |
| Severity | Medium |
| Priority | P3 |
| Status | Verified |

Section markers (section_overrides) are stored in the chart's clock and sent as stored, while the score draws them through the pending tempo/anchors and the notes move with them at the rebuild — the same gap as BUG-0338.

**Steps to reproduce:** 

1. A section at 10 s, first note at 2 s
2. Pending sync: first note +1 s
3. Apply and rebuild

**Expected:** The section at 11 s, as the score showed it.

**Observed:** First note 3.0 s, section still 10.0 s (Playwright on an invented project, 2026-10-19).

**Root cause:** section_overrides are sent in the stored chart clock; gp_pipeline uses them without the per-chart warp, and stored overrides were never re-sent after a later correction.

**Fixes:** [FIX-0339](../FIX_LOG.md#fix-0339) (0.11.1-beta.1)

**Verified:** Playwright, invented GP5 + real rebuilds: a +1 s pending correction moved the first note 2.0 → 3.0 s and the edited section 10 → 11 s; a second +1 s with the sections untouched moved it to 12 s; "+ Adicionar no cursor" drawn exactly on the cursor; untouched GP sections still sent as null (by the developer (Playwright))

**Resolved:** 2026-10-19 · **Closed:** _pending_

**Evidence:**

- Playwright, invented GP5: drawn at 11.0 before the rebuild, built at 10.0 with notes moved +1.0 s

**History:**

- 2026-10-19 — Open: reported
- 2026-10-19 — In Progress: the maintainer asked for the fix
- 2026-10-19 — Fixed: commit f99ff718dd
- 2026-10-19 — Verified: checked in the browser with real rebuilds
