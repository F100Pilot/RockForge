import struct

from rockforge.domain.arrangement import Arrangement, ArrangementKind, Section, SongMetadata
from rockforge.domain.music import Beat, TabNote, Technique, TempoMap, Tuning
from rockforge.infrastructure.packaging.psarc.sng import (
    NOTE_MASK_BEND,
    NOTE_MASK_CHORD,
    NOTE_MASK_CHORDNOTES,
    NOTE_MASK_DOUBLESTOP,
    NOTE_MASK_FRETHANDMUTE,
    NOTE_MASK_HAMMERON,
    NOTE_MASK_OPEN,
    NOTE_MASK_PINCHHARMONIC,
    NOTE_MASK_SINGLE,
    NOTE_MASK_SLIDEUNPITCHEDTO,
    NOTE_MASK_STRUM,
    NOTE_MASK_SUSTAIN,
    NOTE_MASK_TREMOLO,
    TECHNIQUE_BITS,
    TECHNIQUE_TO_MASK,
    from_arrangement,
    from_vocals,
    read_sng,
    write_sng,
)
from rockforge.infrastructure.rsxml.vocals import VocalEvent


def _arrangement() -> Arrangement:
    return Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="Song", artist="Artist", song_length=10.0),
        tuning=Tuning(),
        tempo_map=TempoMap(
            beats=(Beat(time=0.0, measure=1), Beat(time=0.5, measure=-1)), average_bpm=120.0
        ),
        notes=[
            TabNote(
                string=0,
                fret=2,
                time=0.0,
                sustain=0.5,
                techniques=frozenset({Technique.HAMMER_ON}),
            ),
            TabNote(string=1, fret=0, time=1.0, sustain=0.0, bend_semitones=1.5),
        ],
        sections=[
            Section(name="riff", start_time=0.0, number=1),
            Section(name="verse", start_time=5.0, number=1),
        ],
        capo=2,
    )


def test_from_arrangement_round_trips_through_write_read() -> None:
    arrangement = _arrangement()
    vocals = [VocalEvent(time=1.0, length=0.5, lyric="hi+")]
    model = from_arrangement(arrangement, vocals=vocals)
    data = write_sng(model)
    restored = read_sng(data)

    assert len(restored.beats) == len(model.beats)
    for orig, rest in zip(model.beats, restored.beats, strict=True):
        assert abs(orig.time - rest.time) < 1e-6
        assert orig.measure == rest.measure
        assert orig.beat == rest.beat

    assert len(restored.phrases) == len(model.phrases)
    for orig, rest in zip(model.phrases, restored.phrases, strict=True):
        assert orig.name == rest.name

    assert len(restored.phrase_iterations) == len(model.phrase_iterations)
    assert len(restored.sections) == len(model.sections)

    assert len(restored.arrangements) == len(model.arrangements)
    level = restored.arrangements[-1]
    orig_level = model.arrangements[-1]
    assert len(level.notes) == len(orig_level.notes)
    assert len(level.anchors) == len(orig_level.anchors)

    assert restored.metadata.capo_fret == 2
    assert restored.metadata.song_length == 10.0


def test_note_mask_uses_real_rocksmith_values() -> None:
    arrangement = _arrangement()
    model = from_arrangement(arrangement)
    notes = model.arrangements[-1].notes
    # First note: hammer-on, fret 2, sustain 0.5 → SINGLE | HAMMERON | SUSTAIN
    assert notes[0].mask & NOTE_MASK_HAMMERON
    assert notes[0].mask & NOTE_MASK_SINGLE
    assert notes[0].mask & NOTE_MASK_SUSTAIN
    assert not (notes[0].mask & NOTE_MASK_CHORD)
    # Second note: open string (fret 0), half-step bend → OPEN | BEND, peak in the
    # maxBend field (matches a decoded DLC Builder SNG: bent string 0x3000).
    assert notes[1].mask & NOTE_MASK_BEND
    assert notes[1].mask & NOTE_MASK_OPEN
    assert notes[1].bend == 1.5


def test_technique_bits_alias_matches_technique_to_mask() -> None:
    assert TECHNIQUE_BITS is TECHNIQUE_TO_MASK


def test_section_end_times_use_next_section_or_song_length() -> None:
    arrangement = _arrangement()
    model = from_arrangement(arrangement)
    assert model.sections[0].end_time == 5.0
    assert model.sections[1].end_time == 10.0


def test_metadata_reflects_capo_and_tuning() -> None:
    arrangement = _arrangement()
    model = from_arrangement(arrangement)
    assert model.metadata.capo_fret == 2
    assert model.metadata.song_length == 10.0
    assert model.metadata.tuning == (0, 0, 0, 0, 0, 0)


def test_anchors_generated_from_notes() -> None:
    arrangement = _arrangement()
    model = from_arrangement(arrangement)
    level = model.arrangements[-1]
    assert len(level.anchors) >= 1
    assert level.anchors[0].fret >= 1
    assert level.anchors[0].width >= 4


