"""Typed domain errors so pipeline failures are explicit, never silent defaults.

When to raise which (the codebase's convention — follow it in new code):

- A **pipeline-stage adapter** (an ``application.ports`` port implementation:
  ingestion, normalization, separation, packaging, transcription) raises the
  matching ``RockForgeError`` subclass below, so the use case / API can map the
  stage that failed to a clear job error and an HTTP status. This is the layer
  the outside world drives, so its failures must be typed and catchable by
  stage.

- A **pure domain invariant** (``domain/`` — an impossible ``Tuning`` /
  ``TabNote`` / ``TempoMap``) and a **binary-format parser/writer** (the
  ``packaging/psarc`` SNG/container/crypto codecs, ported from a fixed
  spec) raise a bare ``ValueError``. These are programmer-error / corrupt-input
  guards on internal data, not a swappable pipeline stage — a caught, per-stage
  typed error buys nothing there, and a ``ValueError`` reads correctly as "this
  value is invalid". Mirrors how the Python stdlib's own parsers behave.

So: crossing a port boundary → typed ``RockForgeError``; asserting an internal
data/format invariant → ``ValueError``.
"""

from __future__ import annotations


class RockForgeError(Exception):
    """Base class for all domain/pipeline errors."""


class IngestionError(RockForgeError):
    pass


class NormalizationError(RockForgeError):
    pass


class SeparationError(RockForgeError):
    pass


class PackagingError(RockForgeError):
    pass
