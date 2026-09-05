# Workflow Pack Template (`workflows/_template/`)

Authoring template for creating new Workflow Packs in `dev-hub`.

## Step-by-Step Guide

### 1. Copy Template
Copy this directory to create your new pack:
```bash
cp -r workflows/_template workflows/<your-pack-name>
```

### 2. Fill In `manifest.yaml`
Edit `workflows/<your-pack-name>/manifest.yaml`:
- Set `id` to your pack identifier (e.g. `video-production`, `data-pipeline`).
- Set `roles` list (e.g. `[script, visual, post]`).
- Set `command_prefixes` list (e.g. `[SCRIPT, VISUAL, POST]`).
- Set `phase_registry` path (e.g. `workflows/<your-pack-name>/phase_registry.yaml`).
- Set `memory_bank` path (e.g. `memory-bank/<your-pack-name>`).
- Set `rules_root` path (e.g. `.cursor/rules/<your-pack-name>`).
- Set `artifact_layout` (`software-epic-v1` or `production-epic-v1`).
- Fill in the `description`.

### 3. Customize `phase_registry.yaml`
Edit `workflows/<your-pack-name>/phase_registry.yaml`:
- Define phases in `phases` dictionary.
- Specify `arm_template` (`pre_implement` or `implement`).
- Configure `finish_gates` / `finish_gates_dict`.
- Define `terminal_phases`.
- Optional: attach `external_gates` and `verify_agent`.

### 4. Register the Pack
Add your pack entry to `loop/schemas/workflow_pack_registry.yaml`:
```yaml
packs:
  <your-pack-name>:
    id: <your-pack-name>
    roles: [...]
    command_prefixes: [...]
    phase_registry: workflows/<your-pack-name>/phase_registry.yaml
    memory_bank: memory-bank/<your-pack-name>
    rules_root: .cursor/rules/<your-pack-name>
    artifact_layout: software-epic-v1
    description: "Your pack description"
```

### 5. Validate
Validate the new pack configuration using python or pytest:
```bash
python -c "
import yaml
from loop.workflow.schemas import WorkflowPack
data = yaml.safe_load(open('workflows/<your-pack-name>/manifest.yaml'))
pack = WorkflowPack.model_validate(data)
print('Valid pack:', pack.id)
"
```
Or run full test suite:
```bash
bin/pytest loop/tests/test_workflow_pack_registry.py -q --tb=short
```
