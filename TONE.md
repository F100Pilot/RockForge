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

For each knob: `unit, min..max step step, default=X` (knob `Key` is
`<AmpKey>_<KnobName without spaces/dots>`, e.g. `Amp_AT120_Gain`).

- **AT-120** (`Amp_AT120`): Gain number 1..100/1 def 50; Bass number 1..100/1 def 44; Mid number 1..100/1 def 66; Treble number 1..100/1 def 66
- **AT-20** (`Amp_AT20`): Gain number 1..100/1 def 32; Bass number 1..100/1 def 50; Treble number 1..100/1 def 85
- **BTQ-15** (`Amp_BT15`): Gain number 1..100/1 def 88; Bass number 1..100/1 def 65; Mid number 1..100/1 def 66; Treble number 1..100/1 def 80
- **BTQ-30** (`Amp_BT30`): Gain number 1..100/1 def 72; Bass number 1..100/1 def 65; Mid number 1..100/1 def 66; Treble number 1..100/1 def 74
- **BTQ-45** (`Amp_BT45`): Gain number 1..100/1 def 40; Bass number 1..100/1 def 65; Mid number 1..100/1 def 66; Treble number 1..100/1 def 56
- **Cali-100** (`Amp_CA100`): Gain number 1..100/1 def 100; Bass number 1..100/1 def 55; Mid number 1..100/1 def 85; Treble number 1..100/1 def 100; Presence number 1..100/1 def 30
- **Cali-38** (`Amp_CA38`): Gain number 1..100/1 def 65; Bass number 1..100/1 def 80; Mid number 1..100/1 def 80; Treble number 1..100/1 def 70
- **Cali-85** (`Amp_CA85`): Gain number 1..100/1 def 12; Bass number 1..100/1 def 71; Mid number 1..100/1 def 42; Treble number 1..100/1 def 74
- **CL-SS 100** (`Amp_CS100`): Gain number 1..100/1 def 12; Bass number 1..100/1 def 60; Mid number 1..100/1 def 60; Treble number 1..100/1 def 75
- **CL-SS 120** (`Amp_CS120`): Gain number 1..100/1 def 5; Bass number 1..100/1 def 60; Mid number 1..100/1 def 60; Treble number 1..100/1 def 70
- **CL-SS 90** (`Amp_CS90`): Gain number 1..100/1 def 2; Bass number 1..100/1 def 60; Mid number 1..100/1 def 60; Treble number 1..100/1 def 70
- **EN-30** (`Amp_EN30`): Gain number 1..100/1 def 60; Bass number 1..100/1 def 32; Treble number 1..100/1 def 88; Mid number 1..100/1 def 68; Bright enum 0..1/1 def 1; Presence number 1..100/1 def 30
- **EN-50** (`Amp_EN50`): Gain number 1..100/1 def 85; Bass number 1..100/1 def 80; Mid number 1..100/1 def 24; Treble number 1..100/1 def 76; Bright enum 0..1/1 def 1
- **Epiphone Electar Century** (`Amp_EpiphoneElectarCentury`): Volume number 1..100/1 def 88
- **Epiphone Electar Model M** (`Amp_EpiphoneElectarM`): Gain number 1..100/1 def 88
- **Epiphone Electric Hawaiian** (`Amp_EpiphoneElectricHawaiian`): Gain number 1..100/1 def 88; Tone number 1..100/1 def 75
- **Epiphone Zephyr** (`Amp_EpiphoneZephyr`): Speaker number 1..100/1 def 88; Bass number 1..100/1 def 75; Treble number 1..100/1 def 66
- **GBC-1H** (`Amp_GB100`): Gain number 1..100/1 def 100; Bass number 1..100/1 def 100; Mid number 1..100/1 def 100; Treble number 1..100/1 def 100; Presence number 1..100/1 def 52
- **GBC-38** (`Amp_GB38`): Gain number 1..100/1 def 65; Bass number 1..100/1 def 55; Mid number 1..100/1 def 85; Treble number 1..100/1 def 80; Presence number 1..100/1 def 30
- **GBC-50** (`Amp_GB50`): Gain number 1..100/1 def 55; Bass number 1..100/1 def 65; Mid number 1..100/1 def 62; Treble number 1..100/1 def 80; Presence number 1..100/1 def 76
- **Gibson GA-79** (`Amp_GibsonGA79`): Volume 1 number 1..100/1 def 88; Bass number 1..100/1 def 75; Treble number 1..100/1 def 66
- **Gibson GA-8** (`Amp_GibsonGA8`): Loudness number 1..100/1 def 88; Bass number 1..100/1 def 75; Treble number 1..100/1 def 66
- **Gibson GA-88** (`Amp_GibsonGA88`): Volume number 1..100/1 def 88; Bass number 1..100/1 def 75; Treble number 1..100/1 def 66
- **HG-100** (`Amp_HG100`): Gain number 1..100/1 def 100; Bass number 1..100/1 def 80; Mid number 1..100/1 def 69; Treble number 1..100/1 def 85
- **HG-180** (`Amp_HG180`): Gain number 1..100/1 def 100; Bass number 1..100/1 def 88; Mid number 1..100/1 def 80; Treble number 1..100/1 def 68
- **HG-500** (`Amp_HG500`): Gain number 1..100/1 def 100; Bass number 1..100/1 def 65; Mid number 1..100/1 def 44; Mid-Frequency number 1..100/1 def 38; Treble number 1..100/1 def 86
- **Marshall 1962 "Bluesbreaker"** (`Amp_Marshall1962Bluesbreaker`): Volume number 1..100/1 def 88; Bass number 1..100/1 def 75; Mid number 1..100/1 def 66; Treble number 1..100/1 def 66; Presence number 1..100/1 def 30
- **Marshall DSL100H** (`Amp_MarshallDSL100H`): Gain number 1..100/1 def 88; Bass number 1..100/1 def 75; Mid number 1..100/1 def 66; Treble number 1..100/1 def 66; Presence number 1..100/1 def 30; Resonance number 1..100/1 def 30
- **Marshall DSL15H** (`Amp_MarshallDSL15H`): Gain number 1..100/1 def 88; Bass number 1..100/1 def 75; Mid number 1..100/1 def 66; Treble number 1..100/1 def 66; Presence number 1..100/1 def 30
- **Marshall JCM800** (`Amp_MarshallJCM800`): PreAmp number 1..100/1 def 88; Bass number 1..100/1 def 75; Mid number 1..100/1 def 66; Treble number 1..100/1 def 66; Presence number 1..100/1 def 30
- **Marshall JTM45** (`Amp_MarshallJTM45`): Vol 1 number 1..100/1 def 88; Bass number 1..100/1 def 75; Mid number 1..100/1 def 66; Treble number 1..100/1 def 66; Presence number 1..100/1 def 30
- **Marshall JVM410H** (`Amp_MarshallJVM410H`): Gain number 1..100/1 def 88; Bass number 1..100/1 def 75; Mid number 1..100/1 def 66; Treble number 1..100/1 def 66; Presence number 1..100/1 def 30
- **Marshall Plexi** (`Amp_MarshallPlexi`): Loudness 1 number 1..100/1 def 88; Loudness 2 number 1..100/1 def 88; Bass number 1..100/1 def 75; Mid number 1..100/1 def 66; Treble number 1..100/1 def 66; Presence number 1..100/1 def 30
- **Orange AD50** (`Amp_OrangeAD50`): Gain number 1..100/1 def 88; Bass number 1..100/1 def 75; Treble number 1..100/1 def 66; Presence number 1..100/1 def 66
- **Orange 'Jimmy Bean' Amp** (`Amp_OrangeJimmyBean`): Volume number 1..100/1 def 88; Bass number 1..100/1 def 75; Mid number 1..100/1 def 66; Treble number 1..100/1 def 66
- **Orange OR100** (`Amp_OrangeOR100`): Gain number 1..100/1 def 88; Bass number 1..100/1 def 75; Mid number 1..100/1 def 66; Treble number 1..100/1 def 66
- **Orange OR50H** (`Amp_OrangeOR50H`): Gain number 1..100/1 def 88; Bass number 1..100/1 def 75; Mid number 1..100/1 def 66; Treble number 1..100/1 def 66; Punch number 1..100/1 def 66
- **Orange Rockerverb 50 MkII** (`Amp_OrangeRockerverb`): Gain number 1..100/1 def 88; Bass number 1..100/1 def 75; Mid number 1..100/1 def 66; Treble number 1..100/1 def 66
- **Orange Tiny Terror** (`Amp_OrangeTinyTerror`): Gain number 1..100/1 def 88; Tone number 1..100/1 def 75
- **AMTW-22** (`Amp_TW22`): Gain number 1..100/1 def 25; Bass number 1..100/1 def 40; Mid number 1..100/1 def 56; Treble number 1..100/1 def 65
- **AMTW-26** (`Amp_TW26`): Gain number 1..100/1 def 64; Bass number 1..100/1 def 44; Mid number 1..100/1 def 55; Treble number 1..100/1 def 76; Presence number 1..100/1 def 69
- **AMTW-40** (`Amp_TW40`): Gain number 1..100/1 def 80; Bass number 1..100/1 def 80; Mid number 1..100/1 def 80; Treble number 1..100/1 def 80; Presence number 1..100/1 def 69

