# BarcodeBuddy $10K Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Productize BarcodeBuddy into a verifiable $10,000 one-site/one-workflow installed system and wire its prospect qualification into Built To Own without enabling uncontrolled outreach.

**Architecture:** Keep the barcode/FSM/auth core stable. Add release-oriented adapters around the existing processor: secure provisioning, isolated customer-sample acceptance, checksum-backed backup verification, a release gate, documentation, and a deterministic Built To Own product-fit/call-queue layer.

**Tech Stack:** Python 3.12, pytest, FastAPI codebase, PowerShell, Node.js/CommonJS for Built To Own, Git worktrees.

**Spec:** `docs/superpowers/specs/2026-10-06-barcodebuddy-10k-release-design.md`

## Global Constraints

- Do not modify the processing FSM, barcode validation rules, auth/session logic, config schema, or database model migration patterns without explicit defect evidence and tests.
- BarcodeBuddy must remain fully functional without AI.
- Default web binding is loopback-only; LAN and tunnel access are explicit.
- No customer sample is mutated.
- No customer secret is committed.
- No outreach is sent and no call is placed by the build.
- All success claims require fresh executable evidence.
- Preserve the dirty canonical BarcodeBuddy checkout untouched.

## Review Focus

- Customer configs with absolute/relative paths and spaces must survive provisioning and launcher quoting.
- A sample manifest containing missing files, duplicate IDs, invalid expectations, or path traversal must fail safely.
- Acceptance runs must not leak source documents or mutate originals.
- Backup verification must detect missing or tampered members.
- Call-queue qualification must preserve unknowns and must not promote a prospect based on fabricated workflow facts.

---

### Task 1: Stabilize the baseline PowerShell parser guard

**Files:**
- Modify: `tests/test_windows_scripts.py`

**Interfaces:**
- Consumes: Windows PowerShell if responsive.
- Produces: a syntax test that fails on parser errors and explicitly skips when the shell cannot start within a bounded timeout.

- [x] Run the current test and record the timeout failure.
- [x] Add bounded shell-unavailable handling without weakening syntax assertions.
- [x] Run `pytest tests/test_windows_scripts.py -q`.
- [x] Run full compile + test baseline.
- [ ] Commit the test-infrastructure repair.

### Task 2: Secure provisioning and launcher exposure

**Files:**
- Create: `app/customer_provisioning.py`
- Create: `scripts/provision_customer.py`
- Create: `provision-customer.ps1`
- Modify: `start-app.ps1`
- Modify: `install-autostart.ps1`
- Modify: `.gitignore`
- Modify: `tests/test_windows_scripts.py`
- Create: `tests/test_customer_provisioning.py`

**Interfaces:**
- Produces: `build_customer_config(workflow_key, root, secret_key) -> dict`; customer provisioning CLI; launcher `-Config`, `-Lan`, `-Tunnel` switches.

- [ ] Write failing tests for loopback default, explicit LAN mode, config passthrough, generated-secret requirements, safe workflow keys, and ignored customer config.
- [ ] Verify RED.
- [ ] Implement minimal provisioning module, CLI/wrapper, and launcher/autostart changes.
- [ ] Verify targeted tests GREEN.
- [ ] Run compile + full suite.
- [ ] Commit.

### Task 3: Customer-sample acceptance harness

**Files:**
- Create: `app/acceptance.py`
- Create: `scripts/run_acceptance.py`
- Create: `tests/test_acceptance.py`
- Create: `acceptance/example-manifest.json`
- Create: `acceptance/README.md`

**Interfaces:**
- Produces: `run_acceptance(config_path, manifest_path, report_dir) -> dict`; CLI exits 0 only when every case matches.

- [ ] Write failing tests for manifest validation, source immutability, path traversal, duplicate IDs, success/failure comparison, SHA-256 evidence, and report generation.
- [ ] Verify RED.
- [ ] Implement manifest parser and isolated runtime execution around `BarcodeBuddyService.process_file()`.
- [ ] Verify targeted tests GREEN.
- [ ] Run compile + full suite.
- [ ] Commit.

