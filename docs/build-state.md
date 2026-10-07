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
