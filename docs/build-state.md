# Build State

> Last updated: 2026-10-07
> Updated by: native integration verification; see the source-bound session digest

## Current State

| Check | Result | Candidate | Date |
|---|---|---|---|
| Compilation | **GREEN** (app, tests, main.py, stats.py) | native-integration-20261007-1120 | 2026-10-07 |
| Full native suite | **GREEN** (474 passed, 2 skipped, 1 warning, 70 subtests passed in 439.94s (0:07:19)) | b720fd8 + f5a32c8 + f6f260f + owned fixes | 2026-10-07 |
| Actual web + watcher runtime | **GREEN** (health, auth, routing/rejection, rendered branding, SQLite/document restore, owned cleanup) | isolated synthetic runtime | 2026-10-07 |
| Installed Windows launcher | **OPEN** (two required native probes skipped on this host) | customer release blocked | 2026-10-07 |

## Current Blockers

- Native Windows PowerShell parser and launcher execution are unverified. Linux PowerShell and direct native Python proofs do not replace them.
- Repository publication is outside the enabled native broker's repository scope. Nothing was pushed or deployed.
- Actual installed scanner, autostart/reboot, target recovery, owner/customer acceptance and applicable role/device/concurrency checks remain open.

Evidence prefix: C:/Users/david/AppData/Local/Temp/bb-native-integration-20261007-1120; detailed rulings and limits: docs/session-digests/2026-10-07-native-integration.md. Capability implementation does not certify a customer installation.

## History

| Date | Check | Result | Commit | Agent |
|---|---|---|---|---|
| 2026-10-07 | full native suite + compilation + isolated live runtime | GREEN; launcher/install release gates OPEN | native-integration-20261007-1120 | Codex |
| 2026-04-05 | compileall + pytest | GREEN (356 passed, 65 subtests, 0 warnings) | fb00b0a | error handling: fetch resilience, modal Escape, logout robustness |
| 2026-04-05 | compileall + pytest | GREEN (356 passed, 65 subtests, 0 warnings) | 68a2987 | full-system audit: session expiry, edit guard, txn export, pagination, task safety |
| 2026-04-05 | compileall + pytest | GREEN (356 passed, 65 subtests, 0 warnings) | 16174dd | inventory UX: sorting, quick-filters, URL pre-fill, dashboard health |
| 2026-04-05 | compileall + pytest | GREEN (353 passed, 65 subtests, 0 warnings) | bdbbc96 | user profile, activity logging, session cleanup, security fixes |
| 2026-04-05 | compileall + pytest | GREEN (325 passed, 65 subtests, 0 warnings) | 5ce71b5 | full-system audit: gzip, activity logging, command palette, dead code removal |
| 2026-04-05 | compileall + pytest | GREEN (325 passed, 65 subtests, 0 warnings) | 38a72d7 | gzip + empty states + tab persistence + dead code removal |
| 2026-04-05 | compileall + pytest | GREEN (325 passed, 65 subtests, 0 warnings) | 5e792e7 | unified tabs + skeletons + empty states |
| 2026-04-05 | compileall + pytest | GREEN (325 passed, 65 subtests, 0 warnings) | 6a9d2d0 | design system enforcement |
| 2026-04-05 | compileall + pytest | GREEN (325 passed, 65 subtests, 0 warnings) | 35aa253 | visual upgrade suite |
| 2026-04-05 | compileall + pytest | GREEN (325 passed, 65 subtests, 0 warnings) | 6cddc6b | handoff audit + feedback + update |
| 2026-04-05 | compileall + pytest | GREEN (317 passed, 65 subtests, 0 warnings) | 01438ac | doc alignment + transfer fix |

---

## How to Update

After running compilation or tests, update the "Current State" table:

```
| Compilation (`compileall`) | **GREEN** | abc1234 | 2026-04-04 |
| Tests (`pytest`) | **GREEN** | abc1234 | 2026-04-04 |
```

If broken:

```
| Tests (`pytest`) | **BROKEN** (3 failures in test_inventory.py) | abc1234 | 2026-04-04 |
```

Add a row to the History table (newest first, keep last 10 entries).

## Pre-Flight Caveat

This file describes the last known state. Uncommitted changes since the last update are not reflected here. Always run the checks yourself if you need current truth.

## 2026-09-24 (Claude): restored from GitHub after the 2026-09-17 wipe
- Local tree and git were gone; `main` re-checked out at b1302f2 (2026-04-05). The 2026-09-11/12 work (scanner repair, `start-app.ps1 -Tunnel` opt-in fix, 542-test suite, locked deps) was never pushed and is not on any mounted drive.
- New `.venv` from CPython 3.12.9 with `requirements.txt` (`requirements.lock` needs Python 3.13+).
- `python -m compileall app`: exit 0. `pytest`: 356 passed, 65 subtests, 1 deprecation warning, 110s.
- WARNING: this launcher revision auto-starts a public tunnel when cloudflared is present and stops every cloudflared process on the machine. Do not run `start-app.ps1` on a machine that hosts other tunnels until the opt-in fix is re-applied.

