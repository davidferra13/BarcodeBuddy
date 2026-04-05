#!/bin/bash
# .claude/hooks/build-guard.sh
#
# MULTI-AGENT BUILD GUARD
# Blocks test/compile commands when .multi-agent-lock exists at project root.
# Prevents concurrent agents from entering infinite retry loops on failed builds.
#
# Enable guard:   touch .multi-agent-lock
# Disable guard:  rm .multi-agent-lock

INPUT=$(cat)

# Locate project root (two dirs up from .claude/hooks/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

GUARD_FILE="$PROJECT_ROOT/.multi-agent-lock"

# Fast path: no lock file -> allow everything
if [ ! -f "$GUARD_FILE" ]; then
  exit 0
fi

# Lock is active -- check if this is a test or compile command
if echo "$INPUT" | grep -qE 'pytest|compileall|ruff|python.*-m.*test|py.*-m.*test'; then
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"MULTI-AGENT LOCK ACTIVE (.multi-agent-lock exists at project root). Test and compile commands are blocked. You are one of several concurrent agents - running tests in parallel corrupts state, causes port conflicts, and wastes tokens in retry loops. Your job: commit your work and stop. The developer will run one clean test suite after all agents finish. Do not retry this command."}}'
  exit 0
fi

exit 0
