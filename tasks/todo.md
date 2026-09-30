# Português / English em toda a aplicação

Pedido: "cria a tradução de tudo o que está no rockforge para inglês. Fica opção
de Português e Inglês."

- [x] 1. Base: `web/i18n.js` (`T()`, `translateDom`, cabeçalho `X-RockForge-Lang`,
      seletor de idioma), `web/i18n-en.js`, `rockforge/i18n.py` (`tr(pt, en)`),
      `PUT /ui-language`, `tests/test_i18n.py`
- [x] 2. index.html: inglês para cada texto/atributo
- [x] 3. app.js (6 partes) + highway3d.js: textos por `T()`
- [x] 4. Servidor: mensagens em português → `tr(pt, en)` (diagnóstico, Songsterr,
      YouTube, pesquisa de capa/letra, HTTPS, ML, API, worker, janela do .exe)
- [x] 5. README.en.md
- [x] 6. Juntar, testes, Playwright nas duas línguas, docs

# Ruído / tom pouco limpo nos PSARC do RockForge

Pedido: "Existem problemas graves com os tons e mesmo sem os tons, normalmente
os PSARC criados pelo rockforge têm algum ruído e não têm uma tonalidade limpa."
Comparado com o DLC Builder (Rocksmith2014.NET):

- [x] 1. Áudio: sem `loudnorm` dinâmico (limitador + ganho variável sobre a
      gravação); o áudio fica intacto e o nível vem só do volume do SoundBank
      (`alvo - loudness`, como o DLC Builder), sem nunca passar os picos de 0 dBFS
- [x] 2. Pista sem tom: o tom por defeito do DLC Builder para o caminho
      (Lead/Rhythm), como `addDefaultTonesIfNeeded` — em vez de nenhum tom
- [x] 3. Trocas de tom no SNG nativo (a secção Tones ia vazia: nenhuma troca
      acontecia no jogo); id = posição do tom nos espaços A–D
- [x] 4. Testes, docs, verificação

# Deteção de tons melhorada + sugestões de tons por secção de cada pista

Pedido: "melhorar a deteção de tons das músicas e com sugestões para atribuir
tons a partes específicas da música (track)".

- [x] 1. `_librosa_runner`: as medições por janela (4 s, passo 1 s) numa só leitura
      do áudio, junto com as da música inteira (`tone_report`)
- [x] 2. `analyzer.window_profiles` (puro): cada janela ancorada no perfil da
      música inteira (calibrado) e variada pelas pistas que não dependem do
      tamanho da janela; janelas sem guitarra marcadas
- [x] 3. Tarefa `detect_tones` guarda a linha do tempo (relógio da gravação)
- [x] 4. `tone_analysis/sections.py` (puro): por secção × pista, o estilo do que
      a pista toca (acordes, palm mute, notas soltas agudas, bends, let ring) +
      o som da gravação nessa secção → papel (limpo/ritmo/solo) + tom da
      biblioteca + confiança + motivos; secções vazias herdam; junta seguidas;
      máximo 4 tons por pista (os espaços A-D, com o base)
- [x] 5. `GET /jobs/{id}/tone-suggestions`: calculado a partir do build ATUAL
- [x] 6. Tons por pista: `GpJobSpec.arrangement_tones` (+ worker, rebuild, /tones);
      sem entrada = os tons da música, como hoje
- [x] 7. UI Tons: pista escolhida + "os mesmos tons em todas as pistas";
      "Sugestões por secção" com a faixa colorida, motivos e "Aplicar"
- [x] 8. Testes, docs, verificação com a gravação real + Playwright

# Pista 3D ao estilo Rocksmith (three.js) na Partitura

Pedido: "grafismo 3D, com three.js, para o braço da guitarra … o mais idêntico
possível com o rocksmith"; esboço aprovado (headstock, afinação na pestana,
notas arredondadas, brilho no toque, a nota fica na corda com o número).

- [x] 1. three.js 0.186.1 vendido em `web/vendor/three/` (MIT) + rota `/vendor/three/{f}`
- [x] 2. `web/highway3d.js`: módulo que carrega o three.js só quando a pista é ligada;
      notas criadas só para a janela visível (canções com milhares de notas)
