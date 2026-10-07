# Launcher ingestion and customer identity, 2026-10-07 (Claude)

Branch `fix/launcher-ingestion-and-identity-20261007`, one commit on top of `feature/verified-release-20261006-2033` at 5145a8d. Fast-forwards onto it. Not pushed.

## Why this branch exists

`feature/verified-release-20261006-2033` is the leading line. `feature/10k-release-20261006` (a970be7) built the same acceptance, backup, gate and documents in parallel on the evening of 10-06 and is superseded by it. This branch carries only the two things the leading line did not have. Do not continue the 10k-release branch.

## Changes

1. `start-app.ps1` now starts and supervises the ingestion service (`main.py`) with the same customer config as the web app, and restarts it in the watch loop. Before this, the launcher and the logon task started only the web app, so after a restart nothing watched the scan folder. `-NoIngestion` opts out. `install-autostart.ps1` passes it through.
2. No customer identity in the core launcher. The hard-coded public hostname is gone. A named tunnel now needs `-PublicHostname <dns name>` (or `BARCODEBUDDY_PUBLIC_HOSTNAME`) in addition to `-Tunnel`; the value is validated as a plain DNS name before anything starts. The AI system prompt no longer names a customer.
3. `docs/customer/INSTALL.md` gains an unattended-operation section.
4. Three static guards in `tests/test_windows_scripts.py`.

## Evidence

- Full suite on this PC: 447 passed, 2 skipped, 70 subtests, 362s. The two skips are the PowerShell parser and launcher probe, which still cannot start on this host.
- Because PowerShell is unusable on this PC, the four `.ps1` files were copied byte-for-byte (SHA-256 matched) to a Linux workspace and checked with PowerShell 7.4.6:
  - `Parser::ParseFile` reported zero errors for start-app, install-autostart, provision-customer and update-app. A deliberately broken script was rejected by the same check.
  - `start-app.ps1` was executed with a stub interpreter and a config path containing spaces. Observed: preflight ran, web app started with `--config <path> --host 127.0.0.1 --port 8093` (port read from the config), ingestion started with the same config, the stub ingestion exited with code 3 and the watch loop started it again.
  - `-NoIngestion` started the web app only and printed the warning.
  - `-PublicHostname "bad host!"` threw before any process was started.
- This is PowerShell 7 on Linux. It is not Windows PowerShell 5.1 and it is not a customer PC. The release gate's native parser and launcher proof remain open.

## Left alone on purpose

- `app/auth.py` line 29, `DEFAULT_OWNER_EMAIL`, is one named person's address at one customer. It is used when `BB_OWNER_EMAIL` is not set. The repository rules require explicit owner approval before auth changes, so it is unchanged. It should become empty before a second customer install.
- `README.md` and the builder documents still describe the first customer. Tests assert those documents, and the other build line plans to move that identity into a customer profile.
- Scheduled-task registration has not been run (needs elevation at the machine).
