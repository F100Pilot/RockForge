"""Hand shapes (fingerprints) over hundreds of random charts.

The game reads a hand shape for every chord it draws fingers on, at every
Dynamic Difficulty level, and dereferences it while scoring — so a shape that
points at a chord template that does not exist, covers no note, overlaps the
next one or disagrees with its notes is the kind of thing that crashes in Riff
Repeater rather than at load. These are the invariants DLC Builder's own
conversion produces (XmlToSng.fs ``convertHandshape``, Utils.fs
``findFingerPrintId``) and the two hand-made CDLC the user sent obey — held in
``psarc/verify.py``'s ``check_sng``, the checker the app runs on the user's own
file, together with every other rule a chart must keep — checked
level by level on random charts mixing chords, single notes, slides, long
sustains and rests, and again after a write/read round trip.
"""

import random
import xml.etree.ElementTree as ET

import pytest

from rockforge.domain.arrangement import Arrangement, ArrangementKind, Section, SongMetadata
from rockforge.domain.music import Beat, TabNote, Technique, TempoMap, Tuning
from rockforge.infrastructure.packaging.psarc.sng import from_arrangement, read_sng, write_sng
from rockforge.infrastructure.packaging.psarc.verify import check_sng
from rockforge.infrastructure.rsxml.writer import render_arrangement

SHAPES = [
    (3, 5, 5, -1, -1, -1), (-1, 3, 5, 5, -1, -1), (0, 2, 2, 1, 0, 0), (-1, 3, 2, 0, 1, 0),
    (1, 3, 3, 2, 1, 1), (-1, 7, 7, -1, -1, -1), (-1, 5, -1, 7, -1, -1), (5, 7, -1, -1, -1, -1),
    (-1, 6, 8, 8, 8, 6), (12, 14, 14, -1, -1, -1), (-1, -1, 0, 2, 3, 2), (0, 0, -1, -1, -1, -1),
]


def _random_chart(seed: int) -> Arrangement:
    rnd = random.Random(seed)
    length = rnd.uniform(20, 90)
    step = rnd.choice([0.4, 0.5, 0.6])
    beats = tuple(Beat(time=round(1.0 + step * i, 6), measure=(i // 4 + 1) if i % 4 == 0 else -1)
                  for i in range(int((length - 1) / step) + 1))
    end = beats[-1].time - 0.05
    notes: list[TabNote] = []
    t = 1.0 + rnd.choice([0.0, 0.25, 2.0])
    shape = rnd.choice(SHAPES)
    while t < end:
        roll = rnd.random()
        if roll < 0.15:
            t += rnd.choice([0.5, 1.2, 3.0])  # a rest, sometimes past the 1 s break
            continue
        if roll < 0.25:
            shape = rnd.choice(SHAPES)  # change chord
        sustain = rnd.choice([0.0, 0.0, 0.1, 0.3, 1.0, 2.5])
        if roll < 0.75:  # a chord (repeated runs are common: shape is sticky)
            tech: frozenset[Technique] = rnd.choice(
                [frozenset(), frozenset(), frozenset({Technique.PALM_MUTE})])
            for s, f in enumerate(shape):
                if f >= 0:
                    notes.append(TabNote(s, f, round(t, 4), sustain, tech))
        else:  # a single note, maybe sliding
            s, f = rnd.randrange(6), rnd.randrange(0, 15)
            slide = f + rnd.choice([2, -2]) if rnd.random() < 0.2 and f > 2 else None
            notes.append(TabNote(s, f, round(t, 4), max(sustain, 0.2) if slide else sustain,
                                 frozenset({Technique.SLIDE}) if slide else frozenset(),
                                 slide_to_fret=slide))
        t += rnd.choice([0.15, 0.25, 0.25, 0.5, 0.75])
    sections = [Section("riff", 1.0, 1)]
    if rnd.random() < 0.5:
        sections.append(Section("solo", round(length / 2, 2), 1))
    return Arrangement(
        kind=rnd.choice([ArrangementKind.LEAD, ArrangementKind.RHYTHM]),
        metadata=SongMetadata(title="F", artist="Z", song_length=length + 2),
        tuning=Tuning(), notes=notes, sections=sections,
        tempo_map=TempoMap(beats=beats, average_bpm=60 / step),
    )


def _check_levels(model) -> None:
    # The rules live in ONE place, the checker "Verificar PSARC" runs on the
    # user's file — so the builder and the checker are tested against each other.
    assert check_sng(model) == []
    for lvl in model.arrangements:
        assert lvl.fingerprints2 == []
    for ct in model.chord_templates:
        # -1 on disk is the byte 0xFF, which read_sng hands back unsigned.
        assert all(f in (-1, 255) or 1 <= f <= 4 for f in ct.fingers)
        assert len(ct.name.encode("utf-8")) < 32


@pytest.mark.parametrize("dd", [True, False])
def test_hand_shapes_hold_on_hundreds_of_random_charts(dd: bool) -> None:
    for seed in range(150):
        model = from_arrangement(_random_chart(seed), dynamic_difficulty=dd)
        _check_levels(model)
        again = read_sng(write_sng(model))
        _check_levels(again)
        for a, b in zip(model.arrangements, again.arrangements, strict=True):
            assert [(f.chord_id, round(f.start_time, 4), round(f.end_time, 4))
                    for f in a.fingerprints1] == [
                (f.chord_id, round(f.start_time, 4), round(f.end_time, 4)) for f in b.fingerprints1]
            assert [n.fingerprint_id for n in a.notes] == [n.fingerprint_id for n in b.notes]


def test_the_xml_hand_shapes_are_the_full_charts_own() -> None:
    """DLC Builder builds its SNG from the XML's shapes: they must be the same
    as the native full-chart level's, and as valid."""
    for seed in range(80):
        arr = _random_chart(seed)
        song = render_arrangement(arr)
        n_templates = len(song.findall("chordTemplates/chordTemplate"))
        xml_shapes = [(int(h.get("chordId")), float(h.get("startTime")), float(h.get("endTime")))
                      for h in song.findall("levels/level/handShapes/handShape")]
        chords = [float(c.get("time")) for c in song.findall("levels/level/chords/chord")]
        for cid, start, end in xml_shapes:
            assert 0 <= cid < n_templates and end > start
        for a, b in zip(xml_shapes, xml_shapes[1:], strict=False):
            assert a[2] <= b[1] + 1e-6
        for t in chords:
            assert any(s <= t + 1e-6 and t < e for _, s, e in xml_shapes), "a chord with no shape"
        full = from_arrangement(arr, dynamic_difficulty=False).arrangements[0].fingerprints1
        assert [(round(s, 3), round(e, 3)) for _, s, e in xml_shapes] == [
            (round(f.start_time, 3), round(f.end_time, 3)) for f in full]
        assert ET.tostring(song)  # serialises
