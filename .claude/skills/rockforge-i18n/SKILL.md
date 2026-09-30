---
name: rockforge-i18n
description: RockForge is a multilingual app (Portuguese original + English + any other language added later). Use this skill WHENEVER a change adds or edits text a user can see — web UI markup (web/index.html), script strings (web/app.js, web/highway3d.js: labels, toasts, alert/confirm, ⓘ texts, tooltips, status lines), or messages the server writes (HTTPException details, diagnostics rows, task logs/warnings, the desktop window's dialogs) — and when adding a new language. Every new text ships translated into EVERY language the app has, in the same change.
---

# RockForge i18n — every new text, in every language

RockForge is **polyglot**. Portuguese is the original: code and markup are
written in Portuguese, and **the Portuguese text is the key**. Every other
language is one dictionary. A change that adds visible text is not done until
that text exists in every dictionary — `tests/test_i18n.py` fails otherwise.

Read `CLAUDE.md` → "Languages" for the design. The pieces:

| where | how |
|---|---|
| `web/index.html` | nothing to call — `translateDom()` translates every text node and the `title`/`aria-label`/`placeholder`/`alt`/`data-name` attributes at load (whitespace collapsed). `translate="no"` skips an element. |
| `web/app.js`, `web/highway3d.js`, `web/i18n.js` | `T('texto em português')`, `T('{n} notas', {n})` — a FIXED literal, variable parts as `{placeholders}`, never `${}` in the key |
| dictionaries | `web/i18n-<code>.js`: `(self.I18N_DICTS = self.I18N_DICTS \|\| {}).<code> = { "<pt>": "<translation>", ... };` — strict JSON between the braces; served together as `/i18n-dicts.js` |
| server (Python) | `from rockforge.i18n import tr` → `tr("<pt>", "<en>", es="<es>", …)`; English is mandatory, other languages by keyword; a language not given reads the English |

## When you add or change visible text

1. **Write it in Portuguese** (European Portuguese, the app's informal tone:
   "Escolhe…", "Carrega…") — in the markup, or inside `T(...)` in a script, or as
   the first argument of `tr(...)` on the server.
2. **Script strings:**
   - Wrap the whole visible sentence: `` `${n} de ${m} pistas` `` →
     `T('{n} de {m} pistas', {n, m})`. HTML inside a key is fine; its
     translation keeps the SAME markup.
   - Plurals are two keys chosen by a condition.
   - Never `T()` an id, CSS class, API value, arrangement kind sent to the
     server ('Lead', 'Rhythm'…), localStorage key, gear key or user data.
   - `T` is a global: never declare a local `T` (`t` is the time variable —
     that is fine).
   - Never compare displayed text with Portuguese (`el.textContent === 'Pausa'`):
     compare state.
   - A Portuguese literal that is NOT shown (e.g. compared with Portuguese
     data) gets `// i18n-skip` on its line.
3. **Markup:** a sentence split by `<b>`/`<code>`/`<a>` is translated fragment by
   fragment, in the same order. Write it so each fragment translates on its own
   (or move the inline element). Get the exact keys with:
   `python3 -c "import sys,json; sys.path.insert(0,'tests'); import test_i18n as t; print(json.dumps(t.html_texts(), ensure_ascii=False, indent=1))"`
4. **Add the entry to EVERY `web/i18n-*.js`** (today `i18n-en.js`; list them
   with `ls web/i18n-*.js`):
   - The key must be byte-for-byte what `T()` receives (after JS unescaping),
     or the whitespace-collapsed page text.
   - Keep every `{placeholder}`, emoji, symbol and piece of markup.
   - Keep the file valid JSON: double quotes, no trailing comma.
   - When you change a Portuguese text, its key changes: replace the old
     entry in every dictionary, don't leave an orphan.
5. **Server text:**
   - Use `tr("<pt>", "<en>")`, with a keyword for every other language whose
     dictionary exists (`es=`, `fr=`…; English is the fallback).
   - A module-level constant is evaluated once, at import — build the message
     at call time (a function), or it is frozen in one language.
   - Messages the server always wrote in English only (older ones) may stay
     that way, but new ones use `tr`.
6. **Check:** run `python3 -m pytest -p no:warnings -o addopts="" -q tests/test_i18n.py`.
   - It fails on a missing entry in any language, a `${}` inside `T()`,
     placeholders that differ, or Portuguese left outside `T()`.
   - Then run `npm run lint` and `node --check web/app.js`.
   - For UI work, look at the page in each language (PT/EN picker on the
     home top bar; see `TESTING.md` §7c-octies).

## Glossary (keep terms consistent)

Partitura→Score · Pista→Track · Arranjo→Arrangement · Sincronização→Sync ·
Definições→Settings · Projeto→Project · Lote (álbum)→Batch (album) ·
Gravação→Recording · Letra→Lyrics · Tom/Tons→Tone/Tones · Capa→Cover ·
Exportar→Export · Aplicar e reconstruir→Apply and rebuild · Descarregar→Download ·
Carregar→Upload · Compasso→Bar · Andamento→Tempo · Secção→Section ·
Início da música→Song start · Corrigir daqui→Fix from here · Mover seguintes→Move
following · Encaixar em→Snap to · Pista principal→Main track · Silêncio
inicial→Intro silence · Mistura completa→Full mix · Testar tom→Preview tone ·
Fonte de áudio→Audio source · Braço→Fretboard · Pista 3D→3D highway ·
traste→fret · corda→string · acorde→chord · Pendente→Pending · ficheiro→file ·
Lead/Rhythm/Combo/Bass unchanged. For another language, follow the same
concepts (and Rocksmith's own terms in that language where they exist).

## Adding a new language

1. Create `web/i18n-<code>.js` (`es`, `fr`, `de`… — two/three lowercase
   letters). Copy `web/i18n-en.js`, change `.en =` to `.<code> =`, and
   translate every value from the PORTUGUESE key (not from the English).
   - Nothing else is needed on the web side: the server concatenates it into
     `/i18n-dicts.js`, and the pickers list it.
   - If `I18N_NAMES` in `web/i18n.js` lacks its own-language name, add it
     (e.g. `sv: 'Svenska'`).
2. `tests/test_i18n.py` picks the file up and demands full coverage.
3. Server messages: they read the English until a `<code>=` keyword is added
   to their `tr(...)`. Adding it everywhere is a separate, larger pass — say so
   rather than claiming the server is translated.
4. Update `CLAUDE.md` ("Languages") and the README's language note.