def test_chords_produce_templates_and_no_fingerprints() -> None:
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="Song", artist="A", song_length=5.0),
        tuning=Tuning(),
        tempo_map=TempoMap(
            beats=(Beat(time=0.0, measure=1), Beat(time=0.5, measure=-1)), average_bpm=120.0
        ),
        notes=[
            TabNote(string=0, fret=2, time=0.0, sustain=0.5),
            TabNote(string=1, fret=2, time=0.0, sustain=0.5),
            TabNote(string=2, fret=2, time=0.0, sustain=0.5),
        ],
        sections=[Section(name="riff", start_time=0.0)],
    )
    model = from_arrangement(arr)
    assert len(model.chord_templates) == 1
    assert model.chord_templates[0].frets[:3] == (2, 2, 2)

    level = model.arrangements[-1]
    # No handshapes: both working references (a real CDLC SNG and a DLC Builder
    # build of our XML) ship zero fingerprints; our per-chord ones crashed the
    # game at a dense octave riff. Chords render via template + CHORD/STRUM.
    assert level.fingerprints1 == []
    assert level.notes[0].fingerprint_id == (-1, -1)

    # The note entry should be a chord
    chord_note = level.notes[0]
    assert chord_note.mask & NOTE_MASK_CHORD
    assert chord_note.mask & NOTE_MASK_STRUM
    assert chord_note.chord_id == 0


def test_double_stop_gets_mask() -> None:
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="Song", artist="A", song_length=5.0),
        tuning=Tuning(),
        tempo_map=TempoMap(
            beats=(Beat(time=0.0, measure=1), Beat(time=0.5, measure=-1)), average_bpm=120.0
        ),
        notes=[
            TabNote(string=0, fret=2, time=0.0, sustain=0.5),
            TabNote(string=1, fret=2, time=0.0, sustain=0.5),
        ],
        sections=[Section(name="riff", start_time=0.0)],
    )
    model = from_arrangement(arr)
    level = model.arrangements[-1]
    assert level.notes[0].mask & NOTE_MASK_DOUBLESTOP


def test_chord_with_techniques_produces_chord_notes() -> None:
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="Song", artist="A", song_length=5.0),
        tuning=Tuning(),
        tempo_map=TempoMap(
            beats=(Beat(time=0.0, measure=1),), average_bpm=120.0
        ),
        notes=[
            TabNote(string=0, fret=2, time=0.0, sustain=0.5, bend_semitones=1.0),
            TabNote(string=1, fret=3, time=0.0, sustain=0.5),
        ],
        sections=[Section(name="riff", start_time=0.0)],
    )
    model = from_arrangement(arr)
    assert len(model.chord_notes) == 1
    assert model.chord_notes[0].note_mask[0] & NOTE_MASK_BEND  # string 0 bends

    level = model.arrangements[-1]
    chord_note = level.notes[0]
    assert chord_note.chord_notes_id == 0
    assert chord_note.mask & NOTE_MASK_CHORDNOTES


def test_note_linkage_within_phrase() -> None:
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="Song", artist="A", song_length=5.0),
        tuning=Tuning(),
        tempo_map=TempoMap(
            beats=(Beat(time=0.0, measure=1), Beat(time=1.0, measure=-1)), average_bpm=120.0
        ),
        notes=[
            TabNote(string=0, fret=2, time=0.0, sustain=0.3),
            TabNote(string=0, fret=3, time=0.5, sustain=0.3),
            TabNote(string=0, fret=5, time=1.0, sustain=0.3),
        ],
        sections=[Section(name="riff", start_time=0.0)],
    )
    model = from_arrangement(arr)
    notes = model.arrangements[-1].notes
    assert len(notes) == 3
    # First note: no prev, has next
    assert notes[0].prev_iter_note == -1
    assert notes[0].next_iter_note == 1
    # Middle note: has both
    assert notes[1].prev_iter_note == 0
    assert notes[1].next_iter_note == 2
    # Last note: has prev, no next
    assert notes[2].prev_iter_note == 1
    assert notes[2].next_iter_note == -1


def test_vocals_round_trip() -> None:
    arrangement = _arrangement()
    vocals = [VocalEvent(time=1.0, length=0.5, lyric="hello+")]
    model = from_arrangement(arrangement, vocals=vocals)
    data = write_sng(model)
    restored = read_sng(data)
    assert len(restored.vocals) == 1
    assert restored.vocals[0].lyric == "hello+"
    assert abs(restored.vocals[0].time - 1.0) < 1e-6


def test_empty_arrangement_produces_valid_sng() -> None:
    arr = Arrangement(
        kind=ArrangementKind.COMBINED,
        metadata=SongMetadata(title="Empty", artist="A", song_length=5.0),
        tuning=Tuning(),
        tempo_map=TempoMap(beats=(Beat(time=0.0, measure=1),), average_bpm=120.0),
        notes=[TabNote(string=0, fret=2, time=0.0, sustain=0.5)],
        sections=[],
    )
    model = from_arrangement(arr)
    data = write_sng(model)
    restored = read_sng(data)
    assert len(restored.arrangements) == 1
    assert restored.metadata.song_length == 5.0
    # A song with no section markers must STILL get a phrase timeline, or the
    # game loads the fretboard, shows no notes and crashes. The last phrase
    # iteration ends at the song's end so playback doesn't stop early.
    assert len(restored.phrases) >= 1
    assert len(restored.phrase_iterations) >= 1
    assert restored.phrase_iterations[-1].end_time == 5.0


