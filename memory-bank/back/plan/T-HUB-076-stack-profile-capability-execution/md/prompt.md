## Epic

### Outcome

Workflow verification for a managed project becomes an executable, auditable capability boundary rather than an instruction to guess a test command. A declared verification intent either runs through the selected project target and produces a typed outcome, or the workflow stops with a diagnostic.

### In

- Strict declaration of existing verification capabilities for named managed-project targets.
- Safe execution of a resolver-owned command and durable machine-readable proof for the active workflow step.
- Phase and finish enforcement that distinguish a managed project from tests of the hub itself.
- Workflow guidance that describes the one supported path rather than language-specific command folklore.

### Out

- General command execution, installation, deployment and migration operations.
- New capability vocabulary, browser-runner integration, profile extensibility and hidden default-target selection.
- Changing the hub's own test runner into a managed-project profile.

### Done when

1. An explicit verification check for each named target either succeeds with evidence or prevents a green workflow continuation.
2. A raw command string, stale proof or failed resolution cannot stand in for that evidence.
3. The hub remains able to test itself without being treated as a managed profile.

### Forbidden after

No shell reconstruction, arbitrary execution input, implicit target, optional phase execution, cross-target proof reuse, prose-as-proof or fallback from managed verification to a hub command.

### Chat decisions

- Connect execution after the profile resolver; do not merely rewrite workflow prose.
- Keep the existing verification vocabulary and make named targets explicit for workflow evidence.

## Covering

n/a — single epic
