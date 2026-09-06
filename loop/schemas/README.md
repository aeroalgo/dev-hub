# Loop Pydantic Schemas Registry

This directory contains the machine-readable Pydantic schemas and models for the Loop system (`loop-system/v1`).

| Schema ID | Class / Model | File | Description |
|-----------|---------------|------|-------------|
| `loop-handoff/v1` | `LoopHandoffFrontmatter` | `loop/schemas/handoff.py` | Frontmatter metadata for `activeContext.md` handoff state |
| `loop-gate-verdict/v1` | `GateVerdictRecord` | `loop/schemas/gate_verdict.py` | Gate verdict record (PASS/FAIL/BLOCKED) |
| `loop-repair-result/v1` | `RepairResultRecord` | `loop/schemas/repair_result.py` | Gate repair outcome record (done/partial/fail) |
| `loop-sunset-inventory/v1` | `SunsetReport` | `loop/schemas/sunset_inventory.py` | Sunset inventory analysis and extraction report |
| `loop-state/v1` | `LoopState` | `loop/schemas/state.py` | Loop execution state |
| `loop-checkpoint/v1` | `LoopCheckpoint` | `loop/schemas/checkpoint.py` | Step checkpoint model |
| `loop-event/v1` | `LoopEvent` | `loop/schemas/event.py` | Loop lifecycle event |
| `decompose-formula/v1` | `DecomposeFormula` | `loop/schemas/formula.py` | Typed skeleton for reusable DECOMPOSE formula |
| `mb-board-card/v1` | `BoardCard` | `loop/schemas/board.py` | MindBridge board card model |

## §0.11 Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PROJECT_LOOP_HANDOFF_STRICT` | `0` | Strict handoff validation (1=block FINISH without valid `loop-handoff/v1` frontmatter in `activeContext.md`) |
| `PROJECT_LOOP_REPAIR_LEGACY` | `1` | Enable legacy repair execution (0=log warning only, no auto-rewrite) |
| `PROJECT_OUTPUT_SUMMARY` | `1` | Bash output summary flag |
| `PROJECT_OUTPUT_SUMMARY_STRUCTURED` | `1` | Use Pydantic-AI structured output for bash summaries |
| `PROJECT_WORKFLOW_HOOKS` | `loop` | Enabled workflow hooks |
| `EPIC_PERMISSION_MODE` | `bypassPermissions` | Permission mode for epics |

## Usage & Helper Modules

- `loop/schemas/active_context.py`: Functions `parse_handoff_meta`, `render_with_frontmatter`, `validate_handoff_frontmatter`, `split_frontmatter` for parsing and validating `activeContext.md` header frontmatter.
- `loop/schemas/boundary_registry.py`: Registry mapping schema IDs to Pydantic validator models (`BOUNDARY_REGISTRY`).
- `loop/validate_boundary.py`: CLI and helper for validating arbitrary JSON payloads against registered boundary schemas.
