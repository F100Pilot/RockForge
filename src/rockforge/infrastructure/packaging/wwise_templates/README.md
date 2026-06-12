# Wwise template projects

`wwise2019.zip` … `wwise2023.zip` are blank Wwise project templates with the
Rocksmith-compatible conversion settings (Vorbis with seek table) already
configured, taken unmodified from
[iminashi/Rocksmith2014.NET](https://github.com/iminashi/Rocksmith2014.NET)
(`src/Rocksmith2014.Audio/Wwise/`, MIT license). They contain only XML project
files authored for that project — no Audiokinetic software is redistributed.

A plain `convert-external-source` run against a blank Wwise project produces a
.wem **without a seek table**, which Rocksmith 2014 cannot play (the song loads,
audio stays silent and the game exits seconds in). These templates are the
known-good conversion path used by DLC Builder.
