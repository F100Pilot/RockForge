"""The app's two languages (Portuguese, the original, and English) for text the
SERVER writes: error details, diagnostics, task logs.

Each message is written once where it is produced, in both languages —
``tr("não encontrado", "not found")`` — so the two cannot drift apart and no
lookup table has to be kept in step with the code. The language is the one the
browser sent with the request (``X-RockForge-Lang``, set per request by the API
middleware); outside a request (the worker, the desktop window) it is the one
saved in the settings. The web UI translates its own text (``web/i18n.js``).
"""

from __future__ import annotations

from contextvars import ContextVar, Token

LANGUAGES = ("pt", "en")

_request_lang: ContextVar[str | None] = ContextVar("rockforge_ui_lang", default=None)


def use(lang: str | None) -> Token[str | None]:
    """Set the language for the current context (a request); an unknown value
    falls back to the saved setting. Returns the token to reset it with."""
    return _request_lang.set(lang if lang in LANGUAGES else None)


def reset(token: Token[str | None]) -> None:
    _request_lang.reset(token)


def current() -> str:
    lang = _request_lang.get()
    if lang:
        return lang
    from rockforge import runtime_settings

    return runtime_settings.ui_language()


def tr(pt: str, en: str) -> str:
    """``pt`` or ``en``, whichever the user reads."""
    return en if current() == "en" else pt
