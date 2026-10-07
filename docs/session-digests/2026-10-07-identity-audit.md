# Barcode Buddy identity audit — October 7, 2026

Owner outcome: list every relevant identity and its tasks; require 100/100 applicable checks. The catalogue covers 100 practical roles in 10 groups. This is a finite role/workflow taxonomy; renamed job titles do not create new capabilities. Industry-specific operations remain explicit gaps, not automatically promised features.

Starting source: 5145a8dc3e7204a2353538dffc9acb495df2f5ef. New isolated branch: fix/identity-audit-negative-stock-20261007. Canonical checkout and all peer candidates are preserved. Native shared-task status reports no project registration (unmanaged); no managed authority was substituted.

Fresh baseline: 444 tests passed, 2 explicit native PowerShell skips, 70 subtests. The 100-identity synthetic run executed 1,296 real API/processor checks: 1,205 passed and 91 reproduced the same direct-edit negative-stock defect. No production DB, real messages, model calls, payments or household actions were used.

Root cause: ItemCreate.quantity has ge=0; ItemUpdate.quantity lacked that boundary. PUT writes the submitted value and a transaction directly. Adjustment separately rejects negative results. Two RED regressions demonstrated HTTP 200 for negative quantities; two zero/positive control cases passed. Minimal fix: apply the same ge=0 boundary to optional direct-edit quantity. Rejection must preserve both stock and transaction history.

Owned paths: app/inventory_routes.py; tests/test_inventory.py; docs/session-digests/2026-10-07-identity-audit.md. The native byte-preservation guard captured these exact paths before editing.

Full candidate suite, 100-identity rerun, preservation check, commit and report receipt are pending. Release remains blocked by executed native launcher/parser proof, final reconciled factory sequence, authorized repository publication scope and installation-specific scanner/restore/handoff proof. Do not bypass the recorded release capability denial or declare this deployed.

## Final verification and retained checkpoint

The complete repaired native suite passed 448 tests with 2 explicit PowerShell skips, 70 subtests and one existing Starlette deprecation warning. The same 100-identity replay passed all 1,296 core API/processor checks with no failures. The four native quantity-edit regressions include preserved quantity/history on rejection and valid zero/positive updates. No role's complete journey or installation is inferred from that proof.

The standalone catalogue has 100 roles in 10 groups, 100 shared acceptance checks, 400 role-specific full-workflow checks and 20 user/device variants. Its 1,816 unique checks remain evidence-driven; any failure, skip, missing or stale proof blocks 100/100. Authored outputs: BarcodeBuddy-Identity-Checklist-2026-10-07.html, .md and .zip. The bundle includes the deterministic replay, checklists and source-bound receipts.

Next native integration action: incorporate this branch's tested app/inventory_routes.py change and regression tests into the currently owned release candidate; retain the source guard and rerun its changed source gates. Then prove the actual supported Windows parser/launcher, isolated installed scanner/owner/restart/restore, shared-staff stock permissions and concurrent writes, rendered camera/upload behavior, final current native/factory sequence and authorized publication. Existing source ownership and release authority remain intact. Nothing is pushed, merged into a peer branch, installed, deployed or sold by this audit. The existing governed advisory denial is retained without an unchanged inference retry.
