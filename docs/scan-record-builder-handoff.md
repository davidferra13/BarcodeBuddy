# Scan Record Builder Handoff

Last updated: 2026-04-03.

## 1. Purpose

This document turns the scan workbench design into a builder-ready execution plan.

Use it when implementing the future single-scan management page and its supporting persistence, API, and audit model.

This handoff is intentionally dependency-aware:

- understand current runtime truth first
- preserve the deterministic ingestion pipeline
- add missing data capture in the correct order
- keep immutable scan evidence separate from editable owner enrichment
- make every new capability auditable

Read this together with:

1. `README.md`
2. `docs/danpack-builder-handoff.md`
3. `docs/danpack-system-interaction-philosophy.md`
4. `docs/scan-record-workbench.md`
5. the code in `main.py` and `app/`

## 2. Current Runtime Truth Relevant To This Page

The current runtime can already produce part of a scan record, but not the full owner-grade audit surface.

### 2.1 What exists today

- one long-running Python ingestion service
- one JSON config file
- filesystem-managed source, processing, output, rejected, and log directories
- one append-only JSONL processing log
- rejection sidecars with failure context
- per-run `processing_id`
- workflow-level runtime metadata via `workflow`, `host`, `instance_id`, and `config_version`
- per-file recovery journals under `processing/.journal`
- barcode details, page count, output path, and rejection path in logs or sidecars

### 2.2 What does not exist today

- durable `scan_id`
- user identity capture
- device identity capture
- branch or site capture
- location history
- note storage
- link storage
- attachment storage model
- import/export job history
- append-only user action audit events
- queryable record store
- HTTP API
- UI

### 2.3 Immediate implication

The comprehensive owner page cannot be implemented cleanly on top of raw JSONL plus sidecars alone.

The next builder should not start with frontend code.

The correct path is:

1. preserve current runtime behavior
2. add durable record persistence
3. add immutable event and artifact models
4. add editable enrichment models
5. add read APIs or service adapters
6. build the page on top of those stable contracts

### 2.4 Current verification baseline

As of 2026-04-03, the current runtime contract is green and covered by `tests/test_service_runtime.py` plus the wider repo suite.

Current verified behavior:

- when barcode candidates are found but the selected value does not match the configured business rule, the runtime rejects as `INVALID_BARCODE_FORMAT`
- the runtime selects one candidate deterministically across the scanned document by business-rule match, then largest bounding box area, then earlier page number, then scan order
- the runtime uses the configured business rules to prioritize candidates rather than to create a separate ambiguity state
- `eligible_candidate_values` and `page_one_eligible_values` are still emitted as evidence fields for the future page, even though they are not current selection overrides

Verification command:

`py -B -m unittest discover -s tests -v`

## 3. Intelligent Architectural Decisions

These are the recommended decisions unless the builder finds a concrete reason to change them.

### 3.1 Keep the ingestion runtime authoritative for scan evidence

The runtime remains the source of truth for:

- claimed files
- output PDFs
- rejected files
- barcode interpretation
- processing timestamps
- stage transitions

Do not move source-of-truth processing behavior into the future UI.

### 3.2 Add a local database for recordability and queryability

The future scan workbench should be backed by a local SQLite database.

Why SQLite is the right next step here:

- the repo is single-node and local-first today
- the required page needs relational querying and history
- notes, links, import/export jobs, and audit events are awkward in JSONL-only storage
- it avoids introducing a network service dependency too early

The database supplements filesystem artifacts and logs. It does not replace them.

### 3.3 Preserve immutable evidence versus editable enrichment

The builder must maintain a hard split:

`Immutable evidence`

- original artifact facts
- processing runs
- raw barcode context
- routing results
- config snapshot used by a run
- processing-generated timestamps

`Editable enrichment`

- notes
- tags
- linked records
- owner assignment
- business status
- imports
- exports
- follow-up tasks or annotations

### 3.4 Use append-only audit events

Every user or system change relevant to the record should emit an append-only event.

No direct mutation should occur without an audit event.

### 3.5 Capture only truthful actor data

The current system cannot infer who physically scanned a document.

The builder should not fake this.

Truthful capture sources:

- static config per workflow or device
- upstream manifest or sidecar metadata if present
- later human attribution on the record page

If the upstream process cannot provide operator identity, the record should clearly show:

- `captured_by = unknown`
- `device_id = known`
- `capture_channel = known`

### 3.6 Make imports and exports first-class, auditable jobs

Imports and exports should not be invisible helper functions.

They should be durable records with:

- requestor
- requested at
- input or output format
- status
- item count
- merge result summary

## 4. Proposed Future Persistence Model

The builder should introduce the following durable entities.

### 4.1 Primary entities

- `scan_records`
- `scan_processing_runs`
- `scan_artifacts`
- `scan_links`
- `scan_notes`
- `scan_attachments`
- `scan_audit_events`
- `scan_import_jobs`
- `scan_export_jobs`

### 4.2 Identity model

- one `scan_record` per canonical scan record
- one or more `scan_processing_runs` per scan record
- the current runtime `processing_id` should be preserved on each run

This allows:

- initial processing run
- explicit reprocess runs
- comparison of routing outcomes across runs

### 4.3 Suggested storage location

Do not hide the new database in the existing log file path.

Instead, introduce a new managed directory, for example:

- `data/state`

and place the database there, for example:

- `data/state/barcodebuddy.sqlite3`

This is an intentional architecture change and should be updated consistently in:

- config
- docs
- runtime directory creation
- backup instructions

## 5. Delivery Order

This is the recommended execution sequence.

### Phase 1: Freeze and verify current ingestion truth

Objective:

