### New

- **Merge two tracks: choose the bars** (New project → Tracks, and Edit info). A grid of the
  song's bars says which go into the arrangement; by default only the bars where the arrangement
  has no notes — so a LEAD with few notes takes the RHYTHM's parts only where it is silent. Click,
  drag or Shift+click to choose. Experimental.

### Bugs fixed

- **Moving notes and chords without spoiling the tempo.** Notes were moved with the "Drag" mode,
  which is a sync tool: each drag stretches the timing around it, changes the bars' BPM and does
  not let a note pass another. Now, in **Edit notes**, dragging a box on empty staff (or
  Ctrl+click) selects a chord or several notes, and dragging one of them moves them all — they can
  pass other notes and the tempo does not change. "Drag" says what it does and warns when a note
  tries to pass its neighbour.
- **What you change during a detection is no longer lost.** While "Detect lyrics", "Detect tone"
  or "Separate instruments" ran, an uploaded cover, "Mark as synced", the main chart, swapped tones
  or "Install in game" were undone by the next progress line.
- **Lyric detection works in the .exe.** It always failed, after minutes of separation.
- **A title or artist with an accent ("Canção", "Beyoncé") gets its .psarc** when Wwise is
  installed. The song's internal name is now unaccented letters only (songs with accents get a new
  internal name; install them in the game again).
- **Editing a note no longer removes its slide**, nor its bend curve, its link to the next note or
  its fingering. Pasting notes keeps the slide too.
- **The sync tools no longer fold the score** when used after setting the "Song start": "Drag",
  "Mark", "Move following", "Correct from here" and "Mark while listening" pin the start and end of
  the song. The notes after used to lose the correction and the rebuild could fail with "beats must
  be in chronological order"; now, if a correction folds the timing, the message says where.
- **The "Cursor" snap works** (it took notes to the song's last beat).
- **"Guitar Pro with the edited notes" keeps the capo.**
- **"Check PSARC" no longer reports a fault** for a song with slap, pop or tap.
- **A refused cover (too big, or not an image) no longer deletes the cover that was there.**
- **A project (.rfproj) or sync file with a wrong value is refused** naming it, instead of taking
  the home page down.
- **GP7/8 files with a piano (two staves) before the guitar** read the right track.

---

### Novo

- **Juntar duas pistas: escolhe os compassos** (Novo projeto → Pistas, e Editar info). Uma grelha
  com os compassos da música diz quais entram no arranjo; por defeito, só os compassos em que o
  arranjo não tem notas — assim um LEAD com poucas notas recebe as partes do RHYTHM só onde está
  calado. Clica, arrasta ou Shift+clique para escolher. Experimental.

### Bugs corrigidos

- **Mover notas e acordes sem estragar o andamento.** Para mudar notas de sítio usava-se o modo
  "Arrastar", que é uma ferramenta de sincronização: cada arrasto estica o tempo à volta, muda o
  BPM dos compassos e não deixa uma nota passar a outra. Agora, em **Editar notas**, arrastar uma
  caixa no espaço vazio (ou Ctrl+clique) seleciona um acorde ou várias notas, e arrastar uma delas
  move-as todas — podem passar por outras notas e o andamento não muda. O "Arrastar" diz o que
  faz e avisa quando uma nota tenta passar a vizinha.
- **O que mudavas durante uma deteção já não se perde.** Enquanto corria "Detetar letra",
  "Detetar tom" ou "Separar instrumentos", uma capa carregada, "Marcar como sincronizada", a pista
  principal, os tons trocados ou "Instalar no jogo" eram desfeitos pela linha de progresso seguinte.
- **No .exe, a deteção de letra funciona.** Falhava sempre, ao fim de minutos de separação.
- **Um título ou artista com acento ("Canção", "Beyoncé") já tem .psarc** quando o Wwise está
  instalado. O nome interno da música passa a ser só letras sem acento (as músicas com acento
  ganham um novo nome interno; reinstala-as no jogo).
- **Editar uma nota já não lhe tira o slide**, nem a curva do bend, a ligação à nota seguinte ou a
  dedilhação. Colar notas também mantém o slide.
- **As ferramentas de sincronização já não dobram a partitura** quando usadas depois de acertar o
  "Início": "Arrastar", "Marcar", "Mover seguintes", "Corrigir daqui" e "Marcar a ouvir" fixam o
  início e o fim da música. Antes, as notas a seguir perdiam o acerto e a reconstrução podia falhar
  com "beats must be in chronological order"; agora, se uma correção dobrar o tempo, a mensagem diz
  em que ponto.
- **O encaixe "Cursor" funciona** (levava as notas para o último tempo da música).
- **"Guitar Pro com as notas editadas" mantém o capo.**
- **"Verificar PSARC" já não acusa falha** numa música com slap, pop ou tap.
- **Uma capa recusada (grande demais ou que não é imagem) já não apaga a capa que havia.**
- **Um projeto (.rfproj) ou ficheiro de sincronização com um valor errado é recusado** a dizer qual,
  em vez de deitar abaixo a página inicial.
- **Ficheiros GP7/8 com um piano (duas pautas) antes da guitarra** já leem a pista certa.
