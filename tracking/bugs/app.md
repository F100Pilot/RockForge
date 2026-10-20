<!-- Generated from tracking/bugs.json by `python -m tools.tracking render`. Do not edit by hand: edit the JSON and render again. -->

# Bugs: app

API, settings, projects, the web UI shell. Index: [BUG_LOG.md](../BUG_LOG.md).

## BUG-0015

**pip could not install [ml,lyrics] together: ResolutionTooDeep**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | pending (not recorded) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 89aa1f729d2d1656e8b0e95bf11ff9084bc81f4a |
| Severity | High |
| Priority | P2 |
| Status | Fixed |

whisperx>=3.4 pulls numpy>=2.1, conflicting with the ML stack's numpy<2, so installing both extras sent pip's resolver into endless backtracking (ResolutionTooDeep).

**Steps to reproduce:** _pending_

**Expected:** pip install -e .[ml,lyrics] resolves and installs.

**Observed:** pip backtracked endlessly and failed with ResolutionTooDeep.

**Root cause:** whisperx>=3.4 requires pyannote-audio>=4.0 / numpy>=2.1, which conflicts with the numpy<2 pin of the other stack.

**Fixes:** [FIX-0015](../FIX_LOG.md#fix-0015) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-06-15 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Lyric detection could not be installed beside the ML stack.

**Evidence:**

- CLAUDE.md § Hard constraints (these have bitten us — keep them) — '`whisperx` is pinned `<3.4`'
- commit fc6e175c97 Pin whisperx <3.4 to fix pip resolver explosion with [ml,lyrics]
- found_in_version: the fix commit fc6e175c97 is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent 89aa1f729d

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-06-15 — Fixed: commit fc6e175c97

## BUG-0016

**start.bat left the broker down silently when Redis was missing**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | pending (not recorded) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 069c7c305b3da47ff5d362ae94568adae40c4bc9 |
| Severity | Medium |
| Priority | P3 |
| Status | Fixed |

Without a running Redis, start.bat silently left the broker down, so lyric detection and CDLC generation sat waiting on the worker.

**Steps to reproduce:** _pending_

**Expected:** A clear message, or a working broker

**Observed:** Jobs stuck waiting

**Root cause:** No Redis detection/launch check.

**Fixes:** [FIX-0016](../FIX_LOG.md#fix-0016) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-06-15 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Jobs never ran; workaround was starting Redis by hand.

**Evidence:**

- commit c5f20fc08b chore(start): auto-detect Redis/Memurai and fail loudly if missing
- found_in_version: fix c5f20fc08b (2026-06-15) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 069c7c305b, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-06-15 — Fixed: commit c5f20fc08b

## BUG-0018

**Cover art dropped on rebuild**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | pending (not recorded) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 17905578371c8357fad3b4dbe451c58aef70d4df |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

Rebuild copied params (cover_art filename) but not the file into the new work dir, so the worker's existence check dropped it and the bundle shipped without album art.

**Steps to reproduce:** _pending_

**Expected:** Cover kept

**Observed:** Rebuilt bundle has no cover

**Root cause:** Cover file not copied to the forked job's work dir.

**Fixes:** [FIX-0018](../FIX_LOG.md#fix-0018) (0.10.0-beta.1)

**Verified:** regression test(s) test_rebuild_copies_cover_art_to_new_workdir pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-06-15 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Silent loss of the cover after any rebuild.

**Evidence:**

- commit 3c675cf594 Copy cover art into rebuild's new work directory
- found_in_version: fix 3c675cf594 (2026-06-15) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 1790557837, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-06-15 — Fixed: commit 3c675cf594
- 2026-06-15 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0019

**[ml] install failed on Windows building scipy from source**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | pending (not recorded) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 18b79c1793288b715b468a052b4e27f5faca3b0a |
| Severity | Medium |
| Priority | P3 |
| Status | Fixed |

pip resolved scipy 1.9.1, which has no cp311 Windows wheel, forcing a meson build that fails without MSVC.

**Steps to reproduce:** _pending_

**Expected:** Wheel install

**Observed:** 'Compiler cl can not compile programs'

**Root cause:** Loose scipy lower bound from basic-pitch.

**Fixes:** [FIX-0019](../FIX_LOG.md#fix-0019) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-06-15 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: ML install failed on Windows.

**Evidence:**

- commit a8869a3a2c Pin scipy>=1.11 in the ml extra to avoid a source build on Windows
- found_in_version: fix a8869a3a2c (2026-06-15) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 18b79c1793, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-06-15 — Fixed: commit a8869a3a2c

## BUG-0027

**Detection progress lost after the first commit: Job.params reassigned as the same dict**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | pending (not recorded) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 9ce029cd51a61de7608135807511593db12eb2b5 |
| Severity | High |
| Priority | P2 |
| Status | Fixed |

Job.params is a plain JSON column with no mutation tracking; reassigning the same dict object was a silent no-op, so every progress update after the first commit was lost and the UI froze on the first log line ('stuck at 8%') while the task actually ran.

**Steps to reproduce:** _pending_

**Expected:** The lyrics/tone detection log and status update live in the UI.

**Observed:** The UI stayed on its first stage ('detecting' / 'loading ML models') while the task ran or finished invisibly.

**Root cause:** SQLAlchemy compares the JSON column by identity; job.params aliased and reassigned to the same object issues no UPDATE.

**Fixes:** [FIX-0027](../FIX_LOG.md#fix-0027) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-06-18 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Lyric and tone detection looked hung and their results were not persisted.

**Evidence:**

- CLAUDE.md § Hard constraints (these have bitten us — keep them) — '`Job.params` (JSON column) needs a NEW dict object on every write.'
- CLAUDE.md § Async detection tasks — 'Each step commits via `_commit_params()`'
- commit 069c7c305b fix(lyrics): copy job.params before mutating in detect_lyrics
- commit 26e9886aac Fix silent commit no-ops: SQLAlchemy JSON column needs a new dict object
- found_in_version: the fix commit 069c7c305b is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent 9ce029cd51

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-06-18 — Fixed: commit 069c7c305b, 26e9886aac

## BUG-0040

**Closing the tab did not always stop the server (uvicorn --reload)**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 0d97472882ba1cb59b155de99bd65a14c72dfa41 |
| Severity | Low |
| Priority | P4 |
| Status | Fixed |

With --reload, the reloader restarted the child instead of exiting on the idle-shutdown SIGTERM, so closing the tab did not always stop the worker/Redis.

**Steps to reproduce:** _pending_

**Expected:** Everything stops

**Observed:** Processes linger after tab close

**Root cause:** uvicorn reloader parent/child split.

**Fixes:** [FIX-0040](../FIX_LOG.md#fix-0040) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-07-02 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Leftover processes.

**Evidence:**

- CLAUDE.md § Running locally (start.bat runs uvicorn without --reload)
- commit 0d7882dde9 start.bat: auto-open the browser + reliable tab-close shutdown
- commit 6282ed5c7c Fix Basic Pitch failing after whisperx import + harden worker shutdown
- found_in_version: fix 0d7882dde9 (2026-07-02) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 0d97472882, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-02 — Fixed: commit 0d7882dde9, 6282ed5c7c

## BUG-0042

**API shut itself down while its tab was only in the background**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | pending (not recorded) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | b2058c426849f19de2db7b3eeab5acb6cd4aae2b |
| Severity | High |
| Priority | P2 |
| Status | Closed |

After a while with the tab backgrounded or minimised (or the PC asleep) the API exited on its own, so rebuild and delete stopped working on a tab that was still open.

**Steps to reproduce:** _pending_

**Expected:** The server keeps running while the tab is open.

**Observed:** The API stopped and later rebuilds/deletes failed silently.

**Root cause:** Browsers throttle or freeze a background tab's timers, so its 4 s heartbeats stopped and the watchdog treated 15 s of silence as a closed tab.

**Fixes:** [FIX-0042](../FIX_LOG.md#fix-0042) (0.10.0-beta.1)

**Verified:** regression test(s) test_should_shutdown_decision_rules, test_heartbeat_hidden_flag_toggles_state pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-07-03 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: The app stopped working under normal use with nothing pointing at why.

**Evidence:**

- CLAUDE.md § Shutdown on tab close (`ROCKFORGE_IDLE_SHUTDOWN_S`) — 'Do NOT treat missing heartbeats as "closed."'
- commit c42e645f46 Não desligar a API enquanto o separador estiver aberto (idle-shutdown)
- found_in_version: the fix commit c42e645f46 is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent b2058c4268

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-03 — Fixed: commit c42e645f46
- 2026-07-03 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0043

**Closing the tab no longer stopped the server: a hidden heartbeat cancelled /closing**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 236ee85f2859f2cc3899cac749ee8322f89e20fe |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

On tab close the browser sends a hidden heartbeat before the /closing beacon; the two race on the server, and a hidden heartbeat arriving after /closing cleared the pending close, so the tab never shut the server down (a regression of the previous fix).

**Steps to reproduce:** 

1. Open the app in a tab
2. Close the tab

**Expected:** The server exits about 3 s after the tab closes.

**Observed:** The server kept running.

**Root cause:** Any heartbeat, visible or hidden, cleared _closing_at.

**Fixes:** [FIX-0043](../FIX_LOG.md#fix-0043) (0.10.0-beta.1)

**Verified:** regression test(s) test_hidden_heartbeat_does_not_cancel_pending_close pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-07-03 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: The server stayed running after the user closed the app; it still stopped after 30 minutes.

**Evidence:**

- CLAUDE.md § Shutdown on tab close (`ROCKFORGE_IDLE_SHUTDOWN_S`) — 'Only a VISIBLE heartbeat cancels the close ... (this regressed once).'
- commit 2702828850 Corrigir shutdown ao fechar a aba (heartbeat escondido cancelava o /closing)
- found_in_version: the fix commit 2702828850 is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent 236ee85f28

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-03 — Fixed: commit 2702828850
- 2026-07-03 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0044

**Job stuck in RUNNING could never be deleted**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 0fb0a3ee0fc37095000db470c69619c668f2d940 |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

A job whose worker died stayed RUNNING forever; the delete button was disabled and DELETE always returned 409.

**Steps to reproduce:** _pending_

**Expected:** A way to remove a stuck job

**Observed:** Undeletable job

**Root cause:** No force path.

**Fixes:** [FIX-0044](../FIX_LOG.md#fix-0044) (0.10.0-beta.1)

**Verified:** regression test(s) test_force_delete_running_job pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-07-03 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Clutter with no way out.

**Evidence:**

- commit 410e48ef1d Permitir forçar a remoção de um job preso em RUNNING (#1)
- found_in_version: fix 410e48ef1d (2026-07-03) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 0fb0a3ee0f, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-03 — Fixed: commit 410e48ef1d
- 2026-07-03 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0111

**Songs with GP/LRC/edited lyrics read 'sem letra' in the checklist**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 038f33976b474af62a93471f15dbdf83b78717ee |
| Severity | Low |
| Priority | P3 |
| Status | Closed |

The checklist's Letra row checked only lyrics_status == 'ready' (WhisperX detection), which GP-embedded, LRC or edited lyrics never set.

**Steps to reproduce:** 

1. Build a song with GP-embedded or LRC lyrics
2. Open the checklist

**Expected:** Letra shown as present.

**Observed:** 'sem letra'.

**Root cause:** has-lyrics was keyed on lyrics_status alone.

**Fixes:** [FIX-0111](../FIX_LOG.md#fix-0111) (0.10.0-beta.1)

**Verified:** regression test(s) test_has_lyrics_true_from_edited_events pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-07-11 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Misleading status only.

**Evidence:**

- CLAUDE.md § Batch processing ('Antes de usar' checklist, Letra row)
- commit d4aab16 message: 'the completeness panel bug reported after the last change'
- commit d4aab16257 Robust GPU→CPU fallback for the whole ML stack + completeness lyrics fix
- found_in_version: the fix commit is an ancestor of cb00653 (the first public release, 0.10.0 beta 1, 2026-10-14), so the faulty code only existed in development builds before 0.10.0-beta.1
- found_in_build: 038f33976b is the parent of the first fix commit d4aab16257 and still carries the code the fix changes

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-11 — Fixed: commit d4aab16257
- 2026-07-11 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0116

**⚙️ Definições unreachable while a song was open**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | pending (not recorded) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | b78cd5b64453c5945ab28e1ff4f51b95f1691e05 |
| Severity | Low |
| Priority | P4 |
| Status | Fixed |

The settings button (z-index 30) sat below the modal overlay (50).

**Steps to reproduce:** _pending_

**Expected:** Reachable everywhere

**Observed:** Button covered

**Root cause:** z-index.

**Fixes:** [FIX-0116](../FIX_LOG.md#fix-0116) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-07-11 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Usability.

**Evidence:**

- commit 25264486a9 Keep ⚙️ Definições reachable while a song is open
- found_in_version: fix 25264486a9 (2026-07-11) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent b78cd5b644, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-11 — Fixed: commit 25264486a9

## BUG-0122

**Job progress pills never lit (old pipeline stage names)**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | cdd83d8091033a6e3f18542d881ad72ffc419d35 |
| Severity | Low |
| Priority | P4 |
| Status | Closed |

PIPELINE_STAGES still listed the removed audio pipeline's stages, so the running-job highlight never matched.

**Steps to reproduce:** _pending_

**Expected:** Current stage lit

**Observed:** No stage highlighted

**Root cause:** Stale stage list.

**Fixes:** [FIX-0122](../FIX_LOG.md#fix-0122) (0.10.0-beta.1)

**Verified:** regression test(s) test_job_stages_match_the_gp_pipeline_on_stage_calls pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-07-13 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Cosmetic.

**Evidence:**

- commit 71238818ef fix: job progress pills used the removed audio pipeline's stage names
- found_in_version: fix 71238818ef (2026-07-13) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent cdd83d8091, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-13 — Fixed: commit 71238818ef
- 2026-07-13 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0129

**Upload endpoints blocked the event loop (heartbeats starved)**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | c18a764113b4634477a98dfb64882ab52c163121 |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

async def upload/create endpoints did blocking file writes and GP parsing on the event loop, stalling every request including /heartbeat, risking an idle shutdown during a slow upload.

**Steps to reproduce:** _pending_

**Expected:** Other requests served

**Observed:** Server unresponsive during uploads

**Root cause:** Blocking work in async routes.

**Fixes:** [FIX-0129](../FIX_LOG.md#fix-0129) (0.10.0-beta.1)

**Verified:** regression test(s) test_upload_endpoints_are_plain_def_not_async pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-07-13 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Stalls and possible spurious shutdown.

**Evidence:**

- commit ba7edb0a08 Stop blocking the event loop in upload/create GP endpoints (MAJ-5)
- found_in_version: fix ba7edb0a08 (2026-07-13) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent c18a764113, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-13 — Fixed: commit ba7edb0a08
- 2026-07-13 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0149

**New buttons did nothing: browser kept a stale app.js**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 40a9a83cd9a8724e52c3d00cb318527b97d59c3e |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

index.html was regenerated per request but the browser cached an old app.js, so new markup was wired to an old script ('Analisar sincronização does nothing'); handlers also returned silently on unmet preconditions.

**Steps to reproduce:** _pending_

**Expected:** Fresh script after an update

**Observed:** Button with no effect

**Root cause:** No cache-busting for app.js.

**Fixes:** [FIX-0149](../FIX_LOG.md#fix-0149) (0.10.0-beta.1)

**Verified:** regression test(s) test_index_page_references_the_extracted_app_js pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-08-22 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Features appeared broken after updates.

**Evidence:**

- commit 5b795a9df3 Fix "Analisar sincronização does nothing": cache-bust app.js, never fail silently
- found_in_version: fix 5b795a9df3 (2026-08-22) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 40a9a83cd9, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-08-22 — Fixed: commit 5b795a9df3
- 2026-08-22 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0156

**Actions silently did nothing when the server had gone away**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | d9085091f60f7166f17432bbc57eed79fbc0cd20 |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

Several calls did (await fetch(...)).json() unchecked, so with the API gone (tab-close shutdown, sleep) they threw unhandled rejections and the action did nothing, indistinguishable from a broken feature; selectJob's poll died on the first failure.

**Steps to reproduce:** 

1. Let the server stop with the page open
2. Click an action

**Expected:** A clear 'server unreachable' notice.

**Observed:** Nothing happened.

**Root cause:** Unchecked fetch responses and no network-error handling.

**Fixes:** [FIX-0156](../FIX_LOG.md#fix-0156) (0.10.0-beta.1)

**Verified:** CLAUDE.md: 'verified with Playwright against a live server — banner absent on load, present once /jobs is routed to fail, gone again when it succeeds' (by the developer (manual check))

**Resolved:** 2026-08-24 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Confusing failure mode; reloading after restarting worked.

**Evidence:**

- CLAUDE.md § The UI says when the server is gone (`getJSON` + the offline banner)
- commit 33807b8 message: 'Audit findings #9 and #14'
- commit 33807b8e5f Surface server-unreachable in the UI, and clear the last ESLint warnings
- found_in_version: the fix commit is an ancestor of cb00653 (the first public release, 0.10.0 beta 1, 2026-10-14), so the faulty code only existed in development builds before 0.10.0-beta.1
- found_in_build: d9085091f6 is the parent of the first fix commit 33807b8e5f and still carries the code the fix changes

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-08-24 — Fixed: commit 33807b8e5f
- 2026-08-24 — Verified: manual
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0160

**NaN/Infinity accepted in API floats: the build later failed with an error pointing nowhere**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | e4aeee647407683c6408758126f19136b66ec918 |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

JSON NaN/Infinity passed Pydantic float fields and the tempo_scale <= 0 guard (NaN <= 0 is False), so the job forked, the value was persisted and the build failed much later with an unrelated-looking error.

**Steps to reproduce:** _pending_

**Expected:** A 422 naming the bad value.

**Observed:** The request was accepted and the build failed later.

**Root cause:** Bare float types without allow_inf_nan=False, and form/import paths without a guard.

**Fixes:** [FIX-0160](../FIX_LOG.md#fix-0160) (0.10.0-beta.1)

**Verified:** regression test(s) test_non_finite_floats_are_rejected_at_the_boundary, test_non_finite_form_fields_and_imported_sync_are_rejected pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-08-24 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Bad input poisoned a job; needs a hand-crafted request.

**Evidence:**

- CLAUDE.md § API input validation: every client float is `Finite`
- commit message: 'Audit findings #3 and #4.'
- commit 9b3354f024 Reject non-finite floats at the API boundary, and report a missing ml extra as 503
- found_in_version: the fix commit 9b3354f024 is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent e4aeee6474

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-08-24 — Fixed: commit 9b3354f024
- 2026-08-24 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0161

**Missing ML extra reported as a confusing 422 instead of a 503**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | e4aeee647407683c6408758126f19136b66ec918 |
| Severity | Low |
| Priority | P4 |
| Status | Closed |

/detect-tempo and /detect-tuning wrapped the adapter import in an ImportError guard that never fired (the adapters import librosa inside the function), so a missing extra surfaced as '422 could not analyse the recording: No module named librosa'.

**Steps to reproduce:** _pending_

**Expected:** 503 naming the missing extra.

**Observed:** 422 'could not analyse the recording: No module named librosa'.

**Root cause:** The ImportError guard sat around the import, not around the call.

**Fixes:** [FIX-0161](../FIX_LOG.md#fix-0161) (0.10.0-beta.1)

**Verified:** regression test(s) test_missing_ml_extra_reports_503_not_a_confusing_422 pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-08-24 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: A misleading error message.

**Evidence:**

- CLAUDE.md § A missing ML extra is a 503, caught around the CALL
- commit 9b3354f024 Reject non-finite floats at the API boundary, and report a missing ml extra as 503
- found_in_version: the fix commit 9b3354f024 is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent e4aeee6474

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-08-24 — Fixed: commit 9b3354f024
- 2026-08-24 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0162

**Impossible tuning pitch accepted, then crashed the SNG writer with struct.error**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | edfd7a6ea61f57308052138934bfa52b039f350f |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

Only the length of tuning_midi was validated, so an absurd pitch got a 202, was persisted, and died much later in struct.pack in the SNG writer with nothing pointing back at the tuning.

**Steps to reproduce:** _pending_

**Expected:** A 422 for a pitch outside 0-127.

**Observed:** 202 Accepted, then a struct.error at build time.

**Root cause:** Tuning had no __post_init__ validation and the API had no pitch range check.

**Fixes:** [FIX-0162](../FIX_LOG.md#fix-0162) (0.10.0-beta.1)

**Verified:** regression test(s) test_tuning_pitches_are_range_checked_at_the_api, test_tuning_rejects_an_impossible_pitch_at_construction pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-08-24 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Bad input broke a build with an unhelpful error.

**Evidence:**

- CLAUDE.md § `Tuning` validates its own pitches (and the API range-checks them)
- commit message: 'Audit finding #7.'
- commit 1c157754b7 Validate tuning pitches in the domain and range-check them at the API
- found_in_version: the fix commit 1c157754b7 is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent edfd7a6ea6

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-08-24 — Fixed: commit 1c157754b7
- 2026-08-24 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0163

**Deleted jobs and abandoned wizards left their Guitar Pro uploads on disk forever**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 9b3354f024f296d02881f7e7b97769945f1f4770 |
| Severity | Low |
| Priority | P4 |
| Status | Closed |

The GP upload lives outside the job's work dir, so delete_job never removed it, and an upload inspected by an abandoned wizard or batch was never collected.

**Steps to reproduce:** _pending_

**Expected:** A job's GP file goes with its job; orphans are swept.

**Observed:** GP files accumulated forever.

**Root cause:** delete_job removed only work_dir/<job_id>; nothing swept orphan uploads.

**Fixes:** [FIX-0163](../FIX_LOG.md#fix-0163) (0.10.0-beta.1)

**Verified:** regression test(s) test_deleting_a_job_removes_its_gp_file_but_not_a_forks, test_orphaned_gp_uploads_are_swept_but_referenced_ones_are_kept, test_the_orphan_sweep_actually_runs_on_startup pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-08-24 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Disk leak only.

**Evidence:**

- CLAUDE.md § Uploaded GP files are reference-counted and swept
- commit message: 'Audit finding #5'
- commit edfd7a6ea6 Reference-count and sweep uploaded Guitar Pro files
- found_in_version: the fix commit edfd7a6ea6 is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent 9b3354f024

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-08-24 — Fixed: commit edfd7a6ea6
- 2026-08-24 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0175

**A task that died before its own error handling left the job silently pending**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 2902d9c8384024018ddbc041fd0d4f90bfaacc2f |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

When an in-process task failed before its own error handling (as with the missing Celery modules), the traceback went only to a log file and the job never left PENDING, so the UI sat on its first stage.

**Steps to reproduce:** _pending_

**Expected:** The job is marked FAILED with the reason.

**Observed:** The job stayed PENDING with no error shown.

**Root cause:** inprocess._run_task only logged an escaping exception.

**Fixes:** [FIX-0175](../FIX_LOG.md#fix-0175) (0.10.0-beta.1)

**Verified:** regression test(s) test_a_build_that_dies_before_it_starts_fails_the_job_visibly, test_a_detection_that_dies_before_it_starts_stops_saying_detecting, test_a_job_that_already_failed_keeps_its_own_error pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-09-25 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Failures were invisible to the user.

**Evidence:**

- CLAUDE.md § Standalone executable (`build_exe.py` / PyInstaller) — '**A task that dies before its own error handling runs now says so.**'
- commit 89bb3fdaf2 Fix the .exe never starting a job: bundle what Celery imports by name
- found_in_version: the fix commit 89bb3fdaf2 is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent 2902d9c838

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-09-25 — Fixed: commit 89bb3fdaf2
- 2026-09-25 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0178

**Form modals closed on a stray click, losing a half-filled wizard**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 229475adc4fd92a103fe1b74def4eeb0a9e0a2a5 |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

A press inside a field released on the backdrop is dispatched as a click on the overlay, so 'click outside to close' threw away a half-filled wizard.

**Steps to reproduce:** 

1. Fill part of the new-project wizard
2. Select text in a field and release outside the box

**Expected:** The modal stays open.

**Observed:** The modal closed and the input was lost.

**Root cause:** e.target === overlay closed the form modals.

**Fixes:** [FIX-0178](../FIX_LOG.md#fix-0178) (0.10.0-beta.1)

**Verified:** CLAUDE.md: 'Reproduced with Playwright (press in the title field, release on the backdrop → closed) and verified fixed.' (by the developer (manual check))

**Resolved:** 2026-09-26 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Lost user input; had to start again.

**Evidence:**

- CLAUDE.md § The layout (Modals with typed input never close from the backdrop)
- user quote (undated): 'a caixa desaparece e tenho de voltar ao início'
- commit 8567e06641 Stop form modals closing on a stray click outside
- found_in_version: the fix commit is an ancestor of cb00653 (the first public release, 0.10.0 beta 1, 2026-10-14), so the faulty code only existed in development builds before 0.10.0-beta.1
- found_in_build: 229475adc4 is the parent of the first fix commit 8567e06641 and still carries the code the fix changes

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-09-26 — Fixed: commit 8567e06641
- 2026-09-26 — Verified: manual
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0179

**A file dropped outside a drop zone navigated away from the app**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | pending (not recorded) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 229475adc4fd92a103fe1b74def4eeb0a9e0a2a5 |
| Severity | Medium |
| Priority | P3 |
| Status | Fixed |

Dropping a file anywhere outside a drop zone triggered the browser's default of opening the file, navigating away from RockForge.

**Steps to reproduce:** 

1. Drag a file onto the page outside a drop zone

**Expected:** Nothing happens.

**Observed:** The browser opened the file and left the app.

**Root cause:** No document-level dragover/drop preventDefault.

**Fixes:** [FIX-0179](../FIX_LOG.md#fix-0179) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-09-26 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Lost the page state.

**Evidence:**

- CLAUDE.md § The layout (Modals with typed input never close from the backdrop)
- commit 8567e06641 Stop form modals closing on a stray click outside
- found_in_version: the fix commit is an ancestor of cb00653 (the first public release, 0.10.0 beta 1, 2026-10-14), so the faulty code only existed in development builds before 0.10.0-beta.1
- found_in_build: 229475adc4 is the parent of the first fix commit 8567e06641 and still carries the code the fix changes

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-09-26 — Fixed: commit 8567e06641

## BUG-0180

**"Criar CDLC" did nothing when the start time had 3 decimals**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | pending (not recorded) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 89bb3fdaf2efe9ebd22889776b1b350308931d16 |
| Severity | High |
| Priority | P2 |
| Status | Closed |

The wizard pre-filled 'Início da música' with toFixed(3) into an input with step=0.01, so 4.583 was a step mismatch on a hidden earlier step and the browser silently refused the submit.

**Steps to reproduce:** 

1. Use a GP8/Songsterr file that pre-fills a 3-decimal start
2. Go to step 4 and press 'Criar CDLC'

**Expected:** The project is created.

**Observed:** Nothing happened (console only).

**Root cause:** Native validation of a hidden invalid field (step mismatch) cannot be shown.

**Fixes:** [FIX-0180](../FIX_LOG.md#fix-0180) (0.10.0-beta.1)

**Verified:** CLAUDE.md: 'reproduced and verified with Playwright: 4.583 now creates the job' (by the developer (manual check))

**Resolved:** 2026-09-26 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Project creation blocked silently.

**Evidence:**

- CLAUDE.md § The layout (`gpJobForm` is `novalidate`, and the submit handler does the check)
- commit 14e9e21661 Fix "Criar CDLC" doing nothing when the start time has 3 decimals
- found_in_version: the fix commit is an ancestor of cb00653 (the first public release, 0.10.0 beta 1, 2026-10-14), so the faulty code only existed in development builds before 0.10.0-beta.1
- found_in_build: 89bb3fdaf2 is the parent of the first fix commit 14e9e21661 and still carries the code the fix changes

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-09-26 — Fixed: commit 14e9e21661
- 2026-09-26 — Verified: manual
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0181

**The 'confirm sync' reminder could never be cleared for a chart that needed no change**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | b394f70d9197976b677a7fbdd153416611cf9556 |
| Severity | Low |
| Priority | P4 |
| Status | Closed |

The checklist's sync row only cleared after a manual adjustment, so a chart already in sync (GP8, embedded audio, right from the start) kept the warning forever.

**Steps to reproduce:** 

1. Build a chart that is already in sync
2. Open Exportar → 'Antes de usar'

**Expected:** A way to confirm it is in sync.

**Observed:** The reminder stayed.

**Root cause:** sync_edited was the only signal.

**Fixes:** [FIX-0181](../FIX_LOG.md#fix-0181) (0.10.0-beta.1)

**Verified:** regression test(s) test_a_song_that_needed_no_adjustment_can_be_confirmed_as_in_sync, test_songsterr_bar_times_count_as_synchronised pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-09-26 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: A permanent false warning.

**Evidence:**

- CLAUDE.md § Batch processing ('Antes de usar' checklist, Sincronização row)
- user quote (undated): 'nunca consigo tirar, mesmo quando está sincronizado'
- commit 977a37e98b Let the user confirm a chart is in sync
- found_in_version: the fix commit is an ancestor of cb00653 (the first public release, 0.10.0 beta 1, 2026-10-14), so the faulty code only existed in development builds before 0.10.0-beta.1
- found_in_build: b394f70d91 is the parent of the first fix commit 977a37e98b and still carries the code the fix changes

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-09-26 — Fixed: commit 977a37e98b
- 2026-09-26 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0182

**Album lookup found nothing for 'feat.' credits**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 8567e0664106d97a6fa89f5a1a0ba6d3245978da |
| Severity | Low |
| Priority | P4 |
| Status | Closed |

Artists like 'X feat. Y' were searched literally, and an empty result said only 'nothing found'.

**Steps to reproduce:** _pending_

**Expected:** Search by the main artist and explain empties

**Observed:** No match

**Root cause:** Featuring credit kept in the query.

**Fixes:** [FIX-0182](../FIX_LOG.md#fix-0182) (0.10.0-beta.1)

**Verified:** commit b394f70: album lookup confirmed against the live services by the user (by the maintainer)

**Resolved:** 2026-09-26 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Convenience.

**Evidence:**

- commit 6743eefad0 Album lookup: search by the main artist, explain empty results
- found_in_version: fix 6743eefad0 (2026-09-26) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 8567e06641, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-09-26 — Fixed: commit 6743eefad0
- 2026-09-26 — Verified: confirmed by user
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0193

**Batch mode skipped a GP8 file with its own audio or gave it another song's recording**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | d8b7b422419118000c8c812c7f3bee312e4b677f |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

'Lote (álbum)' never asked whether a GP file carried its recording: such a file was skipped for having no recording, or paired in order with a recording of another song.

**Steps to reproduce:** 

1. Open 'Lote (álbum)'
2. Pick a GP8 file with embedded audio plus GP files and recordings
3. Look at the pairs and create the projects

**Expected:** The GP8 file uses its own audio and needs no recording.

**Observed:** The file was skipped or given another song's recording.

**Root cause:** The batch pairing only looked at uploaded recordings, never at /gp/inspect's embedded_audio.

**Fixes:** [FIX-0193](../FIX_LOG.md#fix-0193) (0.10.0-beta.1)

**Verified:** CLAUDE.md: 'Verified with Playwright (the user's GP8 + a GP5 + two recordings → own audio / the leftover wav, both jobs as said)' (by the developer (manual check))

**Resolved:** 2026-09-29 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Workaround: create that song with the single-project wizard.

**Evidence:**

- CLAUDE.md § Batch processing ("Lote (álbum)")
- CLAUDE.md § The generation path (The recording INSIDE the `.gp` is the one to use)
- user quote (undated): 'porque é que continuas a não aproveitar o mp3 do ficheiro gp?'
- commit cc05bc467b Use the audio a GP file carries in the batch and when reloading the GP file
- found_in_version: the fix commit is an ancestor of cb00653 (the first public release, 0.10.0 beta 1, 2026-10-14), so the faulty code only existed in development builds before 0.10.0-beta.1
- found_in_build: d8b7b42241 is the parent of the first fix commit cc05bc467b and still carries the code the fix changes

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-09-29 — Fixed: commit cc05bc467b
- 2026-09-29 — Verified: manual
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0194

**Reloading the GP file always kept the old recording, never the new file's own audio**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | d8b7b422419118000c8c812c7f3bee312e4b677f |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

'Recarregar ficheiro GP' kept the old recording no matter what, so a project could never move onto a GP8 file's embedded audio without being recreated, and a missing old recording was a 409 even when the new file carried audio.

**Steps to reproduce:** 

1. Open a project
2. Use 'Recarregar ficheiro GP' with a GP8 file that carries audio

**Expected:** The new file's embedded audio becomes the recording.

**Observed:** The old recording stayed; with the old recording gone the reload failed with 409.

**Root cause:** /reload-gp only swapped gp_path and never looked at the new file's embedded audio.

**Fixes:** [FIX-0194](../FIX_LOG.md#fix-0194) (0.10.0-beta.1)

**Verified:** regression test(s) test_reloading_a_gp_file_that_carries_audio_uses_that_audio, test_a_gp_file_with_audio_stands_in_for_a_recording_that_is_gone pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-09-29 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Workaround: recreate the project from the wizard.

**Evidence:**

- CLAUDE.md § Reloading the GP file (`/jobs/{id}/reload-gp`)
- CLAUDE.md: 'It used to keep the old recording no matter what'
- commit cc05bc467b Use the audio a GP file carries in the batch and when reloading the GP file
- found_in_version: the fix commit is an ancestor of cb00653 (the first public release, 0.10.0 beta 1, 2026-10-14), so the faulty code only existed in development builds before 0.10.0-beta.1
- found_in_build: d8b7b42241 is the parent of the first fix commit cc05bc467b and still carries the code the fix changes

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-09-29 — Fixed: commit cc05bc467b
- 2026-09-29 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0195

**YouTube audio download hidden inside the Songsterr extra, unseen with a plain GP file**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 133ed79ff436812bc898ce6146d3277e4cba87e6 |
| Severity | Low |
| Priority | P3 |
| Status | Fixed |

The 'Descarregar o áudio' block lived inside step 3's optional Songsterr 'Extra', so a user who only uploaded a GP5 never saw that a download existed.

**Steps to reproduce:** 

1. Create a project from a GP5 file without audio
2. Reach step 3

**Expected:** A way to fetch the audio from a YouTube link is visible.

**Observed:** No download option was visible.

**Root cause:** The YouTube block was placed inside the Songsterr section of step 3.

**Fixes:** [FIX-0195](../FIX_LOG.md#fix-0195) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-09-29 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Discoverability only; the feature worked through the Songsterr extra.

**Evidence:**

- CLAUDE.md § The generation path (The chosen video's audio, fetched)
- user quote (undated): 'quando só carrego um gp5, o mp3 não vem incluído'
- commit 3a3357b8a6 Use the vocal track: lyric phrases, syllable lengths and a "Voz" source; YouTube audio for any GP file
- found_in_version: the fix commit is an ancestor of cb00653 (the first public release, 0.10.0 beta 1, 2026-10-14), so the faulty code only existed in development builds before 0.10.0-beta.1
- found_in_build: 133ed79ff4 is the parent of the first fix commit 3a3357b8a6 and still carries the code the fix changes

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-09-29 — Fixed: commit 3a3357b8a6

## BUG-0231

**Saving 'Editar info' always forked a rebuild, even for title/album changes**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | pending (not recorded) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 64170c54e7035916086390561022727bc3f3666c |
| Severity | Low |
| Priority | P3 |
| Status | Closed |

For a GP job every save of 'Editar info' forked a rebuild, since the arrangements section was merely shown, even when no track or tuning changed.

**Steps to reproduce:** 

1. Open 'Editar info' on a GP project
2. Change only the album and save

**Expected:** A metadata PATCH only.

**Observed:** A new rebuilt version was created.

**Root cause:** The save did not distinguish metadata from track/tuning changes.

**Fixes:** [FIX-0231](../FIX_LOG.md#fix-0231) (0.10.0-beta.1)

**Verified:** CLAUDE.md: 'verified with Playwright (album-only save: PATCH, no new job; a track change: a new rebuilt job)' (by the developer (manual check))

**Resolved:** 2026-10-01 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Unneeded rebuilds and versions.

**Evidence:**

- CLAUDE.md § The layout: home page, full-screen project view, stroke icons ('Editar info' is a page as well)
- commit bcc933a691 Editar info becomes a full-screen page; saving info alone no longer rebuilds
- found_in_version: the fix commit is an ancestor of cb00653 (the first public release, 0.10.0 beta 1, 2026-10-14), so the faulty code only existed in development builds before 0.10.0-beta.1
- found_in_build: 64170c54e7 is the parent of the first fix commit bcc933a691 and still carries the code the fix changes

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-10-01 — Fixed: commit bcc933a691
- 2026-10-01 — Verified: manual
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0235

**start.bat refused Python 3.11 itself: delayed expansion ate the '!'**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | pending (not recorded) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 6e2a1ebf2a956ada2f99897e48216902b99592cc |
| Severity | High |
| Priority | P2 |
| Status | Fixed |

start.bat runs with delayed expansion, so cmd ate the '!' of '!=' in the Python version check and Python got a syntax error: the check failed on every version, 3.11 included.

**Steps to reproduce:** 

1. Run start.bat with Python 3.11 installed

**Expected:** start.bat accepts Python 3.11.

**Observed:** The check refused 3.11.

**Root cause:** A '!' in a command line under delayed expansion.

**Fixes:** [FIX-0235](../FIX_LOG.md#fix-0235) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-10-02 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: The source install could not start.

**Evidence:**

- CLAUDE.md § Running locally (Windows, native, no Docker) — 'The file runs with delayed expansion: no `!` in a command line.'
- commit 61d60c02f1 start.bat: fix the Python 3.11 check, which refused 3.11 itself
- found_in_version: the fix commit 61d60c02f1 is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent 6e2a1ebf2a

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-10-02 — Fixed: commit 61d60c02f1

## BUG-0236

**start.bat used Python 3.13 when 3.11 was installed without the py launcher**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 56ed13ebbc6b838454e7386bf86b546a2f6b1a0f |
| Severity | Low |
| Priority | P4 |
| Status | Fixed |

Without the launcher's 3.11 the script fell back to the default python (3.13), and pip answered only 'requires a different Python'.

**Steps to reproduce:** _pending_

**Expected:** 3.11 found or a clear message

**Observed:** Bare pip refusal

**Root cause:** Only the py launcher was searched.

**Fixes:** [FIX-0236](../FIX_LOG.md#fix-0236) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-10-02 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Setup friction.

**Evidence:**

- commit 29d78e0f87 start.bat: say Python 3.11 is needed instead of pip's bare refusal
- commit 6e2a1ebf2a start.bat: find a Python 3.11 in its install folder without the py launcher
- found_in_version: fix 29d78e0f87 (2026-10-02) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 56ed13ebbc, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-10-02 — Fixed: commit 29d78e0f87, 6e2a1ebf2a

## BUG-0237

**start.bat stopped with an error when Redis could not be installed**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | b9695dd20aac1c06ea251f6759221874cf2e9da2 |
| Severity | Medium |
| Priority | P3 |
| Status | Fixed |

Memurai needs admin rights, which a work laptop refused, and start.bat aborted.

**Steps to reproduce:** _pending_

**Expected:** Runs without Redis

**Observed:** Cannot start

**Root cause:** Redis required.

**Fixes:** [FIX-0237](../FIX_LOG.md#fix-0237) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-10-02 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: App unusable on that machine.

**Evidence:**

- CLAUDE.md § Running locally (No Redis is not an error)
- commit b19279a209 start.bat: run without Redis, with the tasks inside the API
- found_in_version: fix b19279a209 (2026-10-02) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent b9695dd20a, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-10-02 — Fixed: commit b19279a209

## BUG-0238

**CDLC patch check always said 'por confirmar', even on the machine with the game**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | b19279a209052cd627879fc266ff13e0d9c36196 |
| Severity | Low |
| Priority | P4 |
| Status | Closed |

The diagnostics row for the CDLC loader patch always reported unknown, even where the game was installed, and the user did not know what to do with it.

**Steps to reproduce:** _pending_

**Expected:** The row says whether D3DX9_42.dll is in the game folder.

**Observed:** Always 'por confirmar'.

**Root cause:** The patch was not looked for in the game folder (no setting, no Steam libraries on other drives).

**Fixes:** [FIX-0238](../FIX_LOG.md#fix-0238) (0.10.0-beta.1)

**Verified:** regression test(s) test_what_cannot_be_checked_reports_unknown_not_missing, test_the_cdlc_patch_is_looked_for_in_the_game_folder, test_the_game_folder_the_tone_collection_was_pointed_at_wins, test_steam_libraries_on_other_drives_are_searched, test_the_rocksmith_folder_set_in_settings_is_where_the_patch_is_looked_for, test_a_windows_library_path_is_unescaped, test_a_diagnostics_row_is_in_english pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-10-03 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Diagnostics only.

**Evidence:**

- CLAUDE.md § What external software is installed — 'the **Rocksmith CDLC loader patch** ... is looked for (`D3DX9_42.dll`, any case) in the folder set in ⚙️ Definições'
- commit 8b9cfbc12b Look for the CDLC patch in the Rocksmith folder, which can be set in Settings
- found_in_version: the fix commit 8b9cfbc12b is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent b19279a209

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-10-03 — Fixed: commit 8b9cfbc12b
- 2026-10-03 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0244

**Transcription bench could not download its model on Windows (cp1252 stdout)**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 2172a2bdd0bb0a320cdc8e1b46e2fc11bed94d23 |
| Severity | Low |
| Priority | P4 |
| Status | Fixed |

A captured stdout is cp1252 on Windows; hf_midi_transcription printed a check mark while downloading, the download died and GAPS reported it could not download. (Experimental bench, later deleted.)

**Steps to reproduce:** _pending_

**Expected:** Model downloads

**Observed:** 'could not download'

**Root cause:** Non-UTF-8 captured output.

**Fixes:** [FIX-0244](../FIX_LOG.md#fix-0244) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-10-10 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Experimental tool only.

**Evidence:**

- commit b3a6b60392 Transcription bench: run the transcribers in UTF-8
- found_in_version: fix b3a6b60392 (2026-10-10) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 2172a2bdd0, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-10-10 — Fixed: commit b3a6b60392

## BUG-0253

**A late answer reopened a closed project; detection pollers drew into the next project**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | _pending_ |
| Build / commit | cb00653bedba4cd2f9070ceb2acb8e925c883319 |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

selectJob applied an answer that arrived after the user had closed the project (or opened another), reopening it; the tone, stem and lyric pollers kept polling and drawing into the next project opened.

**Steps to reproduce:** 

1. Open a project and close it (or open another) before its data arrives

**Expected:** The closed project stays closed; the last one opened wins.

**Observed:** The late answer reopened the old project; pollers drew the previous project's detection into the new one.

**Root cause:** Async answers and pollers were not bound to the project they were started for.

**Fixes:** [FIX-0253](../FIX_LOG.md#fix-0253) (0.10.0-beta.2)

**Verified:** commit 2d0b87ef91: 'Checked with Playwright against the previous app.js: closed-stays-closed, last-opened-wins and the stopped poll fail there and pass here' (by the developer (manual check))

**Resolved:** 2026-10-14 · **Closed:** 2026-10-15

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Confusing UI state across projects, no data loss.

**Evidence:**

- CHANGELOG.en.md 0.10.0 beta 2 — Fixed: "A late answer for a project you had closed ..."
- commit 2d0b87ef91: "selectJob ignores an answer for a project the user closed or left; the tone, stem and lyric pollers are bound to the project they started for"
- found_in_version pending: faulty code present at cb00653 (beta 1); found by an audit, detection date not documented

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-10-14 — Fixed: commit 2d0b87ef91
- 2026-10-14 — Verified: manual
- 2026-10-15 — Closed: released in 0.10.0-beta.2

## BUG-0256

**The "Lead/Rhythm (exp.)" checkbox did nothing**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | _pending_ |
| Build / commit | cb00653bedba4cd2f9070ceb2acb8e925c883319 |
| Severity | Low |
| Priority | P4 |
| Status | Fixed |

A "Lead/Rhythm (exp.)" checkbox (split_lead_rhythm) was still shown and sent on rebuild, but no code used it any more since the audio transcription path was removed.

**Steps to reproduce:** _pending_

**Expected:** _pending_

**Observed:** Ticking it changed nothing.

**Root cause:** Leftover of the removed audio-transcription path (split_lead_rhythm stored but never read).

**Fixes:** [FIX-0256](../FIX_LOG.md#fix-0256) (0.10.0-beta.2)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-10-14 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: A dead control, misleading but harmless.

**Evidence:**

- CHANGELOG.en.md 0.10.0 beta 2 — Fixed: "The \"Lead/Rhythm (exp.)\" checkbox, which no longer did anything, is gone."
- commit 2d0b87ef91: "The dead 'Lead/Rhythm (exp.)' checkbox and split_lead_rhythm are gone."
- found_in_build: cb00653 web/index.html contains 'Lead/Rhythm (exp'
- found_in_version pending: faulty code present at cb00653 (beta 1); found by an audit, detection date not documented

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-10-14 — Fixed: commit 2d0b87ef91

## BUG-0258

**The six "Afinação (MIDI)" inputs did nothing**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | _pending_ |
| Build / commit | cb00653bedba4cd2f9070ceb2acb8e925c883319 |
| Severity | Low |
| Priority | P3 |
| Status | Fixed |

The viewer's six "Afinação (MIDI)" inputs fed tuning_midi, which no part of the build read.

**Steps to reproduce:** _pending_

**Expected:** _pending_

**Observed:** Changing them had no effect on the build.

**Root cause:** tuning_midi was sent on rebuild but never read.

**Fixes:** [FIX-0258](../FIX_LOG.md#fix-0258) (0.10.0-beta.2)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-10-14 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: A dead control; per-chart tuning was editable in "Editar info".

**Evidence:**

- CLAUDE.md § `Tuning` validates its own pitches (and the API range-checks them): "the viewer's six 'Afinação (MIDI)' inputs fed a tuning_midi nothing read either"
- CHANGELOG.en.md 0.10.0 beta 2 — Fixed: "... The six \"Tuning (MIDI)\" numbers, which did nothing either, are gone"
- commit 8123d67a9f Make the recording's cent offset reach the build; drop the dead MIDI tuning inputs
- found_in_version pending: faulty code present at cb00653 (beta 1); detection date not documented

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-10-14 — Fixed: commit 8123d67a9f

## BUG-0259

**Seven button requests could throw an uncaught error the offline banner did not see**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | pending (not recorded) |
| Found in | _pending_ |
| Build / commit | cb00653bedba4cd2f9070ceb2acb8e925c883319 |
| Severity | Low |
| Priority | P4 |
| Status | Fixed |

Saving settings, detecting lyrics and tone, separating stems, uploading a cover, reading a GP file and creating a project used a hand-written fetch/r.json(); a 500 with a text body or a dropped connection escaped as an uncaught error and the offline banner did not notice.

**Steps to reproduce:** _pending_

**Expected:** A failure is shown as a toast; a dropped connection shows the offline banner.

**Observed:** An uncaught error; the offline banner stayed off.

**Root cause:** These requests bypassed getJSON.

**Fixes:** [FIX-0259](../FIX_LOG.md#fix-0259) (0.10.0-beta.2)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-10-14 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Only the error reporting of failure cases was wrong.

**Evidence:**

- commit e490cd9183 Seven button requests go through getJSON: "a 500 with a text body or a dropped connection no longer escapes as an uncaught error, and the offline banner now sees these requests too"
- CLAUDE.md § The UI says when the server is gone (`getJSON` + the offline banner)
- not in the changelog; found_in_version pending: faulty code present at cb00653 (beta 1)

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-10-14 — Fixed: commit e490cd9183

## BUG-0264

**Stale or wrong UI labels ('Estado do PSARC', English alternate-lead label)**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 47a28cae4f8cdbb1e99dc187e9c0f748f599c289 |
| Severity | Low |
| Priority | P4 |
| Status | Fixed |

Wizard step 4 and its ⓘ still named the checklist 'Estado do PSARC' (it is 'Antes de usar'), and 'Edit info' read 'Alternate lead (in game: LEAD 2) track' in English.

**Steps to reproduce:** _pending_

**Expected:** Current names

**Observed:** Wrong labels

**Root cause:** Text not updated.

**Fixes:** [FIX-0264](../FIX_LOG.md#fix-0264) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-10-14 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Cosmetic.

**Evidence:**

- commit 74130132ec Guide checked in the browser; fixes it turned up
- found_in_version: fix 74130132ec (2026-10-14) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 47a28cae4f, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-10-14 — Fixed: commit 74130132ec

## BUG-0266

**start.bat's git pull stalled on Windows with repeated "Unlink of file ... failed" prompts**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | pending (not recorded) |
| Found in | _pending_ |
| Build / commit | cb00653bedba4cd2f9070ceb2acb8e925c883319 |
| Severity | Medium |
| Priority | P3 |
| Status | Fixed |

After the pull, git's automatic gc failed to delete .git files another program held open and kept prompting "Unlink of file ... failed. Should I try again? (y/n)", stalling the start.

**Steps to reproduce:** 

1. Run start.bat on Windows while a .git file is held open

**Expected:** The start continues.

**Observed:** Repeated "Should I try again? (y/n)" prompts.

**Root cause:** git's automatic gc/maintenance ran after the pull.

**Fixes:** [FIX-0266](../FIX_LOG.md#fix-0266) (0.10.0-beta.2)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-10-15 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Start stalls until answered; answering lets it continue.

**Evidence:**

- commit 9321069994 start.bat: git pull without automatic clean-up (gc)
- found_in_build: cb00653 start.bat runs git pull without gc.auto=0
- not in the changelog; found_in_version pending: detection date not documented

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-10-15 — Fixed: commit 9321069994

## BUG-0282

**The New project wizard could not take a cover image from the computer**

| | |
|---|---|
| Detected | 2026-10-16 |
| Reported by | user report (Facebook) |
| Found in | _pending_ |
| Build / commit | 2d4d4bb5f5a41da9672b7ba5c08853befbb9f217 |
| Severity | Low |
| Priority | P3 |
| Status | Closed |

Step 4 of "Novo projeto" offered only the online lookup's cards and "Sem capa"; a local image could only be added on the Cover page after creating the project.

**Steps to reproduce:** 

1. Open Novo projeto and reach step 4
2. Try to choose a JPEG from the computer

**Expected:** A local image can be chosen and goes into the first build.

**Observed:** "it won't let me upload an album cover from my pc"

**Root cause:** /jobs/gp took only cover_url; the wizard had no file input.

**Fixes:** [FIX-0282](../FIX_LOG.md#fix-0282) (0.10.0-beta.8)

**Verified:** regression test(s) test_a_cover_from_the_computer_is_in_place_before_the_first_build pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-10-16 · **Closed:** 2026-10-16

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: The Cover page after creating was a workaround.

**Evidence:**

- CLAUDE.md § Album, year and cover — looked up, then CHOSEN (`/album-lookup`): "Or the user's own image, in the wizard too (Facebook feedback, 2026-10-16: 'it won't let me upload an album cover from my pc' ...)"
- user quote (2026-10-16): 'it won't let me upload an album cover from my pc'
- CHANGELOG.en.md 0.10.0 beta 8 — Fixed: "A cover from your computer when creating the project ..."
- commit 790038258e Take a cover from the computer in the New project wizard
- found_in_version pending: faulty code present at 8494322 (beta 6) and 2d4d4bb (beta 7); which was in use on 2026-10-16 is not stated

**History:**

- 2026-10-16 — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-10-16 — Fixed: commit 790038258e
- 2026-10-16 — Verified: automated
- 2026-10-16 — Closed: released in 0.10.0-beta.8

## BUG-0298

**A background task undid what the user changed while it ran**

| | |
|---|---|
| Detected | 2026-10-18 |
| Reported by | code review (Claude, on the maintainer's request) |
| Found in | 0.11.0-beta.2 |
| Build / commit | f64c45e8e176c44bd87c7c7866f741330b443011 |
| Severity | High |
| Priority | P1 |
| Status | Verified |

Detect lyrics/tones and Separate instruments copied Job.params once and wrote that whole copy back on every progress line, for minutes. A cover uploaded, "Mark as synced", the main chart, tone swaps, "Install in game" or another detection's status, done meanwhile, was erased by the next progress line.

**Steps to reproduce:** 

1. Start "Separate instruments"
2. While it runs, upload a cover or mark the song as synced
3. Wait for the separation to finish

**Expected:** The cover and the mark stay.

**Observed:** cover_art and sync_confirmed went back to what they were when the task started (SQLite repro).

**Root cause:** Each task kept its own copy of params and assigned it whole on every commit; with expire_on_commit off the row was never re-read.

**Fixes:** [FIX-0298](../FIX_LOG.md#fix-0298) (0.11.0-beta.3)

**Verified:** tests/test_celery_tasks.py::test_what_the_user_changes_while_a_task_runs_is_not_undone passed, and fails with the fix reverted (by pytest (the test fails on the old code))

**Resolved:** 2026-10-18 · **Closed:** _pending_

**Evidence:**

- code review of the whole codebase (six reviewers), confirmed by reading the code

**History:**

- 2026-10-18 — Open: reported
- 2026-10-18 — Fixed: commit 2ae21cd533
- 2026-10-18 — Verified: its test passes and fails on the old code

## BUG-0306

**A refused cover upload deleted the cover the project had**

| | |
|---|---|
| Detected | 2026-10-18 |
| Reported by | code review (Claude, on the maintainer's request) |
| Found in | 0.11.0-beta.2 |
| Build / commit | f64c45e8e176c44bd87c7c7866f741330b443011 |
| Severity | Medium |
| Priority | P2 |
| Status | Verified |

The old cover was removed before the new upload was read, so an oversized (413) or non-image upload left the project with no cover while it still said it had one. The upload was also checked by its name, not its bytes.

**Steps to reproduce:** 

1. Upload a cover
2. Upload an oversized image

**Expected:** The first cover stays.

**Observed:** GET /cover 404 after the 413.

**Root cause:** _replace_cover ran before the upload was read and checked.

**Fixes:** [FIX-0306](../FIX_LOG.md#fix-0306) (0.11.0-beta.3)

**Verified:** tests/test_api.py::test_a_refused_cover_upload_keeps_the_cover_the_project_had passed, and fails with the fix reverted (by pytest (the test fails on the old code))

**Resolved:** 2026-10-18 · **Closed:** _pending_

**Evidence:**

- code review of the whole codebase (six reviewers), confirmed by reading the code

**History:**

- 2026-10-18 — Open: reported
- 2026-10-18 — Fixed: commit f907982d0f
- 2026-10-18 — Verified: its test passes and fails on the old code

## BUG-0322

**After a reload with other audio, dropping the old version reused its stems**

| | |
|---|---|
| Detected | 2026-10-18 |
| Reported by | code review (Claude, on the maintainer's request) |
| Found in | 0.11.0-beta.2 |
| Build / commit | f64c45e8e176c44bd87c7c7866f741330b443011 |
| Severity | Medium |
| Priority | P2 |
| Status | Verified |

"Drop the previous version" moved the old recording's Demucs stems to a version that plays another recording, which then reused them.

**Steps to reproduce:** 

1. See the description (found by reading the code)

**Expected:** As described in the solution.

**Observed:** "Drop the previous version" moved the old recording's Demucs stems to a version that plays another recording, which then reused them.

**Root cause:** The carry ignored which recording the stems belong to.

**Fixes:** [FIX-0322](../FIX_LOG.md#fix-0322) (0.11.0-beta.4)

**Verified:** tests/test_api.py::test_dropping_a_version_gives_its_stems_only_to_one_that_plays_the_same_recording passed, and fails with the fix reverted (by pytest (the test fails on the old code))

**Resolved:** 2026-10-18 · **Closed:** _pending_

**Evidence:**

- code review of the whole codebase (six reviewers), confirmed by reading the code

**History:**

- 2026-10-18 — Open: reported
- 2026-10-18 — Fixed: commit c322940e56
- 2026-10-18 — Verified: its test passes and fails on the old code

## BUG-0323

**Dropping a version left sibling versions with stems in a deleted folder**

| | |
|---|---|
| Detected | 2026-10-18 |
| Reported by | code review (Claude, on the maintainer's request) |
| Found in | 0.11.0-beta.2 |
| Build / commit | f64c45e8e176c44bd87c7c7866f741330b443011 |
| Severity | Medium |
| Priority | P3 |
| Status | Verified |

Only the version asking had its stem paths rewritten.

**Steps to reproduce:** 

1. See the description (found by reading the code)

**Expected:** As described in the solution.

**Observed:** Only the version asking had its stem paths rewritten.

**Root cause:** Other forks were not updated.

**Fixes:** [FIX-0323](../FIX_LOG.md#fix-0323) (0.11.0-beta.4)

**Verified:** tests/test_api.py::test_dropping_a_version_gives_its_stems_only_to_one_that_plays_the_same_recording passed, and fails with the fix reverted (by pytest (the test fails on the old code))

**Resolved:** 2026-10-18 · **Closed:** _pending_

**Evidence:**

- code review of the whole codebase (six reviewers), confirmed by reading the code

**History:**

- 2026-10-18 — Open: reported
- 2026-10-18 — Fixed: commit c322940e56
- 2026-10-18 — Verified: its test passes and fails on the old code

## BUG-0324

**A project could be deleted while a detection ran on it**

| | |
|---|---|
| Detected | 2026-10-18 |
| Reported by | code review (Claude, on the maintainer's request) |
| Found in | 0.11.0-beta.2 |
| Build / commit | f64c45e8e176c44bd87c7c7866f741330b443011 |
| Severity | Medium |
| Priority | P3 |
| Status | Verified |

Only RUNNING blocked a delete; a detection runs with the job COMPLETED, and Demucs then recreated its output in the deleted folder.

**Steps to reproduce:** 

1. See the description (found by reading the code)

**Expected:** As described in the solution.

**Observed:** Only RUNNING blocked a delete; a detection runs with the job COMPLETED, and Demucs then recreated its output in the deleted folder.

**Root cause:** Detection statuses were not checked.

**Fixes:** [FIX-0324](../FIX_LOG.md#fix-0324) (0.11.0-beta.4)

**Verified:** tests/test_api.py::test_a_project_is_not_deleted_while_a_detection_runs_on_it passed, and fails with the fix reverted (by pytest (the test fails on the old code))

**Resolved:** 2026-10-18 · **Closed:** _pending_

**Evidence:**

- code review of the whole codebase (six reviewers), confirmed by reading the code

**History:**

- 2026-10-18 — Open: reported
- 2026-10-18 — Fixed: commit c322940e56
- 2026-10-18 — Verified: its test passes and fails on the old code

## BUG-0325

**A refused new project left its recording in uploads, and "²" gave a 500**

| | |
|---|---|
| Detected | 2026-10-18 |
| Reported by | code review (Claude, on the maintainer's request) |
| Found in | 0.11.0-beta.2 |
| Build / commit | f64c45e8e176c44bd87c7c7866f741330b443011 |
| Severity | Medium |
| Priority | P3 |
| Status | Verified |

The recording was copied before the other checks; every later refusal left it. "²".isdigit() is true but int() fails.

**Steps to reproduce:** 

1. See the description (found by reading the code)

**Expected:** As described in the solution.

**Observed:** The recording was copied before the other checks; every later refusal left it. "²".isdigit() is true but int() fails.

**Root cause:** No cleanup after the copy; isdigit.

**Fixes:** [FIX-0325](../FIX_LOG.md#fix-0325) (0.11.0-beta.4)

**Verified:** tests/test_api.py::test_a_refused_new_project_leaves_no_recording_behind passed, and fails with the fix reverted (by pytest (the test fails on the old code))

**Resolved:** 2026-10-18 · **Closed:** _pending_

**Evidence:**

- code review of the whole codebase (six reviewers), confirmed by reading the code

**History:**

- 2026-10-18 — Open: reported
- 2026-10-18 — Fixed: commit c322940e56
- 2026-10-18 — Verified: its test passes and fails on the old code

## BUG-0326

**Two bundle downloads at once could corrupt the zip**

| | |
|---|---|
| Detected | 2026-10-18 |
| Reported by | code review (Claude, on the maintainer's request) |
| Found in | 0.11.0-beta.2 |
| Build / commit | f64c45e8e176c44bd87c7c7866f741330b443011 |
| Severity | Low |
| Priority | P3 |
| Status | Verified |

Every download rewrote one shared <bundle>.zip while another was still streaming it.

**Steps to reproduce:** 

1. See the description (found by reading the code)

**Expected:** As described in the solution.

**Observed:** Every download rewrote one shared <bundle>.zip while another was still streaming it.

**Root cause:** make_archive to a fixed name.

**Fixes:** [FIX-0326](../FIX_LOG.md#fix-0326) (0.11.0-beta.4)

**Verified:** tests/test_api.py::test_each_bundle_download_is_its_own_zip passed, and fails with the fix reverted (by pytest (the test fails on the old code))

**Resolved:** 2026-10-18 · **Closed:** _pending_

**Evidence:**

- code review of the whole codebase (six reviewers), confirmed by reading the code

**History:**

- 2026-10-18 — Open: reported
- 2026-10-18 — Fixed: commit c322940e56
- 2026-10-18 — Verified: its test passes and fails on the old code

## BUG-0332

**Celery's hard time limit could leave a detection status stuck**

| | |
|---|---|
| Detected | 2026-10-18 |
| Reported by | code review (Claude, on the maintainer's request) |
| Found in | 0.11.0-beta.2 |
| Build / commit | f64c45e8e176c44bd87c7c7866f741330b443011 |
| Severity | Low |
| Priority | P4 |
| Status | Fixed |

A hard kill skips the task's except, so the status stayed "separating" and the UI polled forever.

**Steps to reproduce:** 

1. See the description (found by reading the code)

**Expected:** As described in the solution.

**Observed:** A hard kill skips the task's except, so the status stayed "separating" and the UI polled forever.

**Root cause:** No soft limit.

**Fixes:** [FIX-0332](../FIX_LOG.md#fix-0332) (0.11.0-beta.4)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-10-18 · **Closed:** _pending_

**Evidence:**

- code review of the whole codebase (six reviewers), confirmed by reading the code

**History:**

- 2026-10-18 — Open: reported
- 2026-10-18 — Fixed: commit 76c44a8bcd

## BUG-0340

**With a newer FastAPI an absent default-yes form field reads as no (batch projects lose palm mutes; reload ignores the file's audio)**

| | |
|---|---|
| Detected | 2026-10-20 |
| Reported by | Claude, from the CI failure of the 0.11.1-beta.1 bump |
| Found in | 0.11.0-beta.4 |
| Build / commit | _pending_ |
| Severity | Medium |
| Priority | P2 |
| Status | Verified |

FastAPI 0.155 (allowed by fastapi>=0.110, and what CI and a fresh install get) reads a bool form field that is not sent as False whatever its default, like an unticked HTML checkbox. /jobs/gp's import_mutes (default yes) is not sent by the batch page, and /reload-gp's use_embedded_audio (default yes) is not sent by API clients that rely on the default. Depends on the FastAPI installed; not seen with 0.142.

**Steps to reproduce:** 

1. Install FastAPI 0.155
2. Create a project from "Lote (álbum)" (no import_mutes field)
3. Look at params["import_mute_techniques"]

**Expected:** True (the default): palm mutes and dead notes imported.

**Observed:** False: the batch project's palm mutes and dead notes stripped. CI: test_reloading_a_gp_file_that_carries_audio_uses_that_audio and test_what_was_measured_on_the_old_recording_is_dropped_with_it failed on every commit since 8be374d (2026-10-19, CI run 39325729185), the first run on the newer FastAPI.

**Root cause:** Two default-yes form fields declared as bool = Form(True); newer FastAPI no longer applies the default when the field is absent.

**Fixes:** [FIX-0340](../FIX_LOG.md#fix-0340) (0.11.1-beta.1)

**Verified:** tests/test_api.py on FastAPI 0.155: the two reload tests and the new test_a_project_whose_form_leaves_out_import_mutes_keeps_its_mutes pass (the new one fails with the bool field back); the full suite passes on 0.155 and test_api.py on 0.142 (by the developer (pytest))

**Resolved:** 2026-10-20 · **Closed:** _pending_

**Evidence:**

- CI run 39466239314 (1e76a9b): 2 failed, 1217 passed — the two reload-gp tests
- Reproduced locally with fastapi 0.155.0 / starlette 1.9.0: a minimal endpoint with flag: bool = Form(True) returns False when the field is not sent

**History:**

- 2026-10-20 — Open: reported
- 2026-10-20 — In Progress: found while confirming the 0.11.1-beta.1 publication
- 2026-10-20 — Fixed: commit 55c918ef58
- 2026-10-20 — Verified: tests on FastAPI 0.155 and 0.142
