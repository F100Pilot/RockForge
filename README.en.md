**Português:** [README.md](README.md)

# RockForge

A Guitar Pro → Rocksmith 2014 arrangements (CDLC) pipeline, built on verified research and
**honest about the limits** of current technology.

> An independent, free project, **not affiliated with Ubisoft**. It contains no songs: you bring
> the Guitar Pro file and the recording, and the rights over them are your responsibility — see
> [Legal notices](#legal-notices) and [`LEGAL.md`](LEGAL.md). MIT licence ([`LICENSE`](LICENSE));
> third-party components in [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

The app's interface is available in Portuguese and English: switch it with the PT/EN picker on
the home page or in ⚙️ Settings → "Idioma · Language". The UI labels quoted below are the
English ones.

## What it does (and what it doesn't promise)

| Stage | Technology | Confidence |
|---|---|---|
| Ingestion (Guitar Pro) | FastAPI | — |
| Notes/frets/techniques/tempo/sections | Guitar Pro parser (GP3/4/5 via PyGuitarPro; native GP7/8) | **exact** from the file |
| Normalization (recording) | ffmpeg (linear gain, 44.1 kHz) | deterministic |
| Guitar stem (separation/tone detection) | Demucs `htdemucs_6s` (MIT) | "okay" according to its own authors; no published SDR |
| BPM/onset and tuning (cents) of the recording — GP automatic sync only | librosa (ISC) | published; requires human confirmation |
| Automatic lyrics (optional) | WhisperX on the isolated vocal stem (Demucs `htdemucs` 2-stem; `pip install -e ".[lyrics]"`) | **EXPERIMENTAL** — anti-hallucination gates (RMS + per-word confidence); LRC remains the preferred route; CPU is slow, an NVIDIA GPU ≈ online tools; runs in a **subprocess** (avoids faster-whisper's CUDA deadlock under Celery) |
| Tone detection (optional) | Demucs `htdemucs_6s` (guitar stem) + spectral analysis (librosa) → Lead/Rhythm presets from the Rocksmith catalogue | **EXPERIMENTAL** — classifies the sound's *character* (clean/crunch/high-gain), does not identify the real amp/pedal; the result is a proposal the user reviews and adjusts |
| Song2014 XML | in-house generator (format documented by the community) | structurally tested; emits the 32 `arrangementProperties` and the COUNT/default/END structure that DLC Builder and the game require |
| `.wem` audio | local Wwise + DLC Builder template project | Vorbis **with a seek table** + header fix (without it the game loads but stays silent and exits) — Wwise 2019/2021/2022/2023 |
| PSARC | bundle for DLC Builder; PSARC only with Wwise | **Wwise is required for .wem** |

## The Guitar Pro route (high fidelity)

Upload a **GP3/GP4/GP5 or GP7/GP8 (`.gp`)** +
the recording: notes, frets, techniques (bend/HO/PO/palm mute/harmonics/vibrato/slide), tempo,
bars and sections come **exact** from the file. Includes: Lead/Rhythm track selection, a sync
offset against the recording, lyrics (an **LRC** or **UltraStar TXT** file — per-syllable/line
timing synced to the recording — or lyrics embedded in the GP, aligned to the notes), and tones
(tonebase + up to 4 slots, with timed changes). UI flow: "Inspect tracks" →
choose tracks/options → create the CDLC.

**No Guitar Pro file?** Step 1 also takes the **PDF** of the tab or a **picture** of it
(PNG/JPEG/WebP; several files = one track each): RockForge turns it into a GP5 with the
[PDF-to-GP5](https://github.com/F100Pilot/PDF-to-GP5) converter (the `[pdf]` extra) and the
wizard carries on as with a Guitar Pro file. Reading pictures (OCR) is experimental: it reads
the techniques written as words (H/P, P.M., let ring, harmonics), slides, vibrato, ties
and bends; check the notes and the rhythm on the score.

Honest limitations: **only GP6 (`.gpx`) is unsupported** (a proprietary binary container —
export it as GP5 or GP7 in Guitar Pro/TuxGuitar). GP3/GP4/GP5 are read by PyGuitarPro;
GP7/GP8 (`.gp`) have a native GPIF/XML parser. Sync is manual — you give the second at which
the song starts in the recording and the score/lyrics are shifted to that instant (the
recording stays intact, since it already has its own intro); there is a minimum 2 s lead-in
for DLC Builder's count-in; bass tracks (4/5 strings) are not supported yet.

To fine-tune the sync there is a **visual sync tool** in the job detail view
(GP jobs): play the recording, the cursor runs over the notes and you hear a *tick* on each
one — drag the "Song start" until the ticks line up with the music and click "Apply and
rebuild".

If the tab and the recording **drift apart over the course of the song** (the GP was written
at a slightly different tempo from the recording), adjust the **tempo (BPM)** in the sync
panel: it stretches/compresses the whole song in one go. The notes move over the waveform in
real time so you can confirm the alignment; then "Apply and rebuild". This fixes the linear
part of the drift in a single step — do it **before** the note-by-note corrections below.

If the drift between the score and the audio grows over the song (instead of being a constant
offset), correct it note by note on the tab: **drag a note** horizontally to the instant where
it should play — that leaves a correction point, and the notes between consecutive points are
stretched/compressed proportionally. To fix a whole passage at once, turn on "Select excerpt",
drag a box over that passage's notes and then drag one of them — the excerpt moves as a block.
The notes stay at their corrected position in the viewer (with a time grid every 0.25 s for
fine adjustment) so you can test them against the audio before saving. Each "Apply
corrections and rebuild" adds a new round of corrections on top of the previous ones — **open
the job later (even after leaving and coming back) and keep adjusting**: corrections already
applied stay in the loaded arrangement and new ones add to them, instead of always starting
from the raw GP.

### 3D highway (like in Rocksmith)

On the Score page, tick **3D highway** (next to "Fretboard"): the notes of the chosen track
come down onto the strings as in Rocksmith, with the headstock and the tuning written on the
nut, the fret on the face of each note, a glow when the note reaches the string (and the note
rests on it while it sounds), chords with their name, and the camera following the part of the
neck in play. It follows the recording and the not-yet-applied sync corrections, just like the
score. It uses three.js, bundled with the app (works offline); it needs WebGL in the browser.

### Automatic tone detection (Lead / Rhythm)

The **"Detect tone"** button in the tones panel analyzes the recording and suggests Lead +
Rhythm tones from the Rocksmith gear catalogue, ready to use in the game:

1. Demucs (`htdemucs_6s`) isolates the guitar stem from the recording.
2. Spectral analysis (librosa — zero-crossing rate, spectral contrast, centroid,
   rolloff) classifies the sound's character into one of three categories: **Clean**,
   **Crunch** or **High Gain**.
3. Curated Lead and Rhythm presets (real amps, cabinets and pedals from the catalogue, with
   tuned knobs) matching the detected category are proposed.
4. The user clicks **"Apply suggested tones"** to load the presets into the tone editor,
   reviews/adjusts them and saves with **"Apply and rebuild"**.

**Tone volume:** as in DLC Builder, 0.1–36 and **higher = louder** (the game's own tones sit
around 18–20). The suggested tones already come at that level.

**Tones for each part of each track.** Detection also measures the sound **over the course of
the song** (where it is clean, where it distorts more). The **"Suggestions per section"** card
reads that against what each track plays in each section (chords and palm mute → rhythm;
single notes with bends/legato or high up the neck → solo; ringing chords in a clean passage →
clean) and proposes a tone for each part, with the reason and the confidence. **"Apply to this
track"/"to all"** puts those tones and the switches into the project; with **"Same tones on
all tracks"** unticked, each track has its own base tone, extras and switches (as in the game,
tones are per arrangement).
In **"Replace the suggested tones"** you can keep the switch points the app detected but use the
tones you want: each suggested tone can be replaced by a project tone, a library tone or one from
a PSARC you already have. The chosen swaps are kept with the project.

Honesty note: spectral analysis **does not identify** the actual amp or pedal used on the
recording — it classifies the sound's *character* and suggests a plausible match from the
Rocksmith catalogue. It needs the `[ml]` extra (Demucs + librosa). It works on any job that has
a recording.

**Tones from your songs.** As in DLC Builder: in the tone editor, **"Search your PSARCs"** reads
the Rocksmith `dlc` folder (official and CDLC; the game folder also includes `songs.psarc`) and
lists every song's tones with their exact gear. Search by song, artist, tone or gear, or pick
an artist from the list (or click their name on a tone) to see only their songs' tones; **"Use in
this project"** copies the tone, **★** saves it to the library. The files are only read (just
their manifests), and reading the folder again only opens new ones. It needs the `[psarc]`
extra.

Required reading: [`docs/RELATORIO-TECNICO.md`](docs/RELATORIO-TECNICO.md) (feasibility,
architecture, risks) and the research reports with sources in [`docs/research/`](docs/research/).

## Architecture

Clean Architecture: `domain/` (pure music model) → `application/` (ports + the Guitar Pro
pipeline use case) → `infrastructure/` (adapters: Demucs, librosa, ffmpeg, XML, packaging,
DB) → `interfaces/` (FastAPI API, Celery worker). Each ML stage is a swappable Protocol.
To contribute, see [`CLAUDE.md`](CLAUDE.md) (layers, commands and constraints that have
already cost us dearly).

## External software (what to install, and what you lose without each one)

RockForge **does not ship** the tools it depends on: Wwise cannot be redistributed
(Audiokinetic's license), the ML stack is gigabytes, and ffmpeg is better taken from the
system. Each absence degrades gracefully — but the symptom always shows up further down the
line and looks like a bug in the app ("the PSARC isn't playable", "lyric detection does
nothing").

That's why there is one place that tells you what you have: **⚙️ Settings → 🩺 External
software** (or `GET /system-check`). It shows what is installed on this machine, what each gap
costs you, and the command to install it.

| Software | Needed for | Without it | Install |
|---|---|---|---|
| **ffmpeg** | everything — the recording is normalized here | **no job finishes** | `winget install ffmpeg` |
| **Wwise** 2019/2021/2022/2023 | converting the audio to `.wem` → a **playable** `.psarc` | the bundle for DLC Builder is still produced; the `.psarc` has no audio | Audiokinetic Launcher + `ROCKFORGE_WWISE_ROOT` |
| **`[psarc]`** (cryptography, Pillow) | writing the native `.psarc` and the cover as DDS | only the bundle is produced, no crash | `pip install -e ".[psarc]"` |
| **`[ml]`** (Demucs, librosa) | separating stems, detecting tone, "Fix from here" | those buttons answer 503 saying what is missing | `pip install -e ".[ml]"` |
| **`[lyrics]`** (WhisperX) | transcribing the lyrics from the recording | lyrics still come from the GP, an LRC, or the editor | `pip install -e ".[ml,lyrics]"` |
| **`[youtube]`** (yt-dlp) + **Deno** | downloading the audio of the YouTube video Songsterr marked the times on (YouTube requires solving a JavaScript challenge: the solver comes with `yt-dlp[default]`, the engine is Deno) | you upload that video's MP3 yourself | `pip install -U "yt-dlp[default]"` and `winget install DenoLand.Deno` |
| **`[pdf]`** (PDF-to-GP5, with OCR) | making the project from a PDF or a picture of the tab | the PDF/picture is refused, saying what to install; GP and Songsterr still work | `pip install -e ".[pdf]"` (needs git; `start.bat` installs it in a step of its own) |
| **PyTorch CUDA** | GPU: minutes instead of tens of minutes | everything runs on CPU | see §2b |
| **CDLC patch** (`D3DX9_42.dll`) | Rocksmith accepting *any* CDLC | the song **never appears** in the list | CustomsForge, in the game folder |

Only **ffmpeg** is required. Two honest notes about the table: the CDLC patch is only checked
when the app finds the game — in this computer's Steam libraries, or in the folder you set in
⚙️ Settings → General → «Rocksmith 2014 folder»; and whether the installed PyTorch is the CUDA
or the CPU build is not known — that would require importing torch in the API process, which is
forbidden on purpose. In those cases the panel says **ⓘ unknown**, not ✅ or ❌.

### ML in the `.exe`: point it at a Python 3.11

The `.exe` carries the core (**GP → PSARC**) and, if you put `ffmpeg.exe` in the `ffmpeg/`
folder before building, it carries that too. **It has its own Python**: a PyInstaller
executable only sees the packages it carries inside, never the ones you install in your
Python — so it cannot *import* Demucs, WhisperX or librosa, and no `pip install` changes that.

But **it doesn't need to import them**: all those stages already run in a **subprocess**. All
it takes is a Python 3.11 that has them, and telling the app where it is — exactly as you
already do with ffmpeg and Wwise.

1. Install **Python 3.11** (`winget install Python.Python.3.11`).
2. In that Python: `py -3.11 -m pip install "rockforge[ml,lyrics]"`
   (for GPU, install the CUDA torch first — see the ffmpeg/GPU section below).
3. In the `.exe`: **⚙️ Settings → 🐍 Python for ML** → the path to
   `python.exe` (e.g. `C:\Users\you\AppData\Local\Programs\Python\Python311\python.exe`).

The panel shows ✓/✗ per extra — `[ml]` (stems, tone, "Fix from here") and `[lyrics]`
(lyrics) — and distinguishes "that path is not a Python" from "it is a Python but it lacks
Demucs", which are fixed in different ways.

| | `.exe` | `start.bat` (Python 3.11) |
|---|---|---|
| GP → bundle + `.psarc` | ✅ | ✅ |
| Wwise / ffmpeg / CDLC patch | ✅ (from the system) | ✅ |
| stems, tone, lyrics, "Fix from here" | ✅ with the ML Python set | ✅ with `[ml]` / `[ml,lyrics]` |

When running through `start.bat`, leave the field empty: it uses its own Python, and none of
this is needed. Without the field filled in, the `.exe` answers 503 on those buttons saying
what is missing — it never fails silently.

### Extra: syncing with Songsterr's timings

It is optional and sits collapsed in step 3 of the wizard, under **➕ Extra**; without it,
everything works as before.


Songsterr stores the instant of **every bar** in a YouTube video, marked by people. In step 3
of the wizard, paste the song's Songsterr link and click **Search**: you pick the video and
RockForge uses those times to align the score — no manual adjustments, even with a varying
tempo.

- RockForge fetches **only the times**. The MP3 is yours and has to be **converted from that
  same YouTube video** (the link appears in the wizard). The audio Songsterr itself offers is
  a **different** one and does not match the times.
- The GP file has to be **the Songsterr tab** (exported from there), so that bar 5 of one is
  bar 5 of the other. If they don't match, the project warns you.
- If you cut the start of the MP3, adjust "Song start" by that amount.
- Songsterr's API is not public: it can change without notice. If it stops answering,
  RockForge says so and everything else keeps working.

## Running

### Installing on a new PC (Windows, no Docker — recommended)

**1. Prerequisites**

| Software | How to install | What for |
|---|---|---|
| Git | https://git-scm.com/download/win | cloning the repository |
| Python **3.11** (exactly — 3.12+ does not work: the ML/lyrics stack `torch<2.5`/demucs/whisperx only has wheels up to 3.11) | https://www.python.org/downloads/ — ⚠️ tick **"Add Python to PATH"** | running the app |
| ffmpeg | `winget install ffmpeg` | audio normalization |
| Redis (optional) | [Memurai](https://www.memurai.com/) (Developer, free; runs as a service — installing it needs admin rights) | separate worker; without Redis, `start.bat` runs the tasks inside the API |
| NVIDIA GPU (optional, highly recommended) | up-to-date NVIDIA driver + the CUDA build of PyTorch (see **2b**) | speeds up ML (stem separation/tone detection/lyrics) ~10–20× |
| Wwise (optional) | Audiokinetic Launcher | generating the `.wem` automatically |
| DLC Builder (optional) | [releases](https://github.com/iminashi/Rocksmith2014.NET/releases) | packaging the final PSARC |

**2. Clone and install** (the repo is private — Git asks for a GitHub login the first time)

```cmd
cd C:\wherever\you\like
git clone https://github.com/F100Pilot/RockForge.git
cd RockForge
py -3.11 -m pip install -e ".[dev,ml,lyrics]"
```

`py -3.11` explicitly picks Python 3.11 even if another version is the default; `start.bat`
detects 3.11 automatically. (If 3.11 is all you have, `pip install -e ".[dev,ml,lyrics]"`
works too.)

The install takes a while (PyTorch/Demucs/WhisperX, several GB). The `lyrics` extra
(WhisperX) is required for **automatic lyric detection** — without it, "Detect lyrics"
reports "unavailable". If you want to install without that feature, use
`pip install -e ".[dev,ml]"`.

**2b. GPU acceleration (NVIDIA — optional but highly recommended)**

ML (Demucs separation, WhisperX lyrics) runs on **CPU** by default, where a 4-minute song
takes several minutes per stage. With an NVIDIA GPU the time drops drastically (lyric
detection gets close to the ~3 min of online tools).

⚠️ **The `pip install` above installs the CPU-only PyTorch on Windows.** To use the GPU you
have to install the **CUDA** build of PyTorch (respecting the `lyrics` extra's `<2.5` pin).

⚠️ **Uninstall first.** The CPU build and the CUDA build have the **same version number**
(`2.4.1`), so a plain `pip install torch==2.4.1 --index-url …` is ignored by pip ("already
satisfied") and you are left with the CPU build. You have to uninstall first. With CUDA 12.1:

```cmd
py -3.11 -m pip uninstall -y torch torchaudio
py -3.11 -m pip install torch==2.4.1 torchaudio==2.4.1 --index-url https://download.pytorch.org/whl/cu121
```

Confirm you ended up with the **CUDA** build (note the `+cu121` suffix on the version):

```cmd
py -3.11 -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

It should print `2.4.1+cu121 True`. If you see `+cpu` or `False`:
- `…+cpu` → pip didn't replace the build; repeat the `uninstall` above (sometimes there are two
  copies) and reinstall.
- `…+cu121 False` → the NVIDIA driver is missing/outdated; run `nvidia-smi` (it should list
  the GPU and the supported CUDA version) and update the driver at
  https://www.nvidia.com/Download/index.aspx.

With `True`, you're set. RockForge uses `ROCKFORGE_DEMUCS_DEVICE=auto` by default: it detects
the GPU and uses it automatically, falling back to CPU when there is none. You can force it
with `ROCKFORGE_DEMUCS_DEVICE=cuda` (or `cpu`). During lyric detection, the chosen device
appears in the "Lyrics" panel's log (`device: cuda (GPU)`), so you can confirm the GPU is being
used.

**3. Start**

```cmd
.\start.bat
```

Open **http://localhost:8000**. `start.bat` launches Redis + the worker in the background
(logs in `logs\`) and the API in the current window; Ctrl+C stops everything.
With no Redis installed (e.g. a work laptop without admin rights) the tasks run
inside the API itself, one at a time, and closing the tab waits for them.

Notes:
- The first job downloads the ML models (~2 GB extra, only once)
- Generated bundles go to `C:\Users\<user>\Downloads\RockForge`
- In the **Jobs** list each row has a 🗑 button to remove the job (it also deletes the
  generated bundle and the uploaded file, if no other job uses it); running jobs have to
  finish first
- For updates: `git pull` inside the folder (and `pip install -e ".[dev,ml,lyrics]"` if
  `pyproject.toml` has changed)

### Configuration (environment variables)

All configuration is through the environment (create a `.env` at the root — see
`.env.example`). The main ones:

| Variable | Default | What for |
|---|---|---|
| `ROCKFORGE_DEMUCS_DEVICE` | `auto` | `auto` (NVIDIA GPU if available, otherwise CPU), `cuda` or `cpu` — device for all ML |
| `ROCKFORGE_WHISPERX_DEVICE` | (follows `demucs_device`) | overrides the device for lyric detection only |
| `ROCKFORGE_WHISPER_MODEL` | `small` | WhisperX model for lyrics: `tiny`/`base`/`small`/`medium`/`large-v3` (bigger = more accurate and slower; on CPU drop to `base`/`tiny`) |
| `ROCKFORGE_WORK_DIR` | `~/Downloads/RockForge` | where generated bundles are written |
| `WWISEROOT` | (from the Audiokinetic Launcher) | Wwise location for generating the `.wem` |

### The standalone executable (no Python install)

An alternative to `start.bat` for anyone who wants to distribute the app to others without
asking them to install Python, Redis or dependencies: a single executable (`rockforge.exe`)
that starts everything in one process — API + in-memory worker (no Redis), with ffmpeg
included. Double-click → it opens the browser at `http://localhost:8000`.

**What works in the `.exe`:** everything that is Guitar Pro → CDLC, native PSARC, sync,
tones, manual lyric editing — the complete core pipeline. If the user has the ML stack
installed in a Python 3.11 on the PATH (`pip install rockforge[ml,lyrics]`), stem/tone/lyric
detection (Demucs/WhisperX) works too. If not, the app degrades with the same message as
always — no crash.

#### Building the executable

Prerequisites: **Python 3.11** + `pip install pyinstaller` + **ffmpeg**
(`winget install ffmpeg`).

```cmd
cd RockForge

REM 1. Install the core + psarc + native window dependencies + PyInstaller
py -3.11 -m pip install -e ".[dev,psarc,desktop]"
py -3.11 -m pip install pyinstaller

REM 2. (Optional) Create the ffmpeg/ folder with the executable to bundle
mkdir ffmpeg
copy /b "C:\path\to\ffmpeg.exe" ffmpeg\ffmpeg.exe

REM 3. Build
py -3.11 build_exe.py
```

The result is in `dist\rockforge\`. Distribute that whole folder (or use `--zip` /
`--installer` below). The user double-clicks `rockforge.exe` and the app opens **in its own
window** — no browser tab and no black console window.

The `[desktop]` extra is what gives the native window (pywebview, which uses the **Edge
WebView2** already included in Windows — it doesn't bundle a second browser). **Without it the
build still works**, but falls back to the old behavior: it serves and opens the default
browser. `build_exe.py` warns if it is missing, so you don't go through that without noticing.

If you don't put `ffmpeg.exe` inside `ffmpeg/`, the build warns — the app keeps working if the
user has ffmpeg on the system PATH.

**Where to look for errors:** with no console, the app writes everything to
`%USERPROFILE%\Downloads\RockForge\rockforge.log`. It is the first place to check if the
`.exe` won't start.

#### Checking the build before distributing

**Always do these three checks.** An `.exe` has already been distributed with a completely
dead interface: `rockforge.spec` listed the UI files by hand, and when the JavaScript moved out
of `index.html` into `web/app.js` the list didn't follow. `index.html` loaded an `/app.js`
that wasn't in the bundle, and the result was a page that opens and does absolutely nothing.
No test looked at the spec, so nothing caught the error until someone opened the app.

```cmd
REM 1. BEFORE building — the test that guarantees the spec collects everything
REM    in web\. If it fails, the .exe will come out broken; don't build.
py -3.11 -m pytest tests\test_standalone_spec.py -v

REM 2. AFTER building — the UI files must be inside the bundle.
REM    index.html, app.js and the 6 gear images should be listed.
dir /s /b dist\rockforge\_internal\web

REM 3. Run the .exe and confirm the interface is ALIVE (opening it is not enough):
REM    - the version shows in the corner (it comes from an API call, proving the JS ran)
REM    - clicking "New project" opens the 4-step wizard
REM    - F12 → Console shows no errors (the favicon 404 is normal)
dist\rockforge\rockforge.exe
```

If the page opens but no button responds, this is the problem: `/app.js` is returning 404.
Confirm it in `F12 → Network`.

#### Creating an installer (to distribute to others)

To create a Windows-style `.exe` installer (installation wizard, Desktop shortcut, uninstaller
in the Control Panel):

```cmd
REM Prerequisite: install Inno Setup 6 (free)
REM   https://jrsoftware.org/isinfo.php

REM 1. Build the executable (if not done yet)
py -3.11 build_exe.py

REM 2. Build the installer (generates Output\RockForge_Setup.exe)
py -3.11 build_exe.py --installer
```

The file `Output\RockForge_Setup.exe` is the installer — send that single file and the user
double-clicks it to install. It includes everything: the executable, ffmpeg, Wwise templates
and the gear catalogue.

**Portable alternative (no installation):** to create a portable ZIP the user just extracts
and runs:

```cmd
py -3.11 build_exe.py --zip
```

It generates `dist\RockForge_portable.zip` — extract it and run `rockforge.exe`.

#### Notes about the executable

- **It does not include ML** (torch/demucs/whisperx) — they are several GB and fragile to
  package. The `.exe` serves the GP flow and the core pipeline; stem/tone/lyric detection
  needs the Python with the ML dependencies installed.
- **It does not include Wwise or DLC Builder** (license restrictions) — the `.exe` invokes
  them if installed, as always.
- **You have to rebuild** (`py -3.11 build_exe.py`) every time you change the code. For
  development, keep using `start.bat` / `pip install -e .`.
- Idle shutdown is on: closing the browser tab stops the app automatically after ~3 seconds.
  **If there is work in progress** (a build, a stem separation, a lyric detection) the app
  waits for it to finish before exiting — closing the tab in the middle of a build no longer
  cancels it, leaving the project stuck in "running" forever.
- For a **distribution with ML included**, the alternative is to package a portable Python
  (`python-build-standalone`) with a pre-installed venv — heavier (~5–10 GB) but it includes
  everything. See `CLAUDE.md` for details.

### With Docker (alternative)

This is the only route that opens a network port (`8000:8000`) — unlike `start.bat`/the
standalone executable (both bound to `127.0.0.1`), the API here has no authentication at all
by default. Create a `.env` (it stays out of git) next to `docker-compose.yml` with a secret:

```bash
echo "ROCKFORGE_API_TOKEN=$(openssl rand -hex 32)" > .env
docker compose up --build   # API at http://localhost:8000 (UI at /, OpenAPI at /docs)
```

The browser asks for the credentials natively (any username, the token as the password) on the
first visit. Without the `.env`, `docker compose up` refuses to start — this is intentional,
so it never runs exposed without protection.

Note: inside Docker, Wwise is not available — the `.wem` is only generated in a native Windows
run with Wwise installed.

Development:

```bash
pip install -e ".[dev,psarc]"      # core + tests (no ML) — ALWAYS use this one
pip install -e ".[dev,ml]"         # with Demucs/librosa
pip install -e ".[dev,ml,lyrics]"  # + automatic lyric detection (WhisperX)
pytest && ruff check src tests start_standalone.py build_exe.py && mypy
```

The `[psarc]` extra is not optional for testing: without `cryptography`, 17 tests of the
native PSARC (the encrypted container and the SNG binary) skip themselves silently and the
suite stays green without ever having run them.

## How to test the app (end to end)

1. **Automated tests** (no ML, fast): `pip install -e ".[dev,psarc]" && pytest` — the suite
   covers the domain, XML/chords, the GP use case, the API (incl. job removal), GP import,
   lyrics, tone, CPU/GPU device detection, Demucs separation (commands), the native PSARC
   (container/manifests/SNG/encryption), `.rs2dlc`, tags and Wwise (simulated console). Full
   guide in **[`TESTING.md`](TESTING.md)** (coverage map, how to add tests, and the manual
   end-to-end checklist that CI cannot cover).
2. **Start the stack**: `docker compose up --build`. Open `http://localhost:8000`.
   The optional stem/tone/lyric detection downloads the models (Demucs ~2 GB) on first use;
   on CPU, a 4-minute song takes several minutes in the `separate` stage.
3. **Honest smoke test**: use "Inspect tracks" on a **GP3/GP4/GP5 or GP7/GP8** + the
   recording, choose the Lead/Rhythm tracks and create the CDLC. Open the job, fine-tune the
   sync in the viewer (song start, BPM, dragging notes) and use "Apply and rebuild".
4. **Validate the XML**: download the bundle and open the `arrangement_*.xml` files in EOF or
   import them into DLC Builder. This is the validation that counts — the format is de facto,
   with no official schema.
5. **With Wwise (Windows, native)**: run Redis + API + worker outside Docker
   (`uvicorn rockforge.interfaces.api.app:app` and
   `celery -A rockforge.interfaces.worker.celery_app:celery_app worker --pool=solo`),
   with `WWISEROOT` set (the Audiokinetic Launcher sets it). The worker invokes
   `WwiseConsole` automatically and the bundle includes `audio.wem`. The conversion uses a
   template project with Rocksmith-compatible settings (Vorbis **with a seek table** + header
   fix, like DLC Builder) — it requires Wwise 2019/2021/2022/2023. Without a seek table the
   game loads the song but the audio stays silent and the game exits seconds later — if that
   happens, in DLC Builder choose the bundle's `audio.wav` (not `audio.wem`) and let DLC
   Builder do the conversion.
6. **Final PSARC**: import the bundle into DLC Builder (recommended), or configure
   `ROCKFORGE_PSARC_PACKER_CMD` with an external command that takes `{project}`.

## Legal notices

The full text is in [`LEGAL.md`](LEGAL.md). In short:

- **Not affiliated with Ubisoft.** "Rocksmith" is a trademark of Ubisoft Entertainment, used here
  only to say which game the files work with. There is no official Ubisoft statement on CDLC.
- **No songs and no Ubisoft content.** Of the game's format, RockForge carries only what the
  community's public tools have published for years (PSARC/SNG keys, the `.flat` schema, the
  glyph table, the gear catalogue), so that the files it writes can be read by the game. Where
  each piece comes from is in [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
- **The rights over what you create are your responsibility.** Generating CDLC from copyrighted
  recordings and distributing it is unauthorized distribution. Use only your own, free or
  authorized material.
- **Online services.** They are contacted only when you press the button, and each one's terms
  apply to you:
  - **Songsterr**: undocumented API; the tabs are licensed, for personal use; do not
    redistribute imported tabs or the GP5 written from them.
  - **YouTube** (yt-dlp, optional extra): its terms do not allow downloading; personal use.
  - **LRCLIB / iTunes / MusicBrainz**: lyrics and covers belong to their rights holders.
- **Wwise.** Final packaging requires Wwise (Audiokinetic EULA, not redistributable): each user
  installs it. RockForge also delivers a bundle ready to import into
  [DLC Builder](https://github.com/iminashi/Rocksmith2014.NET).
- **No warranty** (MIT licence).

## Licence

RockForge is released under the MIT licence — see [`LICENSE`](LICENSE). Third-party code and data
keep their own licences (Rocksmith2014.NET and three.js: MIT; logic adapted from alphaTab: MPL-2.0;
PyGuitarPro: LGPL-3.0; …), all listed in [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
Whoever distributes the `.exe` or the installer must include that file and `LICENSE`, and, if
`ffmpeg.exe` is put in it, comply with that ffmpeg build's licence.

## Next steps

Proposed (not yet implemented) features are listed in `TODO.md`.

## Documentation (for developers / picking the project back up)

If you lose context and need to rebuild everything, read in this order:

| Document | What for |
|---|---|
| **[`README.md`](README.md)** (this one, in Portuguese; English: [`README.en.md`](README.en.md)) | installing, running, using, distributing — start here to set up a machine |
| **[`CLAUDE.md`](CLAUDE.md)** | architecture (Clean Architecture), the design of each feature, and the **hard constraints** that have already cost us dearly — the source of truth for *why* the code is the way it is |
| **[`TESTING.md`](TESTING.md)** | running/extending the test suite, the coverage map, and the manual end-to-end checklist (ML, Wwise, DLC Builder, in-game) that CI doesn't cover |
| **[`TODO.md`](TODO.md)** | what is done `[x]`, what is missing `[ ]`, and the current known limitations |
| **[`TONE.md`](TONE.md)** | the tone (gear) model and the serialization of `Tones` in the `.rs2dlc` |
| **`docs/RELATORIO-TECNICO.md`** + **`docs/research/`** | the sourced grounding behind each technical decision |
| **[`LEGAL.md`](LEGAL.md)** · **[`LICENSE`](LICENSE)** · **[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)** | legal notice (Ubisoft, copyright, online services), the MIT licence, and the origin/licence of everything third-party — update the last one whenever you include or adapt code or data from another project |

> **Critical constraint** (it already cost a multi-session debug): the `Job.params` JSON
> column has no mutation tracking — writing the **same** dict object
> (`job.params = params`) is a silent no-op in SQLAlchemy. Any incremental write has to
> assign a fresh copy (`{**params}`). See `CLAUDE.md` ▸ *Hard constraints* and
> `TESTING.md` §8.
