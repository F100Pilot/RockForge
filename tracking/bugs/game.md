<!-- Generated from tracking/bugs.json by `python -m tools.tracking render`. Do not edit by hand: edit the JSON and render again. -->

# Bugs: game

Installing in the game. Index: [BUG_LOG.md](../BUG_LOG.md).

## BUG-0010

**Palm-muted chords rendered as a corrupt highway sprite**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer (in game) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 95954d9d52ff7688732e7c7f6f6a64f896b52bf5 |
| Severity | High |
| Priority | P2 |
| Status | Closed |

The game reads palm mute/accent/HOPO from <chord>, not its chordNotes; the writer hardcoded them to 0 on the chord while chordNotes had palmMute=1, so palm-muted chords rendered with a 'winged'/twisted sprite.

**Steps to reproduce:** _pending_

**Expected:** Normal palm-muted chord render

**Observed:** Corrupt chord sprite on palm-muted chords

**Root cause:** Chord-level flags not mirrored from the notes.

**Fixes:** [FIX-0010](../FIX_LOG.md#fix-0010) (0.10.0-beta.1)

**Verified:** regression test(s) test_chord_element_mirrors_palm_mute_of_its_notes pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-06-13 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Visible rendering corruption in game.

**Evidence:**

- commit c3b69a9b53 Fix corrupt chord rendering: mirror palm mute/accent/HOPO onto <chord>
- found_in_version: fix c3b69a9b53 (2026-06-13) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 95954d9d52, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-06-13 — Fixed: commit c3b69a9b53
- 2026-06-13 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0012

**Plain notes drew a spurious technique glyph (zero-valued attributes)**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer (in game) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 448ed76c3f9427b544cb6d2f5b9197864e298c0a |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

Every Song2014 flag was spelled out even at its default (palmMute="0", slideTo="-1"…); their presence made the highway draw a technique glyph inside plain note boxes.

**Steps to reproduce:** _pending_

**Expected:** Plain filled rectangle

**Observed:** Glyph inside plain note boxes

**Root cause:** Default-valued attributes emitted.

**Fixes:** [FIX-0012](../FIX_LOG.md#fix-0012) (0.10.0-beta.1)

**Verified:** regression test(s) test_plain_note_emits_only_minimal_attributes pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-06-14 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Misleading note rendering.

**Evidence:**

- commit 0dc76bcf46 Emit only non-default note/chord attributes (match Editor on Fire)
- found_in_version: fix 0dc76bcf46 (2026-06-14) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 448ed76c3f, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-06-14 — Fixed: commit 0dc76bcf46
- 2026-06-14 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0279

**Every short note carried a sustain tail on the highway**

| | |
|---|---|
| Detected | 2026-10-16 |
| Reported by | user report |
| Found in | 0.10.0-beta.6 |
| Build / commit | 8494322e3f34a7427e9ed710687f2001493e9bb4 |
| Severity | Medium |
| Priority | P2 |
| Status | Closed |

Every Guitar Pro note's notated length was written as a sustain, so each eighth and sixteenth of a riff dragged a tail on the highway.

**Steps to reproduce:** 

1. Build a riff of eighths/sixteenths (e.g. "Behind", Kills Birds)
2. Look at the highway

**Expected:** Only held notes have tails.

**Observed:** "every single note looks extended when they aren't"

**Root cause:** The parsers wrote each note's notated length as its sustain.

**Fixes:** [FIX-0279](../FIX_LOG.md#fix-0279) (0.10.0-beta.7)

**Verified:** regression test(s) test_notes_shorter_than_a_beat_lose_their_sustain, test_a_short_note_keeps_the_sustain_its_technique_is_drawn_on, test_the_beat_is_the_grids_own_where_the_note_is, test_a_gp5_riff_of_eighths_has_no_tails_but_its_held_notes_do, test_a_gp7_riff_of_eighths_has_no_tails pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-10-16 · **Closed:** 2026-10-16

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Every chart looked wrong in game; playable.

**Evidence:**

- CLAUDE.md § The generation path: "Only a HELD note gets a sustain ... 'every single note looks extended when they aren't' (a user's video, 2026-10-16)"
- user quote (2026-10-16): 'every single note looks extended when they aren't'
- CHANGELOG.en.md 0.10.0 beta 7 — Fixed: "Short notes without a sustain tail ..."
- commit 4b63d25d80 Only held notes get a sustain: short notes no longer drag a tail
- found_in_version: beta 7 was published after this fix (its release notes were edited in 4b63d25 on 2026-10-16), so the newest published release at the report was beta 6 (8494322), which has the faulty code

**History:**

- 2026-10-16 — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-10-16 — Fixed: commit 4b63d25d80
- 2026-10-16 — Verified: automated
- 2026-10-16 — Closed: released in 0.10.0-beta.7

## BUG-0288

**Open-string chords without sustain were painted solid top to bottom in game**

| | |
|---|---|
| Detected | 2026-10-17 |
| Reported by | user report |
| Found in | 0.10.0-beta.10 |
| Build / commit | d73ecc0a067ab1fad10738ab5c81d5b86b527e98 |
| Severity | High |
| Priority | P2 |
| Status | Closed |

A chord with an open string and no sustain or technique (a drop-tuned 0-0-0 power chord, once short notes lost their sustain) went out with chord_notes_id -1, and the game painted it solid from the top string to the bottom.

**Steps to reproduce:** 

1. Build a drop-tuned song with short 0-0-0 power chords (e.g. "Behind", Kills Birds)
2. Play it in Rocksmith

**Expected:** Normal chord shapes.

**Observed:** "as notas estão pintadas de cima a baixo"

**Root cause:** ChordNotes were emitted only for a sustain or a technique; DLC Builder emits one unless every string's mask is empty, and an open string always carries OPEN.

**Fixes:** [FIX-0288](../FIX_LOG.md#fix-0288) (0.10.0-beta.11)

**Verified:** regression test(s) test_an_open_string_chord_without_sustain_still_gets_its_chord_notes, test_each_rule_catches_the_fault_that_crashed_the_game pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-10-17 · **Closed:** 2026-10-17

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: A visible highway glitch on every such chord (2312 in the song); still playable.

**Evidence:**

- CLAUDE.md § SNG binary compilation (`infrastructure/packaging/psarc/sng.py`): "...and so does every chord with an OPEN string, sustained or not (2026-10-17, 'as notas estão pintadas de cima a baixo': a user's screenshot ...)"
- user quote (2026-10-17): 'as notas estão pintadas de cima a baixo'
- CHANGELOG.en.md 0.10.0 beta 11 — Fixed: "Chords \"painted\" top to bottom in game ..."
- commit ec8df7fc2d Give every open-string chord its ChordNotes entry, as DLC Builder does
- found_in_version: reported 2026-10-17 before beta 11 (8b5b49a, 07:42) was published; newest published was beta 10 (d73ecc0), which has the faulty code

**History:**

- 2026-10-17 — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-10-17 — Fixed: commit ec8df7fc2d
- 2026-10-17 — Verified: automated
- 2026-10-17 — Closed: released in 0.10.0-beta.11
