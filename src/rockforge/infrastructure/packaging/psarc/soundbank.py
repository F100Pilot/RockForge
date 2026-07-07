"""Native Wwise SoundBank (``.bnk``) generation (phase 7 of the native-PSARC plan).

Rocksmith reads its song audio through a Wwise SoundBank: the ``.bnk`` carries a
``Play_<key>`` event and a 100 ms *prefetch* of the audio, and the full stream
lives in a separate ``<fileID>.wem`` next to it. Without the ``.bnk`` the game
can list a song (once the appid/manifests are right) but has no event to fire,
so it plays silence — the last gap that kept the native PSARC from being
game-ready.

Like DLC Builder / Rocksmith2014.NET, RockForge does NOT ask Wwise to build the
bank: Wwise only produces the ``.wem`` (``wwise.py``); the ``.bnk`` is generated
here in code with a matching random ``fileID``. This mirrors
``SoundBankGenerator2014.GenerateSoundBank`` from the Rocksmith Custom Song
Toolkit (MIT) — the same lineage as ``sng.py``.

Layout (PC / little-endian): ``BKHD → DIDX → DATA → HIRC → STID`` chunks, each a
4-byte ASCII tag + int32 length + body. HIRC holds four objects (Sound,
ActorMixer, Action, Event). Object/file/soundbank IDs are random (as they are in
DLC Builder). ``generate_soundbank`` returns the ``.bnk`` bytes and the integer
``fileID`` — the name the full ``.wem`` must be packed under.

Unverified-by-design (CLAUDE.md, same as ``sng.py``): the layout is ported from
the open toolkit source and round-tripped by :func:`read_wem_file_id` /
:func:`read_bkhd_version`, but is NOT byte-diffed against a retail bnk — there is
no reference file in CI. The trustworthy audio path remains the DLC Builder
bundle (which drives a real Wwise).
"""

from __future__ import annotations

import io
import random
import struct

_PLAY = "Play_"
_SONG = "Song_"

# Wwise embeds a short prefetch of the stream in the bank; the toolkit uses a
# fixed 51200 bytes (~100 ms) and stores the full audio as the separate .wem.
_PREFETCH_BYTES = 51200

# BKHD version tag Rocksmith 2014 expects; anything else is rejected on load.
_BNK_VERSION = 91

# Fixed magic constants ported verbatim from SoundBankGenerator2014 (toolkit).
_PLUGIN_ID = 262145
_STREAM_TYPE = 2
_DIRECT_PARENT_ID_PC = 65536
_ACTORMIXER_PARENT_BUS_ID = 2616261673
_ACTORMIXER_UNK_ID2 = 65792
_MIXER_ID = 650605636
_ACTION_TYPE = 1027

_HIERARCHY_SOUND = 2
_HIERARCHY_ACTION = 3
_HIERARCHY_EVENT = 4
_HIERARCHY_ACTORMIXER = 7


def _fnv_hash(text: str) -> int:
    """Wwise FNV-1 hash (multiply-then-xor over the lowercased string)."""
    h = 2166136261
    for ch in text.lower():
        h = (h * 16777619) & 0xFFFFFFFF
        h = (h ^ ord(ch)) & 0xFFFFFFFF
    return h


def _u32(v: int) -> bytes:
    return struct.pack("<I", v & 0xFFFFFFFF)


def _u16(v: int) -> bytes:
    return struct.pack("<H", v & 0xFFFF)


def _u8(v: int) -> bytes:
    return struct.pack("<B", v & 0xFF)


def _f32(v: float) -> bytes:
    return struct.pack("<f", v)


