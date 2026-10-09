# Transcrição de notas — fase 0: medir antes de construir (EXPERIMENTAL)

Antes de pôr na aplicação qualquer deteção de notas a partir da gravação,
este banco de ensaio mede os transcritores candidatos **nas tuas próprias
músicas**. A resposta certa são as pistas que já construíste e sincronizaste
no RockForge (as notas do Guitar Pro, com todas as correções de
sincronização). Não mexe em nada da aplicação: só lê os projetos e escreve
na sua própria pasta.

## Passos (Windows, na pasta do RockForge)

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
       bench_transcricao.bat run --projects ID1 ID2 --only-synced

   Por omissão separa a guitarra com o Demucs (`stem`) e corre `gaps` e
   `yourmt3`. Os resultados ficam em cache: correr outra vez só faz o que
   falta (`--force` refaz).

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

O relatório fica em `<pasta de trabalho>\transcription_bench\report.md` e
`results.csv`; em cada música, `truth.mid` é a resposta certa (para ouvir num
DAW) e `<fonte>\<modelo>.mid` o que cada modelo ouviu.

## Para decidir

Manda-me o `report.md` (e o `results.csv`). Com os números decide-se se vale
a pena a fase 1 e com que modelo — e, se forem maus, fica-se por aqui sem
ter tocado na aplicação.
