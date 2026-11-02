<!-- Generated from tracking/bugs.json by `python -m tools.tracking render`. Do not edit by hand: edit the JSON and render again. -->

# Bugs: tones

Tones: editor, detection, suggestions, presets. Index: [BUG_LOG.md](../BUG_LOG.md).

## BUG-0024

**'+ Criar / editar tons' did nothing (tone builder had no JavaScript)**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | pending (not recorded) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 5f448255319f13f262a5df0d1ca6b46efd882288 |
| Severity | Medium |
| Priority | P3 |
| Status | Fixed |

The tone builder HTML existed but no JavaScript was attached, so the button did nothing and its ⓘ was empty.

**Steps to reproduce:** _pending_

**Expected:** Tone builder opens

**Observed:** Button with no effect

**Root cause:** UI wiring never implemented.

**Fixes:** [FIX-0024](../FIX_LOG.md#fix-0024) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-06-17 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Tones could not be created in the app.

**Evidence:**

- commit 23fea9bb05 Wire up the tone builder UI (gear, base/extra, changes) + tones info
- found_in_version: fix 23fea9bb05 (2026-06-17) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 5f44825531, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-06-17 — Fixed: commit 23fea9bb05

## BUG-0046

**Tone detection's flatness feature always contributed zero**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 714289af84055d54e2c7afafb42c7401ba6f5368 |
| Severity | Low |
| Priority | P4 |
| Status | Fixed |

A real log showed flatness normalised = 0.00: guitar flatness (~0.002-0.03) was normalised against base 0.01/range 0.12, wasting 22-34% of the gain weight.

**Steps to reproduce:** _pending_

**Expected:** Feature contributes

**Observed:** flatness 0.00 in the log

**Root cause:** Linear normalisation range wrong.

**Fixes:** [FIX-0046](../FIX_LOG.md#fix-0046) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-07-03 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Heuristic accuracy.

**Evidence:**

- commit 15f9965a92 Corrigir a feature de flatness (contribuía sempre zero) na deteção de tom
- found_in_version: fix 15f9965a92 (2026-07-03) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 714289af84, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-03 — Fixed: commit 15f9965a92

## BUG-0052

**'Voz simples (sem tom)' preview still coloured by the cabinet EQ**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 39b8552b39e58a43fabf9e28edafd09f0d0b8983 |
| Severity | Low |
| Priority | P4 |
| Status | Fixed |

The plain voice still routed through the guitar-cabinet EQ.

**Steps to reproduce:** _pending_

**Expected:** Dry tick

**Observed:** Coloured plain voice

**Root cause:** Plain voice not bypassing the cabinet.

**Fixes:** [FIX-0052](../FIX_LOG.md#fix-0052) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-07-06 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Cosmetic.

**Evidence:**

- commit 8e007ce7ed Tone preview: "Voz simples" is a dry note tick (bypass the cabinet)
- found_in_version: fix 8e007ce7ed (2026-07-06) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 39b8552b39, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-06 — Fixed: commit 8e007ce7ed

## BUG-0053

**Clearing all tones or tone changes did not persist after rebuild**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | a123576b6f247089088236bc377d64ab8d63f180 |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

The editor sent null for empty tone fields and the rebuild treats null as 'keep', so cleared tones survived.

**Steps to reproduce:** _pending_

**Expected:** Cleared tones stay cleared

**Observed:** Removed tones come back

**Root cause:** null sentinel used for an intentional empty value.

**Fixes:** [FIX-0053](../FIX_LOG.md#fix-0053) (0.10.0-beta.1)

**Verified:** regression test(s) test_rebuild_empty_tone_fields_clear_them pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-07-06 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Edits silently undone.

**Evidence:**

- commit d73f0704d5 Fix: clearing tones/changes on the score now persists
- found_in_version: fix d73f0704d5 (2026-07-06) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent a123576b6f, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-06 — Fixed: commit d73f0704d5
- 2026-07-06 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0096

**Native PSARC played a default tone despite the user's custom tones**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer (in game) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | d2e81991a87e2f6cae5583a2ce8087f048947f8f |
| Severity | High |
| Priority | P2 |
| Status | Closed |

Every arrangement manifest left Tone_Base/Tones empty, so the game used a default tone even with a full gear chain built in the editor.

**Steps to reproduce:** _pending_

**Expected:** User's tone in game

**Observed:** Default tone in game

**Root cause:** Tones not serialized into the native manifest.

**Fixes:** [FIX-0096](../FIX_LOG.md#fix-0096) (0.10.0-beta.1)

**Verified:** regression test(s) test_manifest_serializes_custom_tones_into_gearlist pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-07-10 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Tone work lost on the native path.

**Evidence:**

- commit da8d9de131 Serialize custom tones into the native-PSARC manifest
- found_in_version: fix da8d9de131 (2026-07-10) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent d2e81991a8, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-10 — Fixed: commit da8d9de131
- 2026-07-10 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0159

**Tone detection read almost every song as clean**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 8d4bb72ca5e450016197cfb2ecf7f2255f91b08a |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

The gain estimate systematically under-read: averaged over the whole song (silences and clean breaks pulled it to clean) and based on ZCR + centroid, both dominated by brightness, so a dark, low-tuned or palm-muted high-gain tone read low.

**Steps to reproduce:** _pending_

**Expected:** High-gain tones detected as high gain.

**Observed:** Detection 'muito básico e normalmente muito baixo' — usually clean.

**Root cause:** Brightness-dominated features averaged over every frame.

**Fixes:** [FIX-0159](../FIX_LOG.md#fix-0159) (0.10.0-beta.1)

**Verified:** regression test(s) test_high_gain_boundary_is_half, test_tone_profile_carries_distortion_cues, test_a_dark_low_tuned_high_gain_tone_is_not_read_as_clean, test_gain_estimate_separates_clean_from_high_gain pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-08-24 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Wrong tone suggestions; tones can be picked by hand.

**Evidence:**

- CLAUDE.md § Automatic tone detection (`/jobs/{id}/detect-tones`) — '**Gain estimation (why it stopped reading "usually too clean").**'
- commit 714289af84 Melhorar a deteção de gain do tom (deixa de ler "quase sempre clean")
- commit 5bd8c60e6b Make the gain heuristic testable, fix the atomic writes, drop dead code
- found_in_version: the fix commit 714289af84 is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent 8d4bb72ca5

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-08-24 — Fixed: commit 714289af84, 5bd8c60e6b
- 2026-08-24 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0218

**A chart with no tone of its own shipped an empty Tones array**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 03eb8aa3526e60663a3a026729682ec8af8686d5 |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

A chart with no tone of its own went out with an empty Tones array and a blank Tone_Base, so the game fell back to whatever it plays for an unresolved tone.

**Steps to reproduce:** _pending_

**Expected:** DLC Builder's default tone for the chart's path.

**Observed:** An odd/missing tone ('mesmo sem os tons … não têm uma tonalidade limpa').

**Root cause:** _tone_fields did not add DLC Builder's default tones (addDefaultTonesIfNeeded).

**Fixes:** [FIX-0218](../FIX_LOG.md#fix-0218) (0.10.0-beta.1)

**Verified:** regression test(s) test_the_default_tone_is_dlc_builders_own_for_the_path, test_the_default_tone_takes_the_charts_base_tone_name pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-09-30 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Wrong sound on tone-less songs; workaround: create tones.

**Evidence:**

- CLAUDE.md § Dual output: Bundle + PSARC always — '**A chart with no tone of its own gets DLC Builder's default tone, not nothing**'
- commit cad648e4a4 Cleaner PSARC audio and tones: linear gain, default tones, SNG tone changes
- found_in_version: the fix commit cad648e4a4 is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent 03eb8aa352

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-09-30 — Fixed: commit cad648e4a4
- 2026-09-30 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0219

**Mid-song tone changes never happened in the native PSARC**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 03eb8aa3526e60663a3a026729682ec8af8686d5 |
| Severity | High |
| Priority | P2 |
| Status | Closed |

The SNG's Tones section was written empty, so from the native PSARC a chart played its base tone throughout whatever was marked on the score ('problemas graves com os tons').

**Steps to reproduce:** 

1. Mark a tone change to a second tone on the score
2. Rebuild and play the native PSARC

**Expected:** The tone switches at that point.

**Observed:** The base tone played throughout.

**Root cause:** _build_tones did not exist: the Tones section was empty.

**Fixes:** [FIX-0219](../FIX_LOG.md#fix-0219) (0.10.0-beta.1)

**Verified:** CLAUDE.md § Tone volume: 'Heard in game, then tuned again (2026-10-01: "realmente está a fazer as trocas de tons ...")' — 'The tone changes are confirmed working in game.' (by the maintainer)

**Resolved:** 2026-09-30 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Tone changes, a core tone feature, did nothing in game.

**Evidence:**

- CLAUDE.md § Dual output: Bundle + PSARC always — '**Mid-song tone changes now reach the game** (`sng._build_tones`).'
- tasks/todo.md — 'Trocas de tom no SNG nativo (a secção Tones ia vazia: nenhuma troca acontecia no jogo)'
- commit cad648e4a4 Cleaner PSARC audio and tones: linear gain, default tones, SNG tone changes
- found_in_version: the fix commit cad648e4a4 is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent 03eb8aa352

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-09-30 — Fixed: commit cad648e4a4
- 2026-09-30 — Verified: confirmed by user
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0220

**Tone presets nearly inaudible in game: volumes on the wrong side of the scale**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 581429e52d3f574967f7b61418f1ac65097979f4 |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

A tone's Volume is a level in dB where more negative is louder; the curated presets shipped at -13..-16, quieter than every reference, and the new-tone default was -15, so detected and applied tones could hardly be heard.

**Steps to reproduce:** _pending_

**Expected:** Tones as loud as the game's own (about -18/-19.5).

**Observed:** Tones very quiet in game ('os tons detetados e aplicados estão a ficar com o som muito baixo, e quase não se ouvem no rocksmith').

**Root cause:** The preset volumes and the editor's field treated a less negative Volume as louder.

**Fixes:** [FIX-0220](../FIX_LOG.md#fix-0220) (0.10.0-beta.1)

**Verified:** regression test(s) test_presets_are_as_loud_as_the_games_own_tones, test_presets_still_at_their_first_quiet_volume_are_raised_on_startup pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-09-30 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Tones barely audible; editable by hand.

**Evidence:**

- CLAUDE.md § Tone volume: MORE NEGATIVE IS LOUDER
- commit e814045b31 Louder tones, a main chart for sync, and dropping the previous version
- found_in_version: the fix commit e814045b31 is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent 581429e52d

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-09-30 — Fixed: commit e814045b31
- 2026-09-30 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0221

**Plexi presets set a knob the amp does not have, so the setting was dropped**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 581429e52d3f574967f7b61418f1ac65097979f4 |
| Severity | Low |
| Priority | P4 |
| Status | Closed |

The two Plexi presets set Amp_MarshallPlexi_Gain, which that amp does not have (it has Loudness1/2); tone_from_dict drops an unknown knob silently, so the setting never reached the tone.

**Steps to reproduce:** _pending_

**Expected:** Every preset knob reaches the tone.

**Observed:** The gain setting was silently dropped.

**Root cause:** A knob name not in the gear catalogue for that amp.

**Fixes:** [FIX-0221](../FIX_LOG.md#fix-0221) (0.10.0-beta.1)

**Verified:** regression test(s) test_every_preset_knob_is_a_real_knob_of_its_gear pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-09-30 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: A preset sounded different from its definition.

**Evidence:**

- CLAUDE.md § Tone volume: MORE NEGATIVE IS LOUDER — 'Also found on the way: the two Plexi presets set `Amp_MarshallPlexi_Gain`, which that amp does not have'
- commit e814045b31 Louder tones, a main chart for sync, and dropping the previous version
- found_in_version: the fix commit e814045b31 is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent 581429e52d

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-09-30 — Fixed: commit e814045b31
- 2026-09-30 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0232

**Driven tone presets left a hiss at the end of notes**

| | |
|---|---|
| Detected | 2026-10-01 |
| Reported by | the maintainer (in game) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | bcc933a69107c9e855e02a1598108f8cc690f416 |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

Crunch and high-gain presets amplified the guitar's own hum and string noise between notes, leaving a hiss under the end of each note and after the last one.

**Steps to reproduce:** _pending_

**Expected:** No noise when the guitar is not playing.

**Observed:** Noise at the end of notes ('os detetados ainda ficam com um pouco de ruído no final').

**Root cause:** No noise gate in front of the drive.

**Fixes:** [FIX-0232](../FIX_LOG.md#fix-0232) (0.10.0-beta.1)

**Verified:** regression test(s) test_every_preset_with_drive_opens_with_a_noise_gate, test_a_projects_untouched_preset_gets_the_gate_but_a_rebuilt_chain_does_not pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-10-01 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Noisy tones; editable by hand.

**Evidence:**

- CLAUDE.md § Tone volume: MORE NEGATIVE IS LOUDER — '**Every preset with drive opens with a noise gate** (2026-10-01 ...)'
- commit 96e9bb75ab Open every driven tone preset with a noise gate
- found_in_version: the fix commit 96e9bb75ab is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent bcc933a691

**History:**

- 2026-10-01 — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-10-01 — Fixed: commit 96e9bb75ab
- 2026-10-01 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0233

**Orange crunch preset noisy on Daughtry 'September'**

| | |
|---|---|
| Detected | 2026-10-01 |
| Reported by | the maintainer (in game) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 729acffc79d6c4ad30a03db39c25b62e81a625a1 |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

Decoding the user's two PSARCs showed September's Rhythm/Combo/alternates on RFRhythm_Orange, a Rockerverb at gain 68 with bass 74 and only the gentle crunch gate: noisy ('com ruído').

**Steps to reproduce:** _pending_

**Expected:** A clean-sounding crunch.

**Observed:** Noise on September's rhythm charts.

**Root cause:** The Orange preset was a hot amp setting with the gentler gate.

**Fixes:** [FIX-0233](../FIX_LOG.md#fix-0233) (0.10.0-beta.1)

**Verified:** regression test(s) test_a_copy_still_on_an_earlier_version_of_a_preset_gets_the_current_chain pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-10-01 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Noisy tone; editable by hand.

**Evidence:**

- CLAUDE.md § Tone volume: MORE NEGATIVE IS LOUDER — '**The Orange crunch was retuned, and earlier preset chains are upgraded** (2026-10-01, two PSARCs from the user: September "com ruído" ...)'
- commit 0d506f9ee5 Retune the Orange crunch preset and upgrade copies on its earlier chains
- found_in_version: the fix commit 0d506f9ee5 is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent 729acffc79

**History:**

- 2026-10-01 — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-10-01 — Fixed: commit 0d506f9ee5
- 2026-10-01 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0234

**Crunch preset too quiet and still too distorted; Overdrive slightly quiet**

| | |
|---|---|
| Detected | 2026-10-01 |
| Reported by | the maintainer (in game) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 0d506f9ee5a5499ac835221564d34807dc3e0f9b |
| Severity | Low |
| Priority | P4 |
| Status | Closed |

Heard in game: the 'Crunch encorpado' (Orange) tone was too quiet and still noisy with too much distortion, and the Overdrive a little quiet.

**Steps to reproduce:** _pending_

**Expected:** Balanced crunch and overdrive volume and gain.

**Observed:** 'O tom de crunch encorpado está muito baixo, e mesmo assim está com ruído (distorção em demasia). O overdrive está só um pouco baixo'.

**Root cause:** Preset gain and volume values.

**Fixes:** [FIX-0234](../FIX_LOG.md#fix-0234) (0.10.0-beta.1)

**Verified:** regression test(s) test_presets_still_at_their_first_quiet_volume_are_raised_on_startup, test_a_copy_still_on_an_earlier_version_of_a_preset_gets_the_current_chain pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-10-01 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Tone balance; editable in the tone editor.

**Evidence:**

- CLAUDE.md § Tone volume: MORE NEGATIVE IS LOUDER — '**Heard in game, then tuned again** (2026-10-01 ...)'
- commit 1c511fd97e Crunch encorpado louder with less gain, Overdrive a little louder
- found_in_version: the fix commit 1c511fd97e is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent 0d506f9ee5

**History:**

- 2026-10-01 — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-10-01 — Fixed: commit 1c511fd97e
- 2026-10-01 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0239

**Tone presets still hissed and did not sound clean next to hand-made tones**

| | |
|---|---|
| Detected | 2026-10-04 |
| Reported by | the maintainer (in game) |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 8b9cfbc12b085ae581ee73911c721c06a45b6542 |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

The driven presets still hissed and none sounded as clean as originals or community tones; a knob a preset left out took the hot catalogue default (the Plexis' Loudness2 at 88, the EQ5 +10 dB at 750 Hz).

**Steps to reproduce:** _pending_

**Expected:** Clean, low-noise tones comparable to community CDLC.

**Observed:** 'o problema continua a ser o hiss ou ruído. E os sons não são tão limpos'.

**Root cause:** No EQ cutting the rumble/hiss band before the amp, drive pedals stacked into amps near full gain, and omitted knobs taking catalogue defaults.

**Fixes:** [FIX-0239](../FIX_LOG.md#fix-0239) (0.10.0-beta.1)

**Verified:** regression test(s) test_driven_presets_cut_the_hiss_band_before_the_amp_and_stack_no_drive, test_a_copy_still_on_an_earlier_version_of_a_preset_gets_the_current_chain pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-10-04 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Tone quality; editable by hand.

**Evidence:**

- CLAUDE.md § Tone volume: MORE NEGATIVE IS LOUDER — '**Rebuilt on two hand-made tones that sound clean** (2026-10-04 ...)'
- commit adcb02bda9 Rebuild the tone presets on two hand-made tones that sound clean
- found_in_version: the fix commit adcb02bda9 is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent 8b9cfbc12b

**History:**

- 2026-10-04 — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-10-04 — Fixed: commit adcb02bda9
- 2026-10-04 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0243

**Tone collection could report 'done' with the old list**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | d9a79781d73fcb135429af74281a4a4008848cc0 |
| Severity | Low |
| Priority | P4 |
| Status | Fixed |

/tone-collection read the list before the scan status, so a scan ending in between answered 'done' with the old list (a flaky test).

**Steps to reproduce:** _pending_

**Expected:** Fresh list

**Observed:** Stale list after scan

**Root cause:** Read order race.

**Fixes:** [FIX-0243](../FIX_LOG.md#fix-0243) (0.10.0-beta.1)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-10-05 · **Closed:** _pending_

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Rare race.

**Evidence:**

- commit 2a947fe808 Larger Letra page; hand shapes fuzzed; two small races fixed
- found_in_version: fix 2a947fe808 (2026-10-05) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent d9a79781d7, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-10-05 — Fixed: commit 2a947fe808

## BUG-0245

**A swapped tone suggestion could not be undone in the row that showed it**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | the maintainer |
| Found in | before 0.10.0-beta.1 |
| Build / commit | bfb03598146cfc35fe30ad8bfa53913601b956f8 |
| Severity | Low |
| Priority | P4 |
| Status | Closed |

The suggestion table showed 'Distortion (em vez de ...)' for a swap chosen in 'Trocar os tons sugeridos', whose pickers sat above the first track out of sight, so the swap could not be undone where it was seen.

**Steps to reproduce:** _pending_

**Expected:** The swap can be changed or dropped in its own row.

**Observed:** 'Diz que está a distortion, mas eu quero que fique com outro tom … não consigo tirar'.

**Root cause:** Only the picker above the first track could change a swap.

**Fixes:** [FIX-0245](../FIX_LOG.md#fix-0245) (0.10.0-beta.1)

**Verified:** CLAUDE.md: 'verified with Playwright (suggestions faked: the row shows the swap, "o sugerido" sends `swaps: {}`, PT/EN, 1440/760 px, no page errors)' (by the developer (manual check))

**Resolved:** 2026-10-11 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: UI confusion; the swap could be changed above.

**Evidence:**

- CLAUDE.md § Tone over time + a tone for each part of each track — '**The same picker sits in every part's row**'
- commit 2bda715ed4 Tons: change a suggested tone in its own row, and say what a suggestion is
- found_in_version: the fix commit 2bda715ed4 is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent bfb0359814

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-10-11 — Fixed: commit 2bda715ed4
- 2026-10-11 — Verified: manual
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0327

**A tone with a bad value was accepted and failed the build later**

| | |
|---|---|
| Detected | 2026-10-18 |
| Reported by | code review (Claude, on the maintainer's request) |
| Found in | 0.11.0-beta.2 |
| Build / commit | f64c45e8e176c44bd87c7c7866f741330b443011 |
| Severity | Medium |
| Priority | P3 |
| Status | Verified |

A volume such as "loud" or NaN was stored by a rebuild or the library and only failed at build time.

**Steps to reproduce:** 

1. See the description (found by reading the code)

**Expected:** As described in the solution.

**Observed:** A volume such as "loud" or NaN was stored by a rebuild or the library and only failed at build time.

**Root cause:** Tones were stored unchecked.

**Fixes:** [FIX-0327](../FIX_LOG.md#fix-0327) (0.11.0-beta.4)

**Verified:** tests/test_api.py::test_a_tone_that_cannot_be_built_is_refused_up_front passed, and fails with the fix reverted (by pytest (the test fails on the old code))

**Resolved:** 2026-10-18 · **Closed:** _pending_

**Evidence:**

- code review of the whole codebase (six reviewers), confirmed by reading the code

**History:**

- 2026-10-18 — Open: reported
- 2026-10-18 — Fixed: commit c322940e56
- 2026-10-18 — Verified: its test passes and fails on the old code

## BUG-0338

**A tone change does not follow a sync correction made in the same rebuild**

| | |
|---|---|
| Detected | 2026-10-19 |
| Reported by | Claude, while adding tone-change time editing |
| Found in | 0.11.0-beta.4 |
| Build / commit | _pending_ |
| Severity | Medium |
| Priority | P3 |
| Status | Verified |

Tone change times are stored in the chart's clock and used by the build verbatim, while the notes move with the pending tempo/anchor corrections. The score draws the change moved with its notes (warp(previewScale(t))), so the preview and the rebuild disagree.

**Steps to reproduce:** 

1. Project with a tone change at 6.0 s and first note at 2.0 s
2. Pending sync: first note +1 s (one anchor)
3. Apply and rebuild

**Expected:** The tone change at 7.0 s, still on its note, as the score showed it.

**Observed:** Built first note 3.0 s, tone change still 6.0 s (Playwright on an invented project, 2026-10-19).

**Root cause:** toneSetsForRebuild sends the stored chart times; gp_pipeline uses tone_changes without the per-chart warp.

**Fixes:** [FIX-0338](../FIX_LOG.md#fix-0338) (0.11.1-beta.1)

**Verified:** Playwright, invented GP5 + real rebuilds: a +1 s pending correction moved the first note 2.0 → 3.0 s and the tone change 6.0 → 7.0 s (XML 6.980); per-track, the Bass with no correction kept 6.0 s (by the developer (Playwright))

**Resolved:** 2026-10-19 · **Closed:** _pending_

**Evidence:**

- Playwright, invented GP5: drawn at 7.0 before the rebuild, built at 6.0 with notes moved +1.0 s
- Playwright, invented GP5 + real rebuilds: a +1 s pending correction moved the first note 2.0 → 3.0 s and the tone change 6.0 → 7.0 s (XML 6.980); per-track, the Bass with no correction kept 6.0 s

**History:**

- 2026-10-19 — Open: reported
- 2026-10-19 — In Progress: the maintainer asked for the fix
- 2026-10-19 — Fixed: commit a9ba28fe24
- 2026-10-19 — Verified: checked in the browser with real rebuilds

## BUG-0360

**Using a detected tone one by one listed every project tone as switchable, so a rebuild with 5 or more was refused**

| | |
|---|---|
| Detected | 2026-11-02 |
| Reported by | DrekAnon (GitHub issue #9) |
| Found in | 0.12.0-beta.1 |
| Build / commit | _pending_ |
| Severity | Medium |
| Priority | P2 |
| Status | Fixed |

In the Tones page, 'use' on a detected tone set the switchable tone list to every tone of the project; with five or more tones the rebuild was refused.

**Steps to reproduce:** 

1. Have four or more tones in a project
2. Tones → Detect tone → 'use' on a suggestion
3. Apply and rebuild

**Expected:** The chosen tone takes the place of the one it replaces; the rebuild goes through.

**Observed:** 422 'Rocksmith supports at most 4 switchable tones' (reproduced by a direct rebuild with five names).

**Root cause:** applyOneTone in web/app.js assigned toneNames = jobTones.map(t => t.key).

**Fixes:** [FIX-0359](../FIX_LOG.md#fix-0359) (unreleased)

**Verified:** _pending_ (by _pending_)

**Resolved:** 2026-11-02 · **Closed:** _pending_

**History:**

- 2026-11-02 — Open: reported
- 2026-11-02 — Fixed: commit 38e0303d1f

## BUG-0361

**A Bass chart with no tones of its own took the song's guitar tones (a guitar amp on the bass)**

| | |
|---|---|
| Detected | 2026-11-02 |
| Reported by | DrekAnon (GitHub issue #9) |
| Found in | 0.12.0-beta.1 |
| Build / commit | _pending_ |
| Severity | Medium |
| Priority | P2 |
| Status | Verified |

A Bass arrangement with no tone set of its own took the song-level tones; after 'Apply best' those are the detected guitar tones, so the bass chart shipped with a guitar amp as its base tone.

**Steps to reproduce:** 

1. A GP project with a Bass chart (alone or beside a guitar)
2. Tones → Detect tone → Apply best → Apply and rebuild

**Expected:** The bass keeps a bass tone (its own, the project's bass tones or the standard one).

**Observed:** The Bass chart's tonebase is the guitar Lead preset.

**Root cause:** GpJobSpec.tones_for falls back to the song's set for every chart, and every chart received all the project's gear.

**Fixes:** [FIX-0360](../FIX_LOG.md#fix-0360) (unreleased)

**Verified:** test: regression tests passed 2026-11-02 (by the developer (pytest))

**Resolved:** 2026-11-02 · **Closed:** _pending_

**Evidence:**

- 2026-11-02: tests/test_song_end.py and test_the_bass_never_takes_the_songs_guitar_tones pass; full suite green

**History:**

- 2026-11-02 — Open: reported
- 2026-11-02 — Fixed: commit 38e0303d1f
- 2026-11-02 — Verified: regression test passed 2026-11-02
