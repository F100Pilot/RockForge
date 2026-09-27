# Lessons

Patterns captured after a correction, so the same mistake doesn't recur. Skim
this at the start of a session. Newest first.

## Verify shared symbols before deleting a module

**Context:** removing the audio→note pipeline. A codebase-mapping subagent
reported `gp_pipeline.py` used "only `AudioIngestor`/`AudioNormalizer`/`Packager`"
from the audio side — but `gp_pipeline.py` also `import`ed `PipelineResult` from
the deleted `application/pipeline.py`, and deleting the file broke the GP path
(caught by the test suite, not the map).

**Rule:** before deleting a module, grep for EVERY top-level symbol it defines
(classes, dataclasses, constants), not just the module path — "separate" modules
in this repo share dataclasses. Relocate a shared symbol to its surviving user
before removing its origin. Then run the full suite, not just mypy.

## The tone-editor gear knobs are separate from the drawn image knobs

**Context:** aligned functional knobs over the bundled rack images. The user's
rack art already has knobs drawn on it, and the real Rocksmith parameter set
often differs from the drawing (Tape Echo: 3 drawn vs 5 real). Overlaying
functional knobs blindly doubles/misaligns them.

**Rule:** functional knobs come from the gear catalogue (`tone_gear_data.json`),
NOT from the picture. Only gear with a hand-made `KNOB_LAYOUTS` entry (measured
`(x,y,r)` per catalogue knob) uses the aligned overlay; everything else uses the
generic knob strip. Size overlays in % of the source image so they scale.

## Read the refusal before explaining it (Songsterr 403, 2026-09-27)
A 403 from Songsterr was explained twice by guesswork ("bot protection", then
"the User-Agent") and code was changed on that basis, when the response BODY
already said `ERR_UNPUBLISHED` — the tab simply was not public. Rule: when an
external service refuses, first get its status, server header and body (one
diagnostic command for the user if the sandbox cannot reach it), and compare
against a known-good request (another id, the reference tool) before touching
code. Error messages must carry the service's own reason, not a guess.

## Verify an edit at more than one point of the song (note deletes, 2026-09-27)
"Apagar notas" was verified by deleting two notes near the START of a chart,
which happened to sit on exact millisecond times — so a real bug passed: the
pipeline matched note edits by exact 6-decimal time while the editor only sees
the XML's millisecond-rounded times, and half the notes at the end of the song
could not be deleted (or edited without a twin). Rule: when verifying anything
keyed on a float read back from a serialized file, exercise it at several
places (start, middle, end) and count the result, and compare with what the
serialization precision actually is.
