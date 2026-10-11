"""A PDF or a picture of the tab -> GP5, through PDF-to-GP5's converter (the [pdf] extra)."""

from __future__ import annotations

import pytest

from rockforge import i18n
from rockforge.infrastructure.gpimport import pdf_import


def tab_pdf(lines: list[str]) -> bytes:
    """A one-page PDF with ``lines`` in Courier, as a tab printed from a .txt
    looks — written by hand so the tests need no PDF library."""
    text = "".join(f"({line}) Tj T* " for line in lines)
    stream = f"BT /F1 10 Tf 11.5 TL 40 780 Td {text}ET".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1, xref,
    )
    return bytes(out)


# An invented riff, not a real song.
RIFF = [
    "Title: Invented Riff",
    "",
    "e|-----0-----|-----3-----|",
    "B|---1---1---|---0---0---|",
    "G|-2-------2-|-0-------0-|",
    "D|-----------|-----------|",
    "A|-----------|-----------|",
    "E|0----------|3----------|",
]


def test_the_kind_of_file_comes_from_its_bytes_not_its_name() -> None:
    assert pdf_import.file_kind(b"%PDF-1.7\n...") == "pdf"
    assert pdf_import.file_kind(b"\n" * 100 + b"%PDF-1.4") == "pdf"  # within the first 1024 bytes
    assert pdf_import.file_kind(b"\x89PNG\r\n\x1a\n....") == "image"
    assert pdf_import.file_kind(b"\xff\xd8\xff\xe0....") == "image"
    assert pdf_import.file_kind(b"RIFF\x00\x00\x00\x00WEBPVP8 ") == "image"
    assert pdf_import.file_kind(b"PK\x03\x04 a .gp file") is None
    assert pdf_import.file_kind(b"x" * 2000 + b"%PDF-") is None


def test_without_the_extra_it_says_how_to_install_it(monkeypatch) -> None:
    monkeypatch.setattr(pdf_import, "available", lambda: False)
    with pytest.raises(pdf_import.PdfConverterMissingError) as err:
        pdf_import.convert([("tab.pdf", tab_pdf(RIFF))])
    assert ".[pdf]" in str(err.value)


needs_converter = pytest.mark.skipif(
    not pdf_import.available(), reason="the [pdf] extra (PDF-to-GP5) is not installed"
)


@needs_converter
def test_a_text_tab_in_a_pdf_becomes_a_gp5_with_its_notes(tmp_path) -> None:
    from rockforge.infrastructure.gpimport.parser import inspect_gp, parse_gp_track

    result = pdf_import.convert([("riff.pdf", tab_pdf(RIFF))])
    assert result.gp5.startswith(b"\x18FICHIER GUITAR PRO v5")
    assert result.title == "Invented Riff"
    dest = tmp_path / "riff.gp5"
    dest.write_bytes(result.gp5)
    info = inspect_gp(dest)
    assert [t.string_count for t in info.tracks] == [6]
    notes = parse_gp_track(dest, 0).notes
    # RockForge numbers strings from the low E (0); the riff opens on the open low E.
    assert (notes[0].string, notes[0].fret) == (0, 0)
    assert {(n.string, n.fret) for n in notes} >= {(0, 0), (3, 2), (4, 1), (5, 0), (0, 3), (5, 3)}


@needs_converter
def test_the_converter_answers_in_the_users_language() -> None:
    token = i18n.use("en")
    try:
        with pytest.raises(pdf_import.PdfImportError) as english:
            pdf_import.convert([("empty.pdf", tab_pdf(["no tab here"]))])
    finally:
        i18n.reset(token)
    token = i18n.use("pt")
    try:
        with pytest.raises(pdf_import.PdfImportError) as portuguese:
            pdf_import.convert([("empty.pdf", tab_pdf(["no tab here"]))])
    finally:
        i18n.reset(token)
    assert str(english.value) != str(portuguese.value)
