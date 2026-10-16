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

**New in this beta:** **"Sync automatically" (experimental)** — the recording is analysed and each
bar moved to where its notes sound, the tempo allowed to change over the song; it stays as pending
corrections one Ctrl+Z undoes, and lists the bars to check by ear. It can get it wrong: tested on
synthetic recordings, not yet on real songs — tell us how it goes. Also: an **icon** of its own;
**no mode selected** when a project opens; **no black flash** of console windows in the `.exe`;
**Wwise** found wherever it is installed, with a clear word when the version found cannot be
used; and on the return after a D.C./D.S., only the **last ending** is played (no repeats), with a
warning saying that convention was assumed.

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
2024/2025 não serve). Nesta beta: **«Sincronizar automaticamente» (experimental)**, que analisa a
gravação e encaixa cada compasso nas notas que se ouvem, com o andamento a variar; ícone próprio;
nenhum modo selecionado ao abrir um projeto; sem o ecrã preto a piscar no `.exe`; o Wwise
encontrado em qualquer disco; e, no regresso de um D.C./D.S., só a última casa (com um aviso a
dizer que convenção foi assumida). É uma **beta**: diz-nos o que falhar nas
[Issues](https://github.com/F100Pilot/RockForge/issues). Novidades:
[CHANGELOG.md](https://github.com/F100Pilot/RockForge/blob/main/CHANGELOG.md) · guia:
[GUIA.md](https://github.com/F100Pilot/RockForge/blob/main/docs/GUIA.md).
