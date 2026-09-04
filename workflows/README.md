# Workflow Packs

Workflow packs define role sets, command prefixes, phase registries, rules directories, and artifact layouts for different project domains.

## Canonical Registry

The default registry of workflow packs is defined at [`loop/workflow_pack_registry.yaml`](../loop/workflow_pack_registry.yaml) with schema `workflow-pack-registry/v1`.

Schema specification: [`loop/schemas/workflow-pack-registry-schema.json`](../loop/schemas/workflow-pack-registry-schema.json).

## Pack Structure

A workflow pack specifies:
- `id`: unique pack identifier (e.g. `dev-hub-software`)
- `roles`: supported roles (e.g. `[back, front, integration]`)
- `command_prefixes`: command prefixes for roles (e.g. `[BACK, FRONT, INTEG]`)
- `phase_registry`: path to `phase_registry.yaml`
- `memory_bank`: path to memory bank directory
- `rules_root`: path to rules root (`.cursor/rules`)
- `artifact_layout`: artifact structure enum (e.g. `software-epic-v1`)
- `description`: pack summary
