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
  `.psarc`. Objetivo: gerar o PSARC nativamente — implica (a) compilar o
  Song2014 XML para SNG (formato binário do Rocksmith), (b) opcionalmente
  gerar Dynamic Difficulty, e (c) empacotar tudo no contentor PSARC
  (estrutura + compressão zlib). O `.wem` continua a precisar do Wwise (a EULA
  Audiokinetic proíbe redistribuição), por isso esta etapa só remove a
  dependência do DLC Builder para a parte de empacotamento, não para a
  conversão de áudio. Referência: a implementação aberta do
  Rocksmith2014.NET (formato SNG/PSARC).