## Amps — bass

- **BH-600B** (`Bass_Amp_BT600B`): Gain number 1..100/1 def 20; Bass number 1..100/1 def 75; 180hz db -12..12/0.5 def -4; 340hz db -12..12/0.5 def 2; Mid number 1..100/1 def 65; 1.2khz db -12..12/0.5 def 4; 2.6khz db -12..12/0.5 def -6; Treble number 1..100/1 def 75; Compression % 0..100/1 def 45
- **BH-880B** (`Bass_Amp_BT880B`): Gain number 1..100/1 def 12; Bass db -12..12/0.5 def 4; Low-Mid db -12..12/0.5 def -9; Low-Mid Freq. hz 30..300/2.5 def 220; Mid db -12..12/0.5 def 4; Mid Frequency hz 200..2000/20 def 1200; High-Mid db -12..12/0.5 def -4; High-Mid Freq. khz 1.2..12/0.1 def 1.6; Treble db -12..12/0.5 def 6
- **BH-975B** (`Bass_Amp_BT975B`): Gain number 1..100/1 def 65; Low-Shift enum 0..1/1 def 1; Bass db -12..12/0.5 def 5; Mid db -12..12/0.5 def 6; High-Shift enum 0..1/1 def 1; Treble db -12..12/0.5 def 4
- **CLH-300B** (`Bass_Amp_CH300B`): Gain number 1..100/1 def 2; Bass db -12..12/0.5 def 2; Mid db -12..12/0.5 def -5; Mid-Frequency hz 200..2000/2 def 480; Treble db -12..12/0.5 def 4; Enhance % 1..100/1 def 35
- **CLH-350B** (`Bass_Amp_CH350B`): Gain number 1..100/1 def 31; Bass number 1..100/1 def 6; Treble number 1..100/1 def 88; 30hz db -12..12/0.5 def 6; 90hz db -12..12/0.5 def -4; 250hz db -12..12/0.5 def -6; 800hz db -12..12/0.5 def 3; 2.5khz db -12..12/0.5 def -5; 7.5khz db -12..12/0.5 def 4; 15khz db -12..12/0.5 def 6
- **CLH-600B** (`Bass_Amp_CH600B`): Gain number 1..100/1 def 5; Bass db -12..12/0.5 def 4; Treble db -12..12/0.5 def 5; 30hz db -12..12/0.5 def -4; 90hz db -12..12/0.5 def 2; 250hz db -12..12/0.5 def 1; 800hz db -12..12/0.5 def -6; 2.5khz db -12..12/0.5 def 0; 7.5khz db -12..12/0.5 def -9; Compression number 1..100/1 def 55
- **CSS-240B** (`Bass_Amp_CS240B`): Gain number 1..100/1 def 22; Bass number 1..100/1 def 66; Treble number 1..100/1 def 68
- **CSS-300B** (`Bass_Amp_CS300B`): Gain number 1..100/1 def 10; Bass number 1..100/1 def 88; Lo Mid number 1..100/1 def 58; Hi Mid number 1..100/1 def 44; Treble number 1..100/1 def 68
- **CSS-75B** (`Bass_Amp_CS75B`): Gain number 1..100/1 def 45; Bass db -12..12/0.5 def 2; Mid db -12..12/0.5 def 4; Treble db -12..12/0.5 def 3
- **Eden E300** (`Bass_Amp_EdenE300`): Gain number 1..100/1 def 12; Bass db -12..12/0.5 def 4; Mid db -12..12/0.5 def 4; Treble db -12..12/0.5 def -5; Enhance % 1..100/1 def 35
- **Eden WT550** (`Bass_Amp_EdenWT550`): Gain number 1..100/1 def 12; Bass db -12..12/0.5 def 4; Low-Mid db -12..12/0.5 def -9; Low-Mid Freq. hz 30..300/2.5 def 220; Mid db -12..12/0.5 def 4; Mid Frequency hz 200..2000/20 def 1200; High-Mid db -12..12/0.5 def -4; High-Mid Freq. khz 1.2..12/0.1 def 1.6; Treble db -12..12/0.5 def 6; Enhance % 1..100/1 def 35
- **Eden WT800** (`Bass_Amp_EdenWT800`): same knobs as Eden WT550 above, same defaults
- **HW100B** (`Bass_Amp_HT100B`): Gain number 1..100/1 def 66; Bass number 1..100/1 def 88; Mid number 1..100/1 def 68; Treble number 1..100/1 def 44; Presence number 1..100/1 def 30
- **HW-300B** (`Bass_Amp_HT300B`): Gain number 1..100/1 def 68; Bass number 1..100/1 def 88; Mid number 1..100/1 def 24; Mid-Frequency enum 0..4/1 def 1; Treble number 1..100/1 def 88; High-Shift enum 0..1/1 def 1; Low-Shift enum 0..1/1 def 1
- **HW-400B** (`Bass_Amp_HT400B`): Gain number 1..100/1 def 100; Bass db -12..12/0.5 def 4; Mid db -12..12/0.5 def 4; Treble db -12..12/0.5 def 4; High-Shift enum 0..1/1 def 1; Low-Shift enum 0..1/1 def 1
- **LW-25B** (`Bass_Amp_LT25B`): Gain number 1..100/1 def 15; Bass number 1..100/1 def 88; Mid number 1..100/1 def 88; Mid-Frequency enum 0..2/1 def 0; Treble number 1..100/1 def 88; High-Shift enum 0..1/1 def 1; Low-Shift enum 0..1/1 def 1
- **LW-85B** (`Bass_Amp_LT85B`): Gain number 1..100/1 def 44; Bass number 1..100/1 def 44; Mid number 1..100/1 def 44; Treble number 1..100/1 def 44; High-Shift enum 0..1/1 def 1
- **Orange AD200B** (`Bass_Amp_OrangeAD200B`): Gain number 1..100/1 def 88; Bass number 1..100/1 def 75; Mid number 1..100/1 def 66; Treble number 1..100/1 def 50

