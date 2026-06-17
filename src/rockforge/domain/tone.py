"""Tone aggregate: a full Rocksmith gear definition (amp + cabinet + pedals).

This mirrors the Rocksmith2014.NET ``Tone`` model (``Tone.fs``, MIT) closely
enough to serialize a working ``ToneDto`` into a DLC Builder ``.rs2dlc`` project
— so a tone the user builds in RockForge loads and plays in-game without having
to recreate it in DLC Builder's tone editor.

Honesty note: RockForge does not model gear physics; it only references gear by
the catalogue ``Key`` (see ``infrastructure/packaging/gear``). Knob values that
the user does not set fall back to the gear's catalogue ``DefaultValue`` — the
same thing DLC Builder does when you drop stock gear into a tone.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# A tone's switchable name (``tone_base`` / ``tone_names`` / ``ToneChange.name``)
# references a ``Tone.key``; the XML and the instrumental DTO carry those keys,
# DLC Builder matches them to the project's ``Tones`` by ``Key``.


@dataclass(frozen=True)
class Pedal:
    """One gear piece (amp, cabinet, pedal or rack) within a tone's signal chain.

    ``gear_type`` is the catalogue ``Type`` (``Amps`` / ``Cabinets`` /
    ``Pedals`` / ``Racks``); ``key`` is the catalogue gear ``Key`` (e.g.
    ``Amp_MarshallJCM800``); ``knob_values`` maps each knob's full ``Key`` to its
    value. ``category`` is the catalogue ``Category`` (mic/position for cabinets,
    effect family for pedals) and is omitted when ``None``.
    """

    gear_type: str
    key: str
    knob_values: dict[str, float] = field(default_factory=dict)
    category: str | None = None


@dataclass(frozen=True)
class Gear:
    """The signal chain: an amp + cabinet, with up to 4 racks / pre / post pedals."""

    amp: Pedal
    cabinet: Pedal
    racks: tuple[Pedal | None, ...] = (None, None, None, None)
    pre_pedals: tuple[Pedal | None, ...] = (None, None, None, None)
    post_pedals: tuple[Pedal | None, ...] = (None, None, None, None)


@dataclass(frozen=True)
class Tone:
    """A complete, named tone the user can assign and switch to.

    ``key`` is the identifier referenced by ``Arrangement.tone_base`` /
    ``tone_names`` / ``ToneChange.name``. ``descriptors`` are the Rocksmith tone
    descriptor strings (``$[id]NAME``); ``volume`` is the tone's output volume in
    dB (DLC Builder's "Calculate Volumes" recomputes it if left at a default).
    """

    key: str
    name: str
    gear: Gear
    descriptors: tuple[str, ...] = ()
    volume: float = -15.0

    def gear_keys(self) -> list[str]:
        """All catalogue gear keys used by this tone (for validation/UI)."""
        pedals = [self.gear.amp, self.gear.cabinet]
        for slot in (*self.gear.racks, *self.gear.pre_pedals, *self.gear.post_pedals):
            if slot is not None:
                pedals.append(slot)
        return [p.key for p in pedals]
