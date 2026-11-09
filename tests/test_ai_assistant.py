"""Asking an AI for tones (``infrastructure/ai_assistant.py``): what each
provider is sent and how its answer is read, the keys that never come back,
the OpenRouter sign-in and every failure in words. No request leaves: the
opener is replaced by a fake that records them."""

from __future__ import annotations

import base64
import hashlib
import importlib
import io
import json
import urllib.error
import urllib.parse
from typing import Any

import pytest


class _Resp:
    def __init__(self, body: bytes) -> None:
        self._b = io.BytesIO(body)

    def read(self, n: int = -1) -> bytes:
        return self._b.read(n)

    def __enter__(self) -> _Resp:
        return self

    def __exit__(self, *a: object) -> None:
        return None


class FakeNet:
    """Answers each request with the next queued item: a dict/list (JSON), or an
    exception to raise."""

    def __init__(self) -> None:
        self.queue: list[Any] = []
        self.sent: list[dict[str, Any]] = []

    def opener(self, https: bool) -> FakeNet:
        return self

    def open(self, req: Any, timeout: float = 0) -> _Resp:
        body = json.loads(req.data) if req.data else None
        self.sent.append({"url": req.full_url, "method": req.get_method(),
                          "headers": {k.lower(): v for k, v in req.header_items()},
                          "body": body, "timeout": timeout})
        item = self.queue.pop(0)
        if isinstance(item, BaseException):
            raise item
        return _Resp(json.dumps(item).encode())


@pytest.fixture
def ai(tmp_path, monkeypatch):
    monkeypatch.setenv("ROCKFORGE_WORK_DIR", str(tmp_path))
    from rockforge import config

    importlib.reload(config)
    from rockforge.infrastructure import ai_assistant

    net = FakeNet()
    monkeypatch.setattr(ai_assistant, "_opener", net.opener)
    ai_assistant._logins.clear()
    return ai_assistant, net


def _http_error(code: int, message: str = "") -> urllib.error.HTTPError:
    body = json.dumps({"error": {"message": message}}).encode() if message else b""
    return urllib.error.HTTPError("https://x", code, "err", {}, io.BytesIO(body))  # type: ignore[arg-type]


def test_nothing_is_ready_until_chosen_and_a_key_never_comes_back(ai) -> None:
    mod, _ = ai
    state = mod.public_state()
    assert state["provider"] == "" and state["ready"] is False
    assert state["has_key"] == {"openrouter": False, "gemini": False}
    state = mod.update(provider="gemini", key=("gemini", "AIzaSECRETkey0123456789012345678901"),
                       model=("gemini", "gemini-3.8-flash"))
    assert state["ready"] is True and state["has_key"]["gemini"] is True
    assert "AIzaSECRET" not in json.dumps(state)
    assert mod.stored_keys() == ["AIzaSECRETkey0123456789012345678901"]
    state = mod.update(forget_key="gemini")
    assert state["has_key"]["gemini"] is False and state["ready"] is False
    assert mod.stored_keys() == []
    # OpenRouter has its free router as the model until one is chosen
    mod.update(provider="openrouter", key=("openrouter", "sk-or-v1-abcdefabcdefabcdef"))
    assert mod.public_state()["models"]["openrouter"] == mod.OPENROUTER_FREE
    assert mod.public_state()["ready"] is True


def test_settings_that_are_not_what_they_say_are_refused(ai) -> None:
    mod, _ = ai
    with pytest.raises(ValueError):
        mod.update(provider="chatgpt")
    with pytest.raises(ValueError):
        mod.update(key=("gemini", "two words"))
    with pytest.raises(ValueError):
        mod.update(key=("ollama", "abc"))
    with pytest.raises(ValueError):
        mod.update(model=("gemini", "a model with spaces"))
    assert mod.clean_ollama_url("") == mod.OLLAMA_DEFAULT
    assert mod.clean_ollama_url("http://127.0.0.1:11434/") == "http://127.0.0.1:11434"
    for bad in ("http://192.168.1.5:11434", "http://evil.example", "ftp://localhost",
                "http://localhost:11434/api", "http://user:pw@localhost:11434"):
        with pytest.raises(ValueError):
            mod.clean_ollama_url(bad)


