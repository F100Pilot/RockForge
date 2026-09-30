"""The TLS trust used by every outbound HTTPS request (stdlib ``urllib``).

Python's default context trusts only the certificates the operating system's
store already HOLDS. Windows installs root certificates lazily — its own
networking fetches a missing root the first time a site needs it, but Python
only enumerates what is installed and never triggers that — so a machine whose
store lacks a current root while still carrying an old expired cross-signed
one (the classic case: Let's Encrypt's ISRG Root X1 missing, its expired
"DST Root CA X3" path present) refuses a perfectly valid site with
``CERTIFICATE_VERIFY_FAILED: certificate has expired``, while a site on a
different chain works. A user hit exactly that: the album lookup worked and
the Songsterr import did not, on the same machine.

The context therefore trusts the system store PLUS ``certifi`` (Mozilla's
current roots): certifi supplies the root the machine never installed, and the
system store keeps what only it can have — the root an antivirus or a company
proxy installs to inspect HTTPS, which certifi alone would reject. OpenSSL
prefers a time-valid issuer when several share a name, so the expired copy
stops winning. Verification stays ON — this only adds trusted roots, never
turns checking off. Without ``certifi`` (a core dependency, so only a broken
install) it is the system default, as before.
"""

from __future__ import annotations

import ssl
import urllib.error
from functools import cache

from rockforge.i18n import tr


@cache
def ssl_context() -> ssl.SSLContext:
    """The context every outbound HTTPS request uses: the system roots plus certifi's."""
    context = ssl.create_default_context()
    try:
        import certifi
    except ImportError:
        return context
    context.load_verify_locations(cafile=certifi.where())
    return context


def is_certificate_error(exc: BaseException) -> bool:
    """Whether a failed request failed on the server's certificate."""
    reason = exc.reason if isinstance(exc, urllib.error.URLError) else exc
    # ``requests`` wraps the ssl error twice over; its text still names it.
    return isinstance(reason, ssl.SSLCertVerificationError) or (
        "CERTIFICATE_VERIFY_FAILED" in str(exc)
    )


def network_error_message(exc: BaseException, service: str) -> str:
    """A user-facing sentence for a request that never got an answer."""
    if is_certificate_error(exc):
        return tr(
            f"a ligação segura ao {service} foi recusada: o certificado não foi "
            "aceite. Confirma que a data e a hora do computador estão certas e "
            "que o antivírus não está a inspecionar ligações HTTPS; se continuar, "
            "atualiza os certificados com pip install --upgrade certifi "
            f"({exc})",
            f"the secure connection to {service} was refused: its certificate was "
            "not accepted. Check that the computer's date and time are right and "
            "that the antivirus is not inspecting HTTPS connections; if it goes on, "
            "update the certificates with pip install --upgrade certifi "
            f"({exc})",
        )
    return tr(f"não consegui contactar o {service} ({exc})", f"could not reach {service} ({exc})")
