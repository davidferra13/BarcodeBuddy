# Identity acceptance: 2026-10-07 (Claude)

Owner request: list every kind of person Barcode Buddy is good for, a checklist of everything each one does, and make all of it pass.

## Where this sits

Branch `feature/identity-acceptance-20261007`, worktree `BarcodeBuddy-worktrees\identity-acceptance-20261007`.
It starts from the factory seam (`b720fd8`) and merges the stacked launcher fix (`f5a32c8`), so it is the first branch that carries all three finished lines together: verified release, launcher supervision, factory seam. The merge was clean. Nothing in any other worktree or in the canonical checkout was touched. Not pushed.

## What was built

`scripts/identity_acceptance.py`: twelve identities, 143 checklist lines, each one a real action.

- Paperwork lines run the real processor on generated scans (PDF, JPG, PNG, two-page TIFF, rotated, barcode on page 2, blank, fake, empty, duplicate, two conflicting numbers, wrong-workflow).
- Web lines go through the full application with its auth and CSRF middleware, one logged-in client per person (owner, admin, two managers, dock worker, viewer, office, leaver).
- Installer lines provision a customer config, then start the web app and the filing service as two separate operating-system processes, drop a scan, back up, damage a backup, restore, stop, strand a file, restart.
- A line that cannot be proven on the host is recorded BLOCKED with the reason. It never passes.

Run it: `.venv\Scripts\python.exe scripts\identity_acceptance.py --output <new folder>`. Exit 0 only when every line passes. The report lands as `identity-acceptance.md` and `.json` in that folder. The copy from this session is `docs/IDENTITY-ACCEPTANCE.md`.

## Result

First run, before any fix: 118 of 142 proven, 16 failed, 8 blocked.
Final run on committed revision `3554d9a`: 134 of 143 proven, 1 failed, 8 blocked.

## Defects it found, all invisible to the existing suite

1. The hands-off hot folder did not work. The watcher re-checked a waiting file only on the library's 5 s timeout, the stability rule needs four checks, and the stuck-file limit is 10 s, so a scan that landed and sat still was rejected `FILE_LOCKED`. Reproduced on the real two-process install with the provisioned default config, for a dropped scan and for a crash-recovered scan. Every prior acceptance called `process_file` directly and never went through the watcher. Fix: one argument, `rust_timeout=poll_interval_ms`, in `run_forever`. The state machine itself is unchanged. This is the "watcher timing" fix that was lost in the 09-17 wipe.
2. A backup taken while the system runs failed with `PermissionError`: the logs folder holds the service lock (byte-locked by the filing service) and the live SQLite files. `OPERATIONS.md` tells the customer to schedule backups, which means while running. Fix: skip the lock and the SQLite sidecars, snapshot any live `.db` through the SQLite backup API.
3. Feedback from the Help page was written to `./data/logs` relative to wherever the app was started, not the customer's configured log folder, so it sat outside their data and outside their backup. Fix: the web app points feedback at `settings.log_path`.
4. The core carried a real person's email address as `DEFAULT_OWNER_EMAIL`. It gated nothing (the gate only applies when `BB_OWNER_EMAIL` is set) so it is now a neutral placeholder. This was the open item from the launcher-identity task.
5. At phone width every logged-in screen was wider than the phone and the page title sat under the menu button; on the items page the Export and New Item buttons were off screen. Fix in the shared shell CSS only. Twelve screens captured at a true 375 px before and after.

Regressions for 1 to 3: `tests/test_identity_regressions.py`. The hot-folder one drives the real `run_forever` loop with default timing.

## Still open

- FAIL, needs the owner's decision: an ordinary user cannot look up an item a manager created. Stock is private per account by design (`User-scoped inventory isolation`), which contradicts the multi-person warehouse the manual describes. Shared stock changes who can see what, so it was not changed here.
- BLOCKED, 8 lines: launcher run under real PowerShell (PowerShell does not respond on this machine), start at boot (needs an admin approval at the machine), a real scanner on a network share, phone screens by eye inside the runner (done by hand this session, see below), live phone camera, AI answer with a real model, release gate, a real buyer's documents.
- Worth a look, not changed: the stability rule still counts checks rather than time. While one large document is being processed no checks happen, so a second file that was seen once and then waits more than 10 s is rejected `FILE_LOCKED` even though it is not changing. A time-since-last-change rule would satisfy both existing stability tests. That is a change to the stability rule in `processor.py`, which this repo reserves for explicit approval.

## Evidence (private, outside the repo)

`%LOCALAPPDATA%\Temp\bb-identity-20261007\`: `run1.log` (before fixes), `run3\` and `run3.log` (final), `suite-merge-baseline.log`, `suite-final.log`, `phone-screens-375\` (before) and `phone-screens-final\` (after), and `phone_screens.py`, the scratch tool that captured them through a 375 px frame.
