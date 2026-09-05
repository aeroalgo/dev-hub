# dev-hub

## Runtime entrypoint

Используй только entrypoint текущего runtime:

- Claude Code → `CLAUDE.md`
- Codex → `AGENTS.md`

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

## Session context

Для role command используй `memory-bank/activeContext.md` и только текущие
пути из `load_now`. Не подменяй текущий shard другим epic или режимом.

## Общие правила

- Отвечай пользователю на русском языке.
- В конце ответа указывай название модели ИИ.
- Исправляй причину ошибки, не скрывай её fallback-логикой.
- Коммиты и PR выполняй только по явному запросу.
- Комментарии в коде добавляй только по запросу.

## Testing

Python tests запускай из корня репозитория через `bin/pytest …`.
