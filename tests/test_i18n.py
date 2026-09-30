"""Português / English: every text the UI shows has an English entry.

The web UI is written in Portuguese and translated by ``web/i18n.js`` with
``web/i18n-en.js`` (English keyed by the Portuguese). Two ways in:

- index.html: every text node and title/aria-label/placeholder/alt/data-name
  attribute with a letter in it, whitespace collapsed (what ``translateDom``
  looks up). ``translate="no"`` skips an element.
- app.js / highway3d.js: every ``T('...')`` call's literal.

A missing entry does not break anything (the Portuguese shows), which is
exactly why it has to be caught here: nobody would notice. The scripts are also
scanned for Portuguese left OUTSIDE ``T()`` — a string with a Portuguese accent,
or an unaccented Portuguese UI word, that the English UI would show untranslated.
"""

from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

WEB = Path(__file__).resolve().parents[1] / "web"
SCRIPTS = ("app.js", "highway3d.js", "i18n.js")
ATTRS = ("title", "aria-label", "placeholder", "alt", "data-name")
_LETTER = re.compile(r"[A-Za-zÀ-ÿ]")
_PT_ACCENT = re.compile(r"[ãõçáéíóúâêôàÃÕÇÁÉÍÓÚÂÊÔÀ]")
# Portuguese UI words that carry no accent — the accent check alone would let
# "Guardar" or "Remover nota" through.
_PT_WORDS = re.compile(
    r"(?<![.\w-])(?:guardar|remover|apagar|pendente|nenhum|nenhuma|carregar|escolhe|escolher|"
    r"cancelar|fechar|limpar|aplicar|desfazer|copiar|colar|pista|pistas|nota|notas|letra|"
    r"ficheiro|compasso|compassos|tons|sem|para|com|uma|um|os|as|ao|dos|das|nos|nas|"
    r"do|da|de|em|no|na|ou|mais|menos|isto|esta|este|ainda|depois|antes|agora|sim)\b",
    re.I,
)


