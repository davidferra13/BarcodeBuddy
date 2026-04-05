# BarcodeBuddy Product Blueprint

Last updated: 2026-04-05.

This is the master document. It defines everything BarcodeBuddy is, everything it does today, and everything it is supposed to become. The roadmap at the end sequences what remains.

---

## 1. What This Is

BarcodeBuddy is a barcode-driven document ingestion and inventory management system built for Danpack, a custom packaging and industrial supply company based in Massachusetts.

It solves a specific, recurring operational problem: scanned paperwork — packing slips, proof-of-delivery documents, receiving slips, invoices — needs to land on the correct business record automatically, without a clerk renaming files by hand.

The system has two runtime components:

- **Ingestion service** (`main.py`) — a headless hot-folder watcher that claims scanned files, reads the routing barcode, converts them to PDF, and files them by barcode value
- **Web application** (`stats.py`) — a multi-user FastAPI application for inventory management, monitoring, analytics, alerts, team collaboration, and AI-assisted operations

## 2. Who This Is For

| Role | What they need from the system |
| --- | --- |
| **Warehouse clerk / scanner operator** | Drop a document in a folder; it gets filed correctly without manual work |
| **Receiving dock worker** | Scan a packing slip; it attaches to the right PO automatically |
| **Inventory manager** | Track stock levels, generate barcodes, get low-stock alerts, do scan-based lookups |
| **Operations owner** | See what's happening across all scans, what's overdue, what failed, and what tomorrow looks like |
| **Department lead** | Workflow-specific reports for receiving, shipping/POD, and quality/compliance |
| **Branch manager / executive** | Quarter-level rollups, service-level performance, and forecast views |
| **Admin** | Manage users, roles, teams, system settings, and audit trails |

## 3. Design Principles

These are non-negotiable across all current and future work.

1. **Deterministic outcomes** — every file produces exactly one result: success or failure, with full traceability
2. **No guessing** — no OCR inference, no assumed barcode values, no auto-closed obligations without evidence
3. **Truthful reporting** — projections are never presented as actuals; partial data is labeled partial
4. **One workflow per instance** — receiving, shipping/POD, and quality/compliance run as separate configs, not one mixed queue
5. **File-based intake** — hot-folder ingestion is the first-class deployment model; this is how operators actually work
6. **Audit everything** — every state change, user action, and system event is logged to an append-only trail
7. **Operator-first UI** — no data dumps; focused views, clear navigation, interactivity, and color diversity

---

## 4. Full Capability Map

Everything below is what BarcodeBuddy is supposed to be when finished. Status is marked for each capability.

### 4.1 Document Ingestion

| Capability | Status |
| --- | --- |
| Hot-folder file watching (watchfiles / Rust notify backend) | Done |
| File stability detection (configurable delay, consecutive unchanged checks) | Done |
| Magic-byte format validation (PDF, JPG, JPEG, PNG) | Done |
| TIFF support | Not started |
| Exclusive file claim via atomic move to processing directory | Done |
| Per-file recovery journal under `processing/.journal` | Done |
| Crash recovery on restart (journal-based, not blind sweep) | Done |
| Barcode extraction via zxing-cpp with OpenCV preprocessing | Done |
| Multi-rotation barcode scanning (0, 90, 180, 270 degrees) | Done |
| Deterministic barcode selection (business-rule match → largest bbox → earlier page → scan order) | Done |
| Configurable barcode value patterns (regex business-rule filtering) | Done |
| PDF output generation (images converted to PDF; PDFs preserved) | Done |
| Deterministic file naming from barcode value | Done |
| Duplicate handling: `timestamp` mode (preserves rescans) | Done |
| Duplicate handling: `reject` mode (flags collisions) | Done |
| Rejection sidecars (`.meta.json` with failure context) | Done |
| Append-only JSONL logging with daily rotation | Done |
| Runtime metadata in all log entries (schema_version, workflow, host, instance_id, config_version, error_code) | Done |
| Per-workflow startup lock (singleton enforcement) | Done |
| Service lifecycle events (startup, heartbeat, shutdown) | Done |
| Graceful shutdown via SIGINT/SIGTERM | Done |
| Multi-document batch splitting (one PDF containing multiple documents) | Not started |

### 4.2 Configuration and Deployment

