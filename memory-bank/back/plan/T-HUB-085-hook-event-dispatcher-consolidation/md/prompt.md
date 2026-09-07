## Epic

### Outcome

Runtime hook processing is simpler and less duplicative while every pre-tool, post-tool, subagent, and parent-stop trust boundary remains independently enforced.

### In

- Canonical event-specific dispatch for pre-tool and post-tool processing.
- Shared typed policy, identity, validation, evidence, and diagnostic services.
- Registration/materialization cleanup and parity regression proof.

### Out

- Merging lifecycle events into one universal hook.
- Removing external SubagentStop or Stop validation.
- Changing workflow phase policy, gate schemas, provider parity, or product behavior.

### Done when

1. Pre-tool and post-tool processing each have one canonical active route per event.
2. Duplicate policy implementation and active references are removed.
3. Self-checks remain advisory and runtime boundaries remain authoritative.
4. Positive, negative, stale, duplicate, and failure paths are observable and tested.

### Forbidden after

Duplicate active registrations · state-only PASS · self-check as final proof · silent allow on dispatcher failure · universal lifecycle hook · last-writer-wins policy merge.

### Chat decisions

- The requested optimization is an architecture/hot-path optimization, not a request to weaken gates.
- Existing lifecycle and evidence epics remain dependencies; this epic owns dispatcher consolidation only.

## Covering

### Outcome

The workflow runtime has fewer duplicate execution paths and clearer ownership boundaries without sacrificing fail-closed behavior.

### Axes

- Event-specific hook routing.
- Shared typed policy and evidence services.
- Canonical registration/materialization.
- Independent lifecycle trust boundaries.

### Invariants

- Fewer implementations does not mean fewer authorization boundaries.
- External runtime validation remains authoritative.
- Every mutation and failure remains observable and idempotent.

### Out

Provider-specific runtime redesign, product workflows, UI, and broad schema changes.

### Done when

Dispatcher routes, registration graph, evidence ownership, and regression behavior are all machine-verifiable.

### Forbidden after

Mega-hook · dual active route · mutable state as verifier proof · hidden fallback · prose-only migration.

### Chat decisions

- Single epic is appropriate because dispatcher, shared policy, registration, and parity tests form one independently shippable vertical slice.
