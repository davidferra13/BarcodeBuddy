# Current System Truth

Last updated: 2026-04-03.

Version: 1.0.0 — first release.

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

- this workspace is a Git repository as of v1.0.0; this workspace may not be a Git checkout in all deployment contexts, so do not assume commit history or PR metadata exists
- the codebase plus tests are the runtime truth
- `TECHNICAL_ARCHITECTURE_SPECIFICATION.md` is ahead of the implementation and must not override verified runtime behavior
- the current config contract now includes `workflow_key`, and example configs declare explicit workflow identities
- current log events and rejection sidecars include `schema_version`, `workflow`, `host`, `instance_id`, `config_version`, and `error_code`
- current supported file handling includes magic-byte validation before deep parser handoff
- the worker now acquires a per-workflow startup lock before recovery and polling begin
- current restart recovery uses a per-file journal under `processing/.journal` plus explicit recovery log records
- the worker now emits `startup`, `heartbeat`, and `shutdown` lifecycle events, and the stats surface derives health from them
- the active log now rotates locally by day into date-stamped archives, and `stats.py` reads both the active log and archived logs
