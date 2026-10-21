### Bugs fixed

- **Score, fretboard and 3D highway running ahead:** during playback the cursor and the lit notes were ahead of what you hear, by the computer's sound output delay (tens of milliseconds with wired speakers or headphones, a few hundred over Bluetooth). A chart in time looked like its notes were early, and syncing it by eye left it late in game. What you see now follows what you hear; pausing stops where you were listening.
- **Fretboard:** clicking a note on the score lights only that note on the neck. Before, the previous note stayed lit too when the two were less than 0.16 s apart.
- **Songsterr tabs — step 3:** after importing a Songsterr tab, picking another file in step 1 no longer carries that tab's times, the video's or its audio along. If fetching the videos from Songsterr fails, the wizard says it failed and lets you try again with "Find videos". A download of the video's audio that finishes after you chose the tab's tempo no longer becomes the recording. A tempo change at a position in the bar RockForge cannot read is now reported.

---

### Bugs corrigidos

- **Partitura, braço e pista 3D a tocar adiantados:** durante a reprodução, o cursor e as notas acesas iam à frente do que se ouve, pelo atraso da saída de som do computador (dezenas de milissegundos com colunas ou auscultadores com fio, algumas centenas com Bluetooth). Uma pista certa parecia ter as notas adiantadas, e acertá-la a olho deixava-a atrasada no jogo. Agora o que se vê acompanha o que se ouve; a pausa para onde se estava a ouvir.
- **Braço da guitarra:** clicar numa nota da partitura acende só essa nota no braço. Antes, a nota anterior também ficava acesa quando as duas estavam a menos de 0,16 s uma da outra.
- **Tabs do Songsterr — passo 3:** depois de importar uma tab do Songsterr, escolher outro ficheiro no passo 1 já não leva consigo os tempos dessa tab, do vídeo nem o áudio dele. Se ir buscar os vídeos ao Songsterr falhar, o assistente diz que falhou e deixa tentar de novo em «Procurar vídeos». Uma transferência do áudio do vídeo que acabe depois de escolheres o andamento da tab já não passa a ser a gravação. Uma mudança de andamento numa posição do compasso que o RockForge não sabe ler passa a ser avisada.
