"""Smoke-test the built RockForge .exe the way a user would first meet it.

Run by the release workflow on a Windows runner, against the FROZEN build in
``dist/rockforge`` — not the source tree — because the frozen app has failed in
ways no test of the source can see (an index.html with no app.js behind it, a
worker that died importing Celery by name). It starts ``rockforge.exe``, waits
for the page, creates a project from an invented one-bar GP5 and a generated
tone (the bundled ffmpeg makes it), waits for the build, and asks the app's own
PSARC check about the result. Any failure exits non-zero, so no Release gets
files that do not start.

With ``--components`` it then installs the extra components the way a user's
first start does (``POST /components/install``: a private Python 3.11, the ML,
lyrics, YouTube and PDF packages, Deno) and uses each of them through the
frozen app: a tempo measured by librosa, a PDF of a tab converted by
PDF-to-GP5, the recording separated by Demucs.

Usage: python smoke_exe.py <path to rockforge.exe> [--components]
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


def tab_pdf(lines: list[str]) -> bytes:
    """A one-page PDF of a text tab, written by hand (as tests/test_pdf_import.py)."""
    text = "".join(f"({line}) Tj T* " for line in lines)
    stream = f"BT /F1 10 Tf 11.5 TL 40 780 Td {text}ET".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1, xref)
    return bytes(out)


def components_check(job_id: str, work: Path) -> int:
    """Install the extra components through the app and use each of them."""
    request("POST", "/components/install")
    shown = 0
    status: dict = {}
    for _ in range(45 * 6):  # 45 minutes
        status = request("GET", "/components", timeout=120)
        log = status.get("log") or []
        for line in log[shown:]:
            print("   ", line)
        shown = len(log)
        if status.get("status") != "running":
            break
        time.sleep(10)
    if status.get("status") != "done" or not status.get("complete"):
        print(f"FAIL: the components did not install: {status.get('status')} "
              f"{status.get('error')} {status.get('installed')}")
        return 1
    print("components installed:", status.get("installed"))

    checks = {r["key"]: r for r in request("GET", "/system-check", timeout=180)["requirements"]}
    for key in ("ml_python", "ml", "lyrics", "pdf", "ytdlp"):
        if checks.get(key, {}).get("found") is False:
            print(f"FAIL: /system-check still reports {key} missing: {checks.get(key)}")
            return 1
    print("system check: ml, lyrics, pdf and yt-dlp found")

    tempo = request("POST", f"/jobs/{job_id}/detect-tempo",
                    json.dumps({"from_s": 0}).encode(), "application/json", timeout=600)
    print("librosa, in the components' Python: detected", tempo.get("detected_bpm"), "BPM")
    if not tempo.get("detected_bpm"):
        print("FAIL: no tempo measured")
        return 1
    beats = [0.5 * i for i in range(1, 9)]
    aligned = request("POST", f"/jobs/{job_id}/detect-beat-sync",
                      json.dumps({"beats": beats, "notes": beats}).encode(),
                      "application/json", timeout=600)
    if len(aligned.get("times") or []) != len(beats):
        print(f"FAIL: the automatic sync answered {aligned}")
        return 1
    print("automatic sync (experimental), in the components' Python: aligned",
          len(aligned["times"]), "beats")

    pdf = work / "riff.pdf"
    pdf.write_bytes(tab_pdf([
        "e|-----0-----|", "B|---1---1---|", "G|-2-------2-|",
        "D|-----------|", "A|-----------|", "E|0----------|",
    ]))
    body, ctype = multipart({}, {"files": pdf})
    converted = request("POST", "/pdf/import", body, ctype, timeout=900)
    if not converted.get("tracks"):
        print(f"FAIL: the PDF was not converted: {converted}")
        return 1
    print("PDF-to-GP5, in the components' Python: tracks", len(converted["tracks"]))

    request("POST", f"/jobs/{job_id}/separate-stems")
    stems: dict = {}
    for _ in range(30 * 6):  # 30 minutes (the model downloads on first use)
        stems = request("GET", f"/jobs/{job_id}/stems", timeout=60)
        if stems.get("status") in ("ready", "unavailable"):
            break
        time.sleep(10)
    if stems.get("status") != "ready" or not stems.get("stems"):
        print("FAIL: Demucs did not separate the recording:", stems.get("status"))
        for line in stems.get("log") or []:
            print("   ", line)
        return 1
    print("Demucs, in the components' Python: stems", stems["stems"])
    return 0


def main(exe: Path, with_components: bool = False) -> int:
    work = Path(tempfile.mkdtemp(prefix="rf-smoke-"))
    ffmpeg = exe.parent / "_internal" / "ffmpeg" / "ffmpeg.exe"
    if not ffmpeg.exists():
        print(f"FAIL: no bundled ffmpeg at {ffmpeg}")
        return 1
    gp5, wav = work / "smoke.gp5", work / "smoke.wav"
    invented_gp5(gp5)
    # A click every half second (120 BPM), so a tempo can be measured from it.
    subprocess.run([str(ffmpeg), "-nostdin", "-loglevel", "error", "-y", "-f", "lavfi",
                    "-i", "aevalsrc=0.6*sin(2*PI*880*t)*lt(mod(t\\,0.5)\\,0.03)"
                    "+0.2*sin(2*PI*220*t):s=44100:d=8", str(wav)],
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
        if not status.get("psarc_available"):
            print("FAIL: the build made no .psarc. Warnings:")
            for w in status.get("warnings") or []:
                print("  -", w)
            return 1
        report = request("GET", f"/jobs/{job['id']}/psarc-check", timeout=60)
        if not report.get("ok"):
            print("FAIL: the PSARC check found problems:", json.dumps(report)[:2000])
            return 1
        print("build completed; PSARC checked clean:", report.get("charts"))
        if with_components:
            return components_check(job["id"], work)
        return 0
    finally:
        proc.kill()


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]).resolve(), "--components" in sys.argv[2:]))
