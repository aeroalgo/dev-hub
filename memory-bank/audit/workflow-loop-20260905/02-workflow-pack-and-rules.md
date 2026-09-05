# 02. Аудит workflow packs, rules и путей

## 1. Сильная часть текущей конструкции

У software pack есть понятная иерархия:

```text
entrypoint → .cursor/rules/mainrule.mdc → role index → role core
          → workflow-{mode}.mdc → Gates/_lean/{mode}.mdc → @-ссылки
```

Workflow разделены на BACK/FRONT/INTEG, а общие части вынесены в `shared`. В workflow явно зафиксированы `load_now`, scope lock, TDD, `deletes`, `validate-step`, `@verify`, `finalize-step` и graphify. Это хороший foundation.

## 2. Размер и распределение

На snapshot найдено примерно 52 role/shared `workflow-*.mdc` файла. Самые тяжёлые shared workflow:

| Файл | Строк | Риск |
|---|---:|---|
| `shared/workflow-legacy-fallback-cleanup.mdc` | 260 | много policy в одном документе |
| `shared/workflow-behavior-first.mdc` | 230 | высокая стоимость чтения и drift между ссылками |
| `shared/workflow-idea-pipeline.mdc` | 205 | смешивает архивные роли, pipeline и routing |
| `shared/workflow-implement-scope-lock.mdc` | 75 | полезный компактный boundary |

Проблема не в том, что правила подробные. Проблема в отсутствии machine-readable dependency graph и автоматической проверки всех ссылок. Сейчас агент должен сам рекурсивно читать `@`-ссылки, но система не гарантирует, что каждое имя реально разрешается.

## 3. P0 — неправильный layout skills

Workflow ссылаются на:

```text
.agents/skills/tdd/SKILL.md
.agents/skills/writing-plans/SKILL.md
.agents/skills/grill-me/SKILL.md
```

Symlink `.agents/skills` указывает на `harness/skills`, а фактические файлы находятся в:

```text
.agents/skills/skills/tdd/SKILL.md
.agents/skills/skills/writing-plans/SKILL.md
```

То есть ссылка из workflow не разрешается. Это системная ошибка topology, а не несколько опечаток.

Варианты исправления:

- лучший: сделать `harness/skills/<name>/SKILL.md` каноническим путём и убрать лишний вложенный `skills/`;
- переходный: добавить resolver, который canonicalizes обе формы, но в generated artifacts писать только одну форму;
- обязательно: static check literal `@` paths и test на каждый path из `skills.impl`.

Fallback через “попробуй другой путь” не должен скрывать ошибку: если canonical path неверен, workflow должен остановиться с diagnostic code.

## 4. P0 — video-production pack не маршрутизируется в реальные rules

Registry объявляет:

```yaml
roles: [script, visual, post]
command_prefixes: [SCRIPT, VISUAL, POST]
rules_root: .cursor/rules/video
```

`route_command()` по этому контракту строит:

| Команда | Построенный путь | Факт |
|---|---|---|
| `SCRIPT PLAN` | `.cursor/rules/video/script_developer/workflow-plan.mdc` | отсутствует |
| `SCRIPT DECOMPOSE` | `.cursor/rules/video/script_developer/workflow-decompose.mdc` | отсутствует |
| `VISUAL STORYBOARD` | `.cursor/rules/video/visual_developer/workflow-storyboard.mdc` | отсутствует |
| `POST EDIT` | `.cursor/rules/video/post_developer/workflow-edit.mdc` | отсутствует |
| `POST PUBLISH` | `.cursor/rules/video/post_developer/workflow-publish.mdc` | отсутствует |

Реально в `harness/cursor/rules/video` лежат только общий `workflow-plan`, `workflow-implement`, `workflow-qa` и `_lean` файлы. Поэтому `resolve_workflow_pack()` возвращает pack, но command route не получает executable rule.