- [x] 3. Mesmo relógio que a partitura: `warp(previewScale(t))` das notas e
      `playheadDisplay(audioTime())` do cursor — segue as correções pendentes ao vivo
- [x] 4. API: `ArrangementNoteOut.slide_to` (o traste final do slide)
- [x] 5. UI: caixa "Pista 3D" ao lado de "Braço", painel por cima da partitura,
      câmara/traste na nota/ecrã inteiro; lembrado no browser
- [x] 6. ESLint também no `highway3d.js`; teste da rota e do spec; docs; Playwright

# Usar o áudio do ficheiro GP em todos os caminhos

Pedido: "Porque é que continuas a não aproveitar o mp3 do ficheiro gp?". O
ficheiro do utilizador (Ocean Eyes_synced.gp) é detetado pelo assistente normal
(verificado com Playwright), mas dois caminhos ignoram o áudio embutido.

- [x] 1. `/jobs/gp` regista `params["recording_from_gp"]`; `JobOut.recording_from_gp`
- [x] 2. `/reload-gp`: com `use_embedded_audio` (por omissão sim), o áudio do NOVO
      ficheiro substitui a gravação; se a gravação antiga desapareceu e o novo
      ficheiro tem áudio, usa-o em vez do 409; ao passar de um upload para o áudio
      do GP, o início vem de `sync_start_s` (como no assistente)
- [x] 3. UI "Recarregar ficheiro GP": caixa "usar o áudio do ficheiro, se trouxer"
- [x] 4. Lote: inspeciona cada GP ao escolher; os que trazem áudio usam-no e não
      consomem nenhuma gravação do emparelhamento
- [x] 5. Testes, docs, Playwright com o ficheiro do utilizador, gates

# Importar a tab diretamente do Songsterr (em vez de um ficheiro GP)

Pedido: colar o link da tab do Songsterr em vez de carregar um GP; juntar o
MP3 (do vídeo do YouTube) e os tempos por compasso do Songsterr.

- [x] 1. `songsterr.fetch_tab`: meta + JSON de cada pista (CDN do leitor do
      Songsterr, como o guitar-pro-youtube-sync) — só leitura, sem descarregar áudio
- [x] 2. `gpimport/songsterr_gp.py`: pistas do Songsterr → GP5 (PyGuitarPro):
      compassos/assinaturas/marcadores, andamento, ritmo (pontos, tercinas),
      trastes/cordas, ligaduras, hammer-on, slides, bends, vibrato, palm mute,
      notas mortas/fantasma, harmónicos, let ring, acentos
- [x] 3. `POST /songsterr/import`: gera o GP5 em `work_dir/gp/` e responde como
      o `/gp/inspect` (o resto do assistente não muda)
- [x] 4. Assistente passo 1: "Ou importa do Songsterr"; o passo 3 abre já com
      os vídeos dessa música (tempos por compasso) e o link para o MP3
- [x] 5. Testes (JSON de exemplo, sem rede), docs, Playwright, gates

Decisão (revista a pedido do utilizador, 2026-09): sem o áudio a importação
"não vale a pena" — o áudio do vídeo escolhido é descarregado com o yt-dlp
(`youtube_audio.py`, extra `[youtube]`), só esse vídeo, por id.
- [x] 6. `/youtube/audio` + `audio_token` no `/jobs/gp` + limpeza de órfãos;
      passo 3 descarrega sozinho após a importação; sessão do browser se 403

# Procurar a letra online e sincronizá-la

Pedido: "tenta procurar a letra… e sincronizá-la".

- [x] 1. `infrastructure/lyrics_lookup.py`: LRCLIB (`/api/search`, sem chave) por
      título + artista principal; candidatos com letra sincronizada (LRC) e/ou só
      texto; ordenar: sincronizada primeiro, depois duração mais próxima da gravação
- [x] 2. `GET /lyrics-lookup` e `POST /lyrics/parse` (LRC → eventos por palavra,
      com deslocamento)
- [x] 3. Sincronizar com a gravação: `POST /detect-lyrics` aceita `align_lines`
      (+ idioma adivinhado); o runner do WhisperX ALINHA o texto dado à voz em
      vez de transcrever (janelas por linha quando há tempos; a música inteira
      quando é só texto)
