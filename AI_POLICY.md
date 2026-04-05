# AI Policy - BarcodeBuddy

This document defines the boundaries for AI integration in the BarcodeBuddy system. These rules apply to the runtime AI features (chatbot, tools, suggestions), not to Claude Code as a development agent.

---

## Core Principle

AI assists and suggests. It never owns canonical state. Every AI-generated recommendation requires user confirmation before becoming a real inventory change, alert configuration, or system setting.

---

## Allowed Use Cases

| Use Case | What AI Does | What It Does NOT Do |
|---|---|---|
| Inventory lookup | Searches and returns matching items | Never modifies quantities or records |
| Barcode recovery | Suggests possible matches for failed scans | Never auto-assigns a barcode value |
| CSV preview | Previews import data, flags potential issues | Never executes the import |
| Stock analysis | Summarizes trends, flags anomalies | Never creates alerts or adjustments |
| Chat assistance | Answers questions about inventory and system | Never executes admin actions |
| Setup wizard | Guides provider configuration | Never auto-selects a provider |

---

## Hard Restrictions

### AI Must Never:

1. **Modify inventory records** - no quantity changes, no item creation/deletion, no transaction entries
2. **Change system configuration** - no alert thresholds, no auth settings, no processing rules
3. **Execute file operations** - no moving/deleting files in data directories
4. **Bypass authentication** - AI tools respect the same RBAC as the user invoking them
5. **Silently switch providers** - if Ollama is configured and offline, surface the error; never fall back to cloud
6. **Store conversation data externally** - all chat history stays in local SQLite
7. **Access other users' data** - AI tool scope is limited to the authenticated user's permissions

---

## Privacy Boundaries

### Local-First (Ollama)
When Ollama is the configured provider:
- All inference runs on the local machine
- No data leaves the network
- Ollama offline = AI features unavailable (not degraded, unavailable)

### Cloud Providers (Anthropic, OpenAI)
When a cloud provider is explicitly enabled:
- Only the conversation context is sent (not the full database)
- Inventory data in tool calls is scoped to what the query needs
- The privacy page must accurately reflect what data leaves the machine
- Users must opt in; cloud is never the default

---

## UX Rules

1. AI suggestions are visually distinct from system-generated data (never presented as facts)
2. AI errors surface clearly - never swallowed, never shown as "no results"
3. AI loading states are honest - show "thinking" or "connecting," never fake instant responses
4. AI tool calls show what was accessed - transparency over magic
5. If AI is unavailable, the rest of the app works normally - AI is additive, never blocking

---

## The Hard Boundary

BarcodeBuddy must function completely without AI. Every core feature (ingestion, inventory, alerts, auth, teams, reporting) works identically whether AI is configured or not. AI is a convenience layer, not a dependency.
