# Spec Kit adaptation reference — T-HUB-013

- **Epic**: `T-HUB-013-idea-decide-constitution`
- **Source**: `spec-kit/extensions/assess/commands/speckit.assess.decide.md`
- **Adaptation scope**: bounded reference for the IDEA PIPELINE decide gate; this is not a port of the Spec Kit assess extension.

## Adopted concepts

1. **Scorecard** — assess the idea against explicit criteria and record a rating with a short evidence-based justification.
2. **Verdict** — make the outcome explicit as `go`, `needs-clarification`, or `kill` rather than leaving the idea in an ambiguous state.
3. **Kill semantics** — a `kill` is a successful terminal pipeline outcome when the rationale is recorded; it must not silently continue into PLAN or IMPLEMENT.
4. **Clarification loop** — `needs-clarification` names the missing questions and sends the idea back to the appropriate discovery stage.
5. **Traceable rationale** — preserve the criteria, evidence, unknowns, and decision so the call remains auditable.

These concepts are adapted to the existing hub IDEA PIPELINE and its lightweight Decision/Scorecard contract. The adaptation keeps the gate small and does not introduce the Spec Kit assessment directory or command lifecycle.

## Explicitly rejected scope

The full five-command assess port is **not** adopted. In particular, T-HUB-013 does not port the complete intake/research/define/shape/decide command family, its `.specify/assessments` tree, or the associated Spec Kit Articles and CLI/Library-First workflow. Only the `assess.decide` decision semantics above are retained as a reference; the hub's existing workflow and memory-bank artifacts remain the source of truth.