def _header(soundbank_id: int, didx_size: int) -> bytes:
    """BKHD body: version/id/language/feedback + alignment padding so DATA lands
    on a 16-byte boundary (PC), exactly as the toolkit computes it."""
    body = _u32(_BNK_VERSION) + _u32(soundbank_id) + _u32(0) + _u32(0)
    align_size = 16  # PC (consoles use 2048; RockForge targets PC only)
    junk_size = 24 + didx_size
    padding = (len(body) + junk_size) % align_size
    if padding != 0:
        body += _u32(0) * ((align_size - padding) // 4)
    return body


def _data_index(file_id: int, length: int) -> bytes:
    return _u32(file_id) + _u32(0) + _u32(length)


def _hierarchy_sound(
    sound_id: int, file_id: int, mixer_id: int, volume: float, rng: random.Random
) -> bytes:
    return b"".join((
        _u32(sound_id),
        _u32(_PLUGIN_ID),
        _u32(_STREAM_TYPE),
        _u32(file_id),
        _u32(file_id),          # sourceID == fileID
        _u8(0),                 # languageSpecific (SFX)
        _u8(0),                 # overrideParent
        _u8(0),                 # numFX
        _u32(rng.getrandbits(32)),  # parentBusID
        _u32(_DIRECT_PARENT_ID_PC),
        _u32(0),                # unkID1 (0 = not preview)
        _u32(mixer_id),
        _u8(0),                 # priorityOverrideParent
        _u8(0),                 # priorityApplyDist
        _u8(0),                 # overrideMidi
        _u8(3),                 # numParam
        _u8(0),                 # param1: Volume
        _u8(46),                # param2: MidiNoteOnAction
        _u8(47),                # param3: MidiNoteOffAction
        _f32(volume),           # param1 value
        _u32(1),                # param2 value
        _u32(3),                # param3 value
        _u8(0),                 # numRange
        _u8(0),                 # positionOverride
        _u8(0),                 # overrideGameAux
        _u8(0),                 # useGameAux
        _u8(0),                 # overrideUserAux
        _u8(0),                 # hasAux
        _u8(0),                 # virtualQueueBehavior
        _u8(0),                 # killNewest
        _u8(0),                 # useVirtualBehavior
        _u16(0),                # maxNumInstance
        _u8(0),                 # isGlobalLimit
        _u8(0),                 # belowThresholdBehavior
        _u8(0),                 # isMaxNumInstOverrideParent
        _u8(0),                 # isVVoiceOptOverrideParent
        _u32(0),                # stateGroupList
        _u16(0),                # rtpcList
        _u32(0),                # feedbackBus
    ))


def _hierarchy_actormixer(mixer_id: int, sound_id: int) -> bytes:
    return b"".join((
        _u32(mixer_id),
        _u8(0),                 # overrideParent
        _u8(0),                 # numFX
        _u32(_ACTORMIXER_PARENT_BUS_ID),
        _u32(0),                # directParentID
        _u32(0),                # unkID1
        _u32(_ACTORMIXER_UNK_ID2),
        _u8(0),                 # priorityOverrideParent
        _u8(0),                 # priorityApplyDist
        _u8(0),                 # numParam
        _u8(0),                 # numRange
        _u8(0),                 # positionOverride
        _u8(0),                 # overrideGameAux
        _u8(0),                 # useGameAux
        _u8(0),                 # overrideUserAux
        _u8(0),                 # hasAux
        _u8(0),                 # virtualQueueBehavior
        _u8(0),                 # killNewest
        _u8(0),                 # useVirtualBehavior
        _u16(0),                # maxNumInstance
        _u8(0),                 # isGlobalLimit
        _u8(0),                 # belowThresholdBehavior
        _u8(0),                 # isMaxNumInstOverrideParent
        _u8(0),                 # isVVoiceOptOverrideParent
        _u32(0),                # stateGroupList
        _u16(0),                # rtpcList
        _u32(1),                # numChild
        _u32(sound_id),         # child1
    ))


def _hierarchy_action(action_id: int, object_id: int, soundbank_id: int) -> bytes:
    return b"".join((
        _u32(action_id),
        _u16(_ACTION_TYPE),
        _u32(object_id),
        _u8(0),                 # isBus
        _u8(0),                 # numParam
        _u8(0),                 # numRange
        _u8(4),                 # fadeCurve
        _u32(soundbank_id),
    ))


def _hierarchy_event(action_id: int, name: str) -> bytes:
    return b"".join((
        _u32(_fnv_hash(_PLAY + name)),
        _u32(1),                # numEvents
        _u32(action_id),
    ))


def _hierarchy(
    soundbank_id: int, sound_id: int, file_id: int, name: str, volume: float, rng: random.Random
) -> bytes:
    action_id = rng.getrandbits(32)
    objects = (
        (_HIERARCHY_SOUND, _hierarchy_sound(sound_id, file_id, _MIXER_ID, volume, rng)),
        (_HIERARCHY_ACTORMIXER, _hierarchy_actormixer(_MIXER_ID, sound_id)),
        (_HIERARCHY_ACTION, _hierarchy_action(action_id, sound_id, soundbank_id)),
        (_HIERARCHY_EVENT, _hierarchy_event(action_id, name)),
    )
    out = io.BytesIO()
    out.write(_u32(len(objects)))
    for type_id, body in objects:
        out.write(_u8(type_id))
        out.write(_u32(len(body)))
        out.write(body)
    return out.getvalue()


def _string_id(soundbank_id: int, name: str) -> bytes:
    bank_name = (_SONG + name).encode("ascii")
    return _u32(1) + _u32(1) + _u32(soundbank_id) + _u8(len(bank_name)) + bank_name


def _write_chunk(out: io.BytesIO, tag: str, body: bytes) -> None:
    out.write(tag.encode("ascii"))
    out.write(struct.pack("<i", len(body)))
    out.write(body)


def generate_soundbank(
    soundbank_name: str,
    wem: bytes,
    volume: float = 0.0,
    *,
    rng: random.Random | None = None,
) -> tuple[bytes, int]:
    """Build a Rocksmith 2014 song ``.bnk`` for ``wem``.

    Returns ``(bnk_bytes, file_id)``; the full ``.wem`` must be packed as
    ``<file_id>.wem`` so the bank's DIDX reference resolves. ``volume`` is the
    Wwise bus volume in dB (0 = unity; DLC Builder's "Calculate Volumes"
    recomputes it on import). ``rng`` is injectable for deterministic tests.
    """
    rng = rng or random.Random()
    soundbank_id = rng.getrandbits(32)
    file_id = rng.getrandbits(32)
    sound_id = rng.getrandbits(32)

    data_chunk = wem[:_PREFETCH_BYTES]
    didx = _data_index(file_id, len(data_chunk))
    header = _header(soundbank_id, len(didx))
    hierarchy = _hierarchy(soundbank_id, sound_id, file_id, soundbank_name, volume, rng)
    string_id = _string_id(soundbank_id, soundbank_name)

    out = io.BytesIO()
    _write_chunk(out, "BKHD", header)
    _write_chunk(out, "DIDX", didx)
    _write_chunk(out, "DATA", data_chunk)
    _write_chunk(out, "HIRC", hierarchy)
    _write_chunk(out, "STID", string_id)
    return out.getvalue(), file_id


def read_bkhd_version(bnk: bytes) -> int:
    """Read the BKHD version tag (91 for RS2014). Raises on a bad magic."""
    if bnk[:4] != b"BKHD":
        raise ValueError("not a SoundBank: missing BKHD magic")
    return int(struct.unpack_from("<I", bnk, 8)[0])


def read_wem_file_id(bnk: bytes) -> int:
    """Cross-reference the ``<id>.wem`` the bank points at (from its DIDX)."""
    if bnk[:4] != b"BKHD":
        raise ValueError("not a SoundBank: missing BKHD magic")
    len_bkhd = struct.unpack_from("<I", bnk, 4)[0]
    didx_off = len_bkhd + 8
    if bnk[didx_off:didx_off + 4] != b"DIDX":
        raise ValueError("SoundBank has no DIDX section")
    return int(struct.unpack_from("<I", bnk, didx_off + 8)[0])
