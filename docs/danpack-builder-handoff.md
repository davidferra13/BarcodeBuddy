# Danpack Builder Handoff

Last updated: 2026-04-05.

This document is the builder-facing source of truth for the current BarcodeBuddy repo state, the verified Danpack business context, and the recommended execution order for the next implementation pass.

Use this document together with the code as the primary handoff. Treat `TECHNICAL_ARCHITECTURE_SPECIFICATION.md` as target-state design guidance, not as a statement that all of that behavior already exists in the runtime.

The master product blueprint — full capability map, implementation status, and phased roadmap — is in:

- `docs/PRODUCT_BLUEPRINT.md`

New builder-facing interaction rules for any future UI, admin console, rejection review tool, or workflow surface are in:

- `docs/danpack-system-interaction-philosophy.md`

Production operating requirements and exact alert thresholds are in:

- `docs/production-operations-blueprint.md`

The ordered implementation sequence for the next builder is in:

- `docs/builder-execution-plan.md`

The primary production incident runbook is in:

- `docs/runbooks/incident-response.md`

Planner-specific builder handoff and contracts are in:

- `docs/operations-planner-product-spec.md`
- `docs/operations-planner-technical-spec.md`
- `docs/operations-planner-builder-handoff.md`
- `docs/operations-planner-execution-plan.md`
- `docs/contracts/report-snapshot.schema.json`
- `docs/contracts/scan-obligation.schema.json`

Builder-critical repository artifacts:

- `tests/`
- `config.schema.json`
- `docs/production-operations-blueprint.md`
- `docs/builder-execution-plan.md`
- `docs/runbooks/incident-response.md`
- `docs/operations-planner-product-spec.md`
- `docs/operations-planner-technical-spec.md`
- `docs/operations-planner-builder-handoff.md`
- `docs/operations-planner-execution-plan.md`
- `configs/config.receiving.example.json`
- `configs/config.shipping-pod.example.json`
- `configs/config.quality-compliance.example.json`

## 0. Builder Starting Point

The repo includes:

- 325 tests (0 warnings) in `tests/` covering ingestion pipeline and full web application
- workflow starter configs in `configs/`
- production operations blueprint in `docs/production-operations-blueprint.md`
- phased roadmap in `docs/PRODUCT_BLUEPRINT.md` Section 6
- constraint files in `.constraints/` (FSM, barcode, data safety, auth, AI privacy)

Start by reading `docs/PRODUCT_BLUEPRINT.md` for the full capability map and roadmap.

## 1. Current Runtime Truth

### 1.1 What the code actually does today

- `main.py` loads one JSON config file, configures structured logging, ensures the runtime directories exist, recovers stranded files from `data/processing` back to `data/input`, then starts monitoring the input directory via `watchfiles` with APScheduler-managed heartbeat.
- `stats.py` loads the same JSON config file and serves a read-only local stats page via FastAPI plus `/api/stats` and `/health` endpoints from the active log plus any local daily archives.
- The runtime is implemented as a single service class in `app/processor.py`.
- The service polls `input_path`, waits for file stability, claims the file by moving it to `processing_path`, scans for routing barcode candidates, validates the selected result, writes a PDF to `output_path/YYYY/MM`, or moves the source file to `rejected_path`.
- Every terminal and intermediate stage writes JSONL records to the active file `data/logs/processing_log.jsonl`, and prior days are archived locally as `data/logs/processing_log.YYYY-MM-DD.jsonl`.
- Rejected files receive a `.meta.json` sidecar with rejection context.
- Log events and rejection sidecars now include stable runtime metadata: `schema_version`, `workflow`, `host`, `instance_id`, `config_version`, and `error_code`.
- The worker acquires an exclusive per-workflow startup lock before recovery and polling begin.
- Claimed files are tracked in `processing/.journal` until a terminal outcome is logged or recovered.
- The worker emits service lifecycle events so `stats.py` can expose heartbeat-derived health, queue backlog, and recovery visibility.

### 1.2 Current supported behavior

