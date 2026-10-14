# What's new

**Português:** [CHANGELOG.md](CHANGELOG.md)

The changes in each version. Every entry is also in Portuguese, in `CHANGELOG.md`.

## [Unreleased]

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
