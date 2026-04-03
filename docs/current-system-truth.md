# Current System Truth

Last updated: 2026-04-03.

Version: 2.0.0 — infrastructure upgrade.

v2.0.0 infrastructure changes:

- config validation migrated from frozen dataclass to Pydantic v2 `BaseModel` with computed fields and model validators
- structured logging via structlog with context binding (`contextvars`)
- barcode image preprocessing upgraded from Pillow filters to OpenCV pipeline (denoise, CLAHE, adaptive threshold, morphological close)
- file system watching upgraded from `time.sleep` polling to watchfiles (Rust `notify` backend)
- heartbeat scheduling via APScheduler `BackgroundScheduler`
- stats dashboard migrated from stdlib `http.server` to FastAPI + uvicorn with `/api/stats` JSON endpoint, `/health` health check, and `/docs` OpenAPI docs
- all JSONL log writes and journal writes now fsynced for durability
- graceful shutdown via `SIGINT` and `SIGTERM` signal handlers
- dead `ocr.py` module removed (surya-ocr dependency eliminated)
- `barcode_generator.py` and `watcher.py` retained as utility modules
- unused dependencies removed: `surya-ocr`, `pydantic-settings`
- duplicated validation logic consolidated — Pydantic model validators are the single source of truth
- `pyproject.toml` and `.python-version` added
- Python 3.10 through 3.13 is required; 3.14 is not yet supported by all native dependencies

This is a short pointer document for builders.

Read these in order:

1. `README.md`
2. `docs/danpack-builder-handoff.md`
3. `docs/production-operations-blueprint.md`
4. `docs/builder-execution-plan.md`
5. `docs/scan-record-workbench.md` if you are implementing the owner-facing scan page
6. `docs/scan-record-builder-handoff.md` if you are implementing the owner-facing scan page
7. `docs/operations-planner-product-spec.md` if you are implementing the planner, reporting, or obligation system
8. `docs/operations-planner-technical-spec.md` if you are implementing the planner, reporting, or obligation system
9. `docs/operations-planner-builder-handoff.md` if you are implementing the planner, reporting, or obligation system
10. `docs/danpack-system-interaction-philosophy.md`
11. `tests/`
12. `configs/`
13. `config.schema.json`
14. the code in `main.py`, `stats.py`, and `app/`
15. `TECHNICAL_ARCHITECTURE_SPECIFICATION.md` only as target-state design

Before changing runtime behavior, rerun:

- `py -B -m unittest discover -s tests -v`
- `py -m compileall app tests main.py stats.py`

Environment constraints:

- this workspace is a Git repository; this workspace may not be a Git checkout in all deployment contexts, so do not assume commit history or PR metadata exists
- the codebase plus tests are the runtime truth
- `TECHNICAL_ARCHITECTURE_SPECIFICATION.md` is ahead of the implementation and must not override verified runtime behavior
- the current config contract now includes `workflow_key`, and example configs declare explicit workflow identities
- current log events and rejection sidecars include `schema_version`, `workflow`, `host`, `instance_id`, `config_version`, and `error_code`
- current supported file handling includes magic-byte validation before deep parser handoff
- the worker now acquires a per-workflow startup lock before recovery and polling begin
- current restart recovery uses a per-file journal under `processing/.journal` plus explicit recovery log records
- the worker now emits `startup`, `heartbeat`, and `shutdown` lifecycle events, and the stats surface derives health from them
- the active log now rotates locally by day into date-stamped archives, and `stats.py` reads both the active log and archived logs
