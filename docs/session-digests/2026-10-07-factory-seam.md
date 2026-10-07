# Barcode Buddy factory seam — 2026-10-07

Approved scope: Task 7 of the Product Factory / Barcode Buddy plan. Isolated worktree factory-seam-20261007-0451 starts from native release checkpoint 5145a8dc3e7204a2353538dffc9acb495df2f5ef. Canonical source and verified-release-20261006-2033 were preserved.

## Implemented

- Frozen Branding value object and non-secret BB_ORGANIZATION_NAME loader; default product identity is Barcode Buddy.
- Organization text is HTML-escaped in the shared shell, login, signup and password-reset page display. The existing BarcodeBuddy version footer stays compatible. Authentication API function bodies, cookies, roles and sessions are unchanged.
- scripts/factory_acceptance.py creates a fresh synthetic workspace and proves real Code128 PDF routing, preserved no-barcode rejection, duplicate rejection, stranded processing-file recovery, and native SQLite backup content/integrity with WAL mode.
- Existing workspaces and active database engines are refused before writes. All runtime paths belong to the fresh root. The probe stops its service, closes SQLite read connections, and shuts down its temporary database.
- The CLI writes an exclusive fsynced JSON receipt with expected/observed values and five named outcomes. Existing receipts are never overwritten. It always records synthetic=true, customer_approval=false and deployment_verified=false.

## Verification evidence

Pre-edit baseline: 444 passed, two Windows launcher/parser skips, 70 subtests passed; compileall passed.

TDD: focused tests first failed because the two new modules were absent; 14 tests then passed. Full-suite failure found a legacy statistics branding assertion, corrected by preserving the original version footer. Review found unclosed SQLite read handles; a real retained-connection regression reproduced the issue before contextlib.closing fixed it.

Latest focused gate: 21 passed (15 new branding/acceptance cases plus six existing statistics cases).

Final full native suite: 459 passed, two Windows launcher/parser skips, 70 subtests passed, one existing Starlette warning, 384.36 seconds. Compilation passed. Standalone native reference CLI passed all five real probes. Authentication API AST comparison confirmed all API function bodies unchanged. Source-preservation guard and git diff --check passed.

Private evidence prefix:
C:/Users/david/AppData/Local/Temp/bto-finish-20261007-0451

Logs: bb-final-suite-fixed, bb-final-compile-fixed, bb-reference-final-cli, bb-auth-boundary-fixed and bb-final-guard-fixed. Native reference receipt: bto-finish-20261007-0451-bb-reference-final-receipt.json. No deployment, customer acceptance or sellable readiness is inferred from unit tests or this synthetic probe.

## Review and release boundary

Fresh review and follow-up report no Critical/Important findings. The SQLite cleanup Minor was resolved with a regression. Native source admission remains UNMANAGED through the actual shared-task CLI, without an identity bypass.

Native Windows PowerShell launcher/parser execution remains blocked on the host; two skipped tests do not satisfy that release gate. Publication still needs the actual BarcodeBuddy release repository capability/scope. The factory CLI peer candidate and downstream reference/public-offer tasks remain separate pending integration; no peer source was adopted.
