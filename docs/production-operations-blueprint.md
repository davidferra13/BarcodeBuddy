# Production Operations Blueprint

Last updated: 2026-04-05.

This document is the concrete production-operating blueprint for the current BarcodeBuddy repository. It is written against the code that exists today (v3.0.0), with explicit notes where production controls are still required.

## 0. System Boundary

Current runtime shape:

- one polling worker process from `main.py` (document ingestion — hot-folder watcher, barcode scanner, PDF output)
- one multi-user web application from `stats.py` (FastAPI + Uvicorn) serving:
  - JWT cookie-based authentication with bcrypt password hashing and RBAC (owner, admin, manager, user)
  - full inventory management with CRUD, barcode generation, scan lookup, bulk import/export
  - stock alerts with webhook dispatch, analytics dashboards, calendar views
  - team management with roles and task tracking
  - AI chatbot integration (Ollama local, Anthropic, OpenAI cloud providers)
  - scan-to-PDF report generation
  - unified activity log and admin audit trail
  - processing dashboard with health, queue, and latency metrics
- SQLite database in WAL mode (`data/logs/barcodebuddy.db`) for all persistent application state
- filesystem-managed state in `input`, `processing`, `output`, `rejected`, and `logs`
- append-only local JSONL processing audit log with daily archives plus rejection sidecars
- APScheduler background jobs: stock alert checks (every 5 min), database backup (daily at 00:15), session revocation sweep (hourly)
- Prometheus `/metrics` endpoint and `/health` heartbeat-derived endpoint
- CSRF middleware (content-type enforcement) and rate-limited auth endpoints (10 req/60s per IP)

Recommended production topology:

- one workflow per config file and per managed folder set for the ingestion service
- one service wrapper or scheduler entry per workflow instance
- local filesystem for the hot-folder lifecycle on a single volume
- the web application binds to `0.0.0.0:8080` by default; use Cloudflare Tunnel or a reverse proxy for public access
- `start-app.ps1` provides self-healing startup with Cloudflare Tunnel integration and automatic restart
- `install-autostart.ps1` registers a Windows scheduled task for daemon-mode operation
- off-host monitoring and log shipping layered on top of the local runtime, not replacing it

## 1. Integrations And Data Contracts

### 1.1 Critical integration points

