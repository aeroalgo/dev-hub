# dev-hub

## Runtime entrypoint

Используй только entrypoint текущего runtime:

- Claude Code → `CLAUDE.md`
- Codex → `AGENTS.md`
- DSH → `AGENTS.md` with native `read`/`write`/`edit` tools

Не читай другой runtime entrypoint.

## HARD READ RULE

До анализа, изменений и основной работы прочитай только entrypoint текущего
runtime, затем `.cursor/rules/mainrule.mdc` и всю выбранную role/mode chain
с Gates и `@`-ссылками.

## Workflow router

По таблице router выбери текущую команду, роль и режим. Затем прочитай только
выбранную role/mode chain, её Gates и связанные `@`-ссылки.

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

## Session context

Для role command используй `memory-bank/activeContext.md` и только текущие
пути из `load_now`. Не подменяй текущий shard другим epic или режимом.

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

## Testing

Python tests запускай из корня репозитория через `bin/pytest …`.
