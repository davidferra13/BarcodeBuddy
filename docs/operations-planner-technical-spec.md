# Operations Planner Technical Spec

Last updated: 2026-04-03.

## 1. Purpose

This document turns the planner product requirements into a builder-ready technical design.

The design assumes:

- the current BarcodeBuddy ingestion runtime remains authoritative for deterministic scan processing
- the future single-scan workbench remains the canonical detailed record page
- the planner is a higher-level control plane for reporting, obligations, forecasting, and workload monitoring

## 2. Current Baseline And Gap

Current repo truth:

- one ingestion runtime writes append-only JSONL processing logs
- one read-only stats surface aggregates the log file
- no durable database exists yet
- no issue queue for expected scans exists yet
- no immutable report snapshots exist yet
- no forecast engine exists yet

Immediate implication:

The planner cannot be implemented cleanly on top of raw JSONL reads alone.

It needs a durable local state store and a canonical event model.

## 3. Architectural Position

The planner should be implemented as a local-first control plane with five layers:

1. ingestion evidence layer
2. normalization and state projection layer
3. obligation and planning layer
4. report generation layer
5. read-only planner UI and API layer

## 4. Recommended Runtime Components

### 4.1 Ingestion runtime

Existing component.

Responsibilities:

- claim files
- process and validate documents
- write outputs or rejections
- emit append-only processing events

### 4.2 Event normalizer

New component.

Responsibilities:

- ingest processing log events and rejection sidecars
- normalize them into durable relational records
- de-duplicate replays safely
- create canonical activity events

### 4.3 State store

New component.

Recommended storage:

- `data/state/barcodebuddy.sqlite3`

Responsibilities:

- store scan records
- store scan processing runs
- store activity events
- store scan obligations
- store report definitions
- store report snapshots
- store forecast inputs and outputs where needed

### 4.4 Report scheduler and generator

New component.

Responsibilities:

- evaluate schedules by local site timezone
- generate immutable report snapshots
- render machine-readable and human-readable outputs
- support manual reruns without mutating prior snapshots

### 4.5 Planner API and UI

New component.

Responsibilities:

- list reports
- open report snapshots
- list activity events
- manage obligations
- expose live planner summaries
- link to scan workbench pages

## 5. Proposed Durable Entities

The planner should introduce or reuse the following durable entities.

### 5.1 `scan_records`

Canonical per-document record.

Prefer reusing the future model from `docs/scan-record-builder-handoff.md`.

### 5.2 `scan_processing_runs`

One row per deterministic processing attempt.

Must preserve the current `processing_id`.

### 5.3 `activity_events`

Append-only operational ledger.

Minimum columns:

- `event_id`
- `event_type`
- `entity_type`
- `entity_id`
- `workflow_key`
- `site_code`
- `occurred_at`
- `actor_type`
- `actor_id`
- `previous_state`
- `new_state`
- `payload_json`
- `source_ref`

### 5.4 `scan_obligations`

Represents things that should be scanned by a defined due window.

Minimum columns:

- `obligation_id`
- `workflow_key`
- `site_code`
- `status`
- `priority`
- `obligation_type`
- `source_system`
- `source_ref`
- `title`
- `expected_scan_count`
- `observed_scan_count`
- `due_start_at`
- `due_end_at`
- `assigned_to`
- `created_at`
- `updated_at`
- `closed_at`

### 5.5 `scan_obligation_matches`

Join table between obligations and scan records.

Minimum columns:

- `obligation_id`
- `scan_id`
- `match_type`
- `matched_at`
- `matched_by`

### 5.6 `report_definitions`

Saved report configurations.

Minimum columns:

- `report_definition_id`
- `report_key`
- `schedule_type`
- `timezone`
- `site_scope`
- `workflow_scope`
- `filters_json`
- `active`
- `created_at`
- `updated_at`

### 5.7 `report_snapshots`

Immutable generated report instances.

Minimum columns:

- `report_snapshot_id`
- `report_definition_id`
- `report_key`
- `report_kind`
- `status`
- `version`
- `generated_at`
- `window_start_at`
- `window_end_at`
- `timezone`
- `payload_json`
- `rendered_html_path`
- `rendered_pdf_path`

## 6. Canonical Activity Event Model

Every important planner action should emit an `activity_event`.

Recommended event families:

- `scan.discovered`
- `scan.claimed`
- `scan.processing_started`
- `scan.processing_succeeded`
- `scan.processing_failed`
- `scan.reprocessed`
- `scan.linked`
- `scan.assigned`
- `scan.review_state_changed`
- `obligation.created`
- `obligation.imported`
- `obligation.assigned`
- `obligation.status_changed`
- `obligation.matched`
- `obligation.waived`
- `obligation.closed`
- `report.generated`
- `report.failed`
- `report.exported`
- `forecast.generated`

State markers shown in UI should be derived from this append-only ledger, not handwritten mutable fields alone.

