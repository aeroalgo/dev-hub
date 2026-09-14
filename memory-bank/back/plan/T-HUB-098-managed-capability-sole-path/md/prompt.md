## Epic

### Outcome

Managed-project verification cannot green via hub test strings. A named target verification either runs through declared capability checks with executor-authored evidence, or the workflow stops with a typed diagnostic.

### In

- Fail-closed detection of a managed project root (strict project manifest present).
- Requirement that verification steps declare capability checks instead of hub runner proofs.
- Finish and phase gates that reject hub-style test proof and agent-written capability sidecars without executor provenance.

### Out

- Tool-boundary Write deny on execution sidecars (separate follow-up).
- Instruction corpus / gate-agent wording (separate follow-up).
- New capability vocabulary, profile registry changes, hub self-test runner changes.

### Done when

1. A managed root without capability checks cannot finish or continue green on hub tests alone.
2. Capability evidence without executor provenance cannot stand in for a successful check.
3. Hub repositories without a managed manifest still use the hub test path.

### Forbidden after

Managed→hub command fallback, optional capability execution, prose-as-proof, implicit target selection.

### Chat decisions

- Spawned as REPLAN follow-up; parent outcome prompt remains the immutable prior Epic SoT via plan header Parent-prompt link.
- Scope limited to critical gaps only; cosmetic items stay backlog.

---

## Covering

n/a — single epic