Исправить нужно не fallback-логикой в router, а контрактом pack:

1. либо привести filesystem к role-subdirectory convention;
2. либо добавить в pack явную `route_map` (`SCRIPT PLAN → video/workflow-plan.mdc` и т. д.);
3. `full_resolve()` обязан проверять все команды из intent pipelines и phase registry;
4. doctor должен падать с `pack_route_missing`, даже если `phase_registry` и `memory_bank` существуют.

## 5. P1 — `full_resolve()` проверяет слишком мало

`loop/workflow/resolve.py` валидирует только:

- `phase_registry` как файл;
- `memory_bank` как директорию.

Не проверяются:

- `rules_root`;
- role index/core;
- workflow files для всех phase/command;
- `_lean` gate для каждого mode;
- verify agent из phase registry;
- tool-gate adapters из `external_gates`;
- intent pipeline commands;
- artifact layout templates.

В результате pack может быть `ok=True`, а путь исполнения фактически пустой. Нужны два результата:

```text
resolve metadata → validate executable pack graph → usable=true/false
```

## 6. P1 — условный fallback в registry скрывает битый project.yaml

`_read_project_yaml_pack()` ловит любой `Exception` и возвращает `None`. Если `project.yaml` повреждён или содержит malformed YAML, система незаметно переходит к env/default pack. Для orchestration это опасно: пользователь думает, что выбрал один pack, а loop запускает другой.

Рекомендация: различать `file_missing` и `file_invalid`. При наличии файла с ошибкой YAML — `invalid_workflow_pack_config`, fail-closed; fallback разрешать только когда файл отсутствует.

## 7. P1 — отсутствует `_lean/janitor.mdc`

BACK index содержит `BACK JANITOR`, но в `back_developer/isolation_rules/_lean` нет `janitor.mdc`; есть workflow `workflow-janitor.mdc`. Это не обязательно ошибка, если JANITOR намеренно не gate mode, но сейчас правило не объясняет исключение.

Нужно либо:

- добавить `isolation_rules/_lean/janitor.mdc` и объявить Gates в workflow;
- либо удалить JANITOR из role index/command contract или явно пометить `no-gate by design`.

## 8. P1 — архивные роли всё ещё участвуют в literal dependency graph

`mainrule.mdc` маркирует PM/TL/CONTENT/MARKETING/SEO как archived, но `shared/workflow-idea-pipeline.mdc` содержит ссылки на `project_manager`, `content_growth`, `marketing_growth`, `seo_ops`, которых нет в текущем `.cursor/rules`.

Если archive — только историческая документация, она не должна быть достижима через active `@` chain. Перенести её в `_archive` без активных ссылок либо заменить ссылки на существующий `workflow-idea-pipeline` contract.

## 9. Workflow contracts: что усилить

### Усилить

- schema каждого artifact и exact path;
- semantic validator для coverage, outcome map, replacement cleanup;
- correlation `plan_id/epic_id/step_id/role/pack_id` на каждом переходе;
- явный allowed next-state в phase registry;
- negative acceptance criteria, а не только “Done When”;
- one command → one route → one gate → one finish handler;
- static graph check в `doctor` и CI.

### Убрать

- ручные инструкции, которые повторяют canonical table из другого файла;
- active links в архивные role packs;
- fallback, который silently меняет pack/path;
- “прочитай все связанные файлы рекурсивно”, если dependency graph можно сгенерировать заранее;
- `.md` terminology для decompose/implement там, где canonical layout уже YAML.

## 10. Acceptance criteria

- `route_command()` для каждой команды из intent routing возвращает существующий path;
- каждый returned workflow имеет существующий Gate или documented exception;
- `full_resolve()` с intentionally broken `rules_root`, agent и route возвращает fail-closed diagnostics;
- zero broken canonical skill refs;
- archived references не попадают в active rule graph;
- video pack проходит тот же parity matrix, что и software pack.
