# Barcode Buddy v2.0.0

Barcode Buddy is a deterministic hot-folder document ingestion service for Danpack, a custom packaging and industrial supply company. It watches `data/input`, extracts a routing barcode from scanned PDFs or images, writes successful outputs as PDFs in `data/output/YYYY/MM`, and moves failures to `data/rejected` with JSONL audit logs and rejection sidecars.

## Why This Exists

In packaging and industrial supply operations, common workflows still rely on scanned vendor packing slips, proof-of-delivery documents, invoices, and receiving paperwork. The recurring operational problem is not scanning itself. It is getting the right document attached to the right business record quickly and repeatably, without a clerk renaming files by hand.

Barcode Buddy is deliberately scoped to the first automation step:

- intake from a scanner drop folder or shared folder
- detect one routable business barcode
- convert the document into a durable PDF
- produce a deterministic success or failure result

Research notes and source links are in [docs/industry-workflow-research.md](c:/Users/david/Documents/BarcodeBuddy/docs/industry-workflow-research.md).
Recommended operating patterns for packaging and industrial supply deployments are in [docs/packaging-industrial-operating-model.md](c:/Users/david/Documents/BarcodeBuddy/docs/packaging-industrial-operating-model.md).
The quickest builder entry point is [docs/current-system-truth.md](c:/Users/david/Documents/BarcodeBuddy/docs/current-system-truth.md).
Current builder-facing system context and Danpack-specific handoff are in [docs/danpack-builder-handoff.md](c:/Users/david/Documents/BarcodeBuddy/docs/danpack-builder-handoff.md).
Production integration, observability, incident, and security requirements are in [docs/production-operations-blueprint.md](c:/Users/david/Documents/BarcodeBuddy/docs/production-operations-blueprint.md).
The dependency-aware implementation order for the next builder is in [docs/builder-execution-plan.md](c:/Users/david/Documents/BarcodeBuddy/docs/builder-execution-plan.md).
Builder-facing interaction rules for any future human-facing surface are in [docs/danpack-system-interaction-philosophy.md](c:/Users/david/Documents/BarcodeBuddy/docs/danpack-system-interaction-philosophy.md).
A future owner-facing single-scan page design is in [docs/scan-record-workbench.md](c:/Users/david/Documents/BarcodeBuddy/docs/scan-record-workbench.md).
A dependency-aware implementation handoff for that work is in [docs/scan-record-builder-handoff.md](c:/Users/david/Documents/BarcodeBuddy/docs/scan-record-builder-handoff.md).
The future multi-record planning and reporting control plane is defined in [docs/operations-planner-product-spec.md](c:/Users/david/Documents/BarcodeBuddy/docs/operations-planner-product-spec.md), [docs/operations-planner-technical-spec.md](c:/Users/david/Documents/BarcodeBuddy/docs/operations-planner-technical-spec.md), [docs/operations-planner-builder-handoff.md](c:/Users/david/Documents/BarcodeBuddy/docs/operations-planner-builder-handoff.md), and [docs/operations-planner-execution-plan.md](c:/Users/david/Documents/BarcodeBuddy/docs/operations-planner-execution-plan.md).
Executable runtime and artifact-consistency tests are in [tests](/c:/Users/david/Documents/BarcodeBuddy/tests).
The machine-readable config contract is in [config.schema.json](c:/Users/david/Documents/BarcodeBuddy/config.schema.json).

## Requirements

- Python 3.10 through 3.13 (3.14 is not yet supported by all native dependencies)
- Windows or Linux

## Read This First

If you are picking up this repo for implementation work:

- start with [docs/current-system-truth.md](c:/Users/david/Documents/BarcodeBuddy/docs/current-system-truth.md)
- treat `tests/` as the freeze line for current runtime and builder artifact behavior
- treat the code in `main.py`, `stats.py`, and `app/` as the current runtime truth
- use [docs/danpack-builder-handoff.md](c:/Users/david/Documents/BarcodeBuddy/docs/danpack-builder-handoff.md) as the builder handoff
- use [docs/production-operations-blueprint.md](c:/Users/david/Documents/BarcodeBuddy/docs/production-operations-blueprint.md) for production integration, observability, incident, and security decisions
- use [docs/builder-execution-plan.md](c:/Users/david/Documents/BarcodeBuddy/docs/builder-execution-plan.md) for dependency-aware implementation order
- use [docs/danpack-system-interaction-philosophy.md](c:/Users/david/Documents/BarcodeBuddy/docs/danpack-system-interaction-philosophy.md) if you are adding any human-facing surface
- use [docs/operations-planner-builder-handoff.md](c:/Users/david/Documents/BarcodeBuddy/docs/operations-planner-builder-handoff.md) if you are implementing the planner, reporting, or obligation system
- this workspace is now a Git repository; do not assume this workspace has Git metadata in deployment contexts; use the repo files, docs, and executable tests as the evidence trail
- treat `TECHNICAL_ARCHITECTURE_SPECIFICATION.md` as target-state guidance, not proof that every specified behavior already exists