### Task 4: Checksum-backed backup and round-trip verification

**Files:**
- Create: `app/release_backup.py`
- Create: `scripts/customer_backup.py`
- Create: `tests/test_release_backup.py`

**Interfaces:**
- Produces: `create_backup(...)`, `verify_backup(...)`, and verified extraction.

- [ ] Write failing tests for manifest creation, tamper detection, default document exclusion, optional document inclusion, and safe extraction.
- [ ] Verify RED.
- [ ] Implement minimal backup/verification logic.
- [ ] Verify targeted tests GREEN.
- [ ] Run compile + full suite.
- [ ] Commit.

### Task 5: Release gate and evidence receipt

**Files:**
- Create: `app/release_gate.py`
- Create: `scripts/release_gate.py`
- Create: `tests/test_release_gate.py`
- Create: `release/README.md`

**Interfaces:**
- Produces: deterministic JSON receipt with individual gate status and overall `ready: true|false`.

- [ ] Write failing tests for mandatory gate aggregation, failed-command behavior, config/security checks, and no-green-receipt-on-failure.
- [ ] Verify RED.
- [ ] Implement release gate.
- [ ] Verify targeted tests GREEN.
- [ ] Execute a real gate against this branch and inspect the receipt.
- [ ] Commit.

### Task 6: Customer and commercial package

**Files:**
- Create: `docs/customer/INSTALL.md`
- Create: `docs/customer/ACCEPTANCE.md`
- Create: `docs/customer/OPERATIONS.md`
- Create: `docs/customer/ADMIN-RECOVERY.md`
- Create: `docs/customer/SECURITY.md`
- Create: `sales/OFFER.md`
- Create: `sales/DISCOVERY.md`
- Create: `sales/SAMPLE-REQUEST.md`
- Create: `sales/STATEMENT-OF-WORK.md`
- Create: `sales/QUALIFICATION.json`
- Modify: `README.md`
- Modify: repository artifact-consistency tests.

**Interfaces:**
- Produces: one consistent $10,000 offer and operator handoff, grounded only in shipped behavior.

- [ ] Add failing artifact-consistency tests for all referenced files/commands.
- [ ] Write customer and sales package.
- [ ] Verify doc/config tests GREEN.
- [ ] Run compile + full suite.
- [ ] Commit.

### Task 7: Built To Own BarcodeBuddy product-fit and call queue

**Workspace:** separate isolated Built To Own worktree.

**Files:**
- Create: `ops/product-profiles/barcodebuddy.json`
- Create: `scripts/qualify-product-prospect.cjs`
- Create: `scripts/build-call-queue.cjs`
- Create: `scripts/test-barcodebuddy-acquisition.mjs`
- Modify: `package.json`

**Interfaces:**
- Produces: validated product-fit JSON and sorted discovery-call queue; never sends or dials.

- [ ] Create isolated worktree and verify Built To Own baseline.
- [ ] Write failing Node tests for scoring, exclusions, unknown handling, decision authority, and send lock.
- [ ] Verify RED.
- [ ] Implement profile + qualifier + queue builder.
- [ ] Verify targeted tests GREEN.
- [ ] Run `npm run verify`.
- [ ] Commit.

### Task 8: Final verification and branch closeout

- [ ] Run BarcodeBuddy compile.
- [ ] Run BarcodeBuddy full pytest suite.
- [ ] Run real release gate and inspect receipt.
- [ ] Run a synthetic real-processor acceptance set.
- [ ] Verify backup round-trip.
- [ ] Verify git diff contains no secrets/customer documents.
- [ ] Run Built To Own verify.
- [ ] Review diffs against the spec.
- [ ] Update BarcodeBuddy build state/session log/session digest.
- [ ] Commit all final documentation/evidence references.
- [ ] Finish branches without merging/pushing/deploying until the integration gate is reached.

## Execution Ruling

Owner instruction “BUILD EVERYTHING” authorizes inline execution of this plan without per-task approval prompts. The build still stops for destructive operations, security-sensitive external side effects, or merge/push/publication decisions.
