// RockForge's two languages: Portuguese (the original, written in the code and
// the markup) and English (web/i18n-en.js, keyed by the Portuguese text).
//
// - Script text goes through T('texto em português', {vars}) — the Portuguese
//   IS the key, so a string with no English entry still shows, in Portuguese.
//   Placeholders are {name}: T('{n} notas', {n: 3}).
// - index.html is translated once at load by translateDom(): every text node
//   and the title/aria-label/placeholder/alt/data-name attributes whose text
//   (whitespace collapsed) is a key. `translate="no"` on an element skips it.
// - Every same-origin fetch carries X-RockForge-Lang, so the server answers in
//   the same language (rockforge/i18n.py).
// - Switching reloads the page: everything built at load (tables, menus) is
//   built again in the new language.
/* global I18N_EN */
/* exported T, setLang */

const I18N_LANGS = ['pt', 'en'];

const LANG = (() => {
  try {
    const saved = localStorage.getItem('rf-lang');
    if (I18N_LANGS.includes(saved)) return saved;
  } catch {}
  return String(navigator.language || 'pt').toLowerCase().startsWith('pt') ? 'pt' : 'en';
})();

function i18nKey(s) {
  return String(s).replace(/\s+/g, ' ').trim();
}

function T(pt, vars) {
  let s = pt;
  if (LANG === 'en') {
    const en = I18N_EN[pt] ?? I18N_EN[i18nKey(pt)];
    if (typeof en === 'string') s = en;
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
  const en = I18N_EN[key];
  if (typeof en !== 'string') return null;
  const lead = raw.match(/^\s*/)[0];
  const trail = raw.match(/\s*$/)[0];
  return lead + en + trail;
}

function translateDom(root) {
  if (LANG !== 'en' || !root) return;
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
      const en = i18nText(node.nodeValue);
      if (en !== null) node.nodeValue = en;
      continue;
    }
    for (const attr of I18N_ATTRS) {
      const v = node.getAttribute(attr);
      if (v) {
        const en = i18nText(v);
        if (en !== null) node.setAttribute(attr, en);
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

// The language pickers (home top bar, Definições). A switch reloads the page,
// so pending edits in an open project would be lost: ask first.
function wireLangSelects() {
  for (const sel of document.querySelectorAll('select[data-lang-select]')) {
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

// index.html is parsed by the time this runs only if the script sits at the
// end of <body>, which it does (before app.js, so app.js sees translated
// markup — e.g. the mode menu's data-name labels).
translateDom(document.body);
wireLangSelects();