- [x] 4. UI "Letras": procurar, escolher, "1ª palavra = cursor", deslocar,
      "Sincronizar com a gravação"
- [x] 5. Testes (fakes), docs (CLAUDE/TESTING/TODO), Playwright, gates

Limites honestos: LRCLIB nunca contactado daqui (bloqueado); tempos do LRC são
os da versão oficial; o alinhamento precisa dos extras `[ml,lyrics]`.

# ML no .exe — delegar as fases pesadas a um Python externo

## O que eu disse antes estava incompleto

Escrevi "stems, tom, letra: ❌ **nunca** no .exe". Isso só é verdade para
imports **dentro do processo**. Verificado no código:

| fase | como corre hoje | importável no .exe? |
|---|---|---|
| Demucs (stems, tom, letra) | `subprocess(sys.executable, _demucs_patcher.py)` | não precisa |
| WhisperX (letra) | `subprocess(sys.executable, _whisperx_runner.py)` | não precisa |
| Banquet (stems) | `subprocess(sys.executable, train.py)` | não precisa |
| librosa (tom, "Corrigir daqui", afinação) | `import librosa` in-process | **precisa** |

4 dos 5 já são subprocessos. O que os parte no .exe é uma coisa só:
`sys.executable` é o **próprio .exe**, não um Python — relançaria o RockForge.

## Plano

- [x] 1. `Settings.ml_python` + override em `runtime_settings` (editável na UI)
- [x] 2. `infrastructure/ml_python.py`: resolve o interpretador + acha os runners
      (no bundle os `.py` não existem em disco — têm de vir por `_MEIPASS`)
- [x] 3. Trocar os 4 `sys.executable` pelo resolver
- [x] 4. `_librosa_runner.py` standalone (padrão do `_whisperx_runner.py`, zero
      imports de rockforge) para as 3 funções librosa; in-process quando dá
- [x] 5. `diagnostics`: sondar o Python externo por subprocesso; corrigir a
      mensagem "NÃO é possível no .exe"
- [x] 6. `/settings` + campo na modal ⚙️ com validação ✓/✗
- [x] 7. `rockforge.spec`: embarcar os runners como datas
- [x] 8. Testes + docs (CLAUDE.md, README, TESTING)

## Invariantes a não partir

- Sem o Python externo configurado, o .exe comporta-se exactamente como hoje
  (503 a nomear o que falta) — nada de crash novo.
- Correr por `start.bat` não muda nada: in-process continua a ser o caminho.
- A API nunca importa torch/librosa (regra de layering do CLAUDE.md) — a sonda
  do interpretador externo é um subprocesso.

## Estado

- [x] 1. `Settings.ml_python` + override em `runtime_settings`
- [x] 2. `infrastructure/ml_python.py` (resolve / availability / runner_path / run_json)
- [x] 3. Os 4 `sys.executable` trocados — guardado por AST, verificado com mutante
- [x] 4. `_librosa_runner.py` (uma implementação, dois transportes)
- [x] 5. `diagnostics` corrigido + linha nova "Python 3.11 para o ML"
- [x] 6. `/settings` + campo na modal com ✓/✗ por extra
- [x] 7. `rockforge.spec` embarca os runners (walk, guardado por teste)
- [x] 8. Docs

---

# Sincronização pelo Songsterr (2026-09-25)

O princípio do guitar-pro-youtube-sync: o Songsterr guarda, por música, o instante
de CADA COMPASSO num vídeo do YouTube, marcado por pessoas. O utilizador obtém o
MP3 por outra via (conversor do YouTube ou o próprio Songsterr), por isso o
RockForge só precisa dos tempos — não descarrega áudio nenhum.

- [x] `gpimport/sync_map.py`: o mapeamento por pontos (já usado pelos sync points
      do GP8) passa a ser partilhado pelos dois parsers
- [x] `parse_gp_track(..., bar_times=...)` nos DOIS parsers (GP5 e GP7/8):
      tempos por compasso externos, com prioridade sobre os sync points do GP8
- [x] `infrastructure/songsterr.py`: id a partir do link, meta + video-points
      (urllib, sem dependência nova), vídeos ordenados como o programa faz