## 2026-09-24 (Claude): launcher safety fix re-applied and guarded
- `start-app.ps1`: public tunnel is now opt-in (`-Tunnel` switch or `BARCODEBUDDY_TUNNEL=1`); default run is local only and says so in the banner. Cleanup stops only cloudflared processes started with this install's config files or pointed at this app's port, never every cloudflared on the machine. Python resolves to `.venv\Scripts\python.exe` first, then the `py` launcher, then `python`; the hard-coded developer-machine interpreter path is gone. Import preflight fails fast with the pip command instead of crash-looping.
- `install-autostart.ps1`: takes a matching `-Tunnel` switch and passes it through; the default task is described as local only.
- `tests/test_windows_scripts.py` (new, 6 tests): opt-in guard, no blanket cloudflared kill, ownership decided by config paths, venv-first Python, install passthrough, and both scripts tokenized by PowerShell's own parser.
- Proof run 2026-09-24 05:50 ET on the developer PC: launcher started local-only, app on 8080 answered 401 to an anonymous request and 503 on /health (no ingestion process), cloudflared count 0 before, during and after, no tunnel-url.txt written, port released after stop.
- Full suite: see line below.
- pytest: 362 passed, 1 warning, 65 subtests passed in 119.56s (0:01:59)


## 2026-10-07 (Claude): identity acceptance branch, `feature/identity-acceptance-20261007`
- Base: factory seam `b720fd8` merged with launcher fix `f5a32c8` (clean merge, `e09bf27`). Baseline on the merge before any change: 462 passed, 2 skipped (the two PowerShell launcher/parser tests), 70 subtests, 385 s.
- After the four code fixes and four new regression tests (`589cd7c` minus the phone CSS): 466 passed, 2 skipped, 70 subtests, 396 s. `compileall app tests scripts main.py stats.py`: exit 0.
- After the phone-width CSS was added (the committed `589cd7c`): 465 passed, 1 failed, 2 skipped, 405 s. The failure was `tests/test_factory_acceptance.py::test_cli_writes_machine_readable_receipt_and_refuses_overwrite` (one of its five probes did not match) while the identity run and a headless browser were running at the same time on this machine. Re-run on its own with the regression, stats and branding files: 25 passed. A CSS-only change cannot reach that test. Treat it as load-sensitive until a quiet full run says otherwise. A first quiet re-run at 08:10 ET was stopped by Claude after it starved: the machine became saturated by other work (Desktop Commander path checks timing out, `tests/test_auth_rbac.py` alone took 105 s instead of about 15 s, 40 passed). A second full run at low priority started about 08:55 ET and writes to `%LOCALAPPDATA%\Temp\bb-identity-20261007\suite-final-lowprio.log`; its result is the one to trust for this commit.
- `scripts/identity_acceptance.py` on committed `3554d9a`: 134 of 143 proven, 1 failed, 8 blocked. Report: `docs/IDENTITY-ACCEPTANCE.md`.
- The two skipped tests are the same open gate as before: Windows PowerShell does not respond on this machine, so the launcher has never been executed here.

## 2026-10-07 09:00 ET (Claude): result for `b890e9d`, and why this machine's results cannot be trusted right now
- Low-priority full run on `b890e9d`, finished before 08:37 ET: **466 passed, 2 skipped, 70 subtests, 504 s.** The earlier single failure did not reproduce. (The clock times written in the entry above were estimates and are about 45 minutes late; this run started about 08:07 ET.)
- The one failure seen earlier, and two failures another agent recorded on the same commit at 08:45 ET (`AGENT COMMAND\.runtime\filing-1.0-20261007\pytest-b890e9d.txt`), are `MemoryError`. The PC is out of committable memory (159 GB limit, 1.2 GB free at 08:50 ET). See `AGENT COMMAND\.runtime\STALL-INCIDENT-2026-10-06-claude.md`.
- `8aeba41`: cherry-picked `f6f260f` from the parallel identity audit (direct edits can no longer set stock below zero, 4 regression tests). Not yet run here in a quiet window.
- `scripts/identity_acceptance.py` gained three lines after `b890e9d`: negative edit refused; the AI helper answering a stock question through local Ollama; every screen measured at 375 px in headless Chrome with an overflow control page. **None of the three has completed a run on a healthy machine.** Run 5 at 08:50 ET died of memory exhaustion (processor `UNEXPECTED_ERROR`, Ollama could not load a model, the web process could not start). The last trustworthy identity result is still run 3 on `3554d9a`: 134 of 143.
- Next step after Windows is restarted: full suite, then `scripts\identity_acceptance.py --output <new folder>`.

## 2026-10-07 (Claude, Fable 5.1): v3.0.0 = `21ad5b4`, verified on a clean machine
- Where: fresh clone of `21ad5b4` on a clean Linux machine, fresh Python 3.12 venv installed with `-r requirements.txt -c constraints.txt` (installed set identical to constraints.txt), PowerShell 7.4.6 on PATH for the launcher probes.
- `scripts/release_gate.py --product-only`: **ready: true**, release_kind product-only, revision 21ad5b4b107651d4eac1da46c82033cca53a9fcf. compile, tests (479 passed, 1 skipped for Windows drive semantics, 70 subtests, 213 s), launcher (12 passed; native probe and parser both executed), config (4 validated), security, acceptance (7 synthetic cases), backup, customer_package, git (clean, unchanged) all passed. acquisition not run by design in product-only mode.
- Demo kit through `scripts/run_acceptance.py` on the installed copy: 9 of 9.
- Live run on the installed copy (`main.py` + `stats.py` as INSTALL.md describes): 4 good scans dropped in the input folder filed in 10 s; 5 problem scans set aside in 7 s with BARCODE_NOT_FOUND x2, INVALID_BARCODE_FORMAT, AMBIGUOUS_BARCODE, DUPLICATE_FILE; both processes restarted and a new scan filed in 3 s; `customer_backup.py create` while running, `verify`, `extract`: 5 PDFs, 5 rejected files, database integrity ok, owner account present.
- Screens at 1440 and 375 px (sign-in, overview, Documents): page width equals viewport, no script errors.
- Not run here: Windows PowerShell 5.1 on Windows, a real scanner, real customer documents.
