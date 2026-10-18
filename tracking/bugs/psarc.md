<!-- Generated from tracking/bugs.json by `python -m tools.tracking render`. Do not edit by hand: edit the JSON and render again. -->

# Bugs: psarc

The native .psarc: SNG, manifest, container, verification. Index: [BUG_LOG.md](../BUG_LOG.md).

## BUG-0055

**Native PSARC never appeared in the song list: retail enumeration layout missing**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer (in game) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 6ea35fb4fa9bed20c5e9d0250db0daa97301e9dd |
| Severity | Critical |
| Priority | P1 |
| Status | Closed |

A song built with the native packer never appeared in Rocksmith's song list: the file name lacked the _p tag, there was no appid file, no InsertRoot, no xblock, flat models, aggregate graph or header .hsan, the SNG was in the wrong folder and TOC offsets were relative.

**Steps to reproduce:** _pending_

**Expected:** The song appears in the in-game list.

**Observed:** The song never appeared in the list.

**Root cause:** The packer did not emit the retail layout the engine enumerates (found by byte-diffing a working DLC Builder PSARC).

**Fixes:** [FIX-0055](../FIX_LOG.md#fix-0055) (0.10.0-beta.1)

**Verified:** docs/TESTES-NO-JOGO.md Confirmado: 'A música aparece na lista e carrega (PSARC nativo) — Beartooth "Free"' (by the maintainer (in game))

**Resolved:** 2026-07-07 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: The native PSARC could not be played at all.

**Evidence:**

- CLAUDE.md § Dual output: Bundle + PSARC always — 'Rocksmith PC load requirements — the full enumeration layout (`gamedata.py`).'
- commit c07c4deeb6 Fix native PSARC so Rocksmith can list it: _p suffix + appid + InsertRoot
- commit 65f1cad121 Native PSARC: emit the full retail enumeration layout so songs list in-game
- found_in_version: the fix commit c07c4deeb6 is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent 6ea35fb4fa

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-07 — Fixed: commit c07c4deeb6, 65f1cad121
- 2026-07-07 — Verified: confirmed by user
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0056

**Native PSARC froze on the note highway: the SNG was not a real .sng file**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer (in game) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | c91bc1697c681a34e36d1b52bb669ee751603cdc |
| Severity | Critical |
| Priority | P1 |
| Status | Closed |

The packer encrypted the SNG with the bare AES-256-CTR primitive (random IV, no header, no zlib), so the game could not parse it: the song showed its tuning and then froze on the note highway.

**Steps to reproduce:** _pending_

**Expected:** The note highway loads and plays.

**Observed:** The song showed its tuning and froze on the note highway.

**Root cause:** The SNG was written without the retail 8-byte header, zero IV and zlib-compressed, size-prefixed payload.

**Fixes:** [FIX-0056](../FIX_LOG.md#fix-0056) (0.10.0-beta.1)

**Verified:** regression test(s) test_pack_sng_produces_a_loadable_sng_file pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-07-07 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: The song could not be played.

**Evidence:**

- CLAUDE.md § Dual output: Bundle + PSARC always — 'written as a **full retail `.sng` file** (`crypto.pack_sng` ...)'
- commit ab2ff431f7 Native PSARC: write a real .sng file so the note highway loads (fix freeze)
- found_in_version: the fix commit ab2ff431f7 is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent c91bc1697c

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-07 — Fixed: commit ab2ff431f7
- 2026-07-07 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0057

**Game crashed on load: the SNG beat record was 12 bytes instead of 16**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer (in game) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 6455f2dc565c35d7d9ad62be839a688c797f5363 |
| Severity | Critical |
| Priority | P1 |
| Status | Closed |

The Sng2014 beat was written as 12 bytes, missing a trailing int32 mask, so with a few hundred beats the whole SNG misaligned and the game crashed with an access violation (0xc0000005) reading past the buffer.

**Steps to reproduce:** _pending_

**Expected:** The song loads.

**Observed:** Access violation (0xc0000005) on load.

**Root cause:** The beat struct format was <fhhi (12 bytes) instead of <fhhii (16 bytes with a mask).

**Fixes:** [FIX-0057](../FIX_LOG.md#fix-0057) (0.10.0-beta.1)

**Verified:** regression test(s) test_beats_carry_real_measures_and_downbeat_mask pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-07-07 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: The game crashed on every native song.

**Evidence:**

- CLAUDE.md § Dual output: Bundle + PSARC always — 'Iterated to playability against a real Rocksmith install (the SNG format/beat-mask/slide-sentinel/anchor fixes below came from that loop)'
- commit ad51d753ee Native PSARC SNG: fix the beat struct (16 bytes + mask) — the crash cause
- found_in_version: the fix commit ad51d753ee is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent 6455f2dc56

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-07 — Fixed: commit ad51d753ee
- 2026-07-07 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0058

**Every note rendered a slide: the SNG no-slide sentinel was 0 instead of -1**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer (in game) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | ad51d753eefdf88da6f55c16c0f3d9d64dece41b |
| Severity | Critical |
| Priority | P1 |
| Status | Closed |

The SNG slide fields were written as 0, meaning 'slide to fret 0', so every note drew a red slide streak across the neck and the game could crash entering the arrangement.

**Steps to reproduce:** _pending_

**Expected:** Plain notes show no slide.

**Observed:** Every note showed a slide; the game could crash on entry.

**Root cause:** slide_to / slide_unpitch_to defaulted to 0 instead of the -1 (0xFF) sentinel.

**Fixes:** [FIX-0058](../FIX_LOG.md#fix-0058) (0.10.0-beta.1)

**Verified:** regression test(s) test_plain_notes_have_no_slide, test_real_slide_is_preserved pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-07-07 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Charts were unreadable and could crash the game.

**Evidence:**

- CLAUDE.md § Dual output: Bundle + PSARC always — 'the SNG format/beat-mask/slide-sentinel/anchor fixes'
- commit 84eadfb3b4 Native PSARC SNG: no-slide sentinel is -1, not 0 (fix slide on every note)
- found_in_version: the fix commit 84eadfb3b4 is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent ad51d753ee

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-07 — Fixed: commit 84eadfb3b4
- 2026-07-07 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0059

**Note highway crashed on play: every SNG anchor started at t=0**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer (in game) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | f07f5187bc516efa366d9e2b71539bc10812fd5e |
| Severity | Critical |
| Priority | P1 |
| Status | Closed |

Anchors were keyed off the phrase iteration's start, so with the single default phrase every anchor started at t=0; the overlapping anchors crashed the note highway when the song was entered.

**Steps to reproduce:** _pending_

**Expected:** The song plays.

**Observed:** The note highway crashed on entering the song.

**Root cause:** Anchor times were the phrase iteration start time instead of the note where the hand position changes.

**Fixes:** [FIX-0059](../FIX_LOG.md#fix-0059) (0.10.0-beta.1)

**Verified:** regression test(s) test_anchors_have_distinct_increasing_times pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-07-07 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: The game crashed.

**Evidence:**

- CLAUDE.md § Dual output: Bundle + PSARC always — 'the SNG format/beat-mask/slide-sentinel/anchor fixes'
- commit c62ca0635b Native PSARC SNG: sequential anchor times (fix note-highway crash on play)
- found_in_version: the fix commit c62ca0635b is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent f07f5187bc

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-07 — Fixed: commit c62ca0635b
- 2026-07-07 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0060

**Chart showed no notes and crashed when the GP file had no section markers**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer (in game) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | ab2ff431f751d6645bde8fbbaaf7b2ca6dceab29 |
| Severity | Critical |
| Priority | P1 |
| Status | Closed |

When the arrangement carried no section markers (the common case) the SNG had zero phrases; Rocksmith ends playback at the last phrase iteration, so the fretboard loaded with no notes and crashed.

**Steps to reproduce:** _pending_

**Expected:** The notes play.

**Observed:** The fretboard loaded, showed no notes and crashed.

**Root cause:** SNG phrases were built only from arrangement.sections.

**Fixes:** [FIX-0060](../FIX_LOG.md#fix-0060) (0.10.0-beta.1)

**Verified:** regression test(s) test_empty_arrangement_produces_valid_sng pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-07-07 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: The chart was unplayable.

**Evidence:**

- CLAUDE.md § Dual output: Bundle + PSARC always — 'The SNG always emits a valid phrase timeline (`sng._default_sections` ...) — without it the game loads the fretboard, shows no notes and crashes'
- commit f07f5187bc Native PSARC: phrase timeline + manifest note counts (fix no-notes/crash)
- found_in_version: the fix commit f07f5187bc is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent ab2ff431f7

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-07 — Fixed: commit f07f5187bc
- 2026-07-07 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0061

**Song list showed '0 notes' and a blank difficulty bar for native PSARCs**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer (in game) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | ab2ff431f751d6645bde8fbbaaf7b2ca6dceab29 |
| Severity | Low |
| Priority | P4 |
| Status | Closed |

The manifest hard-coded NotesEasy/Medium/Hard = 0 and empty phrase/iteration/section tables, so the song-select screen showed '000' notes and no difficulty bar.

**Steps to reproduce:** _pending_

**Expected:** The song list shows the real note count.

**Observed:** '0 notes' and a blank difficulty bar.

**Root cause:** manifest.py wrote placeholder zeros instead of stats from the compiled SNG.

**Fixes:** [FIX-0061](../FIX_LOG.md#fix-0061) (0.10.0-beta.1)

**Verified:** regression test(s) test_manifest_reports_note_count_and_phrase_structure pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-07-07 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Cosmetic: the song itself was not affected by this field.

**Evidence:**

- CLAUDE.md § Dual output: Bundle + PSARC always — 'the manifest reports the real note count + phrase/iteration/section tables (`manifest.arrangement_stats`...) so the song-list screen shows the note count instead of "0"'
- commit f07f5187bc Native PSARC: phrase timeline + manifest note counts (fix no-notes/crash)
- found_in_version: the fix commit f07f5187bc is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent ab2ff431f7

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-07 — Fixed: commit f07f5187bc
- 2026-07-07 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0062

**Song dropped from the list: toolkit.version was not numeric**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer (in game) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 98a34e1f7e17ea88615c75e94af1bb2958739619 |
| Severity | Critical |
| Priority | P1 |
| Status | Closed |

toolkit.version said 'RockForge-native'; the CDLC loader patch reads that line to whitelist a CDLC, so it skipped the file and the game dropped the song even with the right appid. It played only after re-packing with the Custom Song Toolkit.

**Steps to reproduce:** _pending_

**Expected:** The song appears in the list as built.

**Observed:** The song appeared only after re-packing with the Custom Song Toolkit / CFSM.

**Root cause:** The 'Toolkit version:' line held a custom, non-numeric string.

**Fixes:** [FIX-0062](../FIX_LOG.md#fix-0062) (0.10.0-beta.1)

**Verified:** regression test(s) test_build_manifest_files_packs_and_round_trips pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-07-07 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: The song never appeared in game.

**Evidence:**

- CLAUDE.md § Dual output: Bundle + PSARC always — '`toolkit.version`'s **`Toolkit version:` line must be a numeric RocksmithToolkitLib version**'
- commit bf2dd0b7bb Native PSARC: numeric toolkit.version so the CDLC patch lists the song
- found_in_version: the fix commit bf2dd0b7bb is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent 98a34e1f7e

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-07 — Fixed: commit bf2dd0b7bb
- 2026-07-07 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0063

**Song dropped from the list: PSARC TOC name hashes were zero**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer (in game) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 285cc56674743f8a4385341d4397726c916935dd |
| Severity | Critical |
| Priority | P1 |
| Status | Closed |

Every PSARC TOC entry must store md5(archive_path); writing zeros left the game unable to resolve any asset, so it silently dropped the song from the list even with the correct appid.

**Steps to reproduce:** _pending_

**Expected:** The song appears in the list.

**Observed:** The song never appeared until re-packed by the Custom Song Toolkit.

**Root cause:** container.pack_entries wrote zeroed 16-byte name hashes (and a zero name-block hash).

**Fixes:** [FIX-0063](../FIX_LOG.md#fix-0063) (0.10.0-beta.1)

**Verified:** regression test(s) test_toc_entries_carry_md5_of_path pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-07-07 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: The song never appeared in game.

**Evidence:**

- CLAUDE.md § Dual output: Bundle + PSARC always — '**every TOC entry carries a 16-byte name hash = `md5(archive_path)`**'
- commit 6db29590df Native PSARC: TOC entries carry md5(path) name hash (fix song not listed)
- found_in_version: the fix commit 6db29590df is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent 285cc56674

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-07 — Fixed: commit 6db29590df
- 2026-07-07 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0064

**No cover shown in game: placeholder DDS had mip count 0**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 65f1cad1215a02d550d8b455b24516467a87c910 |
| Severity | Low |
| Priority | P4 |
| Status | Closed |

The placeholder DDS had dwMipMapCount=0, which the game reads as an empty texture.

**Steps to reproduce:** _pending_

**Expected:** Cover shown

**Observed:** No cover

**Root cause:** Wrong DDS header field.

**Fixes:** [FIX-0064](../FIX_LOG.md#fix-0064) (0.10.0-beta.1)

**Verified:** regression test(s) test_dxt1_from_rgb_is_a_valid_dds_of_the_right_size pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-07-07 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Cosmetic.

**Evidence:**

- commit eef9845514 Native PSARC: valid album-art DDS (real cover + fixed mip count)
- found_in_version: fix eef9845514 (2026-07-07) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 65f1cad121, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-07 — Fixed: commit eef9845514
- 2026-07-07 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0067

**Fretboard view thrashed and hid low notes (one anchor per fret change)**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer (in game) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 84eadfb3b4c0f5f3eddb5de1d0232f08db86d06c |
| Severity | Medium |
| Priority | P3 |
| Status | Fixed |

Anchors were re-emitted on every fret change, so the view thrashed and low notes scrolled in off the edge.

**Steps to reproduce:** _pending_

**Expected:** Stable window

**Observed:** Low notes hidden

**Root cause:** No grouping of positions into windows.

**Fixes:** [FIX-0067](../FIX_LOG.md#fix-0067) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-07-07 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Hard to read in game.

**Evidence:**

- commit 5ff67bf2f8 Native PSARC SNG: stable anchor windows (fix fretboard hiding low notes)
- found_in_version: fix 5ff67bf2f8 (2026-07-07) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 84eadfb3b4, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-07 — Fixed: commit 5ff67bf2f8

## BUG-0068

**In-game difficulty slider read a tiny/garbled maximum**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer (in game) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 9c3a8dba94a73ae463a1043f021009cf11b6932f |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

The coarse 5-tier DD and a wrong hero triple (max/3, 2max/3) made the slider show a tiny/garbled max.

**Steps to reproduce:** _pending_

**Expected:** Consistent max difficulty

**Observed:** Garbled difficulty max

**Root cause:** Inconsistent metadata/hero triples.

**Fixes:** [FIX-0068](../FIX_LOG.md#fix-0068) (0.10.0-beta.1)

**Verified:** regression test(s) test_dd_hero_triples_and_density_graduated_ceilings pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-07-07 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: DD unreliable.

**Evidence:**

- commit 285cc56674 Native PSARC DD: simplified DDC (density-graduated levels, hero triples)
- found_in_version: fix 285cc56674 (2026-07-07) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 9c3a8dba94, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-07 — Fixed: commit 285cc56674
- 2026-07-07 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0070

**Song dropped from the list: a partial raw PSARC block stored zlength 0**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer (in game) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | af305abdc194b6075b4abb8f97ef3e2f920dd562 |
| Severity | Critical |
| Priority | P1 |
| Status | Closed |

A partial uncompressed block (the 6-byte appid.appid) stored zlength 0, which Rocksmith reads as a full 65536-byte block, so the appid came back corrupt and the song was dropped even with the right appid value.

**Steps to reproduce:** _pending_

**Expected:** The song appears in the list.

**Observed:** The song never appeared until re-packed by the Custom Song Toolkit.

**Root cause:** _compress_block returned 0 for every raw block, including partial ones.

**Fixes:** [FIX-0070](../FIX_LOG.md#fix-0070) (0.10.0-beta.1)

**Verified:** regression test(s) test_partial_uncompressed_block_zlength_is_its_size_not_zero pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-07-08 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: The song never appeared in game.

**Evidence:**

- CLAUDE.md § Dual output: Bundle + PSARC always — '**a partial uncompressed block stores its real size in the block table, not 0**'
- commit 94b0a12b93 Native PSARC: partial raw block carries its real zlength, not 0 (fix listing)
- found_in_version: the fix commit 94b0a12b93 is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent af305abdc1

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-08 — Fixed: commit 94b0a12b93
- 2026-07-08 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0071

**Game crashed at the start of a section: SNG anchors crossed phrase boundaries**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer (in game) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 83a0d1472b6e3108b35ea9274d9c62e6de54816a |
| Severity | Critical |
| Priority | P1 |
| Status | Closed |

Anchors were generated with no regard for phrase iterations, so one could span a phrase boundary; when a new phrase's opening notes were covered only by the previous phrase's anchor the game found none of its own and crashed on entry (seen at a section / tone-change boundary at 127.5 s).

**Steps to reproduce:** _pending_

**Expected:** The song plays through section starts.

**Observed:** The game crashed at the start of a section, only in the native PSARC.

**Root cause:** Anchors were built globally from note positions and never split at phrase-iteration boundaries.

**Fixes:** [FIX-0071](../FIX_LOG.md#fix-0071) (0.10.0-beta.1)

**Verified:** regression test(s) test_anchors_do_not_cross_phrase_iteration_boundaries pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-07-08 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Game crash.

**Evidence:**

- CLAUDE.md § SNG binary compilation (`infrastructure/packaging/psarc/sng.py`) — 'Anchors never span a phrase-iteration boundary'
- commit 0a16f02576 Native PSARC SNG: split anchors at phrase-iteration boundaries (fix crash)
- found_in_version: the fix commit 0a16f02576 is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent 83a0d1472b

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-08 — Fixed: commit 0a16f02576
- 2026-07-08 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0072

**DD levels kept slide anchor-extensions and hand shapes for notes they dropped: crash**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer (in game) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 94b0a12b93324b91f10e1196892027669bbd76df |
| Severity | Critical |
| Priority | P1 |
| Status | Closed |

Every Dynamic Difficulty level shared the full chart's hand shapes and slide anchor-extensions while low levels drop most notes; on the first low-difficulty pass the game hit entries pointing at notes not in that level and crashed at the entry of a dense double-stop riff.

**Steps to reproduce:** _pending_

**Expected:** Low DD levels play.

**Observed:** Crash at the entry of a dense chord riff, only in the native PSARC.

**Root cause:** _build_level reused the full-chart fingerprint and anchor-extension lists.

**Fixes:** [FIX-0072](../FIX_LOG.md#fix-0072) (0.10.0-beta.1)

**Verified:** regression test(s) test_dd_levels_have_their_own_hand_shapes_and_slide_extensions pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-07-08 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Game crash.

**Evidence:**

- CLAUDE.md § SNG binary compilation (`infrastructure/packaging/psarc/sng.py`) — 'slide anchor-extensions are rebuilt per level from that level's own notes** (`_build_level`): an extension pointing at a note the level dropped crashes the game'
- commit 83a0d1472b Native PSARC DD: rebuild handshapes + slide extensions per level (fix crash)
- found_in_version: the fix commit 83a0d1472b is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent 94b0a12b93

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-08 — Fixed: commit 83a0d1472b
- 2026-07-08 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0073

**Low DD levels showed notes only at the start of a long phrase**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer (in game) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 0a16f0257632509eb0f919ed2f6bc23f2958c383 |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

Each phrase iteration's notes were ranked by (tier, time) and a level took the earliest prefix, so a long single-phrase song showed only its first part at low difficulty ('DD only at the start/end').

**Steps to reproduce:** _pending_

**Expected:** Low levels spread their notes across the phrase.

**Observed:** Low levels clustered notes in the first part of the song.

**Root cause:** Notes within a beat-strength tier were taken in plain time order.

**Fixes:** [FIX-0073](../FIX_LOG.md#fix-0073) (0.10.0-beta.1)

**Verified:** regression test(s) test_dd_low_levels_spread_notes_across_the_phrase pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-07-08 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Low difficulty levels were unbalanced; playable.

**Evidence:**

- CLAUDE.md § SNG binary compilation (`infrastructure/packaging/psarc/sng.py`) — 'within a phrase the shown notes are spread across its timeline (`_spread_order`) rather than clustered at its start'
- commit 5d72714e74 Native PSARC DD: spread low-difficulty notes across the phrase (fix clustering)
- found_in_version: the fix commit 5d72714e74 is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent 0a16f02576

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-08 — Fixed: commit 5d72714e74
- 2026-07-08 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0074

**Section-less song with no lead-in got no phrase segmentation**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | dacf214a060ca8c8581a99ca32ba80b1d881cdd2 |
| Severity | Low |
| Priority | P4 |
| Status | Closed |

When the first note was at the song start, the body branch was skipped and no auto-segmentation happened.

**Steps to reproduce:** _pending_

**Expected:** Phrases every ~13 s

**Observed:** One giant phrase

**Root cause:** Segmentation started from body == start.

**Fixes:** [FIX-0074](../FIX_LOG.md#fix-0074) (0.10.0-beta.1)

**Verified:** regression test(s) test_sectionless_song_is_segmented_into_multiple_phrases pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-07-08 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: DD quality.

**Evidence:**

- commit 7ea15f76f5 Fix section-less segmentation: segment from count-in; anchor test skips empty END
- found_in_version: fix 7ea15f76f5 (2026-07-08) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent dacf214a06, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-08 — Fixed: commit 7ea15f76f5
- 2026-07-08 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0075

**DD always started from level 0: SongDifficulty and mastery fields were zero**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | pending (not recorded) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 949639f435caae2384e019c111492c0eca1c860c |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

SongDifficulty/SongDiffEasy/Med/Hard and Easy/MediumMastery were 0, so DD never started at the player's level.

**Steps to reproduce:** _pending_

**Expected:** Skill-based start

**Observed:** DD starts at 0 every time

**Root cause:** Placeholder manifest values.

**Fixes:** [FIX-0075](../FIX_LOG.md#fix-0075) (0.10.0-beta.1)

**Verified:** regression test(s) test_manifest_reports_nonzero_song_difficulty pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-07-08 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: DD experience.

**Evidence:**

- commit d44648cef8 Native PSARC: non-zero SongDifficulty/mastery so DD starts at the player's level
- found_in_version: fix d44648cef8 (2026-07-08) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 949639f435, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-08 — Fixed: commit d44648cef8
- 2026-07-08 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0076

**Fret-hand anchor sat below the chord being played**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer (in game) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | d44648cef8d1da2935ccd42904d2562809a25612 |
| Severity | Low |
| Priority | P4 |
| Status | Closed |

The greedy grouping merged up to a 5-fret span, letting a stray low note drag a 3-5 chord run into a 1-5 window.

**Steps to reproduce:** _pending_

**Expected:** Anchor hugs the notes

**Observed:** Anchor one or two frets low

**Root cause:** Merge span 5.

**Fixes:** [FIX-0076](../FIX_LOG.md#fix-0076) (0.10.0-beta.1)

**Verified:** regression test(s) test_anchor_does_not_sit_below_a_chord_run pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-07-08 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Visual.

**Evidence:**

- commit 22959323f0 Native PSARC SNG: tighter anchors (max merge span 4) so they hug the notes
- found_in_version: fix 22959323f0 (2026-07-08) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent d44648cef8, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-08 — Fixed: commit 22959323f0
- 2026-07-08 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0077

**Crash at the first 5-7 octave riff in 'Free' (native PSARC)**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer (in game) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 22959323f0235c5ab20bddc54112d0f6fd110eea |
| Severity | Critical |
| Priority | P1 |
| Status | Fixed |

The native PSARC crashed at the entry of the first octave riff (79.1 s); one-fingerprint-per-chord hand shapes were removed as the remaining structural difference. The crash was later traced to chord-template MIDI 0 (c4ced54) and the PhraseId bug (cf30b82); hand shapes came back in 73d49d4.

**Steps to reproduce:** _pending_

**Expected:** Plays

**Observed:** Crash at the octave riff

**Root cause:** Attributed at the time to back-to-back hand shapes; later traced elsewhere.

**Fixes:** [FIX-0077](../FIX_LOG.md#fix-0077) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-07-08 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Crash in game.

**Evidence:**

- CLAUDE.md § SNG binary compilation (History, so the risk is clear)
- commit 070503350a Native PSARC SNG: stop emitting fingerprints/handshapes (fix octave-riff crash)
- found_in_version: fix 070503350a (2026-07-08) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 22959323f0, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-08 — Fixed: commit 070503350a

## BUG-0078

**Corrupt full-height vertical bar at palm-muted chord runs (single-note bit in ChordNotes)**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer (in game) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 070503350ac35c0c477ba11347fdb5ce85b74bb8 |
| Severity | High |
| Priority | P2 |
| Status | Fixed |

ChordNotes per-string masks carried the SINGLE note-kind bit (0x800000), drawing a corrupt vertical bar.

**Steps to reproduce:** _pending_

**Expected:** Normal chords

**Observed:** Vertical bar artifact

**Root cause:** _note_mask reused verbatim for chord strings.

**Fixes:** [FIX-0078](../FIX_LOG.md#fix-0078) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-07-08 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Visible corruption.

**Evidence:**

- commit ea09b649a2 Native PSARC SNG: chordnotes carry technique bits only, deduped (fix bad render)
- found_in_version: fix ea09b649a2 (2026-07-08) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 070503350a, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-08 — Fixed: commit ea09b649a2

## BUG-0079

**Crash entering the next DD phrase: PhraseIterationLinks written as 0**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer (in game) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 82bc1a613c35d39f2027a9e2573c5a2525d451cf |
| Severity | Critical |
| Priority | P1 |
| Status | Closed |

Retail carries each phrase's real iteration count; with 0 the game crashed entering the next DD phrase.

**Steps to reproduce:** _pending_

**Expected:** Plays

**Observed:** Crash on phrase entry

**Root cause:** Placeholder 0.

**Fixes:** [FIX-0079](../FIX_LOG.md#fix-0079) (0.10.0-beta.1)

**Verified:** regression test(s) test_gp_sections_are_bracketed_with_count_and_end_and_links pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-07-08 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Crash in game.

**Evidence:**

- commit eb80ab31a5 Native PSARC SNG: COUNT/END bracket for GP sections + real PhraseIterationLinks
- found_in_version: fix eb80ab31a5 (2026-07-08) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 82bc1a613c, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-08 — Fixed: commit eb80ab31a5
- 2026-07-08 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0080

**First phrase swallowed the silent intro and no END phrase (GP sections)**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer (in game) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 82bc1a613c35d39f2027a9e2573c5a2525d451cf |
| Severity | Low |
| Priority | P4 |
| Status | Closed |

With GP sections the first phrase covered the silent intro (all-black Riff Repeater bar) and there was no closing END phrase.

**Steps to reproduce:** _pending_

**Expected:** COUNT then content then END

**Observed:** Black phrase bar at start

**Root cause:** Sections not bracketed.

**Fixes:** [FIX-0080](../FIX_LOG.md#fix-0080) (0.10.0-beta.1)

**Verified:** regression test(s) test_gp_sections_are_bracketed_with_count_and_end_and_links pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-07-08 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Cosmetic.

**Evidence:**

- commit eb80ab31a5 Native PSARC SNG: COUNT/END bracket for GP sections + real PhraseIterationLinks
- found_in_version: fix eb80ab31a5 (2026-07-08) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 82bc1a613c, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-08 — Fixed: commit eb80ab31a5
- 2026-07-08 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0081

**Crash on DD phrase entry: full-chart anchors on every level**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer (in game) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | e175c1d8a515f8bb9532466886e3850604d3f49c |
| Severity | Critical |
| Priority | P1 |
| Status | Closed |

The same 82 anchors shipped on every level, framing notes absent at low levels; the game crashed on entry to a DD phrase.

**Steps to reproduce:** _pending_

**Expected:** Plays

**Observed:** Crash on phrase entry

**Root cause:** Anchors not built per level.

**Fixes:** [FIX-0081](../FIX_LOG.md#fix-0081) (0.10.0-beta.1)

**Verified:** regression test(s) test_anchors_are_built_per_level_not_shared pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-07-08 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Crash in game.

**Evidence:**

- commit e3be69e561 Native PSARC DD: build anchors per level (fix crash on DD phrase entry)
- found_in_version: fix e3be69e561 (2026-07-08) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent e175c1d8a5, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-08 — Fixed: commit e3be69e561
- 2026-07-08 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0083

**Native PSARC stage stayed dark and the title card was skipped: empty showlights**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer (in game) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 314e09eef91d5bdc10c24075a4bac5e6b38be829 |
| Severity | Low |
| Priority | P4 |
| Status | Closed |

build_showlights returned an empty track, leaving the stage dark; the song started straight on the fretboard without the song-name/title card the game shows over the lit intro.

**Steps to reproduce:** _pending_

**Expected:** Stage lighting and the title card over the intro.

**Observed:** A dark stage and no title card.

**Root cause:** No fog/beam events were generated from the arrangement.

**Fixes:** [FIX-0083](../FIX_LOG.md#fix-0083) (0.10.0-beta.1)

**Verified:** TESTING.md §7f-bis: 'the song-name/title card and stage lighting appear over the intro now that `build_showlights` emits a real fog+beam track' (Confirmed in-game) (by the maintainer (in game))

**Resolved:** 2026-07-09 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Cosmetic; the song played.

**Evidence:**

- CLAUDE.md § Dual output: Bundle + PSARC always — '`songs/arr/<key>_showlights.xml` — the **stage-lighting track** ... An **empty** showlights (the old behaviour) leaves the stage dark'
- commit feb6390a64 Generate a real showlights (stage-lighting) track instead of an empty one
- found_in_version: the fix commit feb6390a64 is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent 314e09eef9

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-09 — Fixed: commit feb6390a64
- 2026-07-09 — Verified: confirmed by user
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0086

**Crash at the first bent chord (ChordNotes UsedCount before the bend array)**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer (in game) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | ea09b649a29b252a75b5827458db260f0227d125 |
| Severity | Critical |
| Priority | P1 |
| Status | Closed |

The native PSARC crashed entering the first bent chord ('Free' C-part, ~128 s). Several placements were tried (time 0, drop bends, two-point, EOF third, drop again); the cause was the ChordNotes layout: UsedCount written before the 32 BendData32 entries.

**Steps to reproduce:** _pending_

**Expected:** Bends play

**Observed:** Crash at bent chords

**Root cause:** UsedCount must follow the 32-entry array.

**Fixes:** [FIX-0086](../FIX_LOG.md#fix-0086) (0.10.0-beta.1)

**Verified:** TESTING.md (69c0abb): 'the half-step bends play correctly and no longer crash at the C-part' (by the maintainer (in game))

**Resolved:** 2026-07-09 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Crash in game.

**Evidence:**

- commit 82bc1a613c Native PSARC SNG: bend points carry absolute song time, not 0.0 (fix crash)
- commit 3bed9fe87f Drop bend emission from the SNG (crashed at the first bent chord)
- commit debd8856c9 Emit proper bend curves instead of dropping bends
- commit 8db4b4bf57 Align bend export to Editor on Fire's convention
- commit 15ad4dced4 Drop bends from the native SNG (keep them in the DLC Builder path)
- commit ed87865b08 Fix ChordNotes bend layout: UsedCount goes AFTER the 32-entry array
- found_in_version: fix 82bc1a613c (2026-07-08) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent ea09b649a2, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-09 — Fixed: commit 82bc1a613c, 3bed9fe87f, debd8856c9, 8db4b4bf57, 15ad4dced4, ed87865b08
- 2026-07-09 — Verified: confirmed by user
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0087

**Bends looked smaller in game (point at the attack = prebend)**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer (in game) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | ed87865b08a41098aa154475e46ad3e8be59af37 |
| Severity | Low |
| Priority | P4 |
| Status | Closed |

The single bend point sat at the attack, so the note started bent and no rise was seen.

**Steps to reproduce:** _pending_

**Expected:** Visible rise across the note

**Observed:** Bend looks small

**Root cause:** Point placed at attack instead of note end.

**Fixes:** [FIX-0087](../FIX_LOG.md#fix-0087) (0.10.0-beta.1)

**Verified:** regression test(s) test_bend_point_reaches_peak_at_note_end_like_dlc_builder pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-07-09 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Visual.

**Evidence:**

- commit 6d037241fc Bend rises to peak at the note's end, not the attack (match DLC Builder)
- found_in_version: fix 6d037241fc (2026-07-09) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent ed87865b08, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-09 — Fixed: commit 6d037241fc
- 2026-07-09 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0091

**DD difficulty bars flat-topped at the level-11 cap**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer (in game) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 4d49009a0eed8ed8bdb24679e0802d61b9900a25 |
| Severity | Low |
| Priority | P4 |
| Status | Closed |

_DD_LEVEL_CAP=11 clamped every dense phrase, so most phrases piled at the ceiling.

**Steps to reproduce:** _pending_

**Expected:** Heights vary with density

**Observed:** Flat difficulty bars

**Root cause:** Low cap.

**Fixes:** [FIX-0091](../FIX_LOG.md#fix-0091) (0.10.0-beta.1)

**Verified:** regression test(s) test_dd_phrase_heights_vary_with_density pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-07-09 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: DD shape.

**Evidence:**

- commit d9a2d282f7 Variable-height Dynamic Difficulty: raise the phrase ceiling 11 -> 20
- found_in_version: fix d9a2d282f7 (2026-07-09) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 4d49009a0e, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-09 — Fixed: commit d9a2d282f7
- 2026-07-09 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0094

**Game crashed at a gapped octave while scoring: chord template unused strings were MIDI 0**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer (in game) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 4eb877bc411eceeff9ae6b0e8bafae819a01488b |
| Severity | Critical |
| Priority | P1 |
| Status | Closed |

A chord template's unused strings carried MIDI 0 instead of -1; the game dereferences them while scoring, so it crashed at the entry of a gapped 5/7 octave only while the player was playing, never on a hands-off run.

**Steps to reproduce:** 

1. Play Beartooth 'Free' (native PSARC) through the octave section after the last solo

**Expected:** The octave plays and scores.

**Observed:** The game crashed at the gapped 5/7 octave, only while playing.

**Root cause:** Unused template strings were written as MIDI 0 (a real pitch) instead of -1.

**Fixes:** [FIX-0094](../FIX_LOG.md#fix-0094) (0.10.0-beta.1)

**Verified:** TESTING.md §7f-bis: 'Notes/chords while scoring ✅ Fixed & confirmed in-game' (with the separate MIDI -1 finding on the same octave) (by the maintainer (in game))

**Resolved:** 2026-07-10 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Game crash during normal play.

**Evidence:**

- CLAUDE.md § SNG binary compilation (`infrastructure/packaging/psarc/sng.py`) — '**A chord template's unused strings carry MIDI note -1, NOT 0.**'
- CLAUDE.md § SNG binary compilation — 'hand shapes were removed once ... That crash was later traced to the chord templates' unused strings carrying MIDI 0' (commit 0705033 had removed hand shapes over this crash)
- commit c4ced54a31 Fix scoring crash: chord template unused strings are MIDI -1, not 0
- found_in_version: the fix commit c4ced54a31 is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent 4eb877bc41

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-10 — Fixed: commit c4ced54a31
- 2026-07-10 — Verified: confirmed by user
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0095

**Game crashed while scoring notes in late sections: note PhraseId out of range**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer (in game) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | c4ced54a31114aad7b2948025bf60b902ee9a873 |
| Severity | Critical |
| Priority | P1 |
| Status | Closed |

A note's PhraseId was set to its phrase-iteration index; once repeated riffs were linked into fewer phrases than iterations, notes in late iterations pointed past the Phrases array and the game crashed while scoring them (DD on or off).

**Steps to reproduce:** 

1. Play Beartooth 'Free' (native PSARC) through the octave section after the last solo

**Expected:** The song scores without crashing.

**Observed:** Crash exactly when the player hit notes in a late section; a hands-off run was fine.

**Root cause:** from_arrangement set phrase_id to the iteration index instead of phrase_iterations[pi].phrase_id.

**Fixes:** [FIX-0095](../FIX_LOG.md#fix-0095) (0.10.0-beta.1)

**Verified:** TESTING.md §7f-bis: 'Fixed (`phrase_id = phrase_iterations[pi].phrase_id`) and confirmed in-game on Beartooth "Free" (played through the octave section, no crash)' (by the maintainer (in game))

**Resolved:** 2026-07-10 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Game crash on almost every song with repeated riffs.

**Evidence:**

- CLAUDE.md § SNG binary compilation (`infrastructure/packaging/psarc/sng.py`) — '**A note's `phrase_id` is the linked phrase id, NOT its iteration index.**'
- commit cf30b82a1e Fix scoring crash: a note's PhraseId must be the linked phrase id, not the iteration index
- found_in_version: the fix commit cf30b82a1e is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent c4ced54a31

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-10 — Fixed: commit cf30b82a1e
- 2026-07-10 — Verified: confirmed by user
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0112

**Corrupt lateral highway blur on fast repeated chords: high density never set**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer (in game) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 34e8758d4c1c2e759bc34020020e3cc1929335f9 |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

NOTE_MASK_HIGHDENSITY was defined but never applied, so a fast chug of the same chord drew a full chord box on every hit and stacked them into a corrupt lateral blur on the native PSARC.

**Steps to reproduce:** _pending_

**Expected:** Repeats of a chord are drawn condensed.

**Observed:** A corrupt lateral blur on dense chugs (native PSARC only).

**Root cause:** The native SNG has no DDC pass to recompute high density and never set the flag.

**Fixes:** [FIX-0112](../FIX_LOG.md#fix-0112) (0.10.0-beta.1)

**Verified:** regression test(s) test_repeated_chords_marked_high_density_but_not_the_first, test_repeated_chords_get_high_density pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-07-11 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Graphical glitch; the song played.

**Evidence:**

- CLAUDE.md § SNG binary compilation (`infrastructure/packaging/psarc/sng.py`) — '**Repeated chords are marked HIGH DENSITY (condensed rendering).**'
- commit c057139 notes HIGH_DENSITY 'turned out not to be the cause' of a later persisting glitch
- commit ddcb6cf001 Native SNG: mark repeated chords high-density (fix corrupt highway sprite)
- found_in_version: the fix commit ddcb6cf001 is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent 34e8758d4c

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-11 — Fixed: commit ddcb6cf001
- 2026-07-11 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0113

**Graphical glitch at the first notes: song-start anchor took the LAST phrase**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer (in game) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 7aa075eeb647bf6bc877e2f47fca8d965763e92d |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

_find_phrase_iteration's not-found fallback returned the last index even for a time before the first phrase, so the song-opening anchor at 0.0 was tagged with a phrase near the song's end, corrupting the fret-hand anchor box at the chart's first notes.

**Steps to reproduce:** _pending_

**Expected:** A clean highway at the first notes.

**Observed:** A corrupt highway sprite right at the first group of notes ('logo o primeiro grupo de notas a começar no compasso 7').

**Root cause:** The fallback did not distinguish a time before the first iteration from one after the last.

**Fixes:** [FIX-0113](../FIX_LOG.md#fix-0113) (0.10.0-beta.1)

**Verified:** regression test(s) test_find_phrase_iteration_before_first_start_returns_first_index, test_song_start_anchor_has_correct_phrase_iteration_not_the_last pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-07-11 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Graphical glitch; playable.

**Evidence:**

- CLAUDE.md § SNG binary compilation (`infrastructure/packaging/psarc/sng.py`) — '**A song-start anchor before the first phrase must not wrap onto the LAST phrase.**'
- commit c057139826 Fix song-start anchor wrapping onto the LAST phrase (real corrupt-highway bug)
- found_in_version: the fix commit c057139826 is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent 7aa075eeb6

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-11 — Fixed: commit c057139826
- 2026-07-11 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0114

**Corrupt highway bars on sustained chords: no ChordNotes entry for plain sustained chords**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer (in game) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | c057139826cfc2fc7655e8209dc984c0e29d7840 |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

ChordNotes entries were emitted only for chords with a technique, so a plain sustained power-chord chug had chord_notes_id -1 and the game drew corrupt vertical/lateral bars while streaming notes (Riff Repeater / scrubbing), only on Rhythm chords.

**Steps to reproduce:** _pending_

**Expected:** Sustained chords render cleanly.

**Observed:** Corrupt vertical/lateral bars on sustained chords in the native PSARC.

**Root cause:** A chord's per-string sustain lives in its ChordNotes entry, which was skipped when the chord had no technique.

**Fixes:** [FIX-0114](../FIX_LOG.md#fix-0114) (0.10.0-beta.1)

**Verified:** CLAUDE.md: '**Confirmed fixed in-game** — the corrupt bars are gone on the native PSARC.' (commit 7a367d8) (by the maintainer (in game))

**Resolved:** 2026-07-11 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Graphical glitch on the highway; playable.

**Evidence:**

- CLAUDE.md § SNG binary compilation (`infrastructure/packaging/psarc/sng.py`) — '**Every SUSTAINED chord gets a ChordNotes entry, not just technique chords.**'
- commit fb8f118456 Emit ChordNotes for every sustained chord (fix corrupt highway bars)
- found_in_version: the fix commit fb8f118456 is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent c057139826

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-11 — Fixed: commit fb8f118456
- 2026-07-11 — Verified: confirmed by user
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0124

**Accented lyrics could crash SNG read-back (UTF-8 cut mid-character)**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 71238818efa88c126ba98c95cf1ef4bda9b1f67d |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

_pack_str truncated by raw bytes, splitting multi-byte characters near the 32/48-byte limit and shipping invalid UTF-8.

**Steps to reproduce:** _pending_

**Expected:** Valid strings

**Observed:** Invalid UTF-8 in the .sng

**Root cause:** Byte slice ignored character boundaries.

**Fixes:** [FIX-0124](../FIX_LOG.md#fix-0124) (0.10.0-beta.1)

**Verified:** regression test(s) test_pack_str_truncates_on_a_utf8_character_boundary pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-07-13 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Corrupt output for some lyrics.

**Evidence:**

- commit 58b629466d fix: two critical corruption bugs found in a full-codebase audit
- found_in_version: fix 58b629466d (2026-07-13) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 71238818ef, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-13 — Fixed: commit 58b629466d
- 2026-07-13 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0131

**DD tier of a note on the final beat compared to the first beat**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | d94e112def3a123154050101b1ba61fdce12472e |
| Severity | Low |
| Priority | P4 |
| Status | Closed |

_note_tier's end-of-song fallback compared with beats[0], so the final downbeat was tier 1.

**Steps to reproduce:** _pending_

**Expected:** Tier 0

**Observed:** Wrong tier

**Root cause:** Wrong edge beat.

**Fixes:** [FIX-0131](../FIX_LOG.md#fix-0131) (0.10.0-beta.1)

**Verified:** regression test(s) test_note_tier_at_song_end_uses_the_last_beat_not_the_first pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-07-13 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Cosmetic DD order.

**Evidence:**

- commit 44123dc84f Fix _note_tier end-of-song fallback comparing to the wrong beat (MIN-12)
- found_in_version: fix 44123dc84f (2026-07-13) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent d94e112def, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-13 — Fixed: commit 44123dc84f
- 2026-07-13 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0155

**Manifest advertised no techniques, SongOffset 0 and TargetScore 0**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 72ba5c049bc3e8f33e160cb2438d6ac43dfbfa6f |
| Severity | Low |
| Priority | P4 |
| Status | Closed |

Every ArrangementProperties technique flag was 0, so each chart claimed to use no palm mutes, power chords, slides, sustain or vibrato; SongOffset was 0 instead of -startTime and TargetScore 0 instead of 100000.

**Steps to reproduce:** _pending_

**Expected:** The manifest describes the chart's content and timing.

**Observed:** Placeholder zeros in those fields.

**Root cause:** manifest.py wrote placeholders instead of values derived from the notes.

**Fixes:** [FIX-0155](../FIX_LOG.md#fix-0155) (0.10.0-beta.1)

**Verified:** regression test(s) test_arrangement_properties_report_the_techniques_actually_played, test_manifest_reports_the_lead_in_and_a_real_target_score pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-08-23 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: A false description of the chart; no in-game symptom traced to it.

**Evidence:**

- CLAUDE.md § Dual output: Bundle + PSARC always — '**`ArrangementProperties`' technique flags, `SongOffset` and `TargetScore` are real values, not zeros.**'
- commit 912ae9e0e4 DD: give every phrase levels to climb, and stop reporting zeros in the manifest
- found_in_version: the fix commit 912ae9e0e4 is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent 72ba5c049b

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-08-23 — Fixed: commit 912ae9e0e4
- 2026-08-23 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0158

**SNG wrote CapoFret 0 ('capo at fret 0') when there was no capo**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | f159fb23f2f31563bffe42b922e27808e03ad250 |
| Severity | Low |
| Priority | P4 |
| Status | Fixed |

CapoFret was 0, a real value, where the format wants 255 for 'no capo'.

**Steps to reproduce:** _pending_

**Expected:** CapoFret 255 without a capo.

**Observed:** CapoFret 0.

**Root cause:** 0 used where the format expects a sentinel (found byte-diffing a DLC Builder build).

**Fixes:** [FIX-0158](../FIX_LOG.md#fix-0158) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-08-24 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: No in-game consequence was traced to it.

**Evidence:**

- CLAUDE.md § SNG binary compilation (`infrastructure/packaging/psarc/sng.py`) — '**`CapoFret` is 255 when there is no capo, NOT 0.**'
- commit 3e0ba45586 Write CapoFret 255 for "no capo", and let read_sng parse a real SNG
- found_in_version: the fix commit 3e0ba45586 is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent f159fb23f2

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-08-24 — Fixed: commit 3e0ba45586

## BUG-0169

**Dynamic Difficulty never kept a raised level in game**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer (in game) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | b8113a347a0667149c71c870fe2ce4a6d37a7152 |
| Severity | High |
| Priority | P2 |
| Status | Closed |

In the native PSARC the Dynamic Difficulty stayed at the minimum; later precisely, Riff Repeater raised a level and it was not kept, zeroing every time. The DLC Builder build of the same song ramped.

**Steps to reproduce:** _pending_

**Expected:** Phrases level up with play and the level persists.

**Observed:** The difficulty never moved off the minimum / a raised level zeroed again.

**Root cause:** Not isolated: a batch of divergences from a working DLC Builder build were fixed together (short phrases with zero levels, one ramp too low, 27 phrases sharing the name 'riff', saturated phrases never dropping out, empty Techniques/Events, one difficulty density written three times, no LastConversionDateTime, raw section UINames, a COUNT section and duplicate section numbers).

**Fixes:** [FIX-0169](../FIX_LOG.md#fix-0169) (0.10.0-beta.1)

**Verified:** CLAUDE.md: '**RESOLVED IN GAME (2026-08-25).** A rebuild carrying A, B, C, D, E, G and H ramps Dynamic Difficulty and KEEPS the level.' (by the maintainer (in game))

**Resolved:** 2026-08-25 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: An essential game feature did not work on native PSARCs; the DLC Builder route was the workaround.

**Evidence:**

- CLAUDE.md § SNG binary compilation (`infrastructure/packaging/psarc/sng.py`) — 'Simplified DDC (Dynamic Difficulty)' table A–H and '**RESOLVED IN GAME (2026-08-25).**'
- CLAUDE.md: 'The user ran the decisive experiment (2026-08-25): the DLC Builder build of the SAME song DOES ramp.'
- commit 75913587ea Fix Dynamic Difficulty never leaving the minimum level in-game
- commit 912ae9e0e4 DD: give every phrase levels to climb, and stop reporting zeros in the manifest
- commit 448c0e6316 Give each phrase a unique name (p0...pN) instead of repeating the section name
- commit 1730f2974b Make the DD levels and difficulty densities match a working reference
- commit 058b43d52b Emit the stage cues and the derived technique ids; fix the note counts
- commit 4f19ec37d3 Fix the section list: localisation names, no COUNT section, per-name numbers
- found_in_version: the fix commit 75913587ea is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent b8113a347a

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-08-25 — Fixed: commit 75913587ea, 912ae9e0e4, 448c0e6316, 1730f2974b, 058b43d52b, 4f19ec37d3
- 2026-08-25 — Verified: confirmed by user
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0170

**Riff Repeater named two passages the same: duplicate section numbers**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 058b43d52b6114a8af92258d4d3520304ca732dc |
| Severity | Low |
| Priority | P4 |
| Status | Closed |

Section Number was the list index, so with COUNT/END and several names mixed in the numbers duplicated and skipped; the shipped build had two consecutive sections both numbered 2.

**Steps to reproduce:** _pending_

**Expected:** Each section is numbered per name, continuing across arrangements.

**Observed:** Two different passages shared one section number.

**Root cause:** Both the SNG builder and the XML writer passed the list index as the number.

**Fixes:** [FIX-0170](../FIX_LOG.md#fix-0170) (0.10.0-beta.1)

**Verified:** regression test(s) test_number_sections_counts_per_name_not_by_position, test_section_numbers_continue_across_arrangements pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-08-25 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Confusing navigation in Riff Repeater.

**Evidence:**

- CLAUDE.md § SNG binary compilation (`infrastructure/packaging/psarc/sng.py`) — 'H — the section list ... **`Number` is an ordinal per NAME, not the list index.**'
- commit 4f19ec37d3 Fix the section list: localisation names, no COUNT section, per-name numbers
- found_in_version: the fix commit 4f19ec37d3 is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent 058b43d52b

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-08-25 — Fixed: commit 4f19ec37d3
- 2026-08-25 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0209

**Game froze on charts that enter late: sections out of order**

| | |
|---|---|
| Detected | 2026-09-30 |
| Reported by | the maintainer (in game) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 366cd3fe4a8db7cc2327173116511355a9ae406b |
| Severity | Critical |
| Priority | P1 |
| Status | Closed |

The COUNT bracket moved the first section to the chart's first note, so a rhythm entering at the chorus got 'Intro' after 'Verse 1' and a backwards phrase range; the game froze on Daughtry 'September''s Rhythm, Alternate Lead and Alternate Rhythm.

**Steps to reproduce:** 

1. Build Daughtry 'September' with its Rhythm / alternate tracks
2. Play one of those charts

**Expected:** The chart plays.

**Observed:** The game froze on the highway ('está a bloquear … é mais que uma pista').

**Root cause:** _prepare_sections always split the first section at the first note, even when that note was outside it.

**Fixes:** [FIX-0209](../FIX_LOG.md#fix-0209) (0.10.0-beta.1)

**Verified:** docs/TESTES-NO-JOGO.md Confirmado: 'Pista que só entra a meio da música (secções por ordem, sem bloquear) — Daughtry "September" (2026-09-30)' (by the maintainer (in game))

**Resolved:** 2026-09-30 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Game freeze.

**Evidence:**

- CLAUDE.md § SNG binary compilation (`infrastructure/packaging/psarc/sng.py`) — '**A chart that rests through the first sections keeps them in order.**'
- docs/TESTES-NO-JOGO.md — '✅ Resolvido: crash no "September" (2026-09-30)'
- commit 075da133c0 Native SNG: a chart that enters late keeps its sections in order (froze in game)
- found_in_version: the fix commit 075da133c0 is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent 366cd3fe4a

**History:**

- 2026-09-30 — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-09-30 — Fixed: commit 075da133c0
- 2026-09-30 — Verified: confirmed by user
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0210

**Game crashed raising the difficulty: notes kept the full chart's anchor**

| | |
|---|---|
| Detected | 2026-09-30 |
| Reported by | the maintainer (in game) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 57d167ef232ea3912a07fd3371c1adfba8b4ee48 |
| Severity | Critical |
| Priority | P1 |
| Status | Closed |

Each DD level rebuilds its anchors from its own notes, but every note kept the full chart's anchor fret/width; once a phrase dropped out a level could be framed differently (September's Alternate Rhythm: fret 2 from level 17, notes saying fret 1) and raising the difficulty in Riff Repeater crashed the game (0xc0000005).

**Steps to reproduce:** 

1. Open Daughtry 'September' (native PSARC) in Riff Repeater
2. Raise the difficulty

**Expected:** The difficulty rises.

**Observed:** Crash (0xc0000005) as soon as the difficulty was raised ('a dificuldade estava a zero e eu só tentei aumentar, e crashou logo').

**Root cause:** _build_sng_notes._find_anchor read the full chart's anchors; anchor first/last note times were carried from the unsplit window.

**Fixes:** [FIX-0210](../FIX_LOG.md#fix-0210) (0.10.0-beta.1)

**Verified:** docs/TESTES-NO-JOGO.md: '✅ Resolvido: crash no "September" (2026-09-30) ... Testado no jogo pelo utilizador e confirmado: perfeito'; CLAUDE.md: 'CONFIRMED IN GAME (2026-09-30) ... "Está perfeito"' (by the maintainer (in game))

**Resolved:** 2026-09-30 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Game crash.

**Evidence:**

- CLAUDE.md § SNG binary compilation (`infrastructure/packaging/psarc/sng.py`) — '**A note's anchor is the one of ITS level, not the full chart's.**'
- docs/TESTES-NO-JOGO.md — '✅ Resolvido: crash no "September" (2026-09-30)'
- commit 44f5338ae0 SNG: a note's anchor is its own level's, and no sliver END phrase
- found_in_version: the fix commit 44f5338ae0 is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent 57d167ef23

**History:**

- 2026-09-30 — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-09-30 — Fixed: commit 44f5338ae0
- 2026-09-30 — Verified: confirmed by user
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0211

**A 0.1 s note-less END phrase when the last note touched the last section**

| | |
|---|---|
| Detected | 2026-09-30 |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 57d167ef232ea3912a07fd3371c1adfba8b4ee48 |
| Severity | Low |
| Priority | P4 |
| Status | Fixed |

A last note ending 3 µs past the last section's start (float noise) pushed END 0.1 s later, leaving a 0.1 s note-less 'Outro' phrase.

**Steps to reproduce:** _pending_

**Expected:** END at the last section.

**Observed:** A 0.1 s sliver phrase.

**Root cause:** The end comparison had no tolerance for a note that only touches the last section.

**Fixes:** [FIX-0211](../FIX_LOG.md#fix-0211) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-09-30 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: No symptom of its own was traced to it.

**Evidence:**

- CLAUDE.md § SNG binary compilation (`infrastructure/packaging/psarc/sng.py`) — 'A last note that ends AT the last section's start ... counts as ending before it (`_END_TOUCH_S`, 50 ms)'
- docs/TESTES-NO-JOGO.md — '✅ Resolvido: crash no "September" (2026-09-30)'
- its regression test test_a_last_note_ending_at_the_last_sections_start_leaves_no_sliver_phrase (added in 44f5338) was removed in 33da4d3, when DLC Builder's phrase generator replaced that logic
- commit 44f5338ae0 SNG: a note's anchor is its own level's, and no sliver END phrase
- found_in_version: the fix commit 44f5338ae0 is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent 57d167ef23

**History:**

- 2026-09-30 — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-09-30 — Fixed: commit 44f5338ae0

## BUG-0212

**Game crashed raising the difficulty on a one-note phrase: ceiling 0**

| | |
|---|---|
| Detected | 2026-09-30 |
| Reported by | the maintainer (in game) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | fce9df565fcd1a5584e14ae0155e6a641d39f6be |
| Severity | Critical |
| Priority | P1 |
| Status | Closed |

The DD floor was bounded by busiest-1, so a one-note phrase got ceiling 0, a phrase with a note and no level; the game crashed there when the difficulty was raised (September's Lead one-note phrase at 43.6 s, the Alternate Rhythm's pickup).

**Steps to reproduce:** 

1. Open Daughtry 'September' (native PSARC) in Riff Repeater
2. Raise the difficulty over the one-note phrase

**Expected:** The difficulty rises.

**Observed:** Crash when raising the difficulty.

**Root cause:** _DD_MIN_LEVELS floor capped by the note count; DLC Builder gives every phrase with notes at least 3 levels.

**Fixes:** [FIX-0212](../FIX_LOG.md#fix-0212) (0.10.0-beta.1)

**Verified:** docs/TESTES-NO-JOGO.md: '✅ Resolvido: crash no "September" (2026-09-30) ... Testado no jogo pelo utilizador e confirmado: perfeito'; CLAUDE.md: 'CONFIRMED IN GAME (2026-09-30) ... "Está perfeito"' (by the maintainer (in game))

**Resolved:** 2026-09-30 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Game crash.

**Evidence:**

- CLAUDE.md § SNG binary compilation (`infrastructure/packaging/psarc/sng.py`) — '**A phrase with notes always has levels to climb.**'
- docs/TESTES-NO-JOGO.md — '✅ Resolvido: crash no "September" (2026-09-30)'
- commit 649ae72e99 SNG: every phrase with notes has levels, linked phrases are equal
- found_in_version: the fix commit 649ae72e99 is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent fce9df565f

**History:**

- 2026-09-30 — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-09-30 — Fixed: commit 649ae72e99
- 2026-09-30 — Verified: confirmed by user
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0213

**Passages differing by a technique or sustain were linked as one phrase**

| | |
|---|---|
| Detected | 2026-09-30 |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | fce9df565fcd1a5584e14ae0155e6a641d39f6be |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

_phrase_signature only knew time/string/fret, so September linked passages where one had a pull-off or let-ring sustain the other lacked: one phrase to the game with two different contents.

**Steps to reproduce:** _pending_

**Expected:** Only identical passages share a phrase.

**Observed:** Different passages linked into one phrase.

**Root cause:** The signature omitted sustain, techniques, slide and bend.

**Fixes:** [FIX-0213](../FIX_LOG.md#fix-0213) (0.10.0-beta.1)

**Verified:** docs/TESTES-NO-JOGO.md: '✅ Resolvido: crash no "September" (2026-09-30) ... Testado no jogo pelo utilizador e confirmado: perfeito'; CLAUDE.md: 'CONFIRMED IN GAME (2026-09-30) ... "Está perfeito"' (by the maintainer)

**Resolved:** 2026-09-30 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Corrupted phrase linking; found by byte-diff during the September crash.

**Evidence:**

- CLAUDE.md § SNG binary compilation (`infrastructure/packaging/psarc/sng.py`) — '**Linked phrases are equal.**'
- docs/TESTES-NO-JOGO.md — '✅ Resolvido: crash no "September" (2026-09-30)'
- commit 649ae72e99 SNG: every phrase with notes has levels, linked phrases are equal
- found_in_version: the fix commit 649ae72e99 is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent fce9df565f

**History:**

- 2026-09-30 — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-09-30 — Fixed: commit 649ae72e99
- 2026-09-30 — Verified: confirmed by user
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0214

**SNG note bytes wrote 0 instead of -1 for unused Tap/Slap/Pluck/LeftHand/PickDirection**

| | |
|---|---|
| Detected | 2026-09-30 |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | fce9df565fcd1a5584e14ae0155e6a641d39f6be |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

DLC Builder writes -1 in Tap/Slap/Pluck of every note and LeftHand/PickDirection of every chord; RockForge wrote 0, a real value for each.

**Steps to reproduce:** _pending_

**Expected:** -1 where a note does not use the field.

**Observed:** 0 in those fields.

**Root cause:** Those fields were unsigned with a 0 default.

**Fixes:** [FIX-0214](../FIX_LOG.md#fix-0214) (0.10.0-beta.1)

**Verified:** docs/TESTES-NO-JOGO.md: '✅ Resolvido: crash no "September" (2026-09-30) ... Testado no jogo pelo utilizador e confirmado: perfeito'; CLAUDE.md: 'CONFIRMED IN GAME (2026-09-30) ... "Está perfeito"' (by the maintainer)

**Resolved:** 2026-09-30 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: A divergence found during the September crash; its own effect is unproven.

**Evidence:**

- CLAUDE.md § SNG binary compilation (`infrastructure/packaging/psarc/sng.py`) — '**"None" is -1 in the note bytes.**'
- docs/TESTES-NO-JOGO.md — '✅ Resolvido: crash no "September" (2026-09-30)'
- commit 649ae72e99 SNG: every phrase with notes has levels, linked phrases are equal
- found_in_version: the fix commit 649ae72e99 is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent fce9df565f

**History:**

- 2026-09-30 — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-09-30 — Fixed: commit 649ae72e99
- 2026-09-30 — Verified: confirmed by user
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0216

**Daughtry 'September' still crashed: native phrases differed from DLC Builder's**

| | |
|---|---|
| Detected | 2026-09-30 |
| Reported by | the maintainer (in game) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 649ae72e9988cd9d283e1ffa6bfade611a52267a |
| Severity | Critical |
| Priority | P1 |
| Status | Closed |

After three earlier fixes the native build of September still crashed while DLC Builder's played. Native phrases were cut at every Guitar Pro section and every ~8 s, with raw names the game has no token for and boundaries inside sustained notes.

**Steps to reproduce:** 

1. Build Daughtry 'September' (native PSARC)
2. Play it and raise the difficulty in Riff Repeater

**Expected:** Every chart plays and the difficulty rises without a crash.

**Observed:** The game crashed.

**Root cause:** The phrase timeline did not follow DLC Builder's PhraseGenerator (COUNT to the first note, a phrase every 8 measures out of sustains/hand shapes, NOGUITAR over gaps, riff/noguitar names).

**Fixes:** [FIX-0216](../FIX_LOG.md#fix-0216) (0.10.0-beta.1)

**Verified:** docs/TESTES-NO-JOGO.md: '✅ Resolvido: crash no "September" (2026-09-30) ... Testado no jogo pelo utilizador e confirmado: perfeito'; CLAUDE.md: 'CONFIRMED IN GAME (2026-09-30) ... "Está perfeito"' (by the maintainer (in game))

**Resolved:** 2026-09-30 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Game crash.

**Evidence:**

- CLAUDE.md § SNG binary compilation (`infrastructure/packaging/psarc/sng.py`) — '**The phrases ARE DLC Builder's now (`_prepare_sections` = a port of `PhraseGenerator.generate`, Rocksmith2014.NET).**'
- docs/TESTES-NO-JOGO.md — '✅ Resolvido: crash no "September" (2026-09-30)'
- commit 33da4d3ca8 SNG: generate phrases exactly as DLC Builder does
- found_in_version: the fix commit 33da4d3ca8 is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent 649ae72e99

**History:**

- 2026-09-30 — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-09-30 — Fixed: commit 33da4d3ca8
- 2026-09-30 — Verified: confirmed by user
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0240

**Native chords showed no finger positions, unlike official songs**

| | |
|---|---|
| Detected | 2026-10-04 |
| Reported by | the maintainer (in game) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | adcb02bda95ab216d6a988ae8338ae7feb34d933 |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

Every chord template went out with fingers -1 and an empty name, and no hand shapes, so the game drew no finger positions on chords.

**Steps to reproduce:** _pending_

**Expected:** Chords show their fingers and name, as official songs do.

**Observed:** 'nas músicas originais do rocksmith, mostra a posição dos dedos e acho que nas nossas não mostra'.

**Root cause:** Templates carried no fingering or name and no fingerprints (hand shapes) were emitted.

**Fixes:** [FIX-0240](../FIX_LOG.md#fix-0240) (0.10.0-beta.1)

**Verified:** CLAUDE.md: '**The fingers SHOW in game (confirmed by the user, 2026-10-05)**' (by the maintainer (in game))

**Resolved:** 2026-10-04 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Missing chord information; playable.

**Evidence:**

- CLAUDE.md § SNG binary compilation (`infrastructure/packaging/psarc/sng.py`) — '**Chords carry fingers, a name and a hand shape — what makes the game draw the finger positions** (2026-10-04 ...)'
- commit 73d49d4c24 Chords carry fingers, a name and hand shapes, so the game shows finger positions
- found_in_version: the fix commit 73d49d4c24 is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent adcb02bda9

**History:**

- 2026-10-04 — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-10-04 — Fixed: commit 73d49d4c24
- 2026-10-04 — Verified: confirmed by user
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0241

**Manifest SongPartition was 1 on every chart, so a Lead and its alternate were both Lead 1**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 2a947fe8083f25a11ab88713a24bae084c922c35 |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

Every chart's manifest carried SongPartition 1, so a main chart and its alternate on the same path both claimed to be the first.

**Steps to reproduce:** _pending_

**Expected:** Main chart 1, alternate 2 (DLC Builder's Partitioner).

**Observed:** 1 on every chart.

**Root cause:** SongPartition was a constant.

**Fixes:** [FIX-0241](../FIX_LOG.md#fix-0241) (0.10.0-beta.1)

**Verified:** regression test(s) test_each_chart_carries_its_number_on_its_path, test_game_names_number_only_a_path_with_two_charts pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-10-05 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Wrong game metadata; in-game effect not observed.

**Evidence:**

- CLAUDE.md § Batch processing ('Every chart is named as Rocksmith names it')
- CLAUDE.md: 'it was 1 on every chart, so a Lead and its alternate both claimed to be the first Lead'
- commit 3f18d16c5c Name each chart as Rocksmith does (LEAD 1, LEAD 2, RHYTHM) and number it in the PSARC
- found_in_version: the fix commit is an ancestor of cb00653 (the first public release, 0.10.0 beta 1, 2026-10-14), so the faulty code only existed in development builds before 0.10.0-beta.1
- found_in_build: 2a947fe808 is the parent of the first fix commit 3f18d16c5c and still carries the code the fix changes

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-10-05 — Fixed: commit 3f18d16c5c
- 2026-10-05 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0242

**Hand shape LastNoteTime equal to its end after float32 rounding**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | d9a79781d73fcb135429af74281a4a4008848cc0 |
| Severity | Low |
| Priority | P4 |
| Status | Closed |

Found by the fuzz test: a last chord whose sustain ends exactly at the next note gave LastNoteTime == the shape's end once written as float32 (DLC Builder writes -1).

**Steps to reproduce:** _pending_

**Expected:** -1

**Observed:** Wrong LastNoteTime

**Root cause:** Float comparison.

**Fixes:** [FIX-0242](../FIX_LOG.md#fix-0242) (0.10.0-beta.1)

**Verified:** regression test(s) test_hand_shapes_hold_on_hundreds_of_random_charts pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-10-05 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Format edge case.

**Evidence:**

- commit 2a947fe808 Larger Letra page; hand shapes fuzzed; two small races fixed
- found_in_version: fix 2a947fe808 (2026-10-05) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent d9a79781d7, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-10-05 — Fixed: commit 2a947fe808
- 2026-10-05 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0250

**Docker image made no .psarc (the [psarc] extra was not installed)**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | _pending_ |
| Build / commit | cb00653bedba4cd2f9070ceb2acb8e925c883319 |
| Severity | High |
| Priority | P2 |
| Status | Fixed |

The Docker image installed only [postgres]/[ml,postgres], without the [psarc] extra, so the worker produced the bundle but never the .psarc.

**Steps to reproduce:** 

1. docker compose up
2. Build a project

**Expected:** The job produces a .psarc as well as the bundle.

**Observed:** The worker made no .psarc.

**Root cause:** docker/Dockerfile ran pip install ".[postgres]" / ".[ml,postgres]" without psarc.

**Fixes:** [FIX-0250](../FIX_LOG.md#fix-0250) (0.10.0-beta.2)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-10-14 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: The game-ready output was missing in Docker deployments; other installs unaffected.

**Evidence:**

- CHANGELOG.en.md 0.10.0 beta 2 — Security: "Docker: the image now makes the .psarc (the [psarc] extra was missing)."
- commit 994c9307ac: "Docker installs [psarc] (the worker made no .psarc), .dockerignore."
- found_in_build: cb00653 docker/Dockerfile lines 13/19 install .[postgres] and .[ml,postgres]
- found_in_version pending: faulty code present at cb00653 (beta 1); detection date not documented

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-10-14 — Fixed: commit 994c9307ac

## BUG-0257

**The detected tuning deviation (cents) never reached the .psarc**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | _pending_ |
| Build / commit | cb00653bedba4cd2f9070ceb2acb8e925c883319 |
| Severity | Medium |
| Priority | P2 |
| Status | Closed |

"Detetar afinação" measured how many cents the recording is off A440, but the worker passed only tuning_overrides to the build, so every chart shipped CentOffset 0.

**Steps to reproduce:** 

1. Run "Detetar afinação" on a recording that is off A440
2. Rebuild and inspect the XML/manifest

**Expected:** CentOffset carries the measured deviation.

**Observed:** CentOffset was always 0.

**Root cause:** Nothing read the measured cent offset: the worker built only from tuning_overrides.

**Fixes:** [FIX-0257](../FIX_LOG.md#fix-0257) (0.10.0-beta.2)

**Verified:** regression test(s) test_the_recordings_cent_offset_reaches_every_chart, test_a_cent_offset_past_half_a_semitone_is_refused pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-10-14 · **Closed:** 2026-10-15

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: An off-pitch recording shipped with the wrong reference in game, with no way to set it.

**Evidence:**

- CLAUDE.md § `Tuning` validates its own pitches (and the API range-checks them): "The recording's cent offset is one job-level value that reaches every chart"
- CHANGELOG.en.md 0.10.0 beta 2 — Fixed: "The tuning deviation reaches the game. ..."
- commit 8123d67a9f Make the recording's cent offset reach the build; drop the dead MIDI tuning inputs
- found_in_build: cb00653 interfaces/worker/celery_app.py has no cent_offset
- found_in_version pending: faulty code present at cb00653 (beta 1); detection date not documented

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-10-14 — Fixed: commit 8123d67a9f
- 2026-10-14 — Verified: automated
- 2026-10-15 — Closed: released in 0.10.0-beta.2

## BUG-0270

**A difficulty level holding only open strings had no anchor in the .psarc**

| | |
|---|---|
| Detected | 2026-10-15 |
| Reported by | found during development |
| Found in | _pending_ |
| Build / commit | bebcf2b5d6e7d074829b4c01106ada00a7fcdb97 |
| Severity | High |
| Priority | P2 |
| Status | Closed |

_level_positions dropped open-string notes before _build_anchors, so a DD level made only of open strings (a bass line's roots at its lowest levels) shipped with no anchor at all.

**Steps to reproduce:** _pending_

**Expected:** Every level with notes has an anchor.

**Observed:** The PSARC check found a level with notes and no anchor.

**Root cause:** Open notes never reached _build_anchors, whose one-window fallback for that case therefore never ran.

**Fixes:** [FIX-0270](../FIX_LOG.md#fix-0270) (0.10.0-beta.5)

**Verified:** regression test(s) test_a_level_of_only_open_strings_still_has_an_anchor pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-10-15 · **Closed:** 2026-10-15

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: A level with notes and no anchor, a shape tied to game crashes before.

**Evidence:**

- CLAUDE.md § The Bass arrangement (`ArrangementKind.BASS`): "Found on the way, not bass-only: a DD level holding only OPEN strings ... shipped with no anchor at all"
- CHANGELOG.en.md 0.10.0 beta 5 — Fixed: "A difficulty level holding only open strings had no anchor ..."
- commit 8b6fb41004 Add the Bass arrangement: "Found on the way: a DD level holding only open strings shipped with no anchor"
- detected 2026-10-15: found during the bass work requested 2026-10-15 ('Implementa a faixa de bass') and fixed the same day
- found_in_version pending: faulty code present at bebcf2b (beta 3); found in development

**History:**

- 2026-10-15 — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-10-15 — Fixed: commit 8b6fb41004
- 2026-10-15 — Verified: automated
- 2026-10-15 — Closed: released in 0.10.0-beta.5

## BUG-0271

**Without Wwise, the .psarc carried the whole WAV (~30 MB) where the game never reads it**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | user report (r/rocksmith) |
| Found in | _pending_ |
| Build / commit | 25a67fbe730581db2109dc0d2d0eb3f3f5b687ea |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

With no Wwise, the packer put the WAV under audio/<key>.<ext>, a path the game never loads, so the .psarc was ~30 MB per 3 minutes and still silent.

**Steps to reproduce:** 

1. Build a project on a machine without Wwise

**Expected:** A .psarc without audio and a clear note that Wwise is missing.

**Observed:** A ~30 MB .psarc that still played silence.

**Root cause:** NativePsarcPacker's no-Wwise fallback packed the raw WAV.

**Fixes:** [FIX-0271](../FIX_LOG.md#fix-0271) (0.10.0-beta.5)

**Verified:** regression test(s) test_package_produces_valid_psarc pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-10-15 · **Closed:** 2026-10-15

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Wasted size and a misleading file; it was silent either way.

**Evidence:**

- CLAUDE.md § Wwise SoundBank (`infrastructure/packaging/psarc/soundbank.py`): "When no Wwise is available the .psarc carries no audio at all (2026-10-15) ... (a user's report on r/rocksmith)"
- CHANGELOG.en.md 0.10.0 beta 5 — Fixed: "Without Wwise, the .psarc carried the whole WAV ..."
- commit 13a2c42b65 Fix the first public reports: downloads in the .exe, the capo, a 30 MB .psarc
- detected pending: the report itself is not dated
- found_in_version pending: faulty code present at 25a67fb (beta 2) and bebcf2b (beta 3)

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-10-15 — Fixed: commit 13a2c42b65
- 2026-10-15 — Verified: automated
- 2026-10-15 — Closed: released in 0.10.0-beta.5

## BUG-0275

**Wwise installed but reported as "ROCKFORGE_WWISE_ROOT is not set"**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | _pending_ |
| Build / commit | 8494322e3f34a7427e9ed710687f2001493e9bb4 |
| Severity | High |
| Priority | P2 |
| Status | Closed |

Detection looked only at the env vars and the Launcher's default folder; a Wwise installed elsewhere (I:\Rocksmith\Wwise_2025.1.11.9262) or of an unsupported version (2024/2025) read "ROCKFORGE_WWISE_ROOT is not set", and a hand-set 2024/2025 folder showed green until the build failed for want of a template.

**Steps to reproduce:** 

1. Install Wwise 2025 with the Launcher on another drive
2. Open Settings → Software

**Expected:** The row names the Wwise found and why it cannot be used.

**Observed:** "ROCKFORGE_WWISE_ROOT is not set".

**Root cause:** Detection did not scan other drives or read the registry's WWISEROOT, and did not check the version in a folder's name.

**Fixes:** [FIX-0275](../FIX_LOG.md#fix-0275) (0.10.0-beta.7)

**Verified:** regression test(s) test_a_wwise_that_cannot_be_used_is_named_not_reported_as_unset, test_wwise_is_found_in_a_folder_of_the_users_choosing pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-10-15 · **Closed:** 2026-10-16

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: No playable .psarc and a message pointing the wrong way; setting the folder was a workaround.

**Evidence:**

- CLAUDE.md § The `.exe` installs its own extra components (`infrastructure/components.py`): "When none is usable the Wwise row says what IS there ('tenho o wwise instalado mas não está a ser detetado' ...)"
- user quote (undated): 'tenho o wwise instalado mas não está a ser detetado'
- CHANGELOG.en.md 0.10.0 beta 7 — Fixed: "Wwise installed but \"not detected\" ..."
- commit 2a780cb79a Say which Wwise was found when none is usable, and look further for it
- commit 416918f6a3 Find Wwise wherever it was installed, and refuse a 2024/2025 folder up front
- found_in_version pending: faulty code present at 8494322 (beta 6); the version used and the date are not stated

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-10-15 — Fixed: commit 2a780cb79a, 416918f6a3
- 2026-10-15 — Verified: automated
- 2026-10-16 — Closed: released in 0.10.0-beta.7

## BUG-0292

**WWISEROOT pointing at another Wwise version hid a usable 2023.1 ("Wwise not installed")**

| | |
|---|---|
| Detected | 2026-10-17 |
| Reported by | user report |
| Found in | _pending_ |
| Build / commit | b0e2145cf6c8231ae18f144f8913e9478342d268 |
| Severity | High |
| Priority | P2 |
| Status | Closed |

The Launcher's WWISEROOT points at the version it set up last (often 2024/2025) and was taken as final, so a 2023.1 installed beside it was never looked for and the user was told Wwise was missing.

**Steps to reproduce:** 

1. Install Wwise 2023.1 and 2024/2025 with the Launcher
2. Build a project

**Expected:** The usable 2023.1 is found.

**Observed:** "It keeps saying that I don't have WWise installed when I do"

**Root cause:** runtime_settings.wwise_root returned WWISEROOT without checking it was usable.

**Fixes:** [FIX-0292](../FIX_LOG.md#fix-0292) (0.10.0-beta.13)

**Verified:** regression test(s) test_the_launchers_wwiseroot_on_another_version_does_not_hide_a_2023 pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-10-17 · **Closed:** 2026-10-17

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: No playable .psarc; setting the folder in Settings was a workaround.

**Evidence:**

- CLAUDE.md § The `.exe` installs its own extra components (`infrastructure/components.py`): "WWISEROOT is not final, and a failed conversion is not 'no Wwise' ..."
- user quote (2026-10-17): 'It keeps saying that I don't have WWise installed when I do'
- CHANGELOG.en.md Unreleased — Fixed: "\"Wwise not installed\" with Wwise installed ..."
- commit e234c859fe Wwise: WWISEROOT is not final, and a failed conversion says why
- found_in_version pending: faulty code present at 8b5b49a (beta 11) and b0e2145 (beta 12); which was in use is not stated
- CLAUDE.md: 'The user's machine was not seen, so which of the two hit them is their Definições → Software row to tell.'

**History:**

- 2026-10-17 — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-10-17 — Fixed: commit e234c859fe
- 2026-10-17 — Verified: automated
- 2026-10-17 — Closed: released in 0.10.0-beta.13

## BUG-0293

**A failed Wwise conversion read "no Wwise found" and the silent .psarc showed as playable**

| | |
|---|---|
| Detected | 2026-10-17 |
| Reported by | user report |
| Found in | _pending_ |
| Build / commit | b0e2145cf6c8231ae18f144f8913e9478342d268 |
| Severity | Medium |
| Priority | P2 |
| Status | Closed |

NativePsarcPacker swallowed a failed convert into a log while gp_pipeline warned "no local Wwise installation found", and "Antes de usar" showed "PSARC jogável gerado" for a .psarc built without a .wem (silent in game).

**Steps to reproduce:** 

1. Build with a Wwise whose conversion fails
2. Open Exportar → Antes de usar

**Expected:** Wwise's own error and "PSARC sem som".

**Observed:** "no local Wwise installation found" and "PSARC jogável gerado".

**Root cause:** The conversion error was not propagated (no PackagingResult.wem_error) and the checklist keyed on the .psarc existing.

**Fixes:** [FIX-0293](../FIX_LOG.md#fix-0293) (0.10.0-beta.13)

**Verified:** regression test(s) test_bundle_survives_wwise_failure, test_a_psarc_built_without_sound_says_so_and_why pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-10-17 · **Closed:** 2026-10-17

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Misleading diagnosis and a silent file reported as playable.

**Evidence:**

- CLAUDE.md § The `.exe` installs its own extra components (`infrastructure/components.py`): "NativePsarcPacker used to swallow a failed convert into a log ..."
- CHANGELOG.en.md Unreleased — Fixed: "... A Wwise conversion that fails no longer says \"Wwise not found\" either ... And a .psarc without sound no longer shows as \"Playable PSARC\""
- commit e234c859fe Wwise: WWISEROOT is not final, and a failed conversion says why
- found_in_build: b0e2145 application/ports.py has no wem_error
- found_in_version pending: which version the reporter ran is not stated

**History:**

- 2026-10-17 — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-10-17 — Fixed: commit e234c859fe
- 2026-10-17 — Verified: automated
- 2026-10-17 — Closed: released in 0.10.0-beta.13

## BUG-0300

**A title or artist with an accent left the project without a .psarc**

| | |
|---|---|
| Detected | 2026-10-18 |
| Reported by | code review (Claude, on the maintainer's request) |
| Found in | 0.11.0-beta.2 |
| Build / commit | f64c45e8e176c44bd87c7c7866f741330b443011 |
| Severity | High |
| Priority | P1 |
| Status | Verified |

The song key kept non-ASCII letters (Canção, Beyoncé); with Wwise installed the SoundBank's ASCII STID chunk raised UnicodeEncodeError and the build produced only the bundle.

**Steps to reproduce:** 

1. Create a project titled "Canção" on a machine with Wwise
2. Build it

**Expected:** A .psarc is produced.

**Observed:** generate_soundbank raised UnicodeEncodeError for 'SigurRósCanção'.

**Root cause:** song_key_from_title kept every str.isalnum() character, including non-ASCII letters.

**Fixes:** [FIX-0300](../FIX_LOG.md#fix-0300) (0.11.0-beta.3)

**Verified:** tests/test_psarc_manifest.py::test_a_song_key_is_ascii_even_for_an_accented_title passed, and fails with the fix reverted (by pytest (the test fails on the old code))

**Resolved:** 2026-10-18 · **Closed:** _pending_

**Evidence:**

- code review of the whole codebase (six reviewers), confirmed by reading the code

**History:**

- 2026-10-18 — Open: reported
- 2026-10-18 — Fixed: commit f907982d0f
- 2026-10-18 — Verified: its test passes and fails on the old code

## BUG-0305

**"Check PSARC" reported a fault for every slap, pop or tap**

| | |
|---|---|
| Detected | 2026-10-18 |
| Reported by | code review (Claude, on the maintainer's request) |
| Found in | 0.11.0-beta.2 |
| Build / commit | f64c45e8e176c44bd87c7c7866f741330b443011 |
| Severity | Medium |
| Priority | P2 |
| Status | Verified |

The note_unused_byte rule wanted tap/slap/pluck all -1, but the builder writes 1 for a note that uses the technique.

**Steps to reproduce:** 

1. Build a chart with a slapped note
2. Look at Check PSARC

**Expected:** No fault.

**Observed:** note_unused_byte for a valid file.

**Root cause:** The rule did not allow the value the builder writes.

**Fixes:** [FIX-0305](../FIX_LOG.md#fix-0305) (0.11.0-beta.3)

**Verified:** tests/test_psarc_verify.py::test_each_rule_catches_the_fault_that_crashed_the_game passed, and fails with the fix reverted (by pytest (the test fails on the old code))

**Resolved:** 2026-10-18 · **Closed:** _pending_

**Evidence:**

- code review of the whole codebase (six reviewers), confirmed by reading the code

**History:**

- 2026-10-18 — Open: reported
- 2026-10-18 — Fixed: commit f907982d0f
- 2026-10-18 — Verified: its test passes and fails on the old code

## BUG-0329

**WwiseConsole inherited the console's stdin**

| | |
|---|---|
| Detected | 2026-10-18 |
| Reported by | code review (Claude, on the maintainer's request) |
| Found in | 0.11.0-beta.2 |
| Build / commit | f64c45e8e176c44bd87c7c7866f741330b443011 |
| Severity | Low |
| Priority | P3 |
| Status | Verified |

The hard rule for console tools was not applied to WwiseConsole.

**Steps to reproduce:** 

1. See the description (found by reading the code)

**Expected:** As described in the solution.

**Observed:** The hard rule for console tools was not applied to WwiseConsole.

**Root cause:** stdin not set.

**Fixes:** [FIX-0329](../FIX_LOG.md#fix-0329) (0.11.0-beta.4)

**Verified:** tests/test_ffmpeg_normalizer.py::test_external_tools_output_is_read_as_utf8_on_every_system passed, and fails with the fix reverted (by pytest (the test fails on the old code))

**Resolved:** 2026-10-18 · **Closed:** _pending_

**Evidence:**

- code review of the whole codebase (six reviewers), confirmed by reading the code

**History:**

- 2026-10-18 — Open: reported
- 2026-10-18 — Fixed: commit 76c44a8bcd
- 2026-10-18 — Verified: its test passes and fails on the old code

## BUG-0337

**Two songs whose names share the first 30 letters get the same song key**

| | |
|---|---|
| Detected | 2026-10-18 |
| Reported by | code review (Claude, on the maintainer's request) |
| Found in | 0.11.0-beta.2 |
| Build / commit | f64c45e8e176c44bd87c7c7866f741330b443011 |
| Severity | Low |
| Priority | P4 |
| Status | Deferred |

song_key_from_title keeps the first 30 letters of artist+title, so two live versions of one song ("... (Live 1992)" / "(Live 2013)") get the same key: the same PersistentIDs and the same .psarc name, one replacing the other in game.

**Steps to reproduce:** 

1. Build two songs whose artist+title share the first 30 letters

**Expected:** Two songs in game.

**Observed:** Same key (code reading).

**Root cause:** A plain 30-character cut.

**Fixes:** —

**Verified:** _pending_ (by _pending_)

**Resolved:** _pending_ · **Closed:** _pending_

**Note:** Not changed on purpose: a key with a hash for long names would give EVERY long-titled song a new key, and with it new persistent IDs — the player's progress on those songs would start over. Two songs sharing 30 letters is rare; to be decided with the maintainer before changing it.

**Evidence:**

- code review of the whole codebase, confirmed by reading the code

**History:**

- 2026-10-18 — Open: reported
- 2026-10-18 — Deferred: changing every long key would reset progress; decide first
