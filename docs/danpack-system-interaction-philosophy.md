# Danpack System Interaction Philosophy

Last updated: 2026-04-03.

This document defines the interaction and operational philosophy that should govern any future human-facing surface built around BarcodeBuddy or its adjacent workflows.

Current repo reality:

- BarcodeBuddy is a deterministic hot-folder service with no operator workflow UI today.
- The repo does include a local read-only stats page exposed by `stats.py`.
- This document does not change that scope.
- This document exists so the next builder does not invent a cluttered dashboard, an overbuilt admin console, or a mixed workflow surface that conflicts with how Danpack and similar companies actually work.

Use this document together with:

1. `README.md`
2. `docs/danpack-builder-handoff.md`
3. `docs/industry-workflow-research.md`
4. `docs/packaging-industrial-operating-model.md`
5. the code in `main.py` and `app/`

## 1. System Scope

This philosophy applies to any future:

- workflow configuration tool
- rejection review screen
- operator console
- admin panel
- document search or retrieval tool
- notification model
- exception queue
- scanner or shared-folder deployment surface

It does not authorize broad product expansion into OCR, classification, ERP orchestration, or generic document management.

## 2. Research Synthesis

The strongest patterns across consumers, developers, entrepreneurs, SMBs, and packaging or industrial operators are stable:

- users keep only tools that prove value quickly
- users search or scan under time pressure instead of browsing deep menus
- users abandon systems that interrupt them before the core job is done
- reliability is worth more than richness
- advanced capability is accepted only when it stays out of the default path
- packaging and industrial operations are role-based and stage-based, not dashboard-first
- document workflows break most often at approvals, exceptions, wrong attachments, duplicates, and fragmented system state

Cross-checked operational implications:

- custom packaging work behaves like a gated project flow
- industrial supply work behaves like a repeat replenishment flow
- BarcodeBuddy itself fits neither as a dashboard nor as a generic document inbox
- BarcodeBuddy is an intake and exception-management utility inside a larger operational system

## 3. Core Philosophy

- The system `MUST` exist to move work forward, not to expose features.
- The default path `MUST` prioritize the current job, current exception, or current lookup.
- The system `MUST` optimize for busy operators, customer service staff, receiving staff, shipping staff, and compliance staff who need a result quickly.
- Reliability, determinism, and traceability `MUST` outrank breadth, novelty, or visual density.
- Every visible control `MUST` answer one of four needs: act now, understand state, recover from failure, or explicitly configure the workflow.

## 4. Visibility Rules

- Default surfaces `MUST` show only the active work area, critical state, and the minimum controls required to proceed.
- Secondary metrics, historical charts, and broad analytics `MUST` be hidden by default.
- Settings, diagnostics, and destructive actions `MUST` be hidden behind explicit operator intent.
- If a user is handling a rejection, they `MUST NOT` be shown unrelated workflow controls.
- If a user is configuring a workflow, they `MUST NOT` be shown production review noise.

## 5. Mode Separation Rules

The builder `MUST` preserve hard mode separation between:

- `custom packaging / project work`
- `industrial supply / repeat replenishment work`
- `BarcodeBuddy intake / routing / exception handling`

Rules:

- These modes `MUST NOT` share one default home screen.
- BarcodeBuddy surfaces `MUST` be framed around intake, lookup, and exceptions, not around full packaging project management.
- Repeat ordering surfaces `MUST` prioritize barcode, PO, shipment, receipt, SKU, quantity, and status.
- Custom project surfaces `MUST` prioritize current stage, approval state, proof version, and release readiness.

## 6. Contextual Rendering

- The system `MUST` determine "what matters now" from workflow, role, stage, and exception state.
- An element `MAY` appear only if it is needed for the current task, current exception, or current configuration step.
- Role surfaces `MUST` be distinct.

Minimum role model:

- receiving
- shipping or POD
- quality or compliance
- admin or configuration

Future extensions such as prepress, planning, or warehouse review `MAY` exist, but they `MUST` follow the same role-specific rule.

## 7. Progressive Disclosure

- Advanced options `MUST` remain collapsed by default.
- Bulk actions, regex rules, barcode-type overrides, retention choices, and diagnostic settings `MUST` be disclosed only when needed.
- Disclosure depth `MUST NOT` exceed two layers from the current task surface.
- Advanced configuration `MUST` stay local to the current workflow instance and `MUST NOT` spill across other workflows.

## 8. Interaction Priority

- Every task surface `MUST` have one primary action.
- No surface `MUST` present more than three secondary actions at the same decision point.
- The primary actions for BarcodeBuddy-adjacent surfaces should usually be one of:
  - review rejection
  - retry or reprocess
  - open routed document
  - find document
  - save workflow settings
- Destructive actions such as delete, purge, or remove workflow `MUST NEVER` share equal visual or interaction priority with corrective actions.

## 9. Cognitive Load Constraints

- A single task surface `MUST NOT` expose more than seven interactive controls before disclosure.
- A single operator decision point `MUST NOT` require comparison across more than three competing choices.
- A rejection review surface `MUST` show the reason, original file, barcode context, and next action before any secondary metadata.
- The system `MUST NOT` require users to infer what failed from absence alone.

## 10. Search-First And Scan-First Rules

- Any future human-facing surface `MUST` support direct retrieval by the identifiers users actually have on hand.
- Retrieval `MUST` support, as applicable:
  - barcode value
  - PO number
  - shipment or delivery number
  - receipt number
  - original filename
  - processing ID
- If physical paperwork is present, scan-based lookup `SHOULD` be preferred over deep navigation.
- Search `MUST` be reachable from anywhere meaningful in the system.

