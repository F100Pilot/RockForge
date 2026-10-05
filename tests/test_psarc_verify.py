"""The PSARC check ("Verificar PSARC") and the copy into the game's dlc folder."""

from dataclasses import replace
from pathlib import Path

import pytest

pytest.importorskip("cryptography")

from rockforge.domain.arrangement import Arrangement, ArrangementKind, Section, SongMetadata
from rockforge.domain.music import Beat, TabNote, TempoMap, Tuning
from rockforge.infrastructure import game_install
from rockforge.infrastructure.packaging.psarc import container, crypto
from rockforge.infrastructure.packaging.psarc.packer import NativePsarcPacker
from rockforge.infrastructure.packaging.psarc.sng import (
    SngTone,
    SngVocal,
    from_arrangement,
    read_sng,
    write_sng,
)
from rockforge.infrastructure.packaging.psarc.verify import check_sng, describe, verify_psarc
from rockforge.infrastructure.rsxml.vocals import VocalEvent


def _chart(kind: ArrangementKind = ArrangementKind.LEAD) -> Arrangement:
    """Chords, single notes and a slide over two sections — every structure the
    checker looks at."""
    beats = tuple(Beat(time=round(1.0 + 0.5 * i, 3), measure=(i // 4 + 1) if i % 4 == 0 else -1)
                  for i in range(80))
    notes: list[TabNote] = []
    for k in range(30):
        t = 2.0 + k * 1.2
        if k % 3 == 0:
            notes += [TabNote(s, f, t, 0.4) for s, f in ((0, 3), (1, 5), (2, 5))]
        elif k % 7 == 1:
            notes.append(TabNote(1, 5, t, 0.5, slide_to_fret=7))
        else:
            notes.append(TabNote(k % 6, 2 + k % 9, t, 0.2))
    return Arrangement(
        kind=kind, metadata=SongMetadata(title="Song", artist="Artist", song_length=42.0),
        tuning=Tuning(), notes=notes,
        sections=[Section("verse", 1.0, 1), Section("chorus", 20.0, 1)],
        tempo_map=TempoMap(beats=beats, average_bpm=120.0),
    )


def _model():
    return read_sng(write_sng(from_arrangement(_chart())))


def _codes(model) -> set[str]:
    return {p.code for p in check_sng(model)}


def test_a_chart_rockforge_builds_passes_every_rule() -> None:
    for dd in (True, False):
        model = from_arrangement(_chart(), dynamic_difficulty=dd)
        assert check_sng(model) == []
        assert check_sng(read_sng(write_sng(model))) == []


def test_each_rule_catches_the_fault_that_crashed_the_game() -> None:
    """Each fault planted in an otherwise sound chart is reported, by its code
    — the checker is only worth having if every rule really fires."""
    m = _model()
    top = m.arrangements[-1]
    chord_at = next(i for i, n in enumerate(top.notes) if n.chord_id >= 0)
    single_at = next(i for i, n in enumerate(top.notes) if n.chord_id < 0)

    def planted(change) -> set[str]:
        model = _model()
        change(model)
        return _codes(model)

    def note(model, i, **kw):
        lv = model.arrangements[-1]
        lv.notes[i] = replace(lv.notes[i], **kw)

    assert "note_phrase_out_of_range" in planted(
        lambda x: note(x, single_at, phrase_id=len(x.phrases)))
    assert "note_outside_its_phrase" in planted(
        lambda x: note(x, single_at, phrase_iteration_id=0))
    assert "note_anchor_mismatch" in planted(lambda x: note(
        x, single_at, anchor_fret=x.arrangements[-1].notes[single_at].anchor_fret + 3))
    assert "note_unused_byte" in planted(lambda x: note(x, single_at, tap=0))
    assert "note_handshape_mismatch" in planted(
        lambda x: note(x, chord_at, fingerprint_id=(-1, -1)))
    assert "template_pitch" in planted(lambda x: x.chord_templates.__setitem__(
        0, replace(x.chord_templates[0], notes=tuple(0 if v == -1 else v
                                                     for v in x.chord_templates[0].notes))))
    assert "phrase_without_levels" in planted(lambda x: [
        x.phrases.__setitem__(i, replace(p, max_difficulty=0)) for i, p in enumerate(x.phrases)])
    assert "phrase_out_of_range" in planted(lambda x: x.phrase_iterations.__setitem__(
        1, replace(x.phrase_iterations[1], phrase_id=99)))
    assert "section_out_of_order" in planted(lambda x: x.sections.reverse())
    assert "tone_slot" in planted(lambda x: x.tones.append(SngTone(time=5.0, tone_id=4)))
    assert "anchor_crosses_phrase" in planted(lambda x: x.arrangements[-1].anchors.__setitem__(
        0, replace(x.arrangements[-1].anchors[0], end_time=x.phrase_iterations[-1].start_time + 1)))
    assert "handshape_bad_chord" in planted(lambda x: x.arrangements[-1].fingerprints1.__setitem__(
        0, replace(x.arrangements[-1].fingerprints1[0], chord_id=99)))
    assert "vocal_note" in planted(lambda x: x.vocals.append(SngVocal(1.0, 0, 0.5, "la")))


def _package(tmp_path: Path, vocals: list[VocalEvent] | None = None) -> Path:
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"RIFF....WAVEfmt ")
    result = NativePsarcPacker().package(
        [_chart(ArrangementKind.LEAD), _chart(ArrangementKind.ALTERNATE_LEAD)],
        audio, tmp_path / "bundle", vocals=vocals,
    )
    assert result.psarc_path is not None
    return result.psarc_path


def test_a_psarc_rockforge_packs_verifies_clean(tmp_path: Path) -> None:
    psarc = _package(tmp_path, vocals=[VocalEvent(2.0, 0.5, "la+")])
    report = verify_psarc(psarc)
    assert report.ok, report.problems
    assert report.charts == ["artistsong_lead", "artistsong_lead2", "artistsong_vocals"]


def test_a_broken_archive_is_reported_not_raised(tmp_path: Path) -> None:
    psarc = _package(tmp_path)
    entries = container.unpack(psarc.read_bytes())
    entries["toolkit.version"] = b"Toolkit version: RockForge-native\n"
    del entries["appid.appid"]
    del entries["songs/bin/generic/artistsong_lead2.sng"]
    entries["songs/bin/generic/artistsong_lead.sng"] = b"\x4a\x00\x00\x00 not an sng"
    broken = tmp_path / "broken_p.psarc"
    broken.write_bytes(container.pack_entries(entries, encrypt=True))
    codes = {(p.code, p.arrangement) for p in verify_psarc(broken).problems}
    assert ("no_appid", "") in codes
    assert ("bad_toolkit_version", "") in codes
    assert ("manifest_without_sng", "artistsong_lead2") in codes
    assert ("sng_unreadable", "artistsong_lead") in codes

    junk = tmp_path / "junk_p.psarc"
    junk.write_bytes(b"not a psarc at all")
    assert [p.code for p in verify_psarc(junk).problems] == ["psarc_unreadable"]


def test_a_broken_chart_inside_the_archive_names_its_chart(tmp_path: Path) -> None:
    psarc = _package(tmp_path)
    entries = container.unpack(psarc.read_bytes())
    name = "songs/bin/generic/artistsong_lead2.sng"
    model = read_sng(crypto.unpack_sng(entries[name]))
    model.phrases[:] = [replace(p, max_difficulty=0) for p in model.phrases]
    entries[name] = crypto.pack_sng(write_sng(model))
    bad = tmp_path / "bad_p.psarc"
    bad.write_bytes(container.pack_entries(entries, encrypt=True))
    problems = verify_psarc(bad).problems
    assert problems and {p.arrangement for p in problems} == {"artistsong_lead2"}
    assert {p.code for p in problems} == {"phrase_without_levels"}


def test_every_rule_has_its_words() -> None:
    import inspect

    from rockforge.infrastructure.packaging.psarc import verify

    codes = set(__import__("re").findall(r'(?:Problem\(|add\()\s*"([a-z_0-9]+)"',
                                         inspect.getsource(verify)))
    assert codes and all(describe(c) != c for c in codes)


def test_the_psarc_goes_into_our_own_folder_and_replaces_the_earlier_copy(tmp_path: Path) -> None:
    dlc = tmp_path / "Rocksmith2014" / "dlc"
    dlc.mkdir(parents=True)
    built = tmp_path / "artistsong_p.psarc"
    built.write_bytes(b"v1")
    first = game_install.install(built, dlc)
    assert first.path == dlc / "RockForge" / "artistsong_p.psarc"
    assert first.path.read_bytes() == b"v1" and first.removed is None

    # The title changed, so the key did: the old copy goes, the new one comes.
    renamed = tmp_path / "artistnewtitle_p.psarc"
    renamed.write_bytes(b"v2")
    second = game_install.install(renamed, dlc, previous=first.path)
    assert second.removed == first.path and not first.path.exists()
    assert second.path.read_bytes() == b"v2"
    assert [p.name for p in (dlc / "RockForge").iterdir()] == ["artistnewtitle_p.psarc"]

    # Reinstalling the same name overwrites it and keeps it.
    renamed.write_bytes(b"v3")
    third = game_install.install(renamed, dlc, previous=second.path)
    assert third.removed is None and third.path.read_bytes() == b"v3"


def test_a_file_rockforge_did_not_put_there_is_never_deleted(tmp_path: Path) -> None:
    dlc = tmp_path / "dlc"
    dlc.mkdir()
    built = tmp_path / "song_p.psarc"
    built.write_bytes(b"new")
    hand_copied = dlc / "song_p.psarc"  # the user copied it by hand before
    hand_copied.write_bytes(b"old")
    other = dlc / "someone_else_p.psarc"
    other.write_bytes(b"cdlc")
    result = game_install.install(built, dlc, previous=other)
    assert other.exists() and result.removed is None
    assert hand_copied.exists()
    assert result.duplicates == (hand_copied,)  # said, so the song is not listed twice