| Integration | Current implementation | Required production control | Authentication | Explicit failure modes | Current behavior | Required fallback / retry |
| Scanner or scan software -> `input_path` | Files are discovered by polling `input_path` | Upstream writers must have write-only access to `input_path` and no access to `processing`, `output`, `rejected`, or `logs` | SMB/share credential or local service account ACL, depending on deployment | partial write, stale open handle, wrong folder, unsupported file, duplicate rescan, share permission drift, network disconnect, backlog growth | waits for stability, then processes or rejects | keep intake isolated by workflow; if a file remains unstable or locked, reject with sidecar and alarm on sustained rate |
| Config deployment -> `config.json` | JSON file loaded once at startup by `load_settings()` | Config must be source-controlled, schema-checked before deploy, and read-only to the runtime account | deployment pipeline credential or admin operator | missing keys, invalid regex, unknown keys, duplicate paths, cross-volume paths, stale config version | startup fails on invalid config | rollback to last-known-good config; block deploy if schema validation fails |
| Internal file lifecycle: `input -> processing -> output/rejected` | Files are moved through managed directories | All managed paths must stay on one filesystem volume and remain service-owned | filesystem ACL only | non-atomic cross-volume move, disk full, rename collision, crash between commit and cleanup, dual-instance race | current repo validates same-volume and distinct paths at config load, acquires a per-workflow startup lock, and keeps a durable journal under `processing/.journal` | keep singleton startup locking in place; define bounded retry policy and add stronger startup reconciliation telemetry before widening throughput |
| Parser stack: `PyMuPDF`, `Pillow`, `zxing-cpp` | Barcode and document processing happen in-process | Treat all input files as untrusted parser input | none at protocol level; host isolation is the control | malformed PDF/image, decompression bomb, parser exception, high CPU, high memory, library CVE, crafted payload | runtime now validates PDF/JPEG/PNG magic bytes before deep parse; remaining parse faults become rejection or `UNEXPECTED_ERROR` | isolate host, patch dependencies, keep spoofed-file tests, and add a quarantine path for suspicious files if operations require retention |
| Web application: `stats.py` -> all routes | Multi-user FastAPI application with JWT auth, RBAC, database, write APIs, AI integration, and processing dashboard | Use Cloudflare Tunnel or reverse proxy for public access; enforce HTTPS in production | JWT cookie-based auth with bcrypt, per-IP rate limiting on auth endpoints, CSRF middleware, encrypted API key storage | accidental external exposure without tunnel, session hijacking, CSRF, brute-force login, SSRF via webhook URLs, database corruption, AI provider API key leak | binds to 0.0.0.0:8080 by default; auth required for all protected routes; SameSite=Lax cookies; SSRF prevention on webhook URLs | use `start-app.ps1` with Cloudflare Tunnel for public access; set `BB_SECRET_KEY` env var for persistent sessions across restarts; back up `data/logs/barcodebuddy.db` regularly (automated daily at 00:15) |
| Downstream document consumer -> `output_path` and `rejected_path` | Consumers are expected to read committed PDFs and rejection sidecars | Downstream must be read-only and must never write back into managed folders | filesystem ACL only | stale reads, case-sensitivity mismatch, manual tampering, consumer outage, duplicate semantics mismatch | no direct coupling in current runtime | downstream outage must not block ingest; alert on disk growth if output backlog accumulates |
| Logging and monitoring pipeline | Active JSONL file at `data/logs/processing_log.jsonl` with local daily archives `processing_log.YYYY-MM-DD.jsonl` | Off-host shipping, retention, and log-write monitoring are still required | local service account for file writes; shipper credential if forwarding is added | disk full, log write failure, dropped shipping agent, corrupted line, schema drift | rotates locally only | keep local write path simple; ship archives off-host and alert on any log write failure |

### 1.2 Exact current config contract

Machine-readable source of truth:

- `config.schema.json` for the published shape
- `app/config.py` for the loader, normalization rules, and derived `config_version`

Accepted shape:

```json
{
  "workflow_key": "default|receiving|shipping_pod|quality_compliance",
  "input_path": "string",
  "processing_path": "string",
  "output_path": "string",
  "rejected_path": "string",
  "log_path": "string",
  "barcode_types": ["string", "..."],
  "barcode_value_patterns": ["regex", "..."],
  "scan_all_pages": true,
  "duplicate_handling": "timestamp|reject",
  "file_stability_delay_ms": 2000,
  "max_pages_scan": 50,
  "poll_interval_ms": 500,
  "barcode_scan_dpi": 300,
  "barcode_upscale_factor": 1.0
}
```

Validation rules currently enforced:

- unknown config keys are rejected
- `workflow_key` is normalized to lowercase with hyphens converted to underscores, must match `^[a-z0-9][a-z0-9_-]{0,63}$`, and defaults to `default`
- `config_version` is derived from the effective config payload as a deterministic 12-character SHA-256 prefix
- `barcode_types` must contain at least one value
- `barcode_value_patterns` cannot contain empty strings and each regex must compile
- `duplicate_handling` must be `timestamp` or `reject`
- `file_stability_delay_ms >= 500`
- `max_pages_scan >= 1`
- `poll_interval_ms >= 100`
- `barcode_scan_dpi >= 72`
- `barcode_upscale_factor >= 1.0`
- `input_path`, `processing_path`, `output_path`, `rejected_path`, and `log_path` must all be distinct and on the same filesystem volume

### 1.3 Exact current file and output contracts

Input file contract:

- supported extensions are `.pdf`, `.jpg`, `.jpeg`, and `.png`
- the file signature must match the extension family; spoofed extensions reject as `UNSUPPORTED_FORMAT`
- empty files reject as `EMPTY_FILE`
- files larger than `50 MB` reject as `FILE_TOO_LARGE`
- a file that keeps changing for `10 seconds` or cannot be exclusively opened after retries rejects as `FILE_LOCKED`
- PDFs with matching headers but unreadable contents reject as `CORRUPT_FILE`

