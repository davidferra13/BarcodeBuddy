# Barcode Buddy Technical Architecture Specification

Implementation status note: this document describes the target architecture direction. It is not a guarantee that every specified component or behavior already exists in the current runtime. For the current implementation truth and builder execution order, start with `docs/danpack-builder-handoff.md` and the code in `main.py` and `app/`.

## 1. System Architecture Overview

### 1.1 Purpose
Barcode Buddy is a single-node, headless document-ingestion service for Danpack. It is the deterministic intake and archive layer for scanned supply-chain paperwork, specifically signed proof-of-delivery pages, packing slips, delivery notes, receiving paperwork, vendor invoices, purchase orders, and Kanban or vendor-managed-inventory replenishment paperwork. It watches a filesystem input directory, claims complete files, extracts one Danpack-valid document barcode, saves the document as a PDF named from that barcode, rejects any file that does not produce one valid document barcode, and writes an append-only audit log for every state transition and terminal outcome.

### 1.2 Runtime Topology
- Deployment model: single process, single host, single instance.
- Execution model: long-running background service.
- Storage model: local filesystem only; no database.
- Filesystem requirement: all managed directories reside on the same NTFS volume to guarantee atomic rename operations.
- Process singleton: enforced with OS mutex `Global\\BarcodeBuddy.Singleton`.

### 1.3 Managed Directories

| Path | Role | Ownership Rule |
| --- | --- | --- |
| `data/input` | external drop zone for newly scanned files | external writers may create files here; Barcode Buddy may only read, stabilize, and claim |
| `data/processing` | transient working area | Barcode Buddy exclusive ownership |
| `data/output` | final successful PDFs | Barcode Buddy exclusive ownership |
| `data/rejected` | final failed source files | Barcode Buddy exclusive ownership |
| `data/logs` | append-only structured logs | Barcode Buddy exclusive ownership |

### 1.4 Component Interaction

```text
Scanner/Scan Software
    -> data/input
    -> Watcher
    -> data/processing + ProcessingJob journal
    -> Processor
       -> Barcode Engine
       -> Validator
       -> Output Manager
    -> data/output | data/rejected
    -> Logger
    -> data/logs

Configuration Manager -> Watcher, Processor, Validator, Output Manager, Logger
```

### 1.5 System Boundary
In scope:
- hot-folder intake from scanner, MFP, or upstream scan-to-folder export
- one-file-per-document ingestion
- file discovery in `data/input`
- stabilization of partially written files
- format detection
- page counting
- barcode extraction
- document-barcode filtering, normalization, and validation
- PDF generation for image inputs
- PDF preservation for PDF inputs
- deterministic file naming
- duplicate rejection
- retry handling
- crash recovery
- structured logging

Out of scope:
- scanner hardware control
- scanner software configuration
- scan job creation
- multi-document batch splitting
- barcode cover-sheet generation
- OCR
- manual review
- UI
- mobile client
- HTTP API
- user authentication or authorization
- cloud storage
- external database
- barcode label generation
- document classification beyond barcode extraction

### 1.6 Operating Assumptions
- Every file dropped into `data/input` represents exactly one business document.
- The authoritative filename barcode is a Danpack document identifier, not a product barcode, carton barcode, pallet barcode, or supplier label barcode.
- Upstream capture systems may be network scanners, MFPs, mobile capture exports, or scan software that writes files into a watched folder. Barcode Buddy does not interact with those systems directly.
- Upstream scan profiles must produce 300 DPI or higher page images for paper-originated documents.
- Upstream scan profiles must preserve sufficient barcode signal quality: no aggressive cleanup, no barcode-destructive blank-page removal, and no high-loss compression that materially degrades edges or contrast.
- Barcode Buddy is not an ERP matching engine, accounts-payable workflow engine, or content-management system. It is the deterministic rename-and-archive stage that precedes those systems.

## 2. Module Architecture (Strict Boundaries)

### 2.1 Watcher

| Attribute | Definition |
| --- | --- |
| Exact responsibility | Detect regular files in `data/input`, determine file stability, claim the file by atomic move into `data/processing`, create the initial `ProcessingJob` journal, and enqueue the job. |
| Can do | poll `data/input`; ignore directories; read file metadata; test file readability; move stable files from input to processing; create `ProcessingJob`; emit watcher log entries |
| Cannot do | decode barcodes; validate barcode content; generate PDFs; write to `data/output`; write to `data/rejected` after claim; decide terminal success or failure |
| Inputs | configuration values for paths and stabilization constants; filesystem directory contents |
| Outputs | claimed processing file; `ProcessingJob` journal; in-memory FIFO queue entry; log entries |
| Dependencies | Configuration Manager, Logger, NTFS filesystem |

### 2.2 Processor

| Attribute | Definition |
| --- | --- |
| Exact responsibility | Orchestrate the lifecycle of one claimed job from `PROCESSING` through terminal `SUCCESS` or `FAILURE`. |
| Can do | load the claimed source file; compute source checksum; detect format; count pages; call Barcode Engine; call Validator; call Output Manager; update job journal state; schedule retries |
| Cannot do | watch `data/input`; bypass Validator; write logs directly without Logger; write output files except through Output Manager; modify configuration |
| Inputs | `ProcessingJob`; claimed source file in `data/processing`; immutable configuration |
| Outputs | `ProcessingResult`; updated `ProcessingJob` journal; retry scheduling decisions; log entries via Logger |
| Dependencies | Barcode Engine, Validator, Output Manager, Logger, Configuration Manager |

