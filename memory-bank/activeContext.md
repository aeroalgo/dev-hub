---
schema: loop-handoff/v1
role: BACK
mode: QA
epic_id: T-HUB-083-role-core-shared-contract
step_id: QA
---

## load_now
1. [qa-20260908-role-core-shared-contract.yaml](back/qa/T-HUB-083-role-core-shared-contract/qa-20260908-role-core-shared-contract.yaml) — текущий QA artifact и gate diagnostic.
2. [decompose-index.yaml](back/plan/T-HUB-083-role-core-shared-contract/yaml/decompose-index.yaml) — epic scope и completed steps.
3. `.cursor/rules/shared/workflow-decompose-transition-gate.mdc` — lifecycle transition contract.

## Handoff BACK QA
- **Эпик:** T-HUB-083-role-core-shared-contract (BACK).
- **Режим/шаг:** `BACK QA`.
- **Причина возврата:** `qa_gate_repair_required`.
- **Дальше:** запусти `verify-qa`; при FAIL/BLOCKED или runtime transport error запусти `gate-repair`, дождись repair и повтори `verify-qa`.
- **Запрет:** не создавай `qa_pass` и не вызывай `mb-finish qa` до свежего автономного PASS текущего QA run.