def test_arrangement_level_has_phrase_counts() -> None:
    arrangement = _arrangement()
    model = from_arrangement(arrangement)
    level = model.arrangements[-1]
    assert level.phrase_count == len(model.phrases)
    assert len(level.avg_notes_per_iteration) == level.phrase_count
    assert len(level.notes_in_iteration1) == len(model.phrase_iterations)


def test_dynamic_difficulty_generates_ramping_levels() -> None:
    # Notes on downbeats/beats/half/quarter should produce several DD levels,
    # each with more notes than the last, the top level being the full chart.
    beats = []
    for meas in range(6):
        for b in range(4):
            beats.append(Beat(time=meas * 2.0 + b * 0.5, measure=meas + 1 if b == 0 else -1))
    times = []
    for meas in range(6):
        base = meas * 2.0
        times += [base, base + 0.5, base + 0.75, base + 1.0, base + 1.25]
    arr = Arrangement(
        kind=ArrangementKind.COMBINED,
        metadata=SongMetadata(title="S", artist="A", song_length=12.0),
        tuning=Tuning(),
        tempo_map=TempoMap(beats=tuple(beats), average_bpm=120.0),
        notes=[TabNote(string=i % 6, fret=(i % 10) + 1, time=times[i], sustain=0.2)
               for i in range(len(times))],
    )
    model = from_arrangement(arr)
    counts = [len(lvl.notes) for lvl in model.arrangements]
    assert len(counts) >= 2                       # DD actually kicked in
    assert counts == sorted(counts)               # each level adds notes
    assert counts[-1] == len(times)               # top level is the full chart
    assert model.metadata.max_difficulty == len(counts) - 1
    # Round-trips with all levels intact.
    restored = read_sng(write_sng(model))
    assert [len(lvl.notes) for lvl in restored.arrangements] == counts


def test_sectionless_song_is_segmented_into_multiple_phrases() -> None:
    # A long GP with no section markers must still be split into many phrases so
    # DD ramps per-phrase as the player progresses (a real DDC auto-segments); one
    # giant phrase spanning the whole song gives a poor DD.
    beats = [Beat(time=i * 0.5, measure=i // 4 + 1 if i % 4 == 0 else -1) for i in range(400)]
    notes = [TabNote(string=i % 6, fret=(i % 7) + 1, time=round(i * 0.5, 3), sustain=0.2)
             for i in range(360)]
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="S", artist="A", song_length=190.0),
        tuning=Tuning(),
        tempo_map=TempoMap(beats=tuple(beats), average_bpm=120.0),
        notes=notes,
        sections=[],
    )
    model = from_arrangement(arr)
    # ~190 s / 13 s ≈ a dozen-plus phrases (not just COUNT/body/END).
    assert len(model.phrases) >= 8
    # Phrase iterations stay ordered and non-overlapping.
    starts = [pi.start_time for pi in model.phrase_iterations]
    assert starts == sorted(starts)
    # No anchor crosses a phrase boundary and each phrase owns an anchor at start.
    bounds = {pi.start_time for pi in model.phrase_iterations}
    top = model.arrangements[-1]
    assert not any(a.start_time < b < a.end_time for a in top.anchors for b in bounds)
    # Every NOTE-BEARING phrase owns an anchor at its start (an empty END phrase
    # needs none — it has no notes to frame).
    for pi in model.phrase_iterations:
        if any(pi.start_time <= n.time < pi.end_time for n in top.notes):
            assert any(abs(a.start_time - pi.start_time) < 1e-9 for a in top.anchors)


def test_dd_phrase_heights_vary_with_density() -> None:
    # Variable-height DD: a dense phrase reaches a higher max difficulty than a
    # sparse one — above the old flat cap of 11 — so the in-game difficulty bars
    # vary per phrase (matching a real DDC) instead of a flat top.
    beats = tuple(Beat(time=i * 0.5, measure=i // 8 + 1 if i % 8 == 0 else -1)
                  for i in range(80))
    notes = [TabNote(string=0, fret=3, time=t, sustain=0.2) for t in (0.5, 2.0, 3.5)]
    notes += [TabNote(string=i % 6, fret=(i % 10) + 1, time=6.0 + i * 0.2, sustain=0.15)
              for i in range(30)]
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="S", artist="A", song_length=20.0),
        tuning=Tuning(),
        tempo_map=TempoMap(beats=beats, average_bpm=120.0),
        notes=notes,
        sections=[Section(name="sparse", start_time=0.0), Section(name="dense", start_time=6.0)],
    )
    model = from_arrangement(arr)
    heights = {p.name: p.max_difficulty for p in model.phrases}
    assert heights.get("dense", 0) > 11              # dense phrase exceeds the old cap
    assert heights.get("sparse", 0) < heights["dense"]  # sparse phrase is shorter
    assert len({p.max_difficulty for p in model.phrases}) >= 3  # not a flat top