### 2.3 Barcode Engine

| Attribute | Definition |
| --- | --- |
| Exact responsibility | Produce the complete set of barcode detections from a document using the fixed symbology set and fixed preprocessing pipeline. |
| Can do | render pages to working rasters; rotate images; apply contrast normalization; apply thresholding; run multi-barcode detection; normalize raw decoder output for downstream validation |
| Cannot do | reject duplicates; decide success or failure; rename files; write files; log terminal outcomes |
| Inputs | `DocumentObject`; processing timeout constant; supported symbology list |
| Outputs | `BarcodeResult` |
| Dependencies | PDF/image rasterizer, barcode decoder library, Configuration Manager for timeout constant |

### 2.4 Validator

| Attribute | Definition |
| --- | --- |
| Exact responsibility | Enforce all deterministic acceptance rules for document constraints, Danpack document-ID matching, duplicate detection, and final filename legality. |
| Can do | verify supported format; verify file size; verify page count; apply deterministic barcode selection by business-rule match, bounding-box area, and scan order; enforce allowed barcode character set; enforce duplicate rejection against `data/output` |
| Cannot do | decode images; move files; generate PDFs; retry jobs; alter barcode values beyond the defined normalization rules |
| Inputs | `DocumentObject`; `BarcodeResult`; immutable configuration; current `data/output` contents |
| Outputs | pass/fail validation decision and error code |
| Dependencies | Configuration Manager, NTFS filesystem, Logger |

### 2.5 Output Manager

| Attribute | Definition |
| --- | --- |
| Exact responsibility | Create the canonical output artifact for success, commit it atomically, or move the source file into `data/rejected` for failure. |
| Can do | preserve PDF inputs byte-for-byte by atomic rename to the final output path; convert image inputs to PDF; write temporary PDF files in `data/processing` for image inputs only; flush and atomically rename final PDFs into `data/output`; move failed source files into `data/rejected`; delete transient files after commit |
| Cannot do | choose the barcode value; override validation; watch input; suppress logging |
| Inputs | `ProcessingJob`; `DocumentObject`; validated barcode string for success; error code for failure |
| Outputs | committed output PDF path or committed rejected-file path; cleanup of transient files |
| Dependencies | Logger, Configuration Manager, NTFS filesystem, PDF writer |

### 2.6 Logger

| Attribute | Definition |
| --- | --- |
| Exact responsibility | Persist every operational event as one structured JSON line in the log file for the UTC day of the event. |
| Can do | write JSON Lines; flush after each entry; assign sequence numbers; write startup, shutdown, state, retry, recovery, and terminal events |
| Cannot do | make processing decisions; mutate jobs; suppress failures; rotate non-log files |
| Inputs | event payloads from all other modules |
| Outputs | append-only log lines in `data/logs/barcodebuddy-YYYY-MM-DD.jsonl` |
| Dependencies | Configuration Manager, NTFS filesystem |

### 2.7 Configuration Manager

| Attribute | Definition |
| --- | --- |
| Exact responsibility | Load, validate, freeze, and expose immutable runtime configuration at startup. |
| Can do | read JSON config; read environment overrides; validate path distinctness and same-volume requirement; validate numeric bounds; create missing managed directories |
| Cannot do | hot-reload values; change values after startup; infer missing required values; bypass validation errors |
| Inputs | `app/config/barcodebuddy.json`; `BARCODE_BUDDY__*` environment variables |
| Outputs | immutable configuration object or fatal startup failure `CONFIG_INVALID` |
| Dependencies | NTFS filesystem, process environment |

## 3. Data Models (Strict Schemas)

All timestamps are UTC ISO-8601 strings with millisecond precision. All enums are uppercase ASCII strings. All paths are absolute Windows paths.

### 3.1 DocumentObject

| Field | Type | Required | Allowed Values |
| --- | --- | --- | --- |
| `document_id` | `string` | yes | 64-character uppercase SHA-256 hex of the stable source bytes |
| `source_file_name` | `string` | yes | original file name including extension |
| `source_path` | `string` | yes | absolute path under `data/processing` after claim |
| `source_extension` | `string` | yes | `.pdf`, `.tif`, `.tiff`, `.png`, `.jpg`, `.jpeg` |
| `detected_format` | `string` | yes | `PDF`, `PNG`, `JPEG` |
| `size_bytes` | `integer` | yes | `1` to `52428800` |
| `page_count` | `integer` | yes | `1` to `100` |
| `created_at_utc` | `string` | yes | valid UTC timestamp |
| `claimed_at_utc` | `string` | yes | valid UTC timestamp |

Example:

