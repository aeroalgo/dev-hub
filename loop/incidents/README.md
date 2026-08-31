# Incidents & Observability Architecture

## Incident Diagnostic Code Registry
The incident engine relies on a canonical diagnostic code registry specified at `loop/incidents/registry.yaml`.

### Registry Schema Version
`version: loop-incident-registry/v1`

### Schema Format
```yaml
version: loop-incident-registry/v1

repairs:
  <diagnostic_code>:
    description: "<Human readable description>"
    runbook_rel: "loop/incidents/runbooks/<diagnostic_code>.md"
    chain:
      - repair_fn: "<python_import_path>"
        verify_fn: "<python_import_path>"
        max_attempts: <int>
```

## Runtime Environment Variables
- `EPIC_INCIDENT_TRACE`: Enables or disables trace logging to JSONL (`1` by default).
- `EPIC_INCIDENT_METRICS`: Enables or disables metrics collection (`1` by default).

## Extension Guide
To register a new diagnostic code:
1. Add a new repair chain entry under `repairs:` in `loop/incidents/registry.yaml`.
2. Create a corresponding runbook at `loop/incidents/runbooks/<diagnostic_code>.md`.
3. Implement python repair and verify functions under `loop.incidents.repairs` or `epic.core`.

## Runtime Storage Paths
- **Incidents JSONL**: `HUB_ROOT/runtime/<slug>/incidents/incidents.jsonl`
- **Trace Events**: `HUB_ROOT/runtime/<slug>/trace/events.jsonl`
- **Metrics JSON**: `HUB_ROOT/runtime/<slug>/metrics/metrics.json`
