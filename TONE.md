# Tone gear reference (DLC Builder / Rocksmith2014.NET)

Reference notes for implementing a minimal `BaseTone` in RockForge (currently
empty — see "Album cover art" / tone-related honesty notes in `CLAUDE.md`).
Source: [`iminashi/Rocksmith2014.NET`](https://github.com/iminashi/Rocksmith2014.NET),
which is what DLC Builder is built from.

## Data model (`src/Rocksmith2014.Common/Manifest/Tone.fs`)

```fsharp
type Tone = {
    GearList: Gear
    ToneDescriptors: string array
    NameSeparator: string
    Volume: float
    MacVolume: float option
    Key: string
    Name: string
    SortOrder: float32 option
}

type Gear = {
    Amp: Pedal
    Cabinet: Pedal
    Racks: Pedal option array       // up to 4 rack units
    PrePedals: Pedal option array   // up to 4 pre-amp pedals
    PostPedals: Pedal option array  // up to 4 post-amp pedals
}

type Pedal = {
    Type: string
    KnobValues: Map<string, float32>
    Key: string
    Category: string option
    Skin: string option
    SkinIndex: float32 option
}
```

Each gear piece is identified by a `Key` (e.g. `Amp_MarshallJCM800`), and each
`Knob` of that gear piece has its own key
(`Amp_MarshallJCM800_Gain`, `Amp_MarshallJCM800_Bass`, ...) with
`UnitType` (`number`/`db`/`hz`/`%`/`enum`), `MinValue`, `MaxValue`,
`ValueStep`, `DefaultValue`.

Gear database (the full catalogue used to populate the tone editor UI):
`samples/DLCBuilder.Domain/Tones/tone_gear_data.json`. Example minimal tones:
`default_lead.json`, `default_rhythm.json`, `default_bass.json` in the same
folder.

## Amps (`Amps`, Category `Amp`) — guitar

| Name | Key |
| --- | --- |
| AT-120 | `Amp_AT120` |
| AT-20 | `Amp_AT20` |
| BTQ-15 | `Amp_BT15` |
| BTQ-30 | `Amp_BT30` |
| BTQ-45 | `Amp_BT45` |
| Cali-100 | `Amp_CA100` |
| Cali-38 | `Amp_CA38` |
| Cali-85 | `Amp_CA85` |
| CL-SS 100 | `Amp_CS100` |
| CL-SS 120 | `Amp_CS120` |
| CL-SS 90 | `Amp_CS90` |
| EN-30 | `Amp_EN30` |
| EN-50 | `Amp_EN50` |
| Epiphone Electar Century | `Amp_EpiphoneElectarCentury` |
| Epiphone Electar Model M | `Amp_EpiphoneElectarM` |
| Epiphone Electric Hawaiian | `Amp_EpiphoneElectricHawaiian` |
| Epiphone Zephyr | `Amp_EpiphoneZephyr` |
| GBC-1H | `Amp_GB100` |
| GBC-38 | `Amp_GB38` |
| GBC-50 | `Amp_GB50` |
| Gibson GA-79 | `Amp_GibsonGA79` |
| Gibson GA-8 | `Amp_GibsonGA8` |
| Gibson GA-88 | `Amp_GibsonGA88` |
| HG-100 | `Amp_HG100` |
| HG-180 | `Amp_HG180` |
| HG-500 | `Amp_HG500` |
| Marshall 1962 "Bluesbreaker" | `Amp_Marshall1962Bluesbreaker` |
| Marshall DSL100H | `Amp_MarshallDSL100H` |
| Marshall DSL15H | `Amp_MarshallDSL15H` |
| Marshall JCM800 | `Amp_MarshallJCM800` |
| Marshall JTM45 | `Amp_MarshallJTM45` |
| Marshall JVM410H | `Amp_MarshallJVM410H` |
| Marshall Plexi | `Amp_MarshallPlexi` |
| Orange AD50 | `Amp_OrangeAD50` |
| Orange 'Jimmy Bean' Amp | `Amp_OrangeJimmyBean` |
| Orange OR100 | `Amp_OrangeOR100` |
| Orange OR50H | `Amp_OrangeOR50H` |
| Orange Rockerverb 50 MkII | `Amp_OrangeRockerverb` |
| Orange Tiny Terror | `Amp_OrangeTinyTerror` |
| AMTW-22 | `Amp_TW22` |
| AMTW-26 | `Amp_TW26` |
| AMTW-40 | `Amp_TW40` |

## Amps — bass

| Name | Key |
| --- | --- |
| BH-600B | `Bass_Amp_BT600B` |
| BH-880B | `Bass_Amp_BT880B` |
| BH-975B | `Bass_Amp_BT975B` |
| CLH-300B | `Bass_Amp_CH300B` |
| CLH-350B | `Bass_Amp_CH350B` |
| CLH-600B | `Bass_Amp_CH600B` |
| CSS-240B | `Bass_Amp_CS240B` |
| CSS-300B | `Bass_Amp_CS300B` |
| CSS-75B | `Bass_Amp_CS75B` |
| Eden E300 | `Bass_Amp_EdenE300` |
| Eden WT550 | `Bass_Amp_EdenWT550` |
| Eden WT800 | `Bass_Amp_EdenWT800` |
| HW100B | `Bass_Amp_HT100B` |
| HW-300B | `Bass_Amp_HT300B` |
| HW-400B | `Bass_Amp_HT400B` |
| LW-25B | `Bass_Amp_LT25B` |
| LW-85B | `Bass_Amp_LT85B` |
| Orange AD200B | `Bass_Amp_OrangeAD200B` |

## DI ("amps" with no real amp stage)

| Name | Key |
| --- | --- |
| DI. Bass Driver | `DI_Amp_BassDriver` |
| DI. Mixer | `DI_Amp_MixerPre` |

## Cabinets (`Cabinets`)

Each physical cabinet model is listed 9x: 3 microphones (`57` = dynamic
SM57-style, `Condenser`, `Ribbon`) x 3 positions (`Cone`, `Edge`,
`OffAxis`), key pattern `Cab_<Model>_<Mic>_<Position>`, Category
`<Mic name> <Position>` (e.g. `Dynamic Cone`, `Condenser Edge`, `Ribbon Off
Axis`).

Guitar cabinet models (each with the 9 mic/position variants above):

- AT-0112C (`Cab_AT0112C_*`)
- AT-112.1C (`Cab_AT1121C_*`)
- BT-1120C (`Cab_BT1120C_*`)
- BT-112.1C (`Cab_BT1121C_*`)
- CA-112C (`Cab_CA112C_*`)
- EN-212C (`Cab_EN212C_*`)
- GB-412 MKI / MKII / MKIII (`Cab_GB412CMKI_*`, `Cab_GB412CMKII_*`, `Cab_GB412CMKIII_*`)
- HG-212C (`Cab_HG212C_*`)
- HG-2120C (`Cab_HG2120C_*`)
- Marshall 1936 (`Cab_Marshall1936_*`)
- Marshall 1960 AX (`Cab_Marshall1960AX_*`)
- Marshall 1960a (`Cab_Marshall1960a_*`)
- Marshall 1960 TV (`Cab_Marshall1960TV_*`)
- Orange 'Jimmy Bean' Cab (`Cab_OrangeJimmyBean_*`)
- Orange PPC212OB (`Cab_OrangePPC212OB_*`)
- Orange PPC412 (`Cab_OrangePPC412_*`)
- TW-110C (`Cab_TW110C_*`)
- TW-112C (`Cab_TW112C_*`)

Bass cabinet models (same 9 variants each):

- BT-410C (`Cab_BT410C_*`)
- CA-215C (`Cab_CA215C_*`)
- CA-412C (`Cab_CA412C_*`)
- CSS-1120C (`Cab_CS1120C_*`)
- CSS-1515C (`Cab_CS1515C_*`)
- CSS-212C (`Cab_CS212C_*`)
- EN-4120C (`Cab_EN4120C_*`)
- HG-215C (`Cab_HG215C_*`)
- TW-410C (`Cab_TW410C_*`)

PA / novelty cabinets (single entry, Category `PA`, no mic/position variants):

| Name | Key |
| --- | --- |
| Audiophile Speakers | `Cab_Audiophile` |
| Boom Box | `Cab_BoomBox` |
| Console Radio | `Cab_CabinetRadio` |
| Gramophone | `Cab_Gramophone` |
| Jukebox | `Cab_JukeBox` |
| PS-115.2C | `Cab_PA1152C` |
| PS-600 | `Cab_PA600C` |
| PA-999C | `Cab_PA999C` |
| Vintage Hi-Fi setup | `Cab_VintageHiFi` |

## Pedals (`Pedals`) — bass

| Name | Key | Category |
| --- | --- | --- |
| Bass Auto Filter | `Bass_Pedal_BassAutoFilter` | Filter |
| Bass Chorus | `Bass_Pedal_BassChorus` | Modulation |
| Bass Distortion | `Bass_Pedal_BassDistortion` | Distortion |
| Bass Enbiggenator | `Bass_Pedal_BassEnbig` | Modulation |
| 8-Band Bass EQ | `Bass_Pedal_BassEQ8` | Filter |
| Bass Filter Delay | `Bass_Pedal_BassFilterDelay` | Delay |
| Bass Filter Echo | `Bass_Pedal_BassFilterEcho` | Delay |
| Bass Flange | `Bass_Pedal_BassFlanger` | Modulation |
| Bass Fuzz | `Bass_Pedal_BassFuzz` | Distortion |
| Bass Overdrive | `Bass_Pedal_BassOverdrive` | Distortion |
| Bass Phase | `Bass_Pedal_BassPhase` | Modulation |
| Bass Sub Octave | `Bass_Pedal_BassSubOctave` | Pitch |
| Bass Wah | `Bass_Pedal_BassWah` | Filter |
| Eden WT D.I. | `Bass_Pedal_EdenWTDI` | Filter |
| MB Comp | `Bass_Pedal_MBComp` | Dynamics |

Note: the full gear database (`tone_gear_data.json`) also contains a much
larger set of guitar effect pedals/racks (drive, modulation, delay, EQ, wah,
pitch, etc.) not enumerated here — fetch the file directly when a specific
effect is needed.

## Minimal `BaseTone` candidate

A simple, clean amp + cabinet + DI combo with no pedals — e.g.:

- `Amp`: `Amp_MarshallJCM800` (or any clean/general-purpose amp)
- `Cabinet`: `Cab_Marshall1960a_57_Cone` (matching 4x12 cab, dynamic mic, on-cone)
- `Racks` / `PrePedals` / `PostPedals`: empty (`None` x4 each)
- `KnobValues`: each gear's knobs at their `DefaultValue` from
  `tone_gear_data.json`

This would give DLC Builder a valid, non-empty `BaseTone` so it stops flagging
"tone missing" — refinement (matching genre/instrument, adding pedals) is a
later, separate task.
