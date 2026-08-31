# Runbook: Tier-1 Incident Autopilot Recovery

## Diagnostic Context
`tier1_recovery`

## Overview
This runbook covers manual remediation when Tier-1 Autopilot fails or reaches escalation after maximum execution attempts.

## Escalation Triggers
- Tier-0 repair attempts exhausted without resolution.
- Tier-1 LLM autopilot session failed verification or encountered fatal errors.
- Maximum Tier-1 attempt limit (`EPIC_INCIDENT_TIER1_MAX`, default 2) reached.
- Non-eligible diagnostic code (e.g. product test failure, missing credentials).

When escalation occurs, an escalation event is logged, `NEED_HUMAN` file is written in the epic directory, and a banner is printed to stderr.

## Manual Remediation Steps

If Tier-1 autopilot escalation occurs:

1. **Inspect Active Context & Incident State**:
   - Check `memory-bank/activeContext.md` for current loop status and `NEED_HUMAN` marker.
   - Run CLI command to view open incidents and diagnostic details:
     ```bash
     python3 loop/context_loop.py incident-status
     ```
   - For JSON output:
     ```bash
     python3 loop/context_loop.py incident-status --json
     ```

2. **Fix Underlying System State**:
   - Address the root cause described in the incident's diagnostic codes (e.g., repair corrupted `activeContext.md`, resolve checkpoint drift, or fix missing files).
   - Remove the `NEED_HUMAN` file from the epic directory once manual remediation is complete.

3. **Reset and Retry Incident**:
   - Once the underlying issue is fixed, clear the incident and allow Tier-1 autopilot or the main loop to resume by triggering `incident-retry`:
     ```bash
     python3 loop/context_loop.py incident-retry <incident_id>
     ```

## Registry Link
Entry in [`loop/incidents/registry.yaml`](../registry.yaml).
