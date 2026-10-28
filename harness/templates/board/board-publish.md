# Публикация задач на доску после PLAN

## Правило

После **BACK PLAN** / **FRONT PLAN** (есть `plan.md` + `prompt.md` с `## Board`)
сразу опубликовать карточки на Bitrix — не ждать DECOMPOSE/IMPLEMENT.

## Кто на карточке

Файл `.loop/board-actors.yaml`: актёр = постановщик и исполнитель.
Ключи `actors.*` и маппинг `epics.<id>: <actor_key>`.

## Команда

```bash
./scripts/board-sync.sh --all
# или
./scripts/board-sync.sh <epic-id> [epic-id...]
```

Текст карточки — из `## Board` в `prompt.md` (простой язык: что / зачем / стадии / результат).

## Описание Board

1. Что делаем  
2. Зачем  
3. Стадии реализации  
4. Результат для наблюдателя  

Без внутренних ID эпиков в title/summary (их подставит loop).

## Не путать

- `board-sync` / `scripts/board-sync.sh` — карточка задачи  
- `board-docs` — вложения plan/prompt  
- авто `loop finish` использует только `.env` `BITRIX_RESPONSIBLE_ID`; для нужного актёра после PLAN зови `scripts/board-sync.sh`