def test_dd_low_levels_spread_notes_across_the_phrase() -> None:
    # A long single-phrase song (no section markers): low DD levels must show the
    # strongest beats spread across the WHOLE phrase, not clustered in its first
    # part (the "low difficulty only shows the first half of the song" bug).
    beats = [Beat(time=i * 0.5, measure=i // 4 + 1 if i % 4 == 0 else -1) for i in range(200)]
    notes = [TabNote(string=i % 6, fret=(i % 7) + 1, time=round(i * 0.25, 3), sustain=0.1)
             for i in range(360)]
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="S", artist="A", song_length=95.0),
        tuning=Tuning(),
        tempo_map=TempoMap(beats=tuple(beats), average_bpm=120.0),
        notes=notes,
        sections=[],  # → one big phrase
    )
    model = from_arrangement(arr)
    song_len = max(n.time for n in notes)
    low = model.arrangements[0]
    assert 0 < len(low.notes) < len(notes)  # DD actually thinned it
    # Split the song into thirds; the low level must have notes in every third.
    thirds = [0, 0, 0]
    for n in low.notes:
        thirds[min(2, int(n.time / song_len * 3))] += 1
    assert all(t > 0 for t in thirds), thirds


def test_dd_hero_triples_and_density_graduated_ceilings() -> None:
    # A DDC-shaped DD: a dense phrase reaches a higher ceiling than a sparse one,
    # and each iteration's hero triple is (round(max/4), round(max/2), max) — the
    # Easy/Medium/Hard levels a retail SNG carries (verified against a reference).
    beats = [Beat(time=i * 0.5, measure=i // 4 + 1 if i % 4 == 0 else -1) for i in range(64)]
    # Phrase A (0..8s): busy — a note every 0.25s. Phrase B (8..end): sparse.
    dense = [round(t * 0.25, 3) for t in range(32)]  # 8s of 16th notes
    sparse = [8.0, 10.0, 12.0]
    notes = [TabNote(string=i % 6, fret=(i % 7) + 1, time=t, sustain=0.1)
             for i, t in enumerate(dense + sparse)]
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="S", artist="A", song_length=16.0),
        tuning=Tuning(),
        tempo_map=TempoMap(beats=tuple(beats), average_bpm=120.0),
        notes=notes,
        sections=[Section(name="busy", number=1, start_time=0.0),
                  Section(name="calm", number=1, start_time=8.0)],
    )
    model = from_arrangement(arr)
    by_name = {p.name: p.max_difficulty for p in model.phrases}
    assert by_name["busy"] > by_name["calm"]  # density graduates the ceiling
    for pi in model.phrase_iterations:
        pmax = model.phrases[pi.phrase_id].max_difficulty
        assert pi.difficulty == (round(pmax / 4), round(pmax / 2), pmax)
    # Consistent song-wide max across levels + metadata.
    assert model.metadata.max_difficulty == len(model.arrangements) - 1
    assert model.metadata.max_difficulty == max(by_name.values())


def test_dd_levels_have_no_handshapes_and_per_level_slide_extensions() -> None:
    # Fingerprints (handshapes) are not emitted at all — both working references
    # (a real CDLC SNG and a DLC Builder build of our XML) ship zero on every
    # level, and our per-chord handshapes crashed the game at a dense octave
    # riff. Slide anchor-extensions ARE per level: an extension pointing at a
    # note the level dropped crashes the game on the first pass.
    beats = [Beat(time=i * 0.5, measure=i // 4 + 1 if i % 4 == 0 else -1) for i in range(64)]
    notes = []
    # A dense double-stop riff (chords on every 8th) + a sliding single note.
    for i in range(32):
        t = round(i * 0.25, 3)
        notes.append(TabNote(string=2, fret=7, time=t, sustain=0.1))
        notes.append(TabNote(string=1, fret=5, time=t, sustain=0.1))
    notes.append(TabNote(string=0, fret=5, time=8.5, sustain=0.5, slide_to_fret=9))
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="S", artist="A", song_length=16.0),
        tuning=Tuning(),
        tempo_map=TempoMap(beats=tuple(beats), average_bpm=120.0),
        notes=notes,
    )
    model = from_arrangement(arr)
    assert len(model.arrangements) >= 2
    top = model.arrangements[-1]
    assert len(top.anchor_extensions) == 1  # the slide
    for lvl in model.arrangements:
        assert lvl.fingerprints1 == [] and lvl.fingerprints2 == []
        assert all(n.fingerprint_id == (-1, -1) for n in lvl.notes)
        # Every extension matches a sliding note present in THIS level.
        slide_ends = {
            round(n.time + n.sustain, 4)
            for n in lvl.notes
            if n.slide_to >= 0 or n.chord_notes_id >= 0
        }
        assert all(round(ae.beat_time, 4) in slide_ends for ae in lvl.anchor_extensions)


