# Spec Queue System

This directory is the task queue for BarcodeBuddy development. Specs define what gets built, in what order, and how it's verified.

---

## How It Works

### Spec Lifecycle

```
Developer describes work
    |
Planner Agent writes spec (status: draft)
    |
Developer reviews and approves (status: ready)
    |
Builder Agent claims spec (status: in-progress)
    |
Builder implements with continuous verification
    |
Builder runs final verification (status: verified)
```

### Statuses

| Status | Meaning |
|---|---|
| `draft` | Spec written, not yet reviewed by developer |
| `ready` | Developer approved, available for builders |
| `in-progress` | Claimed by a builder agent |
| `built` | Code written, verification pending |
| `verified` | All verification passed, work complete |

### Priority

| Level | Meaning |
|---|---|
| P0 | Blocking - must be done before anything else |
| P1 | Next up - high priority |
| P2 | Queued - will be done soon |
| P3 | Backlog - eventually |

---

## For Planner Agents

1. Read `CLAUDE.md` cover to cover
2. Read `_TEMPLATE.md` for the required spec format
3. Read `docs/session-log.md` (last 5 entries) and `docs/build-state.md`
4. Deep-inspect the codebase (follow imports 2 levels, read relevant files)
5. Write the spec using the template
6. Capture Developer Notes (mandatory)
7. Run Spec Validation (14-point checklist with cited evidence)

Full procedure: `.claude/skills/planner/SKILL.md`

---

## For Builder Agents

### Queue Selection

1. Scan every file in `docs/specs/`
2. Filter: only `ready` specs whose dependencies are `verified`
3. Sort by priority: P0 first, then P1, P2, P3
4. Pick the first buildable spec
5. Claim it: change status to `in-progress`, add Timeline entry, commit

### Build Process

1. Pre-flight check (git clean, compilation passes, tests pass)
2. Spike (read every file the spec names, report accuracy)
3. Build with continuous verification
4. Final verification with pasted output
5. Update spec status to `verified`

Full procedure: `.claude/skills/builder/SKILL.md`

---

## File Naming

Spec files use kebab-case: `feature-name.md`

Examples:
- `scan-record-workbench.md`
- `operations-planner-reporting.md`
- `inventory-bulk-operations.md`
