# Danpack Builder Handoff

Last updated: 2026-04-03.

This document is the builder-facing source of truth for the current Barcode Buddy repo state, the verified Danpack business context, and the recommended execution order for the next implementation pass.

Use this document together with the code as the primary handoff. Treat `TECHNICAL_ARCHITECTURE_SPECIFICATION.md` as target-state design guidance, not as a statement that all of that behavior already exists in the runtime.

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

The repo now includes four execution anchors:

- baseline runtime tests in `tests/`
- workflow starter configs in `configs/`
- production operations blueprint in `docs/production-operations-blueprint.md`
- ordered builder plan in `docs/builder-execution-plan.md`

Start from those artifacts before widening the implementation.

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

### 1.3 Important hard constraints already enforced

- No OCR
- No document classification
- No database
- No external or write-capable API
- No operator workflow UI
- No cloud storage integration
- No filename generation from anything other than a routable barcode
- No non-barcoded document inference

### 1.4 Current module boundary in practice

- `app/config.py`: Pydantic-based config loading with model validators, runtime directory creation
- `app/processor.py`: watchfiles-based watcher, processing orchestration, validation, duplicate handling, rejection handling, and logging payload assembly
- `app/documents.py`: file access checks, page counting, PDF rendering, file moves, PDF output writing
- `app/barcode.py`: OpenCV-based image preprocessing and barcode selection via zxing-cpp
- `app/logging_utils.py`: structlog configuration, fsync-backed JSONL append and atomic JSON writes
- `app/contracts.py`: canonical log field names, error codes, and stage/status constants
- `app/stats.py`: log aggregation plus HTML and JSON rendering for the local stats page

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

That matters because Barcode Buddy should be framed as operational document-routing infrastructure for Danpack's real workflows, not as a generic office scanner tool.

### 3.3 Public proof signals worth reusing

- ISTA-certified lab and testing claims
- ESD/electronics packaging positioning
- medical packaging references including temperature-controlled and clean-room-compliant packaging
- military/aerospace compliance positioning
- sustainability and REACH/RoHS references
- testimonials mentioning fast prototyping and tested packaging
- galleries, testimonials, and newsletter/blog infrastructure exposed in the sitemap but not fully surfaced in navigation

## 4. Danpack-Fit Operating Model For Barcode Buddy

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

The repo is no longer in a pre-hardening state.

Already in place:

- fixture-based runtime tests in `tests/test_service_runtime.py`
- config-loader and path-constraint tests in `tests/test_config.py`
- stats aggregation tests in `tests/test_stats.py`
- config schema and example-config consistency tests in `tests/test_config_artifacts.py`
- workflow config templates in `configs/`
- README and builder docs that describe the Danpack-fit deployment split
- runtime support for `barcode_value_patterns`
- local read-only stats surface in `stats.py`

Verification already performed on the current repo state:

- `py -B -m unittest discover -s tests -v`
- `py -m compileall app tests main.py stats.py`
- `load_settings()` against the example workflow configs

### 7.1 What the test suite currently covers

- supported input conversion for `PNG`, `JPG`, `JPEG`, and `PDF`
- duplicate handling for both `reject` and `timestamp`
- rejection paths for `BARCODE_NOT_FOUND`, `INVALID_BARCODE_FORMAT`, `CORRUPT_FILE`, and `UNSUPPORTED_FORMAT`
- rejection sidecar contents
- runtime metadata fields in logs and rejection sidecars
- singleton startup locking
- deterministic best-candidate selection across later pages and multiple eligible values
- journal-backed startup recovery from `processing`
- lifecycle heartbeat events and health-aware stats snapshots
- config-loader rejection of unknown keys
- config-loader enforcement of distinct managed paths and same-volume managed paths
- file-stability readiness and lockout behavior
- stats snapshot aggregation and HTML rendering
- schema coverage for current config keys
- example config loading and workflow duplicate-policy defaults

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

This is the safest dependency-aware order for the next implementation pass from the repo's current state.

### Phase 1: Preserve the verified baseline

Prerequisite:

- treat the code as source of truth, not the architecture spec

Do now:

- keep the existing tests passing before any refactor
- extend tests before changing core routing behavior
- keep the example configs loading without manual edits

Why first:

- the runtime now has a useful regression harness
- later architectural changes should land against that harness rather than replacing it

### Phase 2: Lift observability and define retry policy

Prerequisite:

- verified baseline preserved

Deliverables:

- off-host log shipping and alert wiring
- backlog, latency, failure-rate, and restart telemetry
- explicit bounded retry policy for any retryable failure classes
- clearer distinction between recovery requeue, quarantine, and terminal rejection

Why second:

- Phase 1 and Phase 2 runtime hardening are already in place
- the next operational risk is visibility and retry policy, not another structural refactor

### Phase 3: Add targeted Danpack-specific extensions

Prerequisite:

- owner-provided sample documents or confirmed barcode formats

Deliverables:

- barcode regex rules per workflow
- realistic sample configs
- fixture samples that mirror Danpack documents
- clearer operational guidance for warehouse, shipping, and compliance staff
- optional ERP or record-validation rules if Danpack confirms the target systems

Why third:

- Danpack-specific hardening is impossible to do correctly without real document examples

### Phase 4: Break the monolith only where it buys something real

Prerequisite:

- spec delta understood
- tests covering current routing behavior

Deliverables:

- incremental extraction from `app/processor.py` only where the separation improves maintainability or new features
- no cosmetic module split without behavior-level value

Why fourth:

- the current service is small enough that a large refactor would be easy to overdo
- module extraction should follow verified pressure, not architecture aesthetics

### Phase 5: Apply the interaction philosophy only where a human-facing surface is justified

Prerequisite:

- Phase 1 through Phase 3 complete
- a real operator need exists for review, search, or configuration beyond file and config editing

Deliverables:

- workflow-specific exception review surface if needed
- search-first retrieval by business identifier
- admin-only configuration surface if needed
- no dashboard unless an actual operational decision requires it

Why fifth:

- the repo currently has only a local read-only stats page, not an operator workflow UI
- the correct next step is not to invent one early
- if a surface is later added, it must follow the stricter interaction rules in `docs/danpack-system-interaction-philosophy.md`

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

Barcode Buddy is currently a deterministic barcode-routing hot-folder service with a verified baseline: runtime tests exist, stats-page tests exist, workflow config templates exist, and the Danpack operating model is documented. Danpack is a packaging-engineering business with multiple document families and stronger proof signals than the visible homepage suggests. The right next step is not broad feature expansion. It is to preserve the verified runtime, reconcile the architecture spec with the implementation, and only then harden the system with Danpack-specific barcode rules and samples. If any human-facing surface is added later, it should follow `docs/danpack-system-interaction-philosophy.md` and start as a narrow exception-first tool rather than a dashboard.
