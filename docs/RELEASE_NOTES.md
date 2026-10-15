**RockForge** turns a Guitar Pro file (or a Songsterr tab, or a PDF of one) plus a recording
into a Rocksmith 2014 CDLC: a playable `.psarc` and a DLC Builder project. Free and open
source (MIT). **This is a beta** — please report what breaks:
[Issues](https://github.com/F100Pilot/RockForge/issues).

### Download (Windows)

- **`RockForge-…-Setup.exe`** — the installer (recommended).
- **`RockForge-…-portable.zip`** — the same app, unzip and run `rockforge.exe`.
- **`SHA256SUMS.txt`** — to check the download.

No Python needed; ffmpeg is included. The files are not code-signed, so Windows SmartScreen may
warn: *More info* → *Run anyway*. The installer offers the **extra components** (ticked): audio
analysis, tone and lyric detection, stems, PDF import and YouTube audio — RockForge downloads a
private Python with them (a few GB; PyTorch with CUDA when there is an NVIDIA GPU). They can also
be installed later from the home page or Settings → Software. For a playable `.psarc` you still
need **Wwise** (free from Audiokinetic, it cannot be shipped with the app — RockForge finds it
where the Launcher installs it) and, for the song to appear in the game, the usual CDLC patch.

**New in this beta:** **"Mark by ear"** for tabs that were never synced — press play and hit
**B** on the first beat of every bar, and the notes snap to your taps as you go. **Fixed:** in the
`.exe`, the installed extra components were not used when the "Python for ML" setting was empty —
RockForge now finds them by itself. (Beta 5 brought the fret-hand position editor, redone
automatic FHPs, Bass, the capo and the Download buttons.)

What changed: [CHANGELOG.en.md](https://github.com/F100Pilot/RockForge/blob/main/CHANGELOG.en.md).
User guide: [GUIDE.en.md](https://github.com/F100Pilot/RockForge/blob/main/docs/GUIDE.en.md).

RockForge is not affiliated with Ubisoft and ships no songs: you use your own files and are
responsible for what you make with them ([LEGAL.md](https://github.com/F100Pilot/RockForge/blob/main/LEGAL.md)).

---

**Português:** o RockForge transforma um ficheiro Guitar Pro (ou uma tablatura do Songsterr, ou um
PDF) e uma gravação num CDLC do Rocksmith 2014. Descarrega o **`…-Setup.exe`** (instalador) ou o
**`…-portable.zip`**; não precisa de Python e o ffmpeg vem incluído. Se o SmartScreen avisar:
*Mais informações* → *Executar mesmo assim*. O instalador oferece os **componentes extra**
(análise de áudio, deteção de tom e letra, stems, PDF, áudio do YouTube), que também se instalam
depois na página inicial. Para um `.psarc` jogável continua a ser preciso o **Wwise**. Nesta beta:
**«Marcar a ouvir»** para tabs sem sincronização (carregas em **B** no primeiro tempo de cada
compasso enquanto ouves) e, no `.exe`, os componentes extra instalados passam a ser encontrados
sozinhos. É uma **beta**: diz-nos o que falhar nas
[Issues](https://github.com/F100Pilot/RockForge/issues). Novidades:
[CHANGELOG.md](https://github.com/F100Pilot/RockForge/blob/main/CHANGELOG.md) · guia:
[GUIA.md](https://github.com/F100Pilot/RockForge/blob/main/docs/GUIA.md).
