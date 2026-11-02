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
2. **Score**: listen to the recording with the notes on top and fix the sync (the quickest
   route is in [The most effective way](#the-most-effective-way)). When it lines up, mark each
   track as in sync.
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
  it. **Wwise** cannot come this way (its licence does not allow it): install **2023.1** with the
  Audiokinetic Launcher (2024/2025 will not do) and RockForge finds it on any drive — or set
  ⚙️ **Settings → General → Wwise folder**. **Settings → Software** shows which Wwise it found
  and, if it cannot use it, why.
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
- At the top: **Buy me a coffee**, **Give it a star** (opens RockForge on GitHub), **Batch
  (album)**, **New project** and ⚙️ **Settings**.
- Above the projects, when it applies: **a new version** of RockForge is out (**Download** opens
  its Releases page; **Later** hides it until the next one), the **extra components** are missing
  (`.exe`; **Install now** / **Not now**), or **Wwise** is missing, so the `.psarc` would have no
  sound (`.exe`; **Download Wwise** / **Hide**). Someone running `start.bat` with git never sees
  the version notice: it updates itself on every start.
- **After an update**, the first notice lists **everything that changed** since the version you
  last used (the same entries as each version's notes), until you press **Got it**. In Settings →
  General → About RockForge, **What's new in this version** shows them again.
- Once you have built your first project (never on the first day), a quiet request for **a star
  on GitHub** shows once, only when there is no other notice: **Give it a star**, **Not now**
  (asks once more, 30 days later) or **Don't ask again**. The choice stays in this browser;
  RockForge sends nothing and cannot tell whether you gave the star.

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

**Merge two tracks into one arrangement**: when the file split one part into two tracks
(Songsterr often does this with a single guitarist), pick the second in **Merge the track** and
the arrangement it goes into in **into the arrangement** — the notes of both end up in one chart.
Both tracks must have the same tuning and capo (otherwise the same fret would sound another note,
and the merge is not made, with a warning saying so); where both play the same string at the same
moment, the arrangement's note stays, and the warning counts how many were left out.

Below it a grid shows the song's bars: **choose the bars** whose notes come in. With **Only in
the bars where the arrangement has no notes** (on by default), the arrangement only receives notes
where it is silent — for example, a LEAD with few notes gets the RHYTHM's parts in the bars where
the LEAD does not play, and what the LEAD already plays does not change. Click a bar to include or
leave it out, drag over several, or Shift+click for a range; **All** and **None** do the obvious.
Green goes in; a green outline means the other track has notes but they are left out; hatched
means the arrangement already plays there; faded means the other track has no notes. It is
experimental: check the result on the score. Change it later in **Edit info**.

**Bass track** takes a 4- or 5-string bass track of the file (the guitar pickers do not offer
those). Rocksmith's bass has four strings, so a 5-string bass is folded onto the four strings that
lose the fewest notes — B E A D when the part never plays the high G — and the warnings name the
strings used and count any note left out. A tuning lower than 4 semitones below standard (B
standard, say) is written an octave up with the reference at 220 Hz, as DLC Builder does, so the
game detects the notes; RockForge's score and playback still sound the real pitch. To write the
bass that way in another tuning (Drop C, D standard…), or never, choose in **Edit info** →
**Bass tuning reference**: **A220 (low tuning)**, **A440 (standard)** or **Automatic** (A220 only
below −4 semitones). At A220, tune the bass in the game with the reference at 220 Hz. A 6-string
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
- **Which recording will you play this tab with?** (only after importing from Songsterr in
  step 1): decides where each bar's timing comes from, and each choice fits only its own
  recording.
  - **Songsterr's recording (its MP3) or another one that follows the tab**: the notes follow
    the tab's own tempo, bar by bar and with its decimals, as in Songsterr's player. This is the
    choice for Songsterr's MP3 and for tabs Songsterr's AI made from the recording. Upload your
    file and set the **Start** to where bar 1 sounds. A hand-written tab at a single tempo only
    fits a recording played at a fixed tempo — the card says how many tempos the tab has.
  - **The audio of a YouTube video**: the times Songsterr has for a video, with that video's
    audio downloaded here. They fit bar by bar only that audio.

  If you upload a file of your own with a video's times chosen, a warning appears with **Use
  the tab's tempo**. The choice is remembered for the next tab.
- **Extra — sync with Songsterr's timings** (optional): Songsterr stores the instant each bar
  starts in YouTube videos (marked by people or generated by Songsterr). **Find videos**, pick
  one, and the notes follow that video bar by bar. Two conditions: the recording must be the
  audio of **that** video (its link moves to "Don't have the audio?" so you can download it) and
  the file must be the Songsterr tab. After importing from Songsterr in step 1 with the video
  choice, this is done for you: video picked and audio downloaded.

### Step 4 — Details

- **Title, Band, Album, Year.** Taken from the file or the audio's tags when present.
- **Album, year and cover → Search online**: lists results from iTunes and MusicBrainz; pick
  the right one (or "No cover"). Fan remixes and AI-made songs are rarely there. You can also
  pick an image from your computer (JPEG or PNG), just below.
  **Or from somewhere else:** **Search Google Images** opens the search in your browser; when you
  find the cover, copy the image address and paste it into **Image link** → **Use**, or copy the
  image itself and paste it on the page (Ctrl+V). Only images from public sites are accepted;
  WebP, GIF and other formats are turned into PNG.
- **Synced lyrics → Search lyrics online** (LRCLIB): pick lyrics with timings, or none. If the
  GP file already has lyrics, nothing is picked for you. You can also upload an **LRC** or
  **UltraStar TXT** file (it always wins).
- **Import palm mute / slap / pop / tap**: untick if you do not want those techniques in the
  chart.

**Create CDLC** creates the project and starts the build. Tones can come later.

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
  - **Metronome** (the click's volume) and **Click on every beat**: a click on every beat of the
    score as drawn (with the corrections still to apply), the 1st beat of each bar higher — you
    hear whether the bar grid matches the music. With the **Audio bars** on, the metronome lane
    appears too: each beat green when an attack of the lane above (pick the separated drums) falls
    on it, orange when it is off, grey with no attack near, plus the count and how far ahead or
    behind the grid is;
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
- **Fretboard** shows the guitar neck. With **All notes** on, the fretboard names every note of
  the track's tuning; click a note and it is highlighted, with a dashed outline where **the same
  sound** is (A2 on string 6 fret 5 and string 5 open, for example) and a white outline where
  **the same note in another octave** is; the list of places shows underneath. Clicking it again
  lets it go, and the click does not move the cursor. Beside it pick **Note name (A)** or **Name and
  octave (A2)**, and whether to show all notes, only those matching the picked one or only naturals
  (no #); with "only those matching", nothing shows until a note is picked. With no mode
  selected, clicking a note on the score takes the cursor to it and picks it on the fretboard.
  **3D highway** shows the notes coming down as in Rocksmith — outlined only, tilted, turning level as they reach the string (it
  follows pending corrections too); when a note or chord reaches the strings, a rectangle lights
  up around the frets the hand is in (2–5, for example). A bend is teal: the note's trail rises with
  the bend and, on the string, the note rises as it is bent, up to the dashed frame at the height
  the bend reaches (a whole step = one string gap), and comes down when the bend is released. On
  the 3D highway, drag to turn the camera (up to 120° either
  way, from level with the highway to a view from above), once you click the highway the mouse wheel
  moves closer or further (before that it scrolls the page; Esc or a click elsewhere lets go) and
  a double-click resets; **Camera** has the same axes as sliders. **− / + / Reset**: zoom.
  **Legend** shows, under the score, what each mark means (rings, tails, lines, the orange circles
  of the attacks, the hand-position lane…), drawn as it appears; the ⓘ beside it shows the same.
- **Play** (experimental) opens, above the score, the **Play with the guitar** panel: connect
  the guitar to the computer (Rocksmith's **Real Tone Cable** or a sound card), pick it in the
  list and press **Connect the guitar** — the browser asks to use the audio input. The meter and
  the note beside it show what comes in (it works as a tuner). With the playback stopped,
  **Calibrate the delay** plays 8 clicks: pick an open string on each one, and the delay between
  the speakers and the input is measured and remembered (you can set it by hand, in ms). Then play
  the chart along with the music: each single note is judged as it passes — a **green** ring right
  and in time, **yellow** right but early or late (with the ms), **red** the wrong note (with the
  one heard), **dashed red** missed — and the panel counts the right ones, the streak and whether
  you play early or late on average. What counts is what is drawn (pending corrections and edits
  included), also with the music slowed down. On a **chord**, a frame around it says whether it
  was in time (green or yellow) or wrong (red), and only the strings with a problem get a mark:
  red the one on another fret (with the fret heard), dashed the one not heard. In a chord of four
  strings or more, missing one still counts as right; a wrong fret does not. A string that doubles
  another an octave lower cannot be told apart from it. Muted notes and harmonics are not judged.
  **Hear the guitar** sends the guitar's sound to the speakers (no effects, some delay).
  Nothing leaves your computer.
- **Audio bars** puts two lanes of bars above the score, on the same time axis: on top the
  recording, below the sound of the track's notes where they are drawn (pending corrections
  included). Where the peaks of the two lanes do not fall together, the score is out of time.
  Beside it you pick what the recording's bars show: **Attacks** (the default) marks each strike
  with a narrow peak, even on a distorted guitar whose volume barely dips between pick strokes;
  **Volume** shows the sound's level (and is what you see when the audio analysis is not
  installed). And you pick the audio: what is playing, the full mix or an instrument already
  separated (in **Audio ▾ → Separate instruments**) — for example, listen to the mix and see the
  bars of the guitar only. For the attacks you can also pick the **drums**, the best metronome to
  check the bar lines against. If you turn the bars on with nothing separated, the app asks
  whether to separate the instruments now (once per project); until then it shows the mix's
  volume, and **Cancel** leaves it at that, separating and analysing nothing. When the separation
  finishes, the bars move to the track's instrument by themselves. Clicking the bars moves the cursor.
  **To see whether they line up**: with the mouse over the bars or the score, a line runs down
  both lanes and the staff, and the bars say how far the nearest note is before or after the
  attack nearest to it ("Note 20 ms before the attack"; green up to 15 ms), the two marks joined
  by a dash. **Ctrl + mouse wheel** zooms where the mouse is. It is for the last adjustments: a
  note off by more than half the distance to the next note is paired with its neighbour's
  attack — fix the start and the tempo first.
- **Inspector (on the right):** **Sync**, **Sections** and **Lyrics**.

## 6. Syncing the notes to the recording

### The most effective way

What takes the least work and goes wrong the least, in this order:

1. **Start from a sync made by people, if there is one.** A Guitar Pro 8 file with the audio
   inside (leave "Use the audio inside the GP file" ticked), or the Songsterr tab with a video's
   timings and the audio of **that** video (step 3 of New project). It comes bar by bar: often
   you only need to listen and mark it as synced.
2. **Set the start** (step 1) — with **Detect 1st note**, or the cursor on the 1st note and
   **= cursor**. If the score drifts away evenly over the song, set the **BPM** (step 2).
3. **A tab that was never synced** (one tempo throughout): **Mark by ear**, on every bar, with
   playback slowed down (90% or 75%) and **Smooth the taps** on. It is the most reliable method
   for these tabs: you are the one saying where each bar starts.
4. **Whatever still drifts:** the **Fix from here** mode. Listen until the score starts to
   drift, click that note, and repeat along the song. What came before does not move.
5. **Check with the Recording attacks.** Separate the instruments first (**Audio ▾ → Separate
   instruments**) and measure on one (the guitar, or the bass on the Bass chart): the orange
   circles and ticks show where the score does not line up. Fix them with **Align bar** or by
   dragging notes.
6. **Several tracks:** sync the easiest one to hear first and make it the **Main track** — the
   corrections reach the others. With a Bass chart, the separated bass gives the cleanest
   attacks. Then confirm each track.
7. **Apply and rebuild**, listen again, and **Mark this track as synced**.

**Sync automatically** (experimental) can save time on a tab whose tempo wanders, but only once
the start is set, and always listening to the result. It measures the mix on purpose: the drum
hits help it; on the separated bass it goes wrong more often.

### Step by step, on a tab that was never synced

One example from start to finish, for a first time (the **Sync** inspector, to the right of the
score):

1. **One right tempo.** The **♩ =** number above the notes shows the tempo at each point. If it
   changes midway and the recording does not, in **Tempo** type the recording's BPM in **One
   tempo** and press **Apply to the whole track**: every bar goes to that BPM and the start stays
   where it is. If the score only drifts away evenly, the **BPM** above is enough.
2. **The first bar.** In **Song start**, **Detect 1st note** (or the cursor on the 1st note and
   **= cursor**). Listen to the first bars.
3. **Along the song.** Play, and when the score starts drifting, pause where a note should be.
   Two ways to take everything that follows with it:
   - **Fix from here** mode: click that note — everything before stays put, and the rest is
     stretched to the recording's tempo;
   - or **Notes ▾ → From the cursor to the end** (**Shift+End**) selects every note from there
     to the end, and in **Drag** mode you drag one of them: they all move together, and the
     ones before do not move.
   Repeat further on, always from the start towards the end.
4. **Check** with playback slowed down, or with the **Recording attacks**, and at the end
   **Apply and rebuild** and **Mark this track as synced**.

The steps one by one, one track at a time (at the top of the **Sync** inspector):

### Step 1 — Song start

The second the 1st note **of this track** is heard. Four ways:

- type the value and press Enter — with a dot or a comma (1.25), or in minutes (1:02.5);
  ↑/↓ nudge it 0.01 s (Shift 0.1 s, Alt 0.001 s), Esc gives up; the **−**/**+** buttons beside
  it nudge 1 ms a click (Shift 10 ms, Alt 100 ms; hold to repeat); or use the slider;
- put the cursor where the note sounds and press **= cursor**;
- **Detect 1st note**: press the button, then click the waveform where the 1st note sounds,
  and finally that note;
- **Align to the attacks**: measures the recording's attacks (like the **Recording attacks**),
  looks for the shift, up to 0.3 s, that puts the most notes on an attack, and moves the whole
  track by it. It is for a track that is early or late by the same amount throughout — for
  example, with the times of a Songsterr video. If the rhythm is so regular that two fits work
  equally well, it leaves it alone; if the difference grows along the song, it warns you,
  because then it is the tempo that needs correcting. It only moves the track that is open:
  pick it as **Main track** for the others to follow.

### Step 2 — Tempo

If the score drifts away evenly over the song (the file was written at a slightly different
BPM), change the **BPM**. The notes slide over the waveform live. **Reset to GP** goes back to the
file's tempo.

If the score **changes tempo midway** (the **♩ =** above the notes changes) and the recording does
not, **One tempo** → **Apply to the whole track** puts every bar at the same BPM, the start where it
is.

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

### The tab's rhythm does not match what you hear — marking every attack

When the problem is not the tempo but the notes themselves (an extra strum, a rhythm written
wrong), mark what you hear in the same card, without moving the score:

1. in **Mark by ear**, pick **I tap on every attack (every strum)**, put the cursor a little
   before the passage and press **Start marking**;
2. hit **B** on every strum you hear (Backspace takes the last tap back, Esc finishes). The taps
   sit over the staff, in green, and are saved with the project, one list per track;
3. in the **Marked attacks** box: a green tick is a tap that matches a note; a tall tick with a
   dashed line is a tap with no note; a green square is a note with no tap near it. **Previous /
   Next difference** takes the cursor to each one, and the status line says how many ms on
   average the notes sit before or after the taps;
4. to fix them, pick **Marked attacks** in **Snap to**: the notes you drag or add in **Edit
   notes** go to the taps. Or select notes (with **From the cursor to the end**, say) and press
   **Snap the selected notes to the taps** — each note or chord goes to the nearest tap, within
   250 ms. This changes the notes, not the tempo, and stays pending until **Apply and rebuild**.

Marking a passage again replaces only the taps between where you started and your last tap.
**Undo** steps back and **Delete this track's taps** removes them all.

### A tempo that varies — Sync automatically (experimental)

The **Sync automatically** card, marked **Experimental**, does what marking by ear does, on its
own: it analyses the recording and moves each bar to where its notes sound, letting the tempo
change over the song. **It can get it wrong** — use it like this:

1. first set the start of the bar you begin from (step 1, or "= cursor") and the approximate
   tempo;
2. pick **From bar** and press **Detect and align** (it can take a minute);
3. listen to the result. The bars under **Check by ear** are the ones after a rest or where the
   notes did not match what is heard — confirm them and correct them with **Fix from here** or
   by dragging notes.

It all stays as corrections in step 3 (one Ctrl+Z undoes it all) until **Apply and rebuild**.
It needs the audio analysis (the ML extra, or the extra components in the `.exe`).

### Wrong rhythm in the tab — Recording attacks

When the tab's **rhythm** is wrong (common in tabs made in a hurry), the **Recording attacks**
card shows where. **Detect attacks** marks above the score every attack heard in the recording:
blue ticks where a note of the score is close, and **orange** for the differences — a circle on
a note with no attack near it, a tick where there is a strong attack with no note. **Previous/
Next difference** takes the cursor to each one, so you can listen and fix it with **Edit notes**.

- Sync first: the comparison uses the score as it is on screen.
- Under **Measure on** you choose where: an instrument already separated (**Audio ▾ → Separate
  instruments**) — the guitar by default, and the bass on the Bass chart — or the mix, where the
  drums and the voice give attacks too. With nothing separated, it asks before measuring the mix.
- **Aligning by the bass:** the bass separates better than the guitar. With a Bass chart, make it
  the **Main track** (Sync inspector), measure the attacks on the bass, correct the bass, and the
  other charts get the same change of time.
- It tells **when** something is played, never which notes; with two guitarists you see both
  players' attacks.
- Nothing in the score changes. It needs the audio analysis, like the card above.

### Step 3 — Corrections on the score

For what is left, pick a mode in **Mode ▾** and click where the score drifts:

| Mode | What it does |
|---|---|
| **Fix from here** (recommended) | Listen until the score starts to drift and click that note. Everything before it stays put; RockForge measures the recording's tempo from there on and stretches only the rest. Repeat along the song. |
| **Drag** | Drag a note to where you hear it in the recording. It corrects the **timing**, not the note: the notes around it stretch or shrink, the bars' BPM changes and a note cannot pass the neighbouring correction. With several notes selected, they move as a block. Alt while dragging = no snap. To move a note or a chord to another place, use **Edit notes**. |
| **Mark** | Press play and click the note the moment you hear it: it moves to the cursor. |
| **Excerpt** | Draw a box over a passage and correct its timing as a block. |
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
- **Song end**: the second of the recording where the game ends the song. Empty, the song runs
  to the end of the recording even if the chart stops earlier (an ending of other guitars only,
  a fade); **= cursor** marks where the cursor is, **End of the recording** goes back to normal.
  It never ends before the last note.
- **Reload GP file**: after fixing a note in Guitar Pro and exporting again. Keeps sync, tones,
  lyrics and tuning. If the new file carries audio, that becomes the recording.
- **Save the adjustments → Export / Import**: saves start, tempo, corrections, tuning and
  lyrics in a JSON, so you need not redo them if you recreate the project.

## 7. Editing notes and sections

### Selecting

Click = one note; **Shift+click** = a range; **Ctrl+click** = add or remove a note; click the
background = clear the selection. **Excerpt** mode selects with a box. **Notes ▾ → From the
cursor to the end** (**Shift+End**) selects every note of this track from the cursor to the end. In
**Drag** mode, dragging a selected note moves the whole selection; the rest of the track stays
where it is.

### Two tracks: passing notes from one to the other

Turn on **Two tracks** (under the score, with two or more tracks) and another track appears under
the score, on the same time axis; pick it in **Lower track**. It is for, say, a tab that split
between two tracks what is one guitarist.

- **On the lower track:** click a note, **Ctrl+click** adds or removes, **Shift+click** picks
  everything between two notes, and dragging on an empty place draws a box (only the notes inside
  it, strings included).
- **On the score above:** the usual selection; with **Two tracks** on, dragging on an empty place
  draws a box too (there it picks by time, with whole chords).
- **↓ Pass down** / **↑ Pass up** take the notes off one track and put them on the other exactly
  where they were drawn, on the same string. With **Copy instead of passing** they stay on both.
  If the tunings differ, the fret changes so the sound stays the same (between a guitar and a bass
  the fret stays the same). Notes on a string the other track does not have, off the neck or
  outside its song are left out, and said; if another note is already in that place, nothing is
  passed.

It stays pending on both tracks until **Apply and rebuild**; Ctrl+Z undoes it.

### Editing notes (✏️ Edit notes mode)

- Click a note: change string, fret, sustain, techniques (hammer-on, pull-off, harmonic, palm
  mute, vibrato, tapping, slap, pop, accent), bend and slide; **Save** or **Remove note**.
- **Slides:** in **Slide to** type the fret it lands on and choose **Slide to the fret** or
  **Unpitched slide (out)** (a slide out that does not land on a definite note). **Lasts (s)** is
  how long it takes to slide: shorter than the sustain, the note reaches the fret and rings there
  until the end of the sustain (a slide note linked to a held note, as in Rocksmith); empty, it
  slides over the whole sustain. **Link to the next note** makes the note carry on into the next
  one on the same string without a new pick. On the score the slide is a line to the end of the
  sustain (dashed when unpitched), and you hear it slide.
- **Drag** a note to change its time (it snaps to the grid) or its string (it keeps its fret,
  so its pitch changes).
- To move **a chord or several notes**: drag a box on an empty spot of the staff around them (or
  Ctrl+click each one) and drag one of the selected notes — they all move together, can pass
  over other notes and the tempo does not change. A single click on empty space still moves the
  cursor.
- **Shift + drag** a note to duplicate it — in a chord, the whole chord — and drop the copy
  where you want it (the original stays). Shift+click without dragging still selects.
- **Drag the end of a note's tail** (the small handle on its right) to change its length; back
  onto the note, no sustain. It stops before the next note on the same string.
- **↑ / ↓** move the last clicked or dragged note one fret up or down, and it sounds (with Ctrl,
  an octave) — for example, a 9 that should be 12: click it and press ↑ three times.
- **Double-click** an empty spot to insert a note (string from the click's height, time on the
  nearest grid point, never coarser than sixteenths; with **Alt**, free). Notes can only go
  inside the bars the file has.
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
  To change when a tone comes in: drag its orange mark (under the staff) along the score, type
  the seconds in the field beside the change, or put the cursor in the right place and press
  **= cursor**. A click on the mark puts the cursor where the switch starts.

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

### Import tones from a text (ChatGPT or another assistant)

For when you know — or want to ask — which tones the song uses. In the **Import tones from a
text** card (once the project is built):

1. **Copy the request** puts a ready request on the clipboard: the song, the tracks, the
   sections with each one's bar and time, the answer format and the game's gear, with each
   knob's limits. Paste it into ChatGPT (or another assistant).
2. Copy its **whole** answer and paste it into the box.
3. **Read the answer** shows the tones (with their gear), where each one comes in on each track —
   in a chart per track, like the suggestions' one: a strip with the tone that sounds at each
   moment, the sections under it and, once you have used **Detect tone**, the recording's
   distortion above it — and **every adaptation** that was needed — gear read as the closest one, a knob outside its
   limits, a cabinet chosen for the amp, one tone too many on a track (the game switches between
   only 4 per track). A text without the tone block is refused.
4. **Apply** changes the tones like an edit of your own (it can be undone); **Apply and rebuild**
   saves them. A track the answer does not mention stays as it was. The same chart stays in
   **Tones of each track**, with the tones of the track on screen (also the ones you mark by
   hand); clicking a part takes the cursor there.

It is the assistant's opinion, not a measurement: check it by ear.

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
  album and year too). If it is not there, **Or from somewhere else**: **Search Google Images**,
  then paste the **Image link** (→ **Use**) or the image itself (Ctrl+V). It goes into the PSARC
  on the next rebuild.
- **Edit info** (top bar): title, artist, album, year; and the Guitar Pro tracks, the track merged
  into an arrangement and the tunings.
  Changing only text does not rebuild straight away (it goes into the PSARC on the next
  rebuild); changing tracks or tuning does.
  Each track's tuning offers the common ones (Standard down to Drop A, Open D/G/E/C/A, DADGAD)
  and **Custom…**, which shows one note per string (string 6 = the lowest) so you can set any
  tuning. A tab imported from a PDF that does not state its tuning is read as standard; step 2
  of the wizard says which tuning was read.

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

### Export and import the project

**RockForge project (.rfproj)** → **Export project** saves the whole project in one file: the
recording, the Guitar Pro file, the cover and every correction (sync, edited notes, hand
positions, sections, tones, lyrics). Use it to take the project to another computer, keep a copy
before changing a lot, or send it to someone. If you have separated the instruments, you can
include them (the file is bigger, but whoever opens it need not separate them again). The file
holds the project as it was last built: if there are changes not yet applied, the app asks
first — press **Apply and rebuild** first to include them.

To open one, press **Import project** on the home page (or drop the `.rfproj` on the "Drag a
Guitar Pro file here" card). It becomes a new project, built again with everything the file carries.
What only made sense on the computer it came from (the copy installed in the game, the earlier
versions) does not come along.

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

- **General**: language; **About RockForge** (the version and build you are using; **Copy
  information for a report** puts what a bug report needs on the clipboard — version, build,
  system, the software found and the end of the technical log, without passwords or your user
  name — **Report a problem** opens the form on GitHub, and **What's new in this version** shows
  what changed); **New versions** (ask GitHub at most once an hour, on by default); **Count this install**
  (off until you say yes — the home page asks once; once per version it sends a random number,
  the version, the kind of install and the system, and turning it off deletes what was sent);
  **Wwise folder** (empty = found where the Audiokinetic Launcher installs it); Rocksmith 2014 folder.
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
| Ctrl + mouse wheel | zoom where the mouse is |
| 1 … 9 · 0 | pick the mode in the order of the Mode ▾ menu (the number shows beside each; 0 is the tenth; the same number again turns the mode off) |
| B · Backspace · Esc | in “Mark by ear”: mark the bar (the beat, or the attack) · take the last tap back · finish |
| Shift+click · Ctrl+click | select a range · add or remove a note |
| Shift+End | select every note from the cursor to the end |
| Delete | delete the selection |
| Ctrl+Z · Ctrl+Shift+Z (or Ctrl+Y) | undo · redo (on any page of the project) |
| Ctrl+C · Ctrl+V | copy the selection · paste at the cursor |
| Alt (while dragging) | no snap |
| Shift + drag a note | in “Edit notes”: duplicates the note or chord and moves the copy |
| Drag the end of the tail | in “Edit notes”: changes the note's length (sustain) |
| ↑ / ↓ (Ctrl = octave) | in “Edit notes”: one fret up / down on the last clicked note |
| ? | show the shortcuts |
| Esc | close a menu, popup or the shortcuts window |

## 15. Common problems

| Problem | What to check |
|---|---|
| Something went wrong and you want to report it | Settings → General → About RockForge → **Copy information for a report**, and paste it into the report (**Report a problem**). An unexpected error shows an id: include it, it is the same as in the technical log (`logs/rockforge.log` in the work folder). |
| The song **does not show** in the game | Is the CDLC patch (`D3DX9_42.dll`) in the game folder? (Settings → Software.) Is the AppID used that of a DLC you own? Is the PSARC in `dlc` (or `dlc\RockForge`)? |
| Only the bundle comes out, **no playable PSARC** | Wwise (2019/2021/2022/2023) is missing — Settings → Software. |
| It says **Wwise is missing**, but it is installed | Settings → Software says what it found: a 2024/2025 (install **2023.1** too, both can stay), a Wwise without its **Authoring** part (in the Launcher, Modify → Authoring), or nothing (set the folder in Settings → General → Wwise folder). In Export → "Before you use it", **PSARC without sound** shows Wwise's error when it was found but the conversion failed. |
| The notes drift from the music | Section 6, [The most effective way](#the-most-effective-way): start, BPM, "Mark by ear" on a tab never synced, then "Fix from here". If the file is not exactly the recording (another version, extra bars), the fix belongs in the file itself. |
| YouTube refuses the download | Install the solver and a JavaScript runtime: `pip install -U "yt-dlp[default]"` and `winget install DenoLand.Deno`, then restart. If it asks for a session, pick **firefox** under "Browser session" (Chrome's cannot be read on Windows). Or upload the video's MP3 yourself. |
| Songsterr says the tab is unpublished | Only published tabs can be read; pick another tab of the same song. |
| Certificate error looking up lyrics, cover or Songsterr | Check the PC's date and time, the antivirus (HTTPS scanning) and `pip install --upgrade certifi`. |
| "Detect lyrics/tone" or "Separate instruments" do nothing | The ML extra is missing (Settings → Software). In the `.exe`, set a Python in Settings → ML Python. On the CPU it takes several minutes. |
| I changed something and the game did not | Did you press **Apply and rebuild** and install the new version? In Export, "An earlier version of this song is in the game" means no. |
| The rebuild failed | The message stays in Export; the previous version is kept. A note outside the file's bars, or sync corrections that cross, are the usual causes. |
| The sound is quiet or noisy in game | Settings → Volume (target loudness); in the tone editor, the Volume (higher = louder), the amp's gain and the noise gate. |
