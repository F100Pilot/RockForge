"""Typed domain errors so pipeline failures are explicit, never silent defaults."""

from __future__ import annotations


class RockForgeError(Exception):
    """Base class for all domain/pipeline errors."""


class IngestionError(RockForgeError):
    pass


class NormalizationError(RockForgeError):
    pass


class SeparationError(RockForgeError):
    pass


class TranscriptionError(RockForgeError):
    pass


class FretMappingError(RockForgeError):
    pass


class PackagingError(RockForgeError):
    pass


class FeatureDisabledError(RockForgeError):
    """Raised when a feature is disabled by configuration (e.g. YouTube ingestion)."""
