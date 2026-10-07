# Verify this product revision

From the installed candidate:

```powershell
.\.venv\Scripts\python.exe scripts/release_gate.py --report-dir "C:\ReleaseEvidence\BarcodeBuddy" --acquisition-repo "C:\BuiltToOwn"
```

Use a fresh evidence directory outside the source checkout. The gate runs compilation, full native tests, launcher checks, config validation, installation-secret checks, real synthetic acceptance, SQLite backup round-trip, package completeness, clean Git revision and Built To Own verification.

Every mandatory gate must pass. Missing, failed or timed-out evidence leaves ready=false and returns a nonzero exit code. Parser-unavailable skips stay explicit in the hashed launcher log.

For a particular customer, additionally pass --customer-config and --customer-manifest together. Product reference readiness and customer acceptance are distinct. The receipt never declares a buyer deployed.

Keep receipts and logs private. They bind to the tested Git revision and contain hashes instead of document payloads. Commit changes before the final gate; do not change source while it runs.
