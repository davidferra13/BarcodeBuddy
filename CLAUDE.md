# BarcodeBuddy - Project Rules

This file is read by Claude Code at the start of every conversation. These rules are mandatory.

---

> **STOP - READ THESE TWO BLOCKS BEFORE DOING ANYTHING**

> **BLOCK 1 - DO YOUR OWN WORK, TEST YOUR OWN WORK, FIX YOUR OWN BUGS**
>
> **NEVER** tell the developer to "check the website," "verify this works," "let me know if it looks right," or "you may want to test." You have a test suite. You have pytest. You have `compileall`. **USE THEM.** After writing code: run tests, verify output, check for regressions. If it's broken: fix it yourself, verify the fix, then report it's done. The developer is NOT your QA team. If you CAN test it, you MUST test it. If you find a bug, you MUST fix it - don't report it back.
>
> **NEVER** wait for the developer to tell you the obvious next step. If you know what comes next, DO IT. If a task has a clear continuation, CONTINUE. Don't pause, don't ask "what would you like me to do next?" - just do the work. The developer is paying per token. Every unnecessary back-and-forth is their money wasted on nothing.
>
> **NEVER** generate padded, hedging, verbose responses when a short one works. Don't add caveats. Don't restate what you're about to do - just do it. Don't offer multiple options when one is clearly correct. Be direct. Be brief. Do the work.

> **BLOCK 2 - READ THIS ENTIRE FILE BEFORE STARTING WORK**
>
> This document contains rules that will prevent you from making expensive mistakes. Every section exists because an agent already made that mistake and it cost real money. Skimming or skipping sections = repeating those mistakes. Read it all. Follow it all.

---

## Quick Reference

- **Product Blueprint:** `docs/PRODUCT_BLUEPRINT.md` is THE finish line. Full capability map, implementation status, and phased roadmap. Read it. Update it when you complete features.
- **Builder Handoff:** `docs/danpack-builder-handoff.md` is the builder-facing source of truth for current repo state.
- **Current System Truth:** `docs/current-system-truth.md` is the short pointer document for builders.
- **Interaction Philosophy:** `docs/danpack-system-interaction-philosophy.md` defines all UI rules.
- **Production Ops:** `docs/production-operations-blueprint.md` defines deployment, observability, and incident handling.
- **Incident Runbook:** `docs/runbooks/incident-response.md` is the primary incident playbook.

- **Stack:** Python 3.12 + FastAPI + SQLAlchemy + SQLite (WAL) + structlog + Pydantic v2 + Ollama/Anthropic/OpenAI
- **Data safety first:** append-only logs, immutable journals, all destructive ops require explicit approval
- **End every session:** commit everything, push the branch, write a session digest, update this file if new rules were found
- **Never:** modify `config.json` at runtime, delete activity_log records, skip auth checks on protected endpoints

---

## ANTI-LOOP RULE (3-STRIKE HARD STOP)

If the same error or issue occurs 3 times after attempted fixes: **STOP.**

- Report what was tried
- Report what failed each time
- Let the developer decide the next step

**What counts as a strike:**
- Same test fails after a fix attempt
- Same compilation error after a code change
- Same runtime error after a config change