| Capability | Status |
| --- | --- |
| JSON config with Pydantic v2 validation | Done |
| Machine-readable config schema (`config.schema.json`) | Done |
| Workflow-specific starter configs (receiving, shipping-pod, quality-compliance) | Done |
| All managed paths validated to same filesystem volume | Done |
| Unknown config keys rejected | Done |
| Docker deployment (`Dockerfile`) | Done |
| Railway deployment (`railway.toml`, `Procfile`) | Done |
| Windows PowerShell launcher with Cloudflare Tunnel (`start-app.ps1`) | Done |
| Windows scheduled task installer (`install-autostart.ps1`) | Done |
| Environment variable overrides for config values | Not started |

### 4.3 Authentication and User Management

| Capability | Status |
| --- | --- |
| JWT cookie-based authentication with bcrypt hashing | Done |
| Role-based access control (owner, admin, manager, user) | Done |
| First signup becomes owner (email gated only when `BB_OWNER_EMAIL` is set) | Done |
| Open signup by default, admin-controlled toggle | Done |
| Password reset with email token validation | Done |
| Session management with expiry and revocation | Done |
| Rate-limited auth endpoints (10 req/60s per IP) | Done |
| CSRF middleware (content-type enforcement) | Done |
| Ownership transfer | Done |
| Admin audit log of all sensitive operations | Done |

### 4.4 Inventory Management

| Capability | Status |
| --- | --- |
| Full CRUD for inventory items (name, SKU, quantity, location, category, tags, cost, unit) | Done |
| Auto-generated barcodes (Code128, QR) with downloadable images | Done |
| Barcode and SKU scan lookup | Done |
| Browser camera scanning (BarcodeDetector API) | Done |
| Quick stock adjustments with reason tracking (received, sold, adjusted, damaged, returned) | Done |
| Full transaction history per item | Done |
| Bulk CSV import with conflict handling (create or update by SKU) | Done |
| Bulk CSV and JSON export | Done |
| Bulk actions (multi-select update location, category, status, or delete) | Done |
| Min/max stock thresholds per item | Done |
| User-scoped inventory isolation | Done |

### 4.5 Analytics and Monitoring

| Capability | Status |
| --- | --- |
| Processing dashboard (document counts, success/failure, queue state, latency percentiles) | Done |
| 24-hour activity summary | Done |
| Top failure reasons | Done |
| Service health from worker heartbeat | Done |
| Inventory analytics: transaction breakdown by reason | Done |
| Inventory analytics: daily transaction trends (configurable window) | Done |
| Inventory analytics: valuation by category and location | Done |
| Inventory analytics: velocity metrics (top movers) | Done |
| Inventory analytics: stock health distribution | Done |
| Calendar view of inventory activity (month and day) | Done |
| Prometheus `/metrics` endpoint | Done |
| `/health` endpoint (heartbeat-derived) | Done |

### 4.6 Alerts and Notifications

| Capability | Status |
| --- | --- |
| Per-item stock alert configuration (low-stock, overstock) | Done |
| Alert severity levels | Done |
| Alert state tracking (unread, read, dismissed) | Done |
| Webhook dispatch on threshold breach | Done |
| Scheduled alert checks (every 5 minutes via APScheduler) | Done |
| Alert count badge in navigation | Done |

### 4.7 Scan-to-PDF

| Capability | Status |
| --- | --- |
| Manual barcode entry | Done |
| Camera scanning input | Done |
| Image/PDF file upload with barcode extraction | Done |
| Batch accumulation in browser (localStorage) | Done |
| Inventory enrichment (SKU, name, quantity, location, category) | Done |
| Professional PDF report generation | Done |

### 4.8 Team Management

| Capability | Status |
| --- | --- |
| Create and delete teams | Done |
| Add/remove members with team roles (lead, member, viewer) | Done |
| Task creation with status, priority, and due dates | Done |
| Role-based permission enforcement | Done |
| Cross-team visibility for admins and owner | Done |

### 4.9 AI Integration

| Capability | Status |
| --- | --- |
| Hybrid local (Ollama) and cloud (Anthropic, OpenAI) provider support | Done |
| Setup wizard with provider detection and model selection | Done |
| Encrypted API key storage at rest | Done |
| Chatbot with 11 inventory and operations tools | Done |
| Conversation persistence (create, retrieve, delete) | Done |
| Rate limiting per user and model | Done |
| Privacy page documenting data handling | Done |

