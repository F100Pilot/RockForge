# Vendored tone gear catalogue

`tone_gear_data.json` is the Rocksmith 2014 gear database (amps, cabinets,
pedals, racks) used to build real, in-game-valid tones, copied verbatim from
[`iminashi/Rocksmith2014.NET`](https://github.com/iminashi/Rocksmith2014.NET)
(`samples/DLCBuilder.Domain/Tones/tone_gear_data.json`, MIT). It is the same
catalogue DLC Builder uses to populate its tone editor.

Each entry: `{ Name, Type, Category, Key, Knobs: [{ Name, Key, UnitType,
MinValue, MaxValue, ValueStep, DefaultValue, (EnumValues) }] }`. `Type` is one
of `Amps` / `Cabinets` / `Pedals` / `Racks`. The knob `Key` (not the display
`Name`) is authoritative for `KnobValues` — e.g. the JCM800 "Presence" knob is
`Amp_MarshallJCM800_Pres`, "PreAmp" is `Amp_MarshallJCM800_Gain`. RockForge
reads this file via `gear_catalogue.py`; do not hand-edit knob keys.

`TONE.md` (repo root) is a prose summary of this data for humans; this JSON is
the machine-readable source of truth.

`default_tones/default_lead.json` / `default_rhythm.json` are DLC Builder's
default tones, copied verbatim from the same repository
(`samples/DLCBuilder.Domain/Tones/`, MIT). DLC Builder gives one to every
arrangement without a tone of its own; `default_tones.py` does the same for the
native PSARC.

