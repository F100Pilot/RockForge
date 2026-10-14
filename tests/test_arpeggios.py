"""Arpeggios: single notes let ring across one chord shape, drawn by Rocksmith
as a shape over them — an "-arp" chord template in a hand shape (the SNG's
Fingerprints2), as Rocksmith2014.NET converts it (ChordTemplate.IsArpeggio,
XmlToSngLevel partitioning the hand shapes, XmlToSngNote's Arpeggio mask).

Guitar Pro carries no arpeggio marking a chart can use, so they are derived
(``chords.arpeggio_spans``); these tests pin what counts as one.
"""

from __future__ import annotations

from rockforge.domain.arrangement import Arrangement, ArrangementKind, Section, SongMetadata
from rockforge.domain.chords import arpeggio_spans
from rockforge.domain.music import Beat, TabNote, Technique, TempoMap, Tuning
from rockforge.infrastructure.packaging.psarc.sng import (
    CHORD_MASK_ARPEGGIO,
    NOTE_MASK_ARPEGGIO,
    from_arrangement,
    read_sng,
    write_sng,
)
from rockforge.infrastructure.packaging.psarc.sng_build import _chart_hand_shapes
from rockforge.infrastructure.packaging.psarc.verify import check_sng
from rockforge.infrastructure.rsxml.writer import render_arrangement

RING = frozenset({Technique.LET_RING})
C_SHAPE = ((1, 3), (2, 2), (3, 0), (4, 1))  # C major, string by string


def _c_arpeggio(t0: float = 10.0, step: float = 0.25, **kw: object) -> list[TabNote]:
    return [TabNote(s, f, t0 + k * step, 0.5, RING, **kw)  # type: ignore[arg-type]
            for k, (s, f) in enumerate(C_SHAPE)]


def _groups(notes: list[TabNote]) -> list[list[TabNote]]:
    out: dict[float, list[TabNote]] = {}
    for n in sorted(notes, key=lambda n: n.time):
        out.setdefault(n.time, []).append(n)
    return list(out.values())


