---
name: soak
description: Run load and memory testing for the FastAPI application - endpoint stress, memory profiling, and stability checks.
disable-model-invocation: true
---

# Soak Testing - BarcodeBuddy

Run the full soak pipeline in order. The web server must be running on port 8080.

## Phase 1: Endpoint Stress Test

Hit key endpoints repeatedly to check for memory leaks and stability:

```bash
# Health endpoint (100 requests)
for i in $(seq 1 100); do curl -s -o /dev/null -w "%{http_code} " http://localhost:8080/health; done

# Stats API (50 requests)
for i in $(seq 1 50); do curl -s -o /dev/null -w "%{http_code} " http://localhost:8080/api/stats; done

# Metrics endpoint (50 requests)
for i in $(seq 1 50); do curl -s -o /dev/null -w "%{http_code} " http://localhost:8080/metrics; done
```

All requests must return 200. Any non-200 is a failure.

## Phase 2: Memory Baseline

Check Python process memory before and after stress:

```bash
# Get process memory (if server is running)
py -c "
import psutil
for p in psutil.process_iter(['name', 'memory_info']):
    if 'python' in p.info['name'].lower():
        mem = p.info['memory_info']
        print(f'{p.info[\"name\"]}: RSS={mem.rss/1024/1024:.1f}MB')
"
```

Memory growth > 2x baseline after stress = potential leak.

## Phase 3: Database Stability

```bash
py -c "
import sqlite3
c = sqlite3.connect('data/barcode_buddy.db')
print('Integrity:', c.execute('PRAGMA integrity_check').fetchone())
print('WAL mode:', c.execute('PRAGMA journal_mode').fetchone())
print('Page count:', c.execute('PRAGMA page_count').fetchone())
print('Free pages:', c.execute('PRAGMA freelist_count').fetchone())
c.close()
"
```

## Phase 4: Test Suite Under Load

Run full test suite to verify nothing broke:

```bash
py -3.12 -B -m pytest tests/ -x -q
```

## Report

| Check | Result |
|---|---|
| Health stress (100 req) | X/100 succeeded |
| Stats stress (50 req) | X/50 succeeded |
| Metrics stress (50 req) | X/50 succeeded |
| Memory baseline | X MB RSS |
| Memory after stress | X MB RSS (Xn growth) |
| DB integrity | ok / corrupted |
| Test suite | PASS / FAIL |

If any check fails, diagnose and report. Do not attempt fixes during soak - report findings for a builder.
