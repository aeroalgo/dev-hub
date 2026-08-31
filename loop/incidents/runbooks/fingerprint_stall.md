# Runbook: fingerprint_stall

## Diagnostic Code
`fingerprint_stall`

## Symptom
The runner detects that the session state fingerprint (hash of step, activeContext, and modified state) did not change after a full execution iteration, indicating an infinite loop or stalled progress.

## Tier-0 Chain Summary
- **Repair Function**: `epic.core.repair_fingerprint_stall`
- **Verify Function**: `None` (built-in re-check on next tick)
- **Max Attempts**: 1

The Tier-0 repair invalidates stale runner execution cache or touches activeContext Handoff state to trigger re-evaluation.

## Manual Remediation
If Tier-0 repair fails or stalls persist:
1. Inspect `runtime/<slug>/epic/last-session.json` and session logs to identify the stalling command or agent.
2. Check `memory-bank/activeContext.md` for stuck instructions or missing `Handoff` updates.
3. Manually update `activeContext.md` or restart the loop with `./loop/loop.sh`.

## Registry Link
Entry in [`loop/incidents/registry.yaml`](../registry.yaml#L13).