- [x] `GET /songsterr?song=...` + `/jobs/gp` aceita `bar_times` (validado)
- [x] `GpJobSpec.bar_times` + worker
- [x] Assistente, passo 3: link → vídeos → escolhe → pré-preenche o início
- [x] Testes (HTTP falso — a API está bloqueada neste sandbox) + docs

Limites a dizer ao utilizador: API não documentada; o compasso N do Songsterr
tem de ser o compasso N do GP (o GP deve vir do Songsterr); o MP3 tem de ser o
áudio daquele vídeo; não verificado contra a API real a partir daqui.

---

# Layout novo: projeto em ecrã inteiro + ícones de traço (2026-09-25)

Aprovado pelo utilizador a partir dos esboços (tela "Novo layout"): ícones de
traço em vez de emojis, e o projeto em ecrã inteiro em vez de um modal.

- [x] Ícones: sprite SVG (`<symbol id="i-…">`) + `icon(name)` em app.js;
      trocar os emojis dos botões, menus, cabeçalhos, checklist e início
- [x] Projeto em ecrã inteiro: barra no topo (← voltar, título, estado,
      "Aplicar e reconstruir", Descarregar), barra lateral (Partitura, Tons,
      Letra, Capa, Exportar), centro = leitor + ferramentas + partitura,
      painel direito = Sincronização / Secções
- [x] Exportar: estado do build, avisos, checklist, downloads, exportar GP,
      afinação e opções da construção
- [x] Início: barra no topo (Novo projeto, Lote, Definições) + cartões
- [x] Nenhum id removido (app.js liga tudo por id) — verificar por diff
- [x] Verificar no browser (Playwright) + todos os gates; docs

## Songsterr: CERTIFICATE_VERIFY_FAILED (certificate has expired)
- [x] `_https.ssl_context()`: system roots + certifi, verification on
- [x] Songsterr, LRCLIB, album lookup and cover download use it
- [x] Clear message for a refused certificate (clock / antivirus / certifi)
- [x] `certifi` core dependency; PyInstaller contrib hook bundles it
- [x] Tests (mutation-checked), docs, gates
- [x] Then 403 from /api/meta (turned out: ERR_UNPUBLISHED tab): default `requests`
      like the reference tool, and the refusal now shows Songsterr's own reason
- [x] YouTube download failed where the reference tool worked: yt-dlp[default]
      (solver) + JS runtimes on PATH, warnings kept, failures classified
      (no runtime / unreadable Chromium session / login), diagnostics row

## Mudar o BPM do compasso
- [x] `planBarRetempo` (pure) + `setBarsTempo`: range → BPM, tail keeps tempo and shifts
- [x] 📏 popup + "Sincronizar por compasso" panel: Andamento row, pre-filled
- [x] Node checks (mutation-checked), Playwright on a real chart + rebuild, docs

## Letra sincronizada logo ao criar o projeto
- [x] Wizard step 4: LRCLIB search on arrival, best synced preselected (not over GP lyrics / an LRC file)
- [x] /jobs/gp `lyrics_lrc` → params["lrc_text"]; upload wins; unreadable → 422
- [x] Shared lyricsCardBody; test; Playwright wizard + Letra page regression; docs

## Alinhar o compasso pela linha (mesmo sem notas)
- [x] `.bar-hit` on each bar line/number; 📏 mode opens the popup for that bar; elsewhere still seeks
- [x] Playwright check (bar without a note on its start → "= cursor"), docs

## Acertar a letra ao pé da partitura
- [x] Inspector tab "Letra": whole-lyric shift, selected word (from here / only this / nudge / remove), pick/add at cursor
- [x] Click a word on the score selects it and opens the tab (no seek); "Pendente: letra"
- [x] Playwright check, docs

## Apagar notas
- [x] Delete / "Apagar" / "Notas ▾ → Apagar seleção" on the selected notes (any mode), deleted overrides
- [x] Ctrl+Z / "Desfazer apagar" restores exactly the deleted slots
- [x] Playwright check + real rebuild, docs

## Notas apagadas continuavam no build
- [x] Reproduce (6 of the last 12 deletes ignored; fret edits made twins)
- [x] Match overrides within 5 ms on the same string; unit test (mutation-checked); real rebuilds; docs + lesson