## 11. Feedback And State Visibility

- The system `MUST` always show whether a file is pending, processing, routed, rejected, recovered, or blocked.
- Long-running work `MUST` show explicit processing state.
- Failed work `MUST` show the precise failure reason and immediate next step.
- Workflow configuration `MUST` show whether the current config is valid, incomplete, or unsafe.
- Success and failure `MUST NOT` rely on color alone.

## 12. Exception-First Model

- Normal flow work `MUST` stay quiet.
- Exceptions `MUST` be the default review surface.
- The builder `MUST` prefer "show me what needs attention" over "show me everything."
- Exception queues `MUST` group by actionable cause, not by generic time order alone.

Minimum actionable rejection groups:

- barcode not found
- invalid barcode format
- duplicate file
- file locked
- corrupt or unsupported input

## 13. Canonical Record Rules

- Every routed document `MUST` have one canonical result state.
- Every rejected document `MUST` have one canonical failure record and one canonical rejection reason.
- The system `MUST NOT` create parallel truth sources across UI, logs, and sidecars with conflicting status meanings.
- If a future database or API is added, it `MUST` preserve the current log and rejection semantics or intentionally migrate them with backward-compatible reasoning.

## 14. Toggle-Based Enhancement Rules

- Optional features `MUST` be off by default.
- Potential future enhancements such as notifications, dashboards, rule suggestions, AI-assisted triage, or scanner health insights `MUST NOT` appear in the base path unless explicitly enabled.
- Enhancements `MUST` be reversible and scoped to the workflow or role they affect.
- One workflow's complexity `MUST NOT` clutter another workflow's defaults.

## 15. Default State Definition

The clean default state for BarcodeBuddy-adjacent tools is:

- current workflow selected
- healthy or unhealthy service state visible
- current exception count visible if non-zero
- fastest retrieval path visible
- one primary next action visible

The default state `MUST NOT` include:

- executive dashboard metrics
- broad historical charts
- cross-workflow clutter
- dormant widgets
- upsell-style banners
- speculative AI prompts

## 16. Failure And Recovery Philosophy

- Every failure `MUST` say what failed, why it failed, what file it affected, and what the operator can do next.
- Recovery `MUST` preserve the source artifact whenever safe.
- Reprocessing `MUST` be explicit and auditable.
- Common failures `MUST` be recoverable without forcing users into logs unless the failure is truly diagnostic.
- Support-only recovery for common operator failures is forbidden.

## 17. Notification Budget

- Non-critical notifications `MUST` be off, batched, or summarized by default.
- Immediate interruption is allowed only for:
  - service stopped
  - input path unavailable
  - processing path jammed
  - log write failure
  - sustained rejection spikes
- Routine successes `MUST NOT` interrupt users.

## 18. Compliance And Audit Visibility

Because Danpack operates in compliance-sensitive packaging domains:

- audit-relevant state `MUST` be visible when reviewing failures or routed documents
- version, time, workflow, and processing identity `MUST` remain accessible
- regulated or compliance-sensitive workflows `MUST` favor strict validation over silent acceptance
- configuration changes `MUST` be attributable and reviewable if future admin tooling is added

## 19. Strictly Forbidden

- one giant dashboard that mixes receiving, POD, quality, and admin concerns
- generic inboxes with no workflow separation
- hidden critical recovery actions
- default surfaces full of metrics that do not change the next action
- duplicate controls for the same outcome
- forcing users to browse for records when they already have an identifier
- showing advanced regex, scan, or diagnostic settings to non-admin operators by default
- silent failure where the only evidence is a missing output file
- AI or automation that changes routing behavior without explicit review and traceability
- expanding BarcodeBuddy into OCR or document guessing without an explicit product decision

## 20. Builder Implications

The next builder should treat this philosophy as implementation guidance:

### 20.1 If no operator workflow UI is built yet

- keep runtime behavior simple
- preserve and extend the existing tests first
- preserve and refine the existing workflow-specific config artifacts
- improve rejection clarity before adding new surfaces

### 20.2 If an operator-facing surface is built

- start with a workflow-specific exception console, not a dashboard
- start with retrieval and rejection review, not analytics
- make search and scan the main entry points
- keep admin settings separate from operator review

### 20.3 If notifications are added

- ship exception summaries before real-time alerts
- prove operational need before enabling anything noisy

## 21. Dependency-Aware Execution Order

This is the correct order for future builder work:

1. Preserve the current runtime behavior and keep the existing tests green.
2. Preserve the workflow-specific configs and docs for `receiving`, `shipping_pod`, and `quality_compliance`, then refine them only with real operational input.
3. Improve exception semantics and retrieval clarity using the current log and sidecar model.
4. Add only the minimum human-facing surfaces needed for exception review or configuration.
5. Add integration, compliance, or richer workflow state only after real Danpack samples and operational data exist.

## 22. Missing Data Still Worth Collecting

The builder should not hallucinate these:

- real Danpack barcode formats by workflow
- real sample documents
- actual rejection frequencies by cause
- actual duplicate patterns by workflow
- retrieval identifiers operators use most often
- whether users need barcode-scan lookup on mobile or desktop first
- whether compliance workflows need stronger audit surfaces than receiving or POD

## 23. Bottom Line

Do not build a broad interface.

Build a narrow, fast, exception-first operating surface that:

- respects workflow boundaries
- keeps defaults clean
- makes routing state obvious
- makes failures recoverable
- lets users find what they need by the identifier they already have

That is the correct interaction model for this repo, this business, and this stage of the system.