```json
{
  "document_id": "3E5D7C1B18A2A7C7F6F98BF09220C4A6E9505D7A4CB8FEE1D5104D6B1C953A40",
  "source_file_name": "scan_0001.tif",
  "source_path": "C:\\Users\\david\\Documents\\BarcodeBuddy\\data\\processing\\01961d9a-1e87-7c39-b8f1-32de94b28d1e__scan_0001.tif",
  "source_extension": ".tif",
  "detected_format": "PDF",
  "size_bytes": 348112,
  "page_count": 2,
  "created_at_utc": "2026-04-03T19:07:11.042Z",
  "claimed_at_utc": "2026-04-03T19:07:18.113Z"
}
```

### 3.2 ProcessingJob

| Field | Type | Required | Allowed Values |
| --- | --- | --- | --- |
| `job_id` | `string` | yes | canonical lowercase UUIDv7 |
| `correlation_id` | `string` | yes | exactly equal to `job_id` |
| `state` | `string` | yes | `INPUT`, `STABILIZING`, `PROCESSING`, `VALIDATING`, `SUCCESS`, `FAILURE` |
| `attempt_number` | `integer` | yes | `1`, `2`, `3` |
| `original_input_path` | `string` | yes | absolute path under `data/input` at first detection |
| `processing_path` | `string` | no | absolute path under `data/processing` after claim; null before claim |
| `document_id` | `string` | no | null before checksum computation; otherwise 64-character uppercase SHA-256 hex |
| `target_output_path` | `string` | no | null or absolute path under `data/output` |
| `last_error_code` | `string` | no | null or one value from Section 6 |
| `created_at_utc` | `string` | yes | valid UTC timestamp |
| `updated_at_utc` | `string` | yes | valid UTC timestamp |

Example:

```json
{
  "job_id": "01961d9a-1e87-7c39-b8f1-32de94b28d1e",
  "correlation_id": "01961d9a-1e87-7c39-b8f1-32de94b28d1e",
  "state": "PROCESSING",
  "attempt_number": 1,
  "original_input_path": "C:\\Users\\david\\Documents\\BarcodeBuddy\\data\\input\\scan_0001.tif",
  "processing_path": "C:\\Users\\david\\Documents\\BarcodeBuddy\\data\\processing\\01961d9a-1e87-7c39-b8f1-32de94b28d1e__scan_0001.tif",
  "document_id": "3E5D7C1B18A2A7C7F6F98BF09220C4A6E9505D7A4CB8FEE1D5104D6B1C953A40",
  "target_output_path": null,
  "last_error_code": null,
  "created_at_utc": "2026-04-03T19:07:12.004Z",
  "updated_at_utc": "2026-04-03T19:07:18.113Z"
}
```

### 3.3 BarcodeResult

| Field | Type | Required | Allowed Values |
| --- | --- | --- | --- |
| `status` | `string` | yes | `FOUND`, `NOT_FOUND` |
| `normalized_value` | `string` | no | null or `^[A-Z0-9_-]{1,64}$` |
| `symbology` | `string` | no | null or `GS1_128`, `CODE_128`, `CODE_39`, `INTERLEAVED_2_OF_5`, `QR_CODE`, `DATA_MATRIX`, `PDF_417` |
| `first_page_number` | `integer` | no | null or `1` to `100` |
| `candidate_values` | `array<string>` | yes | unique normalized values found across all pages and passes before Danpack document-ID filtering |
| `eligible_candidate_values` | `array<string>` | yes | unique normalized values that match the configured Danpack document-ID regex |
| `page_one_eligible_values` | `array<string>` | yes | unique eligible values found on page 1 only |
| `raw_detection_count` | `integer` | yes | `0` or greater |
| `confidence` | `number` | yes | `0.0` when no candidate is selected, otherwise `1.0` |

Example:

```json
{
  "status": "FOUND",
  "normalized_value": "DNP-240041",
  "symbology": "CODE_128",
  "first_page_number": 1,
  "candidate_values": ["DNP-240041", "00012345678905"],
  "eligible_candidate_values": ["DNP-240041"],
  "page_one_eligible_values": ["DNP-240041"],
  "raw_detection_count": 3,
  "confidence": 1.0
}
```

### 3.4 ProcessingResult

| Field | Type | Required | Allowed Values |
| --- | --- | --- | --- |
| `job_id` | `string` | yes | canonical lowercase UUIDv7 |
| `correlation_id` | `string` | yes | exactly equal to `job_id` |
| `final_state` | `string` | yes | `SUCCESS` or `FAILURE` |
| `barcode_value` | `string` | no | null or `^[A-Z0-9_-]{1,64}$` |
| `output_pdf_path` | `string` | no | null or absolute path under `data/output` |
| `rejected_file_path` | `string` | no | null or absolute path under `data/rejected` |
| `error_code` | `string` | no | null or one value from Section 6 |
| `attempt_number` | `integer` | yes | `1`, `2`, `3` |
| `started_at_utc` | `string` | yes | valid UTC timestamp |
| `completed_at_utc` | `string` | yes | valid UTC timestamp |
| `duration_ms` | `integer` | yes | `0` or greater |

Example:

