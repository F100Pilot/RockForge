# TODO / ideias futuras

Estado do projeto + lista de funcionalidades (concluídas `[x]` e propostas
`[ ]`). Para *como* cada coisa funciona, ver `CLAUDE.md`. Para *como testar*,
ver `TESTING.md`.

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
  CUDA (README §2b). Confirmar no log: `device: cuda (GPU)`.
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
  secções "Avisos legais"/"Licença" nos dois README; o `.exe`, o zip portátil e
  o instalador levam os três ficheiros (`build_exe.copy_legal_files`,
  `LicenseFile` no `installer.iss`). Guardado por `tests/test_legal_files.py`.
- [ ] **alphaTab é MPL-2.0.** `gpimport/playback.py`, `domain/music.py`
  (`alphatab_bend`) e a leitura dos SyncPoints seguem de perto a lógica do
  alphaTab. Está creditado; falta decidir se esses ficheiros passam a declarar
  também MPL-2.0 no cabeçalho (o MPL permite-o dentro de um projeto MIT).
- [ ] **Licença do Rocksmith Custom Song Toolkit por confirmar.** O
  `soundbank.py` segue o `SoundBankGenerator2014`; as notas dizem MIT, mas o
  repositório do toolkit não mostra um ficheiro de licença.
- [ ] **ffmpeg dentro do instalador.** Se o `ffmpeg.exe` for incluído, juntar o
  texto da licença dessa build (normalmente GPL-3.0 no Windows) e um link para
  o código-fonte correspondente.

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
