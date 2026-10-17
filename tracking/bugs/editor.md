<!-- Generated from tracking/bugs.json by `python -m tools.tracking render`. Do not edit by hand: edit the JSON and render again. -->

# Bugs: editor

Note, section and fret-hand-position editing. Index: [BUG_LOG.md](../BUG_LOG.md).

## BUG-0137

**In 'Editar notas' a click on empty staff inserted a note instead of seeking**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | af5f74d35ea1ea4a913c8d80000f74d79793dcac |
| Severity | Medium |
| Priority | P3 |
| Status | Fixed |

A single empty-space click in the note editor inserted a note, silently hijacking the click-to-seek that works in every other mode.

**Steps to reproduce:** 

1. Select 'Editar notas'
2. Click empty staff space

**Expected:** The playhead moves there.

**Observed:** A note was inserted.

**Root cause:** The single-click handler on empty space inserted.

**Fixes:** [FIX-0137](../FIX_LOG.md#fix-0137) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-07-14 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Unwanted notes and lost navigation in one mode.

**Evidence:**

- CLAUDE.md § Note editor (A single click on EMPTY staff space still seeks)
- user quote (undated): 'não consigo clicar na partitura e o cursor mover-se'
- commit ebe6d4204f Fix: restore click-to-seek in the note editor; surface the copy buttons
- found_in_version: the fix commit is an ancestor of cb00653 (the first public release, 0.10.0 beta 1, 2026-10-14), so the faulty code only existed in development builds before 0.10.0-beta.1
- found_in_build: af5f74d35e is the parent of the first fix commit ebe6d4204f and still carries the code the fix changes

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-14 — Fixed: commit ebe6d4204f

## BUG-0167

**An unrelated rebuild silently erased committed note edits**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 51cb0b17260c260bc7bb87e62e291e9e0b5afb02 |
| Severity | Critical |
| Priority | P1 |
| Status | Closed |

applyAll always sent the whole note_overrides dict and rebuild_job replaced it, but the viewer reset its list to {} on every job open, so reopening a job and rebuilding for anything else wiped every committed note edit.

**Steps to reproduce:** 

1. Edit notes and rebuild
2. Reopen the job
3. Change something else (e.g. tuning) and press 'Aplicar e reconstruir'

**Expected:** Committed note edits are kept.

**Observed:** Every committed note edit was gone.

**Root cause:** loadArrangements reset noteOverridesByKind to {} instead of seeding it from the committed edits.

**Fixes:** [FIX-0167](../FIX_LOG.md#fix-0167) (0.10.0-beta.1)

**Verified:** regression test(s) test_committed_note_edits_survive_an_unrelated_rebuild pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-08-25 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Silent data loss of the user's edits.

**Evidence:**

- CLAUDE.md § Note editor (Committed edits are SEEDED back into the viewer)
- commit f845b9bec9 Stop an unrelated rebuild from erasing committed note edits; add a clear button
- found_in_version: the fix commit is an ancestor of cb00653 (the first public release, 0.10.0 beta 1, 2026-10-14), so the faulty code only existed in development builds before 0.10.0-beta.1
- found_in_build: 51cb0b1726 is the parent of the first fix commit f845b9bec9 and still carries the code the fix changes

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-08-25 — Fixed: commit f845b9bec9
- 2026-08-25 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0184

**Note edits missed notes whose time the XML rounded (deleted notes still sounded)**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | e649a3489e1a3db653c8bddd2ffdcc075ab62998 |
| Severity | High |
| Priority | P2 |
| Status | Closed |

Edits keyed on round(time, 6) never matched about half the notes, since the editor sees millisecond-rounded XML times: a deleted note stayed in the song and an edited one gained a twin (6 of 12 deletes survived; 7 of 10 fret edits duplicated).

**Steps to reproduce:** 

1. Delete an excerpt at the end of a song in 'Editar notas'
2. Apply and rebuild
3. Play

**Expected:** The deleted notes are gone; edited notes replaced.

**Observed:** Deleted notes still played; edits added twins.

**Root cause:** _apply_note_overrides matched by exact 6-decimal time against full-precision parser times.

**Fixes:** [FIX-0184](../FIX_LOG.md#fix-0184) (0.10.0-beta.1)

**Verified:** regression test(s) test_note_overrides_find_notes_whose_time_the_xml_rounded pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-09-27 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Note editing unreliable on about half the notes.

**Evidence:**

- CLAUDE.md § Note editor — add/edit/remove notes and techniques on the score
- user quote (undated): 'apaguei um excerto do final mas o som das notas ainda se ouve, mesmo depois de recompilar'
- commit 65527dd20c Note edits find their note even when the XML rounded its time
- found_in_version: the fix commit is an ancestor of cb00653 (the first public release, 0.10.0 beta 1, 2026-10-14), so the faulty code only existed in development builds before 0.10.0-beta.1
- found_in_build: e649a3489e is the parent of the first fix commit 65527dd20c and still carries the code the fix changes

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-09-27 — Fixed: commit 65527dd20c
- 2026-09-27 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0289

**Inserting a note in a solo snapped to the previous note's beat and made a chord**

| | |
|---|---|
| Detected | 2026-10-17 |
| Reported by | user report |
| Found in | _pending_ |
| Build / commit | 8b5b49a54bb03d085716b529abf41e671788c2fa |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

The double-click insert snapped to the sync grid, whole beats by default, so in a run of sixteenths the nearest point was the beat the previous note already held and the new note became a chord with it.

**Steps to reproduce:** 

1. In "Editar notas", double-click between two sixteenths of a solo

**Expected:** The note lands on the sixteenth clicked.

**Observed:** "it keeps snapping to the previous note making a chord"

**Root cause:** Inserts used snapGridTimes() (whole beats by default) with no minimum resolution.

**Fixes:** [FIX-0289](../FIX_LOG.md#fix-0289) (0.10.0-beta.12)

**Verified:** CLAUDE.md: 'verified with Playwright on the invented "Deriva" project (PT/EN): a click at 27 % of a beat lands on the sixteenth (the old grid: the beat)' (by the developer (manual check))

**Resolved:** 2026-10-17 · **Closed:** 2026-10-17

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Note insertion unusable in fast passages; turning snap off was a workaround.

**Evidence:**

- CLAUDE.md § Note editor — add/edit/remove notes and techniques on the score: "Dragging a note, ↑/↓ for its fret, and an insertion grid of sixteenths (Liam, 2026-10-17 ...)"
- user quote (2026-10-17, Liam): 'found how to add a note but it keeps snapping to the previous note making a chord'
- CHANGELOG.en.md 0.10.0 beta 12 — Fixed: "Inserting a note in a solo made a chord ..."
- commit 6be99ca6da Edit notes: drag a note, arrows step its fret, inserts snap to sixteenths
- found_in_version pending: faulty code present at d73ecc0 (beta 10) and 8b5b49a (beta 11); which was in use on 2026-10-17 is not stated

**History:**

- 2026-10-17 — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-10-17 — Fixed: commit 6be99ca6da
- 2026-10-17 — Verified: manual
- 2026-10-17 — Closed: released in 0.10.0-beta.12

## BUG-0290

**A deleted or edited note was still heard until the rebuild**

| | |
|---|---|
| Detected | 2026-10-17 |
| Reported by | user report |
| Found in | _pending_ |
| Build / commit | 8b5b49a54bb03d085716b529abf41e671788c2fa |
| Severity | Low |
| Priority | P3 |
| Status | Closed |

The tick, the synthesized source, the fretboard and "Pré-visualizar" read the built notes, so a note deleted or edited on the score kept sounding until "Aplicar e reconstruir".

**Steps to reproduce:** 

1. Delete a note on the score
2. Play the passage

**Expected:** The deleted note is silent.

**Observed:** "when i remove a note it still plays in the midi track until its rebuilt"

**Root cause:** Playback paths read a.notes instead of the merged pending notes.

**Fixes:** [FIX-0290](../FIX_LOG.md#fix-0290) (0.10.0-beta.12)

**Verified:** CLAUDE.md: 'Verified with Playwright: 9 notes deleted, 0 of them ticked (the old code ticked all 9), the synth buffer silent there' (by the developer (manual check))

**Resolved:** 2026-10-17 · **Closed:** 2026-10-17

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Preview only; the rebuild was correct.

**Evidence:**

- CLAUDE.md § Note editor — add/edit/remove notes and techniques on the score: "Pending note edits are now heard, not only drawn ('when i remove a note it still plays in the midi track until its rebuilt')"
- user quote (undated, Liam): 'when i remove a note it still plays in the midi track until its rebuilt'
- CHANGELOG.en.md 0.10.0 beta 12 — Fixed: "A deleted note kept playing until the rebuild ..."
- commit cd842cbc9c Edit notes: Shift+drag duplicates, drag a tail's end, edits are heard ("Liam's next three")
- detected 2026-10-17: reported after Liam's 2026-10-17 requests fixed in 6be99ca and fixed the same day
- found_in_version pending: faulty code present at d73ecc0 (beta 10) and 8b5b49a (beta 11)

**History:**

- 2026-10-17 — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-10-17 — Fixed: commit cd842cbc9c
- 2026-10-17 — Verified: manual
- 2026-10-17 — Closed: released in 0.10.0-beta.12
