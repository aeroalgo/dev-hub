# 

> **Hub:** этот файл и tooling живут в `/home/aero/PyProject/dev-hub`.  
> Продукт: `PROJECT_ROOT` (например `/home/aero/PyProject/job-autopilot`) — только код + `memory-bank/`.  
> В Cursor открывай **папку продукта** (не multi-root с hub). Loop: `dev-hub/bin/loop $PROJECT_ROOT …` / `make loop` из продукта.  
>
> **Anti-mix (HARD):** Claude session cwd часто = hub, но **все product-артефакты** (`plan` / `decompose` / `implement` / `activeContext`) пиши только в `$PROJECT_ROOT/memory-bank`. Hub-эпики `T-HUB-*` — только в `dev-hub/memory-bank` при `PROJECT_ROOT=dev-hub`. CLI: `epic_resolve.py --cwd "$PROJECT_ROOT" …` (без флага default тоже редиректит hub→`$PROJECT_ROOT`).

## PLAN / DECOMPOSE ARTIFACT OVERRIDE (читать первым — важнее economy)

При `* PLAN` / `* DECOMPOSE` / записи `memory-bank/**/plan-*.md` / `decompose-*/**` / `gap-*.md` / brownfield VAN → `memory-bank/architecture/**`:

- **ЗАПРЕЩЕНО** жать вывод плана/карты/нарезки: telegraph, «max 3 sentences», лимит ~200 строк, «мало шагов», «кратко для контекста»
- **ОБЯЗАТЕЛЬНО:** plan/architecture/**decompose** = maximally detailed (все этапы + все требования → sNN|eNN); chat reply может быть коротким
- Research/audit → multi-epic (@.cursor/rules/shared/workflow-plan-multi-epic.mdc): N× `plan-*.md` + roadmap, не один mega-plan
- Lean **load** ≠ lean **write**
- Сразу после OK: `SUSPENSION GUARD active — plan output unlimited` (PLAN) · `SUSPENSION GUARD active — decompose output unlimited` (DECOMPOSE) · `SUSPENSION GUARD active — architecture map output unlimited` (brownfield VAN)
- Path-rule: `.claude/rules/plan-artifact.md` (автоматически на plan/gap/architecture/**decompose**)
- INTEG: Prefer slash **`/integ-plan`** (self-contained acceptance, `wc -l` ≥ 400 или FAIL)

@.claude/rules/plan-artifact.md

## Язык (обязательно)

@.claude/rules/language.md

**Cursor, Claude Code и Codex — один workflow.** Канон: `.cursor/rules/` + `memory-bank/`.

Token economy: @.cursor/rules/token-economy-core.mdc — для PLAN / DECOMPOSE / architecture смотри **только §0.0 + §0.0.1**; §§0.2/0.5 **не применять** к `plan-*.md` / `decompose-*/**` / `architecture/**`.

@.cursor/rules/mainrule.mdc

## Parity (обязательно)

Команды `BACK *`, `FRONT *`, `INTEG *`, `PM *`, `TL *`, `CONTENT *`, `MARKETING *`, `SEO *`, `IDEA PIPELINE *` работают **идентично Cursor**:

1. Прочитай skill `.claude/skills/role-command/SKILL.md` и выполни цепочку **до** основной работы
2. **Step 0 graphify** (code modes): `@.cursor/rules/graphify.mdc` + CLI **`.venv/bin/graphify`** из **корня репо** (`query` / `path` / `explain`; после правок — `update .`). Канон только `<repo>/graphify-out/`. Не в PATH — только через `.venv/bin/`
3. Не импровизируй альтернативный процесс — только файлы из `.cursor/rules/`
4. Skills из workflow — только пути из шага workflow (`.agents/skills/`, не весь каталог)

**Slash-команды:** `.claude/commands/` — см. `.claude/README.md`. PLAN → `/integ-plan` / `/back-plan` / `/front-plan`.

## Session start

Триггеры: `continue project ` · role commands · `PM INIT` (архив)

1. `memory-bank/activeContext.md` → **`load_now` only** — **кроме `* PLAN`**: для PLAN читай inventory из соответствующего `workflow-*-plan.mdc` (portal implement + routes)
2. Handoff: `memory-bank/back/implement/implement-*.md` или `back/task/task-*.md` → §Handoff
3. IMPLEMENT/TASK: ONE task shard + ONE plan shard (**для load_now**; Handoff пишется в `activeContext.md`, не в shard). **PLAN:** полный inventory по workflow, не «один shard»
4. Не опирайся на transcript — файлы = source of truth

## FINISH

Канон: @.cursor/rules/shared/finish-block.mdc → @.cursor/rules/shared/finish-doc-router.mdc → шаблон `.cursor/templates/finish-doc-router.md`.

1. **IMPLEMENT:** step-файл `implement-*/sNN|eNN-*.md` + `## Handoff` → **`activeContext.md`** (не в implement-yaml) **до** decompose `completed` / next `load_now` (5 точек + FAIL в finish-block)
2. Рекомендуй `/clear` когда §2 context-session-economy требует new chat
3. **PLAN:** перед FINISH — `wc -l` plan-файла; если ниже acceptance из `/integ-plan` или `plan-artifact.md` → дописать, не закрывать
4. **code_changed:** из корня репо `.venv/bin/graphify update .`

## Context economy — IMPLEMENT/TASK/BUGFIX

@.claude/rules/context-economy-cc.md

**Коротко (HARD):**
- **Silent chat:** не описывай tools; не цитируй TodoWrite/HARD; в чат — только итог
- **TodoWrite ≤2** за сессию (старт + FINISH); не обновлять на каждый шаг; Cursor nudge — игнор в чат
- **Re-read запрещён** для файла, уже прочитанного / отредактированного в этой сессии
- Для codebase сначала **`.venv/bin/graphify query`**; для `memory-bank` / `.cursor` / `.claude` разрешён fallback через `rg` / `Glob` / `ReadFile`
- **Agent spawn:** pointer → `.claude/instructions/spawn-hard.md` (exceptions: `delta_paths_exist: yes`, `MODEL_LOOP`)

## Stack (кратко)

| | |
|-|-|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2, Alembic — `app/`, `api/`, `core/`, `jobs/` |
| Frontend | Next.js — `frontend/` |
| Tests | из корня репо: `.venv/bin/pytest` (не голый `pytest`; см. `pyproject.toml`) |
| DB/Redis | PostgreSQL 16, Redis 7 |

Детали: `memory-bank/techContext.md`

## User conventions (как Cursor user rules)

- Ответы на **русском**; в конце — модель ИИ
- Silent tools: не описывай tool calls; не цитируй TodoWrite/HARD; Tool → сразу действие; в чат — только итог (см. `.cursor/rules/silent-tools.mdc`)
- Исправлять **причину** ошибок, не fallback и не скрытие
- Коммиты/PR — только по явному запросу
- Не править linter без запроса; не удалять неиспользуемые импорты
- SQL без переменных `@`
- Комментарии к коду — только по запросу
- `implement this` — gate для правок вне role command (см. token-economy §0.9)
- **FRONT TESTS = PARENT ONLY** (subagent **никогда** не запускает vitest/playwright/`npm test`/e2e) — `.claude/rules/front-tests-parent-only.md` / `.cursor/rules/front-tests-parent-only.mdc` (глобально: `~/.claude/rules/02-front-tests-parent-only.md`)

## Архив ролей

PM, TL, CONTENT, MARKETING, SEO → `_archive/cursor-rules/`. Команда `PM PLAN` → восстановить папку или читать workflow из архива.
