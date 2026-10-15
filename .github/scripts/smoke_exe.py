"""Smoke-test the built RockForge .exe the way a user would first meet it.

Run by the release workflow on a Windows runner, against the FROZEN build in
``dist/rockforge`` — not the source tree — because the frozen app has failed in
ways no test of the source can see (an index.html with no app.js behind it, a
worker that died importing Celery by name). It starts ``rockforge.exe``, waits
for the page, creates a project from an invented one-bar GP5 and a generated
tone (the bundled ffmpeg makes it), waits for the build, and asks the app's own
PSARC check about the result. Any failure exits non-zero, so no Release gets
files that do not start.

Usage: python smoke_exe.py <path to rockforge.exe>
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
import uuid
from pathlib import Path

PORT = 8765
BASE = f"http://127.0.0.1:{PORT}"
HEADERS = {"Origin": BASE, "X-RockForge-Lang": "en"}


def request(method: str, path: str, body: bytes | None = None,
            content_type: str | None = None, timeout: float = 30) -> dict:
    headers = dict(HEADERS)
    if content_type:
        headers["Content-Type"] = content_type
    req = urllib.request.Request(BASE + path, data=body, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read() or b"{}")


def multipart(fields: dict[str, str], files: dict[str, Path]) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    parts: list[bytes] = []
    for name, value in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"'
                     f"\r\n\r\n{value}\r\n".encode())
    for name, path in files.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; '
                     f'filename="{path.name}"\r\nContent-Type: application/octet-stream'
                     "\r\n\r\n".encode() + path.read_bytes() + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def invented_gp5(path: Path) -> None:
    import guitarpro as gp

    song = gp.Song()
    song.title, song.artist, song.tempo = "Smoke", "RockForge CI", 100
    song.tracks[0].name = "Lead"
    voice = song.tracks[0].measures[0].voices[0]
    for fret in (3, 5, 7, 5, 3, 5, 7, 8):
        beat = gp.Beat(voice)
        beat.status = gp.BeatStatus.normal
        beat.duration = gp.Duration(value=8)
        note = gp.Note(beat)
        note.string, note.value, note.type = 2, fret, gp.NoteType.normal
        beat.notes.append(note)
        voice.beats.append(beat)
    gp.write(song, str(path))


def main(exe: Path) -> int:
    work = Path(tempfile.mkdtemp(prefix="rf-smoke-"))
    ffmpeg = exe.parent / "_internal" / "ffmpeg" / "ffmpeg.exe"
    if not ffmpeg.exists():
        print(f"FAIL: no bundled ffmpeg at {ffmpeg}")
        return 1
    gp5, wav = work / "smoke.gp5", work / "smoke.wav"
    invented_gp5(gp5)
    subprocess.run([str(ffmpeg), "-nostdin", "-loglevel", "error", "-y", "-f", "lavfi",
                    "-i", "sine=frequency=220:duration=8", str(wav)],
                   check=True, stdin=subprocess.DEVNULL)

    env = dict(os.environ, ROCKFORGE_PORT=str(PORT), ROCKFORGE_WORK_DIR=str(work / "data"),
               ROCKFORGE_IDLE_SHUTDOWN_S="0")
    # The runner's own ffmpeg must not stand in for the bundled one.
    env["PATH"] = os.pathsep.join(p for p in env.get("PATH", "").split(os.pathsep)
                                  if "ffmpeg" not in p.lower())
    proc = subprocess.Popen([str(exe)], cwd=work, env=env, stdin=subprocess.DEVNULL)
    try:
        for _ in range(120):
            try:
                with urllib.request.urlopen(BASE + "/", timeout=2) as resp:
                    page = resp.read().decode("utf-8", "replace")
                with urllib.request.urlopen(BASE + "/app.js", timeout=5) as resp:
                    if resp.status != 200 or not resp.read(64):
                        print("FAIL: /app.js is empty")
                        return 1
                break
            except OSError:
                if proc.poll() is not None:
                    print(f"FAIL: rockforge.exe exited with {proc.returncode}")
                    return 1
                time.sleep(1)
        else:
            print("FAIL: the page never answered")
            return 1
        if "app.js" not in page:
            print("FAIL: index.html does not load app.js")
            return 1
        print("page and app.js served")

        checks = request("GET", "/system-check")
        ff = next((r for r in checks.get("requirements", []) if r.get("key") == "ffmpeg"), {})
        if not ff.get("found"):
            print(f"FAIL: the app does not find its bundled ffmpeg: {ff}")
            return 1
        print("bundled ffmpeg found:", ff.get("detail", ""))

        body, ctype = multipart({}, {"file": gp5})
        inspect = request("POST", "/gp/inspect", body, ctype)
        body, ctype = multipart({"gp_token": inspect["gp_token"], "lead_track": "0"},
                                {"audio": wav})
        job = request("POST", "/jobs/gp", body, ctype)
        print("project created:", job["id"])
        status: dict = {}
        for _ in range(300):
            status = request("GET", f"/jobs/{job['id']}")
            if status["status"] in ("completed", "failed"):
                break
            time.sleep(1)
        if status.get("status") != "completed":
            print(f"FAIL: the build ended {status.get('status')}: {status.get('error')}")
            return 1
        report = request("GET", f"/jobs/{job['id']}/psarc-check", timeout=60)
        if not report.get("ok"):
            print("FAIL: the PSARC check found problems:", json.dumps(report)[:2000])
            return 1
        print("build completed; PSARC checked clean:", report.get("charts"))
        return 0
    finally:
        proc.kill()


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]).resolve()))
