# Workflow Pack Operator Runbook

Source of Truth (SoT) for operators configuring, running, and troubleshooting Workflow Packs in `dev-hub`.

---

## 1. Overview

Workflow Packs allow configuring domain-specific execution pipelines, roles, memory banks, rules, and phase registries across projects.

- Canonical pack definitions: `loop/workflow_pack_registry.yaml`
- Machine-readable intent mapping: `loop/workflow/intent_routing.yaml`
- Pack authoring guide: `docs/runbooks/workflow-pack-authoring.md`

---

## 2. Prerequisites

1. Python 3.10+ virtual environment active (`.venv/bin/activate`).
2. Valid `loop/workflow_pack_registry.yaml` or project-level pack configuration.
3. Accessible and writable memory-bank directory for the active pack.

---

## 3. Environment Variables

Workflow pack resolution follows strict precedence: `project.yaml` / `.dev-hub/project.yaml` > Environment Variables > Registry Default (`dev-hub-software`).

| Variable | Type | Default | Description |
|---|---|---|---|
| `WORKFLOW_PACK` | String | *(empty)* | Active workflow pack identifier (e.g. `dev-hub-software`, `video-production`). |
| `EPIC_WORKFLOW_PACK` | String | *(empty)* | Alias for `WORKFLOW_PACK` for backwards compatibility. |

Example:
```bash
export WORKFLOW_PACK=video-production
```

---

## 4. Loop Flags (`--workflow-pack`)

The loop runner supports runtime selection of workflow packs via the `--workflow-pack` CLI flag, providing CLI parity with `WORKFLOW_PACK`.

```bash
python3 loop/context_loop.py --workflow-pack video-production
```

When supplied, `--workflow-pack` sets or overrides the session pack identifier for all downstream orchestrator checks and sub-agents.

---

## 5. Preflight Checks (`doctor workflow-pack`)

Before starting a loop session, operators can run the fail-closed preflight checker to validate pack configuration, rule directories, phase registries, and memory bank permissions.

### Running Doctor Check

```bash
# Run against current working directory
python3 -m loop.doctor.checks.workflow_pack

# Or via doctor runner
python3 loop/doctor/checks/workflow_pack.py
```

### Output Format

Doctor emits structured JSON and exits with `0` on success or non-zero (`1`) if any check fails:

```json
{
  "ok": true,
  "pack_id": "dev-hub-software",
  "diagnostic_codes": []
}
```

If issues are detected:
```json
{
  "ok": false,
  "pack_id": "video-production",
  "diagnostic_codes": [
    "pack_rules_missing"
  ]
}
```

---

## 6. Troubleshooting by Diagnostic Code

When `doctor workflow-pack` fails or loop initialization aborts, refer to the diagnostic code in the table below:

| Diagnostic Code | Test ID | Description / Cause | Resolution / Remediation |
|---|---|---|---|
| `pack_not_found` / `invalid_workflow_pack` | TM-001 | Specified pack ID is not registered in `loop/workflow_pack_registry.yaml`. | Check `WORKFLOW_PACK` value or add pack definition to `loop/workflow_pack_registry.yaml`. |
| `pack_rules_missing` | TM-002 | The directory specified in `rules_root` does not exist. | Create missing directory (e.g. `.cursor/rules/video`) or run `hub-link --pack <id>`. |
| `pack_phase_registry_missing` | TM-003 | The file specified in `phase_registry` does not exist. | Ensure phase registry yaml file is present at configured path (e.g. `workflows/video/phase_registry.yaml`). |
| `mb_root_not_writable` / `mb_root_missing` | TM-004 | Memory-bank path specified in `memory_bank` is missing or not writable. | Ensure directory exists and check file permissions: `mkdir -p <memory_bank> && chmod u+w <memory_bank>`. |
| `invalid_workflow_pack_registry` | TM-001 | Registry file `loop/workflow_pack_registry.yaml` is missing or contains invalid YAML. | Validate syntax and schema of `loop/workflow_pack_registry.yaml`. |
| `pack_resolve_failed` | TM-001 | Generic resolution failure during workflow pack lookup. | Run doctor in verbose mode to inspect stack trace. |

---

## 7. Canonical Routing & Further Reading

- **Machine-readable Intent Routing:** See `loop/workflow/intent_routing.yaml` for canonical mapping from idea intents (`video_production`, `feature_full`, `content_factory`) to default packs and phase pipelines.
- **Pack Authoring Guide:** See `docs/runbooks/workflow-pack-authoring.md` for a step-by-step tutorial on creating and testing a new workflow pack in under 30 minutes.
