# Spec: Preserve ambiguous scans for review

> **Status:** built
> **Priority:** P1
> **Depends on:** none
> **Built by:** Codex session codex-bb-filing-fix-20261001
> **Source:** ee9ba78383870c95a0e288c906b8a43036c5a82b

## Developer Notes

David asked to "keep improving" after a synthetic benchmark exposed two filing
gaps: a mixed two-document PDF and one image with two eligible routing IDs were
both filed under one selected ID. The immediate goal is to prevent silent
misfiling while preserving the existing single-ID ingestion workflow and all
unrelated work in the canonical checkout.

## Behavior and scope

- After scanning, reject more than one distinct eligible routing value with
  canonical error AMBIGUOUS_BARCODE at validation, before any successful output.
- Preserve the complete source bytes in rejected, candidate evidence in the
  metadata sidecar, and an explicit terminal audit event. Do not choose one ID.
- Repeated detections of the same ID remain valid. A configured business rule
  excludes nonmatching IDs from ambiguity. Without rules, all values are eligible.
- Continue honoring scan_all_pages: false means only page one is inspected.
  This repair cannot detect a conflict on an unscanned page.
- Preserve current size, timeout, corrupt-input, invalid-format, duplicate and
  journal behavior. No database, auth, watcher, decoder or dependency changes.
- Mixed files require manual separation and resubmission. Automatic splitting,
  review UI, real Danpack acceptance and a FileCenter comparison remain separate.

## Files

- app/processor.py: guard the filing decision using existing candidate evidence.
- app/contracts.py: define and normalize the canonical rejection code.
- tests/test_service_runtime.py: across-page, same-page, no-rule, repeated-ID and
  unrelated-ID regression behavior; rejected bytes, sidecars, output and audit.
- tests/test_contracts.py: extend the existing canonical error contract.
- tests/test_config_artifacts.py: update existing documentation contract checks.
- .constraints/barcode-integrity.json: reconcile the former largest-ID rule.
- README.md and docs/{danpack-builder-handoff,production-operations-blueprint,
  scan-record-builder-handoff}.md: describe the changed rule and scanned-page limit.
- docs/build-state.md and docs/session-log.md: verification and delivery evidence.

## Spike and verification

The processor already collects distinct eligible values across scanned pages.
Its ranking previously chose a winner even when two eligible IDs conflicted.
The existing rejected-file path preserves originals and candidate evidence, so
this repair uses it without changing the state machine. The previous selection
constraint and documentation must change with this intentional contract change.

Baseline compilation exited 0; isolated HEAD tests passed 362 tests and 65
subtests with one pre-existing Starlette/httpx deprecation warning. Focused
post-change checks passed 45 tests and 58 subtests with the same warning.

Final verification requires compilation, the full isolated suite, integration
with foreign changes preserved, the full canonical suite, and replay of all 16
retained synthetic operations using the real decoder and copied originals.
The two ambiguous cases must reject with every conflicting ID retained and no
output; the other 14 outcomes must stay correct. Record actual results below.

## Coordination and delivery

The native shared-task PreToolUse hook explicitly admitted the unregistered
checkout as UNMANAGED. This is not a coordinated shared-task claim. Edits are
isolated on fix/ambiguous-filing-20261001 and only owned hunks may be integrated.
Pushes require an exact proposal through Agent Command's action broker. Do not
bypass that boundary or describe a pending proposal as a completed push.

## Timeline

| Recorded UTC | Event | Evidence |
|---|---|---|
| 2026-10-01T16:44:41.530021+00:00 | Baseline, repair and focused checks recorded; full verification in progress | baseline.xml; 45 passed, 58 subtests |
| 2026-10-01T16:48:33.576605+00:00 | Isolated full suite and compile passed; canonical integration pending | 364 passed, 65 subtests, one existing warning; isolated-full.xml |
