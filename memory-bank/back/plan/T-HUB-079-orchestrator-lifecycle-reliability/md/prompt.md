## Epic

### Outcome

Every workflow and verification invocation has one owner, one identity and a terminal explanation.

### In

- Idempotent subagent dispatch and durable lifecycle transitions.
- Crash-safe terminal telemetry and a read-only parent status API.

### Out

Provider replacement, runtime dashboard design and product code changes.

### Done when

1. Duplicate launches do not create duplicate work.
2. An interrupted or empty session is visible as a terminal event with cause.

### Forbidden after

Marker clearing, implicit retry loops, or filesystem archaeology as normal agent behavior.

### Chat decisions

- Lifecycle repair remains explicit and fail-closed.

---

## Covering

### Outcome

Agentic workflow execution is fail-closed, economical and observable at every boundary.

### Axes

- Verification evidence is independently attributable and immutable.
- Context and search actions are bounded by declared scope.
- Session and subagent lifecycle has one observable owner and terminal outcome.

### Invariants

- No successful finish is inferred from mutable worker state alone.
- A diagnostic never grants extra authority.

### Out

Feature delivery behavior unrelated to workflow control.

### Done when

1. False-green paths are rejected instead of repaired silently.
2. Each axis can be audited without reading agent-private runtime files.

### Forbidden after

Mega-plan ownership, hidden fallback paths, and prose as the sole control.

### Chat decisions

- Split the audit remediation by independent risk boundary.
