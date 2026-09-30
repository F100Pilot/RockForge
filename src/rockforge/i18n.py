"""The app's languages for text the SERVER writes: error details, diagnostics,
task logs. Portuguese is the original; English is always there; any other
language the UI has (``web/i18n-<code>.js``) may be given too.

Each message is written once where it is produced, in its languages —
``tr("não encontrado", "not found")``, ``tr(pt, en, es="no encontrado")`` — so
they cannot drift apart and no lookup table has to be kept in step with the
code. A language a message was not written in reads the English (the likelier
second language than Portuguese). The language is the one the browser sent
with the request (``X-RockForge-Lang``, set per request by the API); outside a
request (the worker, the desktop window) it is the one saved in the settings.
See ``.claude/skills/rockforge-i18n/SKILL.md``.
"""

from __future__ import annotations

import re
from contextvars import ContextVar, Token

DEFAULT = "pt"
_CODE = re.compile(r"[a-z]{2,3}")

_request_lang: ContextVar[str | None] = ContextVar("rockforge_ui_lang", default=None)


def valid(lang: object) -> bool:
    """A language code as the UI sends it ("pt", "en", "es"…)."""
    return isinstance(lang, str) and _CODE.fullmatch(lang) is not None


def use(lang: str | None) -> Token[str | None]:
    """Set the language for the current context (a request); a malformed value
    falls back to the saved setting. Returns the token to reset it with."""
    return _request_lang.set(lang if valid(lang) else None)


def reset(token: Token[str | None]) -> None:
    _request_lang.reset(token)


def current() -> str:
    lang = _request_lang.get()
    if lang:
        return lang
    from rockforge import runtime_settings

    return runtime_settings.ui_language()


def tr(pt: str, en: str, **other: str) -> str:
    """The message in the language the user reads: ``pt``, ``en``, or one of
    ``other`` by code — English for a language it was not written in."""
    lang = current()
    if lang == "pt":
        return pt
    return other.get(lang, en)