```json
{
  "job_id": "01961d9a-1e87-7c39-b8f1-32de94b28d1e",
  "correlation_id": "01961d9a-1e87-7c39-b8f1-32de94b28d1e",
  "final_state": "SUCCESS",
  "barcode_value": "DNP-240041",
  "output_pdf_path": "C:\\Users\\david\\Documents\\BarcodeBuddy\\data\\output\\DNP-240041.pdf",
  "rejected_file_path": null,
  "error_code": null,
  "attempt_number": 1,
  "started_at_utc": "2026-04-03T19:07:18.113Z",
  "completed_at_utc": "2026-04-03T19:07:20.824Z",
  "duration_ms": 2711
}
```

### 3.5 LogEntry

| Field | Type | Required | Allowed Values |
| --- | --- | --- | --- |
| `timestamp_utc` | `string` | yes | valid UTC timestamp |
| `sequence` | `integer` | yes | monotonically increasing per process start, starting at `1` |
| `severity` | `string` | yes | `DEBUG`, `INFO`, `WARN`, `ERROR`, `FATAL` |
| `event_type` | `string` | yes | fixed event types from Section 12 |
| `job_id` | `string` | no | null or canonical lowercase UUIDv7 |
| `correlation_id` | `string` | no | null or canonical lowercase UUIDv7 |
| `state` | `string` | no | null or one lifecycle state |
| `document_id` | `string` | no | null or 64-character uppercase SHA-256 hex |
| `source_path` | `string` | no | null or absolute path |
| `target_path` | `string` | no | null or absolute path |
| `barcode_value` | `string` | no | null or `^[A-Z0-9_-]{1,64}$` |
| `eligible_candidate_values` | `array<string>` | no | null or unique normalized values matching the Danpack document-ID regex |
| `error_code` | `string` | no | null or one value from Section 6 |
| `message` | `string` | yes | non-empty ASCII sentence |

Example:

```json
{
  "timestamp_utc": "2026-04-03T19:07:20.824Z",
  "sequence": 42,
  "severity": "INFO",
  "event_type": "JOB_COMPLETED",
  "job_id": "01961d9a-1e87-7c39-b8f1-32de94b28d1e",
  "correlation_id": "01961d9a-1e87-7c39-b8f1-32de94b28d1e",
  "state": "SUCCESS",
  "document_id": "3E5D7C1B18A2A7C7F6F98BF09220C4A6E9505D7A4CB8FEE1D5104D6B1C953A40",
  "source_path": "C:\\Users\\david\\Documents\\BarcodeBuddy\\data\\processing\\01961d9a-1e87-7c39-b8f1-32de94b28d1e__scan_0001.tif",
  "target_path": "C:\\Users\\david\\Documents\\BarcodeBuddy\\data\\output\\DNP-240041.pdf",
  "barcode_value": "DNP-240041",
  "eligible_candidate_values": ["DNP-240041"],
  "error_code": null,
  "message": "Job completed successfully."
}
```

## 4. State Machine

### 4.1 Canonical States
- `INPUT`: file exists in `data/input` and has been detected but not yet proven stable
- `STABILIZING`: file is under observation for completeness and readability
- `PROCESSING`: file has been claimed into `data/processing` and is undergoing checksum, format detection, page inspection, barcode scanning, and PDF preparation
- `VALIDATING`: barcode and document constraints are being checked for acceptance
- `SUCCESS`: final PDF has been atomically committed into `data/output`
- `FAILURE`: source file has been committed into `data/rejected` or a deferred rejection has been recorded for a locked source

### 4.2 Valid Transitions

| From | To | Condition |
| --- | --- | --- |
| `INPUT` | `STABILIZING` | Watcher detects a regular file under `data/input` |
| `STABILIZING` | `PROCESSING` | file size is unchanged for 4 consecutive polls at 500 ms intervals, the full 2-second stabilization window is satisfied, and the file can be opened exclusively; Watcher atomically renames the file into `data/processing` |
| `STABILIZING` | `FAILURE` | file exceeds stabilization timeout or cannot be claimed after final retry |
| `PROCESSING` | `VALIDATING` | Processor completed checksum, format detection, page inspection, barcode scan, and PDF staging without technical failure |
| `PROCESSING` | `FAILURE` | technical failure before validation: corrupt file, unsupported format, processing timeout, output staging failure after final retry, or internal error |
| `VALIDATING` | `SUCCESS` | Validator accepts the document and Output Manager atomically commits `data/output/{selected_danpack_document_id}.pdf` |
| `VALIDATING` | `FAILURE` | validation failure: invalid barcode format or duplicate output filename |

### 4.3 Failure Paths
- `STABILIZING -> FAILURE`: `FILE_LOCKED`
- `PROCESSING -> FAILURE`: `FILE_CORRUPT`, `UNSUPPORTED_FORMAT`, `PROCESSING_TIMEOUT`, `OUTPUT_WRITE_FAILED`, `INTERNAL_ERROR`
- `VALIDATING -> FAILURE`: `INVALID_BARCODE_FORMAT`, `DUPLICATE_FILE`

### 4.4 Invalid States
- direct `INPUT -> SUCCESS`
- direct `INPUT -> VALIDATING`
- direct `STABILIZING -> SUCCESS`
- `SUCCESS -> any other state`
- `FAILURE -> any other state`
- `VALIDATING -> STABILIZING`
- `PROCESSING -> INPUT`

Retries do not create new states. A retry repeats work inside the current non-terminal state with `attempt_number` incremented.

## 5. File Lifecycle Rules

