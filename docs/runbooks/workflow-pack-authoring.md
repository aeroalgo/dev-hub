# Workflow Pack Authoring Runbook

Step-by-step guide for creating and publishing a new Workflow Pack in `dev-hub` in under 30 minutes.

---

## 1. Overview

A **Workflow Pack** encapsulates a domain-specific execution model for `dev-hub`, defining:
- **Roles & Command Prefixes:** Domain roles (e.g. `[script, visual, post]`) and command prefixes (e.g. `[SCRIPT, VISUAL, POST]`).
- **Phase Registry:** Valid phases, arm templates, verify agents, and finish gates.
- **Rules Root:** Rule definitions directory for AI assistants (e.g. `.cursor/rules/<domain>`).
- **Memory Bank:** Target directory for epic plans, tasks, and state.
- **Intent Routing:** Intent mappings to auto-select the pack and phase pipeline from idea descriptions.

This runbook guides pack authors through scaffolding from the reference template (from T-HUB-051 / `video-production`), configuring registries, verifying with `doctor workflow-pack`, and executing the first loop run.

---

## 2. Step 1: Scaffold Directories

Create the directory structure for your new workflow pack (using example pack ID `my-domain`):

```bash
# 1. Create workflows definition directory
mkdir -p workflows/my-domain

# 2. Create memory bank root
mkdir -p memory-bank/my-domain

# 3. Create cursor/agent rules root
mkdir -p .cursor/rules/my-domain
```

Ensure directories are writable and tracked in git as needed.

---

## 3. Step 2: Write `phase_registry.yaml`

Create `workflows/my-domain/phase_registry.yaml` defining the domain phases and gates based on the canonical template:

```yaml
schema: phase-registry/v1

terminal_phases:
  - PUBLISH

phases:
  PLAN:
    arm_template: pre_implement
    finish_gates:
      mode: pre_implement
      need_verify: false
      need_reviewer: false
    finish_gates_dict:
      mode: pre_implement
      need_verify: false
      need_reviewer: false
    verify_agent: null
    dsh_preset: plan
    promotable_after_finish: false
    skip_index_sync: false
    board_column: In Progress

  EXECUTE:
    arm_template: implement
    finish_gates:
      mode: implement
      need_verify: true
      need_reviewer: false
    finish_gates_dict:
      mode: implement
      need_verify: true
      need_reviewer: false
    verify_agent: verify-implement
    dsh_preset: implement
    promotable_after_finish: false
    skip_index_sync: false
    board_column: In Progress

  PUBLISH:
    arm_template: implement
    finish_gates:
      mode: implement
      need_verify: true
      need_reviewer: false
    finish_gates_dict:
      mode: implement
      need_verify: true
      need_reviewer: false
    verify_agent: null
    dsh_preset: implement
    promotable_after_finish: false
    skip_index_sync: false
    board_column: Done
```

---

## 4. Step 3: Register in `workflow_pack_registry.yaml`

Add the pack entry to `loop/workflow_pack_registry.yaml`:

```yaml
packs:
  # ... existing packs ...
  my-domain:
    id: my-domain
    roles: [planner, executor]
    command_prefixes: [PLAN, EXEC]
    phase_registry: workflows/my-domain/phase_registry.yaml
    memory_bank: memory-bank/my-domain
    rules_root: .cursor/rules/my-domain
    artifact_layout: software-epic-v1
    description: Custom domain workflow pack description
```

### Key Fields:
- `id` (str): Unique pack identifier matching the dictionary key.
- `roles` (list[str]): Role names participating in the pack.
- `command_prefixes` (list[str]): Command prefix aliases (e.g. `PLAN`, `EXEC`).
- `phase_registry` (str): Relative path to `phase_registry.yaml`.
- `memory_bank` (str): Relative path to pack's memory-bank storage.
- `rules_root` (str): Relative path to rules directory.
- `artifact_layout` (str): Epic artifact layout (`software-epic-v1` or `production-epic-v1`).

---

## 5. Step 4: Verify with `doctor workflow-pack`

Run preflight verification to ensure all paths, schemas, and permissions are valid:

```bash
# Set active pack to target
export WORKFLOW_PACK=my-domain

# Execute doctor check
python3 loop/doctor/checks/workflow_pack.py
```

Expected output on success:
```json
{
  "ok": true,
  "pack_id": "my-domain",
  "diagnostic_codes": []
}
```

If `ok: false`, refer to `docs/runbooks/workflow-pack-operator.md` section *Troubleshooting by Diagnostic Code* for remediation steps (e.g. creating missing rules directory or fixing YAML syntax).

---

## 6. Step 5: Add `intent_routing.yaml` Entry

To enable automatic selection from idea/intent descriptions, add a mapping to `loop/workflow/intent_routing.yaml`:

```yaml
intents:
  # ... existing intents ...
  my_domain_task:
    pack: my-domain
    pipeline:
      - { command: PLAN PLAN, gate: auto }
      - { command: EXEC EXECUTE, gate: auto }
      - { command: EXEC PUBLISH, gate: approval }
```

Steps in `pipeline` define the sequential stage commands and transition gate modes (`auto` or `approval`).

---

## 7. Step 6: Execute First Loop Run

Run a dry run or full session with the newly authored pack:

```bash
# Via CLI flag
python3 loop/context_loop.py --workflow-pack my-domain

# Or via environment variable
WORKFLOW_PACK=my-domain python3 loop/context_loop.py
```

---

## 8. Cross-References

- **Operator Runbook:** `docs/runbooks/workflow-pack-operator.md`
- **Workflow Pack Registry:** `loop/workflow_pack_registry.yaml`
- **Intent Routing Table:** `loop/workflow/intent_routing.yaml`
- **Schema Definitions:** `loop/workflow/schemas.py`