- Supported inputs: `PDF`, `JPG`, `JPEG`, `PNG`
- Unsupported despite the architecture spec: `TIFF`
- Input type is verified by magic-byte validation before deep parser handoff, so extension spoofing now rejects as `UNSUPPORTED_FORMAT`
- Output format: `PDF` only
- Barcode engine: `zxing-cpp`
- PDF/image handling: `PyMuPDF` and `Pillow`
- Duplicate handling modes: `timestamp` and `reject`
- Barcode value filtering: optional regex allowlist via `barcode_value_patterns`
- Scan scope: first page only or full-document page-order scanning depending on `scan_all_pages`
- Barcode selection rule:
  - the best candidate across the scanned document wins deterministically by business-rule match, then largest bounding box area, then earlier page number, then scan order
  - `barcode_value_patterns` affect routing priority, but they do not create separate ambiguity or pattern-mismatch states
  - after barcode selection, the chosen barcode is rejected as `INVALID_BARCODE_FORMAT` if it fails business-rule matching or filename safety rules
  - barcode text must still satisfy filename safety rules: printable characters only, length `4..64`, and characters limited to alphanumeric, dash, and underscore
- Log identity: `processing_id` is UUIDv4
- Local observability surface: read-only stats page via `stats.py`
- Config contract artifact: `config.schema.json`
- Config safeguards: rejects unknown keys, requires distinct managed paths, and enforces same-volume managed paths
- Workflow identity: `workflow_key` is part of the config contract and should be explicit in deployed configs

### 1.3 Important hard constraints on the ingestion pipeline

These constraints apply to the hot-folder document processing pipeline (`main.py` / `app/processor.py`), not to the web application:

- No OCR
- No document classification
- No cloud storage integration
- No filename generation from anything other than a routable barcode
- No non-barcoded document inference

Note: the web application (`stats.py`) does include a SQLAlchemy + SQLite database, a full multi-user UI, write-capable APIs for inventory and team management, and an AI integration layer. These are separate from the ingestion pipeline constraints above.

### 1.4 Current module boundary in practice

**Ingestion pipeline modules:**

- `app/config.py`: Pydantic-based config loading with model validators, runtime directory creation
- `app/processor.py`: watchfiles-based watcher, processing orchestration, validation, duplicate handling, rejection handling, and logging payload assembly
- `app/documents.py`: file access checks, page counting, PDF rendering, file moves, PDF output writing
- `app/barcode.py`: OpenCV-based image preprocessing and barcode selection via zxing-cpp
- `app/logging_utils.py`: structlog configuration, fsync-backed JSONL append and atomic JSON writes
- `app/contracts.py`: canonical log field names, error codes, and stage/status constants

**Web application modules (stats.py):**

- `app/stats.py`: log aggregation plus HTML and JSON rendering for the local stats page
- `app/auth.py` / `app/auth_routes.py`: JWT cookie auth, bcrypt hashing, session management, RBAC
- `app/admin_routes.py`: user management, role changes, ownership transfer, system settings, audit log
- `app/inventory.py`: full CRUD, quantity adjustments, barcode generation, scan lookup, camera scanning, bulk import/export
- `app/alerts.py`: per-item stock alerts, severity, webhook dispatch, scheduled checks
- `app/scan_to_pdf.py`: barcode decode from uploads, inventory enrichment, PDF report generation
- `app/teams.py`: team CRUD, member management, task tracking
- `app/ai_routes.py` / `app/ai_provider.py` / `app/ai_tools.py`: hybrid AI (Ollama/Anthropic/OpenAI), chatbot with 11 tools, setup wizard
- `app/activity.py`: unified audit trail across all subsystems
- `app/feedback.py`: in-app bug reports, feature requests, questions (append-only JSONL)
- `app/layout.py`: shared navigation, sidebar, toast notifications
- `app/database.py`: SQLAlchemy models, SQLite WAL mode, all persistent state
- `app/image_quality.py`: image quality assessment for scan inputs

## 2. Reality Check Against The Architecture Spec

The architecture spec is materially ahead of the implementation. Builder work should start from the code, not from the assumption that the spec has already been realized.

