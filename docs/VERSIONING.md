# Versions, bugs and fixes

How RockForge numbers its versions, records its bugs and the work that fixed
them, and decides what a release may contain. The tools that enforce it are in
[`tools/`](../tools); publishing a version step by step is
[RELEASE_PROCESS.md](RELEASE_PROCESS.md).

| What | Where |
|---|---|
| The version (one place) | `src/rockforge/__init__.py` `__version__` |
| Version rules (parse, order, what may come next) | `src/rockforge/versioning.py` |
| Which build is running | `src/rockforge/build_info.py` → `GET /version`, Definições → Geral → Sobre o RockForge |
| Bugs, fixes, releases (the record) | `tracking/bugs.json`, `tracking/fixes.json`, `tracking/releases.json` |
| The same, to read | `tracking/BUG_LOG.md`, `FIX_LOG.md`, `RELEASE_LOG.md` (generated) |
| Rules on the record | `tools/tracking.py` (`python -m tools.tracking check`, in CI) |
| The gate before a release | `tools/release_check.py` (in the release workflow) |
| Moving to the next version | `tools/bump_version.py` |
| Technical log | `src/rockforge/app_logging.py` → `<work dir>/logs/` |

## The version number

[Semantic Versioning](https://semver.org): `MAJOR.MINOR.PATCH[-PRERELEASE][+BUILD]`.

- **MAJOR** — something that worked stops working the same way: a change to the
  API, a setting, a project's stored data or the files RockForge reads or writes
  that older projects or tools cannot follow; or a structural change that
  deserves the number.
- **MINOR** — new features that keep everything else working.
- **PATCH** — fixes only, nothing incompatible.
- **PRERELEASE** — where the version is in its life: `dev.N`, `alpha.N`,
  `beta.N` or `rc.N`, counted from 1 and up by one within a stage. A new beta or
  RC of the same version is the next number; a new stage starts again at 1.
- **BUILD** — which build, never which version: `+ci.57.0381b134e2` (the CI run
  and the commit), `+0381b134e2` (a git checkout), `.dirty` when it has local
  changes. Two builds of one version carry the same features and fixes and
  compare equal. It is added at build time and never written in the source.

While RockForge is `0.x`, the public API is not frozen (SemVer item 4): a
change that would be MAJOR after 1.0.0 is a MINOR now, and says so in the
changelog's "Breaking changes".

`rockforge.versioning.allowed_next` is the rule, and `tools/bump_version.py`
refuses anything else: the next number is the next pre-release of the same
version, the next stage, the release itself, or the first version (a
pre-release numbered 1, or the release) of the next PATCH, MINOR or MAJOR.
Nothing is skipped and nothing goes back.

Python's packaging reads the same string as PEP 440 (`0.10.0-beta.12` is
`0.10.0b12`, `-dev.1` is `.dev1`); RockForge called itself that way up to
0.10.0 beta 12, and `versioning.parse_loose` still reads those spellings (the
update check compares against releases made with either).

### Where it is written

`__version__` is the one source. `pyproject.toml` reads it (`dynamic`); the API,
the page's corner, the update check and the logs import it. Two copies cannot
import Python and are kept equal by `tests/test_release_version.py`: the
installer (`installer.iss` `MyAppVersion`, which the release workflow also
reads) and each changelog's section heading. `tools/bump_version.py` changes all
of them together.

### Development, beta, release candidate, stable

| Stage | What it is | Published? | To move on |
|---|---|---|---|
| **Development** (`-dev.N`, or `main` between releases) | Work in progress. | Never by the workflow (`decide` skips `-dev`). | Features in, CI green. |
| **Beta** (`-beta.N`) | For testers: may still carry known bugs, said in its notes. | Yes, as a GitHub pre-release. | No open Critical bug affecting it. |
| **Release candidate** (`-rc.N`) | Functionally complete; only verifying. | Yes, as a pre-release. | No open Critical/High/P1 bug affecting it; every Critical/High fix of the line verified. |
| **Stable** (`X.Y.Z`) | Approved for everyone. | Yes, as the latest release. | Follows a published RC of the same number, with no change of its own; every fix of the line Verified or Closed. |
| **Superseded** | A newer version was published. | Stays on the Releases page. | — |
| **Withdrawn** | Pulled after publication (see rollback). | Marked as such, not deleted. | — |

A beta is never presented as stable. A change needed after an RC is a new RC
(`rc.2`), tested again; the stable version is built from an RC's code. Whatever
was published stays as it was: a different content is a different number. A
version prepared and never published stays in the register as
`Not published` (0.10.0 beta 4).

`main` between two releases still carries the last published number; its build
part (the commit) is what tells it apart, and the page and the logs show it.
`-dev.N` exists for a build handed to someone before the next pre-release.

## Bugs

Every bug found — in development, by a test, by a user, in the game — gets a
record in `tracking/bugs.json` with an id `BUG-0001`, `BUG-0002`, … that is
never reused. A record is never deleted: a bug that was not one becomes
`Duplicate`, `Cannot Reproduce` or is closed with a note. `python -m
tools.tracking check` fails if an id is missing or out of order.

The fields, all required (a fact not known yet is the literal `"pending"` —
never a guess):

