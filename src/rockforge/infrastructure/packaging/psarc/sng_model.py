"""The SNG's data model: the Sng2014 records, the note-mask bits and the
limits the builder and the binary codec share.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from rockforge.domain.music import Technique

# ---------------------------------------------------------------------------
# Real Rocksmith 2014 NoteMask values (from Rocksmith2014.NET Constants.cs)
# ---------------------------------------------------------------------------
NOTE_MASK_CHORD = 0x00000002


NOTE_MASK_OPEN = 0x00000004


NOTE_MASK_FRETHANDMUTE = 0x00000008


NOTE_MASK_TREMOLO = 0x00000010


NOTE_MASK_HARMONIC = 0x00000020


NOTE_MASK_PALMMUTE = 0x00000040


NOTE_MASK_SLAP = 0x00000080


NOTE_MASK_PLUCK = 0x00000100


NOTE_MASK_HAMMERON = 0x00000200


NOTE_MASK_PULLOFF = 0x00000400


NOTE_MASK_SLIDE = 0x00000800


NOTE_MASK_BEND = 0x00001000


NOTE_MASK_SUSTAIN = 0x00002000


NOTE_MASK_TAP = 0x00004000


NOTE_MASK_PINCHHARMONIC = 0x00008000


NOTE_MASK_VIBRATO = 0x00010000


NOTE_MASK_MUTE = 0x00020000


NOTE_MASK_IGNORE = 0x00040000


NOTE_MASK_HIGHDENSITY = 0x00200000


NOTE_MASK_SLIDEUNPITCHEDTO = 0x00400000


NOTE_MASK_SINGLE = 0x00800000


NOTE_MASK_CHORDNOTES = 0x01000000


NOTE_MASK_DOUBLESTOP = 0x02000000


NOTE_MASK_ACCENT = 0x04000000


NOTE_MASK_PARENT = 0x08000000


NOTE_MASK_CHILD = 0x10000000


NOTE_MASK_ARPEGGIO = 0x20000000


NOTE_MASK_STRUM = 0x80000000

# A chord template's own mask (Rocksmith2014.NET ChordMask): an arpeggio's
# shape (an "-arp" template in the XML).
CHORD_MASK_ARPEGGIO = 1


TECHNIQUE_TO_MASK: dict[Technique, int] = {
    Technique.HAMMER_ON: NOTE_MASK_HAMMERON,
    Technique.PULL_OFF: NOTE_MASK_PULLOFF,
    Technique.SLIDE: NOTE_MASK_SLIDE,
    Technique.BEND: NOTE_MASK_BEND,
    Technique.HARMONIC: NOTE_MASK_HARMONIC,
    Technique.PALM_MUTE: NOTE_MASK_PALMMUTE,
    Technique.VIBRATO: NOTE_MASK_VIBRATO,
    Technique.TAP: NOTE_MASK_TAP,
    Technique.SLAP: NOTE_MASK_SLAP,
    Technique.POP: NOTE_MASK_PLUCK,
    Technique.ACCENT: NOTE_MASK_ACCENT,
    Technique.FRET_MUTE: NOTE_MASK_FRETHANDMUTE,
    Technique.PINCH_HARMONIC: NOTE_MASK_PINCHHARMONIC,
    Technique.TREMOLO: NOTE_MASK_TREMOLO,
}


# Back-compat alias for existing test imports.
TECHNIQUE_BITS = TECHNIQUE_TO_MASK


_NAME_LEN = 32


_LYRIC_LEN = 48


_CHORD_EPSILON_S = 0.03


# How far the automatic anchors merge neighbours: domain.hand.AUTO_WINDOW_SPAN.


# Dynamic Difficulty ceiling: the most difficulty levels a single phrase can
# ramp its notes in over (0..CAP). A phrase's ceiling scales with the note count
# of its busiest iteration, so a dense phrase reaches a higher difficulty than a
# sparse one — this is what gives each phrase's bar its own HEIGHT on the in-game
# difficulty graph instead of a flat top. Set to 20 to match a real DDC's range (a
# professional CDLC of Animals As Leaders "Tempting Time" decodes to phrase
# max-difficulties spread 0..18, mode 6). A HARD cap (not a proportional rescale)
# is deliberate: it preserves the natural 0..~18 spread of most phrases and only
# flattens the handful of extreme-density outliers (a fast tapping run can hit
# 50-70 notes/iteration) at the top, where a single outlier would otherwise squash
# every other phrase toward zero. Still a simplified DDC — graduated phrases and
# correct hero triples, no NLinkedDifficulty linkage.
_DD_LEVEL_CAP = 22


# Notes admitted per difficulty level. The game promotes a phrase ONE level per
# successful play of it, so the ceiling is literally how many times the passage
# must be played to reach the full chart. Ramping one note per level (the original
# rule) put the ceiling of almost every phrase at the cap: measured on a realistic
# 756-note chart the ceilings came out spread 11..20 with mode 20, i.e. TWENTY
# perfect playthroughs to see the whole song, and only ~15% of the notes after
# two — which reads in-game as "the difficulty never moves off the minimum", the
# reported bug. Admitting a small GROUP of notes per level reproduces the real
# DDC's shape instead: at 3 the same chart gives ceilings spread 3..15 with mode 7
# against the reference's 0..18 / mode 6. The top level is still the complete
# chart either way (``_level_notes`` saturates at the phrase ceiling) — this only
# sets how fast the player climbs to it.
_NOTES_PER_DD_LEVEL = 2


# Floor on the ceiling of a phrase that HAS notes. Without it a short phrase gets
# (n-1)//NOTES_PER_LEVEL == 0 levels — one level, no ramp, permanently pinned at
# the minimum no matter how well it is played. Byte-diffing a DLC Builder build
# of the user's own song against ours (both decoded from the shipped .psarc)
# showed this directly: a real DDC pass gives EVERY phrase with notes a ceiling
# of at least 4 (its 3-note phrase gets 4), while ours handed out 0 to four
# phrases and 1 to three more out of 29. Its ceilings also run about twice ours
# for the same note count (a 30-note phrase: 16 there, 9 here; a 63-note phrase:
# 22 there, 20 here), which is what _NOTES_PER_DD_LEVEL 3 -> 2 and the cap
# 20 -> 22 close. HONEST LIMIT: this is calibrated against that one reference
# file, not against the game — it removes phrases that provably cannot level up
# and brings the ramp's shape into the reference's range, but whether it is the
# whole of the reported "DD never leaves the minimum" is unverified in-game.
# NOT bounded by the note count: a one-note phrase gets the floor too, its note
# shown at every level up to it. It used to get ceiling 0 ("five identical levels
# would be no ramp") and a phrase with a note but no level to climb crashed the
# game the moment its difficulty was raised in Riff Repeater (September: the
# Lead's one-note phrase at 43.6 s, the Alternate Rhythm's pickup before the
# chorus). DLC Builder's build of that song gives its own one-note phrase SIX
# identical levels, and every phrase with notes there has a ceiling of 3 or more.
_DD_MIN_LEVELS = 4


# DLC Builder's phrase generator (Rocksmith2014.XML.Processing/PhraseGenerator.fs),
# which the native PSARC now follows: a new phrase every 8 measures, never
# closer than this to the previous one, and a "noguitar" phrase over a gap in
# the playing at least this long.
_MIN_PHRASE_SEPARATION_S = 2.0


_MIN_NOGUITAR_PHRASE_S = 2.5


_MEASURES_PER_PHRASE = 8


# Entry sizes of the Sng2014 sections RockForge writes empty but a real file may
# populate. Needed to SKIP them when reading someone else's SNG (see read_sng).
_PHRASE_EXTRA_SIZE = 12   # PhraseExtraInfoByLevel


_ACTION_SIZE = 260        # float time + char[256] name


LAST_CONVERSION = "01-01-00 00:00"   # see SngMetadata.last_conversion


_EVENT_CODE_LEN = 256     # the cue string's fixed field width


_EVENT_SIZE = 4 + _EVENT_CODE_LEN   # float time + char[256] (e2/E3/E13/D3 crowd cues)


_SNG_TONE_SIZE = 8        # float time + int32 tone id


_DNA_SIZE = 8             # float time + int32 dna id


# The SNG's CapoFret byte when the arrangement has no capo (a DLC Builder
# build writes 255; 0 would mean a capo placed at fret 0).
NO_CAPO = 255


_BEND_DATA_COUNT = 32  # fixed-size bend array per string in ChordNotes


@dataclass(frozen=True)
class SngBendData32:
    time: float
    step: float
    unk3: int = 0
    unk4: int = 0
    unk5: int = 0


@dataclass(frozen=True)
class SngBeat:
    time: float
    measure: int  # short; the beat's measure number (real, not -1)
    beat: int = 0  # beat within measure (short)
    phrase_iteration: int = -1
    # Bit 0 = first beat of the measure (downbeat), bit 1 = even measure. The
    # real Sng2014 Bpm carries this trailing int32; omitting it made every beat
    # 4 bytes short and misaligned the whole SNG, crashing the game on load.
    mask: int = 0


@dataclass(frozen=True)
class SngPhrase:
    name: str
    solo: int = 0
    disparity: int = 0
    ignore: int = 0
    max_difficulty: int = 0
    phrase_iteration_links: int = 0


@dataclass(frozen=True)
class SngPhraseIteration:
    phrase_id: int
    start_time: float
    end_time: float
    difficulty: tuple[int, int, int] = (0, 0, 0)


@dataclass(frozen=True)
class SngChordTemplate:
    mask: int
    frets: tuple[int, ...]  # 6 bytes
    fingers: tuple[int, ...]  # 6 bytes
    notes: tuple[int, ...]  # 6 × int32 (MIDI note per string)
    name: str


@dataclass
class SngChordNotes:
    note_mask: list[int]  # 6 × uint32
    bend_data: list[list[SngBendData32]]  # 6 strings × up to 32 bends
    slide_to: list[int]  # 6 bytes
    slide_unpitch_to: list[int]  # 6 bytes
    vibrato: list[int]  # 6 × int16


@dataclass(frozen=True)
class SngSection:
    name: str
    number: int
    start_time: float
    end_time: float
    start_phrase_iteration_id: int = 0
    end_phrase_iteration_id: int = 0
    string_mask: bytes = b"\x00" * 36


@dataclass(frozen=True)
class SngAnchor:
    start_time: float
    end_time: float
    first_note_time: float
    last_note_time: float
    fret: int
    width: int
    phrase_iteration_id: int = 0


@dataclass(frozen=True)
class SngAnchorExtension:
    """Slide anchor follow-through: the fretboard re-anchors to the slide's
    destination at the moment the slide ends (Rocksmith2014.NET
    ``AnchorExtension.fs`` / toolkit ``Sng2014FileWriter``)."""

    beat_time: float  # note.time + note.sustain (when the slide ends)
    fret: int  # the slide destination fret


@dataclass(frozen=True)
class SngFingerprint:
    chord_id: int
    start_time: float
    end_time: float
    first_note_time: float
    last_note_time: float


@dataclass
class SngNote:
    time: float
    string: int  # 0-5 for single, -1 (255 unsigned) for chord
    fret: int
    sustain: float
    bend: float
    mask: int
    note_flags: int = 0
    hash: int = 0
    anchor_fret: int = 0
    anchor_width: int = 4
    chord_id: int = -1
    chord_notes_id: int = -1
    phrase_id: int = 0
    phrase_iteration_id: int = 0
    fingerprint_id: tuple[int, int] = (-1, -1)
    next_iter_note: int = -1
    prev_iter_note: int = -1
    parent_prev_note: int = -1
    slide_to: int = -1          # -1 = no slide (a signed byte, 0xFF on disk)
    slide_unpitch_to: int = -1  # -1 = no unpitched slide
    # -1 = none, as DLC Builder writes them (XmlToSngNote.fs): we wrote 0,
    # which is a real value for each (finger 0, and a byte the game reads as a
    # tap/slap/pluck index) — found byte-diffing its September build.
    left_hand: int = -1
    tap: int = -1
    pick_direction: int = -1
    slap: int = -1
    pluck: int = -1
    vibrato: int = 0
    bend_data: list[SngBendData32] = field(default_factory=list)


@dataclass(frozen=True)
class SngVocal:
    time: float
    note: int
    length: float
    lyric: str


@dataclass
class SngArrangementLevel:
    difficulty: int = 0
    anchors: list[SngAnchor] = field(default_factory=list)
    anchor_extensions: list[SngAnchorExtension] = field(default_factory=list)
    fingerprints1: list[SngFingerprint] = field(default_factory=list)
    fingerprints2: list[SngFingerprint] = field(default_factory=list)
    notes: list[SngNote] = field(default_factory=list)
    phrase_count: int = 0
    avg_notes_per_iteration: list[float] = field(default_factory=list)
    notes_in_iteration1: list[int] = field(default_factory=list)
    notes_in_iteration2: list[int] = field(default_factory=list)


@dataclass
class SngMetadata:
    max_score: float = 100_000.0
    max_notes_and_chords: float = 0.0
    max_notes_and_chords_real: float = 0.0
    points_per_note: float = 0.0
    first_beat_length: float = 0.5
    start_time: float = 0.0
    capo_fret: int = 0
    # The reference writes its build time as MM-DD-YY HH:MM. Ours is FIXED, not
    # a timestamp: a value that changes on every rebuild is the kind of thing
    # that could invalidate saved per-song progress, and a deterministic build
    # is worth more here than an accurate date (same reasoning as the
    # deterministic persistent IDs). The format now matches the reference.
    last_conversion: str = LAST_CONVERSION
    part: int = 1
    song_length: float = 0.0
    string_count: int = 6
    tuning: tuple[int, ...] = (0, 0, 0, 0, 0, 0)
    first_note_time: float = 0.0
    first_note_time2: float = 0.0
    max_difficulty: int = 0


@dataclass(frozen=True)
class SngEvent:
    """One stage/crowd cue on the song timeline (SNG section 10)."""

    time: float
    code: str


@dataclass
class SngTone:
    """A tone change: at ``time`` switch to slot ``tone_id`` (0-3 = Tone_A..D)."""

    time: float
    tone_id: int


@dataclass
class SngModel:
    beats: list[SngBeat] = field(default_factory=list)
    phrases: list[SngPhrase] = field(default_factory=list)
    chord_templates: list[SngChordTemplate] = field(default_factory=list)
    chord_notes: list[SngChordNotes] = field(default_factory=list)
    vocals: list[SngVocal] = field(default_factory=list)
    phrase_iterations: list[SngPhraseIteration] = field(default_factory=list)
    events: list[SngEvent] = field(default_factory=list)
    tones: list[SngTone] = field(default_factory=list)
    sections: list[SngSection] = field(default_factory=list)
    arrangements: list[SngArrangementLevel] = field(default_factory=list)
    metadata: SngMetadata = field(default_factory=SngMetadata)
