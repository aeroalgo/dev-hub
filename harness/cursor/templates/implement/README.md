# Implement templates

**Shard (BACK / FRONT / INTEG):** [epic-step.yaml](epic-step.yaml) — `schema: epic-implement/v1`, `role: back|front|integ`

| Роль | Путь shard |
|------|------------|
| BACK / FRONT | `memory-bank/{back\|front}/implement/implement-<plan_id>/sNN-<slug>.yaml` |
| INTEG | `memory-bank/integration/implement/implement-<plan_id>/eNN-<slug>.yaml` |

Hub `implement-<plan_id>/index.md` **не создавать**. Навигация — колонка implement в decompose index + сами yaml.

**Validate:** `python3 .claude/hooks/epic_resolve.py validate-step --path <shard.yaml>`

**FINISH status:** `finalize-step` (implement + `index.yaml` + `tasks/log`; `tasks.md` только при смене фазы эпика).

Legacy `.md` implement shards — **FAIL** (loop after-hook).
