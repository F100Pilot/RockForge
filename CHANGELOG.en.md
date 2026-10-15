# What's new

**Português:** [CHANGELOG.md](CHANGELOG.md)

The changes in each version. Every entry is also in Portuguese, in `CHANGELOG.md`.

## [Unreleased]

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
