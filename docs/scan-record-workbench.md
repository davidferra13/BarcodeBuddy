# Scan Record Workbench

Last updated: 2026-04-03.

## 1. Purpose

This document defines a future owner-facing page for one scan record. The page is not a dashboard. It is a single-record workbench that answers:

- who scanned it
- what was scanned
- when every stage happened
- where it came from and where it went
- how the system interpreted and handled it
- what has been changed, linked, exported, imported, or annotated since

The page must let an owner inspect one scan in full, tie it to any relevant business object, add operational context, and take controlled actions without losing the original evidence trail.

This page follows the repo's interaction philosophy:

- record-first, not metric-first
- exception-friendly, not dashboard-heavy
- search-first and identifier-first
- advanced actions disclosed intentionally
- edits are auditable

## 2. Non-Negotiable Principles

### 2.1 One canonical scan record

Every scan gets one canonical record page keyed by a durable `scan_id`.

### 2.2 Immutable evidence, editable enrichment

The system must split scan data into two layers:

- immutable evidence: source artifact, extracted facts, timestamps, config snapshot, routing result, machine diagnostics
- editable enrichment: notes, tags, links, assignments, custom fields, export packages, review outcomes

Owners can modify the record extensively, but they must not silently overwrite the historical truth of what the system originally received or decided.

### 2.3 Full traceability

Every operator action on the page creates an audit event:

- who made the change
- when it happened
- what changed
- previous value
- new value
- reason or note when required

### 2.4 Tie anything to the scan

The record must support typed links to arbitrary business entities, for example:

- PO
- receipt
- shipment
- delivery
- customer
- vendor
- SKU
- work order
- compliance batch
- lot
- ERP record
- support ticket
- quality incident
- email thread
- external file

## 3. Primary Jobs The Page Must Support

1. Determine the scan's current state in under 5 seconds.
2. Reconstruct the scan's full lifecycle without opening raw logs first.
3. Compare source evidence, barcode interpretation, and output artifact.
4. Understand relationships to business records and related scans.
5. Add notes, attachments, tags, and custom context.
6. Reprocess, relink, export, or otherwise act on the scan.
7. Import external metadata or link packages into the scan record.
8. Prove who changed what later.

## 4. Page Frame

The page should be named `Scan Record` or `Scan Workbench`.

The layout should have five major zones:

1. Identity header
2. Sticky action rail
3. Main record canvas
4. Right-side context rail
5. Lower audit and export surfaces

### 4.1 Identity header

The top of the page must show:

- scan status
- workflow
- canonical scan ID
- primary barcode or rejection reason
- scanned timestamp
- current owner or assignment
- data completeness indicator

Default primary actions in the first viewport:

- `Add note`
- `Link record`
- `Reprocess`

All other actions belong under `More actions`.

### 4.2 Sticky action rail

The sticky action rail should stay visible on desktop and collapse to a bottom sheet on mobile.

It should support:

- reprocess scan
- open original file
- open routed PDF
- export record package
- import metadata
- attach file
- add note
- link business record
- compare to related scan
- void or close review

Destructive actions must stay visually separate and lower priority:

- unlink
- delete note
- remove attachment
- archive record

## 5. Main Record Canvas

The page should default to the `Overview` view and expose secondary tabs:

- `Overview`
- `Artifacts`
- `Events`
- `Links`
- `Notes`
- `Audit`
- `Imports / Exports`
- `Diagnostics`

### 5.1 Overview

This is the default state and must answer the entire story of the scan at a glance.

Sections:

#### A. Preview and file stack

Show:

- source document preview
- routed output preview if present
- page count
- file type
- size
- checksum or content hash
- original filename
- current output path or rejected path

#### B. Who / What / When / Where / How matrix

This matrix is the core owner-facing summary.

`Who`

- captured by user
- uploaded by user
- current assignee
- last editor
- workflow owner
- device or scanner identity

`What`

- scan type
- source file name
- source format
- output format
- extracted barcode values
- selected canonical barcode
- rejection reason if failed
- page count
- duplicate relationship

`When`

- first seen
- file stabilized
- claimed
- barcode scan started
- validation completed
- output committed or rejection committed
- last modified
- last exported

`Where`

- source folder or intake channel
- branch or site
- workstation or device
- processing path
- output path
- rejected path
- downstream system links

`How`

- workflow instance
- config version
- duplicate handling policy
- scan-all-pages flag
- barcode types allowed
- barcode regex policy version
- barcode engine version
- preprocessing mode or pass summary
- manual override flags

