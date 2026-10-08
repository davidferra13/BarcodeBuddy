# Scan workflow recovery — October 8, 2026

Accepted camera/browser work continued in `BarcodeBuddy-worktrees/scan-browser-release-20261007-150228`. The formerly clean candidate was fast-forwarded from 3b8b56f to current main 8e7e45d before implementation. The dirty canonical checkout and its running legacy service on port 8080 were preserved.

Changed `app/scan_to_pdf.py`: browsers without a working BarcodeDetector use the existing authenticated decoder, with one bounded request at a time, cancellation on stop/navigation, retryable permission/decoder errors and an aiming guide. Unreadable saved-session bytes are preserved in a recovery key before a new session can replace them; unavailable browser storage leaves scans usable in memory with an export warning. Upload failure and empty results release the input for retry. No authentication, barcode rules, scanner, processor, FSM, or production configuration changed.

Fresh Windows baseline and regression runs each passed 490 tests, 70 subtests, two skips. The two skipped native PowerShell probes remain release blockers unless the existing launcher gate produces actual successful execution and parser evidence.

Nine rendered checks passed against a separately provisioned loopback runtime: real PNG upload, reload persistence, failed-upload retry, corrupt/malformed storage recovery, quota failure, synthetic camera through the real server decoder without BarcodeDetector, permission denial, stopped-request cancellation, aiming guide, mobile fit and real PDF export. Several related assertions belong to one check. Synthetic MediaStream proof does not establish physical phone-camera behavior. The phone remains CapCut-owned.

The first generated test image was white on white; it was retained as failed fixture evidence and replaced by a black barcode that the real decoder verified. The first storage check raced pending enrichment; the final reproducible test waits for the completed upload status. These harness corrections did not relax product assertions.

Reproduce with a new synthetic customer configuration and its own database/runtime paths. Install runtime dependencies using `requirements.txt` and `constraints.txt`, with pytest 9.1.1 for regression checks. Generate a Code128 PNG containing `BB-RECOVERY-01` (black bars on white), place it at `<proof-directory>/fixture.png`, and start the actual stats server on an unused loopback port. Run the browser helper with Node and a separately installed Playwright/Chrome:

```
BB_PROOF_SCOPE=isolated-synthetic
BB_PROOF_URL=http://127.0.0.1:<isolated-port>
BB_PROOF_OUT=<absolute-proof-directory>
BB_PLAYWRIGHT_MODULE=<optional-file-URL-to-playwright-index.mjs>
node scripts/verify_scan_browser.mjs
```

The helper creates only a synthetic account in the explicitly isolated local server. It never connects to the physical phone. Keep credentials/configuration out of commits. The evidence root for this session is `C:/Users/david/AppData/Local/Temp/barcode-recovery-20261008-1525`.

Release status is partial until native launcher and existing product release gates pass. The separately recorded barcode-free-page timeout remains open behind its protected scanner/processor ownership boundary. No commercial/customer-ready claim is made from these synthetic checks.
