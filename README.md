# RockForge

**English** · [Português](README.pt.md)

Turn a **Guitar Pro file** — or a PDF or picture of a tab, or a Songsterr link — and the song's
**recording** into a **Rocksmith 2014 custom song (CDLC)**: a playable `.psarc` and a DLC Builder
project. **Beta**: ready to use, still being tested before 1.0.
Line the notes up with the recording by ear, edit notes, tones and lyrics, and install the
song in the game with one click.

[![Licence: MIT](https://img.shields.io/badge/licence-MIT-blue)](LICENSE)
[![Latest version (beta)](https://img.shields.io/github/v/release/F100Pilot/RockForge?include_prereleases)](https://github.com/F100Pilot/RockForge/releases)
[![CI](https://github.com/F100Pilot/RockForge/actions/workflows/ci.yml/badge.svg)](https://github.com/F100Pilot/RockForge/actions/workflows/ci.yml)

[![Buy me a coffee](https://img.shields.io/badge/Buy%20me%20a%20coffee-PayPal-0070ba?style=for-the-badge&logo=paypal&logoColor=white)](https://paypal.me/F100Pilot)

![The score over the recording's waveform, with the sync tools on the right](docs/media/score-en.png)

## Features

- **Reads Guitar Pro 3, 4, 5 and 7/8 (`.gp`)** exactly: notes, frets, techniques (bends, slides,
  hammer-ons/pull-offs, palm mute, harmonics, vibrato, ties), tempo changes, sections and lyrics.
  Repeats, voltas and D.S./D.C. jumps are played in order.
- **No Guitar Pro file?** Import the tab from a **Songsterr** link (with the per-bar video timings
  people marked there), or convert a **PDF or picture** of the tab with
  [PDF-to-GP5](https://github.com/F100Pilot/PDF-to-GP5).
- **The recording**: your audio file, the audio inside a Guitar Pro 8 file, or the audio of a
  YouTube video.
- **Both outputs, always**: a native, playable **`.psarc`** and a **DLC Builder** project (`.rs2dlc`
  + Song2014 XML + audio + cover), so you can finish or adjust the song in DLC Builder.
- **Lead, Rhythm, Combo and alternate arrangements**, each synced on its own and named as the game
  names them.
- **Sync you check by ear**: song start, a BPM stretch, "Fix from here" (pin a note, measure the
  tempo from there on), drag notes or whole passages, align a bar. Guitar Pro 8 sync points are used
  directly.
- **Edit on the score**: frets, techniques, insert or delete notes, copy and paste, sections.
- **Tones** with the game's amps, cabinets and pedals; tone changes during the song; a tone
  suggested for each part; the tones of the songs you already own, read from your `dlc` folder.
- **Lyrics** from the Guitar Pro file, LRCLIB or the recording (WhisperX), synced to the voice and
  editable word by word.
- **Dynamic difficulty**, chord fingering and hand shapes in the native `.psarc`.
- **Check the `.psarc`** against the faults that made the game crash before, and **install it** in
  the game's `dlc` folder.
- **3D note highway** in the style of Rocksmith, to check the sync while the song plays.
- **Portuguese and English** interface. Runs on your computer; nothing is uploaded.

| | |
|---|---|
| ![Projects page](docs/media/home-en.png) | ![3D note highway](docs/media/highway-en.png) |
| ![Export page with the checklist and Install in the game](docs/media/export-en.png) | |

## What it does not do

- **It does not transcribe audio into notes.** The notes come from a tab (Guitar Pro, Songsterr,
  PDF). Automatic transcription was measured at about one note in three on real songs, so it is not
  offered.
- **Sync is checked by you.** The tools make it quick, but you confirm each track by ear.
- **Bass** arrangements (4/5 strings) and **Guitar Pro 6** (`.gpx`) files are not supported yet —
  export a `.gpx` as GP5 or GP7.
- Tones are chosen from the game's gear by character; the real amp of a recording is not
  identified.

## Get started

**What you need**

- **Windows** (where it is used and tested). macOS and Linux run the app, untested.
- **Python 3.11** exactly ([python.org](https://www.python.org/downloads/), tick *Add Python to
  PATH*, or `winget install Python.Python.3.11`).
- **ffmpeg** (`winget install ffmpeg`).
- For a **playable `.psarc`**: **Wwise** 2019, 2021, 2022 or 2023, installed with the Audiokinetic
  Launcher (it cannot be shipped with the app). Without it you still get the DLC Builder project.
- For the song to **appear in the game**: the CDLC patch (`D3DX9_42.dll`) in the Rocksmith 2014
  folder, as for any CDLC.

**Windows**

1. Download the latest version (currently a **beta**) from
   [Releases](https://github.com/F100Pilot/RockForge/releases) and extract it — or
   `git clone https://github.com/F100Pilot/RockForge.git`, so `start.bat` can update it.
2. Double-click `start.bat`. The first run installs what is needed (several GB for the
   stem/lyric/tone detection) and takes a while.
3. The app opens in the browser at `http://localhost:8000`. Closing the tab stops it.

**macOS / Linux**

```bash
python3.11 -m pip install -e ".[psarc]"          # add ml,lyrics for the detection features
ROCKFORGE_WORKER_MODE=inprocess python3.11 -m uvicorn rockforge.interfaces.api.app:app --port 8000
```

Then open `http://localhost:8000`. The full installation guide — the GPU, the standalone `.exe`,
Docker and every setting — is in the [technical documentation](docs/TECHNICAL.md).

## Documentation

| | English | Português |
|---|---|---|
| User guide | [GUIDE.en.md](docs/GUIDE.en.md) | [GUIA.md](docs/GUIA.md) |
| Technical documentation (install, configuration, build, Docker) | [TECHNICAL.md](docs/TECHNICAL.md) | [TECNICO.md](docs/TECNICO.md) |
| What's new | [CHANGELOG.en.md](CHANGELOG.en.md) | [CHANGELOG.md](CHANGELOG.md) |
| Tests and the manual checks CI cannot do | [TESTING.md](TESTING.md) | |
| Design and constraints of every feature (for developers) | [CLAUDE.md](CLAUDE.md) | |
| Legal notice | [LEGAL.md](LEGAL.md) | [LEGAL.md](LEGAL.md) |

## Support the project

RockForge is free. If it saves you time, you can buy me a coffee:

[![Buy me a coffee](https://img.shields.io/badge/Buy%20me%20a%20coffee-PayPal-0070ba?style=for-the-badge&logo=paypal&logoColor=white)](https://paypal.me/F100Pilot)

Bug reports and ideas are welcome in [Issues](https://github.com/F100Pilot/RockForge/issues). See
[CONTRIBUTING.md](CONTRIBUTING.md).

## Licence and notices

- The code is under the [MIT licence](LICENSE). Third-party code and data keep their own licences
  ([THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)).
- RockForge contains no songs and no Ubisoft content. Use it only with tabs and recordings you have
  the rights to use; distributing CDLC made from copyrighted recordings is unauthorised
  distribution. The terms of Songsterr, YouTube, LRCLIB and the cover services apply to whoever
  uses them. Full text: [LEGAL.md](LEGAL.md).
- Rocksmith is a trademark of Ubisoft Entertainment, and Guitar Pro of Arobas Music. This project
  is not affiliated with or endorsed by either.