| Area | Architecture Spec | Current Runtime | Builder Implication |
| --- | --- | --- | --- |
| Runtime boundaries | Separate watcher, processor, validator, output manager, logger | Most behavior is consolidated in `app/processor.py` | Do not assume module separation exists yet |
| File support | Includes `TIFF` | Only `PDF`, `JPG`, `JPEG`, `PNG` are supported | Do not build TIFF-dependent workflows without adding support first |
| IDs and models | UUIDv7 jobs, checksum-based document IDs, rich typed models | UUIDv4 `processing_id`, lightweight dataclasses, no checksum IDs | Use current IDs unless a deliberate migration is part of the task |
| Logging | Daily log files and broader event model | Active `processing_log.jsonl` plus local daily archives `processing_log.YYYY-MM-DD.jsonl` | Use the current local archive pattern as the baseline; do not assume off-host shipping or richer schemas exist yet |
| Config | JSON plus environment overrides and stricter validation | JSON file only, no env override layer, but unknown-key rejection and strict path validation are implemented | Use config files as the real control plane for now |
| Startup guarantees | Same-volume validation and singleton mutex | Same-volume managed-path validation and per-workflow startup locking are implemented | Treat one workflow config plus one managed folder set as one runtime boundary |
| Recovery model | Job journal and explicit state machine | Durable per-file journal in `processing/.journal` plus explicit recovery log records | Preserve the journal contract if you refactor recovery further |

## 3. Verified Danpack Business Context

### 3.1 What Danpack is

Danvers Industrial Packaging is a family-owned packaging engineering and industrial supply company founded in 1957 and based in Beverly, Massachusetts.

Verified first-party positioning from the public site:

- custom packaging design
- packaging testing and analysis
- vendor-managed inventory
- foam fabrication
- custom cases
- corrugated packaging
- crating and pallets
- UN hazardous packaging

Core industry pages confirm specific focus on:

- electronics
- medical
- military and aerospace
- ecommerce
- industrial products

### 3.2 What the site proves that matters to this system

The public site repeatedly describes an engineering workflow:

1. customer provides files or a physical sample
2. Danpack creates a CAD-based packaging design
3. Danpack prototypes and fit-checks
4. Danpack performs ISTA-style testing where needed
5. Danpack produces and replenishes packaging

That matters because BarcodeBuddy should be framed as operational document-routing infrastructure for Danpack's real workflows, not as a generic office scanner tool.

### 3.3 Public proof signals worth reusing

- ISTA-certified lab and testing claims
- ESD/electronics packaging positioning
- medical packaging references including temperature-controlled and clean-room-compliant packaging
- military/aerospace compliance positioning
- sustainability and REACH/RoHS references
- testimonials mentioning fast prototyping and tested packaging
- galleries, testimonials, and newsletter/blog infrastructure exposed in the sitemap but not fully surfaced in navigation

## 4. Danpack-Fit Operating Model For BarcodeBuddy

### 4.1 Recommended workflow split

Continue using the existing recommendation of one instance per workflow. For Danpack, the cleanest first operating model remains:

- `receiving`
- `shipping_pod`
- `quality_compliance`

### 4.2 Best-fit document classes

These are the most plausible Danpack document families for this barcode-first runtime:

- vendor packing slips tied to PO or receipt IDs
- proof-of-delivery and shipping paperwork tied to shipment or delivery IDs
- compliance and traceability documents that already carry a routable barcode
- hazardous-packaging support paperwork only if the document already includes a routable identifier

### 4.3 What should stay out of scope

- emailed invoices without barcodes
- multi-document mixed scan batches that need splitting
- engineering files and CAD assets
- documents that need OCR or classification to determine the correct record
- any workflow where Danpack staff expect the system to guess the routing identifier

### 4.4 Sensible default operating decisions until the owner provides sample documents

- `receiving`: prefer `duplicate_handling = "reject"`
- `shipping_pod`: prefer `duplicate_handling = "timestamp"`
- `quality_compliance`: prefer `duplicate_handling = "reject"`
- leave `barcode_value_patterns` empty until real Danpack barcode samples exist
- keep `barcode_scan_dpi = 300`
- keep `scan_all_pages = true` unless a workflow proves the barcode is always on page 1

Do not invent regex patterns for Danpack-specific IDs until sample paperwork confirms the actual formats.

### 4.5 Upstream capture assumptions that fit the current runtime

Current external research supports these assumptions:

