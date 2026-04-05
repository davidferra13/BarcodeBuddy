---
name: hallucination-scan
description: Run the full Zero Hallucination audit - silent failures, no-op handlers, hardcoded values, dead endpoints, untested paths.
disable-model-invocation: true
---

# Zero Hallucination Scan

Run the full audit. Report findings organized by severity.

## Checks

1. **Silent failures** - search for `except` blocks that return default/empty values without logging or user feedback. Every exception handler must either: log the error, surface it to the user, or have a documented reason for swallowing it.

2. **No-op handlers** - search for route handlers or event handlers with empty bodies, `pass` statements, `# TODO`, `# placeholder`, or `return {"success": True}` on functions that don't actually persist anything.

3. **Hardcoded display values** - search for hardcoded counts, percentages, or metrics in templates/responses that aren't computed from real data. Any number shown to a user must come from a query or calculation.

4. **Dead endpoints** - search for routes registered in FastAPI that have no corresponding UI link, test, or documented consumer. Unreachable endpoints are hallucinated features.

5. **Untested paths** - search for functions in `app/` that have no corresponding test in `tests/`. Focus on business logic, not utility helpers.

6. **Stale imports** - search for `import` statements where the imported name is never used in the file.

7. **False empty states** - search for UI templates or API responses that show "0" or empty lists where they should show "no data available" or a proper empty state.

## Report Format

For each finding:

```
### [SEVERITY] Finding: [description]
- File: [path:line]
- What's wrong: [explanation]
- Fix: [recommended action]
```

Severity levels: BLOCKING / CRITICAL / MINOR

## After the Scan

If BLOCKING or CRITICAL findings exist, fix them immediately and re-verify. For MINOR findings, document them but do not fix unless instructed.
