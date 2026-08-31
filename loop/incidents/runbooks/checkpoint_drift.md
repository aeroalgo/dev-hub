# Runbook: checkpoint_drift

## Diagnostic Code
`checkpoint_drift`

## Symptom
Implement shard checkpoints (`checkpoints[]` in `implement/.../sNN.yaml`) diverge from the decompose shard specification (`decompose/.../sNN.yaml`), causing validation errors during step execution.

## Tier-0 Chain Summary
- **Repair Function**: `epic.core.repair_post_implement_handoff_drift`
- **Verify Function**: `None`
- **Max Attempts**: 1

The Tier-0 repair re-synchronizes checkpoint metadata from the decompose shard template.

## Manual Remediation
If Tier-0 repair fails:
1. Re-run `python3 .claude/hooks/epic_resolve.py seed-implement --decompose <decompose_shard.yaml>` to restore checkpoint definitions.
2. Flush completed checkpoints using `flush-checkpoint`.

## Registry Link
Entry in [`loop/incidents/registry.yaml`](../registry.yaml#L45).
