# Third-party notices

RockForge itself is MIT-licensed (see `LICENSE`). It includes, ports or depends
on the third-party work listed below, each under its own licence. This file
satisfies the attribution those licences require; keep it next to every copy
of RockForge you distribute (source tree, wheel, standalone `.exe`, installer).

*Português: este ficheiro lista o código e os dados de terceiros que o
RockForge inclui, adapta ou usa, com as respetivas licenças. Tem de acompanhar
qualquer cópia distribuída (código, `.exe`, instalador).*

Sections:

1. [Included in this repository](#1-included-in-this-repository)
2. [Code ported (re-implemented) from other projects](#2-code-ported-re-implemented-from-other-projects)
3. [Python dependencies](#3-python-dependencies)
4. [External programs (not included)](#4-external-programs-not-included)
5. [Online services the app can contact](#5-online-services-the-app-can-contact)
6. [Full licence texts](#6-full-licence-texts)

---

## 1. Included in this repository

| What | Where in the repo | From | Licence |
|---|---|---|---|
| Wwise template projects (Rocksmith-compatible Vorbis conversion settings; XML project files only, no Audiokinetic software) | `src/rockforge/infrastructure/packaging/wwise_templates/*.zip` | [Rocksmith2014.NET](https://github.com/iminashi/Rocksmith2014.NET) `src/Rocksmith2014.Audio/Wwise/` | MIT, © 2020 Tapio Malmberg ([text](#rocksmith2014net--mit)) |
| Tone gear catalogue (amps, cabinets, pedals, racks, knob ranges) | `src/rockforge/infrastructure/packaging/gear/tone_gear_data.json` | Rocksmith2014.NET `samples/DLCBuilder.Domain/Tones/tone_gear_data.json` | MIT, © 2020 Tapio Malmberg |
| DLC Builder's default Lead/Rhythm/Bass tones | `src/rockforge/infrastructure/packaging/gear/default_tones/*.json` | Rocksmith2014.NET | MIT, © 2020 Tapio Malmberg |
| Song enumeration model schema (`rsenumerable_root.flat`, `rsenumerable_song.flat`) | `src/rockforge/infrastructure/packaging/psarc/flatmodels/` | Rocksmith2014.NET `src/Rocksmith2014.DLCProject/res/` | MIT, © 2020 Tapio Malmberg |
| Lyric-font glyph table of a vocals SNG (describes the game's own built-in `lyrics.dds`; the texture itself is NOT included) | `src/rockforge/infrastructure/packaging/psarc/vocals_symbols.bin` | Extracted byte-for-byte from vocals SNGs built by DLC Builder (Rocksmith2014.NET) | MIT, © 2020 Tapio Malmberg |
| three.js 0.186.1 (`three.module.js` + `three.core.js`) | `web/vendor/three/` | [three.js](https://github.com/mrdoob/three.js) | MIT, © 2010-2026 three.js authors (full text in `web/vendor/three/LICENSE`) |
| Rack faceplate images | `web/gear_images/*.png` | Drawn for RockForge | MIT (RockForge's own) |

**About the game-format data.** The gear catalogue, the `.flat` schema and the
glyph table describe the Rocksmith 2014 file format and the game's built-in
assets so that files RockForge writes load in the game. They reach RockForge
through Rocksmith2014.NET, which publishes them under MIT; the underlying game
belongs to Ubisoft. No Ubisoft audio, songs, note data, textures or executables
are included. Amp/pedal names in the catalogue (e.g. "Marshall Plexi") are the
names the game uses and may be trademarks of their owners. See `LEGAL.md`.

**About the PSARC/SNG encryption keys.** `packaging/psarc/crypto.py` carries
the two AES keys Rocksmith 2014 uses for its archive table of contents and its
`.sng` files, taken from Rocksmith2014.NET (`src/Rocksmith2014.PSARC/Cryptography.fs`,
`src/Rocksmith2014.SNG/Cryptography.fs`, MIT). They are needed only so that the
files RockForge writes can be read by the game (interoperability); they are the
same constants every public CDLC tool has carried for over a decade.

## 2. Code ported (re-implemented) from other projects

These are re-implementations in Python, not copies of source files, but they
follow the original logic closely enough that the original authors are credited
here. Paths are relative to `src/rockforge/infrastructure/` unless written in full.

| RockForge code | Follows | Licence of the original |
|---|---|---|
| `packaging/psarc/container.py`, `crypto.py`, `sng.py` (with `sng_model.py`, `sng_build.py`, `sng_io.py`), `manifest.py`, `gamedata.py`, `packaging/gear/default_tones.py` (PSARC container, Sng2014 binary layout, manifests, xblock, the phrase generator `_prepare_sections` = `PhraseGenerator.generate`, anchors as `XmlToSng`/`XmlToSngNote`, linked notes and arpeggio shapes as `XmlToSngNote`/`XmlToSngLevel`, default tones as `addDefaultTonesIfNeeded`) | [Rocksmith2014.NET](https://github.com/iminashi/Rocksmith2014.NET) | MIT, © 2020 Tapio Malmberg |
| `packaging/rs2dlc.py` (the `.rs2dlc` DLC Builder project format) | Rocksmith2014.NET `DLCProject.Dto` | MIT, © 2020 Tapio Malmberg |
| `normalize/loudness.py` (volume as DLC Builder's `Volume.fs`) | Rocksmith2014.NET | MIT, © 2020 Tapio Malmberg |
| `packaging/psarc/soundbank.py` (Wwise `.bnk` layout) | Rocksmith2014.NET `src/Rocksmith2014.DLCProject/SoundBank/SoundBank.fs` — the same layout, field by field; first read from `SoundBankGenerator2014` of the [Rocksmith Custom Song Toolkit](https://github.com/rscustom/rocksmith-custom-song-toolkit), whose repository has no licence file | MIT, © 2020 Tapio Malmberg (the toolkit: no licence stated; RockForge relies on the MIT publication of the identical layout) |
| `gpimport/playback.py` (order of repeats, voltas and jumps) and `domain/alphatab.py` (`alphatab_bend`) — **ported code, MPL-2.0** (the header of each file says so); the GP8 `SyncPoint` reading in `gpimport/gpif_parser.py`/`sync_map.py` follows only alphaTab's reading of the file FORMAT, with its own timing (no code taken) | [alphaTab](https://github.com/CoderLine/alphaTab) (`Score._addMasterBarToRepeatGroups`, `MidiPlaybackController`, `Note.finish`; format: `GpifParser`, `MidiFileGenerator`) | MPL-2.0, © Daniel Kuschny and Contributors ([text](https://www.mozilla.org/MPL/2.0/)) |
| `infrastructure/songsterr.py` (endpoints and CloudFront hostnames) | Read from [teaqu/guitar-pro-youtube-sync](https://github.com/teaqu/guitar-pro-youtube-sync) | That project carries no licence; **no code was taken from it**, only the facts of which URLs Songsterr's player uses |
| `infrastructure/youtube_audio.py` (JS-runtime names and priority) | yt-dlp `utils/_jsruntime.py` | Unlicense (public domain) |

**alphaTab is MPL-2.0**, a file-level copyleft licence. The MPL lets
MPL-covered files live inside a larger work under another licence (here MIT),
provided those files stay available under the MPL. RockForge therefore keeps
what it ported from alphaTab in two files of their own,
`src/rockforge/infrastructure/gpimport/playback.py` and
`src/rockforge/domain/alphatab.py`, each headed with the MPL-2.0 notice: those
two files are MPL-2.0 (changes to them stay MPL-2.0), everything else is MIT.

## ffmpeg in the Windows downloads

The installer and the portable zip carry `ffmpeg.exe` (in `_internal/ffmpeg/`)
so the app works without installing anything else. It is an **LGPL build**
(GNU LGPL 2.1 or later) from [BtbN/FFmpeg-Builds](https://github.com/BtbN/FFmpeg-Builds),
unmodified; RockForge only runs it as a separate program. Beside it are its
`LICENSE.txt` and a `SOURCE.txt` naming the exact version and the link to its
source code. The release workflow (`.github/workflows/release.yml`) refuses a
GPL build. Running from Python (`start.bat`) uses the ffmpeg you install
yourself, and none is in this repository.

## 3. Python dependencies

Installed by `pip`, not stored in this repository. The standalone `.exe`
(`build_exe.py`/PyInstaller) DOES bundle the core ones, so their licences apply
to that distribution.

**Core** (`pyproject.toml` `dependencies`, bundled in the `.exe`):

| Package | Licence |
|---|---|
| FastAPI, Pydantic, pydantic-settings, SQLAlchemy, redis-py, tinytag | MIT |
| Starlette, Uvicorn, Celery, Kombu, Billiard | BSD-3-Clause |
| python-multipart, requests | Apache-2.0 |
| certifi (its `cacert.pem` is bundled unmodified) | MPL-2.0 |
| **PyGuitarPro** | **LGPL-3.0-only** — used unmodified as a library; its source is at <https://github.com/Perlence/PyGuitarPro>. In the `.exe` it is an ordinary Python package that can be replaced by any compatible version. |

**Optional extras:**

| Extra | Packages | Licences |
|---|---|---|
| `[psarc]` (bundled in the `.exe`) | cryptography, Pillow | Apache-2.0 OR BSD-3-Clause; MIT-CMU (HPND) |
| `[desktop]` (bundled in the `.exe`) | pywebview | BSD-3-Clause |
| `[ml]` (never bundled) | Demucs, librosa, soundfile, NumPy, SciPy | MIT, ISC, BSD-3-Clause, BSD-3-Clause, BSD-3-Clause |
| `[lyrics]` (never bundled) | WhisperX (and faster-whisper, pyannote.audio), PyTorch, torchaudio | BSD-2-Clause (MIT, MIT), BSD-3-Clause, BSD-2-Clause |
| `[youtube]` (never bundled) | yt-dlp, yt-dlp-ejs | Unlicense (see each package) |
| `[pdf]` (not bundled by default) | **PDF-to-GP5** (the converter; same author as RockForge, installed from <https://github.com/F100Pilot/PDF-to-GP5>), pdfplumber, pdfminer.six, pypdfium2; for pictures RapidOCR (PP-OCR models), ONNX Runtime, OpenCV, Shapely, pyclipper | MIT; MIT, MIT, Apache-2.0 OR BSD-3-Clause; Apache-2.0, MIT, Apache-2.0, BSD-3-Clause, MIT |
| `[postgres]` | psycopg | LGPL-3.0 |
| Banquet backend (optional, user-installed) | query-bandit | MIT |

Model weights downloaded at run time by Demucs/WhisperX (e.g. `htdemucs_6s`,
Whisper, wav2vec2 alignment models) come with their own licences from their
publishers. They are fetched by those libraries; RockForge does not ship them.

ESLint and its plugins (`package.json`) are development tools only.

## 4. External programs (not included)

| Program | Notes |
|---|---|
| **Wwise** (Audiokinetic) | Required for the playable `.psarc` audio. Its EULA forbids redistribution, so RockForge never ships it: each user installs it through the Audiokinetic Launcher and accepts that EULA. |
| **ffmpeg** | Taken from the system when running from Python. The Windows downloads carry an unmodified LGPL build with its licence and source link — see "ffmpeg in the Windows downloads" above. Anyone building their own installer with `build_exe.py` must do the same for the build they put in `ffmpeg/` (an LGPL build, or comply with the GPL if it is one). |
| **Deno** (or Node/QuickJS/Bun) | Optional JavaScript runtime yt-dlp uses; installed by the user, or downloaded by the `.exe`'s extra components from Deno's GitHub releases. Deno is MIT. |
| **Python 3.11 and the extra components** (`.exe`) | Downloaded by the app on the user's request (`infrastructure/components.py`), never shipped inside it: the official `python` NuGet package (PSF licence) into the user's local app data, then the packages of the `[ml]`, `[lyrics]`, `[youtube]` and `[pdf]` extras from PyPI (and PyTorch's CUDA build from download.pytorch.org when there is an NVIDIA GPU), each under its own licence (section 3). |
| **DLC Builder** | Optional, to open the bundle; installed by the user. MIT. |
| **Redis / Memurai** | Message broker for the Celery worker (`start.bat`); installed by the user. |

## 5. Online services the app can contact

RockForge only contacts these when the user presses the button that does it —
except the version check, which asks GitHub's Releases API at most once an hour
(turned off in Settings → General). Each has its own terms of use, which apply
to the user who makes the request.

| Service | Used for | Notes |
|---|---|---|
| Songsterr | Tab import and per-measure video times | Undocumented API; see `LEGAL.md` |
| YouTube (through yt-dlp) | Audio of the video those times belong to | YouTube's terms forbid downloading outside its own features; personal use only |
| LRCLIB (lrclib.net) | Synced lyrics | Open, no key |
| iTunes Search API | Album, year, cover | Apple's terms |
| MusicBrainz + Cover Art Archive | Album, year, cover | MusicBrainz data CC0; cover images belong to their rights holders |
| GitHub (api.github.com) | Whether a newer RockForge is out | Once an hour at most, nothing about the user sent; off in Settings |
| NuGet, PyPI, download.pytorch.org, GitHub releases | The `.exe`'s extra components | Only when the user installs them |

## 6. Full licence texts

### Rocksmith2014.NET — MIT

```
MIT License

Copyright (c) 2020 Tapio Malmberg

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

### three.js — MIT

See `web/vendor/three/LICENSE` (Copyright © 2010-2026 three.js authors).

### alphaTab — MPL-2.0

Mozilla Public License, v. 2.0: <https://www.mozilla.org/MPL/2.0/>.
Copyright © Daniel Kuschny and Contributors.

### PyGuitarPro — LGPL-3.0

GNU Lesser General Public License v3: <https://www.gnu.org/licenses/lgpl-3.0.html>.
Source: <https://github.com/Perlence/PyGuitarPro>.

### certifi — MPL-2.0

Mozilla Public License, v. 2.0: <https://www.mozilla.org/MPL/2.0/>.
Source: <https://github.com/certifi/python-certifi>.
