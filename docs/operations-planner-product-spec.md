# Operations Planner Product Spec

Last updated: 2026-04-03.

## 1. Purpose

This document defines the future multi-record planning, reporting, and workload-control layer for BarcodeBuddy.

It complements the future single-record workbench in `docs/scan-record-workbench.md`.

The workbench answers:

- what happened to one scan

The planner answers:

- what is happening across all scans right now
- what was completed by hour, shift, day, and quarter
- what still needs to be scanned
- what is late, blocked, or risky
- what tomorrow and the next quarter are likely to look like

## 2. Problem Statement

The current repo can ingest files, route them by barcode, reject failures, and show a local 24-hour stats page.

That is not enough for operating a real scan-dependent workflow.

Operations owners need a truthful control plane that can:

- evaluate activity every hour
- evaluate every shift, including morning, day, and night
- close out yesterday
- project tomorrow
- summarize quarter-to-date and quarter-over-quarter performance
- issue and track items that still need to be scanned
- preserve a complete history of everything ever scanned
- show exactly what was done, by whom, when, and why

## 3. Product Goals

1. Provide one authoritative planner and report viewer for all workflow activity.
2. Preserve a complete, queryable, append-only activity trail for every scan-relevant event.
3. Track expected scans, overdue scans, and missing scans as first-class operational obligations.
4. Separate factual reporting from forecasted reporting so projected numbers are never mistaken for actuals.
5. Make every report viewable on demand and reproducible later from stored report snapshots.

## 4. Non-Goals

This planner does not change the core BarcodeBuddy promise.

Out of scope unless explicitly approved later:

- OCR-driven document inference
- guessing barcode values or operator identity
- replacing the existing deterministic ingestion path
- replacing the future single-scan workbench
- cloud-first rearchitecture as a prerequisite

## 5. Core Product Objects

The planner depends on five first-class objects:

### 5.1 Scan record

One canonical record per scanned document, with immutable evidence plus editable enrichment.

### 5.2 Activity event

One append-only event for every meaningful system or user action tied to a scan, obligation, report, or planning decision.

### 5.3 Scan obligation

A planned or expected scan that should exist by a certain time window.

Examples:

- a POD expected for a completed delivery
- a receiving slip expected for a vendor shipment
- a compliance document expected for a lot or batch

### 5.4 Report definition

A saved configuration describing:

- report type
- schedule
- time window
- workflow or site scope
- filters
- recipients or viewers

### 5.5 Report snapshot

An immutable generated output for one report run, including inputs, metrics, exceptions, and projection metadata where applicable.

## 6. User Roles

### 6.1 Operations owner

Needs hourly and shift visibility, overdue scan detection, backlog control, and handoff-ready summaries.

### 6.2 Department lead

Needs workflow-specific reports for receiving, shipping/POD, and quality/compliance.

### 6.3 Reviewer or coordinator

Needs to issue missing-scan tasks, assign follow-up, and close obligations when evidence is complete.

### 6.4 Executive or branch manager

Needs quarter-level rollups, service-level performance, and forecast views without raw log digging.

## 7. Report Catalog

The planner must support the following default report set.

| Report key | Default trigger | Window type | Classification | Primary purpose |
| --- | --- | --- | --- | --- |
| `hourly` | every hour at `HH:05` | previous closed hour | actual | monitor throughput, failures, backlog change, and missing-scan growth |
| `morning` | shift start | current morning shift plus carryover from prior night | hybrid | morning handoff, overnight exceptions, due-this-shift obligations |
| `day` | shift start | current day shift plus carryover | hybrid | daytime throughput, aging, and open work coordination |
| `night` | shift start | current night shift plus carryover | hybrid | end-of-day risk, overnight intake readiness, unresolved exceptions |
| `yesterday` | daily close + `00:10` | previous calendar day | actual | locked daily record for audits, management review, and comparisons |
| `tomorrow` | daily planning run | next calendar day | projection | expected workload, scan demand, staffing pressure, and risk forecast |
| `quarterly` | quarter close + on demand | current or closed fiscal quarter | actual with optional forecast section | operating review, trend analysis, and quarter-over-quarter comparison |
| `custom` | manual only | arbitrary | actual or projection | ad hoc owner-selected windows and filters |

The shift boundaries for `morning`, `day`, and `night` must be site-configurable.

Default assumption if no site override exists:

- `morning`: `06:00` to `11:59`
- `day`: `12:00` to `17:59`
- `night`: `18:00` to `05:59` next day

## 8. Mandatory Report Sections

