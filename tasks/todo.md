# Working scratchpad

Short-lived plan/checklist for the change in progress. `TODO.md` (repo root) is
the durable feature list; this file is the working notes for the current task.

## In progress: aligned gear knobs, one device at a time

- [x] Studio Compressor — `KNOB_LAYOUTS` entry, aligned overlay, values below
- [ ] Studio Graphic EQ, Parametric EQ, Tape Echo, Plate, Chamber (see TODO.md
      for the per-device parameters)
- [ ] Then amps + cabinets

## Done: remove audio→note transcription

- [x] Delete `pipeline.py`, Basic Pitch adapter, role splitter, fret mapper
- [x] Remove `/jobs/upload`, `/jobs/upload-split`, `/jobs/youtube` + helpers
- [x] Trim ports / domain (`clean_transcription`, `suggest_tuning`) / librosa adapter
- [x] Remove audio-mode UI, `basic-pitch`/`onnxruntime`/`[youtube]` deps
- [x] Keep stem separation, tone/lyric detection, GP path — tests green
