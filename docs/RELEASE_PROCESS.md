# Release process

From a reported bug to a published version, and back if a version must be
withdrawn. The rules behind each step are in [VERSIONING.md](VERSIONING.md).

## 1. A bug is reported

1. Record it: `python -m tools.tracking new-bug "…" --module … --severity …
   --priority … --found-in <version> --reported-by "…"`, then fill in the
   description, steps, expected and observed result and the evidence in
   `tracking/bugs.json` (whatever is not known stays `"pending"`), and
   `python -m tools.tracking render`.
2. Triage it (`status BUG-… Triaged "…"`): severity, priority, whether it
   blocks the next release. `Duplicate` / `Cannot Reproduce` / `Deferred` with
   the reason, if so.

## 2. It is fixed

1. Reproduce it, if at all possible.
2. Write the regression test that fails on the bug (when it can be automated;
   browser-only behaviour is checked with Playwright and the check is described
   in the fix).
3. Fix it.
4. Run that test, then the whole gate: `pytest`, `ruff check src tests
   start_standalone.py build_exe.py .github/scripts tools`, `mypy`, `npx eslint
   web/app.js web/highway3d.js`.
5. Add a `FIX-` record to `tracking/fixes.json` (root cause, solution,
   components, the commit(s), `"version": "unreleased"`, tests and their real
   result, manual checks, regression risk, `validation`), name it in the bug's
   `fixes`, and move the bug to **Fixed** (`status BUG-… Fixed "…"`).
6. Add the entry to both changelogs' unreleased sections.
7. When the fix is confirmed — the regression test, a manual check, or the
   reporter — move the bug to **Verified**, with `verified_by` and
   `verification`. A fix that turns out not to work: **Reopened**, and a new
   `FIX-`.

Only a test that actually ran counts: a skipped test is not a pass, and a fix
whose tests did not run is `"test_result": "not run"`.

## 3. A version is cut

On `main`, a new version number is a publication: when CI passes on the commit
that changes it, the release workflow builds, tests and publishes it. So this is
done only when a release was asked for.

1. Decide the number (VERSIONING.md): the next beta while testing, an RC when
   nothing more is coming, the stable version after a clean RC.
2. `python -m tools.bump_version <version> --goal "<what it is for>"` writes the
   number everywhere, turns the changelogs' unreleased sections into the
   version's (dated today), assigns every unreleased fix to it, adds its entry
   to `tracking/releases.json` and runs the gate. A stage that does not follow
   the last one, or a skipped number, is refused before anything is written.
3. Write `docs/RELEASE_NOTES.md` — only what is new and the bugs fixed in that
   version, English then Portuguese (`python -m tools.tracking notes <version>`
   lists the fixed bugs).
4. `python -m tools.release_check <version>` must say "may be published". If it
   lists a blocking bug, fix it, or — only with the maintainer's explicit
   approval — write an exception in the version's entry.
5. Commit, push to `main`.
6. CI runs (it also checks the registers and the commits). Then the release
   workflow's `decide` runs `release_check` again on the exact commit CI passed,
   and only then the Windows job builds the installer and the zip from that
   commit, smoke-tests the frozen `.exe` (a real project, a clean `.psarc`) and
   publishes them with `SHA256SUMS.txt` — a pre-release for a beta or an RC. A
   failure at any point publishes nothing.
7. When the release is on GitHub: `python -m tools.bump_version <version>
   --published <date>` records the date and the tag's commit and marks the
   previous version Superseded. Bugs whose fixes are in it and are Verified can
   now be **Closed**.

What is distributed is exactly what CI validated: the workflow checks out the
commit CI passed on (`workflow_run.head_sha`) and builds from it; the tag is
created on that commit by the release itself; a tag that already exists is
never built again.

## 4. Going back (rollback)

A published version is never edited or re-tagged.

- **For a user**: every earlier version stays on the Releases page; install it
  over the current one (installer) or unpack its zip. Projects are kept in the
  work folder and the database schema is frozen (CLAUDE.md), so an earlier
  version opens them; the `params` of a project built by a newer version are
  ignored by an older one where it does not know them.
- **For the project**: when a published version is broken, mark it
  `Withdrawn` in `tracking/releases.json` (with a note), mark its GitHub
  release as a pre-release or edit its notes to say so, record the bug, and
  publish a new number — a PATCH, or the next beta/RC — with the fix or the
  revert. The withdrawn version keeps its record and its downloads.
- A source install goes back with `git checkout v<version>` (tags from 0.10.0
  beta 10 on).
