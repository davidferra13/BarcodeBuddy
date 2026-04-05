# Agent Workflow - BarcodeBuddy

This document defines agent behavior before, during, and after work sessions. All agents must follow this protocol.

---

## Before Starting Work

Every agent runs these checks before writing any code:

### 1. Orientation

```bash
# What branch am I on?
git branch --show-current

# Is the repo clean?
git status --short

# What happened recently?
git log --oneline -10

# Is there in-progress work from another agent?
cat docs/session-log.md | tail -30
```

### 2. Health Check

```bash
# Compilation check
py -m compileall app tests main.py stats.py -q

# Test suite
py -3.12 -B -m pytest tests/ -x -q
```

If either fails, you are NOT allowed to write new feature code. Fix the existing break first, or report it to the developer.

### 3. Context Loading

1. Read `CLAUDE.md` (this is mandatory, every session)
2. Read `docs/build-state.md` (is the build green?)
3. Skim `docs/session-log.md` (last 3-5 entries)
4. Read latest session digest in `docs/session-digests/` if exists

---

## During Work

### Continuous Verification

After every significant change (new function, major edit, or completing a logical unit):

```bash
py -m compileall app/ -q
```

If it fails, fix it NOW. Do not accumulate errors.

### Anti-Loop Rule

3 failures on the same issue = STOP and report. See `CLAUDE.md` for details.

### File Safety

- All file moves use atomic operations (shutil.move or os.rename)
- Never delete files in `data/output/` or `data/logs/`
- Never modify files in `data/rejected/` after creation
- Journal files in `data/processing/.journal` are immutable during processing

---

## After Completing Work

Every agent runs these steps when finishing:

### 1. Verify

```bash
# Full compilation
py -m compileall app tests main.py stats.py -q

# Full test suite
py -3.12 -B -m pytest tests/ -x -q
```

### 2. Commit

```bash
# Stage relevant files (never use git add -A blindly)
git add [specific files]

# Commit with convention
git commit -m "feat(scope): description

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

### 3. Document

Update `docs/session-log.md` with departure entry:

```
## YYYY-MM-DD HH:MM EST
- Agent: [planner | builder | research | qa | general]
- Task: [what you did]
- Status: completed | partial | blocked
- Files touched: [list every file you modified]
- Commits: [commit hashes]
- Build state on departure: [green | broken]
- Notes: [anything the next agent needs to know]
```

### 4. Update Build State

If you ran tests or compilation, update `docs/build-state.md` with current results.

### 5. Push

```bash
git push origin $(git branch --show-current)
```

### 6. Session Digest (if significant work)

Write a digest to `docs/session-digests/YYYY-MM-DD-HHMMSS-description.md`:

- What was discussed or decided
- What was implemented
- What remains unresolved
- Context the next agent needs

---

## Multi-Agent Parallel Rules

When `.multi-agent-lock` exists at project root:

1. **Build guard is active** - `pytest` and `compileall` commands are blocked by the hook
2. **Your job:** write code, commit, stop. Do not attempt test runs.
3. **The developer** will remove the lock and run one clean test pass after all agents finish.

### Preventing Conflicts

- Check `docs/session-log.md` for in-progress work before starting
- If another agent is working on the same area, coordinate or wait
- Never run destructive git operations (`reset --hard`, `clean -f`, `checkout .`)
- Never commit generated files (`.pyc`, `__pycache__/`, `*.db` backups)

---

## Key Commands Reference

| Purpose | Command |
|---|---|
| Compilation check | `py -m compileall app tests main.py stats.py -q` |
| Test suite | `py -3.12 -B -m pytest tests/ -x -q` |
| Server health | `curl -s http://localhost:8080/health` |
| Metrics | `curl -s http://localhost:8080/metrics` |
| Git status | `git status --short` |
| Recent history | `git log --oneline -10` |
| Current branch | `git branch --show-current` |
| Enable multi-agent lock | `touch .multi-agent-lock` |
| Disable multi-agent lock | `rm .multi-agent-lock` |
