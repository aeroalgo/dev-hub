---
schema: loop-handoff/v1 # handoff
role: BACK
mode: DECOMPOSE
epic_id: T-HUB-048-workflow-pack-registry
step_id: DECOMPOSE
---

## load_now
1. [plan.md](back/plan/T-HUB-048-workflow-pack-registry/md/plan.md) — source plan/artifact for pre-implement phase DECOMPOSE.
2. `.cursor/templates/decompose/` — epic-step.yaml + index.md (канон sNN-<slug>.yaml).
3. `.cursor/rules/back_developer/workflow-decompose.mdc` — §Maximal detail + §Replacement cleanup.
4. Target decompose: [`decompose-T-HUB-048-workflow-pack-registry/index.yaml`](back/plan/decompose-T-HUB-048-workflow-pack-registry/index.yaml) (index.md + index.yaml + sNN-<slug>.yaml).

## Handoff DECOMPOSE
- # epic_id: T-HUB-048-workflow-pack-registry — NOT short queue id
- **Эпик:** T-HUB-048-workflow-pack-registry (BACK).
- **Режим/шаг:** `BACK DECOMPOSE`.
- **Дальше:** выполнить `BACK DECOMPOSE`.
