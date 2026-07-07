# TODO / ideias futuras

Estado do projeto + lista de funcionalidades (concluídas `[x]` e propostas
`[ ]`). Para *como* cada coisa funciona, ver `CLAUDE.md`. Para *como testar*,
ver `TESTING.md`.

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
- **Sem dynamic difficulty (DD):** todas as frases têm `maxDifficulty=0`; a
  tablatura toca a densidade total. É uma lacuna de funcionalidade, não um
  ficheiro malformado.
- **SNG nativo não validado byte-a-byte** contra um SNG retail (não há ficheiro
  de referência em CI) — só round-trip `read_sng∘write_sng`. A validação real é
  carregar no jogo.
- **`offset_s` (trim) do caminho áudio-ML não é subtraído** dos tempos das
  palavras da letra editada (mesma limitação do WhisperX automático).
- **GP6 (`.gpx`) não suportado** (container binário proprietário). GP3/GP4/GP5 e
  GP7/GP8 (`.gp`) são suportados.
- **Capa de álbum não vira textura DDS in-game** — copiada para o bundle e
  registada no `.rs2dlc`, mas o `albumArt` do Song2014 XML fica vazio.
- **Não corre no GitHub Pages** (precisa de backend Python + Redis + ML); é uma
  app desktop/servidor local por design.

## Ideias futuras (não implementadas)

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

- [ ] **Exportar/importar estado de sincronização como JSON**: permitir
  guardar/restaurar `sync_anchor_stages`, `tempo_scale`, `arrangement_sync` e
  `lyrics_events` para não perder ajustes manuais finos.

- [ ] **Deteção de secções (intro/verso/refrão) no caminho áudio-ML**: hoje as
  secções só vêm do GP; áudio puro não tem estrutura de secções no Song2014
  XML.

- [ ] **Histórico/desfazer de rebuilds**: manter as últimas N versões do
  bundle por job, para comparar ou recuar se uma correção de sync piorar o
  resultado.

- [ ] **Destaque visual de quebras de linha da letra no tab view**: marcar
  visualmente os eventos com `+` (fim de linha) com uma barra mais forte,
  simulando a quebra no jogo.

- [ ] **Validação de tuning vs. alcance das notas**: avisar se, após uma
  correção de afinação, alguma nota do GP ficar fora do alcance do braço
  (fret > 24 ou negativo).

