# TODO / ideias futuras

Lista de funcionalidades propostas, ainda não implementadas.

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