## DI ("amps" with no real amp stage)

- **DI. Bass Driver** (`DI_Amp_BassDriver`): Gain number 1..100/1 def 50; Bass number 1..100/1 def 66; Presence number 1..100/1 def 45; Treble number 1..100/1 def 65; Blend % 0..100/1 def 71
- **DI. Mixer** (`DI_Amp_MixerPre`): Gain number 1..100/1 def 10; Bass number 1..100/1 def 50; Mid number 1..100/1 def 50; Treble number 1..100/1 def 50; Tone number 1..100/1 def 76

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

- **Bass Auto Filter** (`Bass_Pedal_BassAutoFilter`, Filter): Sensitivity number 1..100/1 def 88; Attack Speed ms 1..250/1 def 15; Release Speed ms 10..1000/10 def 120; Filter Type enum 0..2/1 def 1; Mix % 1..100/1 def 38
- **Bass Chorus** (`Bass_Pedal_BassChorus`, Modulation): Rate hz 0.1..10/0.1 def 1; Mix % 0..100/1 def 80; Depth % 1..100/1 def 65; Low Filter number 1..100/1 def 62
- **Bass Distortion** (`Bass_Pedal_BassDistortion`, Distortion): Gain number 1..100/1 def 80; Tone number 1..100/1 def 28; Filter % 1..100/1 def 50
- **Bass Enbiggenator** (`Bass_Pedal_BassEnbig`, Modulation): Rate hz 0.1..10/0.1 def 4; Mix % 0..100/1 def 45; Depth % 1..100/1 def 55; Filter % 1..100/1 def 30
- **8-Band Bass EQ** (`Bass_Pedal_BassEQ8`, Filter): 30hz db -15..15/1 def 8; 75hz db -15..15/1 def 3; 185hz db -15..15/1 def -9; 460hz db -15..15/1 def -2; 1.1khz db -15..15/1 def 2; 2.7khz db -15..15/1 def -3; 6.8khz db -15..15/1 def 2; 16khz db -15..15/1 def 4
- **Bass Filter Delay** (`Bass_Pedal_BassFilterDelay`, Delay): Time ms 20..2000/10 def 360; Feedback % 0..100/1 def 45; Mix % 1..100/1 def 55; Low Filter number 1..100/1 def 20
- **Bass Filter Echo** (`Bass_Pedal_BassFilterEcho`, Delay): Time ms 20..2000/10 def 120; Feedback % 0..100/1 def 69; Mix % 1..100/1 def 65; Low Filter number 1..100/1 def 20
- **Bass Flange** (`Bass_Pedal_BassFlanger`, Modulation): Rate number 1..100/1 def 20; Depth % 1..100/1 def 50; Mix % 0..100/1 def 65; Filter % 1..100/1 def 50
- **Bass Fuzz** (`Bass_Pedal_BassFuzz`, Distortion): Gain number 1..100/1 def 66; Tone number 1..100/1 def 10; Filter % 1..100/1 def 75
- **Bass Overdrive** (`Bass_Pedal_BassOverdrive`, Distortion): Gain number 1..100/1 def 80; Tone number 1..100/1 def 40; Blend % 1..100/1 def 55; Filter % 1..100/1 def 75
- **Bass Phase** (`Bass_Pedal_BassPhase`, Modulation): Rate number 1..100/1 def 78; Depth % 1..100/1 def 50; Mix % 0..100/1 def 65; Filter % 1..100/1 def 65
- **Bass Sub Octave** (`Bass_Pedal_BassSubOctave`, Pitch): Mix % 0..100/1 def 70; Tone number 1..100/1 def 88
- **Bass Wah** (`Bass_Pedal_BassWah`, Filter): Auto-Mode enum 0..1/1 def 1; Sensitivity number 1..100/1 def 68; Speed number 1..100/1 def 89; Pedal (Auto=OFF) number 1..100/1 def 50
- **Eden WT D.I.** (`Bass_Pedal_EdenWTDI`, Filter): Gain number 1..100/1 def 65; Bass db -12..12/0.5 def 4; Mid db -12..12/0.5 def 4; Treble db -12..12/0.5 def -5; Enhance % 1..100/1 def 35; Bass Boost enum 0..1/1 def 1; Mid-Shift enum 0..1/1 def 1; Compression % 0..100/1 def 45
- **MB Comp** (`Bass_Pedal_MBComp`, Dynamics): Compression number 1..100/1 def 40; Recovery Speed number 1..100/1 def 40; Transition Band hz 100..1000/10 def 600

Note: the full gear database (`tone_gear_data.json`) also contains a much
larger set of guitar effect pedals/racks (drive, modulation, delay, EQ, wah,
pitch, etc.) not enumerated here — fetch the file directly when a specific
effect is needed.

## Knob format

`Name unit min..max/step def X` — `unit` is `number` (plain 1-100 dial),
`db` (decibel EQ band), `hz`/`khz` (frequency), `ms` (milliseconds), `%`
(percent), or `enum` (discrete switch positions, e.g. on/off or mode select).
Each knob's full `Key` is `<GearKey>_<KnobName>` with spaces/dots/+ stripped
(e.g. `Amp_MarshallJCM800_Presence`, `Bass_Pedal_BassEQ8_30hz`).

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
