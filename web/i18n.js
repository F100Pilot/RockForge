// RockForge speaks several languages. Portuguese is the original — written in
// the code and the markup — and every other language is ONE dictionary file,
// web/i18n-<code>.js, keyed by the Portuguese text:
//
//     (self.I18N_DICTS = self.I18N_DICTS || {}).en = { "Guardar": "Save", ... };
//
// The server concatenates every web/i18n-*.js into /i18n-dicts.js (loaded
// before this file), so adding a language is adding that file — the pickers
// list it by itself. See .claude/skills/rockforge-i18n/SKILL.md.
//
// - Script text goes through T('texto em português', {vars}) — the Portuguese
//   IS the key, so a string a dictionary lacks still shows, in Portuguese.
//   Placeholders are {name}: T('{n} notas', {n: 3}).
// - index.html is translated once at load by translateDom(): every text node
//   and the title/aria-label/placeholder/alt/data-name attributes whose text
//   (whitespace collapsed) is a key. `translate="no"` on an element skips it.
// - Every same-origin fetch carries X-RockForge-Lang, so the server answers in
//   the same language (rockforge/i18n.py).
// - Switching reloads the page: everything built at load (tables, menus) is
//   built again in the new language.
/* exported T, setLang */

const I18N_DICTS = self.I18N_DICTS || {};

// Each language's name in its own language, for the pickers (the long picker
// shows it; the top bar shows the code). A dictionary for a language missing
// here is still offered, under its code.
const I18N_NAMES = {
  pt: 'Português', en: 'English', es: 'Español', fr: 'Français', de: 'Deutsch',
  it: 'Italiano', nl: 'Nederlands', pl: 'Polski', ru: 'Русский', ja: '日本語', zh: '中文',
};

const I18N_LANGS = ['pt', ...Object.keys(I18N_DICTS).filter(c => c !== 'pt').sort()];

// The saved choice; else the first of the browser's languages we have; else
// English when it exists (the likelier second language of whoever reads this),
// else Portuguese.
const LANG = (() => {
  try {
    const saved = localStorage.getItem('rf-lang');
    if (I18N_LANGS.includes(saved)) return saved;
  } catch {}
  const wanted = (navigator.languages && navigator.languages.length ? navigator.languages : [navigator.language || ''])
    .map(l => String(l).toLowerCase().split('-')[0]);
  const hit = wanted.find(l => I18N_LANGS.includes(l));
  if (hit) return hit;
  return I18N_LANGS.includes('en') ? 'en' : 'pt';
})();

const I18N = LANG === 'pt' ? {} : (I18N_DICTS[LANG] || {});

function i18nKey(s) {
  return String(s).replace(/\s+/g, ' ').trim();
}

function T(pt, vars) {
  let s = pt;
  if (LANG !== 'pt') {
    const tr = I18N[pt] ?? I18N[i18nKey(pt)];
    if (typeof tr === 'string') s = tr;
  }
  if (vars) s = s.replace(/\{(\w+)\}/g, (m, k) => (k in vars ? String(vars[k]) : m));
  return s;
}

const I18N_ATTRS = ['title', 'aria-label', 'placeholder', 'alt', 'data-name'];

// Translate a text in place, keeping the whitespace around it (it separates
// inline elements in the markup).
function i18nText(raw) {
  const key = i18nKey(raw);
  if (!key) return null;
  const tr = I18N[key];
  if (typeof tr !== 'string') return null;
  const lead = raw.match(/^\s*/)[0];
  const trail = raw.match(/\s*$/)[0];
  return lead + tr + trail;
}

function translateDom(root) {
  if (LANG === 'pt' || !root) return;
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      if (node.nodeType === Node.ELEMENT_NODE) {
        const tag = node.tagName;
        if (tag === 'SCRIPT' || tag === 'STYLE' || tag === 'symbol') return NodeFilter.FILTER_REJECT;
        if (node.getAttribute('translate') === 'no') return NodeFilter.FILTER_REJECT;
      }
      return NodeFilter.FILTER_ACCEPT;
    },
  });
  for (let node = walker.currentNode; node; node = walker.nextNode()) {
    if (node.nodeType === Node.TEXT_NODE) {
      const tr = i18nText(node.nodeValue);
      if (tr !== null) node.nodeValue = tr;
      continue;
    }
    for (const attr of I18N_ATTRS) {
      const v = node.getAttribute(attr);
      if (v) {
        const tr = i18nText(v);
        if (tr !== null) node.setAttribute(attr, tr);
      }
    }
  }
}

function setLang(lang) {
  if (!I18N_LANGS.includes(lang) || lang === LANG) return;
  try { localStorage.setItem('rf-lang', lang); } catch {}
  // The server keeps it too, for what runs outside a request (the worker's
  // logs, the desktop window's close dialog). Reload either way.
  fetch('/ui-language', {
    method: 'PUT', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ lang }),
  }).catch(() => {}).finally(() => location.reload());
}

(() => {
  const nativeFetch = window.fetch.bind(window);
  window.fetch = (input, init) => {
    const url = typeof input === 'string' ? input : (input && input.url) || String(input);
    const abs = new URL(url, location.href);
    if (abs.origin !== location.origin) return nativeFetch(input, init);
    const headers = new Headers((init && init.headers) || (input instanceof Request ? input.headers : undefined));
    if (!headers.has('X-RockForge-Lang')) headers.set('X-RockForge-Lang', LANG);
    return nativeFetch(input, { ...(init || {}), headers });
  };
  document.documentElement.lang = LANG;
})();

// The language pickers (home top bar: codes; Definições: names). Filled from
// the dictionaries there are. A switch reloads the page, so pending edits in
// an open project would be lost: ask first.
function wireLangSelects() {
  for (const sel of document.querySelectorAll('select[data-lang-select]')) {
    const short = sel.dataset.langSelect === 'short';
    sel.replaceChildren(...I18N_LANGS.map(code => {
      const o = document.createElement('option');
      o.value = code;
      o.textContent = short ? code.toUpperCase() : (I18N_NAMES[code] || code.toUpperCase());
      return o;
    }));
    sel.value = LANG;
    sel.addEventListener('change', () => {
      const pending = document.getElementById('pendingChangesInfo');
      if (pending && pending.textContent.trim() && !confirm(T(
        'Há alterações por aplicar neste projeto e mudar de idioma recarrega a página — perdem-se. Mudar na mesma?',
      ))) { sel.value = LANG; return; }
      setLang(sel.value);
    });
  }
}

// index.html is parsed by the time this runs: the script sits at the end of
// <body>, before app.js, so app.js sees translated markup (e.g. the mode
// menu's data-name labels).
translateDom(document.body);
wireLangSelects();
