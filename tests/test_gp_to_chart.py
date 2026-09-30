"""A GP5 all the way to the Rocksmith chart: arrangement XML and SNG.

The score is the kind of passage that went wrong on real songs (Daughtry
"September" bar 4, Eagles "Hotel California"): a note held, then bent ½ and
released ON THE TIE and pulled off; a repeat with 1st/2nd endings; a grace note
hammered into its note; a pinch harmonic; let ring. It goes through the real GP
pipeline and packager (only the audio stages are fakes), and the SNG is built
from the written XML the way the PSARC packer does, then written and read back.

Times: 120 BPM, 2 s a bar, bar 1 at 2.0 s (the minimum lead-in).
Played bars: 1 2 1 3 (|: 1 [1. 2 :| [2. 3).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import guitarpro as gp
import pytest

from rockforge.application.gp_pipeline import GenerateFromGpUseCase, GpJobSpec
from rockforge.domain.arrangement import SongMetadata
from rockforge.infrastructure.packaging.dlcbuilder import DlcBuilderPackager
from rockforge.infrastructure.packaging.psarc.sng import (
    NOTE_MASK_BEND,
    NOTE_MASK_HAMMERON,
    NOTE_MASK_PINCHHARMONIC,
    NOTE_MASK_PULLOFF,
    from_arrangement,
    read_sng,
    write_sng,
)
from rockforge.infrastructure.rsxml.reader import read_arrangement_xml


class _Ingestor:
    def fetch(self, source: str, workdir: Path) -> Path:
        workdir.mkdir(parents=True, exist_ok=True)
        path = workdir / "input.wav"
        path.write_bytes(b"RIFF")
        return path


class _Normalizer:
    def normalize(
        self, audio: Path, workdir: Path, offset_s: float = 0.0, pad_start_s: float = 0.0
    ) -> Path:
        return audio


def _beat(voice, value: int, dotted: bool = False, notes=(), rest: bool = False):  # noqa: ANN001, ANN202
    beat = gp.Beat(voice)
    beat.status = gp.BeatStatus.rest if rest else gp.BeatStatus.normal
    beat.duration = gp.Duration(value=value, isDotted=dotted)
    for string, fret, kind, effects in notes:
        note = gp.Note(beat)
        note.string, note.value, note.type = string, fret, kind
        for key, val in effects.items():
            setattr(note.effect, key, val)
        beat.notes.append(note)
    voice.beats.append(beat)


def _score(path: Path) -> Path:
    song = gp.Song()
    song.title, song.artist, song.tempo = "Chart", "Band", 120
    song.newMeasure()
    song.newMeasure()
    lead = song.tracks[0]
    lead.name = "Lead Guitar"
    normal, tie = gp.NoteType.normal, gp.NoteType.tie
    release = gp.BendEffect(
        type=gp.BendType.bendRelease, value=50,
        points=[gp.BendPoint(0, 0), gp.BendPoint(3, 2), gp.BendPoint(6, 2), gp.BendPoint(9, 0)],
    )
    # Bar 1 — "September" bar 4: rest, 3 held, bent ½ and released on the tie, pulled off to 1.
    v = lead.measures[0].voices[0]
    _beat(v, 2, rest=True)
    _beat(v, 8, True, [(3, 3, normal, {})])
    _beat(v, 16, True, [(3, 3, tie, {"bend": release})])
    _beat(v, 32, False, [(3, 3, tie, {"hammer": True})])
    _beat(v, 16, False, [(3, 1, normal, {})])
    _beat(v, 8, False, [(4, 2, normal, {})])
    # Bar 2 — 1st ending: a let-ring whole note.
    _beat(lead.measures[1].voices[0], 1, False, [(2, 5, normal, {"letRing": True})])
    # Bar 3 — 2nd ending: a grace note hammered into 7, a pinch harmonic, a rest.
    v = lead.measures[2].voices[0]
    grace = gp.GraceEffect(fret=5, duration=32, transition=gp.GraceEffectTransition.hammer)
    _beat(v, 4, False, [(2, 7, normal, {"grace": grace})])
    _beat(v, 4, False, [(1, 9, normal, {"harmonic": gp.PinchHarmonic()})])
    _beat(v, 2, rest=True)
    headers = song.measureHeaders
    headers[0].isRepeatOpen = True
    headers[1].repeatAlternative, headers[1].repeatClose = 1, 1
    headers[2].repeatAlternative = 2
    gp.write(song, str(path))
    return path


@pytest.fixture()
def chart(tmp_path: Path) -> tuple[ET.Element, object]:
    use_case = GenerateFromGpUseCase(
        ingestor=_Ingestor(), normalizer=_Normalizer(), packager=DlcBuilderPackager()
    )
    spec = GpJobSpec(gp_path=_score(tmp_path / "chart.gp5"), audio_source="x.wav", lead_track=0)
    result = use_case.run(spec, SongMetadata(title="Chart", artist="Band"), tmp_path / "w")
    xml_path = next(p for p in result.packaging.xml_paths if "vocals" not in p.name)
    sng = read_sng(write_sng(from_arrangement(read_arrangement_xml(xml_path))))
    return ET.parse(xml_path).getroot(), sng


def _xml_notes(root: ET.Element) -> list[ET.Element]:
    return sorted(root.iter("note"), key=lambda n: float(n.get("time", "0")))


def test_every_played_note_is_in_the_chart(chart) -> None:  # noqa: ANN001
    root, sng = chart
    # (XML times have 3 decimals: the grace note's 7.9375 s is written 7.938)
    got = [(round(float(n.get("time", "0")), 3), int(n.get("string", "0")), int(n.get("fret", "0")))
           for n in _xml_notes(root)]
    # RS strings: 0 = low E. Pass 1 of bar 1 (from 2.0 s), bar 2, pass 2 of bar 1
    # (from 6.0 s), bar 3 (from 8.0 s) with the grace note a 32nd before 7.
    assert got == [
        (3.0, 3, 3), (3.625, 3, 1), (3.75, 2, 2),
        (4.0, 4, 5),
        (7.0, 3, 3), (7.625, 3, 1), (7.75, 2, 2),
        (7.938, 4, 5), (8.0, 4, 7), (8.5, 5, 9),
    ]
    sng_notes = sng.arrangements[-1].notes
    assert [(round(n.time, 3), n.string, n.fret) for n in sng_notes] == got


def test_the_bend_on_the_tie_is_bent_and_released_on_time(chart) -> None:  # noqa: ANN001
    """The held 3 (3.0 s) bends ½ from the tie on (3.375 s) and is back by 3.52 s;
    the pull-off to 1 follows. Same in the XML and the SNG."""
    root, sng = chart
    held = next(n for n in _xml_notes(root) if float(n.get("time", "0")) == 3.0)
    assert held.get("bend") == "1" and held.get("fret") == "3"
    curve = [(round(float(b.get("time")), 3), float(b.get("step"))) for b in held.iter("bendValue")]
    assert curve[0] == (3.0, 0.0)
    assert max(step for _, step in curve) == pytest.approx(1.0)
    rise = next(t for t, step in curve if step == pytest.approx(1.0))
    assert 3.375 < rise < 3.45 and curve[-1][1] == 0.0 and curve[-1][0] <= 3.575
    pulled = next(n for n in _xml_notes(root) if float(n.get("time", "0")) == pytest.approx(3.625))
    assert pulled.get("pullOff") == "1"

    sng_held = next(n for n in sng.arrangements[-1].notes if n.time == pytest.approx(3.0))
    assert sng_held.mask & NOTE_MASK_BEND and sng_held.bend == pytest.approx(1.0)
    assert [(round(b.time, 3), b.step) for b in sng_held.bend_data] == pytest.approx(curve)
    sng_pulled = next(n for n in sng.arrangements[-1].notes if n.time == pytest.approx(3.625))
    assert sng_pulled.mask & NOTE_MASK_PULLOFF


def test_grace_note_and_pinch_harmonic(chart) -> None:  # noqa: ANN001
    root, sng = chart
    notes = {round(n.time, 4): n for n in sng.arrangements[-1].notes}
    assert notes[8.0].mask & NOTE_MASK_HAMMERON  # the grace note hammers into 7
    assert notes[8.5].mask & NOTE_MASK_PINCHHARMONIC
    xml = {round(float(n.get("time", "0")), 4): n for n in _xml_notes(root)}
    assert xml[8.0].get("hammerOn") == "1" and xml[8.5].get("harmonicPinch") == "1"
