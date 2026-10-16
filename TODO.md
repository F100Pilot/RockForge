# TODO / ideias futuras

Estado do projeto + lista de funcionalidades (concluídas `[x]` e propostas
`[ ]`). Para *como* cada coisa funciona, ver `CLAUDE.md`. Para *como testar*,
ver `TESTING.md`.

## Bolsa para a próxima versão (pedidos e bugs de utilizadores)

Acumula-se aqui o que os utilizadores pedem; quando houver o suficiente, faz-se
tudo de uma vez e um novo bump de versão.

- [x] **Pista 3D com mais mobilidade** (2026-10-16: "em todos os eixos até um
  máximo de 1220 graus horizontalmente e verticalmente de 0 a 90 graus" — lido
  como 120° para cada lado): arrastar roda, roda do rato afasta, duplo clique
  repõe; "Câmara ▾" com os três eixos; guardada no browser.
- [ ] **Juntar duas pistas numa só, com as duas linhas de tempo à vista**
  (Facebook, 2026-10-16: "have both lead and rhythm timelines available one on
  top of each other, these songsterr tabs are a bit of a mess and they have
  split the song into 2 sections when there's only 1 guitarist, i want to
  combine these into 1 ideally by dragging from one timeline to another").
  Hoje: Copiar seleção (Ctrl+C) numa pista e Colar no cursor (Ctrl+V) noutra
  já leva notas de uma para a outra, mas uma de cada vez, sem ver as duas.
  Ideia: (a) uma vista com duas pautas empilhadas (a pista atual + outra
  escolhida), arrastar uma seleção da de baixo para a de cima = colar no mesmo
  instante (as notas viram `note_overrides` da pista de destino, como o colar);
  (b) talvez também no assistente, "juntar as pistas X e Y" num só arranjo
  (fundir as notas das duas pistas GP no parse, com aviso das notas que
  colidem na mesma corda e instante). Ver se a fusão no parse resolve o caso
  do Songsterr sem a vista dupla.

- [x] **Bug: as notas sustentadas tocam como um toque curto na pré-escuta** (corrigido 2026-10-16, ver CLAUDE.md "Tone preview")
  (Liam, 2026-10-16: "when playing back sustained notes in editor they just
  play as a single strum rather than sustained"). Causa: o som das notas no
  editor ignora a sustentação — `playNote` toca sempre 0,24 s e
  `synthesizeArrangement` sempre `NOTE_LEN` = 0,28 s, com um Karplus-Strong de
  decaimento rápido (0,99). Sempre foi assim (não vem da beta 7). Correção:
  durar a sustentação da nota tal como está no ecrã (pelo mesmo warp do tempo
  de início), mínimo ~0,24 s, e um decaimento mais lento (ex. 0,998) para as
  notas longas; `playNote` passa a receber a nota toda.
- [x] **Ver na pauta onde a gravação tem ataques** (feito 2026-10-16, ver CLAUDE.md "The recording's attacks over the score") (Liam, 2026-10-16: "beat
  detection from the audio, the strumming pattern on the left is incorrect
  compared to the right … more fixing crappy tabbing"). Corrigir o ritmo
  sozinho é transcrever, e isso foi medido e abandonado (~1 nota em 3).
  Possível e honesto: marcas finas por baixo da pauta nos ataques que a
  gravação tem (o mesmo envelope de onsets do "Sincronizar automaticamente",
  `_librosa_runner`), e realçar as notas sem ataque perto (±40 ms) e os ataques
  sem nota — o utilizador vê onde a tab mente e corrige no editor de notas.
  Precisa do librosa (componentes extra), como a sincronização automática.

- [x] **Criar o projeto a partir de um PDF ou de uma imagem da tab.** O passo 1
  do "Novo projeto" aceita PDFs e imagens (PNG/JPEG/WebP, um por pista); o
  conversor é o do PDF-to-GP5, instalado como pacote (extra `[pdf]`, fixo a um
  commit desse repositório, que continua a ser onde o conversor evolui). Para
  trazer melhorias do PDF-to-GP5, muda-se o commit no `pyproject.toml`.
- [x] ~~**Deteção de notas a partir da gravação (EXPERIMENTAL).**~~ **Abandonada
  (2026-10-10), a pedido**, e o banco de ensaio apagado. Os modelos abertos
  acertaram cerca de uma nota em cada três; o Songsterr AI chegou aos 73% e o
  `.gp` que ele exporta já entra no "Novo projeto".
- [x] **Instalar no jogo e verificar o PSARC.** Na página Exportar, "Instalar
  no jogo" copia o `.psarc` para `dlc/RockForge/` (substitui a cópia de uma
  versão anterior; avisa se houver outra cópia posta à mão) e "Antes de usar"
  verifica o ficheiro construído contra as regras que já fizeram o jogo
  crashar. A subpasta `dlc/RockForge` é lida pelo jogo (confirmado 2026-10-09).
- [x] **Pistas com o nome do jogo.** As abas e listas mostram "LEAD 1",
  "LEAD 2", "RHYTHM", "COMBO" (numeradas só quando há duas no mesmo caminho),
  e o PSARC passa a dizer ao jogo que a Lead alternativa é a 2.ª Lead
  (`SongPartition`, antes 1 em todas). Falta confirmar no jogo como aparece.
- [x] **Posição dos dedos nos acordes.** Cada acorde leva os dedos (os do
  ficheiro GP quando os tem, senão a regra das CDLC feitas à mão — 79 de 100
  formas iguais às duas dos Daughtry), o nome e uma "hand shape" por sequência
  do mesmo acorde, no SNG nativo e no XML do DLC Builder. Por confirmar no
  jogo: `docs/TESTES-NO-JOGO.md` #12.
- [x] **Importar a tab do Songsterr (sem ficheiro GP).** No passo 1 cola-se o
  link do Songsterr: as pistas são descarregadas e escritas num GP5, e o passo 3
  já mostra os vídeos com os tempos por compasso da mesma música, e o áudio
  desse vídeo é descarregado com o yt-dlp (com a sessão de um browser se o
  YouTube recusar). Por validar contra o Songsterr e o YouTube reais:
  TESTING.md §7d-quinquies.
- [x] **Letra encontrada online e sincronizada.** Pesquisa no LRCLIB; "Usar"
  carrega a letra sincronizada no editor, "1ª palavra = cursor"/−/+ acertam o
  início, e "Sincronizar com a gravação" mede cada palavra na voz com o
  WhisperX (alinhamento do texto conhecido, não transcrição). Por validar
  contra o LRCLIB real e com o WhisperX instalado: TESTING.md §7c-bis.
- [x] **Álbum, ano e capa automáticos.** Pesquisa por título + banda no iTunes
  e no MusicBrainz/Cover Art Archive; o utilizador escolhe entre as capas
  encontradas (passo 4 do assistente e página Capa). Download só dos servidores
  de imagens desses serviços. Confirmado a funcionar pelo utilizador com os
  serviços reais (2026-09-26); o sandbox continua sem acesso — TESTING.md §7d-sexies.
- [x] **Sincronização pelos tempos do Songsterr.** O princípio do
  guitar-pro-youtube-sync: tempos por compasso marcados por pessoas, lidos da
  API (não documentada) do Songsterr e aplicados como os sync points do GP8. Só
  os tempos — o MP3 é do utilizador. Por validar contra a API real (bloqueada
  no sandbox): TESTING.md §7d-quinquies.
- [x] **Áudio embebido no `.gp`.** O assistente usa a gravação que vem dentro de
  um ficheiro GP8 (a que os sync points descrevem) sem pedir MP3.
- [x] **ML a partir do `.exe`, através de um Python 3.11 externo.** O executável
  não pode *importar* o Demucs/WhisperX/librosa (tem o seu próprio Python), mas
  todas essas fases correm em **subprocesso** — o que faltava era não passar
  `sys.executable` (que no `.exe` é o próprio `.exe`). `ROCKFORGE_ML_PYTHON`
  (⚙️ Definições) aponta para um Python com `[ml,lyrics]` e o `.exe` ganha
  stems, deteção de tom e de letra e "Corrigir daqui". Ver
  `infrastructure/ml_python.py` e o §7d-quater do TESTING.md (por validar numa
  build Windows real).

## Sincronização automática — REMOVIDA (2026-08)

Todas as funcionalidades de sincronização **automática** foram removidas a
pedido do utilizador, por não darem resultado utilizável no material real dele:
sincronização automática (andamento médio), sincronização dinâmica, import de
mapa de tempo MIDI (RIPX), sincronização pela bateria com rede neural, e o
painel de análise/diagnóstico com gráfico de desvio. Ficaram **só as ferramentas
manuais** (Passo 1, andamento/BPM, alinhar por compasso, arrastar/marcar/mover,
novo beat), que o utilizador consegue verificar de ouvido.

Estão todas no histórico do git com os algoritmos e os modos de falha medidos
documentados nas mensagens de commit, caso valha a pena ressuscitar alguma.

## Concluído recentemente (resumo — detalhe em CLAUDE.md)

- [x] **Aviso de versão nova + componentes extra instalados pelo `.exe`**
  (2026-10-15): `update_check.py` (GitHub Releases, 1×/dia, não para checkouts
  git), `components.py` (Python 3.11 do NuGet + extras `[ml,lyrics,youtube,pdf]`
  + Deno, a partir do instalador, da página inicial ou de Definições →
  Software), PDF via `_pdf_runner.py`, Wwise detetado na pasta do Launcher.
  O teste das Releases instala-os no `.exe` congelado e usa librosa, PDF-to-GP5
  e Demucs.

- [x] **Arranjo de baixo (Bass)** (2026-10-15): pista Bass de 4/5 cordas no
  assistente e em "Editar info", codificada como o DLC Builder (ArrangementName
  3, RouteMask 4, pathBass, afinação a partir de E1 A1 D2 G2, tom por defeito
  Eden WT550), baixo de 5 cordas dobrado em quatro com aviso, afinação abaixo de
  -4 escrita uma oitava acima a 220 Hz. **Por testar no jogo.**

- [x] **Recarregar o ficheiro GP** (`/jobs/{id}/reload-gp`): substitui o GP de um
  job existente por uma reexportação (editaste uma nota no Guitar Pro) sem perder
  os ajustes — forka um novo job herdando afinação/sync/tons/letra/capa, só troca
  o `gp_path`. Botão "Recarregar ficheiro GP" no painel de sincronização.
- [x] **Símbolos gráficos na partitura**: nome do acorde derivado (na faixa
  inferior), bend como seta com quantidade (full/½), vibrato como linha de
  sustain ondulada, slide/harmónico/hammer/pull com glifos.

- [x] **Suporte a Guitar Pro 7/8 (`.gp`)**: parser GPIF/XML nativo
  (`gpimport/gpif_parser.py`), sem dependência extra (o `.gp` é um ZIP com
  `Content/score.gpif` em XML). Dispatch automático por formato em `inspect_gp`/
  `parse_gp_track`. Cobre afinação, tempo, técnicas (HO/PO via Hopo, palm mute,
  slide, bend), secções e letra (apanhada da pista Vocals, alinhada às notas com
  suporte a melisma `_`). Só **GP6 (`.gpx`)** continua sem suporte (container
  binário proprietário).
- [x] **Letra do GP alinhada às notas** (`distribute_syllables`): uma sílaba por
  ataque de nota (em vez do bloco fixo de 2s), com marcadores Rocksmith (`-`
  junta sílabas, `+` quebra de linha) e melisma (`_` estende a sílaba anterior).
- [x] **Deteção automática de letra** (`/jobs/{id}/detect-lyrics`): Demucs isola
  os vocais + WhisperX faz force-align. Tarefa Celery assíncrona; estado em
  `params["lyrics_status"]`/`["lyrics_log"]`. WhisperX corre num **subprocesso**
  (`_whisperx_runner.py`) para evitar o deadlock CUDA do faster-whisper dentro
  do Celery. Editor de letra na UI ("Letras") com edição palavra-a-palavra,
  arrastar palavras na partitura, e exportar LRC.
- [x] **Deteção automática de tom** (`/jobs/{id}/detect-tones`): separação
  Demucs `htdemucs_6s` + análise espectral classifica `clean`/`crunch`/
  `high_gain` e sugere presets de gear (amp/cabine/pedais) reais. Honesto: NÃO
  identifica o amp real, classifica o *carácter* do som.
- [x] **Presets refeitos contra o hiss** (2026-10-04): a partir de dois tons
  CDLC que o utilizador acha limpos (Daughtry, "Crazy" e "It's Not Over" — não
  são da Ubisoft) — EQ de 5 bandas antes do amplificador a cortar 63 Hz e
  5,7 kHz, EQ de estúdio depois, compressor + EQ + reverb nos cleans, nada de
  pedal de distorção empilhado num amp quase no máximo; o `Loudness2` dos
  Plexi (88 de origem) passa a estar definido. Cópias por mexer atualizam-se
  pela cadeia inteira (`tone_preset_history.py`). Por ouvir em jogo.
- [x] **Modelo de tom (gear) + construtor na UI**: `domain/tone.py` + catálogo
  vendido; tons custom serializados no `.rs2dlc` `Tones` e no PSARC. Ver
  `TONE.md`.
- [x] **PSARC nativo sempre** (`psarc_mode=native` por defeito): cada job produz
  Bundle (DLC Builder) **e** `.psarc` (SNG cifrado + manifestos).
- [x] **Ficheiro `.phrase-levels`**: gerado junto ao `.rs2dlc` — sem ele o DLC
  Builder falha com `FileNotFoundException` ao compilar.
- [x] **Sync em massa** (`RebuildIn.apply_to_all`): aplicar tempo/anchors a todos
  os arranjos de uma vez (checkbox "Aplicar sync a todos").
- [x] **Persistência de BPM/tempo entre separadores** de arranjo na UI.
- [x] **Playback via Web Audio API** (não o `<audio>`): seek sample-accurate,
  sem deriva a meio da música.
- [x] **Volume da música + destaque da palavra ativa** durante o playback.
- [x] **Executável standalone** (`build_exe.py`, PyInstaller, worker in-process
  sem Redis) + **instalador Windows** (Inno Setup) + **ZIP portátil**.

## Estado atual / limitações conhecidas

- **Letra/tom precisam de GPU para ser rápido.** Em CPU a separação Demucs
  demora minutos. O `pip install torch` no Windows é só-CPU — é preciso o build
  CUDA (docs/TECNICO.md §2b). Confirmar no log: `device: cuda (GPU)`.
- **Dynamic Difficulty FUNCIONA no jogo (confirmado 2026-08-25)** — sobe e o
  nível é guardado. Chegou lá por byte-diff contra um build do DLC Builder da
  mesma música (ambos os `.psarc` descodificados e comparados campo a campo);
  as sete correções (nomes de frase únicos, frases a sair dos níveis acima do
  seu teto, `Techniques`, eventos de palco, as três densidades
  `SongDiff*`, `LastConversionDateTime` e a lista de secções) foram numa só
  leva, por isso **não se sabe qual delas resolveu** — não remover nenhuma por
  parecer cosmética. Detalhe e o resultado negativo útil (o `Hash`/`NoteFlags`
  das notas ficaram a 0 e portanto NÃO são precisos) em `CLAUDE.md`.
  Continua a ser uma **rampa por densidade**, não uma passagem DDC musical: a
  seleção de notas por nível é por força métrica, não frascada musicalmente —
  para esse fraseado o caminho continua a ser o DLC Builder.
- **SNG nativo não validado byte-a-byte** contra um SNG retail (não há ficheiro
  de referência em CI) — só round-trip `read_sng∘write_sng` + validação manual
  no jogo (vários bugs de renderização já isolados e corrigidos por byte-diff
  contra PSARC do DLC Builder — ver `CLAUDE.md`).
- **Baixo nunca tocado no jogo**: o arranjo Bass segue a codificação do DLC
  Builder e passa a verificação do PSARC, mas falta confirmá-lo no Rocksmith.
- **GP6 (`.gpx`) não suportado** (container binário proprietário). GP3/GP4/GP5 e
  GP7/GP8 (`.gp`) são suportados.
- **Capa de álbum: resolvido.** O PSARC nativo converte a capa real para **DDS
  DXT1** em 64/128/256 (`gamedata.album_art_dds`, precisa de Pillow do extra
  `[psarc]`), o manifesto leva o URN e o xblock aponta-lhe — verificado ponta a
  ponta a descodificar a cor do bloco DXT1 de dentro do `.psarc` empacotado. Sem
  Pillow, ou com imagem ilegível, degrada para o placeholder neutro em vez de
  falhar. O `<albumArt>` do XML também leva o URN, mas isso é só completude para
  o caminho do DLC Builder (o jogo lê o manifesto, e o XML dos instrumentos nem
  sequer entra no `.psarc`).
- **Não corre no GitHub Pages** (precisa de backend Python + Redis + ML); é uma
  app desktop/servidor local por design.

## Antes de publicar (licenças — ver `THIRD_PARTY_NOTICES.md`)

- [x] `LICENSE` (MIT), `THIRD_PARTY_NOTICES.md` (origem e licença de tudo o que
  vem de terceiros, com o texto MIT do Rocksmith2014.NET), `LEGAL.md` (aviso
  legal PT/EN: Ubisoft, direitos de autor, serviços online, sem garantia),
  secções "Avisos legais"/"Licença" na documentação técnica e "Licença e
  avisos" nas páginas iniciais; o `.exe`, o zip portátil e
  o instalador levam os três ficheiros (`build_exe.copy_legal_files`,
  `LicenseFile` no `installer.iss`). Guardado por `tests/test_legal_files.py`.
- [x] **alphaTab é MPL-2.0.** O código portado está em dois ficheiros próprios
  com o cabeçalho MPL-2.0: `gpimport/playback.py` e `domain/alphatab.py`
  (`alphatab_bend`, que saiu do `music.py`). A leitura dos SyncPoints só segue o
  formato do ficheiro, com temporização própria — fica MIT.
- [x] **PDF-to-GP5 tem licença MIT** (desde o seu commit `c30a701`; o commit
  fixado no `[pdf]` já a inclui).
- [x] **Toolkit sem licença; o `.bnk` apoia-se no Rocksmith2014.NET (MIT).** O
  repositório do toolkit não tem ficheiro de licença (confirmado 2026-10-15). O
  `soundbank.py` tem o mesmo layout, campo a campo, que o `SoundBank.fs` do
  Rocksmith2014.NET, publicado em MIT — é nessa publicação que assenta.
- [x] **ffmpeg dentro do instalador.** O workflow de lançamento junta uma build
  LGPL (BtbN), com o `LICENSE.txt` e um `SOURCE.txt` com o link para o código
  exato, e recusa uma build GPL.

## Pronto para publicar (2026-10-14, como no PDF-to-GP5)

- [x] Página inicial em inglês (`README.md`) e português (`README.pt.md`), com
  capturas de ecrã de músicas inventadas (`docs/media/`), emblemas e o botão
  PayPal; os README antigos passaram a `docs/TECHNICAL.md`/`docs/TECNICO.md`.
- [x] `CHANGELOG.md`/`CHANGELOG.en.md` (versão 0.10.0 beta 1 — a 1.0.0 fica para depois da beta), `CONTRIBUTING.md`,
  `SECURITY.md`, modelos de issues bilingues, `.github/FUNDING.yml`.
- [x] Mensagens do `start.bat` em português e inglês.
- [x] Histórico verificado: sem segredos, e-mails pessoais, áudio ou ficheiros
  de músicas.
- [ ] Ativar no GitHub: repositório público, *Private vulnerability reporting*
  (Settings → Code security), e as *Issues*.

## Anúncio (textos para a CustomsForge e o Reddit)

Os dois fóruns são em inglês, por isso os textos também. Antes de publicar:

- [x] Release `v0.10.0-beta.2` publicada (pre-release) com o instalador, o zip
  portátil e o `SHA256SUMS.txt`, construídos e testados pelo `release.yml`.
- [ ] Apagar a Release e a tag `v0.10.0-beta.1` (ficou sem ficheiros), tornar o
  repositório público e ligar o *Private vulnerability reporting*
  (Settings → Security).
- [ ] Instalar a Release num PC teu (o instalador, sem Python) e criar um CDLC
  com o Wwise até ao jogo — o teste automático cobre a app, não o Wwise nem o
  jogo.
- [x] Capturas de ecrã em `docs/media/` e o vídeo tutorial (`tutorial-en.mp4`,
  `tutorial-pt.mp4`), feitos com uma música e capas inventadas.
- [ ] Reler as regras do fórum de ferramentas da CustomsForge e as do
  r/rocksmith (autopromoção, *flair*, o que dizem sobre CDLC) no dia em que
  publicares.
- [ ] No Reddit, carregar o `tutorial-en.mp4` (ou um excerto) como vídeo do
  próprio post, ou no YouTube, e pôr o link no texto: um vídeo vê-se no
  Reddit, um link para um ficheiro no GitHub não.
- [ ] Nunca pôr links para CDLC com música comercial nas respostas — só para a
  ferramenta.

### CustomsForge (fórum, secção de ferramentas)

Título: `RockForge 0.10 beta — free, open-source Guitar Pro → Rocksmith 2014 CDLC builder (Windows installer, native PSARC + DLC Builder project)`

```markdown
Hi all,

I've been building **RockForge**, a free and open-source (MIT) app that turns a
**Guitar Pro file + a recording** into a Rocksmith 2014 CDLC. It started as a
personal project; it's now at a public beta and I'd like the community's
feedback.

**Download (Windows):** https://github.com/F100Pilot/RockForge/releases
— an installer or a portable zip. No Python needed, ffmpeg included.
**Tutorial video and source:** https://github.com/F100Pilot/RockForge

**What it does**
- Reads **GP3/GP4/GP5 and GP7/GP8 (.gp)**: notes, frets, techniques (bends,
  HO/PO, slides, palm mute, harmonics, vibrato, tapping, ties), tempo changes,
  sections, and repeats/voltas/D.S.-D.C. unrolled the way they are played.
  A Songsterr link or a PDF/picture of a tab can also be the starting point.
- Outputs **both** a playable **native .psarc** and a **DLC Builder project**
  (.rs2dlc + Song2014 XMLs + audio + cover), so you can always finish or
  tweak it in DLC Builder.
- **Lead, Rhythm, Combo and alternate arrangements** (LEAD 2, RHYTHM 2), named
  and numbered as the game shows them, each synced on its own.
- Chords with **finger positions and names** (hand shapes), **linked notes**
  from legato slides, and **arpeggios** detected from let-ring runs.
- **Sync tools you check by ear**: song start, BPM, "fix from here" (pin a
  note, measure the tempo from that point on), drag notes or whole passages,
  align by bar, a main track the others follow, undo/redo. Guitar Pro 8 sync
  points and the audio embedded in a .gp file are used directly.
- **Songsterr link** (optional): the tab, the per-measure video timestamps
  people marked there, and the audio of that same video.
- **Lyrics**: from the GP file (timed on the vocal line), LRC / UltraStar,
  a search on LRCLIB, or experimental detection (WhisperX), with an editor
  beside the score.
- **Tones**: a gear editor with the real Rocksmith catalogue (amps, cabs,
  pedals, racks), a library across projects, the tones of every song in your
  dlc folder to copy from, timed tone changes, and experimental suggestions
  per part of each track. With no tones of your own, DLC Builder's default
  tones are used.
- **Check and install**: RockForge checks its own PSARC for the faults that
  used to crash the game, and "Install in the game" copies it into a folder
  of its own inside dlc, replacing the previous version.
- Generated Dynamic Difficulty, phrases like DLC Builder's, showlights, album
  art (with an online cover/album lookup), a note/section editor, a 3D note
  highway preview, batch creation for whole albums, PT/EN interface.

**What it does NOT do (honest limits)**
- No audio-to-tab transcription: you need a Guitar Pro file (or a Songsterr
  tab, or a PDF of one). An audio-transcription path was measured and dropped
  — about one note in three on real distorted guitar.
- No bass arrangements yet; GP6 (.gpx) is not supported (export as GP5/GP7).
- Dynamic Difficulty is a density ramp, not a full DDC pass — for DLC
  Builder's DDC, open the bundled project there.
- Tone suggestions classify the sound's character; they don't identify the
  real amp.
- Tested in game on my own songs. It's a beta — please report what breaks.

**Requirements**
- Windows for the installer (Python 3.11 + start.bat or Docker for the
  source install).
- **Wwise 2019/2021/2022/2023** for the playable .psarc audio (free from
  Audiokinetic, but its licence doesn't allow bundling it). Without Wwise you
  still get the DLC Builder project.
- The CDLC patch, as for any custom.
- Source install only (the extras are too big or can't be bundled): PDF
  import, stem/lyric/tone detection (Demucs, librosa, WhisperX), YouTube audio.
- The installer isn't code-signed yet, so SmartScreen may warn: More info →
  Run anyway. SHA256SUMS.txt is on the release page.

**Credits**: huge thanks to iminashi's **Rocksmith2014.NET / DLC Builder**
(MIT) — the SNG/PSARC format work, Wwise templates, gear catalogue and phrase
generator RockForge follows; **alphaTab** (playback order and GP8 sync
semantics); **teaqu/guitar-pro-youtube-sync** (the idea of using Songsterr's
video timestamps); and this community's documentation over the years. Full
list in THIRD_PARTY_NOTICES.md.

**Please note**: RockForge is not affiliated with Ubisoft and contains no
songs. Use it with material you own or are allowed to use; Songsterr tabs and
YouTube audio are for personal use only — please don't redistribute imported
tabs or CDLCs with copyrighted recordings. Details in LEGAL.md.

Feedback, bug reports and feature requests are very welcome — GitHub issues
or here.
```

### Reddit (r/rocksmith)

Título: `I made a free, open-source app that turns Guitar Pro files into Rocksmith 2014 CDLC — Windows installer, sync tools, 3D preview`

```markdown
Hey everyone! I've been working on **RockForge**, a free, open-source (MIT)
app that builds Rocksmith 2014 customs from a **Guitar Pro file + a
recording**. It just reached a public beta with a Windows installer (no
Python needed, ffmpeg included).

**Download:** https://github.com/F100Pilot/RockForge/releases
**Tutorial video + source:** https://github.com/F100Pilot/RockForge

**Highlights**
- GP3/4/5 and GP7/8 → a playable **.psarc** *and* a **DLC Builder project**
- Lead / Rhythm / Combo / alternate arrangements, named like in game
- Chord finger positions, linked notes, arpeggios
- Sync you check by ear: song start, BPM, "fix from here", drag notes, align
  bars, undo/redo — plus Guitar Pro 8 sync points and embedded audio
- Optional **Songsterr link**: tab + human-marked bar timings + that video's
  audio
- Lyrics from the GP file, LRC, LRCLIB or (experimental) auto-detection
- Tone editor with the real Rocksmith gear, tone library, the tones of your
  own dlc folder, tone suggestions
- Checks its own PSARC and installs it in your dlc folder with one click
- Dynamic Difficulty, album art lookup, 3D highway preview, batch mode,
  Portuguese/English UI

**Limits**: no audio-to-tab transcription (you need a GP file, a Songsterr
tab or a PDF of one), no bass yet, no .gpx. You need **Wwise** (free from
Audiokinetic, can't be bundled) for the playable PSARC audio, plus the usual
CDLC patch. Beta — tested in game on my own songs, so please tell me what
breaks.

Built on the shoulders of DLC Builder / Rocksmith2014.NET (iminashi) and
alphaTab — thank you! Not affiliated with Ubisoft, no songs included; please
only use material you own or are allowed to use.

Feedback and bug reports very welcome!
```

## Ideias futuras (não implementadas)

- [ ] **Pré-visualizar o *note highway* em 3D (three.js)**: desenhar a
  autoestrada de notas do Rocksmith no browser, **a partir do `.sng` já
  construído** (`crypto.unpack_sng` + `read_sng`, que já existem) e não do
  `Arrangement` do domínio — assim mostra o que está mesmo no binário. Com um
  slider de nível de DD, mostraria: as notas por nível, as caixas de âncora com
  o seu traste/largura e `phrase_iteration_id`, os sustains ao comprimento real,
  acordes condensados (alta densidade) vs caixa completa, e as fronteiras das
  iterações de frase.

  **Porquê:** todos os bugs nativos de SNG que custaram sessões inteiras —
  o borrão lateral (faltava `HIGHDENSITY`), os "pilares altos" (sustain
  re-inflado por um stretch local), o crash à entrada de uma frase (âncora
  sem cobertura), a âncora do início a enrolar para a ÚLTIMA frase, os
  handshapes a crashar — são **geometria de notas e âncoras**, e a única
  forma de os ver hoje é construir o PSARC, abrir o jogo e tocar até ao
  sítio. Isto trocaria esse ciclo por arrastar um slider.

  **Limite honesto:** renderiza a NOSSA leitura do binário. Se o jogo
  interpretar mal algo que escrevemos, a pré-visualização mostra-o correto —
  não teria apanhado o `VOCAL_NOTE = 254` nem o `zlength = 0` do bloco
  parcial, que são interpretação do jogo e não geometria. Encurta o ciclo
  para uma classe real de bugs; **não substitui o teste no jogo**.

  **Constrangimentos:** o `web/` não tem hoje nenhuma dependência em runtime
  nem build step, por isso o three.js (MIT) teria de ser **vendorizado** em
  `web/` como ES module + importmap — **CDN está fora**, a app é local-first,
  distribui-se como `.exe` e tem de funcionar offline. O `rockforge.spec` já
  percorre todo o `web/`, por isso entra no `.exe` sozinho. Precisa de um
  endpoint que sirva o SNG descodificado em JSON (ou estender o
  `/arrangements` com níveis e âncoras). O código novo fica num ficheiro
  próprio dentro do alcance do ESLint; a biblioteca vendorizada fora.

  **Onde NÃO vale a pena 3D:** gear no editor de tons (já há faceplates 2D
  com knobs funcionais, e são explicitamente só cosméticos), braço/acordes
  (um diagrama plano é melhor e é o que a concorrência faz), e
  waveform/espectrograma (um espectrograma 2D seria estritamente mais útil).

- [x] **Deteção automática de afinação para jobs GP**: `POST
  /jobs/{id}/detect-tuning` estima o desvio em cents (A440) com
  `librosa.estimate_tuning` sobre a gravação; é apenas uma proposta — o
  utilizador revê e aplica via "Aplicar e reconstruir" (botão "Detetar
  afinação (cents)" no painel de afinação). A afinação das cordas (drop/open)
  continua a vir do ficheiro GP — não é detetável de forma fiável a partir de
  áudio polifónico.

- [x] **Pré-visualização de áudio por arranjo (Lead/Rhythm)**: botão "▶
  Pré-visualizar este arranjo" sintetiza (Web Audio, osciladores) e toca as
  notas do arranjo selecionado, isoladamente da gravação — útil para validar
  o split experimental Lead/Rhythm.

- [~] **Separação fina de guitarras (Banquet) — INTEGRADO, EM TESTES**:
  adaptador `BanquetSeparator` (`infrastructure/separation/banquet_adapter.py`)
  no port `StemSeparator`, selecionável via `ROCKFORGE_STEM_SEPARATOR=banquet`
  (Demucs continua por defeito). O **Banquet** (`query-bandit`, **MIT**, MoisesDB,
  arXiv 2406.18747) separa por **classe** — elétrica/acústica, limpa/distorcida —
  e bate o htdemucs_6s na guitarra/piano. É **query-based** (um clip de
  referência por classe, em `ROCKFORGE_BANQUET_QUERIES`); pesos no Zenodo
  (`ev-pre-aug.ckpt`). Ativável **na app** (menu "⚙️ Definições" — escolher
  backend + caminhos, com validação ✓/✗) ou por env vars; as definições da UI
  vivem em `work_dir/settings.json` (partilhado API↔worker). Setup em
  `TESTING.md §7g`; testado em `test_banquet_adapter.py` + `test_settings.py`
  (o modelo não corre em CI).
  **Falta:** validar a qualidade em ficheiros reais (o maintainer testa e
  analisa). **Limite que se mantém:** duas guitarras da *mesma* classe
  (Lead+Rhythm ambas distorcidas) continuam inseparáveis — para isso, a fonte
  sintetizada por arranjo. Futuro possível: seletor na UI + clips embutidos.

- [x] **Testar tons criados na partitura** ("🎸 Testar tom"): ouvir o *carácter*
  de um tom criado aplicado às notas (tique + fonte sintetizada), via uma voz
  Web Audio partilhada (`voiceNote`) com waveshaper de distorção derivado dos
  descritores/knob de Gain/pedais do tom. Honesto: é aproximação do carácter
  (limpo/crunch/distorcido + brilho), NÃO o som real do amp (esse só no
  jogo/DLC Builder).

- [x] **Barra de pesquisa no construtor de tons**: cada seletor de gear
  (amplificador, cabine, e pedais pré/pós/rack) tem uma pesquisa que filtra a
  lista por nome/key, mantendo sempre a escolha atual visível (nunca troca o
  gear silenciosamente). `populateGearSelect(..., filter)` no `web/index.html`.

- [~] **Knobs funcionais alinhados sobre a imagem do gear** (`KNOB_LAYOUTS`,
  `web/index.html`): um gear com layout feito à mão mostra a sua imagem com os
  knobs funcionais posicionados EXATAMENTE sobre os knobs desenhados (tamanho em
  % da imagem, escala sozinho) e os valores numa faixa POR BAIXO do aparelho.
  Sem layout → faixa de knobs genérica (sem imagem). Feito para
  `Rack_StudioCompressor` (Threshold→knob "Input", Attack/Release/Ratio nos knobs
  homónimos; 2 knobs extra da arte ficam decorativos). **Falta mapear os
  restantes, um a um** — para cada, medir `(x,y,r)` de cada knob na imagem
  (`web/gear_images/<key>.png`) e ligar aos knobs reais do catálogo por nome:
  - `Rack_StudioGraphicEQ` (588×232) — 10 knobs reais (Bass, Bass Freq., Low-Mid,
    Low-Mid Freq., Mid, Mid Freq., High-Mid, High-Mid Freq., Treble, Treble
    Freq.); a arte tem *sliders*, não knobs → decidir se os controlos ficam nos
    sliders desenhados ou numa faixa abaixo.
  - `Rack_StudioEQ` — Parametric EQ, 10 knobs reais; a arte só desenha 3
    (Frequency/Gain/Q) → mapear subset + restantes numa faixa abaixo.
  - `Rack_TapeEcho` — 5 reais (Time, Feedback, Mix, Hi Filter, Lo Filter); arte
    tem 3 (Delay/Repeats/Level) → 3 sobre a arte + 2 numa faixa abaixo.
  - `Rack_StudioPlate` — 4 reais (Decay, Diffusion, Mix, Tone); arte tem 3
    (Pre-Delay/Decay/Tone).
  - `Rack_StudioChamber` — 4 reais (Decay, Diffusion, Mix, Tone); arte tem 3
    (Room Size/Damping/Wet-Dry).
  - Depois estender também a **amps e cabines** (hoje amp usa faceplate genérica
    com knobs por cima; cabine mostra só a imagem). Enquanto um gear não tem
    layout, fica a versão genérica.

- [x] **Imagens de gear empacotadas + fallback** (`GET /gear-image/{key}`,
  `_gear_image_dirs`): procura primeiro em `work_dir/gear_images/` (override do
  utilizador) e depois nas imagens do repo (`web/gear_images/`). RockForge traz a
  arte própria dos racks (Compressor, ParaGraphic EQ, Parametric EQ, Tape Echo,
  Plate, Chamber), sem molduras verdes.

- [x] **Exportar/importar estado de sincronização como JSON**: `GET
  /jobs/{id}/sync-state` exporta um blob JSON com o subconjunto de sync dos
  params (whitelist `_SYNC_STATE_KEYS`: `offset_s`/`lead_in_s`/`tempo_scale`/
  `sync_anchor_stages`/`arrangement_sync`/`tuning_midi`/`cent_offset`/
  `tuning_overrides`/`lyrics_events` + atribuição de tracks); `POST
  /jobs/{id}/import-sync` aplica-o (forka um rebuild), largando chaves só-GP num
  job não-GP e validando afinações. Botões "⬇ Exportar sync / ⬆ Importar sync"
  no painel de sync. Guardado por `test_api.py` (whitelist, round-trip, drop de
  chaves GP, validação).

- [x] **Histórico/recuar de rebuilds**: cada rebuild/reload-gp/import-sync já
  forka um job novo **sem apagar o antigo** (o bundle anterior fica), por isso as
  versões já persistem — faltava ligá-las. Agora o fork guarda
  `params["rebuilt_from"]` (o id de origem), exposto em `JobOut.rebuilt_from`, e o
  tab viewer mostra um botão **"↩ Versão anterior"** que abre o job de onde esta
  foi reconstruída — recua-se uma correção de sync que tenha piorado o resultado.
  Guardado por `test_forked_jobs_link_back_to_the_original`. (Retenção/limpeza
  automática das versões antigas fica para depois.)

- [x] **Destaque visual de quebras de linha da letra no tab view**: a palavra
  de fim-de-linha (o `+` do jogo) mostra agora um conector vertical **sólido,
  âmbar e mais grosso** (em vez do tique tracejado das palavras normais) mais um
  glifo `¶`, para se ver na partitura onde a letra quebra de linha no ecrã.

- [x] **Notas fora do alcance do braço — aviso**: uma nota com fret > 24 ou < 0
  (ou, no GP7, numa corda além da afinação) já era **saltada** por ambos os
  parsers, mas em silêncio; agora conta-se e emite-se um aviso em
  `ParsedGpTrack.warnings`, que o `gp_pipeline` propaga para os warnings do job
  (`"Lead: N note(s) dropped: off the 24-fret neck…"`). O `TabNote` continua a
  rejeitar frets inválidos na construção; isto só torna transparente o descarte
  (parte extended-range/bass). Guardado por
  `test_gp7_out_of_range_note_dropped_with_warning`.

- [x] **Criar o PSARC diretamente na aplicação (sem DLC Builder) — CONCLUÍDO**:
  o empacotamento final já não depende do DLC Builder — `psarc_mode="native"`
  (por defeito) compila o SNG, gera a Dynamic Difficulty, serializa os tons e
  produz o `.psarc` jogável inteiramente em Python, a partir da implementação
  aberta do Rocksmith2014.NET (DLC Builder, MIT). O `.wem` continua a precisar
  do Wwise (a EULA Audiokinetic proíbe redistribuição) — só a parte de
  empacotamento deixou de depender do DLC Builder, não a conversão de áudio.
  Vários bugs de renderização in-game (chord templates com MIDI -1, high
  density em acordes repetidos, ChordNotes por sustain, anchors cruzando
  fronteiras de frase, `phrase_id` fora de alcance após o phrase-linking, o
  vocal-note sentinel 254 + atlas de glifos da letra) foram isolados por
  byte-diff contra PSARC reais do DLC Builder e **confirmados corrigidos no
  jogo** — ver `CLAUDE.md` (secção "SNG binary compilation") para a lista
  completa e o método de debug reutilizável. Honesto: o SNG binário continua
  *round-tripped* mas não byte-diffed contra um SNG retail em CI (não há
  ficheiro de referência); a Dynamic Difficulty é uma rampa de densidade por
  frase, não uma passagem DDC musical real — o caminho de maior confiança
  para DD continua a ser o bundle DLC Builder. Construído em 8 fases, cada
  uma com testes próprios:

  - [x] **Fase 1 — Contentor PSARC** (`infrastructure/packaging/psarc/container.py`):
    `pack_entries(files: dict[str, bytes]) -> bytes` / `unpack(data: bytes) ->
    dict[str, bytes]`. Cabeçalho "PSAR" v1.4, blocos de dados comprimidos em
    zlib, TOC com hash MD5 do caminho de cada ficheiro + índice do primeiro
    bloco + tamanho descomprimido + offset, e tabela de tamanhos de bloco. TOC
    ainda NÃO cifrado (cifra vem na fase 4) — testável sem `cryptography`.

  - [x] **Fase 2 — Manifestos** (`infrastructure/packaging/psarc/manifest.py`):
    gera `manifests/songs_dlc_<key>/<key>_<arr>.json` por arranjo,
    `songs_dlc_<key>.hsan` agregado, `<key>_aggregategraph.nt` e
    `toolkit.version` — os manifestos de runtime do Rocksmith, distintos do
    `rockforge_project.json` interno (que serve para importar no DLC Builder).
    Cobre apenas identidade/metadados (nomes, artista/álbum/ano, afinação,
    duração, capo, IDs persistentes determinísticos); estatísticas por nota,
    iterações de frase/secção e dynamic difficulty dependem do SNG compilado
    (fase 3) e ainda não são emitidas — documentado no módulo.

  - [x] **Fase 3 — Compilação SNG** (`infrastructure/packaging/psarc/sng.py`):
    converte o `Arrangement` num `SngModel` estrutural (beats, phrases/secções,
    notas com tempo/corda/traste/sustain/bend/técnicas, vocais, metadados) e
    serializa-o/lê-o em binário (`write_sng`/`read_sng`, round-trip testado).
    Porte ainda parcial e não validado contra o jogo: chord templates/chord
    notes (o modelo de domínio não tem agregado de acordes), anchors/
    fingerprints (hand shapes), NewLinkedDifficulty e ligações entre notas
    (next/prev/parent) não são emitidos; o bitmask de técnicas em
    `TECHNIQUE_BITS` é uma codificação própria do RockForge pendente de
    validação contra o `NoteMask` real do Sng2014 — a confirmar nas fases 4/5.

  - [x] **Fase 4 — Cifragem** (`infrastructure/packaging/psarc/crypto.py`): AES-256-CFB
    para o TOC do PSARC (`encrypt_psarc_toc`/`decrypt_psarc_toc`, IV zero,
    padding zero) e AES-256-CTR para o SNG (`encrypt_sng`/`decrypt_sng`, IV
    aleatório de 16 bytes prefixado), com `ARC_KEY`/`SNG_PC_KEY` portadas do
    Rocksmith2014.NET (MIT) com nota de proveniência. `pack_entries(...,
    encrypt=True)` cifra o TOC e marca `archive_flags=4`, tal como os PSARC
    reais; `unpack` deteta a flag e decifra. Nova extra `[psarc]`
    (`cryptography`), importada lazily. `encrypt_sng`/`decrypt_sng` cobrem só
    a primitiva AES-CTR — o envelope real do `.sng` (cabeçalho + zlib) fica
    para a fase 5.

  - [x] **Fase 5 — Adaptador e wiring** (`infrastructure/packaging/psarc/packer.py`):
    `NativePsarcPacker` junta as fases 1-4 atrás do `Packager` Protocol
    (extraído para `application/ports.py`; `gp_pipeline.py` deixa de depender do
    tipo concreto `DlcBuilderPackager`). Nova opção `settings.psarc_mode`
    (`"dlcbuilder"` default | `"native"`), lida por `celery_app._build_packager()`
    (usado por `_build_gp_use_case()`).
    `GET /jobs/{id}/psarc` não precisa de alterações — já serve qualquer
    `PackagingResult.psarc_path`, seja do DLC Builder ou nativo. Honestidade:
    `NativePsarcPacker` empacota o `.wem` se o Wwise estiver disponível, senão
    cai para o WAV normalizado (mesmo aviso "no .wem" da pipeline); vocais só
    são anexados ao SNG do primeiro arranjo (mesma limitação da fase 3);
    requer a extra `[psarc]`, com `PackagingError` claro se ausente.

  Plano totalmente aditivo: `DlcBuilderPackager` continua a ser o caminho por
  omissão até à fase 5; o novo código vive isolado em
  `infrastructure/packaging/psarc/`.

  - [x] **Fase 6 — Requisitos de carregamento no jogo (parcial)**: o CDLC não
    aparecia na lista do Rocksmith porque faltavam três coisas, agora
    corrigidas: o ficheiro tem de terminar em **`_p.psarc`** (etiqueta de
    plataforma PC — `packer.py`), o PSARC tem de conter um ficheiro **`appid`**
    na raiz (`manifest.APP_ID`, hoje `492989` — Train "Drops of Jupiter"; o
    jogo só lista um CDLC cujo appid o jogador **possui**, por isso reutiliza-se
    o de um DLC que se tem) e os manifestos precisam de **`InsertRoot`**
    (`Static.Songs.Entries`). Guardado por `test_psarc_manifest`.
    Necessário mas não suficiente sozinho — via as fases seguintes.

  - [x] **Fase 7 — SoundBank Wwise (`.bnk`) no PSARC nativo**: o Rocksmith
    carrega o áudio através de uma SoundBank (`song_<key>.bnk`) com um evento
    `Play_<key>` que referencia o `.wem` por ID; sem ela, mesmo listada, a
    música não toca. Tal como o DLC Builder, o Wwise só produz o `.wem` — o
    `.bnk` é gerado em código (`psarc/soundbank.py`, porte do
    `SoundBankGenerator2014` do toolkit, MIT), e o packer emite
    `audio/windows/song_<key>.bnk` + `audio/windows/<fileID>.wem`, com o
    manifesto a apontar `SongBank`/`SongEvent`. Round-trip testado; layout
    unverified-by-design (como `sng.py` — sem ficheiro `.bnk` retail em CI),
    mas o áudio confirmado a tocar no jogo a partir do PSARC nativo.

  - [x] **Fase 8 — Layout completo de enumeração (o CDLC nativo não aparecia)**:
    por byte-diff de um PSARC real do DLC Builder contra o nosso, descobriu-se
    que faltavam/estavam errados muitos ficheiros. Agora o PSARC nativo bate
    certo com o layout retail (`psarc/gamedata.py`): `gamexblocks/nsongs/<key>.xblock`,
    `flatmodels/rs/rsenumerable_{root,song}.flat` (vendored), `<key>_aggregategraph.nt`,
    o `.hsan` como *headers* (`InsertRoot = Static.Songs.Headers`) distinto dos
    `.json` de *entries* (`Static.Songs.Entries`, com `ArrangementType` **int**),
    o SNG em `songs/bin/generic/`, `showlights.xml`, DDS de capa (placeholder),
    banco de preview, `appid.appid`, e offsets **absolutos** na TOC. Verificado
    por unpack+diff contra o PSARC de referência **e validado no jogo**
    (carrega, lista, toca e é jogável).

  - [x] **Dados de score/frases/secções no manifesto do PSARC nativo**:
    populados a partir do SNG compilado (`manifest.arrangement_stats`) —
    contagem de notas, `Phrases`/`PhraseIterations`/`Sections`,
    `MaxPhraseDifficulty` + `NotesEasy/Medium/Hard` (a partir da Dynamic
    Difficulty por densidade). **Os tons também vão** (`Tones`/`Tone_Base`/
    `Tone_A`..`Tone_D`, via `packaging/tone_dto.py` partilhado com o
    `.rs2dlc`; formato validado contra um build DLC Builder dos nossos
    próprios tons), por isso o tom in-game é o do utilizador e não um default.
    Falta ainda: a secção Tones do SNG para *mudanças* de tom a meio da
    música (o `tone_base` já aplica desde o início).

  - [x] **DDS real da capa**: o PSARC nativo converte a capa do utilizador para
    as texturas DDS in-game (64/128/256) via `gamedata.album_art_dds` (encoder
    DXT1, precisa do Pillow no extra `[psarc]`); sem capa/Pillow usa um placeholder
    de cor sólida para o URN resolver.

  - [x] **Calibração de volume ("Calculate Volumes")**: **um** alvo
    (`runtime_settings.loudness_target()`, default **-12 LUFS**) comanda o
    ganho linear da gravação (sem `loudnorm` desde 2026-09-30) **e** a calibração do volume do bus Wwise no `.bnk`, por
    isso o `.wem` e o volume nunca desalinham (`normalize/loudness.py` +
    `ffmpeg.py` → `generate_soundbank(volume=…)`). Passou de -16 (broadcast, soava
    baixo) para -12 (nível de master de música) porque o retail é alto (o DLC
    Builder atenua ~-3/-4 dB num master alto). **Editável na ⚙️ Definições**
    ("Volume alvo (LUFS)", clamp -20..-6) — sobe para -10/-9 se ficar baixo,
    desce para -14 se soar comprimido. Sem limitador, o que o teto de -1 dBTP não deixa subir vai
    para o volume do bus — -16 (o do DLC Builder) é o mais limpo. O
    preview é medido no seu próprio clip. Testado (`test_loudness.py`,
    `test_settings.py`); ffmpeg ausente → 0 dB. O `Volume` do `.rs2dlc` fica
    neutro (o DLC Builder recalcula na importação).

- [~] **Dynamic Difficulty (DD)**: DD por densidade com **teto variável por
  frase** (até 21 níveis) — uma nota entra quando a dificuldade chega ao seu
  *tier* de força métrica (`_note_tier`), com o manifesto a reportar
  `MaxPhraseDifficulty` + `NotesEasy/Medium/Hard`. **Phrase-linking (novo):**
  iterações musicalmente idênticas colapsam numa só frase partilhada
  (`_phrase_signature`), por isso um riff repetido é UMA frase com várias
  iterações — aprende-se uma vez e domina-se em cada repetição, e o grafo de
  dificuldade/Riff Repeater mostram as poucas frases únicas reais em vez de uma
  barra por secção (um CDLC real tem muito menos frases que secções). Falta
  ainda: a secção `NLinkedDifficulty` (linkar os *níveis* de frases diferentes),
  a redução por técnica/importância (a seleção de notas por nível continua por
  densidade, não musicalmente frascada), e validação in-game. O caminho de
  qualidade continua a ser o DDC via DLC Builder.

- [x] **Biblioteca de tons (guardar/carregar entre projetos)**: reutilizar os
  tons criados noutras músicas sem os recriar. Os tons (gear completo) são
  guardados numa loja partilhada (`work_dir/tone_library.json`,
  `tone_library.py`) via `GET/POST /tone-library` + `DELETE /tone-library/{key}`;
  o construtor de tons tem um bloco "Biblioteca" (carregar ⬇ / remover 🗑) e um
  botão "★ Biblioteca" para guardar o tom em edição. Carregar copia para o
  projeto (não altera o original). Complementa a barra de pesquisa de gear.

- [x] **Trocar os tons sugeridos, mantendo os pontos de troca**: nas
  "Sugestões por secção", cada tom sugerido pode ser trocado por um tom do
  projeto, da biblioteca ou dos teus PSARC; "Aplicar" mantém os tempos das
  trocas detetados e usa os tons escolhidos (dois sugeridos trocados pelo mesmo
  juntam-se). As escolhas ficam guardadas no projeto (`PATCH /jobs/{id}/tone-swaps`),
  por isso sobrevivem a mudar de projeto e a reconstruir.

- [x] **Tons das tuas músicas (como o DLC Builder)**: lê os `.psarc` da pasta
  `dlc` do Rocksmith (oficiais e CDLC; a pasta do jogo inclui `songs.psarc`) e
  lista os tons de cada música com o gear exato, pesquisáveis por música,
  artista, tom ou equipamento, e filtráveis por artista (lista de artistas; o
  artista de cada tom é um atalho). "Usar neste projeto" copia o tom; ★ guarda-o na
  biblioteca. Só lê os manifestos (`container.read_entries`), nunca o áudio, e
  guarda o resultado (`work_dir/tone_collection.json`): reler só abre ficheiros
  novos ou alterados. `GET /tone-collection`, `GET /tone-collection/tone`,
  `POST /tone-collection/scan`. Nunca corrido contra uma pasta dlc real daqui.

- [x] **Pasta do Rocksmith 2014 nas Definições** (Geral): o patch de CDLC
  (`D3DX9_42.dll`) passa a ser procurado nessa pasta e, sem ela, em todas as
  bibliotecas do Steam (`libraryfolders.vdf`, outros discos incluídos) — a
  linha "Patch de CDLC" deixa de dizer "por confirmar" no computador que tem o
  jogo. Sem jogo neste computador continua "desconhecido", e diz porquê. A
  coleção de tons sugere a pasta `dlc` dessa pasta.

- [x] **Processamento em lote** (`📦 Processamento em lote`): cria vários
  projetos GP de uma vez a partir de vários ficheiros Guitar Pro + gravações,
  em vez de repetir o assistente música a música — para quem tem um álbum
  inteiro. Só frontend: emparelha ficheiro↔gravação pelo **nome** (sem
  extensão; sobras emparelham pela ordem), e por cada par corre exatamente os
  mesmos dois pedidos do assistente normal (`/gp/inspect` → `/jobs/gp`), com as
  pistas em branco (a heurística `auto_pick_tracks` já existente escolhe
  Lead/Rhythm pelo nome). Sem passo próprio de revisão por música — uma
  escolha errada corrige-se depois em "✎ Editar info" de cada projeto, como
  qualquer outro job. Ver `CLAUDE.md` ("Batch processing").

- [x] **Editor de secções na partitura** (`🏷️ Secções` + modo "Secção"):
  marcar/renomear/mover secções (intro/verso/refrão…) diretamente no
  visualizador, em vez de virem só do GP — útil para Riff Repeater e
  navegação no jogo. `GpJobSpec.section_overrides` (job-level, partilhado por
  todos os arranjos, como `tone_changes`) substitui as secções vindas do GP
  quando definido; `ArrangementOut.sections` expõe-as (excluindo o sentinela
  `"noguitar"` do writer). Sem edição, mantém as secções do GP inalteradas
  (dirty-flag no frontend, não um always-send). Ver `CLAUDE.md` ("Section
  editor").

- [x] **Editor de notas na partitura** (modo "Editar notas", ✏️): clicar numa
  nota existente abre um popup para editar traste/sustain/técnicas
  (hammer-on/pull-off/harmónico/palm mute/vibrato/tapping/slap/pop/acento) +
  bend/slide, ou removê-la; clicar no pentagrama vazio insere uma nota nova,
  encaixada na grelha de sincronização (`nearestGridChartTime`). Backend:
  `GpJobSpec.note_overrides` (por arranjo, ao contrário de `tone_changes`/
  `section_overrides` que são partilhados) — um patch `(time, string) →
  fret/sustain/técnicas/deleted`, aplicado pelo `gp_pipeline` depois do parse
  **e** do corte de mute techniques, para uma edição manual nunca ser
  silenciosamente descartada. Pré-visualização no browser funde as edições
  pendentes só visualmente (`mergeNoteOverrides`); a sincronização/reprodução
  continuam a usar as notas construídas até um "Aplicar e reconstruir" real.
  **Limite honesto:** uma nota só pode ser colocada dentro do mapa de tempo já
  autorado no GP (`Arrangement.validate()` já rejeitava notas além do último
  ebeat) — para estender a música em si continua a ser preciso acrescentar
  compassos no Guitar Pro. Criar acordes é possível adicionando várias notas
  ao mesmo tempo/corda-diferente uma a uma (sem um gesto dedicado
  "criar acorde"). Ver `CLAUDE.md` ("Note editor").
  - [x] **Copiar/colar notas** ("📋 Copiar" / "📥 Colar no cursor", Ctrl+C/
    Ctrl+V): copia o excerto selecionado (a mesma seleção Shift+clique/
    Ctrl+clique/"Excerto") e cola-o a partir do cursor — noutro ponto da
    mesma pista, ou noutra pista (ex. Lead → Rhythm), preservando o ritmo
    relativo entre as notas copiadas. Puramente client-side: cada nota colada
    é só mais um `note_overrides` upsert, sem novo conceito no backend.
  - [x] **Limpar as edições de notas** ("🧹 Limpar edições" / "🧹 Limpar em
    todas"): descartar explicitamente os `note_overrides` desta pista ou de
    todas. Necessário depois de as edições já commitadas passarem a ser
    re-semeadas no visualizador (`ArrangementOut.note_overrides`) — antes
    disso, um rebuild sobre um job reaberto apagava-as em silêncio.
  - [x] **Exportar o GP com as notas editadas**
    (`POST /jobs/{id}/export-arrangement-gp`, "🎸 Exportar GP com as notas
    editadas"): gera um ficheiro **GP5 novo** a partir do arranjo já
    construído — notas editadas, técnicas, afinação, secções e a linha
    temporal corrigida incluídas. Complementa o `/export-gp` (que só escreve
    andamentos numa **cópia** do ficheiro do utilizador, preservando tudo o
    resto): este traz as edições de notas, ao custo de levar **só esta
    pista**. Lê o XML **construído** (`infrastructure/rsxml/reader.py`), não
    o GP de origem, para apanhar `tempo_scale` + anchors + `note_overrides`
    de uma vez. **Limite honesto:** o Guitar Pro guarda ritmo *notado*, por
    isso um ataque fora da grelha tem de ser quantizado — o relatório diz
    quantas notas foram movidas e o desvio máximo, em vez de as re-temporizar
    em silêncio. Ver `CLAUDE.md` ("Exporting the EDITED chart as a new GP
    file").

- [x] **Mais atalhos de teclado no visualizador**: além do espaço (play/pause),
  agora **←/→** avançam/recuam o cursor (±1s, **Shift** ±5s), **Home** vai ao
  início e **`+`/`-`** fazem zoom — só com o painel de sync aberto e sem foco num
  campo de texto. Os seeks passam pelo `audioSeek` (tempo de gravação), por isso
  movem o playhead visualmente mesmo em pausa. (Salto ←/→ é por tempo fixo, não
  nota-a-nota — evita depender do relógio nota↔playhead, que varia com edições de
  sync pendentes.)

- [ ] **Validar o Banquet em ficheiros reais** (ver entrada "Separação fina de
  guitarras" acima): confirmar a qualidade da separação por classe
  (elétrica/acústica, limpa/distorcida) e decidir se passa a default ou ganha um
  seletor dedicado na UI.
