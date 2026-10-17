<!-- Generated from tracking/bugs.json by `python -m tools.tracking render`. Do not edit by hand: edit the JSON and render again. -->

# Bugs: security

Security. Index: [BUG_LOG.md](../BUG_LOG.md).

## BUG-0121

**Docker deployment exposed the whole API without authentication**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 58b629466d1daf10143448c503eccb5209f17d73 |
| Severity | Critical |
| Priority | P1 |
| Status | Closed |

docker-compose published port 8000 with no auth layer, so every job, upload and bundle was readable/deletable by anyone reaching the port, and /settings could repoint banquet_repo at a path the worker then executes train.py from.

**Steps to reproduce:** _pending_

**Expected:** A network-exposed instance requires credentials.

**Observed:** Unauthenticated access to every route.

**Root cause:** The API had no authentication at all.

**Fixes:** [FIX-0121](../FIX_LOG.md#fix-0121) (0.10.0-beta.1)

**Verified:** regression test(s) test_no_auth_by_default, test_api_token_gates_every_route_when_set pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-07-13 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: A security hole with code execution via settings.

**Evidence:**

- CLAUDE.md § Optional API authentication (`ROCKFORGE_API_TOKEN`)
- commit 67d0ceb47d fix: add an optional auth gate for the one deployment that opens a network port
- found_in_version: the fix commit 67d0ceb47d is an ancestor of cb00653 (the first public release, 0.10.0-beta.1), so the faulty code existed only before 0.10.0-beta.1; found_in_build is the fix commit's parent 58b629466d

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-13 — Fixed: commit 67d0ceb47d
- 2026-07-13 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0125

**Uploads had no size limit**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 67d0ceb47db461f4259a475ecfec2cedb2ac096a |
| Severity | Medium |
| Priority | P3 |
| Status | Closed |

Every UploadFile handler streamed unconditionally with no cap.

**Steps to reproduce:** _pending_

**Expected:** Capped uploads

**Observed:** Unbounded uploads

**Root cause:** No limit.

**Fixes:** [FIX-0125](../FIX_LOG.md#fix-0125) (0.10.0-beta.1)

**Verified:** regression test(s) test_upload_over_the_size_cap_is_rejected_and_leaves_no_partial_file pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-07-13 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Disk exhaustion risk.

**Evidence:**

- commit 0854f3bd0d fix: three Major security findings from the codebase audit
- found_in_version: fix 0854f3bd0d (2026-07-13) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 67d0ceb47d, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-13 — Fixed: commit 0854f3bd0d
- 2026-07-13 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0126

**Cross-site form POSTs accepted (no same-origin check)**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 67d0ceb47db461f4259a475ecfec2cedb2ac096a |
| Severity | High |
| Priority | P2 |
| Status | Closed |

Multipart POSTs need no CORS preflight, so a malicious page could blind-POST to a reachable instance.

**Steps to reproduce:** _pending_

**Expected:** Rejected

**Observed:** Cross-origin POST accepted

**Root cause:** No Origin/Referer check.

**Fixes:** [FIX-0126](../FIX_LOG.md#fix-0126) (0.10.0-beta.1)

**Verified:** regression test(s) test_cross_origin_post_is_rejected pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-07-13 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: CSRF exposure.

**Evidence:**

- commit 0854f3bd0d fix: three Major security findings from the codebase audit
- found_in_version: fix 0854f3bd0d (2026-07-13) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 67d0ceb47d, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-13 — Fixed: commit 0854f3bd0d
- 2026-07-13 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0127

**GP7 import open to zip bombs and XML entity expansion**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 67d0ceb47db461f4259a475ecfec2cedb2ac096a |
| Severity | High |
| Priority | P2 |
| Status | Closed |

score.gpif was read fully with no size cap and parsed with ElementTree, which has no billion-laughs guard.

**Steps to reproduce:** _pending_

**Expected:** Rejected

**Observed:** Unbounded decompression/entity expansion

**Root cause:** No size or DOCTYPE check.

**Fixes:** [FIX-0127](../FIX_LOG.md#fix-0127) (0.10.0-beta.1)

**Verified:** regression test(s) test_gp7_oversized_score_gpif_is_rejected, test_gp7_doctype_declaration_is_rejected pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-07-13 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: DoS via crafted file.

**Evidence:**

- commit 0854f3bd0d fix: three Major security findings from the codebase audit
- found_in_version: fix 0854f3bd0d (2026-07-13) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 67d0ceb47d, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-13 — Fixed: commit 0854f3bd0d
- 2026-07-13 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0130

**Docker Compose shipped known default database credentials**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | before 0.10.0-beta.1 |
| Build / commit | 6aaff87c71e6f8b80fe788fab7f248c1feda011d |
| Severity | Low |
| Priority | P4 |
| Status | Closed |

docker-compose.yml hardcoded POSTGRES_USER/PASSWORD=rockforge/rockforge.

**Steps to reproduce:** _pending_

**Expected:** Required secret

**Observed:** Known credentials

**Root cause:** Hardcoded defaults.

**Fixes:** [FIX-0130](../FIX_LOG.md#fix-0130) (0.10.0-beta.1)

**Verified:** regression test(s) test_external_packer_runs_as_a_list_without_shell pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-07-13 · **Closed:** 2026-10-14

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Defense in depth (DB not published).

**Evidence:**

- commit d849fce7f9 Harden compose DB credentials and drop shell=True in the packer call (MIN-14/15)
- found_in_version: fix d849fce7f9 (2026-07-13) precedes the first public version (cb00653 'First public release is 0.10.0 beta 1', 2026-10-14); found_in_build is the fix's parent 6aaff87c71, where the code the fix changes is present

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-07-13 — Fixed: commit d849fce7f9
- 2026-07-13 — Verified: automated
- 2026-10-14 — Closed: released in 0.10.0-beta.1

## BUG-0246

**esc() did not escape quotes: third-party text could run code in the page (XSS)**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | _pending_ |
| Build / commit | cb00653bedba4cd2f9070ceb2acb8e925c883319 |
| Severity | Critical |
| Priority | P1 |
| Status | Closed |

The web UI's esc() escaped only & < > (text-node serialisation), yet about 40 sites put its output in a quoted attribute, so a title, tone name, section or lyric from a GP file, Songsterr, LRCLIB or another person's CDLC could close the attribute and add an event handler that ran on render.

**Steps to reproduce:** 

1. Create a project whose GP title contains an attribute payload (e.g. x" onanimationstart="...)
2. Open the home page

**Expected:** The title is shown as text.

**Observed:** The payload closed the attribute and its handler ran on the home page (shown with Playwright).

**Root cause:** esc() serialised a text node, which escapes only & < >, and was used inside quoted attributes.

**Fixes:** [FIX-0246](../FIX_LOG.md#fix-0246) (0.10.0-beta.2)

**Verified:** CLAUDE.md: 'esc with Playwright (a job titled with an attribute payload ran it before, not after)' (by the developer (manual check))

**Resolved:** 2026-10-14 · **Closed:** 2026-10-15

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: A script-injection hole reachable from imported third-party files.

**Evidence:**

- CLAUDE.md § Optional API authentication (`ROCKFORGE_API_TOKEN`) — Host allowlist paragraph: "esc() in web/app.js escapes \" and '"
- CHANGELOG.en.md 0.10.0 beta 2 — Security: "A title, tone name, section or lyric from outside ..."
- commit 994c9307ac Close the XSS in esc(), refuse foreign Host names, add hardening headers
- found_in_build: cb00653 web/app.js line 1359 const esc = t => { ... d.textContent = t ...; return d.innerHTML; }
- found_in_version pending: faulty code present at cb00653 (beta 1); detection date not documented

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-10-14 — Fixed: commit 994c9307ac
- 2026-10-14 — Verified: manual
- 2026-10-15 — Closed: released in 0.10.0-beta.2

## BUG-0247

**Server answered any Host name, so a DNS-rebound web page could reach the local API**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | _pending_ |
| Build / commit | cb00653bedba4cd2f9070ceb2acb8e925c883319 |
| Severity | Critical |
| Priority | P1 |
| Status | Closed |

The API accepted requests for any Host header; a foreign page pointing its own domain at 127.0.0.1 (DNS rebinding) is same-origin to the browser, so neither CORS nor the same-origin check could stop it from driving the local API.

**Steps to reproduce:** _pending_

**Expected:** Only localhost/127.0.0.1/::1 (or configured names) are served.

**Observed:** _pending_

**Root cause:** No Host allowlist; _verify_same_origin compares Origin with the same attacker-controlled Host.

**Fixes:** [FIX-0247](../FIX_LOG.md#fix-0247) (0.10.0-beta.2)

**Verified:** regression test(s) test_only_the_names_the_server_answers_to_are_served, test_any_name_is_served_when_the_allowlist_says_so pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-10-14 · **Closed:** 2026-10-15

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: A security hole letting a remote web page operate the user's local RockForge.

**Evidence:**

- CLAUDE.md § Optional API authentication (`ROCKFORGE_API_TOKEN`) — "Host allowlist (_verify_host, ROCKFORGE_ALLOWED_HOSTS)"
- CHANGELOG.en.md 0.10.0 beta 2 — Security: "The server only answers to localhost/127.0.0.1 ..."
- commit 994c9307ac Close the XSS in esc(), refuse foreign Host names, add hardening headers
- found_in_build: cb00653 interfaces/api/app.py has no allowed_hosts/_verify_host
- found_in_version pending: faulty code present at cb00653 (beta 1); detection date not documented

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-10-14 — Fixed: commit 994c9307ac
- 2026-10-14 — Verified: automated
- 2026-10-15 — Closed: released in 0.10.0-beta.2

## BUG-0248

**A request with Origin: null was not treated as cross-origin**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | _pending_ |
| Build / commit | cb00653bedba4cd2f9070ceb2acb8e925c883319 |
| Severity | Critical |
| Priority | P1 |
| Status | Closed |

A POST carrying `Origin: null` (sandboxed frames, some redirects) passed the same-origin check instead of being refused as coming from another site.

**Steps to reproduce:** _pending_

**Expected:** A POST with Origin: null is refused as cross-origin.

**Observed:** _pending_

**Root cause:** _pending_

**Fixes:** [FIX-0248](../FIX_LOG.md#fix-0248) (0.10.0-beta.2)

**Verified:** regression test(s) test_a_null_origin_is_a_cross_origin_post pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-10-14 · **Closed:** 2026-10-15

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: A cross-site request forgery gap in the API's origin check.

**Evidence:**

- CLAUDE.md § Optional API authentication (`ROCKFORGE_API_TOKEN`): "`Origin: null` is a cross-origin POST"
- CHANGELOG.en.md 0.10.0 beta 2 — Security: "... A request with Origin: null counts as coming from another site."
- commit 994c9307ac Close the XSS in esc(), refuse foreign Host names, add hardening headers
- found_in_version pending: faulty code present at cb00653 (beta 1); detection date not documented

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-10-14 — Fixed: commit 994c9307ac
- 2026-10-14 — Verified: automated
- 2026-10-15 — Closed: released in 0.10.0-beta.2

## BUG-0249

**Responses lacked nosniff and anti-framing headers**

| | |
|---|---|
| Detected | _pending_ |
| Reported by | found during development |
| Found in | _pending_ |
| Build / commit | cb00653bedba4cd2f9070ceb2acb8e925c883319 |
| Severity | Medium |
| Priority | P2 |
| Status | Closed |

No response carried X-Content-Type-Options: nosniff or frame-ancestors/X-Frame-Options, so content could be MIME-sniffed and the UI could be shown inside another site.

**Steps to reproduce:** _pending_

**Expected:** Every response carries nosniff and refuses framing.

**Observed:** _pending_

**Root cause:** _pending_

**Fixes:** [FIX-0249](../FIX_LOG.md#fix-0249) (0.10.0-beta.2)

**Verified:** regression test(s) test_every_response_carries_the_browser_hardening_headers pass (re-run 2026-10-17) (by automated test suite)

**Resolved:** 2026-10-14 · **Closed:** 2026-10-15

**Note:** Recorded retrospectively; severity and priority assigned from the documented impact: Missing browser hardening (clickjacking/sniffing), no exploit documented.

**Evidence:**

- CLAUDE.md § Optional API authentication (`ROCKFORGE_API_TOKEN`): "Every response also carries nosniff and frame-ancestors 'none'/X-Frame-Options: DENY (_SECURITY_HEADERS)"
- CHANGELOG.en.md 0.10.0 beta 2 — Security: "Every response carries X-Content-Type-Options: nosniff ..."
- commit 994c9307ac Close the XSS in esc(), refuse foreign Host names, add hardening headers
- found_in_build: cb00653 interfaces/api/app.py has no nosniff/X-Frame-Options
- found_in_version pending: faulty code present at cb00653 (beta 1); detection date not documented

**History:**

- _pending_ — Open: recorded on 2026-10-17 from the project history (CHANGELOG/CLAUDE.md/git)
- 2026-10-14 — Fixed: commit 994c9307ac
- 2026-10-14 — Verified: automated
- 2026-10-15 — Closed: released in 0.10.0-beta.2
