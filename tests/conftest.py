"""Shared test setup.

Starlette's TestClient sends ``Host: testserver``, which the production Host
allowlist (``ROCKFORGE_ALLOWED_HOSTS``, see ``app._verify_host``) rightly
refuses. Set before any test imports ``rockforge.config``, and kept across the
``importlib.reload(config)`` the API tests do, since they re-read the
environment.
"""

import os

os.environ.setdefault("ROCKFORGE_ALLOWED_HOSTS", "localhost,127.0.0.1,::1,testserver")
