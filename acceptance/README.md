# Customer sample acceptance

Use this harness before promising a workflow is production-ready.

1. Put redacted customer samples in a directory beside a copied manifest.
2. Set each case's expected status and, when known, expected barcode or failure reason.
3. Run:

```text
python scripts/run_acceptance.py --config config.customer.json --manifest acceptance/customer-manifest.json --report-dir acceptance/reports
```

The harness copies every source into a temporary isolated BarcodeBuddy runtime and invokes the real `BarcodeBuddyService.process_file()` path. It never processes the supplied file in place. The JSON and Markdown receipts store the sample's relative filename, SHA-256 hash, expected outcome, actual outcome, and verdict. They do not embed document contents.

A zero exit code means every case matched. Any mismatch returns exit code 1. Invalid manifests fail before processing.

The example manifest is a template only; replace its sample paths with real redacted files before running it.
