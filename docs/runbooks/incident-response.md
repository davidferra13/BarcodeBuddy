# Incident Response Runbook

Last updated: 2026-04-03.

Use this runbook for BarcodeBuddy production incidents. Pair it with `docs/production-operations-blueprint.md`.

## 1. Severity mapping

Sev1:

- service heartbeat missing for more than 60 seconds
- repeated unexpected runtime faults
- backlog age greater than 900 seconds
- disk free space below 10 percent
- log write failure
- suspected malicious or crafted input file
- ACL or unauthorized-access failure on a managed folder

Sev2:

- backlog age greater than 300 seconds
- backlog count greater than 20 for 10 minutes
- failure rate above 5 percent over 15 minutes with at least 50 documents
- repeated `FILE_LOCKED` events
- any unexpected recovery event on startup
- disk free space below 15 percent

Sev3:

- duplicate spike
- invalid barcode or business-rule mismatch spike
- documentation drift
- one-off data quality issue with no service outage

## 2. Response sequence

### Step 1: Acknowledge and open the incident

Owner:

- Operations or SRE on-call

Actions:

- acknowledge the page within 5 minutes
- create the incident channel and incident record
- capture workflow, host, environment, and first alert timestamp

### Step 2: Contain upstream risk

Owner:

- Operations on-call with Platform support

Actions:

- if the workflow is unsafe, pause scanner writes to the affected `input` path
- if a malicious file is suspected, quarantine the file and stop requeue actions
- do not delete files from `processing`, `rejected`, or `logs`

### Step 3: Preserve evidence

Owner:

- Operations on-call

Collect:

- the active `config.json`
- config checksum or deployment version
- latest `processing_log.jsonl`
- any relevant `processing_log.YYYY-MM-DD.jsonl` archives for the incident window
- host restart history
- disk usage for the managed volume
- ACL snapshot for all managed directories
- hashes of suspicious source files if security is involved

### Step 4: Diagnose by discipline

App Owner:

- inspect failure reasons, recent code or config changes, and parser exceptions
- confirm whether failures are business rejects or system failures

Platform Owner:

- inspect service-wrapper state, filesystem health, share access, disk, and host-level restarts

Security Owner:

- inspect suspicious file indicators, dependency CVEs, unauthorized access, or ACL drift

### Step 5: Mitigate with the smallest safe action

Allowed actions in preferred order:

1. rollback the config
2. restore ACLs
3. free disk space
4. restart the affected workflow instance
5. quarantine a bad document batch
6. apply a temporary scanner redirect if intake must stay open

Prohibited before diagnosis:

- blind bulk requeue from `rejected`
- deleting `processing` artifacts
- changing multiple variables at once without recording them

### Step 6: Recover the workflow

Owner:

- Operations with App Owner sign-off

Actions:

- resume scanner writes only after mitigation is in place
- requeue only files confirmed safe to replay
- verify that backlog drains
- verify that output and rejection counts balance against intake for the incident window

### Step 7: Communicate

Cadence:

- Sev1 updates every 30 minutes
- Sev2 updates every 60 minutes

Recipients:

- App Owner
- Platform Owner
- Security Owner when applicable
- Workflow Owner
- Operations Manager for Sev1

### Step 8: Close and learn

Owner:

- Incident Commander with App Owner

Requirements:

- Sev1 and Sev2 postmortem due within 2 business days
- Sev3 recurring issue review due within 5 business days

## 3. Escalation path

Sev1:

- page Operations on-call, App Owner, and Platform Owner immediately
- page Security within 15 minutes if there is any auth, parser, or malicious-file concern
- notify Workflow Owner and Operations Manager within 30 minutes

Sev2:

- page App Owner and Platform Owner within 30 minutes
- add Security if the cause touches access, credentials, suspicious files, or dependency risk

Sev3:

- create a same-day ticket for the App Owner
- copy Workflow Owner if operations are affected

## 4. Recovery verification checklist

Before closure, confirm all of the following:

- service heartbeat is healthy
- backlog age returned below threshold
- failure rate returned to baseline
- log writes are healthy
- no unexpected files remain stranded in `processing`
- `output` and `rejected` counts reconcile for the incident window
- any quarantined files are accounted for

## 5. Postmortem minimum content

- incident summary and impact window
- affected workflows, hosts, and document counts
- exact timeline of detection, mitigation, and recovery
- root cause and contributing factors
- what signal should have detected it sooner
- corrective action with owner and due date
- preventative control with owner and due date
