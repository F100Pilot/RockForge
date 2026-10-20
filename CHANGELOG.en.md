# What's new

**Português:** [CHANGELOG.md](CHANGELOG.md)

The changes in each version. Every entry is also in Portuguese, in `CHANGELOG.md`.

## [Unreleased]

### New

- **Score:** with no mode selected, clicking a note takes the cursor to it, and the fretboard shows and picks it ("All notes").
- **Sync:** the song start, the corrections, sections, tone changes, lyrics and intro silence now adjust to the millisecond (three decimals).
- **3D highway — bends:** a bend now shows in teal. The note's trail rises following the bend (up, held, released, pre-bend) and, when the note reaches the strings, it rises on the string as it is bent, up to a dashed frame at the height the bend has to reach — a whole step rises one string gap.

### Fixes

- **Work folder moved:** after moving RockForge's data folder (to another disk or computer), earlier projects could no longer find their bundle, recording, GP file and stems. On start, RockForge now looks for them in the new folder.
- **Arrangement with no notes:** when the GP track picked for an arrangement has no notes (a vocal, drum or empty track), the error now says which arrangement and which track, and what to do, instead of just "arrangement has no notes".
- **Fretboard — "Only those matching the picked one":** with no note picked, it showed every note on the neck. Now only the equivalents of the picked note show (picked on the neck or clicked on the score), and nothing until you pick one.

## [0.11.1 beta 1] — 2026-10-20

### New

- **Fretboard — All notes:** a new switch beside "Fretboard" names every note of the track's tuning. Click a note to see where else the same sound is, and the same note in another octave. You can show the name with or without the octave, and only the notes matching the picked one or only naturals.
- **Tones:** you can now change when a tone comes in. Drag the change's orange mark on the score, type the seconds in the "Tones of each track" list, or put the cursor in place and press "= cursor".

### Fixes

- **Batch (album):** projects created in a batch bring the score's palm mutes and dead notes again. With the newest versions of one of the app's libraries they were silently dropped.
- **Sections:** sections you edited now follow a sync correction made before the same rebuild, like tone changes. Before, the notes moved and the section stayed at the old time. "+ Add at cursor" puts the section exactly where the cursor is, even with a correction pending.
- **Tones:** a tone change now follows a sync correction made before the same rebuild. Before, the notes moved and the switch stayed at the old time.
- **Rocksmith:** two songs whose names start with the same 30 letters (two live versions, say) no longer replace each other in game, and neither do titles with no Latin letters (Cyrillic, Japanese…). Note: these songs get a new identifier when rebuilt, and the game starts their progress over. Songs with short names do not change.

## [0.11.0 beta 4] — 2026-10-18

### Fixes

- **Projects and files:**
  - A track named "Lead/Rhythm" no longer goes into both arrangements (the build failed).
  - A .gp file locked in Guitar Pro is refused with a message instead of an internal error.
  - A refused new project no longer leaves its recording behind on disk.
  - A project can no longer be deleted while a detection or separation runs on it.
- **Imported score:**
  - A slide in at fret 1 no longer turns an earlier note into a slide lasting seconds.
  - Trills keep their fingering and their final slide.
  - The capo no longer pushes slide targets past fret 24.
  - A GP7 lyric line on a bar that is never played no longer appears at the start.
- **Export to Guitar Pro:**
  - Very fast notes on the same string no longer break the file.
  - Rounding the BPM no longer builds up drift, and the tempo of bars without notes is no longer lost.
  - A tempo correction wins over a tempo left on another track.
- **Lyrics:**
  - UltraStar syllables of one word are joined.
  - An LRC line with several times is sung at each of them.
- **DLC Builder:** a half-step bend and a fully muted chord are now written in the XML.
- **Versions:** when dropping the previous version, the separated instruments go only to a version that uses the same recording, and sibling versions still find them.
- **Downloads:** two bundle downloads at once no longer break it.
- **Tones:** a tone with invalid values is refused straight away, instead of failing the build.
- **Windows:** Japanese or Cyrillic tags or paths no longer make the build fail.
- **.exe:**
  - Without WebView2, it shuts down again when the browser tab is closed.
  - Installing the components no longer hangs forever on a stalled download.
