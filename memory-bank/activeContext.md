---
schema: loop-handoff/v1
role: BACK
mode: AUDIT
epic_id: T-HUB-072-context-bundle-fail-closed
step_id: T-HUB-072-context-bundle-fail-closed
---

## load_now
1. [back/plan/T-HUB-072-context-bundle-fail-closed/md/plan.md](back/plan/T-HUB-072-context-bundle-fail-closed/md/plan.md) — plan.md — Intent Inventory + epic goal (SoT for AUDIT PLAN↔runtime).
2. [.cursor/rules/back_developer/workflow-audit.mdc](.cursor/rules/back_developer/workflow-audit.mdc) — AUDIT workflow — Triple Assess PLAN↔runtime (не pytest).
3. [.cursor/rules/shared/cheatsheets/back-audit.mdc](.cursor/rules/shared/cheatsheets/back-audit.mdc) — AUDIT cheatsheet — Intent Inventory → Triple Assess → no pytest.
4. [back/plan/T-HUB-072-context-bundle-fail-closed/yaml/decompose-index.yaml](back/plan/T-HUB-072-context-bundle-fail-closed/yaml/decompose-index.yaml) — decompose index.yaml (status only; secondary to plan; эпик T-HUB-072-context-bundle-fail-closed).
5. [.cursor/templates/audit/epic-audit.yaml](.cursor/templates/audit/epic-audit.yaml) — epic-audit/v2 template — plan_intent + plan_vs_runtime required.

## Handoff BACK AUDIT — T-HUB-072-context-bundle-fail-closed
- **Дальше:** выполнить `BACK AUDIT`: из plan.md вывести цель эпика + все FR/US/SC/layout; Triple Assess plan_vs_runtime vs runtime (behavior, не sNN completed); Assess D: Read implement yaml `{mb_root}/back/implement/T-HUB-072-context-bundle-fail-closed/sNN-*.yaml` ↔ decompose `{mb_root}/back/plan/T-HUB-072-context-bundle-fail-closed/yaml/steps/sNN-*.yaml`; записать epic-audit/v2 (plan_intent, findings, converged); mb-finish audit отклонит v1/shallow, phantom implement_file, presence-only evidence. FORBIDDEN: pytest как единственная проверка; PASS по пустому not_implemented[]; implement_file = plan/.../md/sNN.md. НЕ ставить EPIC_DONE до QA pass
- **Эпик:** T-HUB-072-context-bundle-fail-closed — implement queue исчерпана; AUDIT = PLAN↔IMPLEMENT parity.
- **Режим/шаг:** `BACK AUDIT`.
- **SoT:** `{mb_root}/back/plan/T-HUB-072-context-bundle-fail-closed/md/plan.md` (цели/FR).
- **Implement yaml:** `{mb_root}/back/implement/T-HUB-072-context-bundle-fail-closed/sNN-*.yaml` (не plan/.../md).
- **Decompose yaml:** `{mb_root}/back/plan/T-HUB-072-context-bundle-fail-closed/yaml/steps/sNN-*.yaml`.
- **Артефакт:** {mb_root}/<role>/audit/<epic_id>/audit.yaml (epic-audit/v2).
- **ARCHIVE:** вне loop после EPIC_DONE (не в AUDIT/QA сессии).
