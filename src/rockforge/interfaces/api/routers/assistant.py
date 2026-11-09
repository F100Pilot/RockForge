"""The player's instrument and the AI assistant: the guitar profile, which AI
answers the tone requests (and its keys, which never come back to the page),
and one tone asked from a few words. The song's tone plan asked of the AI is
in ``tones`` beside the pasted one."""

from __future__ import annotations

import html
import urllib.parse
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse

from rockforge import i18n
from rockforge.interfaces.api.schemas import (
    AiAssistantIn,
    AiAssistantOut,
    AiModelOut,
    GuitarProfileIn,
    ToneDescribeIn,
    ToneTextIn,
    ToneTextOut,
)

router = APIRouter()

CALLBACK_PATH = "/ai-assistant/openrouter/callback"


@router.get("/guitar-profile")
def get_guitar_profile() -> dict[str, Any]:
    from rockforge.infrastructure import guitar_profile

    return guitar_profile.load()


@router.put("/guitar-profile")
def set_guitar_profile(body: GuitarProfileIn) -> dict[str, Any]:
    """Stored at once (its own file: the Definições save rewrites settings.json)."""
    from rockforge.infrastructure import guitar_profile

    return guitar_profile.save(body.model_dump())


def _ai_error(exc: Exception) -> HTTPException:
    from rockforge.infrastructure.ai_assistant import AiError

    if isinstance(exc, AiError):
        return HTTPException(exc.status, str(exc))
    return HTTPException(422, str(exc))


@router.get("/ai-assistant", response_model=AiAssistantOut)
def get_ai_assistant() -> AiAssistantOut:
    from rockforge.infrastructure import ai_assistant

    return AiAssistantOut(**ai_assistant.public_state())


