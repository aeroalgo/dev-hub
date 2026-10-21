# dev-hub

## Runtime entrypoint

Используй только entrypoint текущего runtime:

- Claude Code → `CLAUDE.md`
- Codex → `AGENTS.md`
- DSH → `AGENTS.md` with native `read`/`write`/`edit` tools

Не читай другой runtime entrypoint.

## HARD READ RULE

До анализа, изменений и основной работы:

- **IMPLEMENT / TASK / BUGFIX / REFACTOR:** прочитай
  `.cursor/rules/shared/_lean/implement-bootstrap.mdc` и следуй его Read order
  (Gates → scope-lock → role `## Hot path` → shard). **Не** грузи
  `mainrule.mdc` monolith на старте code-phase.
- **PLAN / DECOMPOSE / VAN / прочие:** entrypoint → `.cursor/rules/mainrule.mdc`
  → выбранная role/mode chain с Gates и `@`-ссылками.

**EXCEPT Policy lazy:** не читай тела файлов из блока/строки `Policy lazy`
на старте только из-за `@` — только по trigger (см. `mainrule.mdc` §Full linked
chain / implement-bootstrap). На **DECOMPOSE** не читай тела Core/situational/Design
SKILL.md — только copy paths в step (`shared/_lean/decompose-skills-load.mdc`).

## Workflow router

По таблице router выбери текущую команду, роль и режим. Для code-phase — bootstrap;
иначе — role/mode chain и Gates.

Не загружай workflow или skills заранее и не выбирай другую роль или режим.
Пути и имена файлов определяются каноническими workflow, index и skills.

## Workflow-owned skills

Единственный skill-root этого workflow — локальный `.agents/skills/` репозитория
(в dev-hub он указывает на `harness/skills/`). Автоматический skills-каталог
Codex отключён в `.codex/config.toml`, поэтому его полный список не является
частью стартового prompt.

Загружай только конкретные локальные `SKILL.md`, явно указанные выбранной
role/mode chain или текущим shard (`skills.impl`, `skills.design`,
`skills.design_skills`, audit skills). Если workflow или shard не назвал
skill-путь, не загружай skills и не угадывай соседние. Явный запрос пользователя
или runtime на конкретный skill имеет приоритет.

Для DSH ссылки `@file` — это навигация, а не готовый system prompt: прочитай
entrypoint, выбери текущую фазу, затем последовательно прочитай только файлы
выбранной цепочки и явно перечисленные `SKILL.md`.

## Session context

Для role command используй `memory-bank/activeContext.md` и только текущие
пути из `load_now`. Не подменяй текущий shard другим epic или режимом.
Write `activeContext` — `.cursor/rules/token-economy-stub.mdc` §0.7.

## Context ledger and budget enforcement

- Context ledger: durable metadata tracking для Read/Edit решений (allow, cached-ref, duplicate deny, split, fail.closed).
- Read semantics: duplicate Read неизменённого диапазона запрещён; при изменении файла (hash mismatch) перечитывается только новый диапазон.
- Plan jump: IMPLEMENT/TASK/BUGFIX используют ограниченные `plan_jumps`, чтение whole plan запрещено.
- Search allowlist: поиск ограничен файлами шага (`files:`); расширенный поиск требует graphify receipt.
- Derived identity: root и subagent соблюдают единый контракт ledger и derived_identity без provider drift.

## Общие правила

- Отвечай пользователю на русском языке.
- В конце ответа указывай название модели ИИ.
- Исправляй причину ошибки, не скрывай её fallback-логикой.
- Коммиты и PR выполняй только по явному запросу.
- Комментарии в коде добавляй только по запросу.

## Root classification & Testing

- Hub (dev-hub self-test) / **BACK**: Python tests — `bin/pytest …` (300s встроен) или `timeout -k 10s 300s .venv/bin/pytest …`.
- **FRONT** (IMPLEMENT/TASK/QA): Vitest + Playwright (`timeout -k 10s 300s npm --prefix frontend exec vitest|playwright …`). **FORBIDDEN:** `bin/pytest` / backend pytest как FRONT suite.
- Managed projects: верификация через stack profile `capability_checks` и typed execution evidence; без generic fallback к raw pytest. Role surface сохраняется (front checks ≠ backend suite).
