# Testes no jogo

O que os testes automáticos não conseguem confirmar: como o chart aparece e se
toca no Rocksmith 2014, e como os ficheiros abrem no Guitar Pro / TuxGuitar.
Atualizar depois de cada teste (passar de "Por testar" para "Confirmado", com a
data e a música). O detalhe técnico de cada ponto está em `TESTING.md` §7.

Em cada teste: gerar o PSARC nativo (`psarc_mode=native`). Se algo correr mal,
gerar também pelo DLC Builder, para saber se o problema é do PSARC nativo.

## ⚠️ Problema aberto: crash no "September"

| | |
|---|---|
| **Desde** | 2026-09-30 |
| **Música** | Daughtry "September" (`.gp` do PDF-to-GP5, com áudio e início a −2,15 s) |
| **Sintoma** | O jogo fecha depois de começar a tocar, **em todas as pistas** (Lead e Rhythm/Acoustic). Ainda não se sabe em que compasso |
| **Já verificado aqui** (chart gerado com o mesmo `.gp`, PSARC nativo) | Tempos das batidas, notas e letra por ordem e sem negativos; curvas dos bends dentro das notas e por ordem; nenhuma nota sobreposta na mesma corda; `phrase_id` válidos; sem trocas de tom no SNG. A pista Rhythm (Acoustic) não tem bends, portanto os bends não explicam um crash em todas as pistas |
| **Alterações do dia a suspeitar** | 2cf1749 (outra sessão): áudio com ganho linear, tom por defeito do DLC Builder em cada pista, secção de trocas de tom no SNG. a566e91: let ring nos `.gp` (344 notas na Acoustic). Letra da pista "Letra (voz)", partilhada por todas as pistas |
| **Causa provável encontrada** | 4ec2d04 (outra sessão): numa pista que só entra a meio, a 1.ª secção passava para a 1.ª nota e ficava depois de outra ("Intro" depois de "Verse 1"); o jogo bloqueava. No "September" afeta Rhythm, Lead alternativo e Rhythm alternativo — ver o ponto 12 abaixo. **Por confirmar** se resolve também a pista Lead |
| **Depois de 4ec2d04** | Já toca, mas fecha no Riff Repeater ao subir a dificuldade (Rhythm alternativo: dificuldade a 0 → subir → fecha, 0xc0000005; Lead: 5.º retângulo). Causa encontrada: as notas levavam a posição da mão da pista inteira e não a do seu nível (Rhythm alternativo: traste 1 nas notas, traste 2 no nível a partir do 17). Corrigido em 2d95db9 (ponto 13), mas **continuou a fechar**. Comparado byte a byte com o build do DLC Builder do mesmo September: lá, todas as fases com notas têm pelo menos 3 níveis (a de uma nota tem 6); cá, uma fase de uma nota tinha 0 — é exatamente o 5.º retângulo da Lead e a anacrusa do Rhythm alternativo. Corrigido, com mais duas diferenças (ponto 14), e **continuou a fechar**. A seguir, as fases passaram a ser geradas exatamente como o DLC Builder as gera ao construir o pacote (ponto 15): nas quatro pistas ficam iguais às do build dele. **Por confirmar no jogo** |
| **Se continuar a fechar, para isolar** | 1) Em que compasso/segundo fecha (é sempre no mesmo?). 2) O mesmo projeto pelo DLC Builder (bundle): se não fechar, o problema está no SNG/manifest do PSARC nativo. 3) Outra música que funcionava, reconstruída com o RockForge atual: se também fechar, é uma alteração de hoje e não o "September". 4) Com a dificuldade dinâmica desligada |

## Por testar — alterações recentes

