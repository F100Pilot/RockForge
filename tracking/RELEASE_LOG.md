<!-- Generated from tracking/releases.json by `python -m tools.tracking render`. Do not edit by hand: edit the JSON and render again. -->

# Release log

Every version, newest first. What a version fixed and the bugs it still carried come from the bug and fix registers. Process: [docs/RELEASE_PROCESS.md](../docs/RELEASE_PROCESS.md).

## 0.10.0-beta.15

| | |
|---|---|
| Status | Beta |
| Created | 2026-10-17 |
| Published | 2026-10-17 |
| Commit | f9b99838f06eb113086d08ed308d23e7bd78c80a |
| Build | GitHub Actions release workflow |
| Artifacts | https://github.com/F100Pilot/RockForge/releases/tag/v0.10.0-beta.15 |
| Tests | CI (ruff, mypy, pytest, ESLint, Docker build) on the release commit, tools/release_check, and the frozen .exe smoke test of the release workflow |
| Approved by | the maintainer (asked for the release) |

**Goal:** Tones from a pasted text: a request for ChatGPT (or any assistant) and its answer read into the project's tones

**New:**

- Import tones from a text

**Bugs fixed:** —

**Known bugs it carried:** —

**Update / rollback:** Install the new version over it (installer) or replace the folder (portable zip); start.bat pulls by itself. To go back, install an earlier release from the Releases page.

## 0.10.0-beta.14

| | |
|---|---|
| Status | Superseded |
| Created | 2026-10-17 |
| Published | 2026-10-17 |
| Commit | b301ac07482bf49107b94c1634c7278f8f8ae7d0 |
| Build | GitHub Actions release workflow |
| Artifacts | https://github.com/F100Pilot/RockForge/releases/tag/v0.10.0-beta.14 |
| Tests | CI (ruff, mypy, pytest, ESLint, Docker build) on the release commit, tools/release_check, and the frozen .exe smoke test of the release workflow |
| Approved by | the maintainer (asked for the release) |

**Goal:** A GitHub star button beside the coffee one, and one quiet ask after the first project.

**New:**

- A star on GitHub

**Bugs fixed:** —

**Known bugs it carried:** —

**Update / rollback:** Install the new version over it (installer) or replace the folder (portable zip); start.bat pulls by itself. To go back, install an earlier release from the Releases page.

## 0.10.0-beta.13

| | |
|---|---|
| Status | Superseded |
| Created | 2026-10-17 |
| Published | 2026-10-17 |
| Commit | 2b7eb07575880a4c125d6f8739b0c4a92d4f75a6 |
| Build | GitHub Actions release workflow |
| Artifacts | https://github.com/F100Pilot/RockForge/releases/tag/v0.10.0-beta.13 |
| Tests | CI (ruff, mypy, pytest, ESLint, Docker build) on the release commit, tools/release_check, and the frozen .exe smoke test of the release workflow |
| Approved by | the maintainer (asked for the release) |

**Goal:** The score legend, About RockForge with a copyable report, a technical log, the versioning and bug registers; fixes for Wwise detection and the 3D highway's mouse wheel.

**New:**

- Score legend
- About RockForge
- Technical log

**Improved:**

- Version numbers follow Semantic Versioning
- The `.exe`'s console output moved to `logs/console.log`, with the three previous runs kept; `start.bat` keeps the previous `logs\worker.log` as `worker.prev.log`

**Bugs fixed:** 

