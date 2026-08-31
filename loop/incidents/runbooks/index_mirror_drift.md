# Runbook: index_mirror_drift

## Diagnostic Code
`index_mirror_drift`

## Symptom
The step statuses in `index.yaml` and human-readable `index.md` have diverged (e.g. `s01` is `completed` in `index.yaml` but `in_progress` in `index.md`).

## Tier-0 Chain Summary
- **Repair Function**: `epic.core.repair_index_mirror`
- **Verify Function**: `None`
- **Max Attempts**: 2

The Tier-0 repair regenerate/syncs `index.md` from `index.yaml` as the authoritative source of truth.

## Manual Remediation
If Tier-0 repair fails:
1. Treat `index.yaml` as canon.
2. Re-render or manually sync `index.md` to reflect identical step statuses as `index.yaml`.
3. Run `python3 .claude/hooks/epic_resolve.py validate-step` to verify mirror integrity.

## Registry Link
Entry in [`loop/incidents/registry.yaml`](../registry.yaml#L21).