Output contract:

- successful documents are written as PDFs under `output_path/YYYY/MM`
- original source files are removed from `processing_path` after successful PDF commit
- failures are moved to `rejected_path` with a `.meta.json` sidecar
- duplicate behavior is either timestamped output filenames or `DUPLICATE_FILE` rejection, depending on config
- there is no content-hash deduplication in the current runtime

Current barcode validation contract:

- current runtime accepts filename-safe values matching `^[A-Za-z0-9_-]{4,64}$`
- optional `barcode_value_patterns` narrow the set of routable values
- if no barcode is detected, the file is rejected as `BARCODE_NOT_FOUND`
- the best candidate across the scanned document wins deterministically by business-rule match, then largest bounding box area, then earlier page number, then scan order
- `barcode_value_patterns` affect routing priority, but they do not create separate ambiguity or pattern-mismatch states
- after barcode selection, the chosen barcode is rejected as `INVALID_BARCODE_FORMAT` if it fails business-rule matching or filename safety rules
- barcode text must still satisfy filename safety rules: printable characters only, length `4..64`, and characters limited to alphanumeric, dash, and underscore


### 1.4 Exact current log and rejection-sidecar contracts

Current log event shape:

```json
{
  "schema_version": "1.0",
  "workflow": "string",
  "host": "hostname",
  "instance_id": "uuid4",
  "config_version": "12-hex-character checksum",
  "error_code": "string|null",
  "timestamp": "ISO-8601 timestamp",
  "processing_id": "uuid4",
  "stage": "processing|validation|output",
  "status": "success|failure",
  "duration_ms": 1234,
  "original_filename": "string",
  "reason": "string|null",
  "barcode": "string|null",
  "barcode_format": "string|null",
  "barcode_orientation_degrees": 0,
  "barcode_matches_business_rule": true,
  "pages": 1,
  "raw_detection_count": 0,
  "candidate_values": ["..."],
  "eligible_candidate_values": ["..."],
  "page_one_eligible_values": ["..."],
  "output_path": "string|null",
  "rejected_path": "string|null",
  "error": "exception class|null"
}
```

Recovery-generated log events may also include `recovery_action`, `journal_state`, `journal_path`, `processing_path`, `recovered_input_path`, `output_path`, or `rejected_path` when startup reconciliation runs.

Service lifecycle events use `stage = "service"` and `event_type = "startup" | "heartbeat" | "shutdown"`. They also carry `input_backlog_count`, `processing_count`, `journal_count`, and `oldest_input_age_seconds`.

Current rejection sidecar shape:

```json
{
  "schema_version": "1.0",
  "workflow": "string",
  "host": "hostname",
  "instance_id": "uuid4",
  "config_version": "12-hex-character checksum",
  "error_code": "string|null",
  "processing_id": "uuid4",
  "reason": "string",
  "stage": "processing|validation|output",
  "timestamp": "ISO-8601 timestamp",
  "attempts": 1,
  "original_filename": "string",
  "barcode": "string|null",
  "barcode_format": "string|null",
  "barcode_orientation_degrees": 0,
  "barcode_matches_business_rule": true,
  "pages": 1,
  "raw_detection_count": 0,
  "candidate_values": ["..."],
  "eligible_candidate_values": ["..."],
  "page_one_eligible_values": ["..."]
}
```

Production gap to close:

- logs now rotate locally by day, but there is still no off-host durability or enforced retention policy in the runtime
- there is no off-host instance registry or monitored service-discovery layer
- `stats.py` now derives local health from lifecycle events and queue state, but it is still not a production monitoring system
- there is no quarantine path for suspicious but unsupported inputs
- log-write failure is still operationally critical and not yet isolated by a shipper or fallback channel

## 2. Documentation System

