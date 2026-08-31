# Runbook: mark_index_missing

## Diagnostic Code
`mark_index_missing`

## Symptom
The implement shard for a step is marked `completed` (or all checkpoints/evidence are verified done), but the decompose index (`index.yaml` / `index.md`) step status remains `in_progress` or `pending`.

## Tier-0 Chain Summary
- **Repair Function**: `epic.core.repair_finish_desync`
- **Verify Function**: `epic.core.validate_index_vs_implement`
- **Max Attempts**: 2

The Tier-0 repair inspects the implement shard state, verifies that step criteria were fulfilled, and synchronizes `index.yaml` and `index.md` status to match the completed implement step.

## Manual Remediation
If Tier-0 repair fails or manual override is required:
1. Verify that `memory-bank/back/implement/.../sNN.yaml` exists and `status` is `completed`.
2. Run `python3 .claude/hooks/epic_resolve.py mark-index-status --cwd "$PROJECT_ROOT" --step sNN --status completed`.
3. Check `index.yaml` and `index.md` to confirm both reflect `completed` for `sNN`.

## Registry Link
Entry in [`loop/incidents/registry.yaml`](../registry.yaml#L5).
