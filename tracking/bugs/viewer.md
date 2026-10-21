<!-- Generated from tracking/bugs.json by `python -m tools.tracking render`. Do not edit by hand: edit the JSON and render again. -->

# Bugs: viewer

The score, fretboard, 3D highway and playback. Index: [BUG_LOG.md](../BUG_LOG.md).

## BUG-0009

**Note viewer string colours wrong and reversed**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | pending (not recorded) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 1426aa6eb035a760161b01fd4f3649cf61304ee9 |
| Severity | Low |
| Priority | P4 |
| Status | Fixed |

The tab viewer's per-string colours did not match Rocksmith's highway mapping, and the order was then reversed.

**Steps to reproduce:** _pending_

**Expected:** Rocksmith's string colours

**Observed:** Strings drawn in the wrong colours

**Root cause:** STRING_COLORS mapping and order wrong.

**Fixes:** [FIX-0009](../FIX_LOG.md#fix-0009) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-06-13 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Cosmetic.

**Evidence:**

- commit 79e4c614da Fix string color mapping and surface all GP technique types
- commit d77e030047 Fix reversed string color order in note viewer
- found_in_version: fix 79e4c614da (2026-06-13) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 1426aa6eb0, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-06-13 — Fixed: commit 79e4c614da, d77e030047

## BUG-0014

**Note tick desynced after seeking backward**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | pending (not recorded) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 68fea2932de0db7817ad8b52fc7771a07e0ba77c |
| Severity | Low |
| Priority | P4 |
| Status | Fixed |

After seeking backward in the tab viewer, the per-note tick no longer fired in step with the notes.

**Steps to reproduce:** _pending_

**Expected:** Ticks follow the playhead

**Observed:** Ticks out of step after a backward seek

**Root cause:** _pending_

**Fixes:** [FIX-0014](../FIX_LOG.md#fix-0014) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-06-14 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Audible aid only.

**Evidence:**

- commit c60afad337 UI: add note-volume control, fix tick desync after seeking backward
- found_in_version: fix c60afad337 (2026-06-14) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 68fea2932d, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-06-14 — Fixed: commit c60afad337

## BUG-0022

**Tab viewer playback drifted mid-song (aligned at start, off after seeking)**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 20c9bfbf4903a2d58e58fadaa676fab52b3acac1 |
| Severity | High |
| Priority | P2 |
| Status | Closed |

The viewer played through an HTML <audio> element, whose seek estimates a byte offset; for VBR/seek-table-less sources it drifted further into the song, so a chart aligned from the start looked off after a seek into the middle.

**Steps to reproduce:** 

1. Seek into the middle of the song in the tab viewer
2. Play

**Expected:** Audio plays exactly at the seek position.

**Observed:** Audio played from a different position than reported.

**Root cause:** <audio> currentTime/seek imprecision on VBR sources.

**Fixes:** [FIX-0022](../FIX_LOG.md#fix-0022) (0.10.0-beta.1)

**Verified:** Playback goes through the Web Audio buffer source with sample-exact seeks, not the <audio> element (by the developer (Playwright))

**Resolved:** 2026-06-17 · **Closed:** 2026-10-20

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Sync checking mid-song was unreliable.

**Evidence:**

- CLAUDE.md § Note editor (Playback in the tab viewer goes through the Web Audio API)
- CLAUDE.md: 'the "aligned from the start, off in the middle" symptom'
- commit dd4177d36f Fix mid-song sync drift: play via Web Audio, not the <audio> element
- found_in_version: the fix commit is an ancestor of cb00653 (the first public release, 0.10.0 beta 1, 2026-10-14), so the faulty code only existed in development builds before 0.10.0-beta.1
- found_in_build: 20c9bfbf49 is the parent of the first fix commit dd4177d36f and still carries the code the fix changes
- Playwright 2026-10-20: source AudioBufferSourceNode; seek 8.123 -> audioTime 8.123

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-06-17 — Fixed: commit dd4177d36f
- 2026-10-20 — Verified: regression check re-run (pytest/Playwright)
- 2026-10-20 — Closed: released in 0.10.0-beta.1

## BUG-0023

**Recording playback stopped and waveform flickered while a job was open**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 5dca471597fee02af9bcbf641cb40127d5017520 |
| Severity | Medium |
| Priority | P3 |
| Status | Fixed |

The status poll used setInterval on the async selectJob; on a completed job it re-ran loadArrangements (decode + reset audio src), overlapping invocations reset playback every tick and nulled the waveform.

**Steps to reproduce:** _pending_

**Expected:** Steady playback

**Observed:** Playback stops; waveform flickers

**Root cause:** Overlapping setInterval polls re-loading arrangements.

**Fixes:** [FIX-0023](../FIX_LOG.md#fix-0023) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-06-17 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Sync viewer unusable during polling.

**Evidence:**

- commit 5f44825531 Fix GP audio playback stopping + waveform flicker on the sync viewer
- found_in_version: fix 5f44825531 (2026-06-17) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 5dca471597, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-06-17 — Fixed: commit 5f44825531

## BUG-0035

**Intro silence (lead_in_s) invisible in the viewer**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | da5084a3c99241e9c53806401acdf8476d447026 |
| Severity | Low |
| Priority | P4 |
| Status | Fixed |

lead_in only padded the bundle audio; the viewer played the original recording, so the silence was invisible ('nada avançou').

**Steps to reproduce:** _pending_

**Expected:** Silence shown at the start

**Observed:** Nothing moved

**Root cause:** Viewer's decoded buffer not padded.

**Fixes:** [FIX-0035](../FIX_LOG.md#fix-0035) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-06-30 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Feature looked broken.

**Evidence:**

- user quote: 'nada avançou'
- commit 19f40bfea9 Show intro silence (lead_in_s) in the tab viewer
- found_in_version: fix 19f40bfea9 (2026-06-30) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent da5084a3c9, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-06-30 — Fixed: commit 19f40bfea9

## BUG-0037

**Staff string labels always read E A D G B e, whatever the tuning**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | pending (not recorded) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 9c10711313abea76a9533b9839210b62efb3aa2c |
| Severity | Low |
| Priority | P4 |
| Status | Fixed |

The staff hard-coded standard-tuning names, so a Drop C# chart was labelled E A D G B e.

**Steps to reproduce:** 

1. Open a chart in a non-standard tuning

**Expected:** Labels show the real tuning (C# G# C# F# A# D#).

**Observed:** Standard names.

**Root cause:** Labels were a fixed array.

**Fixes:** [FIX-0037](../FIX_LOG.md#fix-0037) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-07-02 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Cosmetic.

**Evidence:**

- CLAUDE.md § Sync by bar number (String labels show the real tuning)
- commit 53038eb47b Tab viewer: label strings with the real tuning, not fixed E A D G B e
- found_in_version: the fix commit is an ancestor of cb00653 (the first public release, 0.10.0 beta 1, 2026-10-14), so the faulty code only existed in development builds before 0.10.0-beta.1
- found_in_build: 9c10711313 is the parent of the first fix commit 53038eb47b and still carries the code the fix changes

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-02 — Fixed: commit 53038eb47b

## BUG-0045

**Chord names collided with low-string notes on the score**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | pending (not recorded) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | f94913af194c4d8dd84f7f3a96e35ce3fa4e07b5 |
| Severity | Low |
| Priority | P4 |
| Status | Fixed |

A chord on the lowest string had its name stuck to the notes: only 35 px separated string 0 from the SVG bottom.

**Steps to reproduce:** _pending_

**Expected:** Name in a clear band

**Observed:** Name overlapping notes

**Root cause:** Bottom band too small.

**Fixes:** [FIX-0045](../FIX_LOG.md#fix-0045) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-07-03 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Cosmetic.

**Evidence:**

- commit 49465d60d0 Alargar a banda de acordes para não colidir com cordas graves
- found_in_version: fix 49465d60d0 (2026-07-03) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent f94913af19, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-03 — Fixed: commit 49465d60d0

## BUG-0050

**Note tick ignored the arrangement's tuning (wrong pitch in drop/open tunings)**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | pending (not recorded) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 6f4814fbb6d8e49f4780ae828cebeee87157bf86 |
| Severity | Low |
| Priority | P4 |
| Status | Fixed |

The per-note tick computed MIDI from standard tuning, ignoring tuning offsets, so it sounded the wrong pitch on drop/open charts.

**Steps to reproduce:** _pending_

**Expected:** Real pitch

**Observed:** Wrong pitch

**Root cause:** tuning_offsets not applied.

**Fixes:** [FIX-0050](../FIX_LOG.md#fix-0050) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-07-04 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Audible aid only.

**Evidence:**

- commit 7b47c7e714 Sliders de volume mais largos, tique até 200% e a espelhar o pitch da nota
- found_in_version: fix 7b47c7e714 (2026-07-04) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 6f4814fbb6, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-04 — Fixed: commit 7b47c7e714

## BUG-0054

**Removed tone markers stayed on the score until another redraw**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 5e023f398d957e1f788ed2a5cc13ee5e4256b510 |
| Severity | Low |
| Priority | P4 |
| Status | Fixed |

Handlers changing tone assignment never redrew the score, so removed tone markers stayed visible.

**Steps to reproduce:** _pending_

**Expected:** Markers update at once

**Observed:** Stale markers

**Root cause:** Missing showArr call.

**Fixes:** [FIX-0054](../FIX_LOG.md#fix-0054) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-07-06 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Cosmetic.

**Evidence:**

- commit c27a849681 Fix: removing tones from the score now redraws the markers immediately
- found_in_version: fix c27a849681 (2026-07-06) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 5e023f398d, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-06 — Fixed: commit c27a849681

## BUG-0092

**Nonsense '? (0n/0c)' tab for the vocals XML**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | pending (not recorded) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 69c0abb0fbc96d8394dd0037ab56c61958bc0402 |
| Severity | Low |
| Priority | P4 |
| Status | Fixed |

get_arrangements globbed arrangement_*.xml, including arrangement_vocals.xml.

**Steps to reproduce:** _pending_

**Expected:** Only instrument tabs

**Observed:** '?' tab with 0 notes

**Root cause:** Glob matched vocals.

**Fixes:** [FIX-0092](../FIX_LOG.md#fix-0092) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-07-09 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Cosmetic.

**Evidence:**

- commit 6cfbb291c4 Hide the vocals XML from the arrangement tabs (the '? (0n/0c)' tab)
- found_in_version: fix 6cfbb291c4 (2026-07-09) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 69c0abb0fb, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-09 — Fixed: commit 6cfbb291c4

## BUG-0105

**Zooming lost the place in the song**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | pending (not recorded) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 8f9e18d0ff4f0154ca6adb10a337a3e01c0b061f |
| Severity | Low |
| Priority | P3 |
| Status | Fixed |

setZoom rescaled px-per-second and redrew without touching #tabwrap's scrollLeft, so the view jumped away from the passage being zoomed.

**Steps to reproduce:** 

1. Scroll to a passage mid-song
2. Zoom in or out

**Expected:** The same passage stays in view.

**Observed:** The view jumped to another time.

**Root cause:** scrollLeft kept its pixel value while the scale changed.

**Fixes:** [FIX-0105](../FIX_LOG.md#fix-0105) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-07-11 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Navigation annoyance.

**Evidence:**

- CLAUDE.md § Sync by bar number (Zoom keeps its place)
- commit 1e02138b80 Tab viewer: per-track note start + more precise note adjustment
- found_in_version: the fix commit is an ancestor of cb00653 (the first public release, 0.10.0 beta 1, 2026-10-14), so the faulty code only existed in development builds before 0.10.0-beta.1
- found_in_build: 8f9e18d0ff is the parent of the first fix commit 1e02138b80 and still carries the code the fix changes

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-11 — Fixed: commit 1e02138b80

## BUG-0106

**Shift+click/drag on the score selected label text like page text**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | pending (not recorded) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 8f9e18d0ff4f0154ca6adb10a337a3e01c0b061f |
| Severity | Low |
| Priority | P4 |
| Status | Fixed |

Shift+click or a click-drag over the SVG's <text> labels (technique letters, tuning names, bar numbers) highlighted them as page text instead of only driving note selection/drag.

**Steps to reproduce:** 

1. Shift+click or drag over labels on the score

**Expected:** Only note selection happens.

**Observed:** Native text selection highlighted the labels.

**Root cause:** No user-select:none or preventDefault on the score SVG.

**Fixes:** [FIX-0106](../FIX_LOG.md#fix-0106) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-07-11 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Cosmetic interference with selection.

**Evidence:**

- CLAUDE.md § Sync by bar number (No native text selection during score interaction)
- commit 1e02138b80 Tab viewer: per-track note start + more precise note adjustment
- found_in_version: the fix commit is an ancestor of cb00653 (the first public release, 0.10.0 beta 1, 2026-10-14), so the faulty code only existed in development builds before 0.10.0-beta.1
- found_in_build: 8f9e18d0ff is the parent of the first fix commit 1e02138b80 and still carries the code the fix changes

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-11 — Fixed: commit 1e02138b80

## BUG-0108

**A track resting through the outro was drawn shorter than the song**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 924199fbe6474448ca61b4fbf7db22f227817d74 |
| Severity | Low |
| Priority | P3 |
| Status | Closed |

showArr sized the chart to the last note only, so a track that rests through the outro (Lead stopping at bar 120 of 146) had its trailing bars and waveform tail clipped.

**Steps to reproduce:** 

1. Open a chart whose track stops before the song ends

**Expected:** All bars and the waveform to the end are shown.

**Observed:** The track appeared to end around bar 122.

**Root cause:** dur = max(note.time) instead of the song length.

**Fixes:** [FIX-0108](../FIX_LOG.md#fix-0108) (0.10.0-beta.1)

**Verified:** commit 11be186: 'Verified headless: with notes ending at ~138s and bars to ~181s, the bar-146 line now falls inside the SVG width' (by the developer (manual check))

**Resolved:** 2026-07-11 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Display only.

**Evidence:**

- CLAUDE.md § Note editor (The chart is sized to the whole song, not the last note)
- user quote (undated): 'o lead só aparece até ao compasso 122'
- commit 11be186b7a Tab viewer: size the chart to the whole song, not just the last note
- found_in_version: the fix commit is an ancestor of cb00653 (the first public release, 0.10.0 beta 1, 2026-10-14), so the faulty code only existed in development builds before 0.10.0-beta.1
- found_in_build: 924199fbe6 is the parent of the first fix commit 11be186b7a and still carries the code the fix changes

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-11 — Fixed: commit 11be186b7a
- 2026-07-11 — Verified: manual
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0128

**Interrupted drags stacked listeners (knobs spun 2-3× faster)**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 0854f3bd0d482b22e6e2e1972e5ddc130a815f7a |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

Knob and SVG drag handlers cleaned up only on pointerup; a pointercancel left the pointermove listener attached, stacking another on the next drag.

**Steps to reproduce:** _pending_

**Expected:** Clean drag state

**Observed:** Values keep moving after a cancelled drag

**Root cause:** No pointercancel handling.

**Fixes:** [FIX-0128](../FIX_LOG.md#fix-0128) (0.10.0-beta.1)

**Verified:** commit 444cb0e: verified live by invoking wireKnob in a headless browser (by the developer (manual check))

**Resolved:** 2026-07-13 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Erratic input.

**Evidence:**

- commit 444cb0e77e fix: two Major bugs found in a full-codebase audit
- found_in_version: fix 444cb0e77e (2026-07-13) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 0854f3bd0d, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-13 — Fixed: commit 444cb0e77e
- 2026-07-13 — Verified: manual
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0133

**Clicks/noise when scrubbing the recording**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 34e46504bca3bb600a6f612f2411f18f33019072 |
| Severity | Low |
| Priority | P4 |
| Status | Closed |

Every seek/pause hard-stopped/started the buffer source mid-waveform, an audible click; scrubbing stacked them into noise.

**Steps to reproduce:** _pending_

**Expected:** Click-free seeks

**Observed:** Noise while scrubbing

**Root cause:** No fade envelope.

**Fixes:** [FIX-0133](../FIX_LOG.md#fix-0133) (0.10.0-beta.1)

**Verified:** commit 27d75a3: verified in headless Chromium (one live source after 20 seeks) (by the developer (manual check))

**Resolved:** 2026-07-13 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Audio quality.

**Evidence:**

- commit 27d75a367f Fade the music source on seek/pause to kill scrubbing clicks (noise)
- found_in_version: fix 27d75a367f (2026-07-13) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 34e46504bc, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-13 — Fixed: commit 27d75a367f
- 2026-07-13 — Verified: manual
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0136

**Drag/box-select could not reach past the visible part of the score**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 0ba84ae66e66a4d1a8a36e0719290cd630aa3a42 |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

#tabwrap never scrolled during a pointer-capture drag, so the rubber-band selection, note drag, block drag and lyric drag could only reach what was already visible.

**Steps to reproduce:** 

1. Start a box selection on the score
2. Hold the pointer at the right edge

**Expected:** The score scrolls and the selection extends.

**Observed:** Nothing scrolled; selection limited to one screen.

**Root cause:** No auto-scroll during drags; the box coordinates depend on rect.left, which changes on scroll.

**Fixes:** [FIX-0136](../FIX_LOG.md#fix-0136) (0.10.0-beta.1)

**Verified:** CLAUDE.md: 'Guarded manually via Playwright (a 4000px-wide synthetic chart, a 600px viewport, holding the rubber-band drag at the right edge reaches and selects a note far outside the initial view)' (by the developer (manual check))

**Resolved:** 2026-07-14 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Long selections needed several steps or zooming out.

**Evidence:**

- CLAUDE.md § Manual drift correction (Auto-scroll during a drag/box-select)
- user quote (undated): 'só seleciono o que está visível'
- commit af5f74d35e Fix: auto-scroll the tab viewer during drag/box-select
- found_in_version: the fix commit is an ancestor of cb00653 (the first public release, 0.10.0 beta 1, 2026-10-14), so the faulty code only existed in development builds before 0.10.0-beta.1
- found_in_build: 0ba84ae66e is the parent of the first fix commit af5f74d35e and still carries the code the fix changes

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-14 — Fixed: commit af5f74d35e
- 2026-07-14 — Verified: manual
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0138

**Synthesized audio kept playing under a 'full mix' selector after switching jobs**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | pending (not recorded) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | ebe6d4204f3ff6a271ad3fa8b8497675f85fb1c1 |
| Severity | Medium |
| Priority | P3 |
| Status | Fixed |

initSync fired decodeWaveform and loadStems concurrently; a stale audio source from the previous job could be decoded first, then loadStems reset the dropdown to 'Mistura completa' without re-decoding, leaving the synth buffer playing under a selector that read the full mix.

**Steps to reproduce:** 

1. Pick a synthesized source in one job
2. Open a different job

**Expected:** The full mix plays when the selector says so.

**Observed:** Synthesized audio played while the selector read 'Mistura completa' ('dá música sintetizada mas a seleção está em mistura').

**Root cause:** A race between two un-awaited async calls reading a stale audioSourceName.

**Fixes:** [FIX-0138](../FIX_LOG.md#fix-0138) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-07-14 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Misleading playback; re-picking the source fixes it.

**Evidence:**

- CLAUDE.md § Stem separation — selectable audio source — '**`initSync` resets `audioSourceName` SYNCHRONOUSLY, before firing `decodeWaveform`/`loadStems`.**'
- commit e05cea0067 Fix: synthesized audio kept playing under a "full mix" selector after switching jobs
- found_in_version: the fix commit e05cea0067 is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent ebe6d4204f

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-14 — Fixed: commit e05cea0067

## BUG-0145

**Audio crackle/dropouts and score slowing down while editing**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 45ce440b063ea76cf62c599cee6d3c5144f0bab8 |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

O(n²) chord scan in mergeNoteOverrides after the first edit, linear warp lookups per point, O(bars×beats) BPM, a tick backlog burst after a stalled frame, uncached Karplus buffers and forced relayout every frame ('o som faz ruido, ou para, ou a partitura anda mais devagar').

**Steps to reproduce:** _pending_

**Expected:** Smooth playback

**Observed:** Crackle, dropouts, sluggish score

**Root cause:** Six performance defects in the render/playback loop.

**Fixes:** [FIX-0145](../FIX_LOG.md#fix-0145) (0.10.0-beta.1)

**Verified:** commit 1bf06f6: verified in headless Chromium against reference implementations (by the developer (manual check))

**Resolved:** 2026-08-21 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Editing degraded the tool.

**Evidence:**

- commit 1bf06f60cd Fix audio crackle/dropouts and the score slowing down while editing
- found_in_version: fix 1bf06f60cd (2026-08-21) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 45ce440b06, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-08-21 — Fixed: commit 1bf06f60cd
- 2026-08-21 — Verified: manual
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0150

**Score labels piled into an unreadable wall on dense charts**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 5b795a9df31f181a8735e3266eaa089a8e66e068 |
| Severity | Low |
| Priority | P4 |
| Status | Fixed |

Chord names, technique glyphs and bar numbers were drawn with no minimum spacing ('que confusão').

**Steps to reproduce:** _pending_

**Expected:** Readable labels

**Observed:** Overlapping labels

**Root cause:** No collision skipping.

**Fixes:** [FIX-0150](../FIX_LOG.md#fix-0150) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-08-22 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Readability.

**Evidence:**

- commit 246ed7b5d7 Tab viewer: stop labels piling into an unreadable wall on dense charts
- found_in_version: fix 246ed7b5d7 (2026-08-22) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 5b795a9df3, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-08-22 — Fixed: commit 246ed7b5d7

## BUG-0152

**Re-tempo mode reused the 'Detetar 1ª nota' icon**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 4eb9849f2292ee09fb643d89f7d04b06e1e706e9 |
| Severity | Low |
| Priority | P4 |
| Status | Fixed |

Two different functions showed the same target icon.

**Steps to reproduce:** _pending_

**Expected:** Distinct icons

**Observed:** Duplicate icon

**Root cause:** Relabel reused an icon.

**Fixes:** [FIX-0152](../FIX_LOG.md#fix-0152) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-08-22 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Cosmetic.

**Evidence:**

- commit eda3d23395 Fix icon collision: the re-tempo mode reused the "Detetar 1ª nota" target icon
- found_in_version: fix eda3d23395 (2026-08-22) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 4eb9849f22, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-08-22 — Fixed: commit eda3d23395

## BUG-0154

**The live BPM readout ignored pending tempo and anchor edits**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | eda3d2339598a04721a00aa06eff03dba7ebd04c |
| Severity | Low |
| Priority | P3 |
| Status | Fixed |

liveInfoAtTime measured the beat interval on the raw beat times, so the '♩ =' readout ignored every pending tempo_scale/anchor edit.

**Steps to reproduce:** _pending_

**Expected:** The readout shows the tempo as displayed.

**Observed:** The readout kept the built tempo.

**Root cause:** liveInfoAtTime used raw beat times instead of the displayed (warped) spacing.

**Fixes:** [FIX-0154](../FIX_LOG.md#fix-0154) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-08-23 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Misleading readout; it also fed 'Corrigir daqui'.

**Evidence:**

- CLAUDE.md § The recommended workflow: "Corrigir daqui"
- CLAUDE.md: '`liveInfoAtTime` was also measuring the beat interval on the RAW beat times'
- commit 72ba5c049b Fix "Corrigir daqui" always reading a higher tempo and running the chart fast
- found_in_version: the fix commit is an ancestor of cb00653 (the first public release, 0.10.0 beta 1, 2026-10-14), so the faulty code only existed in development builds before 0.10.0-beta.1
- found_in_build: eda3d23395 is the parent of the first fix commit 72ba5c049b and still carries the code the fix changes

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-08-23 — Fixed: commit 72ba5c049b

## BUG-0168

**"Pendente" summary never shown: its element was missing from the markup**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 51cb0b17260c260bc7bb87e62e291e9e0b5afb02 |
| Severity | Low |
| Priority | P3 |
| Status | Fixed |

updatePendingChangesInfo() wrote into #pendingChangesInfo, which was never in the markup, so the pending-changes summary had always been a silent no-op.

**Steps to reproduce:** _pending_

**Expected:** A summary of pending changes is shown.

**Observed:** Nothing was shown.

**Root cause:** The #pendingChangesInfo element did not exist; the function returned on its guard.

**Fixes:** [FIX-0168](../FIX_LOG.md#fix-0168) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-08-25 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: A missing indicator; nothing lost.

**Evidence:**

- CLAUDE.md § Note editor (Committed edits are SEEDED back into the viewer)
- commit f845b9b message: 'it was never in the markup, so updatePendingChangesInfo() had always been a silent no-op'
- commit f845b9bec9 Stop an unrelated rebuild from erasing committed note edits; add a clear button
- found_in_version: the fix commit is an ancestor of cb00653 (the first public release, 0.10.0 beta 1, 2026-10-14), so the faulty code only existed in development builds before 0.10.0-beta.1
- found_in_build: 51cb0b1726 is the parent of the first fix commit f845b9bec9 and still carries the code the fix changes

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-08-25 — Fixed: commit f845b9bec9

## BUG-0200

**An alternate chart showed as a second Lead/Rhythm and shared the main chart's edits**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | cf06d659e34be58e3f45d8819022e29a0e79f70c |
| Severity | High |
| Priority | P2 |
| Status | Closed |

/arrangements named each chart from its XML <arrangement> tag, where an alternate writes its base path, so the user saw two 'Lead'/'Rhythm' tabs, and pending anchors, tempo, note edits and the rebuild's arrangement — keyed by that name — landed on the main chart; the GP export looked for the wrong file.

**Steps to reproduce:** 

1. Build a song with a Lead and an Alternate Lead
2. Open the Partitura page

**Expected:** The alternate is its own chart.

**Observed:** Two 'Lead' tabs; the alternate could not be synced on its own.

**Root cause:** Chart names came from the <arrangement> tag instead of the file name.

**Fixes:** [FIX-0200](../FIX_LOG.md#fix-0200) (0.10.0-beta.1)

**Verified:** regression test(s) test_an_alternate_chart_is_its_own_arrangement_not_a_second_lead, test_each_chart_is_marked_in_sync_on_its_own, test_a_song_confirmed_before_charts_were_marked_one_by_one_marks_them_all pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-09-29 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: The alternate chart could not be edited or synced independently.

**Evidence:**

- CLAUDE.md § Batch processing ('This surfaced a real bug: an alternate chart looked like a second Lead.')
- commit d8b7b42241 Mark each track in sync on its own, with a green tab; alternates are their own charts
- found_in_version: the fix commit is an ancestor of cb00653 (the first public release, 0.10.0 beta 1, 2026-10-14), so the faulty code only existed in development builds before 0.10.0-beta.1
- found_in_build: cf06d659e3 is the parent of the first fix commit d8b7b42241 and still carries the code the fix changes

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-09-29 — Fixed: commit d8b7b42241
- 2026-09-29 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0208

**A GP8 file with SyncPoints turned every track green with none marked**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | d8a1dbfd7c395640634ecad03b88a022b2d065e7 |
| Severity | Medium |
| Priority | P3 |
| Status | Fixed |

A GP8 file carrying SyncPoints made every arrangement tab green and the card read 'Sincronizada no Guitar Pro 8' with 0 of 5 tracks marked by the user.

**Steps to reproduce:** 

1. Build a GP8 file with sync points
2. Open the Sincronização tab

**Expected:** Only tracks the user marked are green.

**Observed:** All tabs green.

**Root cause:** The viewer treated sync_source 'gp'/'songsterr' as synced.

**Fixes:** [FIX-0208](../FIX_LOG.md#fix-0208) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-09-30 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Misleading sync status.

**Evidence:**

- CLAUDE.md § Batch processing ('Reversed in the UI (2026-09-30): only the user's marking is "synced"')
- user quote (undated): 'O estado da sincronização está a verde, mas ainda não sincronizei nenhuma das pistas'
- commit fb37c187c0 Only the user's marking turns a track green; GP8/Songsterr sync is a hint
- found_in_version: the fix commit is an ancestor of cb00653 (the first public release, 0.10.0 beta 1, 2026-10-14), so the faulty code only existed in development builds before 0.10.0-beta.1
- found_in_build: d8a1dbfd7c is the parent of the first fix commit fb37c187c0 and still carries the code the fix changes

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-09-30 — Fixed: commit fb37c187c0

## BUG-0260

**Project top bar drew the status chip over the title buttons on narrow screens**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | _pending_ |
| Build / commit | cb00653bedba4cd2f9070ceb2acb8e925c883319 |
| Severity | Low |
| Priority | P4 |
| Status | Closed |

On narrow screens the project top bar's status chip was drawn over the head's buttons ("Editar info", "Versão anterior"); a pre-existing fault made worse by new top-bar buttons.

**Steps to reproduce:** 

1. Open a project in a window under ~1150 px wide

**Expected:** Nothing overlaps.

**Observed:** The status chip covered the head's buttons.

**Root cause:** The head and chip did not shrink; the chip stayed visible at any width.

**Fixes:** [FIX-0260](../FIX_LOG.md#fix-0260) (0.10.0-beta.2)

**Verified:** CLAUDE.md: 'verified with Playwright (... the top bar at 1440/1150/1000/800 px in PT and EN, nothing overlapping or cut)' (by the developer (manual check))

**Resolved:** 2026-10-14 · **Closed:** 2026-10-15

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Cosmetic layout overlap on narrow windows.

**Evidence:**

- CLAUDE.md § Keyboard shortcuts: the "?" list and 1–9 for the modes: "the project top bar stopped drawing the status chip over the head's buttons on narrow screens (pre-existing, made worse by the new buttons)"
- CHANGELOG.en.md 0.10.0 beta 2 — Added: "The project's top bar no longer draws the status over ..."
- commit ab4acf24d1 Keyboard shortcuts in sight: the ? list and 1-9 for the modes
- found_in_version pending: described as pre-existing; detection date not documented

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-10-14 — Fixed: commit ab4acf24d1
- 2026-10-14 — Verified: manual
- 2026-10-15 — Closed: released in 0.10.0-beta.2

## BUG-0263

**Áudio panel did not close with Escape when focus was outside it**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 47a28cae4f8cdbb1e99dc187e9c0f748f599c289 |
| Severity | Low |
| Priority | P4 |
| Status | Fixed |

Escape only closed the panel when it had focus.

**Steps to reproduce:** _pending_

**Expected:** Escape closes it

**Observed:** Panel stays open

**Root cause:** Key handler scoped to the panel.

**Fixes:** [FIX-0263](../FIX_LOG.md#fix-0263) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-10-14 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Cosmetic.

**Evidence:**

- commit 74130132ec Guide checked in the browser; fixes it turned up
- found_in_version: fix 74130132ec (2026-10-14) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 47a28cae4f, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-10-14 — Fixed: commit 74130132ec

## BUG-0284

**Sustained notes played as a short pick in the editor's preview**

| | |
|---|---|
| Detected | 2026-10-16 |
| Reported by | user report |
| Found in | 0.10.0-beta.7 |
| Build / commit | 2d4d4bb5f5a41da9672b7ba5c08853befbb9f217 |
| Severity | Low |
| Priority | P3 |
| Status | Closed |

The editor's tick and the synthesized source gave every note a fixed 0.24/0.28 s with a fast Karplus-Strong decay, so a held note sounded as a single strum.

**Steps to reproduce:** 

1. Play a chart with long sustained notes in the editor (tick or "sintetizada" source)

**Expected:** Each note rings for its sustain.

**Observed:** "when playing back sustained notes in editor they just play as a single strum rather than sustained"

**Root cause:** playNote always 0.24 s and synthesizeArrangement NOTE_LEN 0.28 s with a 0.99 decay; sustain ignored.

**Fixes:** [FIX-0284](../FIX_LOG.md#fix-0284) (0.10.0-beta.9)

**Verified:** CLAUDE.md: 'checked with Node ... and with Playwright on a built invented GP5 (a 2.35 s note still sounds at 1 s and 2 s in the synthesized source ...)' (by the developer (manual check))

**Resolved:** 2026-10-16 · **Closed:** 2026-10-16

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Preview only; the built chart was correct.

**Evidence:**

- CLAUDE.md § Tone preview on the score (`voiceNote` / "Testar tom"): "A held note sounds for its sustain (Liam, 2026-10-16 ...)"
- user quote (2026-10-16, Liam): 'when playing back sustained notes in editor they just play as a single strum rather than sustained'
- TODO.md: 'Sempre foi assim (não vem da beta 7).'
- CHANGELOG.en.md 0.10.0 beta 9 — Fixed: "Long notes ring for their whole length in the preview ..."
- commit c2c679c34a Preview: a held note sounds for its sustain, not as a pick
- found_in_version: TODO.md's note that it does not come from beta 7 implies beta 7 was in use; faulty code present at 2d4d4bb

**History:**

- 2026-10-16 — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-10-16 — Fixed: commit c2c679c34a
- 2026-10-16 — Verified: manual
- 2026-10-16 — Closed: released in 0.10.0-beta.9

## BUG-0294

**The 3D highway grabbed the mouse wheel while the page was scrolled over it**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | user report |
| Found in | _pending_ |
| Build / commit | b0e2145cf6c8231ae18f144f8913e9478342d268 |
| Severity | Low |
| Priority | P3 |
| Status | Closed |

With the free camera, the wheel over the 3D highway zoomed the camera and prevented the page from scrolling, even when the user only meant to scroll the page.

**Steps to reproduce:** 

1. Open the 3D highway
2. Scroll the page with the mouse over it

**Expected:** The page scrolls.

**Observed:** "when im scrolling up and down the page the highway seems to be in focus when i mouse over it"

**Root cause:** The wheel handler always called preventDefault and zoomed.

**Fixes:** [FIX-0294](../FIX_LOG.md#fix-0294) (0.10.0-beta.13)

**Verified:** CLAUDE.md: 'Verified with Playwright: wheel before a click scrolls the page and leaves the distance, after a click zooms, after Esc or a click outside scrolls again' (by the developer (manual check))

**Resolved:** 2026-10-17 · **Closed:** 2026-10-17

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: An annoyance; moving the mouse off the canvas was a workaround.

**Evidence:**

- CLAUDE.md § The 3D note highway ("Pista 3D", `web/highway3d.js`): "the wheel works only once the canvas has been clicked ('when im scrolling up and down the page ...', Liam)"
- user quote (undated, Liam): 'when im scrolling up and down the page the highway seems to be in focus when i mouse over it … maybe it should be click to gain focus?'
- CHANGELOG.en.md Unreleased — Fixed: "The 3D highway grabbed the mouse wheel ..."
- commit 0381b134e2 3D highway: the mouse wheel zooms only after a click on it
- found_in_version pending: the free camera shipped in beta 10 (7ca604f); the version used and the date are not stated

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-10-17 — Fixed: commit 0381b134e2
- 2026-10-17 — Verified: manual
- 2026-10-17 — Closed: released in 0.10.0-beta.13

## BUG-0296

**Cancelling the separation question of the audio bars still analysed the recording**

| | |
|---|---|
| Detected | 2026-10-18 |
| Reported by | the maintainer (manual test) |
| Found in | unreleased |
| Build / commit | c870e573150125f4c32f8f31bb0cb5d3c17ecba5 |
| Severity | Low |
| Priority | P3 |
| Status | Fixed |

Turning "Audio bars" on with nothing separated asks whether to separate the instruments. The bars were drawn before the question, in "Attacks", which asks the server for the mix's onset analysis; that ran behind the dialog and went on after "Cancel", so the user saw work being done that they had just declined.

**Steps to reproduce:** 

1. Open a built project with no separated instruments
2. Tick "Audio bars"
3. Press "Cancel" in the question

**Expected:** Nothing is separated or analysed; the bars show the mix.

**Observed:** GET /jobs/<id>/onset-levels?source=mix was requested as the bars turned on and ran after Cancel (Playwright request log).

**Root cause:** The change handler called setLevels(true) and then asked; drawing in "Attacks" fetches /onset-levels on the server whatever the answer.

**Fixes:** [FIX-0296](../FIX_LOG.md#fix-0296) (0.11.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-10-18 · **Closed:** _pending_

**Evidence:**

- user report, 2026-10-18: 'o aviso de criação de stems quando clico em barras de áudio, mesmo que o cancele, extrai na mesma'
- Playwright request log before the fix: onset-levels?source=mix after Cancel

**History:**

- 2026-10-18 — Open: reported
- 2026-10-18 — Fixed: commit b2efa19bbf

## BUG-0334

**Opening another project quickly could show the previous one's charts or recording**

| | |
|---|---|
| Detected | 2026-10-18 |
| Reported by | code review (Claude, on the maintainer's request) |
| Found in | 0.11.0-beta.2 |
| Build / commit | f64c45e8e176c44bd87c7c7866f741330b443011 |
| Severity | Medium |
| Priority | P2 |
| Status | Fixed |

Late responses of the previous project (arrangements, lyrics, tones, stems, the decoded recording) were applied to the new one.

**Steps to reproduce:** 

1. See the description (found by reading the code)

**Expected:** As described in the solution.

**Observed:** Late responses of the previous project (arrangements, lyrics, tones, stems, the decoded recording) were applied to the new one.

**Root cause:** No check after each await.

**Fixes:** [FIX-0334](../FIX_LOG.md#fix-0334) (0.11.0-beta.4)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-10-18 · **Closed:** _pending_

**Evidence:**

- code review of the whole codebase (six reviewers), confirmed by reading the code

**History:**

- 2026-10-18 — Open: reported
- 2026-10-18 — Fixed: commit e0e939b8ce

## BUG-0336

**The 3D highway could start drawing after being closed while loading**

| | |
|---|---|
| Detected | 2026-10-18 |
| Reported by | code review (Claude, on the maintainer's request) |
| Found in | 0.11.0-beta.2 |
| Build / commit | f64c45e8e176c44bd87c7c7866f741330b443011 |
| Severity | Low |
| Priority | P4 |
| Status | Verified |

close() during the first load was undone when load() returned.

**Steps to reproduce:** 

1. See the description (found by reading the code)

**Expected:** As described in the solution.

**Observed:** close() during the first load was undone when load() returned.

**Root cause:** No generation check.

**Fixes:** [FIX-0336](../FIX_LOG.md#fix-0336) (0.11.0-beta.4)

**Verified:** Playwright: open then close before three.js loads → Highway3D.ready stays false (by the developer (Playwright))

**Resolved:** 2026-10-18 · **Closed:** _pending_

**Evidence:**

- code review of the whole codebase (six reviewers), confirmed by reading the code
- Playwright: open then close before three.js loads → Highway3D.ready stays false

**History:**

- 2026-10-18 — Open: reported
- 2026-10-18 — Fixed: commit e0e939b8ce
- 2026-10-18 — Verified: checked in the browser

## BUG-0341

**Fretboard "All notes" with "only those matching the picked one" shows every note when no note is picked**

| | |
|---|---|
| Detected | 2026-10-20 |
| Reported by | the maintainer (screenshot) |
| Found in | 0.11.1-beta.1 |
| Build / commit | _pending_ |
| Severity | Low |
| Priority | P3 |
| Status | Verified |

With the fretboard's All notes on and the scope set to only those matching the picked one, the whole neck stayed named while no note was picked on the fretboard.

**Steps to reproduce:** 

1. Open a project, tick Braço and Todas as notas
2. Pick "Só as iguais à escolhida" without picking a note

**Expected:** Only the equivalents of the chosen note; nothing until a note is chosen.

**Observed:** Every note of the tuning drawn on the neck.

**Root cause:** fbAllNotesSvg applied the 'same' filter only when a note was picked (pm !== null), so with none it skipped the filter.

**Fixes:** [FIX-0341](../FIX_LOG.md#fix-0341) (0.11.1-beta.2)

**Verified:** Live server, invented GP5 project: with the scope and no pick, 0 pills drawn and the tuning labels shown with the hint; a note clicked on the score picked it and drew its 12 equivalents; a hidden place on the neck still picks; PT 1440 / EN 760 px, no page errors (by the developer (Playwright))

**Resolved:** 2026-10-20 · **Closed:** _pending_

**Evidence:**

- Playwright run of 2026-10-20 on a local server (scratchpad script pw_fb.py)

**History:**

- 2026-10-20 — Open: reported
- 2026-10-20 — In Progress: from the maintainer's screenshot
- 2026-10-20 — Fixed: commit 535e4c7e23
- 2026-10-20 — Verified: Playwright, PT 1440 / EN 760 px

## BUG-0350

**Clicking a note on the score lights the previous note on the fretboard too**

| | |
|---|---|
| Detected | 2026-10-21 |
| Reported by | the maintainer (screenshot) |
| Found in | 0.11.1-beta.2 |
| Build / commit | _pending_ |
| Severity | Low |
| Priority | P3 |
| Status | Verified |

With the fretboard on, clicking a note (no mode selected) moves the cursor to its attack; the overlay of sounding notes kept every note lit at least 0.16 s after its attack, so a short note just before the clicked one was lit with it.

**Steps to reproduce:** 

1. Open a chart whose notes are less than 0.16 s apart
2. Turn on Braço
3. Click a note on the score

**Expected:** Only the clicked note is lit on the neck.

**Observed:** The clicked note and the one before it are lit.

**Root cause:** updateFretboard lit each note for max(sustain, 0.16 s) whatever came next, and its 30 ms lead-in could reach back past the previous attack.

**Fixes:** [FIX-0348](../FIX_LOG.md#fix-0348) (unreleased)

**Verified:** Playwright on an invented riff of sixteenths at 120 BPM (notes 125 ms apart), PT 1440 / EN 760 px (by the developer (Playwright))

**Resolved:** 2026-10-21 · **Closed:** _pending_

**Evidence:**

- 2026-10-21: five clicks lit two notes each with the old code, one each with the fix; no page errors

**History:**

- 2026-10-21 — Open: reported with a screenshot
- 2026-10-21 — Fixed: commit a6a7f3d714
- 2026-10-21 — Verified: Playwright 2026-10-21
