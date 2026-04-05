# Spec: [Feature Name]

> **Status:** draft | ready | in-progress | built | verified
> **Priority:** P0 (blocking) | P1 (next up) | P2 (queued) | P3 (backlog)
> **Depends on:** [list spec filenames this depends on, or "none"]
> **Estimated complexity:** small (1-2 files) | medium (3-8 files) | large (9+ files)

## Timeline

_Every status change, every claim, every verification gets a row. This is the audit trail._

| Event                 | Date             | Agent/Session     | Commit |
| --------------------- | ---------------- | ----------------- | ------ |
| Created               | YYYY-MM-DD HH:MM | [planner session] |        |
| Status: ready         | YYYY-MM-DD HH:MM | [planner session] | [hash] |
| Claimed (in-progress) |                  |                   |        |
| Spike completed       |                  |                   |        |
| Pre-flight passed     |                  |                   |        |
| Build completed       |                  |                   |        |
| Tests passed          |                  |                   |        |
| Compilation passed    |                  |                   |        |
| Status: verified      |                  |                   |        |

---

## Developer Notes

_This section preserves the developer's original conversation and intent. It is MANDATORY. A spec without Developer Notes is incomplete. A builder reading a spec without this section is building blind._

### Raw Signal

_The developer's actual words, cleaned up for readability but faithful to what they said. Remove filler and repetition, keep the passion and reasoning. This is the "why behind the why."_

[Developer's words go here]

### Developer Intent

_Translate the raw signal into clear system-level requirements. What were they actually trying to achieve beneath what they said?_

- **Core goal:** [one sentence]
- **Key constraints:** [what must not happen, what must be preserved]
- **Motivation:** [why this matters to the developer right now]
- **Success from the developer's perspective:** [what "done" looks like in their mind]

---

## What This Does (Plain English)

_One paragraph. What does the user see or experience after this is built? Write it so a builder agent with zero prior context understands the goal._

---

## Why It Matters

_One to two sentences. Why are we building this now? What problem does it solve?_

---

## Files to Create

_List every NEW file with its full path and a one-line description._

| File | Purpose |
| ---- | ------- |
| `app/example.py` | New module for X |

---

## Files to Modify

_List every EXISTING file that needs changes. Be specific about what changes._

| File | What to Change |
| ---- | -------------- |
| `app/stats.py` | Add route for /example |
| `app/database.py` | Add ExampleModel class |

---

## Database Changes

_If no DB changes, write "None" and skip the subsections._

### New Models

```python
# Paste the full SQLAlchemy model here
```

### New Columns on Existing Models

```python
# Paste the column additions here
```

### Migration Notes

- SQLAlchemy models auto-create tables on first run (SQLite)
- All migrations are additive. No DROP/DELETE without explicit developer approval.

---

## Data Model

_Describe the key entities and relationships. What fields matter? What are the constraints?_

---

## API Endpoints

_List every endpoint with its method, path, auth requirement, and behavior._

| Method | Path | Auth | Input | Output | Side Effects |
| ------ | ---- | ---- | ----- | ------ | ------------ |
| POST | `/api/example` | `require_role("user")` | `{ name: str }` | `{ success: bool }` | Creates record |

---

## UI / Component Spec

_Describe what the user sees. Be specific: layout, components, states._

### Page Layout

_Describe the page structure. Reference existing patterns from app/layout.py._

### States

- **Loading:** _what shows while data loads_
- **Empty:** _what shows when there's no data yet_
- **Error:** _what shows when the request fails (never show fake zeros)_
- **Populated:** _what shows with real data_

### Interactions

_What happens when the user clicks, submits, etc. Be specific about error handling._

---

## Edge Cases and Error Handling

_List anything that could go wrong and what the correct behavior is._

| Scenario | Correct Behavior |
| -------- | ---------------- |
| API endpoint fails | Show toast error, do not show stale data |
| User has no data yet | Show empty state with guidance, not zeros |
| Concurrent requests | Last-write-wins with timestamp check |

---

## Verification Steps

_How does the builder agent confirm this works? Be specific._

1. Run `py -m compileall app/ -q` - must exit 0
2. Run `py -3.12 -B -m pytest tests/ -x -q` - must pass
3. Start the server: `py stats.py`
4. Navigate to the feature endpoint
5. Verify: page loads without errors
6. Test the primary user flow
7. Test edge cases listed above

---

## Out of Scope

_What does this spec explicitly NOT cover? Prevents scope creep._

- Not building X (that's a separate spec)
- Not changing Y (out of scope for this feature)

---

## Notes for Builder Agent

_Anything else the builder needs to know: gotchas, patterns to follow, files to reference for similar implementations._