| Artifact | Purpose | Owner | Source of truth | Update trigger | Versioning rule |
| `README.md` | repo entry point and operator commands | App Owner | repo root | command, install, or runtime-shape change | update in same PR |
| `docs/current-system-truth.md` | quick builder entry point | App Owner | repo docs | any change to recommended read order or runtime truth anchors | keep short and current |
| `docs/danpack-builder-handoff.md` | builder-facing repo and business context | App Owner | repo docs | any change to verified runtime, workflow split, or test baseline | update in same PR |
| `docs/production-operations-blueprint.md` | production operating contract | App Owner + Platform Owner + Security Owner | repo docs plus code | any change to integration, metrics, auth boundary, runbook, or alert threshold | review every release |
| `docs/builder-execution-plan.md` | dependency-aware implementation order | App Owner | repo docs | any change to sequencing, ownership, or prerequisite logic | review every release |
| `docs/runbooks/incident-response.md` | on-call response procedure | SRE / Operations Owner | repo docs | any change to alert policy, severity mapping, or recovery process | review quarterly |
| `config.schema.json` | machine-readable config contract | App Owner | repo root | any config field/default/validation change | schema and code must land together |
| `tests/` | executable runtime and artifact baseline | App Owner | repo tests | any behavior, schema, or artifact change | tests must change with code |
| security package: SBOM, dependency audit, ACL audit | patching and hardening record | Security Owner | CI artifacts plus repo docs | dependency change, host/image change, auth model change | generate per release |

Accuracy rules:

- if `config.schema.json`, `app/config.py`, and this document disagree, the code plus tests win until the doc is corrected in the same change
- config examples in `configs/` are deployment templates, not proof of validated Danpack barcode regexes
- `TECHNICAL_ARCHITECTURE_SPECIFICATION.md` is target-state guidance and must not override the contracts documented here

## 3. Observability

### 3.1 Required metrics

Per workflow instance:

- process up/down heartbeat age
- input backlog count
- oldest input age
- current processing count
- processing duration p50/p95/p99
- success count and failure count by `error_code`
- recovery events on startup
- log write failures
- disk free percentage for the managed volume

User-level or workflow-level visibility:

- recent successful outputs by barcode and filename
- recent rejections with reason, barcode evidence, and rejected path
- duplicate rejection rate versus timestamped-duplicate rate
- page-count distribution and raw detection counts for troubleshooting
- document-level lookup by `processing_id` from logs or sidecars

The web application provides comprehensive local visibility through the processing dashboard, inventory analytics, activity log, and alert system. The Prometheus `/metrics` endpoint enables integration with external monitoring (Grafana, Alertmanager). The `/health` endpoint supports external uptime checks. For production monitoring beyond the built-in surfaces, wire the Prometheus metrics into an external alerting pipeline using the thresholds defined in Section 3.3.

### 3.2 Logging standards

Current minimum standard:

- append-only JSONL written to the active file `data/logs/processing_log.jsonl`
- older log segments rotate locally by day into `data/logs/processing_log.YYYY-MM-DD.jsonl`
- every log and rejection sidecar payload includes `schema_version`, `workflow`, `host`, `instance_id`, `config_version`, and `error_code`
- stage events remain filesystem-first and are emitted from the runtime, not synthesized later by the stats page
- rejection sidecars preserve the barcode evidence available at the time of failure
- service lifecycle events emit local heartbeat and queue telemetry for the stats surface

Production-required additions:

- off-host shipping with retention and shipper-health monitoring
- enforced retention for local archives that does not break `stats.py`
- explicit startup, shutdown, and heartbeat events
- alert wiring keyed off the canonical `error_code` field
- schema-versioned downstream consumers and dashboards

### 3.3 Exact alert thresholds

| Condition | Threshold | Action |
| service heartbeat missing | `service_heartbeat_age_seconds > 60` | Sev1 page |
| restart loop | `process_restart_count >= 3` in `15m` | Sev1 page |
| growing input backlog | `input_backlog_count > 20` for `10m` | Sev2 page |
| stalled workflow | `oldest_input_age_seconds > 300` | Sev2 page |
| hard stall | `oldest_input_age_seconds > 900` | Sev1 page |
| latency degradation | `processing_duration_ms_p95 > 12000` for `15m` | Sev2 page |
| timeout-edge latency | `processing_duration_ms_p95 > 14000` for `5m` | Sev1 page |
| failure-rate spike | `failure_rate > 5%` over `15m` with at least `50` documents | Sev2 page |
| severe failure spike | `failure_rate > 15%` over `15m` with at least `20` documents | Sev1 page |
| unexpected runtime faults | `unexpected_error_total >= 2` in `15m` | Sev1 page |
| repeated file locks | `file_locked_total > 10` in `15m` | Sev2 page |
| disk pressure | `disk_free_pct < 15%` | Sev2 page |
| severe disk pressure | `disk_free_pct < 10%` | Sev1 page |
| log write failure | `log_write_failures_total >= 1` | Sev1 page |
| recovery on startup | `recovery_events_total >= 1` | Sev2 page |