**What does NOT count as a strike:**
- Different errors (that's forward progress)
- Reading multiple files to understand a problem
- Making edits across multiple files for one logical change

---

## DATA SAFETY

### Append-Only Systems
- JSONL processing logs: never UPDATE or DELETE
- Activity log (SQLite): append-only audit trail
- Inventory transactions: ledger-style, adjustments create new records
- Journal files: immutable during active processing

### Immutability Rules
- Config is frozen after startup
- Rejection sidecars (.meta.json) are write-once
- Daily log archives are write-once after rotation
- Database backups are never modified after creation

### Dangerous Operations (Require Explicit Approval)
- Deleting database tables or columns
- Modifying activity_log or inventory_transaction records
- Changing auth/session logic
- Modifying the file processing state machine in processor.py
- Altering barcode validation rules in barcode.py

---

## ZERO HALLUCINATION RULE

Three laws:

1. **Never confirm success without evidence.** If you say "tests pass," paste the output. If you say "the endpoint works," show the response. If you say "the file was created," verify it exists.

2. **Never hide failure as zero.** If a query returns no results, show "no data" or "empty" - never show zeros, blank tables, or default values that imply data exists when it doesn't.

3. **Never render non-functional features as functional.** If a button doesn't work yet, don't add it to the UI. If an endpoint isn't wired, don't list it in the API docs. Partial implementations must be clearly labeled or hidden.

---

## AGGRESSIVE DEFINITION OF DONE

A feature is only done when:

1. **Verified via tests** - `py -3.12 -B -m pytest tests/ -x -q` passes with the new code
2. **Verified via compilation** - `py -m compileall app tests main.py stats.py -q` exits 0
3. **Honest about failure** - if something doesn't work, you said so explicitly
4. **Protected against drift** - if the feature depends on config, the schema validates it; if it depends on data, the test creates it

---

## WORKFLOW SKILLS

These slash commands invoke standardized agent procedures:

| Skill | Purpose |
|---|---|
| `/planner` | Full Planner Gate - write a spec from developer intent |
| `/builder` | Full Builder Gate - implement from a spec with continuous verification |
| `/research` | Full Research Gate - investigate and write a findings report |
| `/verify` | Full verification protocol - spec audit, build integrity, test pressure |
| `/health` | Quick health check - compilation, tests, server, database, git |
| `/ship` | Git add + commit + push |
| `/close-session` | Session close-out - commit, push, update session log and build state |
| `/pre-flight` | Pre-build checks - git status, compilation, tests |
| `/hallucination-scan` | Zero Hallucination audit for Python patterns |
| `/feature-closeout` | Feature close-out - compile, test, commit, push |
| `/soak` | Load and memory testing for FastAPI |

---

## FEATURE LOOKUP (3-Tier)

When you need to understand what exists:

1. **Product Blueprint** (`docs/PRODUCT_BLUEPRINT.md`) - what's built, what's planned, what's the roadmap
2. **Builder Handoff** (`docs/danpack-builder-handoff.md`) - current repo state, execution anchors, reading order
3. **Current System Truth** (`docs/current-system-truth.md`) - version history, what the code actually does

---

## SESSION AWARENESS

### On Session Start
1. Read `docs/PRODUCT_BLUEPRINT.md` (skim for current status)
2. Read `docs/build-state.md` (is the build green or broken?)
3. Read latest entries in `docs/session-log.md` (what did the last agent do?)
4. Read latest file in `docs/session-digests/` if one exists (context from last session)

### On Session End
1. Commit all changes
2. Push the branch
3. Append departure entry to `docs/session-log.md`
4. Update `docs/build-state.md` if you ran tests or compilation
5. Write a session digest to `docs/session-digests/` if significant work was done
6. Update this file if new patterns or rules were discovered

---

## AGENT GATES

### Planner Gate
Spec agents must follow `.claude/skills/planner/SKILL.md`. Every claim in a spec must cite file paths and line numbers. No spec is "ready" without evidence-based validation.

### Builder Gate
Builder agents must follow `.claude/skills/builder/SKILL.md`. Pre-flight checks are mandatory. Continuous verification (compileall after each major change). Final verification with pasted output.

### Research Gate
Research agents must follow `.claude/skills/research/SKILL.md`. Every finding cites a file path. No code changes - flag issues in the report for a builder.

---

## DEVELOPMENT WORKFLOW

### Before Making Changes
1. Read the files you're about to modify (not skim - read)
2. Understand the existing patterns
3. Run pre-flight: `py -m compileall app tests main.py stats.py -q`

### During Changes
- Run `py -m compileall app/ -q` after each significant change
- No speculative refactoring
- No "while I'm here" cleanup
- If you discover something unexpected: stop, investigate, then continue

### After Changes
1. Run full test suite: `py -3.12 -B -m pytest tests/ -x -q`
2. Run compilation check: `py -m compileall app tests main.py stats.py -q`
3. If tests fail: fix them before reporting completion

### Commit Convention
- `feat(scope): description` for new features
- `fix(scope): description` for bug fixes
- `docs(scope): description` for documentation
- `refactor(scope): description` for refactoring
- `test(scope): description` for test changes
- Always include `Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>`

---

## CONSTRAINT SYSTEM

Machine-readable domain rules in `.constraints/`:

| File | Enforces |
|---|---|
| `file-processing-fsm.json` | File state transitions, journal integrity, recovery rules |
| `barcode-integrity.json` | Barcode validation, detection, deterministic selection |
| `data-safety.json` | Append-only logs, immutable journals, write-once archives |
| `auth-boundary.json` | JWT auth, RBAC, session management, owner email enforcement |
| `ai-privacy.json` | Local-first AI, no silent cloud fallback, user-controlled providers |

Read the relevant constraint file before modifying any code in that domain. These are NOT suggestions - they are hard rules extracted from the codebase.

---

## HEALTH CHECKS

Run these to verify system health:

```bash
# Compilation check (syntax + imports)
py -m compileall app tests main.py stats.py -q

# Full test suite
py -3.12 -B -m pytest tests/ -x -q

# Server status (if running)
curl -s http://localhost:8080/health

# Git status
git status --short
git log --oneline -5
```

---

## GIT WORKFLOW

- Always push at end of session
- Never force-push main
- Feature branches: `feature/description`
- Fix branches: `fix/description`
- One logical change per commit
- If pre-commit hooks fail: fix the issue, don't bypass with `--no-verify`

---

## MULTI-AGENT RULES

When multiple agents are working concurrently:

1. **Build guard:** `.multi-agent-lock` file blocks test/compile commands when present
2. **No concurrent tests:** only one agent runs pytest at a time
3. **File conflicts:** if two agents need the same file, one waits
4. **Duplicate work:** check `docs/session-log.md` before starting - another agent may already be on it
5. **Generated files:** never commit generated artifacts (`.pyc`, `__pycache__`, `.db` backups)
6. **Destructive git ops:** never `git reset --hard`, `git clean -f`, or `git checkout .` without explicit approval

---

## WHAT NOT TO TOUCH (Without Explicit Approval)

- `app/processor.py` state machine logic (file FSM is load-bearing)
- `app/contracts.py` error codes (downstream systems depend on these)
- `app/auth.py` JWT/session logic (security-critical)
- `config.schema.json` (contract with operators)
- Database migration patterns in `app/database.py` model definitions
