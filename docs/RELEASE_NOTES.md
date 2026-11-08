### New

- **Example project and tutorial:** on the home page, **Example project** creates an invented song whose recording starts late, is slower than the tab and speeds up at bar 9. The Guide now has a tutorial that syncs it step by step, with the right values to check each step against, and the "How to sync" card links to it.

- **A PSARC without one instrument:** in Export → Build options, **Recording** now has "Without: Bass" (or guitar, vocals…), so you play that instrument over the rest of the song. RockForge puts the other separated instruments together and uses that mix as the audio; the song gains "(no bass)" in its title and sits in game beside the full version. It needs "Separate instruments" first. Separation is never perfect: a trace of the instrument taken out may still be heard.

- **Simpler syncing:** the Sync inspector now has **Simple** and **Advanced**. Simple (the usual one) keeps only the tools most songs need, with a four-step **How to sync** guide: start, tempo, fix where it drifts, apply and confirm. Each step takes you to the right card. The rest (main track, automatic sync, the recording's attacks, the Mark, Excerpt, Move following and Align bar modes) is under Advanced, and switching loses no correction.

- **Each tone has its own volume on the Tones page:** the cards under "Project tones" now have "Volume in game" (higher = louder), without opening the tone editor. In Settings, the target loudness now says it is the recording's, not the tones', and that it only counts for projects you rebuild after saving. (GitHub #24)

### Fixes

- **A Songsterr tab's capo comes in:** Songsterr counts frets from the capo, as Guitar Pro does, but the import ignored it, so a capo-2 tab played two semitones low. The capo now goes into the Guitar Pro file RockForge writes, and the frets are counted from the nut, as everywhere else in the program. A capo that is not a valid fret is ignored, and the warning says so.

- **3D highway:** it no longer draws while its page or panel is not shown, and the note right at the paused position (after a click on a bar, for example) lights up again when Play is pressed.
- **Tab PDFs and pictures:** a digit that is not ASCII ("²", "①") in the PDF or read by OCR no longer stops the import, and a 16-bit greyscale PNG picture is no longer read almost all white.

- **A Songsterr tab no longer comes in at another part's tempo:** each part of a Songsterr tab carries its own tempo, and RockForge used the first imported track's. In a tab whose bass changes tempo almost every bar, the notes of bar 7 came earlier than in the `.gp` of the same tab. It now uses the tempo of the longest part (the first, on a tie), even if that is the drums, and says which one it used when the parts disagree. (GitHub #26)

- **Palm mutes from a Songsterr tab come in:** Songsterr can mark a palm mute on the beat rather than on each note, and RockForge only looked for it on the note, so those palm mutes were lost from the score and the `.psarc`. They now apply to every note of the beat. Tapping, tremolo picking, the pick direction (down / up) and harmonics written another way come in too. (GitHub #23)

- **A version rebuilt during a detection can be deleted again:** if you rebuilt the project while it was separating instruments or detecting tones or lyrics, the new version stayed stuck as "running" and deleting it always failed. It now starts without that status. And in the app (`.exe`), a build or detection left halfway because the app closed now says so when you open it again, instead of waiting forever.

- **Closing the app with work in progress really closes it:** after you answered "Quit anyway?", the `.exe` kept running with no window until its queued work finished, and opening it again meanwhile put two RockForges on the same database.

- **The Lead track's edits are no longer lost when you add or remove the Rhythm track:** on its own, the Lead track is built as Combined; with a Rhythm, as Lead. Changing that in "Edit info" made that track's edited notes, sync, hand positions, tones and tuning stop applying, without a warning. They now move to the new name.

- **Guitar tracks no longer get a bass tone:** if you had only used a bass tone from tone detection, the guitar tracks took it as their tone. Each track now uses only its own instrument's tones.

- **"Sync with the recording" no longer glues words together:** a word split into syllables was glued to the one before it ("she loo- king" became "shelooking") in the text aligned with the recording.

- **The score's keys work on the Score page only:** with notes selected, Backspace deleted them even on the Tones page, in Settings or in a dialog; Ctrl+C/V would not copy text on those pages and Space played the music inside a dialog.

- **Repeated chords show correctly at every difficulty level:** in a riff repeating one chord, the easier levels could show only the condensed strum marks and never draw the chord. The first chord of each run is now shown in full at every level.

- **A failed preview no longer throws the `.psarc` away:** if Wwise converted the song but not the preview clip, you got no `.psarc`. The preview now uses the whole song and the `.psarc` is built.

- **A Wwise 2025 no longer passes as supported:** the Wwise version was read from the whole path, so a Wwise 2025 inside a folder such as `Games2022` counted as 2022. The name of Wwise's own folder now decides.

- **An odd CDLC no longer stops the tone collection:** a manifest with a missing value (a knob with no value, for example) in a single file of the `dlc` folder made the whole reading in "Tones from your songs" fail. That value now takes its default and the other songs are read.

- **Turning the install counter off really deletes the data:** the request to delete what was sent was made only once; with no network, it was never repeated. It is now repeated at every start until the server answers.

- **A GP file with impossible numbers is refused with a message:** a `.gp` (GP7/8) with a 0/4, 4/0 or 1,000,000/4 bar, or a tempo of 0, gave an unexplained error — and the last one kept loading forever. A GP5 with a bar of no beats failed the build with a division by zero. The wizard now says what is wrong straight away.

- **An odd `.psarc` in the `dlc` folder no longer uses too much memory:** reading your songs' tones, one block of an archive could decompress to tens of MB (a file made on purpose reached 141 MB in a single block). Each block now stays the size of a block, and an inconsistent archive is reported as unreadable.

- **Pasting a huge text into "Import tones from a text" answers at once:** a text full of unclosed braces could keep the request working for minutes. The search for the tone block now has a limit and answers immediately.

- **A Songsterr track of more than seven strings is left out and said:** a GP5 holds up to seven strings, and the rest disappeared without a warning. The track now shows among the tracks not included, with its number of strings. A bar like 200/4 no longer gives an error.

- **Track names and tone values are checked:** a track name the app never makes (from a hand-made request) was stored in the project, and a tone knob set to NaN reached the game's manifest, which then was no longer valid JSON. Both are now refused.

- **With Redis stopped, the project says what is going on:** with no task queue, creating or rebuilding a project gave an error and the project stayed "pending" for ever. It is now marked as failed, asking you to check that Redis and the worker are running; a detection is "unavailable" with that line in its log.

- **Several unexplained errors became messages:** a malformed cover link (`http://[::1`), a huge year in "Edit info", an enormous number in a sync file, a `.psarc` or bundle deleted from disk by hand, an answer from LRCLIB or iTunes cut off mid-way, a stored GP file that can no longer be read, and a `.rfproj` project whose tone detection or vocal line had the wrong shape all gave a 500 error. Each is now refused with a message.

- **A section called "noguitar" no longer disappears:** the closing marker the app adds has that name, and every section with that name was removed when reading the score back, so a section of yours with that name was lost on the next rebuild. Now only the last one goes.

- **A short note's bend keeps its curve:** a bent note with no sustain lost its curve (up and back down, for example) when it was read back into the editor.

- **A sung grace note at the start of a bar gets its own syllable:** in a GP5, a grace note before a bar's first beat lasted nothing in the vocal line and its syllable sounded with the next note. It now starts in the bar before, like the note on the score.

- **The game and DLC Builder see the same chord techniques:** the manifest did not recognise a power chord strummed fast (strings 10 ms apart), and the XML said there were power chords and open chords in any track with chords. Both now use the same rule.

- **With a password (Docker), an upload without credentials is refused before it is received:** a file sent without the password was written to disk in full before it was refused. The refusal now comes at once, without reading the file.

- **A huge LRC file is refused:** the LRC sent in the wizard accepted up to 500 MB, which went into memory and the database. The limit is now a lyric's (800 KB).

- **The 3D highway no longer uses more and more memory in an A–B loop:** the notes' shapes were made again on every pass and only freed when the song changed. Each note now frees its own when it leaves the view.

- **The neck and the current tone cost less during playback:** the neck went through every note of the song on every frame, and the current tone label was rewritten 60 times a second. They are now only redone when something changes.

- **The recording's length reads the same everywhere:** 196.9 s showed as 3:17 in the online lyric results and as 3:16 under the score.

---

### Novidades

- **Projeto de exemplo e tutorial:** na página inicial, **Projeto de exemplo** cria uma música inventada cuja gravação começa tarde, é mais lenta do que a tab e acelera no compasso 9. O Guia tem agora um tutorial que a sincroniza passo a passo, com os valores certos para confirmares cada passo, e o cartão "Como sincronizar" liga para ele.

- **Um PSARC sem um instrumento:** em Exportar → Opções da construção, **Gravação** passa a ter "Sem: Baixo" (ou guitarra, voz…), para tocares esse instrumento por cima do resto da música. O RockForge junta os outros instrumentos separados e usa essa mistura como áudio; a música ganha "(sem baixo)" no título e fica no jogo ao lado da versão completa. Precisa de "Separar instrumentos" antes. A separação nunca é perfeita: pode ouvir-se um resto do instrumento tirado.

- **Sincronização mais simples:** o inspetor Sincronização tem agora **Simples** e **Avançado**. Em Simples (o habitual) ficam só as ferramentas que a maioria das músicas precisa, com um guia **Como sincronizar** em quatro passos: início, andamento, corrigir onde foge, aplicar e confirmar. Cada passo leva-te ao cartão certo. O resto (pista principal, sincronização automática, ataques da gravação, os modos Marcar, Excerto, Mover seguintes e Alinhar compasso) fica em Avançado, e nenhuma correção se perde ao mudar.

- **Cada tom tem o seu volume na página Tons:** os cartões em «Tons do projeto» têm agora «Volume no jogo» (maior = mais alto), sem ser preciso abrir o editor de tons. Nas Definições, o volume alvo diz que é o da gravação, não o dos tons, e que só conta nos projetos que reconstruíres depois de guardar. (GitHub #24)

### Correções

- **O capo de um tab do Songsterr já entra:** o Songsterr conta os trastes a partir do capo, como o Guitar Pro, mas a importação ignorava-o, e um tab com capo 2 tocava dois meios-tons abaixo. Agora o capo passa para o ficheiro Guitar Pro que o RockForge escreve e os trastes ficam contados a partir da pestana, como no resto do programa. Um capo que não seja um traste válido é ignorado e o aviso diz isso.

- **Pista 3D:** deixa de desenhar quando a página ou o painel não está à vista, e a nota que está exatamente na posição em pausa (num clique num compasso, por exemplo) volta a brilhar ao carregar em Tocar.
- **PDFs e imagens de tabs:** um algarismo que não é ASCII ("²", "①") no PDF ou lido por OCR já não interrompe a importação, e uma imagem PNG em tons de cinzento de 16 bits já não é lida quase toda a branco.

- **Um tab do Songsterr já não sai com o andamento de outra parte:** cada parte de um tab do Songsterr traz o seu próprio andamento, e o RockForge usava o da primeira pista que importava. Num tab cujo baixo muda de andamento quase em cada compasso, as notas do compasso 7 apareciam mais cedo do que no `.gp` do mesmo tab. Agora usa o andamento da parte mais longa (a primeira, num empate), mesmo que seja a bateria, e diz qual usou quando as partes não concordam. (GitHub #26)

- **Os palm mutes de um tab do Songsterr já entram:** o Songsterr pode marcar o palm mute no tempo (beat) e não em cada nota, e o RockForge só o procurava na nota. Esses palm mutes perdiam-se na partitura e no `.psarc`. Agora valem para todas as notas do tempo. Também passam a entrar o tapping, o tremolo picking, o sentido da palhetada (para baixo / para cima) e os harmónicos escritos de outra forma. (GitHub #23)

- **Uma versão reconstruída durante uma deteção já se pode apagar:** se reconstruísses o projeto enquanto separava instrumentos ou detetava tons ou letra, a versão nova ficava presa em «a correr» e apagá-la dava sempre erro. Agora começa sem esse estado. E, na aplicação (`.exe`), uma construção ou deteção que ficou a meio porque a aplicação fechou passa a dizer isso mesmo quando voltas a abrir, em vez de ficar à espera para sempre.

- **Fechar a aplicação com trabalho a meio fecha mesmo:** depois de responderes «Sair mesmo assim?», o `.exe` continuava a correr sem janela até acabar o trabalho que tinha em fila, e abri-lo outra vez nesse tempo punha dois RockForge na mesma base de dados.

- **As edições da pista Lead já não se perdem ao juntar ou tirar a pista Rhythm:** sozinha, a pista Lead é construída como Combined; com uma Rhythm, como Lead. Ao mudar isso em «Editar info», as notas editadas, a sincronização, as posições da mão, os tons e a afinação dessa pista deixavam de se aplicar, sem aviso. Agora passam para o nome novo.

- **As pistas de guitarra já não ficam com um tom de baixo:** se só tivesses usado um tom de baixo da deteção de tons, as pistas de guitarra levavam-no como tom. Agora cada pista só usa os tons do seu instrumento.

- **«Sincronizar com a gravação» já não cola as palavras:** uma palavra dividida em sílabas colava-se à anterior («she loo- king» passava a «shelooking») no texto que vai ser alinhado com a gravação.

- **As teclas da partitura só funcionam na Partitura:** com notas selecionadas, o Backspace apagava-as mesmo estando nos Tons, nas Definições ou num diálogo; Ctrl+C/V não deixavam copiar texto dessas páginas e o Espaço tocava a música dentro de um diálogo.

- **Os acordes repetidos aparecem bem em todos os níveis de dificuldade:** num riff com o mesmo acorde repetido, os níveis mais fáceis podiam mostrar só os traços condensados, sem nunca desenhar o acorde. Agora o primeiro acorde de cada série aparece inteiro em todos os níveis.

- **Uma falha na pré-escuta já não deita fora o `.psarc`:** se o Wwise convertesse a música mas não o excerto da pré-escuta, ficavas sem `.psarc`. Agora a pré-escuta usa a música inteira e o `.psarc` é criado.

- **Um Wwise 2025 já não passa por suportado:** a versão do Wwise era lida do caminho inteiro, por isso um Wwise 2025 dentro de uma pasta como `Jogos2022` contava como 2022. Agora conta o nome da pasta do próprio Wwise.

- **Um CDLC estranho já não para a recolha de tons:** um manifesto com um valor em falta (um botão sem valor, por exemplo) num só ficheiro da pasta `dlc` fazia falhar a leitura inteira em «Tons das tuas músicas». Agora esse valor fica por omissão e as outras músicas são lidas.

- **Desligar o contador de instalações apaga mesmo os dados:** o pedido para apagar o que foi enviado só era feito uma vez; sem rede, nunca mais era repetido. Agora é repetido em cada arranque até o servidor responder.

- **Um ficheiro GP com números impossíveis é recusado com uma mensagem:** um `.gp` (GP7/8) com um compasso de 0/4, 4/0 ou 1 000 000/4, ou um andamento de 0, dava um erro sem explicação — e o último ficava a carregar para sempre. Um GP5 com um compasso sem tempos falhava a construção com uma divisão por zero. Agora o assistente diz logo qual é o problema.

- **Um `.psarc` estranho na pasta `dlc` já não gasta memória a mais:** ao ler os tons das tuas músicas, um bloco do arquivo podia descomprimir-se em dezenas de MB (um ficheiro feito de propósito chegava a 141 MB num só bloco). Cada bloco fica agora no tamanho de um bloco, e um arquivo incoerente é dado como ilegível.

- **Colar um texto enorme em «Importar tons de um texto» responde logo:** um texto cheio de chavetas abertas podia deixar o pedido a trabalhar durante minutos. Agora a procura do bloco de tons tem um limite e responde de imediato.

- **Uma pista com mais de sete cordas vinda do Songsterr é deixada de fora e dita:** o GP5 guarda até sete cordas, e as restantes desapareciam sem aviso. Agora a pista aparece nas pistas não incluídas, com o número de cordas. Um compasso como 200/4 já não dá erro.

- **Os nomes das pistas e os valores dos tons são verificados:** um nome de pista que a aplicação não cria (vindo de um pedido feito à mão) era guardado no projeto, e um botão de um tom com valor NaN ia parar ao manifesto do jogo, que deixava de ser JSON válido. Ambos são agora recusados.

- **Com o Redis parado, o projeto diz o que se passa:** sem fila de tarefas, criar ou reconstruir um projeto dava erro e o projeto ficava «pendente» para sempre. Agora fica marcado como falhado, com a indicação para confirmar que o Redis e o worker estão a correr; uma deteção fica «indisponível» com essa linha no registo.

- **Vários erros sem explicação passaram a mensagens:** um link de capa malformado (`http://[::1`), um ano gigante em «Editar info», um número enorme num ficheiro de sincronização, um `.psarc` ou um bundle apagados à mão do disco, uma resposta cortada a meio do LRCLIB ou do iTunes, um ficheiro GP guardado que já não se consegue ler, e um projeto `.rfproj` com a deteção de tons ou a linha de voz num formato errado davam erro 500. Agora cada um é recusado com uma mensagem.

- **Uma secção chamada «noguitar» já não desaparece:** o marcador final que a aplicação acrescenta tem esse nome, e todas as secções com esse nome eram tiradas ao ler a partitura, por isso uma secção tua com esse nome perdia-se na reconstrução seguinte. Agora só sai a última.

- **O bend de uma nota curta mantém a sua curva:** uma nota com bend e sem duração perdia a curva (subir e voltar, por exemplo) ao ser lida de volta para o editor.

- **Uma nota de ornamento cantada no início de um compasso já tem a sua sílaba:** num GP5, a nota de ornamento antes do primeiro tempo de um compasso ficava com duração zero na linha de voz e a sílaba soava com a nota seguinte. Agora começa no compasso anterior, como a nota da pauta.

- **O jogo e o DLC Builder veem as mesmas técnicas de acordes:** o manifesto não reconhecia um power chord tocado em arpejo rápido (cordas a 10 ms umas das outras), e o XML dizia que havia power chords e acordes abertos em qualquer pista com acordes. Agora os dois usam a mesma regra.

- **Com palavra-passe (Docker), um envio sem credenciais é recusado antes de ser recebido:** um ficheiro enviado sem a palavra-passe era gravado por inteiro em disco antes de receber a recusa. Agora a recusa sai logo, sem ler o ficheiro.

- **Um ficheiro LRC enorme é recusado:** o LRC enviado no assistente aceitava até 500 MB, que iam para a memória e para a base de dados. Agora o limite é o de uma letra (800 KB).

- **A pista 3D já não gasta cada vez mais memória num loop A–B:** as formas das notas eram feitas de novo em cada passagem e só eram libertadas ao mudar de música. Agora cada nota liberta as suas quando sai de vista.

- **O braço e o tom em uso pesam menos durante a reprodução:** o braço percorria todas as notas da música a cada imagem, e o rótulo do tom em uso era reescrito 60 vezes por segundo. Agora só se refazem quando algo muda.

- **A duração da gravação lê-se da mesma forma em todo o lado:** 196,9 s aparecia como 3:17 nos resultados da letra online e como 3:16 debaixo da partitura.
