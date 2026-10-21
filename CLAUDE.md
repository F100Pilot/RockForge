# CLAUDE.md

Guidance for working in this repository. Read this before making changes.

## What RockForge is

A pipeline that turns an audio recording (or a Guitar Pro file) into a Rocksmith
2014 CDLC arrangement bundle, importable into DLC Builder. It is deliberately
**honest about limits**: every ML stage carries an explicit confidence label and
nothing is silently defaulted. Read `docs/RELATORIO-TECNICO.md` and
`docs/research/` for the grounding (with sources) behind every technical claim.

See `TODO.md` for proposed (not yet implemented) future features.

## Architecture (Clean Architecture — respect the layering)

```
domain/         pure music model (Arrangement, TabNote, Tuning, TempoMap) — no I/O, no frameworks
application/    ports.py (Protocols) + gp_pipeline.py (use case) — orchestration only
infrastructure/ adapters implementing the ports (Demucs, librosa, ffmpeg, Wwise, RS XML, DB)
interfaces/     api/ (FastAPI) and worker/ (Celery) — the boundary; wiring lives here
```

Rules:
- `domain/` and `application/` must not import frameworks or `infrastructure/`.
  Each ML stage is a swappable `Protocol` in `application/ports.py`.
- **The API is `interfaces/api/app.py` + `schemas.py` + `routers/`.** `app.py`
  holds what the endpoints share (`settings`, `_session_factory`, the
  `_enqueue*` dispatchers, the heartbeat/idle-shutdown state, the common
  helpers, the middleware) and the two lifecycle endpoints; each group of
  endpoints is a `routers/<group>.py` (`imports`, `jobs`, `sync`, `charts`,
  `lyrics`, `tones`, `stems`, `analysis`, `gp_export`, `delivery`, `settings`,
  `web`) whose code reads app.py's names as **`api.<name>`** (`from
  rockforge.interfaces.api import app as api`), looked up when a request runs.
  Never `from …api.app import X` or `from rockforge.config import settings` in
  a router: the API tests reload app.py and `monkeypatch.setattr(app_module,
  …)` its state, and a router holding its own reference silently keeps the
  original — a patch that misses does not fail, the test just runs real code.
  `tests/test_api_routers.py` enforces it (and that every router is
  included). The pydantic models live in `schemas.py`, which nothing reloads:
  a model defined in app.py would be re-created on each reload and a model
  elsewhere naming it in a field would then refuse its instances (found the
  hard way, `TrackTonePlanOut.changes`). A new endpoint goes in its group's
  router; a helper two groups share stays in app.py.
- Heavy imports (torch, demucs, whisperx) are deferred into the Celery worker's
  builders (`_build_gp_use_case()`, `_build_detection()`, `_build_stem_separator()`)
  — never import them at module top level in the API path, or the web process
  pays the cost and may fail without the ML extra.

**`VocalEvent`/`PackagingResult` live in `application/ports.py`, not
`infrastructure/`.** They used to be defined inside
`infrastructure/rsxml/vocals.py` / `infrastructure/packaging/dlcbuilder.py`,
which forced `ports.py` (and `gp_pipeline.py`) to import them back FROM
infrastructure — the inverted, forbidden dependency direction: a `Protocol`
whose own signature imports its adapter's module isn't an abstraction the
adapter can be swapped behind. Both are plain data (no I/O, no framework),
so they belong on the application side of the boundary; infrastructure now
imports them from `application.ports`, same direction as everything else.
`gp_pipeline.py` keeps two narrow, deliberate exceptions to the no-infra-import
rule: `infrastructure/gpimport/parser.py` (`inspect_gp`/`parse_gp_track`) and
the lyric-format functions in `infrastructure/rsxml/vocals.py`
(`parse_lyrics`/`distribute_syllables`/`enforce_max_line_words`) are core,
deterministic, single-implementation format parsers — not a swappable ML
stage like `Packager`/`LyricTranscriber`/`AudioNormalizer` — so putting them
behind a `Protocol` would be indirection with no second implementation to
justify it. `tests/test_architecture.py` guards both: `ports.py` must import
zero `infrastructure/` modules, and any OTHER `application/` file's
infrastructure imports must be on the explicit allowlist above, so a future
accidental import (or an unnoted new exception) fails CI instead of quietly
re-inverting the dependency.

## The generation path

> **Audio→note transcription was removed.** RockForge previously had a second
> path that turned a raw MP3 into an arrangement via Basic Pitch (`pipeline.py`,
> the fret mapper, the role splitter, `clean_transcription`/`suggest_tuning`,
> `/jobs/upload` + `/jobs/upload-split`, YouTube ingestion). Basic Pitch's
> accuracy on a distorted electric-guitar mix was never good enough to be
> trustworthy, so the whole path was deleted to slim the codebase. What remains
> that still uses the recording: **stem separation** (`/jobs/{id}/separate-stems`),
> **tone detection** (`/detect-tones`), **lyric detection** (`/detect-lyrics`),
> and the per-point tempo / tuning-cents helpers — all operate on an
> existing GP job's recording, none transcribe notes. `[ml]` (Demucs/librosa)
> is still needed for those; `basic-pitch`/`onnxruntime` and the old
> `[youtube]` INGESTION are gone (today's `[youtube]` extra only fetches the
> audio of the one video Songsterr's bar times belong to — see below).

**Guitar Pro** (`gp_pipeline.py`): notes/frets/techniques/sections come exact
   from the GP file; audio sync is a manual offset. High fidelity, preferred
   when a GP file exists. Guitar charts take 6-string tracks; a 4/5-string bass
   track becomes the Bass arrangement (below). Two parsers behind one API (`inspect_gp` /
   `parse_gp_track` dispatch on format): **GP3/GP4/GP5** binary via PyGuitarPro
   (`parser.py`), and **GP7/GP8 (`.gp`)** via a native GPIF/XML parser
   (`gpif_parser.py` — the `.gp` is a ZIP whose `Content/score.gpif` is XML, so
   no extra dependency). Only **GP6 (`.gpx`)** — a proprietary binary container —
   is unsupported; export it as GP5 or GP7.

   **Guitar Pro 8 audio sync (`SyncPoint` automations) drives the timing.** GP8
   aligns a score to its audio track WITHOUT touching the tempo markings: the
   authored `<Tempo>` stays one number and the alignment lives in
   `MasterTrack/Automations/Automation[Type=SyncPoint]`, each `<Value>` carrying
   `<BarIndex>`/`<BarOccurrence>`/`<FrameOffset>` (samples at 44.1 kHz) minus
   `<BackingTrack><FramePadding>`. Guitar Pro then SHOWS a varying BPM computed
   from the points. Reading only `Type=Tempo` locked such a file to its header
   tempo, so a chart the user had synced perfectly in Guitar Pro drifted in
   RockForge. `gpif_parser._sync_points` + `sync_map.audio_clock` map each span between
   neighbouring points linearly onto the audio (format and semantics from
   alphaTab's `GpifParser.ts`/`MidiFileGenerator.ts`; alphaTab holds a constant
   BPM after each point instead — identical whenever a span has no tempo change
   of its own). The result is **relative to bar 1**, so `offset_s` keeps its one
   meaning; the absolute bar-1 position is `sync_start_s(path)` (NEGATIVE when
   bar 1 comes before the audio starts — alphaTab/PDF-to-GP5 save such a start
   as a positive `<FramePadding>`; `offset_s` accepts down to `MIN_OFFSET_S`
   = -60 s and the lead-in pad grows by it, so the chart keeps its place;
   clamping it to 0 had put every note that much late — the sync view in
   `web/app.js` must not clamp it either: `setOffsetLive` did, so the preview
   padded the audio by 2 s instead of 4.15 s and a rebuild sent offset_s 0;
   guarded by `test_the_web_sync_view_keeps_a_negative_offset`), returned by
   `/gp/inspect` and pre-filled into the wizard's offset field, exact when the
   uploaded recording IS the audio GP was synced to. A point's
   `<BarIndex>`/`<BarOccurrence>` names the pass of a written bar, which the
   unrolled bars below resolve; a pass never played, and a point earlier in the
   audio than its predecessor, are dropped — both counted in the warnings. The
   synced file's `average_bpm` is what actually plays, not the header. **Gradual
   tempo ramps are NOT modelled** (GPIF `<Linear>true`, GP5's MixTableChange
   duration): alphaTab reads the flag but its timing ignores it, so there is no
   citable reference for how Guitar Pro interpolates, and they are read as steps.
   Guarded by `test_gp8_sync_points_*` and
   `test_gp_inspect_reports_where_a_gp8_synced_file_starts`.

   **Repeats, voltas and jumps are unrolled, in alphaTab's order.** Both parsers
   lay the bars out as PLAYED (`gpimport/playback.py`, a port of alphaTab's
   repeat groups and `MidiPlaybackController`: `|: :|` with counts, nested
   repeats and multiple closings, voltas as a bitmask of passes, D.C./D.S./al
   Coda/al Fine/Da Coda). **One departure from alphaTab, on the return after a
   D.C./D.S.**: alphaTab takes no repeats there but plays EVERY volta (a 1st-time
   bar sounds again before the 2nd); the usual convention (Gould, *Behind Bars*)
   is no repeats and the LAST ending only, and that is what is played (a bar
   after a volta bar without one of its own stays in that ending). Neither GP
   format records a "repeats after the jump" choice (no field in GP3-5, nothing
   in GPIF's `<Directions>`), so when the convention changes what is heard
   (`jump_skips_repeats`: the return passes a repeat end or a volta) both parsers
   add a warning saying which convention was assumed (user feedback, 2026-10-16).
   Guarded by `test_after_a_jump_no_repeats_and_only_the_last_ending`,
   `test_a_jump_that_returns_through_no_repeat_needs_no_convention` and
   `test_gp5/7_says_which_convention_it_assumed_after_a_jump` (mutation-checked).
   Bar N of the chart — beat grid, sections, per-bar
   times (Songsterr's are per played bar), tempo corrections — is the N-th bar
   HEARD; a tempo automation applies on every pass of its written bar; a lyric
   line starts again on every pass of the bar it starts on. `tempo_writer` maps
   a played bar back to its written bar and refuses different tempos for passes
   of the same written bar (the file holds one). A score without repeats is
   untouched. Guarded by `test_gp_playback.py` (orders checked against alphaTab
   1.8.4's MidiFileGenerator, and its `directions.gp5`/`.gp` test files).

   **Three-point bends are read as alphaTab plays them** (`alphatab_bend`,
   in `domain/alphatab.py` — an MPL-2.0 file, see the licence section,
   alphaTab 1.8's `Note.finish`, in both parsers): the middle point stays only
   when it is a peak (a bend-and-release); otherwise the bend is a straight line
   from origin to destination — "up by the middle of the note, then held" rises
   across the whole note, and the same for a pre-bend released. Other point
   counts are untouched. A plain rise from unbent at the attack to the peak at
   the end (`is_plain_rise`) is written to the XML/SNG as the single point at the
   note's end, the DLC Builder shape the game already ramps across the note — no
   bend point at the attack. A flat pre-bend keeps its curve (`is_composite_bend`
   is true for a curve bent at the attack): charted bent from the attack to the
   end, as alphaTab plays it, not a rise. Guarded by
   `test_a_pre_bend_is_bent_from_the_attack`,
   `test_a_pre_bend_is_bent_at_the_attack_in_sng_and_xml`,
   `test_alphatab_bend_reads_three_points_as_alphatab`,
   `test_gp7_bend_up_and_held_is_a_rise_across_the_note` and
   `test_a_plain_rise_is_the_single_point_at_the_note_end`.

   **The recording INSIDE the `.gp` is the one to use.** A GP8 file with an
   audio track carries its own copy (`<BackingTrack>` Enabled + Source=Local →
   `<Assets><Asset id=AssetId><EmbeddedFilePath>`), and the sync points
   describe THAT copy, not whatever file was imported. The user's case proved
   it matters: `teaqu/guitar-pro-youtube-sync` (which built their file from
   Songsterr's human-marked per-measure video timestamps) **trims the video's
   intro to bar 1 before embedding** (`ffmpeg -ss <bar-1 time> -c copy`), so
   uploading the untrimmed download put the chart exactly one bar late — a
   constant offset, which is why one "Início" nudge fixed the whole song.
   `gpif_parser.embedded_audio`/`extract_embedded_audio` find and copy it out
   (declared-size cap like `score.gpif`; the ZIP member name is only ever READ,
   never used as an output path); `/gp/inspect` returns `embedded_audio`
   `{name, size_bytes}` and `/jobs/gp` takes `use_embedded_audio=true` with no
   `audio` upload at all. The wizard's step 3 ticks "🎧 Usar o áudio que vem
   dentro do ficheiro GP" by default when present (hiding the upload and its
   `required`). Anything short of a real, local audio member is "none",
   never an error. **Every path that gives a job its recording honours it**,
   not only the wizard ("porque é que continuas a não aproveitar o mp3 do
   ficheiro gp?" — the user's file was detected fine; "Lote (álbum)" and
   "Recarregar ficheiro GP" simply never asked): `/jobs/gp` records
   `params["recording_from_gp"]` (`JobOut.recording_from_gp`), `/reload-gp`
   takes the new file's audio (below), and the batch reads each GP as it is
   picked (below).

   **Detection is tolerant, and says where the audio is when it is not
   inside** (`backing_track` → `BackingTrackInfo`). "Carreguei um ficheiro gp
   com áudio mas não foi detetado": the check wanted an ENABLED track, one of
   six extensions and the exact member name, so one detail hid the audio. Now
   an audio track switched off in Guitar Pro still names the audio the sync
   points describe and is used (`disabled`, said in the wizard); the asset is
   found by its id, else any declared asset, else the ONE audio file in
   `Content/Assets`, matched regardless of case/leading slash (the member name
   is still only READ); `.opus/.webm/.aac/.mp4/.wma` count (a YouTube download
   embedded as-is). When it is not inside: a **YouTube** source (GP8 can play
   the audio from a video — its sync points then describe THAT video) is
   returned as `backing_youtube_url`, and the wizard puts it in "Não tens o
   áudio?" and downloads it by itself, like after a Songsterr import; a file
   elsewhere on disk is `backing_external_path`, named in step 3 so the user
   knows which file to upload. The actual file was never seen here (the user
   did not attach it), so this covers every way the old check could miss one,
   not a reproduction. **A member with no extension is recognised by its
   bytes** (`audio_suffix_from_bytes`: ID3/MPEG sync, ADTS, OggS, ftyp, RIFF
   WAVE, fLaC, AIFF, EBML, ASF): the user's screenshot finally showed the
   member — "Content/Assets/backing-track", no extension — which the name
   check skipped and then offered as a file OUTSIDE the .gp to go and upload
   ("continua a não detetar que o GP file tem o mp3 incluído"). Only
   extension-less or `.bin`/`.dat` names are sniffed (a file that names itself
   something else is still not audio), the extracted copy takes the sniffed
   suffix, and a `Content/…` path is never reported as `external_path`.
   Guarded by `test_an_embedded_recording_with_no_extension_is_recognised_by_its_bytes`
   (six formats, mutation-checked) and
   `test_an_extensionless_member_that_is_not_audio_is_not_taken_for_one`; the
   user's Ocean Eyes GP8 re-packed with its MP3 renamed `backing-track` goes
   through `/gp/inspect` (embedded_audio found) and `/jobs/gp` with
   `use_embedded_audio=true`, and ffmpeg decodes the extracted 3:16.
   Guarded by `test_the_audio_embedded_in_a_gp8_file_is_*`,
   `test_no_usable_embedded_audio_is_none_never_an_error`,
   `test_the_embedded_audio_is_found_despite_details_that_used_to_hide_it`
   (disabled / .opus + case + slash / an undeclared single asset —
   mutation-checked), `test_audio_that_is_not_in_the_file_says_where_it_is`,
   `test_gp_inspect_says_where_the_audio_is_when_it_is_not_inside`,
   `test_a_gp8_job_can_use_the_audio_embedded_in_the_file` and
   `test_a_gp_job_without_any_recording_is_refused_clearly`; the wizard with
   Playwright on a GP8 whose audio is a YouTube link (link filled, download
   run, upload hidden).

   **Songsterr's per-measure timestamps (`bar_times`) — fetched rather than
   estimated.** Songsterr stores, per song, the instant every measure starts
   in one or more YouTube videos (marked by people, or — for a tab Songsterr's
   AI made, the user's correction 2026-10-21 — presumably generated); that
   is the whole reason a `teaqu/guitar-pro-youtube-sync` file lines up
   "perfectly", and the opposite of the automatic estimators that were removed
   (see below). `infrastructure/songsterr.py` fetches ONLY those times
   (`/api/meta/{id}` → `revisionId`, then `/api/video-points/{id}/{rev}/list`),
   with **`requests` and its default headers — the reference tool's exact
   client** (see the 403 note below), ordering the videos the way that
   tool picks them. The recording has to be **that same YouTube video's audio**
   — Songsterr's own audio is a different recording and does NOT match the
   times (the user plays it in sync with the tab on Songsterr, so it is the
   tab's own tempo map that fits it: see "the tab's OWN tempo map" below) — so the wizard can fetch it (`youtube_audio`, below) or take an MP3
   the user converted from it. `GET /songsterr?song=` returns the
   videos with their points (the wizard offers it as a closed, optional
   "➕ Extra" in step 3, so the default flow is untouched) (422 for a link we cannot read, **502** when the
   undocumented API changed or is unreachable — never a 500); the wizard's
   step 3 lets the user pick a video, pre-fills "Início da música" with bar 1's
   instant in that video, and sends the points back as `/jobs/gp`'s
   `bar_times` (a JSON list, validated in `_parse_bar_times` because multipart
   bypasses the models: finite, ≤ 10 000 entries). **Negative times are
   points like any other** (GitHub PR #5, mongrelx: a count-in marked before
   the video starts, e.g. bars 1-8 at -15.12 … -0.12 s): the timeline is
   relative to bar 1 and the wizard's start is bar 1's own negative mark,
   which `offset_s` takes (down to `MIN_OFFSET_S`) as for a GP8 file whose
   bar 1 precedes its audio. The PR first SKIPPED them; measured on an invented
   GP5 whose count-in was marked 650 ms slower than the rest, that put the
   whole song 650 ms early (bar 1 became an extrapolation of the later marks
   while `offset_s` stayed the real mark), so they are kept. Guarded by
   `test_bar_times_negative.py` (the end-to-end placement fails with the skip
   back). They live in
   `params["bar_times"]`, so rebuild/reload forks inherit them, and reach
   `GpJobSpec.bar_times` → `parse_gp_track(..., bar_times)` in BOTH parsers.
   The re-timing is the SAME machinery as GP8's sync points, now shared in
   `gpimport/sync_map.py` (`audio_clock`/`relative_to_bar_one`/
   `bar_time_points`), applied at parse time — before `tempo_scale` and the
   anchor stages, exactly where the GP8 sync sits, so a later BPM change or
   anchor round composes the same way it does for any file. External bar times
   **win over** a file's own GP8 sync points (they were chosen for this
   recording). Honest limits, all surfaced: the API is undocumented; measure N
   must be measure N (the GP has to be that Songsterr tab — a bar-count
   mismatch is a warning, not silence); the times belong to one video's audio,
   so a trimmed MP3 needs its start moved. **Never verified against the real
   API from here** (the sandbox's network policy blocks songsterr.com) —
   TESTING.md §7d-quinquies. Guarded by `test_songsterr.py`,
   `test_gp5_bar_times_*`, `test_bar_times_retime_a_gp7_file_and_win_over_its_own_sync_points`,
   `test_bar_times_reach_the_parser_and_retime_the_built_chart` (mutation-checked)
   and `test_songsterr_lookup_*` / `test_*bar_times*` in `test_api.py`.

   **Or no Guitar Pro file at all: the tab imported from Songsterr
   (`/songsterr/import`).** Step 1 of the wizard also takes a Songsterr link.
   `songsterr.fetch_tab` reads `/api/meta/{id}` (revision, `image` hash, the
   track list) and then each track's JSON **part** — what Songsterr's own player
   draws — from its CloudFront distributions (`part_urls`: the `image` layout,
   a `-stage` one, and the legacy `part/{rev}/{i}` one; each distribution is
   tried in turn because the others answer 403; hostnames read from
   `teaqu/guitar-pro-youtube-sync`, which found them in the player's bundle). A
   track that will not download is NAMED in the warnings, not fatal; none at
   all is a 502. `gpimport/songsterr_gp.write_songsterr_gp5` writes the parts as
   a **GP5 with PyGuitarPro** — not GP7 like that tool (and none of its code:
   it carries no licence) — because GP5 is what our importer and
   `arrangement_writer` already speak, so the file lands in `work_dir/gp/` like
   an upload and `/songsterr/import` answers exactly `/gp/inspect`'s shape
   (`_inspect_stored_gp`, shared) plus `songsterr_song`/`import_warnings`.
   Nothing downstream knows the difference: track choice, bar times, reload,
   export all apply. Mapping details that matter: Songsterr lists tuning and
   numbers strings from the HIGHEST (its string 0 = GP5 string 1); `hp` marks
   the TARGET of a hammer/pull while GP5 marks the ORIGIN (the previous note on
   that string); bend `position` 0..60 → 0..12 and `tone` 50 = one semitone →
   value 2 (what `parser.py` reads as `value / 2` semitones); every
   `MeasureHeader.start` is set by hand from the time signatures, so an
   under-/over-filled Songsterr bar cannot push the next one; tempo = the first
   track's `automations.tempo` (song tempo + a mix-table change per later
   measure, as `tempo_writer` does). Honest losses, all counted in the report
   and shown in the wizard: drums skipped, **grace notes dropped** (a GP5 grace
   is an ornament on the NEXT note — written as beats they would push the
   rhythm late), a mid-bar tempo change moved to its bar's start in the GP5
   (the tab's tempo map, below, keeps it at the bar lines), text GP5
   cannot store (it is cp1252 — a Cyrillic title used to abort the whole
   write) turned into "?" by `_gp5_text`. **Lyrics come along**: a part's
   `newLyrics[]` `{text, offset}` (0-based bar) becomes the GP5 song lyrics
   bound to THAT part's track (`trackChoice`, 1-based) — normally the vocal
   line, which is written as a track of its own (a 1-string one is fine) — so
   the importer times each syllable on that line's notes, below; five lines
   at most (GP5's limit, the rest counted); lyrics on a part that could not be
   written fall back to track 1 with a warning. The wizard then sees
   `has_lyrics` and does not preselect an LRCLIB text over them. Guarded by
   `test_songsterr_lyrics_are_written_on_the_part_that_sings_them`,
   `test_lyrics_on_a_part_that_could_not_be_written_fall_back_and_say_so`,
   `test_text_gp5_cannot_store_does_not_abort_the_import` and
   `test_a_songsterr_tab_with_lyrics_is_imported_with_them`. After an import the wizard fills step
   3's Songsterr link and fetches the videos, so the per-measure times of the
   SAME song are one pick away — tab and times from one source is exactly what
   makes "measure N is measure N" hold — and then fetches the default video's
   audio too, so one link gives tab, times AND recording.

   **The tab's OWN tempo map is the other timing, for the MP3 Songsterr plays**
   ("Tenho usado sempre a gravação presente no songsterr (mp3)", 2026-10-21 —
   the tab drifted in RockForge while it played in sync on Songsterr). A tab
   whose tempo follows a recording (one Songsterr's AI made from it) carries
   decimals and mid-bar changes; GP5 holds a whole BPM at a bar's start, and
   `_int()` even CUT 117.85 to 117, so the chart drifted bar by bar.
   `write_songsterr_gp5` now rounds the GP5 tempo and returns the exact map as
   `report.bar_times` (`tab_bar_times`, pure: per bar, quarters from the
   signature, `{measure, position, bpm}` with `position` read as the fraction
   of the bar — what the reference tool hands GPIF's `<Position>`; any value
   outside (0, 1) is the bar's start, no other unit having been seen), plus
   `tempo_count`/`tempo_decimal`. `/songsterr/import` answers them
   (`songsterr_bar_times`, `songsterr_revision`, `songsterr_tempo_count`,
   `songsterr_tempo_decimal`), and step 3 shows **"Com que gravação vais tocar
   esta tab?"** (`#songsterrChoice`, ⓘ `songsterr-sync`), each option saying
   which recording it fits: **the Songsterr recording or another that follows
   the tab** (`songsterrSyncMode = 'tab'`: those times go as `bar_times` with
   `bar_times_source` `songsterr-tab:<song>:<rev>` — the same `sync_map`
   machinery, so every bar starts where the player starts it; the user's own
   file and "Início" at bar 1; the video block hidden, a video's auto-download
   dropped, the video's start taken out of "Início") or **a YouTube video's
   audio** (the old flow). The choice is remembered (`localStorage`
   `rf-songsterr-sync`, default the video); with no videos only the tab. A file
   of the user's own while a video's times are in use shows
   `#songsterrAudioWarn` with "Usar o andamento da tab"
   (`refreshSongsterrAudioWarn`, also for a plain GP with the Extra's times).
   `JobOut.sync_source` is then `songsterr_tab` (`_sync_source`,
   `SONGSTERR_TAB_SOURCE`), worded on the sync card and the checklist. Inside
   a bar the GP5's own proportions are mapped linearly, so a mid-bar change is
   exact at the bar lines only. Where bar 1 sits in Songsterr's MP3 is not
   known here — the user sets "Início". Guarded by
   `test_the_tabs_tempo_map_gives_each_bar_its_exact_start`,
   `test_a_tab_that_follows_a_recording_keeps_its_tempo_to_the_decimal`
   (rounding and the mid-bar rule mutation-checked) and the `songsterr_tab`
   line of `test_a_chart_says_why_it_counts_as_in_sync`; with Playwright on a
   live server (Songsterr faked, PT 1440 / EN 760 px): video by default, own
   file → warning → "Usar o andamento da tab" → a real build whose bars sit on
   the tab's times to the millisecond, the choice remembered with no download,
   no page errors. Not tried with a real Songsterr MP3 from here.
   **An independent review (a subagent, 2026-10-21) found three wizard paths**,
   fixed: a new file in step 1 after an import kept the tab's state
   (`forgetSongsterrForNewFile`: the tab map, the video points, a Songsterr
   video's audio and the start it set — the video-points leak predated the
   choice); a failed `/songsterr` during the import read as "no videos" and
   hid the retry (`songsterrVideosFailed`: `#songsterrVideoFailed`, the block
   stays open, a successful "Procurar vídeos" re-applies the remembered
   choice); a download for a Songsterr video ending after "tab" was chosen
   became the recording (`forVideoTimes`, auto or by the button), and
   switching back started a second download (`ytDownloading`). A `position`
   ≥ 1 is counted and warned (`tempo_position_unknown`). Browser-only paths,
   verified with Playwright (each of the three, no page errors); the backend
   rule by `test_a_tempo_change_at_a_position_that_cannot_be_read_is_said`
   (mutation-checked). Still open, not seen: whether Songsterr's parts carry
   repeats the GP5 (and the reference tool) drop.

   Never run against the real Songsterr from here (blocked) — TESTING.md
   §7d-quinquies. Guarded by `test_songsterr_gp.py` (a note-for-note round trip
   through `parse_gp_track`: ties, triplets, dead notes, hammer target, bend,
   palm mute/vibrato, slide, sections, tempo change, odd meters, an empty bar,
   drums skipped), the `fetch_tab` tests in `test_songsterr.py` and
   `test_a_songsterr_tab_becomes_a_gp_file_the_wizard_can_use`. Verified with
   Playwright end to end (Songsterr answers faked): import → tracks → step 3
   with the video's times → a real build whose bars sit on those times.

   **Or a PDF or a picture of the tab (`/pdf/import`) — the user's own
   PDF-to-GP5 converter, installed as a package.** "Quero introduzir o
   programa PDF-to-GP5 no RockForge": only the CONVERTER came in (its player,
   library and YouTube duplicate RockForge's), and PDF-to-GP5 stays the one
   place it is developed. That repository's `pyproject.toml` describes a
   package that installs its `app/` folder under the name `pdf_to_gp5` (the
   converter imports its own modules relatively, so it works under any name —
   its `tests/test_packaging.py` keeps every subpackage listed and `app/` free
   of absolute self-imports); nothing about running PDF-to-GP5 changed. Here
   it is the `[pdf]` extra, `pdf-to-gp5[ocr] @ git+…@<commit>` — **pinned to a
   commit**: to take PDF-to-GP5's improvements, move the commit (start.bat
   reinstalls when `pyproject.toml` changes). `gpimport/pdf_import.py` calls
   it exactly as PDF-to-GP5 calls itself: `sandbox.run_isolated` parses each
   file in a child process with a hard timeout and a memory limit (a crafted
   PDF is untrusted input) and answers in JSON, never pickle; the child writes
   its warnings and errors in RockForge's language (`pdf_to_gp5.i18n.use`
   with `i18n.current()`). Files: PDF or PNG/JPEG/WebP by their BYTES, never
   the name, one per track in order, ≤ 7, 10 MB each / 40 MB total
   (PDF-to-GP5's own limits). The GP5 lands in `work_dir/gp/` like an upload
   and the answer is `/gp/inspect`'s shape (`_inspect_stored_gp`) plus
   `pdf_files` and `import_warnings` — the Songsterr import's pattern, so the
   wizard, the job and every later tool see an ordinary GP file. Repeats are
   left as written (RockForge unrolls them, `playback.py`). 503 without the
   extra (naming the install), 413/415 for a file it would not take, 422 with
   the converter's own message. UI: step 1's file drop takes `.pdf/.png/.jpg/
   .webp` too (`multiple`; several GP files are refused), `importPdfTab` shows
   the progress in `#pdfImportInfo`, and step 2's `#gpImportNote` says where
   the file came from and the conversion's warnings (Songsterr's too — step 1
   is out of sight once the wizard advances). ⚙️ Software externo has a
   "Conversor de PDF (PDF-to-GP5)" row (with/without OCR). **start.bat
   installs `[pdf]` in a step of its own** that only warns on failure — it
   comes from GitHub and needs git, and a failed fetch must not stop the rest
   of RockForge from starting; it is retried on every start until
   `import pdf_to_gp5` works. **`multiprocessing.freeze_support()` is the
   first line under `__main__` in `start_standalone.py`**: frozen, the
   converter's child process is the `.exe` itself, which without it would
   open a second RockForge (guarded by
   `test_a_frozen_child_process_runs_its_work_instead_of_a_second_app`); the
   converter inside the `.exe` was NOT verified (OCR certainly is not there:
   the spec excludes numpy). CI installs `[pdf]` and checks the import, so the
   real conversion tests never skip silently. PyGuitarPro: PDF-to-GP5 pins
   0.9.3 for its app; its converter tests (258) pass on RockForge's 0.11.
   Guarded by `test_pdf_import.py` (the kind of file from its bytes, the
   missing extra, a hand-written text-tab PDF converted for real into a GP5
   whose notes `parse_gp_track` reads back, and the user's language reaching
   the child — mutation-checked) and
   `test_a_pdf_of_the_tab_becomes_a_gp_file_the_wizard_can_use`; with
   Playwright on a live server: a bad PDF refused with the converter's
   message, an invented riff's PDF → step 2 (its track, the note) → a real
   build whose 12 notes are the riff's.

   **Bars whose rhythm the converter ESTIMATED become links on the score.** In
   a part that prints rhythm, a bar where PDF-to-GP5 could not read it falls
   back to the note spacing; its report names those bars per track
   (`rhythm_estimated_bars`, from PDF-to-GP5 01d9e79). They are the ones to
   check before trusting the chart, so `pdf_import.estimated_bars_as_played`
   turns them into chart bars: the converter numbers WRITTEN bars and the
   chart PLAYED ones (repeats unrolled, `parser._as_played`), so
   `parser.bars_as_played` (the same `playback_order`) maps each to every
   pass — a repeated estimated bar is one link per pass, each opening that
   exact pass. Only for a track with printed rhythm (a text tab is estimated
   throughout: nothing stands out), and a file that will not read back gives
   no hint rather than failing the import. `/pdf/import` answers them as
   `estimated_bars` (track index → bars); the wizard keeps them
   (`wzEstimatedBars`) and hands them to `/jobs/gp` as a JSON form field,
   checked like `bar_times` (`_parse_estimated_bars`: digit keys < 64, bars
   1…10000) and stored as `params["estimated_bars"]` (string keys, as JSON
   keeps them). `/jobs/{id}/arrangements` answers each arrangement's own list
   (`ArrangementOut.estimated_bars`) through `_track_of_kind`, which mirrors
   `gp_pipeline`'s slots — **a lone Lead is built as Combined**, so Combined
   falls back to `lead_track` when it is the only slot. `/reload-gp` drops
   them (they described the old file); a rebuild keeps them. UI:
   `renderEstimatedBars` (called from `showArr`) fills `#barEstimatedRow`,
   right above the score — not in "Sincronizar por compasso", which sits
   folded in "Mais opções" — one button per run of bars; `goToBar` puts the
   cursor on the bar's downbeat as it sits now (`arrangementDisplayTime`, live
   sync included), centres it and selects it in the bar-sync selector.
   Guarded by `test_estimated_bars_are_renumbered_as_the_chart_plays_them`,
   `test_no_estimated_bars_when_there_is_nothing_to_point_at` and
   `test_the_bars_with_an_estimated_rhythm_reach_the_viewer`; with Playwright
   on a live server, the "5–6" link put the cursor on bar 5 (c.5).

   **`runtime_settings` reads `config.settings` at call time**, never a
   `settings` bound at import: the API tests `importlib.reload(config)`, so a
   module holding the import-time object reads another test's `work_dir` —
   adding one API test that imported it first made
   `test_a_diagnostics_row_is_in_english` read the "nowhere" folder
   `test_diagnostics` had saved.

   **The chosen video's audio, fetched (`/youtube/audio`, `youtube_audio.py`).**
   Without it the Songsterr import still needed one manual step — convert the
   video to MP3 by hand — and the user judged the feature not worth having
   without that step gone, so the earlier "no yt-dlp" decision was reversed at
   their request (2026-09). Scope is deliberately ONE video's audio: the client
   sends only an 11-character id (`VIDEO_ID`), we build the `youtu.be` URL, and
   yt-dlp runs as a **subprocess** with no stdin (the console-tool hard rule),
   `bestaudio` kept as-is (m4a preferred, no re-encode — the build's ffmpeg
   reads any of it), `--max-filesize`, a timeout, and the file it reports is
   only trusted if it is ours (`yt-<uuid>` in `uploads/`). yt-dlp is found like
   the ML stages find their interpreter (`ytdlp_command`: this process's module
   when not frozen, a `yt-dlp` program on PATH, else the configured
   `ml_python`), so the `.exe` works with any of them, and it is the optional
   `[youtube]` extra, unpinned above because YouTube breaks old releases.
   YouTube often refuses anonymous downloads; a 403 / "sign in to confirm"
   comes back as a 502 whose detail says so (`needs_cookies`), and the wizard
   offers `--cookies-from-browser` from a FIXED list (`COOKIE_BROWSERS`) — the
   same retry the reference tool offers. No yt-dlp = 503 naming the install;
   `/system-check` lists it (`_ytdlp`). `/jobs/gp` takes the result as
   `audio_token` (a bare `yt-…` name under `uploads/`, never a path), and
   `_sweep_orphan_youtube_audio` collects downloads an abandoned wizard left
   (same 24 h rule as the GP sweep, keyed on `Job.source`). UI: step 3's own
   **"Não tens o áudio?"** block (`#ytBlock`, a YouTube link + "Descarregar o
   áudio" + "Sessão do browser") — for ANY GP file, not only a Songsterr
   import: it used to live inside the Songsterr "Extra", so a user who only
   uploaded a GP5 (their own, from a PDF) never saw that a download existed
   ("quando só carrego um gp5, o mp3 não vem incluído"). `youtubeVideoId`
   takes the id out of any link shape (watch?v=, youtu.be/, shorts/, embed/,
   live/, music./m.) or a bare id, and only the id goes to the server as
   before. Picking a Songsterr video writes its link into that block and opens
   it; after an import the download runs by itself; audio fetched for another
   video is dropped when a Songsterr video is picked (its times would not
   match), and one downloaded from a different link while Songsterr times are
   in use says so; the block hides when the GP8 file's own audio is used; a
   fetched file hides and un-requires the upload like the GP8 embedded audio
   does. Honest limits: it
   is against YouTube's terms outside YouTube's own features — personal use,
   said in the ⓘ; never run against YouTube from here (blocked). Guarded by
   `test_youtube_audio.py` (the command, id/browser validation, no stdin, the
   untrusted reported path, 403 → `needs_cookies`, missing/hung yt-dlp),
   `test_a_youtube_videos_audio_becomes_the_projects_recording` and
   `test_fetched_youtube_audio_no_job_uses_is_swept`; the wizard flow (refusal
   → retry with a browser → switch video → build) with Playwright.

   **YouTube's JavaScript challenge: yt-dlp needs a solver AND a runtime.**
   The user's first real download failed where the reference tool, on the
   same machine and video, succeeded. The reference installs
   `yt-dlp[default]>=2026.8.19` (whose `[default]` brings `yt-dlp-ejs`, the
   challenge-solver scripts) and BUNDLES Deno; we asked for a bare
   `yt-dlp>=2024.1` and had no runtime, and yt-dlp enables only Deno by
   default. Without both, YouTube refuses in a way that reads like "log in",
   and `--no-warnings` hid the one line that said so ("No supported
   JavaScript runtime could be found"), so the UI sent the user to pick a
   browser session — and Chrome's cookies are then unreadable on Windows
   ("Failed to decrypt with DPAPI", yt-dlp#10927: Chromium's app-bound
   encryption). Now: `[youtube]` = `yt-dlp[default]>=2026.8.19`;
   `js_runtime_args` enables every runtime yt-dlp supports that is on PATH
   (deno/node/quickjs/bun, yt-dlp's own priority order and program names,
   `utils/_jsruntime.py`); warnings are kept; `classify_failure` reads ALL of
   stderr and names the missing runtime first (install Deno + the solver —
   a session would not help), then an unreadable Chromium session ("pick
   Firefox"), and only then the login case, printing each `ERROR` line once.
   With a session it also passes the reference tool's
   `--extractor-args youtube:player_client=default,web_embedded`. The ⚙️
   diagnostics row reports yt-dlp as missing without a JS runtime, and the
   solver as unknown (`None`) unless yt-dlp runs in this interpreter.
   Guarded by the runtime/classification tests in `test_youtube_audio.py`
   and `test_ytdlp_without_a_js_runtime_is_reported_missing`. **Confirmed
   working by the user (2026-09-27)** on their Windows machine after
   `pip install -U "yt-dlp[default]"` + `winget install DenoLand.Deno`: the
   Songsterr link → video times → the video's audio downloaded, no browser
   session needed. The sandbox itself still cannot reach YouTube or
   Songsterr, so CI only ever sees the fakes.

   **A capo is read and the frets are counted from the nut** (`strings.apply_capo`,
   both parsers; "It doesn't understand the capo", r/rocksmith 2026-10-15). Guitar
   Pro counts a note's fret from the capo (alphaTab: a string's pitch includes
   `staff.capo`; GP3-5 `Track.offset`, GPIF Staff `CapoFret`); Rocksmith counts
   from the nut, plays an open string at the capo (Rocksmith2014.NET
   `Midi.toMidiNote`) and carries the capo fret (`Arrangement.capo` → XML `<capo>`,
   SNG `CapoFret`, manifest). So every fretted note moves up by the capo, open
   strings stay 0, a note pushed past fret 24 is dropped and counted; chord
   templates' MIDI and names sound an open string at the capo (`chord_display(...,
   capo)`); the GP5 export writes it back; the viewer labels the staff "Capo N" and
   the synth plays open strings at it (`ArrangementOut.capo`, `noteMidi`). Not seen
   in game from here. Guarded by `test_capo.py`.

   **Tied notes** (GP `(17)` in parentheses — a held continuation, not a
   re-pick) are folded into the note they extend in BOTH parsers, never emitted
   as a second attack: GP5 via `NoteType.tie` (inline, tracking the last note
   per string), GP7 via `<Tie destination="true">` (`gpif_parser._merge_ties`).
   Skipping this makes "4 notes show as 5" and throws the rhythm off — guarded by
   `test_tied_note_extends_previous_not_new_attack` (GP5) and
   `test_gp7_tied_note_extends_not_duplicates` (GP7).

   **Only a HELD note gets a sustain** (`music.drop_short_sustains`, both
   parsers, before `apply_sustain_gap`): "every single note looks extended
   when they aren't" (a user's video, 2026-10-16) — every Guitar Pro note has
   a length, and writing each sixteenth/eighth's notated length as a sustain
   drew a tail on every note of a riff. A note shorter than `SUSTAIN_MIN_BEATS`
   (0.95) of the grid's beat around it is charted with sustain 0, unless its
   sustain carries something the game draws (`_needs_its_sustain`: a slide or
   unpitched slide, a link, a trill, a bend, vibrato, let ring, tremolo).
   Measured on the two hand-made Daughtry CDLC (seven charts, ~3500 notes at
   full difficulty): notes a sixteenth apart carry a sustain 4 % of the time,
   an eighth 8 %, a quarter 64 %, longer nearly always. A sustain set in the
   note editor is applied after, so it still wins. Guarded by
   `test_short_sustains.py` (each keep rule, the grid's own beat, a GP5 and a
   GP7 riff — mutation-checked); the user's file ("Behind", Kills Birds) went
   from every note sustained to 16/24/47 held notes on its three charts.

### The Bass arrangement (`ArrangementKind.BASS`)

"Implementa a faixa de bass" (2026-10-15). A fifth slot beside Lead/Rhythm/
Combo/alternates, encoded the way Rocksmith2014.NET/DLC Builder encode a bass
(read from its source, nothing guessed):
- **Names and routes**: ArrangementName 3 (`"Bass"`), ArrangementType 3,
  RouteMask 4, `pathBass=1` (pathLead/pathRhythm 0) in the XML and the manifest,
  asset `<key>_bass`, FullName/xblock `<Key>_Bass`, game name `BASS`, `.rs2dlc`
  Name 3 / RouteMask 4 / `BassPicked` false. `powerChords`/`openChords` are
  never set on a bass; a bass chord counts as a double stop.
- **Tuning** (`Tuning(bass=True)`, `Tuning.for_bass`): offsets are measured from
  E1 A1 D2 G2 (`BASS_STANDARD_MIDI`), and strings 4-5, which a bass does not
  have, copy string 3's offset — DLC Builder's convention (EOF writes them
  wrong). `string_count` is 4; `sounding_midi` gives the four real pitches.
  Chord templates come out an octave below the guitar's (Midi.toMidiNote with
  isBass). **Below -4 semitones** (B standard on a folded 5-string) DLC
  Builder's low-tuning fix (its checker's I41) applies: every string written
  +12 and the reference at 220 Hz (CentOffset -1200), so the game detects the
  notes; `gp_pipeline._tuning_for` does it and says so in the warnings, and the
  viewer (`openMidi`) and the GP5 export undo it to sound the real pitch.
- **Import** (`gpimport/strings.py`, both parsers, `bass=` on
  `parse_gp_track`): a guitar chart needs 6 strings and a 4/5-string track is
  refused there with "pick it as the Bass track"; a Bass chart needs 4 or 5
  strings (a 6-string bass is charted as a guitar — DLC Builder's own advice,
  its checker refuses a bass note on string 4+, I36). A 5-string bass is
  **folded** onto the four consecutive strings that lose the fewest notes
  (tie: the window closest to bass standard) — B E A D for a part that never
  plays the high G, E A D G for one that never plays the low B — with a warning
  naming the strings and counting any note dropped.
- **Picking it**: `GpJobSpec.bass_track` / `/jobs/gp`'s `bass_track` /
  `params["bass_track"]`, in the reload/rebuild/sync-state keys like the other
  slots. Auto-pick takes a track named "bass", else the only 4/5-string track.
  The lone-Lead→Combined rule ignores the Bass (a guitar + a bass is still
  COMBO + BASS). Per-chart tuning overrides for "Bass" are 4 MIDI pitches.
- **What skips it**: tone suggestions (the analysis is of the guitar stem),
  showlights (from the richest non-bass chart), and the chart GP lyrics are
  timed on when the file names no vocal track. With no tone of its own it gets
  DLC Builder's `default_bass.json` (Eden WT550, vendored verbatim).
- **Checker**: `check_sng(model, bass=True)` adds `bass_string` (a note or a
  template fret on string 4/5); `verify_psarc` knows a chart is a bass from
  its manifest's `pathBass`.
- **UI**: wizard step 2 and "Editar info" have a "Pista Bass" picker listing
  only 4/5-string tracks (the guitar pickers no longer offer them); the score
  draws four taller rows labelled with the real tuning, the fretboard and the
  3D highway four strings (`setStringCount`), the note editor four strings, the
  synthesized source the bass's own pitches.
- **Found on the way, not bass-only**: a DD level holding only OPEN strings (a
  bass line's roots at its lowest levels) shipped with no anchor at all —
  `_level_positions` dropped open notes before `_build_anchors`, whose
  one-window fallback for exactly that case therefore never ran. Open notes now
  reach it (they still place no window). Guarded by
  `test_a_level_of_only_open_strings_still_has_an_anchor` (both halves
  mutation-checked).
Guarded by `test_bass_import.py`, `test_bass_arrangement.py` and
`test_a_four_string_bass_is_read_as_a_bass_never_as_a_guitar`; a real build of
two invented GP5s (a 4-string bass, a 5-string B-standard one) through
`/gp/inspect` → `/jobs/gp` → a clean `/psarc-check`, and the viewer with
Playwright (wizard picker, four-line score B E A D, fretboard, 3D highway,
Editar info; PT/EN, no page errors). **Never played in game from here** — the
encoding is DLC Builder's, the result in Rocksmith is the user's to confirm.

### Two GP tracks charted as one (`merge_tracks`)

"have both lead and rhythm timelines … these songsterr tabs … have split the
song into 2 sections when there's only 1 guitarist, i want to combine these
into 1" (Facebook, 2026-10-16; "Avança com o pedido de juntar as duas pistas",
2026-10-18). Option (b) of the TODO entry — fusion at parse time, no second
staff: `GpJobSpec.merge_tracks` (chart name → a second GP track index) makes
`_merge_into` parse that track with the SAME arguments (shift, the chart's own
`tempo_scale`, `bar_times`, `bass=`) and fold its notes in with
`merge_parsed_tracks` (pure): a note on a string the chart already plays at
that instant (`NOTE_OVERRIDE_MATCH_S`) is dropped and counted, sustains are
re-trimmed (`apply_sustain_gap` — a note of one track can ring into the other
track's next note on that string), the longer beat grid kept. Before the sync
rounds, note edits and `resolve_links`, so everything after sees one chart. A
track in another tuning or capo (the same fret would be another pitch), or one
that will not parse for that chart (a guitar into the Bass), is NOT merged and
says so in the warnings. A lone Lead is built as Combined, so `"Lead"` also
reaches the Combined slot when no Combo track was set. **A chart left with no notes is named** (`_refuse_empty_charts`, after the
note edits, before building; GitHub issue #7): "Lead (GP track 1 "Vocals")
… Pick another track for that arrangement, or merge one in" instead of the bare
"arrangement has no notes" `Arrangement.validate` raised later. Measured on the
way: stripping mutes (`import_mute_techniques` false) never empties a chart —
`_strip_mute_techniques` keeps every note as a plain one — so the issue's
"mutes stripped → no notes" had another cause; the message does not blame mutes.
Guarded by `test_a_chart_whose_track_has_no_notes_is_named_with_its_track`
(fails without the check). Plumbing like the track
slots: `/jobs/gp` form `merge_tracks` (JSON), `RebuildIn.merge_tracks` (null =
untouched, `{}` = none), both through `api._clean_merge_tracks` (known charts,
indexes 0-63, 422 otherwise); `params["merge_tracks"]` (portable in `.rfproj`,
a sync-state key, checked by `/reload-gp` against the new file's tracks),
`/gp-tracks` answers it. UI: a "Juntar duas pistas num só arranjo" card in the
wizard's step 2 (`#wzMerge`) and in "Editar info" (`#metaMerge`), both built by
`renderMergePickers` (one merge from the UI; the backend takes one per chart),
`readMergePickers` refuses merging into a chart with no track or the chart's
own track. Guarded by `test_merge_tracks.py` (the shared note kept once and the
sustain re-trimmed, a split part built as one Combined chart, another tuning
refused, the wizard/rebuild round trip — the four rules mutation-checked); with
Playwright and a real build of an invented split GP5 (PT 1440 / EN 760 px):
own track refused, 2 + 2 notes → 4 (one shared note left out, said), "Editar
info" shows the merge and removing it rebuilds to 2, no page errors.

**Choosing the bars** ("quero que seja possível escolher os compassos … a pista
que escolho como principal só recebe as notas de outra pista nos compassos que
estão vazios na principal", 2026-10-18). Each merge is a `TrackMerge(track,
bars, only_empty)`: `bars` = the chart bars (1-based, as PLAYED, the score's
numbers) whose notes come in, None = all; `only_empty` = only bars where the
chart itself starts no note. A note's bar is `bar_of(bar_starts(tempo_map), t)`
(the grid's last downbeat is the closing bar line, `close_beat_grid`, not a
bar); notes left out by the choice are counted in the warning. Stored as
`params["merge_tracks"][chart] = {track, bars, only_empty}` —
`_clean_merge_tracks` takes the old bare index too and always answers the new
shape; the worker reads either through `track_merges`. `GET /gp/bars?gp_token=`
(before the job) and `GET /jobs/{id}/gp-bars` answer `api._gp_bar_map`: notes
per bar of every chartable track (`{bars, tracks: {index: [counts] | null}}`).
UI: `renderMergePickers(box, tracks, current, {barsUrl, slotTrack})` adds
"Só nos compassos onde o arranjo não tem notas" (ticked by default) and a grid
of bars (`mergeBarStates`: sel / out / own — the chart plays there, locked
while the box is ticked / off — nothing to bring); click, drag-paint,
Shift+click for a range, Todos/Nenhum; `bars` stays null until the user edits
it; "Editar info" counts it as an unsaved change (`mergeStateKey`), and no bar
left is refused. Experimental. Guarded by
`test_only_the_bars_the_chart_leaves_empty_take_the_other_tracks_notes`,
`test_a_merge_stored_before_bars_existed_still_takes_every_bar` and
`test_the_bars_are_chosen_from_a_map_of_each_tracks_notes` (the only-empty
rule, the bar choice and the closing-line rule mutation-checked); with
Playwright (PT 1440 / EN 760 px): bar 1 locked where the Lead plays, a click,
a drag over three bars, Shift+click, "Nenhum" refused, a real build taking
only bar 3, "Editar info" showing it and counting a change, no page errors.

### Reloading the GP file (`/jobs/{id}/reload-gp`)

`POST /jobs/{id}/reload-gp` (multipart `gp`, GP jobs only) swaps the Guitar Pro
file of an existing job for a re-exported one — for when you tweak a note in
Guitar Pro and don't want to recreate the job and redo all the alignment. It
writes the new file to a fresh `work_dir/gp/<uuid>` and, like `/rebuild`, **forks
a new job** that inherits ALL of the original's params (tuning, `offset_s`,
`tempo_scale`, `sync_anchor_stages`, `arrangement_sync`, tones, lyrics, cover) —
only `gp_path` changes. It validates the new file parses (`inspect_gp`) and that
the previously selected `lead_track`/`rhythm_track` indices still exist (a plain
note edit keeps the track layout; a restructured file 422s with a "create a new
job" message rather than silently building the wrong track). Exposed in the
Partitura inspector's "Mais opções" as "Recarregar ficheiro GP".

**The new file's own audio replaces the recording** when it carries one
(`use_embedded_audio`, default true — "usar o áudio que vem dentro do
ficheiro, se trouxer", ticked beside the button): that copy is the one its
sync points describe, exactly as the wizard decides. What was measured on the
old recording goes with it (`stems*`, `detected_tones`, `tone_detection_*`):
kept, the separated guitar fed "Ataques da gravação" and the stem audio sources
from a recording the chart no longer plays against (guarded by
`test_what_was_measured_on_the_old_recording_is_dropped_with_it`,
mutation-checked). It used to keep the old
recording no matter what, so a project could never move onto the GP8 audio
without being recreated. When the recording was a separate upload until now,
`offset_s` becomes `sync_start_s` of the new file (another recording's start
does not fit this one — same value the wizard pre-fills); when it already came
from the GP, the user's own start is kept. A file with audio also stands in
for a recording that no longer exists (it was a 409 regardless). Committed
sync anchors are kept as they are — they are the user's corrections, in the
old timeline. Guarded by
`test_reloading_a_gp_file_that_carries_audio_uses_that_audio` and
`test_a_gp_file_with_audio_stands_in_for_a_recording_that_is_gone` (each
branch mutation-checked); with Playwright and a real build on the user's
Ocean Eyes file (upload + start 5 s → reload → its 6.2 MB MP3, start 0 s).

### Intro silence (`lead_in_s`)

`GpJobSpec.lead_in_s` (default 0) is user-defined extra silence prepended at the
very start, ON TOP of the automatic `MIN_LEAD_S` lead-in:
`pad_start_s = max(0, MIN_LEAD_S - offset_s) + lead_in_s`. Because the score
shifts by the full `pad_start_s` and the audio is padded by the same amount,
the whole bundle (audio + notes + lyrics) moves later together — a way to "push
the music forward" with a silent intro. Exposed in the Partitura inspector's
"Mais opções" as "Silêncio inicial" (commit-on-rebuild, no live drag). The tab viewer's `viewOrigin`
and `playheadDisplay` add the built `lead_in_s` (`leadInBuilt`) so notes/playhead
stay aligned after a rebuild with it.

### Tempo scaling (`tempo_scale`)

`GpJobSpec.tempo_scale` (default 1.0) multiplies the whole musical timeline at
parse time, around the song's start and before `offset_s` — it corrects a
constant GP-vs-recording tempo mismatch (the linearly-growing part of sync
drift) in one move. `>1` stretches (slower); `<1` compresses (faster). The
effective `average_bpm` is scaled inversely. The tab viewer exposes it as an
editable BPM/% control with live preview (notes slide over the fixed waveform).
Use it *before* the per-note `sync_anchor_stages` below, which then only need to
clean up residual non-linear drift.

### Automatic sync was REMOVED (2026-08) — manual only

> **Since 2026-10-15 one automatic tool is back, EXPERIMENTAL and on the user's
> request**: "Sincronizar automaticamente" (variable tempo), built so the two
> failures below cannot recur — see "Automatic sync with a variable tempo" below.

> Every **automatic** synchronisation feature was deleted at the user's explicit
> request after none of them produced a usable result on their real material:
> `/auto-sync` (one average tempo), `/auto-sync-dynamic` (onset-correspondence
> drift curve), `/sync-from-midi` (RIPX tempo-map import), `/sync-from-stem`
> (Beat This! neural downbeats) and `/analyse-sync` (drift diagnosis + graph +
> per-finding accept/reject), along with `application/sync_analysis.py`,
> `infrastructure/rhythm/{beatthis_adapter,midi_tempo}.py`, the
> `align_chart_to_recording`/`align_chart_to_midi`/`align_bars_to_downbeats`/
> `suggest_sync` helpers, the librosa whole-song estimators
> (`detect_beats`/`detect_onsets`/`detect_tempo_and_onset`) and the `beatthis`
> extra. The UI's automatic buttons and the drift-graph panel went with them.
>
> **Why, honestly:** on the user's songs (AI-generated tabs against their source
> recordings) the estimators either read the wrong metrical level, or produced
> so many corrections that applying them scrambled the score. They were correct
> on synthetic data and repeatedly wrong on real audio. Rather than ship
> plausible-looking machinery that misleads, the feature set was cut back to the
> tools the user can verify by ear.
>
> **What remains is deliberate and sufficient:** the whole manual toolkit — Step 1
> (first-note pin: field/slider, "Início = cursor", the guided 3-click "Detetar
> 1ª nota"), `tempo_scale` (BPM/%) for a uniform difference, the bar-align panel
> and 📏 popup, and the per-note modes (drag/tap/excerpt/move-from-here/new-beat)
> — plus `/detect-tempo` (local BPM from one clicked instant, which backs the
> per-point re-tempo) and `/detect-tuning`. `suggest_tempo_scale` stays because
> `/detect-tempo` uses it.
>
> Git history has all of it (`git log -- src/rockforge/application/sync_analysis.py`)
> if any of it is ever worth reviving — the algorithms are documented in those
> commit messages, including the measured failure modes.


### Automatic sync with a variable tempo — EXPERIMENTAL (2026-10-15)

The user asked for it back, clearly marked experimental ("Quero que avances
para a sincronização de BPM variável … tem de ficar claramente marcada como
experimental"), after the question "if guitar-pro-youtube-sync can, we must"
— that tool does NOT detect anything (it reads Songsterr's human-marked bar
times, which RockForge already uses); this is the genuinely automatic path.
It is built to avoid the two measured failures of the removed tools:

- **The metrical level cannot be misread.** It does not ask "where are the
  beats?" but "how must each of the chart's OWN beats move so its notes land
  on attacks heard in the recording?" — the number and order of beats is
  fixed by the chart. `_librosa_runner.align_beats` (plain Python, no numpy,
  so CI tests it): a beam search (48 states) over the beats, each beat
  allowed 0.80-1.25× its current length, scored by the onset envelope
  (librosa `onset_strength`, 10 ms, scaled by its 95th percentile, widened a
  frame) at every note's position inside its beat, a little at the beat
  itself (`ALIGN_BEAT_WEIGHT`, a drum hit), minus a smoothness cost on the
  log-change of tempo from one beat to the next (`ALIGN_SMOOTH` = 3 % per beat
  costs one full attack); the first beat searched ±0.25 s around where it
  shows. A trend (second-order) model was tried and was worse.
- **Corrections cannot scatter.** The answer is turned into ordinary pending
  anchors exactly like "Marcar a ouvir" taps (`runAutoSync` → `planTaps`, one
  per bar downbeat), so it previews, is ONE undo step and rides "Aplicar e
  reconstruir"; bars whose notes landed weakly (`support` < 0.5) are left out
  (the warp carries them) and listed with the bars after a rest
  (`after_gap`: ≥ 4 beats with no note — through silence nothing holds the
  tempo, and the measurements below show that is exactly where a whole
  subdivision can slip while looking supported) under "Verifica de ouvido".
  No improvement in mean note evidence = nothing applied.

Plumbing: `POST /jobs/{id}/detect-beat-sync` (`DetectBeatSyncIn`: beats ≥ 2,
increasing, and note onsets, in seconds of the recording as the viewer shows
them; the full MIX is analysed — a stem may be trimmed to the song's start),
`librosa_adapter.align_to_recording` (in-process with librosa, else the ML
interpreter via `beatalign --spec <json>`), card `#autoSyncCard` in the
Sincronização inspector after "Marcar a ouvir", with an EXPERIMENTAL badge
and ⓘ (`beat-sync`). **Found on the way:** run as a script, the runner's own
folder is `sys.path[0]` and holds RockForge's `packaging` package, which
then shadows the pip `packaging` librosa imports — every runner command
failed from a source install with an external ML Python (the frozen bundle
has no `__init__.py` there, so the pip one won); the `__main__` block now
drops that folder. Measured (synthetic, `tests/test_beat_align.py`, each
piece mutation-checked): ±6 % tempo wander + 3 % overall, two-bar riffs with
rests, missed and spurious attacks, with or without drums → every bar with
notes within 50 ms (from up to 4.3 s off); a chart already in time stays
within 20 ms; stress cases (±10 % wander through a silent rest, uniform
eighths with no accents) slip a beat in 2 of 10 songs, always flagged. End
to end on an invented GP5 + a synthesized "recording" (librosa, Playwright,
a real rebuild): 30 of 32 bars aligned, from up to 2.5 s off to ≤ 28 ms
(the two rest bars 65 ms), a consistent ~+15 ms lag of the onset envelope,
`/psarc-check` clean. **Never run on a real song from here** — that is the
user's test; the release smoke test runs it in the frozen `.exe` through the
components' Python.

### The recording's attacks over the score ("Ataques da gravação")

"It would also be good to have beat detection from the audio, the strumming
pattern on the left is incorrect compared to the right … more fixing crappy
tabbing" (Liam, 2026-10-16), then "use AI to split down the tracks similarly to
x-minus … then run the separated track through an FFT to get the amplitude
peaks". Correcting the rhythm by itself would be transcription (measured and
dropped, below); showing WHERE the tab disagrees with the recording is not.
`POST /jobs/{id}/detect-attacks?source=` (`DetectAttacksOut`: `source` a
separated instrument or "mix", `attacks` [[seconds, strength 0-1]…],
`duration`) measures ONE chosen instrument: any a Demucs pass separated
(`analysis._separated_stems`: the ones "Separar instrumentos" stored, plus every
`demucs_stems/stems/*/*/*.wav` the tone detection left — drums never; listed by
`GET /jobs/{id}/attack-sources`), or the mix; without `source`, the guitar when
there is one, else the mix; an instrument never separated is a 409 (only names
from that list are ever opened). Both separations run on the recording
UNTRIMMED (`normalize` with no offset), so a stem's seconds are the
recording's. The card's **"Medir em"** (`#attacksSource`) picks it: by default
the separated bass for the Bass chart, the guitar for the others, the mix when
neither exists (`defaultAttackSource`, re-applied on every tab switch until the
user picks one). **Nothing separated + "Detetar" asks first** (user request,
2026-10-16: the mix's drums and voice bury the differences) — `confirmModal`
gained an `okLabel` ("Medir na mistura") so a yes that is not a removal is not
a red "Remover". The bass separates more cleanly than the guitar, so with a
Bass chart made the main chart for sync ("Pista principal") the bass's
corrections carry to every chart — that workflow needs nothing new beyond the
choice of instrument.

**A separated instrument is read with a floor** (`ATTACK_STEM_FLOOR_DB` = 40:
the mel bands no lower than 40 dB under the stem's loudest, `onset_envelope(...,
floor_db)`; the endpoint sends `separated` for any stem, never for the mix).
Measured on synthesized songs (drums, bass, distorted guitar, voice; a "stem" =
the instrument plus a few % of the rest, as Demucs leaves): librosa averages
the log-mel flux over EVERY band, and a hi-hat residue 30 dB down fills many
bands the bass never reaches, so without the floor a 3 %-residue bass stem
showed 0.87 strong attacks with no note per note of an in-sync chart (the mix:
1.19) — with it 0.00 (guitar stem 0.39 → 0.01), no real attack lost, and every
planted tab error found (96/96 missing notes, 96/96 extra ones). Floors of 30
dB lost guitar attacks in the mix, so the mix keeps librosa's own. **The
auto-sync on a separated bass was measured and NOT adopted**: same songs, the
chart at one tempo against ±6 % wander, bars within 50 ms — mix 99 %, bass stem
with 10-25 % residue 99 %, a perfectly clean bass 54 % (a riff of eighths is
the same shifted by an eighth once no drum marks the beat, and it slipped by
that after every rest, with full support — so it would have been applied);
±10 % wander: mix 83 %, clean bass 23 %. A separated bass gives the aligner
nothing the mix lacks and takes away the drums' `ALIGN_BEAT_WEIGHT`, so the
auto-sync stays on the mix. Synthesized, not real songs — Demucs cannot run here. `librosa_adapter.detect_attacks` →
`_librosa_runner.attacks` (in-process or the ML interpreter, the
`align_to_recording` pattern) = the same onset envelope as the auto-sync
(spectral flux, 10 ms — not amplitude: a distorted guitar's level barely dips
between strums) through `pick_attacks` (plain Python, CI-tested): a peak within
50 ms, at least 2× the MEDIAN of the envelope ±0.25 s around it (the mean let a
riff's accents hide its softer strokes; steady noise peaks sit near their
median), at least 0.3 of the 95th percentile, and not in the first 0.1 s
(librosa pads the start with silence). The auto-sync keeps the MIX on purpose:
its `ALIGN_BEAT_WEIGHT` counts drum hits.

Viewer: card `#attacksCard` after the auto-sync card (ⓘ `attacks`). "Detetar
ataques" fetches once per version (`recAttacks`, reset in
`loadArrangements`); while "Mostrar na partitura" is ticked `attacksSvg` (from
`showArr`) draws each attack as a blue tick in the band above the staff and
compares it with the note GROUPS as drawn (pending note edits, tempo and
anchors included; `playheadDisplay(0)` turns recording seconds into display
time): within `ATTACK_MATCH_S` (60 ms) a note and an attack are one strike; a
note with none gets an orange circle and a dotted line, an attack of strength ≥
`ATTACK_STRONG` (0.35) with no note an orange tick and a dashed line (weaker
unmatched ones stay faint and uncounted: bleed, ghost strokes). **Seconds of the
recording FILE become display time through `recordingDisplay`** =
`playheadDisplay(s + leadInBuilt)`: the decoded buffer starts with the build's
"Silêncio inicial" (`decodeWaveform` pads it), so `playheadDisplay(0)` alone —
what this card and the auto-sync used at first — put every attack `lead_in_s`
late, and notes that were in sync sat between the ticks ("com as bolas no meio
dos traços, a música estava sincronizada"). With Playwright on the invented riff
rebuilt with a 0.5 s lead-in: 0 of 16 notes matched before, 15 of 16 after (the
same as without a lead-in), and the auto-sync no longer "corrects" a chart that
is in time. The status says
the source and the counts; "Diferença anterior/seguinte" (`goToAttackDiff`)
puts the cursor on each difference. Nothing is applied. Honest limits, in the
ⓘ: when, never which notes or which way the pick goes; the stem holds every
guitar; a mix adds drum/voice attacks. Guarded by `test_attacks.py` (each rule
mutation-checked: a strike is one attack, a near double is one, a quiet passage
keeps its attacks, a raised floor, softer strokes in a dense run — the median —,
the padded start, noise and silence) and
`test_the_recordings_attacks_come_from_the_guitar_stem_when_there_is_one`;
with librosa on a synthesized distorted riff (16 strikes with one tab note
missing and one extra strike) all 16 found 8–24 ms late, one faint artifact;
with Playwright on that invented GP5 built for real: 15 of 16 notes matched,
the missing note (4.0 s) and the extra strike (6.715 s) flagged and reached by
the buttons, hidden when unticked, PT/EN, no page errors. **Never run on a
real song from here.**

### Audio and note bars over the score ("Barras de áudio", `renderLevels`)

"Para ajudar a sincronizar as músicas, pretendo que faças um gráfico de barras
áudio, para a música (até para os stems separados) e outro para o barulho das
notas" (2026-10-18). A "Barras de áudio" switch (`#showLevels`, `rf-levels`)
shows `#levelsSvg`, a second SVG inside `#tabwrap` ABOVE `#tabsvg` (so it scrolls
with the score and the score's own y layout is untouched), redrawn from the end
of `showArr` with its `W`, `px` and warp. Two lanes on the score's x-axis
(recording time): **audio** — peaks per bar (`peakBins`, the helper
`decodeWaveform` now shares) on a 36 dB scale under the loudest peak, of the
source chosen in `#levelsSource`: what is playing (`wavePeaks`, colour of its
kind), the full mix or a separated stem (`stem:<name>`, decoded for the bars
alone by `loadLevelsAudio` when it is not the one playing; its peaks start
`leadInBuilt` later, since only the playing buffer is padded); **notes** —
`notesEnvelope`, the chart's `soundingNotes` at their drawn time (pending
edits, tempo, anchors), each ringing for `noteSoundLength` of its drawn sustain
with a quarter left at the end like the preview's Karplus voice, a chord the
sum of its strings, shown as `1 − e^(−1.2·sum)`. One path per lane, a bar every
max(3 px, one 10 ms bin); both cached by what they were drawn from
(`levelsCache`). Its own playhead (`moveLevelsPlayhead`, from `syncFrame` and
`seekPreview`), a click seeks. **An `<svg>` has no `.hidden` property** —
`toggleAttribute('hidden')`, or the `[hidden]` rule never applies. The state sits
beside `legendOn`, near the top: the legend draws its colours, and
`setLegend(legendOn)` runs at load before the rest of the file (a `let` further
down was a TDZ crash at start-up). Legend group "Barras de áudio". Browser-only;
verified with Playwright (PT 1440 / EN 760 px): first strong audio bar and
first note bar at the same x, "Início" +1 s moved the note bars exactly 1 s
and left the audio path unchanged, a stem source (a filtered copy injected as
a stem) drawn green, the mix, following a synthesized source, the click seek
and both playheads, starting with the bars and the legend already on, no page
errors.

**The audio lane shows the ATTACKS by default, the level on request**
(`#levelsKind`, `rf-levels-kind`; "Avança" on the suggestion that a level is a
poor beat signal). Volume was the first version, and it answers the wrong
question on the material this is for: measured on the synthesized distorted riff
of "Ataques da gravação", the volume bars sat at full height 90 % of the time
(median 1.00, 10th percentile 0.99) while the attack bars' median was 0.04 with
each strike standing up alone. `GET /jobs/{id}/onset-levels?source=`
(`OnsetLevelsOut`: `values` 0-100 per frame, `hop`, `duration`) is the same
onset envelope the attacks are picked from (`_librosa_runner.onset_levels` →
`level_values`: every frame, scaled to the 99th percentile — the 95th the
attacks use flattened every strike to the top —, the first `ATTACK_EDGE_S`
zeroed for librosa's padded start, which otherwise drew a full bar at 0.05 s;
a separated instrument read with `ATTACK_STEM_FLOOR_DB`), reached through
`librosa_adapter.onset_levels` in-process or on the ML interpreter (runner
command `levels`). **The drums are a source here, and only here**: "Separar
instrumentos" keeps them out of the playback list (the user's request), but a
drum track is the clearest beat to check bar lines against, and the pass wrote
`drums.wav` anyway — `_separated_stems(..., drums=True)` finds it in the shared
cache or beside the stored guitar stem (`_drum_stem`), and
`/attack-sources` answers it as `level_stems`. Viewer: `levelsOnsetData`
resolves the source (what is playing → mix or that stem; a SYNTHESIZED source
falls back to its volume, which already says the same), `loadLevelsOnset`
fetches it once per version and source; a 503 (no audio analysis) sets
`levelsOnsetMissing`, says so once and every source shows the volume; any other
failure shows the volume for that source (or drops a source that has none, like
the drums). Values are in the recording's clock, so they start `leadInBuilt`
into the display clock, like a source decoded for the bars. Labels "Ataques ·
…"/"Volume · …". Guarded by
`test_the_bars_keep_every_frame_scaled_to_the_99th_percentile` (the percentile
and the edge, mutation-checked) and
`test_the_audio_bars_can_show_the_attack_strength_of_the_mix_or_any_separated_part`;
with librosa and Playwright (PT 1440 / EN 760 px) on the invented "Deriva"
project: the first strong attack bar at the first note bar's x (129 px — before
the edge fix, a bar at 33 px), the drums offered and drawn green in Ataques and
not offered in Volume, the kind remembered, a faked 503 → volume + one toast,
no page errors. Synthesized, not a real song.

**Turned on with nothing separated, the bars ASK** ("se eu não tiver feito a
separação … tem de aparecer um aviso para fazer a separação"): the drums and
the attacks per instrument both need a separation, and finding that out from
a lane full of drum hits is the wrong way round. The `#showLevels` change
(never at load) asks through `confirmModal` ("Separar instrumentos" /
Cancelar) when `needsStemsQuestion()`: the project's `/attack-sources` has been
read (`levelStemsFor`), lists no instrument, no separation is running
(`stemsBusy`, set by `separateStems`/`loadStems`, cleared when `pollStems`
ends) and this project was not asked before in this page
(`levelsStemsAsked`). **The question comes BEFORE the bars are drawn**
(`turnOnLevelsAsking`): drawing them in "Ataques" fetches `/onset-levels` of
the mix, which used to run behind the dialog and on after "Cancelar" — the
user saw it as "mesmo que o cancele, extrai na mesma" (BUG-0296). Either
answer turns the bars on in **Volume** (`levelsKind = 'volume'`, not stored),
read from the audio already in the browser, so Cancel sends nothing to the
server. Yes runs the ordinary `separateStems`; when that poll ends `ready`,
`levelsWantStems` moves the bars onto the chart's own instrument (bass for the
Bass chart, else guitar) and back to the kind the user keeps (`rf-levels-kind`,
"Ataques" by default), with a toast naming it and the drums. Browser-only;
verified with Playwright: Cancel → no request at all after it, "Volume ·
Mistura completa"; Yes (separation faked) → only `separate-stems` while it
runs, then "Ataques · Guitarra"; a project already separated is never asked;
no page errors.

**Are they lined up? The alignment line** ("é difícil perceber se estão
alinhados", 2026-10-18, a screenshot of the two lanes a few pixels apart).
With the bars on, the pointer over `#tabwrap` draws `#alignLine` (a dashed line
through both lanes AND the staff — an absolutely positioned div in `#tabwrap`,
now `position:relative`) and `#levelsHover` in the bars: `levelsAlignAt(t)`
takes the nearest note onset as drawn (`levelsHover.notes`, the score's own
warp) and, within `ALIGN_SEARCH_S` (0.15 s) of it, the clear attack peaks of
the audio lane (`levelsHover.audioBin`, the same values the lane draws: local
maxima ≥ half the strongest, rising ≥ 0.3 of it above the 50 ms before — a
ringing note's ripple on the Volume view is not a strike) and pairs it with the
NEAREST one (the strongest is often the next note's in a fast riff). The box
says "Nota 20 ms antes/depois do ataque", green within `ALIGN_OK_MS` (15), and
the two marks are joined. Honest limit, in the guides: a note off by more than
half the gap to its neighbour pairs with the neighbour's attack — it is for the
last adjustments, after the start and the tempo. **Ctrl + wheel** zooms at the
pointer (`setZoom(z, clientX)` keeps the time under it; non-passive listener,
so not the page zoom); row in the "?" list and the guides. Browser-only;
verified with Playwright: attack values planted within ±40 ms of each chart
note of the invented "Deriva" project → 40 of 40 readings within 10 ms of the
planted offset (PT 1440 / EN 760 px); on its deliberately drifted recording
(85-175 ms off on sixteenths) most pair with the neighbour, as said; zoom kept
the pointer's time (3.500 → 3.504 s), the line goes when the pointer leaves, no
page errors. Not on a real song from here.

### Exporting a corrected Guitar Pro file (`/export-gp`)

`infrastructure/gpexport/tempo_writer.py` writes the accepted tempo corrections
into a **copy** of the user's Guitar Pro file, so the fix is permanent in Guitar
Pro itself and not only inside RockForge. The uploaded original is only ever read.

| format | write | how |
|---|---|---|
| `.gp3`/`.gp4`/`.gp5` | yes | PyGuitarPro. A tempo change is a `MixTableChange` on a **beat** (there is no tempo field in the measure header); measure 1 is the song header's `tempo`. |
| `.gp` (GP7/8) | yes | The container is a plain ZIP: every entry is copied **byte-for-byte** and ONLY `Content/score.gpif` is replaced. Tempo is a `MasterTrack/Automations/Automation[Type=Tempo]`, `<Value>` = `"<bpm> 2"` (reference 2 = quarter). |
| `.gpx` (GP6) | **no** | A proprietary container nobody writes — not alphaTab, not TuxGuitar, not MuseScore. Refused, pointing at GP5/GP7 like the importer does. |

Routes ruled out by research, so nobody re-litigates them: MuseScore imports GP
but **cannot export it** (import-only module); MusicXML drops vibrato and palm
mute; MIDI loses tab/tuning/technique entirely. Neither leads back to a `.gp*`.

Details that were measured and will bite anyone editing this:
- **The binary formats store tempo as an INTEGER**, so 119.085 BPM is written as
  119. `write_tempo_corrections` returns an `AppliedCorrection` per measure with
  `requested_bpm`/`written_bpm`/`rounded` so the API and UI can say so instead of
  quietly handing back a different tempo. GPIF keeps the decimals.
- A fresh `MixTableChange` has `wah=None`, but GP5 always stores a wah byte, so
  it reads back as `WahEffect(-1)` and the file stops round-tripping; and
  `hideTempo` defaults `True` while the field does not exist before GP5.1. Both
  are set explicitly.
- An existing `MixTableChange` on the target beat is **mutated**, not replaced —
  it may carry an instrument/volume/wah change that is not ours to drop. A tempo
  change the user authored themselves survives untouched (guarded by
  `test_an_authored_tempo_change_is_preserved`), as does a mid-bar GPIF
  automation (only `Position == 0` entries are ours).
- Only **tempo** is exportable. A *jump* cannot be expressed as a BPM change (it
  would need a bar inserted or removed), so it stays a RockForge-side correction
  and the UI says so rather than approximating it.

`POST /jobs/{id}/export-gp` writes `work_dir/<job>/corrected.<ext>` and returns
the report; `GET /jobs/{id}/corrected-gp` downloads it. Wired to the Exportar
page's **"Guitar Pro com os andamentos corrigidos"** row (`#exportGpBtn`), which derives the `(measure, bpm)` list
from the pending sync: `retempoedBars()` returns exactly the bars the score
already draws in AMBER (the same `>= 2` BPM threshold), so what is marked on
screen is what gets written. Both the drawing and the export read one
`barTempoTable(a, warp)` — they were the same code inline in `showArr` before,
and two copies would silently drift until the exported file no longer matched
the score. Bars whose corrected tempo falls outside the endpoint's (10, 400)
bound are dropped with a count rather than 422-ing the whole export. Guarded by
`test_gp_tempo_writer.py` (preservation of notes/frets/techniques/tracks/tuning/
sections across a real write, byte-identity of the .gp ZIP's opaque entries,
rounding reported, `.gpx` refused, bad corrections rejected with nothing
half-written) and `test_export_gp_*` in `test_api.py`.

**Unverified by design:** no Guitar Pro is available in CI or in the sandbox, so
the exported files are round-trip-verified through our own parsers but have NOT
been opened in Guitar Pro itself. The `.gp` ZIP-surgery route in particular is
sound in theory (it is exactly what alphaTab's `Gp7Exporter` builds) but needs a
human to confirm against a real install.

### Exporting the EDITED chart as a new GP file (`/export-arrangement-gp`)

`/export-gp` above only ever writes **tempo** into a copy of the user's own
file, so the note editor's edits (and any note added/removed in the browser)
had no way back into Guitar Pro at all. `infrastructure/gpexport/
arrangement_writer.py` closes that: `write_arrangement_gp5(arrangement, dst)`
generates a **brand-new GP5** from what RockForge actually holds — notes,
frets, techniques, tuning, section markers and the corrected beat grid.

**It reads the BUILT XML, not the Guitar Pro source.** `infrastructure/rsxml/
reader.py`'s `read_arrangement_xml` is the partial inverse of `writer.py`: it
recovers tuning, ebeats, notes-with-techniques and sections — everything the
exporter needs — and deliberately NOT phrases/DD levels/anchors/tones, which
are derived data with no GP counterpart. Reading the built file is the whole
point: it already carries `tempo_scale`, every `sync_anchor_stages` round and
every `note_overrides` patch, so what comes out is the chart as RockForge
plays it. (`find("tuning") or fallback` is a trap here — an ElementTree
element with no children is **falsy**, and `<tuning>` has only attributes, so
the truth test threw the real tuning away and every export came back in
standard E. Use `is None`.)

**The two honest costs, stated on every export, not only on failure:**
- **One track.** A generated file cannot carry the user's other tracks,
  formatting or anything else from the original — it is this arrangement
  alone. That is why `/export-gp` still exists: use it when only the tempo is
  wrong and the original file must survive intact.
- **Quantization.** Guitar Pro stores *notated rhythm*, not absolute seconds,
  so an onset that falls between grid positions has to move. `_quantize`
  snaps to the measure grid and the report returns `quantized` +
  `max_shift_s`; the UI shows both. Silently re-timing notes into a score
  that looks authoritative but plays differently would be the worst outcome
  here. `_split_ticks` decomposes an arbitrary span into notatable durations
  (`Duration.fromTime` raises on anything it cannot represent).

PyGuitarPro details that were measured and will bite anyone editing this:
`MeasureHeader.start` does **not** auto-accumulate — each header's start tick
must be set explicitly, or the score drifts (166.7 ms on the first test song);
`MeasureHeader` has no `tempo` field at all, so a per-measure tempo is a
`MixTableChange` on the measure's first beat, same as `tempo_writer`; string
numbering is 1 = highest pitch.

`POST /jobs/{id}/export-arrangement-gp?arrangement=<Kind>` writes
`work_dir/<job>/corrected.gp5` and records it in `params["corrected_gp"]`, so
the existing `GET /jobs/{id}/corrected-gp` serves it — whichever export ran
last wins, each recording its own filename. Wired to the Exportar page's
**"Guitar Pro com as notas editadas"** row (`#exportArrGpBtn`), under the tempo-only one.
Guarded by `test_gp_arrangement_writer.py` (notes/times/strings/frets,
techniques, chords-as-one-beat, tuning/metadata/sections, a mid-song tempo
change, the reported quantization, the always-present single-track warning,
and an empty beat grid refused) and `test_export_arrangement_gp_*` in
`test_api.py`. Same **unverified-by-design** caveat as above: round-tripped
through our own importer, never opened in Guitar Pro itself.

### Deleting notes ("Apagar", Delete, Ctrl+Z)

"cria uma forma de apagar notas": the only way was "Editar notas" → click one
note → popup → "Remover nota", one note at a time. Now every SELECTED note
(Ctrl/Shift+click or Excerto — selection works in any mode) of the current
arrangement is deleted at once by the **Delete**/Backspace key, the
**"Apagar"** button that appears next to "Limpar seleção", or "Notas ▾" →
"Apagar seleção" (`deleteSelectedNotes`). Same primitive as "Remover nota" — a
`deleted` note override (`deleteNoteAt`, keyed on the built note's OWN time,
which is what `_apply_note_overrides` matches) — so it previews, counts as
"Pendente: edições de notas" and rides "Aplicar e reconstruir"; no backend
change. A note that exists only as a pending insertion just loses that
insertion (and an emptied kind is dropped, or "Pendente" would stay lit).
**The last delete can be undone** (Ctrl+Z / "Desfazer apagar"): once a built
note is off the score there is nothing left to click to bring it back, short
of "Limpar esta pista", which discards every edit. `noteDeleteUndo` records the
override each deleted slot had BEFORE (null = none) and undo restores exactly
those slots — so a pending fret edit on a deleted note comes back as that
edit, and edits made after the delete elsewhere survive. Cleared on job load
and by "Limpar". Browser-only, no pytest coverage; verified with Playwright
(Ctrl+click two notes → Delete → 623→621 groups, pending lit → Ctrl+Z restores
and clears it; an inserted note deleted leaves `{}`; edit-then-delete-then-undo
keeps fret 9; a real rebuild goes 1374→1372 notes with none left at those
times).

### Undo / redo of everything pending (`pendingSnapshot`)

"desfazer/refazer em geral": the only undo was the last note delete. Now one
snapshot (`pendingSnapshot`, plain data) holds everything "Aplicar e
reconstruir" would send — every chart's tempo (only where it differs from the
build) and anchors, `offsetLive`, the cent offset, lead-in/mute/DD, the note
overrides, the lyric ROWS (with their line ends and the follow/back-to-score
flags), the sections, and the tones (`jobTones`, the song's and each chart's
set — `stashToneSet` first, so the set on screen is in its place). Every edit
path ends in `notePendingChange` (from `updatePendingChangesInfo`, `showArr`,
`renderTonePanel`, `renderSectionsList`, `renderLyricsRows`, and the build
option inputs); 400 ms after the last call the state is compared with the
newest snapshot and a different one becomes a step (`recordPending`, ≤ 100
steps), so a drag or a typed word is one step and a tab switch is none.
`restorePending` puts a snapshot back and re-renders, then `resetMainFollow`
and `resetLyricFollow` — the restored rows and other charts already carry
their sync, and nothing may carry them again. Undo flushes an unrecorded edit
first (or Ctrl+Z right after an edit would skip it). The history starts once a
version's charts, lyrics AND tones are loaded (`startPendingHistory` at the end
of `loadArrangements`), so loading is never a step, and stops on close and on
the next load: a rebuild is a new version with a new history. Ctrl+Z /
Ctrl+Shift+Z / Ctrl+Y on any project page, not in a text field (native undo)
or under a dialog; buttons `#undoBtn`/`#redoBtn` in the top bar. "Desfazer
apagar" stays as the delete-only restore. Browser-only, no pytest coverage;
verified with Playwright (tempo, anchor, section, lyric word and note delete
undone one by one across pages and redone; a new edit drops the redo branch;
Ctrl+Z in a visible field stays the field's; with two charts a tab switch is no
step and redo puts each chart's tempo/anchors back; a tone and its change).

**The same snapshot is the autosave** (`saveDraft`, after every recorded step,
undo and redo): `localStorage` `rf-draft:<job id>` = `{t, snap}`, removed when
the state is back to the build (`pendingBase`), kept for the 20 most recent
versions (`pruneDrafts`). Keyed by VERSION, so a draft always matches the
build it was made on; "Aplicar e reconstruir" drops it (the new version is
built with it). When a version finishes loading, `offerDraft` asks whether to
recover it; yes restores it as a step of its own (undo goes back to the
build), no deletes it. Browser storage only — never sent anywhere, lost with
the browser's site data, as the honest limit. Verified with Playwright: tempo,
a lyric word and the cent offset recovered after reloading the page, undone
to the build (draft gone), redone (draft back), declined (gone for good), and
dropped by a real rebuild.

### Repeating a passage (A–B loop, the transport)

`loopA`/`loopB` are recording time (the playhead's clock, `currentPlayheadT`),
set at the cursor by the A/B buttons or `[`/`]`; placing the second point
turns the loop on (`loopOn`, toggled by the ↻ button or `L`), B before A is
swapped, closer than 0.2 s is refused. While on, playback stays inside:
`syncFrame` sends a playhead at or past B back to A (`keepInsideLoop` →
`audioSeek`), and `audioPlay` starts at A when the position is outside — so a
seek outside while playing lands on A too (a seek is a stop + play); paused,
the cursor moves freely. `loopBandSvg` draws the band in `showArr`. Cleared on
every load and close (it belongs to that recording). Not part of the pending
edits (it changes nothing in the build). Browser-only; verified with
Playwright: 4 s of playback from outside started at A and stayed in [2, 3.43]
for A=2/B=3.5, `L` off then ran past B, too-close refused, B-before-A swapped.

### Keyboard shortcuts: the "?" list and 1–9 for the modes

`showShortcuts` fills the read-only ⓘ box (`#infoOverlay`, widened by
`.modal-keys`) with every shortcut, grouped, built with `T()` at open time —
the mode names come from the menu items' own `data-name`, so a renamed mode
follows. It opens with `?` on any project page (not typing, nothing on top) or
the key button in the top bar (`#shortcutsBtn`, hidden under 1150 px — `?`
still works). The ⓘ box now also closes with Esc. Digits 1–9 pick the modes in
`SYNC_MODE_BUTTONS` order (= the Modo ▾ menu's), 0 the tenth (`modeKey`), the active one's own number
deselects it like a second click; each menu item carries its number
(`.dd-kbd`, added at load). **When adding a shortcut, add its row to
`showShortcuts` and to the guides' table.** On the way, the project top bar
stopped drawing the status chip over the head's buttons on narrow screens
(pre-existing, made worse by the new buttons): the head keeps
`min(15.5rem, 28vw)` and barely shrinks, the chip and "Pendente" shrink with
an ellipsis, "Descarregar" is icon-only under 1100 px and the chip hides under
860 px. Browser-only; verified with Playwright (`?`/Esc/button, digits incl.
deselect, `?` and digits ignored in a field; the top bar at 1440/1150/1000/800
px in PT and EN, nothing overlapping or cut).

### Fret-hand positions — the FHP editor (`hand_positions`)

"There's no way to add or edit FHPs. Automatic ones are total shit." (r/rocksmith,
2026-10-15). An FHP is Rocksmith's anchor: from its time to the next one the
game highlights `width` frets from `fret` and points the camera there.
`domain/hand.py` holds the model: `HandPosition(time, fret, width)` (fret 1-24,
width 2-12, never past fret 24 — `ValueError`), `auto_windows` (the automatic
placement, moved here from `sng_build._build_anchors` byte for byte:
consecutive fretted positions folded greedily into one window of at most
`AUTO_WINDOW_SPAN` = 4 frets) and `fixed_windows` (the user's: every note,
open strings included, belongs to the FHP at or before it within
`HAND_POSITION_MATCH_S` = 5 ms — the XML rounds to the millisecond — or the
first FHP when it comes before all; an FHP with no note at a level is DROPPED
at that level, the one before carrying on, so a thinned DD level never ships a
window over notes it does not have — the crash rule of `_build_level`).
`Arrangement.hand_positions` empty = automatic; non-empty = ALL the chart's
FHPs. The SNG uses them at every level (`_build_anchors(..., hand_positions)`;
the phrase-boundary split, `_anchor_note_times` and the note re-pointing are
unchanged, so `check_sng` holds) and skips `_hold_through_arpeggios` (an FHP
inside an arpeggio is the user's call); the XML writes them verbatim.
**The XML's automatic anchors are now `auto_windows` too**: before, the writer
had its own "new anchor when a group leaves the window" rule, so DLC Builder,
the viewer (which reads the XML) and the native SNG each showed different FHPs
— and the editor starts from what the viewer shows.

Plumbing, the `note_overrides` pattern: `GpJobSpec.hand_positions` (keyed by
`ArrangementKind.value`), `params["hand_positions"]` (an empty chart dropped),
`RebuildIn.hand_positions` (null = untouched, `{}` = all automatic;
`HandPositionIn` 422s off the neck), the worker rebuilds them, and
`/arrangements` answers each chart's FHPs AS BUILT (`HandPositionOut`, read
from the XML's anchors, unbounded so an automatic wide chord cannot 500) plus
`hand_positions_edited`. `gp_pipeline` warns with the count and the notes their
FHP does not frame (`notes_outside`) — playable (the window is a highlight),
not refused. A lone Lead is built as Combined, so its FHPs are keyed
"Combined", like every other per-chart edit.

Viewer: the **FHP lane** under the staff (`fhpLaneSvg`, `STAFF_H` grew by 26 px
with `STAFF_SB` unchanged so only the band under the staff gained room): one
bar per FHP labelled "5–8", grey automatic, teal the user's, dashed while
pending; the first bar starts at the song start, as the game applies it. Mode
**"Posição da mão (FHP)"** (`modeFhp`, key 0): a click on a note opens
`#fhpPopup` for a new FHP there (fret = its lowest fretted note, width = the
current FHP's) or the one starting there; a click on a lane bar edits/deletes
that one; Notas ▾ → **Repor automáticas** (`#resetFhp`) drops the chart's own.
`fhpByKind[kind]` holds ALL of a chart's FHPs once edited (`fhpEditable`
copies the automatic ones on the first edit), in the BUILT clock like the
notes, seeded from `hand_positions_edited` on load and always sent whole
(`fhpForRebuild`) — through `chartDisplayTime`, the chart's own pending
tempo/anchors, so FHPs follow a sync correction made in the same rebuild (the
build applies them after the warp, in its output clock). Deleting the last one
returns the chart to automatic. A note its user FHP does not frame gets a red
ring. Part of `pendingSnapshot` (undo/redo, drafts) and "Pendente: posições
da mão". The 3D highway's `anchorAt` follows the chart's FHPs (`data.fhps`)
instead of guessing from the next notes. Guarded by `test_hand_positions.py`
(each level only the user's, in order; a level without an FHP's notes drops
it; an FHP inside an arpeggio honoured; the XML; validation — mutation-checked),
`test_the_fhp_editors_hand_positions_reach_the_build` and
`test_the_fhp_editors_hand_positions_are_stored_and_read_back`; with Playwright
and a real build of an invented two-track GP5 (edit, delete, add from a note,
the red ring, undo/redo, Rhythm untouched, rebuild: the XML's FHPs equal what
was sent, `/psarc-check` clean, seeded back with nothing pending, PT/EN, no
page errors). **Never seen in game from here.**

**The automatic placement was then rebuilt on hand-made charts** ("Melhora as
FHPs automáticas também"). The two community CDLC the user sent (Daughtry,
seven charts: 2 Lead, 3 Rhythm, 2 Bass, 3292 fretted notes at each phrase's
full difficulty) were read back (`read_sng`) and their FHPs taken as the
answer. What their authors do: width 4 always, every note inside its FHP; a
chord whose fingering puts the index on a fret has its FHP exactly there; any
other note leaves the hand where it is while a finger reaches it, and the hand
moves at the first note it cannot. `auto_windows` now does exactly that: each
note allows a range of index frets — `position_pin` (the fret fretted by
finger 1, from the chord template's fingers or a GP left-hand finger) pins
it; a single note, a pair fretted with fingers 2-3, or an open string plus one
fretted note (whose `chord_fingering` "finger 1" the authors did not follow)
allow the four frets from which a finger reaches it — and a run continues
while those ranges overlap (fewest moves, each as late as possible), the index
on the lowest note it allows. Measured: the same FHP fret on **98.0%** of the
notes (80.1% for the old greedy span-4 windows, which grouped chords into
windows below their index finger; a Viterbi with a gap-preferring move cost
and a stretch-to-5 variant were both tried and were WORSE — the authors move
where a note stops fitting, never stretch the window), 99.2% within one fret,
344 moves where the authors made 343. Honest limit: one source of hand-made
charts, so the rules are few and generic on purpose; the files cannot ship in
the repo, so the tests pin the rules on invented notes. The pins travel as a
4th element of a position (`PinnedPosition`): `_level_positions` (template
fingers / `left_hand`), `from_arrangement`'s chart positions (the same, via
`template_ids`) and the writer (`template_pins`), so the XML and every SNG
level agree (`test_the_xml_and_the_sng_place_the_same_automatic_hand_positions`);
inside an arpeggio the merged position is free. Guarded by
`test_a_chord_puts_the_hand_on_its_index_finger`,
`test_a_shape_without_the_index_leaves_the_hand_where_it_is` and
`test_the_hand_moves_at_the_first_note_it_cannot_reach` (each rule
mutation-checked); a real build's `/psarc-check` is clean.

### Clearing note edits ("Notas ▾" → Limpar)

The companion to the seeding fix in the note-editor section: once committed
edits are seeded back into the viewer, discarding them has to be an explicit
action rather than a side effect of reopening the job. "Limpar esta pista"
drops the current arrangement's `note_overrides`, "Limpar em todas" drops
every arrangement's; both send the smaller dict on the next rebuild, which
genuinely removes them. `updateNoteEditsInfo` shows the per-arrangement count
and disables both buttons when there is nothing to clear.

### The recommended workflow: "Corrigir daqui" (`newbeat` mode, `/detect-tempo`)

This is the RECOMMENDED sync mode (it used to be selected on entry; since
2026-10-15 no mode is — `syncMode = null`, reset by `closeDetail` — because "sempre
que entro … existe um modo que está selecionado e não devia": the first click
on a note re-timed the song), and it is the one the
user found actually holds up on real material — worth recording why, because it
is the same principle every removed automatic tool was trying and failing to
apply on its own.

The user listens until the chart starts drifting away from the recording and
clicks that note. `reTempoFromHere` then:

1. pins the clicked note **where it already sits** (`setAnchor(origT, dispT)`) —
   so nothing before the click can move, and whatever was already correct stays
   correct;
2. measures the recording's tempo **from that instant onward**
   (`/detect-tempo` → `detect_tempo_from`, metrically corrected by
   `suggest_tempo_scale`);
3. stretches only the tail `[click, last note]` by that factor.

**The factor is relative to the timeline on screen, and the detector's prior is
the chart's own tempo.** Both halves were wrong and both pushed the same way —
"dá sempre tempo maior e fica muito acelerado". (a) `/detect-tempo` measured the
factor against the GP file's **header** tempo, while the viewer applies it as a
relative stretch of the ALREADY-displayed tail: that double-counts the song's own
tempo changes (a section authored slower than bar 1 got "corrected" by that whole
difference) and, worse, re-applies the same absolute factor on every repeat, so
correcting one passage twice compounds (×0.9 → ×0.81 → ×0.73) into a chart
running away. The viewer now sends `chart_bpm` — the live BPM readout at the
click — and the factor is measured against that, so a second run on an
already-correct passage returns ×1.000. (b) librosa weights its tempo candidates
with a log-normal prior centred on `start_bpm`, which **defaults to 120**; left
there it reads a slow song at double time, which is literally "always a higher
tempo, never a lower one". `chart_bpm` is passed through as `start_bpm`, turning
the open question into the narrow one ("faster or slower than this?"). (c)
`suggest_tempo_scale` broke a genuinely ambiguous half/double pair with
`abs(scale - 1)`, which is asymmetric — an octave high scores 0.5, an octave low
scores 1.0 — so it always preferred the faster reading; it now compares
`abs(log(scale))`. Guarded by
`test_detect_tempo_measures_against_the_chart_bpm_not_the_header` and
`test_suggest_tempo_scale_does_not_favour_the_faster_reading_on_a_tie`.
`liveInfoAtTime` was also measuring the beat interval on the RAW beat times, so
the `♩ =` readout ignored every pending tempo/anchor edit; it now measures the
displayed spacing (which is what makes it usable as `chart_bpm`).

The division of labour is the point: the HUMAN supplies the one thing the
automatic tools kept getting wrong — WHERE the divergence starts — and the
machine answers the narrow, reliable question, "what is the tempo from here?".
Estimating a whole song's drift curve is hard and was consistently wrong;
measuring a local tempo from a known-good starting point is not.

It repeats safely: each application starts from the timeline the previous one
produced (`dispLast` is read through the current warp), so correcting the same
song four or five times along its length composes instead of fighting itself.

### Marking the bars by ear (`Marcar a ouvir`, tap-to-sync)

"The syncing tools are pretty bad too and don't work very well with tabs that
aren't already perfectly synced" (r/rocksmith, 2026-10-15, on a tab its author
wrote on Songsterr: one tempo, never marked against a recording). Every other
tool asks the user to find, one by one, where the score drifts. What makes a
Songsterr tab line up "perfectly" is a person having marked when each measure
starts; this card lets the user do exactly that while listening. Card
`#tapSyncCard` in the Sincronização inspector (after Andamento): from bar N
(bar 1 seeks to the recording's start; any other plays from the cursor), tap
**on every bar** (downbeats) or **on every beat** (`tapGrid`), "Começar a
marcar" starts playback, **B** (or the big `#tapHit`, on `pointerdown`) taps,
**Backspace** takes the last back, **Esc** ends (a capture-phase listener, so
Backspace is not "delete the selected notes"); it ends by itself after the last
grid point, on a tab switch, a job load or an undo. Each tap is the playhead
minus the output latency (`tapLatency`: `outputLatency + baseLatency`, ×
playback rate — slowing playback down is the recommended way to mark, and the
taps stay in recording time). `smoothTaps` (on by default) moves each tap onto
the least-squares line through its ±2 neighbours, so the hand's ±30 ms jitter
does not shake every bar while a tempo change spread over bars still comes
through. `planTaps` (pure) turns them into ORDINARY pending anchors: each
tapped grid point (its `previewScale` origin) → its tap; pending anchors inside
the tapped span superseded; what follows the last tap keeps its own timing,
shifted by that tap's difference (anchors after it too, the song's end pinned);
the song's start pinned where it shows now when no kept anchor precedes the
taps (a lone "Início" anchor is a uniform shift that stops being one beside
others — the `planBarRetempo` lesson). So it previews live as the user taps,
rides "Aplicar e reconstruir", the main-chart propagation and the per-bar BPM
labels/GP tempo export, with no backend change; `recordPending` is held while
marking so the whole run is ONE undo step. Browser-only, no pytest coverage:
`smoothTaps`/`planTaps` checked with Node (jitter, tempo change kept, the
supersede/shift/pin rules — each mutation-checked); with Playwright on a live
server and a real build: 110-BPM chart tapped at 100 BPM, five bars landed on
the taps (±30 ms, the latency compensation), Backspace/Esc, one Ctrl+Z took
all six anchors back and redo restored them, the rebuild's bars sit on the
taps, `/psarc-check` clean; beats mode too; PT/EN, no page errors. **Not used
by a real user on real music from here.**

### Attacks marked by ear ("Toco em cada ataque", `marked_attacks`)

Liam's request (2026-10-20): mark every strum by ear, compare it with the
notes and snap notes to it. A third choice in "Marcar a ouvir"'s `#tapMode`
(`attacks`): "Começar a marcar" plays from the cursor, **B** taps, Backspace
takes the last back, Esc ends (the same `tapState`/keys as the bar taps, with
`mode: 'attacks'`). A tap is **seconds of the recording file**
(`audioTime() - tapLatency() - leadInBuilt`), so no sync correction moves it,
and it creates NO anchor: the list is the chart's, stored on the server at
once (`PUT /jobs/{id}/marked-attacks` `{arrangement, times}` → sorted, to the
millisecond, doubles < 1 ms dropped, an unbuilt chart a 422, an empty list
removes it; `params["marked_attacks"][kind]`, `ArrangementOut.marked_attacks`,
portable in `.rfproj`, inherited by a fork, dropped by `/reload-gp` with the
old recording's measurements). A run replaces the taps between where it began
and its last tap (`applyMarkedRun`); a run ended by a tab switch, an undo or a
version load is saved first (`finishMarkedRun`). It is NOT a pending edit —
the build never reads it — so it has its own undo (`markedUndo`, the card's
"Desfazer", this session only). Drawn by `markedSvg` (green, y 26-37, just
above the staff, under the detected attacks' band): matched within
`MARKED_MATCH_S` (80 ms — a hand is less exact than a detector), only notes
inside the tapped span compared; a tap with no note = tall tick + dashed line,
a note with no tap = hollow square; the card (`#markedBox`, `renderMarkedBox`)
gives the counts, the notes' mean offset from the taps, ◀/▶ to each
difference and its legend (also in "Legenda"). Correcting: `#snapDiv` →
"Ataques marcados" (`snapDiv = 'marked'`): `snapGridTimes`/`noteEditGrid` use
`markedChartTimes()` (each tap → `toneChangeChartTime(recordingDisplay(s))`,
where it shows through the pending tempo/anchors), so drags, double-click
inserts and tails land on taps; "Encaixar as notas selecionadas nos toques"
(`snapSelectedToMarked`) moves each selected note group to the nearest untaken
tap within `MARKED_SNAP_S` (250 ms) as note overrides (all out, then all in;
a clash with an unselected note refuses everything). Guarded by
`test_attacks_marked_by_ear_are_stored_per_chart_and_reach_the_viewer` and the
`marked_attacks` line in
`test_what_was_measured_on_the_old_recording_is_dropped_with_it`; with
Playwright on the invented "Curvas" project (PT 1440 / EN 760 px): 6 B + one
Backspace saved 5 taps on the server, undo emptied it, taps planted 40 ms after
each note read "7 de 8 … 40 ms antes", the snap grid gave the 8 taps, snapping
the selection moved 7 groups (one too far, said) and the mean offset vanished,
Ctrl+Z restored it, no page errors. Not used by Liam yet.

### From the cursor to the end, one tempo, and moving a block (a user's sync workflow)

"the main thing, for me, is getting the BPM setting correct, marking the first
bar, and then going along the song and moving the notes … knowing how to select
all the notes after the cursor would be cool … the little number with the BPM
above the notes was different (faster) than the start" (a user, r/rocksmith,
2026-10-17). Three pieces, browser-only:
- **Notas ▾ → Do cursor até ao fim / Shift+End** (`selectFromCursor`): every
  note group of the chart whose displayed time (`warp(previewScale(t))`) is at
  or after the cursor (`currentPlayheadT + viewOrigin`) becomes the selection;
  in "Arrastar", dragging one moves them all.
- **Moving a selection moves only the selection** (`planBlockMove`, pure, used
  by the group drag): anchors inside the block move with it, the rest stay,
  the notes just outside it are pinned where they show and both ends of the
  chart (`chartSpan`) are pinned. The drag used to add only the block's two
  anchors: with a pending "Início" (a lone anchor, a uniform shift) the notes
  between it and the block were dragged part of the way (+0.17/+0.33 s for a
  +0.5 s drag in the Node check) and, with notes after the block, those lost
  the "Início" (identity past the last anchor) — BUG-0295.
- **Andamento → Um só andamento** (`#oneBpm`/`#oneBpmApply`): `setBarsTempo`
  over every bar of the chart (`chartMeasureRange`), the start left where it
  shows (`planBarRetempo`'s pins); the placeholder is bar 1's tempo as shown
  (`refreshOneBpm`, from `showArr`). For a tab whose authored tempo changes
  where the recording's does not — what the user saw as "the ♩ number above the
  notes got faster".
The guides gained "Passo a passo, numa tab que nunca foi sincronizada" with
exactly that workflow. Verified: `planBlockMove` with Node (a lone "Início" +
a block to the end, a block in the middle, no anchors — the old two-anchor rule
fails the first); with Playwright on the invented "Deriva" project (PT/EN):
"Início" +1 s, cursor at the middle, Shift+End selected 139 of 277 notes, a
+0.5 s drag moved those 139 by exactly 0.5 s and the 138 before by 0, "Um só
andamento" 100 put every bar at 100.00 BPM with the first note unmoved, the
shortcut in the "?" list, no page errors.

### Manual drift correction (`sync_anchor_stages`)

A single `offset_s` only fixes a constant lead-in; if the GP file's tempo map
doesn't exactly match the recording, drift grows over the song. The tab viewer
lets the user drag a note (or a rubber-band-selected excerpt) to where it
should play; each drag/excerpt becomes a `(chart_time, corrected_time)` anchor,
and `_build_time_warp` remaps notes, beats, sections and lyrics
(`_warp_parsed_track`):
- **One anchor** (single-note drag) is a uniform shift applied to the whole
  timeline — for "the whole song's lead-in is off by X".
- **Two-or-more anchors** (excerpt drag) rigidly shift/stretch only the
  excerpt between the first and last anchor; everything before/after is left
  untouched (identity) so unrelated parts of the song don't move.

`GpJobSpec.sync_anchor_stages: list[list[tuple[float, float]]]` is a list of
correction *rounds*, applied in order. Each round's anchors are expressed in
the timeline produced by the *previous* round (i.e. exactly what the tab
viewer shows when the user draws them). `/jobs/{id}/rebuild` appends a new
round to `params["sync_anchor_stages"]` rather than overwriting it, so
reopening a completed job, loading its arrangement (already reflecting prior
rounds), and adding more corrections composes correctly instead of discarding
earlier work. Do not collapse this back to a single `sync_anchors` list —
anchors from different rounds live in different (already-warped) coordinate
systems and cannot simply be concatenated.

**A tempo/offset change RE-EXPRESSES the already-committed anchors (the preview
must equal the rebuild).** The build computes `W(x·s + S)` — parse at
`tempo_scale` `s` with score shift `S = max(offset_s, MIN_LEAD_S) + lead_in_s`,
THEN warp — while the tab viewer previews `R(W(x·s_built + S_built))`: it
rescales the ALREADY-WARPED times it read back from the built XML (it never
re-derives the raw GP times). Composition does not commute (`R∘W ≠ W∘R`), so once
ANY anchor stage is committed, changing the tempo made the rebuild differ from
the preview by **`d·(r−1)` on every note** (`d` = net shift the committed anchors
introduce, `r` = the tempo ratio) — a *constant* desync, invisible in the viewer
but plainly wrong in game. That was the "no programa está sincronizado, no
Rocksmith não" bug, and it fires on the ordinary workflow (drag → rebuild →
BPM change → rebuild). `rebuild_job._remap_committed_anchors` maps every
stored anchor pair through the viewer's own map `φ(t) = (t − S_old)·r + S_new`,
making each stage `W' = φ∘W∘φ⁻¹` so `W'∘φ = φ∘W` exactly; each arrangement is
conjugated with ITS OWN tempo ratio (tempo_scale is per-arrangement) but the
shared job-level shift. Guarded by
`test_tempo_change_reexpresses_committed_anchors_in_the_new_timeline` and
`test_committed_anchors_untouched_when_the_timeline_does_not_change`.
**The two halves of `S` must match on both sides**: `web/app.js`'s `scoreShift`
omitted `lead_in_s` (and `previewScale` did not re-add it), which desynced the
rebuild by `lead_in_s·(r−1)` on its own — both now include it. If you change how
`score_shift` is computed in `gp_pipeline`, change `scoreShift`/`previewScale`
in the same commit.

**Pending anchors are kept in CHART order, and a crossing is flagged in the
list.** `setAnchor` used to append, so the list showed insertion order — a real
case read "Correção 4: 196.93s" above "Correção 5: 195.88s", which makes the
numbering describe an order the music does not have and hides a correction that
crosses another. `setAnchor` now sorts by chart time (the warp sorts internally
on both sides, so no timing changes — only what is shown and the numbering that
follows), and `renderAnchorsList` marks any row whose target is at or before the
previous row's with "⚠ cruza a anterior". That is the same condition
`_check_anchor_order` rejects at build time; surfacing it in the list means it
is fixable while it is still pending, instead of failing at "Aplicar e
reconstruir".

**Conflicting anchors are rejected, not silently warped into nonsense.** Two
anchors whose corrected times contradict their chart-time order (a later chart
point mapped to an earlier recording instant than an earlier point) make
`_build_time_warp` fold back on itself — the beat grid comes out of
chronological order and construction crashes deep inside `TempoMap` with a
cryptic `ValueError`, giving no clue which correction caused it. Successive
"Mover seguintes" clicks are the usual way to create this by accident (each one
re-anchors the arrangement's LAST note to a new target, so two clicks can leave
it pointing at inconsistent targets). `_check_anchor_order` validates each
round before it's applied and raises `IngestionError` naming the two
conflicting points in seconds, so the user knows which correction to remove or
adjust. Guarded by `test_conflicting_sync_anchors_raise_clear_error` /
`test_check_anchor_order_accepts_valid_and_rejects_crossing`.

**A local stretch re-inflates sustain — re-trim after warping.** A correction
that maps a chart interval to a WIDER corrected interval (a local stretch
factor > 1) scales every note's warped sustain by that same factor
(`sustain = warp(time+sustain) - warp(time)`). This can re-inflate — or make
notes overlap outright — a sustain `apply_sustain_gap` already trimmed to a
small gap at parse time (first fixed, on the un-warped timeline, in commit
`ef36b61`): on the highway, fused/overlapping sustain trails render as "tall
pillars" or a solid wall instead of separate note shapes. `_warp_parsed_track`
re-applies `apply_sustain_gap` to the warped notes so the gap invariant holds
regardless of what a sync correction did to the local tempo. Guarded by
`test_warp_re_trims_sustain_after_a_local_stretch`. **It moves notes with
`dataclasses.replace`, never a fresh `TabNote`**: rebuilding each note from a
hand-picked field list dropped every field it did not name — bend curves,
fingering, pick direction, unpitched slide-outs — the moment a song had ANY
sync correction (`_strip_mute_techniques` had the same shape). Guarded by
`test_a_sync_correction_keeps_every_note_field_and_moves_the_lyric_notes`.

**Beat snapping (drag).** By default (checkbox "Encaixar em:") a note (or
selection) drag snaps its target to the nearest position of a grid, so
corrections jump grid-to-grid instead of sliding continuously — cleaner and
jitter-free for the common "align this note to a beat" correction. The grid
resolution is a dropdown (`snapDiv`): bars (downbeats only), whole beats, or
beats subdivided into 2/3/4 (`snapGridTimes` interpolates between the real
ebeats, so tempo changes are respected). The beat times come from
`ArrangementOut.beats` (ALL ebeats — downbeats + off-beats, distinct from
`bars`, which is downbeats only for numbering); the viewer warps each grid point
through the same `previewScale`+anchor warp as the notes, caches those display
positions at drag start (`snapPositions`), and `snapDisplay()` snaps to the
nearest. Holding **Alt** during a drag bypasses the snap for free placement. It
only changes the drag TARGET — the anchor/warp machinery is unchanged, so it
composes with everything else.

**Selecting notes.** Selection is modifier-driven and independent of the sync
mode: a plain click selects one note (and sets it as the pivot), **Shift+click**
selects the inclusive range from the pivot to the clicked note (`rangeSelect`),
**Ctrl/Cmd+click** toggles a single note, and a click on empty staff clears the
selection. Dragging any selected note moves the whole selection in one rigid
block (snapping the earliest to the grid) — but ONLY in the "Arrastar" mode;
re-clicking the active mode button deselects it to a neutral state (no mode
highlighted, note-drag disabled, selection still works), rather than falling
back to "Arrastar". (The older
rubber-band "Excerto" box-select still exists but Shift+click is the primary
path.) True note *editing* — moving a note to a different beat, changing its
fret/techniques, or inserting/removing one — is a separate mode ("Editar
notas", see "Note editor" below), no longer notes-come-exact-from-the-GP-only.

**Auto-scroll during a drag/box-select (fixes "só seleciono o que está
visível").** `#tabwrap` is a plain `overflow-x:auto` container around a
potentially very wide SVG (a long song can be thousands of pixels), and it
never scrolls on its own while a pointer-capture drag is in progress — so
before this fix, the rubber-band ("Excerto") box, a single-note drag, or a
selected-block drag could only ever reach whatever was already visible in the
current viewport; the mouse itself is bounded by the browser window, and
dragging to the screen edge did nothing. `handlePointerMove` (the pointermove
body, refactored into a named function so it can be re-invoked from a second
caller) is now also driven by a `requestAnimationFrame` loop
(`autoScrollStep`) that runs for as long as ANY of the four gestures
(`rubberBand`/`groupDrag`/`dragging`/`lyricDrag`) is active and the last known
pointer position sits within `AUTO_SCROLL_EDGE_PX` (48px) of `#tabwrap`'s left
or right edge: each frame it nudges `scrollLeft` (up to `AUTO_SCROLL_MAX_PX`,
scaling with proximity to the very edge) and re-runs `handlePointerMove` with
the cached last pointer position — necessary because the rubber-band box's
x/width are SVG-local coordinates (`clientX - rect.left`), and `rect.left`
itself shifts as the container scrolls, so the box must be recomputed even
though the mouse hasn't moved. Stops immediately on `pointerup`/`pointercancel`
(verified: no further `scrollLeft` change after release). Guarded manually via
Playwright (a 4000px-wide synthetic chart, a 600px viewport, holding the
rubber-band drag at the right edge reaches and selects a note far outside the
initial view) — no pytest coverage (pure `web/app.js`, same category as the
other browser-only interaction fixes in `TESTING.md`).

### Per-arrangement sync (`arrangement_sync`)

`tempo_scale` and `sync_anchor_stages` are **per-arrangement**: each chart
(Lead/Rhythm/Combined) is parsed and drift-corrected independently, so dragging
a Lead note never moves the Rhythm chart. `GpJobSpec.arrangement_sync: dict[str,
ArrangementSync]` is keyed by `ArrangementKind.value`; an arrangement absent
from it falls back to the job-level `tempo_scale`/`sync_anchor_stages` defaults
(`GpJobSpec.sync_for`). `offset_s` is deliberately NOT per-arrangement — all
arrangements share one `.wem`, so the recording's start is common to all; a
per-arrangement uniform shift is just a single-anchor round. `/jobs/{id}/rebuild`
takes an optional `arrangement` to scope `tempo_scale`/`sync_anchors` to one
chart (seeding its entry from the job-level defaults on first edit). The tab
viewer keeps a separate pending-anchor set per tab and exposes one
"Aplicar e reconstruir" that commits the current tab's tempo+anchors plus the
shared offset/tuning in a single rebuild. When there are multiple arrangements,
a checkbox "Aplicar sync a todos" appears; when checked, `RebuildIn.apply_to_all`
is set and the `rebuild_job` endpoint propagates `tempo_scale` and
`sync_anchors` to every existing per-arrangement override AND the job-level
defaults, so all charts share the same correction in one rebuild instead of
requiring the user to adjust each arrangement separately.

**"Passo 1 — Início da música" is per-arrangement.** `offset_s` itself stays
job-level for the reason above (one shared, once-padded `.wem`) and is set
once at job creation; but Step 1's runtime precision tools in the tab
viewer — the numeric field + slider, "Início = cursor", and the guided "🎯
Detetar 1ª nota" 3-click flow — pin just the CURRENT arrangement's first note
independently of the others, for GP files whose tracks were tabbed with a
different pickup/lead-in per instrument, where a single shared offset can't
fit both. There is deliberately only ONE "first note time" control in the UI
(an earlier version added a second, per-arrangement-only panel; users found
two confusing, so it was folded back into Step 1 — see git history if
resurrecting the idea). It reuses the existing single-anchor mechanism (a
lone `sync_anchor_stages` anchor = a uniform shift for that arrangement)
rather than a new field: `updateSyncOffsetDisplay()` (called from `showArr`
on every redraw/tab-switch) refreshes Step 1's field from
`buildTimeWarp(syncAnchors)(previewScale(firstNoteChartTime)) - viewOrigin`
— for the common case (no per-track anchor yet, the track's first note sits
at its own timeline's start) this equals `offsetLive` exactly, so switching
tabs looks unchanged until a track's first note genuinely has its own
pickup, at which point the field diverges to show and let you fix THAT
track's own value. Every edit — the field, the slider, "Início = cursor"
(`setTrackStart(audioTime())`), and the guided flow's final click — always
writes a per-arrangement anchor via `setAnchor`, never `setOffsetLive`
(which now only fires from `initSync`'s initial load). All write into the SAME per-tab pending anchor array Step 3
already uses (`syncAnchorsByKind[currentKind()]`), so they ride the existing
"Aplicar e reconstruir" commit — no separate button, no backend change.
`setTrackStart`/the guided flow both pass the note's UNwarped
`previewScale(chartT)` as the anchor's origin (matching `'drag'` mode's
convention, not `'tap'` mode's `buildTimeWarp`-wrapped one) specifically so
that repeatedly nudging the slider/re-running the guided flow updates the
SAME anchor slot instead of compounding into an unintended multi-point warp.
**With other pending anchors the start moves the WHOLE chart**
(`planStartShift`, 2026-10-17: "when you do the sync automatically button and
then want to go back and move the intro it only adjusts the first section"):
after an auto-sync, taps or a bar alignment the first note's anchor is one
point of a piecewise warp, so moving it alone stretched only the span up to
the next anchor. Now, with two or more pending anchors, every one shifts by
the same amount (the first note's own point added, both ends of the chart
pinned via `chartSpan` so the identity-outside warp still covers every note);
with none or one it stays ONE anchor at the first note, as before (a lone
anchor elsewhere is a uniform shift, replaced rather than joined). The
guided "Detetar 1ª nota" flow goes through the same `shiftTrackStart`.
Browser-only, no pytest coverage: `planStartShift` checked with Node (the
auto-sync shape, none/one anchor, a pair without end pins; the old
first-anchor-only rule fails it) and with Playwright on the invented
"Deriva" project with the 31 anchors a real auto-sync left: "Início" +1 s
moved all 277 notes and 32 bars by the same 1.002 s (the old code: most by
0), one Ctrl+Z back to the auto-sync result exactly, PT/EN, no page errors.

**All anchor-writing modes use the UNwarped origin (fixed "Mover seguintes"
moving notes the wrong way).** `'tap'`, `'movefrom'` and `'newbeat'` used to set
each anchor's ORIGIN to the WARPED position (`warp(previewScale(t))`); with no
pending anchors that coincides with the unwarped value so it looked fine, but
the moment a pending anchor already exists (e.g. Step 1's own "Início"), a
warped origin corrupts `buildTimeWarp`'s piecewise map and the clicked note
lands somewhere else entirely — the "notes moved away from the cursor instead
of onto it" bug. All three now use `previewScale(t)` (unwarped) as the origin,
same convention as `'drag'`/`setTrackStart` above, and compute the target from
the CURRENT `warp(...)` value + the intended delta.

**"Mover seguintes" pins the region BEFORE the click so it stays put.**
`'movefrom'` shifts the clicked note + everything after it by a delta, via two
anchors (clicked note → cursor, last note → same delta). But those two anchors
alone don't hold the region before the click: once a prior anchor exists (e.g.
Step 1's "Início", which as a lone anchor is a *uniform* shift), adding the
clicked/last anchors turns the previously-uniform pre-click segment into an
*interpolated* one, dragging the preceding notes along ("mover seguintes
atualizou também as notas que ficaram para trás"). The fix mirrors what
`'newbeat'`/`reTempoFromHere` already does with its pivot: also pin the note
immediately BEFORE the click at its CURRENT displayed position
(`setAnchor(previewScale(prevNoteTime), warp(previewScale(prevNoteTime)))`) —
a point already on the current warp curve, so everything up to it is unchanged
and only `[clicked, last]` shifts. (`'newbeat'` never had the bug because its
pivot anchor already pins the click to its unchanged position.)

### The main chart for sync ("Pista principal", `sync_main`)

"quando eu ajusto uma das tracks (… defino qual é a principal para sincronia),
as outras também se sincronizam com o tempo equivalente que foi alterado: se na
principal passo de 0 para 1 segundo, uma que esteja a 30 passa para 31". The
Sincronização tab's **Pista principal** card (`#syncMainCard`, only with ≥ 2
charts) picks one chart; `PATCH /jobs/{id}/sync-main` stores it in
`params["sync_main"]` (`JobOut.sync_main`, inherited by forks, no rebuild).
Whatever changes on the main chart's pending sync — its "Início", its tempo,
any correction — reaches every other chart as the **same change of time**:
`mainSyncFollow` (top of `showArr` and of `applyAll`, the `lyricsFollowSync`
pattern) takes D = built time → where the main chart shows it now, before and
after the edit, and sets each other chart's display map to
`(D_new ∘ D_old⁻¹) ∘ G`, written back as that chart's own PENDING anchors
(`followAnchors`). So it previews on the other tab, can still be corrected
there, undoing on the main takes the others back, and the rebuild commits it.
A uniform shift on a chart with ≤ 1 anchor stays ONE anchor on its first note
(what its "Início" field edits — 30 → 31 in that field); anything else pins
both ends of the chart (the multi-anchor warp is identity outside its range)
plus every point where either map bends (`invertIncreasing`). Only edits made
ON the main chart travel; editing another chart is that chart's alone.

**The rebuild now commits every chart's pending sync** (`RebuildIn.other_sync`,
`otherPendingSync`): before, only the chart on screen was sent and any other
tab's pending corrections silently disappeared — which the main chart's
propagation would have hit on every rebuild. Other charts' tempo goes in
before `_remap_committed_anchors` (so their committed stages are re-expressed
with their own ratio), their anchors after, like the chart on screen; ignored
with `apply_to_all`, which already speaks for every chart (and still REPLACES
their tempo — the main chart is the composing alternative). Guarded by
`test_a_rebuild_commits_every_charts_pending_sync_not_only_the_one_on_screen`
and `test_the_main_chart_for_sync_is_remembered`; the viewer with Playwright on
the user's Ocean Eyes built as Lead + Rhythm: Lead "Início" 1.575 → 2.575 moved
the Rhythm's 8.400 → 9.400 (its own field reads 9.40), undoing cleared it, a
×1.05 tempo on the Lead put four Rhythm notes exactly where the map says, and
a real rebuild moved all 1374 Lead and 1470 Rhythm notes by exactly 1.000 s.

### Sync by bar number (`barSyncPanel`)

For a track whose real content only starts several measures in — e.g. Rhythm
rests through the intro and its first real note coincides with **bar 7** — the
per-track "Início" tools above only pin the very FIRST note, which isn't
useful when the correction point is mid-song. A dedicated panel right after
Step 1 lets the user pick **any bar number** of the current arrangement and
align it two ways:
- **"= cursor"**: pause/scrub playback to where that bar should sound, click —
  same `setAnchor(previewScale(barChartTime), currentPlayheadT + viewOrigin)`
  pattern as `setTrackStart`, just for an arbitrary bar instead of the first
  note.
- **"Sincronizar" with another arrangement**: aligns the chosen bar directly to
  the SAME bar number's current position in an already-synced reference
  arrangement (e.g. Rhythm's bar 7 → Lead's bar 7) — no listening required.
  Sound because bar numbers come from ONE shared, song-level measure header in
  the GP file (`parser.py`: `for measure in track.measures: … header.number` —
  every track iterates the same measure sequence), so bar N is the same
  musical instant across every track before any per-track correction.

  Reading "where does the reference arrangement's bar N currently sit" requires
  that arrangement's OWN live tempo/anchors, independent of whichever tab is on
  screen — `arrangementPreviewScale(idx, t)`/`arrangementDisplayTime(idx, t)`
  generalize `previewScale`/`buildTimeWarp(syncAnchors)` to read `arrangements[
  idx]`'s own `tempo_scale`/`tempoScaleByKind`/`syncAnchorsByKind` instead of
  the current tab's live globals (`tempoScaleLive`/`syncAnchors`), which is only
  possible because every arrangement's pending edits stay in those `ByKind` maps
  for the whole session, not just the active tab's.

  `updateBarSyncPanel()` (called from `showArr`) repopulates the bar dropdown
  from `arrangements[currentArr].bars` and the reference dropdown from every
  OTHER arrangement. Both actions write into the SAME per-tab pending anchor
  array as everything else (`syncAnchorsByKind[currentKind()]`) — rides the
  normal "Aplicar e reconstruir", no backend change.

  Both the panel and the click-a-note popup below share one primitive —
  `alignBarTo(measure, target)`: a single anchor pinning that bar's downbeat
  (`setAnchor(previewScale(barChartTime), target)`) to a bundle-time display
  position, which is the cursor (`currentPlayheadT + viewOrigin`) or another
  arrangement's same bar (`refBarTarget`). Multiple pins compose into a
  piecewise drift correction.

**Bar-align popup (`'baralign'` mode, 📏).** For doing MANY bar-syncs quickly
without hunting the bar number in a dropdown each time: a sync mode where
clicking a note opens a small floating popup (`#barAlignPopup`) with the bar
numbers, the clicked note's OWN bar pre-selected (`openBarAlignPopup` finds the
containing bar). "= cursor" calls `alignBarTo(bar, currentPlayheadT +
viewOrigin)`; "= pista" (shown only with ≥2 arrangements) aligns to the same
bar of a chosen reference arrangement. It's the same `alignBarTo` primitive as
the panel — just a faster, note-driven entry meant to be repeated along the
song for progressive drift correction. Dismisses on Escape or an outside click
(a note click reopens/repositions it).
**The bar line itself opens it too** — "alinhar o compasso no início dele,
mesmo que não tenha notas": `alignBarTo` always pinned the bar's DOWNBEAT,
but the only way in was clicking a note, so a bar starting on a rest or a
note held from the previous bar could not be picked on the score. Each bar
line (and its number) now carries a transparent `.bar-hit` target
(`data-t` = the bar's chart time), drawn BEFORE the notes so a note on the
line still wins; in `'baralign'` mode a click on it opens the popup for
that bar, and in every other mode it is ordinary empty staff and still
seeks (the click-to-seek convention the note editor learnt the hard way).
`#tabsvg.mode-baralign` gives it a pointer and a hover band. Verified with
Playwright: bar 4 (no note on its downbeat) opens from its line, "=
cursor" lands its start exactly on the cursor, and the same click in
"Arrastar" moves the playhead.

**Per-bar tempo — "mudar o BPM do compasso" (`setBarsTempo`).** The 📏
popup and the "Sincronizar por compasso" panel both carry an **Andamento**
row: ♩ = [BPM, pre-filled with the bar's current tempo as displayed] até ao
[compasso] → Aplicar. Every bar in the range gets that BPM; everything AFTER
it keeps its own tempo and is only shifted by the difference (a later
passage is never re-timed because an earlier bar was). No new backend
concept: `planBarRetempo` (pure) turns it into ordinary pending anchors —
pin the span's start where it currently sits, put its end at
`start + beats·60/bpm`, move every pending anchor after the span by the
difference (anchors inside the span are superseded), and pin the song's end
with that difference so the tail follows. A LONE pending anchor is a
uniform whole-song shift that stops being one once a second anchor exists
(`buildTimeWarp` is identity outside a multi-anchor range), so the song
start is pinned with that same shift first — without it the bars before
the edited one silently lost Step 1's "Início". `syncAnchors` is mutated in
place (it IS the `syncAnchorsByKind` entry). Because it is anchors, it
previews live, rides "Aplicar e reconstruir", is drawn amber by
`barTempoTable` and is exactly what "Guitar Pro com os andamentos
corrigidos" writes. The last bar has no next downbeat, so its span runs to
its own last beat (one beat short). BPM bounded 10–400 (the GP export's
own bounds). Browser-only, no pytest coverage: `planBarRetempo`/`barSpan`
checked with Node (no anchors, a lone anchor before/after the span —
mutation-checked —, anchors after/inside the span, faster and slower, the
last bar) and the UI with Playwright on a 139-bar chart: bar 4 171→90 BPM
leaves bars 3/5/6/8 at 171.43 and shifts the rest by exactly 1.267 s,
bars 6–7 → 100 via the panel, and a real rebuild keeps 90/100/100.

**Cursor as an explicit snap target (fixes unreliable "drag to the cursor").**
Before, only the click-based `'tap'`/`'movefrom'` modes snapped to the live
playhead (`currentPlayheadT`); the familiar drag gesture (`'drag'`/`'excerpt'`
modes) only ever snapped to the beat grid, with no visual difference between
the two gestures — the likely source of "arrastar para o cursor nem sempre
funciona". `#snapDiv` now has a `"cursor"` option; `snapDisplay` special-cases
it to return `currentPlayheadT + viewOrigin` directly (skipping the
nearest-neighbor grid search), so the ordinary drag gesture reliably lands on
the playhead when that option is picked, with no mode-switching required.

**Numeric anchor editing.** `renderAnchorsList` rows now show the target time
as an editable `<input type=number>` (was plain text) — typing an exact value
calls `setAnchor` the same as a drag would, so a correction no longer has to
be pixel-perfect by mouse, and an already-placed correction can be adjusted
without delete-and-redo. Also fixed: the single-note and group-drag `pointerup`
handlers redrew the score but never called `renderAnchorsList`/
`updatePendingChangesInfo`, so the pending-anchors list silently went stale
after a plain mouse drag (it only refreshed after `'tap'`/`'movefrom'`/
`'newbeat'` clicks) — both handlers now refresh it too.

**Every time a user types is to the millisecond** ("Quero que os ajustes
alcancem até aos ms", 2026-10-20): the Início field and slider, the correction
rows, sections, tone changes, lyric times/lengths, the lyric nudges and
"Silêncio inicial" are `step="0.001"` and shown with three decimals (they were
two, or one). Nothing rounded them further; the XML writes milliseconds.

**Zoom keeps its place.** `setZoom` used to rescale `tabPx` and redraw without
touching `#tabwrap`'s `scrollLeft`, so the same pixel offset silently mapped to
a different time after zooming — the view jumped away from whatever passage
you were trying to zoom into. It now captures the centered time before
changing `zoomLevel` and restores the equivalent `scrollLeft` after the
redraw, so zooming in/out keeps the same passage in view.

**No native text selection during score interaction.** Shift+click (a classic
browser text-selection trigger) or any click-drag over the SVG's `<text>`
labels (technique letters, tuning names, bar numbers) used to highlight them
like page text instead of purely driving the custom note-selection/drag logic.
Fixed with `user-select:none` on `#tabsvg` plus `e.preventDefault()` as the
first line of the SVG's `pointerdown` handler.

The tab viewer's x-axis is **recording time** (0s at the left edge): notes are
drawn via `timeToX` (which subtracts the lead-in `viewOrigin` from the
bundle-time positions), so the playhead starts at 0 instead of at the first
note. Anchor math stays in bundle time so corrections round-trip through a
rebuild unchanged.

The viewer's `isGpJob()` guard on `previewScale`/`playheadDisplay`/`viewOrigin`
(identity sync for non-GP jobs, hiding `#gpSyncControls`) remains for legacy
non-GP job rows; today only GP jobs are created. `GET /jobs/{id}/source-audio`
serves `job.source` when it's a real file and otherwise falls back to the
ingested `input.*` / `normalized.wav` in the job's work dir.

**String labels show the real tuning.** The staff labels each string with its
actual pitch (`stringLabel` = standard MIDI `[40,45,50,55,59,64]` + the
arrangement's `tuning_offsets`, mapped to a note name), so a Drop C# chart reads
`C# G# C# F# A# D#` instead of the fixed `E A D G B e`. Falls back to standard
if `tuning_offsets` is absent.

**Measure (bar) numbering.** The viewer draws a faint vertical line + bar number
at each measure downbeat. The source is the Song2014 `<ebeats>` (one `<ebeat
time measure>` per beat; downbeats carry the 1-based measure, off-beats `-1`),
which the GP parsers fill from `tempo_map.beats`. `/jobs/{id}/arrangements`
filters `measure>0` into `ArrangementOut.bars`; the viewer warps each bar time
through the same `previewScale`+`buildTimeWarp` as the notes, so bar lines track
pending sync edits. Bars make tempo changes and drift visible — the user can see
exactly which measure slips against the recording and drag-correct it there.

### Section editor — mark/rename song structure on the score

Sections (intro/verso/refrão/solo…) used to come **only** from the GP file's
own measure markers (`GpSection`, extracted in both parsers from a Guitar Pro
"marker" on a measure); there was no way to add, rename, or move one without
going back to Guitar Pro. The **"Secções"** tab of the Partitura inspector
plus a **"Secção" sync mode** (click a note to name where it starts)
let the user edit them directly in the tab viewer, for Riff Repeater and
navigation.

**Job-level, shared across arrangements — same convention as `tone_changes`.**
`GpJobSpec.section_overrides: list[Section] | None = None` (bundle-clock
times, `application/gp_pipeline.py`): `None` keeps each arrangement's own
GP-parsed sections (today's default, unchanged); a list — even empty —
**replaces** the section markers identically on every arrangement, sorted by
time and renumbered. Times are NOT run through each arrangement's own
per-track warp (unlike notes/beats), exactly like `tone_changes` — an accepted
simplification (documented, not silently assumed): if arrangements have very
different `tempo_scale`/drift corrections, a shared section time may not land
on the same musical instant in every chart. `celery_app.py` reconstructs it
from `params.get("section_overrides")` (`None` vs an explicit list — the same
tri-state as `lyrics_events`).

**Surfaced via `ArrangementOut.sections`, not a new endpoint.** `GET
/jobs/{id}/arrangements` already parses each arrangement's built XML; it now
also reads `<sections><section>` into `SectionOut(time, name, number)`,
**excluding** the writer's synthetic trailing `"noguitar"` entry (`writer.py`
always appends one to mark where the phrase timeline ends — a structural
closer, never a user-facing section). `RebuildIn.section_overrides: list[
SectionOverrideIn] | None = None` follows the standard null-sentinel
convention (`None` = untouched; `rebuild_job` writes `params[
"section_overrides"]` only when not `None`).

**Frontend dirty-flag, not always-send.** Unlike `tuning_midi`/`tempo_scale`
(always sent, safe because they're always pre-filled with the live value),
sections have a real prior default (the GP file's own markers) that an
untouched, always-send round-trip could silently overwrite on an unrelated
rebuild. `songSections` (state, shared across tabs) is seeded from
`arrangements[0].sections` on job load; `sectionsTouched` only flips true once
the user actually adds/renames/moves/removes a marker, and `applyAll()` sends
`section_overrides: (isGpJob() && sectionsTouched) ? songSections : null` —
so a rebuild that never touches sections leaves the GP-authored ones alone.
Adding a marker: either the "Secção" sync mode (click a note, prompts for a
name) or "+ Adicionar no cursor" (places one at the current playhead without
needing to land exactly on a note); the list panel's time/name fields are
directly editable (like the sync-anchors list), each edit re-sorting by time.
**Edited sections are sent where the score draws them** (BUG-0339,
`sectionsForRebuild`): the build keeps `section_overrides` as given while the
notes move with the pending tempo/anchors, so a correction made in the same
rebuild left a section behind (drawn at 11 s, built at 10 s). They go through
the chart on screen's `chartDisplayTime`, rounded to the millisecond — and not
only after an edit in this session: `ArrangementOut.sections_edited` (the job
HAS stored overrides) makes the viewer send them on every rebuild, since a
later correction would otherwise leave the stored ones behind too. The GP
file's own sections are warped by the build, so untouched they still send
`null`. "+ Adicionar no cursor" stores the cursor through the inverse map
(`toneChangeChartTime`), so it lands where the cursor shows. Guarded by
`sections_edited` in `test_arrangements_excludes_the_noguitar_sentinel_from_sections`;
with Playwright and real rebuilds: +1 s → the section 10 → 11 s with its
notes, a second +1 s with the sections untouched → 12 s, the cursor add drawn
exactly on the cursor, untouched GP sections → `null`, no page errors.
On the score, section markers span the **full staff height** (distinct from
the tone-change markers, which live in a band below the staff) in teal, with
a `🏷️` label, so the song structure is visible at a glance while scrolling.

### Note editor — add/edit/remove notes and techniques on the score

Until now the tab viewer only ever corrected *sync* (moving a note in time);
the note's *content* — fret, sustain, techniques, bend/slide — always came
verbatim from the GP file, with no way to fix or add a note without
re-exporting from Guitar Pro. A new **"Editar notas" sync mode** (✏️) lets the
user click an existing note to edit or remove it, or click empty staff space
to insert a new one, directly in the browser.

**Genuinely per-arrangement, unlike `tone_changes`/`section_overrides`.**
`GpJobSpec.note_overrides: dict[str, list[NoteOverride]]` (`gp_pipeline.py`)
is keyed by `ArrangementKind.value` — Lead and Rhythm have entirely different
note content, so (unlike the job-level, shared-across-arrangements sections/
tone-changes convention) each kind's edit list is independent; an arrangement
absent from the dict (or with an empty list) is completely unaffected.
`NoteOverride(time, string, fret, sustain, techniques, bend_semitones,
slide_to_fret, deleted)` is a **patch keyed by `(time, string)`**: `deleted=
True` removes the note at that slot, otherwise it upserts (inserts if nothing
was there, replaces if something was) — one primitive covers add/edit/delete
uniformly. **The slot is matched within `NOTE_OVERRIDE_MATCH_S` (5 ms) on the
same string, never by exact time.** The editor only ever sees times read back
from the built XML, which `writer.py` rounds to the millisecond, while the
pipeline's notes carry the parser's full float; the old `round(time, 6)` key
missed about half of them, so a deleted note stayed in the song ("apaguei um
excerto do final mas o som das notas ainda se ouve, mesmo depois de
recompilar": 6 of the last 12 survived) and an edited one gained a twin beside
it (7 of 10 fret edits, 1374 → 1381 notes). A replaced note keeps its own
exact time. Guarded by `test_note_overrides_find_notes_whose_time_the_xml_rounded`
(fails on the exact-key version); reproduced and verified through real rebuilds
of a 1374-note chart (12/12 deleted, 10/10 edited with no twins). `_apply_note_overrides` (pure) does the
merge; applied in `run()` **after** parsing, per-arrangement time-warp, tempo-
scale, AND the `import_mute_techniques` strip — so a manual edit is the final
say and is never silently stripped by that unrelated global checkbox. Times
are bundle-clock, same convention as `tone_changes`/`section_overrides` — the
editor places them directly on the already-warped score, no extra warp needed.

**The grid closes the last bar (`close_beat_grid`).** Both parsers used to
emit one beat per counted beat of every bar and stop there, so the grid ended
on the LAST BEAT of the last bar, not at its end — and any song whose final
notes fall after that beat (eighths to the end: the user's own PDF→GP5 file,
"note at 187.797s beyond final ebeat 187.542s") failed `Arrangement.validate`
and never built. Now the end of the last bar is appended as a downbeat
numbered as the bar that would follow (how EOF charts carry a grid past the
last bar), and an overfull last bar (more than its signature, as a converter
can write) keeps the grid going at the last spacing until it covers the final
note. Two readers had to learn that final downbeat is a bar LINE, not a bar:
`arrangement_writer._measure_grid` stops there (it had been tacking an empty
one-beat bar onto every export — `_steady` in its own tests already had this
shape) and `/jobs/{id}/arrangements` leaves it out of `bars` (still in `beats`,
the snap grid). Guarded by `test_a_song_ending_on_the_and_of_four_builds`,
`test_gp7_grid_closes_the_last_bar_so_a_late_eighth_fits`,
`test_an_overfull_last_bar_still_ends_inside_the_grid`,
`test_the_closing_bar_line_ends_the_last_bar_instead_of_adding_one` and
`test_the_closing_bar_line_is_not_listed_as_a_bar` (all mutation-checked); the
user's file builds end to end.

**Honest limit: still bound by the song's own tempo map.** `Arrangement.
validate()` already rejects a note past the arrangement's final ebeat
("note at Ns beyond final ebeat Ms") — a real, pre-existing invariant, not
new — so a note can only be added within the GP file's authored measure
range; extending the song itself still requires adding measures in Guitar
Pro first. Surfaced as a plain rebuild failure (`job.error`) if violated,
same as any other pipeline error.

**API**: `RebuildIn.note_overrides: dict[str, list[NoteOverrideIn]] | None =
None` (null-sentinel convention — `None` leaves `params["note_overrides"]`
untouched; a set dict, even `{}`, replaces it wholesale). `NoteOverrideIn`
Field-constrains `string` (0-5) and `fret`/`slide_to_fret` (0-24) so an
out-of-range value 422s immediately at rebuild time rather than surfacing as
a deferred build failure.

**Committed edits are SEEDED back into the viewer, or an unrelated rebuild
erases them.** `applyAll()` always sends the whole `note_overrides` dict and
`rebuild_job` REPLACES the stored value, so resetting the viewer's list to `{}`
on job load meant: edit notes → rebuild (stored) → reopen the job → change the
tuning → "Aplicar e reconstruir" sends `{}` → **every committed note edit is
silently gone**. `ArrangementOut.note_overrides` now returns each arrangement's
committed edits and `loadArrangements` seeds `noteOverridesByKind` from them, so
the always-send round-trip is lossless. `noteOverridesBuilt` (a JSON snapshot at
load) is what makes "Pendente" mean *changed since the build* rather than "this
job has note edits". Clearing them is then an explicit action — "Notas ▾" →
"Limpar esta pista" / "Limpar em todas" — which sends the smaller dict and
genuinely removes them on the next rebuild. Guarded by
`test_committed_note_edits_survive_an_unrelated_rebuild`.

**Dragging a note, ↑/↓ for its fret, and an insertion grid of sixteenths**
(Liam, 2026-10-17: "found how to add a note but it keeps snapping to the
previous note making a chord … would be nice to drag a note about and change
the pitch kinda like in Sibelius" — a solo's "10 9 10" that should read
"10 12 10"). The double-click insert snapped to `snapGridTimes()`, whole beats
by default, so in a run of sixteenths the nearest point was the beat the
previous note already held and the new note became a chord with it. Inserts
and drags now use `noteEditGrid` — the snap grid but never coarser than
`NOTE_EDIT_MIN_DIV` (4 per beat), a 48-per-beat grid with snap off or Alt
held (`beatGridTimes`, split out of `snapGridTimes`; paste keeps the snap
grid). In "Editar notas" a press on a note no longer opens the popup at once:
released without moving (4 px) it does; dragged (`noteMove`,
`noteMoveTarget`), the note follows the pointer along the grid (or keeps its
own time when that is nearer — a vertical drag) and onto the string under it,
and on release `moveNote` makes the same two pending edits as a delete and
an insert (fret, sustain and techniques kept; another note already in that
slot refuses it). ↑/↓ (`stepNoteFret`, Ctrl = 12) step the fret of the last
note clicked, moved or saved (`neLast`), 0-24, and play it. All ordinary
pending note overrides: undo/redo, drafts, "Aplicar e reconstruir". Rows in
`showShortcuts` and both guides. Browser-only, no pytest coverage; verified
with Playwright on the invented "Deriva" project (PT/EN): a click at 27 % of
a beat lands on the sixteenth (the old grid: the beat), a drag of half a beat
and one string moved a fret-5 note 0.25 s to the next string with its
sustain, ↑×3 made it 8, a plain click still opens the popup, six Ctrl+Z
cleared every edit, no page errors. Not tried by Liam yet. **Shift+drag duplicates** ("a shift to duplicate and drag a note or chord
shortcut would be massive", Liam): in "Editar notas" a Shift press on a note
starts a copy drag of its whole chord (`chordNotesAt`, the notes within 30 ms),
a ghost of the group follows the pointer, and on release `copyNotes` inserts
the copies (same frets/sustain/techniques, every note moved by the grabbed
note's time and string shift, kept on the neck by `noteMoveTarget`; a clash
refuses all of it). Released without moving it is the old Shift+click range
select. **The tail's end is a handle** ("a draggable tail on the sustain notes
to change the length"): `.sus-handle` on every note, shown only under
`#tabsvg.mode-editnotes`, kept clear of the next note on the string (left out
where there is no room); dragging it (`susDrag`, `sustainDragTarget`) snaps the
end to `noteEditGrid` (Alt free), stops at the build's own gap before the next
note on the string (`apply_sustain_gap`: min(50 ms, 15 %)) and the last beat,
and back onto the note gives no sustain; `setNoteSustain` makes it a pending
override. **Pending note edits are now heard, not only drawn** ("when i
remove a note it still plays in the midi track until its rebuilt"): the tick,
the synthesized source, the fretboard and "Pré-visualizar" read
`soundingNotes(a)` (the list `showArr` draws, via `noteSoundChanged`), the
tick pointer is reset when it changes mid-playback, and a synthesized source of
the edited chart is rendered again 500 ms after its overrides change
(`synthNotesSig`). Verified with Playwright: 9 notes deleted, 0 of them ticked
(the old code ticked all 9), the synth buffer silent there; a tail dragged to
the 16th grid, clamped 50 ms before the next note, back to 0, undone.

**Moving a chord or a passage, and why "Arrastar" is not for that** (Liam,
2026-10-18: "when you're moving notes around it can mess up the bpm and other
notes … you cant drag a note past another note … you have to keep clicking back
… to select a chord"). The user moved notes with "Arrastar", the SYNC drag:
each drag is a time-warp anchor, so the notes around stretch, the bars' BPM
labels change and a note cannot pass the neighbouring anchor (a crossing is what
`_check_anchor_order` refuses) — while "Editar notas" could only move one note.
Now in "Editar notas" a drag on empty staff draws a selection box (`editBox` →
the ordinary `rubberBand`; a press released without moving is still the seek, on
pointerup), and dragging a SELECTED note moves the whole selection
(`selectedChordNotes` → `moveNotes`): the same time (grid-snapped on the grabbed
note) and string shift for every note, as delete + insert note overrides — the
timeline is untouched, notes may pass others; a clash with a note left behind or
a note pushed outside the beat grid refuses it all; the selection follows. In
"Arrastar"/"Excerto" the names, descriptions and hints say they correct the
TIMING, and `warnIfAnchorsCross` toasts when a drag crosses the neighbouring
correction, pointing at "Editar notas". Browser-only, no pytest coverage;
verified with Playwright on an invented GP5 built for real: a box selected two
notes, dragging one moved both 2.4 s later past two others and one string down
(no anchor, "Pendente: edições de notas"), a click on empty staff still seeked,
Ctrl+Z restored, and an "Arrastar" drag past the neighbouring correction toasted
the warning, no page errors. BUG-0297.

**Frontend**: `noteOverridesByKind` (state, per-kind, seeded on job load from the
committed edits) needs no dirty-flag/None-sentinel gymnastics the way
`section_overrides` does — like `tone_changes`, there's no prior non-user
default to lose (a note edit only ever originates from the user), so the
whole dict is simply sent every rebuild; an untouched job sends `{}`. A
single click on an existing note (in "Editar notas" mode) opens a small
floating popup (`#noteEditPopup`, styled like the bar-align popup) pre-filled
with its current fret/sustain/technique checkboxes/bend/slide-to; "Guardar"
upserts an override, "Remover nota" marks it deleted. **A single click on
EMPTY staff space still seeks (moves the playhead), same as every other
note-click mode — inserting a new note is a DOUBLE-click** (`svg`'s `dblclick`
handler). This is deliberate: an earlier version inserted on a single
empty-space click, which silently hijacked click-to-seek the moment the user
was in this mode ("não consigo clicar na partitura e o cursor mover-se") —
the one mode that broke the otherwise-universal "click empty space = move the
cursor" convention. The double-click insert defaults the string from the
click's Y position and the time from **`nearestGridChartTime`** — the nearest
sync-grid point (`snapGridTimes()`, the same bars/beats/subdivision grid
note-dragging already snaps to), found by forward-projecting each grid
candidate to display X and picking the closest, rather than inverting the
click position through the warp+tempo-scale chain (not cheaply invertible) —
so a new note always lands on a real chart time with no new coordinate
machinery.

**Preview merges visually without touching sync/playback.** `mergeNoteOverrides`
(pure, JS) is the client-side mirror of `_apply_note_overrides` — it's spliced
into `showArr`'s note-drawing loop only (chord grouping recomputed from the
merged set, so an edit that changes which notes are simultaneous updates the
chord bracket/shape correctly), while `dur` sizing and the sync drags still
read the untouched `a.notes` until an actual rebuild bakes the edit in. The
tick, the synthesized source, the fretboard and the 3D highway DO play the
merged notes (`soundingNotes`, see "Dragging a note" above). A note
carrying a pending edit gets a dashed cyan ring (`.note-single[data-string]`,
added per-note so a specific note within a chord can be targeted precisely)
so it reads as "not yet rebuilt".

**Copy/paste ("📋 Copiar seleção" / "📥 Colar no cursor", Ctrl+C/Ctrl+V).**
Duplicates a selected excerpt elsewhere in the score — the same arrangement,
or a *different* one (e.g. copy a riff from Lead into Rhythm), without
re-entering it note by note. The two buttons live in their **own labelled
"Copiar/colar notas:" row** below the sync-mode buttons (not crammed into the
end of the 9-emoji mode row, where they were easy to miss when greyed-out).
`copySelectedNotes()` reads whichever notes are
currently in `selectedTimes` (the same selection Shift+click/Ctrl+click/
"Excerto" already populate) from the CURRENT arrangement's live
(`mergeNoteOverrides`-merged, so already-pending edits are copyable too) note
list, and normalizes each to a `dTime` offset from the earliest copied note —
`noteClipboard` is plain in-memory JS state, not the OS clipboard, so it's
session-only (cleared on a fresh job load, to avoid pasting one song's notes
into another). `pasteNotesAtCursor()` re-anchors the clipboard at the
playhead: only the FIRST copied note snaps to the sync grid
(`nearestGridChartTime`), and every other note keeps its original relative
spacing from it, so a copied riff's own rhythm survives the paste intact.
Each pasted note becomes an ordinary `note_overrides` upsert — no new
backend concept, it's a client-side composition over the same primitive the
single-note editor uses.

**The chart is sized to the whole song, not the last note.** `showArr`'s width
(`dur`) is the max of the last note end, the last bar/beat time, AND the
recording length (`waveDuration`) — NOT just `max(note.time)`. A track that
rests through the outro (e.g. a lead that stops at bar 120 of 146) still owns
all its bars in the grid, and the recording keeps playing; sizing to the last
note alone clipped those trailing (empty) bars and the waveform tail off the
right edge, making the track look shorter than the others ("o lead só aparece
até ao compasso 122"). All tracks now span the full song width.

Playback in the tab viewer goes through the **Web Audio API**
(`AudioBufferSourceNode` over the buffer already decoded for the waveform),
driven by a custom transport (`audioPlay`/`audioPause`/`audioSeek`), NOT the
HTML `<audio>` element. The element seeks by estimating a byte offset from
time, which is accurate near the start but drifts further in for VBR /
seek-table-less sources — the "aligned from the start, off in the middle"
symptom. A buffer source seeks sample-accurately and its clock is
`audioCtx.currentTime`, so playback, the waveform and the notes share one exact
timeline. The `<audio>` element survives only as a decode-failure fallback
(`playBuffer === null`), where seeking is codec-imprecise again. Don't revert
playback to the `<audio>` element's `currentTime`/seek.

**What is drawn follows what is HEARD (`heardTime`, BUG-0351).** The sample
the engine renders at `audioCtx.currentTime` reaches the speakers after
`outputLatency + baseLatency` (tens of ms wired, a few hundred over
Bluetooth), so a cursor drawn on `audioTime()` ran that much ahead of the
sound and the notes looked early against a chart that was in time ("as notas
chegam milissegundos antes", on a Songsterr video's times the build places to
the millisecond) — and syncing by eye would have moved them late in game.
`heardTime()` = `audioTime()` minus that latency (× playback rate, never
before where the source started) while playing: the playhead, the scroll,
`currentPlayheadT` ("= cursor" tools), the lit fretboard notes, the live BPM,
the time label, "Início = cursor", the 3D highway's clock and the pause
position read it. The note ticks stay on `audioTime()` (`vtAudio` in
`syncFrame`): they are scheduled through the same output, so they already
sound with the music; the taps keep subtracting `tapLatency()` themselves.
Browser-only; verified with Playwright with a latency of 210 ms injected:
audio 11.01 s, cursor/fretboard/highway at 10.80 s, pause at 10.80 s, PT/EN,
no page errors.

### Lyrics formats (`infrastructure/rsxml/vocals.py`)

`parse_lyrics` auto-detects **LRC** (`[mm:ss.xx]` lines) vs **UltraStar/USDX
TXT** (`#BPM:`/`#GAP:` header + `: start length pitch text` / `-` line-break
note lines; beat→seconds via `15 / BPM`). Rocksmith's vocals XML is
per-syllable: `expand_to_words` splits line-level events (LRC) into one
`<vocal>` per word and appends `+` to the last word of each line — that
trailing `+` is what makes the in-game lyric display break to a new line.
UltraStar input is already per-syllable and is NOT re-expanded.

**GP-embedded lyrics surface in the editor.** GP-embedded lyrics used to be
written straight to the vocals XML at build time and never shown in the UI, so
they looked "missing". Now the GP build returns them on `PipelineResult.gp_lyrics`
(in the **recording clock** — `pipeline` subtracts `pad_start_s` so a rebuild
re-adds it cleanly), and the worker stores them in `params["lyrics_events"]`
when the user hasn't supplied their own — so they appear in the "Letras" editor
and on the tab viewer, editable. **That store silently never happened in a real
run until 2026-09-28**: the task wrote `lyrics_events` into `job.params`' own
dict (the session keeps it as the column's committed value — `expire_on_commit`
is off), so the `{**params}` it then assigned compared equal to "unchanged"
and no UPDATE was issued; the lyrics reached the bundle but never the editor.
`generate_cdlc` now takes a `dict(...)` copy. Guarded by
`test_a_gp_files_lyrics_reach_the_editor_after_the_build`. The melisma `_` marker (a syllable held over
several note attacks) extends the previous syllable's length instead of emitting
a new event.

**GP-embedded lyrics → per-syllable note alignment (`distribute_syllables`).**
A Guitar Pro file stores lyrics as a line of text per `startingMeasure`; the
per-syllable timing is *implicit* — GP/Songsterr distribute the syllables
across the note attacks (whitespace = word boundary, hyphen = syllable split
within a word: `loo-king a-way` → `loo`·`king`·`a`·`way`). **The attacks are
those of the track the lyrics are WRITTEN on** — usually a vocal track, whose
rhythm is not the guitar's: GP3-5 name it in `song.lyrics.trackChoice`
(1-based, 0 = none) and GPIF puts `<Lyrics>` on the track itself, and Guitar
Pro hands one syllable to each beat of that track's first voice that is not a
rest (alphaTab's `Track.applyLyrics`). Both parsers record those beats as
`ParsedGpTrack.lyric_notes` (`LyricNote`: start, end, MIDI pitch, whether the
line rests before it), on the charted track's own clock (ticks are
song-wide); `_warp_parsed_track` moves them with every sync round, and
`gp_pipeline` distributes the text over them, falling back to the chart's own
notes only when the file names no track (the warning says which was used).
Before 2026-09-28 it always used the guitar chart's notes, so a vocal line
with a different rhythm slid off. `_split_syllables` reads the text the way
Guitar Pro does: a run of N spaces skips N-1 notes (an unsung note in the
vocal line), every space around a line break skips one (Songsterr's rule
too), a newline also ends a display line (`+`), `[...]` is a comment and a
hyphen before a space (`Mo- ney`) still joins. Guarded by
`test_gp_lyrics_are_sung_on_the_vocal_line_not_the_charted_guitar`,
`test_gp7_lyrics_are_timed_on_the_notes_of_their_own_track`,
`test_extra_spaces_skip_notes_and_a_newline_ends_a_line` and
`test_comments_and_a_hyphen_before_a_space_are_read_like_guitar_pro` (all
mutation-checked), and a real in-process build of a Songsterr-shaped tab
whose words land on the vocal eighths.

**The vocal line also gives each syllable its length and the lyric its
phrases.** "O GP5 também tinha uma track de Voz, mas unicamente com a letra —
como podes aproveitá-la?": the syllables already rode its notes, but the rest
of what it says was thrown away. Now (a) a syllable lasts its note's written
length (`ends`), not until the next note across a rest; (b) when the text has
no line breaks of its own (ONE lyric line, no newline — the user's PDF→GP5
file is a single 1860-character line, so every break came from the 7-word
cap, mid-phrase: "with+ / who") `distribute_syllables` ends a line at a
**breath before a capitalised word**: the vocal line rests just before it
AND it starts with a capital, how lyrics mark a line. Neither alone: "High
Noon" is a capital with no breath, "tequila (breath) with" a breath before
lower case. Lyrics with no capitals to go by (all lower/upper case; "I" does
not count) break at every breath before a word; never inside a word; lines
the text already has always win. On that file: 65 lines, the ones a person
would write ("Don't know how long / she's been movin' on"). An earlier draft
also accepted a rest just AFTER the capital (a misread of the data) and split
"High / Noon" — `test_a_vocal_lines_breaths_before_a_capital_end_the_lyric_lines`
pins that. (c) The notes themselves go out as `PipelineResult.vocal_melody`
→ `params["vocal_melody"]` (replaced on every build — it follows sync
corrections, unlike stored editor rows) → `GET /jobs/{id}/vocal-line`
(`{notes: [{time, length, midi}], gp_has_lyrics}`) → "Voz (sintetizada)" in
the Fonte de áudio selector (below). And because a job's first build stores
the GP lyrics as editor rows, which then win over the file, the Letra page
has **"Voltar à letra da pauta"** (shown when `gp_has_lyrics`): it empties
the rows and makes "Aplicar e reconstruir" send `lyrics_events: []` (not
`null`, which means "untouched"), so the build reads the file again — how an
existing project gets the new phrasing. Guarded by
`test_a_vocal_lines_breaths_before_a_capital_end_the_lyric_lines`,
`test_lyrics_without_capitals_break_at_every_breath_but_never_mid_word`,
`test_lines_the_text_already_has_are_kept_and_breaths_are_not_used`,
`test_a_syllable_lasts_as_long_as_its_note_not_until_the_next_one` (all four
mutation-checked), the pitches/ends/rests in
`test_gp7_lyrics_are_timed_on_the_notes_of_their_own_track` and
`test_gp_lyrics_are_sung_on_the_vocal_line_not_the_charted_guitar`, the
worker storing it in `test_a_gp_files_lyrics_reach_the_editor_after_the_build`
and `test_the_vocal_line_is_served_for_the_viewers_voice_source`; the user's
own file built end to end, and a real rebuild with `lyrics_events: []`
replaced its old rows. Rocksmith markers: a trailing `-` joins syllables
within a word (no space, hyphen shown in game), a trailing `+` on a line's last
syllable is the line break. Honest limit: it assumes **syllabic** singing (one
syllable per note attack); **melismas** (one syllable held over several notes)
are not recoverable from the GP text, so a melismatic passage drifts by the
number of extra notes until the next line resets it — supply an LRC/UltraStar
file or use the in-app editor for those. The in-app editor (`lyrics_events`)
and an LRC/UltraStar file both still take precedence over GP-embedded lyrics.

### Automatic lyric detection + in-app editor

`POST /jobs/{id}/detect-lyrics` runs `rockforge.detect_lyrics` (an async Celery
task, GP and audio-ML jobs both) — Demucs isolates the vocals stem and WhisperX
force-aligns it. Progress is tracked via `params["lyrics_status"]`
(`detecting`/`ready`/`empty`/`unavailable`), never `JobStatus`, so detection
never hides a completed bundle or disables `/arrangements`. Results land in
`params["lyrics_events"]` (JSON rows `{"time","length","lyric"}`), readable via
`GET /jobs/{id}/lyrics`.

**Line breaks.** WhisperX segments are whole sentences, so putting the `+` line
break only at segment ends made long segments scroll in-game as one wall of
text. `segments_to_vocal_events` splits each segment into short display lines
(`_break_into_lines`): a `+` on a sung pause (word gap > `LINE_BREAK_GAP_S`) or
every `LINE_MAX_WORDS` words. This is detection-only — LRC/UltraStar/GP-embedded
lyrics keep their authored line structure.

**Build-time line cap (`enforce_max_line_words`, `rsxml/vocals.py`).** The finer
breaking above only touches WhisperX *detection*. Both pipelines additionally run
every vocals list through `enforce_max_line_words` (cap `MAX_LINE_WORDS = 7`)
right before packaging — a safety net so lyrics from ANY source (old detection
whose coarse `+`s are already baked into `lyrics_events`, GP-embedded, a
long-lined LRC) don't scroll as a wall of text in-game **without needing a
re-detect**. A line over the cap is split into the FEWEST lines that fit, of
about equal length (8 words → 4 + 4, not 7 + an orphaned "who"), preferring
within two words of the even split a break before a capitalised word, then
after punctuation (`_break_fit`). It counts WORDS: it used to count every
syllable event, so "chas-in' te-qui-la" used up five of the seven. It never
removes an authored break, never breaks on a syllable-join `-` (mid-word) or
on the last event. Guarded by `test_enforce_max_line_words_*` and
`test_a_long_line_is_split_evenly_counting_words_not_syllables`.

**Speed.** This is the slow path on CPU; the heaviest stage is the Demucs
separation. Detection uses `DemucsSeparator.separate_vocals` — the lighter
4-source `htdemucs` with `--two-stems=vocals` — NOT `separate_guitar`'s 6-source
`htdemucs_6s` (which would compute drums/bass/other/guitar/piano just to throw
them away). htdemucs' vocal quality is also better than the 6s model's, so it is
faster *and* more accurate for transcription. The WhisperX model size
(`ROCKFORGE_WHISPER_MODEL`, default `small`) and the detection device
(`ROCKFORGE_WHISPERX_DEVICE`, falling back to `demucs_device` via
`settings.lyrics_device()`) are configurable — on CPU drop the model to
`base`/`tiny` to trade accuracy for speed.

**Subprocess isolation.** WhisperX transcription (and the `import whisperx`
availability check) runs in a **subprocess**, not inside the Celery worker.
faster-whisper / ctranslate2 has a known deadlock during CUDA initialisation
inside Celery child processes (faster-whisper #907, celery #3402) that hangs
the worker indefinitely at the import phase. The fix mirrors how Demucs already
runs — `_whisperx_runner.py` is spawned via `subprocess.run` with
`WHISPERX_TIMEOUT_S` (20 min, covers first-run model download + long songs).
The CUDA warm-up probe was removed entirely (two concurrent `cuInit()` calls —
warm-up thread vs first task — can deadlock on Windows); the first task pays the
one-time 30-60s CUDA init cost, and `@cache` avoids repeating it.

**Windows cuDNN DLL discovery (`_add_cuda_dll_dirs`).** ctranslate2 4.x crashes
natively (exit `0xC0000409`) when it can't load `cudnn_ops64_9.dll` /
`cublas64_12.dll` — and it can't even when a matching cuDNN 9 is installed, if
that copy only lives in `torch/lib` (the torch cu12x wheels bundle it there, but
that dir isn't on the Windows DLL search path). Before importing whisperx, the
runner adds torch's `lib` dir (and any standalone `nvidia-cudnn`/`nvidia-cublas`
pip packages) via `os.add_dll_directory`, so ctranslate2 resolves cuDNN/cuBLAS
instead of crashing. This is the fix for "GPU crashes even with torch cu121 (which
bundles cuDNN 9.1) + ctranslate2 4.4.0 (which needs cuDNN 9)". No-op off Windows;
guarded by `test_add_cuda_dll_dirs_is_noop_off_windows`.

**GPU crash → CPU fallback (WHOLE ML stack, not just WhisperX).** Both Demucs
(torch) and WhisperX (faster-whisper/ctranslate2) can crash natively on GPU
(e.g. exit `3221226505`/`0xC0000409` from a torch/cuDNN mismatch on Turing /
RTX 20-series cards) with no Python traceback. Two layers handle it:
- **In-run fallback.** Each GPU subprocess retries on CPU when a CUDA run
  crashes: `detect_lyrics`'s `_run_whisperx(dev)` (non-zero `cuda` exit →
  retry `cpu`, final failure raises with the stderr tail — don't restore
  `check=True`, it hides the stderr and kills the fallback), and
  `DemucsSeparator._run` (a `CalledProcessError` on a `cuda` device retries the
  same command on `cpu`; a *timeout* does NOT retry — no burning another 30 min).
  So the crashing run still completes.
- **Persisted marker degrades the whole stack.** The first crash drops a
  `work_dir/.gpu_ml_broken` marker (`_mark_cuda_broken`, wired into Demucs via
  `on_cuda_crash` in `_make_demucs` AND into the WhisperX fallback).
  `_resolve_device` consults it (`_cuda_known_broken`) and downgrades a resolved
  `cuda` to `cpu` — for **Demucs AND WhisperX**, in every task and the main
  build — so after ONE crash the flaky GPU is skipped everywhere instead of
  re-crashing each song. The legacy `.whisperx_cuda_broken` filename is still
  honoured so existing installs stay degraded. **The marker is a hidden dotfile
  in `work_dir` most users can't find, so the ⚙️ Definições modal surfaces its
  state ("GPU acelerada") + a "Reativar GPU" button** → `POST /gpu-reset`
  (`_clear_cuda_broken`, also clears the `_detect_device` cache so it takes
  effect without a restart). `SettingsOut.gpu_broken` carries the state.

**Making the GPU actually work — the escalation ladder + auto-persist.** The
float16 ctranslate2 path is the usual trigger of the Turing/cuDNN crash, so
`detect_lyrics` doesn't jump straight to CPU: `_whisperx_attempts(device,
configured)` builds a ladder — **cuda(configured/float16) → cuda(int8_float16)
→ cpu** — and the task runs each rung until one succeeds. `int8_float16` (lower
VRAM, more cuDNN-tolerant) often keeps the GPU working where float16 crashes.
Outcomes: if a non-default GPU compute type wins, it's **persisted to
`runtime_settings` (`whisperx_compute_type`)** so later runs skip the doomed
float16 attempt; if even int8_float16 crashes and it falls to CPU, the
GPU-broken marker is set (whole stack → CPU). The compute type is also settable
manually via `ROCKFORGE_WHISPERX_COMPUTE_TYPE` (env) — the runtime override
wins. Note it only affects the transcribe model — a torch-side cuDNN crash in
the wav2vec2 *alignment* step is unaffected, in which case the int8_float16 rung
also crashes and the CPU fallback is the answer. `_whisperx_attempts` guarded by
`test_whisperx_attempts_escalation_ladder`.

**Device selection (`_resolve_device`).** `demucs_device` defaults to `"auto"`:
`_detect_device` (deferred torch import, worker-only, `@cache`d) returns
`"cuda"` when `torch.cuda.is_available()` and `"cpu"` otherwise; explicit
`"cpu"`/`"cuda"` pass through — then `_resolve_device` downgrades any resolved
`"cuda"` to `"cpu"` when the GPU-broken marker is set. Any import/CUDA failure degrades to CPU, so
`"auto"` is safe even without the ml/lyrics extras. **The question goes to the
interpreter that RUNS the stages** (`ml_python.cuda_available`, a subprocess
when it is another Python): in the `.exe` torch is only in the extra
components' Python, and importing it in the frozen process always failed, so
every stage ran on the CPU whatever the GPU (found answering a user's "will it
run on an enterprise GPU?", 2026-10-16). Any GPU torch drives counts
(GeForce, workstation, data-centre, TCC mode). Guarded by
`test_the_exe_asks_the_components_python_whether_there_is_a_gpu`
(mutation-checked). Resolution happens *before*
the adapters are built (the WhisperX adapter keys `compute_type` off the
concrete device — `float16` on cuda, `int8` on cpu — so it must never see the
literal `"auto"`). The resolved device is written to the lyrics log
(`device: cuda (GPU)`), so the user can confirm the GPU is in use. With an
NVIDIA GPU this is the ~3-minute path online tools get — but note the default
`pip install torch` on Windows is CPU-only; the CUDA build is needed (e.g.
`pip install torch==2.4.1 torchaudio==2.4.1 --index-url
https://download.pytorch.org/whl/cu121`, respecting the `<2.5` pin).

The web UI's "Letras" panel lets the user edit words and per-word timings (and
add/remove rows) regardless of whether detection ran. `applyAll()` sends the
edited rows as `RebuildIn.lyrics_events`; `rebuild_job` stores them in
`params["lyrics_events"]` and clears `lyrics_status` so the next build picks
them up via `events_from_dicts`. These edited events take **top precedence**
over `lrc_text`/GP-embedded lyrics (GP pipeline) and over automatic WhisperX
transcription (audio pipeline) — see `GpJobSpec.lyrics_events` and
`GenerateCdlcUseCase.run(lyrics_events=...)`.

Coordinate space: events from `/lyrics` and the editor are in the **un-padded
recording clock**. For GP jobs, `gp_pipeline` shifts edited times by
`pad_start_s` at build time, same as `lrc_text`. For the audio-ML path, note
that (like the existing automatic-WhisperX path) `offset_s` trimming is not
subtracted from word times — a known limitation.

Detection needs both `[lyrics]` (WhisperX) and `[ml]` (Demucs) extras in the
worker, even for GP jobs whose own build stays ML-free.

### Adjusting the lyric beside the score (the inspector's "Letra" tab)

"é difícil de ajustar a letra, porque deveria existir uma opção perto da
partitura": the timing tools lived only on the separate Letra page, so fixing
a word meant listening on Partitura, switching pages, finding the row by its
number and typing seconds. The Partitura inspector now has a third tab,
**Letra** (`#inspLyrics`, beside Sincronização/Secções), and **clicking a word
on the score** (or dropping it after a drag) selects it and opens that tab. A
click on a word does NOT seek — the cursor has to stay where the word should
sound. Tools: "Letra toda" = "1ª palavra = cursor" and −/+ by a step (the same
`shiftLyrics`); for the selected word ◀/▶ (by time), its text, time and line
end, **"Daqui em diante = cursor"** (`shiftLyricsFrom`: the word goes to the
cursor, every word at or after it follows, earlier words stay put — the
lyric-side twin of "Corrigir daqui"; it cannot pass the previous word and
stops 10 ms after it, saying so), "Só esta = cursor", −/+ (this word and the
following), remove; "Palavra no cursor" picks the word being sung, "+ palavra
no cursor" inserts one and focuses its text. Same rows and clock as the Letra
page (`lyricsEvents`, playhead − `leadInBuilt`), so both views edit one list
(`renderLyricsRows` refreshes the inspector) and every change is an ordinary
pending edit for "Aplicar e reconstruir". The selection is the row OBJECT
(`lyricSelected`), not an index — sorting/removing rows renumbers them and a
reload replaces them. "Pendente: letra" now appears too (`lyricsBuilt`, the
serialized rows as last loaded — before, a lyric edit showed no pending sign
at all). The selected word is drawn teal (`.lyric-word.sel`). Browser-only, no
pytest coverage; verified with Playwright (click → tab + selection without
seeking, from-here/limited/only-this/nudge/remove/pick/add/whole-shift, drag
selects, the Letra page table follows, no page errors).

**Lyrics timed on the score follow the chart's sync corrections.** "Quando
corrijo o início das notas, a letra não se está a mover": after the first
build the GP lyrics live as editor rows in the recording clock, and nothing
moved them when the notes were re-timed — not in the preview, not at the
rebuild. Now the rows are always kept where they are SHOWN (every lyric tool
already works in that clock), and `lyricsFollowSync` (run at the top of
`showArr` and of `applyAll`) carries them whenever the reference chart's
pending sync changes: back through the previous map, forward through the new
one (`lyricSyncMap` — the notes' own `previewScale` + anchor warp applied to
the lyric's bundle time, `lyric + lyricPadBuilt`; `invertIncreasing` bisects
the piecewise-linear map), so undoing a correction brings them back exactly
and a rebuild stores rows that already carry it. The reference chart is the
first in the BUILD's slot order (Lead, Rhythm, Combined, Alternate…,
`lyricRefArr`), the same chart `gp_pipeline` times the GP lyrics on, never the
`/arrangements` file order. **Only lyrics timed on the score follow**: an LRC
or a WhisperX detection is timed to the RECORDING, which a chart correction
does not move. `params["lyrics_follow_chart"]` says which — the build sets it
True when it stores the GP lyrics, detection sets it False, "Usar" (LRCLIB)
clears it and "Voltar à letra da pauta" sets it in the viewer, and it rides
`RebuildIn.lyrics_follow_chart`; a job from before the flag follows when
`gp_has_lyrics` and no LRC/detection (`_lyrics_follow_chart`). The Letra tab
shows it as "Acompanha as correções de sincronização da partitura (pista X)".
"Voz (sintetizada)" goes through the same map, so the vocal line follows the
pending sync too. Two lead-in slips surfaced on the way and were fixed:
`arrangementPreviewScale` (bar sync against another track) and
`synthesizeArrangement` left out `leadInBuilt`, which `previewScale` adds, so
with a "Silêncio inicial" the other track's bar and the synthesized notes sat
that much early. Guarded by
`test_lyrics_say_whether_they_follow_the_charts_sync_corrections`
(mutation-checked) and the flag in
`test_a_gp_files_lyrics_reach_the_editor_after_the_build`; the viewer with
Playwright on the user's file: "Início" +0.75 s moves every word +0.75 s, a
tempo change on top lands word 200 exactly where the notes' map puts it
(length scaled too), undoing restores the rows to the last digit, unticked
nothing moves, and a real rebuild leaves the first guitar note, the first
vocal note and the first word all +0.75 s, each word still on its note.

### Lyrics found online (LRCLIB) and synchronised to the recording

The "Letra" page's **"Procurar letra online"** asks **LRCLIB** (`lrclib.net`,
open, no key) via `infrastructure/lyrics_lookup.py` (`GET /lyrics-lookup`):
same shape as the album lookup — searched by the MAIN artist and the title
without a featuring credit (it reuses `primary_artist`/`search_title`/`_same`),
a ranked LIST the user chooses from (entries WITH timestamps first, then the
length closest to the recording — the likeliest same edit), an instrumental
kept as an answer, a free-text `q=` retry when the field search finds nothing,
502 when LRCLIB is unreachable. Each card shows the length against the user's
recording ("3:20 (a tua gravação: 3:17, −3 s)") so a live take or an extended
mix is visible before it is used.

**Two ways to line it up, deliberately separate:**
- **"Usar"** (synced entries) runs the LRC through `POST /lyrics/parse` — the
  SAME `parse_lyrics` the build uses for an uploaded LRC, so the editor shows
  exactly what the build would make of it — and fills the editor. Its times are
  those of the release the LRC was made from, so the page offers **"1ª palavra
  = cursor"** and **−/+** shifts (the playhead minus `leadInBuilt`, the same
  clock "+ palavra" uses). Pending until "Aplicar e reconstruir", like any edit.
- **"Sincronizar com a gravação"** sends the editor's lines (regrouped from
  its words by their `+` line ends, `editorLines`) — or a plain-only entry's
  lines, untimed — as `/detect-lyrics`'s `align_lines`. The SAME async task
  then **aligns known words instead of transcribing**: `params["lyrics_align"]`
  → `--align-json` on `_whisperx_runner.py` (`_whisperx_command`) →
  `WhisperXLyricTranscriber.align`: `alignment_segments` windows each timed line
  from `ALIGN_MARGIN_S` before it to that margin past the next one (so a line a
  little off still finds its words), or ONE whole-recording segment for
  untimed text (less reliable — the confirm dialog says so), then
  `whisperx.align` (wav2vec2, no transcription model) and
  `aligned_lines_to_events`, which **keeps every word** (the text is right by
  construction — no confidence filter; an unplaceable word goes right after
  the previous one) and ends each line where the lyrics end it. The language
  for the alignment model is `guess_language` (distinct stopwords, so a "la la
  la" refrain cannot outvote a verse; 'en' when unsure) unless the client sends
  one. The request is **consumed by that one run** (popped in the task's
  `finally`), so a later plain "Detetar letra" transcribes. Status `aligning`.
  If the run does not end `ready`, the UI **restores the editor's rows**
  (`lyricsBeforeAlign`): those lyrics may exist only in the editor, loaded from
  LRCLIB and not yet rebuilt, and a failed alignment must not cost them.

**Also at creation time — the wizard's step 4 ("Letra sincronizada").**
The user asked to fetch synced lyrics "when I'm still at the start of
preparing the song", so the first build already carries them. Step 4 runs
the same `/lyrics-lookup` once on arrival (next to the album search, same
title/band fields; the recording's length comes from the chosen audio file,
read by the browser, when there is one) and **preselects the best synced
result** — unless the GP file brings its own lyrics (`/gp/inspect`'s
`has_lyrics`: an LRC would replace them, so nothing is chosen for the user)
or an LRC file was picked. Click another card to change it, or "Escolhida ✓"
to use none. The chosen LRC goes to `/jobs/gp` as the `lyrics_lrc` form
field and is stored exactly like an uploaded LRC (`params["lrc_text"]`) —
an uploaded file still wins, and a text `parse_lyrics` cannot read is a 422
up front rather than a build that silently has no lyrics. Plain-only results
are listed but cannot be chosen there: without timing they need the
recording, i.e. the Letra page's "Sincronizar com a gravação" after
creation. `lyricsCardBody` renders a result for both places (DOM calls —
third-party strings). Guarded by
`test_synced_lyrics_chosen_in_the_wizard_travel_with_the_new_job`; the
wizard flow (auto-search, preselect, unpick/repick, the created job holding
the words) verified with Playwright against faked LRCLIB answers.

Honest limits: LRCLIB has never been contacted from here (the sandbox blocks
it; recorded-shape fakes in `test_lyrics_lookup.py`); fan remixes and AI-made
songs are rarely there; alignment needs `[ml,lyrics]` like detection and has
never run in CI (`alignment_segments`/`aligned_lines_to_events` are pure and
tested, `whisperx.align` itself is not). TESTING.md §7c-bis. Guarded by
`test_lyrics_lookup.py`, `test_known_lines_are_aligned_*`,
`test_plain_lyrics_are_aligned_over_the_whole_recording`,
`test_aligned_known_lyrics_keep_every_word_and_their_lines`,
`test_the_whisperx_runner_aligns_known_lyrics_only_when_asked`,
`test_an_alignment_request_is_used_once_even_when_it_fails`,
`test_detect_lyrics_can_align_known_lyrics_instead_of_transcribing`,
`test_lyrics_lookup_returns_the_lrclib_candidates` and
`test_lrc_text_becomes_the_editors_words_with_the_offset`.

### The UI says when the server is gone (`getJSON` + the offline banner)

The app deliberately shuts itself down when the tab closes
(`ROCKFORGE_IDLE_SHUTDOWN_S`) and a machine can sleep, so the API really can
vanish while the page stays open. Several calls went `(await fetch(...)).json()`
with no check at all, so that threw an unhandled rejection and the action simply
did nothing — indistinguishable from a broken feature. `getJSON(url, opts)`
raises on a non-2xx (so a failure can never be mistaken for an empty result) and
flips a persistent `#serverOffline` banner on a network error, clearing it when
a request succeeds again. `selectJob`'s poll keeps retrying across a blip
instead of dying on the first failure, and a global `unhandledrejection`
listener toasts anything that still escapes. Browser-only, so there is no pytest
coverage: verified with Playwright against a live server — banner absent on load,
present once `/jobs` is routed to fail, gone again when it succeeds, no page
errors throughout.

### Web UI structure: `index.html` (markup) + `app.js` (script) + ESLint

The web UI's client-side script lives in **`web/app.js`**, not inline in
`web/index.html` — it used to be one ~4100-line inline `<script>` block, which
meant no linter could ever check it (ESLint parses files, not markup) and
every past JS change was verified only by `node --check` (syntax only) or by
hand. `index.html` now loads it via `<script src="/app.js"></script>`; the
FastAPI route `app_js()` (`interfaces/api/routers/web.py`, alongside `index()`, both
now sharing `_web_file_candidates(name)`) serves it with a real
`text/javascript` content type, resolved the same repo-checkout-vs-installed
two-path lookup `_gear_image_dirs()` already used for gear images.

**`npm run lint`** (`eslint.config.js` at the repo root, scoped to
`web/app.js` only) is real-bug-focused — `no-undef`/`no-redeclare`/
`no-dupe-keys`/etc as errors, `no-unused-vars` as a warning rather than an
error (the file predates any lint config). It now reports **zero** problems:
the unused `catch (e)` bindings became bare `catch {}`, the genuinely dead
`clickSound()` was deleted, and `openMetaEdit` — a FALSE positive, reached from
an `onclick="…"` inside a template-literal string ESLint cannot trace — is
assigned to `window` explicitly, which is both what inline handlers actually
resolve against and honest about why it looked unused. It is **not** a stylistic
reformat/rewrite of the file — only real-bug rule categories are enabled, so
the existing code style is undisturbed. CI runs it as the `web-lint` job
(`.github/workflows/ci.yml`, Node 22 + `npm ci`), separate from the Python
`test` job. Run locally with `npm ci && npm run lint` (or a bare `eslint
web/app.js` if `eslint` is already on `PATH`); `node --check web/app.js`
remains a useful quick syntax-only sanity check but ESLint is the real gate
now. Verified the extraction preserves behavior: the full existing
`test_psarc_sng.py`-style discipline doesn't apply here (no pure-function
logic changed, it's a pure file-split), but the served page was driven with
Playwright (a real headless Chromium) confirming zero console/page errors and
that DOM wiring (e.g. `openNewJobModal`'s modal toggle) still works after the
split, plus two new API tests (`test_index_page_references_the_extracted_app_js`,
`test_app_js_is_served_with_a_javascript_content_type`).

### Languages: Portuguese original, English, and room for more (`web/i18n.js`, `rockforge/i18n.py`)

"cria a tradução de tudo o que está no rockforge para inglês. Fica opção de
Português e Inglês" — then "cria uma skill de traduz sempre para inglês, tudo
o que for novo. Quero uma aplicação poliglota". **Every new visible text ships in
every language, in the same change: follow `.claude/skills/rockforge-i18n/SKILL.md`.**

The UI is WRITTEN in Portuguese and stays so: **the Portuguese text is the key**,
and every other language is one dictionary file, `web/i18n-<code>.js`:
`(self.I18N_DICTS = self.I18N_DICTS || {}).en = {pt: translation}` (strict JSON
between the braces). A string a dictionary lacks still shows, in Portuguese, and
nothing needs an invented key name. `GET /i18n-dicts.js` concatenates every
`web/i18n-*.js` (`_i18n_dictionaries`, cache-busted by their newest mtime), so
**adding a language is adding that file** — the pickers list whatever is
registered (`I18N_LANGS`), named by `I18N_NAMES`.

- **Script text** goes through `T('texto', {vars})` (global, `web/i18n.js`, loaded
  after the dictionaries and before `app.js`); variable parts are
  `{placeholders}`, never `${}` inside the key. `T`, not `t`: `t` is the time
  variable all over `app.js`. Plurals are two keys.
- **index.html** is not annotated: `translateDom(document.body)` runs once at load
  and translates every text node and the `title`/`aria-label`/`placeholder`/
  `alt`/`data-name` attributes whose text, whitespace collapsed, is a key (the
  whitespace around it is kept — it separates inline elements). A sentence cut
  by `<b>`/`<code>` is translated fragment by fragment, so the fragments were
  written to read well in the same order. `translate="no"` skips an element
  (the pickers).
- **Switching reloads the page** (`setLang`): tables built at load (`SYS_MARK`,
  the ⓘ texts, the mode menu) are simply built again. Pending edits in an open
  project would be lost, so it asks first (`#pendingChangesInfo` non-empty).
  Pickers: codes on the home top bar (`#langSelectTop`, `data-lang-select="short"`)
  and names under "Idioma · Language" at the top of ⚙️ Definições. Default:
  `localStorage` `rf-lang`, else the first of the browser's languages there is a
  dictionary for, else English, else Portuguese.
- **The server answers in the same language.** `i18n.js` wraps `fetch` so every
  same-origin request carries `X-RockForge-Lang`; the `_ui_language` dependency
  (async, so the endpoint — even a sync one run in a copied context — sees it)
  sets `rockforge.i18n`'s context variable. Server text is written once, in its
  languages, where it is produced: `tr("não encontrado", "not found", es=…)` —
  English is mandatory and is what any language a message was not written in
  reads; no table to keep in step. Outside a request (the worker's logs, the
  desktop window's close dialog) `i18n.current()` reads
  `runtime_settings.ui_language()`, which `PUT /ui-language` stores whenever the
  user switches. Messages the server always wrote in English stay English.
- **The gate is `tests/test_i18n.py`**, per dictionary: every index.html
  text/attribute with a letter and every `T()` literal has an entry; `T()` gets a
  fixed literal; placeholders match; and a small JS lexer finds any Portuguese
  string literal (an accent, or a common unaccented PT word) left OUTSIDE `T()`
  in `app.js`/`highway3d.js` — a string that is not shown (compared with
  Portuguese data, a slug fallback) is marked `// i18n-skip` on its line. A
  missing translation breaks nothing, which is exactly why it has to fail here:
  nobody would notice.

### Every note of the tuning on the fretboard ("Todas as notas", `fbAllNotesSvg`)

"Quero uma opção para ligar um modo no fretboard, que mostra todas as notas na
fretboard, para aquela afinação. Assim é mais fácil de identificar notas
equivalentes" (2026-10-20, from a sketch the user approved). A "Todas as notas"
switch beside "Braço" (`#fbAllNotes`, `rf-fb-all`) names every (string, fret)
of the chart on screen, from its own tuning (`fbCells`: `noteMidi`, so a bass,
the low-bass +12 fix and a capo — the open string at the capo, the frets under
it left out — come out right), in the string's colour. The neck widens while
it is on (`FB.fw` 26 → 36, `FB.sh` 20 → 24; `fretXY` reads them, so the
sounding-note overlay follows) and the open-string pills replace the tuning
labels. A click on a pill (`.fb-cell`, delegated on `#fretboard`; never seeks)
picks it (`fbPick`, again = let go): the same MIDI pitch elsewhere gets a
dashed white outline, the same pitch class in another octave a white one, the
rest dims; `#fbInfo` under the neck says the note, its frequency, where else
it sounds (`fbWhere`: "6.ª corda, traste 7") and how many octaves, with a
legend. `#fbNameMode` (name / name + octave, `rf-fb-names`) and `#fbScope`
(all / only those matching the pick / only naturals, `rf-fb-scope`) show only
while it is on. The overlay of sounding notes is drawn on top, as before.
**"Only those matching" draws nothing until a note is picked** (BUG-0341: with
no pick it drew every note), and a note a scope leaves out is still a
transparent `.fb-cell`, so its place on the neck picks it. **The sounding-note overlay**
(`updateFretboard`) lights a note for its sustain, or a brief 0.16 s glow that
stops at the next attack, and its 30 ms lead-in never reaches back past the
previous attack — the glow used to run on, so clicking a note 125 ms after
another lit both (BUG-0350; verified with Playwright on an invented riff of
sixteenths: two notes lit per click before, one after, PT/EN). **A note clicked on
the score with no mode selected** goes to the fretboard (`focusNoteOnFretboard`:
the cursor to its drawn attack + 1 ms, and `fbPick` = that string and fret); in
a mode the cursor is a target ("= cursor", "Mover seguintes"…), so it stays.
Verified with Playwright (PT 1440 / EN 760 px): nothing drawn and the tuning
labels kept before a pick, a click on a note moved the cursor 0 → 2.668 s (the
note at 2.667 s) and drew its 12 equivalents, a click on an empty place of the
neck picked it, no page errors.
Browser-only; verified with Playwright on an invented Combined + Bass project
(PT 1440 / EN 760 px): 150 pills on the guitar and 100 on the bass, B2 picked
→ "6.ª corda, traste 7 · 5.ª corda, traste 2" and 11 octave places, the cursor
unmoved, both selects, the settings remembered after a reload, no page errors.

### The 3D note highway ("Pista 3D", `web/highway3d.js`)

"grafismo 3D, com three.js, para o braço da guitarra … o mais idêntico
possível com o rocksmith", built from a sketch the user approved (a published
artifact, iterated once: "o número da nota não deve desaparecer quando toca na
corda"). A "Pista 3D" checkbox beside "Braço" opens a panel above the score
(`#hw3dWrap`, remembered in `localStorage` `rf-hw3d`, reopened on the next
project by `loadArrangements`, closed by `closeDetail`) with the notes coming
down a Rocksmith-style highway: string colours with low E red and on top, a
six-in-line headstock whose **nut carries the tuning** (one name per string, in
its colour, from `tuning_offsets`), rounded-rectangle gems with the fret on the
face and a drop line to the highway, a glow on the string + flash + sparks when
a note arrives, and **the note stays on the string, number and all** — a short
one `HOLD_MIN` (0.32 s), a sustained one for as long as it sounds, then it
fades. Chords get a frame and the name `/arrangements` already derives; an open
string is a bar across the hand window; the anchor band and the camera follow
the frets about to be played (`anchorAt`); sustains are trails and a slide's
trail runs to the fret it ends on (`ArrangementNoteOut.slide_to`, new, read from
`slideTo`/`slideUnpitchTo`); techniques are short marks above the gem; bar and
beat lines cross the highway, sections are labelled. Controls: "Traste na
nota", "Câmara", "Ecrã inteiro".

**The camera turns on three axes** ("A pista 3D deve ter mais mobilidade … até
um máximo de 1220 graus horizontalmente e verticalmente de 0 a 90 graus",
2026-10-16; read as 120° to either side — `YAW_MAX`, one constant). It orbits
a point between the strings and the notes about to arrive (`PIVOT_Y`/`PIVOT_Z`,
x following the hand window as before): yaw ±120°, pitch 0° (level with the
highway) to 90° (from above, held at 89.9° so `lookAt` keeps an "up"), distance
6–40. Drag on the canvas turns it, the wheel sets the distance, a double click
resets (`wireCamera`); **the wheel works only once the canvas has been
clicked** ("when im scrolling up and down the page the highway seems to be in
focus when i mouse over it … maybe it should be click to gain focus?", Liam):
the canvas is focusable (`tabIndex` 0, focused on `pointerdown`), the wheel
handler returns without `preventDefault` unless it holds the focus, so the
page scrolls over it, and Esc or a click elsewhere lets go (a blue border
shows when it holds it). Verified with Playwright: wheel before a click
scrolls the page and leaves the distance, after a click zooms, after Esc or a
click outside scrolls again; "Câmara ▾" holds the same three axes as sliders and
"Repor câmara". `clampCamera` bounds every way in, the canvas tells app.js
through `open(..., cameraChanged)` so the sliders follow a drag, and the view
is remembered in `localStorage` `rf-hw3d-cam`. The default (yaw 0, pitch 15,
distance 15) reproduces the old fixed view at its default tilt — checked side
by side. The note faces still face the front, so from far to the side the
numbers are seen edge-on.

**The hand window lights up on every hit** ("quando uma nota (ou acorde) bate
nas cordas … um retângulo à volta da área onde estão as notas (1-4, 2-5) … com
brilho", 2026-10-18): `flashWindow` (from `hit`) places a frame at the strings —
the frets of `anchorAt(note time)` (the chart's FHP, else the frets played),
every string the chart has (`stage.stringCount`) — four thin additive cores over
`lineGlowTex` halos and a faint fill; `glow` jumps to 1, decays like the strings'
(1.8/s), is held at 0.45-0.6 while a struck note still rings, and goes with
`clearEffects` on a jump. `stats().window` reports it. Verified with Playwright
under software WebGL: glow 0 → 0.91 at the first hit, held while the notes rang,
the frame on frets 2–5 where the FHP lane says 2–5.

**Bends move, in teal** ("implementes na fretboard em 3D, o movimento teal dos
bends", 2026-10-20): `/arrangements` answers each note's `<bendValues>` as
`bend_curve` ([seconds after the attack, semitones], `ArrangementNoteOut`), and
`hw3dBendCurve` hands it over in the display clock (a note whose bend was edited
and not rebuilt sends none: the highway then draws a plain bend, rising to its
peak at the note's end — `bendPoints`). The trail of a bent note is teal
(`bendTrailMat`) and rises along the curve (`trailGeometry`'s `span`, `bendAt`);
on the string the held note rises by `BEND_Y` (half a string gap) per semitone,
capped at `BEND_MAX` (3), read from the song's clock (`now - t`, so a pause holds
it), with a teal line from the string and a dashed teal frame at the peak
(`heldNote().bend`); the bend chevrons are teal too. `stats().bends` reports
each held bend's rise. Guarded by
`test_arrangements_carry_the_bend_curve_for_the_3d_highway`; with Playwright
under software WebGL on an invented GP5 (a bend up, a bend-and-release, a
pre-bend released): the rise went 0 → 2 → 0 and 2 → 0 semitones as the notes
played, held while paused, PT 1440 / EN 760 px, no page errors. Never seen on a
real GPU from here.

**It knows nothing about sync — it reads the score's own clock.** `hw3dRefresh`
(called from `showArr`, so on every pending edit) hands it each note at
`warp(previewScale(t))` — the score's merged notes, pending note edits
included — and `getNow()` answers `playheadDisplay(heardTime())`; so pending
tempo/anchor corrections move the highway live, exactly as the score
(verified: a +10 % tempo moved note 100 from 41.096 s to 45.006 s, where the
score draws it). The whole song is JSON-compared before a `setSong`, since
`showArr` runs far more often than the notes change. A jump (seek, a new
preview) clears the effects and fires no backlog of hits.

**three.js 0.186.1 is vendored** in `web/vendor/three/` (the module + the core it
imports, byte-identical to `npm pack three@0.186.1`, MIT), imported by
`highway3d.js` only when the panel is first opened — the rest of the UI never
pays for it, and it works offline and in the `.exe` (the spec walks `web/`).
`GET /vendor/three/{name}` answers those two names only; `/highway3d.js` is
served and cache-busted like `/app.js` (`WEB_SCRIPTS`, `_serve_web_js`). ESLint
covers `highway3d.js` too. **Only the notes in view become meshes** (a window
from `now − song.back` to `now + AHEAD`, created on entry and dropped on exit,
geometries and materials shared), so a 1374-note song holds ~40 note meshes at
a time. A line lying on the floor is seen almost edge-on — a 0.07-unit bar line
was under a pixel and simply invisible — hence the 0.3/0.13 widths. Guarded by
`test_the_3d_highway_and_its_three_js_are_served` and
`test_arrangements_say_where_a_slide_ends`; the rest is browser-only, verified
with Playwright on the user's Ocean Eyes build (toggle, playback glow, held
note, chords, headstock, numbers/camera, live tempo follow, close/reopen, no page
errors) — under software WebGL, so real-GPU frame rate is not measured here.

### The score's legend ("Legenda", `scoreLegendHtml`)

"coloca legenda nestas opções todas e na deteção das batidas (bola laranja,
tracks, etc)". A "Legenda" switch beside "Braço"/"Pista 3D" (`#showLegend`,
remembered in `localStorage` `rf-legend`) opens `#scoreLegend` under the score:
every mark the score draws, each beside a 60×36 SVG swatch drawn with the
score's own colours and helpers (`legendNote`, `sustainWave`, `bendArrow`), in
groups — notes (string colours, chord square, technique ring, tail, vibrato,
link arc, bend, pending ring, outside-FHP ring, the tail handle, arpeggio),
staff (bar number + ♩, amber re-tempo, authored tempo change, section, tone
change, lyric word/¶, snap grid, playhead, A–B band), sync anchors, the
recording's attacks (`attacksLegendItems`: blue tick, faint tick, strong
orange tick, the orange circle), the FHP lane and the green ✓ tab. The score's
ⓘ (`INFO['tab-viewer']`, a getter so it is built when opened, after
`STRING_COLORS` exists) shows the same, and the attacks card shows its four
items (`#attacksLegend`) while they are on the score. **When the score gains a
new kind of mark, add it to `scoreLegendHtml`.** Browser-only; verified with
Playwright (28 items in six groups, the ⓘ, the attacks card, PT/EN, 1440 and
760 px with no horizontal scroll, no page errors).

### The layout: home page, full-screen project view, stroke icons

Reworked from sketches the user approved (a Design canvas, "Novo layout"):
the old job view was one very long 75%-wide modal that stacked everything —
warnings, checklist, downloads, tuning, the sync steps, the player, the score,
tones, sections and the exports — which is what made it confusing.

- **Home** (`.app-layout`): a top bar (brand, "Lote (álbum)", "Novo projeto",
  Definições) and the projects as cards (`renderJobCards`: cover when there is
  one, title, artist, a status chip from `jobCardStatus` — the same gaps the
  Exportar page lists), with status filters and a search box over `jobsCache`.
  The first card is a drop zone: a Guitar Pro file dropped on it opens the
  wizard with that file already in step 1's input (a `change` event is
  dispatched so the file-drop label updates).
- **Project** (`#detailOverlay`, now `.project-view`): fixed full-screen at z 40,
  UNDER every modal (z 50), so Definições, tone builder, meta edit and ⓘ all open
  on top of it. Top bar: ← back (`#detailClose`), title/artist with "Editar info"
  and "Versão anterior", a status chip (`setStatusChip`; opens Exportar),
  pending count, "Aplicar e reconstruir", Descarregar. A rail switches pages
  (`showSection`: partitura / tons / letras / capa / exportar, with
  Definições at the bottom).
  - **Partitura** splits into the score (centre: transport with an "Áudio ▾"
    panel for volumes/source/tone preview, then arrangement tabs, "Modo ▾",
    "Notas ▾", snap, the score, fretboard, view controls, the mode hint) and an
    inspector (right: "Sincronização" = the three steps + "Mais opções";
    "Secções" = the section markers). Each column scrolls on its own; the
    `data-page` attribute on `.pv-scroll` is what gives `#review` its full
    height only on this page — without it, every other page opened below a
    screen-tall empty `#review` and looked blank.
  - **Exportar** sits OUTSIDE `#review`: it is also what a building or failed
    job shows (`setReviewReady(false)` disables the other pages and hides
    "Aplicar e reconstruir"/pending, which need a built chart — as when they
    lived inside `#review`). A job's first ready view opens Partitura
    (`sectionShownFor`), so a rebuild shows its progress and comes back to the
    score by itself. Errors stay visible; the pipeline's technical warnings fold
    into one "N avisos técnicos" line.
- **The note tools are two dropdowns** in the score's tool row: "Modo ▾"
  (`#modeMenuBtn` → `#modeMenu`, the nine modes grouped Sincronizar /
  Partitura, each with an icon, name and one-line description) and "Notas ▾"
  (copy, paste, clear this track / all). The user picked this from three
  sketched options. The mode items ARE the old buttons — same ids, still
  `mode-btn`, still wired through `SYNC_MODE_BUTTONS` — so `setSyncMode` also
  writes the trigger's icon/label from the active item's `data-ico`/`data-name`
  ("Nenhum modo" when re-clicking deselects). `wireDropdown` handles
  open/close (Escape, outside click, picking an item), arrow-key focus, and
  flips a menu upward with a capped height when it would run past the bottom
  of its scrolling column.
- **Icons are stroke SVGs**, not emoji: a `<symbol id="i-NAME">` sprite at the
  top of `<body>`, used as `<svg class="ic"><use href="#i-NAME"/></svg>` and,
  from script, `icon(name)` — a function DECLARATION at the top of `app.js`,
  because tables like `SYS_MARK` build markup at load and a `const` there was
  a TDZ crash that blanked the whole UI. They take `currentColor`, so a
  button's state colours its icon. The score's tone/section labels use the
  same symbols through `<use>` inside the SVG. Emoji left in long ⓘ prose or
  toasts is text, not UI.
- **Every id survived the move** (checked by diffing the id list before/after):
  `app.js` reaches the DOM by id, so the reorganisation is markup + CSS plus the
  page/inspector switching above. `[hidden]` is `display:none !important`, so a
  component's own `display` rule can never un-hide what the script hid. Pure
  browser code: verified with Playwright (every page, the dropdowns, modals on
  top, Space to play, drop-to-wizard, a real rebuild going Exportar →
  Partitura, a 1000px viewport), no pytest coverage — same category as the
  other browser-only sections in `TESTING.md`.

**Definições is a page, not a modal** (2026-10-01, sketch "A" the user picked
over a single page of cards: "a página das definições está num texto
corrido"). `#settingsOverlay` is now a `.project-view.settings-view` (z 45:
over the project view, under the modals): the same top bar (← back =
`#settingsClose`, "Guardar" = `#settingsSave`) and a rail of sections —
Geral (idioma), Software (the system check as one card per requirement, a
summary of installed/missing/unknown, a copy button on each install command,
a red dot on the rail when something REQUIRED is missing), Python ML, Stems,
Volume (slider + number + -16/-12/-9 presets, one value), GPU — one section
at a time (`showSettingsPage`, remembered in `localStorage`
`rf-settings-page`). Every id the script reached survived, so `fillSettings`/
the save are unchanged except that the payload is one function,
`settingsPayload`, compared against what was last loaded/saved to show "N
alterações por guardar" and to ask before leaving with unsaved changes.
Browser-only, no pytest coverage; verified with Playwright (every section,
dirty chip, leave-confirm, preset ↔ slider ↔ number, save, remembered
section, English, a 760px viewport, no page errors).

**"Novo projeto" is a page too** (2026-10-01, "faz o mesmo com este banner"
after the Definições page). `#newJobOverlay` is a `.project-view.settings-view
.wizard-view`: top bar (← back = `#newJobClose`, "Passo N de 4 · <nome>" in
`#wizardStepLabel`, `#wizardNav` with Anterior/Seguinte/Criar CDLC), the four
steps as the rail (`#wizardSteps .wz-dot`, now buttons: a done step shows a
tick and goes back on click, the next one acts as "Seguinte" — validation
included), and each step a page of cards. Every id survived; `setWizardStep`
also writes the label and scrolls to the top. Leaving asks first once
anything was chosen (`wizardStarted`), and a successful create hides the page
directly (no question). Browser-only; verified with Playwright (empty
"Seguinte" refused, a real GP5 inspected into step 2, rail back/next, a real
create opening the project, leave-confirm only when started, a 760px
viewport, no page errors).

**"Editar info" is a page as well** (2026-10-01, "faz o mesmo com o Editar
info"). `#metaOverlay` is a `.project-view.settings-view`: top bar (← back =
`#metaClose`, the song in `#metaHeadSub`, "N alterações por guardar",
`#metaSave`), a "Música" card and the GP "Arranjos e afinação" card
(`#metaGp`). `metaValues` splits what needs only the PATCH (title, artist,
album, year) from what needs a rebuild (track map, tunings); the save button
reads "Guardar e reconstruir" only when the latter changed, and **a save that
changed no track or tuning no longer forks a rebuild** — it used to fork one
on every save of a GP job, since the section was merely shown. Leaving with
changes asks first. Browser-only; verified with Playwright (album-only save:
PATCH, no new job; a track change: a new rebuilt job).

**The Tons page is drawn at a larger scale** (2026-10-04, "aumenta o tamanho
da informação na página dos tons … está tudo muito pequeno", from a sketch the
user approved). Text 16-17 px instead of 13-14, buttons/selects 44-48 px,
page-scoped `.tn-*` classes (and the `.ts-*` of the suggestions, used nowhere
else). The page head carries "Criar / editar tons" and "Detetar tom"; "Tons do
projeto" is one card per tone (`toneCardHtml`: gear from the catalogue, a
character from `toneCharacter`, the volume the way the editor shows it);
"Tons de cada pista" picks the chart with tabs (`#toneTrackTabs`, replacing
the old select, shown only with per-track tones), the extras are pills and each
tone change is a row with its time as m:ss.t on the recording clock
(`fmtClockTenths`); the suggestions put the swaps in a grid, each track in a
`<details>` (the first open; `toneTrackOpen` keeps what the user folded across
re-renders, and "Aplicar a esta pista" in the summary does not fold it), an
80 px distortion curve, a 48 px strip, a legend and a table (Parte · Quando ·
Papel · Tom sugerido · Acerto) with the reasons under each row. Every id the
script reached survived except `toneTrackSel`/`toneTrackLabel`. Browser-only;
verified with Playwright on a built two-track project (1440 and 760 px, PT and
EN, tabs/pills/fold/apply, no page errors).

**The Letra page follows the same scale** (2026-10-05, "faz o mesmo para a
página da letra"): three cards — "Encontrar a letra" (search online, detect in
the recording, their status lines, the progress and the LRCLIB results, whose
`.lyr-card` is enlarged only under `#sectionLetras` because the wizard and the
tone collection share it), "Acertar à gravação" (`#lyricsSyncRow`, now the
card itself) and "Palavras" (count, add/sort/export/"Voltar à letra da pauta",
an empty-state line, and a sticky-header table capped at 70vh whose rows show
the recording-clock m:ss.t beside the seconds and a heavier rule under each
line end). Every id survived. Browser-only; verified with Playwright (PT/EN,
1440/760 px, a faked LRCLIB answer, edit/line-end/add/remove, no page errors).

**Modals with typed input never close from the backdrop.** The tone builder
closes only from its own
✕/Cancelar. A press that starts inside a field (selecting text, a trackpad tap
that drifts) and is released outside the box is dispatched by the browser as a
click on the OVERLAY — the common ancestor — so `e.target === overlay`
"click outside to close" silently threw away a half-filled wizard ("a caixa
desaparece e tenho de voltar ao início"). Reproduced with Playwright (press in
the title field, release on the backdrop → closed) and verified fixed. Only the
read-only ⓘ box and the confirm dialog still close from outside. Likewise a
file dropped OUTSIDE a drop zone is `preventDefault`ed at the document level
(`isDropZone`): the browser's default is to open the file, navigating away
from the app. Do not re-add backdrop-close to a form modal.

The "Novo projeto" modal is a **4-step wizard** (`web/index.html`), not a flat
form, because the old single-form layout crammed ~15 fields (including a
`tone_base`/`tone_names` *text* box impossible to fill by hand) and gave no
guidance. Steps, each with a medium icon in a stepper header: **🎸 Ficheiro**
(pick the GP → inspect, which auto-assigns the first eligible track to Lead and
advances), **🎚️ Pistas** (assign Lead/Rhythm/Combo/Alt — needs ≥1), **💾
Gravação** (audio + approximate `offset_s`/`lead_in_s`; fine sync is deferred to
the tab viewer), **🏷️ Detalhes** (title/band/album/year, mutes, optional LRC).
The tone-base/tone-names text inputs were **removed** — tones are built
post-creation in the real tone editor. Step 1 is its own form (submit = inspect,
`/gp/inspect`); steps 2-4 share `gpJobForm` (submit = create, `/jobs/gp`). The
shared footer nav is `setWizardStep(n)` + `validateWizardStep()`; Enter on an
early step advances instead of creating (guarded in the submit handler).

**`gpJobForm` is `novalidate`, and the submit handler does the check.** The
browser's own validation is silent in a wizard: it refuses an invalid field on
an EARLIER, hidden step without being able to show it ("An invalid form control
… is not focusable" in the console only), so "Criar CDLC" simply did nothing.
That is exactly what happened when the start time was pre-filled from GP8 sync
points or Songsterr with `toFixed(3)` into an input declared `step="0.01"` —
4.583 is a step mismatch. The seconds inputs are now `step="any"`, and the
handler finds the first `:invalid` control, jumps to its step and calls
`reportValidity()`. Browser-only (no pytest coverage); reproduced and verified
with Playwright: 4.583 now creates the job, and a genuinely invalid value takes
the user back to step 3 with the field focused.

### Deleting the previous version after a rebuild (`/drop-previous`)

"Quando reconstruo um novo psarc, pergunta sempre se pode apagar o anterior."
Every rebuild (and "Recarregar ficheiro GP", and a track re-map in "Editar
info") forks a new job and keeps the old one. Each of those now asks
(`offerDropPrevious`) whether the old one can go, and the answer waits —
per new version, in `localStorage` `rf-drop-previous` so closing the app does
not lose it — until that version is **built**; a failed rebuild keeps the old
one and says so (`maybeDropPrevious`, run on every `selectJob`). Then
`POST /jobs/{id}/drop-previous` deletes the version it was rebuilt from
(`_delete_job_files_and_row`, shared with `DELETE /jobs/{id}`, so the recording
and GP file stay while another version uses them). **What the new version
still uses from the old one is moved over first**: `params["stems"]` is
inherited with absolute paths into the version that ran the separation, and the
Demucs guitar-stem cache lives there too (`_CARRIED_WORK_DIRS`); deleting
without moving would have left the new version with stems that 404. Anything
rebuilt from the deleted version then points at the version before it
("Versão anterior" keeps working). Guarded by
`test_the_previous_version_can_be_dropped_once_the_new_one_is_built`; with
Playwright on a real rebuild: asked, answered yes, the build finished, the old
job and its folder were gone and the new one pointed at the version before.

### The whole project in one file (`.rfproj`, `infrastructure/project_archive.py`)

"implementes o exportar e importar o projeto" (2026-10-18). A ZIP: `project.json`
(`format` "rockforge-project", `version` 1, the app version, the song, the job's
params) + `files/recording.<ext>`, `files/score.<ext>`, optional
`files/cover.<ext>` and `files/stems/<name>.wav`. The built bundle is NOT
inside — an imported project is built again from the same params (small file,
never an older build). `GET /jobs/{id}/project-info` (what would go in, sizes,
`missing`), `GET /jobs/{id}/export-project?stems=` (written to
`work_dir/exports/` and deleted once sent, `Artist - Title.rfproj`; stems =
every separated instrument `api._separated_stems(..., drums=True)` finds —
moved to app.py from analysis.py, now shared) and `POST /projects/import`
(a new job, enqueued). **Reading one is reading untrusted input** — projects
are made to be passed around: only the known member names are read and an
output path is never built from a member name (a stem's name must match
`STEM_NAME`); `params` keep only `PORTABLE_KEYS` — every key naming a file of
the exporting machine (`gp_path`, `cover_art`, `stems`, `installed_*`,
`corrected_gp`) or a version chain/build outcome/task log is dropped and the
importer sets its own (`HANDLED_KEYS`; statuses only when finished,
`FINISHED_STATUSES`), so a hand-made project cannot point `/stem/{name}` or the
build at a path; NaN refused at parse, encrypted members refused, sizes capped
as declared and as read (`MAX_MEMBER_BYTES`, `MAX_TOTAL_BYTES`), a newer
`version` refused in words; the GP file must parse, the cover is checked by its
bytes, a stem by its RIFF/WAVE header. Imported stems go to
`demucs_stems/stems/htdemucs_6s/imported/` (where every stem reader looks and
"drop the previous version" carries), the non-drum ones into `params["stems"]`.
**When the code writes a new params key, classify it** in `PORTABLE_KEYS` or
`HANDLED_KEYS`: `test_every_key_the_code_writes_into_params_is_classified`
scans the source and fails otherwise. UI: Exportar → "Projeto RockForge
(.rfproj)" (`renderProjectExport`, size from `/project-info`, the stems
checkbox only when there are any, a confirm when "Pendente" is not empty —
pending edits are the browser's, not in the file); home → "Importar projeto"
(`importProject`, hidden `#importProjectFile`) and a `.rfproj` dropped on
`#homeDrop` (not the wizard). Guarded by `test_project_archive.py` (what
travels, the classification scan, read-back, every refusal in words, member
names never becoming paths, the read cap) and in `test_api.py`
`test_a_project_exported_and_imported_comes_back_with_everything`,
`test_a_project_whose_files_are_gone_or_a_bad_file_is_refused_cleanly` and
`test_an_imported_project_cannot_point_the_server_at_a_path` (fails when the
params filter is dropped); with Playwright on a live server (PT 1440 / EN 760
px): the row and its sizes, the pending confirm, a download with both stems,
imported from the home page and built for real (`/psarc-check` clean, guitar
offered, drums in the bars), a dropped `.rfproj` opening as a project, a bad
file refused in words, no page errors.

### Batch processing ("Lote (álbum)")

For an entire album: the home page's "Lote (álbum)" button opens the batch
page (`#batchOverlay`, full-screen like Definições/Novo projeto since
2026-10-01: top bar with back, a live summary in `#batchSummary` — "N por
criar · N criados" — and "Criar projetos"; cards for the files, the shared
fields and one row per project with a status chip; leaving asks first while
something creatable is still pending) that creates several GP jobs without repeating the wizard
per song. **Frontend-only — no new backend endpoint.** Each pair is created by
looping the exact same two calls the single-project wizard makes
(`POST /gp/inspect` → `POST /jobs/gp`), with the track fields left blank so
the pipeline's existing `auto_pick_tracks` name-heuristic fallback
(`gp_pipeline.py`, fires when every track slot is unassigned) fills in
Lead/Rhythm — the same thing that already happens for a lone-track GP in the
normal wizard. This keeps the batch path byte-for-byte the same code as
creating one job by hand; nothing new to guard in `pytest` (pure
`web/index.html`/`web/app.js`, same category as the other browser-only
sections in `TESTING.md`).

**Pairing (`pairBatchFiles`, pure, `web/app.js`).** The user picks multiple GP
files and multiple recordings; each GP file is matched to the recording
sharing its **filename stem** (case-insensitive, extension stripped — e.g.
`faixa1.gp5` ↔ `FAIXA1.wav`); any GP file left unmatched pairs with a leftover
recording **in the order both lists were chosen**, so an album where names
don't line up still gets a pair per song as long as the counts roughly match.
A GP file with no recording left at all shows "sem gravação — não vai ser
criado" in the preview list and is skipped on submit, never silently paired
with the wrong track. **A GP file that carries its own audio (GP8) needs no
recording**: each GP is sent to `/gp/inspect` as soon as it is picked
(`inspectBatchGpFiles`, one at a time, cached per `File` in `batchInspected`
and reused at submit, so nothing is uploaded twice), and `pairBatchFiles(gp,
audio, ownAudio)` gives such a file "o áudio que vem dentro do ficheiro GP"
(`use_embedded_audio=true` + its `sync_start_s` as the start). A recording
named like it is set aside ("fica de fora") rather than handed to the next
song by the in-order fill — before, that file was either skipped or paired
with another song's recording. "Criar projetos" waits until every file has
been read. An abandoned selection leaves inspected uploads for the orphan
sweep, like an abandoned wizard. Verified with Playwright (the user's GP8 +
a GP5 + two recordings → own audio / the leftover wav, both jobs as said). The preview list (`renderBatchPairs`) is the only
confirmation step — there is no per-pair track/metadata screen (that would be
the normal wizard, one song at a time).

Submission is **sequential**, one pair at a time (not `Promise.all`), so the
browser isn't uploading N recordings simultaneously; each pair's row updates
its own ⏳/✅/❌ status live. Album/artist/year fields in the modal are
**shared** across every pair (sent as the form fields on every `/jobs/gp`
call, same precedence rule the single-project endpoint already has — form
value beats the GP file beats the audio tags); title/artist otherwise come
from each song's own GP metadata or audio tags, exactly as for a single job.

**Honest limits:** the auto-pick heuristic is a name match ("lead"/"rhythm"
substrings), the same heuristic the single-project wizard falls back to and
already warns about (`"tracks auto-selected by name heuristic — confirm they
are the right ones"` in that job's warnings) — a wrong pick on an unusually
named track is fixed the same way as any other job: reopen it and use "✎
Editar info" to re-map tracks, which forks a rebuild. No dedicated track
review step exists for batch-created jobs; that's the whole point of skipping
per-song setup, and the completeness checklist plus that pre-existing warning
surface it rather than hiding it.

The **"Antes de usar" checklist** (`renderCompleteness`, on the Exportar page
beside the downloads; its gaps also feed the top bar's status chip) reads completeness signals straight off
`JobOut` and surfaces what would leave the bundle incomplete/poor, each with a
jump-button to the right editor (`COMPLETE_ACTIONS`). Rows + alerts:
- ✅/❌ **PSARC jogável** ← `psarc_available` (❌ = no Wwise/.wem).
- ✅/ⓘ **Tons definidos** ← `has_tones` (`JobOut` field = `params["tones"]`/
  `tone_base`/`tone_names` non-empty); without it the row is the informational
  "Tons standard" (DLC Builder's default per path, see the SNG section).
- ✅/⚠️ **Capa** ← `cover_art` (else `albumArt` empty).
- ✅/⚠️ **Sincronização** ← `sync_edited` (new field; `_sync_edited(params)`:
  offset moved off 0, tempo scaled, or any drift anchor job-level/per-arrangement)
  — a **soft** "confirmaste a sincronização?" reminder, not a hard "desalinhado".
  Songsterr `bar_times` count as synced too. **The row can be cleared by the
  user** ("Está sincronizada" → `PATCH /jobs/{id}/sync-confirmed`, stored as
  `params["sync_confirmed"]`, surfaced as `JobOut.sync_confirmed`, undoable):
  a chart that needed NO adjustment — synced in Guitar Pro 8, its embedded
  audio, or simply right from the start — has nothing for `sync_edited` to see,
  so before this the reminder could never go away ("nunca consigo tirar, mesmo
  quando está sincronizado"). A checklist flag only: no rebuild, and a fork
  inherits it with the rest of `params`. Guarded by
  `test_a_song_that_needed_no_adjustment_can_be_confirmed_as_in_sync` /
  `test_songsterr_bar_times_count_as_synchronised`.
  **A chart synced in Guitar Pro 8 counts by itself, and "synced" is visible
  everywhere** ("cria uma forma de identificar que a track já foi sincronizada
  por mim, ou aceite como sincronizada"). The build stores
  `params["gp_synced"]` (the file carries its own SyncPoints,
  `_gp_carries_sync`), and `_backfill_gp_synced` marks projects built before
  that key existed once at startup, so they need no rebuild.
  `JobOut.sync_source` says why a chart counts as in sync — `confirmed` (the
  user's word wins), `songsterr`, `gp`, `adjusted` (corrected here, not yet
  confirmed) or None (`_sync_source`). It drives a "Sincronizada" chip on the
  project card (`isSynced`), an **"Estado da sincronização"** card at the top
  of the Sincronização tab with "Marcar como sincronizada"/"Desmarcar"
  (`renderSyncState`, the same `PATCH /sync-confirmed` — it was only reachable
  from the Exportar page before), and the checklist row ("Sincronizada no
  Guitar Pro" / "pelo Songsterr"; an adjusted chart also offers "Marcar como
  sincronizada"). Guarded by `test_a_chart_says_why_it_counts_as_in_sync`,
  `test_a_gp8_file_synced_in_guitar_pro_is_recognised` and
  `test_projects_synced_in_guitar_pro_before_the_flag_existed_are_marked_on_startup`
  (mutation-checked); the UI with Playwright (mark → card chip → undo), and
  15 real GP8-synced projects read `gp` after one restart.
  **Reversed in the UI (2026-09-30): only the user's marking is "synced".**
  "O estado da sincronização está a verde, mas ainda não sincronizei nenhuma
  das pistas": a GP8 file with SyncPoints turned every tab green and the card
  said "Sincronizada no Guitar Pro 8" with 0 of 5 tracks marked. The backend
  is unchanged (`sync_source` still reports `gp`/`songsterr`, which is useful
  to know), but the viewer no longer reads them as synced: `arrSynced` is
  `a.sync_confirmed` alone, `isSynced` (the card chip) is `confirmed` alone,
  the card shows the GP8/Songsterr text as a hint ("… Ouve e, quando
  baterem, marca cada pista"), and the checklist row for them is a warning
  ("Temporizada no Guitar Pro — confirma") with "Está sincronizada". Where
  this section says a GP8/Songsterr chart "counts" or turns tabs green, read
  "is hinted". Browser-only, no pytest coverage.
  **Each track is marked on its own, and its tab turns green** ("a
  sincronização é feita por track independente, e o nome da track fica a
  verde"). `params["synced_arrangements"]` lists the charts marked;
  `PATCH /sync-confirmed` takes an optional `arrangement` (none = the whole
  song, every built chart — the checklist's button), and the song's
  `sync_confirmed` becomes true only when every built chart is marked
  (`_built_kinds` reads the bundle's XML names). `ArrangementOut.sync_confirmed`
  drives the tab (`updateArrTabs`: ✓ + green; the active tab green-filled;
  only charts the user marked — `arrSynced`, see the reversal above), and the "Estado da sincronização" card now speaks
  for the chart on screen ("Marcar esta pista como sincronizada", "N de M
  pistas marcadas"), re-rendered on every tab switch. A song confirmed before
  charts could be marked one by one counts every chart (`_synced_arrangements`).
  **This surfaced a real bug: an alternate chart looked like a second Lead.**
  `/arrangements` named each chart from its XML's `<arrangement>` tag, where an
  alternate writes its BASE path ("Lead"/"Rhythm", as the game needs), so the
  user saw two "Lead" and two "Rhythm" tabs — and, since the viewer keys
  pending anchors, tempo, note edits and the rebuild's `arrangement` by that
  name, the alternate's corrections landed on the main chart and it could not
  be synchronised on its own. Charts are now named by their FILE
  (`_built_arrangement_kind`: `arrangement_alternate_lead.xml` → "Alternate
  Lead"), listed in the build's order (Lead, Rhythm, Combined, alternates —
  the file names' alphabetical order put the alternates first), shown by the
  name the game gives them (below), and `/export-arrangement-gp`
  finds `arrangement_alternate_lead.xml` (it looked for "alternate lead", with
  a space). Guarded by
  `test_an_alternate_chart_is_its_own_arrangement_not_a_second_lead`
  (name, order and export each mutation-checked),
  `test_each_chart_is_marked_in_sync_on_its_own` and
  `test_a_song_confirmed_before_charts_were_marked_one_by_one_marks_them_all`;
  with Playwright on the user's GP5 built as Lead + Lead alternativo: the tabs
  read both names, marking one turns only it green, an "Início" correction on
  the alternate lands in its own anchor set, and marking both makes the song
  confirmed.
  **Every chart is named as Rocksmith names it** ("a representação das pistas
  … exatamente como aparece no rocksmith, para ser mais fácil distinguir"):
  `domain.arrangement.game_names` — the path in capitals (LEAD/RHYTHM/COMBO,
  the game's ArrangementName; our Combined is its Combo), numbered only when
  the song has two charts on that path ("LEAD 1", "LEAD 2", "RHYTHM"). The
  number is `song_partitions`, DLC Builder's `Partitioner` (the main chart 1,
  its alternate 2), and it is ALSO what the manifest's `SongPartition` now
  carries — it was 1 on every chart, so a Lead and its alternate both claimed
  to be the first Lead. One function for both, so the tab and the game cannot
  disagree. `ArrangementOut.game_name` carries it; `arrLabel` shows it on the
  tabs, the Tons track tabs, the suggestions, the sync card, "Início da
  música (…)", the note-edit counts and the audio-source list; the game's own
  words, so not translated. The track pickers say which alternate becomes
  "LEAD 2"/"RHYTHM 2" in game. The numbering is the user's description of the
  game (and DLC Builder's partition); the exact in-game rendering of a
  numbered path was not seen from here. Guarded by
  `test_each_chart_carries_its_number_on_its_path` (mutation-checked),
  `test_game_names_number_only_a_path_with_two_charts` and the game names in
  `test_an_alternate_chart_is_its_own_arrangement_not_a_second_lead`.
- ⓘ **Letra** ← `has_lyrics` (informational, never an alert). NOTE: read
  `has_lyrics` (new field: edited `lyrics_events` OR `lrc_text` OR
  `lyrics_status == "ready"`), NOT `lyrics_status` alone — GP-embedded / LRC /
  edited lyrics never set `lyrics_status="ready"` (that's WhisperX-detection
  only), so keying off it made a song WITH lyrics read "sem letra".
- ⓘ **AppID/propriedade** — informational: the `.psarc` reuses a specific DLC's
  appid the player must own (the #1 "não aparece no jogo" cause, otherwise
  invisible in the UI).

When any warn/err row exists, an amber banner over the downloads summarizes
what's missing. Nothing is blocked (honesty principle) — the user can still
download, but won't silently ship a tone-less/cover-less/unsynced PSARC.
`has_tones`/`sync_edited`/`has_lyrics` guarded by
`test_completeness_fields_reflect_job_state` /
`test_sync_edited_true_from_anchor_only` / `test_has_lyrics_true_from_edited_events`.

### Album cover art

`POST /jobs/{id}/cover` (multipart `file`, jpg/png) stores the image as
`<work_dir>/<job_id>/cover<ext>` and records the filename in
`params["cover_art"]`; `GET /jobs/{id}/cover` serves it back for the web UI's
preview. Uploading does not trigger a rebuild — the next build/rebuild picks it
up via the worker's `params.get("cover_art")` lookup and passes it as
`Packager.package(..., cover_art=Path)`.

Both `DlcBuilderPackager` and `NativePsarcPacker` copy the image into the bundle
as `cover.<ext>` and record it in `rockforge_project.json["cover_art"]` (via the
shared `build_project_metadata()`), so it's available as the album art when
creating/updating the DLC Builder project (DLC Builder generates its own in-game
DDS textures on import).

**The native PSARC already ships the real cover as a game texture.**
`gamedata.album_art_dds(size, cover_path)` converts it to **DXT1** at 64/128/256
with Pillow (from the `[psarc]` extra) and the packer writes
`gfxassets/album_art/album_<key>_{64,128,256}.dds`; the manifest's `AlbumArt`
attribute carries `urn:image:dds:album_<key>` and the xblock's
`AlbumArtSmall`/`Medium`/`Large` point at it. Without Pillow, or with an
unreadable image, it degrades to the neutral solid placeholder rather than
failing the build — so the URN always resolves. Verified end to end by driving
the packer with a real image and decoding the DXT1 block colour back out of the
packed `.psarc`. (An earlier honesty note here claimed the opposite; it was
stale, and the recommendation built on it was wrong.)

The Song2014 XML's `<albumArt>` now carries the same URN
(`render_arrangement(arr, album_art_urn)`), which is **completeness for the DLC
Builder path only**: the game resolves the cover through the MANIFEST, and the
instrumental XML is not even shipped inside the `.psarc` (only
`<key>_showlights.xml` is). It stays empty when no key is supplied, so a direct
`write_arrangement_xml` call is unchanged.

### Album, year and cover — looked up, then CHOSEN (`/album-lookup`)

`infrastructure/album_lookup.py` asks two keyless services by title + band —
the **iTunes Search API** (album, release date, artwork) and **MusicBrainz**
(official releases of the recording) with covers from the **Cover Art
Archive** — and returns a ranked LIST (`search_albums`: albums, then EPs,
singles, compilations; earliest year first within each, since a later date is
usually a reissue). Nothing is written from a guess: the user picks a card, and
every card shows the matched track and the source, because a text match can
return a cover version or a compilation first. Matching is case/accent
insensitive containment (`_same`). One service down still returns the other;
both down is a **502**, never a 500, and never an empty list pretending nothing
exists. stdlib `urllib`, no new dependency.

**The search is by the MAIN artist; an empty answer says why.** A credit like
"Eminem feat. Avril Lavigne" is searched as "Eminem" (`primary_artist`; a
"(feat. …)" in the title is dropped by `search_title`) — only the unambiguous
feat./ft./featuring markers split it, never "&" or ",", which are part of real
names ("Simon & Garfunkel"). `/album-lookup` returns `searched_title`/
`searched_artist` and `failures` (a service that could not be asked), so the UI
can say "nothing found for X by Y" and never passes a service outage off as
"not in the catalogue". The user's first real test hit exactly the honest
empty case: "Strangers Now" is a fan remix on YouTube, in neither catalogue —
fan remixes, covers and AI-made songs have no official release to find.

**Downloading a chosen cover is the SSRF-sensitive part.** `/jobs/gp`'s
`cover_url` form field and `POST /jobs/{id}/cover-from-url` take a URL from the
client, so `fetch_cover` only accepts **https** on the services' own image hosts
(`*.mzstatic.com`, `coverartarchive.org`, `*.archive.org` — the archive
redirects there), re-checks EVERY redirect against the same allowlist
(`_AllowlistRedirects`), caps the read at 10 MB (`read_capped`) and trusts the
file's **magic bytes**, not its name (`image_suffix`: JPEG/PNG only). A
disallowed URL is a 422 before anything is opened. The stored file goes through
the same `_replace_cover`/`_record_cover` as a manual upload, so the rest of the
cover path (bundle, `.rs2dlc`, the PSARC's DDS) is unchanged.

**In the wizard a cover failure must not lose the project**: the job is
committed first, the download is attempted after, and a failure only leaves
`cover_art` false — the worker overwrites `job.warnings` at the end, so the UI
reports it from that flag (toast) instead of a warning that would vanish.

**Or the user's own image, in the wizard too** (Facebook feedback, 2026-10-16:
"it won't let me upload an album cover from my pc" — step 4 only offered the
lookup's cards and "Sem capa"; a local file was only possible on the Capa page,
after creating). `/jobs/gp` takes a `cover` upload (`#wzCoverFile`, under the
cards), checked by its BYTES (`image_suffix`, 415 up front for anything not
JPEG/PNG, before the job exists) and stored before the job is queued, winning
over `cover_url`, which is then not fetched; in the UI picking a file
deselects the cards and picking a card clears the file. Guarded by
`test_a_cover_from_the_computer_is_in_place_before_the_first_build`; the
wizard with Playwright (PT/EN: file ↔ card, the created job carries it).

UI: wizard step 4 runs the search once on arrival (`maybeAutoAlbumSearch`),
preselects the best guess filling Álbum/Ano **only if empty**, a card click
fills them outright, "Sem capa" opts out, and a card whose thumbnail fails to
load is marked `cover_broken` (placeholder shown, `cover_url` not sent). The
Capa page's "Procurar capa online" applies a card to an existing project
(`cover-from-url`, plus `PATCH /metadata` when "Preencher também o álbum e o
ano" is ticked). The grid is built with DOM calls, not `innerHTML`, since the
names and URLs come from third parties. **Confirmed working against the live
services by the user (2026-09-26)** on a real machine with an official
release — the sandbox itself still blocks them all, so CI only ever sees the
fakes (TESTING.md §7d-sexies). The `600x600bb` iTunes rendition is
undocumented; if covers ever stop loading, check that first. Guarded by
`test_album_lookup.py` and, in `test_api.py`, `test_album_lookup_*`,
`test_a_chosen_cover_is_downloaded_into_the_job`,
`test_a_cover_url_off_the_cover_services_is_refused_without_fetching`,
`test_a_cover_that_will_not_download_is_a_502_and_changes_nothing`,
`test_the_wizards_chosen_cover_is_in_place_before_the_first_build` and
`test_a_wizard_cover_that_fails_still_creates_the_project`.

### Outbound HTTPS trusts the system roots PLUS certifi's (`infrastructure/_https.py`)

Every stdlib `urllib` client (LRCLIB, iTunes/MusicBrainz, the cover
download) opens its connection with `_https.ssl_context()`: the system
default context with `certifi.where()` ADDED via `load_verify_locations` —
plain system default only when `certifi` is missing (a core dependency, so a
broken install). **Verification stays on** — this adds trusted roots, never
turns checking off; do not "fix" a TLS error by disabling it.

Why: the user's Songsterr import failed with `CERTIFICATE_VERIFY_FAILED:
certificate has expired` while the album lookup worked on the same machine.
Python trusts only the roots the OS store already HOLDS, and Windows installs
roots lazily (its own networking fetches a missing one on demand; Python's
enumeration never triggers that), so a store missing a current root but still
carrying an expired cross-signed path (classically Let's Encrypt's ISRG Root
X1 via the expired DST Root CA X3) refuses a valid site. certifi supplies the
missing root, and OpenSSL prefers a time-valid issuer when names collide.
**Do not switch to certifi ALONE** (`cafile=certifi.where()` in
`create_default_context`): an antivirus or company proxy that inspects HTTPS
re-signs every site with a root it installs only in the SYSTEM store, so
certifi-only would break every lookup on those machines — including the ones
that work today. `network_error_message` turns a certificate refusal into a
sentence that says what to check (clock, antivirus HTTPS scanning,
`pip install --upgrade certifi`) instead of a raw `urlopen error`.
PyInstaller's contrib `hook-certifi` bundles `cacert.pem` into the `.exe`.
yt-dlp does its own TLS (and uses certifi itself when installed). **Not
verified against the user's machine from here** (the sandbox cannot reach
Songsterr); the cause above is the likeliest reading of that exact error, not
a reproduction. Guarded by `test_https.py` (certifi's roots loaded into a
root-less stand-in for the system store — mutation-checked — the system roots
kept, `CERT_REQUIRED` throughout, the fallback, every client passing the
shared context, and the explained message).

**Songsterr is asked with `requests`, default headers — the reference tool's
exact client.** teaqu/guitar-pro-youtube-sync (the tool the user's own GP
file was built with, proven to work on their machine) calls meta, video
points and the CloudFront parts as a bare `requests.get(url, timeout=…)`, so
RockForge does the same instead of `urllib` with an invented `Mozilla/5.0
(RockForge)` User-Agent (`requests` is a core dependency; `types-requests`
in `[dev]` for mypy); `test_songsterr_is_asked_with_the_default_requests_client`
fails if a header is ever added back. Songsterr's TLS trust is therefore
requests' own (certifi), not `_https.ssl_context()` — the same as the
reference tool (`REQUESTS_CA_BUNDLE` points it at another bundle).

**A refusal says Songsterr's OWN reason (`_refusal`).** The 403 that
prompted the switch was NOT bot protection — the user's diagnosis showed it
plainly: `/api/meta/6019365` answered `403` from nginx with JSON
`{"code":"ERR_UNPUBLISHED","reason":"This tab is unpublished. Only authors
can view their own unpublished tabs."}`, while `/api/meta/84` answered 200
and the reference tool worked on a DIFFERENT, published tab (5993626). The
old message ("o Songsterr respondeu 403") and then a guessed "may be
blocking automated requests" sent the diagnosis the wrong way twice.
`_refusal_code()` maps the one code actually seen to a Portuguese sentence;
any other JSON `reason`/`error` is shown verbatim; a non-JSON refusal keeps
the plain status. The status is still carried, so a 403 from a part CDN
still means "try the next distribution". Guarded by
`test_a_refusal_or_an_unreadable_answer_is_a_clear_error`.

### Automatic tone detection (`/jobs/{id}/detect-tones`)

`POST /jobs/{id}/detect-tones` (GP jobs) runs Demucs
guitar separation (`htdemucs_6s`) on the recording and analyzes the guitar
stem (`tone_analysis/analyzer.py`) to classify the tone into one of three
categories: `clean`, `crunch`, or `high_gain`. The classification drives a
preset suggestion: curated Lead + Rhythm tones from the Rocksmith gear catalogue
(real amp/cabinet/pedal keys with knob values) are proposed and stored in
`params["detected_tones"]`.

**Gain estimation (why it stopped reading "usually too clean").** The gain
estimate combines **brightness-independent distortion cues** — spectral
flatness (saturation packs the spectrum → higher) and dynamic compression via
the crest factor (distortion sustains/compresses → low crest) — with spectral
contrast and a low-weighted ZCR. Critically, the features are computed **only
over the frames where the guitar is actually playing loud** (RMS ≥ 30% of the
peak) after peak-normalizing, so silences, count-ins and clean breaks no longer
drag a mostly-distorted song down to `clean`. The old version averaged ZCR +
centroid over the WHOLE stem — both dominated by brightness — so a dark,
low-tuned or palm-muted high-gain tone was systematically under-read. The
crunch/high-gain boundary is `gain_level ≥ 0.5`; `flatness`/`compression` are
surfaced in the tone log and `detected_tones.profile` for transparency. Still a
heuristic — the character, not the actual amp.

Progress is tracked via `params["tone_detection_status"]`
(`detecting`/`normalizing`/`separating`/`analyzing`/`ready`/`unavailable`),
never `JobStatus`. The web UI's "Detetar tom" button triggers detection and
polls `GET /jobs/{id}/detected-tones` for the result; "Aplicar melhores"
loads the top presets into the tone editor so the user confirms/adjusts, then
"Aplicar e reconstruir" commits them.

**Ranked candidates, not one guess (`rank_tones`).** The old path mapped the
detected category 1:1 to a single Lead+Rhythm preset (`suggest_tones`), so when
the guess was off the user had nothing to browse ("dificuldade em encontrar os
tons semelhantes"). `tone_presets.rank_tones(gain, bright, low, category)` now
ranks the WHOLE curated library (`_LEAD_LIBRARY`/`_RHYTHM_LIBRARY`, several
presets spanning the gain axis with brightness/low-end variants, each carrying a
`(gain, bright, low)` fingerprint) by a **weighted distance** to the analyzer's
`ToneProfile` — gain dominates (`_W_GAIN=2.2` vs brightness/low `1.0/0.9`), each
candidate annotated with a 0-100 `match`. The worker stores `lead_candidates` /
`rhythm_candidates` (closest first) plus the detected `profile` in
`params["detected_tones"]`; `/detected-tones` returns them and the tab viewer
renders the profile bars + two ranked lists, each candidate with its `match %`
and a "usar" button that loads only that role's tone (Lead/Rhythm replaced
independently). `suggest_tones` is kept for the legacy one-per-category callers/
tests. Honesty unchanged: this proposes plausible catalogue matches by
character, it does NOT identify the real amp.

Honesty note: spectral analysis does NOT identify the actual amp/pedal used in
the recording — it classifies the *character* of the guitar sound and suggests
a plausible Rocksmith gear match. Detection needs the `[ml]` extra (Demucs +
librosa).

### Tone over time + a tone for each part of each track (`/tone-suggestions`)

"melhorar a deteção de tons das músicas e com sugestões para atribuir tons a
partes específicas da música (track)". One tone per role for the whole song
cannot say that a song has a clean intro, a crunchy verse and a hotter solo,
nor that over the SAME sound the Lead solos while the Rhythm chugs.

**Measured over time, in the same read.** `_librosa_runner.tone_report` returns
the whole-song features (what `tone_features` always returned — it is now
`tone_report(...)["features"]`, one implementation) plus the same seven
features per **4 s window, 1 s hop**, each flagged `active` when the guitar is
playing in at least 40 % of its frames. `analyzer.window_profiles` (pure) turns
them into `WindowProfile`s — and must NOT run a window through the song
calibration: the crest factor, its strongest cue, depends on the length
measured (on the user's real mix: ~1.4-1.7 per window against 2.14 for the
song), so every window read hotter than the song. Each window is instead
**anchored** on the calibrated song gain and moved by how it DIFFERS — crest
against the mean ACTIVE window crest (silences do not set it), contrast,
flatness and ZCR against the song's (frame averages, length-independent) —
with the song mapping's own slopes and weights; brightness/low end are frame
averages and use the song formulas directly. On that real mix: song 0.375,
median window 0.372, intro ~0.30, later ~0.45, outro down to 0.05.
`detect_tones` stores `detected_tones["timeline"] = [[t, gain, bright, low,
active], …]` in the RECORDING clock; `/detected-tones` says `has_timeline`.

**Per part, per track (`tone_analysis/sections.py`, pure).** The stem is every
guitar mixed, so the audio alone cannot tell Lead from Rhythm; the chart can.
For each part of each chart — its sections, or groups of 8 bars when it has
fewer than two (`segments_for`) — `play_style` measures what it plays (share of
notes struck in chords, palm-muted, with lead techniques, at fret ≥ 12, let
ring/harmonic) and `audio_in` averages the ACTIVE windows there, reading the
recording `pad_s` later (`max(0, MIN_LEAD_S - offset_s) + lead_in_s`, the
build's own pad). `choose_role`: **clean** when the recording is quiet there
(gain < 0.22) or the part lets chords ring without palm mute (gain < 0.45);
**lead** for single notes (< 25 % chords) with lead techniques (≥ 15 %) or high
frets (≥ 40 %); else **rhythm**; **silent** with no notes. The preset is the
closest of that role's library (`rank_role`) to the recording's sound nudged by
the part (a solo a little hotter/brighter, a chug heavier in the lows), with
reason codes and a confidence; a part the guitar is barely heard in (< 30 %
active) uses the song's overall sound and says so (`no_audio`, low). A silent
part keeps the tone before it, consecutive parts with one tone merge, and a
track uses **at most four tones** (`MAX_TONES`): Rocksmith only switches to
slots A-D, and the existing convention puts the base among them so a switch
can come back to it — the least-used tone is folded into its nearest
fingerprint (`_fold_tones`). The plan's `names` is exactly what `tone_names`
takes (base first). `GET /jobs/{id}/tone-suggestions` computes it on request
from the CURRENT build's XMLs (409 before a build, 409 without a timeline — a
detection from before this version), so parts and times follow every applied
correction.

**Tones per arrangement (`arrangement_tones`).** Rocksmith's tones always were
per arrangement (the writer, `.rs2dlc` and manifest read `arr.tone_base`/
`tone_names`/`tone_changes`), but RockForge gave every chart the same set.
`GpJobSpec.arrangement_tones: dict[str, ArrangementTones]` — keyed by
`ArrangementKind.value`, resolved by `tones_for(kind)` with the song-level set
as fallback, the `sync_for` pattern; the gear definitions (`tones`) stay
song-level. `RebuildIn.arrangement_tones` (null = untouched, `{}` = back to
the song's set, max 4 names each), stored in `params`, returned by `/tones`,
rebuilt by the worker. UI (Tons page): "Mesmos tons em todas as pistas"; unticked,
the four tone globals are the set of the chart ON SCREEN, swapped on every tab
change (`switchToneSet`, called from `showArr` — the `syncAnchorsByKind`
pattern), each chart seeded from the song's set; `toneSetsForRebuild` sends
the song set plus the full per-track map; `activeToneKeyAt(t, kind)` gives the
synthesized source its own chart's tones; deleting a tone removes it from
every set (`forgetToneKey`). "Sugestões por secção" draws, per track, the
distortion curve (scaled to the song's peak), a strip of parts coloured by
role (a click seeks), and one line per run of parts with the same tone, with
the reasons in words; "Aplicar a esta pista"/"a todas" adds the presets to the
project and sets the track's own set (with one chart, the song's). Pending
until "Aplicar e reconstruir", like every tone edit.

**The switch points with the user's own tones** ("usar a atribuição dos pontos
em que entram os tons (detetado pela app), e substituir os tons por aqueles que
eu quero, incluindo de psarc que já existe"). Above the tracks, "Trocar os tons
sugeridos" lists every distinct suggested tone (`suggestedTones`) with a
picker: the suggested one, a project tone, a library tone, or "Dos teus
PSARC…", which opens the tone collection in PICK mode (`openToneCollection({
label, onPick, onClose})`: the card's button reads "Escolher este", picks and
closes; closing without a pick re-renders and the picker falls back). The
choice is one map for every track (`toneSwaps` — the same preset is usually
suggested on several charts), **kept with the project** ("guarda as trocas
escolhidas para não se perderem ao mudar de projeto"): every change is sent to
`PATCH /jobs/{id}/tone-swaps` (the whole map, `params["tone_swaps"]`, each
stand-in validated as a real tone, ≤ 32, source project/library/collection; no
rebuild, a fork inherits it) and comes back as `ToneSuggestionsOut.swaps`; a
stand-in no longer in the lists (a project tone deleted, a library tone
removed) keeps its own option and is copied back in on "Aplicar" rather than
silently dropped. Guarded by
`test_the_tones_chosen_in_place_of_the_suggested_ones_are_kept_with_the_project`
(stored, read back, inherited by a fork, nonsense refused, cleared). **The same
picker sits in every part's row** ("Diz que está a distortion … não consigo tirar":
the rows only SHOWED "Meu tom (em vez de Crunch encorpado)", and the picker sat
above the first track, out of sight, so a swap could not be undone where it was
seen): `toneSwapSelect(key, name)` builds both, its first option "<tone> (o
sugerido)" drops the swap, and a note under the card's title says the suggestions
change nothing until "Aplicar a esta pista" and that what a track plays is "Tons
de cada pista" — the user had already changed that by hand and read the table as
the track's state. Browser-only; verified with Playwright (suggestions faked: the
row shows the swap, "o sugerido" sends `swaps: {}`, PT/EN, 1440/760 px, no page
errors). "Aplicar" copies a library or
PSARC stand-in into the project once (`swapToneKey`, a different tone under
the same key gets a suffix) and maps the plan through it (`swapPlan`, pure:
names deduplicated, and a switch to the tone already playing dropped — two
suggestions swapped for one tone merge, and the switch between them goes).
The switch TIMES are the plan's, untouched. Frontend only; `swapPlan` checked
with Node (identity, partial swap, two merged into one, all into one) and the
flow with Playwright (suggestions faked: a project tone and a PSARC tone in,
switches at 20/40/60 s kept, the PSARC tone copied into the project, cancel
restores the picker, no page errors).

Honest limits, said in the ⓘ: the per-track difference comes from the chart,
not the audio; presets are chosen by character, not the real amp; parts are
those of the last build. Demucs cannot run here, so the timeline was
calibrated on the user's full mix, not a separated guitar stem. Guarded by
`test_tone_sections.py` (anchoring, silences not moving the reference, roles
and reasons, two tracks over one sound, clean→heavy switch, a rest keeping the
tone, the bundle clock, no audio, the 4-slot fold, parts from sections/bars),
`test_detect_tones_success_populates_ranked_candidates` (the stored timeline),
`test_tone_suggestions_*` and `test_each_track_can_keep_its_own_tones`
(`test_api.py`), `test_a_track_with_its_own_tones_switches_alone`
(mutation-checked) and `test_each_tracks_own_tones_reach_the_build`; with
Playwright on the user's Ocean Eyes built as Lead + Rhythm: suggestions for
both, "Aplicar a todas" → per-track, switching tracks swaps base/changes, a
hand edit stays on its track, and a real rebuild wrote different tones into
`arrangement_lead.xml` and `arrangement_rhythm.xml`.

### Moving a tone change (the list's time, "= cursor", the drag)

"Já consigo ajustar o tempo em que entra um tom?" → "Com as três" (2026-10-19).
A change could only be placed on a note ("Mudança de tom") or removed. Now, in
"Tons de cada pista", each change has a seconds field and "= cursor"
(`setToneChangeTime`), and on the score each change's amber mark is a
`.tone-mark` group dragged sideways (`toneDrag`, auto-scroll counted; a press
without moving puts the cursor where it starts). All three work in the time the
change is SHOWN at — `toneChangeDisplay` (the chart time through the pending
tempo/anchors, as the score draws it) and `toneChangeChartTime` (back, by
`invertIncreasing`) — and the list is refreshed when the Tons page opens
(`showSection`), so a sync edit made on the score shows there. A moved change is
a NEW object (the stashed per-track set shares the objects with the globals);
the list render is guarded against re-entry (`renderingToneChanges`: replacing
a focused field fires its change again). Ordinary tone edits: undo/redo,
drafts, "Aplicar e reconstruir"; the writer still keeps a change off a note
(`_safe_tone_time`). Browser-only; verified with Playwright on an invented
project (typed 5.25 s → shown 0:05.3, "= cursor", a 1.5 s drag, Ctrl+Z / redo,
a real rebuild writing `<tone time="9.500">`, PT 1440 / EN 760 px, no page
errors). **It is sent where it is shown** (BUG-0338, `toneChangesShown` in
`toneSetsForRebuild`): the build keeps a tone change's time as given while the
notes move with the pending tempo/anchors, so a correction made in the same
rebuild left the change behind its note. Each chart's own set goes through
`chartDisplayTime` with that chart's map (the `fhpForRebuild` pattern), the
song's set — and every set under "Aplicar sync a todos" — through the chart on
screen's, rounded to the millisecond. Verified with Playwright and real
rebuilds: a +1 s correction moved the first note 2 → 3 s and the change 6 → 7 s
(written 6.980, `_safe_tone_time`), a Bass with no correction kept its 6.0 s.
Section markers had the same gap (BUG-0339, fixed the same way — see the
section editor).

### Tones from a pasted text (`infrastructure/tone_plan.py`, "Importar tons de um texto")

"receber informação escrita, por exemplo de um prompt colado do chatgpt, com os
tons usados na música e onde cada um começa … O programa iria implementar esta
informação" (2026-10-17). Phase 1 + option A of the plan in `tasks/todo.md`; the
option of asking an AI directly (option B, the user's own API key) is
DEFERRED at the user's request until this one has been used for a while.

- **The request** (`GET /jobs/{id}/tone-plan/prompt`, `build_prompt`): the song,
  each built chart by its game name with its bar count, the sections as
  `section_labels` writes them (a repeated name becomes "Verse #2") with their
  bar and RECORDING time (bundle − `_recording_pad`, the build's own pad, now
  shared with `/tone-suggestions`), the answer format with an example, the
  rules (keys from the list, knobs [min–max; default], volume 0.1-36 higher =
  louder, ≤ 4 tones per track, "all" = every guitar, the bass only when
  named, do not invent sources) and the game's gear (`gear_list`: amps,
  cabinet models + mics, pedals by family, racks, every knob; bass gear only
  when the song has a bass chart) — about 18 KB. The prose is in the user's
  language; the format and the gear stay English, since the answer must use
  them verbatim. "Copiar o pedido" puts it on the clipboard.
- **The answer** (`POST /jobs/{id}/tone-plan/preview`, `read_plan`, nothing
  stored): `extract_plan` finds the JSON in a ``` fence or in prose, forgives
  typographic quotes, `//`/`/* */` comments and trailing commas (string-aware,
  so a URL survives), and accepts PT key aliases (`tons`, `coluna`, `pista`,
  `em`…); a text without a `tones` object is a 422 pointing at the request —
  never guessed at. Gear (`match_gear`): exact by key, game name or the key
  without its prefix ("Marshall JCM800" = `Amp_MarshallJCM800`), else the
  closest (containment, then difflib ≥ 0.72, the chart's instrument first),
  said; an unknown amp drops the tone. A cabinet by full key or model + mic
  (default `57_Cone`); none given → `cabinet_for_amp` (the presets' pairing for
  that amp, else its family preferring a 1960a/4x12/1x12, else the presets'
  usual one), said. A pedal named under the wrong slot moves to pedals/racks;
  more than 4 per slot are cut, said. Knobs by name/key/close spelling,
  values as numbers, "70%" (of the range, unless the knob IS a %), "7/10" or an
  enum label; clamped to the range and snapped to the step, said; the rest at
  the catalogue default. Volume: positive = the DLC Builder scale (stored
  negated), negative = as stored, clamped to 0.1-36. Descriptors by name.
  Every tone is checked through `tone_from_dict` before it is returned.
- **When** (`parse_when`/`_resolve`): "start", "bar N"/"c. N"/"compasso N",
  `{"bar": N}`, a section label (a plain repeated name takes the first, said),
  "m:ss.s" or seconds of the RECORDING (+ pad); per chart, with that chart's
  own bar and section times. A change at or before the chart's first note is
  its start; a chart given no start plays its first tone from the start, said.
  Two changes at one moment keep the last; a change to the tone already playing
  is dropped. **At most four tones per chart**: the base and the three others
  that sound longest stay, changes to the rest are dropped (the tone before
  carries on), said. A chart the answer never names is not in `tracks` and
  keeps its tones; a tone no chart uses is still returned (added to the
  project), said.
- **UI** (Tons page, card `#tonePlanCard`, shown for a built GP project,
  ⓘ `tone-plan`): copy, paste (`#tonePlanText`), "Ler a resposta" → the tones
  as `toneCardHtml` cards with the assistant's description, each chart's
  changes in recording time, the adaptations (open), the sources as text;
  "Aplicar" (`applyTonePlan`) adds the tones to `jobTones` (the same tone
  reused, a different one under a taken key suffixed) and gives each named
  chart its set through `swapPlan` + `setTonesPerTrack`, like "Aplicar a esta
  pista" — so undo/redo, drafts and "Aplicar e reconstruir" carry it.
  **Drawn like the suggestions** ("ficava bom se depois de introduzir os tons,
  cria-se o gráfico como quando deteta os tons", 2026-10-18):
  `toneTimelineChart` draws, per chart, a strip of the tone sounding at each
  moment (from its first to its last beat, a part click seeks), the chart's
  sections under it, and — when `/tone-suggestions` carries a timeline — the
  recording's distortion above it (`gainBars`, the same bars "Sugestões por
  secção" draws, now one helper for both). Each tone keeps one colour on every
  chart (`toneColor`: its place in the plan, or in `jobTones` for the panel;
  eight hues checked for colour-blind separation on the dark surface, a ninth
  grey). Used in the preview and in "Tons de cada pista" (`#toneTimeline`,
  `renderToneTimeline`, the set on screen — so what was applied stays drawn,
  and hand-made changes are drawn too). Browser-only; verified with Playwright
  (PT 1440 / EN 760 px: segments and their times, the curve once a timeline
  exists, a click seeks, the panel after "Aplicar" and gone after Ctrl+Z, no
  horizontal scroll, no page errors).
  (The top bar's "Pendente" never listed tone edits — a hand-made one neither;
  left as it was.)

Honest limits, in the ⓘ and the card: the tones are the assistant's opinion,
not a measurement; the gear is the game's, which imitates the real thing; the
times are the last build's. Never tried against a real ChatGPT answer from
here (no network to it): the parsing is tested on invented answers shaped like
one. Guarded by `test_tone_plan.py` (the text's slips, refusal, gear by
key/name/real name/closest, every adaptation said, knob value forms, cabinets,
volume, bars/sections/times per chart, "all" without the bass, a late chart,
the four-tone limit, two changes at one moment, descriptions/sources/unused
tones, the request — the pad, the bass filter, the four-tone limit, the
same-moment rule, the late start, the volume clamp and the chosen cabinet each
mutation-checked) and
`test_a_tone_plan_pasted_as_text_becomes_tones_and_changes_without_storing_anything`;
with Playwright on a built project (PT 1440 px, EN 760 px): the request on the
clipboard, an empty and a non-plan paste refused, a pasted answer previewed,
applied (2 tones, base + 2 changes at bundle times) and undone with one Ctrl+Z,
no horizontal scroll, no page errors.

### Tone volume: MORE NEGATIVE IS LOUDER

"os tons detetados e aplicados estão a ficar com o som muito baixo, e quase não
se ouvem no rocksmith". A tone's `Volume` is a level in dB where **-20 is louder
than -13**: DLC Builder shows `-Volume` on a 0.1..36 slider with the loud icon
at 36 (`ToneDetails.fs`, `EditFunctions.SetVolume`), its own default tones sit
at -18.6/-19.5 and a new tone at -18 (`ToneGear.fs`, all Rocksmith2014.NET). The
curated presets shipped at -13..-16 — quieter than every reference — and the
UI's new-tone default was -15. Now: presets -19.5 (high gain) / -20 (crunch) /
-21 (clean), the default -18 everywhere (`domain/tone.py`, `gear_catalogue`),
and the tone editor's field works like DLC Builder's (0.1-36, higher = louder,
stored negated). `_backfill_preset_tones` (startup) moves a preset still
at the exact volume it first shipped with (`PRESET_VOLUMES_BEFORE`) to the new
one, in every project and the tone library — a volume the user changed is
left alone — so the next rebuild is audible without re-applying suggestions.
Also found on the way: the two Plexi presets set `Amp_MarshallPlexi_Gain`,
which that amp does not have (it has `Loudness1/2`), and `tone_from_dict` drops
an unknown knob without a word, so the setting never reached the tone.
Guarded by `test_presets_are_as_loud_as_the_games_own_tones`,
`test_every_preset_knob_is_a_real_knob_of_its_gear` and
`test_presets_still_at_their_first_quiet_volume_are_raised_on_startup`. Not
heard in game from here; the scale is the reference's, the exact loudness the
user's ears.

**Every preset with drive opens with a noise gate** (2026-10-01: "os tons
standard acho que estão com um volume bom, os detetados ainda ficam com um
pouco de ruído no final"). Gain amplifies whatever the player's guitar feeds
in when it is NOT playing — pickup hum, string noise — so the crunch and
high-gain presets (CA100 at 90-98 with a drive pedal stacked in front, HG100,
JCM800) left a hiss under the end of each note and after the last one; DLC
Builder's defaults (a Plexi with one drive pedal, an Orange AD50 at gain 25)
are tamer. The catalogue's own `Pedal_NoiseGate` (Threshold -90..-40 dB,
default -55) is now the FIRST pre-pedal of every preset whose fingerprint gain
is ≥ 0.35 — gating the input before the drive, where the game's own metal
tones put it: -55 (the game's default) for high gain, a gentler -65 for crunch
so a note's natural decay is not chopped; the clean presets have none.
`_refresh_presets` (the same startup pass as the volumes) adds it to a
project's or the library's copy only while that copy's pre-pedals are still
the ones the preset shipped with (`tone_presets.with_preset_gate`) — a chain
the user rebuilt, or a full one, is left alone. Guarded by
`test_every_preset_with_drive_opens_with_a_noise_gate`,
`test_a_projects_untouched_preset_gets_the_gate_but_a_rebuilt_chain_does_not`
and the gate assertions in
`test_presets_still_at_their_first_quiet_volume_are_raised_on_startup`
(mutation-checked). Not heard in game from here: the threshold is the game's
default, how much hiss the user's own guitar brings is their rig's.

**The Orange crunch was retuned, and earlier preset chains are upgraded**
(2026-10-01, two PSARCs from the user: September "com ruído", Jet Lag
"bastante bom"). Decoding both showed the SAME two presets in each
(`RFLead_Overdrive` + `RFRhythm_Orange`, gates already in) — the difference
is which one plays: Jet Lag's charts are on the Overdrive and never switch,
while September's Rhythm/Combo/alternates sit on `RFRhythm_Orange`, a
Rockerverb at gain 68 (its catalogue default is 88: a hot amp) with bass 74
and only the gentle crunch gate. It is now gain 55, bass 66 and the high-gain
gate (-55). `PRESET_CHAINS_BEFORE` lists the chains a preset shipped with
before; `upgrade_preset_chain` (run first in `_refresh_presets`, the startup
pass) moves a copy still EXACTLY on one of them — amp and pre-pedals compared
knob by knob with catalogue defaults filled in, so a copy the tone editor
filled in still matches — to the current chain, keeping its cabinet, post
pedals, racks, volume and name. Guarded by
`test_a_copy_still_on_an_earlier_version_of_a_preset_gets_the_current_chain`
and the Orange copy in
`test_presets_still_at_their_first_quiet_volume_are_raised_on_startup`
(mutation-checked). Not heard in game from here. The same PSARCs carry tone
CHANGES only where the plan put them: September's Lead (46.6/85/110.6/213 s)
and Lead alternate (155.4 s); its Rhythm, Combo and Rhythm alternate have one
tone and nothing to switch to, and Jet Lag none at all — the slot ids match
`Tone_A..D` (id 1 = `Tone_B`). No DLC Builder build with tone changes has been
decoded to compare against, so whether the game shows a switch on screen is
unverified.

**Heard in game, then tuned again** (2026-10-01: "realmente está a fazer as
trocas de tons. O tom de crunch encorpado está muito baixo, e mesmo assim está
com ruído (distorção em demasia). O overdrive está só um pouco baixo"). The
tone changes are confirmed working in game. `RFRhythm_Orange` is now gain 42,
bass 60 (a real crunch; fingerprint gain 0.58 → 0.50 to match) at volume
-23.5, and `RFLead_Overdrive` -21 (was -19.5). `PRESET_VOLUMES_BEFORE` maps
each preset to EVERY volume it shipped with (a tuple, oldest first), so a copy
untouched at -20/-19.5 follows too, and the gain-55 chain joins
`PRESET_CHAINS_BEFORE`. Everything stays editable per project in the tone
editor (Volume: higher = louder; the amp's Gain; the gate's Threshold — closer
to -40 cuts more). Guarded by the Overdrive copy and the third Orange chain in
`test_presets_still_at_their_first_quiet_volume_are_raised_on_startup` /
`test_a_copy_still_on_an_earlier_version_of_a_preset_gets_the_current_chain`.
The PSARC the user tested still had the gain-68 Orange (built before the first
retune); the new values are not heard in game from here.

**Rebuilt on two hand-made tones that sound clean** (2026-10-04: "o problema
continua a ser o hiss ou ruído. E os sons não são tão limpos, mesmo comparando
com originais, clean, distortion e overdrive"). The user sent two COMMUNITY
CDLC (Daughtry "Crazy" and "It's Not Over" — Custom Song Toolkit / CFSM builds,
not Ubisoft's, same appid as ours) whose tones they find clean; read with the
tone collection's own `read_entries`, they do four things our presets did not:
a **5-band EQ BEFORE the amp** cutting 63 Hz and 5.7 kHz (the rumble and the
hiss/fizz band — less of both for the amp to amplify), a **studio parametric
EQ after it** scooping the low-mids (240 Hz) and high-mids (~1 kHz), on the
cleans a **compressor**, a gentle EQ and a little **plate reverb**, and **no
drive pedal stacked into an amp already near full gain** (their high gain is an
HG-500 at 92 with only the EQ in front). None uses a noise gate; ours keep
theirs (harmless). Every preset now follows that, with the references' own
knob values (`_drive_eq`, `_drive_racks`, `_clean_comp`, `_clean_post`,
`_clean_racks`); the three high-gain presets lost their stacked drive (and 5-6
gain). Two inherited defaults were found on the way: **a knob a preset leaves
out takes the CATALOGUE default, and those are hot** — the Plexis' `Loudness2`
was never set and sat at 88, and the EQ5 defaults boost 750 Hz by 10 dB — so
every knob of the new pieces is written out and the Plexis set `Loudness2`.
Volumes unchanged. **Copies upgrade by their WHOLE chain now**:
`tone_preset_history.py` holds every earlier version verbatim (`V1` = all
presets until this change, `ORANGE_EARLY`), `PRESET_CHAINS_BEFORE` is built
from it (with and without the gate, only chains that differ from today's), and
`upgrade_preset_chain` compares amp + cabinet + pedals + racks (knobs filled
with catalogue defaults; a copy stored without a cabinet compares on the rest)
and replaces all five slots with deep copies — a copy the user changed
anywhere is left alone. **When a preset's chain changes, add its old version
to `tone_preset_history.py` verbatim first.** Guarded by
`test_a_copy_still_on_an_earlier_version_of_a_preset_gets_the_current_chain`
(every preset × every old chain × sparse/filled/no-cabinet),
`test_driven_presets_cut_the_hiss_band_before_the_amp_and_stack_no_drive` and
`test_presets_still_at_their_first_quiet_volume_are_raised_on_startup`. Two
songs by two authors are a small sample and none of it is heard in game from
here; the user's `tone_collection.json` (every tone of their library) would
let this be checked against many more.

### Tone editor: rotary knobs + optional local gear images

Gear knobs (amp/effect Gain/Bass/Mid/…) render as **draggable rotary dials**
(`renderKnobs`/`wireKnob`, `web/index.html`): drag the dial (−135°..+135° sweep),
type the exact value, or double-click to reset to the catalogue default. The
value still lives in an `input[data-knob]` so `readKnobs` and the tone model are
unchanged — purely a UX layer. Each amp/cabinet **and every effect (pre-pedal,
post-pedal, rack)** can also show a **gear picture**: `GET /gear-image/{key}`
serves `<key>.<ext>` looking first in `work_dir/gear_images/` (the RUNTIME
override — the user drops their own photos there, named by the gear key, without
committing) then the **bundled `web/gear_images/`** shipped in the repo
(`_gear_image_dirs`, resolved the same way `index()` finds the web UI), so a
fresh install has art out of the box and a user file of the same key still wins.
The key is sanitised to a bare slug against path traversal. RockForge ships its
own hand-drawn rack faces there (`Rack_StudioCompressor`, `Rack_StudioGraphicEQ`,
`Rack_StudioEQ`, `Rack_TapeEcho`, `Rack_StudioPlate`, `Rack_StudioChamber`) — the
repo art is the user's OWN (no brand/Ubisoft assets committed).

**Two layouts, chosen by whether a REAL picture loads (`applyGearImageEl`).** A
real photo (user or bundled) already has its own knobs drawn on it, so overlaying
functional knobs would double them; when the `<img>` `onload`s a real image the
panel gets `.gear-photo` and switches to a **stacked** layout — picture on top
(shown whole, full opacity) with the functional rotary knobs BELOW it. The
knob-less generic SVG faceplate (`genericGearSvg`: amp head / speaker cab /
stompbox — our own art) keeps the **overlay** layout (knobs `.knob-face` sit on
the `.gear-bg` backdrop), so the knobs shown are always exactly the gear's own
controls — however many (3, 5, 8…). Effects pass `photoOnly=true`: with no real
image they show NOTHING (not the generic pedal SVG, which HAS drawn knobs that
would clash) — just the plain gradient knob strip; a real rack photo switches
that row to the stacked layout. `renderKnobs` hides an empty container so a
knob-less gear shows no empty bar. Honesty unchanged: this is visual only —
RockForge does not model the amp sound (the real tone comes from the gear keys
in-game / DLC Builder). Guarded by `test_gear_image_serves_local_file_or_404` /
`test_gear_image_falls_back_to_bundled_and_workdir_wins`.

### Tone preview on the score (`voiceNote` / "Testar tom")

The **"Testar tom" selector** (in the transport's "Áudio ▾" panel) lets the user audition a **created
tone**'s *character* on the note playback — both the per-note tick and the
"sintetizada" audio source route through the same `voiceNote(ctx, dest, hz, t0,
dur, peak, char)` voice — a **plucked-string (Karplus-Strong) note**
(`karplusBuffer`) through an optional waveshaper (drive) and a **shared cabinet
EQ** (`getCabinet`: low-mid body bump + mid scoop + 4 kHz speaker roll-off, one
per audio context), a far more guitar-like simulation than the old oscillators.
The selector is **disabled until the user creates a tone** (nothing to preview). With tones, it offers **"Seguir partitura"**
(`'__follow__'`) — the character follows the tones marked on the score, switching
per note via `activeToneKeyAt(chartTime)` (the last `toneChanges` entry at/before
that time, else `toneBase`; both share the chart timeline) — plus each tone to
audition alone. `toneCharForNote(chartTime)` resolves the per-note character, so
a chart with several tone changes mirrors each of them. It defaults to following
the score when tones are marked, unless the user picks otherwise
(`previewToneTouched`).

**A held note sounds for its sustain** (Liam, 2026-10-16: "sustained notes …
just play as a single strum"). Both the tick and the synthesized source used a
fixed length (0.24 / 0.28 s) whatever the note, so a whole note was a pick.
Now each note lasts its sustain as drawn — through the same `previewScale` +
warp as its start, so a pending tempo/sync edit is heard — via
`noteSoundLength` (at least `NOTE_MIN_S` = 0.24 s, at most 6 s, rounded to
50 ms so held notes still share cached buffers), and `karplusDamping` picks the
per-period loss that leaves about a quarter of the level at the end (a fixed
0.99 silenced a high note within tenths of a second); a short note keeps
exactly the old 0.99 pick. The buffer cache is now also bounded by memory.
Browser-only, no pytest coverage: checked with Node (short notes unchanged,
held ones ringing to the end at three pitches) and with Playwright on a built
invented GP5 (a 2.35 s note still sounds at 1 s and 2 s in the synthesized
source; the tick receives its 2.35 s), no page errors.

**On-score tone identification.** The active tone is shown on the tab viewer: an
amber 🎸 label per tone change (plus the base tone at the start,
`activeToneKeyAtDisplay`) and a live `#liveTone` label next to the BPM
(`updateLiveTone`, called from `updateLiveBpm`). `toneCharacter` derives `drive`
from the descriptor category refined by the amp's actual **Gain knob**
(continuous blend) + drive pedals, and `bright` from the amp's **treble/bass/
presence** knobs — so two tones of the same category still differ *if their gear
differs*. Two tones with identical settings sound identical (correct, not a bug). With no tone selected (`previewToneKey === ''`) it's the
plain oscillator pluck (sawtooth+triangle → lowpass); with one, `char =
{drive, bright}` from `toneCharacter(tone)` inserts a **WaveShaper** (drive) and
shifts the lowpass cutoff (brightness), plus a little makeup gain (distortion
compresses level). `toneCharacter` derives `drive` from the tone's **descriptors**
(CLEAN/CRUNCH/OVERDRIVE/DISTORTION/HIGH GAIN), its amp **Gain knob**, and any
drive/dist/fuzz **pedals**; `bright` from LEAD/BASS. Both the live tick
(`playNote`) and the offline render (`synthesizeArrangement`) call `voiceNote`,
so a synth source re-renders when the preview tone changes. `populatePreviewTones`
(called from `renderTonePanel`) keeps the selector in sync with `jobTones`.

Honesty note (surfaced in the "Testar tom" ⓘ): RockForge does **not** model amps
— this is a **character approximation** (gain/distortion + brightness), NOT the
real amp/cabinet sound. The true tone only exists in-game / DLC Builder, which
generates the audio from the gear keys we serialize into the bundle.

### Stem separation — selectable audio source (`/jobs/{id}/separate-stems`)

The **"Fonte de áudio" selector** (in the transport's "Áudio ▾" panel, `populateAudioSources`) offers
three kinds of audio source, all decoded into the same `playBuffer` (which
shares the recording's clock, so the notes stay aligned):

1. **Mistura completa** — the original recording (`/source-audio`).
2. **`<Kind>` (sintetizada)** — a clean synthesized reference of ONE
   arrangement's notes, generated **in-browser** (`synthesizeArrangement`, an
   `OfflineAudioContext` render using the same oscillator voice as the per-note
   tick). No Demucs, always available. Each note is placed at the exact
   recording-clock position it's drawn at — `warp((t-scoreShift)*ratio+pad) -
   viewOrigin` for GP (parameterized by that arrangement's *own* pending
   `tempo_scale`/anchors from `tempoScaleByKind`/`syncAnchorsByKind`, so it's
   correct regardless of the open tab), raw `t` for audio-ML. It reflects the
   pending sync at selection time; re-pick to refresh after more edits. This is
   the honest answer to "isolate each guitar": the two guitars can't be split
   from the *recording*, but each arrangement's notes CAN be rendered alone.
   **Voz (sintetizada)** (`synth:Voz`, offered when `/vocal-line` has notes)
   plays the notes the GP lyrics are sung on, held for their length with a
   little vibrato, at the lyrics' own clock + `leadInBuilt` — so a word and
   its note sound together and the lyric sync can be checked by ear. Its
   samples are computed directly into an `AudioBuffer` (`synthesizeVoice`),
   NOT through audio nodes: 411 scheduled oscillators took 5-20 s to render
   here (even bare ones, ~3 s), long enough that picking the source looked
   broken; the direct loop takes ~0.4 s. It is the vocal line as of the last
   build (it follows committed sync, not pending edits). A PDF→GP converter
   may write every note on one pitch (the user's file does), so it can be a
   rhythm on one note — it plays what the file says.
3. **Separated stems** — `POST /jobs/{id}/separate-stems` runs ONE Demucs
   `htdemucs_6s` pass and keeps the stems it produces (`separate_stems` globs
   the output dir), **minus `drums`** (dropped in the task — noise for
   sync-checking a guitar part), storing `params["stems"] = {name: abs_path}`.
   Same async pattern as `detect_tones`: progress in `params["stems_status"]`
   (`detecting`/`normalizing`/`separating`/`ready`/`unavailable`) +
   `params["stems_log"]`, endpoint mutates the job → 202, heavy failure wrapped
   → `unavailable`. `GET /jobs/{id}/stems` returns the status + the names whose
   file still exists on disk; `GET /jobs/{id}/stem/{name}` serves the WAV.

**`detect_tones` and `separate_stems` (demucs backend) share one guitar-stem
cache.** Both run the exact same `htdemucs_6s` pass over the same normalized
recording, so running one after the other used to pay for Demucs twice —
several redundant minutes. `celery_app._demucs_stems_cache_dir(job_id)` points
both tasks' normalization output and `DemucsSeparator` workdir at the same
`work_dir/<job_id>/demucs_stems`, and `DemucsSeparator.separate_guitar` checks
for an existing `guitar.wav` before invoking the subprocess (htdemucs_6s writes
every source in one pass, so its presence means a full separation already ran)
— whichever task runs second reuses it instantly instead of recomputing.
`has_cached_guitar_stem` lets each task log "reusing an already-separated
guitar stem" instead of the normal "separating…" message when this happens.
Banquet (`separate_stems`' experimental backend) keeps its own `stem_separation`
workdir — its query-based, per-clip output isn't compatible with the shared
htdemucs_6s cache. Guarded by
`test_separate_guitar_reuses_an_existing_stem_without_rerunning` /
`test_separate_stems_reuses_a_guitar_stem_from_a_prior_separate_guitar_call`.

`decodeWaveform` branches on `audioSourceName`: `synth:<kind>` → synthesize,
else fetch `/stem/{name}` or `/source-audio`. Changing the dropdown re-decodes
and restores the playhead; `loadStems` repopulates the selector on reopen (synth
options always; stems if already computed) without re-running Demucs.

**`initSync` resets `audioSourceName` SYNCHRONOUSLY, before firing
`decodeWaveform`/`loadStems`.** Both are async and neither is awaited, so they
run concurrently; `loadStems` also resets `audioSourceName` to `''` once its
own fetch resolves. Without the synchronous reset, a stale `audioSourceName`
left over from a *previous* job (e.g. `"synth:Lead"`, still set from before
the user switched jobs) could still be in effect when `decodeWaveform` reads
it, decoding a synthesized buffer into `playBuffer`; `loadStems` then resets
the dropdown back to "Mistura completa" *without re-decoding*, leaving the
synth buffer silently playing under a selector that reads the full mix — the
"dá música sintetizada mas a seleção está em mistura" bug. `initSync` now
sets `audioSourceName = ''` and the `#audioSource` select's value before
either async call starts, closing the race regardless of which one resolves
first.

Honest limit (surfaced in the "Fonte de áudio" ⓘ and the done log): Demucs
separates by **instrument type**, not by individual track — the `guitar` stem is
ALL guitars mixed together; **Lead vs Rhythm cannot be split** from the
recording (the per-arrangement *synthesized* source is the workaround). Stem
separation needs the `[ml]` extra (Demucs) and takes minutes; the synthesized
source needs neither.

**Selectable separator backend (`ROCKFORGE_STEM_SEPARATOR`).** The `separate_stems`
task picks its adapter via `celery_app._build_stem_separator()`: `"demucs"`
(default, `htdemucs_6s`) or `"banquet"` (EXPERIMENTAL / IN TESTING —
`BanquetSeparator`, `infrastructure/separation/banquet_adapter.py`). Banquet
(query-bandit, MIT, MoisesDB-trained) is **query-based**: it shells out to the
repo's `train.py inference_byoq` once per `<class>.wav` reference clip in
`ROCKFORGE_BANQUET_QUERIES`, producing one finer stem per clip (electric vs
acoustic, clean vs distorted) — needs `ROCKFORGE_BANQUET_REPO`/`_CKPT`/`_QUERIES`
set (see TESTING.md §7g). Same fundamental limit holds: two guitars of the SAME
class stay inseparable. Command-construction is unit-tested
(`test_banquet_adapter.py`); the model never runs in CI.

**In-app settings (`runtime_settings.py` + `/settings`).** The separator backend
and Banquet paths are editable from the web UI's **"⚙️ Definições"** modal, not
only via env vars. `runtime_settings` persists them to `work_dir/settings.json`
(atomic write) and both the API and the Celery worker read it — an override wins
over the env `Settings`, empty string clears it back to the env default. `GET
/settings` returns the effective values plus per-path readiness (`banquet_validation`:
`repo_ok`/`ckpt_ok`/`queries_ok`/`query_names`/`ready`) so the modal shows ✓/✗;
`POST /settings` saves. `_build_stem_separator()` reads `runtime_settings`, so a
change takes effect on the next `separate_stems` run with no restart. Guarded by
`test_settings.py`.

### Tone library (`tone_library.py` + `/tone-library`)

A tone dialled in one project's tone editor can be saved to a **cross-project
library** and reloaded into any other song, so an amp/cabinet/pedal chain isn't
rebuilt per file (like DLC Builder's tone library). Persistence mirrors
`runtime_settings`: a shared `work_dir/tone_library.json` (a list of the same
tone dicts `Job.params["tones"]` holds), atomic writes. `GET /tone-library`
lists; `POST /tone-library` upserts one tone **by its key** (validated to carry a
real amp+cabinet via `tone_from_dict`, else 422); `DELETE /tone-library/{key}`
removes. The tone builder's "Biblioteca" block loads (⬇) / deletes (🗑) and
"★ Biblioteca" saves the tone in edit. **Loading copies into the project**
(suffixing a clashing key) so it's editable locally and never clobbers the
library original, and the project's own tone edits never write back to the
library unless explicitly saved. Guarded by `test_tone_library.py`.

### The tones of the player's own songs (`tone_collection.py` + `/tone-collection`)

"O DLC Builder tem uma função muito interessante, que faz scan à minha
diretoria dlc do rocksmith e cria uma lista dos tons de todas as músicas.
Implementa." Every song's per-arrangement manifest inside its `.psarc`
(`manifests/<…>/<key>_<arr>.json`) carries its `Tones` as `ToneDto`s — the
shape `tone_dto.py` writes — so the tone collection is: read those manifests
from every `.psarc` under the folder (recursive; official DLC, CDLC, and the
on-disc `songs.psarc` when the GAME folder is given), turn each `ToneDto` back
into the editor's tone dict (`tone_from_dto`: `Key` or older tools'
`PedalKey`, `Volume` string or number, a pedal kept in its slot, and a tone
whose amp/cabinet the catalogue does not know dropped and counted), and list
them by song, artist, arrangements and gear, searchable (case/accent-blind, every
word). **And by artist** ("possibilidade de pesquisar por artista"): an artist
picker (`#tcArtist`, every artist of the whole collection with its tone count —
`tone_collection.artists`, spellings that differ only in case/accents/edge
spaces are one artist under its most common spelling) and `?artist=` on
`/tone-collection`, which matches the WHOLE name ("AC" is not AC/DC) and
combines with the words; the artist on a card is a link that picks it. "Usar neste projeto" copies one into the project (`addToneToProject`,
shared with the library's ⬇, so a clashing key is suffixed), ★ saves it to the
library.

**Only the manifests are read, never the audio** —
`container.read_entries(path, wanted)` reads the header, the TOC, the name
block and the wanted entries' blocks by seeking (an official `songs.psarc` is
hundreds of MB); it sizes the block table from the TOC length, as retail
archives require. It equals `unpack` on everything (tested). The archives are
only ever opened for reading. The result is cached in
`work_dir/tone_collection.json` by relative path + size + mtime (written every
25 files too, so a cut-short scan keeps its work): a rescan opens only new or
changed files, drops the ones that are gone, and a different folder starts from
nothing. A Mac copy (`_m.psarc`) beside its PC copy (`_p`) is skipped. The scan
is plain file I/O on a background thread in the API process
(`tone_collection.start_scan`, one at a time — 409 otherwise), polled through
`GET /tone-collection` (`status`: scanning/done/error, done/total/current);
the folder is remembered (`runtime_settings` `rocksmith_dlc_dir`) and Steam's
default location is suggested when it exists (`suggested_folder`: the game
folder set in Definições first, then every Steam library). The list is
paged (`limit` ≤ 500, the UI shows 200 and says to type more), rows are light
(names via `gear_catalogue.gear_name`), and `GET /tone-collection/tone?id=`
hands one out whole (id = sha1 of path + key). Needs `[psarc]` (the TOC is
AES-encrypted); without it the scan ends in a clear error. UI: the tone
builder's "Tons das tuas músicas" block → `#toneCollOverlay`. Guarded by
`test_tone_collection.py` (each piece mutation-checked: PedalKey, the
size/mtime reuse, merging arrangements, the catalogue check, the block table;
`test_the_collection_can_be_narrowed_to_one_artist`)
and `test_the_tones_of_the_songs_in_the_dlc_folder_are_listed_and_handed_out`;
the modal with Playwright on two encrypted archives (scan, list, search, use,
★, PT/EN, no page errors). **Never run against a real dlc folder from here** —
the archives in the tests are packed by `pack_entries` with retail-shaped
manifests (TESTING.md §7d-quater-bis).

### DLC Builder project file (`rockforge.rs2dlc`)

`rockforge_project.json` is RockForge's *own* descriptor — DLC Builder can't
open it, so without help the user must recreate a project and "Add Arrangement"
each XML by hand. `infrastructure/packaging/rs2dlc.py` additionally emits the
**real** DLC Builder project format (`rockforge.rs2dlc`) so the whole song
(every instrumental, the vocals, audio and cover) loads in one "Open project".
Both `DlcBuilderPackager` and `NativePsarcPacker` write it.

The format is the `DLCProject.Dto` from Rocksmith2014.NET, serialized the way
DLC Builder does (System.Text.Json + FSharp.SystemTextJson defaults): arrangements
are an adjacent-tag discriminated union
(`{"Case":"Instrumental"|"Vocals"|"Showlights","Fields":[{…}]}`), `null` members
are omitted, `SortableString` is `{"Value","SortValue"}`, `AudioFile` is
`{"Path","Volume"}`. `ArrangementName`/`RouteMask` per kind: Lead→0/1, Combo
(our COMBINED)→1/1, Rhythm→2/2 (from `Arrangement.fs`). `Tuning` is the six
semitone offsets (`Tuning.offsets_from_standard`), `TuningPitch` from
`cent_offset`. `ID`==`PersistentID` (one GUID), `MasterID` random positive int —
matching a real captured `.rs2dlc`.

**Alternate arrangements.** `ArrangementKind` also has `ALTERNATE_LEAD` /
`ALTERNATE_RHYTHM` — a SECOND Lead/Rhythm chart (from another GP track) the
player can pick in game. They `.base_kind` onto Lead/Rhythm for every format
detail (ArrangementName, RouteMask, ArrangementType, path flags, `<arrangement>`
tag) but are **non-representative**: `Representative=0`, `represent=0`,
`bonusArr=1`, a distinct persistent/master ID, a `lead2`/`rhythm2` asset stem,
and a unique xblock entity name (`…_Lead2`) while the manifest `FullName` stays
`…_Lead`. This is byte-for-byte how a decoded DLC Builder CDLC (Animals As
Leaders "Tempting Time") encodes its `lead`+`lead2`. Selected via
`GpJobSpec.alt_lead_track`/`alt_rhythm_track` (the "Pista Lead/Rhythm
alternativo" selectors); the `.rs2dlc` marks them `Priority=Bonus` (2).

RockForge now has a full tone-gear model (`domain/tone.py`, backed by the
vendored Rocksmith gear catalogue) — custom tones with real amp/cabinet/pedal
definitions are serialized into the `.rs2dlc`'s `Tones` array and flow through
to the PSARC. When no tones are defined, `Tones` stays empty and DLC Builder
flags a "tone missing" issue the user resolves with its tone library. `Volume`
uses a neutral default (DLC Builder's "Calculate Volumes" recomputes it) and the
audio preview is left empty (its "Create Preview Audio" generates it).

### SNG binary compilation (`infrastructure/packaging/psarc/sng.py`)

`sng.py` is the entry point everything calls (`sng.from_arrangement`,
`sng.write_sng`…); the code is in `sng_model.py` (the records, mask bits and
shared limits), `sng_build.py` (`from_arrangement`/`from_vocals` and every
`_build_*` stage) and `sng_io.py` (`write_sng`/`read_sng`). A pure move,
checked byte for byte: 258 SNGs (fuzzed charts with and without DD, real
charts, vocals) hash the same before and after. Keep calling through `sng.`:
tests replace `sng.from_arrangement`, and the packer and manifest reach it there.

`NativePsarcPacker` compiles each `Arrangement` into a Rocksmith Sng2014 binary
payload via `sng.from_arrangement` + `sng.write_sng`. The binary layout
(section ordering, field sizes, struct formats) matches the real Sng2014 format
as ported from the Rocksmith2014.NET / DLC Builder source (MIT). `read_sng`
round-trips the payload for test verification.

Sections emitted (in order): BPMs, Phrases, ChordTemplates (with per-string MIDI
notes), ChordNotes, Vocals (+ symbol stubs if present), PhraseIterations, 3 ×
empty (PhraseExtraInfo/NLD/Actions), **Events** (the stage/crowd cues — see
finding D in the DD section), 2 × empty (Tones/DNAs), Sections,
ArrangementLevels (anchors, **anchor extensions**, notes with NextIter/PrevIter
linkage), Metadata. `NoteMask` values are the real Rocksmith constants (ported
from Constants.cs).

**`from_arrangement` is an orchestrator over named stage helpers, not one
452-line function.** Each `# --- Section ---` block from the original single
function is its own module-level `_build_*` helper — `_build_beats`/
`_assign_beat_phrase_iterations`, `_prepare_sections`, `_link_phrases`,
`_build_chord_data`, `_build_sng_notes`, `_build_sng_sections`,
`_build_difficulty_levels`, `_build_sng_metadata` — called in sequence,
threading the same intermediate values (beats, phrase_iterations, sng_notes,
…) that the inline code used to share as locals. Pure extract-function: no
logic changed, verified by the full existing `test_psarc_sng.py` suite passing
unchanged plus two new tests exercising `_build_chord_data`/`_build_sng_notes`
directly (`test_build_chord_data_is_independently_callable`,
`test_build_sng_notes_is_independently_callable`) — each confirmed to fail
with the reverted logic before restoring it. Keep new stages as separate
`_build_*` helpers rather than growing `from_arrangement` itself; the binary
layout is delicate enough (see the crash-history notes throughout this
section) that a stage should stay independently readable and testable.

**`CapoFret` is 255 when there is no capo, NOT 0.** Same sentinel pattern as the
two below — 0 is a real value (a capo AT fret 0) where the format wants
"absent". Found by byte-diffing a DLC Builder build of the same song. Unlike the
two below, the in-game consequence is UNPROVEN: it was fixed because the value
was plainly wrong and the pattern identical, not because a symptom was traced
to it.

**A chord template's unused strings carry MIDI note -1, NOT 0.** The per-string
`Notes` of a template are dereferenced by the game's note-detection/scoring
path, so writing 0 (a real, absurdly low pitch on a string that shouldn't
sound) crashed the game at the entry of a gapped 5/7 octave — but ONLY while
the player was actually playing/scoring that chord; a hands-off run never
touched the field, which made the crash look intermittent ("fragile"). Isolated
by byte-diffing our native "Free" against a DLC Builder build of the same song:
its 5/7 octave template is `[-1, 50, -1, 62, -1, -1]` where ours was
`[0, 50, 0, 62, 0, 0]` — the only difference on that chord. Guarded by
`test_chord_template_notes_are_real_midi`.

**Chords carry fingers, a name and a hand shape — what makes the game draw the
finger positions** (2026-10-04: "nas músicas originais do rocksmith, mostra a
posição dos dedos e acho que nas nossas não mostra"). Every chord template went
out with fingers -1 and an empty name, and no hand shapes (fingerprints) at
all, so the game had nothing to draw. Two community CDLC the user sent
(Daughtry "Crazy"/"It's Not Over", CSC builds) decoded: every chord template
fingered and named, and EVERY chord inside a hand shape (5293 of them over
both songs' levels; single notes never start one). Now:
- **Fingers** (`domain/chords.py` `chord_display` → `group_fingering`): the
  Guitar Pro file's own left-hand fingering when it fingers every fretted note,
  else `chord_fingering` — a part of an open chord (E, Am, A, C, G; two
  fretted notes at least) as in that chord, a root-less power chord 2-3, else
  finger 1 on the lowest fret, a barre only where one is needed (more than
  four fretted notes, or the top strings all on that fret), the rest by fret
  then string, never a fifth finger (left unfingered instead). 79 of the 100
  fully fingered shapes in those two CDLC come out identical; the rest are
  single notes of an open chord and wide stretches where hand-made charts
  disagree among themselves. **Name** = `name_chord` of the sounding pitches
  ("" when it has none). Both in the SNG template and the XML's
  `chordName`/`displayName`/`finger0..5`.
- **Hand shapes** (`hand_shape_spans`, shared by `sng._build_fingerprints` and
  the XML writer, so the two cannot disagree): one per run of consecutive
  identical chords (any other note, or more than `HAND_SHAPE_BREAK_S` = 1 s of
  rest, starts a new one), from the first chord to 1 ms past the last one's
  sustain (the references' shape), never past the next note. In the SNG they
  are built PER LEVEL from that level's own notes (like the anchors), each
  chord's `fingerprint_id` = its shape's index (`findFingerPrintId`), and
  `FirstNoteTime`/`LastNoteTime` follow DLC Builder's `convertHandshape`
  (last note + sustain, -1 when that reaches the end). The XML carries them as
  `<handShape chordId startTime endTime>` for DLC Builder (its DD keeps them
  where their notes are). Arpeggio shapes (`Fingerprints2`) are the next
  section's.
- **Phrases avoid them**: DLC Builder's `findGoodPhraseTime` moves a phrase out
  of a hand shape as well as a sustain, so our port (`_good_phrase_time`, over
  `_chart_hand_shapes`) does too — the native phrases stay exactly those of its
  build of our XML.

**History, so the risk is clear:** hand shapes were removed once, after a
one-per-chord emission "crashed the game at the entry of a dense 5-7 octave
riff". That crash was later traced to the chord templates' unused strings
carrying MIDI 0 instead of -1 (the paragraph above — the same riff), fixed
since; no working reference ever lacked hand shapes once fingered charts were
compared (the "zero fingerprints" references were DLC Builder builds of OUR
XML, which had none to convert). **The fingers SHOW in game (confirmed by the
user, 2026-10-05)**; whether any chord passage crashes is being tested now — if
one does, this is the first suspect. `tests/test_hand_shape_fuzz.py` builds 150
random charts (chords, single notes, slides, long sustains, rests) with and
without DD and checks every level, before and after a write/read: each shape
points at a real template, covers notes of ITS level only of its own chord,
never overlaps the next, its first/last note times follow `convertHandshape`,
every chord is inside one and no single note is, and each note's
`fingerprint_id` is what `findFingerPrintId` finds; the XML's shapes equal the
native full-chart level's. It found one real slip: a last chord whose sustain
ends exactly at the next note gave `LastNoteTime` == the shape's end once
written as float32 (DLC Builder, in whole ms, writes -1 there) — now compared
at millisecond resolution. 4000 more seeds run by hand: 0 failures over 33 159
levels and 492 362 shapes. Guarded by
`test_chords_produce_templates_with_fingers_and_a_hand_shape`,
`test_dd_levels_have_their_own_hand_shapes_and_slide_extensions`,
`test_a_phrase_is_not_cut_through_a_hand_shape` (both mutation-checked),
`test_chords_carry_fingers_a_name_and_a_hand_shape` (XML) and the fingering /
span tests in `test_chords.py`.

**Linked notes and arpeggios** (2026-10-14, "avança com as notas ligadas e os
arpejos" — the two Rocksmith techniques the Ubisoft Workshop pages describe
that RockForge did not produce). Both follow Rocksmith2014.NET's conversion
(XmlToSngNote/XmlToSngLevel/XmlToSng/PhraseGenerator, checker rules from
InstrumentalChecker); neither has been byte-diffed against a DLC Builder
build that contains them, nor played in game.
- **Linked notes (`TabNote.link_next`)** come from a Guitar Pro **legato slide**
  (GP5 `SlideType.legatoSlideTo` = 2, GPIF `<Slide><Flags>` bit 2, also on a
  slide carried by a tie — both parsers); a shift slide stays a re-picked
  note. `music.resolve_links` (run in `gp_pipeline` on every parsed track,
  before building) keeps a link only where DLC Builder's checker would: the
  next note on that string is a SINGLE note starting within
  `LINK_TOLERANCE_S` (5 ms) of the end, on the note's fret or its slide's
  landing fret, with a bend that carries on and no unpitched slide — then
  snaps the sustain to end exactly on it; otherwise the flag is cleared.
  `apply_sustain_gap` leaves a linked note alone. XML: `linkNext="1"` on the
  note / chordNote / chord, the sustain written as the difference of the two
  ROUNDED times (DLC Builder links within 2 ms of the end), read back by
  `reader.py`. SNG: Parent on the note (a chord: on the chord and per string
  in its ChordNotes), Child + `ParentPrevNote` = the parent's index IN THAT
  LEVEL on the next single note of the string (`_link_pairs`: a pending
  parent per string, taken — or dropped — by the next single note; chords
  never take one); a DD level shows a linked pair together or not at all
  (`_with_partners`); `_phrase_signature` includes the flag; the phrase
  generator keeps a phrase off the note a link runs into (findGoodPhraseTime's
  linkNext rule: earlier → the parent's time, later → that note's end, or
  +100 ms without sustain). The GP5 export writes a linked slide back as a
  legato slide. A held link on the same fret (no slide) has no Guitar Pro
  source today (a GP tie is folded into one note), so it only arises from a
  built XML.
- **Arpeggios** are DERIVED (`chords.arpeggio_spans`): Guitar Pro's "arpeggio"
  is a strum of one chord, not this. A run of ≥ `ARPEGGIO_MIN_NOTES` (3)
  single notes, each LET_RING, on as many distinct strings, one fret per
  string, fretted span ≤ `ARPEGGIO_MAX_FRET_SPAN` (3, four frets), no slide,
  no rest over `HAND_SHAPE_BREAK_S`; a chord or a note breaking any of these
  ends it. The shape ends like a hand shape (last note's end + 1 ms, never past
  the next note). XML: an extra chord template per shape, `displayName` =
  name + "-arp" (what makes DLC Builder's `ChordTemplate.IsArpeggio` true),
  after the chords' templates, and a `<handShape>` over it in the same list.
  SNG (`_arpeggio_templates`, `_build_arpeggio_prints`): templates with
  `CHORD_MASK_ARPEGGIO` (1), one Fingerprints2 entry per shape still holding a
  note at that level (from its first note there), each note inside with
  `fingerprint_id[1]` = the shape and `NOTE_MASK_ARPEGGIO`. **The hand window
  never moves inside one** (`_hold_through_arpeggios` in the SNG, the merged
  anchor groups in the writer): an arpeggio's positions count as one, from
  the arpeggio's start — open strings that begin it place no anchor of their
  own, which otherwise delayed the move into the middle of it (DLC Builder
  flags AnchorInsideHandShape). Phrases avoid arpeggios like any hand shape
  (`_chart_hand_shapes`). The one exception left: DLC Builder's END phrase,
  placed by its own rule near the song's end, can land inside one — as for
  chord shapes.
- **Viewer/API**: `ArrangementNoteOut.link_next` (an arc over the held time)
  and `ArrangementOut.arpeggios` `{start, end, name}` (a bracket "arpejo C" in
  the chord-name row — chords end an arpeggio, so the two never share it).
- **Checker** (`verify.py`): `_check_links` (a Child points back at an earlier
  Parent on its string whose end it starts at, every Parent hands on to a Child
  at its level, no stray ParentPrevNote, no phrase starting on a Child) and
  `_check_shapes`, the hand-shape rules written once for both Fingerprints1
  and Fingerprints2 (an arpeggio shape on an Arpeggio template over single
  notes, its notes carrying the mask exactly when inside). The random-chart
  fuzz plays held/slid links from notes and chords and arpeggios, and each
  piece was mutation-checked there or in `test_linked_notes.py` /
  `test_arpeggios.py`. A real build of an invented GP5 (a legato slide, a C
  arpeggio let ring) went through `/gp/inspect` → `/jobs/gp` → a clean
  `/psarc-check`, the packed SNG carrying Parent/Child (ParentPrevNote → the
  right index) and the "C" arpeggio template + Fingerprints2, and the score
  drew both (Playwright, PT/EN, no page errors).

**Repeated chords are marked HIGH DENSITY (condensed rendering).** A fast
repeated identical chord — an 8th-note power-chord chug, say — must carry
`NOTE_MASK_HIGHDENSITY` on every hit AFTER the first, so the game draws it
condensed (a small strum marker) instead of a full chord box. Emitting them all
as full boxes (the old behaviour: the constant was defined but never applied)
stacks the sprites into a **corrupt lateral highway blur** on a dense chug — a
graphical glitch, NOT a sustain trail (which is longitudinal). The DLC Builder
path never showed it because its DDC pass recomputes high density; only the
native SNG (no DDC) was affected. `high_density_flags` (pure, in
`domain/music.py`) marks a chord high-density when it repeats the previous
chord's exact shape within `HIGH_DENSITY_MAX_GAP_S` (0.35 s) — the first hit of a
run stays low density so its shape is still shown, and a shape change or a wider
gap starts a fresh run. Applied in BOTH the native SNG (`sng.from_arrangement`)
and the XML writer (`writer.py`, `highDensity="1"`; DDC overrides it there but
the two paths stay consistent). Guarded by
`test_repeated_chords_marked_high_density_but_not_the_first` (SNG) /
`test_repeated_chords_get_high_density` (XML).

**Every SUSTAINED chord gets a ChordNotes entry, not just technique chords.**
A chord's per-string SUSTAIN lives in its ChordNotes entry, NOT in the chord
template (which only carries frets/fingers/MIDI). Emitting ChordNotes only for
chords with a bend/slide/vibrato/palm-mute technique (the old rule) left a
plain sustained power-chord chug with `chord_notes_id = -1`, so the game had no
per-string sustain to render and drew **corrupt vertical/lateral bars** on the
highway — visible only while streaming notes in Riff Repeater / when scrubbing
the position (the two guitars' Lead single-notes were fine; only the Rhythm
chords glitched). Byte-diffing a DLC Builder build of the same song is
conclusive: every one of its ChordNotes entries carries the per-string SUSTAIN
bit (`0x2000`), and several carry ONLY sustain (no technique) — DLC Builder
emits one for every sustained chord. `from_arrangement` now emits a ChordNotes
entry whenever any string sustains OR carries a technique; `_note_mask` already
yields `SUSTAIN|OPEN|PALMMUTE` per string, reproducing DLC Builder's
`0x2000/0x2004/0x2040/0x2044` masks exactly. Found by decrypting a real user
PSARC (AES-CFB TOC + AES-CTR SNG via `pycryptodome`) and comparing the
ChordNotes section directly. **Confirmed fixed in-game** — the corrupt bars are
gone on the native PSARC. Guarded by
`test_sustained_chord_gets_chord_notes_with_per_string_sustain`.

**...and so does every chord with an OPEN string, sustained or not**
(2026-10-17, "as notas estão pintadas de cima a baixo": a user's screenshot of
"Behind", Kills Birds — drop C, its C5 is 0-0-0). The rule above was "a
sustain or a technique", which held while every chord had a sustain; once
`drop_short_sustains` gave short chords sustain 0, an open-string chord with no
technique went out with `chord_notes_id = -1` (2312 such chords in that song)
and the game painted it solid from the top string to the bottom — the same
family of glitch. DLC Builder's own rule (`XmlToSngNote.createChordNotes`) is
an entry unless EVERY string's mask is empty, and an open string always carries
`NoteMask.Open`; `_build_chord_data` now builds the masks first and skips only
an all-zero set. `check_sng` flags `open_chord_without_chord_notes`, so a PSARC
built before this shows the fault in "Verificar PSARC". Guarded by
`test_an_open_string_chord_without_sustain_still_gets_its_chord_notes`
(mutation-checked) and the planted fault in `test_psarc_verify.py`; the user's
file rebuilt with every open chord carrying its entry and a clean
`/psarc-check`. Not seen in game from here.

> **Debugging method that cracked this (reusable).** Several native-SNG highway
> glitches were mis-diagnosed by reasoning about our data alone (a symptom that
> *changes as you scrub the score in Riff Repeater, at a fixed DD level*, is the
> game misreading per-note geometry it streams — not a Dynamic Difficulty
> problem). What actually isolated it: get BOTH a native RockForge `.psarc` AND a
> DLC Builder rebuild of the SAME song from the user, **decrypt each** (PSARC TOC
> = AES-256-CFB, SNG payload = AES-256-CTR of a zlib blob — `pycryptodome` works
> in-sandbox where the `cryptography` pyo3 wheel panics), and **byte-diff the SNG
> section counts + struct fields**. The DLC Builder build is the ground truth; the
> first field that differs is the bug. Here it was ChordNotes (9 vs 3 entries).
> Reach for this before speculating whenever a native-only rendering glitch
> resists static analysis.

**A chart that rests through the first sections keeps them in order.** The
COUNT bracket used to move the FIRST section to the chart's first note — right
for a count-in inside the intro, wrong for a rhythm that enters at the chorus:
"Intro" landed after "Verse 1", the section list ran backwards (Intro at 104 s
with phrase range 15→0) and the game froze on the highway ("está a bloquear …
é mais que uma pista": September's Rhythm, Alternate Lead and Alternate Rhythm;
only the Lead, which plays from the intro, was spared). `_prepare_sections` now
splits the first section only when the first note falls INSIDE it; otherwise
that empty section simply becomes the COUNT. Symmetrically, a chart that stops
before the last section turns that empty last section into the END (an END
appended after it could never be in order, so such charts shipped with no END
phrase at all). The XML path (DLC Builder) never had this — its phrases are
COUNT/default/END independent of the sections. Guarded by
`test_a_track_that_enters_late_keeps_its_sections_in_order` (fails on the old
code); the user's September rebuilt with all four charts in order, each ending
in END. Not played in game from here. A last note that ends AT the last
section's start (September's rhythms: 3 µs past it, float noise) counts as
ending before it (`_END_TOUCH_S`, 50 ms) — otherwise END went 0.1 s later and
left a 0.1 s note-less "Outro" phrase. Guarded by
`test_a_last_note_ending_at_the_last_sections_start_leaves_no_sliver_phrase`.

**A note's anchor is the one of ITS level, not the full chart's.** Each DD
level's anchors are rebuilt from that level's own notes (`_build_level`), but
every note kept the `anchor_fret`/`anchor_width` of the FULL chart's anchor
(`_build_sng_notes._find_anchor`). They agree while a level holds the notes
that set the window; once a phrase drops out, the level can be framed
differently — September's Alternate Rhythm was fret 2 from level 17 up while
its notes all said fret 1 — and the game crashed (0xc0000005) the moment the
difficulty was raised in Riff Repeater ("a dificuldade estava a zero e eu só
tentei aumentar, e crashou logo"); the Lead had the same mismatch in the
phrases the user reported. `_build_level` now re-points every note at the
anchor of its level that it falls in, as DLC Builder's XmlToSngNote does
(`findAnchor timeCode level.Anchors`). The anchors' own
`first_note_time`/`last_note_time` were also carried from the unsplit greedy
window into every per-phrase piece (a 13.2–18 s piece claiming a last note at
102.8 s, some with first > last); `_anchor_note_times` now computes them over
the notes inside each anchor, last note's sustain included unless it slides,
and DLC Builder's uninitialised pair (`ANCHOR_NO_NOTE_FIRST/LAST`) for an
anchor with none — XmlToSng.fs `convertAnchor`. Guarded by
`test_a_notes_anchor_is_the_one_of_its_own_level` (fails on the old code); the
user's September rebuilt with zero mismatches on all four charts. Not played in
game from here — and the user's next test STILL crashed, so it was not (only)
this; the byte-diff against DLC Builder's own September build below came next.

**Byte-diffing DLC Builder's September (2026-09-30) — what it never does and we
did.** The user sent both `.psarc`s of the same song; with the
`XmlToSng.fs`/`XmlToSngNote.fs` source beside them:
- **A phrase with notes always has levels to climb.** Every phrase with notes
  there has a ceiling of 3 or more — its one-note phrase gets SIX identical
  levels. Ours bounded the `_DD_MIN_LEVELS` floor by `busiest - 1`, so a
  one-note phrase got ceiling 0: a phrase with a note and no level. That is
  exactly the crashes' shape — the Lead's "5th rectangle, small, after a magenta
  one" is its one-note phrase at 43.6 s, and the Alternate Rhythm's raised
  range held the single pickup note before the chorus ("a dificuldade estava a
  zero e eu só tentei aumentar, e crashou logo"). The floor now applies to every
  phrase with notes, and `_level_notes` shows at least one note at every level
  up to the ceiling. Guarded by
  `test_a_one_note_phrase_has_levels_and_its_note_on_each`.
- **Linked phrases are equal.** `_phrase_signature` only knew
  time/string/fret, so September linked passages where one had a pull-off or a
  let-ring sustain the other lacked — one phrase to the game with two different
  contents. It now includes sustain, techniques, slide and bend. Guarded by
  `test_riffs_that_differ_by_a_technique_or_a_sustain_are_not_linked`.
- **"None" is -1 in the note bytes.** DLC Builder writes -1 in Tap/Slap/Pluck
  of every note and in LeftHand/PickDirection of every chord (PickDirection of a
  single note is 1 for an upstroke, else 0); we wrote 0 — a real value for each.
  Those five are now signed bytes defaulting to -1. Guarded by
  `test_note_bytes_that_a_note_does_not_use_are_minus_one`.
- Found on the way: the XML's `pickDirection` is ONE bit (DLC Builder:
  `ParseBinary(v) << 10`), so our "2" for an upstroke landed on bit 11 — SLAP —
  on the DLC Builder path. The writer now emits "1" for an upstroke only, and
  the reader maps it back to our 2.
Still different and NOT changed (no mechanism tying them to a crash): DLC
Builder's DDC makes its own phrases (~25 s each, COUNT spanning everything
before the first note, no empty phrases in the lead-in), its anchors are the
DDC's (they DO cross phrase boundaries at higher levels, starting at each
phrase that has notes at that level), and its note `Hash`/`NoteFlags` come
from F#'s structural `hash` of the note record and a `NoteFlagger` (finding F,
still not reproduced). Which of the three changes above the game cared about is
unproven until the user plays it.

**The phrases ARE DLC Builder's now (`_prepare_sections` = a port of
`PhraseGenerator.generate`, Rocksmith2014.NET).** The user's next test still
crashed; DLC Builder's build of the same song plays, and its SNG was what the
Song Creator Toolkit re-pack the user needs for the App ID leaves untouched
(only `appid.appid` and `toolkit.version` change). DLC Builder generates the
phrases itself when it builds (`PackageBuilder.setupInstrumental`): COUNT from
the first beat to the first note (every empty lead-in section is part of it);
a phrase at the first note and one every 8 measures, moved to the nearest
time not inside a SINGLE note's sustain or a hand shape (`findGoodPhraseTime`;
chords are kept whole by their hand shapes — see the finger-positions note
above) and never within 2 s of the previous one; a "noguitar" section over any
gap of 2.5 s or more, the next phrase where the playing resumes; END at the XML's
own END (the last beat), 100 ms short of the song's end at most. Every gap is
an iteration of ONE phrase named NOGUITAR (`_link_phrases`), sections are only
"riff"/"noguitar" (names the game has tokens for — DLC Builder refuses any
name outside its table, `AttributesCreation.getSectionUIName`), and a chart
that plays from time 0 has no COUNT (DLC Builder refuses to build one). Ours
used to cut at every Guitar Pro section and again every ~8 s, with raw names
("Verse 1", no token) and boundaries inside sustained notes. On the user's
September all four charts now come out with DLC Builder's exact phrase times,
names and sections. **The Guitar Pro section names no longer reach the native
SNG** (nor did they reach DLC Builder's build); the XML keeps them, and so do
RockForge's own editor and viewer. The DD ceilings still come from our own
ramp, not DLC Builder's DD generator, so their VALUES differ. Guarded by
`test_the_phrases_follow_dlc_builders_generator` and the late-entering test
(both fail on the old code). This supersedes the COUNT/END bracketing and the
~8 s subdivision described above. **CONFIRMED IN GAME (2026-09-30)** by the
user on September, every chart, playing and raising the difficulty in Riff
Repeater: "Está perfeito". Which of the four September fixes (sections in
order, a note's anchor from its own level, levels for every phrase with notes +
-1 note bytes + strict linking, and these generated phrases) the game actually
needed is NOT isolated — they shipped one after another and only the last
round was tested clean, so keep all four; do not "simplify" any away.

Anchors never span a phrase-iteration boundary: the game re-anchors at each
phrase start, so a phrase whose opening notes are covered only by the previous
phrase's anchor finds none of its own and crashes on entry (seen exactly at a
section / tone-change boundary). `from_arrangement` splits any anchor that
crosses a boundary into per-phrase pieces (same hand position, re-tagged with the
phrase iteration), so every phrase owns an anchor at its start. Guarded by
`test_anchors_do_not_cross_phrase_iteration_boundaries`.

**A song-start anchor before the first phrase must not wrap onto the LAST
phrase.** `_build_anchors` always starts the very first anchor at absolute
`0.0` (so the opening notes are framed before they reach the strike line) —
but when the beat grid itself starts after `0.0` (a GP lead-in pad, the usual
case), that leaves a real gap `[0.0, first_phrase.start_time)` with no phrase
covering it. `_find_phrase_iteration`'s "not found" fallback returned
`len(phrase_iterations) - 1` unconditionally — correct for a time genuinely
PAST the song's end, but wrong for a time BEFORE its start: it wrapped the
song-opening anchor (and any beat in that same gap) onto a phrase near the
SONG'S END (index 26 on a real chart), corrupting the fret-hand anchor box
with a context from the wrong end of the song — the reported "graphical
glitch"/corrupt highway sprite right at the arrangement's first notes.
`_find_phrase_iteration` now special-cases a time before the first iteration's
start to return index 0. Found by decoding a real user PSARC (AES-CFB TOC +
AES-CTR SNG, both `pycryptodome`-compatible without the sandboxed
`cryptography` package) and confirming the corrupted `phrase_iteration_id`
directly. Guarded by `test_find_phrase_iteration_before_first_start_returns_first_index`
/ `test_song_start_anchor_has_correct_phrase_iteration_not_the_last`.

Anchor extensions are generated one per sliding note (`BeatTime = time +
sustain`, `FretId = slideTo`), so the fretboard re-anchors where the slide lands
(Rocksmith2014.NET `AnchorExtension.fs`, 12-byte layout). Vocals are emitted as
a **separate `<key>_vocals.sng`** arrangement (same Sng2014 container, only the
Vocals section populated) with its own `Vocals` manifest entry — not embedded in
an instrument SNG (which the game would not read as vocals). `sng.from_vocals`
builds that vocals-only model. Each `SngVocal.note` is the non-pitched sentinel
**`VOCAL_NOTE = 254`**, NOT 0 — 254 is Rocksmith's "scroll lyric, no karaoke
pitch" marker (a DLC Builder vocals SNG writes 254; note 0 is a real, absurdly
low MIDI pitch that the game fails to render as a scrolling lyric, so the letra
silently never appears even though the arrangement/manifest/xblock are all
present — isolated by byte-diffing our native "Pride" against a DLC Builder
build). Guarded by `test_vocals_note_is_non_pitched_sentinel`.

The vocals SNG also embeds the **lyric-font glyph atlas** — the Symbols sections
(`SymbolsHeader`=2, `SymbolsTexture`=1, `SymbolsDefinition`=192) that map each
character to a rectangle in the font texture. Writing these **empty** (the old
behaviour) leaves the game with no glyphs to draw, so the letra silently never
appears *even with note 254 and a fully-registered arrangement* — the second
half of the same "Pride" bug. The atlas is **song-independent**: it is the
default Latin font referencing the built-in game asset
`assets\ui\lyrics\lyrics.dds` (NOT packed in the PSARC), and is byte-identical
across DLC Builder builds (md5-equal between a DLC Builder "Free" and "Pride"
vocals SNG). It is vendored verbatim as
`packaging/psarc/vocals_symbols.bin` (the SymbolsHeader+Texture+Definition byte
blob, counts included) and spliced in by `write_sng` for every vocals SNG;
`read_sng` skips the populated entries by their fixed sizes (32 / 144 / 44
bytes). Rebuilding DLC Builder's own 324 "Pride" syllables through
`from_vocals` reproduces its vocals + symbol block exactly. Guarded by
`test_vocals_sng_carries_the_lyric_font_symbol_atlas` /
`test_instrument_sng_has_no_vocals_symbol_block`.

What is intentionally absent (these are correct given the domain model, not
defects):
- **Simplified DDC (Dynamic Difficulty)** — **working in game as of
  2026-08-25** (it ramps and the level persists; see the resolution note at the
  end of this section). `from_arrangement` emits several
  `ArrangementLevels` shaped like a real DDC pass (verified by decoding a DLC
  Builder reference SNG: 23 levels, per-phrase ceilings graduated by density,
  per-iteration hero triples of ~(¼,½,1)·max). Each **phrase's** ceiling scales
  with the note count of its BUSIEST iteration (`phrase_max = min(_DD_LEVEL_CAP,
  busiest-1)`), so each phrase's difficulty bar gets its own HEIGHT instead of a
  flat top: `phrase_max = min(_DD_LEVEL_CAP, max(min(_DD_MIN_LEVELS, busiest-1),
  (busiest-1)//_NOTES_PER_DD_LEVEL))`, and a phrase with NO notes stays 0. The
  cap is a HARD clamp (not a proportional rescale): it preserves the natural
  spread of most phrases and only flattens the handful of extreme-density
  outliers (a fast tapping run can hit 50-70 notes/iteration) at the top. The
  song's `max_difficulty` is the max over phrases, and there are
  `max_difficulty + 1` levels (up to 23).

  **The constants are calibrated against a DLC Builder build of the user's own
  song** (both `.psarc`s decoded and byte-diffed — see the debugging-method note
  above). Two defects showed up directly in that diff and drove the reported "DD
  never leaves the minimum, even set to maximum":
  - `_DD_MIN_LEVELS = 4` (new; since 2026-09-30 no longer bounded by the note
    count — see the September byte-diff above). The ceiling was a bare `(busiest-1)//group`, so a
    SHORT phrase got **zero** levels — one level, nothing to be promoted to,
    permanently pinned at the minimum however well it was played. The reference
    gives every phrase that has notes a ceiling of at least 4 (its own 3-note
    phrase gets exactly 4). On the user's song this was 1 phrase at 0 and 5 at
    ≤2 out of 27; now 0 and 1. The floor is bounded by `busiest-1` so a one-note
    phrase does not get five identical levels, which would be no ramp either.
  - `_NOTES_PER_DD_LEVEL` 3 → 2 and `_DD_LEVEL_CAP` 20 → 22. The reference's
    ceilings run about twice ours for the same note count (a 30-note phrase: 16
    there, 9 here; 63 notes: 22 there, 20 here), so the whole ramp read lower
    than a real DDC's. On the user's song the song max now comes out 22 —
    exactly the reference's.

  **Unverified in-game.** This removes phrases that provably cannot level up and
  puts the ramp's shape in the reference's range; whether it is the whole of the
  reported symptom is not proven. The same byte-diff found further gaps that are
  NOT fixed and are candidates if it persists: the manifest `Techniques` map is
  `{}` (the reference fills `{level: {phraseIteration: [ids]}}` — a game-internal
  enum we have not mapped); the SNG note `Hash` is 0 and `NoteFlags`' numbered
  bit is never set (the reference writes both); our `Levels` REPEATED a saturated
  phrase's notes at every higher level instead of dropping it to zero once past
  its ceiling (**since fixed** — see B below); and the crowd/stage Events
  (`e2`/`E3`/`E13`/`D3`) are absent.

  **Phrase names are now unique (`p0`…`pN`) — the one SONG-SPECIFIC divergence
  found.** They used to be the section name repeated, and a GP with no section
  markers is auto-segmented into spans all called `riff`, so this song shipped
  **27 phrases sharing one name** where the reference has 20, all distinct. That
  shape matters: the user reports DD working on a DIFFERENT song and failing on
  this one, and a GP that DOES carry markers already produced varied names — so
  the symptom follows the song, not the build, and this is the only difference
  that behaves that way. `_phrase_name` keeps `COUNT`/`END`/`NOGUITAR` verbatim
  (the reference does too) and numbers the rest; the descriptive names stay on
  the SECTIONS, a separate list — again matching the reference, whose sections
  are `riff`/`noguitar` while its phrases are `p0`…`p16`. Unverified in-game.

  **The per-phrase ceiling is NOT the variable — established by elimination, so
  do not tune it again hoping to fix DD.** Git bisect over a fixed synthetic
  arrangement shows the DD output byte-identical from `fb8f118` (2026-07-11)
  through `b8113a3` (2026-07-17) — the July 13 refactor batch (`from_arrangement`
  decomposition, the phrase-iteration bisect, the de-quadratic linking, the
  build-the-model-once packer change) altered nothing — and there are NO commits
  at all between 2026-07-17 and 2026-08-21. The ramp has now been shipped at
  three settings and the symptom appeared under all three: one level per note
  (cap 20, the July build), one per three notes (`7591358`), and one per two with
  a floor of 4 (`912ae9e`). Whatever pins the in-game difficulty is not the
  ceiling arithmetic.

  **The ceiling recalibration did NOT fix it.** A REBUILT PSARC was decoded and
  confirmed to carry it (23 levels, max 22, no phrase-with-notes left at ceiling
  0) and the in-game difficulty still sat at the minimum. So the ceilings were
  not the cause and every candidate above is still open. Two things were ruled
  OUT along the way and must not be re-investigated: `PersistentID` and
  `MasterID_RDV` are byte-identical across rebuilds (the game is NOT seeing each
  build as a new song and losing its progress), and `DynamicVisualDensity` is a
  fixed 20-element constant in both files, unrelated to `MaxPhraseDifficulty`.
  **The user ran the decisive experiment (2026-08-25): the DLC Builder build of
  the SAME song DOES ramp.** So the cause IS in our file, and the search space
  is halved. Byte-diffing that working build against our `.psarc` of the same
  song (the method above) leaves exactly these differences, all confirmed:

  | # | difference | status |
  |---|---|---|
  | A | 27 phrases all named `riff` vs `COUNT`/`p0`…`p16`/`NOGUITAR`/`END` | fixed (`_phrase_name`), unverified in game |
  | B | a saturated phrase never left the levels above its ceiling | **fixed below** |
  | C | manifest `Techniques` is `{}` vs 23 populated levels | **partly fixed** (5 derived ids) |
  | D | SNG `Events` empty vs `e2`/`E3`/`E13`/`D3`/`E13` | **fixed** |
  | E | `SongDiffEasy`/`Med`/`Hard` one value written three times | **fixed** (formula below) |
  | F | note `Hash` always 0, `NoteFlags` never sets its bit | **not fixable** — see below |
  | G | manifest `LastConversionDateTime` missing entirely | **fixed** (constant) |
  | H | raw `UIName`, a `COUNT` section, repeated section `Number`s | **fixed** |

  Two candidates were **eliminated** by that same diff and must not be
  re-investigated. The note `Hash` is NOT a stable cross-level note identity —
  the same `(time, string, fret)` carries different hashes at different levels
  in the reference (281 of 752 notes), and there are 1081 distinct hashes over
  6018 note instances, so zeroing it cannot be collapsing a per-note identity
  the DD engine relies on. And `NoteFlags`' set bit correlates with nothing
  legible: not "new at this level", not chord membership, not first-in-phrase
  (agreement 133/211) — so it cannot be reproduced without guessing, and
  guessing a flag the game dereferences is how the earlier highway crashes
  happened.

  **B — a phrase now DROPS OUT of every level above its own ceiling.** This was
  the largest structural difference. `_level_notes` clamped with `min(d, pm)`,
  so once a phrase saturated it repeated its full content at every higher level
  and `Levels[max]` was the entire chart; the reference's top level holds 126 of
  its 623 notes — only the two phrases whose ceiling IS the song max — and every
  phrase that topped out earlier contributes zero. The ramp UP to each ceiling
  was already identical between the two files (verified per phrase: both reach
  full content exactly AT the ceiling, never above it), so this changes nothing
  a player sees below a phrase's ceiling; what it fixes is that no phrase ever
  left, leaving all 29 present at all 23 levels regardless of their declared
  `max_difficulty`. Anchors follow for free (`_build_level` already derives them
  from that level's own notes), which reproduces the reference's declining
  anchor counts too. Guarded by
  `test_a_phrase_drops_out_of_levels_above_its_own_ceiling`, confirmed to fail
  on the old `min(d, pm)`.

  **E — the difficulty densities are three different values.** Each is that
  difficulty's note density scaled back up by how much of the chart it shows:
  `4 x NotesEasy`, `2 x NotesMedium`, `1 x NotesHard`, each over
  `10 x songLength`. Derived from the reference and checked to the last digit
  (182/331/623 notes over 202.509 s reproduces its 0.359490191 / 0.326899047 /
  0.307640644, where we wrote 0.307641 three times). Guarded by
  `test_song_difficulty_easy_medium_hard_are_three_different_densities`.

  **C — `Techniques`, five ids and no more.** The map is
  `{level: {phraseIteration: [ids]}}` over a game-internal enum. Five ids were
  DERIVED, not guessed: each was tested for exact equivalence ("this id is
  listed for this (level, iteration)" ⟺ "a note there carries this technique")
  across all 508 level×iteration pairs of BOTH reference arrangements, and each
  scored **1.000** — `3` hammer-on, `6` HOPO (hammer-on OR pull-off), `9`
  pull-off, `11` slide, `16` vibrato. The rest is deliberately NOT emitted: the
  reference song uses only a handful of techniques, so there is no evidence at
  all for bends/harmonics/tapping/tremolo/slap-pop/accents/unpitched slides, and
  three ids that DO appear (`7`, `13`, `33`, `35`) top out at 0.87–0.97 against
  their best-matching feature, i.e. their real definition is not pinned down.
  An omitted technique behaves exactly like the empty map we shipped before, so
  partial-but-certain beats complete-but-invented. `_techniques` in
  `manifest.py`; guarded by `test_techniques_map_carries_only_the_derived_ids`,
  which fails if an unmapped id ever leaks out.

  **D — the stage cues.** `_build_events` emits the reference's five, and the
  placement rule is read off the reference and confirmed to hold independently
  on BOTH its arrangements, whose start/first-note times differ: `e2` at
  `start_time`, `E3` at `first_note + 0.6`, `E13` at `E3 + 2.5`, `D3` at
  `song_length - 9`, `E13` at `song_length` (lead 6.421/8.6/11.1/193.509/202.509
  from 6.421/8.0; rhythm 5.0/14.021/16.521/193.509/202.509 from 5.0/13.421).
  Only the PLACEMENT is reproduced — what the codes mean to the game is not
  documented anywhere citable — and they are inert 256-byte strings in a
  venue/crowd-staging section, not note geometry. A song shorter than the
  intro+outro leads DROPS the outro cue rather than clamping it to 0, which
  would put a "nine seconds from the end" cue at the very start.
  **`read_sng` must dispatch on the section's IDENTITY, not its entry size:
  Actions and Events are both 260 bytes**, so keying off the size read the
  Actions section as Events and left the real ones unread (caught by
  `test_read_sng_skips_populated_sections_a_real_file_carries`).

  **F — not fixable without guessing, so not attempted.** The note `Hash` was
  brute-forced against the reference: no CRC-32 or adler32 over ANY contiguous
  byte range of the serialized note matches, and neither does the full standard
  CRC-32 catalogue (11 variants) crossed with every subset of plausibly-zeroed
  fields. It is computed over a representation we do not have. `NoteFlags`'
  bit is no better: "new at this level, per phrase iteration" agrees only
  0.695, and nothing else correlates. Writing a guessed value into a field the
  game dereferences is precisely how the earlier highway crashes happened, so
  both stay 0. Do not re-open this without a new source of truth.

  **G — `LastConversionDateTime`.** Was missing from the manifest entirely (the
  SNG's own copy also used a different format from the reference). Now emitted
  in both, as a **constant** (`LAST_CONVERSION`, kept in sync between `sng.py`
  and `manifest.py`) — a field named "last conversion" is exactly what a game
  could use to decide a song was re-authored and drop its saved progress, and a
  value that changed every rebuild would be the bug rather than the fix. Same
  reasoning as the deterministic persistent IDs. Unproven either way.

  **The note counts had to change with B.** `NotesEasy`/`Medium`/`Hard` were
  `len(levels[k].notes)` for a fixed `k` — only ever right for Hard while the
  top level held the whole chart. They are now what the player SEES at each
  hero setting: for every phrase iteration, the count at ITS OWN hero level,
  summed over the song. Derived from the reference and exact on both its
  arrangements (182/331/623 and 155/283/525, whose top levels hold just 126 and
  99 notes). Guarded by
  `test_note_counts_are_per_iteration_hero_totals_not_one_level`.

  **The symptom was isolated to PERSISTENCE, not level data (2026-08-25).**
  The user's later report is precise: the levels ARE there, Riff Repeater DOES
  raise them, and the new level is not kept — it zeroes every time. So the DD
  tables are being read correctly and something about how the song is
  identified or dated is stopping the profile write from sticking. Two more
  candidates were eliminated against the reference along the way: the `.hsan`
  header and the per-arrangement `.json` agree on `PersistentID`/`MasterID_RDV`
  in BOTH files (the game is not reading progress under one key and saving it
  under another), and `ArrangementProperties` is byte-identical between the two
  builds. `DynamicVisualDensity` is likewise the same fixed 20-element constant
  in both. The `Sections` divergences this left open are now fixed — H below.

  **H — the section list.** Three divergences, all fixed together because they
  are all about the same list, and all read off the reference:
  - **`UIName` is a localisation token**, not the raw string: the reference
    writes `$[34298] Riff [1]` / `$[6091] No Guitar [1]` where we wrote `riff` /
    `noguitar`. Only those two ids are known (the full name→id table is a game
    resource we do not have), so `_SECTION_UI_NAMES` carries exactly them and
    every other name falls back to the raw string — i.e. no worse than before.
    The trailing `[1]` is part of the token, NOT the number (the reference's
    "Riff 17" still ends `[1]`).
  - **The `COUNT` phrase gets no section.** The reference has 19 sections over
    20 phrase iterations, starting at iteration 1; the COUNT *phrase* stays. Its
    END phrase's section is named `noguitar`, the same closer the XML writer
    already appends.
  - **`Number` is an ordinal per NAME, not the list index.** Both callers passed
    the index, so with COUNT/END and several names mixed in the numbers
    duplicated and skipped — the shipped build had two consecutive sections both
    numbered 2, naming two different passages the same thing in Riff Repeater.
    `domain/arrangement.py`'s `number_sections` is the single pure
    implementation, used by BOTH the SNG builder and the XML writer so the two
    cannot drift, and it carries a running tally so the packer's
    `renumber_sections_across` can continue the numbering across the song's
    arrangements — which is what the reference does (Lead riffs 1-17, Rhythm
    riffs 18-34; noguitars 1-2 then 3-4). Applied before both the manifests and
    the `.sng` payloads are derived, so they can never disagree about what
    "Riff 18" is. `gp_pipeline` no longer numbers `section_overrides` by
    position either (it made the first Solo "Solo 2" just because an Intro
    preceded it). Guarded by
    `test_number_sections_counts_per_name_not_by_position`,
    `test_sections_match_the_reference_shape`,
    `test_section_numbers_continue_across_arrangements` and
    `test_section_ui_name_is_a_localisation_token_when_known`.

  **RESOLVED IN GAME (2026-08-25).** A rebuild carrying A, B, C, D, E, G and H
  ramps Dynamic Difficulty and KEEPS the level. The long-running symptom is
  closed.

  **Which one fixed it is NOT known, and that matters.** All seven shipped in
  one batch, so there is no evidence isolating the cause — do not "simplify"
  any of them away later on the grounds that it looks cosmetic. Each was an
  independently confirmed divergence from a build known to work; the ones with
  a plausible mechanism for the *final* symptom (the level rose and then
  zeroed, i.e. a persistence failure rather than missing level data) are G
  (`LastConversionDateTime` absent, so nothing pinned the song's conversion
  identity) and H (duplicate section numbers). B/C/D/E were structural
  correctness. If any of this is ever revisited, the only honest statement is
  "the batch fixed it".

  What stayed at 0 throughout and is therefore proven NOT to be required: the
  note `Hash`, the `NoteFlags` bit (finding F), `NLinkedDifficulty`,
  `PhraseExtraInfo`, Actions, Tones and DNAs. That is a useful negative
  result — F was the largest remaining unknown and it can now be closed rather
  than re-opened. The `.psarc` the user tested is byte-identical to their
  2026-08-24 one (same md5), so it predates even fix A — a rebuild on current
  `main` is what the next round of evidence has to come from.

  At level `d`, each iteration shows the strongest-beat prefix of its
  notes scaled by `d` against that phrase's ceiling (`_level_notes`, ranked by
  `_note_tier` then time), so level 0 is the strongest beats and a phrase's own
  ceiling is where it shows its full content (and above which it drops out). `phrase_iterations[].difficulty` is the `(round(max/4),
  round(max/2), max)` Easy/Medium/Hard hero triple. Anchors are shared across
  levels (fret-hand windows are valid at any density), but **slide
  anchor-extensions are rebuilt per level from that level's own notes**
  (`_build_level`): an extension pointing at a note the level dropped crashes
  the game on the first low-difficulty pass through the section. Hand shapes are
  rebuilt per level the same way (see the finger-positions note above). Guarded by
  `test_dd_levels_have_their_own_hand_shapes_and_slide_extensions`. The manifest reports
  `MaxPhraseDifficulty` + `NotesEasy/Medium/Hard` from the levels.
  **Phrase linking:** musically-identical iterations are collapsed onto ONE
  shared phrase (`_phrase_signature` fingerprints each section's notes relative
  to its start; a match reuses the phrase id), so a repeated riff is a single
  phrase with many iterations — learned once and mastered on every repeat, and
  the difficulty graph / Riff Repeater show the song's true handful of unique
  phrases instead of one bar per section (a real CDLC has far fewer phrases than
  sections — decoded DLC Builder "Pride" lead: 12 phrases vs our old 29). The
  per-phrase ceiling is its BUSIEST iteration, so a repeated riff levels by its
  hardest occurrence. Note-less spans (COUNT/END/gaps) never dedup. Still a
  density ramp for the per-level note *selection* (density-ranked, not musically
  phrased), and the finer `NLinkedDifficulty` section (linking the levels of
  *different* phrases) is NOT emitted. The trustworthy full-DD path stays the
  DLC Builder bundle (it runs a real DDC). Guarded by
  `test_identical_riffs_share_one_phrase`.
  **A note's `phrase_id` is the linked phrase id, NOT its iteration index.**
  Once linking makes fewer phrases than iterations, setting a note's `PhraseId`
  to its phrase-*iteration* index (the pre-linking 1:1 shortcut) runs off the end
  of the Phrases array — the game dereferences it *while scoring that note* and
  crashes (a hands-off run never touches it, so it looks fragile/intermittent).
  `from_arrangement` sets `phrase_id = phrase_iterations[pi_id].phrase_id`.
  Guarded by `test_note_phrase_id_is_in_bounds_after_linking`.
  A section-less GP is auto-segmented into ~13 s phrases (`_default_sections`) so
  DD still ramps per-phrase, and within a phrase the shown notes are spread across
  its timeline (`_spread_order`) rather than clustered at its start. **DD is
  toggleable per song** (`GpJobSpec.dynamic_difficulty` / `RebuildIn`, the "DD"
  checkbox): off ⇒ a single full-chart level (`from_arrangement(...,
  dynamic_difficulty=False)`), a safety valve when DD misbehaves on a song.
- **Note Hash = 0**: a deliberate choice — the two reference tools
  (Rocksmith2014.NET vs toolkit) compute mutually different, non-validated hash
  values, so 0 is safe and source-consistent. It was later brute-forced against
  a DLC Builder reference (no CRC-32/adler32 over any contiguous byte range of
  the serialized note matches, nor the full standard CRC-32 catalogue crossed
  with every subset of plausibly-zeroed fields) and is NOT reproducible — see
  finding F in the DD section.

Unverified-by-design: the binary layout is ported from the open format docs and
round-trip-tested (`read_sng` ∘ `write_sng` = identity), but is NOT byte-diffed
against a retail/DLC Builder SNG — no reference file exists in CI.

### Dual output: Bundle + PSARC always

`psarc_mode` defaults to `"native"`. Every completed job produces **both** a
Bundle zip (DLC Builder-importable: XMLs, `.rs2dlc`, audio, project metadata)
**and** a `.psarc` file (game-ready, encrypted SNG + manifest). The web UI shows
both download links when `psarc_available` is true. If the `[psarc]` extra
(`cryptography`) is missing, `NativePsarcPacker` gracefully degrades: the bundle
is still produced, only the `.psarc` is omitted (no crash).

**Rocksmith PC load requirements — the full enumeration layout (`gamedata.py`).**
A song not appearing in the in-game list was traced (by byte-diffing a working
DLC Builder PSARC against ours) to a large set of missing/wrong files, now
emitted so the native PSARC matches the retail layout file-for-file:
- filename `*_p.psarc` (the `_p` platform tag — `packer.py`);
- `appid.appid` at the root (`manifest.APP_ID`) — the Steam id of a DLC the game
  checks ownership of. Rocksmith only lists a CDLC whose appid the player
  **owns**, so CDLC reuses an owned DLC's appid. RockForge ships Train "Drops of
  Jupiter" (`492989`); swap it for one the target player owns (e.g. the free base
  song Smashing Pumpkins "Cherub Rock", `248750`) if the song doesn't appear;
- `gamexblocks/nsongs/<key>.xblock` — an `entitySet` with one `RSEnumerable_Song`
  entity per arrangement (this is what makes the engine enumerate the song);
- `flatmodels/rs/rsenumerable_{root,song}.flat` — the (song-independent) model
  schema, vendored verbatim under `psarc/flatmodels/`;
- `<key>_aggregategraph.nt` — the N-Triples asset table mapping every URN to its
  archive path;
- `manifests/…/<arr>.json` (full entries, `InsertRoot = Static.Songs.Entries`,
  `ArrangementType` an **int** enum not a string) **and** the aggregated
  `songs_dlc_<key>.hsan` (**header** subset, `InsertRoot = Static.Songs.Headers`)
  — two distinct layers;
- the SNG under **`songs/bin/generic/<asset>.sng`** (not `songs/arr/`, which now
  holds only the showlights), written as a **full retail `.sng` file**
  (`crypto.pack_sng`: 8-byte header `0x4A`/platform 3 + zero IV + AES-256-CTR of
  a zlib-compressed, size-prefixed payload — header byte-verified against a real
  SNG). The earlier bare-AES-CTR primitive produced an unparseable file: the game
  showed tuning then **froze on the note highway**;
- `songs/arr/<key>_showlights.xml` — the **stage-lighting track**, generated
  from the richest chart (`gamedata.build_showlights`): a fog colour (notes
  24-35) at the song start and at each section, plus a pitch-coloured beam
  (notes 42-59) at each note onset (thinned to `_SHOWLIGHT_MIN_GAP_S`), matching
  the fog-per-section + beam-per-onset shape DLC Builder emits. An **empty**
  showlights (the old behaviour) leaves the stage dark and the song can skip its
  lit intro — including the song-name/title card the game shows over the intro.
  Guarded by `test_showlights_generated_from_arrangement`;
- `gfxassets/album_art/album_<key>_{64,128,256}.dds`
  (a neutral solid-DXT1 **placeholder** — real cover DDS is a DLC Builder step),
  and the `song_<key>_preview.bnk` + its `.wem` alongside the main bank;
- the container's TOC entry offsets are **absolute** from the file start
  (`container.py`), as retail expects — not block-section-relative;
- **a partial uncompressed block stores its real size in the block table, not 0**
  (`container.py`, `_compress_block`). Rocksmith reserves `zlength == 0` for a
  *full* `block_size` block (65536, which wraps the 2-byte field to 0); writing 0
  for a *partial* raw block (e.g. the 6-byte `appid.appid`) made the game read it
  as a full 65536-byte block, so the appid came back corrupt and the song was
  silently dropped from the list **even with the right appid value**. Byte-diffing
  a working DLC Builder PSARC (stores `appid.appid` with `zlength = 6`) and the
  toolkit's re-pack of our own output (which rewrites exactly this) isolated it.
  Guarded by `test_partial_uncompressed_block_zlength_is_its_size_not_zero`;
- `toolkit.version`'s **`Toolkit version:` line must be a numeric
  RocksmithToolkitLib version** (`2.9.2.1-5df928a5`, `manifest.TOOLKIT_VERSION`).
  The Rocksmith CDLC loader patch (the `D3DX9_42.dll` proxy that disables the DLC
  signature check) reads this field to recognise a PSARC as legitimate CDLC and
  only then whitelists it; a custom non-numeric value (`RockForge-native`) made
  the patch skip our file, so the game silently dropped the song from the list
  **even with a correct appid** — the "plays only after re-packing with the Custom
  Song Toolkit / CustomsForge Song Manager" symptom. Byte-diffing the toolkit's
  re-pack of our own output isolated this as the sole meaningful change (it only
  rewrites this one line). Guarded by `test_build_manifest_files_packs_and_round_trips`;
- **`ArrangementProperties`' technique flags, `SongOffset` and `TargetScore` are
  real values, not zeros.** All the technique flags were hard 0, so every chart
  advertised itself as using no palm mutes, power chords, slides, sustain or
  vibrato — a false claim about its own content (byte-diffing a DLC Builder build
  of the same song: it sets all of those from the notes). `_technique_flags`
  derives them from the domain notes; the handful the domain cannot express
  (barre/non-standard chords, finger-picking, syncopation, bass pick) stay 0
  rather than being guessed. `SongOffset` (the recording's lead-in, which the
  game shifts its clock by) was 0 where the reference writes `-startTime`, and
  `TargetScore` (the score counting as full mastery) was 0 where it writes
  100000; `SongPartition` 0 → the chart's number on its path (1, an
  alternate 2 — see the per-chart sync section). The manifest `Techniques` map stays `{}` — see
  the DD note above;
- **every TOC entry carries a 16-byte name hash = `md5(archive_path)`**
  (`container.py`). Rocksmith resolves every asset (SNG/manifest/xblock/…)
  THROUGH this hash, so a zeroed hash makes the game unable to find the files and
  it silently drops the whole song from the list **even with a correct appid** —
  the exact "plays fine once re-packed by the Custom Song Toolkit, but our own
  `.psarc` never appears" symptom. The name-block entry (index 0) has no path and
  uses the fixed retail constant `0x4d3d4000dd8eed661b5cfe5f4abc924b` (both DLC
  Builder and the toolkit write it). Verified by byte-diffing a working DLC
  Builder PSARC and the toolkit's re-pack of our own output; guarded by
  `test_toc_entries_carry_md5_of_path`.

The SNG always emits a valid phrase timeline (`sng._default_sections` synthesizes
a COUNT/riff/END structure when the arrangement has no section markers — without
it the game loads the fretboard, shows no notes and crashes), and the manifest
reports the real note count + phrase/iteration/section tables
(`manifest.arrangement_stats`, from the compiled SNG) so the song-list screen
shows the note count instead of "0". Verified by unpacking our output and diffing
the file list + manifest fields against a real DLC Builder PSARC (they match bar
cosmetic `LastConversionDateTime`). Iterated to playability against a real
Rocksmith install (the SNG format/beat-mask/slide-sentinel/anchor fixes below
came from that loop). Custom tones the user builds ARE serialized into each
arrangement's runtime manifest (`Tones` array + `Tone_Base`/`Tone_A`..`Tone_D`,
via the shared `packaging/tone_dto.py` — the same `ToneDto` the `.rs2dlc` emits,
verified byte-identical against a DLC Builder build of our own tones), so the
in-game tone is the user's, not a default.

**A chart with no tone of its own gets DLC Builder's default tone, not
nothing** (`gear/default_tones.py`, `default_lead.json`/`default_rhythm.json`
copied verbatim from Rocksmith2014.NET, MIT). The manifest used to ship an
empty `Tones` array and a blank `Tone_Base`, so the game fell back to whatever
it plays for a tone it cannot resolve — part of "mesmo sem os tons … não têm
uma tonalidade limpa". DLC Builder's `addDefaultTonesIfNeeded` gives such a
chart the default of its route (Lead and Combo share the Lead route mask →
Plexi; Rhythm → Orange AD50), keyed by the chart's own `tone_base` when it
names one; `_tone_fields` now does the same. The pedal `Category` is the
file's, not our catalogue's (they differ: StudioEQ, ModDelay). Guarded by
`test_the_default_tone_is_dlc_builders_own_for_the_path` (the serialized gear
equals the reference file) and `test_build_arrangement_manifest_fields`.
**And the app says so** (2026-10-01, "na aplicação deve ser visível que estão
escolhidos os tons standard"): a project with no tones of its own
(`jobTones` empty / `has_tones` false — the build only falls back when the
project defines NO gear, since every chart gets the project's tones) shows
"Tons standard" on the Tons page with each chart's default
(`standardToneFor`: Rhythm/Alternate Rhythm → Orange AD50, else Marshall
Plexi), "Tom standard: …" as the empty base option and in the score's live
tone label, a neutral "Tons standard" chip on the project card, and an
informational (not warning) checklist row with "Criar tons próprios". Missing
tones are therefore no longer a gap in `jobCardStatus` ("Falta: tons" is
gone). Browser-only; checked with Playwright.

**Mid-song tone changes now reach the game** (`sng._build_tones`). The SNG's
Tones section was written EMPTY, so from the native PSARC a chart played its
base tone throughout, whatever was marked on the score ("problemas graves com
os tons"). Each entry is `{Time: float32, ToneId: int32}` (8 bytes, the size
`read_sng` already skipped by), and the id is the tone's slot in Tone_A..D
(Rocksmith2014.NET sets `Id = IndexOf(Tones.Names, name)`; its SngToXml maps
0..3 back to Tone_A..D). The slot list is ONE function,
`Arrangement.switch_slots()` — the switchable names that have gear, in order —
read by both the manifest's `Tone_A..D` and the SNG, so the two cannot
disagree about which tone id 1 is. The time is the XML writer's
`_safe_tone_time` (20 ms before a note it would land on); a change to a tone
with no slot has nothing to switch to and is left out. Guarded by
`test_tone_changes_reach_the_sng_with_their_slot_and_off_the_note`. Not heard
in game from here.
Remaining honest gaps: the Dynamic Difficulty ramps and persists in game
(confirmed 2026-08-25) but is still a mechanical DENSITY ramp, not a musical
DDC pass — it picks notes by strongest-beat rank, so it levels correctly
without phrasing the way a real DDC would; and the SNG binary is round-tripped
but not byte-diffed against retail. The DLC Builder bundle remains the route to
a real DDC pass if that phrasing matters for a given song.

### Checking the PSARC and installing it in the game

"Verificar PSARC" and "Instalar no jogo" (2026-10-05, the two the user picked
from a list of suggestions) shorten the rebuild → copy → play loop, which is
how every native-SNG crash was found.

**`psarc/verify.py` — the rules in ONE place.** `check_sng(model)` holds every
invariant whose breaking crashed the game before or that DLC Builder's own
conversion keeps: phrase/iteration/section ranges and order, a phrase with
notes and a ceiling of 0 (September), notes in their own phrase iteration
with an in-range phrase id, each note's anchor the one of ITS level, anchors
that never cross a phrase start, anchor extensions that belong to a slide,
templates whose unused strings carry MIDI -1, tap/slap/pluck at -1, tone
slots 0-3, vocal notes 254, and the hand-shape rules (`findFingerPrintId`,
`convertHandshape`). `tests/test_hand_shape_fuzz.py` now asserts
`check_sng(model) == []` on its hundreds of random charts instead of keeping
its own copy, so the builder and the checker are tested against each other.
`verify_psarc(path)` reads the archive the user is about to copy
(`container.read_entries`, only the manifests and SNGs, not the audio) and
adds the container rules that silently keep a song out of the list: a
numeric `appid.appid`, a numeric `toolkit.version`, every manifest's SNG
present, every SNG decodable. Anything unreadable is a finding, never an
exception. `GET /jobs/{id}/psarc-check` runs it on request (never stored, so
it always describes the file on disk; `describe(code)` words each rule in
the user's language) and groups the problems by chart and rule with a count
and where they first happen. The Exportar page's "Antes de usar" shows it as
a row (`psarcCheckRow`, fetched once per version): "PSARC verificado", or
"O PSARC tem falhas conhecidas" listing them (an error row, so it reaches the
status chip). **Honest limit, said in the row:** it is our reading of the
file — it would not have caught `VOCAL_NOTE = 254` or the partial-block
`zlength`, which are the game reading the file differently, so it never
replaces playing the song. Guarded by `test_psarc_verify.py`: a chart and a
packed PSARC (Lead + Lead alternativo + vocals) pass clean, every rule fires
on its planted fault (mutation-proof), a broken archive is reported not
raised, a broken chart is named, every rule has its words; and
`test_the_built_psarc_is_checked_before_it_goes_to_the_game`.

**`infrastructure/game_install.py` — "Instalar no jogo".** `dlc_folder()` is
the game folder set in Definições (its `dlc`), else the tone collection's dlc
folder, else a Steam library's. `install()` writes into **`dlc/RockForge/`**
— Rocksmith loads sub-folders of `dlc` (CustomsForge Song Manager organises
libraries that way; **confirmed in game by the user, 2026-10-09**) and a folder of our own is
what makes it safe to delete: only a `.psarc` in that folder is ever removed,
namely the copy an earlier version of the song installed under another name
(the title changed, so the key did). The copy goes to a hidden `.part` file
renamed over the target, so the game never sees half a file. A copy of the
same file elsewhere in `dlc` (put there by hand) is reported, not touched —
the game would list the song twice. `POST /jobs/{id}/install` records
`params["installed_psarc"]`/`["installed_from"]` (a fork inherits them),
`JobOut.in_game` is "this" / "older" / None (the file gone = None), and
`GET /game-dlc` gives the target for the UI. A copy that fails (the game open
and holding the file) is a 409 saying to close the game. UI: the "Instalar no
jogo" row under the downloads (`renderInstallRow`): the target, "Esta versão
está no jogo", "No jogo está uma versão anterior", or "Abrir Definições" when
no game folder is found (re-asked when Definições closes). Guarded by
`test_the_psarc_goes_into_our_own_folder_and_replaces_the_earlier_copy`,
`test_a_file_rockforge_did_not_put_there_is_never_deleted` and
`test_install_copies_the_psarc_into_the_games_dlc_folder`; the page with
Playwright (install, reinstall label, older/none states, a broken PSARC's
row, the missing-folder button opening Definições, PT/EN, no page errors).

### Audio → guitar notes: measured, then dropped (2026-10-10)

A second attempt at transcription ("deteção de notas … Lead e Rhythm",
experimental) was measured before anything was built, on the user's PC
against their own charts marked in sync (onset F1, ±50 ms, exact pitch, guitar
stem): GAPS 32.7 %, YourMT3+ 29.8 % — one note in three, in line with the
literature (MT3 .29 on GOAT). Songsterr AI reached 73.4 % (tab F1 69.5 %) on
the same song, and its exported `.gp` already enters "Novo projeto". The user
then dropped the feature and the measuring bench was DELETED; it lives in git
history (`git log -- src/rockforge/experimental`). Do not restart audio
transcription without new evidence.

### Wwise SoundBank (`infrastructure/packaging/psarc/soundbank.py`)

Rocksmith reads a song's audio through a Wwise SoundBank: `song_<key>.bnk`
carries a `Play_<key>` event plus a ~100 ms *prefetch* of the audio, and the
full stream lives beside it as `<fileID>.wem`. Without the `.bnk` the game can
list a song (once appid/manifests are right) but has no event to fire, so it
plays silence. Exactly as DLC Builder / Rocksmith2014.NET do, RockForge does NOT
ask Wwise to build the bank — Wwise (`wwise.py`) only produces the `.wem`; the
`.bnk` is generated in code (`soundbank.generate_soundbank`, ported from the
toolkit's `SoundBankGenerator2014`, MIT — same lineage as `sng.py`) with a
random `fileID`, and the packer emits `audio/windows/song_<key>.bnk` +
`audio/windows/<fileID>.wem`. The manifest points `SongBank` at the real `.bnk`
and adds `SongEvent = Play_<key>`. Layout (PC/little-endian):
`BKHD → DIDX → DATA → HIRC → STID`; HIRC holds Sound/ActorMixer/Action/Event
objects. Same honesty caveat as `sng.py`: round-tripped
(`read_wem_file_id`/`read_bkhd_version`) but **unverified-by-design** — no
reference bnk in CI. **When no Wwise is available the `.psarc` carries no audio at
all** (2026-10-15): it used to pack the WAV under `audio/<key>.<ext>`, a path the
game never loads, so the file was ~30 MB per 3 minutes and still played silence
(a user's report on r/rocksmith). The bundle keeps the audio for DLC Builder, the
checklist's "PSARC jogável" row says ❌ and the `.exe`'s home page names Wwise.
Guarded by `test_package_produces_valid_psarc`.

**Volume ("Calculate Volumes", `normalize/loudness.py`).** The Sound object's
Wwise bus volume (dB) is no longer a neutral 0. **One target
(`runtime_settings.loudness_target()`, default -12 LUFS) drives BOTH the
recording's gain AND the volume calibration**, so the `.wem` and the bus volume
never drift: the packer measures the normalized audio with `ebur128` and offsets
the bus volume to the same target (`calculate_volume` →
`generate_soundbank(volume=…)`), and the song-select **preview** (a trimmed clip
whose own loudness differs) is measured separately and matched so it doesn't
blast over the list.

**The recording is NOT dynamics-processed — one linear gain
(`recording_gain_db`).** It used to go through a single-pass
`loudnorm=I=-12:TP=-1.5:LRA=11`: a gain that moves with the music plus a
true-peak limiter, which reshaped every song ("os PSARC criados pelo rockforge
têm algum ruído e não têm uma tonalidade limpa"). Measured on the user's own
mp3: plain decode I -9.5 / LRA 5.0 / peak +0.5 dBFS; loudnorm I -10.9 (missing
its own target) / **LRA 3.1** (squashed) / peak -1.4; now I -12.0 / LRA 5.0 /
peak -2.0. `FfmpegNormalizer` measures the source once (`measure_levels`:
integrated loudness + true peak, `ebur128=peak=true`, from `offset_s`) and
applies `volume=XdB` with X = target − I, capped so the true peak stays under
`PEAK_CEILING_DBTP` (-1 dBTP) — which also pulls a master mastered OVER 0 dBFS
(this one is) back under it in ffmpeg's float pipeline, before the 16-bit WAV
where an over is simply cut off. What the ceiling holds back, the bus volume
makes up. That is DLC Builder's approach: it never touches the audio and sets
the volume to `-16 − loudness` (Volume.fs). Unmeasurable (no ffmpeg answer) =
no gain filter at all. Guarded by `test_the_recording_gets_a_linear_gain_not_loudnorm`,
`test_the_gain_never_pushes_a_peak_over_the_ceiling`,
`test_an_unmeasurable_recording_is_passed_through_untouched` and
`test_the_recording_gain_goes_to_the_target_but_stops_at_the_peak_ceiling`. **Why -12, not the -16
EBU R128 broadcast reference:** retail Rocksmith ships loud music masters (DLC
Builder's Calculate Volumes lands ~-3/-4 dB of *attenuation* on such a master),
so -16 read audibly quiet in-game; -12 is a music-game level. The target is
**user-editable in the ⚙️ Definições modal** ("Volume alvo (LUFS)", clamped
-20..-6) — push toward -10/-9 if still quiet, back toward -14/-16 if it sounds
harsh. With no limiter any more, a target the recording's peaks cannot reach by
gain alone is reached by BUS volume (clamped ±8 dB), i.e. a boost inside the
game's mix: DLC Builder does the same for a quiet master, but a high target on a
quiet, peaky song is where clipping in game would come from. -16 (DLC Builder's
own) is the cleanest choice; -12 stays the default because the user found -16
too quiet.
`parse_ebur128_i`/`volume_for_loudness` are pure and unit-tested without ffmpeg;
a missing ffmpeg degrades to 0 dB, never a crash. The `.rs2dlc` audio `Volume`
stays neutral (DLC Builder recomputes on import).

### What external software is installed (`/system-check` + `diagnostics.py`)

RockForge ships almost none of its dependencies — Wwise cannot legally be
redistributed, the ML stack is gigabytes, ffmpeg is better taken from the
system. Each already degrades cleanly ON ITS OWN (no Wwise still produces the
bundle, a missing `[ml]` extra is a 503 naming it, no `[psarc]` just omits the
`.psarc`), but every one of those symptoms surfaces DOWNSTREAM and reads as a
bug in RockForge: "o PSARC não é jogável", "a deteção de letra não faz nada".

`infrastructure/diagnostics.py` answers the one question that fixes that — *what
is installed, and what does each gap cost me?* — and `GET /system-check` serves
it to the ⚙️ Definições modal's **🩺 Software externo** block. Each
`Requirement` carries `unlocks` (what it enables), `without_it` (what actually
happens when absent — the honest cost, not a scare) and `install`.

**`found` is a TRI-STATE, and that is the point.** `None` means "cannot be
checked from this process", which is a different and more useful answer than
`False`:
- the **Rocksmith CDLC loader patch** is the single most common reason a song
  never appears in game, and it is only knowable where the GAME is. It is
  looked for (`D3DX9_42.dll`, any case) in the folder set in ⚙️ Definições →
  Geral → "Pasta do Rocksmith 2014" (`runtime_settings` `rocksmith_dir`, the
  user's word wins — "Mas eu posso colocar a diretoria onde está o
  rocksmith"), else the parent of the tone collection's dlc folder when it
  holds `Rocksmith2014.exe`, else every Steam library
  (`tone_collection.rocksmith_game_folders`, which reads `libraryfolders.vdf`
  so a game on another drive is found). With no game here — RockForge may run
  on a work laptop without it — the answer stays `None`, saying so, never
  "missing"; a set folder that does not exist says that. Guarded by
  `test_the_cdlc_patch_is_looked_for_in_the_game_folder`,
  `test_the_rocksmith_folder_set_in_settings_is_where_the_patch_is_looked_for`
  and `test_steam_libraries_on_other_drives_are_searched`;
- **PyTorch installed** tells us nothing about whether it is the CUDA build;
  only importing it would, and the API process must never import torch (the
  layering rule above). Installed-and-unverifiable is `None`; marked broken
  after a CUDA crash IS knowable, and is `False`.

**Nothing heavy is imported.** Detection uses `importlib.util.find_spec`, which
locates a package without importing it — the same trick
`whisperx_adapter.available()` already uses. `find_spec` RAISES on a
half-removed package rather than returning `None`, so `_has` catches that: a
diagnostics page that 500s is worse than one that says "missing", and a broken
install is exactly when the user opens it. The ffmpeg probe runs `-version`
with a timeout and `stdin=DEVNULL` (the hard constraint about console tools
inheriting stdin applies here too); a binary that will not answer is still
reported as FOUND, with the detail saying the probe failed.

**Inside the `.exe` an install instruction is rewritten, not printed.** The
frozen process cannot IMPORT a package the user pip-installs (see the
standalone section), so a bare `pip install` would be a lie — but it can hand
the work to another interpreter, so `_extras_install` rewrites the instruction
to say *where* the packages have to go (the Python `ROCKFORGE_ML_PYTHON` points
at) rather than claiming the feature is unreachable. ffmpeg and Wwise are
ordinary programs, so THEIR instructions are untouched.

**The ML rows report the interpreter that will RUN the work, not this
process.** In the `.exe` those are different Pythons, and our own answer
("nothing installed") says nothing about whether the feature works. They read
`ml_python.availability()`, which probes the other interpreter in a subprocess
when there is one — so the API still never imports torch, and could not answer
for a different interpreter anyway. A `ml_python` row names that interpreter
and its extras; it reads "o próprio Python do RockForge" under `start.bat`,
where the setting is unnecessary.

**Only ffmpeg is `required`** — everything else has a documented degraded path,
and `missing_required` is what the UI turns into the red banner. Guarded by
`test_diagnostics.py` (including a test that fails if the probe ever starts
importing torch/demucs/librosa/whisperx) and `test_system_check_*` in
`test_api.py`. This is the machine-level view; the per-job **"Estado do PSARC"**
checklist stays the per-song one.

### Optional API authentication (`ROCKFORGE_API_TOKEN`)

RockForge has **no authentication by design** for local single-user setups —
`start.bat` and the standalone `.exe` both bind `127.0.0.1`, so nothing outside
the machine can reach the API. Docker Compose is the one deployment path that
actually opens a network port (`8000:8000`), and a full-codebase audit found
that with no auth layer, every job (including uploaded GP files, cover art, and
built bundles) is readable/deletable by anyone who can reach the port, and the
unauthenticated `/settings` endpoint can repoint the Banquet stem-separator's
`banquet_repo` at an arbitrary filesystem path the worker then executes
`train.py` from.

`app._verify_api_auth` is a global FastAPI dependency (wired via
`FastAPI(dependencies=[...])`, so it runs before every route) gated on
`settings.api_token` (env `ROCKFORGE_API_TOKEN`): `None` (default) is a no-op —
zero behavior change for local setups. When set, it requires **HTTP Basic**
credentials whose password matches the token (any username;
`secrets.compare_digest` for a constant-time comparison) via
`fastapi.security.HTTPBasic`. Basic, not a custom bearer header, deliberately:
a plain browser gets a native login prompt on first visit and then
auto-attaches the credentials to every subsequent same-origin request
(including the page's own `fetch()` calls) — no frontend code needed.
`docker-compose.yml` requires `ROCKFORGE_API_TOKEN` via `${VAR:?…}` compose
syntax, so `docker compose up` refuses to start without a `.env`-supplied
secret rather than silently running exposed and unauthenticated. Guarded by
`test_no_auth_by_default` / `test_api_token_gates_every_route_when_set`.

**Host allowlist (`_verify_host`, `ROCKFORGE_ALLOWED_HOSTS`).** DNS rebinding
(a foreign page pointing its own domain at 127.0.0.1) is same-origin to the
browser, so neither CORS nor `_verify_same_origin` — which compares Origin with
that same Host — can see it; only the Host header still names the attacker's
domain. Default `localhost,127.0.0.1,::1`; docker-compose sets `*` (its token is
per-origin). `Origin: null` is a cross-origin POST. Tests send
`Host: testserver`, which `tests/conftest.py` adds. Every response also carries
`nosniff` and `frame-ancestors 'none'`/`X-Frame-Options: DENY`
(`_SECURITY_HEADERS`). **`esc()` in `web/app.js` escapes `"` and `'`**: the old
text-node version escaped only `& < >`, and ~40 sites put it in a quoted
attribute, so a GP title closed the attribute and ran a handler on the home page.
Guarded by `test_only_the_names_the_server_answers_to_are_served`,
`test_a_null_origin_is_a_cross_origin_post` (both mutation-checked),
`test_any_name_is_served_when_the_allowlist_says_so` and
`test_every_response_carries_the_browser_hardening_headers`; `esc` with
Playwright (a job titled with an attribute payload ran it before, not after).

### Standalone executable (`build_exe.py` / PyInstaller)

**It opens a NATIVE WINDOW, not a browser tab.** `start_standalone.py` runs
uvicorn on a daemon thread and shows the UI in a `pywebview` window
(`run_windowed`); `webview.start()` must own the main thread, which is why the
server is what moves aside. pywebview wraps the platform's OWN webview — Edge
WebView2 on Windows, which ships with the OS — so it costs a few MB rather than
bundling a second browser the way Electron would, and `web/` is served and
rendered completely unchanged. It is the optional `[desktop]` extra: without it
(or when the GUI backend cannot start — no WebView2 runtime, no display)
`run_in_browser` restores the old behaviour, serve-and-open-the-default-browser,
after releasing the port so the fallback can bind it.

**The window must be allowed to save files** (`allow_downloads`): pywebview
CANCELS every download by default (`webview.settings['ALLOW_DOWNLOADS'] = False`;
edgechromium's `on_download_starting` sets `args.Cancel`), silently, so in the
`.exe` the .psarc/bundle "Download" buttons did nothing at all — a user's first
report after the public release. With it on, WebView2 opens the Save As dialog.
Guarded by `test_the_window_is_allowed_to_save_downloads` and the fake-webview
window test.

**A window close is unambiguous, so windowed mode turns the idle-shutdown
watchdog OFF** (`ROCKFORGE_IDLE_SHUTDOWN_S=0`). That whole mechanism exists only
because "the browser tab closed" is a guess made from missing heartbeats — a
guess a backgrounded tab breaks, which needed its own guard. The window replaces
it, and `should_close_now` keeps the part that matters: in `inprocess` mode the
worker runs in the API's own process, so closing mid-build would abort it and
leave the job stuck at RUNNING, exactly what `_should_shutdown(work_in_flight)`
prevents on the browser path. The window's `closing` event (cancellable —
returning `False` vetoes) asks the user to confirm instead of silently
discarding the work or refusing to close at all.

**Every child process starts without a console window** (`hide_child_consoles`,
the first line of `main()`): the `.exe` is a GUI-subsystem program, so each
console program it runs — ffmpeg, the components' `python.exe`, `nvidia-smi`,
yt-dlp, WwiseConsole — got a console of its own, a black window flashing for a
fraction of a second on every button that ran one ("aparece durante uma fração
de segundo um ecrã preto"). It patches `subprocess.Popen.__init__` once to add
`CREATE_NO_WINDOW` (unless the call asked for `CREATE_NEW_CONSOLE` or
`DETACHED_PROCESS`), so a call site added later is covered too; the hidden
console is inherited by the child's own children (pip, the ML Python's ffmpeg).
Windows only (a non-zero `creationflags` raises elsewhere), and only in the
launcher — `start.bat` runs from a console, where there is nothing to hide.
Guarded by `test_child_processes_start_without_a_console_window_on_windows`;
not seen on Windows from here.

**The icon** is a guitar pick in the app's orange with an anvil and a spark
("Rock" + "Forge"): `assets/rockforge.svg` (48 px up) and
`assets/rockforge-small.svg` (16-32 px: no spark, the pick larger — detail is
noise there). `assets/make_icon.py` renders both through Playwright's Chromium
into `assets/rockforge.ico` (one hand-picked image per size, 16-256),
`rockforge-256.png` (the README heading) and `web/favicon.svg` (the browser
tab, served at `/favicon.svg`); run it after changing an SVG. `rockforge.spec`
sets `icon=` (window, taskbar and shortcuts take it from the `.exe`) and
`installer.iss` `SetupIconFile`. Guarded by
`test_the_exe_and_the_installer_carry_the_rockforge_icon` and
`test_the_page_carries_the_rockforge_icon`. Our own drawing, no third-party art.

**`console=False` means the process has NO stdout or stderr** — they are
`None`, and uvicorn's logging raises on the first line. `main()` redirects both
to `work_dir/rockforge.log` before anything can write (`redirect_output_to_log`),
falling back to a temp file if settings cannot even load: a crash with no console
AND no log is unreportable. pywebview needs no `hiddenimports` — its wheel
declares a `pyinstaller40` entry point pointing at its own hook directory, which
PyInstaller discovers automatically.

Everything in the launcher is a plain function called from `main()`, nothing runs
at import: the environment must be configured before anything imports
`rockforge.config` (pydantic-settings reads the environment once, at import), and
a module that did that on the way in could not be tested without side effects.
Guarded by `test_standalone_launcher.py` (the watchdog/worker-mode defaults and
that an explicit setting still wins, the close-confirmation logic, the readiness
poll, the ffmpeg PATH order, the log fallback, and — with a fake `webview` — that
the window opens on the local API, that the close handler is actually wired to
`work_in_flight`, and that BOTH failure paths release the port).

It sets `ROCKFORGE_WORKER_MODE=inprocess` before any import, so the API
dispatches tasks to a `ThreadPoolExecutor(max_workers=1)` inside the same process
instead of to Celery/Redis. The task functions themselves (`generate_cdlc`,
`detect_lyrics`) are identical — only the dispatch changes. `worker_mode`
(`config.py`) controls which path `_enqueue`/`_enqueue_detect` take:

- `"celery"` (default): `.delay(job.id)` via Celery (needs Redis + worker).
- `"inprocess"`: `inprocess.enqueue_generate(job.id)` via thread pool (no Redis).

The PyInstaller spec (`rockforge.spec`) excludes the ML stack (torch, demucs,
whisperx, scipy, numpy) — the `.exe` covers the GP pipeline + native PSARC core.

**The in-process worker still CREATES the Celery app, so the spec must bundle
what Celery imports by name.** `inprocess` calls the task functions directly,
but it gets them by importing `celery_app`, whose module-level `Celery(...)`
loads its fixups and loaders from strings (`celery.fixups.django:fixup`,
`celery.loaders.app:AppLoader`) — invisible to PyInstaller's static analysis,
and no hook in pyinstaller-hooks-contrib covers Celery. The frozen worker died
on that import (`No module named 'celery.fixups'`) before any job ran, so every
project created in the `.exe` sat PENDING forever. `rockforge.spec` now adds
`celery_by_name`, read from Celery's own `BUILTIN_FIXUPS`/`LOADER_ALIASES` so an
upgrade follows by itself, guarded by
`test_spec_bundles_the_modules_celery_imports_by_name`. Reproduced and verified
by actually building the spec (a Linux build here, same bundling logic) and
running jobs through it to completion — CI cannot build the `.exe`.

**A task that dies before its own error handling runs now says so.** That
failure was silent: `_run_task` logged the traceback to a file and the job never
left PENDING, so the UI just sat on its first stage. `inprocess._record_failure`
marks a build FAILED with the reason (never overwriting a failure the task
already recorded) and a detection `unavailable` with a line in its log, the
places the UI actually reads. Guarded by `test_a_build_that_dies_before_it_starts_*`,
`test_a_detection_that_dies_before_it_starts_*` and
`test_a_job_that_already_failed_keeps_its_own_error` (`test_inprocess.py`).

**The `.exe` cannot IMPORT the ML stack — and does not need to
(`infrastructure/ml_python.py`).** A PyInstaller build's `sys.path` is just its
own `_internal`, so the system's site-packages are never importable (verified
by building a minimal frozen app and reading `sys.path` back; an earlier note
claiming "ML extras work if installed separately on the user's Python" was
false about this). But **every ML stage runs, or now runs, as a subprocess** —
Demucs via `_demucs_patcher.py`, WhisperX via `_whisperx_runner.py` (for the
ctranslate2 CUDA deadlock), Banquet via query-bandit's own `train.py`, and
librosa via `_librosa_runner.py` — so none of them needs the package importable
in the calling process.

What actually kept them out of the standalone build was one argument repeated
at each of those call sites: **`sys.executable`, which in a frozen app is the
`.exe` itself**, so the subprocess would relaunch RockForge instead of running
Demucs. `ROCKFORGE_ML_PYTHON` (⚙️ Definições → "Python para o ML", persisted
via `runtime_settings`) closes that: point it at a Python 3.11 carrying
`[ml,lyrics]` and the `.exe` gains stem separation, tone detection, lyric
detection and "Corrigir daqui". It is the same arrangement ffmpeg and Wwise
already have — external software, installed once, outside the app.

`ml_python.resolve()` returns the configured interpreter, else `sys.executable`
when NOT frozen (so running from a Python install is the byte-for-byte old
path), else **None** — which callers turn into the ordinary "that extra is
missing" error naming the setting, never a crash. `test_ml_python.py` pins the
call sites by **parsing** them for a `sys.executable` attribute access (a text
grep would trip on the comments explaining why it is gone): a regression there
is invisible from a Python install, where the two values are equal, and breaks
only the `.exe`, which CI can neither build nor run.

**The librosa measurements have ONE implementation, reachable two ways.**
`infrastructure/_librosa_runner.py` holds `tempo_from`/`tuning_cents`/
`tone_features` and a `main()` that prints one line of JSON; it imports
**nothing from `rockforge`** (same rule as the other two runners — that is what
lets an interpreter which has librosa but has never heard of RockForge run it).
`librosa_adapter` and `tone_analysis/analyzer` call those functions **directly**
when this process has librosa and shell out otherwise, so `start.bat` keeps the
in-process path — "Corrigir daqui" is a per-click tool and paying an
interpreter start plus a librosa import on every click would make it unusable.
Two copies of the feature extraction would drift and silently classify a tone
differently in the `.exe`; `test_the_librosa_measurements_have_one_implementation`
fails if either adapter grows an `import librosa` of its own. The split of the
tone analyzer was already right for this: the librosa half produces seven
scalars, and the calibration that maps them to a `ToneProfile`
(`profile_from_features`) is pure and stays where CI can test it.

**`ml_python.availability()` is the ONE place that decides whom to ask.** With
nothing configured and not frozen, this process IS the interpreter that will do
the work, so `find_spec` answers exactly and instantly — spawning a probe to
ask ourselves would cost a subprocess on every `/settings` open. Otherwise the
packages live elsewhere and only that interpreter can answer, so it is asked in
a subprocess (`probe`) — the API process must never import torch. Both the ⚙️
diagnostics rows and the settings page's per-extra ✓/✗ read it, so the two
halves of the same modal cannot contradict each other. A configured path that
is not a working interpreter reports `python: False`, deliberately distinct
from "it runs but has no demucs": "Demucs em falta" would send the user to
reinstall Demucs instead of fixing the path.

**The runners must be shipped as real `.py` FILES.** Inside the bundle a
package's modules live in the archive, where no other interpreter can execute
them, so `rockforge.spec` WALKS for `_*_runner.py`/`_demucs_patcher.py` and
bundles each at its package path — which is where `ml_python.runner_path`
looks. Walked, not listed by hand, for the same reason `web/` is (below), and
guarded by `test_spec_bundles_every_ml_runner_at_its_package_path`, which
asserts the destination too: a runner bundled to the wrong folder is exactly as
broken as one not bundled at all.
ffmpeg is bundled from `ffmpeg/ffmpeg.exe` (placed by the user before build);
`start_standalone.py` prepends the bundled path to `$PATH` at launch.

**The spec WALKS `web/`; it must never list those files by hand again.** It used
to carry a single literal `("web/index.html", "web")`, so when `index.html`'s
~4100-line inline `<script>` was extracted into `web/app.js` the list did not
follow — the shipped `.exe` served an `index.html` whose `<script src="/app.js">`
had nothing behind it and **the entire UI was inert**, with `web/gear_images/`
missing too. Nothing could catch it: no gate ever looked at the spec.
`test_standalone_spec.py` now executes `rockforge.spec` with the PyInstaller
builders stubbed out and asserts its real `datas` covers every file under `web/`,
at the matching destination.

**`_web_file_candidates()` tries `sys._MEIPASS/web` FIRST** (`_web_dirs()`), which
is the other half of that bug: inside the bundle neither of the other candidates
resolves — `__file__` points into the frozen archive and `start_standalone.py`
never chdirs — so a bundled file would 404 even once the spec ships it.
`_gear_image_dirs()` shares the same list (after the `work_dir` override).
Guarded by `test_bundled_web_files_are_found_in_the_pyinstaller_bundle`.

### The `.exe` installs its own extra components (`infrastructure/components.py`)

"Implementa o aviso de versão nova. E garante que os utilizadores que usam o
exe sabem que precisam de instalar outras dependências. Deveria ser
automaticamente instalado com o exe, excepto o wwise." (2026-10-15). The
`ml_python` route above already let the `.exe` delegate every heavy stage to
another Python; what was missing was that Python. The app now installs it:
the official `python` NuGet package (3.11.9, relocatable, no registry) into
`%LOCALAPPDATA%\RockForge\components\python`, `ensurepip`, PyTorch's cu121
pair (`torch==2.4.1`, `torchaudio==2.4.1`) when `nvidia-smi` exists, then ONE
pip call with the `[ml]`, `[lyrics]`, `[youtube]` and `[pdf]` requirement
strings — read from `pyproject.toml` by `rockforge.spec` at build time into
`components_requirements.json` (the frozen app has no pyproject), the `git+`
URL rewritten to the commit's GitHub archive (`_github_archive`, no git on the
user's machine) — and Deno into `components\tools` (`add_tools_to_path` at
launch, so yt-dlp's `js_runtime_args` finds it). Then `ml_python` is set to
it, unless the user set another path by hand (`_use`). **And it is found by
itself when that setting is empty** (`ml_python.components_python`, read by
`configured()` — so resolve, availability, the PDF and YouTube routes and the
diagnostics all see it): the user's first install ended with every component
in place and the setting empty — likely a Definições page opened before the
install finished saving its empty field over it — so nothing used them ("fez
download dos extra components mas não os deteta"). A path set by hand still
wins; from a Python install nothing changes. The settings page says "Detetado
sozinho" (`ml_python_validation()["auto"]`). Guarded by
`test_the_exe_finds_the_extra_components_python_by_itself` (mutation-checked). A background thread in
the API process like the tone-collection scan (`start_install`, one at a time,
`busy()` counted by the window-close and idle watchdogs), polled through
`GET /components`; `POST /components/install` (409 off the Windows `.exe` —
`start.bat` installs the extras itself), `POST /components/decline` («Agora
não», `components_declined`). Entry points: Inno Setup's ticked task
`components` → `rockforge.exe --install-components` (`components_flag` →
`ROCKFORGE_INSTALL_COMPONENTS=1` → `auto_install`, the page starts it), the
home page notice, and the «Componentes extra» card at the top of Definições →
Software (list ✓/✗ asked of the private Python via `ml_python.probe`, whose
`PACKAGES` now also cover `yt_dlp`/`pdf_to_gp5`/`rapidocr_onnxruntime`, the
log, Instalar/Completar/Reinstalar). `[UninstallDelete]` removes
`components`. **The PDF converter runs there too** (`gpimport/_pdf_runner.py`,
imports nothing from RockForge, walked into the bundle with the other
runners): `pdf_import.convert` uses it when the converter is not importable
here but the ML interpreter has it; same timeouts, same error messages.
**Wwise stays out** (its EULA; the Launcher needs an account), so
`runtime_settings.wwise_root` adds a Settings field (`wwise_root`) and
`wwise.detect_wwise_root` (newest supported `Wwise*` under Program Files'
`Audiokinetic` with a console inside) after the env vars; the home page warns
in the `.exe` while it is missing, as does the installer's `FinishedLabel`.
**When none is usable the Wwise row says what IS there** ("tenho o wwise
instalado mas não está a ser detetado"; it used to read "ROCKFORGE_WWISE_ROOT
is not set"): `find_wwise_installs` lists every `Wwise <year>…` folder under
the Audiokinetic folders of Program Files and of every drive (`_search_bases`),
any `Wwise…` folder up to two levels under each drive's root (`scan_drive`,
"I:\Rocksmith\Wwise_2025.1.11.9262" was the user's; system folders skipped,
at most 3000 folders listed per drive, remembered 5 min) and the registry's `WWISEROOT`
(`_registry_wwiseroot` — the installer writes it, a process started earlier
does not see it), and `diagnostics._wwise_not_found` names a version without
a template (the Launcher installs the newest, 2024/2025, by default — only
2019-2023 have one, as in DLC Builder), one installed without its Authoring
console, or nothing found (then the Definições → Geral → Pasta do Wwise
field). A folder set by hand or by `WWISEROOT` whose name carries no
supported version reads as NOT found too (`WwiseWemConverter.version()`): its
console is there, but the build would fail for want of a template. Whether a 2024/2025 WwiseConsole could convert with a migrated 2023
template is untested, so they are refused, not guessed. Guarded by
`test_a_wwise_that_cannot_be_used_is_named_not_reported_as_unset` and
`test_wwise_is_found_in_a_folder_of_the_users_choosing`; the
user's actual install was not seen from here.
**`WWISEROOT` is not final, and a failed conversion is not "no Wwise"**
("It keeps saying that I don't have WWise installed when I do", a user,
2026-10-17). `runtime_settings.wwise_root`: the folder set in Definições or
`ROCKFORGE_WWISE_ROOT` wins as before; the Launcher's `WWISEROOT` — which it
points at whichever version it set up last, often the 2024/2025 — is taken
only when it is usable (console + a supported version in its name), else the
search runs and `WWISEROOT` is kept only when nothing usable exists (so the
diagnostics can name it). And `NativePsarcPacker` used to swallow a failed
`convert` into a log while `gp_pipeline` warned "no local Wwise installation
found": `PackagingResult.wem_error` now carries the conversion's own error,
the warning says the conversion failed with it, the worker stores
`params["psarc_has_audio"]`/`["wem_error"]` (`JobOut.psarc_has_audio`/
`wem_error`), and "Antes de usar" shows "PSARC sem som" — with Wwise's error,
or "no usable Wwise" — instead of "PSARC jogável gerado" for a silent `.psarc`,
with a button to Definições → Software. Guarded by
`test_the_launchers_wwiseroot_on_another_version_does_not_hide_a_2023`,
`test_bundle_survives_wwise_failure` (the error kept) and
`test_a_psarc_built_without_sound_says_so_and_why` (each mutation-checked); the
row with Playwright on a real rebuild (PT/EN). The user's machine was not seen,
so which of the two hit them is their Definições → Software row to tell.
The diagnostics rows' install lines in the `.exe` point at «Instalar
componentes extra» (`_components_install`). Guarded by `test_components.py`
(the commands in order, CUDA vs CPU, zip-slip, a repair run, the background
install switching `ml_python`, a hand-set path kept, decline, 409 off the
.exe — each mutation-checked), `test_the_exe_converts_on_the_components_python_through_the_runner`
(the real runner on another process), `test_wwise_is_found_where_the_launcher_installs_it`,
`test_the_installers_components_task_reaches_the_app` and
`test_spec_bundles_what_the_extra_components_install`; **the release
workflow's smoke test installs them for real in the frozen `.exe` on Windows
and uses librosa (`/detect-tempo` on a click track), PDF-to-GP5
(`/pdf/import`) and Demucs (`/separate-stems`) through it**. The UI with
Playwright on a server dressed as the `.exe` (fake download/run: notices,
install with log, card, PT/EN, 760 px).

### A star on GitHub (`#starBtn`, `shouldAskForStar`)

"ao lado do buy me a coffee, uma forma de os utilizadores atribuírem uma
estrela no github … sem ser muito invasivo" (2026-10-17). A "Dar uma estrela"
link beside the coffee one in the home top bar (icon-only under 900 px, like
it) and in Definições → Geral → Apoiar o projeto, both `data-star-link` to
the repository. The ask is a home notice (`renderHomeNotices`), shown only
when NO other notice is up, only once `jobsCache` holds a completed project
(the user chose "after the first project"), never on the day of first use
(`rf-first-seen`, set on the first load — an existing user upgrading is
"first seen" that day too), and at most twice: "Agora não" stores `later` and
`asks`, and it comes back once after `STAR_LATER_DAYS` (30); "Não perguntar
mais" or a click on ANY star link stores `done`. All in `localStorage`
`rf-star` — nothing is sent, and RockForge cannot know whether a star was
given, only that the link was clicked. Storage blocked = never asks.
Browser-only; verified with Playwright (PT/EN: first day none, second day
shown, "Agora não" → hidden, back after 31 days, gone after a second "Agora
não", "Não perguntar mais", the top link ending it, no project / only failed
ones → none, 760 px without horizontal scroll, no page errors).

### «Há uma versão nova» (`infrastructure/update_check.py`)

`GET /update-check` asks GitHub's Releases API (`releases?per_page=20`) at
most once an hour (`CHECK_EVERY_S`, `work_dir/update_check.json`; it was once a
day until the betas started coming hours apart — GitHub allows an anonymous
address 60 an hour; a failure backs off an hour and is just "nothing new"),
and a page left open asks the server again every hour (`loadUpdateInfo`), skipping drafts and offering pre-releases only to
someone on a pre-release (`newest_release`, `parse_version` reads PEP 440
`0.10.0b3` and tags `v0.10.0-beta.4`). `install_kind`: "exe", "git" (a
checkout `start.bat` pulls — the UI shows nothing) or "source" (a zip with no
`.git`). Off with Definições → Geral → «Versões novas» (`check_updates`). The
home page notice links the release page and «Mais tarde» hides that version
(`rf-notice-dismissed` in localStorage). LEGAL.md and THIRD_PARTY_NOTICES say
this is the one contact made without a button (the install counter below only
after a yes). Guarded by
`test_update_check.py` (ordering, the beta rule, the hour's cache, the back-off,
an upgrade not trusting the old cache, git vs zip, the setting).

### Counting installs, only after a yes (`infrastructure/install_counter.py`)

"Existe alguma forma de eu saber quantos utilizadores instalaram a aplicação?"
→ "Implementa o contador opcional de instalações" (2026-10-18). GitHub shows
downloads (a re-download or a `git clone` counts like a new user) and its
traffic API needs push rights, so the app counts itself — **opt-in**: nothing is
sent before the user answers yes. The home page asks once (`renderHomeNotices`,
only when no other notice is up, before the star ask; "Sim, contar" / "Não"),
and Definições → Geral → **Contar esta instalação** (`#installCountCard`,
`#sInstallCount`, saved on change, not part of `settingsPayload`) switches it.
The answer is the SERVER's (`work_dir/install_counter.json` — not
`settings.json`, which the Definições save rewrites whole): asked once per
install, not per browser. Yes → a random `uuid4` (never derived from the
machine) and, once per version, `POST {install_id, version, kind, os}` (kind =
`update_check.install_kind`, os = windows/macos/linux/other) in a background
thread, at the answer and at startup (`_send_install_count` in the lifespan →
`send_in_background`); a failure is silent and retried on the next start
(`sent_version` only moves on a 2xx). No → the id is forgotten and
`{action: "forget", install_id}` asks the server to delete its rows. API:
`GET/PUT /install-count` (`InstallCountOut`: `available`, `enabled` null until
answered; PUT 404s when the counter is off). `config.install_counter_url`
(`ROCKFORGE_INSTALL_COUNTER_URL`, empty = off and never asked; `tests/conftest.py`
empties it, so no test can reach the network).

**The server** is its own free Supabase project "rockforge-counter"
(`fvyqytrtmctsdepyrnlm`, eu-central-1, org "Dream Teams") — not the user's other
projects. Source in the repo: `supabase/migrations/20261018000000_install_counter.sql`
(table `install_versions`, PK `(install_id, version)`, CHECKs on every field,
RLS on with NO policies and `anon`/`authenticated` revoked, so the Data API
reads nothing; `install_counts()` executable by `service_role` only) and
`supabase/functions/install-ping/index.ts` (deployed with `verify_jwt` off —
the app has no key — so it validates the body itself: a v4 UUID, a SemVer
version, the four kinds/OSes, ≤ 1 KB; service-role upsert, `ignoreDuplicates`).
`GET` on the function answers the totals `{installs, by_version, by_kind,
by_os}` — that is how the maintainer reads them (or SQL in the dashboard). No IP
is stored (Supabase's own request logs are the platform's, kept a few days).
Honest limits: anyone can post a made-up id (it is a counter, not an audit);
only installs that said yes are counted. Changing the function: edit the file
and redeploy it with the same settings. Exercised for real from the project's
own database (pg_net, which is left installed — it would not drop): record 204,
a bad id 400, a repeat one row, totals, forget → 0 rows. Guarded by
`test_install_counter.py` (nothing before a yes, only the four fields, once per
version, a new version again with the same id, a failed send retried, no =
forget + a new id next time, no URL = off, the API); with Playwright against a
local fake server (PT 1440 / EN 760 px: the question, yes → one ping, untick →
forget, no → nothing sent and not asked again; the startup ping after an update
sent once and not on the next start), no page errors.

### «Novidades» after an update (`rockforge/whats_new.py`, `GET /whats-new`)

"É importante que exista um banner à entrada da app com todas as alterações
feitas nos updates" (2026-10-17, a user's request). The changelogs ARE the
source — `CHANGELOG.md` for Portuguese, `CHANGELOG.en.md` for any other
language — so the app never says what the changelog does not.
`parse_changelog` reads each `## [<version>] — <date>` section (the unreleased
one and anything that is not a version skipped; the heading's "0.10.0 beta 14"
read by `versioning.parse_loose` with the spaces taken out), its `###` groups
and their items, a wrapped item joined onto one line, its Markdown kept.
`since(seen, current, lang)` returns the sections after `seen` up to the
running version (≤ `MAX_VERSIONS`, a build part ignored, the old PEP 440
spellings read), or only `current`'s own with no `seen`; `available` is false
when no changelog is installed (a plain `pip install`) — nothing is invented.
They sit at the repo root, and at the bundle's root in the `.exe`
(`rockforge.spec` ships both, guarded by
`test_spec_bundles_the_changelogs_for_the_whats_new_banner`).

UI: `checkWhatsNew` (once both `/version` and the first `/jobs` have answered)
compares the version with `localStorage` `rf-seen-version`: the same = nothing;
none recorded and no project = a first start, recorded silently; none recorded
but projects = someone upgrading from before this existed, shown this
version's entries; an older one = every version since. The first home notice
(`.home-notice.news`) lists them (`whatsNewHtml`; `mdInline` escapes, then
**bold** and `code` only), scrollable, until **Percebido** records the
version. Definições → Geral → Sobre → **Novidades desta versão**
(`#aboutWhatsNew`) shows this version's in the ⓘ box. Storage blocked = never
shown. The changelog entries are therefore user-facing text: write them for
the user. Guarded by `test_whats_new.py` (sections, wrapped items, the
unreleased one skipped, the range, old spellings, a downgrade, no changelog,
the real files in both languages) and
`test_whats_new_lists_the_changelog_entries_after_the_version_last_seen`;
with Playwright (PT 1440 px / EN 760 px: an upgrade from beta 12 lists 15,
14 and 13, "Percebido" records it and a reload shows nothing, the About
button, a browser with projects and no record sees this version's, no
horizontal scroll, no page errors).

## Commands

```bash
pip install -e ".[dev,psarc]"       # core + tests + cryptography/Pillow, no ML
pip install -e ".[dev,ml]"          # adds Demucs/librosa (stem separation, tone detection, per-point tempo/tuning)
pip install -e ".[dev,ml,lyrics]"   # + WhisperX (automatic lyric detection)
pip install -e ".[pdf]"             # PDF-to-GP5's converter (PDF/picture -> GP5), from GitHub
pytest                           # full suite (ML stages are faked in tests)
ruff check src tests start_standalone.py build_exe.py .github/scripts tools   # lint — must pass
                                 # (the root scripts are shipped code; rockforge.spec
                                 #  is excluded — it calls PyInstaller-injected names)
mypy                             # strict on domain/application/infra; relaxed at boundaries
python -m tools.tracking check   # the bug/fix/release registers (docs/VERSIONING.md)
```

CI runs ruff + mypy + pytest (+ ESLint on `web/app.js`, + a Docker build). All
must be green before committing. mypy is pinned (`mypy~=1.19.0`) so local matches
CI — do not bump it casually.

**Install `[psarc]`, not bare `[dev]`.** `test_psarc_packer.py` and
`test_psarc_crypto.py` `importorskip("cryptography")`, so without that extra
they skip themselves entirely — 17 tests covering the encrypted PSARC container
and the Sng2014 binary. CI installed only `[dev]` for a long time and was green
throughout while never running any of it. It now installs `[dev,psarc]`, asserts
`import cryptography, PIL` as its own step so losing the extra fails loudly, and
runs `pytest -rs` so any remaining skip is printed with its reason. A silent
skip reads as coverage, which is worse than a failure.

### Uploaded GP files are reference-counted and swept

The Guitar Pro upload lives OUTSIDE the job's work dir — `/gp/inspect` and
`/reload-gp` both write `work_dir/gp/<uuid>.gp*` — so `delete_job`'s
`rmtree(work_dir/<job_id>)` never touched it and every deleted job left its GP
behind forever. `delete_job` now removes it too, reference-counted like the
recording (`_gp_path_in_use`): a `/rebuild` or `/reload-gp` fork SHARES
`gp_path`, so deleting one of a pair must not pull the file out from under the
other. The check runs in Python over `(id, params)` rather than in SQL because
`gp_path` sits inside the JSON column and JSON-path querying differs between
SQLite and Postgres — this is a single-user app with a job list measured in
tens, so portability beats the scan.

The other half is orphans: `/gp/inspect` stores the file BEFORE the job exists
(the wizard inspects tracks first), so abandoning the wizard — or the batch
modal, which inspects one file per song — left an upload nothing would ever
collect. `_sweep_orphan_gp_uploads()` runs from the app's **lifespan** (nothing
else calls it; there is no scheduler here) and deletes only files that no job
references AND that are older than `GP_ORPHAN_MAX_AGE_S` (24 h) — a fresh upload
may still belong to an open wizard, including one left open across a restart. It
never raises: failed housekeeping must not stop the API from starting. Guarded by
`test_deleting_a_job_removes_its_gp_file_but_not_a_forks`,
`test_orphaned_gp_uploads_are_swept_but_referenced_ones_are_kept` and
`test_the_orphan_sweep_actually_runs_on_startup` (which drives a real startup,
because a sweep nothing calls is worthless).

### The work dir can move (`work_paths.rebase`, `_rebase_moved_paths`)

The database keeps every file as an ABSOLUTE path (`Job.source`, `bundle_dir`,
`psarc_path`, `params["gp_path"]`, `params["stems"]`), so after the work dir
moved — another disk, a restored backup — every earlier job pointed at the old
place: the bundle 500ed, the recording 409ed (GitHub issue #6, a user who moved
the store to a USB drive). A startup pass (`_rebase_moved_paths`, in the
lifespan before the backfills) looks for each path that no longer exists under
the CURRENT work dir by its tail — the longest tail of at least two parts
(`_MIN_TAIL`: "<job id>/bundle", "gp/<file>"; a bare file name never lands on
an unrelated file at the root) — and stores the new path only when the file is
there. A path that exists, or that matches nothing, is left alone; a Windows
path read on another system is split as Windows (`PureWindowsPath`). New paths
are still written absolute: the pass makes a move self-healing on the next
start without changing what is stored or how it is read. Never raises.
Guarded by `test_work_paths.py` (the tail, the minimum tail, Windows, the most
specific place — mutation-checked) and
`test_jobs_follow_their_files_when_the_work_dir_moves` (a real startup; fails
with the call removed).

### The database schema is frozen; drift fails loudly at startup

There is no migration tool, and `Base.metadata.create_all` creates missing
TABLES but never `ALTER`s an existing one. **This is a deliberate constraint,
not an oversight: the `jobs` schema is effectively frozen and everything that
varies lives in the `params` JSON column** — which is exactly why adding
features has never needed a migration. If a column ever is added anyway, every
query against an older database dies with a bare `no such column`, request after
request, saying nothing about why. `_check_schema` (`db/models.py`) compares the
model's columns against the real table at startup and raises
`SchemaOutOfDateError` naming the missing ones and what to do. **Detect-only on
purpose** — a hand-rolled auto-`ALTER` is a migration system in disguise, and
this app has no need of one; if that changes, adopt Alembic rather than growing
this. The check itself never blocks startup for any other reason (an inspector
that cannot read the dialect just yields nothing). Guarded by
`test_db_schema.py`.

### `Tuning` validates its own pitches (and the API range-checks them)

`Tuning` was the one pitch-carrying domain type with **no** `__post_init__`,
while `TabNote` (string/fret), `Beat` and `TempoMap` all check
theirs. Only the LENGTH of `tuning_midi` was validated at the API, so an absurd
pitch 202'd, was persisted into `params`, and only died much later inside
`struct.pack("<h", ...)` in the SNG writer — a `struct.error` with nothing
pointing back at the tuning. It now raises a plain `ValueError` (the project's
convention for a pure domain invariant) on a non-6-string tuning, a pitch
outside 0-127, or a non-finite `cent_offset`; the API's `MidiPitch =
Annotated[int, Field(ge=0, le=127)]` turns the same thing into a 422 at the
boundary, and `_reject_bad_midi` covers `/import-sync`, which takes raw JSON and
bypasses the models. Real drop/down tunings are unaffected — the guard is
against nonsense, and `test_tuning_rejects_an_impossible_pitch_at_construction`
pins a Drop C# and a Drop B as still-valid alongside the rejections.

**The recording's cent offset is one job-level value that reaches every chart**
(`GpJobSpec.cent_offset`, `params["cent_offset"]`, `RebuildIn.cent_offset` —
`None` = untouched, `CentOffset` bounds it to ±50: past that it is the next
semitone, a tuning). A Guitar Pro file carries no cent offset, so "Detetar
afinação" (`/detect-tuning`) used to measure one that the build never read —
the worker passed only `tuning_overrides`, the viewer's six "Afinação (MIDI)"
inputs fed a `tuning_midi` nothing read either, and every chart shipped
`CentOffset` 0. `_tuning_for` now applies it with or without a per-chart
tuning override; the six inputs are gone (the strings' tuning lives in "Editar
info", per chart) and the field is "Desvio da afinação (cents)" in Exportar's
"Opções da construção" (`setCentOffsetLive`, counted in "Pendente").
`tuning_midi` is no longer a rebuild or sync-state key. Guarded by
`test_the_recordings_cent_offset_reaches_every_chart` (mutation-checked) and
`test_a_cent_offset_past_half_a_semitone_is_refused`; with Playwright, -31.8
typed → rebuild → the XML and the `.psarc` manifest carry `CentOffset` -31.8.
How the game's tuner treats a large offset was not seen from here.

### API input validation: every client float is `Finite`

`Finite = Annotated[float, Field(allow_inf_nan=False)]` (`interfaces/api/schemas.py`)
is what EVERY float a client can send is typed as — never a bare `float`. JSON
carries the literals `NaN`/`Infinity`, Pydantic accepts them in a float by
default, and `NaN <= 0` is False, so the `tempo_scale <= 0` guard waved NaN
straight through: the job forked, the value was persisted into the `params` JSON
column, and the build only failed much later with an error pointing nowhere
(`_build_time_warp` propagates a NaN silently across the whole timeline).

Two paths bypass the models and carry their own guard: **multipart form fields**
(`/jobs/gp`'s `offset_s`/`lead_in_s`/`tempo_scale` arrive as strings and coerce)
and **`/import-sync`** (a raw JSON blob a hand-edited file could poison), both
via `_reject_non_finite(**values)` / `_iter_floats`.

**Rejecting NaN needs the `RequestValidationError` handler too.** FastAPI echoes
the rejected input back inside the 422 body and Starlette serializes with
`allow_nan=False`, so a refused NaN crashed the encoder and surfaced as a bare
**500** — trading a silent accept for an unexplained crash. `_validation_error`
returns the same 422 through `_json_safe`, which replaces non-finite floats with
their name. Guarded by `test_non_finite_floats_are_rejected_at_the_boundary`
(which asserts the body says "finite", i.e. that it encoded at all) and
`test_non_finite_form_fields_and_imported_sync_are_rejected`.

### A missing ML extra is a 503, caught around the CALL

`/detect-tempo` and `/detect-tuning` used to wrap the ADAPTER IMPORT in
`try/except ImportError` to raise a 503 naming the extra. That was dead code:
the adapters `import librosa` **inside** their function bodies (deliberately —
the API process must never pay for the ML stack), so the module import always
succeeds and the real `ImportError` only surfaces on the call, where the generic
`except Exception` turned it into `422 could not analyse the recording: No
module named 'librosa'`. Catch `ImportError` around the CALL, ahead of that
handler, via `_ml_extra_missing(what, exc)`. Guarded by
`test_missing_ml_extra_reports_503_not_a_confusing_422`. Any future ML-backed
endpoint must follow the same shape — an import guard at module level is
guaranteed to be dead here.

## Hard constraints (these have bitten us — keep them)

- **Python 3.11 only** (`requires-python = ">=3.11,<3.12"`). The ml/lyrics stack
  (torch<2.5 / demucs / whisperx) targets 3.11 wheels. On Windows use
  `py -3.11 -m pip ...`; the user does NOT want virtualenvs. (The old, stricter
  reason — `basic-pitch`'s `tensorflow<2.15.1` — is gone now that audio note
  transcription was removed, so this pin *could* be relaxed after re-validating
  the full `[ml,lyrics]` install.)
- **`whisperx` is pinned `<3.4`** (the `lyrics` extra). `whisperx>=3.4` pulls
  `pyannote-audio>=4.0`/`numpy>=2.1`, which directly conflicts with the `[ml]`
  stack's `numpy<2` pin — installing `[ml,lyrics]`
  together then sends pip's resolver into `ResolutionTooDeep` (it backtracks
  over the whole `transformers`/`numpy` version range and never finishes). Don't
  bump this without re-checking the `numpy` ranges of both stacks.
- **The .wem must have a seek table.** Converting through a blank Wwise project
  produces a seek-table-less Vorbis .wem; Rocksmith loads the song but plays
  silence, freezes the note highway and exits seconds in. `wwise.py` extracts the
  vendored DLC Builder template project (`wwise_templates/*.zip`, MIT) per Wwise
  version, runs `generate-soundbank`, and patches the header word at offset 40 to
  3. Do not "simplify" this back to convert-external-source.
- **Song2014 XML completeness for DLC Builder.** `ArrangementProperties.ReadXml`
  (Rocksmith2014.XML) dereferences all 32 arrangementProperties attributes
  without null checks — every one must be emitted or import throws an NRE. There
  is a test (`DLC_BUILDER_REQUIRED_ARRPROP_ATTRS`) guarding this.
- **Phrase structure ends the song.** Rocksmith ends playback at the last
  `phraseIteration`. The writer emits COUNT/default/END phrases with END placed
  after the last note, plus a closing `noguitar` section. Guarded by
  `test_phrase_structure_marks_song_end`. Don't remove the END phrase.
- **A tone change must not coincide with a note.** DLC Builder errors when a
  `<tone time>` event lands exactly on a note's time. The writer nudges each
  tone change to `TONE_SWITCH_GAP_S` (20 ms) *before* the note it starts on, but
  strictly after the previous note (halfway between them if that gap is tighter
  than 20 ms) — per-arrangement, using that arrangement's own note times. A tone
  time not on any note (e.g. an arrangement silent there) is left untouched.
  `_safe_tone_time` in `rsxml/writer.py`, guarded by
  `test_tone_change_never_lands_on_a_note` / `test_safe_tone_time_uses_gap_then_midpoint`.
- **External CLIs must not inherit stdin.** ffmpeg (and any console tool) run as
  a subprocess from the Windows `start.bat` worker inherits the console's stdin,
  goes interactive and blocks forever — the symptom is a job stuck at the
  `normalize`/lyrics-`normalizing` stage. `FfmpegNormalizer` passes `-nostdin` +
  `stdin=subprocess.DEVNULL` (plus a `FFMPEG_TIMEOUT_S` ceiling so a genuine
  stall fails loudly); `DemucsSeparator` uses `stdin=subprocess.DEVNULL` too.
  Guarded by `test_ffmpeg_normalizer.py`. Don't drop these when touching the
  subprocess calls.
- PSARC/.wem packing needs a local Wwise (Audiokinetic EULA forbids
  redistribution); RockForge only *invokes* an installed copy.
- **`Job.params` (JSON column) needs a NEW dict object on every write.** It is a
  plain SQLAlchemy `JSON` column with NO `MutableDict` tracking, so reassigning
  the *same* dict object (`job.params = params`) is a silent no-op — SQLAlchemy
  compares by identity, sees no change, and skips the `UPDATE`. The symptom is
  the worst kind: the task runs fine but every progress update after the first
  commit is lost, so the UI freezes on the first log line while detection
  actually completes (or fails) invisibly. This cost a multi-session debug. The
  async detection tasks use a `_commit_params()` helper that assigns `{**params}`
  (a fresh copy) every time. ANY incremental write to `Job.params` must copy the
  dict (`{**params}`/`dict(params)`) on assignment. See `TESTING.md` §8.
  **Copy it on READ too, before writing into it.** The session factory has
  `expire_on_commit=False`, so the dict you read IS the column's committed
  value: `params = job.params; params[k] = v; job.params = {**params}` changes
  the "old" value along with the new one, they compare equal, and nothing is
  written. Take `dict(job.params or {})` first (every detection task does; the
  build task did not, and lost the GP file's lyrics that way).

## The code review of 2026-10-18, lot 1 (BUG-0298…0308)

A review of the whole codebase (six reviewers, each finding confirmed in the
code) found these; the rules they leave behind:
- **A long task writes params through `_ParamsWriter`** (`celery_app.py`): each
  commit re-reads the row and applies only the keys the task changed since its
  last commit. Writing the task's own copy back whole erased what the API wrote
  meanwhile (a cover, "synced", tone swaps, another detection's status) — the
  JSON column rule above is necessary, not sufficient. Guarded by
  `test_what_the_user_changes_while_a_task_runs_is_not_undone`.
- **No runner imports `rockforge`**, now enforced by
  `test_no_runner_imports_rockforge` (it parses every `_*_runner.py`): the
  WhisperX runner imported the adapter, so lyric detection failed in every
  `.exe`. Its implementation lives in the runner on plain dicts;
  `whisperx_adapter` wraps it.
- **A note edit patches the note** (`_apply_note_overrides` uses `replace()`):
  the bend curve, link, fingering and pick direction stay unless the bend or
  fret changed. The popup and the clipboard read the built note's `slide_to`.
- **A sync tool that adds an anchor beside others pins the chart's ends**
  (`pinChartEnds`, used by Arrastar, Marcar, Mover seguintes, Corrigir daqui;
  `planTaps` pins the start beside a lone "Início"). The server refuses two
  corrections with the same target and names the beat a correction would fold
  (`_warp_parsed_track`), instead of TempoMap's bare error.
- **Imported params are type-checked** (`_check_imported_params`, for
  `/import-sync` and `.rfproj`), and `_to_out`/`_sync_edited` read numbers with
  `_param_number`: one bad value must never take GET /jobs down.
- **GPIF bars are found by staff** (`gpif_parser._staff_slot`): `MasterBar/<Bars>`
  holds one bar per staff, track after track (alphaTab's buildModel).
- Smaller ones: the song key is ASCII (accents folded — the SoundBank's STID is
  ASCII); the XML reader reads `<capo>` as an element; `note_unused_byte` allows
  1; a cover upload is checked by its bytes before the old one goes; the snap
  select keeps `'cursor'`.
Lots 2 and 3 (BUG-0309…0337), the rules they leave:
- **Stems belong to the recording**: "drop the previous version" carries
  `demucs_stems` only to a version with the same `source`, and rewrites the
  stem paths of EVERY version pointing into the moved folder.
- **A project with a detection running is not deleted** (`_detection_running`,
  unless `force`); `/jobs/gp` removes the recording it copied on any refusal.
- **Each bundle download is its own zip**, removed once sent.
- **Tones are checked on arrival** (`api._check_tones`: rebuild, library, rfproj).
- **External tools' output is read as UTF-8** (`HARDENED_RUN_KWARGS`, loudness,
  Wwise — which also gets `stdin=DEVNULL`); the components step limit is a timer.
- **The .exe's browser fallback restores the idle watchdog**
  (`restore_browser_idle_shutdown`) when the window could not open.
- **GP5 export**: one note per string per beat (`string_clashes`), the whole-BPM
  rounding carried bar to bar (`tempo_drift_s`), and a bar's tempo change on its
  first beat even when it is a rest (it used to need a note). `tempo_writer`
  updates every tempo change on the corrected bar's first beat on every track.
- **The viewer drops late responses of another project** (`staleFor`, a
  `waveToken` for decodes), clears the selection and `neLast` on a tab change,
  and wires the merge grid once (by delegation on the card).
- **The song key is unique** (BUG-0337, decided with the maintainer
  2026-10-19): a name of ≤ `SONG_KEY_MAX` (30) ASCII letters is its own key,
  as always; a longer one keeps its first 24 and ends in 6 hex of a SHA-1 of
  the whole cleaned name, and one with no ASCII letter is "RockForge" + that
  hash (it was "RockForgeSong" for every Cyrillic title). Only those songs got
  a new key — new persistent IDs, so their in-game progress starts over, and
  a new `.psarc` name ("Instalar no jogo" removes the copy it installed
  before). Guarded by
  `test_songs_whose_names_share_their_first_letters_get_different_keys` and
  `test_a_name_that_fits_keeps_the_key_it_always_had`.

**A form field that defaults to yes is TEXT, never `bool = Form(True)`**
(BUG-0340): FastAPI 0.155 — what `fastapi>=0.110` installs today — reads a bool
form field that is not sent as False whatever its default (an unticked HTML
checkbox), so the batch page's projects (no `import_mutes`) lost their palm
mutes and `/reload-gp` stopped defaulting to the file's audio. They are
`str = Form("true")` read by `jobs._form_flag` (absent = yes; true/false/1/0/
on/off/yes/no; anything else a 422). A default-NO bool field is unaffected.
Guarded by `test_a_project_whose_form_leaves_out_import_mutes_keeps_its_mutes`
(fails with the bool field back) and the two reload tests; CI had been red on
it since 2026-10-19 without anyone noticing — check CI after every push.

## Async detection tasks (the `detect_lyrics` / `detect_tones` pattern)

Both lyric and tone detection are slow (minutes) Celery tasks that follow one
deliberate pattern — copy it for any future "analyze the recording in the
background" feature:

- **Progress lives in `Job.params`, never in `JobStatus`.** They write
  `params["<x>_status"]` (e.g. `detecting`/`separating`/`ready`/`unavailable`)
  and append timestamped lines to `params["<x>_log"]`. Using `params` (not
  `JobStatus`) means a long detection never hides a COMPLETED bundle or disables
  `/arrangements`.
- **Each step commits via `_commit_params()`** (assigns `{**params}` — see the
  hard constraint above) so the UI's polling sees live progress.
- **The endpoint mutates the existing job** (sets status to `detecting`, commits,
  enqueues) and returns 202 — it does NOT fork a new job like `rebuild` does.
- **Heavy ML failure never crashes the job:** the whole task body is wrapped in
  try/except that sets status `unavailable` + a warning and returns.
- **The UI polls** `GET /jobs/{id}/lyrics` or `/detected-tones` and renders the
  log; the progress *bar* is a client-side time animation and is NOT a real
  progress signal — the log is.

## Documentation map (read these to rebuild context)

- **`.claude/skills/rockforge-i18n/SKILL.md`** — how to add visible text (in every
  language) and how to add a language.
- **`CLAUDE.md`** (this file) — architecture, every feature's design, hard
  constraints. The single source of truth for *why* the code is shaped as it is.
- **`LICENSE`**, **`THIRD_PARTY_NOTICES.md`**, **`LEGAL.md`** — the MIT licence,
  the origin and licence of everything third-party, and the legal notice (PT/EN).
- **`README.md`** (English) + **`README.pt.md`** — the public home page: what
  it does and does not do, what to install, how to start, the documentation
  table, the PayPal button. Short on purpose; the detail lives below.
- **`docs/TECHNICAL.md`** + **`docs/TECNICO.md`** — install, run, configure,
  build the `.exe`/installer, Docker, external software. (They were the
  READMEs until the public release.)
- **`CHANGELOG.md`** + **`CHANGELOG.en.md`** — what changed per version, same
  entries in both; new entries go under "Por lançar"/"Unreleased".
- **`CONTRIBUTING.md`**, **`SECURITY.md`**, `.github/ISSUE_TEMPLATE/`,
  `.github/FUNDING.yml` — bilingual community files (the PDF-to-GP5 pattern).
- **`docs/GUIA.md`** + **`docs/GUIDE.en.md`** — the user guide: how to work
  with the app page by page, in the UI's own words (each language quotes the
  labels of its own interface — check them against `web/i18n-en.js`), plus
  common problems. When a visible workflow changes (a page, a button's name, a
  new step), update both in the same change.
- **`TESTING.md`** — how to run/extend the test suite, the coverage map, and the
  manual end-to-end checks CI cannot do (ML, Wwise, DLC Builder, in-game).
- **`docs/VERSIONING.md`** + **`docs/RELEASE_PROCESS.md`** — version numbers,
  the bug/fix/release registers in `tracking/` and how a version is published.
- **`TODO.md`** — done (`[x]`) and proposed (`[ ]`) features + current known
  limitations.
- **`TONE.md`** — deep dive on the tone-gear model and the `.rs2dlc` `Tones`
  serialization.
- **`docs/RELATORIO-TECNICO.md`** + **`docs/research/`** — the sourced grounding
  behind every technical/feasibility claim.

## Testing approach

**See `TESTING.md` for the full guide** (coverage map, how to add tests, manual
end-to-end checks, debugging the async tasks). In short: ML/Wwise/external tools
cannot run in CI, so tests inject fakes at the port boundary — a Python-based
fake WwiseConsole (`test_wwise.py`), a fake GP parser + packager (`test_gp_pipeline.py`),
stubbed Celery enqueue + per-test SQLite (`test_api.py`). When you add an
adapter, add a fake-driven test at the same boundary rather than mocking deep
internals. `pytest` + `ruff check src tests` + `mypy` must all be
green before committing.

## Running locally (Windows, native, no Docker)

`start.bat` launches Redis (Memurai) + Celery worker (background) + the API
(foreground) from a single window; it auto-selects `py -3.11` (or a 3.11 in
its python.org/winget install folder, and says so plainly when only another
version exists). **No Redis is not an error**: it sets
`ROCKFORGE_WORKER_MODE=inprocess` and runs the tasks inside the API, as the
`.exe` does — Memurai needs admin rights to install, which a work laptop may
refuse. The file runs with delayed expansion: no `!` in a command line. Requires ffmpeg
(`winget install ffmpeg`) and a running Redis. See `docs/TECHNICAL.md` for the full guide.
Before that it runs `git pull --ff-only` and restarts itself (`--atualizado`:
cmd reads a .bat while running it, so the pulled version must be re-read),
`pip install -e ".[ml,lyrics,psarc,youtube]"` only when `pyproject.toml`
differs from `logs\pyproject.installed` (the ML resolve is slow), then the
`[pdf]` extra in a step of its own that only warns (see the PDF import), refuses a
busy port 8000, and opens the page in Chrome when installed (same as
PDF-to-GP5's `start-casa.bat`). `.gitattributes` keeps `*.bat` CRLF: cmd
mis-reads labels/`goto` in LF files.

### Shutdown on tab close (`ROCKFORGE_IDLE_SHUTDOWN_S`)

`start.bat` sets `ROCKFORGE_IDLE_SHUTDOWN_S=15`: the web UI calls `POST
/heartbeat` every 4s while its tab is open; a background watchdog
(`_idle_shutdown_watchdog` in `interfaces/api/app.py`) decides via the pure
`_should_shutdown(...)` helper (unit-tested). The real close signal is the
`POST /closing` beacon on `pagehide` (tab close/navigate), which arms a
`CLOSE_GRACE_S` (~3s) deadline; a following **visible** `/heartbeat` (a refresh
that came back) clears it, so a refresh survives while a genuine close exits
after ~3s. Only a VISIBLE heartbeat cancels the close: on tab close the browser
fires `visibilitychange→hidden` (which beacons `/heartbeat?hidden=1`) *before*
`pagehide` (which beacons `/closing`), and the two beacons race on the server —
if a hidden heartbeat cleared `_closing_at` it could cancel the very close it
precedes, so the tab would never shut the server down (this regressed once).

**Work in flight defers the shutdown (the standalone `.exe`).** In `inprocess`
mode the worker runs in the API's OWN process, so exiting on a closed tab
aborted whatever it was doing — a build, or a 20-minute Demucs separation — and
left that job stuck at `RUNNING` in the database with nothing left to finish it.
`_should_shutdown` now takes `work_in_flight` and defers ALL THREE triggers
while it is true; the close reason is remembered and applied the moment the
queue drains, so closing the tab lets the work complete and the bundle is there
on the next launch. `inprocess.work_in_flight()` counts tasks that are **queued
as well as running** — the pool holds one worker, so a rebuild can sit behind a
separation, and exiting between the two would lose the queued one. Every heavy
stage is bounded by its own timeout (`DEMUCS_TIMEOUT_S`/`WHISPERX_TIMEOUT_S`/
`FFMPEG_TIMEOUT_S`), so this cannot defer forever. `_work_in_flight()` returns
False under **Celery**, deliberately: that worker is a separate process which
survives the API exiting, and a job left at `RUNNING` there is a stale row from
a dead worker — waiting on it would hang shutdown forever. `inprocess.shutdown()`
(which existed with no caller) is now wired to the lifespan teardown.

**Do NOT treat missing heartbeats as "closed."** A backgrounded/minimised tab
has its JS timers throttled or frozen by the browser, so its heartbeats stop
even though it's still open — treating that 15s silence as a close (the old
behaviour) killed the API out from under an idle-but-open tab, and every
subsequent rebuild/delete silently failed. Two guards fix this:
- The UI marks the tab hidden via Page Visibility: `ping(document.hidden)` sends
  `POST /heartbeat?hidden=1` (a `sendBeacon`) on `visibilitychange`, and
  `/heartbeat` sets `_tab_hidden`. While `_tab_hidden`, the idle-kill is
  suspended — only `/closing` (real close) or the long `HEARTBEAT_MAX_S`
  (30 min, crashed-browser safety net) stops the server.
- The watchdog resets its clock when a poll gap exceeds `SUSPEND_JUMP_S` (5s),
  i.e. the process was frozen by system sleep — waking never finds a dead
  server. `pageshow`/`visibilitychange→visible` also re-ping immediately.

So: the server stops on a real tab close (~3s) or after 30 min with no signal at
all, but never merely because you left an open tab backgrounded or the machine
slept. The foreground uvicorn then exits, and `start.bat`'s cleanup (after the
`uvicorn` line) stops the Celery worker and any Redis it launched too. Default
is `0` (disabled) — required for shared deployments (docker-compose) where one
user's closed tab must not stop the service for everyone.

`start.bat` runs uvicorn **without `--reload`**: the reloader's parent/child
split would fight the SIGTERM (the child gets restarted instead of exiting), so
a single uvicorn process is used for a clean tab-close shutdown. It also opens
the browser automatically — a background PowerShell one-liner polls port 8000
and launches `http://localhost:8000` once the API accepts connections.

## Versions, bugs and releases (`docs/VERSIONING.md`, `docs/RELEASE_PROCESS.md`)

"Implementação de um sistema profissional de versionamento e gestão de bugs"
(2026-10-17). What exists, so nobody rebuilds it:

- **The version is written once**, `rockforge.__version__`, in Semantic
  Versioning (`0.10.0-beta.12`; until then it was the PEP 440 `0.10.0b12`).
  `pyproject.toml` reads it (`dynamic`); `installer.iss` and the changelog
  headings are copies `tests/test_release_version.py` holds equal.
  `rockforge/versioning.py` parses, orders (dev < alpha < beta < rc <
  release), converts to PEP 440 and decides what may come next
  (`allowed_next`: nothing skipped, nothing back); `update_check` uses it and
  still reads the old spellings.
- **The build is not the version**: `rockforge/build_info.py` — the `.exe`
  reads the `build_info.json` `rockforge.spec` writes (commit, CI run, time), a
  git checkout asks git, a zip knows only the version. Shown in `/version`
  (`full` = `0.10.0-beta.12+ci.57.<commit>`), the home page's tooltip,
  Definições → Geral → **Sobre o RockForge** (`renderAboutCard`), the first lines
  of every log and the diagnostic report.
- **Registers, in the repo** (`tracking/bugs.json`, `fixes.json`,
  `releases.json`; the user chose the repo over GitHub Issues): permanent ids
  `BUG-0001…`/`FIX-0001…`, every field the spec asked for, `"pending"` for any
  fact not known. `tools/tracking.py` holds the rules (ids contiguous, allowed
  status transitions, Fixed needs a fix with commits, Verified needs a passed
  test or a manual/user check, Closed needs a published release, both sides of
  a bug↔fix link, found-in before fixed-in) and `check_commits` confirms with
  git that each fix is an ancestor of its version's commit — CI checks out the
  full history for it. `BUG_LOG.md` (index), `bugs/<module>.md` (one page per
  module: a single file was 600 KB), `FIX_LOG.md`, `RELEASE_LOG.md` are
  generated (`render`) and a stale one fails the check. What a release fixed and
  carried is DERIVED, never written twice.
- **The whole history is in it** (the user chose "todo o histórico"): 294 bugs
  rebuilt from CHANGELOG, CLAUDE.md and every commit since 2026-06, deduplicated
  by commit; statuses from the evidence — Closed only with a test that passed
  on re-run (2026-10-17), a documented manual check or the user's confirmation,
  in a published release; 95 stay Fixed (no verification on record). Release
  commits come from the release workflow's run history (beta 7 was published
  on 2026-10-16 from 7ca9153, not from the commit that set its number; betas
  2-9 have lost their tags and GitHub releases; beta 3's run is not recorded).
- **The gate**: `tools/release_check.py` (in `decide`, before anything is
  built): versions and changelogs in step, release notes, registers clean, no
  fix left unassigned, then by stage — beta: no open Critical; rc: no open
  Critical/High/P1 and the line's Critical/High fixes verified; stable: follows
  a published RC with no fix of its own, every fix of the line verified. Only an
  `exceptions` entry in the version's record lets a bug through.
  `tools/bump_version.py` writes the number everywhere, closes the changelogs'
  unreleased sections, assigns unreleased fixes, adds the release and runs the
  gate; `--published` records the date and tag commit afterwards.
- **Technical log** (`rockforge/app_logging.py`): `<work>/logs/rockforge.log`
  (API + in-process worker; configured in the lifespan, because uvicorn
  resets its own loggers at start) and `rockforge-worker.log` (Celery's
  `after_setup_logger`), 2 MB × 5, `ROCKFORGE_LOG_LEVEL`, a request id per
  request (`X-Request-ID`; `request.state` carries it to the error handler, which
  runs outside the middleware), unhandled errors logged with the traceback and
  answered `{"detail", "error_id"}`; `redact` strips the API token, credentials,
  `password=`/`token=` values and the account name in paths. The `.exe`'s
  console goes to `logs/console.log` (three runs kept); `start.bat` keeps
  `worker.prev.log`. `GET /diagnostic-report` = build + system + external
  software + log tails, redacted, in English.
- **No management UI**: the registers are files a single maintainer edits with
  `tools.tracking`; a dashboard would be code to keep with nothing it adds.

Guarded by `test_release_version.py`, `test_build_info.py`,
`test_app_logging.py`, `test_tracking.py` (the real registers + every rule on
invented ones + the gate + the bump) and `test_spec_records_which_build_the_exe_is`;
the About card and the copy with Playwright (PT/EN, no page errors).

## Licence, third-party notices and the legal notice

RockForge is MIT (`LICENSE`). Everything taken from another project is listed
in **`THIRD_PARTY_NOTICES.md`** with where it came from and its licence:
vendored files (the Wwise templates, gear catalogue, default tones, `.flat`
schema and lyric glyph table from Rocksmith2014.NET; three.js), code ported
from Rocksmith2014.NET / the Custom Song Toolkit / alphaTab (MPL-2.0 — see the
note there), the Python dependencies (PyGuitarPro is LGPL-3.0, certifi
MPL-2.0) and the external programs and online services. **`LEGAL.md`** (PT/EN)
is the user-facing notice: not affiliated with Ubisoft, no songs or Ubisoft
content inside, copyright of what users create is theirs, the terms of
Songsterr/YouTube/LRCLIB/covers apply to whoever presses the button, no
warranty, and a good-faith takedown contact. Both home pages summarise it in
"Licença e avisos"/"Licence and notices", and the technical docs in
"Avisos legais"/"Legal notices" and "Licença"/"Licence".

**When you vendor a file or port code from another project, add it to
`THIRD_PARTY_NOTICES.md` in the same commit** (and to `VENDORED` in
`tests/test_legal_files.py` for a file): the MIT notices of what we copy must
travel with every copy. `build_exe.copy_legal_files` puts `LICENSE`,
`THIRD_PARTY_NOTICES.md` and `LEGAL.md` beside `rockforge.exe`, so the portable
zip and the Inno Setup installer (which also shows `LICENSE` before installing)
carry them. Guarded by `tests/test_legal_files.py`.

**Code ported from alphaTab (MPL-2.0, file-level copyleft) lives in files of
its own, headed with the MPL notice:** `gpimport/playback.py` and
`domain/alphatab.py`. Keep it that way — porting more alphaTab logic means a
new MPL-headed file (or one of these two), never MPL code inside an MIT file;
reading the GP file FORMAT the way alphaTab does is not porting. The Wwise
`.bnk` layout (`soundbank.py`) was first read from the Custom Song Toolkit,
which carries no licence; it is the same layout, field for field, that
Rocksmith2014.NET publishes under MIT (`SoundBank.fs`, compared 2026-10-15),
and that publication is what the file relies on.

### Publishing a release (`.github/workflows/release.yml`)

"Quero distribuir pelo público" (2026-10-15). **A version bump on `main`
publishes itself** ("Precisava mesmo que conseguisses fazer os releases e as
tags, automaticamente", 2026-10-16 — this session's git proxy refuses tag
pushes and API writes, both tried): the workflow also runs on `workflow_run`
of CI, and its `decide` job, when CI passed on a push to `main`, reads
`installer.iss`'s version and, if `v<version>` has no tag yet, has the Windows
job create the release WITH its tag on that commit (`gh release create
--target <sha>`; a tag made with GITHUB_TOKEN starts no second run). A commit
that does not change the version finds the tag and does nothing;
`concurrency: release` queues a second CI run on the same unreleased version
until the first has made the tag. **So bumping the version IS publishing — and
deciding WHEN to bump is Claude's job** (the user's rule, 2026-10-17, refined
2026-10-18: "Não faças sempre bump. Se não for uma alteração importante para
corrigir alguma coisa, prefiro juntar mais alterações e depois fazer bump."):
bump right away only for an important FIX (a bug that breaks or misleads the
user — a crash, a wrong build, a feature that does nothing); anything else (a
new feature, an improvement, a small fix, docs) goes to `main` under the
changelogs' "Por lançar"/"Unreleased" with its fix records unassigned, and is
released together with later changes — when an important fix ships, or when
the user asks. Each reply says whether it bumped and why, or that the change
waits for the next version. The number follows docs/VERSIONING.md
(next beta/RC/PATCH/MINOR/MAJOR, the stage's criteria), written with
`tools/bump_version.py`. A pushed tag `v*` or a manual
run still work as before. The `decide` script was run locally for each event
(new version, existing tag, failed CI, pushed tag, dry run); the GitHub run
itself is the next bump. The Windows job builds the downloads on
`windows-latest` — nobody builds them by hand: installs
`[psarc,desktop]` + PyInstaller, bundles an **LGPL** ffmpeg from
BtbN/FFmpeg-Builds (release branch, newest; its `LICENSE.txt` and a
`SOURCE.txt` naming the exact version and source commit go into `ffmpeg/`,
which `rockforge.spec` bundles whole; a build whose `-version` says
`enable-gpl` fails the run), Inno Setup via choco if missing,
`build_exe.py --zip --installer`, then **`.github/scripts/smoke_exe.py` starts
the FROZEN `rockforge.exe`** (PATH stripped of other ffmpegs) and checks the
page and `app.js`, that `/system-check` finds the bundled ffmpeg, and makes a
real project (an invented one-bar GP5 + a sine from that ffmpeg) whose build
completes and whose `/psarc-check` is clean — the frozen app has failed before
in ways no test of the source sees. Only then: `RockForge-<v>-Setup.exe`,
`-portable.zip` and `SHA256SUMS.txt` go to the GitHub Release (created as a
pre-release for a `-beta.N` tag, text `docs/RELEASE_NOTES.md` — **only what
is new and the bugs fixed in that version, English then Portuguese, nothing
else**: the user's rule for every bump, 2026-10-16). A manual run
(workflow_dispatch) is a dry build whose files stay as artifacts. The tag must
equal `installer.iss`'s version, and `tests/test_release_version.py` keeps
`installer.iss` and `__version__` (both `0.10.0-beta.17`, SemVer; pyproject
reads `__version__`) and both changelogs' `## [0.10.0 beta 17]` in step. Since
the versioning rules (below) `decide` also runs `tools/release_check` before
building and never publishes a `-dev.N` version. `[pdf]` and the ML stack
are not in the `.exe`; the README says which three extras need the source
install. The smoke script was checked here against the source server dressed
as a fake `.exe`; the Windows run itself only happens on GitHub. **Its first
run caught a real defect**: `rockforge.spec` listed the package's data files
by hand and missed `gear/default_tones/*.json`, so in the `.exe` every project
without tones of its own built no `.psarc` (`FileNotFoundError` in
`default_tones._load`, the job still "completed"). The spec now walks every
non-`.py` file of the package, guarded by
`test_spec_bundles_every_data_file_of_the_package_at_its_package_path`
(fails on the old spec), and the smoke test fails with the job's warnings when
no `.psarc` came out.

## Conventions

- **Polyglot: every visible text in every language, in the same change** —
  Portuguese written in the code/markup, each other language in
  `web/i18n-<code>.js`, server text via `tr(pt, en, …)`. Use the
  `rockforge-i18n` skill (`.claude/skills/rockforge-i18n/SKILL.md`);
  `tests/test_i18n.py` enforces it.
- **Bump only for an important fix; otherwise gather changes** (the user's
  rule, see "Publishing a release"): a non-urgent change goes under
  "Por lançar"/"Unreleased" and waits for the next version; say in the reply
  which it was.
- **Every bug goes in the register, every fix gets a `FIX-` record** (the
  section below). Never mark a bug Verified/Closed without the evidence, never
  write a test result that was not seen.
- Keep the honesty: surface warnings via the pipeline's `warnings` list, never
  invent metadata, label confidence explicitly.
- Match surrounding code style. The codebase comments only to state non-obvious
  constraints (often citing the research doc section), not to narrate.
- **Errors: typed at port boundaries, `ValueError` for internal invariants.** A
  pipeline-stage adapter (an `application.ports` implementation) raises the
  matching `RockForgeError` subclass (`IngestionError`/`NormalizationError`/
  `SeparationError`/`PackagingError`) so the use case/API can map the failing
  stage; a pure `domain/` invariant or a fixed-spec binary parser/writer
  (`packaging/psarc` SNG/container/crypto) raises a bare `ValueError`. Full rule
  in `domain/errors.py`'s module docstring.

## Working method (how to make changes here)

A short playbook for working in this repo. It complements the hard constraints
above; when the two conflict, the constraints win.

- **Plan non-trivial work first.** For anything 3+ steps or with an
  architectural decision, write the plan down (`tasks/todo.md`, checkable items)
  before editing, and adjust it as you learn. Simple, obvious fixes skip this —
  don't over-engineer.
- **Use subagents to keep context clean.** Offload research, codebase mapping,
  and parallel analysis to subagents (one focused task each). Before deleting a
  module, have a subagent (or a grep sweep) map its full surface — *this repo
  shares symbols across "separate" modules* (e.g. `PipelineResult` lived in the
  audio `pipeline.py` but was imported by `gp_pipeline.py`), so "only X imports
  it" must be verified, not assumed.
- **Verify before calling it done.** Never mark work complete on a green
  typecheck alone. Run `pytest` + `ruff check src tests` + `mypy` (all three
  green — the hard rule), and for a behavioural change exercise the actual path
  (drive the endpoint / `node --check` the inline UI JS / diff behaviour vs the
  previous version). If tests fail, say so with the output.
- **Prefer the elegant, minimal-impact change.** Find the root cause, not a
  patch over it; touch only what's necessary and match the surrounding style, so
  a change introduces no new side effects. If a fix feels hacky, redo it properly.
- **Fix reported bugs autonomously.** Point at the failing test / error / log,
  diagnose, and resolve it without asking for hand-holding — then verify.
- **Capture lessons after a correction.** When the user corrects a mistake,
  append the pattern (and the rule that prevents it) to `tasks/lessons.md`, and
  skim that file at the start of a session. Ruthlessly iterate so the same
  mistake doesn't recur.
