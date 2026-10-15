"""Run PDF-to-GP5's converter for RockForge in ANOTHER Python.

The `.exe` cannot import ``pdf_to_gp5`` (a frozen app sees only its own
bundle), so ``pdf_import.convert`` hands the work to the interpreter the
components installer set up (``ml_python``) and runs this script there. It
imports nothing from RockForge — that interpreter has never heard of it — and
calls the converter exactly as ``pdf_import`` does in-process: each file is
parsed in a sandboxed child (``run_isolated``), the GP5 is written to the path
asked for, and one line of JSON says how it went.

Usage: python _pdf_runner.py <request.json>
  request: {"files": [{"name", "path"}], "out", "lang", "timeout", "memory", "total"}
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    request = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    from pdf_to_gp5 import i18n as converter_i18n
    from pdf_to_gp5.converter import ConversionError, ConversionOptions, TrackOptions
    from pdf_to_gp5.sandbox import ConversionTimeout, ConversionUnavailable, run_isolated

    files = request["files"]
    options = ConversionOptions(tracks=tuple(TrackOptions(filename=f["name"]) for f in files))
    data = [Path(f["path"]).read_bytes() for f in files]
    token = converter_i18n.use(request.get("lang") or "en")
    try:
        result = run_isolated(
            data, options, request["timeout"], request["memory"], total_s=request["total"]
        )
    except ConversionTimeout:
        answer: dict[str, object] = {"error": "timeout"}
    except ConversionUnavailable:
        answer = {"error": "unavailable"}
    except ConversionError as exc:
        answer = {"error": "conversion", "message": str(exc)}
    else:
        Path(request["out"]).write_bytes(result.gp5)
        answer = {"report": result.report}
    finally:
        converter_i18n.reset(token)
    print(json.dumps(answer, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