Log-only, no page:

- single rejected file with intact sidecar and no backlog growth
- one startup recovery event when the service intentionally reclaims stranded files
- one unsupported or spoofed file where the rejection rate stays below the alert threshold

## 4. Incident Response

Primary runbook:

- `docs/runbooks/incident-response.md`

Step sequence:

1. detect and classify severity
2. contain upstream intake if the workflow is unsafe
3. preserve logs, config, and file evidence
4. diagnose runtime, platform, and security dimensions separately
5. mitigate with the smallest safe change
6. recover, requeue if appropriate, and verify intake-output balance
7. communicate status on a fixed cadence
8. complete postmortem and corrective actions

## 5. Security And Stability Risks

| Risk | Current repo state | Immediate mitigation | Prevent recurrence | Owner |
| dual-instance race | runtime now acquires one per-workflow startup lock file, but wrapper discipline is still required | keep one service wrapper and one scheduler entry per workflow | add startup-heartbeat monitoring and deployment guardrails around the lock | Platform + App |
| cross-volume or overlapping path mistakes | path validation now blocks these at config load | keep example configs and deployed configs schema-checked | validate configs in CI before deploy | App |
| untrusted parser input | parser libraries run in-process | isolate host, patch dependencies, enable AV on intake path | SBOM, dependency scan, and patch policy | Security + Platform |
| extension spoofing | runtime now validates magic bytes and rejects mismatches as `UNSUPPORTED_FORMAT` | keep spoofed-file tests and preserve suspicious files when operations require review | quarantine policy plus parser regression coverage | App |
| crash recovery still lacks policy depth | current startup uses a durable per-file journal plus recovery log records, but there is no bounded retry policy or quarantine branch | preserve journal files and recovery logs during incidents | add explicit retry policy, quarantine handling, and startup telemetry | App |
| observability loss | logs are local only | ship logs off-host and alert on write failure | add monitored shipper and retention policy | Platform + SRE |
| auth drift on shares | filesystem ACLs are the main auth boundary for the ingestion pipeline; the web application uses JWT auth with RBAC | baseline ACLs now and remove human write access from managed paths; set `BB_SECRET_KEY` for session persistence | scheduled ACL audit and deployment automation; rotate `BB_SECRET_KEY` periodically | Platform + Security |
| web application exposure | the web app binds to 0.0.0.0 by default and includes write APIs, auth, and AI features | use Cloudflare Tunnel or reverse proxy; never expose port 8080 directly to the public internet without TLS | enforce HTTPS via tunnel or proxy; monitor tunnel health via `start-app.ps1` watchdog | Platform + Security |
| database integrity | SQLite in WAL mode; automated daily backup at 00:15; no replication | ensure backup job runs and backups are retained off-host | add backup verification and off-host backup shipping | Platform + App |
| AI provider key security | API keys encrypted at rest with Fernet derived from `secret_key` | set a strong `BB_SECRET_KEY`; rotate if compromised | monitor AI usage via rate limiting and activity log | Security + App |
| docs and runtime drift | already happened in this repo | keep docs in the same PR as code changes | enforce artifact and test gates in CI | App |

Immediate next actions:

1. keep one instance per workflow and lock down folder ACLs
2. add off-host log shipping, retention, and the thresholds in this document
3. define the bounded retry policy and any quarantine branch for recovery edge cases
4. publish and review the security patch baseline for `Pillow`, `PyMuPDF`, and `zxing-cpp`
5. ship lifecycle telemetry into real alerts and service-level dashboards
