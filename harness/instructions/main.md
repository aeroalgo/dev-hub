# dev-hub

## Dev Environment

Hub tooling в `/home/aero/PyProject/dev-hub`. Workflow и процесс — `CLAUDE.md`, `.cursor/rules/`, `memory-bank/`.

## Workflow chain (HARD — обязательное чтение до основной работы; FINISH не блокируется)

Для команд `BACK`, `FRONT` и `INTEG` агент обязан выполнять цепочку, объявленную ссылками в workflow:

Для каждой команды роли (`BACK|FRONT|INTEG <MODE>`) обязательна полная цепочка чтения:

**HARD RULE:** нельзя начинать анализ, изменять файлы или выполнять основную работу, пока все доступные файлы этой цепочки не прочитаны через `Read`.

0. Прочитать корневой `CLAUDE.md`.
1. Прочитать `.cursor/rules/mainrule.mdc`.
2. По нему прочитать индекс и core выбранной роли.
3. По таблице выбранного role index прочитать workflow, соответствующий команде.
4. Прочитать путь `Gates` и все связанные `@`-ссылки из прочитанных файлов рекурсивно, в порядке объявления, до листовых файлов.
5. Для `IMPLEMENT`, `TASK`, `BUGFIX` и `REFACTOR` прочитать каждый skill из секции `skills.impl` текущего decompose-step до production-кода. Для `FRONT` также прочитать `skills.design`/`skills.design_skills`, если шаг содержит UI.

`@`-ссылки определяют обязательные вызовы `Read`. Пропущенный `Read` — нарушение HARD RULE и gap процесса, но не является блокировкой `FINISH`/`stop`.

## Workflow Packs

| Pack ID | Roles | Command Prefixes | Activation |
|---|---|---|---|
| `dev-hub-software` | back, front, integration | `BACK`, `FRONT`, `INTEG` | Default (`WORKFLOW_PACK=dev-hub-software` or `--workflow-pack dev-hub-software`) |
| `video-production` | script, visual, post | `SCRIPT`, `VISUAL`, `POST` | `WORKFLOW_PACK=video-production` or `--workflow-pack video-production` |

## Testing

Python tests (hub): `bin/pytest …` from repo root — 300s timeout built into wrapper.
