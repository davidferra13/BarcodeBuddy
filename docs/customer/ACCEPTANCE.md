# Accept the customer's document workflow

Work on redacted copies with known routing identifiers and expected outcomes. Include normal scans, rotated scans, repeated pages, duplicate IDs, blank scans, unreadable scans, incorrect barcode patterns and conflicting routing IDs. Preserve the originals.

Create a manifest using acceptance/example-manifest.json. For successful cases include the exact expected barcode; for failures include the expected reason.

```powershell
.\.venv\Scripts\python.exe scripts/run_acceptance.py --config ".\config.customer.json" --manifest "C:\Samples\manifest.json" --report-dir "C:\Acceptance\receiving"
```

The runner executes the real processor in an isolated temporary workspace. JSON and Markdown reports retain sample hashes and expected/actual outcomes, not document contents. Exit 0 means all listed expectations matched. The temporary outputs are deleted when the runner finishes. For visual review, process separate redacted copies in a disposable installation and inspect the generated PDFs and rejected-file sidecars there before handoff. Do not reconnect that installation to a live scan folder.

Never point a report output at a source document or the source manifest. A failed run blocks this workflow's acceptance. Correct the configuration or supported defect and rerun the same originals as copies.

Acceptance of one workflow does not establish compatibility with every scanner or document type. Record the tested scanner, sample set, application revision and operator signoff in the customer's private handoff.

Conflicts are detected only on inspected pages. For mixed-document acceptance, enable scan_all_pages and set max_pages_scan at least as high as the document's page count. Exceeding that hard page-count cap rejects the entire document with PROCESSING_TIMEOUT before decoding. With scan_all_pages=false and a sufficient cap, later-page identifiers are outside the configured scan scope. Conflicting eligible identifiers must reject with AMBIGUOUS_BARCODE. Repeated occurrences of one identifier remain a valid document. Mixed documents require manual separation and resubmission.
