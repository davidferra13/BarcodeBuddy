# Accept the customer's document workflow

Work on redacted copies with known routing identifiers and expected outcomes. Include normal scans, rotated scans, repeated pages, duplicate IDs, blank scans, unreadable scans, incorrect barcode patterns and conflicting routing IDs. Preserve the originals.

Create a manifest using acceptance/example-manifest.json. For successful cases include the exact expected barcode; for failures include the expected reason.

```powershell
.\.venv\Scripts\python.exe scripts/run_acceptance.py --config ".\config.customer.json" --manifest "C:\Samples\manifest.json" --report-dir "C:\Acceptance\receiving"
```

The runner executes the real processor in an isolated temporary workspace. JSON and Markdown reports retain sample hashes and expected/actual outcomes, not document contents. Exit 0 means all listed expectations matched. Review the association and output PDF, not just the decoded barcode.

Never point a report output at a source document or the source manifest. A failed run blocks this workflow's acceptance. Correct the configuration or supported defect and rerun the same originals as copies.

Acceptance of one workflow does not establish compatibility with every scanner or document type. Record the tested scanner, sample set, application revision and operator signoff in the customer's private handoff.