### 5.0 Upstream Input Contract
- Upstream capture must deliver exactly one business document per file into `data/input`.
- Upstream capture must not merge multiple logical documents into one file.
- Upstream capture may originate from a scanner, MFP, mobile delivery system export, or scan software hot folder.
- Upstream file names are ignored after claim. Only the extracted Danpack document barcode determines the success filename.
- Barcode Buddy accepts upstream PDF, PNG, JPEG, and JPG files only.
- For paper-originated documents, upstream capture must use 300 DPI or higher, preserve page order, avoid destructive image cleanup, and avoid high-loss compression settings.

### 5.1 Source Discovery and Claim
1. The Watcher polls `data/input` every 500 ms by default.
2. Only regular files are eligible. Directories are ignored.
3. A file is stable only when `size_bytes` is unchanged across 4 consecutive polls, each 500 ms apart, and the file can be opened exclusively.
4. On stability, the Watcher claims the file by atomic same-volume rename to `data/processing/{job_id}__{original_file_name}`.
5. The Watcher writes `data/processing/{job_id}.job.json` immediately after the claim.
6. The Processor updates the job journal on every state transition and sets `target_output_path` before the final output rename.

### 5.2 Success Path
1. Validator confirms `data/output/{selected_danpack_document_id}.pdf` does not already exist.
2. If `detected_format = PDF`, Output Manager atomically renames the claimed source file directly to `data/output/{selected_danpack_document_id}.pdf`.
3. If `detected_format != PDF`, Processor creates `data/processing/{job_id}.pdf.tmp`.
4. For image inputs, Output Manager flushes the temp PDF to disk and atomically renames it to `data/output/{selected_danpack_document_id}.pdf`.
5. For image inputs, Output Manager deletes the claimed source file from `data/processing`.
6. Output Manager deletes `data/processing/{job_id}.job.json`.

### 5.3 Failure Path
1. On terminal failure after claim, Output Manager moves the claimed source file to `data/rejected/{job_id}__{error_code}__{original_file_name}` by atomic same-volume rename.
2. Output Manager deletes `data/processing/{job_id}.pdf.tmp` if it exists.
3. Output Manager deletes `data/processing/{job_id}.job.json`.
4. No file is written to `data/output`.

### 5.4 Partial File Handling
- A file that is still being written remains in `STABILIZING`.
- A file that never becomes stable within 10 seconds enters `FAILURE` with `FILE_LOCKED`.
- If a locked file cannot be moved to `data/rejected` at the moment of terminal failure, the system records a deferred rejection in the log and retries the move using the retry strategy until the move succeeds.

### 5.5 Interruption Rules
- If the process stops before a source file is claimed, the file remains in `data/input` and is rediscovered on restart.
- If the process stops after claim and before terminal commit, the source file remains in `data/processing` and is recovered from the job journal.
- If the process stops after final output rename and before source cleanup, recovery treats the output as authoritative and completes cleanup.

### 5.6 File Integrity Guarantees
- Source bytes are never modified in place.
- All inter-directory moves use atomic rename on the same NTFS volume.
- Final output is never written directly to its final name; it is always written to `*.pdf.tmp` first.
- A source file is deleted only after the final PDF rename succeeds or after the source file rename into `data/rejected` succeeds.

### 5.7 Output PDF Rules
- Every successful output file has the `.pdf` extension.
- If the source is PDF, the output PDF is byte-for-byte identical to the source file; only the path and file name change.
- If the source is PNG, JPEG, or JPG, the output is a generated PDF 1.7 file.
- The output page count exactly matches the source page count.
- Page order is preserved exactly.
- For image inputs, original page color fidelity is preserved in the output PDF.
- Generated output PDFs contain no OCR layer, no form fields, no attachments, no JavaScript, and no encryption.
- Generated output PDF metadata is fixed:
  - `Title = {selected_danpack_document_id}`
  - `Producer = Barcode Buddy`
  - `CreationDate = completion timestamp in UTC`

## 6. Error Taxonomy

| Error Code | Description | Trigger Condition | Retryable | Handling Behavior |
| --- | --- | --- | --- | --- |
| `BARCODE_NOT_FOUND` | no supported barcode was found | `raw_detection_count = 0` after all pages and passes | no | move source to `data/rejected`; log terminal failure |
| `INVALID_BARCODE_FORMAT` | decoded barcode cannot be used as the canonical filename | selected value fails business-rule matching, contains non-printable characters, violates `^[A-Za-z0-9_-]{4,64}$`, or becomes invalid after normalization | no | move source to `data/rejected`; log terminal failure |
| `FILE_CORRUPT` | file bytes cannot be parsed as the declared or detected format | parser, renderer, or page reader fails on the source bytes | no | move source to `data/rejected`; log terminal failure |
| `FILE_LOCKED` | file cannot be claimed or read within stabilization budget | source remains unstable or unclaimable for 10 seconds, or exclusive-open retries fail after 5 attempts at 500 ms intervals | yes | retry; on final failure move to `data/rejected` when lock clears and log deferred rejection until commit |
| `UNSUPPORTED_FORMAT` | file format is outside the accepted set | file is not PDF, PNG, JPEG, or JPG | no | move source to `data/rejected`; log terminal failure |
| `PROCESSING_TIMEOUT` | processing exceeded the hard execution budget | one attempt exceeds 15 seconds from processor start to terminal action, or page count exceeds the 50-page processing ceiling | yes | abort current attempt, clean temp files, retry |
| `FILE_TOO_LARGE` | file is too large for V1 limits | `size_bytes > 52428800` | no | move source to `data/rejected`; log terminal failure |
| `DUPLICATE_FILE` | the final output filename already exists | `data/output/{barcode}.pdf` already exists at validation time and duplicate handling is `reject` | no | move source to `data/rejected`; log terminal failure |
| `OUTPUT_WRITE_FAILED` | final output artifact could not be written or renamed | temp PDF write, flush, or final rename fails | yes | clean temp file if possible; retry |
| `CONFIG_INVALID` | runtime configuration is invalid | startup validation fails | no | service does not start; write fatal log entry |
| `INTERNAL_ERROR` | unclassified runtime fault in controlled code path | uncaught exception inside Processor, Watcher, Validator, Barcode Engine, or Output Manager | yes | clean temp files; retry; final failure after attempt 3 |

