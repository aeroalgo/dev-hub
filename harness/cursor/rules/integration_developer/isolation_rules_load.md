# Isolation — каталог INTEG (не грузить целиком)

**На команде:** читай **только** `_lean/<mode>.mdc` из **Gates** в `workflow-*.mdc`.  
Скиллы — только из workflow.  
Контракт: inline §Contract в `eNN`. Paths: @.cursor/rules/shared/memory-bank-paths.mdc (VAN).

База: `.cursor/rules/integration_developer/isolation_rules/_lean/`  
Legacy (`main.mdc`, `Core/*` кроме pointer на shared paths, `_archive/`) — **не грузить**.

| Режим | Gates |
|-------|-------|
| VAN | `_lean/van.mdc` |
| CLARIFY | `_lean/clarify.mdc` |
| GAP | `_lean/gap.mdc` |
| GAP CLOSE | `_lean/gap-close.mdc` |
| PLAN | `_lean/plan.mdc` |
| PLAN REFACTOR | `_lean/plan-refactor.mdc` |
| ROADMAP MERGE | `@.cursor/rules/shared/_lean/roadmap-merge.mdc` (recovery-only) |
| DECOMPOSE | `_lean/decompose.mdc` |
| ANALYZE | `_lean/analyze.mdc` |
| RECONCILE | `_lean/reconcile.mdc` |
| REPLAN | `_lean/replan.mdc` |
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
