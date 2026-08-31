# Runbook: active_context_shape_invalid

## Diagnostic Code
`active_context_shape_invalid`

## Symptom
`memory-bank/activeContext.md` is missing required section headers (`## load_now` or `## Handoff`), preventing `context_loop.py` from determining the active step.

## Tier-0 Chain Summary
- **Repair Function**: `loop.incidents.repairs.repair_active_context_shape`
- **Verify Function**: `loop.incidents.repairs.verify_active_context_shape`
- **Max Attempts**: 2

The Tier-0 repair re-formats `activeContext.md` with standard required headers while preserving existing status notes.

## Manual Remediation
If Tier-0 repair fails:
1. Open `memory-bank/activeContext.md`.
2. Ensure both `## load_now` and `## Handoff` section headers exist.
3. Verify step reference (e.g. `1. [sNN-title.yaml](back/plan/.../sNN-title.yaml)`).

## Registry Link
Entry in [`loop/incidents/registry.yaml`](../registry.yaml#L53).
