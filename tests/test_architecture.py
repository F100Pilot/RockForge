"""Guards the Clean Architecture layering rule from CLAUDE.md:
"domain/ and application/ must not import frameworks or infrastructure/."

application/ports.py defines the Protocols (and the plain data types that
cross them); it must import nothing from infrastructure/, or a "port" stops
being an abstraction and becomes tied to one concrete adapter.

gp_pipeline.py is allowed two narrow, explicitly-accepted exceptions: the GP
parser (infrastructure/gpimport/parser.py) and the lyric-format parsing
functions (infrastructure/rsxml/vocals.py) are core, deterministic, exact-
format logic with a single implementation each — not a swappable ML stage
like Packager/LyricTranscriber/AudioNormalizer, which already go through a
Protocol in ports.py. Anything beyond that allowlist is a regression of the
MAJ-7 audit fix (VocalEvent/PackagingResult used to be defined inside
infrastructure/, forcing ports.py to import them back from there).
"""

from __future__ import annotations

import ast
from pathlib import Path

APPLICATION_DIR = Path(__file__).resolve().parents[1] / "src" / "rockforge" / "application"

# module -> allowed imported names, for the one file allowed any exception at all.
_ALLOWED_INFRA_IMPORTS: dict[str, set[str]] = {
    "gp_pipeline.py": {
        "rockforge.infrastructure.gpimport.parser",
        "rockforge.infrastructure.rsxml.vocals",
    },
}


def _infrastructure_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module.startswith("rockforge.infrastructure"):
                modules.add(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("rockforge.infrastructure"):
                    modules.add(alias.name)
    return modules


def test_ports_defines_no_infrastructure_dependency() -> None:
    """ports.py holds the Protocols; a port that imports its own adapter's
    module is no longer an abstraction the adapter can be swapped behind."""
    found = _infrastructure_imports(APPLICATION_DIR / "ports.py")
    assert found == set(), f"application/ports.py must not import infrastructure/: {found}"


def test_application_modules_only_import_the_explicitly_accepted_infrastructure() -> None:
    for path in APPLICATION_DIR.glob("*.py"):
        if path.name == "__init__.py":
            continue
        found = _infrastructure_imports(path)
        allowed = _ALLOWED_INFRA_IMPORTS.get(path.name, set())
        unexpected = found - allowed
        assert not unexpected, (
            f"{path.name} imports infrastructure/ modules outside the accepted "
            f"allowlist: {unexpected} (update CLAUDE.md + _ALLOWED_INFRA_IMPORTS "
            "if this is a deliberate new exception, not a layering regression)"
        )