| # | O quê | Commit | Como testar | O que deve acontecer | Se falhar |
|---|---|---|---|---|---|
| 1 | **Pre-bend simples** dobrado desde o início da nota | a2f1c0a | `teste-prebend.gp5` + `teste-prebend.mp3`, acerto 0 (ver abaixo) | Compassos 2, 3, 6 e 8: notas já dobradas desde o início. 5: só a corda Sol dobrada. 4: começa dobrada e desce. 7: dobrada durante a nota toda. Sem crash | Reverter a2f1c0a (volta a subida) |
| 2 | **Bend de 3 pontos** como subida ao longo da nota | def07fd | Compasso 1 do mesmo teste | Sobe durante a nota (um ponto no fim da nota, a forma já confirmada no Beartooth) | Avisar |
| 3 | **Bend + release no tempo certo**, também numa nota ligada | cdbdd97, 7f6d106 | Daughtry "September", compasso 4 (nota aos 13,2 s) | A nota fica, sobe ½ perto do fim, volta, e o pull-off vem a seguir | Avisar, com o compasso |
| 4 | **Repetições, voltas e saltos** (D.C., D.S., Coda) tocados pela ordem do alphaTab | 565ed05 | Um GP com `|: :|`, 1ª/2ª volta ou D.S. | O chart segue a música em todas as passagens, sem compassos a mais ou a menos | Avisar, com a música |
| 5 | **Início antes do áudio** (acerto negativo), também na página de sincronização | 31948f4, 8b61bf0 | Um GP sincronizado cujo compasso 1 começa antes da gravação | As notas batem com a música desde o início | Avisar |
| 6 | **Grace notes, rasgueado, harmónico pinch (GP5), vibrato ligado** | 8b8407f | Um GP com estas técnicas | A grace note aparece como nota curta antes da principal (com hammer quando o tem); o pinch tem o símbolo de pinch | Avisar, com a técnica |
| 7 | **Let ring nos `.gp`** | a566e91 | Um `.gp` com let ring ("September.gp") | A nota continua a soar por cima das seguintes | Avisar |
| 12 | **Pista que só entra a meio da música** (secções fora de ordem → bloqueava) | (este) | Daughtry "September" com Rhythm, Lead alternativo e Rhythm alternativo | Todas as pistas tocam até ao fim, sem bloquear; no Riff Repeater as secções aparecem pela ordem da música | Avisar, com a pista e o tempo onde bloqueia |
| 15 | **Fases geradas como o DLC Builder** (COUNT até à 1.ª nota, uma fase a cada 8 compassos fora das notas sustentadas, NOGUITAR nas pausas) | (este) | Daughtry "September", todas as pistas: tocar do início ao fim e, no Riff Repeater, subir a dificuldade de 0 ao máximo em todas as fases | Sem crash. No Riff Repeater as fases têm as posições das do DLC Builder e as secções chamam-se "Riff"/"No Guitar" (os nomes do Guitar Pro já não vão para o PSARC nativo) | Avisar, com a pista, a fase e o nível |
| 14 | **Fases com uma só nota têm níveis**, fases ligadas iguais, bytes das notas como no DLC Builder | (este) | Daughtry "September", todas as pistas: no Riff Repeater, dificuldade a 0 e subir até ao máximo em todas as secções | Sobe sem crash; a nota solitária (Lead aos 43,6 s, anacrusa do Rhythm alternativo antes do refrão) aparece em todos os níveis | Avisar, com a pista, a secção e o nível |
| 13 | **Aumentar a dificuldade no Riff Repeater** (a posição da mão das notas não era a do nível → crash) | (este) | Daughtry "September", Rhythm alternativo e Lead: no Riff Repeater, escolher as secções do meio com a dificuldade a 0 e subi-la até ao máximo | A dificuldade sobe sem crash e as notas aparecem na posição certa do braço | Avisar, com a pista, a secção e o nível |
| 9 | **Som da gravação sem compressão** (sem `loudnorm`, só um ganho fixo) | (este) | Reconstruir uma música que soava com ruído / pouco limpa | Soa como a gravação original: sem "bombear", sem ataques esmagados, sem estalidos nas partes fortes | Avisar; experimentar Volume alvo -16 na ⚙️ |
| 10 | **Trocas de tom a meio da música** no PSARC nativo | (este) | Marcar na partitura uma troca para um 2.º tom e reconstruir | O tom muda nesse ponto (antes ficava sempre o tom base) | Avisar, com o tempo da troca |
| 11 | **Pista sem tom próprio** | (este) | Uma música sem nenhum tom criado | Lead/Combo com o tom por defeito do DLC Builder (Plexi), Rhythm com o Orange AD50 — não um som estranho/em falta | Avisar |

### Ficheiro de teste dos pre-bends

`teste-prebend.gp5` + `teste-prebend.mp3` (enviados na conversa; se se perderem,
pedir para os gerar de novo). Andamento 80: 3 s por compasso, e no chart o
compasso 1 começa aos 2 s. São 8 compassos, repetidos duas vezes, cada um com o
nome do caso como marcador:

1. Bend ½ normal (referência)
2. Pre-bend ½
3. Pre-bend de 1 tom
4. Pre-bend ½ com release
5. Acorde com pre-bend só na corda Sol
6. Acorde com pre-bend nas duas cordas
7. Pre-bend numa nota ligada
8. Quatro pre-bends curtos seguidos

## Por testar — anteriores (`TESTING.md` §7f-bis e §7f-ter)

- Harmónico pinch / artificial com o símbolo próprio, diferente do natural (Ozzy "No More Tears").
- Tremolo picking: aparece a marca de tremolo.
- Trill: aparece como hammer-on/pull-off alternados, não como uma nuvem de notas.
- Direção da palheta e dedilhação: não estragam nada.
- Tap / slap / pop em ficheiros `.gp` (GP7/8): não havia nenhum ficheiro de exemplo.
- Dificuldade dinâmica: o seletor tem mais níveis, e o Riff Repeater mostra alturas diferentes por frase.
- Frases repetidas partilham a mesma frase no Riff Repeater.
- Lead / Rhythm alternativo: aparecem as duas entradas para a mesma música.
- Tons personalizados no PSARC nativo: o som é o do amplificador escolhido, e cada arranjo mantém o seu tom.
- Volume dos tons: ao nível de um tom do DLC Builder.

## Fora do jogo (Guitar Pro / TuxGuitar)

- "September" convertido pelo PDF-to-GP5 depois de 6626363 e b7031ab: os bends
  aparecem no Guitar Pro e no TuxGuitar (antes não apareciam), com a mesma
  forma do alphaTab.

## Confirmado

| O quê | Onde | Notas |
|---|---|---|
| A música aparece na lista e carrega (PSARC nativo) | Beartooth "Free" | |
| Bends de ½ com o tamanho certo (sobem, não aparecem já dobrados) e sem crash na parte C | Beartooth "Free" | |
| Slides, notas abafadas (fret-mute) e o intervalo entre notas | Beartooth "Free" | |
| Dificuldade dinâmica com alturas diferentes por frase | Beartooth "Free" | |
| Tocar notas e acordes sem crash (secção das oitavas) | Beartooth "Free" | Com a dificuldade dinâmica ligada e desligada |
| Slide para fora (cauda sem altura) e slide para dentro | — | `TESTING.md` §7f-bis |
| Letra a passar no ecrã, cartão com o nome da música e luzes do palco | Várias músicas | |
| Áudio dentro do `.gp` do PDF-to-GP5 (`backing-track.mp3`) detetado e usado, com o início antes da gravação (−2,15 s) a bater na página de sincronização | Daughtry "September" (2026-09-30) | Precisou de 8b61bf0. Ainda não confirmado no jogo: ver o problema aberto acima |
