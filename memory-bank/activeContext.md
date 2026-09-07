---
schema: loop-handoff/v1 # handoff
role: BACK
mode: DECOMPOSE
epic_id: T-HUB-077-gate-evidence-integrity
step_id: DECOMPOSE
---

## load_now
1. [plan.md](back/plan/T-HUB-077-gate-evidence-integrity/md/plan.md) — source plan/artifact for pre-implement phase DECOMPOSE.
2. `.cursor/templates/decompose/` — epic-step.yaml + index.md (layout v2: md/decompose-index.md + yaml/decompose-index.yaml + yaml/steps/sNN-<slug>.yaml).
3. `.cursor/rules/back_developer/workflow-decompose.mdc` — §Maximal detail + §Replacement cleanup.
4. Target decompose: [`decompose-index.yaml`](back/plan/T-HUB-077-gate-evidence-integrity/yaml/decompose-index.yaml) (layout v2: `back/plan/T-HUB-077-gate-evidence-integrity/md/decompose-index.md` + `back/plan/T-HUB-077-gate-evidence-integrity/yaml/decompose-index.yaml` + `yaml/steps/sNN-<slug>.yaml`).

## Handoff DECOMPOSE
- # epic_id: T-HUB-077-gate-evidence-integrity — NOT short queue id
- **Эпик:** T-HUB-077-gate-evidence-integrity (BACK).
- **Режим/шаг:** `BACK DECOMPOSE`.
- **Дальше:** выполнить `BACK DECOMPOSE`.
