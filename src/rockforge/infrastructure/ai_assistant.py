"""Asking an AI for tones directly, instead of copying the request to a chatbot
and pasting its answer back.

The request and the reading are the ones the copy/paste path already uses
(``tone_plan.build_prompt`` / ``build_tone_prompt`` and ``read_plan`` /
``read_tones``): this module only carries the text to an assistant and its
answer back. Three ways in, chosen by the user in Definições → Tons e IA:

* **OpenRouter** — many models (free ones included) behind one account. The
  user either signs in (OAuth PKCE: the browser goes to openrouter.ai, which
  sends it back to this app's own ``…/openrouter/callback`` with a code that
  :func:`finish_openrouter_login` exchanges for a key tied to the user's
  account — OpenRouter supports a localhost callback on any port) or pastes a
  key. ``openrouter/free`` is OpenRouter's own router to a free model.
* **Gemini** — the user's Google AI Studio key (``x-goog-api-key``).
* **Ollama** — a model running on this computer; free and offline, and the
  smaller models get more of the settings wrong (the reader still checks every
  value against the game's gear and says what it changed).

Facts from the providers' own documentation, read 2026-11-09: OpenRouter's
OAuth PKCE guide and OpenAPI (``/auth``, ``/api/v1/auth/keys`` → ``key``,
``/api/v1/models`` with ``pricing.prompt``/``completion`` in USD per token as
strings, ``/api/v1/chat/completions`` → ``choices[0].message.content``);
Google's Gemini API reference (``POST /v1beta/models/{model}:generateContent``
→ ``candidates[].content.parts[].text``, ``GET /v1beta/models`` with
``supportedGenerationMethods``); Ollama's API doc (``POST /api/chat`` with
``stream: false`` → ``message.content``, ``GET /api/tags``). None of it was run
against the live services from where this was written (no keys there); the
tests drive every request against recorded-shape fakes.

The keys live in ``work_dir/ai_assistant.json`` on this computer, are never
sent back to the page (only whether one is stored), and are taken out of the
logs (``app_logging``). Nothing is asked of any of these services until the
user presses a button.
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rockforge import __version__, config
from rockforge._atomic import write_text_atomic
from rockforge.i18n import tr
from rockforge.infrastructure._https import network_error_message, ssl_context

PROVIDERS = ("openrouter", "gemini", "ollama")
KEY_PROVIDERS = ("openrouter", "gemini")
OPENROUTER_API = "https://openrouter.ai/api/v1"
OPENROUTER_AUTH = "https://openrouter.ai/auth"
OPENROUTER_FREE = "openrouter/free"
GEMINI_API = "https://generativelanguage.googleapis.com/v1beta"
OLLAMA_DEFAULT = "http://localhost:11434"
OLLAMA_HOSTS = ("localhost", "127.0.0.1", "::1", "host.docker.internal")

ASK_TIMEOUT_S = 240.0
LIST_TIMEOUT_S = 20.0
MAX_READ = 8_000_000          # a model list is ~1 MB; an answer far less
MAX_ANSWER = 200_000
MAX_KEY = 400
MAX_MODEL = 200
LOGIN_TTL_S = 15 * 60
OLLAMA_CONTEXT = 16384        # Ollama's default context would cut the request short
TEMPERATURE = 0.3
_USER_AGENT = f"RockForge/{__version__}"

_lock = threading.Lock()
_logins: dict[str, tuple[str, float]] = {}   # state -> (code_verifier, started)


class AiError(Exception):
    """A request the assistant did not answer, in words for the user."""

    def __init__(self, message: str, status: int = 502) -> None:
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class Answer:
    text: str
    provider: str
    model: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


def _label(provider: str) -> str:
    return {"openrouter": "OpenRouter", "gemini": "Gemini", "ollama": "Ollama"}.get(
        provider, provider)


# --- what is stored -----------------------------------------------------------

def _file() -> Path:
    return config.settings.work_dir / "ai_assistant.json"


def _load() -> dict[str, Any]:
    try:
        data = json.loads(_file().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(state: dict[str, Any]) -> None:
    write_text_atomic(_file(), json.dumps(state, indent=2))


def _keys(state: dict[str, Any]) -> dict[str, str]:
    raw = state.get("keys")
    return {p: v for p, v in (raw.items() if isinstance(raw, dict) else [])
            if p in KEY_PROVIDERS and isinstance(v, str) and v}


def _models(state: dict[str, Any]) -> dict[str, str]:
    raw = state.get("models")
    return {p: v for p, v in (raw.items() if isinstance(raw, dict) else [])
            if p in PROVIDERS and isinstance(v, str) and v}


_keys_seen: tuple[tuple[str, int], list[str]] | None = None


def stored_keys() -> list[str]:
    """Every key stored, for the log redaction (read again only when the file
    changed: this runs for every log line)."""
    global _keys_seen
    path = _file()
    try:
        stamp = (str(path), path.stat().st_mtime_ns)
    except OSError:
        return []
    if _keys_seen is None or _keys_seen[0] != stamp:
        _keys_seen = (stamp, list(_keys(_load()).values()))
    return list(_keys_seen[1])


def clean_ollama_url(raw: object) -> str:
    """An Ollama address on this computer (or the Docker host), or ValueError.
    Only a local address: the setting must not turn the server into a way to
    reach other machines."""
    text = str(raw or "").strip().rstrip("/")
    if not text:
        return OLLAMA_DEFAULT
    parts = urllib.parse.urlsplit(text)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError(tr("o endereço do Ollama tem de começar por http:// ou https://",
                            "the Ollama address must start with http:// or https://"))
    if parts.hostname.lower() not in OLLAMA_HOSTS:
        raise ValueError(tr("o Ollama tem de estar neste computador (localhost ou 127.0.0.1)",
                            "Ollama has to be on this computer (localhost or 127.0.0.1)"))
    if parts.username or parts.password or parts.query or parts.fragment or parts.path not in (
            "", "/"):
        raise ValueError(tr("o endereço do Ollama é só o servidor, ex.: http://localhost:11434",
                            "the Ollama address is the server only, e.g. http://localhost:11434"))
    try:
        port = parts.port
    except ValueError as exc:
        raise ValueError(tr("porta inválida no endereço do Ollama",
                            "invalid port in the Ollama address")) from exc
    host = f"[{parts.hostname}]" if ":" in parts.hostname else parts.hostname
    return f"{parts.scheme}://{host}" + (f":{port}" if port else "")


def public_state() -> dict[str, Any]:
    """What the page may know: the choice and whether each key is stored —
    never a key."""
    state = _load()
    provider = state.get("provider")
    provider = provider if provider in PROVIDERS else ""
    keys = _keys(state)
    url = state.get("ollama_url")
    models = _models(state)
    if provider == "openrouter":
        models.setdefault("openrouter", OPENROUTER_FREE)
    ready = bool(provider) and (provider == "ollama" or provider in keys) and bool(
        models.get(provider) or provider == "openrouter")
    return {
        "provider": provider,
        "models": models,
        "has_key": {p: p in keys for p in KEY_PROVIDERS},
        "ollama_url": url if isinstance(url, str) and url else OLLAMA_DEFAULT,
        "ready": ready,
    }


def update(*, provider: str | None = None, model: tuple[str, str] | None = None,
           key: tuple[str, str] | None = None, forget_key: str | None = None,
           ollama_url: str | None = None) -> dict[str, Any]:
    """Change what is stored (each argument left None stays as it is)."""
    with _lock:
        state = _load()
        if provider is not None:
            if provider not in PROVIDERS and provider != "":
                raise ValueError(tr("assistente desconhecido", "unknown assistant"))
            state["provider"] = provider
        if model is not None:
            prov, name = model
            if prov not in PROVIDERS:
                raise ValueError(tr("assistente desconhecido", "unknown assistant"))
            name = name.strip()
            if len(name) > MAX_MODEL or any(c.isspace() for c in name):
                raise ValueError(tr("nome de modelo inválido", "invalid model name"))
            models = _models(state)
            if name:
                models[prov] = name
            else:
                models.pop(prov, None)
            state["models"] = models
        if key is not None:
            prov, value = key
            value = value.strip()
            if prov not in KEY_PROVIDERS:
                raise ValueError(tr("esse assistente não usa chave",
                                    "that assistant takes no key"))
            if not value or len(value) > MAX_KEY or any(c.isspace() for c in value):
                raise ValueError(tr("a chave não parece uma chave",
                                    "that does not look like a key"))
            keys = _keys(state)
            keys[prov] = value
            state["keys"] = keys
        if forget_key is not None:
            keys = _keys(state)
            keys.pop(forget_key, None)
            state["keys"] = keys
        if ollama_url is not None:
            state["ollama_url"] = clean_ollama_url(ollama_url)
        _save(state)
    return public_state()


# --- talking to them ------------------------------------------------------------

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


def _opener(https: bool) -> urllib.request.OpenerDirector:
    handlers: list[urllib.request.BaseHandler] = [_NoRedirect()]
    if https:
        handlers.append(urllib.request.HTTPSHandler(context=ssl_context()))
    return urllib.request.build_opener(*handlers)


def _error_text(body: bytes) -> str:
    try:
        data = json.loads(body.decode("utf-8", "replace"))
    except ValueError:
        return ""
    err = data.get("error") if isinstance(data, dict) else None
    if isinstance(err, dict):
        return str(err.get("message") or "")[:300]
    if isinstance(err, str):
        return err[:300]
    return ""


def _http_error(exc: urllib.error.HTTPError, provider: str, model: str) -> AiError:
    try:
        detail = _error_text(exc.read(64_000))
    except OSError:
        detail = ""
    name = _label(provider)
    tail = f" ({detail})" if detail else ""
    if exc.code in (401, 403):
        return AiError(tr(f"o {name} não aceitou a chave — confirma-a nas Definições{tail}",
                          f"{name} did not accept the key — check it in Settings{tail}"), 401)
    if exc.code == 402:
        return AiError(tr(f"a conta do {name} não tem créditos para este modelo — escolhe um "
                          f"modelo grátis{tail}",
                          f"the {name} account has no credits for this model — pick a free "
                          f"model{tail}"), 402)
    if exc.code == 404:
        return AiError(tr(f"o {name} não conhece o modelo «{model}» — escolhe outro{tail}",
                          f"{name} does not know the model “{model}” — pick another{tail}"), 404)
    if exc.code == 429:
        return AiError(tr(f"limite de pedidos do {name} atingido — espera um pouco ou escolhe "
                          f"outro modelo{tail}",
                          f"{name}'s request limit was reached — wait a little or pick another "
                          f"model{tail}"), 429)
    return AiError(tr(f"o {name} respondeu {exc.code}{tail}",
                      f"{name} answered {exc.code}{tail}"))


def _request(method: str, url: str, *, provider: str, model: str = "",
             headers: dict[str, str] | None = None, body: dict[str, Any] | None = None,
             timeout: float = LIST_TIMEOUT_S) -> Any:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "User-Agent": _USER_AGENT, "Accept": "application/json",
        **({"Content-Type": "application/json"} if data is not None else {}),
        **(headers or {}),
    })
    try:
        with _opener(url.startswith("https:")).open(req, timeout=timeout) as resp:
            raw = resp.read(MAX_READ + 1)
    except urllib.error.HTTPError as exc:
        if 300 <= exc.code < 400:
            raise AiError(tr(f"o {_label(provider)} mandou o pedido para outro sítio — não "
                             "foi seguido",
                             f"{_label(provider)} sent the request elsewhere — not "
                             "followed")) from exc
        raise _http_error(exc, provider, model) from exc
    except TimeoutError as exc:
        raise AiError(tr(f"o {_label(provider)} não respondeu em {timeout:g} s",
                         f"{_label(provider)} did not answer within {timeout:g} s"), 504) from exc
    except urllib.error.URLError as exc:
        if provider == "ollama":
            raise AiError(tr(f"o Ollama não está a responder em {url.split('/api')[0]} — abre-o "
                             "e confirma o endereço nas Definições",
                             f"Ollama is not answering at {url.split('/api')[0]} — open it and "
                             "check the address in Settings")) from exc
        raise AiError(network_error_message(exc, _label(provider))) from exc
    except OSError as exc:
        raise AiError(network_error_message(exc, _label(provider))) from exc
    if len(raw) > MAX_READ:
        raise AiError(tr(f"a resposta do {_label(provider)} é demasiado grande",
                         f"{_label(provider)}'s answer is too large"))
    try:
        return json.loads(raw.decode("utf-8", "replace"))
    except ValueError as exc:
        raise AiError(tr(f"o {_label(provider)} respondeu algo que não é JSON",
                         f"{_label(provider)} answered something that is not JSON")) from exc


def _price(value: object) -> float | None:
    try:
        price = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return price if price >= 0 and price == price else None


def list_models(provider: str) -> list[dict[str, Any]]:
    """The models a provider offers: ``id``, ``name``, ``free`` (True / False /
    None when the provider does not say), the price per token in USD
    (``prompt_price``/``completion_price``, None when not known), ``context``."""
    state = _load()
    if provider == "openrouter":
        data = _request("GET", f"{OPENROUTER_API}/models", provider=provider)
        rows = data.get("data") if isinstance(data, dict) else None
        out = [{"id": OPENROUTER_FREE, "name": tr("Modelo grátis (o OpenRouter escolhe)",
                                                  "Free model (OpenRouter picks it)"),
                "free": True, "prompt_price": 0.0, "completion_price": 0.0, "context": None}]
        for m in rows if isinstance(rows, list) else []:
            if not isinstance(m, dict) or not isinstance(m.get("id"), str):
                continue
            pricing = _obj(m.get("pricing"))
            pp, cp = _price(pricing.get("prompt")), _price(pricing.get("completion"))
            ctx = m.get("context_length")
            out.append({
                "id": m["id"], "name": str(m.get("name") or m["id"])[:120],
                "free": pp == 0 and cp == 0 if pp is not None and cp is not None else None,
                "prompt_price": pp, "completion_price": cp,
                "context": ctx if isinstance(ctx, int) else None,
            })
        return out
    if provider == "gemini":
        key = _keys(state).get("gemini")
        if not key:
            raise AiError(tr("guarda primeiro a chave do Gemini", "store the Gemini key first"),
                          401)
        data = _request("GET", f"{GEMINI_API}/models?pageSize=1000", provider=provider,
                        headers={"x-goog-api-key": key})
        rows = data.get("models") if isinstance(data, dict) else None
        out = []
        for m in rows if isinstance(rows, list) else []:
            if not isinstance(m, dict) or "generateContent" not in (
                    m.get("supportedGenerationMethods") or []):
                continue
            name = str(m.get("name") or "")
            mid = name.removeprefix("models/")
            if not mid:
                continue
            limit = m.get("inputTokenLimit")
            out.append({"id": mid, "name": str(m.get("displayName") or mid)[:120], "free": None,
                        "prompt_price": None, "completion_price": None,
                        "context": limit if isinstance(limit, int) else None})
        return out
    if provider == "ollama":
        base = public_state()["ollama_url"]
        data = _request("GET", f"{base}/api/tags", provider=provider)
        rows = data.get("models") if isinstance(data, dict) else None
        return [{"id": m["name"], "name": m["name"], "free": True, "prompt_price": 0.0,
                 "completion_price": 0.0, "context": None}
                for m in rows if isinstance(m, dict) and isinstance(m.get("name"), str)
                ] if isinstance(rows, list) else []
    raise AiError(tr("assistente desconhecido", "unknown assistant"), 422)


def _obj(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _first(value: object) -> object:
    return value[0] if isinstance(value, list) and value else None


def _int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def ask(prompt: str, *, provider: str | None = None, model: str | None = None) -> Answer:
    """``prompt`` to the chosen assistant; its text answer. AiError, in words,
    for anything that stops it."""
    state = _load()
    pub = public_state()
    prov = provider or pub["provider"]
    if prov not in PROVIDERS:
        raise AiError(tr("escolhe um assistente de IA nas Definições → Tons e IA",
                         "choose an AI assistant in Settings → Tones and AI"), 409)
    name = (model or pub["models"].get(prov) or "").strip()
    if not name:
        raise AiError(tr(f"escolhe um modelo do {_label(prov)} nas Definições → Tons e IA",
                         f"choose a {_label(prov)} model in Settings → Tones and AI"), 409)
    keys = _keys(state)
    if prov in KEY_PROVIDERS and prov not in keys:
        raise AiError(tr(f"liga primeiro o {_label(prov)} nas Definições → Tons e IA",
                         f"connect {_label(prov)} first in Settings → Tones and AI"), 409)
    if prov == "openrouter":
        data = _request("POST", f"{OPENROUTER_API}/chat/completions", provider=prov, model=name,
                        timeout=ASK_TIMEOUT_S,
                        headers={"Authorization": f"Bearer {keys['openrouter']}"},
                        body={"model": name, "temperature": TEMPERATURE,
                              "messages": [{"role": "user", "content": prompt}]})
        top = _obj(data)
        if isinstance(top.get("error"), dict):
            msg = str(top["error"].get("message") or "")[:300]
            raise AiError(tr(f"o OpenRouter não respondeu: {msg}",
                             f"OpenRouter did not answer: {msg}"))
        text = _obj(_obj(_first(top.get("choices"))).get("message")).get("content")
        usage = _obj(top.get("usage"))
        return _answer(text, prov, str(top.get("model") or name),
                       _int(usage.get("prompt_tokens")), _int(usage.get("completion_tokens")))
    if prov == "gemini":
        model_id = urllib.parse.quote(name.removeprefix("models/"), safe="-._")
        data = _request("POST", f"{GEMINI_API}/models/{model_id}:generateContent",
                        provider=prov, model=name, timeout=ASK_TIMEOUT_S,
                        headers={"x-goog-api-key": keys["gemini"]},
                        body={"contents": [{"role": "user", "parts": [{"text": prompt}]}],
                              "generationConfig": {"temperature": TEMPERATURE,
                                                   "responseMimeType": "application/json"}})
        top = _obj(data)
        fb = _obj(top.get("promptFeedback"))
        if fb.get("blockReason"):
            raise AiError(tr(f"o Gemini recusou o pedido ({fb['blockReason']})",
                             f"Gemini refused the request ({fb['blockReason']})"))
        parts = _obj(_obj(_first(top.get("candidates"))).get("content")).get("parts")
        text = "".join(str(p.get("text") or "") for p in parts
                       if isinstance(p, dict) and not p.get("thought")) if isinstance(
            parts, list) else None
        usage = _obj(top.get("usageMetadata"))
        return _answer(text, prov, name, _int(usage.get("promptTokenCount")),
                       _int(usage.get("candidatesTokenCount")))
    base = pub["ollama_url"]
    data = _request("POST", f"{base}/api/chat", provider=prov, model=name,
                    timeout=ASK_TIMEOUT_S,
                    body={"model": name, "stream": False, "format": "json",
                          "messages": [{"role": "user", "content": prompt}],
                          "options": {"temperature": TEMPERATURE, "num_ctx": OLLAMA_CONTEXT}})
    top = _obj(data)
    return _answer(_obj(top.get("message")).get("content"), prov, name,
                   _int(top.get("prompt_eval_count")), _int(top.get("eval_count")))


def _answer(text: object, provider: str, model: str, pt: int | None, ct: int | None) -> Answer:
    if not isinstance(text, str) or not text.strip():
        raise AiError(tr(f"o {_label(provider)} não devolveu texto — tenta outra vez ou outro "
                         "modelo",
                         f"{_label(provider)} returned no text — try again or another model"))
    return Answer(text=text[:MAX_ANSWER], provider=provider, model=model,
                  prompt_tokens=pt, completion_tokens=ct)


# --- signing in to OpenRouter (OAuth PKCE) ----------------------------------------

def _challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def start_openrouter_login(callback_url: str) -> str:
    """The openrouter.ai address to open in the browser. The verifier stays here
    until the callback comes back with the same ``state``."""
    verifier = secrets.token_urlsafe(64)
    state = secrets.token_urlsafe(24)
    now = time.monotonic()
    with _lock:
        for s, (_, t) in list(_logins.items()):
            if now - t > LOGIN_TTL_S:
                _logins.pop(s, None)
        _logins[state] = (verifier, now)
    query = urllib.parse.urlencode({
        "callback_url": callback_url, "code_challenge": _challenge(verifier),
        "code_challenge_method": "S256", "state": state, "key_label": "RockForge",
    })
    return f"{OPENROUTER_AUTH}?{query}"


def finish_openrouter_login(code: str, state: str) -> None:
    """Exchange the code the callback brought for the user's key, store it and
    make OpenRouter the assistant. AiError when the state is not one this app
    started (or it expired) or the exchange fails."""
    with _lock:
        pending = _logins.pop(state, None)
    if pending is None or time.monotonic() - pending[1] > LOGIN_TTL_S:
        raise AiError(tr("esta ligação ao OpenRouter não foi pedida por este RockForge, ou "
                         "expirou — carrega outra vez em «Entrar com o OpenRouter»",
                         "this OpenRouter sign-in was not started by this RockForge, or it "
                         "expired — press “Sign in with OpenRouter” again"), 400)
    if not code or len(code) > 2000:
        raise AiError(tr("o OpenRouter não devolveu o código", "OpenRouter returned no code"),
                      400)
    data = _request("POST", f"{OPENROUTER_API}/auth/keys", provider="openrouter",
                    body={"code": code, "code_verifier": pending[0],
                          "code_challenge_method": "S256"})
    key = data.get("key") if isinstance(data, dict) else None
    if not isinstance(key, str) or not key:
        raise AiError(tr("o OpenRouter não devolveu a chave", "OpenRouter returned no key"))
    update(provider="openrouter", key=("openrouter", key))