- ensure the current service remains deterministic while new persistence is added

Tasks:

- run the existing test suite before any runtime changes
- add or refine tests only where the new persistence hooks touch the ingestion path
- document the exact fields currently emitted by logs and sidecars

Do not proceed if:

- current tests are failing
- runtime behavior is changing unintentionally

Exit gate:

- ingestion tests green
- current runtime truth still matches `README.md` and `docs/danpack-builder-handoff.md`

### Phase 2: Introduce capture context configuration

Objective:

- allow the runtime to capture known workflow and device context without guessing

Recommended new config keys:

- `workflow_key`
- `site_code`
- `site_name`
- `device_id`
- `capture_channel`
- `static_actor_label` optional
- `state_path`

Rules:

- all new keys should be optional at first except `workflow_key` once the record store is introduced
- if actor identity is unavailable, store null or `unknown`, not invented values

Exit gate:

- config loader validates the new fields
- runtime can emit contextual metadata without changing scan outcome behavior

### Phase 3: Add the SQLite record store

Objective:

- persist scan records and queryable history

Tasks:

- add schema migrations
- create the primary tables listed above
- add a persistence adapter module
- preserve current JSONL logging and rejection sidecars

Rules:

- database writes must not become the sole source of truth for output or rejection files
- if database write fails, the builder must define whether processing stops or the record is marked incomplete; do not silently drop auditability

Exit gate:

- one successful scan produces a `scan_record`, a `scan_processing_run`, and artifact rows
- one rejected scan produces the same with failure state

### Phase 4: Mirror runtime processing into durable record events

Objective:

- map stage transitions and terminal outcomes into durable audit events

Tasks:

- write audit events for claim, processing, validation, success, and failure
- store config snapshot per processing run
- store barcode candidate context per run
- preserve `processing_id` on each run

Rules:

- processing events remain append-only
- reprocessing creates a new run, not a destructive overwrite of the old run

Exit gate:

- the page read model can reconstruct a complete timeline without reading JSONL directly

### Phase 5: Add enrichment models

Objective:

- support owner-managed metadata and relationships

Tasks:

- notes
- typed links
- tags
- owner and assignee
- custom fields
- attachments

Rules:

- enrichment changes must not mutate immutable evidence tables
- every enrichment write must emit an audit event

Exit gate:

- one scan record can hold notes, links, attachments, and custom metadata with traceability

### Phase 6: Add import and export jobs

Objective:

- make scan records portable and integrable

Tasks:

- JSON record export
- CSV timeline export
- evidence ZIP export
- JSON or CSV import preview
- merge application with audit trail

Rules:

- imports must support preview before apply
- exports must record who generated them and when

Exit gate:

- import and export jobs are durable, queryable, and auditable

### Phase 7: Add a read API or equivalent service layer

Objective:

- create a stable interface for the future page

Minimum capabilities:

- fetch scan record by `scan_id`
- fetch by `processing_id`
- fetch by barcode
- fetch related scans
- add note
- add or remove link
- create import job
- create export job
- trigger reprocess

Rules:

- keep this layer thin
- do not put routing logic in the UI layer

Exit gate:

- all record-page actions can be served by stable service calls

### Phase 8: Build the scan record workbench UI

Objective:

- implement the page described in `docs/scan-record-workbench.md`

Build order inside the UI:

1. overview header and status summary
2. artifacts and timeline
3. links and notes
4. audit trail
5. imports and exports
6. diagnostics

Rules:

- do not build charts first
- do not build a dashboard first
- optimize for exact-record lookup and exception handling

Exit gate:

- the page can present one scan in full without requiring the owner to inspect raw files or logs first

## 6. Verification Strategy

Every phase should include verification, not just coding.

### 6.1 Runtime regression verification

- existing unit tests pass
- success path unchanged
- reject path unchanged
- duplicate handling unchanged
- sidecars unchanged unless intentionally versioned

### 6.2 Persistence verification

- every processed file creates the expected durable rows
- no duplicate rows for one run
- reprocess creates a new run under the same scan record
- audit events are append-only

### 6.3 Record integrity verification

- one record can show all artifacts
- immutable evidence does not change after enrichment edits
- owner edits create audit entries
- imported metadata records provenance

### 6.4 UI verification

- exact-record lookup works by `scan_id`, `processing_id`, and barcode
- mobile layout retains primary actions and record understanding
- empty states are explicit
- destructive actions are visually secondary

## 7. Suggested Definition Of Done

The builder should consider the work complete only when all of the following are true:

1. A successful scan produces a durable, queryable scan record.
2. A rejected scan produces a durable, queryable scan record.
3. The record preserves initial processing evidence and later enrichment separately.
4. Reprocessing does not destroy the original processing history.
5. Notes, links, imports, and exports are auditable.
6. The UI can render one scan with its full story from a stable service contract.
7. The current ingestion runtime still behaves deterministically.

## 8. Key Risks

### 8.1 Mixing evidence and enrichment

If evidence tables are editable, audit quality collapses.

### 8.2 Guessing actor identity

If the system invents who scanned something, the audit trail becomes misleading.

### 8.3 Treating raw logs as the page query model forever

JSONL is useful for operations, but it is the wrong long-term substrate for owner-grade record interaction.

### 8.4 Building the page before the contracts

Frontend-first work here will force unstable data shapes and rework.

## 9. Immediate Builder Artifacts Added In This Repo

This handoff is paired with:

- `docs/scan-record-workbench.md`
- `docs/contracts/scan-record.schema.json`
- `docs/examples/scan-record.example.json`
- `docs/prototypes/scan-record-workbench.html`

The builder should treat those files as the initial working package for implementation.