def test_openrouter_is_asked_with_the_key_and_its_answer_read(ai) -> None:
    mod, net = ai
    mod.update(provider="openrouter", key=("openrouter", "sk-or-v1-0123456789abcdef"),
               model=("openrouter", "anthropic/claude-x"))
    net.queue.append({"model": "anthropic/claude-x", "choices": [
        {"message": {"role": "assistant", "content": '{"tones": []}'}}],
        "usage": {"prompt_tokens": 5000, "completion_tokens": 900}})
    ans = mod.ask("the request")
    sent = net.sent[0]
    assert sent["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert sent["method"] == "POST"
    assert sent["headers"]["authorization"] == "Bearer sk-or-v1-0123456789abcdef"
    assert sent["body"]["model"] == "anthropic/claude-x"
    assert sent["body"]["messages"] == [{"role": "user", "content": "the request"}]
    assert sent["timeout"] == mod.ASK_TIMEOUT_S
    assert (ans.text, ans.model, ans.prompt_tokens, ans.completion_tokens) == (
        '{"tones": []}', "anthropic/claude-x", 5000, 900)
    # an error object inside a 200 is an error, not an empty answer
    net.queue.append({"error": {"message": "model overloaded"}})
    with pytest.raises(mod.AiError, match="model overloaded"):
        mod.ask("again")


def test_gemini_takes_its_key_in_a_header_and_answers_json(ai) -> None:
    mod, net = ai
    mod.update(provider="gemini", key=("gemini", "AIzaKEY01234567890123456789012345"),
               model=("gemini", "gemini-3.8-flash"))
    net.queue.append({"candidates": [{"content": {"parts": [
        {"text": "thinking…", "thought": True}, {"text": '{"tones":'}, {"text": " []}"}]}}],
        "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 3}})
    ans = mod.ask("p")
    sent = net.sent[0]
    assert sent["url"] == ("https://generativelanguage.googleapis.com/v1beta/models/"
                           "gemini-3.8-flash:generateContent")
    assert "key=" not in sent["url"]
    assert sent["headers"]["x-goog-api-key"] == "AIzaKEY01234567890123456789012345"
    assert sent["body"]["contents"][0]["parts"] == [{"text": "p"}]
    assert sent["body"]["generationConfig"]["responseMimeType"] == "application/json"
    assert ans.text == '{"tones": []}'
    net.queue.append({"promptFeedback": {"blockReason": "SAFETY"}})
    with pytest.raises(mod.AiError, match="SAFETY"):
        mod.ask("p")


def test_ollama_is_asked_on_this_computer_with_room_for_the_whole_request(ai) -> None:
    mod, net = ai
    mod.update(provider="ollama", model=("ollama", "llama3.1:8b"),
               ollama_url="http://127.0.0.1:11500")
    net.queue.append({"message": {"role": "assistant", "content": "{}"}, "done": True,
                      "prompt_eval_count": 4000, "eval_count": 500})
    ans = mod.ask("p")
    sent = net.sent[0]
    assert sent["url"] == "http://127.0.0.1:11500/api/chat"
    assert sent["body"]["stream"] is False and sent["body"]["format"] == "json"
    assert sent["body"]["options"]["num_ctx"] == mod.OLLAMA_CONTEXT
    assert (ans.text, ans.prompt_tokens) == ("{}", 4000)
    net.queue.append(urllib.error.URLError("connection refused"))
    with pytest.raises(mod.AiError, match="Ollama"):
        mod.ask("p")


def test_every_failure_is_said_in_words_with_the_right_status(ai) -> None:
    mod, net = ai
    mod.update(provider="openrouter", key=("openrouter", "sk-or-v1-0123456789abcdef"))
    for code, status in ((401, 401), (403, 401), (402, 402), (404, 404), (429, 429),
                         (500, 502)):
        net.queue.append(_http_error(code, "nope"))
        with pytest.raises(mod.AiError) as err:
            mod.ask("p")
        assert err.value.status == status and "nope" in str(err.value)
    net.queue.append(TimeoutError())
    with pytest.raises(mod.AiError) as err:
        mod.ask("p")
    assert err.value.status == 504
    net.queue.append({"choices": [{"message": {"content": "   "}}]})
    with pytest.raises(mod.AiError):
        mod.ask("p")
    # a redirect is never followed
    net.queue.append(_http_error(302))
    with pytest.raises(mod.AiError):
        mod.ask("p")
    # nothing chosen, nothing asked
    mod.update(provider="")
    sent = len(net.sent)
    with pytest.raises(mod.AiError) as err:
        mod.ask("p")
    assert err.value.status == 409 and len(net.sent) == sent


def test_the_models_and_their_prices_are_listed(ai) -> None:
    mod, net = ai
    net.queue.append({"data": [
        {"id": "meta/llama:free", "name": "Llama (free)",
         "pricing": {"prompt": "0", "completion": "0"}, "context_length": 131072},
        {"id": "anthropic/claude-x", "name": "Claude X",
         "pricing": {"prompt": "0.000003", "completion": "0.000015"}},
        {"name": "no id"}]})
    models = mod.list_models("openrouter")
    assert models[0]["id"] == mod.OPENROUTER_FREE and models[0]["free"] is True
    assert models[1] == {"id": "meta/llama:free", "name": "Llama (free)", "free": True,
                         "prompt_price": 0.0, "completion_price": 0.0, "context": 131072}
    assert models[2]["free"] is False and models[2]["completion_price"] == pytest.approx(1.5e-5)
    assert len(models) == 3
    assert "authorization" not in net.sent[0]["headers"]   # the list needs no key
    with pytest.raises(mod.AiError):
        mod.list_models("gemini")                           # no key stored yet
    mod.update(key=("gemini", "AIzaKEY01234567890123456789012345"))
    net.queue.append({"models": [
        {"name": "models/gemini-3.8-flash", "displayName": "Gemini 3.8 Flash",
         "supportedGenerationMethods": ["generateContent", "countTokens"]},
        {"name": "models/embedding-1", "supportedGenerationMethods": ["embedContent"]}]})
    assert [m["id"] for m in mod.list_models("gemini")] == ["gemini-3.8-flash"]
    net.queue.append({"models": [{"name": "qwen2.5:14b"}, {"size": 1}]})
    assert [m["id"] for m in mod.list_models("ollama")] == ["qwen2.5:14b"]
    assert net.sent[-1]["url"] == "http://localhost:11434/api/tags"


def test_signing_in_to_openrouter_exchanges_the_code_once(ai) -> None:
    mod, net = ai
    url = mod.start_openrouter_login("http://localhost:8000/ai-assistant/openrouter/callback")
    q = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
    assert url.startswith("https://openrouter.ai/auth?")
    assert q["callback_url"] == ["http://localhost:8000/ai-assistant/openrouter/callback"]
    assert q["code_challenge_method"] == ["S256"]
    state = q["state"][0]
    verifier = mod._logins[state][0]
    want = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=")
    assert q["code_challenge"] == [want.decode()]
    with pytest.raises(mod.AiError):
        mod.finish_openrouter_login("code", "a state this app never made")
    assert net.sent == []
    net.queue.append({"key": "sk-or-v1-userkey0123456789", "user_id": "u"})
    mod.finish_openrouter_login("the-code", state)
    sent = net.sent[0]
    assert sent["url"] == "https://openrouter.ai/api/v1/auth/keys"
    assert sent["body"] == {"code": "the-code", "code_verifier": verifier,
                            "code_challenge_method": "S256"}
    state_now = mod.public_state()
    assert state_now["provider"] == "openrouter" and state_now["has_key"]["openrouter"]
    with pytest.raises(mod.AiError):           # the same state cannot be used twice
        mod.finish_openrouter_login("the-code", state)


def test_the_keys_never_reach_the_technical_log(ai) -> None:
    mod, _ = ai
    from rockforge.app_logging import redact

    mod.update(key=("gemini", "PLAINKEY-0123456789-abcdef"))
    line = redact("asked with PLAINKEY-0123456789-abcdef and sk-or-v1-feedfacefeedfacefeed, "
                  "AIzaSyA0123456789012345678901234567890 and x-goog-api-key: zzz")
    assert "PLAINKEY" not in line and "sk-or-v1-feed" not in line
    assert "AIzaSyA0" not in line and "zzz" not in line
