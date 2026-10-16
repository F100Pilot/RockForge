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
need **Wwise 2019–2023** (free from Audiokinetic — install **2023.1**; the newer 2024/2025 the
Launcher offers first will not do; it cannot be shipped with the app, and RockForge finds it on any
drive) and, for the song to appear in the game, the usual CDLC patch.

**New in this beta:** a **cover from your computer** can be chosen in the last step of "New
project" (before, only an online result or none; the Cover page still works as before); the
**`.exe` now uses the GPU** — in beta 7 it always fell back to the CPU, so stems and tone and lyric
detection were much slower than they should be with an NVIDIA card; and the **"new version"
notice** comes within the hour instead of within the day.

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
depois na página inicial. Para um `.psarc` jogável continua a ser preciso o **Wwise** (o 2023.1 — o
2024/2025 não serve). Nesta beta: a **capa pode vir do teu computador** no último passo de «Novo
projeto»; o **`.exe` passa a usar a GPU** (na beta 7 caía sempre para o CPU, por isso stems e
deteção de tom e letra eram muito mais lentos com uma NVIDIA); e o aviso de **versão nova** chega
dentro de uma hora em vez de um dia. É uma **beta**: diz-nos o que falhar nas
[Issues](https://github.com/F100Pilot/RockForge/issues). Novidades:
[CHANGELOG.md](https://github.com/F100Pilot/RockForge/blob/main/CHANGELOG.md) · guia:
[GUIA.md](https://github.com/F100Pilot/RockForge/blob/main/docs/GUIA.md).