def test_gp_sections_are_bracketed_with_count_and_end_and_links() -> None:
    # Real GP sections must still be bracketed by a COUNT phrase (count-in, max
    # difficulty 0 — without it the silent intro sits inside a high-difficulty
    # phrase, an all-black bar in the Riff Repeater) and an END phrase after the
    # last note. Every phrase carries PhraseIterationLinks = its iteration count
    # (retail values; 0 broke Riff Repeater phrase navigation → crash entering
    # the next phrase).
    beats = [Beat(time=i * 0.5, measure=i // 4 + 1 if i % 4 == 0 else -1) for i in range(80)]
    notes = [TabNote(string=i % 6, fret=(i % 5) + 2, time=round(4.0 + i * 0.5, 3), sustain=0.3)
             for i in range(40)]  # first note at 4.0s — a silent intro
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="S", artist="A", song_length=40.0),
        tuning=Tuning(),
        tempo_map=TempoMap(beats=tuple(beats), average_bpm=120.0),
        notes=notes,
        sections=[Section(name="Verse", number=1, start_time=0.0),
                  Section(name="Chorus", number=1, start_time=12.0)],
    )
    model = from_arrangement(arr)
    names = [p.name for p in model.phrases]
    assert names[0] == "COUNT" and names[-1] == "END"
    assert model.phrases[0].max_difficulty == 0
    assert model.phrases[-1].max_difficulty == 0
    # COUNT covers the silent intro; the body starts at the first note.
    assert model.phrase_iterations[0].start_time == 0.0
    assert model.phrase_iterations[0].end_time == 4.0
    # Links = per-phrase iteration count, never 0.
    assert all(p.phrase_iteration_links >= 1 for p in model.phrases)


def test_bend_point_reaches_peak_at_note_end_like_dlc_builder() -> None:
    # A decoded DLC Builder SNG of a bent note carries a single bend point at the
    # note's END (attack + sustain) with step = the bend in half-steps — a bend-UP
    # across the note, not a prebend at the attack.
    beats = tuple(Beat(time=i * 0.5, measure=1 if i == 0 else -1) for i in range(20))
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="S", artist="A", song_length=10.0),
        tuning=Tuning(),
        tempo_map=TempoMap(beats=beats, average_bpm=120.0),
        notes=[
            TabNote(string=0, fret=5, time=3.0, sustain=0.6, bend_semitones=1.0),  # single
            TabNote(string=1, fret=5, time=6.0, sustain=0.6, bend_semitones=1.0),  # chord…
            TabNote(string=2, fret=7, time=6.0, sustain=0.6),                      # …mate
        ],
    )
    model = from_arrangement(arr)
    top = model.arrangements[-1]
    single = next(n for n in top.notes if n.string == 0)
    assert len(single.bend_data) == 1
    assert single.bend_data[0].step == 1.0
    assert single.bend_data[0].time == 3.6  # attack 3.0 + sustain 0.6, not the attack
    chord = next(n for n in top.notes if n.chord_id >= 0)
    cn = model.chord_notes[chord.chord_notes_id]
    assert len(cn.bend_data[1]) == 1
    assert cn.bend_data[1][0].step == 1.0 and cn.bend_data[1][0].time == 6.6


def test_fret_mute_slide_unpitch_and_composite_bend_in_sng() -> None:
    from rockforge.domain.music import BendPoint

    beats = tuple(Beat(time=i * 0.5, measure=1 if i == 0 else -1) for i in range(20))
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="S", artist="A", song_length=10.0),
        tuning=Tuning(),
        tempo_map=TempoMap(beats=beats, average_bpm=120.0),
        notes=[
            TabNote(string=0, fret=5, time=1.0, sustain=0.4,
                    techniques=frozenset({Technique.FRET_MUTE})),        # dead X
            TabNote(string=1, fret=9, time=2.0, sustain=0.4, slide_unpitch_to=4),  # slide-out
            TabNote(string=2, fret=7, time=3.0, sustain=0.4, bend_semitones=1.0,   # bend-and-
                    bend_points=(BendPoint(0.0, 0.0), BendPoint(0.5, 1.0),         # release
                                 BendPoint(1.0, 0.0))),
        ],
    )
    top = from_arrangement(arr).arrangements[-1]
    mute = next(n for n in top.notes if n.string == 0)
    assert mute.mask & NOTE_MASK_FRETHANDMUTE
    slide = next(n for n in top.notes if n.string == 1)
    assert slide.slide_unpitch_to == 4 and slide.mask & NOTE_MASK_SLIDEUNPITCHEDTO
    bend = next(n for n in top.notes if n.string == 2)
    assert len(bend.bend_data) == 3  # full curve, not collapsed to a single point
    assert [round(b.step, 1) for b in bend.bend_data] == [0.0, 1.0, 0.0]


