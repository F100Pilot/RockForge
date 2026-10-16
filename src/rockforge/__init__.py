"""RockForge."""

# major.minor.build.revision (unidade.decimal.centésima.milésima). Single source
# of truth: the API (FastAPI `version` + `GET /version`) and the web UI header
# read this. Bump the last part for a fix, the third for a feature.
__version__ = "0.10.0b9"
