# Operations Planner Builder Handoff

Last updated: 2026-04-03.

## 1. Purpose

This document is the builder-facing handoff for the future BarcodeBuddy planner, reporting system, obligation queue, and activity ledger.

Use it when implementing:

- scheduled hourly, shift, yesterday, tomorrow, and quarterly reports
- expected-scan tracking
- missing-scan and overdue-scan workflows
- multi-record operational visibility
- report snapshots and forecast views

Read this together with:

1. `README.md`
2. `docs/current-system-truth.md`
3. `docs/danpack-builder-handoff.md`
4. `docs/scan-record-builder-handoff.md`
5. `docs/operations-planner-product-spec.md`
6. `docs/operations-planner-technical-spec.md`
7. `docs/operations-planner-execution-plan.md`
8. `docs/danpack-system-interaction-philosophy.md`
9. `tests/`

## 2. Current Runtime Truth Relevant To The Planner

### 2.1 What exists today

- one deterministic ingestion runtime
- one append-only JSONL processing log
- rejection sidecars with failure context
- workflow-aware config and runtime metadata in log events
- one read-only local stats surface over the log file
- documented future single-scan record design and handoff

### 2.2 What does not exist today

- durable scan record database
- append-only multi-entity activity ledger
- scan obligation model for expected or missing scans
- immutable report snapshot store
- report scheduler beyond the lightweight stats page
- forecasting engine
- planner UI or planner API

### 2.3 Immediate implication

Do not build the planner directly on top of ad hoc log-file parsing plus frontend state.

The correct sequence is:

1. stabilize runtime event truth
2. persist normalized operational state
3. introduce obligations
4. generate immutable reports
5. build planner surfaces on top of those contracts

## 3. Non-Negotiable Decisions

These are the recommended defaults unless the builder finds concrete evidence to change them.

### 3.1 Keep ingestion authoritative

The ingestion runtime remains the source of truth for:

- scan discovery
- file movement
- barcode interpretation
- routing outcome
- rejection reasons
- processing timestamps

The planner must consume and project this truth, not replace it.

### 3.2 Use local SQLite before widening architecture

The planner should use a local SQLite database in `data/state`.

Why:

- the repo is local-first and single-node today
- obligations, report snapshots, and activity events need relational querying
- it introduces minimal operational risk compared with a new external service

### 3.3 Separate actuals from projections

The planner must never blur actual completed work with projected work.

Required report classifications:

- `actual`
- `projection`
- `hybrid`

Projection fields must always stay labeled as projection.

### 3.4 Treat expected scans as first-class obligations

Items that "need to get scanned" should not be loose notes.

They should be modeled as durable obligations with:

- due windows
- source references
- assignment
- status
- matching to zero, one, or many scans

### 3.5 Keep report runs immutable

Every report generation should create a new snapshot.

Do not mutate or overwrite old report outputs.

## 4. Default Scope Decisions Taken For The Owner

These are the current chosen defaults.

### 4.1 Report types

Required now:

- `hourly`
- `morning`
- `day`
- `night`
- `yesterday`
- `tomorrow`
- `quarterly`
- `custom`

### 4.2 Default schedule windows

Per site-local time:

- `hourly`: every hour at `HH:05` for the previous closed hour
- `morning`: `06:05`
- `day`: `12:05`
- `night`: `18:05`
- `yesterday`: `00:10`
- `tomorrow`: `18:10`
- `quarterly`: `01:00` on the first day after quarter close

Default shift windows unless site overrides exist:

- `morning`: `06:00` to `11:59`
- `day`: `12:00` to `17:59`
- `night`: `18:00` to `05:59` next day

### 4.3 Core planner entities

- `scan_records`
- `scan_processing_runs`
- `activity_events`
- `scan_obligations`
- `scan_obligation_matches`
- `report_definitions`
- `report_snapshots`

### 4.4 Required planner surfaces

- planner overview
- report library
- obligation queue
- activity ledger
- scan history

## 5. Builder-Critical Contracts

The builder should treat these artifacts as the planner contract anchors:

- `docs/operations-planner-product-spec.md`
- `docs/operations-planner-technical-spec.md`
- `docs/operations-planner-execution-plan.md`
- `docs/contracts/report-snapshot.schema.json`
- `docs/contracts/scan-obligation.schema.json`
- `docs/examples/report-snapshot.example.json`
- `docs/examples/scan-obligation.example.json`

## 6. Recommended Build Order

### Phase 1: Freeze event truth

- version the runtime event schema
- finalize canonical event families
- keep tests green

### Phase 2: Add durable state

- introduce `data/state`
- normalize processing logs into durable records
- make replays idempotent

### Phase 3: Add obligations

- create expected-scan records
- add assignment, aging, and matching
- support overdue and waived states

### Phase 4: Add report engine

- generate immutable snapshots
- render JSON and HTML
- separate actual and projection fields

### Phase 5: Add planner API and UI

- expose report viewing
- expose obligation management
- expose activity ledger and scan history

## 7. Verification Baseline

Before changing runtime behavior:

- `py -B -m unittest discover -s tests -v`
- `py -m compileall app tests main.py stats.py`

Before calling planner foundations ready:

1. normalized rows must reconcile to raw log evidence
2. obligation state changes must emit append-only activity events
3. report reruns must create new snapshot versions
4. tomorrow reports must remain forecast-labeled
5. quarterly snapshots must remain reproducible later

## 8. Remaining Unknowns The Builder Must Not Invent

- actual upstream systems that create expected-scan obligations
- real Danpack barcode formats by workflow
- final site-specific shift boundaries if they differ from defaults
- any per-site staffing or forecasting heuristics

Until those are known, keep the chosen defaults and preserve truthfulness markers instead of guessing.