### 4.10 Activity and Audit

| Capability | Status |
| --- | --- |
| Unified activity log across all subsystems (inventory, auth, admin, scan, import, export, alert, system) | Done |
| Filter by date range and category | Done |
| Summary statistics (today, this week, category breakdown) | Done |
| Recent activity drawer in navigation | Done |

### 4.11 Scan Record Workbench — NOT STARTED

A future single-scan deep-dive page where an operator can open one scan record and see its full lifecycle.

| Capability | Status |
| --- | --- |
| Single-scan detail view with full processing history | Not started |
| All processing runs, artifacts, and durations | Not started |
| Related obligations linked to this scan | Not started |
| Notes (operator, compliance, pinned) | Not started |
| Attachments and export history | Not started |
| Reprocessing and manual enrichment | Not started |
| Links to ERP records, support cases, or external references | Not started |

Spec: `docs/scan-record-workbench.md`, `docs/scan-record-builder-handoff.md`

### 4.12 Operations Planner — NOT STARTED

A future multi-record planning, reporting, and workload-control layer that answers: what is happening across all scans right now, what was completed, what still needs to be scanned, what is late, and what tomorrow looks like.

| Capability | Status |
| --- | --- |
| **Event truth and state store** | |
| Freeze event schema versioning | Not started |
| Durable scan state store (SQLite event normalization) | Not started |
| Append-only activity event ledger | Not started |
| **Scan obligations** | |
| Manual creation of expected-scan obligations | Not started |
| Imported obligations from upstream business systems | Not started |
| Obligation states: open, due_soon, overdue, matched, partially_matched, waived, closed | Not started |
| Obligation queue with assignee, priority, and due window | Not started |
| Overdue scan detection | Not started |
| **Report engine** | |
| Hourly reports (throughput, failures, backlog change) | Not started |
| Shift reports (morning, day, night with configurable boundaries) | Not started |
| Daily close-out report (locked, immutable) | Not started |
| Tomorrow forecast (projected workload, staffing pressure, risk) | Not started |
| Quarterly report (actual with optional forecast section) | Not started |
| Custom ad-hoc reports (arbitrary window and filters) | Not started |
| Immutable report snapshots with versioning | Not started |
| Drill-down from report totals to underlying scan records | Not started |
| **Planner screens** | |
| Live overview (current workload, backlog, failure rate, exceptions) | Not started |
| Report library (saved definitions, generated snapshots, filters) | Not started |
| Obligation queue UI | Not started |
| Activity ledger UI (append-only event stream with filters) | Not started |
| Scan history (complete history, state progression, report inclusion) | Not started |
| **Forecasting** | |
| Tomorrow report driven by obligations, due dates, patterns, throughput, carryover | Not started |
| Confidence labels and assumption sourcing | Not started |
| Quarter-forward risk and capacity sections (labeled projection-only) | Not started |
| **Planner observability** | |
| Planner health metrics and recovery tooling | Not started |

Specs: `docs/operations-planner-product-spec.md`, `docs/operations-planner-technical-spec.md`, `docs/operations-planner-builder-handoff.md`, `docs/operations-planner-execution-plan.md`

### 4.13 Production Hardening — PARTIALLY DONE

| Capability | Status |
| --- | --- |
| Structured logging via structlog | Done |
| Prometheus metrics | Done |
| Health endpoint | Done |
| Incident response runbook | Done (documented) |
| Alerting thresholds (queue depth, failure rate, heartbeat staleness) | Documented, not wired |
| External log shipping (syslog, Loki, etc.) | Not started |
| Backup automation (DB backup at 00:15 via APScheduler) | Done |
| Session revocation sweep (hourly via APScheduler) | Done |
| In-app feedback widget (bug reports, feature requests, questions) | Done |
| Update script (`update-app.ps1`) for safe patch delivery | Done |

### 4.14 ERP and External Integration — NOT STARTED

| Capability | Status |
| --- | --- |
| Bridge to attach filed PDFs to ERP records (PO, shipment, receipt) | Not started |
| Webhook or API callbacks on successful file routing | Not started |
| Upstream obligation import from ERP or business systems | Not started |

### 4.15 Mobile Capture — NOT STARTED

| Capability | Status |
| --- | --- |
| Mobile-native scanning app for warehouse floor use | Not started |
| Mobile file upload to hot-folder or API | Not started |