def test_pinch_tremolo_finger_and_pickdir_in_sng() -> None:
    beats = tuple(Beat(time=i * 0.5, measure=1 if i == 0 else -1) for i in range(20))
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="S", artist="A", song_length=10.0),
        tuning=Tuning(),
        tempo_map=TempoMap(beats=beats, average_bpm=120.0),
        notes=[
            TabNote(string=0, fret=5, time=1.0, sustain=0.4,
                    techniques=frozenset({Technique.PINCH_HARMONIC})),
            TabNote(string=1, fret=7, time=2.0, sustain=0.4,
                    techniques=frozenset({Technique.TREMOLO})),
            TabNote(string=2, fret=3, time=3.0, sustain=0.4, left_hand=2, pick_direction=1),
        ],
    )
    top = from_arrangement(arr).arrangements[-1]
    assert next(n for n in top.notes if n.string == 0).mask & NOTE_MASK_PINCHHARMONIC
    assert next(n for n in top.notes if n.string == 1).mask & NOTE_MASK_TREMOLO
    finger = next(n for n in top.notes if n.string == 2)
    assert finger.left_hand == 2 and finger.pick_direction == 1


def test_chord_notes_bend_usedcount_is_after_the_32_entry_array() -> None:
    # The Sng2014 ChordNotes BendData layout per string is 32 fixed BendData32
    # entries THEN the Int32 UsedCount — verified against a DLC Builder SNG.
    # Writing the count first put it where the game expects the first bend point,
    # crashing at the first bent chord. This locks the byte order.
    from rockforge.infrastructure.packaging.psarc.sng import (
        _BEND32_SIZE,
        _BEND_DATA_COUNT,
        SngBendData32,
        SngChordNotes,
        _read_chord_notes_entry,
        _write_chord_notes_entry,
    )

    cn = SngChordNotes(
        note_mask=[0, 0x3000, 0, 0, 0, 0],
        bend_data=[[], [SngBendData32(time=6.0, step=1.0)], [], [], [], []],
        slide_to=[0xFF] * 6,
        slide_unpitch_to=[0xFF] * 6,
        vibrato=[0] * 6,
    )
    blob = _write_chord_notes_entry(cn)
    # String 0 has no bend → UsedCount 0 sits right after its 32 empty entries.
    string_block = 32 * _BEND32_SIZE + 4
    s0_count_off = 24 + _BEND_DATA_COUNT * _BEND32_SIZE  # after masks + s0's 32 entries
    assert struct.unpack_from("<i", blob, s0_count_off)[0] == 0
    # String 1's UsedCount (1) is at the END of its 32-entry array, not the front.
    s1_count_off = 24 + string_block + _BEND_DATA_COUNT * _BEND32_SIZE
    assert struct.unpack_from("<i", blob, s1_count_off)[0] == 1
    # And the bend point is the FIRST entry of string 1's array.
    s1_first_entry_off = 24 + string_block
    t, step = struct.unpack_from("<ff", blob, s1_first_entry_off)
    assert t == 6.0 and step == 1.0
    # Round-trips.
    restored, _ = _read_chord_notes_entry(blob, 0)
    assert len(restored.bend_data[1]) == 1
    assert restored.bend_data[1][0].time == 6.0 and restored.bend_data[1][0].step == 1.0
    assert restored.bend_data[0] == []


def test_plain_notes_have_no_slide() -> None:
    # slide_to must be -1 (no slide) for ordinary notes; writing 0 told the game
    # every note slides to fret 0 — a slide streak on every note.
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="S", artist="A", song_length=5.0),
        tuning=Tuning(),
        tempo_map=TempoMap(beats=(Beat(time=0.0, measure=1),), average_bpm=120.0),
        notes=[TabNote(string=s, fret=s + 2, time=s * 0.3, sustain=0.2) for s in range(6)],
    )
    notes = read_sng(write_sng(from_arrangement(arr))).arrangements[-1].notes
    assert notes and all(n.slide_to == -1 for n in notes)


def test_real_slide_is_preserved() -> None:
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="S", artist="A", song_length=5.0),
        tuning=Tuning(),
        tempo_map=TempoMap(beats=(Beat(time=0.0, measure=1),), average_bpm=120.0),
        notes=[TabNote(string=0, fret=5, time=0.0, sustain=0.5, slide_to_fret=7)],
    )
    note = read_sng(write_sng(from_arrangement(arr))).arrangements[-1].notes[0]
    assert note.slide_to == 7


