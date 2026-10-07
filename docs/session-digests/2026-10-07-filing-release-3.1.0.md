# 2026-10-07: BarcodeBuddy 3.1.0 released (tag v3.1.0, main fast-forwarded)

Agent: Claude (Fable 5.1), session https://claude.ai/code/session_01J4q9SunhdtiRMfSuUDrKRb. David said "Do it" to the two agent-owned items left after 3.0.0: move PDF reading off the AGPL library, and fix the "Inventory Management" sidebar label.

## What changed since 3.0.0

1. **Merged the other agent's Windows line into main** (`cf4efae`, merging `feature/native-integration-20261007-1120` at `3b8b56f`, committed at 09:59 after the 3.0.0 release). It bounds OpenBLAS to 1 thread and OpenCV to 2 by default after real allocation crashes on a 24-core Windows host, and adds real-process watcher tests. Two conflicts: the identical watcher fix (kept the commented version) and the backup routine, where the two lines fixed backup-while-running in opposite ways. Kept the release design (live databases captured through SQLite's backup API at their own path plus `database/barcode_buddy.db`) and changed the other line's test to assert the same intent (both copies consistent, no WAL, SHM or journal files).
2. **PyMuPDF removed** (`2c35217`). PDF reading uses PDFium through pypdfium2 (BSD-3-Clause/Apache-2.0), reading the document from memory so no handle stays open on a scan. The scan-to-PDF report writer uses ReportLab (BSD) with the same layout. `tests/test_dependency_licenses.py` fails the build if a GPL or AGPL package or import comes back. Every installed library is permissive (`THIRD-PARTY-NOTICES.md`).
3. Sidebar subtitle reads "Document Filing" when no buyer name is set; footer version comes from `app.__version__`.
4. `sales/OFFER.md` says "excludes" again: the 3.0.0 rewrite dropped the word and `scripts/identity_acceptance.py` line buyer-03 checks for it.

## Verified on a clean machine (fresh clone of `2c35217`, fresh Python 3.12, constraints.txt, PyMuPDF not installed)

- Release gate `--product-only`: ready. 491 tests passed, 1 Windows-only skip, launcher probes executed in PowerShell 7.4.6.
- Demo kit through the real reader: 9 of 9.
- Live run: 4 good scans filed in 10 s, 5 problem scans set aside with the right reasons in 7 s, a new scan filed 3 s after restarting both services, backup while running verified and restored (5 PDFs, 5 rejected, database ok, owner present).
- Identity acceptance on the merged candidate before the offer fix: 134 of 144 proven; the 2 failures were the known shared-stock owner decision and buyer-03 (fixed in this release); 8 blocked on hardware, a model or a buyer.
- Every pin in constraints.txt has a Windows wheel (`pip download --platform win_amd64`).
- Screens at 1440 and 375 px: page width equals viewport, no script errors, sidebar shows "Document Filing".

## Still owed

- A native Windows install from the tag. The developer PC was at 167 of 171 GB committed memory all morning.
- A real scanner and real customer documents.
- Owner decisions: price, the licensor's legal entity, a lawyer's read of the license. The PDF licensing item is settled.
