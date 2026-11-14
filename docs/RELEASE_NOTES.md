### Fixes

- **A slide into a note no longer turns the note before it into a slide:** when the tab marks a slide into a note (like "8 /12"), the picked note before it became a slide up to that note (the 8 slid to the 12), which the tab does not have. The note before is now left as it is. When there is room before the note, the slide-in is still a short note a few frets lower, now linked to the note, so the game shows one attack sliding onto it. When there is no room, the note stays plain. Rebuild the song to see the change.

- **Moving a note to another string or fret no longer leaves the old one behind:** if the same rebuild (or a later one) also corrected the sync, the old note stayed on the score and the new one sat at its time from before the correction. Note edits now follow the sync, like sections and tone changes. When you drag a note only onto another string, a small sideways wobble of the mouse no longer changes its time. In a project where this already happened, clear it with "Notes ▾" → "Clear this track" and redo the edit.

- **Editing a note no longer takes away its tremolo or pinch harmonic:** in "Edit notes", changing only the fret (or the length) of a note with tremolo picking or a pinch harmonic removed that technique on the rebuild, because the editor never received it. A note now keeps every technique it had that the edit window does not show, and the score marks them (**T.P.** and **P.H.**), as the 3D highway does. An arpeggio's let ring also stays when one of its notes is edited.

---

### Correções

- **Um slide de entrada já não transforma a nota anterior num slide:** quando a tab marca um slide para dentro de uma nota (como "8 /12"), a nota palhetada antes dela passava a um slide até ao alvo (o 8 deslizava até ao 12), coisa que a tab não tem. Agora a nota anterior fica como está. Quando há espaço antes da nota, o slide de entrada continua a ser uma nota curta uns trastes abaixo, agora ligada ao alvo, para o jogo mostrar um só ataque a deslizar até ele. Quando não há espaço, a nota fica simples. Reconstrói a música para ver a mudança.

- **Mudar uma nota de corda ou de traste já não deixa a antiga no sítio:** se na mesma reconstrução (ou numa seguinte) também acertavas a sincronização, a nota antiga continuava na partitura e a nova ficava no tempo de antes da correção. Agora as edições de notas acompanham a sincronização, como as secções e as mudanças de tom. Ao arrastar uma nota só para outra corda, um pequeno desvio do rato para o lado já não lhe muda o tempo. Num projeto onde isto já aconteceu, apaga em "Notas ▾" → "Limpar esta pista" e refaz a edição.

- **Editar uma nota já não lhe tira o tremolo nem o harmónico pinch:** em "Editar notas", mudar só o traste (ou a duração) de uma nota com tremolo picking ou harmónico pinch tirava-lhe essa técnica na reconstrução, porque o editor não as recebia. Agora a nota guarda todas as técnicas que tinha e que a janela de edição não mostra, e a pauta passa a marcá-las (**T.P.** e **P.H.**), tal como a pista 3D. O let ring de um arpejo também fica quando se edita uma das notas.