- **Editor:**
  - The note selection and ↑/↓ no longer carry over to the other track.
  - Opening another project quickly no longer shows the previous one's score or recording.
  - The 3D highway closed while loading no longer starts.

## [0.11.0 beta 3] — 2026-10-18

### New

- **Merge two tracks: choose the bars** (New project → Tracks, and Edit info). A grid of the
  song's bars says which go into the arrangement; by default only the bars where the arrangement
  has no notes — so a LEAD with few notes takes the RHYTHM's parts only where it is silent. Click,
  drag or Shift+click to choose. Experimental.

### Fixes

- **Moving notes and chords without spoiling the tempo.** Notes were moved with the "Drag" mode,
  which is a sync tool: each drag stretches the timing around it, changes the bars' BPM and does
  not let a note pass another. Now, in **Edit notes**, dragging a box on empty staff (or
  Ctrl+click) selects a chord or several notes, and dragging one of them moves them all — they can
  pass other notes and the tempo does not change. "Drag" says what it does and warns when a note
  tries to pass its neighbour.
- **What you change during a detection is no longer lost.** While "Detect lyrics", "Detect tone"
  or "Separate instruments" ran, an uploaded cover, "Mark as synced", the main chart, swapped tones
  or "Install in game" were undone by the next progress line.
- **Lyric detection works in the .exe.** It always failed, after minutes of separation.
- **A title or artist with an accent ("Canção", "Beyoncé") gets its .psarc** when Wwise is
  installed. The song's internal name is now unaccented letters only (songs with accents get a new
  internal name; install them in the game again).
- **Editing a note no longer removes its slide**, nor its bend curve, its link to the next note or
  its fingering. Pasting notes keeps the slide too.
- **The sync tools no longer fold the score** when used after setting the "Song start": "Drag",
  "Mark", "Move following", "Correct from here" and "Mark while listening" pin the start and end of
  the song. The notes after used to lose the correction and the rebuild could fail with "beats must
  be in chronological order"; now, if a correction folds the timing, the message says where.