## Install

```bash
python -m pip install -r requirements.txt
```

## Run

```bash
python main.py
```

If `python` is mapped to the Microsoft Store alias on Windows, use:

```bash
py main.py
```

## Stats Page

Barcode Buddy includes a dedicated read-only local stats page served by FastAPI, built from the active log `data/logs/processing_log.jsonl` plus any daily archives under `data/logs/processing_log.YYYY-MM-DD.jsonl`.

Run it in a separate terminal:

```bash
python stats.py
```

If `python` is mapped to the Microsoft Store alias on Windows, use:

```bash
py stats.py
```

Then open:

```text
http://127.0.0.1:8080
```

Available options:

- `--host`: bind address, defaults to `127.0.0.1`
- `--port`: bind port, defaults to `8080`
- `--refresh-seconds`: browser auto-refresh interval, defaults to `15`
- `--history-days`: number of daily buckets shown, defaults to `14`
- `--recent-limit`: number of recent documents shown, defaults to `25`

The page shows:

- total documents seen in the log
- completed, succeeded, failed, and incomplete document counts
- service health derived from worker startup and heartbeat events
- live queue state from the input, processing, and journal folders
- completion latency percentiles
- 24-hour activity summary
- top failure reasons
- raw pipeline stage counts
- recent document outcomes and durations

## Inventory Management

Barcode Buddy includes a full inventory management system accessible at `/inventory` on the stats server.

### Features

- **Create items** with name, SKU, quantity, location, category, tags, cost, and auto-generated barcodes
- **Scan lookup** — type or scan a barcode/SKU to instantly find and act on an item
- **Camera scanning** — use a device camera with the browser BarcodeDetector API
- **Quick adjustments** — receive, issue, or adjust stock directly from scan results
- **Full CRUD** — edit, archive, or delete items with complete transaction history
- **Bulk import** — upload a CSV to create or update items in batch
- **Bulk export** — download all items as CSV for backup or external editing
- **Bulk actions** — select multiple items to update location, category, status, or delete
- **Barcode generation** — each item gets a downloadable barcode image (Code128, QR, etc.)
- **Dashboard** — overview with total items, units, value, low stock alerts, category/location breakdown
- **Multi-user** — each user's inventory is isolated; first signup becomes admin

### Accessing

Start the stats server and navigate to:

```text
http://127.0.0.1:8080/inventory
```

First-time users will be prompted to create an account at `/auth/signup`.

### API Endpoints

| Method | Path | Description |
| ------ | ---- | ----------- |
| GET | `/api/inventory` | List items (search, filter, paginate) |
| POST | `/api/inventory` | Create item |
| GET | `/api/inventory/{id}` | Get item with transaction history |
| PUT | `/api/inventory/{id}` | Update item |
| DELETE | `/api/inventory/{id}` | Delete item |
| POST | `/api/inventory/{id}/adjust` | Adjust quantity |
| GET | `/api/scan/lookup?code=...` | Scan lookup by barcode or SKU |
| GET | `/api/inventory/{id}/barcode.png` | Download barcode image |
| GET | `/api/inventory/summary` | Dashboard summary data |
| GET | `/api/inventory/categories` | List categories |
| GET | `/api/inventory/locations` | List locations |
| POST | `/api/inventory/import/csv` | Bulk import from CSV |
| GET | `/api/inventory/export/csv` | Export all items as CSV |
| POST | `/api/inventory/bulk/delete` | Bulk delete items |
| POST | `/api/inventory/bulk/update` | Bulk update items |
| GET | `/api/barcode/formats` | List supported barcode formats |

### CSV Import Format

Required columns: `name`, `sku`. Optional: `quantity`, `unit`, `location`, `category`, `tags`, `notes`, `barcode_type`, `barcode_value`, `cost`, `min_quantity`.

If `barcode_value` is blank, one is auto-generated. If a SKU already exists, the row updates the existing item.

## Test

```bash
py -3.12 -m pytest tests/ -x -q
```

Workflow starter configs are in `configs/`. These are placeholders for deployment shape only. Keep `barcode_value_patterns` empty until Danpack sample documents confirm the actual routing formats.

## Folder Structure

