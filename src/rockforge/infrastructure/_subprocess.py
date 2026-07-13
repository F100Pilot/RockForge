"""Shared hardening for the external-CLI subprocess calls (ffmpeg, Demucs,
Banquet), so the security-relevant defaults and the error mapping live in ONE
place instead of being copy-pasted across each adapter.

``HARDENED_RUN_KWARGS`` carries the defaults every external tool must run with —
most importantly ``stdin=subprocess.DEVNULL``: a CLI launched from the Windows
``start.bat`` console otherwise inherits the console's stdin, goes interactive
and blocks forever (the "stuck at normalizing" hang). ``map_external_errors`` is
a context manager that maps the three subprocess failure modes
(FileNotFoundError / TimeoutExpired / CalledProcessError) to a caller-chosen
typed error with a consistent stderr-tail truncation.

The ``subprocess.run`` call itself stays in each adapter module (wrapped in
``map_external_errors``) rather than moving here — Demucs needs its own
CalledProcessError handling for the GPU→CPU retry, and keeping the call local
also keeps each adapter's tests able to patch its own ``subprocess.run``.
"""

from __future__ import annotations

import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

# check/capture/text are the normal "run to completion, surface output" defaults;
# stdin=DEVNULL is the anti-hang guard (see module docstring). timeout is passed
# per-call by each adapter (their ceilings differ).
HARDENED_RUN_KWARGS: dict[str, Any] = {
    "check": True,
    "capture_output": True,
    "text": True,
    "stdin": subprocess.DEVNULL,
}


@contextmanager
def map_external_errors(
    *,
    error_cls: type[Exception],
    not_installed_msg: str,
    timeout_msg: str,
    fail_msg_prefix: str,
    stderr_tail: int = 2000,
) -> Iterator[None]:
    """Map a wrapped ``subprocess.run`` call's failures to ``error_cls``.

    - ``FileNotFoundError`` (the tool isn't on PATH) → ``not_installed_msg``
    - ``TimeoutExpired`` (the run exceeded its ceiling) → ``timeout_msg``
    - ``CalledProcessError`` (non-zero exit) → ``fail_msg_prefix`` + the last
      ``stderr_tail`` chars of stderr.
    """
    try:
        yield
    except FileNotFoundError as exc:
        raise error_cls(not_installed_msg) from exc
    except subprocess.TimeoutExpired as exc:
        raise error_cls(timeout_msg) from exc
    except subprocess.CalledProcessError as exc:
        raise error_cls(f"{fail_msg_prefix}{(exc.stderr or '')[-stderr_tail:]}") from exc
