# Публикация задач на доску после PLAN / BUGFIX

## Правило

После **BACK PLAN** / **FRONT PLAN** / **APP PLAN** (есть `plan.md` + `prompt.md` с `## Board`)
сразу опубликовать карточки на Bitrix — не ждать DECOMPOSE/IMPLEMENT.

После **BUGFIX** / «закинь на доску»: **без файлов** — только CLI
`--title` / `--summary` / `--phase DONE`. Отчёт bugfix (если нужен) — отдельно;
доска от него не зависит.

## Какой id передавать (HARD)

Только полный `epic_id` = имя папки `memory-bank/<role>/plan/<epic_id>/`.
Короткий roadmap `id:` (например `T-NF-005`) без разрешения в full → карточка
без человеческого Board. `scripts/board-sync.sh` может resolve short→full
через `queue.yaml`, но канон — передавать full id.

## Кто на карточке

Файл `.loop/board-actors.yaml`: актёр = постановщик и исполнитель.

## Команда

```bash
./scripts/board-sync.sh <full-epic-id>
```

Скрипт сам передаёт `--title`/`--summary` из `## Board` (обязательно для
обновления текста существующей карточки).

Закрытый bugfix:

```bash
BITRIX_RESPONSIBLE_ID=<uid> \
  python3 "$(cat .dev-hub)/bin/loop.py" board-sync \
  --project "$PWD" --epic <bugfix-slug> --role back --phase DONE \
  --title "Bugfix: …" --summary "…" --json
```

## Описание Board

1. Простой русский абзац (без ярлыка «Для людей»)  
2. Зачем это бизнесу  
3. Технически (ниже)

Без внутренних ID в title/summary.

**FORBIDDEN** создавать `prompt.md` / `plan/` только ради ad-hoc board-sync.
