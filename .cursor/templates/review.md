# Epic QA — redirect

**Канон FINISH:** `.cursor/templates/qa/epic-step.yaml` (`epic-qa/v1`)

Путь: `memory-bank/{back|front|integration}/qa/<epic>/qa-YYYYMMDD-<slug>.yaml`

Поля: `verdict`, `scope[]`, `checks[]`, `fix_plan[]` (при fail/blocked), `issues[]`, `blockers[]`, `suite[]`.

Validate: `python3 .claude/hooks/epic_resolve.py validate-step --path <shard.yaml>`

Human-readable outline (legacy reference):

- Verdict: pass | fail | blocked
- Scope / Checks / Issues / Blockers / Fix plan — см. поля yaml-шаблона
