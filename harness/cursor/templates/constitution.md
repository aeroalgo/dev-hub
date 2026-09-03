# [Product name] Workflow Constitution

- **version:** [constitution version]
- **date:** [YYYY-MM-DD]
- **scope:** [product workflow, roles, hooks, and memory-bank artifacts covered by this constitution]

> Copy this starter into the product repository and adapt each rule to the product's
> workflow. Preserve the fail-closed and evidence-first intent; do not omit a rule
> without recording the reason in the product's plan or constitution change.

## MUST

### MUST-1 — [test and validation policy]

[State which tests or validation steps are mandatory, who runs them, and the required
command or evidence format.]

### MUST-2 — [no silent fallback]

[Required dependencies, paths, markers, and configuration must fail closed when
missing. Describe the explicit failure signal.]

### MUST-3 — [test ownership and execution boundaries]

[Define which role or agent may run each test class, including any parent-only
frontend runner boundary.]

### MUST-4 — [lean context and workflow loading]

[Define the files and rules loaded for one role session and the permitted conditions
for re-reading them.]

### MUST-5 — [fail-closed configuration]

[Invalid or ambiguous environment and configuration values are errors; do not invent
or coerce defaults.]

### MUST-6 — [no-guess markers]

[When evidence is insufficient, preserve uncertainty with the product's defined
clarification or human-escalation marker.]

### MUST-7 — [handoff and state ownership]

[Define the single current handoff, status authority, and evidence required before a
step can be finalized.]

### MUST-8 — [integration parity]

[For integrated features, require matching evidence for the user-facing element,
client, backend route or service, and persisted or external data contract.]

### MUST-9 — [phase authority]

[Name the read-only and post-implementation authority checks and where their findings
must be recorded.]

## SHOULD

### SHOULD-1 — [outcome-first titles]

[Prefer titles that describe the user or system outcome.]

### SHOULD-2 — [preserve decision rationale]

[Retain the rationale for accepted, rejected, or killed decisions.]

### SHOULD-3 — [replacement cleanup]

[After replacing or deleting a path, symbol, fallback, or entrypoint, use search and
import-audit evidence to confirm that no live callers remain.]

## Product adaptation note

This constitution is a product-scoped adaptation of the hub starter. Keep the scope,
owners, commands, markers, and evidence paths explicit, and record any deliberate
divergence before implementation.

## Fail-closed reminders

- A missing required rule, marker, path, dependency, or evidence item is an error.
- An ambiguous role, project, route, status, or configuration value is not a default.
- An incomplete checkpoint remains open until its prescribed verification succeeds.
