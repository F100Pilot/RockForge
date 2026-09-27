"""Outbound HTTPS trusts certifi's roots, and a refused certificate is explained."""

from __future__ import annotations

import ssl
import sys
import urllib.error
import urllib.request
from typing import Any

import pytest

from rockforge.infrastructure import _https, album_lookup, lyrics_lookup

_EXPIRED = ssl.SSLCertVerificationError(
    1, "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: certificate has expired"
)


@pytest.fixture(autouse=True)
def _fresh_context() -> Any:
    _https.ssl_context.cache_clear()
    yield
    _https.ssl_context.cache_clear()


def _bare_client_context() -> ssl.SSLContext:
    # A verifying client context with NO roots loaded, standing in for a
    # machine whose system store lacks the root a site needs.
    return ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)


def test_certifis_roots_are_added_to_the_system_ones_and_checking_stays_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(_https.ssl, "create_default_context", _bare_client_context)
    ctx = _https.ssl_context()
    assert ctx.cert_store_stats()["x509_ca"] > 100  # Mozilla's list, loaded
    assert ctx.verify_mode == ssl.CERT_REQUIRED
    assert ctx.check_hostname is True


def test_the_system_roots_are_kept_not_replaced() -> None:
    # An antivirus/proxy root lives only in the system store; certifi must
    # add to it, never stand in for it.
    system = ssl.create_default_context().cert_store_stats()["x509_ca"]
    assert _https.ssl_context().cert_store_stats()["x509_ca"] >= system


def test_without_certifi_the_system_default_is_used(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "certifi", None)
    monkeypatch.setattr(_https.ssl, "create_default_context", _bare_client_context)
    ctx = _https.ssl_context()
    assert ctx.cert_store_stats()["x509_ca"] == 0
    assert ctx.verify_mode == ssl.CERT_REQUIRED


def _fake_urlopen(calls: list[Any], exc: BaseException | None = None) -> Any:
    def fake(request: Any, timeout: float = 0, context: Any = None) -> Any:
        calls.append(context)
        raise exc or urllib.error.URLError("offline")

    return fake


@pytest.mark.parametrize(
    ("module", "error", "service"),
    [
        (lyrics_lookup, lyrics_lookup.LyricsLookupError, "LRCLIB"),
        (album_lookup, album_lookup.AlbumLookupError, "serviço"),
    ],
)
def test_every_json_client_uses_the_shared_context_and_explains_an_expired_certificate(
    monkeypatch: pytest.MonkeyPatch, module: Any, error: type[Exception], service: str
) -> None:
    calls: list[Any] = []
    monkeypatch.setattr(
        urllib.request, "urlopen", _fake_urlopen(calls, urllib.error.URLError(_EXPIRED))
    )
    with pytest.raises(error) as info:
        module._http_get_json("https://example.invalid/x")
    assert calls == [_https.ssl_context()]
    message = str(info.value)
    assert f"ligação segura ao {service}" in message
    assert "data e a hora" in message and "certifi" in message


def test_an_ordinary_network_failure_keeps_its_plain_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen([]))
    with pytest.raises(lyrics_lookup.LyricsLookupError, match="não consegui contactar o LRCLIB"):
        lyrics_lookup._http_get_json("https://example.invalid/x")


def test_the_cover_download_verifies_with_the_shared_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    handlers: list[Any] = []
    real = urllib.request.build_opener

    def spy(*args: Any) -> Any:
        handlers.extend(args)
        opener = real(*args)

        def refuse(request: Any, timeout: float = 0) -> Any:
            raise urllib.error.URLError(_EXPIRED)

        opener.open = refuse  # type: ignore[method-assign]
        return opener

    monkeypatch.setattr(urllib.request, "build_opener", spy)
    with pytest.raises(album_lookup.AlbumLookupError, match="ligação segura"):
        album_lookup._open_url("https://is1-ssl.mzstatic.com/a.jpg")
    https = [h for h in handlers if isinstance(h, urllib.request.HTTPSHandler)]
    assert https and https[0]._context is _https.ssl_context()
