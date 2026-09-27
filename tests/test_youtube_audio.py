"""The audio of one YouTube video, fetched with yt-dlp.

YouTube is unreachable from CI and the sandbox, and yt-dlp is an optional
extra, so the module is driven with a fake ``run``: what is pinned is the
command we build (only a validated id, only a known browser, no stdin) and how
every outcome is reported.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from rockforge.infrastructure import youtube_audio as ya

VID = "dQw4w9WgXcQ"


def test_the_command_takes_only_a_valid_id_and_a_known_browser(tmp_path: Path) -> None:
    args = ya.build_args(["yt-dlp"], VID, tmp_path / "yt-x.%(ext)s", "firefox")
    assert args[0] == "yt-dlp" and args[-1] == f"https://youtu.be/{VID}"
    assert args[args.index("--cookies-from-browser") + 1] == "firefox"
    assert "--no-playlist" in args and args[args.index("-f") + 1].startswith("bestaudio")
    assert "--cookies-from-browser" not in ya.build_args(["yt-dlp"], VID, tmp_path / "t", None)
    for bad in ("https://youtu.be/x", "short", f"{VID}; rm -rf /", "../../etc/passwd1"):
        with pytest.raises(ya.YouTubeAudioError):
            ya.build_args(["yt-dlp"], bad, tmp_path / "t", None)
    with pytest.raises(ya.YouTubeAudioError):
        ya.build_args(["yt-dlp"], VID, tmp_path / "t", "netscape")


def test_a_download_returns_the_file_it_wrote(tmp_path: Path) -> None:
    seen = {}

    def run(args, **kw):  # noqa: ANN001, ANN003, ANN202
        seen.update(kw, args=args)
        out = Path(args[args.index("-o") + 1].replace("%(ext)s", "m4a"))
        out.write_bytes(b"audio")
        return SimpleNamespace(returncode=0, stdout=f"{out}\n", stderr="")

    path = ya.download_audio(VID, tmp_path, command=["yt-dlp"], run=run)
    assert path.read_bytes() == b"audio" and path.name.startswith(ya.FILE_PREFIX)
    assert path.parent == tmp_path
    assert seen["stdin"] is subprocess.DEVNULL and seen["timeout"] == ya.DOWNLOAD_TIMEOUT_S


def test_a_reported_path_outside_the_folder_is_not_trusted(tmp_path: Path) -> None:
    elsewhere = tmp_path / "other"
    elsewhere.mkdir()
    (elsewhere / "yt-evil.m4a").write_bytes(b"x")

    def run(args, **kw):  # noqa: ANN001, ANN003, ANN202
        return SimpleNamespace(returncode=0, stdout=str(elsewhere / "yt-evil.m4a"), stderr="")

    with pytest.raises(ya.YouTubeAudioError, match="não encontrei"):
        ya.download_audio(VID, tmp_path / "dest", command=["yt-dlp"], run=run)


def test_a_refusal_says_when_youtube_wants_a_login(tmp_path: Path) -> None:
    def run(args, **kw):  # noqa: ANN001, ANN003, ANN202
        return SimpleNamespace(returncode=1, stdout="",
                               stderr="ERROR: unable to download: HTTP Error 403: Forbidden")

    with pytest.raises(ya.YouTubeAudioError) as exc:
        ya.download_audio(VID, tmp_path, command=["yt-dlp"], run=run)
    assert exc.value.needs_cookies and "403" in str(exc.value)

    def gone(args, **kw):  # noqa: ANN001, ANN003, ANN202
        return SimpleNamespace(returncode=1, stdout="", stderr="ERROR: Video unavailable")

    with pytest.raises(ya.YouTubeAudioError) as exc:
        ya.download_audio(VID, tmp_path, command=["yt-dlp"], run=gone)
    assert not exc.value.needs_cookies


def test_no_ytdlp_or_a_hung_one_is_a_clear_error(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(ya, "ytdlp_command", lambda: None)
    with pytest.raises(ya.YtDlpMissingError, match="yt-dlp"):
        ya.download_audio(VID, tmp_path)

    def slow(args, **kw):  # noqa: ANN001, ANN003, ANN202
        raise subprocess.TimeoutExpired(args, 1)

    with pytest.raises(ya.YouTubeAudioError, match="demorou"):
        ya.download_audio(VID, tmp_path, command=["yt-dlp"], run=slow)


def test_every_installed_js_runtime_is_enabled_in_yt_dlps_priority_order() -> None:
    # Only deno is on by default in yt-dlp; node/quickjs/bun must be asked for.
    found = {"node": "/usr/bin/node", "bun": "/opt/bun"}
    assert ya.js_runtime_args(found.get) == [
        "--js-runtimes", "node:/usr/bin/node", "--js-runtimes", "bun:/opt/bun",
    ]
    assert ya.js_runtime_args(lambda _p: None) == []


def test_the_command_keeps_warnings_and_passes_the_runtimes(tmp_path: Path) -> None:
    runtimes = ["--js-runtimes", "deno:/d/deno"]
    args = ya.build_args(["yt-dlp"], VID, tmp_path / "t", None, runtimes)
    # --no-warnings hid "No supported JavaScript runtime", the real cause.
    assert "--no-warnings" not in args
    assert args[args.index("--js-runtimes") + 1] == "deno:/d/deno"
    with_session = ya.build_args(["yt-dlp"], VID, tmp_path / "t", "firefox", [])
    assert with_session[with_session.index("--extractor-args") + 1] == (
        "youtube:player_client=default,web_embedded"
    )


def test_a_missing_js_runtime_is_named_not_passed_off_as_a_login() -> None:
    stderr = (
        "WARNING: [youtube] No supported JavaScript runtime could be found. Only deno is "
        "enabled by default\nERROR: unable to download video data: HTTP Error 403: Forbidden\n"
    )
    exc = ya.classify_failure(stderr, 1)
    assert "motor JavaScript" in str(exc) and "Deno" in str(exc)
    assert not exc.needs_cookies


def test_an_unreadable_chrome_session_says_to_pick_another_browser() -> None:
    line = ("ERROR: Failed to decrypt with DPAPI. See  "
            "https://github.com/yt-dlp/yt-dlp/issues/10927  for more info")
    exc = ya.classify_failure(f"{line}\n{line}\n", 1)
    assert "Firefox" in str(exc) and not exc.needs_cookies


def test_a_plain_failure_shows_each_error_once() -> None:
    exc = ya.classify_failure("ERROR: Video unavailable\nERROR: Video unavailable\n", 1)
    assert str(exc) == "ERROR: Video unavailable"
