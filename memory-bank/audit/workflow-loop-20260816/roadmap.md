# Roadmap: не трогать / изменить / убрать

## Не трогать (Do Not Touch)

1. §0.0 + §0.0.1 в `token-economy-core.mdc`
2. `plan-artifact.md` (anti-shrink планов)
3. `load_now` + ONE Handoff + forbid sandwich
4. Порядок FINISH: step yaml → Handoff activeContext → validate → @verify → finalize → index
5. AC из work shard; не полный plan в IMPLEMENT hot path
6. Multi-epic + `roadmap-*.queue.yaml`
7. Смысл front-tests = parent only
8. graphify: один `graphify-out/` в корне репо
9. Silent tools / не цитировать HARD в чат
10. Роутер «без role command → не грузить workflow»
11. Ядро loop (`context_loop` prepare/arm) + flock + model_substitution HALT
12. Agents `verify` / `reviewer` / `explorer` как gate defs (чинить policy, не выкидывать)

## Убрать / deprecate

| Кандидат | Действие |
|----------|----------|
| `epic/{checkpoint,context,events,index,io,state}.py` | delete (мёртвые re-export) |
| unused `import epic as _epic` в `epic_lib` | delete |
| `.cursor/hooks/*` без wiring | либо `hooks.json`, либо удалить/пометить legacy в architecture |
| Orphaned MB claims | `workers.md` создать или убрать из index; `tests/` / `test_ports_browser` почистить |
| Stale product `.claude/runtime/epic` | migrate/docs после унификации hub runtime (не удалять evidence вслепую) |
| Live paths PM/TL/… в mainrule | заменить на «archived; require `_archive` present» |

## Изменить — P0

1. Vendoring `_archive/cursor-rules/` в hub **или** FAIL-fast в commands + убрать live paths из mainrule  
2. Создать `.cursor/rules/front-tests-parent-only.mdc` (копия/symlink с `.claude`)  
3. Синхронизировать `.agents/skills/role-command` ← `.claude/...` (один SoT)  
4. CLAUDE.md: implement `*.yaml`; Session без «ONE plan shard»; Handoff только activeContext  
5. Graphify exception: INTEG PLAN / brownfield inventory **или** убрать 1b из workflow-plan  
6. `loop.sh`: `check-after` halt / NEED_HUMAN → **exit**, не outer retry  
7. Единый runtime root: `last_session_path` = `epic_dir()` hub  
8. Fix `extract_verdict` (last match wins; убрать PASS short-circuit)  
9. Выровнять messaging на `NEED_HUMAN:` (убрать BLOCKED: verify_no_verdict из pretool)

## Изменить — P1

10. Единая матрица spawn → pointer из CLAUDE на `spawn-hard` exceptions  
11. Re-read HARD = как `context-economy-cc` (FINISH 1× ok)  
12. TodoWrite scope: ≤2 на IMPLEMENT/TASK/BUGFIX; PLAN N/A  
13. Единый `_discover_registry` во всех hooks  
14. `ALIAS["explore"]="explorer"` или убрать claim  
15. `agent-posttool`: не silent swallow на mirror; file lock на `save_state`  
16. Hub graphify N/A protocol в `graphify.mdc`  
17. Docs: канон runtime = hub `runtime/<slug>/` везде  
18. `architecture/workers.md` + починка gaps index  
19. Pytest entry для хаба (`pyproject` или явная ссылка на product venv)

## Изменить — P2 (упрощение)

20. Cheatsheet BACK IMPLEMENT / INTEG PLAN ≤40 строк  
21. Урезать дубли SUSPENSION GUARD (pointer на §0.0)  
22. Слить finish-block + finish-doc-router index (один вход)  
23. IDEA PIPELINE: gate «PM phases require archive present»  
24. Split `_lib.py` / `epic/core.py` по доменам (не меняя поведение)  
25. `projects/` — README-пример или document-only

## Приоритет эффекта

```text
P0 docs/path sync + halt parity + verdict bug  → меньше ложных PASS и бесконечных loop
P1 policy unify + runtime docs               → меньше мисинтерпретаций агента
P2 cheatsheets + split monoliths             → дешевле сопровождение
```

## Рекомендуемый порядок работ (эпики)

1. **T-hub-canon-sync** — CLAUDE + role-command SoT + front-tests.mdc + archive policy  
2. **T-hub-loop-halt** — check-after HALT + last-session path + docs runtime  
3. **T-hub-hooks-hygiene** — extract_verdict, NEED_HUMAN, dead epic re-exports, registry dual-path  
4. **T-hub-simplify-docs** — cheatsheets, hop-count, IDEA archive gate