def key(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def dictionary() -> dict[str, str]:
    src = (WEB / "i18n-en.js").read_text(encoding="utf-8")
    body = src[src.index("= {") + 2 : src.rindex("}") + 1]
    data = json.loads(body)
    assert isinstance(data, dict)
    return data


class _Html(HTMLParser):
    _SKIP = {"script", "style", "symbol"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.texts: list[str] = []
        self._skip_depth = 0
        self._stack: list[bool] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        skip = tag in self._SKIP or a.get("translate") == "no"
        if tag not in _VOID:
            self._stack.append(skip)
            if skip:
                self._skip_depth += 1
        if self._skip_depth or skip:
            return
        for name in ATTRS:
            if a.get(name):
                self.texts.append(key(a[name] or ""))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        if self._skip_depth or tag in self._SKIP or a.get("translate") == "no":
            return
        for name in ATTRS:
            if a.get(name):
                self.texts.append(key(a[name] or ""))

    def handle_endtag(self, tag: str) -> None:
        if tag in _VOID or not self._stack:
            return
        if self._stack.pop():
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip_depth and key(data):
            self.texts.append(key(data))


_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
         "source", "track", "wbr", "use", "path", "circle", "rect", "line", "polyline",
         "polygon", "ellipse"}


def html_texts() -> list[str]:
    p = _Html()
    p.feed((WEB / "index.html").read_text(encoding="utf-8"))
    return [s for s in dict.fromkeys(p.texts) if _LETTER.search(s)]


# --- a small JS lexer: string literals, with the code just before each -----

def _unescape(body: str) -> str:
    def sub(m: re.Match[str]) -> str:
        c = m.group(1)
        if c.startswith("u"):
            return chr(int(c[1:].strip("{}"), 16))
        return {"n": "\n", "t": "\t", "r": "\r"}.get(c, c)

    return re.sub(r"\\(u\{[0-9a-fA-F]+\}|u[0-9a-fA-F]{4}|.)", sub, body, flags=re.S)


def js_strings(src: str) -> list[tuple[int, str, str, bool]]:
    """``(line, text, code_before, is_template_with_expr)`` for every string
    literal (a template's static parts are joined by ``${…}``)."""
    out: list[tuple[int, str, str, bool]] = []
    i, n = 0, len(src)
    last_sig = ""  # last significant (non-space) char of code, to tell / regex from divide

    def before(pos: int) -> str:
        return src[max(0, pos - 40) : pos]

    def read_template(i: int) -> tuple[int, str, bool]:
        parts, buf, has_expr = [], [], False
        i += 1
        while i < n:
            c = src[i]
            if c == "\\":
                buf.append(src[i : i + 2])
                i += 2
            elif c == "`":
                parts.append("".join(buf))
                return i + 1, "${…}".join(parts), has_expr
            elif c == "$" and src[i + 1 : i + 2] == "{":
                has_expr = True
                parts.append("".join(buf))
                buf = []
                i = skip_code(i + 2, "}")
            else:
                buf.append(c)
                i += 1
        return i, "${…}".join(parts), has_expr

    def skip_code(i: int, until: str) -> int:
        depth = 0
        while i < n:
            c = src[i]
            if c in "'\"":
                i = read_quoted(i)[0]
            elif c == "`":
                start = i
                i, text, has_expr = read_template(i)
                out.append((src.count("\n", 0, start) + 1, _unescape(text), before(start), has_expr))
            elif c == "{":
                depth += 1
                i += 1
            elif c == "}":
                if depth == 0 and until == "}":
                    return i + 1
                depth -= 1
                i += 1
            else:
                i += 1
        return i

    def read_quoted(i: int) -> tuple[int, str]:
        q = src[i]
        j = i + 1
        while j < n and src[j] != q and src[j] != "\n":
            j += 2 if src[j] == "\\" else 1
        return j + 1, src[i + 1 : j]

    while i < n:
        c = src[i]
        if src.startswith("//", i):
            i = src.find("\n", i)
            i = n if i < 0 else i
        elif src.startswith("/*", i):
            i = src.find("*/", i + 2) + 2
        elif c == "/" and last_sig and last_sig in "(,=:[!&|?{};+-*%<>~^":
            # a regex literal: skip it, classes included
            j, in_class = i + 1, False
            while j < n and src[j] != "\n":
                if src[j] == "\\":
                    j += 2
                    continue
                if src[j] == "[":
                    in_class = True
                elif src[j] == "]":
                    in_class = False
                elif src[j] == "/" and not in_class:
                    break
                j += 1
            i = j + 1
            last_sig = "/"
        elif c in "'\"":
            start = i
            i, body = read_quoted(i)
            out.append((src.count("\n", 0, start) + 1, _unescape(body), before(start), False))
            last_sig = "a"
        elif c == "`":
            start = i
            i, text, has_expr = read_template(i)
            out.append((src.count("\n", 0, start) + 1, _unescape(text), before(start), has_expr))
            last_sig = "a"
        else:
            if not c.isspace():
                last_sig = c
            i += 1
    return out


def _is_t_arg(code_before: str) -> bool:
    return re.search(r"(?<![\w.$])T\(\s*$", code_before) is not None


def t_keys() -> list[tuple[str, int, str, bool]]:
    keys = []
    for name in SCRIPTS:
        for line, text, code, has_expr in js_strings((WEB / name).read_text(encoding="utf-8")):
            if _is_t_arg(code):
                keys.append((name, line, text, has_expr))
    return keys


def test_the_dictionary_is_plain_json_with_english_text() -> None:
    d = dictionary()
    assert d, "web/i18n-en.js has no entries"
    bad = [k for k, v in d.items() if not isinstance(v, str) or not v.strip()]
    assert not bad, f"empty English for: {bad[:10]}"


def test_every_text_in_the_page_has_an_english_entry() -> None:
    d = dictionary()
    missing = [s for s in html_texts() if s not in d]
    assert not missing, f"{len(missing)} index.html texts with no English: {missing[:20]}"


def test_every_translated_script_string_has_an_english_entry() -> None:
    d = dictionary()
    keys = t_keys()
    assert keys, "no T('...') calls found"
    dynamic = [(f, ln) for f, ln, _s, has_expr in keys if has_expr]
    assert not dynamic, f"T() takes a fixed text with {{placeholders}}, not ${{…}}: {dynamic[:10]}"
    missing = [(f, ln, s) for f, ln, s, _e in keys if s not in d and key(s) not in d]
    assert not missing, f"{len(missing)} T() texts with no English: {missing[:15]}"


def test_placeholders_survive_translation() -> None:
    """``{n}`` in the Portuguese must be in the English too, or the value is lost."""
    bad = []
    for pt, en in dictionary().items():
        if set(re.findall(r"\{(\w+)\}", pt)) != set(re.findall(r"\{(\w+)\}", en)):
            bad.append(pt)
    assert not bad, f"placeholders differ: {bad[:10]}"


def _looks_portuguese(text: str) -> bool:
    visible = re.sub(r"<[^>]*>|\$\{…\}|&\w+;", " ", text)
    if not _LETTER.search(visible):
        return False
    if _PT_ACCENT.search(visible):
        return True
    words = re.findall(r"[A-Za-zÀ-ÿ]+", visible)
    return len(words) >= 2 and _PT_WORDS.search(visible) is not None


@pytest.mark.parametrize("name", ["app.js", "highway3d.js"])
def test_no_portuguese_is_left_outside_T(name: str) -> None:
    """A Portuguese string that does not go through ``T()`` stays Portuguese in
    the English UI. A string that is not shown to the user (a comparison with
    Portuguese data, say) is marked on its line with ``// i18n-skip``."""
    src = (WEB / name).read_text(encoding="utf-8")
    lines = src.splitlines()
    left = []
    for line, text, code, _e in js_strings(src):
        if _is_t_arg(code) or "i18n-skip" in lines[line - 1]:
            continue
        if _looks_portuguese(text):
            left.append((line, text[:70]))
    assert not left, f"{len(left)} Portuguese strings outside T() in {name}: {left[:15]}"
