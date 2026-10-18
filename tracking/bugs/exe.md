<!-- Generated from tracking/bugs.json by `python -m tools.tracking render`. Do not edit by hand: edit the JSON and render again. -->

# Bugs: exe

The Windows .exe, installer and extra components. Index: [BUG_LOG.md](../BUG_LOG.md).

## BUG-0157

**Closing the tab aborted in-process work and left the job stuck at RUNNING**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 1c157754b70ec2784b3b93e6ae1e8654ab7b282a |
| Severity | High |
| Priority | P2 |
| Status | Closed |

In inprocess mode (the standalone .exe) the worker runs in the API's own process, so closing the browser tab killed the process seconds later, aborting a build or a 20-minute Demucs separation and leaving its job at RUNNING with nothing to finish it.

**Steps to reproduce:** 

1. Start a build or a stem separation in the standalone app
2. Close the tab while it runs

**Expected:** The work finishes and the result is there on the next launch.

**Observed:** The work was aborted and the job stayed at RUNNING forever.

**Root cause:** The idle watchdog decided purely on heartbeats and knew nothing about queued or running in-process tasks.

**Fixes:** [FIX-0157](../FIX_LOG.md#fix-0157) (0.10.0-beta.1)

**Verified:** regression test(s) test_work_in_flight_defers_every_shutdown_trigger, test_in_flight_counts_queued_work_and_drains, test_celery_mode_never_defers_on_worker_state pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-08-24 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Lost work and a permanently stuck job.

**Evidence:**

- CLAUDE.md § Shutdown on tab close (`ROCKFORGE_IDLE_SHUTDOWN_S`) — 'Work in flight defers the shutdown (the standalone `.exe`).'
- commit message: 'Audit finding #6.'
- commit d9085091f6 Defer the idle shutdown while the in-process worker still has work
- found_in_version: the fix commit d9085091f6 is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent 1c157754b7

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-08-24 — Fixed: commit d9085091f6
- 2026-08-24 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0165

**Standalone .exe shipped an inert UI: web/app.js not bundled**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | cff0f84ff2bfbe789c6f69ca678df121ad5acf81 |
| Severity | Critical |
| Priority | P1 |
| Status | Closed |

rockforge.spec listed its web files by hand as only index.html, so after the script moved to web/app.js the bundled page loaded nothing (no buttons, no score) and web/gear_images was missing; inside the bundle the server could not find web files either.

**Steps to reproduce:** _pending_

**Expected:** The .exe's UI works.

**Observed:** An inert page.

**Root cause:** A hand-written datas list in the spec, and _web_file_candidates not trying sys._MEIPASS/web.

**Fixes:** [FIX-0165](../FIX_LOG.md#fix-0165) (0.10.0-beta.1)

**Verified:** regression test(s) test_bundled_web_files_are_found_in_the_pyinstaller_bundle, test_spec_bundles_every_web_file, test_spec_puts_web_files_where_the_server_looks_for_them, test_index_html_only_references_bundled_local_assets pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-08-24 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: The .exe was unusable.

**Evidence:**

- CLAUDE.md § Standalone executable (`build_exe.py` / PyInstaller) — '**The spec WALKS `web/`; it must never list those files by hand again.**'
- commit 93c0a5083d Fix the standalone .exe's missing web assets, and stop CI skipping the PSARC tests
- found_in_version: the fix commit 93c0a5083d is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent cff0f84ff2

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-08-24 — Fixed: commit 93c0a5083d
- 2026-08-24 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0172

**Standalone .exe could never run the ML stages: it relaunched itself as the interpreter**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 6b24f8c9be8049274a821b33750c52d8f8d0ba47 |
| Severity | High |
| Priority | P2 |
| Status | Closed |

Every ML stage runs as a subprocess of sys.executable, which in a frozen app is the .exe itself, so the subprocess relaunched RockForge instead of Demucs/WhisperX; the docs had also promised that ML extras installed on the system would work.

**Steps to reproduce:** _pending_

**Expected:** Stem separation, tone/lyric detection and 'Corrigir daqui' work from the .exe with an external Python.

**Observed:** Those features were unavailable in the .exe.

**Root cause:** sys.executable passed at each ML call site; librosa imported in-process.

**Fixes:** [FIX-0172](../FIX_LOG.md#fix-0172) (0.10.0-beta.1)

**Verified:** regression test(s) test_the_ml_call_sites_never_pass_sys_executable, test_the_exe_resolves_to_nothing_rather_than_to_itself, test_a_python_install_resolves_to_itself_exactly_as_before, test_the_librosa_measurements_have_one_implementation, test_spec_bundles_every_ml_runner_at_its_package_path, test_inside_the_exe_a_pip_instruction_points_at_the_ml_interpreter pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-09-23 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Several features unavailable in the .exe; the Python install was the workaround.

**Evidence:**

- CLAUDE.md § Standalone executable (`build_exe.py` / PyInstaller) — '**The `.exe` cannot IMPORT the ML stack — and does not need to (`infrastructure/ml_python.py`).**'
- commit 6b24f8c corrected the false docs claim and the pip instructions shown inside the .exe
- commit 99a969d359 Give the .exe real ML by delegating to an external Python 3.11
- found_in_version: the fix commit 99a969d359 is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent 6b24f8c9be

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-09-23 — Fixed: commit 99a969d359
- 2026-09-23 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0174

**Every project created in the .exe stayed pending forever: Celery modules not bundled**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 2902d9c8384024018ddbc041fd0d4f90bfaacc2f |
| Severity | Critical |
| Priority | P1 |
| Status | Closed |

The in-process worker imports celery_app, whose Celery(...) loads fixups and loaders by name; PyInstaller could not see them, so the frozen worker died on 'No module named celery.fixups' before any job ran.

**Steps to reproduce:** 

1. Build the .exe
2. Create a project

**Expected:** The project builds.

**Observed:** The job stayed PENDING forever.

**Root cause:** Modules Celery imports by string were missing from the bundle.

**Fixes:** [FIX-0174](../FIX_LOG.md#fix-0174) (0.10.0-beta.1)

**Verified:** regression test(s) test_spec_bundles_the_modules_celery_imports_by_name pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-09-25 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: The .exe could not build anything.

**Evidence:**

- CLAUDE.md § Standalone executable (`build_exe.py` / PyInstaller) — '**The in-process worker still CREATES the Celery app, so the spec must bundle what Celery imports by name.**'
- commit 89bb3fdaf2 Fix the .exe never starting a job: bundle what Celery imports by name
- found_in_version: the fix commit 89bb3fdaf2 is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent 2902d9c838

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-09-25 — Fixed: commit 89bb3fdaf2
- 2026-09-25 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0265

**In the .exe, a project without tones of its own made no .psarc**

| | |
|---|---|
| Detected | 2026-10-15 |
| Reported by | found during development |
| Found in | _pending_ |
| Build / commit | 614178f84922e5aad4969d8054c1ea46b002e5f0 |
| Severity | Critical |
| Priority | P1 |
| Status | Closed |

rockforge.spec listed the package's data files by hand and left out gear/default_tones/*.json, so in the frozen app every project without tones of its own failed default_tones._load and built no .psarc (the job still "completed").

**Steps to reproduce:** 

1. Build the .exe
2. Create a project without tones in it

**Expected:** A .psarc with DLC Builder's default tones.

**Observed:** No .psarc (FileNotFoundError in default_tones._load).

**Root cause:** Hand-written data-file list in rockforge.spec missing gear/default_tones/*.json.

**Fixes:** [FIX-0265](../FIX_LOG.md#fix-0265) (0.10.0-beta.2)

**Verified:** regression test(s) test_spec_bundles_every_data_file_of_the_package_at_its_package_path pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-10-15 · **Closed:** 2026-10-15

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: The .exe could not make a playable file for the common no-tone project.

**Evidence:**

- CLAUDE.md § Publishing a release (`.github/workflows/release.yml`): "Its first run caught a real defect"
- CHANGELOG.en.md 0.10.0 beta 2 — Distribution: "Fixed in the .exe: a project without tones of its own made no .psarc ..."
- commit 25a67fbe73: "The release workflow's first dry run built the .exe, started it and made a project - and the build made no .psarc"
- detected 2026-10-15: the release workflow was added in 614178f (2026-10-15) and fixed in 25a67fb the same day
- found_in_version pending: faulty spec present at cb00653 (beta 1, a source release per its README); caught before the first .exe was published (tag v0.10.0-beta.2 points at the fix 25a67fb)

**History:**

- 2026-10-15 — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-10-15 — Fixed: commit 25a67fbe73
- 2026-10-15 — Verified: automated
- 2026-10-15 — Closed: released in 0.10.0-beta.2

## BUG-0268

**In the .exe, the "Download" buttons did nothing**

| | |
|---|---|
| Detected | 2026-10-15 |
| Reported by | user report |
| Found in | _pending_ |
| Build / commit | 25a67fbe730581db2109dc0d2d0eb3f3f5b687ea |
| Severity | Critical |
| Priority | P1 |
| Status | Closed |

pywebview cancels every download by default (ALLOW_DOWNLOADS False), silently, so in the .exe the .psarc and bundle "Download" buttons did nothing and showed no error.

**Steps to reproduce:** 

1. Open a built project in the .exe
2. Click Download for the .psarc

**Expected:** A Save As dialog.

**Observed:** Nothing happened.

**Root cause:** pywebview's ALLOW_DOWNLOADS defaults to False and edgechromium cancels the download.

**Fixes:** [FIX-0268](../FIX_LOG.md#fix-0268) (0.10.0-beta.5)

**Verified:** regression test(s) test_the_window_is_allowed_to_save_downloads pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-10-15 · **Closed:** 2026-10-15

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: The essential output could not be saved from the .exe.

**Evidence:**

- CLAUDE.md § Standalone executable (`build_exe.py` / PyInstaller): "The window must be allowed to save files ... a user's first report after the public release"
- CHANGELOG.en.md 0.10.0 beta 5 — Fixed: "In the .exe, the \"Download\" buttons did nothing ..."
- commit 13a2c42b65 Fix the first public reports: downloads in the .exe, the capo, a 30 MB .psarc
- detected 2026-10-15: the first .exe was published with beta 2 (tag at 25a67fb, 2026-10-15) and the fix is dated 2026-10-15
- found_in_version pending: faulty code present at 25a67fb (beta 2) and bebcf2b (beta 3); which one the reporter ran is not stated

**History:**

- 2026-10-15 — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-10-15 — Fixed: commit 13a2c42b65
- 2026-10-15 — Verified: automated
- 2026-10-15 — Closed: released in 0.10.0-beta.5

## BUG-0273

**In the .exe, installed extra components were unused when the ML Python setting was empty**

| | |
|---|---|
| Detected | 2026-10-15 |
| Reported by | the maintainer |
| Found in | 0.10.0-beta.5 |
| Build / commit | 84553bd6104d9f5538808207df74c1c32412a291 |
| Severity | High |
| Priority | P2 |
| Status | Closed |

After the extra components installed, the ml_python setting ended up empty, so stems, tone, lyrics, PDF and YouTube all said the components were missing while the components card said they were installed.

**Steps to reproduce:** 

1. Install the extra components from the .exe (the "Python para o ML" setting ends up empty)
2. Use stem separation or tone detection

**Expected:** The components' Python is used.

**Observed:** Every ML feature reported the components missing.

**Root cause:** Only the ml_python setting pointed the stages at the components; per CLAUDE.md likely a Definições page opened before the install finished saving its empty field over it.

**Fixes:** [FIX-0273](../FIX_LOG.md#fix-0273) (0.10.0-beta.6)

**Verified:** regression test(s) test_the_exe_finds_the_extra_components_python_by_itself pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-10-15 · **Closed:** 2026-10-15

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Every ML feature of the .exe unavailable; setting the path by hand was a workaround.

**Evidence:**

- CLAUDE.md § The `.exe` installs its own extra components (`infrastructure/components.py`): "the user's first install ended with every component in place and the setting empty ... ('fez download dos extra components mas não os deteta')"
- user quote (undated): 'fez download dos extra components mas não os deteta'
- CHANGELOG.en.md 0.10.0 beta 6 — Fixed: "In the .exe, the installed extra components were not used ..."
- commit b9017147b2 Find the extra components' Python by itself in the .exe
- detected 2026-10-15: the components install was added in f092c7c (2026-10-15) and fixed in b901714 the same day
- found_in_version: the components install first shipped in beta 5 (beta 4 never published) and was fixed before beta 6

**History:**

- 2026-10-15 — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-10-15 — Fixed: commit b9017147b2
- 2026-10-15 — Verified: automated
- 2026-10-15 — Closed: released in 0.10.0-beta.6

## BUG-0274

**Black console windows flashed in the .exe whenever a child program ran**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | _pending_ |
| Build / commit | 8494322e3f34a7427e9ed710687f2001493e9bb4 |
| Severity | Low |
| Priority | P4 |
| Status | Closed |

The GUI-subsystem .exe gave every console program it ran (ffmpeg, the components' python.exe, nvidia-smi, yt-dlp, WwiseConsole) a console of its own, flashing a black window for a fraction of a second on every button that ran one.

**Steps to reproduce:** 

1. In the .exe, click a button that runs ffmpeg or the components' Python

**Expected:** No window appears.

**Observed:** A black window flashes.

**Root cause:** Child processes were started without CREATE_NO_WINDOW.

**Fixes:** [FIX-0274](../FIX_LOG.md#fix-0274) (0.10.0-beta.7)

**Verified:** regression test(s) test_child_processes_start_without_a_console_window_on_windows pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-10-15 · **Closed:** 2026-10-16

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Cosmetic flash, no functional effect.

**Evidence:**

- CLAUDE.md § Standalone executable (`build_exe.py` / PyInstaller): "Every child process starts without a console window ... ('aparece durante uma fração de segundo um ecrã preto')"
- user quote (undated): 'aparece durante uma fração de segundo um ecrã preto'
- CHANGELOG.en.md 0.10.0 beta 7 — Fixed: "The black screen that flashed when clicking some buttons in the .exe ..."
- commit d05ab8355b Start the .exe's child processes without a console window
- found_in_version pending: faulty code present at 8494322 (beta 6); the version used and the date are not stated

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-10-15 — Fixed: commit d05ab8355b
- 2026-10-15 — Verified: automated
- 2026-10-16 — Closed: released in 0.10.0-beta.7

## BUG-0283

**The .exe never used the GPU for the ML stages**

| | |
|---|---|
| Detected | 2026-10-16 |
| Reported by | found during development |
| Found in | 0.10.0-beta.7 |
| Build / commit | 2d4d4bb5f5a41da9672b7ba5c08853befbb9f217 |
| Severity | Medium |
| Priority | P2 |
| Status | Closed |

Device auto-detection imported torch in the frozen .exe, which carries no PyTorch (it lives in the extra components' Python), so it always failed and stem separation, tone and lyric detection ran on the CPU even with an NVIDIA GPU.

**Steps to reproduce:** 

1. Install the extra components with CUDA in the .exe
2. Run stem separation

**Expected:** Runs on the GPU.

**Observed:** Always on the CPU.

**Root cause:** _detect_device asked the frozen process, not the interpreter that runs the stages.

**Fixes:** [FIX-0283](../FIX_LOG.md#fix-0283) (0.10.0-beta.8)

**Verified:** regression test(s) test_the_exe_asks_the_components_python_whether_there_is_a_gpu, test_an_ml_python_that_cannot_answer_means_the_cpu pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-10-16 · **Closed:** 2026-10-16

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Much slower ML stages on every GPU machine; results still correct.

**Evidence:**

- CLAUDE.md § Automatic lyric detection + in-app editor (Device selection): "found answering a user's 'will it run on an enterprise GPU?', 2026-10-16"
- CHANGELOG.en.md 0.10.0 beta 8 — Fixed: "The .exe never used the GPU ..."
- docs/RELEASE_NOTES.md at 611a82e (beta 8): "in beta 7 it always fell back to the CPU"
- commit b40f200f48 Ask the ML interpreter, not the .exe, whether there is a GPU

**History:**

- 2026-10-16 — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-10-16 — Fixed: commit b40f200f48
- 2026-10-16 — Verified: automated
- 2026-10-16 — Closed: released in 0.10.0-beta.8

## BUG-0299

**Lyric detection always failed in the .exe**

| | |
|---|---|
| Detected | 2026-10-18 |
| Reported by | code review (Claude, on the maintainer's request) |
| Found in | 0.11.0-beta.2 |
| Build / commit | f64c45e8e176c44bd87c7c7866f741330b443011 |
| Severity | High |
| Priority | P1 |
| Status | Verified |

The WhisperX runner imported rockforge's adapter; in the .exe it is run by the extra components' Python, which has whisperx but not the rockforge package, so every lyric detection failed after minutes of separation.

**Steps to reproduce:** 

1. In the .exe with the extra components installed, open a project
2. Press "Detect lyrics"

**Expected:** Lyrics are detected.

**Observed:** python -I -S _whisperx_runner.py gives ModuleNotFoundError: No module named 'rockforge'; the job ends unavailable.

**Root cause:** _whisperx_runner.py imported rockforge.infrastructure.lyrics.whisperx_adapter (which imports application.ports); the other runners import nothing from rockforge.

**Fixes:** [FIX-0299](../FIX_LOG.md#fix-0299) (0.11.0-beta.3)

**Verified:** tests/test_ml_python.py::test_no_runner_imports_rockforge; tests/test_lyrics_transcribe.py passed, and fails with the fix reverted (by pytest (the test fails on the old code))

**Resolved:** 2026-10-18 · **Closed:** _pending_

**Evidence:**

- code review of the whole codebase (six reviewers), confirmed by reading the code

**History:**

- 2026-10-18 — Open: reported
- 2026-10-18 — Fixed: commit 2ae21cd533
- 2026-10-18 — Verified: its test passes and fails on the old code

## BUG-0330

**A components install step that stalled silently never timed out**

| | |
|---|---|
| Detected | 2026-10-18 |
| Reported by | code review (Claude, on the maintainer's request) |
| Found in | 0.11.0-beta.2 |
| Build / commit | f64c45e8e176c44bd87c7c7866f741330b443011 |
| Severity | Low |
| Priority | P3 |
| Status | Verified |

The limit was checked only between output lines.

**Steps to reproduce:** 

1. See the description (found by reading the code)

**Expected:** As described in the solution.

**Observed:** The limit was checked only between output lines.

**Root cause:** readline blocked.

**Fixes:** [FIX-0330](../FIX_LOG.md#fix-0330) (0.11.0-beta.4)

**Verified:** tests/test_components.py::test_a_step_that_stalls_without_printing_is_stopped_at_its_limit passed, and fails with the fix reverted (by pytest (the test fails on the old code))

**Resolved:** 2026-10-18 · **Closed:** _pending_

**Evidence:**

- code review of the whole codebase (six reviewers), confirmed by reading the code

**History:**

- 2026-10-18 — Open: reported
- 2026-10-18 — Fixed: commit 76c44a8bcd
- 2026-10-18 — Verified: its test passes and fails on the old code

## BUG-0331

**Without WebView2 the .exe never shut down when the browser tab closed**

| | |
|---|---|
| Detected | 2026-10-18 |
| Reported by | code review (Claude, on the maintainer's request) |
| Found in | 0.11.0-beta.2 |
| Build / commit | f64c45e8e176c44bd87c7c7866f741330b443011 |
| Severity | Medium |
| Priority | P3 |
| Status | Verified |

The window path set the idle watchdog off before the window failed; the browser fallback then served without it.

**Steps to reproduce:** 

1. See the description (found by reading the code)

**Expected:** As described in the solution.

**Observed:** The window path set the idle watchdog off before the window failed; the browser fallback then served without it.

**Root cause:** The idle value was chosen before knowing the window would open.

**Fixes:** [FIX-0331](../FIX_LOG.md#fix-0331) (0.11.0-beta.4)

**Verified:** tests/test_standalone_launcher.py::test_when_the_window_fails_the_browser_gets_its_tab_close_watchdog_back passed, and fails with the fix reverted (by pytest (the test fails on the old code))

**Resolved:** 2026-10-18 · **Closed:** _pending_

**Evidence:**

- code review of the whole codebase (six reviewers), confirmed by reading the code

**History:**

- 2026-10-18 — Open: reported
- 2026-10-18 — Fixed: commit 76c44a8bcd
- 2026-10-18 — Verified: its test passes and fails on the old code