```text
.
|-- app
|-- configs
|-- config.json
|-- config.schema.json
|-- data
|   |-- input
|   |-- processing
|   |-- output
|   |   `-- YYYY
|   |       `-- MM
|   |-- rejected
|   `-- logs
|-- docs
|   `-- industry-workflow-research.md
|-- main.py
|-- stats.py
|-- tests
`-- requirements.txt
```

## Core Interface

```text
process_file(file_path) -> ProcessingResult
```

Each `ProcessingResult` carries a `processing_id` UUIDv4 for tracing across logs and rejection metadata.

## Current Operating Assumptions

These assumptions are based on how packaging and industrial supply teams actually run scan-to-record workflows today:

- one input file should represent one business document
- the desired routing barcode should be printed on the document, not inferred from OCR
- production workflows should prefer company-specific barcode value rules such as PO, sales order, or delivery-note patterns
- duplicate documents can happen in real operations because of rescans, corrected paperwork, and multiple documents tied to the same order, so duplicate handling is configurable
- most companies do not use one universal document rule set; receiving, proof-of-delivery, and quality paperwork often need different routing keys and different duplicate policies

If your upstream process produces multi-document scan batches or mixed documents with several unrelated barcodes, Barcode Buddy should be paired with an upstream splitting or review step.

## Recommended Deployment For Packaging And Industrial Supply

The research supports a simple operating model:

- run one Barcode Buddy instance per workflow, not one giant mixed queue
- give each workflow its own input folder and config file
- use `barcode_value_patterns` to enforce the routing key expected by that workflow
- use `duplicate_handling="reject"` where duplicates usually indicate a clerical mistake
- use `duplicate_handling="timestamp"` where rescans and corrected paperwork are normal

Typical split:

- receiving: vendor packing slips tied to PO or receipt identifiers
- shipping or POD: signed delivery paperwork and bill-of-lading style documents where rescans are common
- quality or compliance: certificates and traceability paperwork only if the source document already carries a routable barcode

Do not force emailed AP invoices or other non-barcoded documents into this pipeline. Those usually belong in a separate OCR or ERP-attached workflow.

Upstream capture guidance:

- prefer `PDF` at `300 DPI` or higher
- prefer `one file per scan`, not `one file per page`
- route each workflow to its own dedicated input folder
- if a device defaults to `TIFF`, switch the profile to `PDF`, `JPG`, or `PNG` unless runtime support is added
- keep all managed paths for a workflow on the same filesystem volume under the current config safeguards

More deployment and capture guidance is in [docs/packaging-industrial-operating-model.md](c:/Users/david/Documents/BarcodeBuddy/docs/packaging-industrial-operating-model.md).

## Configuration

`config.json` contains the hot-folder paths and scan controls:

- `workflow_key`: workflow identity emitted into logs and rejection sidecars
- `barcode_types`: expected formats, for example `["code128", "auto"]`
- `barcode_value_patterns`: optional regex rules for valid business IDs
- `duplicate_handling`: `timestamp` or `reject`
- `file_stability_delay_ms`: file stabilization window in milliseconds
- `max_pages_scan`: hard page limit for scanning
- `poll_interval_ms`: folder polling interval
- `barcode_scan_dpi`: PDF render DPI for barcode detection
- `barcode_upscale_factor`: optional image upscaling before decode

Current loader guarantees:

- unknown config keys are rejected
- `workflow_key` is normalized, validated, and included in the runtime settings object
- all managed runtime paths must be distinct
- `input_path`, `processing_path`, `output_path`, `rejected_path`, and `log_path` must resolve onto the same filesystem volume

The current machine-readable config contract is in [config.schema.json](c:/Users/david/Documents/BarcodeBuddy/config.schema.json).
Workflow-specific starter configs are in:

- [configs/config.receiving.example.json](c:/Users/david/Documents/BarcodeBuddy/configs/config.receiving.example.json)
- [configs/config.shipping-pod.example.json](c:/Users/david/Documents/BarcodeBuddy/configs/config.shipping-pod.example.json)
- [configs/config.quality-compliance.example.json](c:/Users/david/Documents/BarcodeBuddy/configs/config.quality-compliance.example.json)

Current default configuration:

```json
{
  "workflow_key": "default",
  "input_path": "./data/input",
  "processing_path": "./data/processing",
  "output_path": "./data/output",
  "rejected_path": "./data/rejected",
  "log_path": "./data/logs",
  "barcode_types": ["code128", "auto"],
  "barcode_value_patterns": [],
  "scan_all_pages": true,
  "duplicate_handling": "timestamp",
  "file_stability_delay_ms": 2000,
  "max_pages_scan": 50,
  "poll_interval_ms": 500,
  "barcode_scan_dpi": 300,
  "barcode_upscale_factor": 1.0
}
```

Example value rules for a receiving workflow where the packing slip barcode should match a PO-style identifier:

```json
{
  "barcode_value_patterns": ["^\\d{7}-\\d{2}$"]
}
```

## Deterministic Processing Rules

- supported inputs: `PDF`, `JPG`, `JPEG`, `PNG`
- supported-file detection uses magic-byte validation before deep parser handoff
- maximum file size: `50 MB`
- file stability uses `500 ms` checks and requires `4` consecutive unchanged checks by default
- if a file is still changing after `10 seconds`, it is treated as `FILE_LOCKED`
- exclusive-open retries run `5` times at `500 ms` intervals before `FILE_LOCKED`
- the worker acquires an exclusive per-workflow startup lock before recovery or polling begins
- claimed files are journaled under `processing/.journal` until a terminal outcome is logged
- restart recovery uses the journal plus explicit recovery log records instead of blindly sweeping every claimed file
- the worker emits `startup`, `heartbeat`, and `shutdown` lifecycle events to the log
- the active processing log rotates locally by day into `data/logs/processing_log.YYYY-MM-DD.jsonl`
- PDFs are rendered one page at a time at `300 DPI`
- `max_pages_scan` defaults to `50`
- maximum processing time per file is `15 seconds`
- every exception is caught, logged, and converted into a failure outcome
- no completed file remains in `data/processing`
- all JSONL log writes and journal writes are fsynced for durability
- the service handles `SIGINT` and `SIGTERM` for graceful shutdown
- input directory is monitored via `watchfiles` (OS-level file notifications) instead of pure polling

## Barcode Selection And Validation

- barcode preprocessing converts to grayscale, denoises, applies CLAHE contrast normalization, adaptive thresholding, and morphological cleanup via OpenCV, then decodes
- barcode decoding retries in this order: `0`, `90`, `180`, `270` degrees
- configured barcode types are preferred before `auto` fallback
- page scan order is `Page 1 -> Page N`
- within a page, scan order is top-left to bottom-right
- the best candidate across the scanned document wins deterministically by business-rule match, then largest bounding box area, then earlier page number, then scan order
- `barcode_value_patterns` affect routing priority, but they do not create separate ambiguity or pattern-mismatch states
- after barcode selection, the chosen barcode is rejected as `INVALID_BARCODE_FORMAT` if it fails business-rule matching or filename safety rules
- barcode text must still satisfy filename safety rules: printable characters only, length `4..64`, and characters limited to alphanumeric, dash, and underscore



This business-rule filter is the main research-driven refinement in the current version. It exists because packing slips and delivery paperwork often contain more than one barcode, and the largest barcode is not always the one that identifies the ERP record.

## Duplicate Handling

`duplicate_handling` is configurable because real operations vary:

- `timestamp`: preserves rescans and corrected paperwork by writing `{barcode}_{YYYYMMDD_HHMMSS}.pdf`
- `reject`: sends an exact filename collision to `data/rejected` as `DUPLICATE_FILE`

No content hashing is performed.

## Outputs

- successful outputs: `data/output/YYYY/MM`
- rejected originals: `data/rejected`
- rejection metadata: `data/rejected/*.meta.json`
- active processing log: `data/logs/processing_log.jsonl`
- archived processing logs: `data/logs/processing_log.YYYY-MM-DD.jsonl`
- stats page: read-only local web page served by `python stats.py`
- health endpoint: `http://127.0.0.1:8080/health`, returns `200` only when the worker heartbeat is fresh and the lock file is present

Every log entry now includes stable runtime metadata plus per-stage outcome fields. The runtime metadata fields are `schema_version`, `workflow`, `host`, `instance_id`, `config_version`, and `error_code`.

```json
{
  "schema_version": "1.0",
  "workflow": "default|receiving|shipping_pod|quality_compliance",
  "host": "hostname",
  "instance_id": "uuid4",
  "config_version": "12-hex-character checksum",
  "error_code": "string|null",
  "processing_id": "uuid",
  "stage": "processing|validation|output",
  "duration_ms": 1234
}
```

Rejected files also receive a `.meta.json` sidecar with the rejection stage and any barcode context that was available at failure time. This is intended to make branch or warehouse review faster without having to inspect the log stream first.

The runtime also writes service lifecycle events with `stage = "service"` and `event_type = "startup" | "heartbeat" | "shutdown"`. Those events carry queue and heartbeat context for the stats page and health endpoint, but they are not counted as documents. The stats surface aggregates both the active log and any date-stamped archives in the log directory.

## How To Verify

- start the service with `python main.py`
- drop a document with a readable business barcode into `data/input`
- confirm the file leaves `data/input`
- confirm a PDF appears in `data/output/YYYY/MM`
- confirm `data/logs/processing_log.jsonl` contains `schema_version`, `workflow`, `processing_id`, `stage`, and `duration_ms`
- if the service has crossed midnight, confirm the previous day was archived to `data/logs/processing_log.YYYY-MM-DD.jsonl` and the stats page still shows the full history
- if you configured `barcode_value_patterns`, test a matching barcode, a non-matching barcode, and a document with multiple eligible values to confirm deterministic selection

## Deployment Notes

- Windows: Task Scheduler or a service wrapper
- Linux: `systemd`