def _chart(notes: list[TabNote]) -> Arrangement:
    beats = tuple(Beat(time=round(1.0 + 0.5 * i, 3), measure=(i // 4 + 1) if i % 4 == 0 else -1)
                  for i in range(70))
    return Arrangement(
        kind=ArrangementKind.LEAD, metadata=SongMetadata(title="A", artist="B", song_length=36.0),
        tuning=Tuning(), notes=sorted(notes, key=lambda n: (n.time, n.string)),
        sections=[Section("verse", 1.0, 1)],
        tempo_map=TempoMap(beats=beats, average_bpm=120.0),
    )


def _melody() -> list[TabNote]:
    return [TabNote(5, 5 + k % 3, 2.0 + 0.5 * k, 0.2) for k in range(14)]


def test_single_notes_let_ring_across_a_shape_are_an_arpeggio() -> None:
    notes = [*_c_arpeggio(), TabNote(0, 3, 12.0, 0.3)]
    spans = arpeggio_spans(_groups(notes))
    assert spans == [(0, 3, (-1, 3, 2, 0, 1, -1), 10.75 + 0.5 + 0.001)]
    # ... and the shape stops at the next note when the last one rings on.
    tight = [*_c_arpeggio(), TabNote(0, 3, 11.0, 0.3)]
    assert arpeggio_spans(_groups(tight))[0][3] == 11.0


def test_what_is_not_an_arpeggio() -> None:
    ring_less = [TabNote(s, f, 10.0 + k * 0.25, 0.5) for k, (s, f) in enumerate(C_SHAPE)]
    cases = {
        "not let ring": ring_less,
        "two notes": _c_arpeggio()[:2],
        "a slide moves the hand": _c_arpeggio(slide_to_fret=5),
        "one string, three notes": [TabNote(2, 2, 10.0 + k * 0.25, 0.2, RING) for k in range(3)],
        "wider than one hand": [TabNote(1, 3, 10.0, 0.2, RING), TabNote(2, 5, 10.25, 0.2, RING),
                                TabNote(3, 7, 10.5, 0.2, RING)],
        "a rest between": [*_c_arpeggio()[:2], *_c_arpeggio(13.0)[2:]],
    }
    for why, notes in cases.items():
        assert arpeggio_spans(_groups(notes)) == [], why


def test_a_chord_or_another_fret_on_a_string_ends_it() -> None:
    chord = [TabNote(0, 3, 10.5, 0.2), TabNote(1, 3, 10.5, 0.2)]
    notes = [*_c_arpeggio()[:2], *chord, *[TabNote(s, f, 11.0 + k * 0.25, 0.5, RING)
                                           for k, (s, f) in enumerate(C_SHAPE)]]
    assert [(a, b) for a, b, _, _ in arpeggio_spans(_groups(notes))] == [(3, 6)]
    moved = [*_c_arpeggio(), TabNote(1, 5, 11.0, 0.5, RING), TabNote(2, 5, 11.25, 0.5, RING),
             TabNote(3, 5, 11.5, 0.5, RING)]
    assert [(a, b) for a, b, _, _ in arpeggio_spans(_groups(moved))] == [(0, 3), (4, 6)]
    # Within the same hand: the A string from fret 3 to 2 is another shape.
    near = [*_c_arpeggio(), TabNote(1, 2, 11.0, 0.5, RING), TabNote(2, 3, 11.25, 0.5, RING),
            TabNote(3, 2, 11.5, 0.5, RING)]
    assert [(a, b) for a, b, _, _ in arpeggio_spans(_groups(near))] == [(0, 3), (4, 6)]


def test_the_xml_writes_an_arp_template_and_its_hand_shape() -> None:
    song = render_arrangement(_chart([*_melody(), *_c_arpeggio(20.0)]))
    templates = song.findall("chordTemplates/chordTemplate")
    arp = next(i for i, t in enumerate(templates) if t.get("displayName") == "C-arp")
    assert templates[arp].get("chordName") == "C"
    assert [templates[arp].get(f"fret{i}") for i in range(6)] == ["-1", "3", "2", "0", "1", "-1"]
    shape = next(h for h in song.iter("handShape") if h.get("chordId") == str(arp))
    assert (shape.get("startTime"), shape.get("endTime")) == ("20.000", "21.251")


def test_the_sng_carries_it_in_fingerprints2_with_the_arpeggio_mask() -> None:
    model = from_arrangement(_chart([*_melody(), *_c_arpeggio(20.0)]))
    arp = [i for i, t in enumerate(model.chord_templates) if t.mask & CHORD_MASK_ARPEGGIO]
    assert len(arp) == 1
    template = model.chord_templates[arp[0]]
    assert template.name == "C" and template.fingers[1:5] == (3, 2, -1, 1)
    for model_ in (model, read_sng(write_sng(model))):
        assert check_sng(model_) == []
        # The full chart: every level showing the arpeggio's first note.
        full = [lv for lv in model_.arrangements
                if any(abs(n.time - 20.0) < 1e-6 for n in lv.notes)]
        assert full
        for lv in full:
            assert [(f.chord_id, round(f.start_time, 3)) for f in lv.fingerprints2] == [
                (arp[0], 20.0)]
            for n in lv.notes:
                inside = 20.0 <= n.time < 21.251
                assert (n.fingerprint_id[1] == 0) == inside
                assert bool(n.mask & NOTE_MASK_ARPEGGIO) == inside
                assert n.fingerprint_id[0] == -1


def test_a_phrase_and_an_anchor_stay_out_of_an_arpeggio() -> None:
    notes = [*_melody(), *_c_arpeggio(20.0)]
    assert (20.0, 21.251) in [(round(a, 3), round(b, 3))
                              for a, b in _chart_hand_shapes(_groups(notes))]
    # A hand window that the first notes of the arpeggio still fit would move
    # in the middle of it (fret 1 is outside 2..5): it moves at its start.
    for before in (2, 5):
        chart = _chart([TabNote(5, before, 19.5, 0.2), *_c_arpeggio(20.0)])
        song = render_arrangement(chart)
        assert not [a for a in song.iter("anchor") if 20.0 < float(a.get("time")) < 21.251]
        for lv in from_arrangement(chart).arrangements:
            assert not [a for a in lv.anchors if 20.0 < a.start_time < 21.251]
    # Opening on an open string, which places no anchor of its own: the hand
    # still moves where the arpeggio starts, not at its first fretted note.
    opening = [TabNote(3, 0, 20.0, 0.5, RING), TabNote(1, 3, 20.25, 0.5, RING),
               TabNote(2, 2, 20.5, 0.5, RING), TabNote(4, 1, 20.75, 0.5, RING)]
    chart = _chart([TabNote(5, 9, 19.5, 0.2), *opening])
    for lv in from_arrangement(chart).arrangements:
        assert not [a for a in lv.anchors if 20.0 < a.start_time < 21.251]