- **The "Cursor" snap works** (it took notes to the song's last beat).
- **"Guitar Pro with the edited notes" keeps the capo.**
- **"Check PSARC" no longer reports a fault** for a song with slap, pop or tap.
- **A refused cover (too big, or not an image) no longer deletes the cover that was there.**
- **A project (.rfproj) or sync file with a wrong value is refused** naming it, instead of taking
  the home page down.
- **GP7/8 files with a piano (two staves) before the guitar** read the right track.

## [0.11.0 beta 2] — 2026-10-18

### New

- **Merge two tracks into one arrangement** (New project → Tracks, and Edit info): for a part the
  file split into two tracks — Songsterr often does this with a single guitarist — the notes of
  the second track go into the chosen arrangement. Both must have the same tuning and capo; where
  both play the same string at the same moment, the arrangement's note stays.
- **Audio bars: a line to see whether they line up.** With the mouse over the bars or the score,
  a line runs down both lanes and the bars say how far the nearest note is before or after the
  attack ("Note 20 ms before the attack", green when it hits). **Ctrl + mouse wheel** zooms where
  the mouse is.

## [0.11.0 beta 1] — 2026-10-18

### New

- **Counting installs, only if you say yes**: the home page asks once whether the install may
  count, so it is known how many people use RockForge (GitHub only shows downloads). Once per
  version it sends a random number, the version, the kind of install and the system — nothing
  about you or your songs, and the IP address is not kept. Turn it off in Settings → General →
  **Count this install**, and what was sent is deleted.
- **Export and import the project** (Export → **RockForge project (.rfproj)**; home page →
  **Import project**): the whole project in one file — the recording, the Guitar Pro file, the
  cover, every correction and, if you want, the separated instruments — to open it on another
  computer, keep a copy or send it to someone. Importing makes a new project, built again.
- **Audio bars above the score** (Score → **Audio bars**): one lane with the recording and one
  with the sound of the track's notes, on the same time axis. Where their peaks do not fall
  together, the score is out of time. The recording's bars show the **attacks** — each strike a
  narrow peak, even on a distorted guitar — or the **volume**, of what is playing, the full mix or
  a separated instrument (the guitar, the bass… and, for the attacks, the drums); the notes' bars
  follow pending corrections. Turned on with nothing separated, they first ask whether to separate
  the instruments (then they move to the track's own); **Cancel** shows the mix's volume without
  separating or analysing anything.
- **3D highway: the hand's frets light up when a note strikes the strings**, as in Rocksmith — a
  glowing rectangle around the frets the hand is in (2–5, for example), lit while the note sounds.

## [0.10.0 beta 17] — 2026-10-18

### New

- **Tones imported from a text show in a chart**, like the per-section suggestions' one: on each
  track, a strip with the tone that sounds at each moment, the sections under it and, after
  **Detect tone**, the recording's distortion above it, to compare. It shows when the answer is
  read and stays in **Tones of each track** once applied (also with the tones you mark by hand);
  clicking a part takes the cursor there.

## [0.10.0 beta 16] — 2026-10-17

### New
- **What's new after every update:** when you open a new version, the home page lists everything
  that changed since the version you last used — the same entries as these notes — until you
  press "Got it". In Settings → General → About RockForge, "What's new in this version" shows
  them again.
- **Select from the cursor to the end** (Notes ▾, or Shift+End): every note of the track from
  there to the end is selected, and in "Drag" mode dragging one moves them all. Asked for by a
  user, to line a song up from start to end.
- **One tempo** (Sync → Tempo): when the score changes tempo midway and the recording does not,
  it puts every bar of the track at the same BPM, the start where it is.
- **Guide: syncing step by step**, on a tab that was never synced (tempo, first bar, then
  lining up along the song).

### Fixed
- **Dragging a selection stretched the notes before it:** with another pending correction (the
  "Song start", for example), the notes between that correction and the selection were partly
  dragged along, and those after the selection lost the correction. Now only the selection moves.

## [0.10.0 beta 15] — 2026-10-17

### New
- **Import tones from a text** (Tones page): "Copy the request" prepares a request for ChatGPT
  (or another assistant) with the song, the tracks, the sections with their bars and times and the
  game's gear; you paste its answer and "Read the answer" shows the tones — amp, cabinet, pedals,
  racks and their settings — and where each one comes in on each track, given by bar, section or
  time. Every adaptation is shown (gear read as the closest one, a knob outside its limits, one
  tone too many on a track); "Apply" changes the tones like an edit of your own, with undo, and
  "Apply and rebuild" saves them.

## [0.10.0 beta 14] — 2026-10-17

### New
- **A star on GitHub:** a "Give it a star" button beside "Buy me a coffee" (and in Settings →
  General → Support the project) opens RockForge on GitHub. Once a first project has been built,
  the home page asks once, quietly, whether you could give it a star — with "Not now" (once more
  in 30 days) and "Don't ask again". Nothing is sent.

## [0.10.0 beta 13] — 2026-10-17

### New
- **Score legend:** the "Legend" switch (beside "Fretboard" and "3D highway") shows what each mark
  on the score means, drawn as it appears — notes, rings, tails, bars, sections, tones,
  corrections, hand position, track tabs and the recording's attacks (the orange circles and
  ticks). The "Recording attacks" card shows its four.
- **About RockForge** (Settings → General): the version and which build of it is running (the
  commit, when it was built, how it was installed), and **"Copy information for a report"**, which
  puts the build, the system, the external software found and the end of the technical log on the
  clipboard for a bug report — without passwords, tokens or your user name.
- **Technical log** in `logs/` inside the work folder (`rockforge.log`, and `rockforge-worker.log`
  for a separate worker): every line with its time, level and part of the app, rotated so it never
  grows past ~12 MB. An unexpected error now gives an id you can quote, and the same id is in the
  log. The level is `ROCKFORGE_LOG_LEVEL`.

### Changed
- **Version numbers follow Semantic Versioning**, `0.10.0-beta.13` and so on, with dev, beta,
  release-candidate and stable stages and fixed rules for what comes next (`docs/VERSIONING.md`).
  Every bug found, every fix and every release is now recorded with a permanent id in
  `tracking/` (`BUG_LOG.md`, `FIX_LOG.md`, `RELEASE_LOG.md`), the whole history included, and a
  version is only published when it meets the release criteria (`docs/RELEASE_PROCESS.md`).
- The `.exe`'s console output moved to `logs/console.log`, with the three previous runs kept;
  `start.bat` keeps the previous `logs\worker.log` as `worker.prev.log`.

### Fixed
- **The 3D highway grabbed the mouse wheel:** scrolling the page with the mouse over the 3D
  highway zoomed the highway instead. The wheel now moves the camera only after you click the
  highway; Esc or a click elsewhere lets go of it.
- **"Wwise not installed" with Wwise installed:** the `WWISEROOT` variable the Audiokinetic Launcher
  leaves in Windows often points at another version (2024/2025), and RockForge took it as final
  without looking for the 2023.1 installed beside it. Only the folder you choose in Settings is
  final now. A Wwise conversion that fails no longer says "Wwise not found" either: it shows
  Wwise's own error. And a .psarc without sound no longer shows as "Playable PSARC" in "Before you
  use it".

## [0.10.0 beta 12] — 2026-10-17

### New
- **Edit notes — drag, and change the fret with the arrows:** in "Edit notes" mode, drag a note to
  another time or string; ↑/↓ move the last clicked note one fret up or down (with Ctrl, an
  octave), and it sounds. With Shift, dragging duplicates the note or chord and moves the copy. The end of a note's tail
  can be dragged to change its length (sustain).

### Fixed
- **A deleted note kept playing until the rebuild:** the note click, the "synthesized" source and
  the fretboard played the chart as built. They now play what is on screen, pending edits included.
- **Inserting a note in a solo made a chord:** the new note snapped to the nearest whole beat,
  which in a fast solo is the previous note's. It now snaps to sixteenths at most (with Alt,
  free).
