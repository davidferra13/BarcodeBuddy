# Operations Planner Execution Plan

Last updated: 2026-04-03.

This is the dependency-aware implementation plan for the future planner, obligation queue, and reporting control plane.

It assumes the current repo remains the baseline runtime truth.

## 0. Starting Rule

Do not treat this plan as proof that the planner already exists.

Build in this order:

1. stabilize event truth
2. add durable state
3. add obligations
4. add report generation
5. add planner surfaces

## 1. Phase 1: Freeze Event Truth

Objective:

- make current runtime events safe to build on

Tasks:

- freeze one canonical event schema for processing and failure records
- add schema version, workflow identity, host identity, and config version to emitted events
- define canonical event families that the planner will normalize into `activity_events`
- document exact current error codes and state transitions

Exit criteria:

- log shape is versioned
- stats and future planner work can rely on stable event fields
- event schema is documented and tested

## 2. Phase 2: Add Durable State Store

Objective:

- move from JSONL-only aggregation to queryable operational state

Tasks:

- add `data/state`
- introduce SQLite schema for scan records, scan processing runs, and activity events
- build idempotent event normalization from existing JSONL logs
- store source references so every normalized row can be traced back to raw evidence

Exit criteria:

- planner queries no longer depend on full-log rescans only
- replaying normalization does not duplicate state
- every normalized row can be traced to raw evidence

## 3. Phase 3: Add Scan Obligations

Objective:

- represent things that should be scanned even before evidence exists

Tasks:

- add `scan_obligations`
- add import path for expected-scan feeds
- add manual obligation creation and assignment
- implement obligation matching to scan records
- implement overdue, partial, waived, and closed state transitions

Exit criteria:

- operators can create and track missing-scan work
- obligations can be linked to one or more scan records
- overdue logic is timezone-aware and tested

## 4. Phase 4: Build Report Engine

Objective:

- generate immutable snapshots for all required report types

Tasks:

- add `report_definitions` and `report_snapshots`
- implement schedule evaluator for hourly, shift, yesterday, tomorrow, and quarterly reports
- compute actual metrics from scans and obligations
- compute projections for tomorrow and quarter-forward sections
- render JSON plus HTML outputs

Exit criteria:

- all required report types generate snapshots
- reruns create new versions
- actual and projected fields remain clearly separated

## 5. Phase 5: Build Planner UI And API

Objective:

- expose the planner as a usable operational surface

Tasks:

- add overview, report library, obligation queue, activity ledger, and scan history views
- add local API endpoints for reports, obligations, and activity
- link every report exception back to scan records or obligations
- add export actions with audit events

Exit criteria:

- operations owner can detect missing scans quickly
- reports are viewable on demand
- drill-down to underlying scans works

## 6. Phase 6: Productionize

Objective:

- make the planner safe for real operations

Tasks:

- add authentication and authorization boundary if exposed beyond localhost
- add backup and retention policy for `data/state` and rendered reports
- add observability for normalization lag, report generation lag, obligation backlog, and planner errors
- add recovery tooling for failed imports and failed report runs

Exit criteria:

- planner data is backed up
- planner alerts exist
- recovery procedures are documented

## 7. Work That Must Not Happen Early

Do not do these before Phases 1 through 4 are complete:

- build the final planner UI directly on raw JSONL files
- add quarter forecasting without obligation modeling
- allow mutable edits to report snapshots
- let projections silently replace actual metrics

## 8. Verification Checklist

Before calling the planner implementation production-ready, verify:

1. hourly report totals reconcile to underlying scan and obligation rows
2. yesterday report is immutable and versioned on rerun
3. tomorrow report is clearly marked as forecast
4. quarterly report can show closed-quarter actuals without live-data drift
5. overdue obligations can be traced to why a scan is missing
6. every report run, export, assignment, waiver, and closure emits an activity event