Every report does not need the same density, but the planner must be able to render these sections consistently:

1. Header
2. Time window and timezone
3. Workflow and site scope
4. Actual scan counts
5. Success, rejection, and incomplete counts
6. Backlog and aging summary
7. Missing or overdue scan obligations
8. Top exceptions and failure reasons
9. Activity markers and state-change counts
10. Links to the underlying scan records
11. Forecast section when the report includes projections
12. Generation metadata, including `generated_at`, generator version, and source snapshot references

## 9. Core Planner Screens

The future planner should expose five top-level surfaces:

### 9.1 Live overview

Shows:

- current workload by workflow
- backlog
- oldest open obligation
- current-hour throughput
- current-hour failure rate
- recent exceptions

### 9.2 Report library

Shows:

- all saved report definitions
- all generated report snapshots
- filters by type, workflow, site, date, and status
- ability to open any report on demand

### 9.3 Obligation queue

Shows:

- everything expected to be scanned
- due soon, overdue, matched, partially matched, waived, and closed states
- assignee and priority
- links to source references and resulting scans

### 9.4 Activity ledger

Shows:

- every append-only activity event
- filters by scan, report, obligation, actor, workflow, status, and date
- full event details and evidence links

### 9.5 Scan history

Shows:

- complete history of anything ever scanned
- state progression
- related obligations
- report inclusion history
- links to the single-scan workbench

## 10. Functional Requirements

### 10.1 Reporting

- The system must generate scheduled hourly, shift, daily, tomorrow, and quarterly reports.
- The system must let an authorized user generate any report type on demand.
- Each generated report must be stored as an immutable snapshot.
- Each report snapshot must store the exact time window, timezone, filters, and generator version used.
- Reports must distinguish `actual`, `projection`, and `hybrid` sections explicitly.
- Reports must include drill-down links to the scan records and obligations that produced the totals.

### 10.2 Activity tracking

- Every scan-relevant state change must emit an append-only activity event.
- Every obligation change must emit an append-only activity event.
- Every report generation, report publication, and report export must emit an append-only activity event.
- Events must preserve actor, timestamp, entity type, entity ID, action, previous state where applicable, and new state where applicable.
- The system must not overwrite or delete historical activity events.

### 10.3 Obligation management

- The system must support manual creation of scan obligations.
- The system must support imported scan obligations from upstream business systems.
- An obligation must track due window, expected scan count, workflow, priority, assignment, and closure reason.
- An obligation must be able to match zero, one, or many scans.
- The system must support `open`, `due_soon`, `overdue`, `matched`, `partially_matched`, `waived`, and `closed` obligation states.

### 10.4 Scan history and traceability

- The system must preserve full history for every scan ever processed.
- The system must expose all processing runs, artifacts, notes, links, and audit events for a scan.
- The planner must expose report inclusion history so an operator can see where a scan affected operational summaries.
- The planner must preserve rejected and incomplete records, not just successful outputs.

### 10.5 Forecasting and planning

- The `tomorrow` report must be forecast-driven, not a relabeled actuals report.
- Forecast inputs may include open obligations, due dates, workflow patterns, prior throughput, and carryover backlog.
- Forecast outputs must clearly label confidence and assumption source.
- Quarterly reporting may include forward-looking risk and capacity sections, but those sections must be labeled projection-only.

## 11. Truthfulness Rules

These are non-negotiable.

- The system must never present projections as if they were actual completed scans.
- Unknown actor identity must stay `unknown` until a truthful source exists.
- Missing expected scans must stay missing; the system must not auto-close obligations without evidence.
- If a report uses partial data, it must show `partial` state and the reason.
- If a report is regenerated, the system must keep the old snapshot and create a new versioned snapshot.

## 12. Success Measures

The future implementation should be considered successful when:

1. an operations owner can identify overdue or missing scans in under 60 seconds
2. an owner can open any hourly, shift, daily, tomorrow, or quarterly report in under 5 seconds
3. every report total can be traced back to underlying scan records or obligations
4. yesterday and quarterly reports are immutable once closed unless a versioned rerun is explicitly created
5. every scan, obligation, and report action is auditable end to end

## 13. Relationship To Existing Repo Artifacts

Use this document together with:

- `README.md`
- `docs/current-system-truth.md`
- `docs/danpack-builder-handoff.md`
- `docs/production-operations-blueprint.md`
- `docs/scan-record-workbench.md`
- `docs/scan-record-builder-handoff.md`

This document is future-state design guidance. It does not claim that the current runtime already implements these capabilities.