- [ ] **Criar o PSARC diretamente na aplicação (sem DLC Builder)**: hoje o
  empacotamento final depende do DLC Builder (ou de um packer externo via
  `ROCKFORGE_PSARC_PACKER_CMD`) para compilar SNG, gerar DD e produzir o
  `.psarc`. Objetivo: gerar o PSARC nativamente, reimplementado em Python puro
  a partir da implementação aberta do Rocksmith2014.NET (DLC Builder, MIT). O
  `.wem` continua a precisar do Wwise (a EULA Audiokinetic proíbe
  redistribuição), por isso esta etapa só remove a dependência do DLC Builder
  para a parte de empacotamento, não para a conversão de áudio. Plano em 5
  fases, cada uma com testes próprios:

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
    (extraído para `application/ports.py`; `application/pipeline.py` e
    `gp_pipeline.py` deixam de depender do tipo concreto
    `DlcBuilderPackager`). Nova opção `settings.psarc_mode` (`"dlcbuilder"`
    default | `"native"`), lida por um novo `celery_app._build_packager()`
    partilhado entre `_build_use_case()` e `_build_gp_use_case()`.
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
    Necessário mas ainda **não suficiente** — o PSARC nativo continua por
    validar no jogo (ver fase 3).

  - [x] **Fase 7 — SoundBank Wwise (`.bnk`) no PSARC nativo**: o Rocksmith
    carrega o áudio através de uma SoundBank (`song_<key>.bnk`) com um evento
    `Play_<key>` que referencia o `.wem` por ID; sem ela, mesmo listada, a
    música não toca. Tal como o DLC Builder, o Wwise só produz o `.wem` — o
    `.bnk` é gerado em código (`psarc/soundbank.py`, porte do
    `SoundBankGenerator2014` do toolkit, MIT), e o packer emite
    `audio/windows/song_<key>.bnk` + `audio/windows/<fileID>.wem`, com o
    manifesto a apontar `SongBank`/`SongEvent`. Round-trip testado; layout
    não-verificado-por-desenho (como `sng.py`). Continua sem validação in-game
    — o caminho de confiança continua a ser o bundle DLC Builder.

  - [x] **Fase 8 — Layout completo de enumeração (o CDLC nativo não aparecia)**:
    por byte-diff de um PSARC real do DLC Builder contra o nosso, descobriu-se
    que faltavam/estavam errados muitos ficheiros. Agora o PSARC nativo bate
    certo com o layout retail (`psarc/gamedata.py`): `gamexblocks/nsongs/<key>.xblock`,
    `flatmodels/rs/rsenumerable_{root,song}.flat` (vendored), `<key>_aggregategraph.nt`,
    o `.hsan` como *headers* (`InsertRoot = Static.Songs.Headers`) distinto dos
    `.json` de *entries* (`Static.Songs.Entries`, com `ArrangementType` **int**),
    o SNG em `songs/bin/generic/`, `showlights.xml`, DDS de capa (placeholder),
    banco de preview, `appid.appid`, e offsets **absolutos** na TOC. Verificado
    por unpack+diff contra o PSARC de referência. **Ainda por validar no jogo** e
    incompleto para *jogar* (arrays de score/frases vazios — dificuldade única
    sem DD; tons não serializados no manifesto; SNG binário não verificado).

  - [~] **Dados de score/frases/secções no manifesto do PSARC nativo**: já
    populados a partir do SNG compilado (`manifest.arrangement_stats`) — contagem
    de notas, `Phrases`/`PhraseIterations`/`Sections`. Falta ainda: os tons
    (`Tones`/`Tone_Base`) e as contagens por dificuldade (dependem da DD).

  - [x] **DDS real da capa**: o PSARC nativo converte a capa do utilizador para
    as texturas DDS in-game (64/128/256) via `gamedata.album_art_dds` (encoder
    DXT1, precisa do Pillow no extra `[psarc]`); sem capa/Pillow usa um placeholder
    de cor sólida para o URN resolver.

  - [ ] **Calibração de volume ("Calculate Volumes")**: o DLC Builder analisa o
    áudio e calcula o volume (dB) para uma sonoridade consistente; a RockForge
    usa um valor neutro (0 dB) no `.bnk`/`.rs2dlc`. Como o áudio já é normalizado
    para -16 LUFS (loudnorm EBU R128), a sonoridade entre músicas é consistente,
    mas não está calibrada para a referência do Rocksmith. Medir a sonoridade do
    `.wem` e mapear para o volume do banco de som (e do manifesto).

- [~] **Dynamic Difficulty (DD)**: implementada uma DD **simples/mecânica** —
  o `from_arrangement` gera vários `ArrangementLevels` (até 5); uma nota entra
  quando a dificuldade chega ao seu *tier* de força métrica (`_note_tier`:
  tempo forte→0, tempo→1, meio→2, quarto→3, mais fino→4), com o manifesto a
  reportar `MaxPhraseDifficulty` + `NotesEasy/Medium/Hard`. Falta: o *leveling*
  musical inteligente de um DDC a sério (frases repetidas via `NLinkedDifficulty`,
  redução por técnica/importância), e validação in-game dos níveis. O caminho
  de qualidade continua a ser o DDC via DLC Builder.

- [x] **Biblioteca de tons (guardar/carregar entre projetos)**: reutilizar os
  tons criados noutras músicas sem os recriar. Os tons (gear completo) são
  guardados numa loja partilhada (`work_dir/tone_library.json`,
  `tone_library.py`) via `GET/POST /tone-library` + `DELETE /tone-library/{key}`;
  o construtor de tons tem um bloco "Biblioteca" (carregar ⬇ / remover 🗑) e um
  botão "★ Biblioteca" para guardar o tom em edição. Carregar copia para o
  projeto (não altera o original). Complementa a barra de pesquisa de gear.

- [ ] **Processamento em lote**: converter vários ficheiros Guitar Pro de uma
  vez (fila de jobs), em vez de um a um, para quem tem um álbum inteiro.

- [ ] **Editor de secções na partitura (caminho GP)**: marcar/renomear secções
  (intro/verso/refrão) diretamente no visualizador, em vez de virem só do GP —
  útil para Riff Repeater e navegação no jogo.

- [ ] **Mais atalhos de teclado no visualizador**: além do espaço (play/pause),
  ex.: setas ←/→ para saltar nota-a-nota, `+`/`-` para zoom, `Home` para o
  início — para editar sync mais depressa sem o rato.

- [ ] **Validar o Banquet em ficheiros reais** (ver entrada "Separação fina de
  guitarras" acima): confirmar a qualidade da separação por classe
  (elétrica/acústica, limpa/distorcida) e decidir se passa a default ou ganha um
  seletor dedicado na UI.
