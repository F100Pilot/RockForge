# Testes no jogo

O que os testes automáticos não conseguem confirmar: como o chart aparece e se
toca no Rocksmith 2014, e como os ficheiros abrem no Guitar Pro / TuxGuitar.
Atualizar depois de cada teste (passar de "Por testar" para "Confirmado", com a
data e a música). O detalhe técnico de cada ponto está em `TESTING.md` §7.

Em cada teste: gerar o PSARC nativo (`psarc_mode=native`). Se algo correr mal,
gerar também pelo DLC Builder, para saber se o problema é do PSARC nativo.

**Versões atuais: RockForge 0.9.0.0** (`main` fb37c18, 2026-09-30) e
**PDF-to-GP5 0.7.0** (de onde vêm os `.gp`/`.gp5` de teste). O que está "Por
testar" é para testar nestas versões: atualizar com o `start.bat`, que faz o
`git pull`, e gerar de novo o PSARC — um PSARC feito antes não tem as correções.

### Verificado aqui (sem o jogo), nestas versões

| O quê | Data | Resultado |
|---|---|---|
| Testes do RockForge (`pytest`) | 2026-09-30 | Todos passam |
| RockForge igual ao alphaTab (skill `rockforge-alphatab-check` do PDF-to-GP5), nos 12 PDFs convertidos pelo PDF-to-GP5 0.7.0, no `September.gp` (6 pistas, com áudio) e no `teste-prebend.gp5` | 2026-09-30 | Tudo igual, incluindo a forma dos bends |

## ✅ Resolvido: crash no "September" (2026-09-30)

O jogo fechava no Daughtry "September" (primeiro ao tocar, depois no Riff
Repeater ao subir a dificuldade). Foram quatro correções seguidas, a última
decisiva: as fases do PSARC nativo passaram a ser geradas **exatamente como o
DLC Builder as gera** ao construir o pacote (ponto 15 abaixo, em "Confirmado").
**Testado no jogo pelo utilizador e confirmado: perfeito.** Qual das quatro
correções (pontos 12–15) o jogo exigia não está isolado — ficam todas.

## Por testar — alterações recentes

| # | O quê | Commit | Como testar | O que deve acontecer | Se falhar |
|---|---|---|---|---|---|
| 1 | **Pre-bend simples** dobrado desde o início da nota | 513d653 | `teste-prebend.gp5` + `teste-prebend.mp3`, acerto 0 (ver abaixo) | Compassos 2, 3, 6 e 8: notas já dobradas desde o início. 5: só a corda Sol dobrada. 4: começa dobrada e desce. 7: dobrada durante a nota toda. Sem crash | Reverter 513d653 (volta a subida) |
| 2 | **Bend de 3 pontos** como subida ao longo da nota | ae9dab0 | Compasso 1 do mesmo teste | Sobe durante a nota (um ponto no fim da nota, a forma já confirmada no Beartooth) | Avisar |
| 3 | **Bend + release no tempo certo**, também numa nota ligada | 8cda047, 028d004 | Daughtry "September", compasso 4 (nota aos 13,2 s) | A nota fica, sobe ½ perto do fim, volta, e o pull-off vem a seguir | Avisar, com o compasso |
| 4 | **Repetições, voltas e saltos** (D.C., D.S., Coda) tocados pela ordem do alphaTab | 48b47e1 | Um GP com `|: :|`, 1ª/2ª volta ou D.S. | O chart segue a música em todas as passagens, sem compassos a mais ou a menos | Avisar, com a música |
| 5 | **Início antes do áudio** (acerto negativo), também na página de sincronização | 9fff993, 39a5aa4 | Um GP sincronizado cujo compasso 1 começa antes da gravação | As notas batem com a música desde o início | Avisar |
| 6 | **Grace notes, rasgueado, harmónico pinch (GP5), vibrato ligado** | f8f1537 | Um GP com estas técnicas | A grace note aparece como nota curta antes da principal (com hammer quando o tem); o pinch tem o símbolo de pinch | Avisar, com a técnica |
| 7 | **Let ring nos `.gp`** | f5fa599 | Um `.gp` com let ring ("September.gp") | A nota continua a soar por cima das seguintes | Avisar |
| 9 | **Som da gravação sem compressão** (sem `loudnorm`, só um ganho fixo) | (este) | Reconstruir uma música que soava com ruído / pouco limpa | Soa como a gravação original: sem "bombear", sem ataques esmagados, sem estalidos nas partes fortes | Avisar; experimentar Volume alvo -16 na ⚙️ |
| 10 | **Trocas de tom a meio da música** no PSARC nativo | (este) | Marcar na partitura uma troca para um 2.º tom e reconstruir | O tom muda nesse ponto (antes ficava sempre o tom base) | Avisar, com o tempo da troca |
| 11 | **Pista sem tom próprio** | (este) | Uma música sem nenhum tom criado | Lead/Combo com o tom por defeito do DLC Builder (Plexi), Rhythm com o Orange AD50 — não um som estranho/em falta | Avisar |
| 12 | **Posição dos dedos nos acordes** (dedos, nome do acorde e "hand shapes") — **os dedos já aparecem (confirmado 2026-10-05)**; falta ver se crasha | (este) | Tocar várias músicas com acordes e, no Riff Repeater, subir a dificuldade em partes com acordes. Insistir em: acordes repetidos rápidos, acordes longos (sustain) seguidos de outro acorde, mudanças de acorde a meio de uma frase, oitavas com cordas saltadas (5/7), acordes logo no início da música e uma música com Lead e Rhythm alternativos | Nenhum crash, a tocar ou a mudar de dificuldade | Avisar com a música, a pista, o tempo/compasso e o nível de dificuldade: as hand shapes são o primeiro suspeito |
| 13 | **Número de cada pista** (`SongPartition`: a Lead alternativa é a 2.ª Lead) | (este) | Reconstruir uma música com Lead e Lead alternativo (ou Rhythm e Rhythm alternativo) | No jogo, a alternativa aparece como a 2.ª Lead/Rhythm, com o mesmo nome que a aplicação mostra nas abas ("LEAD 2") | Avisar com o que o jogo mostra (uma foto ajuda) |
| 14 | **"Instalar no jogo"** (copia para `dlc\RockForge`) | (este) | Página Exportar → "Instalar no jogo", depois abrir o jogo | A música aparece na lista (a subpasta `RockForge` é lida). Reinstalar uma versão nova substitui a anterior | Avisar: se não aparecer, a subpasta não é lida e passa a copiar para `dlc` diretamente |

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
| Áudio dentro do `.gp` do PDF-to-GP5 (`backing-track.mp3`) detetado e usado, com o início antes da gravação (−2,15 s) a bater na página de sincronização | Daughtry "September" (2026-09-30) | Precisou de 39a5aa4. Também no jogo, depois das correções abaixo |
| Pista que só entra a meio da música (secções por ordem, sem bloquear) | Daughtry "September" (2026-09-30) | Rhythm, Lead alternativo e Rhythm alternativo — 075da13 |
| Subir a dificuldade no Riff Repeater sem crash (posição da mão do nível, fases de uma nota com níveis, bytes das notas como no DLC Builder) | Daughtry "September" (2026-09-30) | 44f5338, 649ae72 |
| Fases geradas como o DLC Builder (COUNT até à 1.ª nota, uma fase a cada 8 compassos, NOGUITAR nas pausas, secções "Riff"/"No Guitar") | Daughtry "September" (2026-09-30) | 33da4d3 — "Está perfeito". Todas as pistas, a tocar e no Riff Repeater |
