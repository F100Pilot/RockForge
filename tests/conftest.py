"""Shared test setup.

Starlette's TestClient sends ``Host: testserver``, which the production Host
allowlist (``ROCKFORGE_ALLOWED_HOSTS``, see ``app._verify_host``) rightly
refuses. Set before any test imports ``rockforge.config``, and kept across the
``importlib.reload(config)`` the API tests do, since they re-read the
environment.
"""

import os

# Tests never reach the install counter's server; the ones about it set a URL.
os.environ.setdefault("ROCKFORGE_INSTALL_COUNTER_URL", "")
os.environ.setdefault("ROCKFORGE_ALLOWED_HOSTS", "localhost,127.0.0.1,::1,testserver")
