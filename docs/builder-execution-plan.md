# Builder Execution Plan

Last updated: 2026-04-03.

Version: 1.0.0

This is the dependency-aware execution order for the next builder. Follow the phases in order. Do not start a later phase until the exit criteria for the earlier phase are met.

## 0. Verified starting state

Verified now:

- config contract tests exist in `tests/test_config.py`
- runtime and artifact tests pass with `py -B -m unittest discover -s tests -v`
- end-to-end runtime contract coverage lives in `tests/test_service_runtime.py`
- code compiles with `py -m compileall app tests main.py stats.py`
- config loader now rejects unknown keys, duplicate managed paths, and cross-volume path sets
- config loader now emits normalized `workflow_key` plus deterministic `config_version`
- log and sidecar payloads now include `schema_version`, `workflow`, `host`, `instance_id`, `config_version`, and `error_code`
- supported-file detection now uses magic-byte validation before deep parse
- the worker now acquires an exclusive per-workflow startup lock
- claimed files are now tracked by a durable per-file journal under `processing/.journal`
- restart recovery is now journal-backed and emits explicit recovery log records
- the worker now emits lifecycle heartbeat events and the stats surface derives local health plus queue state from them
- the active log now rotates locally by day into `processing_log.YYYY-MM-DD.jsonl`
- the stats surface now aggregates active plus archived logs
- production blueprint exists in `docs/production-operations-blueprint.md`
- incident runbook exists in `docs/runbooks/incident-response.md`

Builder rule:

- treat the current code plus tests as the baseline
- treat `TECHNICAL_ARCHITECTURE_SPECIFICATION.md` as target-state only

## 1. Phase order

### Phase 1 is complete: Freeze current contracts and remove unsafe ambiguity

Prerequisites:

- completed in the verified starting state above

Completed deliverables:

- freeze current log field names and current rejection reason set in one code-owned constants module
- add `schema_version`, `workflow`, `host`, `instance_id`, and `config_version` to all log events
- add magic-byte validation so file type is determined from bytes before deep parsing
- define one canonical current error-code enum and map existing string reasons to it

Files to touch first:

- `app/processor.py`
- `app/documents.py`
- `app/logging_utils.py`
- tests that cover processor and stats behavior

Exit criteria now satisfied:

- log schema is stable and documented
- every terminal event includes a canonical error code or null
- unsupported or spoofed files are rejected before deep parse
- tests cover the new log fields and type validation

Verification already performed:

- `py -B -m unittest discover -s tests -v`
- drop one spoofed file and confirm rejection reason plus sidecar

Builder rule for the next pass:

- treat the Phase 1 log schema and canonical error-code enum as the fixed baseline unless a deliberate versioned contract change is part of the work

### Phase 2 is complete: Add process safety and durable recovery

Prerequisites:

- Phase 1 complete and preserved

Completed deliverables:

- enforce singleton startup so one workflow cannot run twice against the same folders
- add a durable job journal in `processing`
- convert crash recovery from "move everything back to input" to journal-backed reconciliation
- make output commit and source cleanup recoverable through the journal plus recovery records

Deferred intentionally:

- bounded retry behavior is still not implemented because retry policy should land with Phase 3 observability and explicit operator semantics, not as a hidden runtime behavior change

Files to touch first:

- `main.py`
- `app/processor.py`
- `app/runtime_lock.py`
- new tests around crash recovery and locking

Exit criteria now satisfied:

- second instance fails fast at startup
- restart recovery is deterministic and journal-backed
- no claimed file can disappear without either a success artifact, a rejected artifact, or a recovery record

Verification already performed:

- unit tests for singleton startup locking and journal-backed recovery
- recovery-path simulations in `tests/test_service_runtime.py`

### Phase 3 is in progress — repo-owned slice is complete for v1.0: Lift observability to production-grade

Prerequisites:

- Phase 2 complete

Completed for v1.0:

- emit `startup`, `heartbeat`, and `shutdown` lifecycle events from the worker
- expose local service health, queue backlog, journal count, and latency percentiles in `stats.py`
- make `/health` reflect heartbeat freshness and lock presence instead of always returning `ok`
- classify recovery-finalized output and rejection events correctly in the stats surface
- rotate the active log locally by day without changing the runtime log path
- make `stats.py` read both the active log and local daily archives

Post-v1.0 work (requires deployment infrastructure):

- emit metrics for backlog, age, latency, success rate, rejection reasons, restarts, and log write failures
- ship local logs and archives off-host with retention enforcement
- wire the alert thresholds from `docs/production-operations-blueprint.md`
- define and implement any bounded retry policy only after those metrics and alerts exist

### Phase 4: Lock down platform and security controls

Prerequisites:

- Phase 3 complete or monitoring equivalent is in place

Tasks:

- baseline and document folder ACLs
- make `input` write-only for upstream writers
- keep `processing`, `output`, `rejected`, and `logs` service-owned
- generate SBOM and dependency audit for `Pillow`, `PyMuPDF`, and `zxing-cpp`
- define patch SLA and release gating for parser dependencies

Files and artifacts:

- deployment docs
- security audit records
- build or CI configuration

Exit criteria:

- ACL matrix is documented and applied
- dependency audit exists for the current release
- patch and upgrade path is explicit

Verification:

- ACL audit
- dependency scan report

### Phase 5: Close the documentation and release gates

Prerequisites:

- earlier phases complete

Tasks:

- block release if docs reference missing files
- block release if tests fail or zero tests run
- block release if example configs fail schema or loader checks
- block release if log samples drift from the published schema
- keep `README.md`, `docs/current-system-truth.md`, `docs/danpack-builder-handoff.md`, and the production blueprint in the same PR as behavior changes

Exit criteria:

- builder docs, runtime docs, and executable tests agree
- release artifacts include schema version, config checksum, SBOM, and runbook version

Verification:

- CI passes all gates
- spot-check docs against runtime commands and files

## 2. Work that is already done in this repo

Completed in the current pass:

- config loader rejects unsupported keys
- config loader rejects duplicate managed paths
- config loader rejects cross-volume managed path sets
- config loader normalizes and validates `workflow_key`
- config loader derives deterministic `config_version`
- config contract tests were added
- current runtime contracts were frozen in `app/contracts.py`
- log events and rejection sidecars now carry runtime metadata and a canonical error code
- supported-file detection now uses magic-byte validation instead of suffix-only trust
- the worker now enforces a per-workflow startup lock in `main.py`
- claimed files are now tracked by a durable journal and recovered deterministically from `processing/.journal`
- production operations blueprint was added
- incident runbook was added
- top-level builder docs were refreshed to point at the current runtime anchors

## 3. Work that should not happen early

Do not do these before Phases 1 through 3:

- widening the system into OCR or document classification
- building an operator workflow UI
- exposing the stats surface beyond localhost without an auth boundary
- refactoring the runtime into many modules without test coverage for the current behavior
- adding workflow-specific regexes without real Danpack samples

## 4. Operator commands to keep using

Runtime:

```text
py main.py
py stats.py
```

Verification:

```text
py -B -m unittest discover -s tests -v
py -m compileall app tests main.py stats.py
```
