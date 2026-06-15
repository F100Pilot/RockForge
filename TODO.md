# TODO / ideias futuras

Lista de funcionalidades propostas, ainda não implementadas.

- [ ] **Deteção automática de afinação para jobs GP**: hoje `tuning_estimator`
  (librosa) só corre no caminho áudio-ML; para GP a afinação vem do ficheiro,
  mas se a gravação estiver numa afinação diferente não há deteção a partir
  do áudio.

- [ ] **Pré-visualização de áudio por arranjo (Lead/Rhythm)**: sintetizar e
  tocar cada arranjo isoladamente a partir das notas, para validar a
  separação experimental Lead/Rhythm antes do rebuild.

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
