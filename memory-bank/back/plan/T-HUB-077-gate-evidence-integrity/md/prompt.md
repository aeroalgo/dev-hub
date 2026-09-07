## Epic

### Outcome

Workflow completion becomes trustworthy: a successful verification is an independently produced fact, not a mutable claim made by the agent that wants to continue.

### In

- Provenance and validation of verification evidence.
- Fail-closed handling of interrupted or stale verification.
- A narrow, auditable operator recovery boundary.

### Out

Product capability execution, UI, and broad lifecycle redesign.

### Done when

1. A worker cannot turn its own work into a passing verification.
2. Interrupted verification stops with an actionable typed failure.

### Forbidden after

Manual pass markers, mutable evidence as authority, or silent gate cleanup.

### Chat decisions

- Security and reproducibility take precedence over an automatic retry.

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
