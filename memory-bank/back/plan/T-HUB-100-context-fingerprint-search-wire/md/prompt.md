## Epic

### Outcome

Cached test results cannot silently survive relevant file changes, and search-by-convenience cannot bypass the shared context scope policy for root and subagents when that policy is active.

### In

- Wire the existing test fingerprint cache into Bash/PreToolUse decision path.
- Apply search-scope enforcement whenever context ledger/policy is active for the actor, not only inside an epic-loop environment flag.

### Out

- Capability evidence write deny, managed verification fallback, agent prompt corpus, incident clearing.
- Global token metering and product UI.

### Done when

1. Reusing a stale test-command fingerprint after a relevant edit is denied or forces fresh execution evidence.
2. Unscoped search is denied under active context policy for root and subagents with equivalent Claude/Codex decisions.

### Forbidden after

Unwired cache classes, EPIC_LOOP-only search gate as sole policy, provider-specific bypass.

### Chat decisions

- Spawned as REPLAN follow-up; parent Epic prompt linked from plan header Parent-prompt.
- Duplicate-read / plan-jump already met — not in scope.

---

## Covering

n/a — single epic