- **"Song start" after the automatic sync:** moving the start only adjusted the first stretch of
  the song. It now shifts the whole chart, keeping the corrections already made.

## [0.10.0 beta 11] — 2026-10-17

### Fixed
- **Chords "painted" top to bottom in game:** a chord with open strings and no sustain (a 0-0-0
  power chord in a drop tuning, say) went out without the chord notes the game draws it from, and
  showed as a solid block of colour. It now goes out the way DLC Builder writes it. The PSARC check
  (Export → "Before you use it") points the fault out in an older PSARC — just rebuild.

## [0.10.0 beta 10] — 2026-10-16

### New
- **3D highway with a free camera:** drag to turn the view up to 120° either way and from level
  with the highway (0°) to a view from above (90°); the mouse wheel moves closer or further and a
  double-click resets. The same axes are under "Camera", and the view is remembered.
- **Recording attacks — choose the instrument:** "Measure on" picks a separated instrument (the
  guitar by default, the bass on the Bass chart) or the mix. With nothing separated, it asks
  before measuring the mix. On a separated instrument, the faint leftovers of the others (which
  the separation leaves behind) no longer show as false attacks.

### Fixed
- **Recording attacks with an intro silence:** in a project with an intro silence the attacks
  were drawn that much late, and notes in sync sat between the ticks. The automatic sync had
  the same offset.
- **Reload GP file with the file's own audio:** the separated guitar and the tone detection of
  the old recording no longer carry over to the new version (they described another recording).

## [0.10.0 beta 9] — 2026-10-16

### New
- **Recording attacks** (Sync inspector): marks above the score where the recording has attacks
  and highlights the differences with the tab — notes with no attack nearby and strong attacks
  with no note —, with "Previous/Next difference" to get there. For tabs with the wrong rhythm.
  It measures the guitar stem when the instruments have been separated, otherwise the mix. It
  tells when something is played, not which notes; nothing in the score changes.

### Fixed
- **Long notes ring for their whole length in the preview**: the editor's note sound (each
  note's tick and the “synthesized” source) played every note as a short pick, even held ones.
  Each note now lasts the sustain drawn on the score; short notes sound as before.

## [0.10.0 beta 8] — 2026-10-16

### Changed
- **The “A new version is out” notice arrives sooner**: the app asks GitHub at most once an hour
  (it was once a day), and a page left open asks again every hour.

### Fixed
- **A cover from your computer when creating the project**: step 4 of “New project” only offered
  a result of the online search or “No cover”. It now also takes a JPEG or PNG image from your
  computer, which goes into the first build (before, only on the Cover page, after creating).
