# Runbook: premature_epic_done

## Diagnostic Code
`premature_epic_done`

## Symptom
An epic's overall status in `roadmap-epics.queue.yaml` or `tasks.md` was marked `completed` / `done`, but `index.yaml` still contains uncompleted steps (e.g. `in_progress` or `pending`).

## Tier-0 Chain Summary
- **Repair Function**: `epic.core.repair_post_implement_handoff_drift`
- **Verify Function**: `None`
- **Max Attempts**: 1

The Tier-0 repair resets epic status back to `in_progress` if uncompleted steps remain in `index.yaml`.

## Manual Remediation
If Tier-0 repair fails:
1. Open `memory-bank/back/plan/decompose-<epic_id>/index.yaml` and inspect remaining steps.
2. If steps remain pending, update roadmap/tasks status back to `in_progress`.
3. If all work was actually completed, ensure all steps in `index.yaml` are set to `completed`.

## Registry Link
Entry in [`loop/incidents/registry.yaml`](../registry.yaml#L29).
