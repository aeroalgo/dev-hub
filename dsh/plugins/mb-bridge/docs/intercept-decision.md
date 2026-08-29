# Перехват запуска `task-board`

## Проверенная версия

Решение проверено по зафиксированному профилю DSH `epic-implement`:

- DSH-пакеты: `@deepseek-ai/dsh-*` `0.1.1-rc.2` (`dsh/profiles/epic-implement/package.json`, `pnpm-lock.yaml`);
- Cordis: `@deepseek-ai/cordis` `4.0.1` (`dsh/profiles/epic-implement/pnpm-lock.yaml`);
- опубликованные npm-версии на момент spike совпадают: DSH `0.1.1-rc.2`, Cordis `4.0.1`.

В доступном checkout нет установленного `node_modules`, исходников DSH/Cordis или API-документации, в которых был бы зарегистрирован публичный hook для stock `task-board` `kind:run`. В репозитории также не найдено подтверждения события `task-board/run`, `ctx.on(...)` либо другого стабильного interception hook. Поэтому нельзя считать Cordis-перехват подтверждённым только по наличию Cordis в lockfile.

## Выбранный путь

**Path B — Host-route fallback.**

Основание: для версии DSH `0.1.1-rc.2` и Cordis `4.0.1` в проверяемых артефактах отсутствует подтверждённый публичный API, который надёжно перехватывает stock `task-board` run. Использование неподтверждённого имени события создало бы silent defer и зависимость от внутренностей DSH.

Перехват выполняется через Host API endpoint:

```text
POST /api/mb-bridge/action
```

Stock run prompt для mb-* карточек должен быть отключён/заменён на объявление bridge в plugin mount. Реализация endpoint, mount и UI-поведения относится к **s08**; этот shard фиксирует только решение и контракт направления.

## Path A — отвергнут

Path A требовал бы подтверждённого Cordis hook, например условного `ctx.on('task-board/run', handler)`. Такой hook в текущем checkout и зафиксированных пакетах не обнаружен, поэтому skeleton не должен притворяться рабочим Cordis interceptor.

## Path B — контракт для s08

1. Plugin mount регистрирует bridge action для mb-* карточек.
2. Host принимает `POST /api/mb-bridge/action` и передаёт действие в board/loop bridge.
3. Запуск stock `task-board` для этих карточек не должен показывать обычный stock run prompt.
4. Ошибка Host API должна быть явной и fail-closed; fallback на неподтверждённый Cordis hook запрещён.

Ссылки на локальные артефакты: `dsh/profiles/epic-implement/package.json`, `dsh/profiles/epic-implement/pnpm-lock.yaml`, `dsh/README.md`.