def test_beats_carry_real_measures_and_downbeat_mask() -> None:
    # The Sng2014 beat is 16 bytes: the trailing mask (bit0 downbeat, bit1 even
    # measure) must be present, or every beat is 4 bytes short and the whole SNG
    # misaligns — the game crashes on load with an access violation.
    from rockforge.infrastructure.packaging.psarc.sng import _BEAT_SIZE

    assert _BEAT_SIZE == 16
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="S", artist="A", song_length=8.0),
        tuning=Tuning(),
        tempo_map=TempoMap(
            beats=tuple(
                Beat(time=i * 0.5, measure=(i // 4) + 1 if i % 4 == 0 else -1) for i in range(12)
            ),
            average_bpm=120.0,
        ),
        notes=[TabNote(string=0, fret=2, time=0.0, sustain=0.5)],
    )
    beats = read_sng(write_sng(from_arrangement(arr))).beats
    # Every beat has a real measure number (never -1), beat-in-measure 0..3.
    assert all(b.measure >= 1 for b in beats)
    assert beats[0].mask == 1  # measure 1 downbeat
    assert beats[4].mask == 3  # measure 2 (even) downbeat
    assert beats[1].mask == 0  # off-beat


def test_anchors_have_distinct_increasing_times() -> None:
    # Anchors that share a start time (an earlier bug keyed them off the phrase
    # iteration) overlap and crash the note highway on load.
    frets = [1, 5, 9, 5, 1, 7, 12, 3]
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="S", artist="A", song_length=8.0),
        tuning=Tuning(),
        tempo_map=TempoMap(
            beats=tuple(Beat(time=i * 0.5, measure=1 if i == 0 else -1) for i in range(18)),
            average_bpm=120.0,
        ),
        notes=[TabNote(string=0, fret=frets[i], time=i * 0.5, sustain=0.4) for i in range(8)],
        sections=[],
    )
    anchors = from_arrangement(arr).arrangements[-1].anchors
    assert len(anchors) >= 2
    times = [a.start_time for a in anchors]
    assert times == sorted(times)
    assert len(set(times)) == len(times)  # strictly distinct
    # Each anchor ends where the next begins (contiguous coverage).
    for i in range(len(anchors) - 1):
        assert anchors[i].end_time == anchors[i + 1].start_time


def test_anchors_are_built_per_level_not_shared() -> None:
    # A real DDC sizes anchors to each level's notes; sharing the full-chart
    # anchor set on a thinned low level ships anchors framing notes that don't
    # exist there, crashing the game on phrase entry. Low levels must therefore
    # carry FEWER anchors than the top level, and each level's anchors must cover
    # only its own note positions.
    beats = [Beat(time=i * 0.5, measure=i // 4 + 1 if i % 4 == 0 else -1) for i in range(120)]
    notes = [TabNote(string=i % 6, fret=(i % 9) + 1, time=round(i * 0.25, 3), sustain=0.1)
             for i in range(200)]
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="S", artist="A", song_length=60.0),
        tuning=Tuning(),
        tempo_map=TempoMap(beats=tuple(beats), average_bpm=120.0),
        notes=notes,
    )
    model = from_arrangement(arr)
    assert len(model.arrangements) >= 3
    counts = [len(lvl.anchors) for lvl in model.arrangements]
    assert counts[0] < counts[-1]  # low levels have fewer anchors than the top
    # A level's anchors are derived from its OWN notes: each level has a distinct
    # anchor set (not the shared full-chart one), and every anchor is in range.
    assert len(set(counts)) > 1
    for lvl in model.arrangements:
        for a in lvl.anchors:
            assert 1 <= a.fret <= 24 and a.start_time < a.end_time


def test_anchors_do_not_cross_phrase_iteration_boundaries() -> None:
    # An anchor that spans a phrase-iteration boundary leaves the new phrase's
    # opening notes covered only by the PREVIOUS phrase's anchor; the game
    # re-anchors at each phrase start, finds none of its own, and crashes on
    # entry (seen exactly at a section / tone-change boundary). Every anchor must
    # stay within one phrase iteration, and each phrase must own an anchor at its
    # start.
    beats = [Beat(time=i * 0.5, measure=i // 4 + 1 if i % 4 == 0 else -1) for i in range(48)]
    notes = [TabNote(string=0, fret=(i % 5) + 3, time=round(i * 0.5, 3), sustain=0.4)
             for i in range(40)]
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="S", artist="A", song_length=24.0),
        tuning=Tuning(),
        tempo_map=TempoMap(beats=tuple(beats), average_bpm=120.0),
        notes=notes,
        # Sections carve the song into several phrase iterations.
        sections=[Section(name="a", number=1, start_time=0.0),
                  Section(name="b", number=1, start_time=8.0),
                  Section(name="c", number=1, start_time=15.0)],
    )
    model = from_arrangement(arr)
    pis = model.phrase_iterations
    bounds = {round(pi.start_time, 6) for pi in pis}
    for lvl in model.arrangements:
        for a in lvl.anchors:
            assert not any(a.start_time < b < a.end_time for b in bounds)
    # Each phrase iteration owns an anchor starting exactly at its start.
    top = model.arrangements[-1]
    for pi in pis:
        assert any(abs(a.start_time - pi.start_time) < 1e-6 for a in top.anchors)


