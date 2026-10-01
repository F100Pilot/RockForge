"""The tones of the songs in a Rocksmith dlc folder (``tone_collection``)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from rockforge.infrastructure import tone_collection as tc
from rockforge.infrastructure.packaging.psarc.container import pack_entries, read_entries, unpack


def _tone(key: str, name: str, amp: str = "Amp_MarshallPlexi", **extra: object) -> dict:
    gear: dict = {
        "Amp": {"Type": "Amps", "KnobValues": {"Amp_MarshallPlexi_Bass": 70}, "Key": amp},
        "Cabinet": {"Type": "Cabinets", "KnobValues": {}, "Key": "Cab_Marshall1960a_57_Cone"},
    }
    gear.update(extra)
    return {"GearList": gear, "ToneDescriptors": ["$[35716]CRUNCH"], "NameSeparator": " - ",
            "Volume": "-19.5", "Key": key, "Name": name}


def _manifest(arrangement: str, tones: list | None, song: str = "Highway to Hell") -> bytes:
    attrs: dict = {"SongName": song, "ArtistName": "AC/DC", "AlbumName": "Highway",
                   "ArrangementName": arrangement}
    if tones is not None:
        attrs["Tones"] = tones
    return json.dumps({"Entries": {"ABC": {"Attributes": attrs}},
                       "InsertRoot": "Static.Songs.Entries"}).encode()


def _song_psarc(path: Path, song: str = "Highway to Hell", encrypt: bool = False) -> Path:
    drive = {"Type": "Pedals", "KnobValues": {"Pedal_SuperDrive_Gain": 61},
             "PedalKey": "Pedal_SuperDrive"}  # older tools wrote PedalKey
    lead = [
        _tone("HTH_Lead", "Lead", PrePedal2=drive),
        _tone("HTH_Clean", "Clean"),
        _tone("HTH_Odd", "Odd", amp="Amp_NotInTheGame"),  # unknown gear: skipped
    ]
    files = {
        "audio/windows/123.wem": os.urandom(200_000),  # several blocks to skip over
        "manifests/songs_dlc_hth/hth_lead.json": _manifest("Lead", lead, song),
        "manifests/songs_dlc_hth/hth_rhythm.json": _manifest(
            "Rhythm", [_tone("HTH_Lead", "Lead")], song,
        ),
        "manifests/songs_dlc_hth/hth_vocals.json": _manifest("Vocals", None, song),
        "manifests/songs_dlc_hth/songs_dlc_hth.hsan": b"{}",
    }
    path.write_bytes(pack_entries(files, encrypt=encrypt))
    return path


def test_only_the_wanted_entries_are_read_and_they_match_a_full_unpack(tmp_path: Path) -> None:
    big = os.urandom(150_000) + b"x" * 70_000  # incompressible blocks then compressible ones
    files = {"a/big.bin": big, "manifests/x.json": b'{"k": 1}', "z.txt": b"z"}
    path = tmp_path / "s.psarc"
    path.write_bytes(pack_entries(files))
    wanted = read_entries(path, lambda n: n.startswith("manifests/"))
    assert wanted == {"manifests/x.json": b'{"k": 1}'}
    assert read_entries(path, lambda n: True) == unpack(path.read_bytes()) == files
    (tmp_path / "no.psarc").write_bytes(b"not an archive at all, really")
    with pytest.raises(ValueError):
        read_entries(tmp_path / "no.psarc", lambda n: True)


def test_the_tones_of_a_song_come_out_of_its_manifests(tmp_path: Path) -> None:
    pytest.importorskip("cryptography")
    result = tc.read_psarc_tones(_song_psarc(tmp_path / "hth_p.psarc", encrypt=True))
    assert result["skipped"] == 1
    by_key = {r["tone"]["key"]: r for r in result["tones"]}
    assert set(by_key) == {"HTH_Lead", "HTH_Clean"}
    lead = by_key["HTH_Lead"]
    assert (lead["song"], lead["artist"], lead["album"]) == ("Highway to Hell", "AC/DC", "Highway")
    assert lead["arrangements"] == ["Lead", "Rhythm"]  # one tone, two charts
    tone = lead["tone"]
    assert tone["volume"] == -19.5 and tone["descriptors"] == ["$[35716]CRUNCH"]
    assert tone["amp"] == {"key": "Amp_MarshallPlexi", "knobs": {"Amp_MarshallPlexi_Bass": 70.0}}
    # the pedal keeps its slot, whichever name the key was written under
    assert tone["pre"][0] is None
    assert tone["pre"][1] == {"key": "Pedal_SuperDrive", "knobs": {"Pedal_SuperDrive_Gain": 61.0}}
    from rockforge.infrastructure.packaging.gear.gear_catalogue import tone_from_dict

    built = tone_from_dict(tone)
    assert built is not None and built.gear.pre_pedals[1].key == "Pedal_SuperDrive"
    assert built.gear.amp.knob_values["Amp_MarshallPlexi_Bass"] == 70.0


def test_an_unreadable_archive_is_noted_not_fatal(tmp_path: Path) -> None:
    (tmp_path / "broken.psarc").write_bytes(b"PSAR" + b"\0" * 10)
    assert "error" in tc.read_psarc_tones(tmp_path / "broken.psarc")


def test_a_rescan_only_reads_what_changed(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(tc.config.settings, "work_dir", tmp_path / "work")
    dlc = tmp_path / "dlc"
    (dlc / "sub").mkdir(parents=True)
    _song_psarc(dlc / "a_p.psarc", "Alpha")
    _song_psarc(dlc / "sub" / "b_p.psarc", "Beta")
    _song_psarc(dlc / "b_m.psarc", "Beta")  # a Mac copy of a song whose PC copy is here
    (dlc / "notes.txt").write_text("x")
    read: list[str] = []
    real = tc.read_psarc_tones
    monkeypatch.setattr(tc, "read_psarc_tones", lambda p: read.append(p.name) or real(p))

    data = tc.scan(dlc)
    assert sorted(read) == ["a_p.psarc", "b_p.psarc"]
    assert sorted(data["files"]) == ["a_p.psarc", "sub/b_p.psarc"]
    assert len(tc.rows()) == 4

    read.clear()
    tc.scan(dlc)
    assert read == []  # nothing changed, nothing opened
    os.utime(dlc / "a_p.psarc", (2, 2))  # same size, saved again
    tc.scan(dlc)
    assert read == ["a_p.psarc"]
    read.clear()
    _song_psarc(dlc / "a_p.psarc", "Alpha 2")
    os.utime(dlc / "a_p.psarc", (1, 1))
    (dlc / "sub" / "b_p.psarc").unlink()
    data = tc.scan(dlc)
    # the changed file is read again, and the Mac copy stands in for the PC
    # copy that is gone; the unchanged-and-gone one is dropped
    assert read == ["a_p.psarc", "b_m.psarc"]
    assert sorted(data["files"]) == ["a_p.psarc", "b_m.psarc"]
    assert {r["song"] for r in tc.rows()} == {"Alpha 2", "Beta"}
    # another folder starts from nothing
    other = tmp_path / "other"
    other.mkdir()
    assert tc.scan(other)["files"] == {}


def test_the_collection_is_searched_by_song_artist_tone_and_gear(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(tc.config.settings, "work_dir", tmp_path / "work")
    dlc = tmp_path / "dlc"
    dlc.mkdir()
    _song_psarc(dlc / "a_p.psarc", "Canção Açucarada")
    tc.scan(dlc)
    assert {r["tone"]["key"] for r in tc.search("cancao acucarada")} == {"HTH_Lead", "HTH_Clean"}
    assert [r["tone"]["key"] for r in tc.search("superdrive")] == ["HTH_Lead"]
    assert [r["tone"]["key"] for r in tc.search("ac/dc clean")] == ["HTH_Clean"]
    assert tc.search("nothing like it") == []
    ids = {r["id"] for r in tc.rows()}
    assert len(ids) == 2 and all(len(i) == 16 for i in ids)


def test_steams_default_dlc_folder_is_suggested_when_it_exists(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(tc.Path, "home", lambda: tmp_path)
    monkeypatch.setenv("PROGRAMFILES(X86)", str(tmp_path / "nope"))
    monkeypatch.setenv("PROGRAMFILES", str(tmp_path / "nope"))
    assert tc.suggested_folder() is None
    dlc = tmp_path / ".steam" / "steam" / "steamapps" / "common" / "Rocksmith2014" / "dlc"
    dlc.mkdir(parents=True)
    assert tc.suggested_folder() == dlc