- [BUG-0292](bugs/psarc.md#bug-0292) WWISEROOT pointing at another Wwise version hid a usable 2023.1 ("Wwise not installed")
- [BUG-0293](bugs/psarc.md#bug-0293) A failed Wwise conversion read "no Wwise found" and the silent .psarc showed as playable
- [BUG-0294](bugs/viewer.md#bug-0294) The 3D highway grabbed the mouse wheel while the page was scrolled over it

**Known bugs it carried:** —

**Update / rollback:** Install the new version over it (installer) or replace the folder (portable zip); start.bat pulls by itself. To go back, install an earlier release from the Releases page.

## 0.10.0-beta.12

| | |
|---|---|
| Status | Superseded |
| Created | 2026-10-17 |
| Published | 2026-10-17 |
| Commit | b0e2145cf6c8231ae18f144f8913e9478342d268 |
| Build | GitHub Actions run 39053887931 (https://github.com/F100Pilot/RockForge/actions/runs/39053887931) |
| Artifacts | https://github.com/F100Pilot/RockForge/releases/tag/v0.10.0-beta.12 |
| Tests | CI (ruff, mypy, pytest, ESLint, Docker build) on the version commit, and the frozen .exe smoke test of the release workflow |
| Approved by | the maintainer (asked for the release) |

**Goal:** Beta for testers: edit notes — drag, and change the fret with the arrows, and fixes.

**New:**

- Edit notes — drag, and change the fret with the arrows

**Bugs fixed:** 

- [BUG-0289](bugs/editor.md#bug-0289) Inserting a note in a solo snapped to the previous note's beat and made a chord
- [BUG-0290](bugs/editor.md#bug-0290) A deleted or edited note was still heard until the rebuild
- [BUG-0291](bugs/sync.md#bug-0291) "Song start" after an automatic sync moved only the first stretch of the song

**Known bugs it carried:** —

**Update / rollback:** Install the new version over it (installer) or replace the folder (portable zip); start.bat pulls by itself. To go back, install an earlier release from the Releases page.

**Note:** Published automatically when CI passed on its commit; the tag v0.10.0-beta.12 is that commit.

## 0.10.0-beta.11

| | |
|---|---|
| Status | Superseded |
| Created | 2026-10-17 |
| Published | 2026-10-17 |
| Commit | 8b5b49a54bb03d085716b529abf41e671788c2fa |
| Build | GitHub Actions run 39014176593 (https://github.com/F100Pilot/RockForge/actions/runs/39014176593) |
| Artifacts | https://github.com/F100Pilot/RockForge/releases/tag/v0.10.0-beta.11 |
| Tests | CI (ruff, mypy, pytest, ESLint, Docker build) on the version commit, and the frozen .exe smoke test of the release workflow |
| Approved by | the maintainer (asked for the release) |

**Goal:** One fix: open-string chords drawn as a solid block in game.

**Bugs fixed:** 

- [BUG-0288](bugs/game.md#bug-0288) Open-string chords without sustain were painted solid top to bottom in game

**Known bugs it carried:** —

**Update / rollback:** Install the new version over it (installer) or replace the folder (portable zip); start.bat pulls by itself. To go back, install an earlier release from the Releases page.

**Note:** Published automatically when CI passed on its commit; the tag v0.10.0-beta.11 is that commit.

## 0.10.0-beta.10

| | |
|---|---|
| Status | Superseded |
| Created | 2026-10-16 |
| Published | 2026-10-16 |
| Commit | d73ecc0a067ab1fad10738ab5c81d5b86b527e98 |
| Build | GitHub Actions run 38981804533 (https://github.com/F100Pilot/RockForge/actions/runs/38981804533) |
| Artifacts | https://github.com/F100Pilot/RockForge/releases/tag/v0.10.0-beta.10 |
| Tests | CI (ruff, mypy, pytest, ESLint, Docker build) on the version commit, and the frozen .exe smoke test of the release workflow |
| Approved by | the maintainer (asked for the release) |

**Goal:** Beta for testers: 3D highway with a free camera, recording attacks — choose the instrument, and fixes.

**New:**

- 3D highway with a free camera
- Recording attacks — choose the instrument

**Bugs fixed:** 

- [BUG-0285](bugs/sync.md#bug-0285) Recording attacks (and the auto-sync) sat late by the intro silence
- [BUG-0286](bugs/audio.md#bug-0286) Separated stems showed many false attacks from the separation's residue
- [BUG-0287](bugs/sync.md#bug-0287) Reload GP with the file's own audio kept the old recording's stems and tone detection

**Known bugs it carried:** 

- [BUG-0288](bugs/game.md#bug-0288) Open-string chords without sustain were painted solid top to bottom in game (High, now Closed)

**Update / rollback:** Install the new version over it (installer) or replace the folder (portable zip); start.bat pulls by itself. To go back, install an earlier release from the Releases page.

**Note:** Published automatically when CI passed on its commit; the tag v0.10.0-beta.10 is that commit.

## 0.10.0-beta.9

| | |
|---|---|
| Status | Superseded |
| Created | 2026-10-16 |
| Published | 2026-10-16 |
| Commit | ba8f5fc7180b87c6d1da0b7f89ea321b6ca593e2 |
| Build | GitHub Actions run 38969486294 (https://github.com/F100Pilot/RockForge/actions/runs/38969486294) |
| Artifacts | — |
| Tests | CI (ruff, mypy, pytest, ESLint, Docker build) on the version commit, and the frozen .exe smoke test of the release workflow |
| Approved by | the maintainer (asked for the release) |

**Goal:** Beta for testers: recording attacks, and fixes.

**New:**

- Recording attacks

**Bugs fixed:** 

- [BUG-0284](bugs/viewer.md#bug-0284) Sustained notes played as a short pick in the editor's preview

**Known bugs it carried:** 

- [BUG-0285](bugs/sync.md#bug-0285) Recording attacks (and the auto-sync) sat late by the intro silence (Medium, now Closed)

**Update / rollback:** Install the new version over it (installer) or replace the folder (portable zip); start.bat pulls by itself. To go back, install an earlier release from the Releases page.

**Note:** Built and published by the release workflow from the tag v0.10.0-beta.9 on commit ba8f5fc718 (run history of release.yml). The GitHub release and the tag no longer exist; the Releases page starts at beta 10.

## 0.10.0-beta.8

| | |
|---|---|
| Status | Superseded |
| Created | 2026-10-16 |
| Published | 2026-10-16 |
| Commit | 611a82e924631764440ca2a7d417c63c39ba7675 |
| Build | GitHub Actions run 38959448656 (https://github.com/F100Pilot/RockForge/actions/runs/38959448656) |
| Artifacts | — |
| Tests | CI (ruff, mypy, pytest, ESLint, Docker build) on the version commit, and the frozen .exe smoke test of the release workflow |
| Approved by | the maintainer (asked for the release) |

**Goal:** Beta for testers: the “A new version is out” notice arrives sooner, and fixes.

**Improved:**

- The “A new version is out” notice arrives sooner

**Bugs fixed:** 

- [BUG-0282](bugs/app.md#bug-0282) The New project wizard could not take a cover image from the computer
- [BUG-0283](bugs/exe.md#bug-0283) The .exe never used the GPU for the ML stages

**Known bugs it carried:** 

- [BUG-0284](bugs/viewer.md#bug-0284) Sustained notes played as a short pick in the editor's preview (Low, now Closed)

**Update / rollback:** Install the new version over it (installer) or replace the folder (portable zip); start.bat pulls by itself. To go back, install an earlier release from the Releases page.

**Note:** Built and published by the release workflow from the tag v0.10.0-beta.8 on commit 611a82e924 (run history of release.yml). The GitHub release and the tag no longer exist; the Releases page starts at beta 10.

## 0.10.0-beta.7

| | |
|---|---|
| Status | Superseded |
| Created | 2026-10-15 |
| Published | 2026-10-16 |
| Commit | 7ca91539fe31adfbfae1c50bb3271dadceff5662 |
| Build | GitHub Actions run 38888935893 (https://github.com/F100Pilot/RockForge/actions/runs/38888935893) |
| Artifacts | — |
| Tests | CI (ruff, mypy, pytest, ESLint, Docker build) on the version commit, and the frozen .exe smoke test of the release workflow |
| Approved by | the maintainer (asked for the release) |

**Goal:** Beta for testers: sync automatically, with a variable tempo — experimental, an icon of its own, and fixes.

**New:**

- Sync automatically, with a variable tempo — experimental
- An icon of its own

**Bugs fixed:** 

- [BUG-0274](bugs/exe.md#bug-0274) Black console windows flashed in the .exe whenever a child program ran
- [BUG-0275](bugs/psarc.md#bug-0275) Wwise installed but reported as "ROCKFORGE_WWISE_ROOT is not set"
- [BUG-0276](bugs/sync.md#bug-0276) A sync mode was selected on entry, so the first click on a note re-timed the song
- [BUG-0277](bugs/audio.md#bug-0277) librosa runner failed with an external ML Python: its packaging folder shadowed pip's
- [BUG-0278](bugs/import.md#bug-0278) After a D.C./D.S. the 1st-time ending was played again before the 2nd
- [BUG-0279](bugs/game.md#bug-0279) Every short note carried a sustain tail on the highway
- [BUG-0280](bugs/import.md#bug-0280) PDF import: a grace number drawn over the next note's digits joined into other frets
- [BUG-0281](bugs/import.md#bug-0281) PDF import (OCR): small 9/6/3 grace notes were read as normal notes

**Known bugs it carried:** 

- [BUG-0283](bugs/exe.md#bug-0283) The .exe never used the GPU for the ML stages (Medium, now Closed)
- [BUG-0284](bugs/viewer.md#bug-0284) Sustained notes played as a short pick in the editor's preview (Low, now Closed)

**Update / rollback:** Install the new version over it (installer) or replace the folder (portable zip); start.bat pulls by itself. To go back, install an earlier release from the Releases page.

**Note:** Built and published by the release workflow from the tag v0.10.0-beta.7 on commit 7ca91539fe (run history of release.yml). The GitHub release and the tag no longer exist; the Releases page starts at beta 10. The CHANGELOG dates it 2026-10-15, when its number was set (2d4d4bb); it was published on 2026-10-16 from a later commit, with two more fixes.

## 0.10.0-beta.6

| | |
|---|---|
| Status | Superseded |
| Created | 2026-10-15 |
| Published | 2026-10-15 |
| Commit | 8494322e3f34a7427e9ed710687f2001493e9bb4 |
| Build | GitHub Actions run 38812870334 (https://github.com/F100Pilot/RockForge/actions/runs/38812870334) |
| Artifacts | — |
| Tests | CI (ruff, mypy, pytest, ESLint, Docker build) on the version commit, and the frozen .exe smoke test of the release workflow |
| Approved by | the maintainer (asked for the release) |

**Goal:** Beta for testers: “Mark by ear”, for tabs that were never synced, and fixes.

**New:**

- “Mark by ear”, for tabs that were never synced

**Bugs fixed:** 

- [BUG-0273](bugs/exe.md#bug-0273) In the .exe, installed extra components were unused when the ML Python setting was empty

**Known bugs it carried:** 

- [BUG-0278](bugs/import.md#bug-0278) After a D.C./D.S. the 1st-time ending was played again before the 2nd (Medium, now Closed)
- [BUG-0279](bugs/game.md#bug-0279) Every short note carried a sustain tail on the highway (Medium, now Closed)

**Update / rollback:** Install the new version over it (installer) or replace the folder (portable zip); start.bat pulls by itself. To go back, install an earlier release from the Releases page.

**Note:** Built and published by the release workflow from the tag 0.10.0-beta.6 on commit 8494322e3f (run history of release.yml). The GitHub release and the tag no longer exist; the Releases page starts at beta 10.

## 0.10.0-beta.5

| | |
|---|---|
| Status | Superseded |
| Created | 2026-10-15 |
| Published | 2026-10-15 |
| Commit | 248e46e787bf3ba0b6acde98e05fec53eb78a3e3 |
| Build | GitHub Actions run 38807973611 (https://github.com/F100Pilot/RockForge/actions/runs/38807973611) |
| Artifacts | — |
| Tests | CI (ruff, mypy, pytest, ESLint, Docker build) on the version commit, and the frozen .exe smoke test of the release workflow |
| Approved by | the maintainer (asked for the release) |

**Goal:** Beta for testers: fret-hand position (FHP) editor, bass arrangement, new version notice, and fixes.

**New:**

- Fret-hand position (FHP) editor
- Bass arrangement
- New version notice
- The `.exe` installs the extra components by itself
- Wwise is found by itself

**Improved:**

- The automatic fret-hand positions were redone
- The XML for DLC Builder now carries the same automatic fret-hand positions as the `.psarc` (they used to be worked out two different ways)

**Bugs fixed:** 

- [BUG-0267](bugs/release.md#bug-0267) Release workflow ignored a tag without the leading v; the beta 3 release had no files
- [BUG-0268](bugs/exe.md#bug-0268) In the .exe, the "Download" buttons did nothing
- [BUG-0269](bugs/import.md#bug-0269) The Guitar Pro file's capo was ignored
- [BUG-0270](bugs/psarc.md#bug-0270) A difficulty level holding only open strings had no anchor in the .psarc
- [BUG-0271](bugs/psarc.md#bug-0271) Without Wwise, the .psarc carried the whole WAV (~30 MB) where the game never reads it
- [BUG-0272](bugs/dlc-builder.md#bug-0272) XML, viewer and native SNG placed different automatic fret-hand positions

**Known bugs it carried:** 

- [BUG-0273](bugs/exe.md#bug-0273) In the .exe, installed extra components were unused when the ML Python setting was empty (High, now Closed)

**Update / rollback:** Install the new version over it (installer) or replace the folder (portable zip); start.bat pulls by itself. To go back, install an earlier release from the Releases page.

**Note:** Built and published by the release workflow from the tag 0.10.0-beta.5 on commit 248e46e787 (run history of release.yml). The GitHub release and the tag no longer exist; the Releases page starts at beta 10.

## 0.10.0-beta.4

| | |
|---|---|
| Status | Not published |
| Created | 2026-10-15 |
| Published | not published |
| Commit | a89c6a49ccb9e548d7f486008ab165ae74568b1d |
| Build | a manual dry run, GitHub Actions run 38800774563; never published |
| Artifacts | — |
| Tests | none recorded |
| Approved by | _pending_ |

**Goal:** Prepared but never published; its content went out in 0.10.0-beta.5.

**Bugs fixed:** —

**Known bugs it carried:** 

- [BUG-0267](bugs/release.md#bug-0267) Release workflow ignored a tag without the leading v; the beta 3 release had no files (High, now Fixed)

**Update / rollback:** _pending_

**Note:** CHANGELOG (0.10.0 beta 5): "Includes what was prepared for beta 4, which was never published". The commit is the one that set the version.

## 0.10.0-beta.3

| | |
|---|---|
| Status | Superseded |
| Created | 2026-10-15 |
| Published | 2026-10-15 |
| Commit | bebcf2b5d6e7d074829b4c01106ada00a7fcdb97 |
| Build | pending: no tag push run is recorded |
| Artifacts | — |
| Tests | CI (ruff, mypy, pytest, ESLint, Docker build) on the version commit, and the frozen .exe smoke test of the release workflow |
| Approved by | the maintainer (asked for the release) |

**Goal:** Support button and tutorial video.

**New:**

- A **“Buy me a coffee”** button (PayPal) on the home page and a **Support the project** card in Settings → General
- A **tutorial video** (Portuguese and English) and a GIF in the README

**Bugs fixed:** —

**Known bugs it carried:** 

- [BUG-0267](bugs/release.md#bug-0267) Release workflow ignored a tag without the leading v; the beta 3 release had no files (High, now Fixed)

**Update / rollback:** Install the new version over it (installer) or replace the folder (portable zip); start.bat pulls by itself. To go back, install an earlier release from the Releases page.

**Note:** Published per the CHANGELOG; no tag push run of the release workflow is recorded for it (a manual run on ed59086 at 12:58 could attach files to an existing release). The commit is the one that set the version: the release was built from it or a later commit.

## 0.10.0-beta.2

| | |
|---|---|
| Status | Superseded |
| Created | 2026-10-15 |
| Published | 2026-10-15 |
| Commit | 9321069994e940bcc999bf2f8481e881be33972d |
| Build | GitHub Actions run 38721278055 (https://github.com/F100Pilot/RockForge/actions/runs/38721278055) |
| Artifacts | — |
| Tests | CI (ruff, mypy, pytest, ESLint, Docker build) on the version commit, and the frozen .exe smoke test of the release workflow |
| Approved by | the maintainer (asked for the release) |

**Goal:** The Windows downloads (installer, portable zip), built and smoke-tested by the release workflow; security hardening; first round of fixes.

**New:**

- 3D highway with Rocksmith's symbols
- Undo / Redo
- Changes not yet applied are saved automatically
- Repeat a passage (A–B)
- Keyboard shortcuts in sight
- Linked notes
- Arpeggios
- The PSARC check ("Before you use it", on the Export page) also checks the links and the arpeggios
- The project's top bar no longer draws the status over "Edit info"/"Previous version" on narrow screens: the status and "Pending" shrink and "Download" keeps only its icon

**Improved:**

- Windows installer and portable zip
- Licences made clear: the code adapted from alphaTab is in two files of its own, under MPL-2.0; everything else is MIT

**Bugs fixed:** 

- [BUG-0246](bugs/security.md#bug-0246) esc() did not escape quotes: third-party text could run code in the page (XSS)
- [BUG-0247](bugs/security.md#bug-0247) Server answered any Host name, so a DNS-rebound web page could reach the local API
- [BUG-0248](bugs/security.md#bug-0248) A request with Origin: null was not treated as cross-origin
- [BUG-0249](bugs/security.md#bug-0249) Responses lacked nosniff and anti-framing headers
- [BUG-0250](bugs/psarc.md#bug-0250) Docker image made no .psarc (the [psarc] extra was not installed)
- [BUG-0251](bugs/import.md#bug-0251) GP8 embedded audio in .opus/.webm/.aac/.mp4/.wma was detected, then refused by the build
- [BUG-0252](bugs/sync.md#bug-0252) A double click on "Apply and rebuild" created two versions
- [BUG-0253](bugs/app.md#bug-0253) A late answer reopened a closed project; detection pollers drew into the next project
- [BUG-0254](bugs/lyrics.md#bug-0254) Times rounded to "1:60" in lyric lengths and "[00:60.00]" in the exported LRC
- [BUG-0255](bugs/sync.md#bug-0255) Negative intro silence was accepted and misaligned sync corrections after a tempo change
- [BUG-0256](bugs/app.md#bug-0256) The "Lead/Rhythm (exp.)" checkbox did nothing
- [BUG-0257](bugs/psarc.md#bug-0257) The detected tuning deviation (cents) never reached the .psarc
- [BUG-0258](bugs/app.md#bug-0258) The six "Afinação (MIDI)" inputs did nothing
- [BUG-0259](bugs/app.md#bug-0259) Seven button requests could throw an uncaught error the offline banner did not see
- [BUG-0260](bugs/viewer.md#bug-0260) Project top bar drew the status chip over the title buttons on narrow screens
- [BUG-0261](bugs/import.md#bug-0261) PDF import put the next staff's H/P letters into the lyrics
- [BUG-0265](bugs/exe.md#bug-0265) In the .exe, a project without tones of its own made no .psarc
- [BUG-0266](bugs/app.md#bug-0266) start.bat's git pull stalled on Windows with repeated "Unlink of file ... failed" prompts

**Known bugs it carried:** —

**Update / rollback:** Install the new version over it (installer) or replace the folder (portable zip); start.bat pulls by itself. To go back, install an earlier release from the Releases page.

**Note:** Built and published by the release workflow from the tag v0.10.0-beta.2 on commit 9321069994 (run history of release.yml). The GitHub release and the tag no longer exist; the Releases page starts at beta 10.

## 0.10.0-beta.1

| | |
|---|---|
| Status | Superseded |
| Created | 2026-10-14 |
| Published | 2026-10-14 |
| Commit | cb00653bedba4cd2f9070ceb2acb8e925c883319 |
| Build | none: a source release, no downloads |
| Artifacts | — |
| Tests | CI (ruff, mypy, pytest, ESLint, Docker build) on the version commit |
| Approved by | the maintainer (asked for the release) |

**Goal:** First public version, in beta: ready to use, awaiting more testing in game and on a PC without Python before 1.0.0.

**New:**

- Guitar Pro 3, 4, 5 and 7/8 (`.gp`) files: notes, frets, techniques, tempos, sections and lyrics read from the file; repeats, voltas and D.S./D.C
- No Guitar Pro file: the tab imported from a Songsterr link (with the per-bar video timings), or a PDF or picture of the tab converted by PDF-to-GP5
- The recording: an audio file, the audio inside the GP8 file, or the audio of a YouTube video
- A 4-step wizard and a batch mode for whole albums; album, year, cover and synced lyrics looked up online and chosen by you
- Song start, BPM stretch, "Fix from here", dragging notes and passages, aligning bars, per-bar tempo, and a main track whose corrections reach the others
- Each track marked as synced on its own
- Note editor (frets, techniques, insert, delete, copy and paste) and section editor on the score
- Rocksmith-style 3D highway
- Tone editor with the game's gear, a tone library, and the tones of the songs in your `dlc` folder
- Per-track tones, tone changes, tone detection and a suggested tone for each part
- Lyrics from the GP file, LRCLIB or the recording (WhisperX), lined up with the voice and editable beside the score
- A native, playable `.psarc` (with Wwise) and a DLC Builder project, always both
- Dynamic difficulty, chord fingering and hand shapes
- `.psarc` check and installation into the game's `dlc` folder
- Export back to Guitar Pro: the corrected tempos in a copy of your file, or the edited notes in a new GP5
- MIT licence, third-party notices and legal notice; home page, user guide and technical documentation in Portuguese and English; `start.bat` messages in both languages

**Bugs fixed:** 

- [BUG-0001](bugs/dlc-builder.md#bug-0001) In-game song ended seconds in: only one phrase iteration was written
- [BUG-0002](bugs/audio.md#bug-0002) Silent in-game audio: the .wem had no seek table
- [BUG-0003](bugs/dlc-builder.md#bug-0003) DLC Builder import crashed (NullReferenceException) on missing arrangementProperties
- [BUG-0004](bugs/dlc-builder.md#bug-0004) Song2014 XML lacked elements DLC Builder's schema expects
- [BUG-0005](bugs/sync.md#bug-0005) GP sync offset kept the recording's own intro gap, so chart and audio drifted apart
- [BUG-0006](bugs/dlc-builder.md#bug-0006) In-game chart re-zeroed despite the lead-in (offset left at 0)
- [BUG-0007](bugs/dlc-builder.md#bug-0007) DLC Builder import crashed at offset 0: no room for the count-in phrase
- [BUG-0008](bugs/import.md#bug-0008) Minimum lead-in warning shown on every GP build
- [BUG-0009](bugs/viewer.md#bug-0009) Note viewer string colours wrong and reversed
- [BUG-0010](bugs/game.md#bug-0010) Palm-muted chords rendered as a corrupt highway sprite
- [BUG-0011](bugs/sync.md#bug-0011) Drift correction shifted notes far outside the corrected excerpt
- [BUG-0012](bugs/game.md#bug-0012) Plain notes drew a spurious technique glyph (zero-valued attributes)
- [BUG-0013](bugs/sync.md#bug-0013) Pending drag anchors did not round-trip through a rebuild with a pending tempo/offset
- [BUG-0014](bugs/viewer.md#bug-0014) Note tick desynced after seeking backward
- [BUG-0015](bugs/app.md#bug-0015) pip could not install [ml,lyrics] together: ResolutionTooDeep
- [BUG-0016](bugs/app.md#bug-0016) start.bat left the broker down silently when Redis was missing
- [BUG-0017](bugs/lyrics.md#bug-0017) LRC/UltraStar lyrics supplied at creation never shown in the editor
- [BUG-0018](bugs/app.md#bug-0018) Cover art dropped on rebuild
- [BUG-0019](bugs/app.md#bug-0019) [ml] install failed on Windows building scipy from source
- [BUG-0020](bugs/lyrics.md#bug-0020) WhisperX silently unavailable: torchaudio 2.5 removed AudioMetaData
- [BUG-0021](bugs/audio.md#bug-0021) Jobs stuck at the normalize/lyrics stage: ffmpeg inherited the console's stdin
- [BUG-0022](bugs/viewer.md#bug-0022) Tab viewer playback drifted mid-song (aligned at start, off after seeking)
- [BUG-0023](bugs/viewer.md#bug-0023) Recording playback stopped and waveform flickered while a job was open
- [BUG-0024](bugs/tones.md#bug-0024) '+ Criar / editar tons' did nothing (tone builder had no JavaScript)
- [BUG-0025](bugs/lyrics.md#bug-0025) Lyric detection hung for 40+ minutes at the WhisperX import (Celery CUDA deadlock)
- [BUG-0026](bugs/lyrics.md#bug-0026) A CUDA warm-up thread deadlocked the first detection on Windows
- [BUG-0027](bugs/app.md#bug-0027) Detection progress lost after the first commit: Job.params reassigned as the same dict
- [BUG-0028](bugs/dlc-builder.md#bug-0028) DLC Builder build failed for want of a .phrase-levels file
- [BUG-0029](bugs/lyrics.md#bug-0029) Lyric detection progress looked frozen at 8-10% with no feedback
- [BUG-0030](bugs/sync.md#bug-0030) Pending BPM edit lost on arrangement tab switch
- [BUG-0031](bugs/import.md#bug-0031) Tied notes emitted as extra attacks ('4 notes show as 5')
- [BUG-0032](bugs/lyrics.md#bug-0032) GP-embedded lyrics were never shown in the UI, so they looked missing
- [BUG-0033](bugs/import.md#bug-0033) .gp (GP7/8) uploads rejected at the API although the parser supported them
- [BUG-0034](bugs/import.md#bug-0034) GP7 parser missed note-level vibrato
- [BUG-0035](bugs/viewer.md#bug-0035) Intro silence (lead_in_s) invisible in the viewer
- [BUG-0036](bugs/lyrics.md#bug-0036) Lyrics drawn early after a lead-in; added words landed off-cursor
- [BUG-0037](bugs/viewer.md#bug-0037) Staff string labels always read E A D G B e, whatever the tuning
- [BUG-0038](bugs/import.md#bug-0038) YouTube ingest hung (whole playlist download, yt-dlp ffmpeg inherited stdin)
- [BUG-0039](bugs/import.md#bug-0039) Basic Pitch transcription failed: TF SavedModel 'nmp' would not load
- [BUG-0040](bugs/app.md#bug-0040) Closing the tab did not always stop the server (uvicorn --reload)
- [BUG-0041](bugs/import.md#bug-0041) Basic Pitch failed after WhisperX availability check imported speechbrain
- [BUG-0042](bugs/app.md#bug-0042) API shut itself down while its tab was only in the background
- [BUG-0043](bugs/app.md#bug-0043) Closing the tab no longer stopped the server: a hidden heartbeat cancelled /closing
- [BUG-0044](bugs/app.md#bug-0044) Job stuck in RUNNING could never be deleted
- [BUG-0045](bugs/viewer.md#bug-0045) Chord names collided with low-string notes on the score
- [BUG-0046](bugs/tones.md#bug-0046) Tone detection's flatness feature always contributed zero
- [BUG-0047](bugs/sync.md#bug-0047) Guided first-note flow created a hidden anchor instead of updating the start field
- [BUG-0048](bugs/sync.md#bug-0048) Removing a single pending correction left its marker on the score
- [BUG-0049](bugs/import.md#bug-0049) GP5 tempo change authored on another track was ignored (grid stuck at the first tempo)
- [BUG-0050](bugs/viewer.md#bug-0050) Note tick ignored the arrangement's tuning (wrong pitch in drop/open tunings)
- [BUG-0051](bugs/dlc-builder.md#bug-0051) A tone change landing exactly on a note made DLC Builder throw
- [BUG-0052](bugs/tones.md#bug-0052) 'Voz simples (sem tom)' preview still coloured by the cabinet EQ
- [BUG-0053](bugs/tones.md#bug-0053) Clearing all tones or tone changes did not persist after rebuild
- [BUG-0054](bugs/viewer.md#bug-0054) Removed tone markers stayed on the score until another redraw
- [BUG-0055](bugs/psarc.md#bug-0055) Native PSARC never appeared in the song list: retail enumeration layout missing
- [BUG-0056](bugs/psarc.md#bug-0056) Native PSARC froze on the note highway: the SNG was not a real .sng file
- [BUG-0057](bugs/psarc.md#bug-0057) Game crashed on load: the SNG beat record was 12 bytes instead of 16
- [BUG-0058](bugs/psarc.md#bug-0058) Every note rendered a slide: the SNG no-slide sentinel was 0 instead of -1
- [BUG-0059](bugs/psarc.md#bug-0059) Note highway crashed on play: every SNG anchor started at t=0
- [BUG-0060](bugs/psarc.md#bug-0060) Chart showed no notes and crashed when the GP file had no section markers
- [BUG-0061](bugs/psarc.md#bug-0061) Song list showed '0 notes' and a blank difficulty bar for native PSARCs
- [BUG-0062](bugs/psarc.md#bug-0062) Song dropped from the list: toolkit.version was not numeric
- [BUG-0063](bugs/psarc.md#bug-0063) Song dropped from the list: PSARC TOC name hashes were zero
- [BUG-0064](bugs/psarc.md#bug-0064) No cover shown in game: placeholder DDS had mip count 0
- [BUG-0065](bugs/audio.md#bug-0065) Song-select preview played the full track over itself
- [BUG-0066](bugs/audio.md#bug-0066) Overlapping copies of the preview played while browsing
- [BUG-0067](bugs/psarc.md#bug-0067) Fretboard view thrashed and hid low notes (one anchor per fret change)
- [BUG-0068](bugs/psarc.md#bug-0068) In-game difficulty slider read a tiny/garbled maximum
- [BUG-0069](bugs/import.md#bug-0069) Sustains ran into the next note on the same string
- [BUG-0070](bugs/psarc.md#bug-0070) Song dropped from the list: a partial raw PSARC block stored zlength 0
- [BUG-0071](bugs/psarc.md#bug-0071) Game crashed at the start of a section: SNG anchors crossed phrase boundaries
- [BUG-0072](bugs/psarc.md#bug-0072) DD levels kept slide anchor-extensions and hand shapes for notes they dropped: crash
- [BUG-0073](bugs/psarc.md#bug-0073) Low DD levels showed notes only at the start of a long phrase
- [BUG-0074](bugs/psarc.md#bug-0074) Section-less song with no lead-in got no phrase segmentation
- [BUG-0075](bugs/psarc.md#bug-0075) DD always started from level 0: SongDifficulty and mastery fields were zero
- [BUG-0076](bugs/psarc.md#bug-0076) Fret-hand anchor sat below the chord being played
- [BUG-0077](bugs/psarc.md#bug-0077) Crash at the first 5-7 octave riff in 'Free' (native PSARC)
- [BUG-0078](bugs/psarc.md#bug-0078) Corrupt full-height vertical bar at palm-muted chord runs (single-note bit in ChordNotes)
- [BUG-0079](bugs/psarc.md#bug-0079) Crash entering the next DD phrase: PhraseIterationLinks written as 0
- [BUG-0080](bugs/psarc.md#bug-0080) First phrase swallowed the silent intro and no END phrase (GP sections)
- [BUG-0081](bugs/psarc.md#bug-0081) Crash on DD phrase entry: full-chart anchors on every level
- [BUG-0082](bugs/dlc-builder.md#bug-0082) Bends vanished in DLC Builder builds: XML had no <bendValues>
- [BUG-0083](bugs/psarc.md#bug-0083) Native PSARC stage stayed dark and the title card was skipped: empty showlights
- [BUG-0084](bugs/lyrics.md#bug-0084) Native lyrics never appeared: vocal note was 0 instead of the 254 sentinel
- [BUG-0085](bugs/lyrics.md#bug-0085) Native lyrics never appeared: vocals SNG had an empty glyph atlas
- [BUG-0086](bugs/psarc.md#bug-0086) Crash at the first bent chord (ChordNotes UsedCount before the bend array)
- [BUG-0087](bugs/psarc.md#bug-0087) Bends looked smaller in game (point at the attack = prebend)
- [BUG-0088](bugs/dlc-builder.md#bug-0088) arrangementProperties tapping and slapPop hardcoded 0
- [BUG-0089](bugs/import.md#bug-0089) GP7 pinch harmonics read as none (HType compared case-sensitively)
- [BUG-0090](bugs/import.md#bug-0090) GP7 slide-out lost when combined with a slide-in flag
- [BUG-0091](bugs/psarc.md#bug-0091) DD difficulty bars flat-topped at the level-11 cap
- [BUG-0092](bugs/viewer.md#bug-0092) Nonsense '? (0n/0c)' tab for the vocals XML
- [BUG-0093](bugs/lyrics.md#bug-0093) Lyrics scrolled in game as a wall of text (no line breaks within long lines)
- [BUG-0094](bugs/psarc.md#bug-0094) Game crashed at a gapped octave while scoring: chord template unused strings were MIDI 0
- [BUG-0095](bugs/psarc.md#bug-0095) Game crashed while scoring notes in late sections: note PhraseId out of range
- [BUG-0096](bugs/tones.md#bug-0096) Native PSARC played a default tone despite the user's custom tones
- [BUG-0097](bugs/audio.md#bug-0097) Song-select preview blasted over the song list (uncalibrated bus volume)
- [BUG-0098](bugs/import.md#bug-0098) Notes off the 24-fret neck dropped silently
- [BUG-0099](bugs/audio.md#bug-0099) Songs sounded quiet in game next to official DLC (-16 LUFS target)
- [BUG-0100](bugs/sync.md#bug-0100) Conflicting sync anchors crashed the build with a cryptic TempoMap error
- [BUG-0101](bugs/sync.md#bug-0101) A local sync stretch re-inflated sustains into fused 'tall pillars'
- [BUG-0102](bugs/sync.md#bug-0102) "Mover seguintes", tap and re-tempo moved notes the wrong way once an anchor existed
- [BUG-0103](bugs/sync.md#bug-0103) "Mover seguintes" also moved the notes before the click
- [BUG-0104](bugs/sync.md#bug-0104) Dragging a note to the playback cursor was unreliable
- [BUG-0105](bugs/viewer.md#bug-0105) Zooming lost the place in the song
- [BUG-0106](bugs/viewer.md#bug-0106) Shift+click/drag on the score selected label text like page text
- [BUG-0107](bugs/sync.md#bug-0107) Pending-corrections list went stale after a plain mouse drag
- [BUG-0108](bugs/viewer.md#bug-0108) A track resting through the outro was drawn shorter than the song
- [BUG-0109](bugs/lyrics.md#bug-0109) A native GPU crash (Turing/cuDNN) aborted lyric detection and recurred on every run
- [BUG-0110](bugs/lyrics.md#bug-0110) ctranslate2 could not load torch's bundled cuDNN on Windows and crashed
- [BUG-0111](bugs/app.md#bug-0111) Songs with GP/LRC/edited lyrics read 'sem letra' in the checklist
- [BUG-0112](bugs/psarc.md#bug-0112) Corrupt lateral highway blur on fast repeated chords: high density never set
- [BUG-0113](bugs/psarc.md#bug-0113) Graphical glitch at the first notes: song-start anchor took the LAST phrase
- [BUG-0114](bugs/psarc.md#bug-0114) Corrupt highway bars on sustained chords: no ChordNotes entry for plain sustained chords
- [BUG-0115](bugs/sync.md#bug-0115) Automatic sync jumped the BPM ~50% on triplet/compound feels
- [BUG-0116](bugs/app.md#bug-0116) ⚙️ Definições unreachable while a song was open
- [BUG-0117](bugs/import.md#bug-0117) Audio-ML job crashed on out-of-order librosa beat times
- [BUG-0118](bugs/import.md#bug-0118) Transcription flooded the chart and warnings with unplayable ghost notes
- [BUG-0119](bugs/import.md#bug-0119) Down-tuned songs read as standard; real low notes pruned
- [BUG-0120](bugs/audio.md#bug-0120) detect_tones and separate_stems ran the same Demucs separation twice
- [BUG-0121](bugs/security.md#bug-0121) Docker deployment exposed the whole API without authentication
- [BUG-0122](bugs/app.md#bug-0122) Job progress pills never lit (old pipeline stage names)
- [BUG-0123](bugs/import.md#bug-0123) GP5 notes after a dropped out-of-range note came one beat late
- [BUG-0124](bugs/psarc.md#bug-0124) Accented lyrics could crash SNG read-back (UTF-8 cut mid-character)
- [BUG-0125](bugs/security.md#bug-0125) Uploads had no size limit
- [BUG-0126](bugs/security.md#bug-0126) Cross-site form POSTs accepted (no same-origin check)
- [BUG-0127](bugs/security.md#bug-0127) GP7 import open to zip bombs and XML entity expansion
- [BUG-0128](bugs/viewer.md#bug-0128) Interrupted drags stacked listeners (knobs spun 2-3× faster)
- [BUG-0129](bugs/app.md#bug-0129) Upload endpoints blocked the event loop (heartbeats starved)
- [BUG-0130](bugs/security.md#bug-0130) Docker Compose shipped known default database credentials
- [BUG-0131](bugs/psarc.md#bug-0131) DD tier of a note on the final beat compared to the first beat
- [BUG-0132](bugs/lyrics.md#bug-0132) All-melisma GP lyric line dropped instead of holding the previous syllable
- [BUG-0133](bugs/viewer.md#bug-0133) Clicks/noise when scrubbing the recording
- [BUG-0134](bugs/sync.md#bug-0134) Dynamic auto-sync discarded the pinned first note and realigned from 0 s
- [BUG-0135](bugs/sync.md#bug-0135) Dynamic auto-sync rushed the chart ahead
- [BUG-0136](bugs/viewer.md#bug-0136) Drag/box-select could not reach past the visible part of the score
- [BUG-0137](bugs/editor.md#bug-0137) In 'Editar notas' a click on empty staff inserted a note instead of seeking
- [BUG-0138](bugs/viewer.md#bug-0138) Synthesized audio kept playing under a 'full mix' selector after switching jobs
- [BUG-0139](bugs/sync.md#bug-0139) Tempo detection read the wrong metrical level on dense mixes
- [BUG-0140](bugs/sync.md#bug-0140) Missing beatthis extra reported as 422 instead of 503
- [BUG-0141](bugs/sync.md#bug-0141) Beat This! checkpoint download kept failing on the user's machine
- [BUG-0142](bugs/sync.md#bug-0142) Neural downbeat sync put the BPM off (wrong metrical level / mixed meter)
- [BUG-0143](bugs/sync.md#bug-0143) Synced in the app but desynced in Rocksmith after a tempo change with committed anchors
- [BUG-0144](bugs/sync.md#bug-0144) Viewer's scoreShift omitted lead_in_s, desyncing the rebuild by lead_in_s·(r−1)
- [BUG-0145](bugs/viewer.md#bug-0145) Audio crackle/dropouts and score slowing down while editing
- [BUG-0146](bugs/sync.md#bug-0146) Pending corrections listed in insertion order; a crossing correction was hidden
- [BUG-0147](bugs/import.md#bug-0147) GP7/8 tempo: reference note value ignored (half-note tempo read at half speed)
- [BUG-0148](bugs/import.md#bug-0148) GP7/8 mid-bar tempo changes placed at the wrong tick
- [BUG-0149](bugs/app.md#bug-0149) New buttons did nothing: browser kept a stale app.js
- [BUG-0150](bugs/viewer.md#bug-0150) Score labels piled into an unreadable wall on dense charts
- [BUG-0151](bugs/sync.md#bug-0151) Sync analysis flooded the score with corrections on real audio
- [BUG-0152](bugs/viewer.md#bug-0152) Re-tempo mode reused the 'Detetar 1ª nota' icon
- [BUG-0153](bugs/sync.md#bug-0153) "Corrigir daqui" always read a higher tempo and ran the chart fast
- [BUG-0154](bugs/viewer.md#bug-0154) The live BPM readout ignored pending tempo and anchor edits
- [BUG-0155](bugs/psarc.md#bug-0155) Manifest advertised no techniques, SongOffset 0 and TargetScore 0
- [BUG-0156](bugs/app.md#bug-0156) Actions silently did nothing when the server had gone away
- [BUG-0157](bugs/exe.md#bug-0157) Closing the tab aborted in-process work and left the job stuck at RUNNING
- [BUG-0158](bugs/psarc.md#bug-0158) SNG wrote CapoFret 0 ('capo at fret 0') when there was no capo
- [BUG-0159](bugs/tones.md#bug-0159) Tone detection read almost every song as clean
- [BUG-0160](bugs/app.md#bug-0160) NaN/Infinity accepted in API floats: the build later failed with an error pointing nowhere
- [BUG-0161](bugs/app.md#bug-0161) Missing ML extra reported as a confusing 422 instead of a 503
- [BUG-0162](bugs/app.md#bug-0162) Impossible tuning pitch accepted, then crashed the SNG writer with struct.error
- [BUG-0163](bugs/app.md#bug-0163) Deleted jobs and abandoned wizards left their Guitar Pro uploads on disk forever
- [BUG-0164](bugs/release.md#bug-0164) CI was green while never running the native PSARC tests
- [BUG-0165](bugs/exe.md#bug-0165) Standalone .exe shipped an inert UI: web/app.js not bundled
- [BUG-0166](bugs/export.md#bug-0166) Corrected-GP export had no entry point in the UI
- [BUG-0167](bugs/editor.md#bug-0167) An unrelated rebuild silently erased committed note edits
- [BUG-0168](bugs/viewer.md#bug-0168) "Pendente" summary never shown: its element was missing from the markup
- [BUG-0169](bugs/psarc.md#bug-0169) Dynamic Difficulty never kept a raised level in game
- [BUG-0170](bugs/psarc.md#bug-0170) Riff Repeater named two passages the same: duplicate section numbers
- [BUG-0171](bugs/import.md#bug-0171) Every mid-song GP5 tempo change applied one quarter note late
- [BUG-0172](bugs/exe.md#bug-0172) Standalone .exe could never run the ML stages: it relaunched itself as the interpreter
- [BUG-0173](bugs/import.md#bug-0173) Guitar Pro 8 SyncPoints ignored, so a chart synced in Guitar Pro drifted
- [BUG-0174](bugs/exe.md#bug-0174) Every project created in the .exe stayed pending forever: Celery modules not bundled
- [BUG-0175](bugs/app.md#bug-0175) A task that died before its own error handling left the job silently pending
- [BUG-0176](bugs/import.md#bug-0176) GP8 chart came out one bar late with the untrimmed recording
- [BUG-0177](bugs/sync.md#bug-0177) UI said the MP3 could come from Songsterr, whose audio does not match the times
- [BUG-0178](bugs/app.md#bug-0178) Form modals closed on a stray click, losing a half-filled wizard
- [BUG-0179](bugs/app.md#bug-0179) A file dropped outside a drop zone navigated away from the app
- [BUG-0180](bugs/app.md#bug-0180) "Criar CDLC" did nothing when the start time had 3 decimals
- [BUG-0181](bugs/app.md#bug-0181) The 'confirm sync' reminder could never be cleared for a chart that needed no change
- [BUG-0182](bugs/app.md#bug-0182) Album lookup found nothing for 'feat.' credits
- [BUG-0183](bugs/import.md#bug-0183) YouTube audio download failed: yt-dlp lacked the JavaScript challenge solver and runtime
- [BUG-0184](bugs/editor.md#bug-0184) Note edits missed notes whose time the XML rounded (deleted notes still sounded)
- [BUG-0185](bugs/lyrics.md#bug-0185) Lyric edits showed no pending sign
- [BUG-0186](bugs/import.md#bug-0186) Songsterr import failed with CERTIFICATE_VERIFY_FAILED: certificate has expired
- [BUG-0187](bugs/import.md#bug-0187) Songsterr refusals said only '403', hiding 'this tab is unpublished'
- [BUG-0188](bugs/import.md#bug-0188) Songsterr import aborted entirely on text GP5 cannot store (e.g. a Cyrillic title)
- [BUG-0189](bugs/sync.md#bug-0189) Any sync correction dropped bend curves, fingering and pick direction
- [BUG-0190](bugs/lyrics.md#bug-0190) GP-embedded lyrics never reached the editor (params dict mutated in place)
- [BUG-0191](bugs/lyrics.md#bug-0191) GP lyrics timed on the guitar chart's notes instead of the vocal line
- [BUG-0192](bugs/import.md#bug-0192) Audio embedded in a GP8 file not detected (disabled track, other extensions, member name)
- [BUG-0193](bugs/app.md#bug-0193) Batch mode skipped a GP8 file with its own audio or gave it another song's recording
- [BUG-0194](bugs/app.md#bug-0194) Reloading the GP file always kept the old recording, never the new file's own audio
- [BUG-0195](bugs/app.md#bug-0195) YouTube audio download hidden inside the Songsterr extra, unseen with a plain GP file
- [BUG-0196](bugs/import.md#bug-0196) Songs whose last notes fall after the last beat refused to build
- [BUG-0197](bugs/lyrics.md#bug-0197) Lyric line cap counted syllables, splitting mid-phrase and leaving orphan words
- [BUG-0198](bugs/lyrics.md#bug-0198) Lyrics stayed put when the notes' sync was corrected
- [BUG-0199](bugs/sync.md#bug-0199) Bar sync against another track and the synthesized source ignored the intro silence
- [BUG-0200](bugs/viewer.md#bug-0200) An alternate chart showed as a second Lead/Rhythm and shared the main chart's edits
- [BUG-0201](bugs/import.md#bug-0201) Bar 1 before the recording (negative GP start) clamped to 0, every note late
- [BUG-0202](bugs/sync.md#bug-0202) Sync view clamped a negative start to 0 and a rebuild then lost the file's sync
- [BUG-0203](bugs/import.md#bug-0203) Three-point bends rose twice as fast as alphaTab/Guitar Pro play them
- [BUG-0204](bugs/import.md#bug-0204) A flat pre-bend was charted as a rise across the note instead of bent from the attack
- [BUG-0205](bugs/import.md#bug-0205) GP8 embedded audio with no file extension not recognised and offered as an external file
- [BUG-0206](bugs/import.md#bug-0206) Repeats, voltas and jumps played once, putting everything after them early
- [BUG-0207](bugs/sync.md#bug-0207) Rebuild committed only the on-screen chart's pending sync; other tabs' edits vanished
- [BUG-0208](bugs/viewer.md#bug-0208) A GP8 file with SyncPoints turned every track green with none marked
- [BUG-0209](bugs/psarc.md#bug-0209) Game froze on charts that enter late: sections out of order
- [BUG-0210](bugs/psarc.md#bug-0210) Game crashed raising the difficulty: notes kept the full chart's anchor
- [BUG-0211](bugs/psarc.md#bug-0211) A 0.1 s note-less END phrase when the last note touched the last section
- [BUG-0212](bugs/psarc.md#bug-0212) Game crashed raising the difficulty on a one-note phrase: ceiling 0
- [BUG-0213](bugs/psarc.md#bug-0213) Passages differing by a technique or sustain were linked as one phrase
- [BUG-0214](bugs/psarc.md#bug-0214) SNG note bytes wrote 0 instead of -1 for unused Tap/Slap/Pluck/LeftHand/PickDirection
- [BUG-0215](bugs/dlc-builder.md#bug-0215) Upstrokes became SLAP on the DLC Builder path: XML pickDirection wrote 2
- [BUG-0216](bugs/psarc.md#bug-0216) Daughtry 'September' still crashed: native phrases differed from DLC Builder's
- [BUG-0217](bugs/audio.md#bug-0217) Recording squashed by loudnorm: PSARC audio noisy and not clean
- [BUG-0218](bugs/tones.md#bug-0218) A chart with no tone of its own shipped an empty Tones array
- [BUG-0219](bugs/tones.md#bug-0219) Mid-song tone changes never happened in the native PSARC
- [BUG-0220](bugs/tones.md#bug-0220) Tone presets nearly inaudible in game: volumes on the wrong side of the scale
- [BUG-0221](bugs/tones.md#bug-0221) Plexi presets set a knob the amp does not have, so the setting was dropped
- [BUG-0222](bugs/import.md#bug-0222) Tied notes lost their bend and hammer/pull-off when folded
- [BUG-0223](bugs/import.md#bug-0223) GP7 bend-and-release lost its hold at the top
- [BUG-0224](bugs/export.md#bug-0224) Corrected-GP export wrote bends 50 times too big
- [BUG-0225](bugs/import.md#bug-0225) GP7 grace notes counted as bar time, shifting every later note
- [BUG-0226](bugs/import.md#bug-0226) GP5 pinch and tapped harmonic types swapped
- [BUG-0227](bugs/import.md#bug-0227) Vibrato on a tied note lost when the tie folded
- [BUG-0228](bugs/import.md#bug-0228) GP7/8 let ring lost (<LetRing/> inside the note)
- [BUG-0229](bugs/import.md#bug-0229) Bend-and-release happened early after the sustain trim
- [BUG-0230](bugs/export.md#bug-0230) Charts read back from the XML lost their bend curves
- [BUG-0231](bugs/app.md#bug-0231) Saving 'Editar info' always forked a rebuild, even for title/album changes
- [BUG-0232](bugs/tones.md#bug-0232) Driven tone presets left a hiss at the end of notes
- [BUG-0233](bugs/tones.md#bug-0233) Orange crunch preset noisy on Daughtry 'September'
- [BUG-0234](bugs/tones.md#bug-0234) Crunch preset too quiet and still too distorted; Overdrive slightly quiet
- [BUG-0235](bugs/app.md#bug-0235) start.bat refused Python 3.11 itself: delayed expansion ate the '!'
- [BUG-0236](bugs/app.md#bug-0236) start.bat used Python 3.13 when 3.11 was installed without the py launcher
- [BUG-0237](bugs/app.md#bug-0237) start.bat stopped with an error when Redis could not be installed
- [BUG-0238](bugs/app.md#bug-0238) CDLC patch check always said 'por confirmar', even on the machine with the game
- [BUG-0239](bugs/tones.md#bug-0239) Tone presets still hissed and did not sound clean next to hand-made tones
- [BUG-0240](bugs/psarc.md#bug-0240) Native chords showed no finger positions, unlike official songs
- [BUG-0241](bugs/psarc.md#bug-0241) Manifest SongPartition was 1 on every chart, so a Lead and its alternate were both Lead 1
- [BUG-0242](bugs/psarc.md#bug-0242) Hand shape LastNoteTime equal to its end after float32 rounding
- [BUG-0243](bugs/tones.md#bug-0243) Tone collection could report 'done' with the old list
- [BUG-0244](bugs/app.md#bug-0244) Transcription bench could not download its model on Windows (cp1252 stdout)
- [BUG-0245](bugs/tones.md#bug-0245) A swapped tone suggestion could not be undone in the row that showed it
- [BUG-0262](bugs/lyrics.md#bug-0262) Letra table showed times like 1:010.0
- [BUG-0263](bugs/viewer.md#bug-0263) Áudio panel did not close with Escape when focus was outside it
- [BUG-0264](bugs/app.md#bug-0264) Stale or wrong UI labels ('Estado do PSARC', English alternate-lead label)

**Known bugs it carried:** —

**Update / rollback:** Source install only (no downloads yet): start.bat pulls the newest code by itself; git checkout of an earlier commit to go back.

**Note:** A source-only release (start.bat); no tag or GitHub release exists. The commit is the one that set the version.
