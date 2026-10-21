"""A cover image from any address the user pastes.

The album lookup (``album_lookup.fetch_cover``) only ever downloads from the
cover services' own image hosts. This is the other way in: an image found
anywhere — on Google Images, a band's site, a shop — whose address the user
copies. The address comes from the client, so this is the SSRF-sensitive path,
and every rule below is there for that:

- ``http``/``https`` on their default ports, no user name or password;
- every address the name resolves to must be public (``is_global``), and the
  connection goes to THAT address (pinned) — a name that resolves differently
  a moment later cannot send the request inside the user's network;
- each redirect is checked the same way, at most ``MAX_REDIRECTS``;
- at most ``MAX_COVER_BYTES`` are read, and the file is trusted by its bytes:
  JPEG/PNG as they are, any other image Pillow can open (WebP, GIF, BMP…)
  turned into PNG, never more than ``MAX_PIXELS``.

A ``data:`` address (what "copy image address" gives for a Google Images
thumbnail) is decoded here without any network, and a Google ``imgres`` link
is unwrapped to the image it points at.
"""

from __future__ import annotations

import base64
import binascii
import http.client
import ipaddress
import socket
import ssl
import urllib.parse
from collections.abc import Callable
from io import BytesIO

from rockforge.i18n import tr
from rockforge.infrastructure._https import ssl_context
from rockforge.infrastructure.album_lookup import MAX_COVER_BYTES, image_suffix

MAX_REDIRECTS = 5
TIMEOUT_S = 15
MAX_PIXELS = 40_000_000  # a 6000 x 6000 image is far more than a cover needs
DEFAULT_PORTS = {"http": 80, "https": 443}
_USER_AGENT = "Mozilla/5.0 (RockForge cover download)"
_REDIRECTS = {301, 302, 303, 307, 308}


class ImageFetchError(Exception):
    """The image could not be downloaded (network, the site's answer)."""


class ImageLinkRefused(ImageFetchError):
    """The address itself is not allowed — refused before anything is opened."""


class NotAnImage(ImageFetchError):
    """The address answered, but not with an image."""


def unwrap(url: str) -> str:
    """The image a Google Images result link points at; anything else as is."""
    parts = urllib.parse.urlsplit(url.strip())
    host = (parts.hostname or "").lower()
    if host.startswith(("google.", "www.google.")) or ".google." in host:
        query = urllib.parse.parse_qs(parts.query)
        for key in ("imgurl", "url", "q"):
            target = query.get(key, [""])[0]
            if target.startswith(("http://", "https://")):
                return target
    return url.strip()


def _ip_allowed(ip: str) -> bool:
    addr = ipaddress.ip_address(ip)
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped is not None:
        addr = addr.ipv4_mapped
    return addr.is_global and not addr.is_multicast


def _resolve(host: str, port: int) -> list[str]:
    infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return list(dict.fromkeys(str(info[4][0]) for info in infos))


def _check(url: str) -> tuple[str, str, int, str]:
    """Scheme, host, port and request target of an allowed address."""
    parts = urllib.parse.urlsplit(url)
    scheme = parts.scheme.lower()
    if scheme not in DEFAULT_PORTS:
        raise ImageLinkRefused(tr(
            "o link tem de começar por http:// ou https://",
            "the link must start with http:// or https://",
        ))
    if parts.username or parts.password:
        raise ImageLinkRefused(tr(
            "o link não pode levar nome de utilizador nem palavra-passe",
            "the link cannot carry a user name or password",
        ))
    host = parts.hostname
    try:
        port = parts.port or DEFAULT_PORTS[scheme]
    except ValueError as exc:
        raise ImageLinkRefused(tr("o link não é válido", "the link is not valid")) from exc
    if not host or port != DEFAULT_PORTS[scheme]:
        raise ImageLinkRefused(tr(
            "o link não é de um site público (só endereços normais, sem portas especiais)",
            "the link is not a public site's (ordinary addresses only, no special ports)",
        ))
    target = parts.path or "/"
    if parts.query:
        target += "?" + parts.query
    return scheme, host, port, target


def _public_ip(host: str, port: int) -> str:
    try:
        ips = _resolve(host, port)
    except OSError as exc:
        raise ImageFetchError(tr(
            f"não encontrei o site {host}", f"could not find the site {host}",
        )) from exc
    if not ips or not all(_ip_allowed(ip) for ip in ips):
        raise ImageLinkRefused(tr(
            "esse link aponta para dentro da tua rede ou do teu computador — só imagens de "
            "sites públicos",
            "that link points inside your network or your computer — only images from public "
            "sites",
        ))
    return ips[0]


class _PinnedHTTP(http.client.HTTPConnection):
    def __init__(self, host: str, ip: str, port: int) -> None:
        super().__init__(host, port, timeout=TIMEOUT_S)
        self._ip = ip

    def connect(self) -> None:
        self.sock = socket.create_connection((self._ip, self.port), self.timeout)