## 7. Retry Strategy

### 7.1 Retryable Errors
- `FILE_LOCKED`
- `PROCESSING_TIMEOUT`
- `OUTPUT_WRITE_FAILED`
- `INTERNAL_ERROR`

### 7.2 Retry Limits
- Total attempts per job: `3`
- Initial execution: `attempt_number = 1`
- Retries: `attempt_number = 2` and `attempt_number = 3`

### 7.3 Delay Strategy

| Attempt Transition | Delay |
| --- | --- |
| `1 -> 2` | 5 seconds |
| `2 -> 3` | 15 seconds |

### 7.4 Retry Rules
- The same `job_id` is reused across all attempts.
- Retries preserve the original claimed source path in `data/processing`.
- Temp PDF files are deleted before a retry starts.
- Each retry writes a `RETRY_SCHEDULED` log entry with the delay and error code.

### 7.5 Final Failure
- A retryable error becomes terminal after the third failed attempt.
- On terminal failure, the source file is committed to `data/rejected`.
- Exactly one terminal `ProcessingResult` is produced per job.

## 8. Concurrency Model

### 8.1 Processing Mode
- Watcher concurrency: single thread.
- Processor concurrency: single worker.
- Queue type: in-memory FIFO queue.
- Overall job execution: strictly sequential; only one document may be in `PROCESSING` or `VALIDATING` at a time.

### 8.2 Simultaneous File Arrivals
- The Watcher may detect multiple files during one poll cycle.
- Claim order is deterministic: ascending `creation_time_utc`, then ascending `source_file_name` using ordinal ASCII comparison.
- Claimed jobs are enqueued in that same order.

### 8.3 File Locking Behavior
- A file is owned by external writers while in `data/input`.
- Ownership transfers to Barcode Buddy only after atomic rename into `data/processing`.
- Only the Watcher may move files from `data/input`.
- Only Output Manager may move files from `data/processing` into `data/output` or `data/rejected`.

### 8.4 Race Condition Guarantees
- Single process instance prevents dual ownership.
- Single worker prevents concurrent writes to `data/output`.
- Atomic rename prevents partial visibility of claimed or committed files.
- Duplicate check occurs immediately before final output rename and on the same worker, eliminating same-process output races.

## 9. Performance Constraints

| Constraint | Value |
| --- | --- |
| Maximum input file size | 50 MiB |
| Maximum page count | 50 pages |
| Poll interval | 500 ms |
| Stabilization requirement | 4 unchanged size checks |
| Stabilization timeout | 10 seconds |
| Hard processing timeout per attempt | 15 seconds |
| Expected processing time for 1-10 pages | 15 seconds or less |
| Expected processing time for 11-50 pages | 30 seconds or less |
| Expected processing time for 51+ pages | not supported; reject with `PROCESSING_TIMEOUT` |
| Peak resident memory budget | 1 GiB |

Memory rule: page rasterization is page-by-page. The service must never materialize all document pages in memory at once.

## 10. Barcode Processing Rules (Deep)

### 10.1 Supported Barcode Formats
- `GS1_128`
- `CODE_128`
- `CODE_39`
- `INTERLEAVED_2_OF_5`
- `QR_CODE`
- `DATA_MATRIX`
- `PDF_417`

All other symbologies are ignored and do not count as detections.

### 10.2 Input Format Detection
- Format is determined by file signature, not by extension.
- Accepted signatures:
  - PDF: `%PDF-`
  - PNG: `89 50 4E 47 0D 0A 1A 0A`
  - JPEG: `FF D8 FF`

### 10.3 Rasterization Rules
- PDF pages are rendered at 300 DPI for barcode detection.
- PNG and JPEG files are decoded at native pixel dimensions for barcode detection.
- All pages are converted to 8-bit grayscale working images for barcode detection.
- Page order is always natural document order starting at page 1.

### 10.4 Preprocessing Pipeline
For every page, the Barcode Engine runs the following pipeline in exact order:
1. convert the page image to grayscale
2. apply contrast normalization
3. apply a sharpening filter
4. attempt barcode detection at orientation `0`
5. if detection fails, retry at `90`, `180`, and `270` degrees