- scan-to-folder remains a valid first-mile deployment pattern
- workflow-specific scan destinations are better than one mixed queue
- `PDF` at `300 DPI` or higher is the safest default capture profile
- `one file per scan` is the correct assumption for the current runtime
- TIFF support should stay out of scope until real Danpack devices require it

This repo should currently assume a workflow-specific MFP or desktop scan profile writing to the `input` folder, not direct device integration inside the Python runtime.

## 5. Public Data Already Available But Not Fully Used

### 5.1 High-value first-party data

- page sitemap with 23 indexed page URLs
- gallery sitemap with 9 indexed gallery URLs
- 3 live testimonial pages
- sustainability/compliance PDFs and letters
- news/blog/newsletter pages that indicate an existing but dormant content structure

### 5.2 Technical signals from the public website

- WordPress site with Yoast SEO and W3 Total Cache
- Google Tag Manager present
- some sitemap and canonical URLs still use `http://`
- homepage has only partial social metadata
- homepage does not expose JSON-LD structured data
- contact form is present but captures only `name`, `email`, `company`, and `message`

### 5.3 How the builder can use this

- use testimonials and gallery categories as future fixture and demo-story inputs
- use the industry pages as the source for Danpack-facing workflow naming and documentation language
- use the sitemap findings to avoid under-modeling Danpack as only a corrugated-box supplier
- use the technical SEO findings only as product-context input, not as part of the current Python runtime

## 6. Missing Data We Still Do Not Have

These are the most important unknowns. The builder should not hallucinate them.

- actual Danpack barcode formats by workflow
- sample scanned documents for receiving, POD, and compliance
- several real rejected or problematic documents per workflow
- real duplicate expectations by workflow
- final destination systems or records the documents need to attach to
- expected daily or monthly scan volume
- scanner or MFP model list, plus exact scan-profile exports if available
- scanner vendor behavior on Danpack's real network shares
- whether POD is mobile-first, scan-back, or mixed
- whether any workflow currently depends on TIFF

## 7. Verified Builder Baseline

The repo is production-hardened with comprehensive test coverage.

**Test suite:** 325 tests + 65 subtests, 0 warnings, verified at commit 8b646e0 (2026-04-05).

**Verification commands:**

- `py -3.12 -B -m pytest tests/ -x -q`
- `py -m compileall app tests main.py stats.py -q`

### 7.1 What the test suite covers

**Ingestion pipeline:**

- supported input conversion for `PNG`, `JPG`, `JPEG`, and `PDF`
- duplicate handling for both `reject` and `timestamp`
- rejection paths for `BARCODE_NOT_FOUND`, `INVALID_BARCODE_FORMAT`, `CORRUPT_FILE`, and `UNSUPPORTED_FORMAT`
- rejection sidecar contents and runtime metadata fields
- singleton startup locking
- deterministic best-candidate selection across later pages and multiple eligible values
- journal-backed startup recovery from `processing`
- lifecycle heartbeat events and health-aware stats snapshots
- config-loader rejection of unknown keys, distinct managed paths, same-volume enforcement
- file-stability readiness and lockout behavior
- stats snapshot aggregation and HTML rendering
- schema coverage for current config keys
- example config loading and workflow duplicate-policy defaults

**Web application:**

- auth: signup, login, logout, password reset, session management, RBAC, ownership transfer, zero-friction first-user signup
- inventory: CRUD, adjustments, barcode generation, scan lookup, bulk import/export, bulk actions
- alerts: stock alert configuration, threshold checks, webhook dispatch (with SSRF prevention)
- scan-to-PDF: barcode extraction, inventory enrichment, PDF generation
- teams: team CRUD, member management, task tracking
- AI: provider configuration, chatbot tool execution, conversation persistence
- activity: unified audit trail across subsystems
- feedback: bug reports, feature requests, question submission
- image quality: threshold logic, scoring, quality assessment
- contracts: error code stability, normalization
- documents: type detection, page counts, PDF conversion, file locking

### 7.2 What the workflow config templates currently provide

- `configs/config.receiving.example.json`
- `configs/config.shipping-pod.example.json`
- `configs/config.quality-compliance.example.json`

The intended workflow names remain:

- `receiving`
- `shipping_pod`
- `quality_compliance`