def test_anchor_does_not_sit_below_a_chord_run() -> None:
    # A fret 3-5 chord run followed by a lone low (fret 1) note must NOT be folded
    # into one wide fret 1-5 anchor — the chords would then sit two frets below
    # where they're played ("anchor shows fret 1 for a 2-5 chord" glitch). The
    # chord run gets its own anchor that does not extend below fret 3.
    beats = [Beat(time=i * 0.5, measure=i // 4 + 1 if i % 4 == 0 else -1) for i in range(24)]
    notes = []
    for i in range(8):  # a 3-5 power-chord run
        t = round(i * 0.5, 3)
        notes.append(TabNote(string=4, fret=3, time=t, sustain=0.3))
        notes.append(TabNote(string=3, fret=5, time=t, sustain=0.3))
    notes.append(TabNote(string=5, fret=1, time=4.5, sustain=0.3))  # lone low note
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="S", artist="A", song_length=8.0),
        tuning=Tuning(),
        tempo_map=TempoMap(beats=tuple(beats), average_bpm=120.0),
        notes=notes,
    )
    anchors = from_arrangement(arr).arrangements[-1].anchors
    # The anchor active while the 3-5 chords play (t≈1.0) must not start at fret 1.
    active = [a for a in anchors if a.start_time <= 1.0 < a.end_time]
    assert active and active[0].fret >= 2
    assert all(a.width <= 4 for a in anchors)


def test_slide_notes_produce_anchor_extensions() -> None:
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="Song", artist="A", song_length=5.0),
        tuning=Tuning(),
        tempo_map=TempoMap(
            beats=(Beat(time=0.0, measure=1), Beat(time=1.0, measure=-1)), average_bpm=120.0
        ),
        notes=[
            TabNote(string=0, fret=5, time=0.0, sustain=0.5,
                    techniques=frozenset({Technique.SLIDE}), slide_to_fret=7),
            TabNote(string=1, fret=3, time=1.0, sustain=0.2),  # no slide
        ],
        sections=[Section(name="riff", start_time=0.0)],
    )
    model = from_arrangement(arr)
    exts = model.arrangements[-1].anchor_extensions
    assert len(exts) == 1
    # BeatTime is when the slide ends (time + sustain), fret is the destination.
    assert abs(exts[0].beat_time - 0.5) < 1e-6
    assert exts[0].fret == 7


def test_anchor_extensions_round_trip() -> None:
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="Song", artist="A", song_length=5.0),
        tuning=Tuning(),
        tempo_map=TempoMap(
            beats=(Beat(time=0.0, measure=1), Beat(time=1.0, measure=-1)), average_bpm=120.0
        ),
        notes=[
            TabNote(string=0, fret=5, time=0.0, sustain=0.5,
                    techniques=frozenset({Technique.SLIDE}), slide_to_fret=9),
        ],
        sections=[Section(name="riff", start_time=0.0)],
    )
    model = from_arrangement(arr)
    restored = read_sng(write_sng(model))
    exts = restored.arrangements[-1].anchor_extensions
    assert len(exts) == 1
    assert exts[0].fret == 9
    assert abs(exts[0].beat_time - 0.5) < 1e-6


def test_chord_template_notes_are_real_midi() -> None:
    # Drop-D-ish chord on standard tuning: open E (40), A fret2 (47), D fret2 (52)
    arr = Arrangement(
        kind=ArrangementKind.LEAD,
        metadata=SongMetadata(title="Song", artist="A", song_length=5.0),
        tuning=Tuning(),  # standard: 40,45,50,55,59,64
        tempo_map=TempoMap(beats=(Beat(time=0.0, measure=1),), average_bpm=120.0),
        notes=[
            TabNote(string=0, fret=0, time=0.0, sustain=0.5),
            TabNote(string=1, fret=2, time=0.0, sustain=0.5),
            TabNote(string=2, fret=2, time=0.0, sustain=0.5),
        ],
        sections=[Section(name="riff", start_time=0.0)],
    )
    model = from_arrangement(arr)
    notes_midi = model.chord_templates[0].notes
    assert notes_midi[0] == 40  # open low E
    assert notes_midi[1] == 47  # A + 2
    assert notes_midi[2] == 52  # D + 2
    assert notes_midi[3] == 0   # unused string


def test_from_vocals_only_populates_vocals() -> None:
    vocals = [
        VocalEvent(time=0.5, length=0.3, lyric="hel"),
        VocalEvent(time=0.8, length=0.4, lyric="lo+"),
    ]
    model = from_vocals(vocals)
    assert len(model.vocals) == 2
    assert model.beats == []
    assert model.arrangements == []
    assert model.chord_templates == []

    restored = read_sng(write_sng(model))
    assert len(restored.vocals) == 2
    assert restored.vocals[0].lyric == "hel"
    assert restored.vocals[1].lyric == "lo+"
    assert restored.arrangements == []


def test_vocals_note_is_non_pitched_sentinel() -> None:
    """Scroll lyrics must carry note 254 (Rocksmith's non-pitched sentinel),
    not 0. A DLC Builder-built vocals SNG uses 254; note 0 is a real (absurdly
    low) MIDI pitch, and the game then fails to render the lyric as a scroll —
    the "letra não aparece" symptom on a native PSARC."""
    from rockforge.infrastructure.rsxml.vocals import VOCAL_NOTE

    model = from_vocals([VocalEvent(time=0.5, length=0.3, lyric="hi+")])
    assert model.vocals[0].note == VOCAL_NOTE == 254
    assert read_sng(write_sng(model)).vocals[0].note == 254