Note: Browser-based camera scanning for inventory lookups is already implemented. Mobile capture here refers to a purpose-built mobile scanning workflow for document ingestion.

---

## 5. Architecture Summary

```
┌──────────────────────────────────────────────────────────┐
│                    Scanner / MFP / Operator               │
│              (drops files into hot-folder)                 │
└─────────────────────────┬────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────┐
│              Ingestion Service (main.py)                   │
│                                                            │
│  data/input → stabilize → claim → barcode scan →           │
│  validate → PDF output or reject → JSONL log               │
│                                                            │
│  Per-workflow config, startup lock, recovery journal        │
└──────────────────────────────────────────────────────────┘
                          │
            JSONL logs + filesystem artifacts
                          │
                          ▼
┌──────────────────────────────────────────────────────────┐
│              Web Application (stats.py)                    │
│                                                            │
│  FastAPI + SQLite (WAL mode) + Uvicorn                     │
│                                                            │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐   │
│  │  Dashboard   │  │  Inventory   │  │  Auth & Admin   │   │
│  │  & Stats     │  │  Management  │  │  (RBAC, JWT)    │   │
│  └─────────────┘  └──────────────┘  └─────────────────┘   │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐   │
│  │  Analytics   │  │  Alerts &    │  │  AI Chatbot     │   │
│  │  & Calendar  │  │  Webhooks    │  │  (Ollama/Cloud) │   │
│  └─────────────┘  └──────────────┘  └─────────────────┘   │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐   │
│  │  Scan-to-PDF │  │  Teams &     │  │  Activity Log   │   │
│  │             │  │  Tasks       │  │  & Audit Trail  │   │
│  └─────────────┘  └──────────────┘  └─────────────────┘   │
│                                                            │
│  FUTURE:                                                   │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Operations Planner                                   │  │
│  │  (obligations, reports, forecasts, scan workbench)    │  │
│  └──────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

**Tech stack:** Python 3.10–3.13 · FastAPI · Uvicorn · SQLAlchemy · SQLite (WAL) · Pydantic v2 · structlog · zxing-cpp · OpenCV · PyMuPDF · APScheduler · Prometheus client

**Deployment:** Windows (Task Scheduler / PowerShell), Linux (systemd), Docker, Railway

---

## 6. Roadmap

Everything in Sections 4.1–4.10 is **done**. The roadmap below covers what remains, sequenced by dependency and operational value.

### Phase 1 — Foundation Gaps

Small, independent items that unblock nothing but fill real holes.

| Item | Why |
| --- | --- |
| TIFF input support | Some scanners default to TIFF; operators shouldn't need to change device profiles |
| Environment variable config overrides | Needed for containerized deployments where you can't mount a config file |
| Wire alerting thresholds to external notification (queue depth, failure rate, heartbeat staleness) | Monitoring infrastructure already exists; thresholds are documented but not dispatching |

### Phase 2 — Scan Record Workbench

The single-scan deep-dive page. This is a prerequisite for the planner because the planner links to individual scan records.

| Item | Why |
| --- | --- |
| Scan record detail page with full processing lifecycle | Operators need to see what happened to one document end-to-end |
| Notes, attachments, and external links on scan records | Supports compliance review and dispute resolution |
| Reprocessing and manual enrichment | Allows correction without re-scanning |

Spec: `docs/scan-record-workbench.md`

### Phase 3 — Event Truth and State Store

The durable foundation the planner depends on. No reports or obligations without this.

| Item | Why |
| --- | --- |
| Freeze event schema versioning | All planner data must share a stable event contract |
| Normalize JSONL scan events into SQLite state store | Moves from file-based log reading to queryable scan history |
| Append-only activity event ledger for planner actions | Every obligation change, report generation, and planning action is auditable |

Spec: `docs/operations-planner-execution-plan.md` Phase 1–2

### Phase 4 — Scan Obligations

The "what's missing?" layer. This is where BarcodeBuddy stops being reactive and becomes proactive.

| Item | Why |
| --- | --- |
| Manual obligation creation (expected scans with due windows) | Operations owners can declare what should be scanned and by when |
| Obligation state machine (open → due_soon → overdue → matched → closed) | Enables overdue detection and accountability |
| Obligation queue UI with assignee and priority | Makes missing scans visible and actionable |
| Imported obligations from upstream systems | Connects to ERP-generated expectations (POs received, shipments dispatched) |

Spec: `docs/operations-planner-execution-plan.md` Phase 3

### Phase 5 — Report Engine

Scheduled and on-demand operational reporting.

| Item | Why |
| --- | --- |
| Hourly and shift reports (configurable shift boundaries) | Operations owners need periodic visibility without checking dashboards |
| Daily close-out report (immutable snapshot) | Locked record for audits and management review |
| Tomorrow forecast (projected workload from obligations, patterns, carryover) | Planning and staffing decisions |
| Quarterly report (actual + optional forecast section) | Executive review and quarter-over-quarter comparison |
| Custom ad-hoc reports | Owner-defined windows and filters |
| Immutable report snapshots with versioning | Reproducibility and audit trail |
| Report library UI and drill-down to scan records | Makes reports navigable and verifiable |

Spec: `docs/operations-planner-execution-plan.md` Phase 4–5

### Phase 6 — Planner Screens

The full operational control plane.

| Item | Why |
| --- | --- |
| Live overview (current workload, backlog, failure rate, open obligations) | Single view of operational health |
| Obligation queue (overdue, due soon, matched, waived, closed) | Accountability and follow-up |
| Activity ledger (full append-only event stream) | Audit and investigation |
| Scan history (complete history with state progression and report inclusion) | Traceability |

Spec: `docs/operations-planner-product-spec.md` Section 9

### Phase 7 — External Integration

Connecting BarcodeBuddy to the systems around it.

| Item | Why |
| --- | --- |
| ERP bridge (attach filed PDFs to PO/shipment/receipt records) | Closes the last-mile gap between filing a document and attaching it to a business record |
| Webhook/API callbacks on successful routing | Lets downstream systems react to filed documents |
| Upstream obligation import API | Enables ERP-driven expected-scan workflows |

### Phase 8 — Extended Capabilities

Lower priority, higher ambition.

| Item | Why |
| --- | --- |
| Multi-document batch splitting | Handles operators who scan a stack of documents as one PDF |
| Mobile capture workflow | Purpose-built scanning from the warehouse floor, beyond browser camera |
| External log shipping (syslog, Loki) | Enterprise observability integration |

---

## 7. What's Explicitly Out of Scope

These are not bugs or missing features. They are intentional boundaries.

- **OCR-driven document inference** — the routing key must come from a barcode, not guessed text
- **Scanner hardware control** — BarcodeBuddy consumes files; it does not drive scanners
- **ERP matching engine** — BarcodeBuddy is the rename-and-archive stage that precedes ERP, not a replacement for it
- **Cloud-first architecture** — designed for single-node, local-filesystem deployment; cloud is optional
- **Non-barcoded documents** — emailed AP invoices and other documents without routing barcodes belong in a separate workflow
- **Content hashing for deduplication** — duplicate detection is filename-based by design

---

## 8. Reference Index

| Document | Purpose |
| --- | --- |
| `README.md` | User-facing install, run, and feature overview |
| `docs/current-system-truth.md` | Builder starting point — what the code does today |
| `docs/danpack-builder-handoff.md` | Full builder context and verified business decisions |
| `docs/production-operations-blueprint.md` | Production integration, observability, incident, and security |
| `docs/builder-execution-plan.md` | Dependency-aware implementation order for next builder |
| `docs/danpack-system-interaction-philosophy.md` | UI and interaction design rules |
| `docs/industry-workflow-research.md` | Research backing the product decisions |
| `docs/packaging-industrial-operating-model.md` | Deployment patterns for packaging/industrial supply |
| `docs/scan-record-workbench.md` | Future single-scan detail page spec |
| `docs/scan-record-builder-handoff.md` | Builder handoff for scan workbench |
| `docs/operations-planner-product-spec.md` | Full planner product definition |
| `docs/operations-planner-technical-spec.md` | Planner technical architecture |
| `docs/operations-planner-builder-handoff.md` | Planner builder handoff |
| `docs/operations-planner-execution-plan.md` | Planner phased implementation order |
| `TECHNICAL_ARCHITECTURE_SPECIFICATION.md` | Target-state architecture (not all implemented) |
| `config.schema.json` | Machine-readable config contract |
| `docs/runbooks/incident-response.md` | Production incident response |
