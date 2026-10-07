# 2026-10-07: BarcodeBuddy 3.0.0 released (tag v3.0.0, main fast-forwarded)

Agent: Claude (Fable 5.1), session https://claude.ai/code/session_01J4q9SunhdtiRMfSuUDrKRb

## Why

David asked for an audit of why two years of agent work produced no commercial closure, and for one finished, demonstrable, sellable application. The recommendation he was given: ship Barcode Buddy's filing workflow as a licensed, self-installed product (buyer pays once, owns the install and the data; David keeps the software and sells it again), and stop adding to it until the first license is paid. That freeze is Claude's recommendation to David, not yet his recorded decision.

## Finish line and what met it

1. One frozen release, tagged, tests and release gate green on that exact commit: `v3.0.0` = `21ad5b4`. `scripts/release_gate.py --product-only` on a clean clone: ready, all nine product gates passed, 479 tests passed, 1 Windows-only skip, launcher parser and native probe executed (PowerShell 7.4.6 on Linux).
2. Fresh install from the documented steps, demo scans through the real watched folder, restart, backup and restore: done on a clean Linux machine (fresh clone, fresh Python 3.12 venv, constraints.txt). 4 good scans filed in 10 s; 5 problem scans set aside with the right reason in 7 s; filing continued after restarting both processes; backup taken while running, verified and restored with 5 PDFs, 5 rejected files and an intact database.
3. Demo kit and five-minute script: `scripts/make_demo_kit.py`, `sales/DEMO.md`, guarded by `tests/test_demo_kit.py` (real reader, both direct and through the running watcher).
4. Ownership terms: `sales/LICENSE-AGREEMENT.md`, `sales/ORDER-FORM.md`, `sales/OFFER.md`, `THIRD-PARTY-NOTICES.md`. Drafts for legal review.
5. Screens a buyer sees, at 1440 and 375 px: sign-in, overview, Documents. No horizontal overflow, no script errors.

## Changes (commits 9f01b66, 21ad5b4)

- Release gate `--product-only`: requires every product gate, records `release_kind: product-only`, and leaves out only the Built To Own repository gate. The default full release still requires acquisition and still fails closed.
- Documents screen: rejected scans lead with the reason in plain words; the outcome also shows under the file name so it is visible on a phone.
- `constraints.txt`: exact versions tested; installers use it. Every pin has a Windows wheel.
- Client-facing copy: no em dashes, no forbidden words (checked by script over sales/, docs/customer/, release/).

## Not proven, and why

- A native Windows install from the tag. The developer PC was out of committable memory (170.3 of 170.9 GB committed, about 400 conhost, 250 PowerShell and 200 node processes) and Windows PowerShell does not respond there, so the two memory-starved test failures seen on the PC (`MemoryError`) are machine faults, and the Windows run is still owed.
- A real scanner and any real customer document.
- The PDF library: PyMuPDF is AGPL or Artifex commercial. Settle before the first signed license (buy the commercial license, move PDF reading to a permissive library, or get legal advice).

## For the next agent

Build on `main` (= v3.0.0). Do not open another "finish Barcode Buddy" branch. Anything that changes what the buyer installs needs a new tag and a new gate receipt. The Built To Own factory line and the inventory, AI and team features are outside the 3.0.0 offer.