#### C. Relationship graph

This section should show all direct ties from the scan to the rest of the business.

Each link should carry:

- type
- target identifier
- target system
- display label
- link source: manual, imported, inferred, upstream
- confidence or verification state
- created by
- created at

#### D. Notes and operational commentary

The page must support rich notes with:

- plain text or markdown
- mention users
- pin important notes
- resolve note threads
- attach files to a note
- classify note types: ops, quality, shipping, compliance, support, owner

#### E. Timeline summary

A simplified timeline should appear on the overview before the full audit tab.

Key events:

- detected
- claimed
- barcode found
- validation passed or failed
- output created or rejection created
- links added
- notes added
- exports run
- imports applied
- manual edits
- reprocess actions

### 5.2 Artifacts tab

This tab is for file-level evidence and must show every artifact tied to the scan:

- original source file
- normalized output PDF
- rejection sidecar
- OCR or extracted text if later enabled
- preview thumbnails
- attachment files
- imported manifests
- exported packages

Each artifact row must show:

- artifact type
- format
- file size
- checksum
- created at
- created by system or user
- retention class
- download action

### 5.3 Events tab

This tab is the machine and operator lifecycle, not only human notes.

It must include:

- timestamp
- actor type: system, user, integration
- actor identity
- event type
- state before
- state after
- message
- payload drill-in

Filters:

- system events
- user events
- integration events
- failures only
- exports only
- link changes only

### 5.4 Links tab

This tab manages everything the scan is tied to.

Capabilities:

- create link
- remove link
- mark one link as primary
- add relation notes
- group links by type
- show verification state
- show whether link came from import or manual action

### 5.5 Notes tab

This tab is the full collaboration surface:

- note threads
- pinned notes
- unresolved notes
- attachments
- mentions
- note visibility if roles are introduced later

### 5.6 Audit tab

This is the compliance-grade change ledger.

It must show immutable history for:

- field changes
- action executions
- import applications
- export creations
- assignment changes
- note creation and deletion
- link creation and unlink
- reprocess attempts

### 5.7 Imports / Exports tab

The owner asked for full import and export control. This tab must support both.

`Import`

- import JSON metadata
- import CSV link mappings
- import note package
- import external record references
- preview incoming changes before apply
- show per-field merge strategy

`Export`

- export record as JSON
- export scan timeline as CSV
- export evidence package as ZIP
- export original plus output plus sidecar bundle
- export audit trail
- export attachments

Every import and export must generate an event and remain reviewable later.

### 5.8 Diagnostics tab

This tab is not default-visible content, but it should exist for owner or admin use.

Show:

- barcode engine details
- raw candidate barcode list
- page-one eligible values
- orientation and format
- processing duration breakdown
- runtime config snapshot
- processing errors
- source path history
- version information

## 6. Field Inventory

The record should support the following field groups.

### 6.1 Identity

- `scan_id`
- `processing_id`
- `workflow_key`
- `current_state`
- `review_state`
- `priority`
- `canonical_barcode`

### 6.2 Capture context

- `captured_by_user_id`
- `captured_by_display_name`
- `capture_channel`
- `scanner_device_id`
- `scanner_profile`
- `branch_code`
- `site_name`
- `workstation_name`
- `source_ip`

### 6.3 Artifact facts

- `original_filename`
- `original_extension`
- `source_size_bytes`
- `source_checksum_sha256`
- `page_count`
- `source_artifact_id`
- `output_artifact_id`
- `rejection_artifact_id`

### 6.4 Routing facts

- `selected_barcode`
- `barcode_format`
- `barcode_orientation_degrees`
- `barcode_matches_business_rule`
- `raw_detection_count`
- `candidate_values`
- `eligible_candidate_values`
- `page_one_eligible_values`
- `duplicate_handling_mode`

### 6.5 Lifecycle timestamps

- `detected_at`
- `stabilized_at`
- `claimed_at`
- `processing_started_at`
- `barcode_scanned_at`
- `validation_completed_at`
- `output_committed_at`
- `rejection_committed_at`
- `last_modified_at`
- `last_exported_at`

### 6.6 Mutable business enrichment

- `tags`
- `owner_user_id`
- `assignee_user_id`
- `business_status`
- `custom_fields`
- `linked_records`
- `notes`
- `attachments`
- `tasks`

## 7. Editable Versus Immutable

The page must make this distinction visible.

