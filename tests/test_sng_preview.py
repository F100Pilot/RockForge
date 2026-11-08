"""The built .sng shown on the 3D highway (psarc/preview.py): what the game reads."""

from pathlib import Path

import pytest

pytest.importorskip("cryptography")

from rockforge.domain.arrangement import Arrangement, ArrangementKind, Section, SongMetadata
from rockforge.domain.music import Beat, TabNote, TempoMap, Tuning
from rockforge.infrastructure.packaging.psarc import preview
from rockforge.infrastructure.packaging.psarc.packer import NativePsarcPacker
from rockforge.infrastructure.packaging.psarc.sng import from_arrangement, read_sng, write_sng
from rockforge.infrastructure.rsxml.vocals import VocalEvent


def _chart(kind: ArrangementKind = ArrangementKind.LEAD) -> Arrangement:
    """A busy riff (so dynamic difficulty has levels to thin), a repeated chord
    (high density) and a slide."""
    beats = tuple(Beat(time=round(1.0 + 0.5 * i, 3), measure=(i // 4 + 1) if i % 4 == 0 else -1)
                  for i in range(80))
    notes: list[TabNote] = []
    for k in range(60):
        t = 2.0 + k * 0.25
        notes.append(TabNote(k % 3, 2 + k % 5, t, 0.0))
    for k in range(4):  # the same power chord four times, close together
        t = 18.0 + k * 0.25
        notes += [TabNote(0, 3, t, 0.0), TabNote(1, 5, t, 0.0)]
    notes.append(TabNote(1, 5, 20.0, 0.5, slide_to_fret=7))
    return Arrangement(
        kind=kind, metadata=SongMetadata(title="Song", artist="Artist", song_length=42.0),
        tuning=Tuning(), notes=notes, sections=[Section("verse", 1.0, 1)],
        tempo_map=TempoMap(beats=beats, average_bpm=120.0),
    )


def test_each_level_shows_the_notes_the_sng_holds_there() -> None:
    model = read_sng(write_sng(from_arrangement(_chart())))
    top = preview.level_preview(model, len(model.arrangements) - 1)
    low = preview.level_preview(model, 0)
    assert top["levels"] == len(model.arrangements) > 1
    assert top["level"] == top["levels"] - 1
    assert len(low["notes"]) < len(top["notes"])  # the lower level is thinner
    # The hardest level is the whole chart: a phrase leaves the levels above its
    # own ceiling and is played at its ceiling, not dropped (the SNG's top level
    # alone holds only the phrases whose ceiling is the song's).
    assert len(top["notes"]) == len(_chart().notes)
    assert len(model.arrangements[-1].notes) < len(_chart().notes)
    chord = [n for n in top["notes"] if n["chord"]]
    assert {(n["string"], n["fret"]) for n in chord} == {(0, 3), (1, 5)}
    assert [n["high_density"] for n in chord[::2]] == [False, True, True, True]
    slide = next(n for n in top["notes"] if n["time"] == 20.0)
    assert slide["slide_to"] == 7 and "slide" in slide["techniques"]
    assert top["anchors"] and all(1 <= a["fret"] <= 24 for a in top["anchors"])
    assert top["bars"][0] == {"time": 1.0, "measure": 1}
    assert len(top["beats"]) == 80
    # a level past the last is the last; below 0 is the first
    assert preview.level_preview(model, 999)["level"] == top["level"]
    assert preview.level_preview(model, -5)["level"] == 0


def test_the_charts_of_a_psarc_are_read_by_kind_and_the_vocals_left_out(tmp_path: Path) -> None:
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"RIFF....WAVEfmt ")
    psarc = NativePsarcPacker().package(
        [_chart(ArrangementKind.LEAD), _chart(ArrangementKind.ALTERNATE_LEAD),
         _chart(ArrangementKind.RHYTHM)],
        audio, tmp_path / "bundle", vocals=[VocalEvent(2.0, 0.5, "la+")],
    ).psarc_path
    assert psarc is not None
    charts = preview.read_charts(psarc)
    assert sorted(charts) == ["Alternate Lead", "Lead", "Rhythm"]
    assert preview.kind_of_asset("artistsong_combo") == "Combined"
    assert preview.kind_of_asset("artistsong_bass") == "Bass"
    assert preview.kind_of_asset("artistsong_vocals") is None