No deskew, thresholding, or alternative preprocessing branches are applied in V1.

### 10.5 Scan Order
- Pages are scanned from page 1 through page `N`.
- Within a page, scan order is top-left to bottom-right.
- Multi-barcode detection is enabled on every pass.
- Candidate selection is deterministic across the full document:
  1. prefer candidates that match the configured business-rule regex
  2. within that group, choose the candidate with the largest bounding-box area
  3. if areas tie, choose the first candidate encountered in document scan order
  4. if no candidates are detected anywhere in the document, fail with `BARCODE_NOT_FOUND`

### 10.6 Normalization Rules
- Leading and trailing whitespace are removed.
- Internal whitespace is preserved.
- Non-printable characters are removed.
- The selected value must match `^[A-Za-z0-9_-]{4,64}$`.
- Business-rule regexes affect routing priority and validity, but do not create a separate ambiguity state.

### 10.7 Fallback Behavior
- If no supported barcode is detected on any page in any pass, the result is `BARCODE_NOT_FOUND`.
- If barcode data is detected but the selected value fails business-rule matching or filename safety validation, the result is `INVALID_BARCODE_FORMAT`.
- If the same normalized value is detected multiple times, it is treated as one candidate value for metadata purposes.

### 10.8 Confidence Threshold
- `confidence = 1.0` when at least one candidate is selected.
- `confidence = 0.0` when no candidate is selected.
- Acceptance threshold: `1.0`.

## 11. Configuration Hierarchy

### 11.1 Configurable Values

| Key | Type | Required | Default |
| --- | --- | --- | --- |
| `paths.data_root` | absolute path string | no | application root `data` |
| `paths.input_dir` | absolute path string | no | `{data_root}\\input` |
| `paths.processing_dir` | absolute path string | no | `{data_root}\\processing` |
| `paths.output_dir` | absolute path string | no | `{data_root}\\output` |
| `paths.rejected_dir` | absolute path string | no | `{data_root}\\rejected` |
| `paths.log_dir` | absolute path string | no | `{data_root}\\logs` |
| `barcode.document_id_regex` | regex string | yes | none; startup fails if absent |
| `logging.retention_days` | integer | no | `90` |

### 11.2 Hard-Coded Values
The following values are not configurable:
- lifecycle states
- supported barcode symbologies
- supported input formats
- deterministic barcode selection rule
- stabilization rule: 4 polls at 500 ms each
- stabilization timeout: 10 seconds
- max file size: 50 MiB
- max page count: 50
- retry count: 3 total attempts
- retry delays: 5 seconds then 15 seconds
- hard processing timeout: 15 seconds
- output filename pattern: `{barcode}.pdf`
- rejected filename pattern: `{job_id}__{error_code}__{original_file_name}`
- processing filename pattern: `{job_id}__{original_file_name}`
- log file pattern: `barcodebuddy-YYYY-MM-DD.jsonl`
- final filename safety regex: `^[A-Za-z0-9_-]{4,64}$`

### 11.3 Precedence Rules
Highest to lowest:
1. environment variables with prefix `BARCODE_BUDDY__`
2. JSON file `app/config/barcodebuddy.json`
3. hard-coded defaults

### 11.4 Validation Rules
- Every configured path must be absolute.
- All managed directories must be distinct.
- All managed directories must be on the same NTFS volume.
- `barcode.document_id_regex` must compile successfully, must begin with `^`, and must end with `$`.
- `logging.retention_days` must be an integer from `1` to `3650`.
- Any validation failure terminates startup with `CONFIG_INVALID`.

### 11.5 Load Timing
- Configuration is loaded once at startup.
- Configuration never hot-reloads.

## 12. Logging & Observability

### 12.1 Log Format
- File format: JSON Lines
- File name: `data/logs/barcodebuddy-YYYY-MM-DD.jsonl`
- Encoding: UTF-8 without BOM
- Flush policy: flush after every line

### 12.2 Severity Levels
- `DEBUG`: non-terminal diagnostic detail
- `INFO`: normal lifecycle events
- `WARN`: retryable abnormal condition
- `ERROR`: terminal job failure
- `FATAL`: startup or process-level fatal condition

### 12.3 Fixed Event Types
- `SERVICE_STARTED`
- `SERVICE_STOPPED`
- `FILE_DETECTED`
- `FILE_STABILIZING`
- `FILE_CLAIMED`
- `STATE_CHANGED`
- `BARCODE_SCAN_STARTED`
- `BARCODE_SCAN_COMPLETED`
- `VALIDATION_PASSED`
- `VALIDATION_FAILED`
- `OUTPUT_COMMITTED`
- `REJECTION_COMMITTED`
- `RETRY_SCHEDULED`
- `JOB_RECOVERED`
- `JOB_COMPLETED`
- `DEFERRED_REJECTION_PENDING`

### 12.4 Required Fields
Every `LogEntry` must include:
- `timestamp_utc`
- `sequence`
- `severity`
- `event_type`
- `message`

For job-scoped events, the following are also required:
- `job_id`
- `correlation_id`
- `state`
- `source_path`

