# Большой аудит loop / workflow / subagents

Дата снимка: **2026-09-05**  
Репозиторий: `/home/aero/PyProject/dev-hub`  
Область: `harness/agents`, `harness/manifest.yaml`, runtime materializers, hooks, `loop/*`, Pydantic boundary schemas, Cursor rules, workflow packs, start/finish path.

## Итог

Архитектура уже содержит хорошие защитные идеи: typed state, atomic writes, checkpoint lifecycle, fail-closed stop gate, отдельные gate/repair agents, schema retry и запрет ручного `status: completed`. Главная проблема не в отсутствии правил, а в том, что один и тот же контракт описан в нескольких независимых слоях:

`agent markdown → manifest → generated Codex TOML → _lib.CONTRACTS → SubagentStop → stop-gate → phase registry → workflow rules`.

Слои не образуют единую проверяемую матрицу. Поэтому часть запретов остаётся только текстом, часть агентов не доходит до runtime validation, а workflow pack может успешно резолвиться при фактически несуществующем rule path.

## Критические findings

| Приоритет | Finding | Воздействие | Где разобрано |
|---|---|---|---|
| P0 | Большинство `@.agents/skills/<name>/SKILL.md` не существует: реальные файлы лежат в `.agents/skills/skills/<name>/SKILL.md` | Главный read-contract workflow не исполняется; агент либо получает ошибку чтения, либо начинает угадывать skill | [02-workflow-pack-and-rules.md](./02-workflow-pack-and-rules.md) |
| P0 | `loop-sunset-inventory/v1` есть как модель и prompt contract, но отсутствует в `BOUNDARY_REGISTRY`; ветка `SubagentStop` для sunset отсутствует | Sunset-agent не может подтвердить свой JSON через общий validator, а его результат не проверяется hook-ом | [04-schemas-validation.md](./04-schemas-validation.md), [05-repair-and-verdict.md](./05-repair-and-verdict.md) |
| P0 | Video pack резолвится, но `route_command()` строит role-subdirectory paths, которых нет; video verify agents не входят в manifest | `SCRIPT/VISUAL/POST` pipeline формально объявлен, но команда не получает исполнимый workflow и Codex не материализует `verify-script/edit/publish` | [01-subagents-prompts.md](./01-subagents-prompts.md), [02-workflow-pack-and-rules.md](./02-workflow-pack-and-rules.md) |
| P0 | Codex materializer переносит только `name`, `description`, `developer_instructions` | `tools`, `disallowedTools`, `maxTurns`, `color`, overlay metadata не являются runtime-конфигурацией Codex; enforcement остаётся prose/hook-dependent | [01-subagents-prompts.md](./01-subagents-prompts.md) |
| P1 | `SessionStart` может inject-ить частичный bundle как успешный и при ошибке продолжает с `Warning`; `build_prompt_scope()` не получает runtime | Неполный контекст выглядит пригодным; Codex scope может содержать `CLAUDE.md` вместо `AGENTS.md` | [03-start-finish-inject.md](./03-start-finish-inject.md) |
| P1 | `mainrule.mdc` требует читать `CLAUDE.md` даже в Codex, хотя current runtime rule требует читать только текущий entrypoint | Прямой cross-runtime prompt drift и лишнее чтение устаревших инструкций | [06-drift-and-contradictions.md](./06-drift-and-contradictions.md) |
| P1 | `.claude/settings.json` содержит двойное подключение одних и тех же symlinked hooks через `.claude/hooks` и `harness/hooks` | Каждый Claude hook запускается дважды; возможны двойные state writes, retry counters, race и duplicate logs | [06-drift-and-contradictions.md](./06-drift-and-contradictions.md) |
| P1 | Unified validator принимает gate/repair без явного поля `schema`, а SubagentStop принимает внешний `data.verdict` без JSON fence | Можно обойти требование machine JSON через hook payload; schema version фактически optional | [04-schemas-validation.md](./04-schemas-validation.md), [05-repair-and-verdict.md](./05-repair-and-verdict.md) |
| P1 | `finish_handoff()` остаётся low-level escape hatch, а phase-specific finish функции дублируют write/backup/state transitions | Есть путь записать Handoff и перевооружить state без полного verify/finalize pipeline; исправление partial failure не является транзакцией между activeContext и index/state | [03-start-finish-inject.md](./03-start-finish-inject.md) |
| P1 | Текущая ветка удаления `REFLECT` неполна | В baseline падают 15 тестов; `finish_reflect` всё ещё существует, но удалённые core helpers импортировать уже нельзя | [06-drift-and-contradictions.md](./06-drift-and-contradictions.md), [07-priority-roadmap.md](./07-priority-roadmap.md) |

## Что проверено

- canonical agent prompts и frontmatter всех 11 файлов в `harness/agents/*.md`;
- `harness/manifest.yaml`, `.codex/agents/*.toml`, runtime materializers и parity checker;
- Claude/Codex hooks, symlink topology, `SessionStart`, `SubagentStart`, `SubagentStop`, `Stop`, `loop.sh`;
- workflow indexes, role workflows, `_lean` gates, finish router/block, workflow pack registry и video pack;
- start/inject: `session-start.py → session_start_payload → build_prompt_scope → mb_load.load_session`;
- finish: `prepare → agent → check-after → mb-finish → render → finalize_step → stop`;
- boundary schemas, registry, Pydantic validation, sidecars, repair result, sunset result, Codex collab bridge;
- static literal `@` references и наличие referenced paths;
- `bin/runtime-sync --check` для Codex и Claude;
- полный тестовый baseline через `bin/pytest -q`.

## Baseline tests

На момент аудита:

```text
1931 passed, 3 skipped, 15 failed, 75 warnings
```

Падения связаны с текущими незавершёнными изменениями `T-HUB-060-remove-reflect-phase`: `finish_reflect` вызывает удалённый `find_reflection_artifact`, удалены reflection helpers, старые тесты ожидают REFLECT, а repo roadmap queue сейчас пуст. Это не было исправлено в рамках аудита, чтобы не перезаписывать пользовательский dirty worktree.

## Рекомендуемый порядок исправления

1. Восстановить консистентность текущей миграции `REFLECT`: либо завершить удаление из всех runtime/tests/docs, либо временно вернуть совместимые exports. Не оставлять смешанный контракт.
2. Исправить layout/reference resolver skills и добавить CI-проверку каждого literal `@` path.
3. Зарегистрировать sunset schema и подключить его к stop/sidecar validation либо удалить sunset machine contract целиком.
4. Сделать pack doctor, который проверяет не только `phase_registry` и `memory_bank`, но и все route rule paths, gates и verify agents.
5. Устранить duplicate Claude hooks и runtime-specific entrypoint drift.
6. Связать JSON record с `agent_id`, `epic_id`, `step_id`, `session_id`, parent gate evidence и expected phase.
7. После этого рефакторить start/finish в единую transaction/recovery boundary.

Подробный порядок, acceptance criteria и список того, что убрать, находится в [07-priority-roadmap.md](./07-priority-roadmap.md).