`Immutable evidence`

- source file bytes
- checksums
- original timestamps from system processing
- raw barcode results captured by the engine
- config snapshot used for that run
- original success or failure result

`Editable enrichment`

- notes
- tags
- assignments
- linked records
- custom fields
- review state
- pinned indicators
- export packages
- imported metadata overlays

If an owner changes a routing conclusion later, the original result stays in history and the new decision becomes a new action record, not a replacement of history.

## 8. Actions The Page Must Permit

The owner asked to "modify or do anything" with the scan. The workbench should therefore support these actions, with auditability:

- add or edit note
- attach file
- link record
- unlink record
- assign owner
- change review state
- add tags
- import metadata
- export record package
- open source
- open output
- reprocess under current config
- reprocess under selected workflow
- compare against another scan
- mark canonical within a duplicate family
- create follow-up task
- flag for compliance review
- pin important fields

Actions that change operational meaning should require a reason:

- reprocess
- unlink primary business record
- mark canonical
- archive or void

## 9. Search and Entry Points

This page should be reachable by any meaningful identifier:

- scan ID
- processing ID
- barcode
- original filename
- PO
- shipment
- receipt
- related business record ID

Direct lookup should open this page, not a generic results dashboard first, when there is one exact match.

## 10. Data Sources Required

### 10.1 Already available in current runtime

The current repo can already supply part of this page from:

- `data/logs/processing_log.jsonl`
- `data/rejected/*.meta.json`
- output files in `data/output/YYYY/MM`
- rejected files in `data/rejected`

Current fields available today:

- `processing_id`
- `stage`
- `status`
- `duration_ms`
- `original_filename`
- `reason`
- `barcode`
- `barcode_format`
- `barcode_orientation_degrees`
- `barcode_matches_business_rule`
- `pages`
- `output_path`
- `rejected_path`

### 10.2 Missing data that must be added for the full page

The current runtime does not track the full owner context requested. To support this page completely, future persistence must add:

- durable `scan_id`
- operator identity
- device identity
- intake channel metadata
- branch or site metadata
- checksums
- config snapshot per run
- audit events for user actions
- notes and attachments
- typed business links
- import and export history
- manual override history

## 11. Suggested Future Record Model

The workbench should be backed by a normalized read model with these entities:

- `scan_record`
- `scan_artifact`
- `scan_event`
- `scan_link`
- `scan_note`
- `scan_attachment`
- `scan_import_job`
- `scan_export_job`
- `scan_field_change`

### 11.1 Minimal JSON shape

```json
{
  "scan_id": "scan_20260403_00418",
  "processing_id": "0f6b58c6-9ee8-4ef6-89c2-f0a2f6dd3f25",
  "workflow_key": "shipping_pod",
  "current_state": "routed",
  "canonical_barcode": "6013796-00",
  "capture_context": {
    "captured_by_user_id": "u_204",
    "scanner_device_id": "dock-03-fujitsu",
    "capture_channel": "network_hot_folder",
    "branch_code": "BEV"
  },
  "artifacts": [],
  "links": [],
  "notes": [],
  "events": [],
  "imports": [],
  "exports": []
}
```

## 12. UI Behavior Rules

- Show the current state and primary action before diagnostics.
- Do not show charts by default.
- Keep the first viewport useful with no scrolling.
- Allow deep detail without forcing it on the operator.
- Use plain labels instead of internal jargon where possible.
- Show explicit empty states, never blank containers.
- Preserve mobile usability for lookup, note entry, and artifact access.

## 13. Mobile Behavior

Mobile does not need the full desktop density, but it must still support:

- identifier lookup
- top-level state understanding
- preview of the source artifact
- link inspection
- notes
- reprocess
- export package

The right rail should collapse into stacked cards below the main summary on small screens.

## 14. Success Criteria

The page is correct if an owner can do all of the following without leaving the record:

1. Identify exactly what happened to the scan.
2. See all known facts about the scan.
3. See every file tied to the scan.
4. See every business record tied to the scan.
5. Add context, notes, and attachments.
6. Import or export data tied to the scan.
7. Reprocess or otherwise act on the scan.
8. Prove later who changed what and why.

## 15. Deliverable Pairing

This document is paired with:

- `docs/prototypes/scan-record-workbench.html`
- `docs/scan-record-builder-handoff.md`

The HTML file is a static layout prototype only. It illustrates the page composition and visual hierarchy, but it does not imply the current Python runtime already supports the backing data model.
