### New

- **Score:** with no mode selected, clicking a note takes the cursor to it, and the fretboard shows and picks it ("All notes").
- **Sync:** the song start, the corrections, sections, tone changes, lyrics and intro silence now adjust to the millisecond (three decimals).
- **3D highway — bends:** a bend now shows in teal. The note's trail rises following the bend (up, held, released, pre-bend) and, when the note reaches the strings, it rises on the string as it is bent, up to a dashed frame at the height the bend has to reach — a whole step rises one string gap.
- **Mark by ear — every attack:** a new mode, "I tap on every attack", marks every strum you hear with the B key, without moving the score. The taps sit in green over the staff and are saved with the project, per track; the score shows the notes with no tap and the taps with no note, with "Previous/Next difference". To fix them, "Marked attacks" in "Snap to" takes the notes you drag or add to the taps, and "Snap the selected notes to the taps" moves each note or chord to the nearest tap. Requested by Liam.

### Bugs fixed

- **Songsterr tabs — sync:** a tab imported from Songsterr lost its tempo's decimals (117.85 BPM became 117) and its mid-bar tempo changes, so it started right and drifted away from the recording. The notes now follow the tab's own tempo, bar by bar, as in Songsterr's player. In step 3 you choose which recording you will play — Songsterr's MP3 (or another that follows the tab) or a YouTube video's audio — and each choice says which recording it fits; uploading a file of your own with a video's times shows a warning.
- **Work folder moved:** after moving RockForge's data folder (to another disk or computer), earlier projects could no longer find their bundle, recording, GP file and stems. On start, RockForge now looks for them in the new folder.
- **Songsterr:** a video whose marks start before the video begins (a count-in marked at negative times) was refused when creating the project. It is now accepted, and every bar sits on its own mark. Contributed by mongrelx (#5).
- **Arrangement with no notes:** when the GP track picked for an arrangement has no notes (a vocal, drum or empty track), the error now says which arrangement and which track, and what to do, instead of just "arrangement has no notes".
- **Fretboard — "Only those matching the picked one":** with no note picked, it showed every note on the neck. Now only the equivalents of the picked note show (picked on the neck or clicked on the score), and nothing until you pick one.

---

### Novidades

- **Partitura:** sem nenhum modo escolhido, clicar numa nota leva o cursor a essa nota, e o braço mostra-a e escolhe-a ("Todas as notas").
- **Sincronização:** o início da música, as correções, as secções, as mudanças de tom, a letra e o silêncio inicial passam a ajustar-se ao milissegundo (três casas decimais).
- **Pista 3D — bends:** um bend passa a ver-se em verde-água. O rasto da nota sobe seguindo o bend (subir, segurar, soltar, pré-bend) e, quando a nota chega às cordas, sobe na corda à medida que é dobrada, até uma moldura tracejada na altura que o bend tem de alcançar — um tom sobe um espaço de corda.
- **Marcar a ouvir — cada ataque:** um novo modo, "Toco em cada ataque", marca com a tecla B cada palhetada que ouves, sem mexer na partitura. Os toques ficam a verde por cima da pauta e guardados com o projeto, por pista; a partitura mostra as notas sem toque e os toques sem nota, com "Diferença anterior/seguinte". Para corrigir, "Ataques marcados" em "Encaixar em" leva as notas que arrastas ou acrescentas para os toques, e "Encaixar as notas selecionadas nos toques" leva cada nota ou acorde ao toque mais perto. Pedido de Liam.

### Bugs corrigidos

- **Tabs do Songsterr — sincronização:** uma tab importada do Songsterr perdia as casas decimais do andamento (117,85 BPM ficava 117) e as mudanças de andamento a meio do compasso, por isso começava certa e ia-se afastando da gravação. Agora as notas seguem o andamento da própria tab, compasso a compasso, como no leitor do Songsterr. No passo 3 escolhes com que gravação vais tocar — o MP3 do Songsterr (ou outra que siga a tab) ou o áudio de um vídeo do YouTube — e cada opção diz com que gravação bate; se carregares um ficheiro teu com os tempos de um vídeo, aparece um aviso.
- **Pasta de trabalho mudada de sítio:** depois de mover a pasta de dados do RockForge (para outro disco ou outro computador), os projetos antigos deixavam de encontrar o bundle, a gravação, o ficheiro GP e os stems. No arranque, o RockForge passa a procurá-los na pasta nova.
- **Songsterr:** um vídeo cujas marcações começam antes do início do vídeo (uma contagem marcada em tempos negativos) era recusado ao criar o projeto. Agora é aceite, e cada compasso fica na sua marcação. Contribuição de mongrelx (#5).
- **Arranjo sem notas:** quando a pista GP escolhida para um arranjo não tem notas (uma pista de voz, de bateria ou vazia), o erro diz agora qual arranjo e qual pista, e o que fazer, em vez de só "arrangement has no notes".
- **Braço — "Só as iguais à escolhida":** sem nenhuma nota escolhida, mostrava todas as notas do braço. Agora só aparecem as equivalentes à nota escolhida (no braço ou clicada na partitura), e nada até escolheres uma.
