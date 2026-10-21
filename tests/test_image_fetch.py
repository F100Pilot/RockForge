"""A cover image from any address the user pastes (infrastructure/image_fetch.py).

The address comes from the client, so most of these pin the refusals: no
address inside the user's network, no special port, every redirect checked,
and the connection made to the address that was checked. The downloads run
against a local HTTP server; the names it is reached by are invented and
resolved by a stand-in, so nothing here touches the internet.
"""

from __future__ import annotations

import base64
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO

import pytest

from rockforge.infrastructure import image_fetch
from rockforge.infrastructure.image_fetch import (
    ImageFetchError,
    ImageLinkRefused,
    NotAnImage,
    fetch_link,
    unwrap,
)

PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 32
JPEG = b"\xff\xd8\xff\xe0" + b"\0" * 32


def _image(fmt: str) -> bytes:
    from PIL import Image

    out = BytesIO()
    Image.new("RGB", (8, 8), (200, 40, 20)).save(out, format=fmt)
    return out.getvalue()


@pytest.fixture()
def site(monkeypatch):
    """A local server reached as covers.example (and inside.example, which
    resolves into the 'private' network), with loopback counted as public."""
    routes: dict[str, tuple[int, dict[str, str], bytes]] = {}
    seen_hosts: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            seen_hosts.append(self.headers.get("Host", ""))
            status, headers, body = routes.get(self.path, (404, {}, b""))
            self.send_response(status)
            for k, v in headers.items():
                self.send_header(k, v)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_a):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    names = {"covers.example": ["127.0.0.1"], "inside.example": ["10.0.0.7"]}
    monkeypatch.setattr(image_fetch, "_resolve", lambda host, _port: names[host])
    monkeypatch.setattr(image_fetch, "_ip_allowed", lambda ip: ip == "127.0.0.1")
    monkeypatch.setattr(image_fetch, "DEFAULT_PORTS", {"http": port, "https": 443})
    base = f"http://covers.example:{port}"
    yield base, routes, seen_hosts
    server.shutdown()


def test_an_image_on_a_public_site_is_downloaded_through_the_checked_address(site) -> None:
    base, routes, seen_hosts = site
    routes["/art/cover.jpg"] = (200, {"Content-Type": "image/jpeg"}, JPEG)
    data, suffix = fetch_link(f"{base}/art/cover.jpg")
    assert (data, suffix) == (JPEG, ".jpg")
    # covers.example is not a real name: the request reached the server only
    # because it went to the address that was checked, with the name as Host.
    assert seen_hosts[-1].startswith("covers.example")


def test_a_redirect_is_followed_only_to_another_public_address(site) -> None:
    base, routes, _ = site
    port = base.rsplit(":", 1)[1]
    routes["/go"] = (302, {"Location": "/final.png"}, b"")
    routes["/final.png"] = (200, {}, PNG)
    assert fetch_link(f"{base}/go") == (PNG, ".png")
    routes["/sneaky"] = (302, {"Location": f"http://inside.example:{port}/x.png"}, b"")
    with pytest.raises(ImageLinkRefused):
        fetch_link(f"{base}/sneaky")


def test_a_redirect_loop_and_a_missing_image_are_said(site) -> None:
    base, routes, _ = site
    routes["/loop"] = (302, {"Location": "/loop"}, b"")
    with pytest.raises(ImageFetchError, match="redirecion|redirected"):
        fetch_link(f"{base}/loop")
    with pytest.raises(ImageFetchError, match="404"):
        fetch_link(f"{base}/nothing.png")


def test_an_image_bigger_than_the_cap_is_refused(site, monkeypatch) -> None:
    base, routes, _ = site
    monkeypatch.setattr(image_fetch, "MAX_COVER_BYTES", 64)
    routes["/big.jpg"] = (200, {}, JPEG + b"\0" * 100)
    with pytest.raises(ImageFetchError, match="10 MB"):
        fetch_link(f"{base}/big.jpg")


@pytest.mark.parametrize("url", [
    "ftp://covers.example/a.png",
    "file:///etc/passwd",
    "http://user:secret@covers.example/a.png",
    "https://covers.example:8443/a.png",
    "http://127.0.0.1/a.png",
    "http://10.0.0.7/a.png",
    "http://169.254.169.254/latest/meta-data",
    "http://[::1]/a.png",
    "http://[::ffff:127.0.0.1]/a.png",
    "http://localhost/a.png",
])
def test_an_address_outside_the_public_internet_is_refused_before_anything_opens(
    url, monkeypatch
) -> None:
    def resolve(host, _port):
        return {"localhost": ["127.0.0.1"], "covers.example": ["93.184.216.34"]}.get(host, [host])

    def never(*_a, **_k):
        raise AssertionError("a connection was opened for a refused address")

    monkeypatch.setattr(image_fetch, "_resolve", resolve)
    monkeypatch.setattr(image_fetch, "_connection", never)
    with pytest.raises(ImageLinkRefused):
        fetch_link(url)


def test_a_name_that_resolves_to_any_private_address_is_refused(monkeypatch) -> None:
    monkeypatch.setattr(image_fetch, "_resolve", lambda *_a: ["93.184.216.34", "192.168.1.10"])
    monkeypatch.setattr(image_fetch, "_connection", lambda *_a: pytest.fail("opened"))
    with pytest.raises(ImageLinkRefused):
        fetch_link("https://mixed.example/a.png")


def test_a_google_images_link_points_at_the_image_itself() -> None:
    link = ("https://www.google.com/imgres?imgurl=https%3A%2F%2Fcdn.example.org%2Fa%2Fcover.jpg"
            "&imgrefurl=https%3A%2F%2Fexample.org%2F&tbnid=x")
    assert unwrap(link) == "https://cdn.example.org/a/cover.jpg"
    assert unwrap("https://cdn.example.org/b.png") == "https://cdn.example.org/b.png"


def test_a_data_address_is_read_without_the_network(monkeypatch) -> None:
    monkeypatch.setattr(image_fetch, "_download", lambda _u: pytest.fail("network"))
    url = "data:image/jpeg;base64," + base64.b64encode(JPEG).decode()
    assert fetch_link(url) == (JPEG, ".jpg")
    with pytest.raises(ImageLinkRefused):
        fetch_link("data:text/plain,hello")


@pytest.mark.parametrize("fmt", ["WEBP", "GIF", "BMP"])
def test_other_image_formats_become_a_png(fmt) -> None:
    # through the data: route, so no network is involved
    url = f"data:image/{fmt.lower()};base64," + base64.b64encode(_image(fmt)).decode()
    data, suffix = fetch_link(url)
    assert suffix == ".png" and data.startswith(b"\x89PNG")


def test_a_page_is_not_taken_for_an_image(monkeypatch) -> None:
    monkeypatch.setattr(image_fetch, "_resolve", lambda *_a: ["93.184.216.34"])
    page = b"<!DOCTYPE html><html><body>an image page</body></html>"
    with pytest.raises(NotAnImage, match="página|page"):
        fetch_link("https://cdn.example.org/view", download=lambda _u: page)
    with pytest.raises(NotAnImage):
        fetch_link("https://cdn.example.org/x", download=lambda _u: b"\x00\x01garbage" * 10)
