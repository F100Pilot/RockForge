"""RockForge."""

# The one place the version is written (docs/VERSIONING.md), in Semantic
# Versioning: MAJOR.MINOR.PATCH[-dev|alpha|beta|rc.N]. pyproject.toml reads it
# (as PEP 440: "0.10.0-beta.12" is "0.10.0b12"); the installer's copy and the
# changelogs are kept in step by tests/test_release_version.py, and
# tools/bump_version.py changes them all together.
__version__ = "0.11.1-beta.4"
