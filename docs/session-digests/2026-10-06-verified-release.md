# BarcodeBuddy release continuation

Plan: docs/superpowers/plans/2026-10-06-barcodebuddy-10k-release.md
Spec: docs/superpowers/specs/2026-10-06-barcodebuddy-10k-release-design.md
Latest owner instruction: commit the current BarcodeBuddy work (2026-10-07 UTC).
Candidate: feature/verified-release-20261006-2033; base 899c06fcc16e5a395c81a1cb71b8c080a8c565c0.
Canonical checkout and original 10k-release peer worktree remain untouched.
Native admission refreshed: UNMANAGED; no project registration or authority bypass.
Source guard: expanded baseline verified before staging; original baseline retained.

Implemented: isolated acceptance with source/report collision protection and strict expectations; checksummed backup and SQLite WAL restore proof; fail-closed release gates; customer and $10k one-site/one-workflow package. Incorporated existing raw-first barcode, multipage TIFF and ambiguous-routing fixes while preserving originals.

Verification:
- Compilation passed for app/scripts/tests/main.py/stats.py.
- Review regressions: 16 failures before repair, then 34 targeted tests passed.
- Final native full suite: 428 passed, 2 skipped, 1 warning, 70 subtests passed in 348.58s (0:05:48)
- Native PowerShell execution remains subject to the recorded skips; skipped/missing functional probe fails release readiness.
- Fresh read-only review: no Critical issue; both Important findings repaired in one RED-to-GREEN pass.

Final fixes:
- Unknown, missing, null, non-string, empty or invalid expected outcomes cannot silently weaken customer acceptance.
- Release receipts require the same clean Git revision before all checks and after acquisition verification.
- Customer readiness requires every mandatory gate; successful customer samples alone cannot make a failed release ready.

Rulings retained:
- Isolate this continuation to preserve peer untracked work. Cost if wrong: further integration work; no peer bytes discarded.
- Restore only into a new directory. Review absolute config paths before reconnecting a restored installation. Cost if wrong: incorrect reconnection could target the original runtime.
- Actual native PowerShell behavior is unverified on this host; the gate stays closed. Cost if wrong: launcher compatibility remains unresolved before delivery.
- Built To Own integration and real customer/scanner acceptance remain pending; this commit is a development checkpoint. Cost if wrong: customer-readiness claims would be unsupported.
- Parent owns full-suite evidence; the fresh reviewer did not rerun it.

Final: minor (deferred): acceptance instructions request output-PDF visual review, but the harness deletes temporary outputs. Document a separate isolated copy-based review run before operator handoff.

Release status: not deployed and not customer-ready. No outreach, calls, payments, public tunnel, household/network changes or customer documents were introduced.