The filenames use hyphens only as filesystem-friendly config names, while the runtime `workflow_key` values use underscores.

## 8. Recommended Builder Execution Order

This is the safest dependency-aware order for the next implementation pass. Sections 4.1–4.10 of the Product Blueprint are complete. The roadmap below covers what remains.

The full phased roadmap is in `docs/PRODUCT_BLUEPRINT.md` Section 6. The summary here is for quick orientation.

### Phase 1: Foundation Gaps (independent, low-risk)

- TIFF input support (some scanners default to TIFF)
- Environment variable config overrides (containerized deployments)
- Wire alerting thresholds to external notification dispatch

### Phase 2: Scan Record Workbench

- Single-scan detail page with full processing lifecycle
- Notes, attachments, and external links on scan records
- Reprocessing and manual enrichment

Spec: `docs/scan-record-workbench.md`

### Phase 3: Event Truth and State Store

- Freeze event schema versioning
- Normalize JSONL scan events into SQLite state store
- Append-only activity event ledger for planner actions

Spec: `docs/operations-planner-execution-plan.md` Phase 1–2

### Phase 4: Scan Obligations

- Manual obligation creation with due windows
- Obligation state machine and overdue detection
- Obligation queue UI
- Imported obligations from upstream systems

Spec: `docs/operations-planner-execution-plan.md` Phase 3

### Phase 5: Report Engine + Planner Screens + External Integration

See `docs/PRODUCT_BLUEPRINT.md` Sections 6.5–6.7 for full details.

### Builder guardrails for all phases

- Keep the 325-test baseline passing before any refactor
- Extend tests before changing core routing behavior
- Treat the code as source of truth, not the architecture spec
- Do not widen the runtime into OCR or AI classification without an explicit product decision
- Do not create barcode regexes from guesswork — wait for real Danpack samples
- Prefer small reversible steps with tests before structural refactors

## 9. Builder Guardrails

- Do not widen the runtime into OCR or AI classification without an explicit product decision.
- Do not implement TIFF support unless Danpack actually needs it.
- Do not create barcode regexes from guesswork.
- Do not assume the architecture spec behavior already exists.
- Prefer small reversible steps with tests before structural refactors.

## 10. Primary First-Party Source Links

- https://www.danpack.com/
- https://www.danpack.com/services/custom-packaging-design/
- https://www.danpack.com/services/testing-analysis/
- https://www.danpack.com/services/vendor-managed-inventory/
- https://www.danpack.com/industries/electronics/
- https://www.danpack.com/industries/medical/
- https://www.danpack.com/industries/compliant-packaging/
- https://www.danpack.com/industries/industrial-products/
- https://www.danpack.com/industries/ecommerce/
- https://www.danpack.com/products/foam-fabrication/
- https://www.danpack.com/products/cases/
- https://www.danpack.com/products/un-hazardous-packaging/
- https://www.danpack.com/about-us/company-overview/
- https://www.danpack.com/about-us/sustainability/
- https://www.danpack.com/contact/
- https://www.danpack.com/testimonial/john-smith/
- https://www.danpack.com/testimonial/tony-silva/
- https://www.danpack.com/testimonial/greg-dulley/
- https://www.danpack.com/robots.txt
- https://www.danpack.com/sitemap.xml

## 11. Bottom Line For The Next Agent

BarcodeBuddy is a production-ready barcode-driven document ingestion and inventory management system. The ingestion pipeline (main.py) is a deterministic hot-folder service. The web application (stats.py) is a full multi-user FastAPI app with authentication, RBAC, inventory management, analytics, alerts, scan-to-PDF, team management, AI chatbot, activity audit trail, and in-app feedback — all verified by 325 tests with 0 warnings.

Danpack is a packaging-engineering business with multiple document families. All core capabilities (Sections 4.1–4.10) are complete. The next implementation work is the roadmap in `docs/PRODUCT_BLUEPRINT.md` Section 6: foundation gaps (TIFF, env overrides, alert wiring), then Scan Record Workbench, then the Operations Planner (event store, obligations, reports).

Any new UI surfaces must follow `docs/danpack-system-interaction-philosophy.md`. Any changes to the ingestion pipeline FSM, auth, or contracts require explicit approval per CLAUDE.md.