@router.put("/ai-assistant", response_model=AiAssistantOut)
def set_ai_assistant(body: AiAssistantIn) -> AiAssistantOut:
    from rockforge.infrastructure import ai_assistant

    try:
        state = ai_assistant.update(
            provider=body.provider,
            model=(body.model_provider, body.model or "")
            if body.model_provider and body.model is not None else None,
            key=(body.key_provider, body.key) if body.key_provider and body.key else None,
            forget_key=body.forget_key,
            ollama_url=body.ollama_url,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return AiAssistantOut(**state)


@router.get("/ai-assistant/models", response_model=list[AiModelOut])
def get_ai_models(provider: str) -> list[AiModelOut]:
    from rockforge.infrastructure import ai_assistant

    try:
        return [AiModelOut(**m) for m in ai_assistant.list_models(provider)]
    except ai_assistant.AiError as exc:
        raise _ai_error(exc) from exc


def _callback_url(request: Request) -> str:
    """This app's own callback, as the browser reaches it. OpenRouter takes a
    localhost callback on any port, so the loopback address is named that way."""
    base = urllib.parse.urlsplit(str(request.base_url))
    host = base.hostname or "localhost"
    if host in ("127.0.0.1", "::1"):
        host = "localhost"
    netloc = host + (f":{base.port}" if base.port else "")
    return urllib.parse.urlunsplit((base.scheme, netloc, CALLBACK_PATH, "", ""))


@router.post("/ai-assistant/openrouter/login")
def openrouter_login(request: Request) -> dict[str, str]:
    """The openrouter.ai address to open: the user signs in there and comes
    back to the callback below, which stores the key."""
    from rockforge.infrastructure import ai_assistant

    return {"url": ai_assistant.start_openrouter_login(_callback_url(request))}


def _page(title: str, text: str, ok: bool) -> HTMLResponse:
    colour = "#3fb37f" if ok else "#e88"
    body = (
        "<!doctype html><html><head><meta charset=utf-8>"
        "<meta name=viewport content='width=device-width,initial-scale=1'>"
        f"<title>{html.escape(title)}</title></head>"
        "<body style='font:16px system-ui,sans-serif;background:#0f1115;color:#e6e6e6;"
        "display:grid;place-items:center;min-height:90vh;margin:0 16px'>"
        f"<div style='max-width:32rem'><h1 style='color:{colour};font-size:1.4rem'>"
        f"{html.escape(title)}</h1><p>{html.escape(text)}</p></div></body></html>"
    )
    return HTMLResponse(body, status_code=200 if ok else 400)


@router.get(CALLBACK_PATH, response_class=HTMLResponse)
def openrouter_callback(code: str = "", state: str = "", error: str = "") -> HTMLResponse:
    """Where openrouter.ai sends the browser back. Opened in the system
    browser, so the page is the answer: say it worked and that it can close."""
    from rockforge.infrastructure import ai_assistant

    if error or not code:
        return _page(i18n.tr("Ligação ao OpenRouter cancelada", "OpenRouter sign-in cancelled"),
                     i18n.tr("Não foi guardada nenhuma chave. Podes fechar esta janela e "
                             "tentar outra vez no RockForge.",
                             "No key was stored. You can close this window and try again in "
                             "RockForge."), ok=False)
    try:
        ai_assistant.finish_openrouter_login(code, state)
    except ai_assistant.AiError as exc:
        return _page(i18n.tr("Não foi possível ligar o OpenRouter", "Could not connect OpenRouter"),
                     str(exc), ok=False)
    return _page(i18n.tr("OpenRouter ligado", "OpenRouter connected"),
                 i18n.tr("A chave ficou guardada neste computador. Podes fechar esta janela e "
                         "voltar ao RockForge.",
                         "The key is stored on this computer. You can close this window and go "
                         "back to RockForge."), ok=True)


def _profile_text(*, guitar: bool, bass: bool) -> str:
    from rockforge.infrastructure import guitar_profile

    return guitar_profile.describe(guitar_profile.load(), guitar=guitar, bass=bass)


@router.get("/tone-prompt")
def get_tone_prompt(description: str, bass: bool = False) -> dict[str, str]:
    """The request for ONE tone from a few words, to paste into an assistant."""
    from rockforge.infrastructure.tone_plan import build_tone_prompt

    if not description.strip():
        raise HTTPException(422, i18n.tr("descreve o som primeiro", "describe the sound first"))
    return {"prompt": build_tone_prompt(description, bass=bass,
                                        guitar=_profile_text(guitar=not bass, bass=bass))}


def _tones_out(text: str, answer: str = "", model: str = "") -> ToneTextOut:
    from rockforge.infrastructure.tone_plan import TonePlanError, read_tones

    try:
        res = read_tones(text)
    except TonePlanError as exc:
        if answer:
            raise _Unreadable(str(exc), answer, model) from exc
        raise HTTPException(422, str(exc)) from exc
    return ToneTextOut(tones=res.tones, warnings=res.warnings, notes=res.notes,
                       sources=res.sources, answer=answer, model=model)


class _Unreadable(Exception):
    """An AI answered, but not with tones: the answer goes back with the reason,
    so the page can show what it said."""

    def __init__(self, message: str, answer: str, model: str) -> None:
        super().__init__(message)
        self.answer = answer
        self.model = model


def unreadable_response(exc: _Unreadable) -> JSONResponse:
    return JSONResponse(status_code=422, content={
        "detail": str(exc), "answer": exc.answer, "model": exc.model})


@router.post("/tone-text", response_model=ToneTextOut)
def read_tone_text(body: ToneTextIn) -> ToneTextOut:
    """A pasted answer to the one-tone request, read into tones. Nothing stored."""
    return _tones_out(body.text)


@router.post("/tone-ask", response_model=ToneTextOut)
def ask_tone(body: ToneDescribeIn) -> Any:
    """The one-tone request asked of the chosen AI, its answer read into tones."""
    from rockforge.infrastructure import ai_assistant
    from rockforge.infrastructure.tone_plan import build_tone_prompt

    prompt = build_tone_prompt(body.description, bass=body.bass,
                               guitar=_profile_text(guitar=not body.bass, bass=body.bass))
    try:
        answer = ai_assistant.ask(prompt)
    except ai_assistant.AiError as exc:
        raise _ai_error(exc) from exc
    try:
        return _tones_out(answer.text, answer.text, answer.model)
    except _Unreadable as exc:
        return unreadable_response(exc)
