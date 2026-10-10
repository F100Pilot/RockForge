# Transcrição de notas — fase 0: medir antes de construir (EXPERIMENTAL)

Antes de pôr na aplicação qualquer deteção de notas a partir da gravação,
este banco de ensaio mede os transcritores candidatos **nas tuas próprias
músicas**. A resposta certa são as pistas que já construíste e sincronizaste
no RockForge (as notas do Guitar Pro, com todas as correções de
sincronização). Não mexe em nada da aplicação: só lê os projetos e escreve
na sua própria pasta.

## O jeito simples (duplo clique)

1. Fecha o RockForge e abre-o uma vez com o `start.bat` (traz os ficheiros
   novos), depois fecha-o outra vez.
2. Na aplicação, em pelo menos uma música cujas notas batem com a gravação:
   Partitura → Sincronização → "Estado da sincronização" → **"Marcar esta
   pista como sincronizada"** em cada pista.
3. Na pasta do RockForge, **duplo clique em `bench_transcricao.bat`**. Na
   primeira vez instala os transcritores (minutos; precisa do `git`), depois
   corre nas músicas marcadas e abre o `report.md` sozinho.
4. Manda-me o `report.md` e o `results.csv` (a mesma pasta), ou, se der erro,
   as últimas linhas da janela.

## Na linha de comandos (opcional)

1. **Instalar os transcritores** (uma vez; precisa do `git`):

       bench_transcricao.bat instalar

   Instala o GAPS (Riley et al.) e o `mt3-infer` (YourMT3+ e MR-MT3) com o
   torch e o numpy presos às versões do RockForge.

2. **Ver que projetos servem**:

       bench_transcricao.bat list

   `✓` marca as pistas que marcaste como sincronizadas — são as que dão uma
   resposta certa fiável. Projetos sem gravação ficam de fora.

3. **Correr e medir** (minutos por música; com GPU é muito mais rápido):

       bench_transcricao.bat run
       bench_transcricao.bat run --input stem,mix --models gaps,yourmt3,mr_mt3
       bench_transcricao.bat run --projects ID1 ID2 --only-synced --open

   Por omissão separa a guitarra com o Demucs (`stem`) e corre `gaps` e
   `yourmt3`. Os resultados ficam em cache: correr outra vez só faz o que
   falta (`--force` refaz). `--open` abre o relatório no fim.

4. **Medir uma tab feita por outra ferramenta** (Songsterr AI, Klangio, …),
   exportada em MIDI ou Guitar Pro:

       bench_transcricao.bat score "C:\caminho\tab.gp5" --project ID

   Procura sozinho o desvio de início (até 60 s). Um andamento diferente não
   é corrigido e aparece como nota baixa.

## O que é medido

- **F1** — notas certas (mesma altura, início a menos de 50 ms), a média
  entre precisão (das notas encontradas, quantas existem) e recall (das notas
  da música, quantas foram encontradas).
- **F1 sem oitava** — o mesmo, ignorando a oitava: mostra se os erros são
  sobretudo de oitava.
- **F1 tab** — só para ficheiros com cordas e trastes (as tabs de outras
  ferramentas): a mesma nota na mesma corda e traste.
- **recall por pista** — que parte das notas da Lead, da Rhythm, … foi
  encontrada (o transcritor ouve as guitarras todas juntas).
- **desvio** — o atraso que foi descontado (latência do modelo).

O relatório fica em `<pasta de trabalho>\transcription_bench\report.md` (por omissão `Downloads\RockForge\transcription_bench`) e
`results.csv`; em cada música, `truth.mid` é a resposta certa (para ouvir num
DAW) e `<fonte>\<modelo>.mid` o que cada modelo ouviu.

## Para decidir

Manda-me o `report.md` (e o `results.csv`). Com os números decide-se se vale
a pena a fase 1 e com que modelo — e, se forem maus, fica-se por aqui sem
ter tocado na aplicação.

## Primeiros resultados (2026-10-10)

Três músicas com todas as pistas marcadas como sincronizadas, guitarra
separada pelo Demucs:

| modelo | F1 | precisão | recall | F1 sem oitava |
|---|---|---|---|---|
| GAPS | 32.7% | 39.6% | 28.0% | 39.0% |
| YourMT3+ | 29.8% | 32.8% | 28.3% | 35.7% |

Cerca de uma nota certa em cada três: igual ao que a literatura reporta, e
pouco para gerar uma tab automática. A fase 1 fica parada até se medir uma
ferramenta comercial (Songsterr AI, Klangio) com `score`.

### Songsterr AI (2026-10-10)

A tab gerada pelo Songsterr AI para o Jet Lag, exportada em `.gp` e medida com
`score`: **F1 73,4%** (precisão 65,0%, recall 84,3%), **F1 tab 69,5%** (mesma
corda e traste), Lead 79% e Rhythm 86% das notas encontradas, com um desvio
constante de 0,20 s. Os modelos abertos ficaram em 42,7% e 46,0% na mesma
música. Falta confirmar em September e em You're the Bullet.