## 7. Scheduler Model

The planner must support both scheduled and on-demand generation.

### 7.1 Schedule semantics

Recommended default schedule keys:

- `hourly`
- `morning`
- `day`
- `night`
- `yesterday`
- `tomorrow`
- `quarterly`

### 7.2 Timezone rules

- Every site must have an explicit IANA timezone.
- Report windows must be computed in the site timezone.
- Stored timestamps should remain ISO-8601 with offset or UTC conversion, but each snapshot must preserve the reporting timezone used.

### 7.3 Default execution times

Recommended defaults:

- `hourly`: every hour at minute `05`
- `morning`: `06:05`
- `day`: `12:05`
- `night`: `18:05`
- `yesterday`: `00:10`
- `tomorrow`: `18:10`
- `quarterly`: first day after quarter close at `01:00`

These times must be configurable.

### 7.4 Window definitions

- `hourly`: previous fully closed hour
- `morning`: current morning shift plan plus unresolved carryover from the prior night
- `day`: current day shift plan plus unresolved carryover from the prior morning
- `night`: current night shift plan plus unresolved carryover from the prior day
- `yesterday`: previous calendar day actuals only
- `tomorrow`: next calendar day forecast, backlog carryover, and due obligations
- `quarterly`: quarter-to-date or closed-quarter actuals with optional forecast appendix

## 8. Actual Versus Projection Logic

The planner must enforce strict classification of metrics.

### 8.1 `actual`

Derived from completed or currently recorded facts:

- scan counts
- success counts
- rejection counts
- aging
- backlog
- obligation closures

### 8.2 `projection`

Derived from future-looking estimation:

- tomorrow expected volume
- expected missing scans
- staffing pressure
- quarter-end completion projection

### 8.3 `hybrid`

Combines both, but fields must still carry explicit type labels.

Example:

- actual current backlog
- projected carryover to tomorrow morning

## 9. Report Generation Pipeline

Each report run should follow this sequence:

1. resolve report definition and schedule
2. compute effective scope and time window
3. materialize source scan, obligation, and activity query sets
4. compute actual metrics
5. compute projections if the report type requires them
6. assemble immutable payload JSON
7. write report snapshot row
8. render HTML and optional PDF
9. emit `report.generated` or `report.failed` activity event

If rendering fails after payload creation, the snapshot should remain with a partial status rather than disappearing.

## 10. Suggested API Surface

Recommended local API endpoints:

- `GET /api/planner/overview`
- `GET /api/reports`
- `GET /api/reports/{report_snapshot_id}`
- `POST /api/reports/run`
- `GET /api/obligations`
- `POST /api/obligations`
- `POST /api/obligations/import`
- `POST /api/obligations/{obligation_id}/assign`
- `POST /api/obligations/{obligation_id}/status`
- `GET /api/activity`
- `GET /api/scans`
- `GET /api/scans/{scan_id}`
- `GET /api/health`

The existing `stats.py` surface can remain as a lightweight local page, but it should not be treated as the planner API.

## 11. UI Behavior Requirements

### 11.1 Planner overview

Must answer in one view:

- what is late
- what is failing
- what changed in the last hour
- what must be scanned next
- what tomorrow looks like

### 11.2 Report viewer

Must show:

- snapshot header
- report window
- actual versus projected labels
- expandable exception groups
- direct links to source scans and obligations

### 11.3 Obligation queue

Must support:

- filter by workflow, site, priority, and due status
- bulk assignment
- waiver with reason
- direct navigation to matched or missing scans

### 11.4 Activity ledger

Must support:

- append-only timeline view
- filters by entity type and event family
- exact payload inspection

## 12. Retention And Versioning

Recommended default retention:

- activity events: retain indefinitely unless compliance policy overrides
- report snapshots: retain at least `8` closed quarters
- rendered report files: retain in sync with snapshot retention
- projections: retain with the report snapshot that generated them

Versioning rules:

- report reruns must create a new snapshot version
- obligation edits must create events, not silent rewrites
- scan evidence must stay immutable

## 13. Failure Handling

The planner must not silently lose operational truth.

Required behaviors:

- if event normalization fails, keep the raw source reference and record the failure
- if report generation fails, write a failed report run record plus activity event
- if a forecast input source is missing, label the projection partial or unavailable
- if an obligation import partially fails, preserve import job results and failures per item

## 14. Security And Exposure Rules

- planner should bind to loopback by default unless an authenticated deployment boundary exists
- report exports must be auditable
- only authorized users should be allowed to create, assign, waive, or close obligations
- immutable report snapshots must not be editable from the UI

## 15. Relationship To Existing Work

This planner is downstream of:

- current ingestion runtime truth in `main.py`, `stats.py`, and `app/`
- future scan record persistence in `docs/scan-record-builder-handoff.md`

Recommended dependency rule:

Do not start planner UI work until durable record persistence and canonical activity events exist.
