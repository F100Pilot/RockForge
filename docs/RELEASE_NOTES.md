### New

- **Score legend**: the "Legend" switch (beside "Fretboard" and "3D highway") shows what every
  mark on the score means, drawn as it appears — including the recording's attacks (the orange
  circles and ticks).
- **About RockForge** (Settings → General): which version and build you are running, and
  **"Copy information for a report"** — version, build, system, the software found and the end of
  the technical log, without passwords, tokens or your user name — to paste into a bug report.
- **Technical log** in `logs/` inside the work folder, rotated so it never grows past ~12 MB. An
  unexpected error now shows an id that is also in the log.

### Fixed

- **The 3D highway grabbed the mouse wheel** while you scrolled the page over it. The wheel now
  moves the camera only after you click the highway; Esc or a click elsewhere lets go.
- **"Wwise not installed" with Wwise installed**: the `WWISEROOT` variable the Audiokinetic
  Launcher leaves often points at a 2024/2025 version, and hid the 2023.1 installed beside it.
- **A failed Wwise conversion read "Wwise not found"**, and a .psarc without sound showed as
  playable. The conversion's own error is now shown, and "Before you use it" says "PSARC without
  sound".

---

### Novo

- **Legenda da partitura**: o interruptor «Legenda» (ao lado de «Braço» e «Pista 3D») mostra o
  que quer dizer cada marca da partitura, desenhada como aparece — incluindo os ataques da
  gravação (as bolas e os traços laranja).
- **Sobre o RockForge** (Definições → Geral): que versão e que build estás a usar, e **«Copiar
  informação para relatório»** — versão, build, sistema, o software encontrado e o fim do registo
  técnico, sem palavras-passe, tokens nem o teu nome de utilizador — para colar num relatório de
  erro.
- **Registo técnico** em `logs/` dentro da pasta de trabalho, em rotação para nunca passar de
  ~12 MB. Um erro inesperado mostra agora um id que também está no registo.

### Corrigido

- **A pista 3D apanhava a roda do rato** ao deslocar a página por cima dela. A roda só mexe na
  câmara depois de clicares na pista; Esc ou um clique fora largam-na.
- **«Não tenho o Wwise» com o Wwise instalado**: a variável `WWISEROOT` que o Audiokinetic
  Launcher deixa aponta muitas vezes para uma versão 2024/2025, e escondia o 2023.1 instalado ao
  lado.
- **Uma conversão do Wwise que falhava dizia «Wwise não encontrado»**, e um .psarc sem som
  aparecia como jogável. Agora mostra o erro da própria conversão, e «Antes de usar» diz «PSARC
  sem som».
