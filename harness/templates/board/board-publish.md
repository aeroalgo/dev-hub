# Публикация задач на доску после PLAN / BUGFIX

## Правило

После **BACK PLAN** / **FRONT PLAN** (есть `plan.md` + `prompt.md` с `## Board`)
сразу опубликовать карточки на Bitrix — не ждать DECOMPOSE/IMPLEMENT.

После **BUGFIX** / «закинь на доску»: **без файлов** — только CLI
`--title` / `--summary` / `--phase DONE`. Отчёт bugfix (если нужен) — отдельно;
доска от него не зависит.

## Кто на карточке

Файл `.loop/board-actors.yaml`: актёр = постановщик и исполнитель.

## Команда

```bash
./scripts/board-sync.sh <epic-id>
```

Закрытый bugfix:

```bash
BITRIX_RESPONSIBLE_ID=<uid> \
  python3 "$(cat .dev-hub)/bin/loop.py" board-sync \
  --project "$PWD" --epic <bugfix-slug> --role back --phase DONE \
  --title "Bugfix: …" --summary "…" --json
```

**FORBIDDEN** создавать `prompt.md` / `plan/` только ради ad-hoc board-sync.
