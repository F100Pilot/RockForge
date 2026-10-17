# What's new

**Português:** [CHANGELOG.md](CHANGELOG.md)

The changes in each version. Every entry is also in Portuguese, in `CHANGELOG.md`.

## [Unreleased]

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