For terminal events, the following are also required:
- `error_code` for failures
- `barcode_value` and `target_path` for success

For barcode-validation events, the following are also required:
- `eligible_candidate_values`

### 12.5 Correlation and Tracing
- `correlation_id` equals `job_id`.
- All log entries for one source file use the same `correlation_id`.
- A file is traced end-to-end by filtering logs on `correlation_id`.
- The terminal trace guarantee is exactly one `JOB_COMPLETED` event per `job_id`.

### 12.6 Retention
- Log retention is 90 days by default.
- Retention deletes only whole daily log files older than the retention window.
- Log deletion never occurs during active writes to the same file.

## 13. Crash Recovery Rules

### 13.1 Recovery Source of Truth
- `data/processing/{job_id}.job.json` is the durable recovery journal.
- `data/output` is authoritative for committed successes.
- `data/rejected` is authoritative for committed failures.

### 13.2 Startup Recovery Sequence
1. Acquire the singleton mutex.
2. Load configuration and validate paths.
3. Scan `data/processing`.
4. Delete orphan temp files matching `*.pdf.tmp`.
5. Read every `*.job.json`.
6. For each claimed source file without a matching journal, reconstruct a minimal journal from the `job_id` prefix in the processing filename and set `attempt_number = 1`.
7. For each journal:
   - if `target_output_path` is non-null and that output PDF exists, complete success cleanup by deleting the claimed source and journal
   - else if a rejected file exists with the prefix `{job_id}__`, delete the journal
   - else re-enqueue the claimed source at `attempt_number` stored in the journal
8. Emit one `JOB_RECOVERED` log entry per recovered journal.

### 13.3 Mid-Process Crash Rules
- Crash before claim: file remains in `data/input` and is rediscovered.
- Crash after claim but before journal creation: recovery reconstructs the missing journal from the processing filename and restarts the job from `PROCESSING`.
- Crash after claim and after journal creation but before terminal commit: job restarts from the beginning of `PROCESSING` using the claimed source in `data/processing`.
- Crash after output commit but before source cleanup: recovery deletes the claimed source and journal; output remains unchanged.
- Crash after rejection commit but before journal cleanup: recovery deletes the journal; rejected file remains unchanged.

### 13.4 Data Loss Prevention
- Source files remain intact until terminal commit succeeds.
- Temp PDFs are disposable and may be deleted during recovery.
- No terminal state is inferred from memory-only state; only filesystem artifacts and journals are trusted.

## 14. Storage Guarantees

### 14.1 Immutability Rules
- Files in `data/output` are immutable after commit and are never overwritten.
- Files in `data/rejected` are immutable after commit and are never renamed again.
- Log files are append-only until retention deletion.
- Source files are never edited in place.

### 14.2 Naming Guarantees
- Successful output filename is exactly `{selected_danpack_document_id}.pdf`.
- Barcode filenames are uppercase due to normalization.
- Duplicate output filenames are not versioned and are not overwritten; they are rejected.
- Rejected filename is exactly `{job_id}__{error_code}__{original_file_name}`.

### 14.3 Duplicate Handling
- Duplicate detection is path-based against `data/output/{selected_danpack_document_id}.pdf`.
- If that path exists and duplicate handling is `reject`, the job fails with `DUPLICATE_FILE`.
- Duplicate detection does not inspect file content; filename collision alone is authoritative.

### 14.4 Directory Structure Enforcement
- Barcode Buddy writes only to the five managed directories and `app/config`.
- No module may create nested subdirectories under `data/input`, `data/processing`, `data/output`, or `data/rejected`.
- `data/output` contains only final `.pdf` files.
- `data/rejected` contains only original source files with the rejected naming pattern.
- `data/processing` contains only claimed source files, `*.job.json`, and `*.pdf.tmp`.

## 15. Extensibility Constraints

### 15.1 Isolation Rules
The following module boundaries are fixed and must remain unchanged in future versions:
- Watcher remains the only filesystem-ingest adapter.
- Processor remains the only orchestration module.
- Barcode Engine remains isolated from transport, UI, API, and storage concerns.
- Validator remains the only rules engine for document and barcode acceptance.
- Output Manager remains the only filesystem commit module.
- Logger remains the only audit-log writer.
- Configuration Manager remains the only configuration source.

### 15.2 Future Web UI
- A future web UI may read job status only through Processor-exposed read models and Logger data.
- A future web UI must not read or write managed directories directly.
- A future web UI must not call Barcode Engine or Output Manager directly.

### 15.3 Future Mobile Access
- A future mobile client may consume read-only status data from an API layer.
- Mobile access must remain outside the processing runtime and must never mount managed directories.

### 15.4 Future API Layer
- A future API layer must be an adapter in front of Processor, not a replacement for Processor.
- API-submitted jobs must produce the same `ProcessingJob`, `DocumentObject`, `BarcodeResult`, `ProcessingResult`, and `LogEntry` schemas.
- API ingestion must reuse the same Validator and Output Manager rules without branching behavior.

### 15.5 Non-Negotiable Core Contracts
The following contracts are stable and must remain identical in future versions:
- lifecycle states
- error codes
- output filename rule
- duplicate rejection rule
- barcode normalization rule
- log schema
- single terminal outcome per job
