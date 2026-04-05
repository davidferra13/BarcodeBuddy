# BarcodeBuddy - Project Handoff

> Current state snapshot for the Continue drafter. Updated by Claude Code.

## Stack

- Python 3.12 (CPython)
- FastAPI + Uvicorn (web server)
- SQLAlchemy + SQLite (WAL mode, 14 models)
- structlog + JSONL (structured logging)
- Pydantic v2 (config validation)
- APScheduler (background jobs)
- watchfiles (file system monitoring, Rust notify backend)
- pyzbar + OpenCV (barcode detection)
- Ollama / Anthropic / OpenAI (AI integration)
- JWT + bcrypt (authentication)

## Current Branch

`main`

## Recent Work

- v3.0.0: AI integration, team management, activity logging, inventory enhancements
- v2.0.0: Pydantic config, structlog, OpenCV barcode preprocessing, watchfiles, FastAPI migration
- Docker and Railway deployment infrastructure
- Complete system reference documentation

## Key Patterns

- Single service class (`BarcodeBuddyService`) owns all file processing
- File state machine: INPUT -> STABILIZING -> PROCESSING -> VALIDATING -> SUCCESS/FAILURE
- Journal-based crash recovery in `processing/.journal`
- Atomic file moves via `shutil.move`
- JSONL append-only logging with daily rotation
- JWT cookie auth with role hierarchy: owner > admin > manager > user
- First signup must use owner email (`BB_OWNER_EMAIL`)
- Inventory transactions are ledger-style (append-only)
- Error codes in `app/contracts.py` are canonical
- Config is immutable after startup (Pydantic v2 frozen model)
- Background scheduler: stock alerts (5min), DB backup (daily), session revocation (hourly)

## What NOT to Touch

- `app/processor.py` state machine logic (file FSM is load-bearing)
- `app/contracts.py` error codes (downstream systems depend on these)
- `app/auth.py` JWT/session logic (security-critical)
- `config.schema.json` (contract with operators)
- `app/database.py` model definitions (without migration planning)