## Letra da pauta: Songsterr + tempo pela pista da voz
- [x] vocals: GP lyric text rules — 2+ spaces skip note beats, [comments] dropped, newline = line end, "Mo- ney" joins
- [x] ParsedGpTrack.lyric_onsets: beats (voice 1, not rests) of the track the lyrics belong to (GP5 trackChoice, GPIF track with <Lyrics>)
- [x] gp_pipeline: warp/strip/overrides carry it (dataclasses.replace); syllables timed on it, chart notes only as fallback
- [x] songsterr_gp: newLyrics → GP5 song.lyrics on the part that carries them (offset 0-based → startingMeasure+1)
- [x] tests (mutation-checked), real Songsterr-shaped import → build, docs
- [x] Found on the way: the warp dropped bend curves/fingering; GP lyrics never reached the editor (params mutated in place); cp1252 text aborted a Songsterr import

## "note beyond final ebeat" on a song ending in eighths
- [x] Reproduced with the user's GP5 (last note on the "and" of 4, grid ended on beat 4)
- [x] close_beat_grid in both parsers; exporter and /arrangements treat the final downbeat as the bar line
- [x] Tests (mutation-checked), the user's file built end to end, docs

# A pista de voz: frases, durações e melodia; áudio do YouTube sem Songsterr (2026-09-29)

Pedido: "implementa a 1, a 2 e a 3" (quebras de linha pelas pausas da voz,
duração da sílaba pela nota, melodia da voz como fonte de áudio) + "quando só
carrego um gp5, o mp3 não vem incluído — já não existia download de mp3?"

- [x] 1. Parsers: `lyric_onsets` → `lyric_notes` (início, fim, MIDI, pausa antes)
- [x] 2. `distribute_syllables`: duração = fim da nota; quebra de linha antes de
      uma palavra com maiúscula junto a uma pausa da voz (só quando o texto não
      traz as suas próprias quebras); sem maiúsculas → pela pausa
- [x] 3. Melodia da voz: `PipelineResult.vocal_melody` → `params["vocal_melody"]`
      → `GET /jobs/{id}/vocal-melody` → "Voz (sintetizada)" na Fonte de áudio
- [x] 4. Assistente passo 3: link do YouTube direto (sem Songsterr) → `/youtube/audio`
- [x] 5. Testes, docs, Playwright, gates
- [x] extra: o limite de 7 palavras contava sílabas e deixava palavras órfãs →
      conta palavras e parte ao meio; "Voltar à letra da pauta" para projetos
      já criados (as linhas do editor ganham ao ficheiro)

# A letra acompanha as correções de sincronização (2026-09-29)

Pedido: "quando corrijo o início das notas, a letra não se está a mover".

- [x] Linhas guardadas onde se veem; ao mudar a sincronização pendente da pista
      de referência passam do mapa antigo para o novo (pré-visualização e build)
- [x] Só a letra da pauta segue (`lyrics_follow_chart`); LRC/deteção não
- [x] Caixa no separador Letra; a voz sintetizada segue também
- [x] Silêncio inicial em falta em `arrangementPreviewScale`/`synthesizeArrangement`
- [x] Testes, Playwright com o ficheiro do utilizador, docs, gates

# Áudio do GP8 não detetado + marca "sincronizada" (2026-09-29)

- [x] Deteção tolerante (faixa desligada, .opus/.webm, nome com outra
      capitalização, um único áudio em Assets); YouTube e ficheiro externo ditos
- [x] Assistente: link do YouTube do próprio GP descarregado sozinho
- [x] `gp_synced` no build + preenchido no arranque para projetos antigos
- [x] `sync_source`; chip "Sincronizada"; cartão "Estado da sincronização"
- [x] Testes (mutação), Playwright, docs, gates

# Sincronização por pista, com a aba a verde (2026-09-29)

- [x] `synced_arrangements` + `PATCH /sync-confirmed {arrangement}`; canção
      confirmada quando todas as pistas estão
- [x] Aba verde (✓), cartão "Estado da sincronização" por pista
- [x] Bug: as alternativas apareciam como "Lead"/"Rhythm" e partilhavam as
      correções da pista principal → nome pelo ficheiro, ordem do build, export
- [x] Testes (mutação), Playwright, docs, gates
