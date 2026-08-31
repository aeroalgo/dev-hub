# Runbook: stale_owner

## Diagnostic Code
`stale_owner`

## Symptom
A runner lock file (`runner.lock`) exists, but the process ID (PID) specified inside the lock file is no longer running on the host system.

## Tier-0 Chain Summary
- **Repair Function**: `loop.incidents.repairs.clear_stale_runner_lock`
- **Verify Function**: `loop.incidents.repairs.verify_runner_owner`
- **Max Attempts**: 1

The Tier-0 repair verifies PID deadness and safely removes the stale lock file so execution can resume.

## Manual Remediation
If Tier-0 repair fails:
1. Verify PID status using `ps aux | grep <PID>` or `kill -0 <PID>`.
2. If process is dead, remove lock file: `rm -f runtime/<slug>/runner.lock`.
3. Restart runner `./loop/loop.sh`.

## Registry Link
Entry in [`loop/incidents/registry.yaml`](../registry.yaml#L37).
