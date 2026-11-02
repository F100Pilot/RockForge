<!-- Generated from tracking/bugs.json by `python -m tools.tracking render`. Do not edit by hand: edit the JSON and render again. -->

# Bug log

Every bug found in RockForge, with a permanent id; the full record of each is on its module's page in [bugs/](bugs). Rules and states: [docs/VERSIONING.md](../docs/VERSIONING.md#bugs). Fixes: [FIX_LOG.md](FIX_LOG.md). Releases: [RELEASE_LOG.md](RELEASE_LOG.md).

| Fixed | Verified | Closed |
|---|---|---|
| 88 | 61 | 215 |

| ID | Title | Module | Severity | Priority | Status | Found in | Fixed in |
|---|---|---|---|---|---|---|---|
| [BUG-0001](bugs/dlc-builder.md#bug-0001) | In-game song ended seconds in: only one phrase iteration was written | dlc-builder | Critical | P1 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0002](bugs/audio.md#bug-0002) | Silent in-game audio: the .wem had no seek table | audio | Critical | P1 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0003](bugs/dlc-builder.md#bug-0003) | DLC Builder import crashed (NullReferenceException) on missing arrangementProperties | dlc-builder | High | P2 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0004](bugs/dlc-builder.md#bug-0004) | Song2014 XML lacked elements DLC Builder's schema expects | dlc-builder | High | P2 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0005](bugs/sync.md#bug-0005) | GP sync offset kept the recording's own intro gap, so chart and audio drifted apart | sync | High | P2 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0006](bugs/dlc-builder.md#bug-0006) | In-game chart re-zeroed despite the lead-in (offset left at 0) | dlc-builder | High | P2 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0007](bugs/dlc-builder.md#bug-0007) | DLC Builder import crashed at offset 0: no room for the count-in phrase | dlc-builder | High | P2 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0008](bugs/import.md#bug-0008) | Minimum lead-in warning shown on every GP build | import | Low | P4 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0009](bugs/viewer.md#bug-0009) | Note viewer string colours wrong and reversed | viewer | Low | P4 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0010](bugs/game.md#bug-0010) | Palm-muted chords rendered as a corrupt highway sprite | game | High | P2 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0011](bugs/sync.md#bug-0011) | Drift correction shifted notes far outside the corrected excerpt | sync | Medium | P2 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0012](bugs/game.md#bug-0012) | Plain notes drew a spurious technique glyph (zero-valued attributes) | game | Medium | P3 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0013](bugs/sync.md#bug-0013) | Pending drag anchors did not round-trip through a rebuild with a pending tempo/offset | sync | Medium | P3 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0014](bugs/viewer.md#bug-0014) | Note tick desynced after seeking backward | viewer | Low | P4 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0015](bugs/app.md#bug-0015) | pip could not install [ml,lyrics] together: ResolutionTooDeep | app | High | P2 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0016](bugs/app.md#bug-0016) | start.bat left the broker down silently when Redis was missing | app | Medium | P3 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0017](bugs/lyrics.md#bug-0017) | LRC/UltraStar lyrics supplied at creation never shown in the editor | lyrics | Medium | P3 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0018](bugs/app.md#bug-0018) | Cover art dropped on rebuild | app | Medium | P3 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0019](bugs/app.md#bug-0019) | [ml] install failed on Windows building scipy from source | app | Medium | P3 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0020](bugs/lyrics.md#bug-0020) | WhisperX silently unavailable: torchaudio 2.5 removed AudioMetaData | lyrics | Medium | P3 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0021](bugs/audio.md#bug-0021) | Jobs stuck at the normalize/lyrics stage: ffmpeg inherited the console's stdin | audio | High | P2 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0022](bugs/viewer.md#bug-0022) | Tab viewer playback drifted mid-song (aligned at start, off after seeking) | viewer | High | P2 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0023](bugs/viewer.md#bug-0023) | Recording playback stopped and waveform flickered while a job was open | viewer | Medium | P3 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0024](bugs/tones.md#bug-0024) | '+ Criar / editar tons' did nothing (tone builder had no JavaScript) | tones | Medium | P3 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0025](bugs/lyrics.md#bug-0025) | Lyric detection hung for 40+ minutes at the WhisperX import (Celery CUDA deadlock) | lyrics | High | P2 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0026](bugs/lyrics.md#bug-0026) | A CUDA warm-up thread deadlocked the first detection on Windows | lyrics | High | P2 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0027](bugs/app.md#bug-0027) | Detection progress lost after the first commit: Job.params reassigned as the same dict | app | High | P2 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0028](bugs/dlc-builder.md#bug-0028) | DLC Builder build failed for want of a .phrase-levels file | dlc-builder | High | P2 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0029](bugs/lyrics.md#bug-0029) | Lyric detection progress looked frozen at 8-10% with no feedback | lyrics | Low | P4 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0030](bugs/sync.md#bug-0030) | Pending BPM edit lost on arrangement tab switch | sync | Medium | P3 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0031](bugs/import.md#bug-0031) | Tied notes emitted as extra attacks ('4 notes show as 5') | import | High | P2 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0032](bugs/lyrics.md#bug-0032) | GP-embedded lyrics were never shown in the UI, so they looked missing | lyrics | Low | P3 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0033](bugs/import.md#bug-0033) | .gp (GP7/8) uploads rejected at the API although the parser supported them | import | Medium | P3 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0034](bugs/import.md#bug-0034) | GP7 parser missed note-level vibrato | import | Low | P4 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0035](bugs/viewer.md#bug-0035) | Intro silence (lead_in_s) invisible in the viewer | viewer | Low | P4 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0036](bugs/lyrics.md#bug-0036) | Lyrics drawn early after a lead-in; added words landed off-cursor | lyrics | Low | P4 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0037](bugs/viewer.md#bug-0037) | Staff string labels always read E A D G B e, whatever the tuning | viewer | Low | P4 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0038](bugs/import.md#bug-0038) | YouTube ingest hung (whole playlist download, yt-dlp ffmpeg inherited stdin) | import | Medium | P3 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0039](bugs/import.md#bug-0039) | Basic Pitch transcription failed: TF SavedModel 'nmp' would not load | import | Medium | P3 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0040](bugs/app.md#bug-0040) | Closing the tab did not always stop the server (uvicorn --reload) | app | Low | P4 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0041](bugs/import.md#bug-0041) | Basic Pitch failed after WhisperX availability check imported speechbrain | import | Medium | P3 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0042](bugs/app.md#bug-0042) | API shut itself down while its tab was only in the background | app | High | P2 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0043](bugs/app.md#bug-0043) | Closing the tab no longer stopped the server: a hidden heartbeat cancelled /closing | app | Medium | P3 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0044](bugs/app.md#bug-0044) | Job stuck in RUNNING could never be deleted | app | Medium | P3 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0045](bugs/viewer.md#bug-0045) | Chord names collided with low-string notes on the score | viewer | Low | P4 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0046](bugs/tones.md#bug-0046) | Tone detection's flatness feature always contributed zero | tones | Low | P4 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0047](bugs/sync.md#bug-0047) | Guided first-note flow created a hidden anchor instead of updating the start field | sync | Low | P4 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0048](bugs/sync.md#bug-0048) | Removing a single pending correction left its marker on the score | sync | Low | P4 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0049](bugs/import.md#bug-0049) | GP5 tempo change authored on another track was ignored (grid stuck at the first tempo) | import | High | P2 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0050](bugs/viewer.md#bug-0050) | Note tick ignored the arrangement's tuning (wrong pitch in drop/open tunings) | viewer | Low | P4 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0051](bugs/dlc-builder.md#bug-0051) | A tone change landing exactly on a note made DLC Builder throw | dlc-builder | Medium | P3 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0052](bugs/tones.md#bug-0052) | 'Voz simples (sem tom)' preview still coloured by the cabinet EQ | tones | Low | P4 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0053](bugs/tones.md#bug-0053) | Clearing all tones or tone changes did not persist after rebuild | tones | Medium | P3 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0054](bugs/viewer.md#bug-0054) | Removed tone markers stayed on the score until another redraw | viewer | Low | P4 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0055](bugs/psarc.md#bug-0055) | Native PSARC never appeared in the song list: retail enumeration layout missing | psarc | Critical | P1 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0056](bugs/psarc.md#bug-0056) | Native PSARC froze on the note highway: the SNG was not a real .sng file | psarc | Critical | P1 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0057](bugs/psarc.md#bug-0057) | Game crashed on load: the SNG beat record was 12 bytes instead of 16 | psarc | Critical | P1 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0058](bugs/psarc.md#bug-0058) | Every note rendered a slide: the SNG no-slide sentinel was 0 instead of -1 | psarc | Critical | P1 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0059](bugs/psarc.md#bug-0059) | Note highway crashed on play: every SNG anchor started at t=0 | psarc | Critical | P1 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0060](bugs/psarc.md#bug-0060) | Chart showed no notes and crashed when the GP file had no section markers | psarc | Critical | P1 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0061](bugs/psarc.md#bug-0061) | Song list showed '0 notes' and a blank difficulty bar for native PSARCs | psarc | Low | P4 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0062](bugs/psarc.md#bug-0062) | Song dropped from the list: toolkit.version was not numeric | psarc | Critical | P1 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0063](bugs/psarc.md#bug-0063) | Song dropped from the list: PSARC TOC name hashes were zero | psarc | Critical | P1 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0064](bugs/psarc.md#bug-0064) | No cover shown in game: placeholder DDS had mip count 0 | psarc | Low | P4 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0065](bugs/audio.md#bug-0065) | Song-select preview played the full track over itself | audio | Low | P4 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0066](bugs/audio.md#bug-0066) | Overlapping copies of the preview played while browsing | audio | Low | P4 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0067](bugs/psarc.md#bug-0067) | Fretboard view thrashed and hid low notes (one anchor per fret change) | psarc | Medium | P3 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0068](bugs/psarc.md#bug-0068) | In-game difficulty slider read a tiny/garbled maximum | psarc | Medium | P3 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0069](bugs/import.md#bug-0069) | Sustains ran into the next note on the same string | import | Medium | P3 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0070](bugs/psarc.md#bug-0070) | Song dropped from the list: a partial raw PSARC block stored zlength 0 | psarc | Critical | P1 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0071](bugs/psarc.md#bug-0071) | Game crashed at the start of a section: SNG anchors crossed phrase boundaries | psarc | Critical | P1 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0072](bugs/psarc.md#bug-0072) | DD levels kept slide anchor-extensions and hand shapes for notes they dropped: crash | psarc | Critical | P1 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0073](bugs/psarc.md#bug-0073) | Low DD levels showed notes only at the start of a long phrase | psarc | Medium | P3 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0074](bugs/psarc.md#bug-0074) | Section-less song with no lead-in got no phrase segmentation | psarc | Low | P4 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0075](bugs/psarc.md#bug-0075) | DD always started from level 0: SongDifficulty and mastery fields were zero | psarc | Medium | P3 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0076](bugs/psarc.md#bug-0076) | Fret-hand anchor sat below the chord being played | psarc | Low | P4 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0077](bugs/psarc.md#bug-0077) | Crash at the first 5-7 octave riff in 'Free' (native PSARC) | psarc | Critical | P1 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0078](bugs/psarc.md#bug-0078) | Corrupt full-height vertical bar at palm-muted chord runs (single-note bit in ChordNotes) | psarc | High | P2 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0079](bugs/psarc.md#bug-0079) | Crash entering the next DD phrase: PhraseIterationLinks written as 0 | psarc | Critical | P1 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0080](bugs/psarc.md#bug-0080) | First phrase swallowed the silent intro and no END phrase (GP sections) | psarc | Low | P4 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0081](bugs/psarc.md#bug-0081) | Crash on DD phrase entry: full-chart anchors on every level | psarc | Critical | P1 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0082](bugs/dlc-builder.md#bug-0082) | Bends vanished in DLC Builder builds: XML had no <bendValues> | dlc-builder | Medium | P3 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0083](bugs/psarc.md#bug-0083) | Native PSARC stage stayed dark and the title card was skipped: empty showlights | psarc | Low | P4 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0084](bugs/lyrics.md#bug-0084) | Native lyrics never appeared: vocal note was 0 instead of the 254 sentinel | lyrics | High | P2 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0085](bugs/lyrics.md#bug-0085) | Native lyrics never appeared: vocals SNG had an empty glyph atlas | lyrics | High | P2 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0086](bugs/psarc.md#bug-0086) | Crash at the first bent chord (ChordNotes UsedCount before the bend array) | psarc | Critical | P1 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0087](bugs/psarc.md#bug-0087) | Bends looked smaller in game (point at the attack = prebend) | psarc | Low | P4 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0088](bugs/dlc-builder.md#bug-0088) | arrangementProperties tapping and slapPop hardcoded 0 | dlc-builder | Low | P4 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0089](bugs/import.md#bug-0089) | GP7 pinch harmonics read as none (HType compared case-sensitively) | import | Low | P4 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0090](bugs/import.md#bug-0090) | GP7 slide-out lost when combined with a slide-in flag | import | Low | P4 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0091](bugs/psarc.md#bug-0091) | DD difficulty bars flat-topped at the level-11 cap | psarc | Low | P4 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0092](bugs/viewer.md#bug-0092) | Nonsense '? (0n/0c)' tab for the vocals XML | viewer | Low | P4 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0093](bugs/lyrics.md#bug-0093) | Lyrics scrolled in game as a wall of text (no line breaks within long lines) | lyrics | Medium | P3 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0094](bugs/psarc.md#bug-0094) | Game crashed at a gapped octave while scoring: chord template unused strings were MIDI 0 | psarc | Critical | P1 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0095](bugs/psarc.md#bug-0095) | Game crashed while scoring notes in late sections: note PhraseId out of range | psarc | Critical | P1 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0096](bugs/tones.md#bug-0096) | Native PSARC played a default tone despite the user's custom tones | tones | High | P2 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0097](bugs/audio.md#bug-0097) | Song-select preview blasted over the song list (uncalibrated bus volume) | audio | Low | P4 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0098](bugs/import.md#bug-0098) | Notes off the 24-fret neck dropped silently | import | Low | P4 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0099](bugs/audio.md#bug-0099) | Songs sounded quiet in game next to official DLC (-16 LUFS target) | audio | Medium | P3 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0100](bugs/sync.md#bug-0100) | Conflicting sync anchors crashed the build with a cryptic TempoMap error | sync | Medium | P3 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0101](bugs/sync.md#bug-0101) | A local sync stretch re-inflated sustains into fused 'tall pillars' | sync | Medium | P3 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0102](bugs/sync.md#bug-0102) | "Mover seguintes", tap and re-tempo moved notes the wrong way once an anchor existed | sync | High | P2 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0103](bugs/sync.md#bug-0103) | "Mover seguintes" also moved the notes before the click | sync | Medium | P2 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0104](bugs/sync.md#bug-0104) | Dragging a note to the playback cursor was unreliable | sync | Medium | P3 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0105](bugs/viewer.md#bug-0105) | Zooming lost the place in the song | viewer | Low | P3 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0106](bugs/viewer.md#bug-0106) | Shift+click/drag on the score selected label text like page text | viewer | Low | P4 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0107](bugs/sync.md#bug-0107) | Pending-corrections list went stale after a plain mouse drag | sync | Low | P3 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0108](bugs/viewer.md#bug-0108) | A track resting through the outro was drawn shorter than the song | viewer | Low | P3 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0109](bugs/lyrics.md#bug-0109) | A native GPU crash (Turing/cuDNN) aborted lyric detection and recurred on every run | lyrics | High | P2 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0110](bugs/lyrics.md#bug-0110) | ctranslate2 could not load torch's bundled cuDNN on Windows and crashed | lyrics | Medium | P3 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0111](bugs/app.md#bug-0111) | Songs with GP/LRC/edited lyrics read 'sem letra' in the checklist | app | Low | P3 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0112](bugs/psarc.md#bug-0112) | Corrupt lateral highway blur on fast repeated chords: high density never set | psarc | Medium | P3 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0113](bugs/psarc.md#bug-0113) | Graphical glitch at the first notes: song-start anchor took the LAST phrase | psarc | Medium | P3 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0114](bugs/psarc.md#bug-0114) | Corrupt highway bars on sustained chords: no ChordNotes entry for plain sustained chords | psarc | Medium | P3 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0115](bugs/sync.md#bug-0115) | Automatic sync jumped the BPM ~50% on triplet/compound feels | sync | Medium | P3 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0116](bugs/app.md#bug-0116) | ⚙️ Definições unreachable while a song was open | app | Low | P4 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0117](bugs/import.md#bug-0117) | Audio-ML job crashed on out-of-order librosa beat times | import | Medium | P3 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0118](bugs/import.md#bug-0118) | Transcription flooded the chart and warnings with unplayable ghost notes | import | Low | P4 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0119](bugs/import.md#bug-0119) | Down-tuned songs read as standard; real low notes pruned | import | Low | P4 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0120](bugs/audio.md#bug-0120) | detect_tones and separate_stems ran the same Demucs separation twice | audio | Low | P4 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0121](bugs/security.md#bug-0121) | Docker deployment exposed the whole API without authentication | security | Critical | P1 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0122](bugs/app.md#bug-0122) | Job progress pills never lit (old pipeline stage names) | app | Low | P4 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0123](bugs/import.md#bug-0123) | GP5 notes after a dropped out-of-range note came one beat late | import | High | P2 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0124](bugs/psarc.md#bug-0124) | Accented lyrics could crash SNG read-back (UTF-8 cut mid-character) | psarc | Medium | P3 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0125](bugs/security.md#bug-0125) | Uploads had no size limit | security | Medium | P3 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0126](bugs/security.md#bug-0126) | Cross-site form POSTs accepted (no same-origin check) | security | High | P2 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0127](bugs/security.md#bug-0127) | GP7 import open to zip bombs and XML entity expansion | security | High | P2 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0128](bugs/viewer.md#bug-0128) | Interrupted drags stacked listeners (knobs spun 2-3× faster) | viewer | Medium | P3 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0129](bugs/app.md#bug-0129) | Upload endpoints blocked the event loop (heartbeats starved) | app | Medium | P3 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0130](bugs/security.md#bug-0130) | Docker Compose shipped known default database credentials | security | Low | P4 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0131](bugs/psarc.md#bug-0131) | DD tier of a note on the final beat compared to the first beat | psarc | Low | P4 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0132](bugs/lyrics.md#bug-0132) | All-melisma GP lyric line dropped instead of holding the previous syllable | lyrics | Low | P4 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0133](bugs/viewer.md#bug-0133) | Clicks/noise when scrubbing the recording | viewer | Low | P4 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0134](bugs/sync.md#bug-0134) | Dynamic auto-sync discarded the pinned first note and realigned from 0 s | sync | Medium | P3 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0135](bugs/sync.md#bug-0135) | Dynamic auto-sync rushed the chart ahead | sync | Medium | P3 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0136](bugs/viewer.md#bug-0136) | Drag/box-select could not reach past the visible part of the score | viewer | Medium | P3 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0137](bugs/editor.md#bug-0137) | In 'Editar notas' a click on empty staff inserted a note instead of seeking | editor | Medium | P3 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0138](bugs/viewer.md#bug-0138) | Synthesized audio kept playing under a 'full mix' selector after switching jobs | viewer | Medium | P3 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0139](bugs/sync.md#bug-0139) | Tempo detection read the wrong metrical level on dense mixes | sync | Medium | P3 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0140](bugs/sync.md#bug-0140) | Missing beatthis extra reported as 422 instead of 503 | sync | Low | P4 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0141](bugs/sync.md#bug-0141) | Beat This! checkpoint download kept failing on the user's machine | sync | Medium | P3 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0142](bugs/sync.md#bug-0142) | Neural downbeat sync put the BPM off (wrong metrical level / mixed meter) | sync | Medium | P3 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0143](bugs/sync.md#bug-0143) | Synced in the app but desynced in Rocksmith after a tempo change with committed anchors | sync | High | P2 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0144](bugs/sync.md#bug-0144) | Viewer's scoreShift omitted lead_in_s, desyncing the rebuild by lead_in_s·(r−1) | sync | Medium | P2 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0145](bugs/viewer.md#bug-0145) | Audio crackle/dropouts and score slowing down while editing | viewer | Medium | P3 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0146](bugs/sync.md#bug-0146) | Pending corrections listed in insertion order; a crossing correction was hidden | sync | Low | P4 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0147](bugs/import.md#bug-0147) | GP7/8 tempo: reference note value ignored (half-note tempo read at half speed) | import | High | P2 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0148](bugs/import.md#bug-0148) | GP7/8 mid-bar tempo changes placed at the wrong tick | import | Medium | P3 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0149](bugs/app.md#bug-0149) | New buttons did nothing: browser kept a stale app.js | app | Medium | P3 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0150](bugs/viewer.md#bug-0150) | Score labels piled into an unreadable wall on dense charts | viewer | Low | P4 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0151](bugs/sync.md#bug-0151) | Sync analysis flooded the score with corrections on real audio | sync | Medium | P3 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0152](bugs/viewer.md#bug-0152) | Re-tempo mode reused the 'Detetar 1ª nota' icon | viewer | Low | P4 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0153](bugs/sync.md#bug-0153) | "Corrigir daqui" always read a higher tempo and ran the chart fast | sync | High | P2 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0154](bugs/viewer.md#bug-0154) | The live BPM readout ignored pending tempo and anchor edits | viewer | Low | P3 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0155](bugs/psarc.md#bug-0155) | Manifest advertised no techniques, SongOffset 0 and TargetScore 0 | psarc | Low | P4 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0156](bugs/app.md#bug-0156) | Actions silently did nothing when the server had gone away | app | Medium | P3 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0157](bugs/exe.md#bug-0157) | Closing the tab aborted in-process work and left the job stuck at RUNNING | exe | High | P2 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0158](bugs/psarc.md#bug-0158) | SNG wrote CapoFret 0 ('capo at fret 0') when there was no capo | psarc | Low | P4 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0159](bugs/tones.md#bug-0159) | Tone detection read almost every song as clean | tones | Medium | P3 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0160](bugs/app.md#bug-0160) | NaN/Infinity accepted in API floats: the build later failed with an error pointing nowhere | app | Medium | P3 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0161](bugs/app.md#bug-0161) | Missing ML extra reported as a confusing 422 instead of a 503 | app | Low | P4 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0162](bugs/app.md#bug-0162) | Impossible tuning pitch accepted, then crashed the SNG writer with struct.error | app | Medium | P3 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0163](bugs/app.md#bug-0163) | Deleted jobs and abandoned wizards left their Guitar Pro uploads on disk forever | app | Low | P4 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0164](bugs/release.md#bug-0164) | CI was green while never running the native PSARC tests | release | Medium | P3 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0165](bugs/exe.md#bug-0165) | Standalone .exe shipped an inert UI: web/app.js not bundled | exe | Critical | P1 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0166](bugs/export.md#bug-0166) | Corrected-GP export had no entry point in the UI | export | Low | P4 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0167](bugs/editor.md#bug-0167) | An unrelated rebuild silently erased committed note edits | editor | Critical | P1 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0168](bugs/viewer.md#bug-0168) | "Pendente" summary never shown: its element was missing from the markup | viewer | Low | P3 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0169](bugs/psarc.md#bug-0169) | Dynamic Difficulty never kept a raised level in game | psarc | High | P2 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0170](bugs/psarc.md#bug-0170) | Riff Repeater named two passages the same: duplicate section numbers | psarc | Low | P4 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0171](bugs/import.md#bug-0171) | Every mid-song GP5 tempo change applied one quarter note late | import | High | P2 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0172](bugs/exe.md#bug-0172) | Standalone .exe could never run the ML stages: it relaunched itself as the interpreter | exe | High | P2 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0173](bugs/import.md#bug-0173) | Guitar Pro 8 SyncPoints ignored, so a chart synced in Guitar Pro drifted | import | High | P2 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0174](bugs/exe.md#bug-0174) | Every project created in the .exe stayed pending forever: Celery modules not bundled | exe | Critical | P1 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0175](bugs/app.md#bug-0175) | A task that died before its own error handling left the job silently pending | app | Medium | P3 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0176](bugs/import.md#bug-0176) | GP8 chart came out one bar late with the untrimmed recording | import | High | P2 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0177](bugs/sync.md#bug-0177) | UI said the MP3 could come from Songsterr, whose audio does not match the times | sync | Low | P4 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0178](bugs/app.md#bug-0178) | Form modals closed on a stray click, losing a half-filled wizard | app | Medium | P3 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0179](bugs/app.md#bug-0179) | A file dropped outside a drop zone navigated away from the app | app | Medium | P3 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0180](bugs/app.md#bug-0180) | "Criar CDLC" did nothing when the start time had 3 decimals | app | High | P2 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0181](bugs/app.md#bug-0181) | The 'confirm sync' reminder could never be cleared for a chart that needed no change | app | Low | P4 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0182](bugs/app.md#bug-0182) | Album lookup found nothing for 'feat.' credits | app | Low | P4 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0183](bugs/import.md#bug-0183) | YouTube audio download failed: yt-dlp lacked the JavaScript challenge solver and runtime | import | High | P2 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0184](bugs/editor.md#bug-0184) | Note edits missed notes whose time the XML rounded (deleted notes still sounded) | editor | High | P2 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0185](bugs/lyrics.md#bug-0185) | Lyric edits showed no pending sign | lyrics | Low | P4 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0186](bugs/import.md#bug-0186) | Songsterr import failed with CERTIFICATE_VERIFY_FAILED: certificate has expired | import | High | P2 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0187](bugs/import.md#bug-0187) | Songsterr refusals said only '403', hiding 'this tab is unpublished' | import | Low | P4 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0188](bugs/import.md#bug-0188) | Songsterr import aborted entirely on text GP5 cannot store (e.g. a Cyrillic title) | import | High | P2 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0189](bugs/sync.md#bug-0189) | Any sync correction dropped bend curves, fingering and pick direction | sync | High | P2 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0190](bugs/lyrics.md#bug-0190) | GP-embedded lyrics never reached the editor (params dict mutated in place) | lyrics | High | P2 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0191](bugs/lyrics.md#bug-0191) | GP lyrics timed on the guitar chart's notes instead of the vocal line | lyrics | Medium | P2 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0192](bugs/import.md#bug-0192) | Audio embedded in a GP8 file not detected (disabled track, other extensions, member name) | import | Medium | P3 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0193](bugs/app.md#bug-0193) | Batch mode skipped a GP8 file with its own audio or gave it another song's recording | app | Medium | P3 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0194](bugs/app.md#bug-0194) | Reloading the GP file always kept the old recording, never the new file's own audio | app | Medium | P3 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0195](bugs/app.md#bug-0195) | YouTube audio download hidden inside the Songsterr extra, unseen with a plain GP file | app | Low | P3 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0196](bugs/import.md#bug-0196) | Songs whose last notes fall after the last beat refused to build | import | Critical | P1 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0197](bugs/lyrics.md#bug-0197) | Lyric line cap counted syllables, splitting mid-phrase and leaving orphan words | lyrics | Low | P3 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0198](bugs/lyrics.md#bug-0198) | Lyrics stayed put when the notes' sync was corrected | lyrics | Medium | P2 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0199](bugs/sync.md#bug-0199) | Bar sync against another track and the synthesized source ignored the intro silence | sync | Medium | P3 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0200](bugs/viewer.md#bug-0200) | An alternate chart showed as a second Lead/Rhythm and shared the main chart's edits | viewer | High | P2 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0201](bugs/import.md#bug-0201) | Bar 1 before the recording (negative GP start) clamped to 0, every note late | import | High | P2 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0202](bugs/sync.md#bug-0202) | Sync view clamped a negative start to 0 and a rebuild then lost the file's sync | sync | High | P2 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0203](bugs/import.md#bug-0203) | Three-point bends rose twice as fast as alphaTab/Guitar Pro play them | import | Medium | P3 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0204](bugs/import.md#bug-0204) | A flat pre-bend was charted as a rise across the note instead of bent from the attack | import | Medium | P3 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0205](bugs/import.md#bug-0205) | GP8 embedded audio with no file extension not recognised and offered as an external file | import | Medium | P3 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0206](bugs/import.md#bug-0206) | Repeats, voltas and jumps played once, putting everything after them early | import | High | P2 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0207](bugs/sync.md#bug-0207) | Rebuild committed only the on-screen chart's pending sync; other tabs' edits vanished | sync | High | P2 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0208](bugs/viewer.md#bug-0208) | A GP8 file with SyncPoints turned every track green with none marked | viewer | Medium | P3 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0209](bugs/psarc.md#bug-0209) | Game froze on charts that enter late: sections out of order | psarc | Critical | P1 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0210](bugs/psarc.md#bug-0210) | Game crashed raising the difficulty: notes kept the full chart's anchor | psarc | Critical | P1 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0211](bugs/psarc.md#bug-0211) | A 0.1 s note-less END phrase when the last note touched the last section | psarc | Low | P4 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0212](bugs/psarc.md#bug-0212) | Game crashed raising the difficulty on a one-note phrase: ceiling 0 | psarc | Critical | P1 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0213](bugs/psarc.md#bug-0213) | Passages differing by a technique or sustain were linked as one phrase | psarc | Medium | P3 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0214](bugs/psarc.md#bug-0214) | SNG note bytes wrote 0 instead of -1 for unused Tap/Slap/Pluck/LeftHand/PickDirection | psarc | Medium | P3 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0215](bugs/dlc-builder.md#bug-0215) | Upstrokes became SLAP on the DLC Builder path: XML pickDirection wrote 2 | dlc-builder | Medium | P3 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0216](bugs/psarc.md#bug-0216) | Daughtry 'September' still crashed: native phrases differed from DLC Builder's | psarc | Critical | P1 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0217](bugs/audio.md#bug-0217) | Recording squashed by loudnorm: PSARC audio noisy and not clean | audio | Medium | P3 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0218](bugs/tones.md#bug-0218) | A chart with no tone of its own shipped an empty Tones array | tones | Medium | P3 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0219](bugs/tones.md#bug-0219) | Mid-song tone changes never happened in the native PSARC | tones | High | P2 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0220](bugs/tones.md#bug-0220) | Tone presets nearly inaudible in game: volumes on the wrong side of the scale | tones | Medium | P3 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0221](bugs/tones.md#bug-0221) | Plexi presets set a knob the amp does not have, so the setting was dropped | tones | Low | P4 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0222](bugs/import.md#bug-0222) | Tied notes lost their bend and hammer/pull-off when folded | import | Medium | P3 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0223](bugs/import.md#bug-0223) | GP7 bend-and-release lost its hold at the top | import | Low | P4 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0224](bugs/export.md#bug-0224) | Corrected-GP export wrote bends 50 times too big | export | Medium | P3 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0225](bugs/import.md#bug-0225) | GP7 grace notes counted as bar time, shifting every later note | import | High | P2 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0226](bugs/import.md#bug-0226) | GP5 pinch and tapped harmonic types swapped | import | Low | P4 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0227](bugs/import.md#bug-0227) | Vibrato on a tied note lost when the tie folded | import | Low | P4 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0228](bugs/import.md#bug-0228) | GP7/8 let ring lost (<LetRing/> inside the note) | import | Low | P4 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0229](bugs/import.md#bug-0229) | Bend-and-release happened early after the sustain trim | import | Low | P4 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0230](bugs/export.md#bug-0230) | Charts read back from the XML lost their bend curves | export | Medium | P3 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0231](bugs/app.md#bug-0231) | Saving 'Editar info' always forked a rebuild, even for title/album changes | app | Low | P3 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0232](bugs/tones.md#bug-0232) | Driven tone presets left a hiss at the end of notes | tones | Medium | P3 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0233](bugs/tones.md#bug-0233) | Orange crunch preset noisy on Daughtry 'September' | tones | Medium | P3 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0234](bugs/tones.md#bug-0234) | Crunch preset too quiet and still too distorted; Overdrive slightly quiet | tones | Low | P4 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0235](bugs/app.md#bug-0235) | start.bat refused Python 3.11 itself: delayed expansion ate the '!' | app | High | P2 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0236](bugs/app.md#bug-0236) | start.bat used Python 3.13 when 3.11 was installed without the py launcher | app | Low | P4 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0237](bugs/app.md#bug-0237) | start.bat stopped with an error when Redis could not be installed | app | Medium | P3 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0238](bugs/app.md#bug-0238) | CDLC patch check always said 'por confirmar', even on the machine with the game | app | Low | P4 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0239](bugs/tones.md#bug-0239) | Tone presets still hissed and did not sound clean next to hand-made tones | tones | Medium | P3 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0240](bugs/psarc.md#bug-0240) | Native chords showed no finger positions, unlike official songs | psarc | Medium | P3 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0241](bugs/psarc.md#bug-0241) | Manifest SongPartition was 1 on every chart, so a Lead and its alternate were both Lead 1 | psarc | Medium | P3 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0242](bugs/psarc.md#bug-0242) | Hand shape LastNoteTime equal to its end after float32 rounding | psarc | Low | P4 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0243](bugs/tones.md#bug-0243) | Tone collection could report 'done' with the old list | tones | Low | P4 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0244](bugs/app.md#bug-0244) | Transcription bench could not download its model on Windows (cp1252 stdout) | app | Low | P4 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0245](bugs/tones.md#bug-0245) | A swapped tone suggestion could not be undone in the row that showed it | tones | Low | P4 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0246](bugs/security.md#bug-0246) | esc() did not escape quotes: third-party text could run code in the page (XSS) | security | Critical | P1 | Closed | pending | 0.10.0-beta.2 |
| [BUG-0247](bugs/security.md#bug-0247) | Server answered any Host name, so a DNS-rebound web page could reach the local API | security | Critical | P1 | Closed | pending | 0.10.0-beta.2 |
| [BUG-0248](bugs/security.md#bug-0248) | A request with Origin: null was not treated as cross-origin | security | Critical | P1 | Closed | pending | 0.10.0-beta.2 |
| [BUG-0249](bugs/security.md#bug-0249) | Responses lacked nosniff and anti-framing headers | security | Medium | P2 | Closed | pending | 0.10.0-beta.2 |
| [BUG-0250](bugs/psarc.md#bug-0250) | Docker image made no .psarc (the [psarc] extra was not installed) | psarc | High | P2 | Closed | pending | 0.10.0-beta.2 |
| [BUG-0251](bugs/import.md#bug-0251) | GP8 embedded audio in .opus/.webm/.aac/.mp4/.wma was detected, then refused by the build | import | Medium | P3 | Closed | pending | 0.10.0-beta.2 |
| [BUG-0252](bugs/sync.md#bug-0252) | A double click on "Apply and rebuild" created two versions | sync | Medium | P3 | Closed | pending | 0.10.0-beta.2 |
| [BUG-0253](bugs/app.md#bug-0253) | A late answer reopened a closed project; detection pollers drew into the next project | app | Medium | P3 | Closed | pending | 0.10.0-beta.2 |
| [BUG-0254](bugs/lyrics.md#bug-0254) | Times rounded to "1:60" in lyric lengths and "[00:60.00]" in the exported LRC | lyrics | Low | P4 | Fixed | pending | 0.10.0-beta.2 |
| [BUG-0255](bugs/sync.md#bug-0255) | Negative intro silence was accepted and misaligned sync corrections after a tempo change | sync | Medium | P3 | Closed | pending | 0.10.0-beta.2 |
| [BUG-0256](bugs/app.md#bug-0256) | The "Lead/Rhythm (exp.)" checkbox did nothing | app | Low | P4 | Fixed | pending | 0.10.0-beta.2 |
| [BUG-0257](bugs/psarc.md#bug-0257) | The detected tuning deviation (cents) never reached the .psarc | psarc | Medium | P2 | Closed | pending | 0.10.0-beta.2 |
| [BUG-0258](bugs/app.md#bug-0258) | The six "Afinação (MIDI)" inputs did nothing | app | Low | P3 | Fixed | pending | 0.10.0-beta.2 |
| [BUG-0259](bugs/app.md#bug-0259) | Seven button requests could throw an uncaught error the offline banner did not see | app | Low | P4 | Fixed | pending | 0.10.0-beta.2 |
| [BUG-0260](bugs/viewer.md#bug-0260) | Project top bar drew the status chip over the title buttons on narrow screens | viewer | Low | P4 | Closed | pending | 0.10.0-beta.2 |
| [BUG-0261](bugs/import.md#bug-0261) | PDF import put the next staff's H/P letters into the lyrics | import | Medium | P3 | Closed | pending | 0.10.0-beta.2 |
| [BUG-0262](bugs/lyrics.md#bug-0262) | Letra table showed times like 1:010.0 | lyrics | Low | P4 | Closed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0263](bugs/viewer.md#bug-0263) | Áudio panel did not close with Escape when focus was outside it | viewer | Low | P4 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0264](bugs/app.md#bug-0264) | Stale or wrong UI labels ('Estado do PSARC', English alternate-lead label) | app | Low | P4 | Fixed | before 0.10.0-beta.1 | 0.10.0-beta.1 |
| [BUG-0265](bugs/exe.md#bug-0265) | In the .exe, a project without tones of its own made no .psarc | exe | Critical | P1 | Closed | pending | 0.10.0-beta.2 |
| [BUG-0266](bugs/app.md#bug-0266) | start.bat's git pull stalled on Windows with repeated "Unlink of file ... failed" prompts | app | Medium | P3 | Fixed | pending | 0.10.0-beta.2 |
| [BUG-0267](bugs/release.md#bug-0267) | Release workflow ignored a tag without the leading v; the beta 3 release had no files | release | High | P2 | Closed | 0.10.0-beta.3 | 0.10.0-beta.5 |
| [BUG-0268](bugs/exe.md#bug-0268) | In the .exe, the "Download" buttons did nothing | exe | Critical | P1 | Closed | pending | 0.10.0-beta.5 |
| [BUG-0269](bugs/import.md#bug-0269) | The Guitar Pro file's capo was ignored | import | High | P2 | Closed | pending | 0.10.0-beta.5 |
| [BUG-0270](bugs/psarc.md#bug-0270) | A difficulty level holding only open strings had no anchor in the .psarc | psarc | High | P2 | Closed | pending | 0.10.0-beta.5 |
| [BUG-0271](bugs/psarc.md#bug-0271) | Without Wwise, the .psarc carried the whole WAV (~30 MB) where the game never reads it | psarc | Medium | P3 | Closed | pending | 0.10.0-beta.5 |
| [BUG-0272](bugs/dlc-builder.md#bug-0272) | XML, viewer and native SNG placed different automatic fret-hand positions | dlc-builder | Medium | P3 | Closed | pending | 0.10.0-beta.5 |
| [BUG-0273](bugs/exe.md#bug-0273) | In the .exe, installed extra components were unused when the ML Python setting was empty | exe | High | P2 | Closed | 0.10.0-beta.5 | 0.10.0-beta.6 |
| [BUG-0274](bugs/exe.md#bug-0274) | Black console windows flashed in the .exe whenever a child program ran | exe | Low | P4 | Closed | pending | 0.10.0-beta.7 |
| [BUG-0275](bugs/psarc.md#bug-0275) | Wwise installed but reported as "ROCKFORGE_WWISE_ROOT is not set" | psarc | High | P2 | Closed | pending | 0.10.0-beta.7 |
| [BUG-0276](bugs/sync.md#bug-0276) | A sync mode was selected on entry, so the first click on a note re-timed the song | sync | Medium | P3 | Fixed | pending | 0.10.0-beta.7 |
| [BUG-0277](bugs/audio.md#bug-0277) | librosa runner failed with an external ML Python: its packaging folder shadowed pip's | audio | High | P2 | Closed | pending | 0.10.0-beta.7 |
| [BUG-0278](bugs/import.md#bug-0278) | After a D.C./D.S. the 1st-time ending was played again before the 2nd | import | Medium | P3 | Closed | 0.10.0-beta.6 | 0.10.0-beta.7 |
| [BUG-0279](bugs/game.md#bug-0279) | Every short note carried a sustain tail on the highway | game | Medium | P2 | Closed | 0.10.0-beta.6 | 0.10.0-beta.7 |
| [BUG-0280](bugs/import.md#bug-0280) | PDF import: a grace number drawn over the next note's digits joined into other frets | import | Medium | P3 | Fixed | pending | 0.10.0-beta.7 |
| [BUG-0281](bugs/import.md#bug-0281) | PDF import (OCR): small 9/6/3 grace notes were read as normal notes | import | Medium | P3 | Fixed | pending | 0.10.0-beta.7 |
| [BUG-0282](bugs/app.md#bug-0282) | The New project wizard could not take a cover image from the computer | app | Low | P3 | Closed | pending | 0.10.0-beta.8 |
| [BUG-0283](bugs/exe.md#bug-0283) | The .exe never used the GPU for the ML stages | exe | Medium | P2 | Closed | 0.10.0-beta.7 | 0.10.0-beta.8 |
| [BUG-0284](bugs/viewer.md#bug-0284) | Sustained notes played as a short pick in the editor's preview | viewer | Low | P3 | Closed | 0.10.0-beta.7 | 0.10.0-beta.9 |
| [BUG-0285](bugs/sync.md#bug-0285) | Recording attacks (and the auto-sync) sat late by the intro silence | sync | Medium | P2 | Closed | 0.10.0-beta.9 | 0.10.0-beta.10 |
| [BUG-0286](bugs/audio.md#bug-0286) | Separated stems showed many false attacks from the separation's residue | audio | Medium | P3 | Closed | pending | 0.10.0-beta.10 |
| [BUG-0287](bugs/sync.md#bug-0287) | Reload GP with the file's own audio kept the old recording's stems and tone detection | sync | Medium | P3 | Closed | pending | 0.10.0-beta.10 |
| [BUG-0288](bugs/game.md#bug-0288) | Open-string chords without sustain were painted solid top to bottom in game | game | High | P2 | Closed | 0.10.0-beta.10 | 0.10.0-beta.11 |
| [BUG-0289](bugs/editor.md#bug-0289) | Inserting a note in a solo snapped to the previous note's beat and made a chord | editor | Medium | P3 | Closed | pending | 0.10.0-beta.12 |
| [BUG-0290](bugs/editor.md#bug-0290) | A deleted or edited note was still heard until the rebuild | editor | Low | P3 | Closed | pending | 0.10.0-beta.12 |
| [BUG-0291](bugs/sync.md#bug-0291) | "Song start" after an automatic sync moved only the first stretch of the song | sync | Medium | P3 | Closed | pending | 0.10.0-beta.12 |
| [BUG-0292](bugs/psarc.md#bug-0292) | WWISEROOT pointing at another Wwise version hid a usable 2023.1 ("Wwise not installed") | psarc | High | P2 | Closed | pending | 0.10.0-beta.13 |
| [BUG-0293](bugs/psarc.md#bug-0293) | A failed Wwise conversion read "no Wwise found" and the silent .psarc showed as playable | psarc | Medium | P2 | Closed | pending | 0.10.0-beta.13 |
| [BUG-0294](bugs/viewer.md#bug-0294) | The 3D highway grabbed the mouse wheel while the page was scrolled over it | viewer | Low | P3 | Closed | pending | 0.10.0-beta.13 |
| [BUG-0295](bugs/sync.md#bug-0295) | Dragging a selection stretched the notes before it when another correction was pending | sync | Medium | P2 | Closed | 0.10.0-beta.15 | 0.10.0-beta.16 |
| [BUG-0296](bugs/viewer.md#bug-0296) | Cancelling the separation question of the audio bars still analysed the recording | viewer | Low | P3 | Fixed | unreleased | 0.11.0-beta.1 |
| [BUG-0297](bugs/editor.md#bug-0297) | Moving notes in the score changed the tempo and other notes, and a chord could not be moved | editor | Medium | P2 | Fixed | 0.11.0-beta.2 | 0.11.0-beta.3 |
| [BUG-0298](bugs/app.md#bug-0298) | A background task undid what the user changed while it ran | app | High | P1 | Verified | 0.11.0-beta.2 | 0.11.0-beta.3 |
| [BUG-0299](bugs/exe.md#bug-0299) | Lyric detection always failed in the .exe | exe | High | P1 | Verified | 0.11.0-beta.2 | 0.11.0-beta.3 |
| [BUG-0300](bugs/psarc.md#bug-0300) | A title or artist with an accent left the project without a .psarc | psarc | High | P1 | Closed | 0.11.0-beta.2 | 0.11.0-beta.3 |
| [BUG-0301](bugs/sync.md#bug-0301) | The "Cursor" snap option snapped every drag to the song's last beat | sync | Medium | P2 | Fixed | 0.11.0-beta.2 | 0.11.0-beta.3 |
| [BUG-0302](bugs/editor.md#bug-0302) | Editing a note lost its slide and the fields the editor does not show | editor | High | P1 | Verified | 0.11.0-beta.2 | 0.11.0-beta.3 |
| [BUG-0303](bugs/sync.md#bug-0303) | A sync tool used beside a lone "Song start" folded the chart and failed the rebuild | sync | High | P1 | Verified | 0.11.0-beta.2 | 0.11.0-beta.3 |
| [BUG-0304](bugs/export.md#bug-0304) | The Guitar Pro export of the edited notes lost the capo | export | Medium | P2 | Verified | 0.11.0-beta.2 | 0.11.0-beta.3 |
| [BUG-0305](bugs/psarc.md#bug-0305) | "Check PSARC" reported a fault for every slap, pop or tap | psarc | Medium | P2 | Verified | 0.11.0-beta.2 | 0.11.0-beta.3 |
| [BUG-0306](bugs/app.md#bug-0306) | A refused cover upload deleted the cover the project had | app | Medium | P2 | Verified | 0.11.0-beta.2 | 0.11.0-beta.3 |
| [BUG-0307](bugs/import.md#bug-0307) | A wrong value in an imported project broke the home page | import | High | P2 | Verified | 0.11.0-beta.2 | 0.11.0-beta.3 |
| [BUG-0308](bugs/import.md#bug-0308) | A GP7/8 file with a two-staff track before the guitar charted the wrong bars | import | High | P2 | Verified | 0.11.0-beta.2 | 0.11.0-beta.3 |
| [BUG-0309](bugs/import.md#bug-0309) | Auto-pick put a "Lead/Rhythm" track in both slots and the build failed | import | Medium | P2 | Verified | 0.11.0-beta.2 | 0.11.0-beta.4 |
| [BUG-0310](bugs/import.md#bug-0310) | A scoop from its own fret turned a note seconds earlier into a long slide | import | Medium | P2 | Verified | 0.11.0-beta.2 | 0.11.0-beta.4 |
| [BUG-0311](bugs/import.md#bug-0311) | A trilled note lost its fingering, pick direction, slide and link | import | Low | P3 | Verified | 0.11.0-beta.2 | 0.11.0-beta.4 |
| [BUG-0312](bugs/import.md#bug-0312) | A capo pushed slide and trill targets past fret 24 | import | Low | P3 | Verified | 0.11.0-beta.2 | 0.11.0-beta.4 |
| [BUG-0313](bugs/export.md#bug-0313) | The GP5 export of edited notes could write an unreadable file | export | Medium | P2 | Verified | 0.11.0-beta.2 | 0.11.0-beta.4 |
| [BUG-0314](bugs/export.md#bug-0314) | The GP5 export drifted with whole-BPM rounding and lost the tempo of bars without notes | export | Medium | P2 | Verified | 0.11.0-beta.2 | 0.11.0-beta.4 |
| [BUG-0315](bugs/export.md#bug-0315) | A tempo correction in the GP5 export lost to a tempo left on another track | export | Medium | P3 | Verified | 0.11.0-beta.2 | 0.11.0-beta.4 |
| [BUG-0316](bugs/import.md#bug-0316) | A locked .gp file gave a 500 and left its upload | import | Medium | P3 | Verified | 0.11.0-beta.2 | 0.11.0-beta.4 |
| [BUG-0317](bugs/lyrics.md#bug-0317) | A GP7 lyric line on a bar never played appeared at the start | lyrics | Low | P3 | Verified | 0.11.0-beta.2 | 0.11.0-beta.4 |
| [BUG-0318](bugs/dlc-builder.md#bug-0318) | A half-step bend lost its value in the XML | dlc-builder | Medium | P3 | Verified | 0.11.0-beta.2 | 0.11.0-beta.4 |
| [BUG-0319](bugs/dlc-builder.md#bug-0319) | A chord with every string fret-hand muted was not marked muted in the XML | dlc-builder | Low | P3 | Verified | 0.11.0-beta.2 | 0.11.0-beta.4 |
| [BUG-0320](bugs/lyrics.md#bug-0320) | UltraStar syllables of one word were shown as separate words | lyrics | Medium | P3 | Verified | 0.11.0-beta.2 | 0.11.0-beta.4 |
| [BUG-0321](bugs/lyrics.md#bug-0321) | An LRC line with several times put a time into the lyric | lyrics | Medium | P3 | Verified | 0.11.0-beta.2 | 0.11.0-beta.4 |
| [BUG-0322](bugs/app.md#bug-0322) | After a reload with other audio, dropping the old version reused its stems | app | Medium | P2 | Verified | 0.11.0-beta.2 | 0.11.0-beta.4 |
| [BUG-0323](bugs/app.md#bug-0323) | Dropping a version left sibling versions with stems in a deleted folder | app | Medium | P3 | Verified | 0.11.0-beta.2 | 0.11.0-beta.4 |
| [BUG-0324](bugs/app.md#bug-0324) | A project could be deleted while a detection ran on it | app | Medium | P3 | Verified | 0.11.0-beta.2 | 0.11.0-beta.4 |
| [BUG-0325](bugs/app.md#bug-0325) | A refused new project left its recording in uploads, and "²" gave a 500 | app | Medium | P3 | Verified | 0.11.0-beta.2 | 0.11.0-beta.4 |
| [BUG-0326](bugs/app.md#bug-0326) | Two bundle downloads at once could corrupt the zip | app | Low | P3 | Verified | 0.11.0-beta.2 | 0.11.0-beta.4 |
| [BUG-0327](bugs/tones.md#bug-0327) | A tone with a bad value was accepted and failed the build later | tones | Medium | P3 | Verified | 0.11.0-beta.2 | 0.11.0-beta.4 |
| [BUG-0328](bugs/audio.md#bug-0328) | On Windows, a tag or path in Japanese or Cyrillic broke reading ffmpeg's output | audio | Medium | P2 | Verified | 0.11.0-beta.2 | 0.11.0-beta.4 |
| [BUG-0329](bugs/psarc.md#bug-0329) | WwiseConsole inherited the console's stdin | psarc | Low | P3 | Verified | 0.11.0-beta.2 | 0.11.0-beta.4 |
| [BUG-0330](bugs/exe.md#bug-0330) | A components install step that stalled silently never timed out | exe | Low | P3 | Verified | 0.11.0-beta.2 | 0.11.0-beta.4 |
| [BUG-0331](bugs/exe.md#bug-0331) | Without WebView2 the .exe never shut down when the browser tab closed | exe | Medium | P3 | Verified | 0.11.0-beta.2 | 0.11.0-beta.4 |
| [BUG-0332](bugs/app.md#bug-0332) | Celery's hard time limit could leave a detection status stuck | app | Low | P4 | Fixed | 0.11.0-beta.2 | 0.11.0-beta.4 |
| [BUG-0333](bugs/editor.md#bug-0333) | A note selection and the ↑/↓ note carried over to the other track | editor | Medium | P2 | Verified | 0.11.0-beta.2 | 0.11.0-beta.4 |
| [BUG-0334](bugs/viewer.md#bug-0334) | Opening another project quickly could show the previous one's charts or recording | viewer | Medium | P2 | Fixed | 0.11.0-beta.2 | 0.11.0-beta.4 |
| [BUG-0335](bugs/editor.md#bug-0335) | The merge bar grid piled up listeners each time Editar info opened | editor | Low | P3 | Verified | 0.11.0-beta.2 | 0.11.0-beta.4 |
| [BUG-0336](bugs/viewer.md#bug-0336) | The 3D highway could start drawing after being closed while loading | viewer | Low | P4 | Verified | 0.11.0-beta.2 | 0.11.0-beta.4 |
| [BUG-0337](bugs/psarc.md#bug-0337) | Two songs whose names share the first 30 letters get the same song key | psarc | Low | P4 | Verified | 0.11.0-beta.2 | 0.11.1-beta.1 |
| [BUG-0338](bugs/tones.md#bug-0338) | A tone change does not follow a sync correction made in the same rebuild | tones | Medium | P3 | Verified | 0.11.0-beta.4 | 0.11.1-beta.1 |
| [BUG-0339](bugs/sync.md#bug-0339) | A section marker does not follow a sync correction made in the same rebuild | sync | Medium | P3 | Verified | 0.11.0-beta.4 | 0.11.1-beta.1 |
| [BUG-0340](bugs/app.md#bug-0340) | With a newer FastAPI an absent default-yes form field reads as no (batch projects lose palm mutes; reload ignores the file's audio) | app | Medium | P2 | Verified | 0.11.0-beta.4 | 0.11.1-beta.1 |
| [BUG-0341](bugs/viewer.md#bug-0341) | Fretboard "All notes" with "only those matching the picked one" shows every note when no note is picked | viewer | Low | P3 | Verified | 0.11.1-beta.1 | 0.11.1-beta.2 |
| [BUG-0342](bugs/app.md#bug-0342) | Earlier jobs break when the work dir moves: bundle, recording, GP file and stems stored as absolute paths | app | Medium | P2 | Verified | 0.11.0-beta.4 | 0.11.1-beta.2 |
| [BUG-0343](bugs/import.md#bug-0343) | A chart whose GP track has no notes fails with a bare 'arrangement has no notes' that names neither the chart nor the track | import | Low | P3 | Verified | 0.11.0-beta.4 | 0.11.1-beta.2 |
| [BUG-0344](bugs/sync.md#bug-0344) | Creating a job from Songsterr fails with 422 when the video's bar marks start before the video (negative times) | sync | Medium | P2 | Verified | 0.11.0-beta.4 | 0.11.1-beta.2 |
| [BUG-0345](bugs/sync.md#bug-0345) | A tab imported from Songsterr drifts away from Songsterr's own recording: the tempo's decimals and mid-bar changes are lost | sync | High | P1 | Verified | 0.11.1-beta.1 | 0.11.1-beta.2 |
| [BUG-0346](bugs/sync.md#bug-0346) | After a Songsterr import, another file picked in step 1 keeps the tab's times, the video's audio and its start | sync | Medium | P2 | Verified | 0.11.1-beta.2 | 0.11.1-beta.3 |
| [BUG-0347](bugs/sync.md#bug-0347) | A failed Songsterr video fetch during the import says there are no videos and hides the retry | sync | Medium | P2 | Verified | 0.11.1-beta.2 | 0.11.1-beta.3 |
| [BUG-0348](bugs/sync.md#bug-0348) | A Songsterr video's audio downloaded by the button becomes the recording after the tab's tempo was chosen | sync | Low | P3 | Verified | 0.11.1-beta.2 | 0.11.1-beta.3 |
| [BUG-0349](bugs/sync.md#bug-0349) | A Songsterr tempo change at a position of 1 or more is placed at the bar's start without a word | sync | Low | P3 | Verified | 0.11.1-beta.2 | 0.11.1-beta.3 |
| [BUG-0350](bugs/viewer.md#bug-0350) | Clicking a note on the score lights the previous note on the fretboard too | viewer | Low | P3 | Verified | 0.11.1-beta.2 | 0.11.1-beta.3 |
| [BUG-0351](bugs/viewer.md#bug-0351) | The cursor and lit notes run ahead of the sound during playback, by the output latency | viewer | Medium | P2 | Verified | 0.11.1-beta.2 | 0.11.1-beta.3 |
| [BUG-0352](bugs/lyrics.md#bug-0352) | Lyrics of a Songsterr tab land later and later: a grace note in the vocal line gets no syllable | lyrics | Medium | P2 | Verified | 0.11.1-beta.3 | 0.11.1-beta.4 |
| [BUG-0353](bugs/lyrics.md#bug-0353) | Lyrics of a Songsterr tab follow the guitar's notes when the text comes in the guitar's part | lyrics | Medium | P2 | Fixed | 0.11.1-beta.4 | 0.11.1-beta.5 |
| [BUG-0354](bugs/viewer.md#bug-0354) | The song start field cannot be typed into: each key applies the value and the field rewrites itself | viewer | Medium | P2 | Verified | 0.11.1-beta.4 | 0.11.1-beta.5 |
| [BUG-0355](bugs/lyrics.md#bug-0355) | Lyrics drift further off along the song: a tied note in the vocal line takes a syllable | lyrics | Medium | P2 | Verified | 0.11.1-beta.4 | 0.11.1-beta.5 |
| [BUG-0356](bugs/viewer.md#bug-0356) | Chords lag when they play on the score, and a six-string chord sounds only three strings | viewer | Medium | P2 | Verified | 0.11.1-beta.4 | 0.11.1-beta.5 |
| [BUG-0357](bugs/viewer.md#bug-0357) | The song start field lost its fine -/+ adjustment | viewer | Low | P2 | Verified | unreleased | 0.11.1-beta.5 |
| [BUG-0358](bugs/viewer.md#bug-0358) | The Score's Audio panel opened past the left edge of a narrow window | viewer | Low | P2 | Verified | 0.11.1-beta.5 | 0.12.0-beta.1 |
| [BUG-0359](bugs/game.md#bug-0359) | The game stopped the song 1 s after the last note, cutting the rest of the recording | game | Medium | P2 | Verified | 0.12.0-beta.1 | — |
| [BUG-0360](bugs/tones.md#bug-0360) | Using a detected tone one by one listed every project tone as switchable, so a rebuild with 5 or more was refused | tones | Medium | P2 | Fixed | 0.12.0-beta.1 | — |
| [BUG-0361](bugs/tones.md#bug-0361) | A Bass chart with no tones of its own took the song's guitar tones (a guitar amp on the bass) | tones | Medium | P2 | Verified | 0.12.0-beta.1 | — |
| [BUG-0362](bugs/psarc.md#bug-0362) | Two notes on one string within 30 ms became a chord with a dangling link and slide, and Rocksmith crashed on play | psarc | High | P1 | Verified | 0.11.1-beta.2 | — |
| [BUG-0363](bugs/viewer.md#bug-0363) | Every rebuild of a project whose first chart is a bass at A220 was refused: cent_offset -1200 | viewer | High | P1 | Verified | 0.10.0-beta.10 | — |
| [BUG-0364](bugs/lyrics.md#bug-0364) | An LRC with a time on every word showed '<mm:ss.xx>Word' and spread the words evenly over the line | lyrics | Medium | P2 | Verified | 0.10.0-beta.1 | — |
