# What's new

**Português:** [CHANGELOG.md](CHANGELOG.md)

The changes in each version. Every entry is also in Portuguese, in `CHANGELOG.md`.

## [Unreleased]

### Added
- **Undo / Redo** for everything pending: sync corrections, tempo, notes, lyrics, sections,
  tones and the build options, on any page of the project (buttons in the top bar, Ctrl+Z,
  Ctrl+Shift+Z or Ctrl+Y). Before, only the last note delete could be undone.
- **Changes not yet applied are saved automatically** in this browser: closing the app before
  "Apply and rebuild" no longer loses them, and reopening the project asks whether to recover
  them.
- **Repeat a passage (A–B)** in the transport: mark A and B at the cursor (or [ and ]) and
  playback stays in that passage until you turn it off (L); the passage shows on the score.
  With the speed, it lets you hear a bit slowly until the sync is right.

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
