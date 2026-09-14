## Epic

### Outcome

Open incidents are not silently cleared on every loop start. Terminal failure remains visible until an explicit, auditable operator recovery action.

### In

- Remove automatic clear-open-on-start from the orchestrator start path.
- Keep opt-in operator CLI recovery with audit trail; fail-closed visibility across restart.

### Out

- Capability evidence paths, context fingerprint cache, instruction corpus.
- Full durable LifecycleReducer rewrite (backlog unless required for terminal visibility).

### Done when

1. Starting the loop does not resolve open incidents by default.
2. Explicit operator clear remains available and leaves a forensic record.

### Forbidden after

Marker clearing on start, implicit retry that wipes typed failure surface.

### Chat decisions

- Spawned as REPLAN follow-up; parent Epic prompt linked from plan header Parent-prompt.

---

## Covering

n/a — single epic
