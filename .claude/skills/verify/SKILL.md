---
name: verify
description: Run the full BarcodeBuddy verification protocol - spec audit, build integrity, and test pressure.
user-invocable: true
---

# BarcodeBuddy Verification Protocol

The system is considered fully up to date and complete. Your job is to prove that claim, not trust it.

Do not ask questions. Do not stop early. Run all phases autonomously.

## GLOBAL RULES

- No new feature work
- No refactors unless required to fix a verified issue
- Do not trust "marked complete" - verify behavior
- Evidence > claims

## PHASE 1 - RECENT WORK INVENTORY

Identify everything completed recently (last 14-30 days).

Pull from:

- `docs/specs/` (check status fields)
- `git log --oneline --since="14 days ago"`
- Recently modified files in `app/`

Build a structured inventory: feature name, spec reference, files involved, endpoints, expected behavior.

## PHASE 2 - SPEC TO CODE TO RUNTIME VALIDATION

For each inventory item, verify:

1. Spec exists (if applicable)
2. Code exists
3. Code is wired (routes registered, models imported)
4. Feature runs (tests pass, endpoint responds)
5. Behavior matches spec intent

Classify each: VERIFIED / PARTIAL / MISSING / UNPROVEN

## PHASE 3 - BUILD CONFIRMATION

```bash
# Compilation check
py -m compileall app tests main.py stats.py -q

# Full test suite
py -3.12 -B -m pytest tests/ -x -q
```

Both must exit 0. Capture and paste full output.

## PHASE 4 - SERVER HEALTH (If Running)

```bash
# Health endpoint
curl -s http://localhost:8080/health

# Metrics endpoint
curl -s http://localhost:8080/metrics | head -20
```

If server is not running, note it and skip.

## PHASE 5 - TEST PRESSURE

Run the full test suite with verbose output to catch flaky tests:

```bash
py -3.12 -B -m pytest tests/ -v --tb=short
```

Look for:
- Tests that pass inconsistently
- Tests with hardcoded paths or dates
- Tests that depend on external state
- Tests that take abnormally long

## PHASE 6 - ISSUE CLASSIFICATION

Classify findings:

- BLOCKING (prevents core usage)
- CRITICAL (major feature broken)
- MINOR (non-blocking)

## PHASE 7 - SURGICAL FIX PASS (IF NEEDED)

If BLOCKING or CRITICAL issues exist:

- Apply minimal fixes
- Do not expand scope
- Re-run affected tests
- Capture before/after evidence

## PHASE 8 - FINAL REPORT

1. Recent Work Inventory
2. Validation Matrix (spec -> code -> runtime)
3. Build Proof (compilation + test output)
4. Server Health Results
5. Test Pressure Results
6. Issues Found (classified)
7. Fixes Applied (if any)
8. Final Verdict

Final Verdict must answer:

- Is everything marked complete actually complete?
- Do all tests pass?
- Is any work still required?
- What breaks under pressure?
