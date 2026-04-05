# Phase 3 - Adoption Plan: CFv1 Infrastructure into BarcodeBuddy

> Date: 2026-04-04
> Purpose: Document the integration strategy, file mapping, and order of operations for the infrastructure adoption.

---

## Strategy

**Replicate structure, adapt content.** Every CFv1 infrastructure file is replicated in BarcodeBuddy with the same path structure and behavioral intent, but with content adapted for a Python/FastAPI project.

## Principles

1. **Preserve all current functionality** - no application code modified
2. **No blind overwrites** - existing docs (blueprint, handoff, specs, runbooks) untouched
3. **Extend over replace** - add new systems alongside existing ones
4. **Domain-specific constraints** - CFv1's ChefFlow rules replaced with BarcodeBuddy domain rules

## File-by-File Mapping

| CFv1 Source | BB Target | Action |
|---|---|---|
| `CLAUDE.md` | `CLAUDE.md` | CREATE NEW - BB-specific rules |
| `AGENT-WORKFLOW.md` | `AGENT-WORKFLOW.md` | CREATE NEW - Python-adapted |
| `AI_POLICY.md` | `AI_POLICY.md` | CREATE NEW - BB's AI system |
| `.claude/settings.json` | `.claude/settings.json` | CREATE NEW - hooks config |
| `.claude/hooks/build-guard.sh` | `.claude/hooks/build-guard.sh` | ADAPTED - Python commands |
| `.claude/hooks/notify.sh` | `.claude/hooks/notify.sh` | COPIED VERBATIM |
| `.claude/skills/planner/` | `.claude/skills/planner/` | ADAPTED - Python verification |
| `.claude/skills/builder/` | `.claude/skills/builder/` | ADAPTED - pytest, compileall |
| `.claude/skills/research/` | `.claude/skills/research/` | ADAPTED - minimal changes |
| `.claude/skills/verify/` | `.claude/skills/verify/` | ADAPTED - Python verification |
| `.claude/skills/health/` | `.claude/skills/health/` | ADAPTED - Python health checks |
| `.claude/skills/ship/` | `.claude/skills/ship/` | COPIED VERBATIM - git-only |
| `.claude/skills/close-session/` | `.claude/skills/close-session/` | ADAPTED - minor path changes |
| `.claude/skills/pre-flight/` | `.claude/skills/pre-flight/` | ADAPTED - Python commands |
| `.claude/skills/hallucination-scan/` | `.claude/skills/hallucination-scan/` | ADAPTED - Python patterns |
| `.claude/skills/feature-closeout/` | `.claude/skills/feature-closeout/` | ADAPTED - Python commands |
| `.claude/skills/soak/` | `.claude/skills/soak/` | ADAPTED - FastAPI testing |
| `.claude/agents/qa-tester/` | `.claude/agents/qa-tester/` | ADAPTED - Python/FastAPI |
| `.constraints/event-fsm.json` | `.constraints/file-processing-fsm.json` | NEW - BB domain |
| `.constraints/financial-integrity.json` | `.constraints/data-safety.json` | NEW - BB domain |
| `.constraints/privacy-boundary.json` | `.constraints/ai-privacy.json` | NEW - BB domain |
| `.constraints/server-actions.json` | `.constraints/auth-boundary.json` | NEW - BB domain |
| `.constraints/tier-gating.json` | `.constraints/barcode-integrity.json` | NEW - BB domain |
| `.patches/handoff.md` | `.patches/handoff.md` | CREATE NEW - BB state |
| `docs/specs/_TEMPLATE.md` | `docs/specs/_TEMPLATE.md` | ADAPTED - Python sections |
| `docs/specs/README.md` | `docs/specs/README.md` | CREATE NEW |
| `docs/session-log.md` | `docs/session-log.md` | CREATE NEW |
| `docs/session-digests/` | `docs/session-digests/` | CREATE DIR |
| `docs/build-state.md` | `docs/build-state.md` | CREATE NEW |

## Order of Operations (As Executed)

1. Directory structure creation
2. Hooks (build-guard.sh, notify.sh) + settings.json
3. Constraint files (5 domain-specific)
4. Policy files (CLAUDE.md, AGENT-WORKFLOW.md, AI_POLICY.md)
5. Handoff file (.patches/handoff.md)
6. Spec system (template, README, queue)
7. Communication layer (build-state, session-log, session-digests)
8. Skills (11 files)
9. Agent definitions (qa-tester)
10. Documentation (audit, gap analysis, adoption plan, verification)
11. Verification (pytest, structure check)

## Risk Mitigation

| Risk | Mitigation | Outcome |
|---|---|---|
| CLAUDE.md conflicts with existing docs | References existing docs, no duplication | No conflicts |
| Skills reference wrong commands | Every skill uses Python equivalents | All adapted |
| Constraints too restrictive | Document existing rules from code, not new rules | Accurate |
| Spec system unused | README explains system, ready for first spec | Available |
| Session log grows unbounded | Pruning note included | Managed |