- **The `.exe` never used the GPU**: the app asked the `.exe` itself whether there was a GPU,
  and the `.exe` carries no PyTorch (it lives in the extra components' Python) — so stem
  separation and tone and lyric detection always ran on the CPU, even with an NVIDIA card. The
  question now goes to the components' Python.

## [0.10.0 beta 7] — 2026-10-15

### New
- **Sync automatically, with a variable tempo — experimental** (Sync inspector): analyses the
  recording and moves each bar to where its notes sound, letting the tempo change over the song.
  It keeps the chart's beats (it cannot read the song at double or half speed), stays as pending
  corrections one Ctrl+Z undoes, and lists the bars to check by ear (those after a rest and those
  that did not match). It can get it wrong: tested on synthetic recordings, not yet on real songs.
- **An icon of its own**: an orange guitar pick with an anvil and a spark. It shows on the
  `.exe`, the taskbar, the shortcuts, the installer and the browser tab.

### Fixed
- **No mode is selected when a project opens.** “Fix from here” was on by default, and the first
  click on a note re-timed the song; now a click only selects or moves the cursor until you pick
  a mode.
- **The black screen that flashed when clicking some buttons in the `.exe`**: it was the console
  window of each program the app runs behind the scenes (ffmpeg, the extra components' Python,
  yt-dlp…). They all run without a window now.
- **Wwise installed but “not detected”**: RockForge now also looks on every drive (up to two
  folders below the root, like `I:\Rocksmith\Wwise_…`) and at the `WWISEROOT` the Wwise installer
  writes to the registry, and when there is a Wwise it cannot use it says which and why — the
  Audiokinetic Launcher installs the newest version (2024/2025) by default, and only 2019–2023
  converts the audio (as in DLC Builder). Before, it only said “ROCKFORGE_WWISE_ROOT is not set”.
- **Short notes without a sustain tail**: every eighth and sixteenth went out with its Guitar Pro
  length as a sustain, so the game drew a tail behind every note of a riff. Now, as in hand-made
  charts, only a note of a beat or longer is sustained, unless the tail is needed (a slide, a
  linked note, a bend, vibrato, let ring, tremolo, a trill).
- **Voltas (1st/2nd time) on the return after a D.C./D.S.**: repeats were already not taken on
  that return, but the 1st ending was played again before the 2nd. It now follows the usual
  convention — no repeats, the last ending only — and, since a Guitar Pro file does not say which
  is meant, the project's warnings say that this is the one assumed.

## [0.10.0 beta 6] — 2026-10-15

### New
- **“Mark by ear”, for tabs that were never synced** (Sync inspector): press play and hit **B** on
  the first beat of every bar (or on every beat), and the notes snap to your taps as you go.
  Backspace takes the last tap back, Esc finishes; you can slow the playback down, and the taps
  are smoothed to remove the shake of the hand. They stay as pending corrections (one Ctrl+Z
  undoes them all) until “Apply and rebuild”.

### Fixed
- **In the `.exe`, the installed extra components were not used** when the “Python for ML”
  setting ended up empty: the card said everything was installed and the rest of the app that
  it was missing. RockForge now finds the components' Python by itself; a path chosen by hand
  still wins.

## [0.10.0 beta 5] — 2026-10-15

Includes what was prepared for beta 4, which was never published.

### New
- **Fret-hand position (FHP) editor.** A lane under the staff shows where the game puts the hand,
  and the new “Fret-hand position (FHP)” mode (key 0) lets you add, change (fret and width) and
  delete positions, track by track; a note outside its position gets a red ring. Your positions
  go into the `.psarc` (at every difficulty level) and the DLC Builder project; Notes ▾ → “Back
  to automatic” returns to the computed ones. The 3D highway follows them.
- **Bass arrangement.** Pick the bass track of the Guitar Pro file in the wizard (or in “Edit
  info”) and the project gains a BASS arrangement, encoded the way DLC Builder does it. A
  5-string bass is folded onto the four strings that lose the fewest notes, with a warning; a very
  low tuning (B standard) is written an octave up at 220 Hz, as DLC Builder does, so the game
  detects the notes. The score, the fretboard and the 3D highway show four strings. Not played in
  game yet — tell us how it goes.
- **New version notice** on the home page: RockForge asks GitHub's Releases, at most once a day,
  whether a newer version is out (turned off in Settings → General). Someone using `start.bat`
  with git does not see it, since that updates itself.
- **The `.exe` installs the extra components by itself**: audio analysis, tone and lyric
  detection, PDF conversion and YouTube audio. The installer offers them (ticked) and so does the
  home page; RockForge downloads a Python 3.11 of its own with the packages (PyTorch with CUDA
  when there is an NVIDIA GPU) and Deno into the account's local app data, and the uninstaller
  removes them. The PDF import now works in the `.exe`.
- **Wwise is found by itself** where the Audiokinetic Launcher installs it, or set in Settings →
  General → “Wwise folder”. The home page and the installer's last page say when it is missing
  (its licence does not allow bundling it).

### Changed
- **The automatic fret-hand positions were redone** from hand-made charts: a chord puts the hand
  where its index finger is, other notes leave the hand where it is while a finger reaches them,
  and the hand only moves at the first note it cannot reach. Against two community CDLC they
  agree on 98% of the notes (80% before), with the same number of moves.
- The XML for DLC Builder now carries the same automatic fret-hand positions as the `.psarc`
  (they used to be worked out two different ways).

### Fixed
- **In the `.exe`, the "Download" buttons did nothing** (and showed no error): the app's own
  window blocked downloads. It now opens the Save As dialog.
- **The Guitar Pro file's capo was ignored.** It is now read (GP3-5 and GP7/8): frets are counted
  from the nut, as in Rocksmith, and the arrangement carries the capo.
- **Without Wwise, the `.psarc` carried the whole WAV** (about 30 MB) where the game never reads
  it. Not any more: the audio stays in the bundle for DLC Builder and the app says Wwise is
  missing.
- A difficulty level holding only open strings had no anchor in the `.psarc` (caught by the PSARC
  check on a bass whose simplest notes are its open roots).

## [0.10.0 beta 3] — 2026-10-15

### New
- A **“Buy me a coffee”** button (PayPal) on the home page and a **Support the project** card in
  Settings → General. RockForge stays free.
- A **tutorial video** (Portuguese and English) and a GIF in the README.

## [0.10.0 beta 2] — 2026-10-15

### Distribution
- **Windows installer and portable zip** on the Releases page, built and tested automatically
  (the `.exe` starts and makes a project before it is published), with a `SHA256SUMS.txt`. They
  need no Python and carry ffmpeg (an LGPL build, with its licence and the link to its source).
- Licences made clear: the code adapted from alphaTab is in two files of its own, under MPL-2.0;
  everything else is MIT.
- Fixed in the `.exe`: a project without tones of its own made no `.psarc` (DLC Builder's default
  tones were missing from the package). Found by the automatic test of the `.exe`.

### Added
- **3D highway with Rocksmith's symbols:** the note no longer carries the fret number — the
  neck's fret number turns amber and glows as a note on that fret comes, and stays lit while it
  sounds ("Fret on the note" puts the number back on the note). The technique letters give way to
  the game's symbols: ▼ hammer-on and ▲ pull-off on the note; above it, a bow tie (palm mute), a
  ring with a dot (harmonic), an eye (pinch), a wide V (tapping), a block with a notch / with a
  peak (slap / pop) and ˄ chevrons for the bend's strength; a double frame (accent); a wavy trail
  (vibrato) and a zigzag one (tremolo picking).
- **Undo / Redo** for everything pending: sync corrections, tempo, notes, lyrics, sections,
  tones and the build options, on any page of the project (buttons in the top bar, Ctrl+Z,
  Ctrl+Shift+Z or Ctrl+Y). Before, only the last note delete could be undone.
- **Changes not yet applied are saved automatically** in this browser: closing the app before
  "Apply and rebuild" no longer loses them, and reopening the project asks whether to recover
  them.
- **Repeat a passage (A–B)** in the transport: mark A and B at the cursor (or [ and ]) and
  playback stays in that passage until you turn it off (L); the passage shows on the score.
  With the speed, it lets you hear a bit slowly until the sync is right.
- **Keyboard shortcuts in sight:** **?** (or the key button) lists them all; **1–9** pick the
  score's mode, with the number beside each one in the Mode ▾ menu.
- **Linked notes:** a Guitar Pro legato slide (the landing note not picked again) reaches the game
  as Rocksmith has it — the note runs on into the next without a new attack, in the DLC Builder
  XMLs and in the PSARC. On the score, an arc over the note. The "Guitar Pro with the edited
  notes" export writes it back as a legato slide.
- **Arpeggios:** single notes let ring over one chord shape (at least three, on three strings,
  in one hand position) now show in game with the chord's shape above them, like the arpeggios of
  the original songs. Guitar Pro does not mark arpeggios, so they are worked out; on the score
  they get an "arpeggio C" bracket underneath.
- The PSARC check ("Before you use it", on the Export page) also checks the links and the
  arpeggios.
- The project's top bar no longer draws the status over "Edit info"/"Previous version" on narrow
  screens: the status and "Pending" shrink and "Download" keeps only its icon.

### Security
- A title, tone name, section or lyric from outside (a GP file, Songsterr, LRCLIB, other
  people's CDLC) can no longer run code in the page: text is now escaped inside attributes too.
- The server only answers to `localhost`/`127.0.0.1`: a web page that points its own domain at
  your computer (DNS rebinding) is refused. Other names go in `ROCKFORGE_ALLOWED_HOSTS`. A
  request with `Origin: null` counts as coming from another site.
- Every response carries `X-Content-Type-Options: nosniff` and cannot be shown inside another
  site.
- Docker: the image now makes the `.psarc` (the `[psarc]` extra was missing).

### Fixed
- A GP8 file's audio in `.opus`, `.webm`, `.aac`, `.mp4` or `.wma` (and a YouTube download in
  those formats) was found but then refused by the build. There is now one list of formats, and
  they can be uploaded too.
- A double click on "Apply and rebuild" created two versions.
- A late answer for a project you had closed (or left for another one) reopened it; and tone/stem
  detection kept polling the new project after you switched.
- `1:60` in the length of lyrics found online and `[00:60.00]` in the exported LRC.
- A negative intro silence was accepted when creating a project and put the corrections out of
  line after a tempo change.
- The "Lead/Rhythm (exp.)" checkbox, which no longer did anything, is gone.
- **The tuning deviation reaches the game.** "Detect tuning" measured how many cents the recording
  is off A440, but the value never reached the `.psarc` (it always said 0). There is now a "Tuning
  deviation (cents)" field (−50 to +50) in Export → Build options, filled by the detection or by
  hand, the same on every track. The six "Tuning (MIDI)" numbers, which did nothing either, are
  gone: the strings' tuning is changed in "Edit info".

## [0.10.0 beta 1] — 2026-10-14

First public version, in beta: ready to use, but waiting for more testing in the game and on
a PC without Python before 1.0.0.

### Creating a project
- Guitar Pro 3, 4, 5 and 7/8 (`.gp`) files: notes, frets, techniques, tempos, sections and lyrics
  read from the file; repeats, voltas and D.S./D.C. jumps in the order they are played; a Guitar
  Pro 8 file's sync points and audio.
- No Guitar Pro file: the tab imported from a Songsterr link (with the per-bar video timings), or a
  PDF or picture of the tab converted by PDF-to-GP5.
- The recording: an audio file, the audio inside the GP8 file, or the audio of a YouTube video.
- A 4-step wizard and a batch mode for whole albums; album, year, cover and synced lyrics looked up
  online and chosen by you.

### Syncing and editing
- Song start, BPM stretch, "Fix from here", dragging notes and passages, aligning bars, per-bar
  tempo, and a main track whose corrections reach the others.
- Each track marked as synced on its own.
- Note editor (frets, techniques, insert, delete, copy and paste) and section editor on the score.
- Rocksmith-style 3D highway.

### Tones and lyrics
- Tone editor with the game's gear, a tone library, and the tones of the songs in your `dlc`
  folder.
- Per-track tones, tone changes, tone detection and a suggested tone for each part.
- Lyrics from the GP file, LRCLIB or the recording (WhisperX), lined up with the voice and editable
  beside the score.

### For the game
- A native, playable `.psarc` (with Wwise) and a DLC Builder project, always both.
- Dynamic difficulty, chord fingering and hand shapes.
- `.psarc` check and installation into the game's `dlc` folder.
- Export back to Guitar Pro: the corrected tempos in a copy of your file, or the edited notes in a
  new GP5.

### Distribution
- MIT licence, third-party notices and legal notice; home page, user guide and technical
  documentation in Portuguese and English; `start.bat` messages in both languages.