class _PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host: str, ip: str, port: int, context: ssl.SSLContext) -> None:
        super().__init__(host, port, timeout=TIMEOUT_S, context=context)
        self._ip = ip
        self._ctx = context

    def connect(self) -> None:
        sock = socket.create_connection((self._ip, self.port), self.timeout)
        self.sock = self._ctx.wrap_socket(sock, server_hostname=self.host)


def _connection(scheme: str, host: str, ip: str, port: int) -> http.client.HTTPConnection:
    if scheme == "https":
        return _PinnedHTTPS(host, ip, port, ssl_context())
    return _PinnedHTTP(host, ip, port)


def _download(url: str) -> bytes:
    for _ in range(MAX_REDIRECTS + 1):
        scheme, host, port, target = _check(url)
        conn = _connection(scheme, host, _public_ip(host, port), port)
        try:
            conn.request("GET", target, headers={
                "User-Agent": _USER_AGENT, "Accept": "image/*,*/*;q=0.5",
            })
            resp = conn.getresponse()
            if resp.status in _REDIRECTS:
                location = resp.getheader("Location")
                if not location:
                    break
                url = urllib.parse.urljoin(url, location)
                continue
            if resp.status != 200:
                raise ImageFetchError(tr(
                    f"o site respondeu {resp.status} — a imagem não está disponível nesse link",
                    f"the site answered {resp.status} — the image is not available at that link",
                ))
            declared = resp.getheader("Content-Length")
            if declared and declared.isdigit() and int(declared) > MAX_COVER_BYTES:
                raise ImageFetchError(_too_large())
            data = resp.read(MAX_COVER_BYTES + 1)
            if len(data) > MAX_COVER_BYTES:
                raise ImageFetchError(_too_large())
            return data
        except (OSError, http.client.HTTPException) as exc:
            raise ImageFetchError(tr(
                f"não consegui descarregar a imagem ({exc})",
                f"could not download the image ({exc})",
            )) from exc
        finally:
            conn.close()
    raise ImageFetchError(tr(
        "o link redirecionou demasiadas vezes", "the link redirected too many times",
    ))


def _too_large() -> str:
    return tr(
        "a imagem é demasiado grande (máximo 10 MB)", "the image is too large (10 MB at most)",
    )


def _from_data_url(url: str) -> bytes:
    header, sep, payload = url.partition(",")
    if not sep or ";base64" not in header.lower():
        raise ImageLinkRefused(tr(
            "esse link data: não traz uma imagem", "that data: link carries no image",
        ))
    if len(payload) > MAX_COVER_BYTES * 4 // 3 + 4:
        raise ImageFetchError(_too_large())
    try:
        return base64.b64decode(payload, validate=False)
    except (binascii.Error, ValueError) as exc:
        raise NotAnImage(tr(
            "esse link data: não é válido", "that data: link is not valid",
        )) from exc


def as_cover(data: bytes) -> tuple[bytes, str]:
    """JPEG/PNG bytes as they are; any other image turned into a PNG."""
    suffix = image_suffix(data)
    if suffix is not None:
        return data, suffix
    head = data[:512].lstrip().lower()
    if head.startswith((b"<!doctype", b"<html", b"<?xml", b"<svg", b"{")):
        raise NotAnImage(tr(
            "esse link é de uma página, não de uma imagem — abre a imagem sozinha e copia o "
            "endereço da imagem",
            "that link is a page, not an image — open the image on its own and copy the "
            "image address",
        ))
    try:
        from PIL import Image
    except ImportError as exc:
        raise NotAnImage(tr(
            "a imagem não é JPEG nem PNG, e converter outros formatos precisa do extra [psarc] "
            "(Pillow)",
            "the image is neither JPEG nor PNG, and converting other formats needs the [psarc] "
            "extra (Pillow)",
        )) from exc
    try:
        with Image.open(BytesIO(data)) as img:
            width, height = img.size
            if width * height > MAX_PIXELS:
                raise NotAnImage(tr(
                    "a imagem é grande demais para uma capa", "the image is too big for a cover",
                ))
            img.load()
            frame = img.convert("RGBA" if "A" in img.getbands() else "RGB")
            out = BytesIO()
            frame.save(out, format="PNG")
    except NotAnImage:
        raise
    except Exception as exc:  # Pillow raises many kinds for a file it cannot read
        raise NotAnImage(tr(
            "o link não devolveu uma imagem que eu consiga ler",
            "the link did not return an image I can read",
        )) from exc
    return out.getvalue(), ".png"


def fetch_link(
    url: str, *, download: Callable[[str], bytes] | None = None
) -> tuple[bytes, str]:
    """Download the image at a pasted address: its bytes and ``.jpg``/``.png``."""
    url = unwrap(url)
    if not url:
        raise ImageLinkRefused(tr("cola o link da imagem", "paste the image link"))
    if url[:5].lower() == "data:":
        data = _from_data_url(url)
    else:
        # Refuse a bad address — scheme, port, where it resolves — before
        # anything is opened; the download checks every hop again.
        _scheme, host, port, _target = _check(url)
        _public_ip(host, port)
        data = (download or _download)(url)
    return as_cover(data)
