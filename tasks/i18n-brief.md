# RockForge — Portuguese → English translation brief (shared by all agents)

RockForge is a web app (FastAPI + a vanilla-JS UI in `web/`) that turns Guitar Pro
files into Rocksmith 2014 songs. Its UI is written in **European Portuguese**. We are
adding **English** as a second language, switchable at runtime. Read `CLAUDE.md` only
if you need background; you do not need all of it.

## How the i18n works (already built — commit 30f1f20)

- `web/i18n.js` (loaded before `app.js`) defines the global **`T(pt, vars)`**: returns
  the English for the Portuguese string `pt` when the UI language is English, else `pt`
  itself. The Portuguese text IS the key. Placeholders: `T('{n} notas', {n: count})`.
- `web/i18n-en.js` holds `const I18N_EN = { "<Portuguese>": "<English>", ... }`
  (strict JSON inside the braces).
- `index.html` is translated at load by `translateDom()`: every **text node** and the
  `title` / `aria-label` / `placeholder` / `alt` / `data-name` attributes are looked up
  with whitespace collapsed (`\s+` → one space, trimmed). An element with
  `translate="no"` is skipped (use it for user data / proper nouns if needed).
- `tests/test_i18n.py` is the gate:
  - every index.html text/attribute (with a letter) must have an entry;
  - every `T('...')` literal in app.js/highway3d.js must have an entry;
  - `T()` must get a FIXED literal (a plain '...'/"..." or a backtick string WITHOUT
    `${}`) — put variable parts in `{placeholders}`;
  - placeholders must match between Portuguese and English;
  - no Portuguese string literal may be left outside `T()` in app.js/highway3d.js
    (heuristic: accents or common PT words). A string that is NOT shown to the user
    (e.g. compared with Portuguese data, a slug fallback) gets `// i18n-skip` on its line.
  You can import its helpers to see what's left, e.g.:
  `python3 -c "import sys; sys.path.insert(0,'tests'); import test_i18n as t; src=open('web/app.js').read(); L=src.splitlines(); print([(l,s[:60]) for l,s,c,e in t.js_strings(src) if t._looks_portuguese(s) and not t._is_t_arg(c) and 'i18n-skip' not in L[l-1] and A<=l<=B])"`

## Rules for wrapping JS strings (app.js / highway3d.js)

- Wrap every string the user can SEE: textContent/innerHTML, button labels, toasts,
  `alert`/`confirm`/`prompt`, titles/tooltips, `<option>` text, status text, the ⓘ info
  bodies (long HTML strings — the whole HTML string can be the key: `body: T('<p>…</p>')`,
  and the English value keeps the SAME markup), error messages written by the UI,
  number+unit phrases, etc. Also text the scanner does not flag (unaccented short
  words like 'Guardar', 'Pausa', 'Lead alternativo'): READ YOUR WHOLE RANGE.
- Template literals with interpolation: turn the visible sentence into one key with
  placeholders: `` `${n} de ${m} pistas marcadas` `` → `T('{n} de {m} pistas marcadas', {n, m})`.
  For HTML templates, wrap just the text pieces: `` `<b>${x}</b> ${T('notas')}` `` —
  or one key with placeholders if the sentence would otherwise be cut up badly
  (`T('O compasso 1 começa em <b>{s} s</b> desse vídeo', {s: ...})` — fine: markup
  inside a key is allowed). Prefer whole sentences as keys so English word order works.
- Plurals: pick with a conditional between two keys.
- Do NOT translate: ids, CSS classes, data values, API field names/values, localStorage
  keys, arrangement kinds sent to the server ('Lead', 'Rhythm', 'Combined',
  'Alternate Lead'…), technique codes, gear keys, file names, server-supplied text
  (the server translates its own messages), user data (song titles, tone names…).
- If code READS displayed text back and compares it with Portuguese
  (`btn.textContent === 'Pausa'`), refactor it to compare state instead.
- `T` is a global function name — never declare a local `T`. (`t` is used everywhere
  as a time variable; that is fine, it is a different name.)
- `T()` evaluated at load (top-level tables) is fine: the language is fixed per page
  load (switching reloads the page).
- Keep code style; touch only strings. Don't reformat.

## Glossary (use consistently; US English)

Partitura→Score · Pista (a chart/track)→Track · Arranjo→Arrangement · Sincronização/
sincronizar→Sync/synchronize · Definições→Settings · Projeto→Project · Lote (álbum)→Batch
(album) · Gravação→Recording · Letra→Lyrics · Tom/Tons→Tone/Tones · Capa→Cover ·
Exportar→Export · Aplicar e reconstruir→Apply and rebuild · Reconstruir→Rebuild ·
Descarregar→Download · Carregar (upload)→Upload · Compasso→Bar · Andamento→Tempo ·
Secção→Section · Início da música→Song start · Corrigir daqui→Fix from here · Mover
seguintes→Move following · Modo→Mode · Encaixar em→Snap to · Cursor→Cursor ·
Pista principal→Main track · Silêncio inicial→Intro silence · Mistura completa→Full mix ·
(sintetizada)→(synthesized) · Testar tom→Preview tone · Fonte de áudio→Audio source ·
Braço→Fretboard · Pista 3D→3D highway · Estado da sincronização→Sync status · Marcar
como sincronizada→Mark as synced · Antes de usar→Before you use it · Afinação→Tuning ·
traste→fret · corda→string · acorde→chord · Pendente→Pending · Versão anterior→Previous
version · Editar info→Edit info · Novo projeto→New project · Lead alternativo→Alternate
lead · Rhythm alternativo→Alternate rhythm · Lead/Rhythm/Combo/Bass stay as is ·
ficheiro→file · Não tens o áudio?→Don't have the audio? · Sessão do browser→Browser
session · Arrastar→Drag · Excerto→Excerpt · Editar notas→Edit notes · Alinhar
compasso→Align bar · Procurar→Search · Guardar→Save · Remover→Remove · Apagar→Delete ·
Limpar→Clear · Desfazer→Undo · Copiar/Colar→Copy/Paste · Assistente→Wizard ·
ⓘ info boxes keep their icon. Keep emoji and symbols (✓ ⚠ ▶ …) exactly as they are.
Use the informal but clear tone of the original ("Escolhe…" → "Choose…").

## Deliverable

- Your English entries in a JSON file `i18n-parts/<your-part>.json` at the repo root:
  a flat object `{"<Portuguese key exactly as T() receives it / as the page shows it>": "<English>"}`.
  Keys must match byte-for-byte (after JS unescaping for script strings; whitespace-
  collapsed for index.html texts). Do NOT edit `web/i18n-en.js` (other agents work in
  parallel; the lead merges the parts).
- Run `node --check web/app.js` and `npx eslint web/app.js` (or `npm run lint`) if you
  touched JS; run the relevant pytest (`python3 -m pytest -p no:warnings -o addopts="" -q tests/<file>`).
  The i18n tests will only pass after the merge — that's expected; use the helper
  one-liner above to check YOUR range is clean.
- Commit your work in your worktree (one commit, message "i18n: <part>"), trailers:
  Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01GeAknYTYRLS4B4vyUVDiRo
  Do NOT push. Report: files touched, count of strings wrapped, anything unsure
  (ambiguous meaning, code you had to refactor because it read text back).
