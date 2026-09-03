# Isolation — каталог (не грузить целиком)

**На команде:** читай **только** `_lean/<mode>.mdc` из шага `1a` текущего `workflow-*.mdc`.  
Этот файл — справочник. **Скиллы** — только из workflow.

База: `.cursor/rules/back_developer/isolation_rules/_lean/`  
Legacy (`main.mdc`, `Core/*` кроме pointer на shared paths, `_archive/`) — **не грузить**.

| Режим | Gates |
|-------|-------|
| VAN | `_lean/van.mdc` |
| CLARIFY | `_lean/clarify.mdc` |
| PLAN | `_lean/plan.mdc` |
| ROADMAP MERGE | `_lean/roadmap-merge.mdc` (recovery-only) |
| DECOMPOSE | `_lean/decompose.mdc` |
| ANALYZE | `_lean/analyze.mdc` |
| RECONCILE | `_lean/reconcile.mdc` |
| CREATIVE | `_lean/creative.mdc` |
| IMPLEMENT | `_lean/implement.mdc` |
| AUDIT | `_lean/audit.mdc` |
| TASK | `_lean/task.mdc` |
| BUGFIX | `_lean/bugfix.mdc` |
| REFACTOR | `_lean/refactor.mdc` |
| QA | `_lean/qa.mdc` |
| JANITOR | `_lean/audit.mdc` (scan gates; см. workflow-janitor) |
| ARCHIVE NOW | `_lean/archive.mdc` |
| SECURITY | `_lean/security.mdc` (+ `workflow-security.mdc`; epic: `shared/workflow-security-epic.mdc`) |

**REFLECT:** workflow-reflect.mdc — архив; не в hot path / не в таблице режимов.
