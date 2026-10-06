# BarcodeBuddy $10K Release Design

**Date:** 2026-10-06
**Status:** approved for execution by the owner ("BUILD EVERYTHING")
**Base commit:** ee9ba78383870c95a0e288c906b8a43036c5a82b
**Release branch:** feature/10k-release-20261006

## Goal
Turn the existing deterministic BarcodeBuddy document-routing system into a repeatable, ownable $10,000 installed business system for one customer site and one production document workflow.

The release does not broaden the barcode engine. It productizes installation, security defaults, customer-sample acceptance, backup verification, release evidence, operator documentation, and the sales handoff around the proven core.

## Commercial product
**Offer:** BarcodeBuddy Document Automation System — $10,000 implementation.

Included:
- one physical customer location;
- one production workflow such as receiving paperwork or proof-of-delivery filing;
- local/on-prem Windows deployment;
- customer-specific config and barcode rule configuration from real samples;
- scan-folder intake and deterministic PDF routing;
- explicit rejected-document handling;
- operator/admin setup;
- sample acceptance report;
- production-readiness verification;
- installation and operating documentation;
- 30-day stabilization window.

Not included:
- ERP attachment integration;
- OCR or handwriting interpretation;
- signature verification;
- mixed-document batch splitting;
- custom mobile capture;
- multi-site deployment;
- customer-specific features not required for the accepted workflow.

Additional workflows/sites are separate scoped work.

## Engineering constraints
1. Preserve the existing processing FSM and barcode validation rules unless an explicit, tested defect is discovered.
2. Core product must work without AI.
3. Default web exposure is loopback-only. LAN or public access is explicit opt-in.
4. Customer secrets are generated per installation; repository defaults are never reused as customer credentials.
5. Customer acceptance runs on copies of supplied samples in an isolated temporary workspace and never mutates originals.
6. Acceptance reports retain hashes and outcome metadata, not document contents.
7. Backups are checksum-manifested and verified before being called valid.
8. Release claims require fresh executable evidence.
9. Outbound automation remains draft/call-queue only until identity, suppression, provider, and compliance gates are configured.
10. Existing dirty work in the canonical checkout remains untouched.

## Components

### Secure customer provisioning
A PowerShell provisioning script creates a project venv, installs dependencies, generates a unique strong secret, creates a customer config, validates it, and prepares workflow directories.

The launcher gains `-Config <path>`, loopback binding by default, explicit `-Lan` for `0.0.0.0`, while `-Tunnel` remains explicit opt-in. Autostart passes config/exposure mode through exactly.

### Customer-sample acceptance harness
A Python runner consumes a JSON manifest of redacted customer samples and expected outcomes. It copies samples into an isolated temporary runtime, executes the real `BarcodeBuddyService.process_file()` contract, compares actual status/barcode/reason against expectations, and writes JSON + Markdown reports.

Reports include product/version, workflow/config checksum, sample SHA-256, expected outcome, actual outcome, pass/fail per case, and aggregate counts. No mocks are used by the acceptance CLI.

### Backup verification
A deterministic backup utility captures customer configuration plus operational metadata/database material into a ZIP with a SHA-256 manifest. Verification recalculates every stored hash. A round-trip verifier extracts into a temporary directory and proves internal consistency. Document payload inclusion is explicit because archives may be large.

### Release gate
A developer-facing release gate runs compilation, full pytest, repository config validation, launcher safety checks, optional acceptance, backup round-trip, security-default checks, and git metadata capture. It writes a machine-readable release receipt. No green receipt is emitted after a failed mandatory gate.

### Customer package
Add installation, acceptance, operator, admin/recovery, security/deployment, and support-handoff documentation. No unfinished feature is documented as shipped.

### Sales package
Define the $10,000 scope, qualification checklist, discovery questions, sample-request checklist, statement-of-work template, acceptance/payment milestones, truthful limitations, and objection handling. The sale is framed around eliminating manual scan/rename/file/retrieval work, not AI.

### Built To Own acquisition integration
Built To Own remains prospect-facing. Add a deterministic BarcodeBuddy product-fit profile and call-queue builder that ingests candidate records, scores only business/workflow evidence, excludes enterprise/no-authority/non-physical-operation cases, preserves missing discovery facts, produces a sorted discovery-call queue, never sends/dials itself, and keeps existing approval/send locks.

Existing Site Foundry evidence may be input; its general customer-acquisition auditor is not rewritten.

## Verification criteria
Release is eligible to sell only when:
- the isolated branch compiles;
- the full BarcodeBuddy suite passes, with environment-unavailable parser checks explicitly skipped rather than silently passed;
- new release tests pass;
- a synthetic acceptance manifest proves success and failure cases through the real processor;
- launcher tests prove loopback default and explicit LAN/tunnel modes;
- backup round-trip passes;
- release gate emits a green receipt;
- Built To Own verification passes after product-fit integration;
- no actual outbound message/call is sent during build.

## Release boundary
This branch is not merged, pushed, or deployed automatically as a side effect of implementation. Integration follows the repository's branch-finish gate after fresh verification.
