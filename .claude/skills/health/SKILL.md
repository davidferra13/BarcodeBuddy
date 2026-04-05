---
name: health
description: Quick health check for BarcodeBuddy - compilation, tests, server status, database, and git state.
user-invocable: true
---

# BarcodeBuddy Health Check

Run these checks in order. Report results concisely.

## 1. Compilation Check

```bash
py -m compileall app tests main.py stats.py -q
```

Expected: exit 0, no errors

## 2. Test Suite

```bash
py -3.12 -B -m pytest tests/ -x -q
```

Expected: all tests pass

## 3. Server Status (if running)

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/health
```

Expected: 200

## 4. Database Integrity

```bash
py -c "import sqlite3; c=sqlite3.connect('data/barcode_buddy.db'); c.execute('PRAGMA integrity_check'); print(c.fetchone())"
```

Expected: ('ok',)

## 5. Git Status

```bash
git status --short
git log --oneline -5
```

Report: clean/dirty, last 5 commits

## Report Format

| Check | Result |
|---|---|
| Compilation | PASS / FAIL (error count) |
| Tests | PASS / FAIL (X passed, Y failed) |
| Server (8080) | UP / DOWN / NOT RUNNING |
| Database | HEALTHY / UNHEALTHY / NOT FOUND |
| Git | CLEAN / DIRTY (file count) |

If any check fails, flag it with the exact error.
