"""Tablature in a PDF or a picture -> a GP5 file, by PDF-to-GP5's converter.

The converter is the user's own PDF-to-GP5 project, installed as the package
``pdf_to_gp5`` (the ``[pdf]`` extra, pinned to a commit of that repository —
it stays the one place the conversion is developed). It is used exactly as
PDF-to-GP5 uses it itself: ``sandbox.run_isolated`` parses each file in a
short-lived child process with a hard timeout and a memory limit, because a
crafted PDF is untrusted input, and the reply comes back as JSON, never pickle.

The GP5 it writes is an ordinary Guitar Pro file, so the wizard, the job and
every later tool treat it like an upload — the Songsterr import's pattern.
Repeats are left as written: RockForge unrolls them itself (``playback.py``).
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass, field
from typing import Any

from rockforge import i18n
from rockforge.domain.errors import IngestionError

MAX_FILES = 7  # one per track: GP5's limit of melodic tracks, as PDF-to-GP5 enforces
MAX_FILE_BYTES = 10 * 1024 * 1024  # PDF-to-GP5's own limits (MAX_UPLOAD_MB, MAX_TOTAL_UPLOAD_MB)
MAX_TOTAL_BYTES = 40 * 1024 * 1024
TIMEOUT_S = 120  # without news from the child (each page read is news)
TOTAL_S = 900  # the whole conversion, however it advances
MEMORY_MB = 2048  # the child's address space; OCR (onnxruntime) needs ~1.5 GB

_IMAGE_MAGIC = (b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff")


class PdfImportError(IngestionError):
    """A file the converter refused; the message is safe to show the user."""


class PdfConverterMissingError(PdfImportError):
    """The ``[pdf]`` extra is not installed."""


@dataclass(frozen=True)
class PdfImport:
    gp5: bytes
    title: str
    artist: str
    warnings: list[str] = field(default_factory=list)
    report: dict[str, Any] = field(default_factory=dict)


def available() -> bool:
    """Whether the converter is installed, without importing it."""
    try:
        return importlib.util.find_spec("pdf_to_gp5") is not None
    except (ImportError, ValueError):
        return False


def ocr_available() -> bool:
    """Whether tab pictures can be read (PDF-to-GP5's ``[ocr]`` extra)."""
    try:
        return importlib.util.find_spec("rapidocr_onnxruntime") is not None
    except (ImportError, ValueError):
        return False


def file_kind(head: bytes) -> str | None:
    """"pdf", "image" or None, from the file's own bytes (never its name)."""
    if b"%PDF-" in head[:1024]:  # ISO 32000-1 7.5.2, as PDF-to-GP5 checks it
        return "pdf"
    if head.startswith(_IMAGE_MAGIC) or (head[:4] == b"RIFF" and head[8:12] == b"WEBP"):
        return "image"
    return None


def missing_message() -> str:
    return i18n.tr(
        'O conversor de PDF não está instalado: pip install -e ".[pdf]" (traz o PDF-to-GP5).',
        'The PDF converter is not installed: pip install -e ".[pdf]" (it brings PDF-to-GP5).',
    )


def convert(files: list[tuple[str, bytes]]) -> PdfImport:
    """Convert the files — one per track, in order — into one GP5.

    Raises ``PdfConverterMissingError`` without the extra and ``PdfImportError``
    with the converter's own message (in the user's language) otherwise.
    """
    if not available():
        raise PdfConverterMissingError(missing_message())
    from pdf_to_gp5 import i18n as converter_i18n
    from pdf_to_gp5.converter import ConversionError, ConversionOptions, TrackOptions
    from pdf_to_gp5.sandbox import ConversionTimeout, ConversionUnavailable, run_isolated

    options = ConversionOptions(tracks=tuple(TrackOptions(filename=name) for name, _ in files))
    token = converter_i18n.use(i18n.current())  # the child writes its warnings in it
    try:
        result = run_isolated(
            [data for _, data in files], options, TIMEOUT_S, MEMORY_MB, total_s=TOTAL_S
        )
    except ConversionTimeout as exc:
        raise PdfImportError(
            i18n.tr(
                "A conversão do PDF excedeu o tempo limite.", "Converting the PDF took too long."
            )
        ) from exc
    except ConversionUnavailable as exc:
        raise PdfImportError(
            i18n.tr(
                "Não foi possível iniciar a conversão. Tenta de novo.",
                "The conversion could not start. Try again.",
            )
        ) from exc
    except ConversionError as exc:
        raise PdfImportError(str(exc)) from exc
    finally:
        converter_i18n.reset(token)
    report = dict(result.report)
    return PdfImport(
        gp5=result.gp5,
        title=str(report.get("title") or ""),
        artist=str(report.get("artist") or ""),
        warnings=[str(w) for w in report.get("warnings") or []],
        report=report,
    )
