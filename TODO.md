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

  - [ ] **Fase 3 — Compilação SNG** (`infrastructure/packaging/psarc/sng.py`):
    converter o `Arrangement`/Song2014 XML já produzido por
    `rsxml/writer.py` no formato binário SNG (ebeats, phrases,
    phraseIterations, sections, chordTemplates, levels/notes/chords, anchors,
    handShapes, vocals), portado de `Sng2014FileWriter`. Idealmente partilha o
    modelo intermédio com `render_arrangement` em vez de duplicar lógica.

  - [ ] **Fase 4 — Cifragem** (`infrastructure/packaging/psarc/crypto.py`): AES-256-CFB
    para o TOC do PSARC e AES-256-CTR para o SNG, com as chaves tratadas da
    mesma forma que o DLC Builder (constantes no código, portadas da fonte MIT,
    com nota de proveniência). Nova extra `[psarc]` que adiciona
    `cryptography`. Mantém a postura de honestidade/legal já documentada
    (distribuição de áudio protegido não é autorizada por esta ferramenta).

  - [ ] **Fase 5 — Adaptador e wiring** (`infrastructure/packaging/psarc/packer.py`):
    `NativePsarcPacker` que junta as fases 1-4; extrair um `Packager` Protocol
    para `application/ports.py` (hoje `DlcBuilderPackager` é um tipo
    concreto); nova opção `settings.psarc_mode` (`"dlcbuilder"` default |
    `"native"`) usada em `celery_app._build_use_case()`; atualizar
    `GET /jobs/{id}/psarc` para servir o `.psarc` gerado nativamente quando
    `psarc_mode == "native"`.

  Plano totalmente aditivo: `DlcBuilderPackager` continua a ser o caminho por
  omissão até à fase 5; o novo código vive isolado em
  `infrastructure/packaging/psarc/`.
