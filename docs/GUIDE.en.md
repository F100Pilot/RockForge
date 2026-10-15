**Português:** [GUIA.md](GUIA.md)

# User guide

How to use RockForge, from the song's file to playing it in Rocksmith 2014. To install it, see
the [home page](../README.md#get-started) (in detail: [TECHNICAL.md](TECHNICAL.md)). Every tool in the app also has an **ⓘ** with its short
explanation; this guide puts it all together in the order you work. To see it done first,
watch the **[tutorial video](media/tutorial-en.mp4)** (9 min, captions and chapters).

The interface can be in English (PT/EN at the top of the home page, or Settings → General);
the names below are the English ones.

**Contents**

1. [The path in short](#1-the-path-in-short)
2. [Before you start](#2-before-you-start)
3. [The home page](#3-the-home-page)
4. [Creating a project (New project)](#4-creating-a-project-new-project)
5. [The project page](#5-the-project-page)
6. [Syncing the notes to the recording](#6-syncing-the-notes-to-the-recording)
7. [Editing notes and sections](#7-editing-notes-and-sections)
8. [Tones](#8-tones)
9. [Lyrics](#9-lyrics)
10. [Cover and song information](#10-cover-and-song-information)
11. [Export, check and install in the game](#11-export-check-and-install-in-the-game)
12. [A whole album at once (Batch)](#12-a-whole-album-at-once-batch)
13. [Settings](#13-settings)
14. [Keyboard shortcuts](#14-keyboard-shortcuts)
15. [Common problems](#15-common-problems)

---

## 1. The path in short

1. **New project**: pick the song's file (Guitar Pro, a PDF/picture of the tab, or a Songsterr
   link) and the recording, and assign the Lead/Rhythm tracks.
2. **Score**: listen to the recording with the notes on top and fix the sync. When it lines
   up, mark each track as in sync.
3. **Tones**, **Lyrics**, **Cover**: whatever you want to add (none of it is required).
4. **Apply and rebuild** whenever you change something — only a rebuild writes the changes into
   the PSARC.
5. **Export**: check "Before you use it", press **Install in the game** (or download the PSARC) and
   play.

Nothing is made up silently: whatever the app does not know or cannot do shows up as a warning.

## 2. Before you start

- **Starting:** on Windows, `start.bat` (updates, installs what is missing and opens the page),
  or `rockforge.exe`, which opens in its own window.
- **What is installed:** ⚙️ **Settings → Software** lists each external tool, whether it is
  installed and what you lose without it. Only **ffmpeg** is required. A **playable PSARC**
  needs **Wwise** (without it you get only the DLC Builder bundle); separating instruments,
  detecting tone or lyrics and "Fix from here" need the ML extra.
- **With `rockforge.exe`:** the **extra components** (audio analysis, tone and lyric detection,
  PDF and YouTube) are installed by the app: the installer offers them (ticked), or press
  **Install now** on the home page, or ⚙️ **Settings → Software → Install extra components**.
  RockForge downloads a Python 3.11 of its own with those packages into your local app data
  (about 1 GB, or 3 GB with an NVIDIA GPU) and uses it by itself; uninstalling RockForge removes
  it. **Wwise** cannot come this way (its licence does not allow it): install it with the
  Audiokinetic Launcher and RockForge finds it — or set ⚙️ **Settings → General → Wwise
  folder**.
- **For the song to show in the game:** Rocksmith needs the **CDLC patch** (`D3DX9_42.dll` in
  the game folder). Set the game folder in ⚙️ **Settings → General → Rocksmith 2014 folder**
  so the app can confirm it and "Install in the game" works.
- **Closing:** closing the window/tab shuts RockForge down. If a build is running, let it
  finish.

## 3. The home page

- Each **project** is a card with cover, title, artist and a status: ready, in progress,
  failed, "Synced" (once you marked every track) or "Standard tones".
- Filters (**All / Ready / In progress / Failed**) and a search box.
- The first card takes a dropped Guitar Pro file: it opens the wizard with it.
- At the top: **Batch (album)**, **New project** and ⚙️ **Settings**.
- Above the projects, when it applies: **a new version** of RockForge is out (**Download** opens
  its Releases page; **Later** hides it until the next one), the **extra components** are missing
  (`.exe`; **Install now** / **Not now**), or **Wwise** is missing, so the `.psarc` would have no
  sound (`.exe`; **Download Wwise** / **Hide**). Someone running `start.bat` with git never sees
  the version notice: it updates itself on every start.

## 4. Creating a project (New project)

Four steps; the bar on the left shows where you are and lets you go back.

### Step 1 — File

One of three sources:

- **A Guitar Pro file**: GP3, GP4, GP5 or GP7/GP8 (`.gp`). Notes, frets, techniques, tempo,
  bars and sections come exactly from the file. Only GP6 (`.gpx`) cannot be read — export it as
  GP5 or GP7 in Guitar Pro/TuxGuitar. Two things Guitar Pro does not say the way Rocksmith does,
  which RockForge translates: a **legato slide** becomes a note linked into the next (no new
  pick; an arc on the score), and single notes **let ring** over one chord shape (three or
  more, on different strings, in one hand position) become an **arpeggio** (the game shows the
  shape above them; an "arpeggio …" bracket on the score). To avoid an arpeggio, take the let
  ring off those notes in Guitar Pro.
- **A PDF or picture of the tab** (PNG, JPEG, WebP): converted into a GP5 by PDF-to-GP5's
  converter. Several files = one track each, in order (up to 7). Reading pictures (OCR) is
  experimental: check the notes and rhythm on the score after creating the project — the
  warnings name the bars whose rhythm was estimated from the spacing, the first ones to check.
  Once the project is created, those bars show above each track's score ("Rhythm estimated
  from the spacing"), and a click puts the cursor on that bar; a repeated bar shows once for
  each time it plays.
- **A Songsterr link** ("… or import the tab from Songsterr"): downloads the tab and writes a
  GP5 from it, lyrics included when the tab has them. Drum tracks and grace notes are left out
  (the app says how many). Published tabs only.

Press **Next** to see the tracks.

### Step 2 — Tracks

Assign a track of the file to each arrangement: **Lead**, **Rhythm**, **Combo**, and, if you
want, **Alternate lead track** / **Alternate rhythm track** (in game: LEAD 2 / RHYTHM 2). One is enough.
Leave empty the ones the song does not have.

**Bass track** takes a 4- or 5-string bass track of the file (the guitar pickers do not offer
those). Rocksmith's bass has four strings, so a 5-string bass is folded onto the four strings that
lose the fewest notes — B E A D when the part never plays the high G — and the warnings name the
strings used and count any note left out. A tuning lower than 4 semitones below standard (B
standard, say) is written an octave up with the reference at 220 Hz, as DLC Builder does, so the
game detects the notes; RockForge's score and playback still sound the real pitch. A 6-string
bass is charted as a guitar.

### Step 3 — Recording

- **The recording** (the song's audio). If the file is a Guitar Pro 8 with the audio inside,
  "Use the audio inside the GP file" is ticked — it is the most precise choice, because that is
  the audio the file was synced to.
- **Don't have the audio?** Paste the link of a YouTube video and press **Download the audio**. If YouTube
  refuses, see [Common problems](#15-common-problems). (Personal use: downloading is against
  YouTube's terms.)
- **Song start in the recording (s)**: the second the 1st note is heard. A rough value is
  enough — it is fine-tuned later on the score. Filled in for a synced GP8 and for Songsterr.
- **Intro silence (s)**: extra seconds of silence before the song in the game. 0 = none.
- **Extra — sync with Songsterr's timings** (optional): Songsterr stores the instant each bar
  starts in YouTube videos, marked by people. **Find videos**, pick one, and the notes follow
  that video bar by bar. Two conditions: the recording must be the audio of **that** video (its
  link moves to "Don't have the audio?" so you can download it) and the file must be the Songsterr tab.
  After importing from Songsterr in step 1 this is done for you: video picked and audio
  downloaded.

### Step 4 — Details

- **Title, Band, Album, Year.** Taken from the file or the audio's tags when present.
- **Album, year and cover → Search online**: lists results from iTunes and MusicBrainz; pick
  the right one (or "No cover"). Fan remixes and AI-made songs are rarely there.
- **Synced lyrics → Search lyrics online** (LRCLIB): pick lyrics with timings, or none. If the
  GP file already has lyrics, nothing is picked for you. You can also upload an **LRC** or
  **UltraStar TXT** file (it always wins).
- **Import palm mute / slap / pop / tap**: untick if you do not want those techniques in the
  chart.

**Create CDLC** creates the project and starts the build. Tones and cover can come later.

## 5. The project page

- **Top bar:** ← back to the home page; the title with **Edit info** and, after a rebuild,
  **Previous version**; the status (click to go to Export); the **keyboard shortcuts** (the key,
  or **?**); **Undo** and **Redo**; the number
  of pending changes; **Apply and rebuild**; **Download**.
- **Left bar:** the pages **Score**, **Tones**, **Lyrics**, **Cover**, **Export**, and
  **Settings** at the bottom.
- While the build runs, Export shows its progress; when it is done, the Score opens by itself.

### Apply and rebuild

Everything you change (sync, notes, sections, tones, lyrics, tuning) is **pending**: you see
and hear the result on the score, but the PSARC changes only when you press **Apply and
rebuild**. Each rebuild creates a **new version** of the project and asks whether the previous
one can be deleted once the new one is ready. If the rebuild fails, the previous one stays.

**Undo / Redo** (the arrows in the top bar, **Ctrl+Z** and **Ctrl+Shift+Z** or **Ctrl+Y**) step
back and forward through those pending changes, on any page: a sync correction, a tempo, a note
edited or deleted, a lyric word, a section, a tone. Each step is what you did between two pauses
(a whole drag counts as one). Inside a text field, Ctrl+Z undoes what you typed in it. Undo does
not go back past a rebuild: it always starts at the version that is open.

Pending changes are also **saved automatically** in this browser. If you close the app (or the
computer shuts down) before rebuilding, reopening the project asks whether to recover them.
They stay pending as before; Undo goes back to the built version.

### The Score page

- **Transport:** play/pause (or Space), time, speed (25–100 %), **repeat a passage** and
  **Audio ▾**:
  - **A** and **B** mark the start and end of the passage at the cursor (or the keys **[** and
    **]**); with both marked the passage repeats by itself, and the button beside them (or
    **L**) turns the repeat on and off. While it repeats, playback stays between A and B
    (playing from outside starts at A); paused, the cursor moves freely. The passage shows in
    purple on the score; **×** removes it. Good for hearing a bit slowly (with the speed) until
    the sync is right;
  - music and note volumes, **Tick per note**;
  - **Audio source**: the full mix; **«track» (synthesized)**, that track's notes played alone
    and clean, good for checking each track's sync; **Vocals (synthesized)**, the melody the GP
    lyrics are sung on; and, after **Separate instruments** (Demucs, takes minutes), the
    separated stems. The "guitar" stem holds every guitar: Lead and Rhythm cannot be separated
    from the recording;
  - **Preview tone**: hear the notes with the character of one of your tones (an approximation —
    the real sound only exists in the game).
- **Track tabs:** named as the game names them (LEAD, RHYTHM, COMBO, LEAD 2…), with the number of
  notes (n) and chords (c). They turn **green** when you mark the track as synced.
- **Mode ▾**: what clicking a note does (see sections 6 and 7). **Notes ▾**: copy, paste,
  delete, undo, clear edits. **Snap**: the grid dragged notes jump to (bar, beat, ½, ¼,
  triplet, or the cursor).
- **The score:** the axis is the recording's time. Clicking the background moves the cursor.
  Bars are numbered; an amber bar has its tempo changed by your corrections.
- **preview** plays only the track's notes, without the recording.
- **Fretboard** shows the guitar neck; **3D highway** shows the notes coming down as in Rocksmith (it
  follows pending corrections too). **− / + / Reset**: zoom.
- **Inspector (on the right):** **Sync**, **Sections** and **Lyrics**.

## 6. Syncing the notes to the recording

Work in this order, one track at a time (at the top of the **Sync** inspector):

### Step 1 — Song start

The second the 1st note **of this track** is heard. Three ways:

- type the value (or use the slider);
- put the cursor where the note sounds and press **= cursor**;
- **Detect 1st note**: press the button, then click the waveform where the 1st note sounds,
  and finally that note.

### Step 2 — Tempo

If the score drifts away evenly over the song (the file was written at a slightly different
BPM), change the **BPM**. The notes slide over the waveform live. **Reset to GP** goes back to the
file's tempo.

### An unsynced tab — Mark by ear

If the tab was never synced (written by hand at one tempo, on Songsterr for instance), the
quickest and most reliable way is to mark the bars yourself, in the **Mark by ear** card:

1. pick **From bar** (bar 1 starts from the beginning of the recording; any other from the
   cursor) and whether you tap **on every bar** or **on every beat** (more precise);
2. **Start marking** and hit **B** (or the big button) on the first beat of every bar while
   listening. The score follows your taps as you go;
3. **Backspace** takes the last tap back; **Esc** finishes. You can stop halfway: the rest
   keeps its own tempo and moves with the last tap.

To mark calmly, slow the playback down with the speed selector next to play. **Smooth the
taps** removes the shake of the hand. The taps stay as corrections in step 3 (one Ctrl+Z undoes
them all) until **Apply and rebuild**; then fine-tune the rest with **Fix from here**.

### Step 3 — Corrections on the score

For what is left, pick a mode in **Mode ▾** and click where the score drifts:

| Mode | What it does |
|---|---|
| **Fix from here** (recommended) | Listen until the score starts to drift and click that note. Everything before it stays put; RockForge measures the recording's tempo from there on and stretches only the rest. Repeat along the song. |
| **Drag** | Drag a note to where it should play. With several notes selected, they move as a block. Alt while dragging = no snap. |
| **Mark** | Press play and click the note the moment you hear it: it moves to the cursor. |
| **Excerpt** | Draw a box over a passage and move it as a block. |
| **Move following** | This note and all the following ones go to the cursor; earlier ones stay. |
| **Align bar** | Click a note or a bar line: line that bar up with the cursor (**= cursor**), with the same bar of another track (**= track**), or change that bar's BPM up to another bar (**Tempo**). |

Corrections stay in step 3's list (you can type each one's exact time or delete it) until
**Apply and rebuild**. A correction marked "⚠ crosses the previous one" contradicts another
and must be fixed before rebuilding.

### Mark as in sync

When the track lines up with the recording, press **Mark this track as synced** under **Sync
status**: its tab turns green. With every track marked, the project counts as in sync. A file
synced in Guitar Pro 8 or to Songsterr's timings should already line up, but only you confirm
it, by ear.

### Several tracks

- **Main track:** pick one; whatever you fix on it reaches the others as the same change of
  time (if the Lead goes from 0 to 1 s, a track that was at 30 s goes to 31 s). Each track can
  still be fixed on its own.
- **Apply the sync to all tracks:** applies the same tempo and corrections to all of them.
- **Sync by bar** (in More options): lines a bar up with the cursor or with the same bar of
  another track — useful for a track that only comes in midway.

### More options

- **Intro silence**: pushes music and notes later.
- **Reload GP file**: after fixing a note in Guitar Pro and exporting again. Keeps sync, tones,
  lyrics and tuning. If the new file carries audio, that becomes the recording.
- **Save the adjustments → Export / Import**: saves start, tempo, corrections, tuning and
  lyrics in a JSON, so you need not redo them if you recreate the project.

## 7. Editing notes and sections

### Selecting

Click = one note; **Shift+click** = a range; **Ctrl+click** = add or remove a note; click the
background = clear the selection. **Excerpt** mode selects with a box.

### Editing notes (✏️ Edit notes mode)

- Click a note: change string, fret, sustain, techniques (hammer-on, pull-off, harmonic, palm
  mute, vibrato, tapping, slap, pop, accent), bend and slide; **Save** or **Remove note**.
- **Double-click** an empty spot to insert a note (string from the click's height, time on the
  nearest grid point). Notes can only go inside the bars the file has.
- A note edited but not yet rebuilt has a dashed ring.

### Delete, copy, paste

- **Delete** (or **Delete** / Notes ▾ → **Delete selection**) removes the selected notes.
  **Ctrl+Z** undoes the delete (like any other change); **Undo delete** restores only the last
  delete, even after other edits.
- **Ctrl+C / Ctrl+V** (or Notes ▾): copy the selection and paste it at the cursor, on this
  track or another.
- Notes ▾ → **Clear this track / Clear on all** discards note edits.

### Fret-hand positions (FHP)

The **FHP** lane under the staff shows where the game puts the hand (the fret highlight and the
camera), from one position to the next: grey = worked out by RockForge, teal = yours. In the
**Fret-hand position (FHP)** mode (key **0**):

- click a **note** to move the hand there (the fret comes from its lowest note);
- click a **bar** of the lane to change its fret and width, or **Delete** it.

The first edit copies the automatic positions, so you only change the ones that are wrong. A
note its position does not cover gets a **red ring** (still playable, but worth a look). Notes ▾
→ **Back to automatic** returns to RockForge's on this track. Each track has its own; they are
pending until **Apply and rebuild** and follow the sync corrections made in the same rebuild.

### Sections (intro, verse, chorus…)

For navigation and Riff Repeater. In the **Sections** inspector: **+ Add at cursor**, or the
**Section** mode and a click on a note. Name and time are edited in the list.

### Taking the edits back to Guitar Pro

In Export: **Guitar Pro with the edited notes** writes a new GP5 with the current track only,
as it is in RockForge (times are rounded to the bar grid; the app says by how much). **Guitar
Pro with the corrected tempos** writes only the tempo changes into a copy of your file, which
keeps all its tracks.

## 8. Tones

Without tones of your own, each track gets DLC Builder's **standard tone** (Lead and Combo:
Marshall Plexi; Rhythm: Orange AD50), and the app says "Standard tones".

### Creating or editing a tone

**Create / edit tones** opens the editor: **+ New tone**, pick amp, cabinet and effects, turn
the knobs (drag, type the value, or double-click for the default). **Volume: higher = louder**
(0.1–36). **Save tone**.

- **Library**: save a tone (★) to use in other projects; **Load** copies it into this one.
- **Tones from your songs**: reads Rocksmith's `dlc` folder and lists the tones of all your
  songs (official and CDLC), searchable by artist and words. **Use in this project** copies a
  tone.

### Which tone each track plays

In **Tones of each track**:

- **Same tones on all tracks**, or untick it so each track has its own (pick the track in the
  tabs);
- **Base tone**: the tone the track starts with;
- **Tones it can switch to** (max 4 — the game's limit);
- **Tone changes**: first tick the tones the track uses under "Tones it can switch to"; then,
  on the score, **Tone change** mode and click the note where the switch should happen.

This is what goes into the game, after **Apply and rebuild**.

### Tone detection and suggestions

- **Detect tone** separates the guitar (Demucs, minutes) and classifies the sound's character
  (clean, crunch, distorted), proposing presets from the game's catalogue ranked by likeness.
  It does not identify the real amp.
- **Suggestions per section** proposes a tone for each part of each track (clean, rhythm,
  lead), from the recording and from what the track plays. A suggestion **changes nothing**
  until you press **Apply to this track** or **Apply to all tracks**. On each row you can
  replace the suggested tone with one of yours (from the project, the library or your PSARCs);
  picking "(the suggested one)" undoes it.

## 9. Lyrics

Lyrics can come:

- **from the GP file** (or Songsterr): each syllable on its note, following your sync
  corrections;
- **from LRCLIB**: **Search lyrics online** → **Use** on lyrics with timings;
- **from the recording**: **Detect lyrics in the recording** (WhisperX; experimental, takes
  minutes);
- from an LRC/UltraStar file, or typed by hand.

**Line up with the recording:** if the lyrics are all early or late, **1st word = cursor** or −/+.
If they drift midway, **Sync with the recording** measures each word's time in the recording's
voice (the words stay as they are; needs the ML extra).

**Words:** the table edits text, time, length and line end (the line end is what makes the
game start a new line). **Export LRC** saves the lyrics; **Back to the score's lyrics** replaces
what is in the editor with the GP file's lyrics.

**Beside the score:** in the **Lyrics** inspector, click a word on the score to fix it without
leaving the page: **From here on = cursor** (the word goes to the cursor and the following ones
follow), **Only this = cursor**, ◀ ▶, −/+.

## 10. Cover and song information

- **Cover:** drop a JPG/PNG image, or **Search cover online** and pick a result (it can fill in
  album and year too). It goes into the PSARC on the next rebuild.
- **Edit info** (top bar): title, artist, album, year; and the Guitar Pro tracks and tunings.
  Changing only text does not rebuild straight away (it goes into the PSARC on the next
  rebuild); changing tracks or tuning does.

## 11. Export, check and install in the game

### Before you use it

A list of what is missing or may go wrong, each row with a button to fix it:

- **Playable PSARC** (needs Wwise);
- **PSARC checked**: checks the file against the rules whose breaking has made the game crash
  or hide the song before. It does not replace playing the song;
- **Tones**, **Cover**, **Sync** (mark each track on the Score page, or press **Mark as synced**
  here for the whole song), **Lyrics**;
- **AppID / ownership**: the PSARC uses the AppID of a DLC the player must own.

Nothing is blocked: you can download anyway.

### Download

- **PSARC for the game**: the file that goes into Rocksmith's `dlc` folder.
- **DLC Builder bundle**: XML, audio and a `.rs2dlc` project to open in DLC Builder (Open
  project), if you want to finish there.

### Install in the game

**Install in the game** copies the PSARC into `dlc\RockForge\` in the game folder and deletes
the copy of an earlier version of the same song that RockForge put there. Files you put there
by hand are never deleted (the app warns if the song would be listed twice). Close the game
before installing and start it again for the song to appear; with the game open the copy can
fail.

### Build options

**Tuning deviation (cents)**: how far the recording is from A at 440 Hz (a band that tunes to
432 Hz sits near −32). The game's tuner uses it to ask for the guitar tuned like the recording;
it is the same on every track. **Detect tuning** measures it in the recording and fills the
field. The strings' tuning (Drop D, Eb…) is changed per track in **Edit info** → **Arrangements
and tuning**.

Import palm mute / slap / tap, and **Dynamic difficulty** (untick for a single difficulty with
every note, if DD misbehaves on a song).

## 12. A whole album at once (Batch)

**Batch (album)** creates several projects at once: pick several GP files and the recordings.
Each GP gets the recording with the same name (`track1.gp5` ↔ `track1.mp3`), or goes by order
when the names do not match; a GP8 with audio inside needs no recording. Band, album and year
are shared. Lead/Rhythm tracks are picked by name; check them afterwards in each project's
**Edit info**.

## 13. Settings

- **General**: language; **New versions** (ask GitHub once a day, on by default); **Wwise
  folder** (empty = found where the Audiokinetic Launcher installs it); Rocksmith 2014 folder.
- **Software**: in the `.exe`, the **Extra components** card (what is installed, **Install extra
  components** / **Reinstall**, the install log); then what is installed, what is missing and how
  to get it.
- **ML Python**: set by the extra components by itself; only for using a Python 3.11 of your
  own that already has `rockforge[ml,lyrics]`.
- **Stems**: the separation engine (Demucs; Banquet in testing).
- **Volume**: the song's target loudness in game (LUFS). −12 by default; −10/−9 if it sounds
  quiet beside official DLC; −16 is the cleanest.
- **GPU**: if the GPU crashed, RockForge moves to the CPU; **Re-enable GPU** once you have fixed
  the drivers.

## 14. Keyboard shortcuts

On the score, outside text fields. **?** (or the key button in the top bar) shows this list in
the app itself.

| Key | Does |
|---|---|
| Space | play / pause |
| ← / → (Shift = bigger step) | back / forward |
| Home | go to the start |
| [ · ] · L | mark A · mark B (at the cursor) · turn the passage repeat on/off |
| + / − | zoom |
| 1 … 9 · 0 | pick the mode in the order of the Mode ▾ menu (the number shows beside each; 0 is the tenth; the same number again turns the mode off) |
| B · Backspace · Esc | in “Mark by ear”: mark the bar (or beat) · take the last tap back · finish |
| Shift+click · Ctrl+click | select a range · add or remove a note |
| Delete | delete the selection |
| Ctrl+Z · Ctrl+Shift+Z (or Ctrl+Y) | undo · redo (on any page of the project) |
| Ctrl+C · Ctrl+V | copy the selection · paste at the cursor |
| Alt (while dragging) | no snap |
| ? | show the shortcuts |
| Esc | close a menu, popup or the shortcuts window |

## 15. Common problems

| Problem | What to check |
|---|---|
| The song **does not show** in the game | Is the CDLC patch (`D3DX9_42.dll`) in the game folder? (Settings → Software.) Is the AppID used that of a DLC you own? Is the PSARC in `dlc` (or `dlc\RockForge`)? |
| Only the bundle comes out, **no playable PSARC** | Wwise (2019/2021/2022/2023) is missing — Settings → Software. |
| The notes drift from the music | Section 6: start, then BPM, then "Fix from here". If the file is not exactly the recording (another version, extra bars), the fix belongs in the file itself. |
| YouTube refuses the download | Install the solver and a JavaScript runtime: `pip install -U "yt-dlp[default]"` and `winget install DenoLand.Deno`, then restart. If it asks for a session, pick **firefox** under "Browser session" (Chrome's cannot be read on Windows). Or upload the video's MP3 yourself. |
| Songsterr says the tab is unpublished | Only published tabs can be read; pick another tab of the same song. |
| Certificate error looking up lyrics, cover or Songsterr | Check the PC's date and time, the antivirus (HTTPS scanning) and `pip install --upgrade certifi`. |
| "Detect lyrics/tone" or "Separate instruments" do nothing | The ML extra is missing (Settings → Software). In the `.exe`, set a Python in Settings → ML Python. On the CPU it takes several minutes. |
| I changed something and the game did not | Did you press **Apply and rebuild** and install the new version? In Export, "An earlier version of this song is in the game" means no. |
| The rebuild failed | The message stays in Export; the previous version is kept. A note outside the file's bars, or sync corrections that cross, are the usual causes. |
| The sound is quiet or noisy in game | Settings → Volume (target loudness); in the tone editor, the Volume (higher = louder), the amp's gain and the noise gate. |
