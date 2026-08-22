"""Writing a corrected tempo map back into a Guitar Pro file.

The correction must be permanent in Guitar Pro itself, not only inside
RockForge — and it must change NOTHING else. These tests exercise both real
write routes (PyGuitarPro for the binary formats, ZIP surgery for .gp) and
assert preservation, not just that a file came out.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from rockforge.domain.errors import IngestionError
from rockforge.infrastructure.gpexport.tempo_writer import (
    TempoCorrection,
    write_tempo_corrections,
)
from rockforge.infrastructure.gpimport.parser import inspect_gp, parse_gp_track


def _make_gp5(path: Path, bars: int = 80) -> None:
    """A multi-track GP5 with techniques, a marker and an authored tempo change."""
    import guitarpro as gp

    song = gp.Song()
    song.tempo = 120
    song.title, song.artist = "T", "A"
    song.tracks = []
    for ti, (name, pitches) in enumerate(
        (("Lead", [64, 59, 55, 50, 45, 40]), ("Bass", [43, 38, 33, 28]))
    ):
        tr = gp.Track(song, ti + 1)
        tr.name = name
        tr.strings = [gp.GuitarString(i + 1, p) for i, p in enumerate(pitches)]
        tr.measures = []
        for m in range(bars):
            if m < len(song.measureHeaders):
                hdr = song.measureHeaders[m]
            else:
                hdr = gp.MeasureHeader()
                hdr.number = m + 1
                song.measureHeaders.append(hdr)
            if m == 0 and ti == 0:
                hdr.marker = gp.Marker(title="Intro")
            meas = gp.Measure(tr, hdr)
            meas.voices = [gp.Voice(meas) for _ in range(2)]
            v = meas.voices[0]
            v.beats = []
            for b in range(4):
                beat = gp.Beat(v)
                beat.duration = gp.Duration(value=4)
                note = gp.Note(beat)
                note.string = (b % len(pitches)) + 1
                note.value = (m + b) % 12
                note.effect.palmMute = b == 2
                note.effect.vibrato = b == 3
                beat.notes = [note]
                v.beats.append(beat)
            tr.measures.append(meas)
        song.tracks.append(tr)
    # A tempo change the user authored themselves, which must survive.
    if bars > 59:
        mtc = gp.MixTableChange()
        mtc.wah = gp.WahEffect.none
        mtc.hideTempo = False
        mtc.tempo = gp.MixTableItem(value=132, duration=0, allTracks=False)
        song.tracks[0].measures[59].voices[0].beats[0].effect.mixTableChange = mtc
    with open(path, "wb") as fh:
        gp.write(song, fh, version=(5, 1, 0))


_GPIF_BLOBS = {
    "Content/BinaryStylesheet": bytes(range(256)) * 4,
    "Content/PartConfiguration": b"\x00\xffOPAQUE\x01" * 30,
    "Content/LayoutConfiguration": b"LAYOUT\x00\x01\x02" * 20,
}


def _make_gp(path: Path, bars: int = 100) -> None:
    mb = "".join(f"<MasterBar><Time>4/4</Time><Bars>{i}</Bars></MasterBar>" for i in range(bars))
    br = "".join(f'<Bar id="{i}"><Voices>-1</Voices></Bar>' for i in range(bars))
    gpif = (
        '<?xml version="1.0" encoding="utf-8"?>\n<GPIF>'
        "<Score><Title>T</Title><Artist>A</Artist></Score>"
        "<MasterTrack><Automations>"
        "<Automation><Type>Tempo</Type><Linear>false</Linear><Bar>0</Bar>"
        "<Position>0</Position><Visible>true</Visible><Value>120 2</Value></Automation>"
        "<Automation><Type>Tempo</Type><Linear>false</Linear><Bar>59</Bar>"
        "<Position>0.5</Position><Visible>true</Visible><Value>132 2</Value></Automation>"
        "</Automations></MasterTrack>"
        '<Tracks><Track id="0"><Name>Guitar</Name>'
        "<InstrumentSet><Type>electricGuitar</Type></InstrumentSet><Staves><Staff><Properties>"
        '<Property name="Tuning"><Pitches>40 45 50 55 59 64</Pitches></Property>'
        "</Properties></Staff></Staves></Track></Tracks>"
        f"<MasterBars>{mb}</MasterBars><Bars>{br}</Bars>"
        "<Voices/><Beats/><Notes/><Rhythms/></GPIF>"
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("VERSION", "7.0")
        z.writestr("Content/score.gpif", gpif)
        for k, v in _GPIF_BLOBS.items():
            z.writestr(k, v)


def test_gp5_export_changes_timing_and_nothing_else(tmp_path: Path) -> None:
    src, dst = tmp_path / "o.gp5", tmp_path / "c.gp5"
    _make_gp5(src)
    before, info_b = parse_gp_track(src, 0, 0.0, 1.0), inspect_gp(src)
    original_bytes = src.read_bytes()

    write_tempo_corrections(
        src, dst, [TempoCorrection(1, 118.0), TempoCorrection(40, 116.0)]
    )

    # The user's own file is never touched.
    assert src.read_bytes() == original_bytes

    after, info_a = parse_gp_track(dst, 0, 0.0, 1.0), inspect_gp(dst)
    # Everything that is not timing survives.
    assert [(n.string, n.fret, sorted(t.value for t in n.techniques)) for n in before.notes] == \
           [(n.string, n.fret, sorted(t.value for t in n.techniques)) for n in after.notes]
    assert [t.name for t in info_b.tracks] == [t.name for t in info_a.tracks]
    assert before.tuning.offsets_from_standard() == after.tuning.offsets_from_standard()
    assert [s.name for s in before.sections] == [s.name for s in after.sections]
    # ...and the timing genuinely moved.
    assert info_a.tempo == 118
    bb = [b.time for b in before.tempo_map.beats if b.measure > 0]
    ba = [b.time for b in after.tempo_map.beats if b.measure > 0]
    assert ba[-1] > bb[-1]


def test_an_authored_tempo_change_is_preserved(tmp_path: Path) -> None:
    """A tempo change the user put in the file themselves must not be clobbered
    by ours — we only add/replace at the measures we were asked about."""
    from rockforge.infrastructure.gpimport.parser import _load, _tempo_events

    src, dst = tmp_path / "o.gp5", tmp_path / "c.gp5"
    _make_gp5(src)
    write_tempo_corrections(src, dst, [TempoCorrection(1, 118.0), TempoCorrection(40, 116.0)])
    after = {bpm for _, bpm in _tempo_events(_load(dst).tracks[0])}
    assert 132.0 in after, after          # the authored change at bar 60 survived
    assert {116.0, 118.0} <= after


def test_binary_formats_round_the_tempo_and_say_so(tmp_path: Path) -> None:
    """GP3/4/5 store tempo as an integer. The caller must be told, not quietly
    handed a different tempo than the one recommended."""
    src, dst = tmp_path / "o.gp5", tmp_path / "c.gp5"
    _make_gp5(src)
    applied = write_tempo_corrections(src, dst, [TempoCorrection(40, 119.085)])
    assert len(applied) == 1
    assert applied[0].requested_bpm == 119.085
    assert applied[0].written_bpm == 119.0
    assert applied[0].rounded is True


def test_gp_export_replaces_only_the_score_and_keeps_decimals(tmp_path: Path) -> None:
    """The .gp route copies every ZIP entry byte-for-byte and rewrites only
    Content/score.gpif, so nothing outside the tempo automation can change.
    GPIF stores tempo as a decimal, so nothing is rounded either."""
    src, dst = tmp_path / "o.gp", tmp_path / "c.gp"
    _make_gp(src)
    applied = write_tempo_corrections(
        src, dst, [TempoCorrection(1, 118.085), TempoCorrection(40, 116.25)]
    )
    assert [a.written_bpm for a in applied] == [118.085, 116.25]
    assert not any(a.rounded for a in applied)

    with zipfile.ZipFile(src) as a, zipfile.ZipFile(dst) as b:
        assert a.namelist() == b.namelist()
        assert a.read("VERSION") == b.read("VERSION")
        for k in _GPIF_BLOBS:
            assert a.read(k) == b.read(k), k
        import xml.etree.ElementTree as ET

        autos = ET.fromstring(b.read("Content/score.gpif")).find("MasterTrack/Automations")
        got = [(x.findtext("Bar"), x.findtext("Position"), x.findtext("Value"))
               for x in autos.findall("Automation")]
    assert ("0", "0", "118.085 2") in got
    assert ("39", "0", "116.25 2") in got
    # The authored MID-BAR change is a different event and is left alone.
    assert ("59", "0.5", "132 2") in got
    # Ordered by bar, as Guitar Pro writes them.
    assert [int(b_) for b_, _, _ in got] == sorted(int(b_) for b_, _, _ in got)
    assert parse_gp_track(dst, 0, 0.0, 1.0) is not None


def test_gpx_is_refused_with_a_usable_message(tmp_path: Path) -> None:
    """No tool on earth writes .gpx — say so and name the way out."""
    src = tmp_path / "song.gpx"
    src.write_bytes(b"BCFZfake")
    with pytest.raises(IngestionError, match="GP5 or GP7"):
        write_tempo_corrections(src, tmp_path / "o.gpx", [TempoCorrection(1, 120.0)])


def test_bad_corrections_are_rejected(tmp_path: Path) -> None:
    src, dst = tmp_path / "o.gp5", tmp_path / "c.gp5"
    _make_gp5(src, bars=8)
    with pytest.raises(IngestionError, match="no tempo corrections"):
        write_tempo_corrections(src, dst, [])
    with pytest.raises(IngestionError, match="measure must be"):
        write_tempo_corrections(src, dst, [TempoCorrection(0, 120.0)])
    with pytest.raises(IngestionError, match="implausible tempo"):
        write_tempo_corrections(src, dst, [TempoCorrection(2, 1000.0)])
    # A measure past the end of the song has no beat to attach to.
    with pytest.raises(IngestionError, match="no beat"):
        write_tempo_corrections(src, dst, [TempoCorrection(500, 120.0)])
    assert not dst.exists()  # nothing half-written is left behind
