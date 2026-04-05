# BarcodeBuddy — Complete System Reference

Last updated: 2026-04-04
Version: 3.0.0

This is the exhaustive technical reference for every file, endpoint, database table, business rule, configuration option, and behavioral nuance in the BarcodeBuddy project. If a question can be answered about this system, the answer is in this document.

---

## Table of Contents

1. [What This Is](#1-what-this-is)
2. [Who This Is For](#2-who-this-is-for)
3. [Design Principles](#3-design-principles)
4. [Folder Size and Metrics](#4-folder-size-and-metrics)
5. [Complete File Inventory](#5-complete-file-inventory)
6. [Technology Stack](#6-technology-stack)
7. [Architecture](#7-architecture)
8. [Document Ingestion Service](#8-document-ingestion-service)
9. [Configuration System](#9-configuration-system)
10. [Authentication and User Management](#10-authentication-and-user-management)
11. [Admin Panel](#11-admin-panel)
12. [Inventory Management](#12-inventory-management)
13. [Analytics and Monitoring](#13-analytics-and-monitoring)
14. [Alerts and Notifications](#14-alerts-and-notifications)
15. [Scan-to-PDF](#15-scan-to-pdf)
16. [Team Management](#16-team-management)
17. [AI Integration](#17-ai-integration)
18. [Activity and Audit Log](#18-activity-and-audit-log)
19. [Layout and UI System](#19-layout-and-ui-system)
20. [Dashboard and Stats Engine](#20-dashboard-and-stats-engine)
21. [Database Schema](#21-database-schema)
22. [Deployment](#22-deployment)
23. [Test Suite](#23-test-suite)
24. [All HTTP Endpoints](#24-all-http-endpoints)
25. [All Numeric Constants](#25-all-numeric-constants)
26. [What Is Not Built Yet](#26-what-is-not-built-yet)
27. [What Is Explicitly Out of Scope](#27-what-is-explicitly-out-of-scope)
28. [Document Index](#28-document-index)

---

## 1. What This Is

BarcodeBuddy is a barcode-driven document ingestion and inventory management system built for **Danpack**, a custom packaging and industrial supply company based in Massachusetts.

It solves a specific, recurring operational problem: scanned paperwork — packing slips, proof-of-delivery documents, receiving slips, invoices — needs to land on the correct business record automatically, without a clerk renaming files by hand.

The system has two runtime components:

- **Ingestion service** (`main.py`) — a headless hot-folder watcher that claims scanned files, reads the routing barcode, converts them to PDF, and files them by barcode value into `data/output/YYYY/MM/`
- **Web application** (`stats.py`) — a multi-user FastAPI application for inventory management, monitoring, analytics, alerts, team collaboration, and AI-assisted operations

---

## 2. Who This Is For

| Role | What they need from the system |
|------|-------------------------------|
| **Warehouse clerk / scanner operator** | Drop a document in a folder; it gets filed correctly without manual work |
| **Receiving dock worker** | Scan a packing slip; it attaches to the right PO automatically |
| **Inventory manager** | Track stock levels, generate barcodes, get low-stock alerts, do scan-based lookups |
| **Operations owner** | See what's happening across all scans, what's overdue, what failed, and what tomorrow looks like |
| **Department lead** | Workflow-specific reports for receiving, shipping/POD, and quality/compliance |
| **Branch manager / executive** | Quarter-level rollups, service-level performance, and forecast views |
| **Admin** | Manage users, roles, teams, system settings, and audit trails |

---

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

## 4. Folder Size and Metrics

| Metric | Value |
|--------|-------|
| Project code + docs (excl .venv/.git) | 1.4 MB |
| With virtual environment | 293 MB |
| Total files (excl .venv/.git) | 178 |
| Total Python lines of code | 19,399 |
| App code (26 modules in app/) | 15,983 lines |
| Test code (12 modules in tests/) | 3,416 lines |
| Documentation files (.md) | 19 |
| Configuration/schema files (.json) | 11 |
| HTTP endpoints | 95 |
| Database tables | 16 |
| Database columns | 142 |
| Test functions | 174 (all passing) |
| Python dependencies | 28 (+ 2 optional cloud AI) |

---

## 5. Complete File Inventory

### Root Directory (17 files)

| File | Lines | Purpose |
|------|------:|---------|
| main.py | 70 | Ingestion service entry point |
| stats.py | 84 | Web application entry point |
| config.json | — | Runtime configuration |
| config.schema.json | — | JSON Schema validation contract |
| requirements.txt | — | 28 Python dependencies |
| requirements.lock | — | Pinned dependency versions |
| pyproject.toml | — | Project metadata (Python 3.10–3.13) |
| README.md | — | User-facing install and feature overview |
| TECHNICAL_ARCHITECTURE_SPECIFICATION.md | — | Target-state architecture (aspirational, not current truth) |
| Dockerfile | — | Multi-stage Docker build |
| Procfile | — | Railway deployment |
| railway.toml | — | Railway configuration |
| start-app.ps1 | — | PowerShell launcher with Cloudflare Tunnel + auto-restart |
| install-autostart.ps1 | — | Windows scheduled task installer |
| .env | — | Environment variables |
| .gitignore | — | Git exclusions |
| .python-version | — | Python version pin |

### app/ Directory (26 Python modules)

| Module | Lines | Purpose |
|--------|------:|---------|
| __init__.py | 4 | Version declaration: 3.0.0 |
| processor.py | 1,301 | Core ingestion state machine, recovery, journals |
| watcher.py | 94 | Hot-folder file discovery and stabilization |
| barcode.py | 268 | zxing-cpp barcode extraction with OpenCV preprocessing |
| documents.py | 245 | File format detection, PDF generation, page counting |
| image_quality.py | 92 | OpenCV image quality assessment (sharpness, contrast, brightness) |
| config.py | 278 | Pydantic v2 config validation with computed fields |
| contracts.py | 67 | Event types and error code definitions |
| logging_utils.py | 170 | structlog setup, JSONL append-only logs, rotation, fsync |
| runtime_lock.py | 95 | Filesystem singleton lock per workflow |
| database.py | 538 | SQLAlchemy v2 models (16 tables), WAL mode, backup, cleanup |
| stats.py | 2,223 | FastAPI app factory, stats snapshot engine, dashboard HTML |
| layout.py | 1,507 | Shared HTML layout, navigation, sidebar, toasts, components |
| auth.py | 332 | JWT token creation, bcrypt hashing, session mgmt, permission decorators |
| auth_routes.py | 513 | Signup, login, logout, password reset endpoints |
| admin_routes.py | 493 | User management, roles, ownership transfer, system settings |
| inventory_routes.py | 1,144 | Inventory API: CRUD, bulk ops, analytics, export/import |
| inventory_pages.py | 1,305 | Inventory HTML pages: list, detail, calendar, analytics, scan |
| alerts.py | 414 | Stock alert configuration, scheduled checks, webhook dispatch |
| activity.py | 346 | Unified activity logging and activity page |
| scan_to_pdf.py | 770 | Barcode scanning → inventory enrichment → PDF report generation |
| team_routes.py | 1,013 | Team CRUD, membership management, task tracking |
| ai_provider.py | 584 | Ollama + Anthropic/OpenAI provider abstraction, encryption, rate limiting |
| ai_routes.py | 1,515 | AI setup wizard, chat, conversations, suggestions, CSV preview, privacy |
| ai_tools.py | 586 | 11 chatbot tools for inventory and operations queries |
| barcode_generator.py | 86 | Code128 and QR barcode image generation via Pillow |

### tests/ Directory (12 modules)

| File | Tests | Lines | Coverage |
|------|------:|------:|----------|
| test_auth_rbac.py | 39 | 495 | Auth flow, RBAC, sessions, rate limiting |
| test_inventory.py | 62 | 662 | Inventory CRUD, bulk ops, CSV import, scan lookup |
| test_scan_to_pdf.py | 20 | 296 | PDF generation, barcode decode, enrichment |
| test_service_runtime.py | 18 | 480 | Full ingestion lifecycle |
| test_config_artifacts.py | 13 | 292 | Config schema and example consistency |
| test_stats.py | 6 | 392 | Dashboard stats snapshot |
| test_config.py | 6 | 125 | Config validation edge cases |
| test_barcode.py | 4 | 102 | Barcode scanning with mocks |
| test_logging_utils.py | 2 | 70 | Log rotation and compression |
| test_runtime_lock.py | 2 | 56 | Singleton enforcement |
| test_e2e.py | 1 (5 sub) | 258 | Full workflow: signup → inventory → scan → alerts → export |
| test_config_examples.py | 1 | 34 | Example config validation |

### docs/ Directory (19 files)

| File | Purpose |
|------|---------|
| PRODUCT_BLUEPRINT.md | Master document: full capability map, status, and roadmap |
| COMPLETE_SYSTEM_REFERENCE.md | This document |
| current-system-truth.md | Builder entry point — what the code does today |
| danpack-builder-handoff.md | Full builder context and verified business decisions |
| danpack-system-interaction-philosophy.md | UI and interaction design rules |
| production-operations-blueprint.md | Production integration, observability, incident, security |
| builder-execution-plan.md | Dependency-aware implementation order |
| industry-workflow-research.md | Research backing the product decisions |
| packaging-industrial-operating-model.md | Deployment patterns for packaging/industrial supply |
| scan-record-workbench.md | Future single-scan detail page spec |
| scan-record-builder-handoff.md | Builder handoff for scan workbench |
| operations-planner-product-spec.md | Full planner product definition |
| operations-planner-technical-spec.md | Planner technical architecture |
| operations-planner-builder-handoff.md | Planner builder handoff |
| operations-planner-execution-plan.md | Planner phased implementation order |
| contracts/*.json (3 files) | JSON schemas: report-snapshot, scan-obligation, scan-record |
| examples/*.json (3 files) | Example data for each contract |
| prototypes/scan-record-workbench.html | HTML prototype for scan workbench |
| runbooks/incident-response.md | Production incident response playbook |

### configs/ Directory (4 files)

| File | Purpose |
|------|---------|
| README.md | Explains starter configs |
| config.receiving.example.json | Receiving dock workflow config |
| config.shipping-pod.example.json | Shipping/POD workflow config |
| config.quality-compliance.example.json | Quality/compliance workflow config |

### data/ Directory (runtime, not committed)

Created at runtime: `input/`, `processing/`, `processing/.journal/`, `output/`, `rejected/`, `logs/`, `logs/backups/`

---

## 6. Technology Stack

| Layer | Technology | Version Constraint |
|-------|-----------|-------------------|
| Language | Python | 3.10–3.13 (3.14 not supported by zxing-cpp) |
| Web framework | FastAPI | ≥0.110.0 |
| ASGI server | Uvicorn | ≥0.30.0 |
| Database | SQLite (WAL mode) | via SQLAlchemy ≥2.0.0 |
| ORM | SQLAlchemy v2 | ≥2.0.0 |
| Config validation | Pydantic v2 | ≥2.0.0 |
| Barcode scanning | zxing-cpp | ≥3.0.0, <4.0.0 |
| Image processing | OpenCV (headless) | ≥4.9.0 |
| PDF processing | PyMuPDF (fitz) | ≥1.24.0, <2.0.0 |
| Image manipulation | Pillow | ≥10.0.0, <13.0.0 |
| File monitoring | watchfiles | ≥1.0.0 |
| Structured logging | structlog | ≥24.0.0 |
| Metrics | prometheus-client | ≥0.20.0 |
| Auth (passwords) | bcrypt | ≥4.0.0 |
| Auth (tokens) | PyJWT | ≥2.8.0 |
| Encryption | cryptography (Fernet) | ≥42.0.0 |
| HTTP client | httpx | ≥0.27.0 |
| Scheduling | APScheduler | ≥3.10.0, <5.0.0 |
| Retry logic | tenacity | ≥8.0.0 |
| CLI output | rich | ≥13.0.0 |
| File uploads | python-multipart | ≥0.0.6 |
| AI (optional) | anthropic | ≥0.40.0 (commented) |
| AI (optional) | openai | ≥1.50.0 (commented) |

---

## 7. Architecture

```
┌──────────────────────────────────────────────────────────┐
│                  Scanner / MFP / Operator                 │
│            (drops files into hot-folder)                  │
└─────────────────────────┬────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────┐
│            Ingestion Service (main.py)                    │
│                                                           │
│  data/input → stabilize → claim → barcode scan →          │
│  validate → PDF output or reject → JSONL log              │
│                                                           │
│  Per-workflow config, startup lock, recovery journal       │
└──────────────────────────────────────────────────────────┘
                          │
            JSONL logs + filesystem artifacts
                          │
                          ▼
┌──────────────────────────────────────────────────────────┐
│            Web Application (stats.py)                     │
│                                                           │
│  FastAPI + SQLite (WAL mode) + Uvicorn                    │
│                                                           │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐  │
│  │  Dashboard   │  │  Inventory   │  │  Auth & Admin   │  │
│  │  & Stats     │  │  Management  │  │  (RBAC, JWT)    │  │
│  └─────────────┘  └──────────────┘  └─────────────────┘  │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐  │
│  │  Analytics   │  │  Alerts &    │  │  AI Chatbot     │  │
│  │  & Calendar  │  │  Webhooks    │  │  (Ollama/Cloud) │  │
│  └─────────────┘  └──────────────┘  └─────────────────┘  │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐  │
│  │  Scan-to-PDF │  │  Teams &     │  │  Activity Log   │  │
│  │              │  │  Tasks       │  │  & Audit Trail  │  │
│  └─────────────┘  └──────────────┘  └─────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

**Deployment targets:** Windows (Task Scheduler / PowerShell), Linux (systemd), Docker, Railway

---

## 8. Document Ingestion Service

### 8.1 Processing Pipeline State Machine

A file transitions through these states:

```
INPUT → stabilize → acquire_lock → claim (journal: "claimed")
  → validate_barcode → journal: "pending_output"
  → save_pdf → OUTPUT (journal removed)
  OR
  → REJECT (journal: "pending_rejection") → journal removed
```

### 8.2 File Stabilization

Observes file size changes to detect when writing completes.

- `file_stability_delay_ms`: Default 2000ms (minimum 500ms)
- `poll_interval_ms`: Default 500ms (minimum 100ms)
- Required stable checks: `ceil((delay + poll - 1) / poll)` = **5 checks** at defaults
- FILE_STABILITY_TIMEOUT_MS: **10,000ms** — if a file's size keeps changing for 10 seconds, it's treated as stuck ("file_locked")
- Size unchanged for full stability delay → transitions to "ready"

### 8.3 Exclusive File Claim

1. **Lock acquisition**: `ensure_exclusive_access(file_path, retries=5, interval=0.5s)`
   - Windows: `msvcrt.locking(fd, LK_NBLCK, 1)` — non-blocking exclusive lock
   - POSIX: `fcntl.flock(fd, LOCK_EX | LOCK_NB)` — non-blocking exclusive lock
   - 5 attempts, 0.5s apart. If all fail → ERROR_FILE_LOCKED
2. **Atomic move**: `shutil.move()` to processing directory
3. **Journal entry**: Written immediately after successful move

### 8.4 Recovery Journal

Location: `processing_path/.journal/<processing_id>.json`

Written atomically via `.tmp` file → fsync → atomic replace.

Journal entry fields:
- `schema_version`, `workflow`, `host`, `instance_id`, `config_version`
- `processing_id` (UUID v4), `original_filename`, `processing_path`
- `state`: "claimed" | "pending_output" | "pending_rejection"
- `stage`: "processing" | "validation" | "output"
- `updated_at`, `barcode` (optional), `reason` (optional)
- `output_path` (optional), `rejected_path` (optional)

**Recovery on startup** (`recover_processing_files()`):
1. Read all journal files from `.journal/`
2. For each entry:
   - If processing file exists → move back to input with `_recovered` suffix
   - If state="pending_output" and output exists → finalize output, remove journal
   - If state="pending_rejection" and rejected exists → finalize rejection, remove journal
   - Otherwise → log as unresolved, keep journal for manual inspection
3. Orphan files in processing/ not referenced by any journal → moved back to input with `_recovered` suffix

### 8.5 Barcode Scanning

**Multi-rotation strategy**: Scans at 0°, 90°, 180°, 270° rotation. Stops at first match.

**OpenCV preprocessing pipeline** (grayscale):
1. Convert to grayscale
2. Denoise: `fastNlMeansDenoising(h=10)`
3. CLAHE: `clipLimit=2.0, tileGridSize=(8,8)`
4. Adaptive threshold: Gaussian, block size 21, constant 10
5. Morphological closing: kernel (2,2)
6. Conditional upscaling if `barcode_upscale_factor > 1.0`

**Selection logic** (priority cascade):
1. Matches business rule pattern (highest priority)
2. Largest bounding box area
3. Earlier page number
4. Earlier vertical position (y)
5. Earlier horizontal position (x)
6. Scan order index

**Format support**: aztec, codabar, code128, code39, code93, datamatrix, ean13, ean8, itf, pdf417, qrcode, upca, upce, auto

**Barcode validation**: Must match regex `^[A-Za-z0-9_-]{4,64}$`. If `barcode_value_patterns` configured, must also `fullmatch()` at least one pattern.

### 8.6 PDF Conversion

- **PDF source**: Copy directly (atomic via `.tmp` → replace)
- **Image source** (JPG/PNG): Load with PIL → EXIF transpose → normalize to RGB → save as PDF
- **Image normalization**: RGBA/LA → white background composite; P/palette → convert to RGB
- **PDF rendering for barcode scan**: At `barcode_scan_dpi` (default 300), grayscale, no alpha

### 8.7 Output Naming

```
output_path/YYYY/MM/<barcode>.pdf
```

Barcode sanitized: spaces → `_`, invalid chars removed per `[<>:"/\\|?*\x00-\x1f]`.

### 8.8 Duplicate Handling

- **Timestamp mode** (`duplicate_handling: "timestamp"`): If file exists, generates `<barcode>_YYYYMMDD_HHMMSS.pdf`, then `_01.pdf`, `_02.pdf`, etc.
- **Reject mode** (`duplicate_handling: "reject"`): If file exists → ERROR_DUPLICATE_FILE, moved to rejected/ with sidecar

### 8.9 Rejection Sidecar

File: `<rejected_filename>.meta.json`

Contains: schema_version, workflow, host, instance_id, config_version, error_code, processing_id, reason, stage, timestamp, attempts, original_filename, barcode info (if available), detection metadata.

### 8.10 Error Codes

| Error Code | Trigger |
|-----------|---------|
| ERROR_FILE_LOCKED | 5 lock attempts failed |
| ERROR_FILE_MISSING | Input file disappeared |
| ERROR_EMPTY_FILE | File size == 0 |
| ERROR_FILE_TOO_LARGE | > 50 MB |
| ERROR_UNSUPPORTED_FORMAT | Not JPG/PNG/PDF or magic-byte mismatch |
| ERROR_CORRUPT_FILE | PDF/image reading failed |
| ERROR_BARCODE_NOT_FOUND | No valid barcode detected |
| ERROR_INVALID_BARCODE_FORMAT | Doesn't match pattern or `^[A-Za-z0-9_-]{4,64}$` |
| ERROR_DUPLICATE_FILE | In reject mode, output already exists |
| ERROR_PROCESSING_TIMEOUT | > 15 seconds total or PDF > max_pages_scan |
| ERROR_RECOVERY_FAILED | Journal recovery couldn't complete |
| ERROR_UNEXPECTED_ERROR | Catch-all for unhandled exceptions |

### 8.11 Image Quality Assessment

| Metric | Threshold | Meaning |
|--------|----------|---------|
| Blur (Laplacian variance) | < 50.0 | Image is blurry |
| Contrast (std deviation) | < 30.0 | Low contrast |
| Brightness (mean pixel) | < 40 | Underexposed |
| Brightness (mean pixel) | > 240 | Overexposed |

Quality score: 0–100 float (rounded to 1 decimal). Issues reported as string array.

### 8.12 JSONL Logging

Log file: `log_path/processing_log.jsonl`

Every entry includes: `schema_version`, `workflow`, `host`, `instance_id`, `config_version`, `error_code`, `timestamp`, `processing_id`, `stage`, `status`, `duration_ms`, `original_filename`.

Processing entries add: barcode info, pages, detection counts, quality score/issues, output/rejected path.

Service lifecycle entries add: `event_type` (startup/heartbeat/shutdown), `input_backlog_count`, `processing_count`, `journal_count`, `oldest_input_age_seconds`.

**Heartbeat interval**: Every 30 seconds.

**Log rotation**: When log date changes from file modification date. Renamed to `processing_log.YYYY-MM-DD.jsonl` → gzipped to `.jsonl.gz`.

### 8.13 Runtime Lock

Lock file: `log_path/.service.lock`

- OS-level exclusive non-blocking lock (msvcrt on Windows, fcntl on POSIX)
- Writes metadata: workflow, config_path, config_version, pid, acquired_at
- One instance per workflow_key; released on exit via context manager
- No stale lock detection — relies on OS lock semantics

---

## 9. Configuration System

### 9.1 Config Fields

| Field | Default | Validation |
|-------|---------|-----------|
| `workflow_key` | "default" | Pattern: `^[a-z0-9][a-z0-9_-]{0,63}$` |
| `input_path` | "./data/input" | Must be distinct from other managed paths |
| `processing_path` | "./data/processing" | Must be on same filesystem volume |
| `output_path` | "./data/output" | All 5 paths validated for distinctness |
| `rejected_path` | "./data/rejected" | All 5 paths validated for same volume |
| `log_path` | "./data/logs" | — |
| `barcode_types` | ["code128", "auto"] | Non-empty array of valid format names |
| `barcode_value_patterns` | [] | Array of valid regex patterns |
| `scan_all_pages` | true | Boolean |
| `duplicate_handling` | "timestamp" | "timestamp" or "reject" |
| `file_stability_delay_ms` | 2000 | ≥ 500 |
| `max_pages_scan` | 50 | ≥ 1 |
| `poll_interval_ms` | 500 | ≥ 100 |
| `barcode_scan_dpi` | 300 | ≥ 72 |
| `barcode_upscale_factor` | 1.0 | ≥ 1.0 |
| `server_host` | "0.0.0.0" | — |
| `server_port` | 8080 | 1–65535 |
| `secret_key` | "" | — |

### 9.2 Path Validation

1. **Distinct paths**: All 5 managed paths must resolve to different locations (case-insensitive on Windows)
2. **Same volume**: All 5 paths must reside on same filesystem volume (checked via `st_dev` on nearest existing ancestor)
3. Unknown config keys are **rejected** (Pydantic strict mode)

### 9.3 Normalization

- Barcode types: `.strip().lower().replace("-", "").replace("_", "")`
- Workflow key: `.strip().lower().replace("-", "_")`
- Config version: 12-character SHA256 hash of canonical JSON (sorted keys, compact separators)

### 9.4 Environment Variables

| Variable | Purpose |
|----------|---------|
| `BB_CONFIG` | Config file path (CLI `--config` takes precedence) |
| `BB_SECRET_KEY` | Secret key (takes precedence over config file) |
| `BB_OWNER_EMAIL` | Owner email for first-user signup (default: `mferragamo@danpack.com`) |
| `BB_SMTP_HOST` | SMTP server for password reset emails |
| `BB_SMTP_PORT` | SMTP port (default: 587) |
| `BB_SMTP_USER` | SMTP username |
| `BB_SMTP_PASSWORD` | SMTP password |
| `BB_RESET_FROM` | Sender email for password reset |
| `BB_SMTP_USE_TLS` | Enable TLS (default: "true") |

### 9.5 Workflow Configs

Three starter configs in `configs/`:
- `config.receiving.example.json` — Receiving dock workflow
- `config.shipping-pod.example.json` — Shipping/proof-of-delivery workflow
- `config.quality-compliance.example.json` — Quality/compliance workflow

---

## 10. Authentication and User Management

### 10.1 Role Hierarchy

| Role | Level | Capabilities |
|------|------:|-------------|
| owner | 40 | Everything. Can promote to admin, transfer ownership, demote admins |
| admin | 30 | User management (non-owner), system settings, audit log. Cannot promote to admin |
| manager | 20 | Standard app features + team creation. No admin access |
| user | 10 | Standard app features only |

### 10.2 First-User Signup (Owner Onboarding)

1. If user count == 0, the first signup **must** use `BB_OWNER_EMAIL` (default: `mferragamo@danpack.com`)
2. If signup email ≠ owner email → **403 Forbidden**: "The owner account must be created with {OWNER_EMAIL}"
3. First user automatically assigned role: **owner**
4. All subsequent signups are gated by `SystemSettings.open_signup` (default: False)
5. If open_signup is False → **403 Forbidden**: "Signup is currently disabled"

### 10.3 Signup Validation

| Field | Constraint |
|-------|-----------|
| Email | 3–255 chars, regex `^[^@\s]+@[^@\s]+\.[^@\s]+$`, normalized to lowercase |
| Password | 8–128 chars, no complexity requirements |
| Display name | 1–255 chars |

### 10.4 Login Flow

1. Email normalized to lowercase
2. User must exist AND `is_active == True`
3. Password verified against bcrypt hash
4. Invalid → **401**: "Invalid email or password" (generic, prevents email enumeration)
5. JWT token created with session record
6. Cookie set on response

### 10.5 JWT Token Details

| Property | Value |
|----------|-------|
| Algorithm | HS256 |
| Secret key | `secrets.token_hex(32)` (64 chars) generated at startup, or from config |
| Claims | sub (user.id), email, role, jti (16-byte hex), iat, exp |
| Expiry | 24 hours |
| Cookie name | `bb_session` |
| Cookie HttpOnly | True |
| Cookie Secure | Auto-detected (True if HTTPS, False if HTTP) |
| Cookie SameSite | Lax |
| Cookie Max-Age | 86,400 seconds (24 hours) |
| Cookie Path | `/` |

Token extraction priority: Cookie first, then `Authorization: Bearer` header.

### 10.6 Session Management

- Each token has a unique JTI (JWT ID), SHA256 hashed and stored in `user_sessions`
- Multiple active sessions per user allowed
- Every request validates: token exists, JTI hash matches active session, not revoked, not expired
- HTML requests (Accept: text/html) get 307 redirect to /auth/login on failure
- API requests get 401 JSON response

### 10.7 Rate Limiting

- **Algorithm**: Sliding window using `time.monotonic()`
- **Limit**: 10 requests per 60 seconds per client IP
- **Applies to**: signup, login, password reset endpoints
- **Exceeded response**: 429 with "Too many requests. Please try again later."
- Expired hits evicted on each check

### 10.8 Password Reset

1. `POST /auth/api/reset-request` — always returns 200 (prevents email enumeration)
2. Token generated: `secrets.token_urlsafe(32)`, SHA256 hash stored
3. Token expiry: **1 hour**
4. Reset URL: `{scheme}://{host}/auth/reset?token={raw_token}`
5. Email sent via SMTP (best-effort, 15-second timeout)
6. `POST /auth/api/reset-confirm` — validates token, updates password, revokes all sessions
7. Token marked `used=True` (single use)

### 10.9 Session Revocation Triggers

- User deactivation → all sessions revoked
- Admin password reset → all sessions revoked
- Logout → specific session revoked
- Password reset → all sessions revoked
- Automatic cleanup: APScheduler hourly job revokes expired sessions

---

## 11. Admin Panel

### 11.1 Admin Capabilities by Role

| Action | Owner | Admin | Manager/User |
|--------|:-----:|:-----:|:------------:|
| List all users | Yes | Yes | No |
| Change user role | Yes (any) | Yes (non-owner, cannot promote to admin) | No |
| Deactivate user | Yes (any non-self) | Yes (non-admin, non-self) | No |
| Delete user | Yes (any non-self) | Yes (non-admin, non-self) | No |
| Reset user password | Yes (any non-self) | Yes (non-admin, non-self) | No |
| Transfer ownership | Yes | No | No |
| Toggle open signup | Yes | Yes | No |
| View audit log | Yes | Yes | No |

### 11.2 Ownership Transfer

- Only the current owner can initiate
- Target must have email == `BB_OWNER_EMAIL` and be active
- Cannot transfer to self
- Current owner demoted to "admin", target promoted to "owner"
- Logged in audit with both old and new owner IDs

### 11.3 Guards

- Cannot modify own role, deactivate self, or delete self
- Cannot modify/deactivate/delete the owner account (except via ownership transfer)
- Last admin guard: Cannot demote if only 1 active admin+owner remains
- Audit log: Last 100 entries, ordered by created_at DESC

---

## 12. Inventory Management

### 12.1 Item Fields

| Field | Type | Constraints | Default |
|-------|------|------------|---------|
| name | string | 1–255 chars, required | — |
| sku | string | 1–100 chars, required, unique per user | — |
| description | string | unlimited | "" |
| quantity | int | ≥ 0 | 0 |
| unit | string | — | "each" |
| location | string | — | "" |
| category | string | — | "" |
| tags | string | comma-separated | "" |
| notes | string | — | "" |
| barcode_type | string | valid zxing-cpp format | "Code128" |
| barcode_value | string | unique per user, auto-generated if empty | `BB-{SKU.upper()}-{6_hex}` |
| min_quantity | int | ≥ 0, triggers low-stock alerts | 0 |
| cost | float | nullable, null = no costing | null |
| status | string | "active" or "archived" | "active" |

### 12.2 Auto-Generation

If barcode_value is empty on creation: `BB-{SKU.upper()}-{uuid_hex_6_chars_uppercase}`

### 12.3 Stock Adjustments

```
POST /api/inventory/{item_id}/adjust
{ "quantity_change": int, "reason": string, "notes": string }
```

- Quantity change can be positive or negative
- Result must be ≥ 0 (returns 400 if negative)
- Creates immutable `InventoryTransaction` record
- Reasons: received, sold, adjusted, damaged, returned, initial

### 12.4 Bulk CSV Import

- Headers: name, sku, description, quantity, unit, location, category, tags, notes, barcode_value, barcode_type, min_quantity, cost
- Only name and sku required
- Max file size: **10 MB**
- Conflict handling: **Upsert by SKU** — existing SKU updates, new SKU creates
- If quantity changes on update: creates InventoryTransaction with reason="adjusted", notes="CSV import update"
- Encoding: UTF-8-sig or latin-1 detection
- Returns: `{created, updated, errors, message}`

### 12.5 Export

- CSV: `/api/inventory/export/csv` (active items, sorted by name ASC)
- CSV filtered: `/api/inventory/export/csv/filtered?status=&category=&location=`
- JSON: `/api/inventory/export/json?status=&category=&location=`
- JSON includes: export_date, total_items, items array

### 12.6 Bulk Operations

- **Bulk delete**: `POST /api/inventory/bulk/delete` — 1–500 item_ids
- **Bulk update**: `POST /api/inventory/bulk/update` — 1–500 item_ids, can update location, category, status, tags

### 12.7 Barcode Generation

- Types: Code128, QRCode, EAN13, Code39, DataMatrix, and all zxing-cpp formats
- Scale: 1–20 (default 4)
- Endpoint: `GET /api/inventory/{item_id}/barcode.png?scale=4`
- Preview: `GET /api/barcode/preview.png?value=TEXT&format=Code128&scale=4`
- Cache-Control: public, max-age=3600

### 12.8 Camera Scanning

- Uses native `BarcodeDetector` API (modern browsers)
- Video constraints: facingMode: "environment", ideal 1280×720
- Scan loop: **400ms** interval
- Multi-camera support via dropdown
- Lookup: searches barcode_value first, then SKU (exact match, active items only)
- Quick adjust available directly from scan page
- Stores up to 50 recent scans in memory

### 12.9 Calendar View

**Month view** (`GET /api/calendar?year=2024&month=4`):
- Per-day buckets: transaction count, received/sold/adjusted/damaged/returned counts, net_change, items touched, items created
- Colored dots for reason types: green (received), purple (sold), gold (adjusted), red (damaged)

**Day view** (`GET /api/calendar/day?date=2024-04-15`):
- All transactions for that day with item_name and item_sku resolved
- Items created that day

### 12.10 Analytics

**Transaction breakdown** (`GET /api/analytics/transactions?days=30`):
- Period: 1–365 days (default 30)
- by_reason: count per reason type
- by_reason_quantity: sum of ABS(quantity_change) per reason
- daily_trend: per-day aggregation

**Valuation** (`GET /api/analytics/valuation`):
- total_value = sum of (cost × quantity) for all active items
- Breakdown by category and location (items, quantity, value)
- Items without cost use 0 in value calculation

**Velocity** (`GET /api/analytics/velocity?days=30`):
- Top 20 items by transaction count
- total_volume = sum of ABS(quantity_change)

**Stock health** (`GET /api/analytics/stock-health`):
- Out of stock: quantity == 0
- Low stock: quantity ≤ min_quantity AND min_quantity > 0
- Overstocked: quantity > (min_quantity × 10) AND min_quantity > 0
- Healthy: everything else
- Shows top 20 items per category

### 12.11 Search and Filtering

```
GET /api/inventory?q=search&category=cat&location=loc&status=active&sort=updated_at&order=desc&limit=100&offset=0
```

- `q`: case-insensitive substring search across name, sku, barcode_value, location, tags
- `category`, `location`: exact match
- `status`: "active" or "archived" (default: all if empty)
- `sort`: any InventoryItem column (default: updated_at)
- `order`: "desc" or "asc" (default: desc)
- `limit`: 1–1000 (default 100)
- `offset`: pagination offset (default 0)

### 12.12 RBAC for Inventory

- Regular users: see own items only
- Managers: can view other users' items with `view_user` param
- Admins: can edit/delete other users' items

---

## 13. Analytics and Monitoring

### 13.1 Dashboard Pages

The web dashboard has 8 tabbed pages:

1. **Overview**: Hero cards (service health, latency percentiles, success rate ring, health score ring), KPI grid (7 cards: documents seen, succeeded, failed, incomplete, input backlog, avg completion, queue ETA)
2. **Documents**: Recent documents table (time, file, status, detail, duration), newest first
3. **Analytics**: 24-hour throughput bar chart (hourly), 14-day volume (daily), failure reasons, pipeline stages
4. **Quality**: Avg quality score ring, min/max/average metrics, quality issues table, barcode format distribution
5. **Achievements**: Error-free streak, throughput badge (Bronze/Silver/Gold), health score grade (A–F), milestones
6. **Service**: Service state table, queue state table, log info table
7. **Configuration**: Directory paths card grid

### 13.2 Stats Calculation from JSONL

- Reads all JSONL log files (gzip or plain) from log_path
- Groups by processing_id, classifies latest status per file
- Status: success (status="success" AND stage="output"), failure (status="failure" OR rejected), incomplete (no terminal outcome), service (lifecycle events)
- Latency: P50, P95, P99 from completion durations (success + failure events with duration_ms)
- 24h summary: documents, completed, succeeded, failed, incomplete in last 24 hours
- Queue state: counts files in input/, processing/, .journal/
- Worker health: latest heartbeat timestamp, heartbeat_age_seconds, lock file check

### 13.3 Health Score

Weighted from 4 components:
- 35% success rate
- 25% uptime (heartbeat freshness)
- 20% throughput
- 20% error trend

Grade: A (90–100), B (80–89), C (70–79), D (60–69), F (<60)

### 13.4 Prometheus Metrics

Endpoint: `GET /metrics` — standard Prometheus scrape format

### 13.5 Health Endpoint

`GET /health` — heartbeat-derived health status

---

## 14. Alerts and Notifications

### 14.1 Alert Types

| Type | Severity | Trigger |
|------|----------|---------|
| `out_of_stock` | critical | `item.quantity == 0` |
| `low_stock` | warning | `item.quantity ≤ item.min_quantity` AND `item.min_quantity > 0` |

### 14.2 Configuration

- Per-user alert type enablement in `AlertConfig` table
- Thresholds are per-item (`min_quantity` field on inventory item)
- Webhook URL is per-user, per-alert-type

### 14.3 Scheduled Check

- **Interval**: Every 5 minutes via APScheduler
- For each active user → for each active item → check both out_of_stock and low_stock
- **Duplicate prevention**: Skips if existing undismissed alert exists for same user + item + type
- Creates Alert record with title, message (includes quantities), item_id reference

### 14.4 Webhook Dispatch

- HTTP POST to configured webhook_url
- Timeout: **10 seconds**
- Payload: `{alert_type, severity, title, message, item_id, timestamp}`
- **No retry**. Single attempt, best-effort. Failures logged as warning.

### 14.5 Alert States

| is_read | is_dismissed | State | In badge count | Visible |
|---------|-------------|-------|:--------------:|:-------:|
| false | false | Unread | Yes | Yes |
| true | false | Read | No | Yes |
| false | true | Dismissed | No | No |
| true | true | Dismissed | No | No |

### 14.6 Alert Badge

- Polls `GET /api/alerts/count` every **30 seconds** (initial 2-second delay)
- Counts: `is_read=False AND is_dismissed=False`
- Red badge with count, animates with `badgePop` scale animation

### 14.7 Alert Endpoints

- List: `GET /api/alerts?unread_only=false&limit=50` (max 200)
- Count: `GET /api/alerts/count`
- Mark read: `POST /api/alerts/read` — sets is_read=True for selected IDs
- Dismiss: `POST /api/alerts/dismiss` — sets is_dismissed=True for selected IDs
- Dismiss all: `POST /api/alerts/dismiss-all` — dismisses all undismissed for user

---

## 15. Scan-to-PDF

### 15.1 User Flow

1. Visit `/scan-to-pdf` page
2. **Input** via three methods:
   - **Manual entry**: Type/paste barcode, press Enter or click Add
   - **Camera scanning**: Browser BarcodeDetector API, 400ms scan loop, 3-second duplicate suppression
   - **File upload**: Images (.png/.jpg/.jpeg/.tiff/.bmp) or PDFs, server decodes all barcodes
3. **Enrichment** (automatic): Each barcode looked up by barcode_value then SKU → returns name, sku, quantity, location, category
4. **Accumulation**: Session stored in browser localStorage (key: `stp_session`)
5. **Export**: Click "Export PDF" → POST to server → professional PDF downloaded

### 15.2 Barcode Decode (File Upload)

- Max file size: **50 MB**
- Images: PIL + zxingcpp decode
- PDFs: PyMuPDF renders each page as PNG at **300 DPI**, max **50 pages**
- Deduplication: same barcode value found across pages only included once

### 15.3 Enrichment Matching

Two-pass lookup per code:
1. `barcode_value = code` (exact match, active items, user-scoped)
2. `sku = code` (fallback if barcode not found)

Batch: 1–500 codes per request.

### 15.4 PDF Report Format

- A4 page (595 × 842 points), 50pt margins
- Header: Dark bar with title (18pt white) and timestamp (9pt gray)
- Operator line: `"Operator: {name} | Generated: {time} | Items: {count}"`
- Table columns: # (6%), Barcode Value (26%), Format (12%), Item Name (24%), Location (16%), Time (16%)
- Alternating row backgrounds, 20pt row height, 8pt font
- Text truncation: barcode 30 chars, name 28 chars, location 18 chars
- Summary bar: `"Total Scanned: N | Matched to Inventory: M | Unmatched: K"`
- Footer: `"BarcodeBuddy — Scan Report | Page N"` on every page
- Page breaks when within 50pt of bottom margin
- Filename: `{sanitized_title}_{YYYYMMdd-HHMMSS}.pdf`

### 15.5 Camera Duplicate Suppression

Same barcode within **3000ms** is ignored. Prevents rapid re-detection of stationary barcodes.

---

## 16. Team Management

### 16.1 Team Creation

- **Who can create**: Managers and above (require_manager decorator)
- **Fields**: name (1–255 chars), description (optional)
- Creator automatically becomes a **lead** member

### 16.2 Team Roles

| Role | Level | Capabilities |
|------|------:|-------------|
| lead | 30 | Manage team, add/remove members, create/assign tasks |
| member | 20 | Create tasks within team, update own task status |
| viewer | 10 | Read-only access |

Owner/admin can do anything on any team regardless of membership.

### 16.3 Permission Model

| Action | Lead | Member | Viewer | Owner/Admin |
|--------|:----:|:------:|:------:|:-----------:|
| View team | Yes | Yes | Yes | Yes (all teams) |
| Edit team | Yes | No | No | Yes |
| Delete team | No | No | No | Yes |
| Add members | Yes | No | No | Yes |
| Remove members | Yes* | No | No | Yes |
| Create tasks | Yes | Yes | No | Yes |
| Update any task | Yes | No | No | Yes |
| Update own assigned task status | Yes | Yes | No | Yes |
| Delete tasks | Yes | No | No | Yes |

*Last lead cannot remove themselves unless owner/admin.

### 16.4 Task Fields

| Field | Type | Options | Default |
|-------|------|---------|---------|
| title | string | 1–500 chars | required |
| description | string | unlimited | "" |
| assigned_to | string | user_id (must be team member) | null |
| status | string | todo, in_progress, done, blocked | todo |
| priority | string | low, medium, high, urgent | medium |
| due_date | datetime | ISO string with Z suffix | null |

### 16.5 Cross-Team Visibility

- Regular users: see only teams they're members of
- Owner/admin: see all teams
- Available users endpoint (`GET /api/available-users`): returns all active users for adding

---

## 17. AI Integration

### 17.1 Setup Wizard

4-step progressive configuration of singleton `AIConfig` (id=1):

1. **choose_mode**: Select local (Ollama), cloud (Anthropic/OpenAI), or hybrid
   - Local: ollama_enabled=True, all providers set to "local"
   - Cloud: cloud_enabled=True, all providers set to "cloud"
   - Hybrid: both enabled; chat/csv/suggest → "local", vision → "cloud"

2. **ollama_url**: Set Ollama base URL (default: `http://localhost:11434`)
   - Validated via `POST /api/check-ollama` health check

3. **ollama_model**: Set chat model (default: "llama3.2") and vision model (default: "llava")
   - `POST /api/pull-model` downloads models (600-second timeout)

4. **cloud_config**: Set cloud provider, API key (encrypted), models
   - `POST /api/test-cloud` verifies key by sending "Hi" with max_tokens=10

5. **complete**: Sets ai_enabled=True, setup_completed=True
   - Or **skip**: Sets ai_enabled=False, can return later

Config cached with **60-second TTL**, invalidated on any update.

### 17.2 Provider Routing

Each AI task type routes to a specific provider:

| Task Type | Default Provider |
|-----------|-----------------|
| chat | local (Ollama) |
| vision | cloud (Anthropic/OpenAI) |
| csv_cleanup | local |
| inventory_suggest | local |

**Fallback chain**: If primary provider fails, automatically tries the opposite (local ↔ cloud). User never sees which provider responded.

### 17.3 API Key Encryption

- **Method**: Fernet (symmetric, authenticated encryption)
- **Key derivation**: `SHA256("barcode-buddy-ai-" + app_secret_key)` → base64 URL-safe encoded
- **Storage**: `cloud_api_key_encrypted` column (TEXT)
- **Exposure**: Frontend only sees boolean `cloud_api_key_set`, never the actual key

### 17.4 Rate Limiting

- **Limit**: 30 requests per minute per user (from `AIConfig.max_requests_per_minute`)
- **Window**: 60 seconds, reset-based (not sliding)
- **Exceeded**: HTTP 429 "Too many messages. Please wait a moment."

### 17.5 Chat Flow

1. Validate: message not empty, ≤ 2000 chars, rate limit check, AI enabled
2. Create or fetch conversation (title = first 60 chars of first message)
3. Save user message immediately
4. Build message array: system prompt + all historical user/assistant turns
5. **Tool-calling loop** (max 4 rounds, rounds 0–3):
   - Rounds 0–2: Send with tool definitions, AI can call tools
   - Round 3: Send without tools, forces text-only response
   - Each tool call executed, result appended as "tool" role message
   - Loop continues until AI responds without tool calls or round 3 reached
6. Save assistant response with model_used and provider_used

### 17.6 All 11 Chatbot Tools

| Tool | Parameters | What It Returns |
|------|-----------|----------------|
| query_inventory | search, category, location, low_stock_only, limit (max 50) | Matching items with name, sku, quantity, unit, location, category, cost |
| get_inventory_stats | none | total_items, total_quantity, total_value, low_stock_count, out_of_stock_count, categories, locations |
| get_processing_stats | days (max 90) | total_documents, completed, succeeded, failed, success_rate, avg_completion_seconds, latency p50/p90 |
| get_recent_activity | category, search, days (max 90), limit (max 50) | Matching activity entries with action, category, summary, user_name |
| get_alerts_summary | none | total_active, unread_count, by_type, recent_alerts (top 10) |
| get_item_history | item_name or sku, limit (max 50) | Item info + transaction history |
| get_transaction_analytics | days (max 365) | total_transactions, by_reason with count and total_volume |
| get_inventory_valuation | none | total_value, items_with/without_cost, value_by_category, value_by_location |
| get_top_movers | days (max 365), limit (max 20) | Top items by transaction_count with total_volume |
| get_stock_health | none | out_of_stock, low_stock, overstocked (qty > min_qty × 3), healthy counts + items |
| get_system_health | none | service_status, last_heartbeat, queue state, health_score, health_grade, latency |

### 17.7 CSV Preview

- `POST /api/csv-preview` with columns + sample_rows (first 5 rows)
- AI maps each CSV column to closest system column
- Temperature: **0.1** (very deterministic)
- Returns: `{mapping: {csv_col: system_col}}`

### 17.8 Item Suggestion

- `POST /api/suggest-item` with name, sku, field
- Fields: "category" (suggests from existing), "location" (suggests from existing), "min_quantity" (suggests from similar items, default 10)
- Temperature: **0.2**
- Returns: `{suggestion, field}`

### 17.9 Conversation Management

- Create: implicit on first chat message (title = first 60 chars + "..." if longer)
- List: `GET /api/conversations?limit=50` (1–100, default 50), newest first
- Retrieve: `GET /api/conversations/{id}` — user/assistant messages only
- Delete: `DELETE /api/conversations/{id}` — cascade deletes all messages
- User isolation: each user only sees their own conversations

### 17.10 Privacy Page

Shows color-coded status badge:
- Green: "All AI is Local" (Ollama only)
- Amber: "Cloud AI Active" (Cloud only)
- Blue: "Hybrid — Local + Cloud"
- Gray: "AI Not Configured"

SVG data flow diagram showing exactly where data goes. Table documenting what data is sent for each AI feature.

---

## 18. Activity and Audit Log

### 18.1 Activity Categories

| Category | Color | Background |
|----------|-------|-----------|
| inventory | #3b82f6 (blue) | #1e3a5f |
| auth | #a78bfa (purple) | #2e1f5e |
| admin | #f59e0b (amber) | #422006 |
| scan | #10b981 (green) | #064e3b |
| import | #06b6d4 (cyan) | #164e63 |
| export | #8b5cf6 (violet) | #2e1065 |
| alert | #ef4444 (red) | #450a0a |
| system | #64748b (slate) | #1e293b |

### 18.2 Activity Logging

Any route can call `log_activity(db, user, action, category, summary, detail, item_id)`. Creates record and commits immediately.

### 18.3 Activity Endpoints

- List: `GET /api/activity?category=&q=&days=30&limit=100&offset=0`
  - category: exact match filter
  - q: case-insensitive substring search across summary and action
  - days: 1–365 (default 30)
  - limit: 1–500 (default 100)
- Stats: `GET /api/activity/stats` — today count, week count, total, week_by_category breakdown
- Recent: `GET /api/activity/recent?limit=20` (1–50) — latest N entries, no time filter

### 18.4 Audit Log (Admin)

Separate from activity log. Records admin-specific actions:
- role_change, deactivate_user, activate_user, delete_user, admin_reset_password, transfer_ownership, update_signup
- Stored in `audit_log` table with actor_id, action, target_id, detail (JSON)
- Endpoint: `GET /admin/api/audit-log` — last 100 entries
- No retention policy (persists indefinitely)

---

## 19. Layout and UI System

### 19.1 Navigation Structure

Fixed sidebar (230px, collapses to 64px), 4 main sections:

1. **Inventory**: Scan, Scan to PDF, Items, Calendar, New Item, Import CSV
2. **Monitor**: Dashboard, Analytics, Activity Log, Alerts
3. **AI**: AI Chat, Privacy & Data, AI Settings, AI Setup
4. **System**: Team, Admin Panel

Active item: golden left accent bar (3px, #e8a04c)

### 19.2 Color Scheme (CSS Variables)

| Variable | Value | Usage |
|----------|-------|-------|
| --bg | #f0ebe3 | Warm beige page background |
| --sidebar-bg | #1e2530 | Dark gray sidebar |
| --paper | rgba(255,251,245,0.92) | Off-white content cards |
| --panel | rgba(255,255,255,0.82) | White panels |
| --text | #1a1f26 | Primary text |
| --muted | #68737d | Secondary text |
| --success | #1a7a54 | Green |
| --failure | #c0392b | Red |
| --warning | #b8860b | Golden |
| --info | #2472a4 | Blue |
| --radius | 16px | Border radius |

### 19.3 Toast Notifications

- Container: fixed bottom-right, z-index 9999
- Types: success (green), error (red), info (blue), warning (gold)
- Animation: 0.3s ease in, 0.25s ease out
- Auto-dismiss: **3500ms** default
- Backdrop blur 12px, box shadow

### 19.4 Floating Chat FAB

- Position: fixed bottom-right (24px margin)
- Size: 56px circular, background #885529
- Hover: scale 1.08, shadow
- Opens: 400px-wide chat panel, full height

### 19.5 Responsive Behavior

- Desktop (>900px): full sidebar, main content margin-left 230px
- Mobile (≤900px): sidebar hidden, hamburger menu top-left, overlay with backdrop blur

### 19.6 Component Library

- `.panel`: white card, 20px padding, border
- `.kpi`: stat card with accent left border
- `.hero-card`: large stat display with gradient background
- `.ring-chart`: SVG circular progress indicator
- `.btn`, `.btn-primary`, `.btn-success`, `.btn-danger`
- `.badge`, `.br` (red), `.by` (yellow), `.bg` (green)
- `.fg` (form group), `.fr` (2-col form grid), `.fr3` (3-col)
- Command palette: Ctrl+K, searches pages and sections

---

## 20. Dashboard and Stats Engine

### 20.1 Stats Calculation

Built from JSONL log files:
- Reads all `.jsonl` and `.jsonl.gz` files from log_path
- Groups events by processing_id
- Classifies latest status: success, failure, incomplete, service

### 20.2 Latency Percentiles

| Percentile | Calculation |
|-----------|-------------|
| P50 | 50th percentile of completion_durations |
| P95 | 95th percentile |
| P99 | 99th percentile |

Only from events with duration_ms (success + failure).

### 20.3 Queue State

- Input backlog: file count in input_path
- Processing: file count in processing_path (excluding .journal)
- Journals: file count in .journal/
- Oldest input age: max age of files in input_path

### 20.4 Worker Health

- From latest heartbeat/startup service event
- heartbeat_age_seconds = now - last_heartbeat_timestamp
- Status derived from: heartbeat age, lock file existence, latest event type
- Counts startups/shutdowns in last 24 hours

### 20.5 Daily History

14-day rolling window (configurable via `--history-days`): per-day success/failure/incomplete/total counts.

### 20.6 Achievement System

- Error-free streak: consecutive days with zero failures
- Throughput badges: named tiers based on total succeeded documents
- Health score: weighted grade A–F (35% success rate, 25% uptime, 20% throughput, 20% error trend)

---

## 21. Database Schema

SQLite with WAL mode. 16 tables, 142 columns total.

### 21.1 Tables

| # | Table | Columns | Purpose |
|---|-------|--------:|---------|
| 1 | users | 8 | User accounts with roles |
| 2 | user_sessions | 6 | JWT session tracking (token hash, expiry, revocation) |
| 3 | password_reset_tokens | 6 | Email reset flow (token hash, expiry, used flag) |
| 4 | inventory_items | 18 | Stock items (name, SKU, quantity, barcode, cost, location, category) |
| 5 | inventory_transactions | 8 | Quantity change audit trail (change, after, reason, notes) |
| 6 | audit_log | 6 | Admin action log (actor, action, target, detail) |
| 7 | alert_configs | 7 | Per-user alert enablement and webhook URLs |
| 8 | alerts | 10 | Triggered alert instances (type, severity, read/dismissed state) |
| 9 | activity_log | 8 | Unified cross-system activity trail |
| 10 | teams | 6 | Team definitions |
| 11 | team_members | 6 | Team membership with roles |
| 12 | team_tasks | 11 | Tasks with priority, status, due dates, assignment |
| 13 | ai_config | 20 | AI provider settings, encryption, setup state (singleton id=1) |
| 14 | chat_conversations | 5 | Chat session metadata |
| 15 | chat_messages | 9 | Chat message history (role, content, tool_calls, provider) |
| 16 | system_settings | 3 | Global settings (open_signup) (singleton id=1) |

### 21.2 Key Relationships

- User → UserSession (CASCADE delete)
- User → InventoryItem (CASCADE delete) → InventoryTransaction (CASCADE delete)
- User → InventoryTransaction (SET NULL on user delete)
- User → AuditLog (SET NULL)
- Team → TeamMember (CASCADE delete)
- Team → TeamTask (CASCADE delete)
- ChatConversation → ChatMessage (CASCADE delete)

### 21.3 Indexes

- users: email (unique)
- user_sessions: token_hash (unique), user_id
- password_reset_tokens: token_hash (unique)
- inventory_items: user_id, sku, barcode_value
- inventory_transactions: item_id
- audit_log: actor_id, created_at
- alerts: user_id
- alert_configs: user_id
- activity_log: user_id, action, category, created_at, item_id
- team_members: team_id, user_id
- team_tasks: team_id, assigned_to
- chat_conversations: user_id
- chat_messages: conversation_id

### 21.4 Automated Jobs (APScheduler)

| Job | Schedule | Action |
|-----|----------|--------|
| Database backup | Cron 00:15 UTC daily | SQLite native backup to `logs/backups/`, keeps 14 rolling |
| Session cleanup | Interval every 1 hour | Revoke expired sessions (is_revoked=True where expires_at ≤ now) |
| Stock alert check | Interval every 5 minutes | Check all items for all users, create alerts, fire webhooks |

---

## 22. Deployment

### 22.1 Windows PowerShell Launcher (start-app.ps1)

1. Detects Cloudflare Tunnel config at `.cloudflared/barcodebuddy.yml`
2. If DNS CNAME for `app.danpack.com` → cfargotunnel.com: **Named Tunnel** (permanent URL `https://app.danpack.com`)
3. Otherwise: **Quick Tunnel** (temporary `*.trycloudflare.com` URL, scraped from stderr)
4. Runs app via `py -3.12 stats.py --host 0.0.0.0 --port 8080`
5. **Auto-restart loop**: every 10 seconds checks if app or tunnel process has exited → restarts
6. Tunnel URL saved to `tunnel-url.txt`

### 22.2 Windows Autostart (install-autostart.ps1)

Creates Windows Scheduled Task "BarcodeBuddy":
- Trigger: AtLogon for current user
- Action: `powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "start-app.ps1"`
- Settings: AllowStartIfOnBatteries, DontStopIfGoingOnBatteries, StartWhenAvailable
- RestartInterval: 1 minute, RestartCount: 999
- ExecutionTimeLimit: 0 (no limit)
- RunLevel: Highest (Administrator)

### 22.3 Docker

- Base: `python:3.12-slim`
- System deps: libgl1, libglib2.0-0, libgomp1
- Creates non-root `appuser`
- Healthcheck: every 30s, 10s timeout, 15s start period, 3 retries → checks `http://localhost:8080/health`
- Entrypoint: `python stats.py --host 0.0.0.0 --port 8080`

### 22.4 Railway

- `Procfile`: `web: python stats.py --host 0.0.0.0 --port $PORT`
- `railway.toml`: Python 3.12, pip install

### 22.5 CLI Options (stats.py)

| Option | Default | Description |
|--------|---------|-------------|
| `--host` | 0.0.0.0 | Bind address |
| `--port` | 8080 | Bind port |
| `--refresh-seconds` | 15 | Browser auto-refresh interval |
| `--history-days` | 14 | Daily buckets shown |
| `--recent-limit` | 25 | Recent documents shown |

---

## 23. Test Suite

174 tests across 12 modules, all passing.

Run command: `py -3.12 -B -m pytest tests/ -x -q`

**Known warnings** (non-blocking):
- 334 deprecation warnings: FastAPI `on_event` → should migrate to lifespan handlers; httpx/starlette per-request cookies deprecated
- JWT key length warning: test secret is 27 bytes (below 32-byte RFC 7518 minimum)

**Not yet covered by tests**: AI routes, team routes, activity module.

---

## 24. All HTTP Endpoints

### Auth (10 endpoints)

| Method | Path | Auth | Purpose |
|--------|------|:----:|---------|
| GET | /auth/login | No | Login page |
| GET | /auth/signup | No | Signup page |
| GET | /auth/reset-request | No | Reset request page |
| GET | /auth/reset | No | Reset confirm page |
| POST | /auth/api/signup | No | User registration |
| POST | /auth/api/login | No | User authentication |
| POST | /auth/api/logout | User | User logout |
| POST | /auth/api/reset-request | No | Password reset request |
| POST | /auth/api/reset-confirm | No | Password reset confirm |
| GET | /auth/api/me | User | Current user info |

### Admin (10 endpoints)

| Method | Path | Auth | Purpose |
|--------|------|:----:|---------|
| GET | /admin | Admin | Admin dashboard page |
| GET | /admin/api/users | Admin | List all users |
| PUT | /admin/api/users/{id}/role | Admin | Change user role |
| PUT | /admin/api/users/{id}/active | Admin | Toggle user active |
| DELETE | /admin/api/users/{id} | Admin | Delete user |
| PUT | /admin/api/users/{id}/password | Admin | Admin password reset |
| POST | /admin/api/transfer-ownership | Owner | Transfer ownership |
| GET | /admin/api/settings | Admin | Get system settings |
| PUT | /admin/api/settings/signup | Admin | Toggle open signup |
| GET | /admin/api/audit-log | Admin | Get audit log |

### Inventory API (27 endpoints)

| Method | Path | Auth | Purpose |
|--------|------|:----:|---------|
| GET | /api/inventory | User | List items (search, filter, sort, paginate) |
| POST | /api/inventory | User | Create item |
| GET | /api/inventory/{id} | User | Get item + last 50 transactions |
| PUT | /api/inventory/{id} | User | Update item |
| DELETE | /api/inventory/{id} | User | Delete item |
| POST | /api/inventory/{id}/adjust | User | Stock quantity adjustment |
| GET | /api/inventory/categories | User | List categories |
| GET | /api/inventory/locations | User | List locations |
| GET | /api/inventory/summary | User | Inventory summary stats |
| GET | /api/inventory/{id}/barcode.png | User | Generate barcode image |
| GET | /api/barcode/preview.png | User | Barcode preview |
| GET | /api/barcode/formats | User | List barcode formats |
| GET | /api/scan/lookup | User | Scan barcode lookup |
| GET | /api/calendar | User | Calendar month view |
| GET | /api/calendar/day | User | Calendar day detail |
| GET | /api/inventory/export/csv | User | Export all as CSV |
| GET | /api/inventory/export/json | User | Export all as JSON |
| GET | /api/inventory/export/csv/filtered | User | Export filtered CSV |
| POST | /api/inventory/import/json | User | Import from JSON |
| POST | /api/inventory/import/csv | User | Import from CSV |
| POST | /api/inventory/bulk/delete | User | Bulk delete (1–500) |
| POST | /api/inventory/bulk/update | User | Bulk update (1–500) |
| GET | /api/analytics/transactions | User | Transaction analytics |
| GET | /api/analytics/valuation | User | Inventory valuation |
| GET | /api/analytics/velocity | User | Stock velocity |
| GET | /api/analytics/stock-health | User | Stock health distribution |

### Inventory Pages (8 endpoints)

| Method | Path | Auth | Purpose |
|--------|------|:----:|---------|
| GET | /inventory | User | Inventory list page |
| GET | /inventory/new | User | New item form |
| GET | /inventory/import | User | Import page |
| GET | /inventory/bulk | User | Bulk operations page |
| GET | /inventory/{id} | User | Item detail page |
| GET | /scan | User | Camera scan page |
| GET | /calendar | User | Calendar page |
| GET | /analytics | User | Analytics dashboard page |

### Alerts (8 endpoints)

| Method | Path | Auth | Purpose |
|--------|------|:----:|---------|
| GET | /alerts | User | Alerts page |
| GET | /api/alerts | User | List alerts |
| GET | /api/alerts/count | User | Unread alert count |
| POST | /api/alerts/read | User | Mark alerts as read |
| POST | /api/alerts/dismiss | User | Dismiss alerts |
| POST | /api/alerts/dismiss-all | User | Dismiss all alerts |
| GET | /api/alerts/config | User | Get alert config |
| PUT | /api/alerts/config | User | Update alert config |

### Activity (4 endpoints)

| Method | Path | Auth | Purpose |
|--------|------|:----:|---------|
| GET | /activity | User | Activity page |
| GET | /api/activity | User | Activity log (filtered, paginated) |
| GET | /api/activity/recent | User | Recent activity (latest N) |
| GET | /api/activity/stats | User | Activity statistics |

### AI (19 endpoints)

| Method | Path | Auth | Purpose |
|--------|------|:----:|---------|
| GET | /ai/setup | Owner | Setup wizard page |
| GET | /ai/chat | User | Chat interface page |
| GET | /ai/privacy | User | Privacy/data page |
| GET | /ai/settings | Admin | AI settings page |
| GET | /api/ai/status | User | AI system status |
| GET | /api/ai/config | Admin | AI configuration |
| POST | /api/ai/config | Owner | Update AI config |
| POST | /api/ai/setup-step | Owner | Setup wizard step |
| POST | /api/ai/check-ollama | Owner | Check Ollama availability |
| POST | /api/ai/pull-model | Owner | Download Ollama model |
| GET | /api/ai/models | User | List available models |
| POST | /api/ai/test-cloud | Owner | Test cloud API key |
| POST | /api/ai/chat | User | Send chat message |
| GET | /api/ai/conversations | User | List conversations |
| GET | /api/ai/conversations/{id} | User | Get conversation |
| DELETE | /api/ai/conversations/{id} | User | Delete conversation |
| POST | /api/ai/suggest-item | User | AI item suggestion |
| POST | /api/ai/csv-preview | User | CSV column mapping |
| POST | /api/ai/recover-scan | User | AI scan recovery |

### Teams (13 endpoints)

| Method | Path | Auth | Purpose |
|--------|------|:----:|---------|
| GET | /teams | User | Teams page |
| POST | /api/teams | Manager | Create team |
| GET | /api/teams | User | List teams (scoped) |
| GET | /api/teams/{id} | User | Get team details |
| PUT | /api/teams/{id} | Lead/Admin | Update team |
| DELETE | /api/teams/{id} | Admin | Delete team |
| POST | /api/teams/{id}/members | Lead/Admin | Add member |
| PUT | /api/teams/{id}/members/{mid} | Lead/Admin | Update member role |
| DELETE | /api/teams/{id}/members/{mid} | Lead/Admin | Remove member |
| POST | /api/teams/{id}/tasks | Lead/Member | Create task |
| PUT | /api/teams/{id}/tasks/{tid} | Lead/Assignee | Update task |
| DELETE | /api/teams/{id}/tasks/{tid} | Lead/Admin | Delete task |
| GET | /api/available-users | Manager | List active users |

### Scan-to-PDF (4 endpoints)

| Method | Path | Auth | Purpose |
|--------|------|:----:|---------|
| GET | /scan-to-pdf | User | Scan-to-PDF page |
| POST | /api/scan-to-pdf/decode | User | Decode barcodes from file |
| POST | /api/scan-to-pdf/enrich | User | Enrich codes with inventory |
| POST | /api/scan-to-pdf/generate | User | Generate PDF report |

### System (2 endpoints)

| Method | Path | Auth | Purpose |
|--------|------|:----:|---------|
| GET | /metrics | No | Prometheus metrics |
| GET | /health | No | Health check |

**Total: 95 endpoints** (+ dashboard HTML pages served from stats.py)

---

## 25. All Numeric Constants

### Processing Pipeline

| Constant | Value |
|----------|-------|
| File stability delay | 2000ms (min 500) |
| Poll interval | 500ms (min 100) |
| File stability timeout | 10,000ms |
| File lock retries | 5 |
| File lock retry interval | 0.5s |
| Max file size (ingestion) | 50 MB |
| Max processing duration | 15,000ms |
| Heartbeat interval | 30s |
| Barcode scan DPI | 300 (min 72) |
| Max pages scan | 50 (min 1) |
| Barcode value regex | `^[A-Za-z0-9_-]{4,64}$` |

### Authentication

| Constant | Value |
|----------|-------|
| JWT expiry | 24 hours |
| JWT algorithm | HS256 |
| Secret key size | 64 chars (32-byte hex) |
| Token JTI size | 16-byte hex (32 chars) |
| Cookie name | bb_session |
| Cookie max-age | 86,400 seconds |
| Cookie SameSite | lax |
| Password min | 8 chars |
| Password max | 128 chars |
| Email min/max | 3–255 chars |
| Display name min/max | 1–255 chars |
| Reset token size | 32-byte URL-safe |
| Reset token expiry | 1 hour |
| Rate limit (auth) | 10 req / 60s per IP |
| SMTP timeout | 15 seconds |
| Owner email default | mferragamo@danpack.com |

### Inventory

| Constant | Value |
|----------|-------|
| Item name max | 255 chars |
| SKU max | 100 chars |
| List limit max | 1000 |
| Bulk operation max | 500 items |
| Import file max | 10 MB |
| Transaction history | last 50 |
| Export preview rows | 50 |
| Stock health items shown | 20 per category |
| Velocity top items | 20 |
| Analytics max days | 365 |
| Barcode scale range | 1–20 |
| Overstocked threshold | quantity > min_quantity × 10 |

### Alerts

| Constant | Value |
|----------|-------|
| Check interval | 5 minutes |
| Alert list limit max | 200 |
| Webhook timeout | 10 seconds |
| Badge poll interval | 30 seconds |
| Badge initial delay | 2 seconds |

### Activity

| Constant | Value |
|----------|-------|
| Default time window | 30 days |
| Max time window | 365 days |
| List limit max | 500 |
| Recent limit max | 50 |
| Audit log limit | 100 entries |

### Scan-to-PDF

| Constant | Value |
|----------|-------|
| File size max | 50 MB |
| PDF pages scanned max | 50 |
| PDF render DPI | 300 |
| Entries per PDF max | 1000 |
| Title max | 200 chars |
| Codes per enrich max | 500 |
| Camera dup suppress | 3000ms |
| Scan loop interval | 400ms |
| Row text truncation | code 30ch, name 28ch, location 18ch |

### AI

| Constant | Value |
|----------|-------|
| Rate limit | 30 req/min per user |
| Message max | 2000 chars |
| Chat rounds max | 4 (rounds 0–3) |
| Max tokens default | 1024 |
| Conversation title | first 60 chars |
| Conversation list max | 100 |
| Model pull timeout | 600 seconds |
| Health check timeout | 5 seconds |
| Config cache TTL | 60 seconds |
| CSV preview temperature | 0.1 |
| Item suggest temperature | 0.2 |
| Chat temperature | 0.3 |

### Teams

| Constant | Value |
|----------|-------|
| Team name max | 255 chars |
| Task title max | 500 chars |

### UI

| Constant | Value |
|----------|-------|
| Toast auto-dismiss | 3500ms |
| Sidebar width | 230px (collapsed: 64px) |
| Mobile breakpoint | 900px |
| Chat panel width | 400px |
| Command palette | Ctrl+K |
| Border radius | 16px |

### Database Jobs

| Constant | Value |
|----------|-------|
| Backup schedule | 00:15 UTC daily |
| Backup retention | 14 rolling |
| Session cleanup | every 1 hour |
| Alert check | every 5 minutes |

---

## 26. What Is Not Built Yet

Sections 4.11–4.15 of the Product Blueprint. Sequenced in an 8-phase roadmap:

1. **Foundation gaps**: TIFF support, env var config overrides, wire alerting thresholds
2. **Scan Record Workbench**: Single-scan detail page with full lifecycle, notes, attachments, reprocessing
3. **Event truth and state store**: Freeze event schema, normalize JSONL into SQLite, append-only ledger
4. **Scan obligations**: Expected-scan creation, state machine (open → overdue → matched → closed), queue UI
5. **Report engine**: Hourly/shift/daily/quarterly reports, tomorrow forecast, immutable snapshots
6. **Planner screens**: Live overview, obligation queue, activity ledger, scan history
7. **External integration**: ERP bridge, webhook callbacks, upstream obligation import
8. **Extended**: Multi-document batch splitting, mobile capture, log shipping

---

## 27. What Is Explicitly Out of Scope

These are intentional boundaries, not missing features:

- **OCR-driven document inference** — routing key must come from a barcode, not guessed text
- **Scanner hardware control** — consumes files, does not drive scanners
- **ERP matching engine** — precedes ERP, does not replace it
- **Cloud-first architecture** — designed for single-node, local-filesystem deployment
- **Non-barcoded documents** — emailed invoices without routing barcodes belong elsewhere
- **Content hashing for deduplication** — duplicate detection is filename-based by design

---

## 28. Document Index

| Document | Purpose |
|----------|---------|
| `README.md` | User-facing install, run, and feature overview |
| `docs/PRODUCT_BLUEPRINT.md` | Master document: capability map, status, roadmap |
| `docs/COMPLETE_SYSTEM_REFERENCE.md` | This document |
| `docs/current-system-truth.md` | Builder starting point |
| `docs/danpack-builder-handoff.md` | Builder context and business decisions |
| `docs/danpack-system-interaction-philosophy.md` | UI and interaction design rules |
| `docs/production-operations-blueprint.md` | Production integration, observability, security |
| `docs/builder-execution-plan.md` | Implementation order |
| `docs/industry-workflow-research.md` | Research backing product decisions |
| `docs/packaging-industrial-operating-model.md` | Deployment patterns |
| `docs/scan-record-workbench.md` | Future scan workbench spec |
| `docs/scan-record-builder-handoff.md` | Scan workbench builder handoff |
| `docs/operations-planner-product-spec.md` | Planner product definition |
| `docs/operations-planner-technical-spec.md` | Planner technical architecture |
| `docs/operations-planner-builder-handoff.md` | Planner builder handoff |
| `docs/operations-planner-execution-plan.md` | Planner phased implementation |
| `TECHNICAL_ARCHITECTURE_SPECIFICATION.md` | Target-state architecture (not all implemented) |
| `config.schema.json` | Machine-readable config contract |
| `docs/runbooks/incident-response.md` | Production incident response |
