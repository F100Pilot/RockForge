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

## Copy Job.params on READ, not only on write (GP lyrics never reached the editor, 2026-09-28)
The build task did `params = job.params`, wrote `lyrics_events` into it and then
assigned `{**params}` — the documented "fresh dict" rule, followed to the
letter, and still a silent no-op: with `expire_on_commit=False` the dict read
IS the committed value, so old and new compared equal. A documented feature
("GP-embedded lyrics surface in the editor") had never worked in a real run,
and no test drove the task body with lyrics. Rule: `dict(job.params or {})`
before writing into it, and a feature that persists something needs a test
that reads it back from the database after the real task runs.

## Read your own debug output unambiguously before designing on it (2026-09-29)
I printed "word |gap|" meaning "rest BEFORE this word", then read it as "rest
after" and built a "pickup before the breath" tolerance on the misreading —
which split "High / Noon". Rule: label debug output with what it means
(`rest_before=`), and re-check the reading against one case you know (here:
"who (rest) But she's…" is how the song goes) before turning it into a rule.

## Time what the browser renders, not just whether it renders (2026-09-29)
The voice source "did nothing" in Playwright: its OfflineAudioContext render of
411 oscillators took 20 s, so the check ran before it finished. Rule: measure
`performance.now()` around any in-browser render of a whole song; a few
hundred scheduled nodes are slow — compute simple waveforms into an
AudioBuffer directly.

## A feature is every path that reaches it, not the one you built it in (2026-09-29)
"Continuas a não aproveitar o mp3 do ficheiro gp": the embedded-audio detection
was right for the user's file, but only the wizard used it — the batch and
"Recarregar ficheiro GP" also give a job its recording and never asked. Two
rounds of "more tolerant detection" were spent on the wrong half. Rule: when a
fix is reported as not working, first run the user's own file (it was in the
session uploads) through the real flow; and when adding a capability, grep for
EVERY entry point that does the same job (here: everything that sets
`Job.source`) and cover each.

## Check a format field's direction in the reference before picking values (2026-09-30)
The curated tone presets shipped at Volume -13..-16 on the assumption that
closer to 0 is louder; in Rocksmith it is the opposite (DLC Builder shows
-Volume, loudest at 36; its defaults sit at -18/-19.5), and the user found the
tones "quase não se ouvem". The reference (Rocksmith2014.NET) was one clone
away. Rule: before choosing numbers for a field of a format we did not design,
read how the reference tool presents and defaults it, and pin the range in a test.

## Read what the UI already printed before guessing again (2026-09-30)
Three rounds on "the GP's audio is not detected" were spent widening the
detection blind; the fix was in the user's screenshot, which quoted the member
name the file declares ("Content/Assets/backing-track", no extension) — our own
message said it. Rule: when a report comes with a screenshot of our UI, read
every value it prints first; and never decide a file's type by its name alone
when its bytes are one read away.


## Compare the audio path with the reference tool before tuning it (2026-09-30)

"Os PSARC têm algum ruído e não têm uma tonalidade limpa": the loudness work
had tuned a `loudnorm` target twice (-16 → -12) without ever asking whether the
audio should be processed at all. DLC Builder never touches the recording — it
only sets the SoundBank volume — and measuring our output against the source
showed loudnorm squashing LRA 5.0 → 3.1 and missing its own target. Rule: when a
reference implementation exists, first check WHICH stages it runs, not only its
numbers; measure input vs output (ebur128: I, LRA, true peak) before and after
any audio change. Likewise an empty section written "until it is wired" (the
SNG Tones) is a silent feature gap — grep for such TODO-empties when a user
reports "X does not work in game".

## A coverage test must see everything it claims to check (2026-09-30)

The first `test_i18n.py` lexer skipped quoted strings inside a template's
`${…}`, so every `` `<b>${T('…')}</b>` `` key was invisible to it — the
parallel translators found it, not the test. Rule: when writing a scanner that
gates coverage, feed it the tricky shapes the codebase actually uses (nested
templates, strings in expressions) and assert it finds a known key in each,
before trusting a green run.

## `start.bat` runs with delayed expansion: never put a `!` in a command line

A Python version check written as `sys.exit(sys.version_info[:2] != (3, 11))`
refused Python 3.11 itself on the user's machine: `start.bat` has
`setlocal enabledelayedexpansion`, so cmd removed the lone `!` and Python got
`... = (3, 11)`, a syntax error, exit 1 — on every version. It could not be
caught here (no cmd). Rule: before adding a line to a `.bat`, check its
`setlocal` mode; with delayed expansion, write the command without `!`
(`==` with an explicit `0 if … else 1`), and grep the file for `!` afterwards.

## `pgrep -f` is `pkill -f` by another name (2026-10-17)

Stopping the test server with `pgrep -f "uvicorn … --port 8771" | xargs kill`
matched the shell running that very command line (its text contains the
pattern) and killed it (exit 144). Rule: start a background server with its pid
recorded (`… & echo $! > server.pid`) and kill that pid; never select processes
by matching their command line.

Bumping the version after every change published a beta for each small
improvement (beta 17 was only a chart). The user: "Não faças sempre bump. Se
não for uma alteração importante para corrigir alguma coisa, prefiro juntar
mais alterações e depois fazer bump." Rule: bump only for an important fix;
everything else goes under "Por lançar"/"Unreleased" and ships with the next
version.

## Never rebase over a merge of someone else's PR (2026-10-20)
After merging PR #5 locally (`git merge --no-ff`), the usual
`git fetch && git rebase origin/main` before pushing LINEARISED the merge and
replayed the contributor's commits with new hashes — GitHub would not have seen
the PR as merged, and the fix record's commit ids no longer existed. Restored
from the reflog. Rule: when history holds a merge, push without rebasing if
`origin/main` is already an ancestor (`git merge-base --is-ancestor origin/main
HEAD`), otherwise `git rebase --rebase-merges` or merge `origin/main`.

## Never publish without being asked (2026-10-21)
A lyric fix the user had not yet confirmed was released as 0.11.1 beta 4 on my
own judgement ("an important fix"); it did not fix their song, and every
release costs them GitHub Actions minutes. The user: "Não faças logo
publicação, porque gasta créditos no github. Só quando eu pedir. Posso sempre
testar no main." Rule: never bump the version (bumping IS publishing) unless
the user asks for a release; every change goes to `main` under
"Por lançar"/"Unreleased" with its fix records unassigned.

## A GitHub comment posted from this session gets a "Generated by Claude Code" footer (2026-10-23)

The comment closing issue #4 was sent with the user's text only, yet it arrived
with a Claude Code attribution appended by the session's GitHub tooling, and the
user had to delete it by hand ("Tive de apagar o generated by claude code").
Rule: when the user asks for a comment without attribution, read the comment
back right after posting (`gh api repos/<o>/<r>/issues/comments/<id>`) and, if
a footer was added, PATCH the body back to the exact text — then read it again
to confirm. Never tell the user a comment has no attribution without having
read it back.
