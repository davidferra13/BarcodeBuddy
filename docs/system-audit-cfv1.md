# Phase 1 - System Audit: CFv1 Infrastructure

> Date: 2026-04-04
> Purpose: Document the complete infrastructure of the CFv1 gold standard system for replication into BarcodeBuddy.

---

## 1. Agent Architecture

CFv1 runs up to 5 concurrent agent worktrees, each an isolated git environment with full project access:

- **Planner Agent** - reads codebase, writes specs (no code changes)
- **Builder Agent** - implements specs with continuous verification
- **QA Tester Agent** - tests via Playwright, read-only exploration
- **Research Agent** - investigates questions, produces written reports with citations
- **General/Verification Agent** - runs health checks, verification protocols

Each worktree contains: own `.claude/settings.json`, `.constraints/` (5 files), `.patches/handoff.md`, and complete application code.

Agent definitions live in `.claude/agents/` (e.g., `qa-tester/qa-tester.md`).

## 2. Agent Communication

### Spec Files (`docs/specs/*.md`)
Central task queue. Statuses: draft -> ready -> in-progress -> built -> verified. Priority levels P0-P3. Dependency tracking between specs. Template in `_TEMPLATE.md` with mandatory Developer Notes section.

### Handoff File (`.patches/handoff.md`)
Current branch state snapshot: stack, recent work, key patterns, what NOT to touch. Updated by agents, read by Continue drafter.

### Session Log (`docs/session-log.md`)
Timestamped append-only record. Each entry: agent type, task, status, files touched, commits, build state, notes for next agent.

### Session Digests (`docs/session-digests/`)
Per-session summaries: what was discussed, decisions made, unresolved items. Named `YYYY-MM-DD-HHMMSS-description.md`.

### Build State (`docs/build-state.md`)
Green/broken status for typecheck and build. Last verified commit hash. 10-entry history table. Pre-flight caveat.

## 3. Task Lifecycle

1. **Creation** - Developer describes work in plain English
2. **Spec Writing** - Planner reads codebase deeply, writes spec with Developer Notes, 14-point validation
3. **Queue** - Spec enters `docs/specs/` with status `draft`, developer approves to `ready`
4. **Claim** - Builder scans queue, picks first buildable `ready` spec (priority + dependency order), changes to `in-progress`
5. **Pre-Flight** - git status clean, typecheck passes, build passes
6. **Spike** - Read every spec-named file, report accuracy, flag discrepancies
7. **Build** - Implement with continuous verification (tsc after each major change)
8. **Final Verification** - Typecheck + build + Playwright + edge cases + regression + before/after evidence
9. **Completion** - Update spec timeline, status -> verified, commit, push, write digest

## 4. Constraint System

5 JSON files in `.constraints/`:

| File | Domain |
|---|---|
| `event-fsm.json` | 8-state event lifecycle, transition rules, audit trail |
| `financial-integrity.json` | Money in cents, immutable ledger, computed balances |
| `privacy-boundary.json` | Ollama-only for PII, hard-fail if offline |
| `server-actions.json` | 'use server' patterns, auth-first, tenant from session |
| `tier-gating.json` | Free vs Pro feature boundaries |

## 5. Skills (11 Total)

| Skill | Purpose | Invocable |
|---|---|---|
| `planner` | Spec writing gate | agent-only |
| `builder` | Execution gate | agent-only |
| `research` | Investigation gate | agent-only |
| `verify` | Full verification protocol | yes |
| `health` | Quick health check | yes |
| `ship` | Git add + commit + push | yes |
| `close-session` | Session cleanup | yes |
| `pre-flight` | Pre-build checks | yes |
| `hallucination-scan` | Honesty audit | yes |
| `feature-closeout` | Close-out procedure | yes |
| `soak` | Memory/load testing | yes |

## 6. Hooks

- `build-guard.sh` - PreToolUse hook on Bash. Blocks `next build` and `tsc` when `.multi-agent-lock` exists. Prevents concurrent build corruption.
- `notify.sh` - Notification hook. Sends Windows toast notification when agent needs user input.

## 7. Quality Systems

- **3-Strike Anti-Loop Rule** - 3 failures on same issue = hard stop and report
- **Zero Hallucination Audit** - systematic scan for fake success, hidden failures, non-functional features
- **Pre-Flight Checks** - mandatory verification before writing any code
- **Aggressive Definition of Done** - verified in real app, honest about failure, protected against drift

## 8. Policy Files

- `CLAUDE.md` (36KB) - comprehensive project rules, read at every session start
- `AGENT-WORKFLOW.md` - pre-start, health, post-work, multi-agent rules
- `AI_POLICY.md` - AI-as-draft-only boundaries

## 9. Session Awareness

- On start: read product blueprint, session digests, build state
- On end: log departure, write digest, update docs, commit, push
- Self-maintaining: CLAUDE.md updated when new patterns emerge