| Field | What |
|---|---|
| `id`, `title`, `description` | The bug, in words a user would recognise. |
| `detected`, `reported_by` | When and by whom (a user report says the channel, not the person's name). |
| `found_in_version`, `found_in_build` | The version (and commit) it was seen in; `before 0.10.0-beta.1` for the development before the first public version; `unreleased` when it never reached a release. |
| `module` | One of the areas in `tools/tracking.py` `MODULES`. |
| `steps`, `expected`, `observed` | How to see it, what should happen, what happens. |
| `severity`, `priority` | Below. |
| `status`, `history` | Below. Every change of status is a step of the history, with its date. |
| `root_cause` | Once identified. |
| `fixes` | The `FIX-` records that fixed it (what was changed, where, the commits, the version, the tests). |
| `verified_by`, `verification` | Who checked the fix, and how. |
| `evidence` | Logs, quotes, screenshots, reports, the parts of CLAUDE.md that tell the story. |
| `resolved`, `closed` | When it was fixed, when it was closed. |

Optional: `duplicate_of`, `note` (required for Deferred / Cannot Reproduce),
`links` (an issue, a forum thread).

### Severity

| | In RockForge |
|---|---|
| **Critical** | The game crashes or the song never appears or plays; a project's data is lost or corrupted; a security hole; an essential function (making a project, building the `.psarc`, starting the app) cannot be used. |
| **High** | An essential feature is broken and there is no reasonable way round it. |
| **Medium** | A feature misbehaves with limited impact, or there is a way round it. |
| **Low** | Cosmetic, a minor inconvenience, a wrong word. |

### Priority

Separate from severity: how soon.

| | When |
|---|---|
| **P1** | Now: everything else waits. Critical bugs, a release blocker. |
| **P2** | Before the next release. |
| **P3** | In the normal course of work. |
| **P4** | When convenient. |

Triage weighs the impact, how many people it reaches (every song or one
file), the risk (crash, data, security) and whether there is a way round it. A
Critical or High bug that touches security, a project's data or an essential
function blocks a release (see the table above) unless the version's entry in
`releases.json` carries an **exception**: the bug, why it may ship, the risk,
who approved it and when. The gate reads exceptions from there and nowhere
else.

### Status

`Open → Triaged → In Progress → Fixed → Verified → Closed`, and when needed
`Reopened`, `Deferred` (with why), `Duplicate` (of which record) and `Cannot
Reproduce` (with the conditions tried). `TRANSITIONS` in `tools/tracking.py`
lists every allowed step; anything else fails the check.

- **Fixed** — a change was committed (a `FIX-` record with its commits). Not
  closed: nobody has confirmed it works yet.
- **Verified** — the fix was confirmed: a regression test that failed before and
  passes now, a manual check described in the record, or the reporter or the
  maintainer confirming it (in game, for a game problem).
- **Closed** — verified AND inside a published release.
- A fix that did not work: the bug goes back to `Reopened`, and a new `FIX-`
  record follows. The earlier record stays; history is never rewritten into the
  final answer.

## Fixes

`tracking/fixes.json`, ids `FIX-0001`, …: the root cause, what was changed, the
files, the commits, the version that contains it (`unreleased` until a version
is cut), the tests and their result (`passed`, `failed`, `not run`,
`pending`), the manual checks, the regression risk, who and when, and how it was
validated (`automated`, `manual`, `confirmed by user`, `failed`, `pending`).
One fix may close several bugs, and a bug may need several fixes; each side
names the other, and the check fails when they disagree.

A fix is said to be in a version only when git agrees: every commit of the fix
is an ancestor of the version's commit (`check_commits`, run in CI with the full
history). The versions before 0.10.0 beta 10 have no tag any more; their
register entry names the commit that set their number, which the release was
built from or after.

## Releases

`tracking/releases.json`, oldest first: the number, the build, when it was made
and published, its status, what it was for, its features and improvements,
breaking changes, the tests run, who approved it, the commit and artifacts, and
how to update or go back. What it fixed and the bugs it still carried are not
written here — they are computed from the bugs and the fixes, so the logs cannot
contradict the registers.

## Technical log

`<work dir>/logs/rockforge.log` (the API, and the in-process worker of the
`.exe`) and `rockforge-worker.log` (a Celery worker): time, level, component,
the request id, the message. Rotated at 2 MB, five older copies kept. The
level is `ROCKFORGE_LOG_LEVEL` (`INFO`). Every start writes the build, the
Python and the system; an error no endpoint handled is written with its
traceback and an id, and the user gets that id. The API token, HTTP
credentials, `password=`/`token=` values and the account name in paths are
taken out before anything is written. The `.exe`'s raw console goes to
`logs/console.log` (three earlier runs kept); `start.bat` keeps the previous
`logs\worker.log` as `worker.prev.log`.

The log records what happened; it decides nothing. A line in the log becomes a
bug only when someone triages it into the register. Definições → Geral →
"Copiar informação para relatório" puts the build, the system, the external
software found and the end of the logs (redacted) on the clipboard for a bug
report.

## Commands

```bash
python -m tools.tracking check                     # every rule (CI runs it)
python -m tools.tracking render                    # regenerate the three logs
python -m tools.tracking new-bug "Title" --module psarc --severity High --priority P2 \
       --found-in 0.10.0-beta.12 --reported-by "user report (r/rocksmith)"
python -m tools.tracking status BUG-0042 Triaged "reproduced with a 7-string GP5"
python -m tools.tracking notes 0.10.0-beta.13      # the bugs a version fixed
python -m tools.release_check 0.10.0-beta.13       # may it be published?
python -m tools.bump_version 0.10.0-beta.13 --goal "…"
python -m tools.bump_version 0.10.0-beta.13 --published 2026-10-18
```

Fields the commands do not set (steps, root cause, evidence, the `FIX-` record)
are edited in the JSON, followed by `render`.
