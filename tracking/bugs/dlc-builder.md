<!-- Generated from tracking/bugs.json by `python -m tools.tracking render`. Do not edit by hand: edit the JSON and render again. -->

# Bugs: dlc-builder

The DLC Builder bundle: XML, .rs2dlc. Index: [BUG_LOG.md](../BUG_LOG.md).

## BUG-0001

**In-game song ended seconds in: only one phrase iteration was written**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer (in game) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | c122c200f038fa96488ed52c8ad209fe63311c4c |
| Severity | Critical |
| Priority | P1 |
| Status | Closed |

The Song2014 XML carried a single phrase iteration at the start beat. Rocksmith ends the song at the last phrase iteration, so the song finished seconds in with the note highway frozen.

**Steps to reproduce:** _pending_

**Expected:** The song plays to its end.

**Observed:** The song finished seconds in with the note highway frozen.

**Root cause:** The writer emitted a single phraseIteration at the start beat; Rocksmith ends playback at the last phraseIteration.

**Fixes:** [FIX-0001](../FIX_LOG.md#fix-0001) (0.10.0-beta.1)

**Verified:** regression test(s) test_phrase_structure_marks_song_end pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-06-12 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: The song could not be played in game.

**Evidence:**

- CLAUDE.md § Hard constraints (these have bitten us — keep them) — 'Phrase structure ends the song'
- commit fc6c5b64db Fix in-game early song end: emit COUNT/default/END phrases and noguitar closer
- found_in_version: the fix commit fc6c5b64db is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent c122c200f0

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-06-12 — Fixed: commit fc6c5b64db
- 2026-06-12 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0003

**DLC Builder import crashed (NullReferenceException) on missing arrangementProperties**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | pending (not recorded) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 56aa3d81b77878cebbc96c6a56231698b2e20bce |
| Severity | High |
| Priority | P2 |
| Status | Closed |

DLC Builder's ArrangementProperties.ReadXml dereferences all 32 attributes without null checks, so a Song2014 XML missing any of them crashed the import with 'Object reference not set to an instance of an object'.

**Steps to reproduce:** _pending_

**Expected:** The XML imports into DLC Builder.

**Observed:** The import failed with a NullReferenceException.

**Root cause:** The writer did not emit the full set of 32 arrangementProperties attributes.

**Fixes:** [FIX-0003](../FIX_LOG.md#fix-0003) (0.10.0-beta.1)

**Verified:** regression test(s) test_arrangement_properties_has_all_dlc_builder_attributes pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-06-12 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: The DLC Builder bundle could not be imported.

**Evidence:**

- CLAUDE.md § Hard constraints (these have bitten us — keep them) — 'Song2014 XML completeness for DLC Builder.'
- commit ef069eb706 Emit all 32 arrangementProperties attributes required by DLC Builder
- found_in_version: the fix commit ef069eb706 is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent 56aa3d81b7

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-06-12 — Fixed: commit ef069eb706
- 2026-06-12 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0004

**Song2014 XML lacked elements DLC Builder's schema expects**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | pending (not recorded) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 8d253521201a0c80a4580359c9e19d6933e04367 |
| Severity | High |
| Priority | P2 |
| Status | Closed |

The arrangement XML omitted required Song2014 elements (part, sort names, albumArt, crowdSpeed, linkedDiffs, phraseProperties, events, transcriptionTrack…) and used a wrong arrangementProperties attribute set, so it did not match what Rocksmith2014.NET/DLC Builder read.

**Steps to reproduce:** _pending_

**Expected:** XML in the schema-defined order with every required element

**Observed:** XML missing schema-required elements and attributes

**Root cause:** Writer emitted a partial Song2014 structure that did not follow Rocksmith2014.NET's schema.

**Fixes:** [FIX-0004](../FIX_LOG.md#fix-0004) (0.10.0-beta.1)

**Verified:** A written XML carries every element the fix added and the 32 arrangementProperties attributes DLC Builder's reader dereferences (by the developer (pytest))

**Resolved:** 2026-06-12 · **Closed:** 2026-10-20

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: DLC Builder import depends on the XML structure; no workaround inside RockForge.

**Evidence:**

- commit bd5c107eca Fix Song2014 XML schema to match Rocksmith2014.NET / DLC Builder expectations
- found_in_version: fix bd5c107eca (2026-06-12) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 8d25352120, where the code the fix changes is present
- pytest 2026-10-20: passes; full suite passes
- Mutation: dropping <events> from the writer fails the element test

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-06-12 — Fixed: commit bd5c107eca
- 2026-10-20 — Verified: regression check re-run (pytest/Playwright)
- 2026-10-20 — Closed: released in 0.10.0-beta.1

## BUG-0006

**In-game chart re-zeroed despite the lead-in (offset left at 0)**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | pending (not recorded) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 2cb35ecf5febc362a7cffbd51fdc0f3a33b04aa8 |
| Severity | High |
| Priority | P2 |
| Status | Closed |

DLC Builder/EOF use <offset> to detect a lead-in; leaving it 0 while <startBeat> reflected a shifted lead-in re-zeroed the timeline, so the in-game chart started at 0 despite the silence.

**Steps to reproduce:** _pending_

**Expected:** Chart keeps its lead-in

**Observed:** Chart starts at 0 in game, out of sync with the padded audio

**Root cause:** <offset> was not set to -startBeat.

**Fixes:** [FIX-0006](../FIX_LOG.md#fix-0006) (0.10.0-beta.1)

**Verified:** regression test(s) test_offset_matches_negated_start_beat pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-06-13 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Charts built through DLC Builder were out of sync.

**Evidence:**

- commit b6abc8bfb0 Set Song2014 offset = -startBeat to preserve sync lead-in
- found_in_version: fix b6abc8bfb0 (2026-06-13) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 2cb35ecf5f, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-06-13 — Fixed: commit b6abc8bfb0
- 2026-06-13 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0007

**DLC Builder import crashed at offset 0: no room for the count-in phrase**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | pending (not recorded) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 14f973fece9f45d81e14f907e1e16d563c474d77 |
| Severity | High |
| Priority | P2 |
| Status | Closed |

With offset 0 the chart started at time 0 and DLC Builder's PhraseGenerator failed with 'no room for an empty phrase before the arrangement content starts'.

**Steps to reproduce:** _pending_

**Expected:** Import succeeds regardless of offset

**Observed:** DLC Builder import error at offset 0

**Root cause:** No minimum lead-in before the first note.

**Fixes:** [FIX-0007](../FIX_LOG.md#fix-0007) (0.10.0-beta.1)

**Verified:** The first note is at least MIN_LEAD_S (2 s) in and the pad is reported (by the developer (pytest))

**Resolved:** 2026-06-13 · **Closed:** 2026-10-20

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Import failed for songs starting at 0 s; workaround was a manual offset.

**Evidence:**

- commit 95d2d20cc1 Fix GP sync: align score to recording, don't pad audio equally
- found_in_version: fix 95d2d20cc1 (2026-06-13) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 14f973fece, where the code the fix changes is present
- pytest 2026-10-20: passes; full suite passes
- Mutation: MIN_LEAD_S = 0 fails both tests

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-06-13 — Fixed: commit 95d2d20cc1
- 2026-10-20 — Verified: regression check re-run (pytest/Playwright)
- 2026-10-20 — Closed: released in 0.10.0-beta.1

## BUG-0028

**DLC Builder build failed for want of a .phrase-levels file**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | pending (not recorded) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 79e4c614dafa72c13558b3e92d863cb20cb3a8f9 |
| Severity | High |
| Priority | P2 |
| Status | Closed |

DLC Builder's PhraseLevelComparer threw on a fresh project's first build. A pre-created .phrase-levels folder (and its .keep) collided with the FILE DLC Builder writes and was reverted; DLC Builder then threw FileNotFoundException reading .phrase-levels.

**Steps to reproduce:** _pending_

**Expected:** First build succeeds

**Observed:** DLC Builder build throws DirectoryNotFound/FileNotFound around .phrase-levels

**Root cause:** .phrase-levels is a JSON file DLC Builder reads from the project directory; the bundle shipped none (the first attempts wrongly created a directory).

**Fixes:** [FIX-0028](../FIX_LOG.md#fix-0028) (0.10.0-beta.1)

**Verified:** regression test(s) test_write_rs2dlc_creates_phrase_levels pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-06-18 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: DLC Builder build failed.

**Evidence:**

- commit cbc13dca35 Pre-create .phrase-levels dir to avoid DLC Builder crash on first build
- commit 7b3f129ac0 Add .keep so .phrase-levels folder survives bundle zip/extract
- commit 11b880b1fb Revert .phrase-levels creation: it is a DLC Builder file, not our folder
- commit 4ebbabe716 Generate .phrase-levels file alongside .rs2dlc for DLC Builder compatibility
- found_in_version: fix cbc13dca35 (2026-06-13) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 79e4c614da, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-06-18 — Fixed: commit cbc13dca35, 7b3f129ac0, 11b880b1fb, 4ebbabe716
- 2026-06-18 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0051

**A tone change landing exactly on a note made DLC Builder throw**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | pending (not recorded) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 0be7dbbba4cef1bb42c5de855a763db28e991a01 |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

A <tone time> event coinciding with a note's time makes DLC Builder error, so a chart with a tone change marked on a note could not be imported.

**Steps to reproduce:** _pending_

**Expected:** The XML with tone changes imports into DLC Builder.

**Observed:** DLC Builder errored on the tone change.

**Root cause:** The XML writer wrote tone change times unchanged, including on a note's time.

**Fixes:** [FIX-0051](../FIX_LOG.md#fix-0051) (0.10.0-beta.1)

**Verified:** regression test(s) test_tone_change_never_lands_on_a_note, test_safe_tone_time_uses_gap_then_midpoint pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-07-06 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Breaks the DLC Builder import of charts with tone changes on notes.

**Evidence:**

- CLAUDE.md § Hard constraints (these have bitten us — keep them) — 'A tone change must not coincide with a note.'
- commit 90ed59010c Never write a tone change on a note (DLC Builder errors otherwise)
- found_in_version: the fix commit 90ed59010c is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent 0be7dbbba4

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-06 — Fixed: commit 90ed59010c
- 2026-07-06 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0082

**Bends vanished in DLC Builder builds: XML had no <bendValues>**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 3bed9fe87fe3b89fad0b1c3369b03e4ad30b19ae |
| Severity | Medium |
| Priority | P3 |
| Status | Fixed |

The XML writer emitted only the bend='N' flag and never the <bendValues> curve, so DLC Builder built charts with no bend at all.

**Steps to reproduce:** _pending_

**Expected:** Bends reproduced

**Observed:** No bends in DLC Builder builds

**Root cause:** Missing bendValues.

**Fixes:** [FIX-0082](../FIX_LOG.md#fix-0082) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-07-08 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Lost technique.

**Evidence:**

- commit debd8856c9 Emit proper bend curves instead of dropping bends
- found_in_version: fix debd8856c9 (2026-07-08) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 3bed9fe87f, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-08 — Fixed: commit debd8856c9

## BUG-0088

**arrangementProperties tapping and slapPop hardcoded 0**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 6d037241fcca9dc46edb1d5ce6fe20a5bc322c17 |
| Severity | Low |
| Priority | P4 |
| Status | Fixed |

tapping and slapPop properties were 0 despite notes carrying the technique.

**Steps to reproduce:** _pending_

**Expected:** Derived from notes

**Observed:** Properties 0

**Root cause:** Hardcoded.

**Fixes:** [FIX-0088](../FIX_LOG.md#fix-0088) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-07-09 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Metadata.

**Evidence:**

- commit 3dd2f3551d Implement four more techniques: GP7 slap/tap/accent, slide-out, fret-mute, composite bends
- found_in_version: fix 3dd2f3551d (2026-07-09) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 6d037241fc, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-09 — Fixed: commit 3dd2f3551d

## BUG-0215

**Upstrokes became SLAP on the DLC Builder path: XML pickDirection wrote 2**

| | |
|---|---|
| Detected | 2026-09-30 |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | fce9df565fcd1a5584e14ae0155e6a641d39f6be |
| Severity | Medium |
| Priority | P3 |
| Status | Fixed |

The XML pickDirection is one bit (DLC Builder shifts it to bit 10); RockForge wrote '2' for an upstroke, which landed on bit 11, SLAP.

**Steps to reproduce:** _pending_

**Expected:** An upstroke is an upstroke in DLC Builder.

**Observed:** Upstrokes read as slap.

**Root cause:** The writer emitted the domain's value 2 instead of the one-bit 1.

**Fixes:** [FIX-0215](../FIX_LOG.md#fix-0215) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-09-30 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Wrong technique on the DLC Builder path only.

**Evidence:**

- CLAUDE.md § SNG binary compilation (`infrastructure/packaging/psarc/sng.py`) — 'Found on the way: the XML's `pickDirection` is ONE bit'
- commit 649ae72e99 SNG: every phrase with notes has levels, linked phrases are equal
- found_in_version: the fix commit 649ae72e99 is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent fce9df565f

**History:**

- 2026-09-30 — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-09-30 — Fixed: commit 649ae72e99

## BUG-0272

**XML, viewer and native SNG placed different automatic fret-hand positions**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | _pending_ |
| Build / commit | bebcf2b5d6e7d074829b4c01106ada00a7fcdb97 |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

The XML writer had its own "new anchor when a group leaves the window" rule while the SNG used _build_anchors, so DLC Builder, the viewer (which reads the XML) and the native SNG each showed different FHPs.

**Steps to reproduce:** _pending_

**Expected:** The same automatic FHPs in the XML and every SNG level.

**Observed:** Different FHPs per path.

**Root cause:** Two independent automatic anchor algorithms (writer.py vs sng_build).

**Fixes:** [FIX-0272](../FIX_LOG.md#fix-0272) (0.10.0-beta.5)

**Verified:** regression test(s) test_the_users_hand_positions_are_the_xml_anchors, test_the_xml_and_the_sng_place_the_same_automatic_hand_positions pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-10-15 · **Closed:** 2026-10-15

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Inconsistent hand positions between outputs; each still playable.

**Evidence:**

- CLAUDE.md § Fret-hand positions — the FHP editor (`hand_positions`): "The XML's automatic anchors are now auto_windows too: before, the writer had its own ... rule, so DLC Builder, the viewer ... and the native SNG each showed different FHPs"
- CHANGELOG.en.md 0.10.0 beta 5 — Changed: "The XML for DLC Builder now carries the same automatic fret-hand positions as the .psarc"
- commit c2b203891b FHP editor: place, change and delete fret-hand positions per chart
- found_in_version pending: detection date not documented

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-10-15 — Fixed: commit c2b203891b, 4e145389ab
- 2026-10-15 — Verified: automated
- 2026-10-15 — Closed: released in 0.10.0-beta.5

## BUG-0318

**A half-step bend lost its value in the XML**

| | |
|---|---|
| Detected | 2026-10-18 |
| Reported by | code review (Claude, on the maintainer's request) |
| Found in | 0.11.0-beta.2 |
| Build / commit | f64c45e8e176c44bd87c7c7866f741330b443011 |
| Severity | Medium |
| Priority | P3 |
| Status | Verified |

bend was int(round(x)): 0.5 became 0 and was dropped, 1.5 became 2.

**Steps to reproduce:** 

1. See the description (found by reading the code)

**Expected:** As described in the solution.

**Observed:** bend was int(round(x)): 0.5 became 0 and was dropped, 1.5 became 2.

**Root cause:** Integer rounding in the writer.

**Fixes:** [FIX-0318](../FIX_LOG.md#fix-0318) (0.11.0-beta.4)

**Verified:** tests/test_rsxml_writer.py::test_a_half_step_bend_and_a_muted_chord_say_so_in_the_xml passed, and fails with the fix reverted (by pytest (the test fails on the old code))

**Resolved:** 2026-10-18 · **Closed:** _pending_

**Evidence:**

- code review of the whole codebase (six reviewers), confirmed by reading the code

**History:**

- 2026-10-18 — Open: reported
- 2026-10-18 — Fixed: commit 0b354c27fe
- 2026-10-18 — Verified: its test passes and fails on the old code

## BUG-0319

**A chord with every string fret-hand muted was not marked muted in the XML**

| | |
|---|---|
| Detected | 2026-10-18 |
| Reported by | code review (Claude, on the maintainer's request) |
| Found in | 0.11.0-beta.2 |
| Build / commit | f64c45e8e176c44bd87c7c7866f741330b443011 |
| Severity | Low |
| Priority | P3 |
| Status | Verified |

fretHandMute was hard-coded 0 on <chord>.

**Steps to reproduce:** 

1. See the description (found by reading the code)

**Expected:** As described in the solution.

**Observed:** fretHandMute was hard-coded 0 on <chord>.

**Root cause:** Not mirrored from the notes like palm mute.

**Fixes:** [FIX-0319](../FIX_LOG.md#fix-0319) (0.11.0-beta.4)

**Verified:** tests/test_rsxml_writer.py::test_a_half_step_bend_and_a_muted_chord_say_so_in_the_xml passed, and fails with the fix reverted (by pytest (the test fails on the old code))

**Resolved:** 2026-10-18 · **Closed:** _pending_

**Evidence:**

- code review of the whole codebase (six reviewers), confirmed by reading the code

**History:**

- 2026-10-18 — Open: reported
- 2026-10-18 — Fixed: commit 0b354c27fe
- 2026-10-18 — Verified: its test passes and fails on the old code
